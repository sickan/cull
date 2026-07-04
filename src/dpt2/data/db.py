"""SQLite-anslutning + schema-applicering för dpt2-datalagret.

Enkelt och beroendefritt (bara stdlib `sqlite3`). Schemaversionen spåras via
`PRAGMA user_version`; `init_db` applicerar `schema.sql` första gången och är
idempotent. Tunga binärer (modell-pickles, feature-vektorer i .npz) ligger som
filer — DB:n lagrar sökvägar, inte blobbar.
"""

import sqlite3
from pathlib import Path

# Schemaversion. Höj vid migrering och lägg migreringssteg i _migrera().
SCHEMA_VERSION = 11

# Standardplats för datalagret. Eget config-träd så gamla dpt rörs inte.
DB_DEFAULT = Path.home() / ".config" / "dpt2" / "dpt.db"

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _schema_sql():
    return _SCHEMA_PATH.read_text(encoding="utf-8")


def oppna(path=DB_DEFAULT, *, init=True, check_same_thread=True):
    """Öppnar (och skapar) databasen. Sätter FK-tvång och Row-factory.

    path : sökväg till .db-filen (skapas inkl. föräldrakatalog vid behov).
    init : kör init_db automatiskt (default). Sätt False för en rå anslutning.
    check_same_thread : False när anslutningen delas mellan trådar (t.ex.
        pywebview-bryggan som anropas från JS-tråden).
    """
    path = Path(path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if init:
        init_db(conn)
    return conn


def schemaversion(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def init_db(conn):
    """Applicerar schemat om databasen är tom/äldre. Idempotent.

    Returnerar True om något applicerades, annars False.
    """
    v = schemaversion(conn)
    if v == SCHEMA_VERSION:
        return False
    if v == 0:
        # Färsk databas: lägg in hela schemat.
        conn.executescript(_schema_sql())
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return True
    if v < SCHEMA_VERSION:
        _migrera(conn, v)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return True
    # v > SCHEMA_VERSION: databasen är nyare än koden.
    raise RuntimeError(
        f"Databasens schemaversion {v} är nyare än kodens {SCHEMA_VERSION}. "
        "Uppdatera dpt2.")


def _migrera(conn, fran_version):
    """Inkrementella migreringssteg. Varje steg är additivt och idempotent."""
    if fran_version < 2:
        # v2: per-bild-urval (vilka bilder gallringen behöll).
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS urval_bild (
          urval_id TEXT NOT NULL REFERENCES urval(id) ON DELETE CASCADE,
          stem     TEXT NOT NULL,
          behall   INTEGER NOT NULL DEFAULT 0,
          poang    REAL,
          PRIMARY KEY (urval_id, stem)
        );""")
    if fran_version < 3:
        # v3: tävling.hemsida, lag Individ-stöd (kind/profilfarg/klubb),
        # tavling_lag-relation (tävling äger sina lag). Additivt.
        for kol, ddl in (
            ("hemsida", "ALTER TABLE tavling ADD COLUMN hemsida TEXT"),
        ):
            if not _har_kolumn(conn, "tavling", kol):
                conn.execute(ddl)
        for kol, ddl in (
            ("kind", "ALTER TABLE lag ADD COLUMN kind TEXT NOT NULL DEFAULT 'team'"),
            ("profilfarg", "ALTER TABLE lag ADD COLUMN profilfarg TEXT"),
            ("klubb", "ALTER TABLE lag ADD COLUMN klubb TEXT"),
        ):
            if not _har_kolumn(conn, "lag", kol):
                conn.execute(ddl)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tavling_lag (
          tavling_id TEXT NOT NULL REFERENCES tavling(id) ON DELETE CASCADE,
          lag_id     TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
          PRIMARY KEY (tavling_id, lag_id)
        );""")
    if fran_version < 4:
        # v4: lagets trupp-källa ("från hemsida" / "CSV" / "bild" / "PDF").
        if not _har_kolumn(conn, "lag", "trupp_kalla"):
            conn.execute("ALTER TABLE lag ADD COLUMN trupp_kalla TEXT")
    if fran_version < 5:
        # v5: lokalt fotojobb-utkast (tävling → "Lägg i Google Calendar") som
        # väntar på att fotografen kategoriserar och aktiverar synk manuellt —
        # pushas ALDRIG till Calendar Sync-tjänsten förrän det uttryckligen görs.
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fotojobb_utkast (
          id         TEXT PRIMARY KEY,
          tavling_id TEXT UNIQUE REFERENCES tavling(id) ON DELETE CASCADE,
          title      TEXT NOT NULL,
          start_at   TEXT NOT NULL,
          end_at     TEXT NOT NULL,
          all_day    INTEGER NOT NULL DEFAULT 1,
          location   TEXT,
          category   TEXT,
          skapad     TEXT NOT NULL
        );""")
    if fran_version < 6:
        # v6: publicerad hemsideslänk per match ("Efter match · länkar",
        # tillsammans med den befintliga galleri/Pixieset-URL:en).
        if _har_tabell(conn, "matchen") and not _har_kolumn(conn, "matchen", "sida_url"):
            conn.execute("ALTER TABLE matchen ADD COLUMN sida_url TEXT")
    if fran_version < 7:
        # v7: fotojobb → match-koppling ("Koppla till match" när kategori=Sport).
        # Lokal länktabell — fristående från Calendar Sync-tjänsten, som inte
        # känner till matcher. fotojobb_id är antingen ett utkasts id
        # (fotojobb_utkast) eller tjänstens jobb-id, samma textnyckel-rymd.
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fotojobb_match (
          fotojobb_id TEXT PRIMARY KEY,
          match_id    TEXT NOT NULL REFERENCES matchen(id) ON DELETE CASCADE
        );""")
    if fran_version < 8:
        # v8: gren (dam/herr/mixed) på lag OCH tävling + sport på LAGET —
        # landslag som "Sverige" är olika poster per sport (Sverige Volleyboll
        # ≠ Sverige Handboll). Additivt; store normaliserar värdena.
        for tabell, kol, ddl in (
            ("lag", "sport", "ALTER TABLE lag ADD COLUMN sport TEXT"),
            ("lag", "gren", "ALTER TABLE lag ADD COLUMN gren TEXT"),
            ("tavling", "gren", "ALTER TABLE tavling ADD COLUMN gren TEXT"),
        ):
            if not _har_kolumn(conn, tabell, kol):
                conn.execute(ddl)
    if fran_version < 9:
        # v9: Publicera-panelens "Sparade material" — utkast + publicerat
        # arbetsyta (skilt från some_material, som bara loggar faktiskt
        # utgångna poster).
        conn.execute("""
        CREATE TABLE IF NOT EXISTS publicera_material (
          id         TEXT PRIMARY KEY,
          kind       TEXT NOT NULL CHECK (kind IN ('live','some')),
          match_id   TEXT REFERENCES matchen(id) ON DELETE SET NULL,
          match_namn TEXT,
          status     TEXT NOT NULL CHECK (status IN ('utkast','publicerad')),
          moment     TEXT,
          tema       TEXT,
          channels   TEXT,
          caption    TEXT,
          uppdaterad TEXT NOT NULL
        );""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pubmat_uppdaterad "
            "ON publicera_material(uppdaterad DESC);")
    if fran_version < 10:
        # v10: spara vald bild med utkastet — utan den var "Fortsätt" på ett
        # sparat material meningslös (bytte moment/tema men förhandsvisningen
        # förblev tom eftersom bildvalet aldrig persisterades).
        for kol, ddl in (
            ("dropbox", "ALTER TABLE publicera_material ADD COLUMN dropbox TEXT"),
            ("foto", "ALTER TABLE publicera_material ADD COLUMN foto TEXT"),
            ("banor", "ALTER TABLE publicera_material ADD COLUMN banor TEXT"),
        ):
            if not _har_kolumn(conn, "publicera_material", kol):
                conn.execute(ddl)
    if fran_version < 11:
        # v11: "Delvis publicerad" (per-kanal-resultat) + publiceringshistorik.
        # status-CHECK måste utökas med 'delvis' — SQLite tillåter inte att en
        # CHECK ändras på en befintlig tabell, så den skrivs om (leaf-tabell,
        # inget refererar till publicera_material via FK).
        if not _har_kolumn(conn, "publicera_material", "ch_results"):
            conn.executescript("""
            CREATE TABLE publicera_material_ny (
              id         TEXT PRIMARY KEY,
              kind       TEXT NOT NULL CHECK (kind IN ('live','some')),
              match_id   TEXT REFERENCES matchen(id) ON DELETE SET NULL,
              match_namn TEXT,
              status     TEXT NOT NULL CHECK (status IN ('utkast','publicerad','delvis')),
              moment     TEXT,
              tema       TEXT,
              dropbox    TEXT,
              foto       TEXT,
              channels   TEXT,
              caption    TEXT,
              banor      TEXT,
              ch_results TEXT,
              uppdaterad TEXT NOT NULL
            );
            INSERT INTO publicera_material_ny
              (id,kind,match_id,match_namn,status,moment,tema,dropbox,foto,
               channels,caption,banor,uppdaterad)
              SELECT id,kind,match_id,match_namn,status,moment,tema,dropbox,foto,
                     channels,caption,banor,uppdaterad
              FROM publicera_material;
            DROP TABLE publicera_material;
            ALTER TABLE publicera_material_ny RENAME TO publicera_material;
            CREATE INDEX IF NOT EXISTS idx_pubmat_uppdaterad
              ON publicera_material(uppdaterad DESC);
            """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS publicera_material_historik (
          id          TEXT PRIMARY KEY,
          material_id TEXT NOT NULL REFERENCES publicera_material(id) ON DELETE CASCADE,
          tid         TEXT NOT NULL,
          status      TEXT NOT NULL CHECK (status IN ('publicerad','delvis')),
          note        TEXT
        );""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pubmathist_material "
            "ON publicera_material_historik(material_id, tid DESC);")


def _har_kolumn(conn, tabell, kolumn):
    return any(r[1] == kolumn
               for r in conn.execute(f"PRAGMA table_info({tabell})"))


def _har_tabell(conn, tabell):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (tabell,)).fetchone() is not None


def tabeller(conn):
    """Lista skapade tabeller (för test/inspektion)."""
    rader = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r[0] for r in rader]


if __name__ == "__main__":
    # Snabbtest: skapa en temporär DB och rapportera.
    import sys
    mål = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(":memory:")
    c = oppna(mål)
    print(f"Schemaversion: {schemaversion(c)}")
    print(f"Tabeller ({len(tabeller(c))}):")
    for t in tabeller(c):
        print("  -", t)
    # FK-integritet ska vara ren.
    problem = c.execute("PRAGMA foreign_key_check").fetchall()
    print("FK-problem:", problem or "inga")
