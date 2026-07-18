"""SQLite-anslutning + schema-applicering för dpt2-datalagret.

Enkelt och beroendefritt (bara stdlib `sqlite3`). Schemaversionen spåras via
`PRAGMA user_version`; `init_db` applicerar `schema.sql` första gången och är
idempotent. Tunga binärer (modell-pickles, feature-vektorer i .npz) ligger som
filer — DB:n lagrar sökvägar, inte blobbar.
"""

import sqlite3
import threading
from pathlib import Path

# Schemaversion. Höj vid migrering och lägg migreringssteg i _migrera().
SCHEMA_VERSION = 36

# Standardplats för datalagret. Eget config-träd så gamla dpt rörs inte.
DB_DEFAULT = Path.home() / ".config" / "dpt2" / "dpt.db"

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _schema_sql():
    return _SCHEMA_PATH.read_text(encoding="utf-8")


class _SafeCursor:
    """Tunt cursor-omslag — varje fetch serialiseras med samma lås som
    skapade cursorn (se SafeConnection). Bara fetch/iteration omsluts;
    raderna som kommer ut (sqlite3.Row) är oförändrade och trådsäkra att
    läsa efteråt."""
    __slots__ = ("_cur", "_lock")

    def __init__(self, cur, lock):
        object.__setattr__(self, "_cur", cur)
        object.__setattr__(self, "_lock", lock)

    def fetchall(self):
        with self._lock:
            return self._cur.fetchall()

    def fetchone(self):
        with self._lock:
            return self._cur.fetchone()

    def fetchmany(self, size=None):
        with self._lock:
            return self._cur.fetchmany() if size is None else self._cur.fetchmany(size)

    def __iter__(self):
        return self

    def __next__(self):
        with self._lock:
            row = self._cur.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __getattr__(self, name):
        return getattr(self._cur, name)


class SafeConnection:
    """Serialiserar allt bruk av en delad sqlite3.Connection med ett lås.

    pywebviews JS-brygga kan anropa Api-metoder från flera trådar samtidigt
    (self.conn öppnas med check_same_thread=False för att tillåta just det),
    men en enda sqlite3.Connection är INTE trådsäker för samtidiga anrop från
    flera trådar — check_same_thread=False stänger bara av Pythons EGEN
    trådaffinitetskontroll, inte samtidighetssäkerheten i C-nivå-anropen.
    Utan ett lås observerades intermittent `sqlite3.InterfaceError`/
    `IndexError` OCH tystare fall där två samtidiga `hamta_match`-liknande
    anrop läste ihopblandade rader (bekräftat: databasen på disk förblev
    korrekt, bara det tillfälliga Python-objektet blandades ihop) — se
    projektminnet för detaljer. Låset omsluter bara den faktiska DB-
    operationen (execute/fetch/commit), ALDRIG en hel Api-metod — annars
    skulle en långsam nätverksanrop (t.ex. Bildsvepets Claude-generering,
    ~2 min) blockera alla andra paneler under tiden."""

    def __init__(self, conn):
        self._conn = conn
        self._lock = threading.RLock()

    def execute(self, *a, **kw):
        with self._lock:
            cur = self._conn.execute(*a, **kw)
        return _SafeCursor(cur, self._lock)

    def executemany(self, *a, **kw):
        with self._lock:
            cur = self._conn.executemany(*a, **kw)
        return _SafeCursor(cur, self._lock)

    def executescript(self, *a, **kw):
        with self._lock:
            return self._conn.executescript(*a, **kw)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def close(self):
        with self._lock:
            return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def oppna(path=DB_DEFAULT, *, init=True, check_same_thread=True):
    """Öppnar (och skapar) databasen. Sätter FK-tvång och Row-factory.

    path : sökväg till .db-filen (skapas inkl. föräldrakatalog vid behov).
    init : kör init_db automatiskt (default). Sätt False för en rå anslutning.
    check_same_thread : False när anslutningen delas mellan trådar (t.ex.
        pywebview-bryggan som anropas från JS-tråden) — se SafeConnection för
        varför det då MÅSTE serialiseras med ett lås.
    """
    path = Path(path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn = SafeConnection(conn)
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
    if fran_version < 12:
        # v12: nätverkspublicering till content-sync-workern (Innehåll →
        # hemsidan, skild från den lokala .md-exportens `publicerad`-flagga).
        # _har_tabell-kollen krävs — synteticka äldre testdatabaser (v7-v9)
        # saknar innehall helt (tabellen kom in via schema.sql, aldrig via en
        # egen migreringssteg), så en ovillkorad ALTER kraschar på dem.
        if _har_tabell(conn, "innehall"):
            if not _har_kolumn(conn, "innehall", "synkad_tid"):
                conn.execute("ALTER TABLE innehall ADD COLUMN synkad_tid TEXT")
            # Legacy: 'portratt' var en egen typ innan Porträtt blev en
            # Event-kategori (se CTYPER/EVENT_KAT i Innehall.svelte samma bytt
            # som calendar-sync/migrations/0003_rename_portratt_to_event.sql).
            conn.execute("UPDATE innehall SET typ = 'event' WHERE typ = 'portratt'")
    if fran_version < 13:
        # v13: sportprofiler (data/sportprofil.py) styr resultat-/mellan-
        # resultat-/målskyttar-/uppställningsfälten per sport istället för
        # fotbollslåsta antaganden. `halvtid` döps om till sport-neutrala
        # `mellan`; sport-enumen på tavling/lag/matchen utökas med
        # 'innebandy'. CHECK kan inte ALTER:as i SQLite, så alla tre
        # tabellerna skrivs om i tur och ordning — matchen har inkommande
        # FK:er från flera tabeller (fotojobb_match, match_trupp, urval,
        # some_material, publicera_material, innehall) så FK-tvång stängs
        # av under ombyggnaden och verifieras efteråt.
        # Samma typ av guard som övriga steg — synteticka äldre testdatabaser
        # (t.ex. v1-v2, v7-v10) skapar inte alltid tavling/lag/matchen, och en
        # ovillkorad ombyggnad kraschar då på "no such table".
        if (_har_tabell(conn, "tavling") and _har_tabell(conn, "lag")
                and _har_tabell(conn, "matchen")
                and not _har_kolumn(conn, "matchen", "mellan")):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
            CREATE TABLE tavling_ny (
              id        TEXT PRIMARY KEY,
              typ       TEXT NOT NULL CHECK (typ IN ('liga','turnering','masterskap')),
              sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis')),
              gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
              namn      TEXT NOT NULL,
              hemsida   TEXT,
              fran      TEXT,
              till      TEXT,
              ort       TEXT,
              arena     TEXT,
              logga     TEXT,
              kalender  INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO tavling_ny (id,typ,sport,gren,namn,hemsida,fran,till,ort,arena,logga,kalender)
              SELECT id,typ,sport,gren,namn,hemsida,fran,till,ort,arena,logga,kalender FROM tavling;
            DROP TABLE tavling;
            ALTER TABLE tavling_ny RENAME TO tavling;

            CREATE TABLE lag_ny (
              id           TEXT PRIMARY KEY,
              namn         TEXT NOT NULL,
              kind         TEXT NOT NULL DEFAULT 'team'
                             CHECK (kind IN ('team','individ')),
              sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis')),
              gren         TEXT CHECK (gren IN ('dam','herr','mixed')),
              hemsida      TEXT,
              instagram    TEXT,
              logga        TEXT,
              stall_hemma  TEXT,
              stall_borta  TEXT,
              stall_tredje TEXT,
              profilfarg   TEXT,
              klubb        TEXT,
              trupp_kalla  TEXT
            );
            INSERT INTO lag_ny (id,namn,kind,sport,gren,hemsida,instagram,logga,
                                stall_hemma,stall_borta,stall_tredje,profilfarg,klubb,trupp_kalla)
              SELECT id,namn,kind,sport,gren,hemsida,instagram,logga,
                     stall_hemma,stall_borta,stall_tredje,profilfarg,klubb,trupp_kalla FROM lag;
            DROP TABLE lag;
            ALTER TABLE lag_ny RENAME TO lag;

            CREATE TABLE matchen_ny (
              id           TEXT PRIMARY KEY,
              tavling_id   TEXT REFERENCES tavling(id) ON DELETE SET NULL,
              sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis')),
              lag_hemma_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
              lag_borta_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
              datum        TEXT,
              tid          TEXT,
              arena        TEXT,
              resultat     TEXT,
              mellan       TEXT,
              malskyttar   TEXT,
              status       TEXT NOT NULL DEFAULT 'kommande'
                             CHECK (status IN ('kommande','pagaende','avslutad')),
              galleri      TEXT,
              sida_url     TEXT,
              omslag       TEXT,
              skapad       TEXT NOT NULL
            );
            INSERT INTO matchen_ny (id,tavling_id,sport,lag_hemma_id,lag_borta_id,datum,
                                     tid,arena,resultat,mellan,malskyttar,status,galleri,
                                     sida_url,omslag,skapad)
              SELECT id,tavling_id,sport,lag_hemma_id,lag_borta_id,datum,
                     tid,arena,resultat,halvtid,malskyttar,status,galleri,
                     sida_url,omslag,skapad FROM matchen;
            DROP TABLE matchen;
            ALTER TABLE matchen_ny RENAME TO matchen;
            CREATE INDEX idx_match_datum   ON matchen(datum);
            CREATE INDEX idx_match_tavling ON matchen(tavling_id);
            """)
            conn.execute("PRAGMA foreign_keys=ON")
            problem = conn.execute("PRAGMA foreign_key_check").fetchall()
            if problem:
                raise RuntimeError(
                    f"v13-migrering: FK-integritet trasig efter ombyggnad: {problem}")
    if fran_version < 14:
        # v14: arbetsyta_utkast — autosparat utkastinnehåll per match (Live/
        # SoMe/Webb-Sport), skilt från publicera_material/innehall som bara
        # skrivs på explicit Spara-klick (se DATAMODELL-UTKAST-RESULTAT.md).
        conn.execute("""
        CREATE TABLE IF NOT EXISTS arbetsyta_utkast (
          match_id     TEXT PRIMARY KEY REFERENCES matchen(id) ON DELETE CASCADE,
          some_caption TEXT,
          some_targets TEXT,
          some_lib     TEXT,
          live_moment  TEXT,
          live_tema    TEXT,
          live_cfg     TEXT,
          live_dropbox TEXT,
          live_vald    TEXT,
          cms          TEXT,
          cms_own      TEXT,
          uppdaterad   TEXT NOT NULL
        );""")
    if fran_version < 15:
        # v15: På gång — kurerad aktivitetslista → content/pagang/*.md på
        # webbens Sport-sida. Persistent lista (autospar), skild från innehall
        # (engångspublicering per formulär). Se schema.sql för kolumn-noter.
        conn.execute("""
        CREATE TABLE IF NOT EXISTS aktivitet (
          id          TEXT PRIMARY KEY,
          kategori    TEXT NOT NULL DEFAULT 'Match'
                        CHECK (kategori IN ('Match','Uppdrag','Utställning','Övrigt')),
          etikett     TEXT,
          titel       TEXT,
          datum       TEXT,
          tid         TEXT,
          plats       TEXT,
          beskrivning TEXT,
          publicerad  INTEGER NOT NULL DEFAULT 0,
          synkad_tid  TEXT,
          skapad      TEXT NOT NULL,
          uppdaterad  TEXT NOT NULL
        );""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_aktivitet_datum ON aktivitet(datum);")
    if fran_version < 16:
        # v16: heldagsaktivitet — döljer tid i På gång, webben visar "Heldag".
        if not _har_kolumn(conn, "aktivitet", "heldag"):
            conn.execute(
                "ALTER TABLE aktivitet ADD COLUMN heldag INTEGER NOT NULL DEFAULT 0;")
    if fran_version < 17:
        # v17: kurerad aktivitet-lista borttagen (På gång drivs nu av match-synk).
        conn.execute("DROP TABLE IF EXISTS aktivitet")
    if fran_version < 18:
        # v18: arkiverade lag — gömda i registret utan att raderas, så gamla
        # matcher behåller sina lagreferenser.
        if _har_tabell(conn, "lag") and not _har_kolumn(conn, "lag", "arkiverad"):
            conn.execute(
                "ALTER TABLE lag ADD COLUMN arkiverad INTEGER NOT NULL DEFAULT 0;")
    if fran_version < 19:
        # v19: fotografens anteckning per fotojobb. Egen tabell, inte en kolumn
        # på jobbet — jobben bor hos Calendar Sync-tjänsten, bara länkarna är
        # lokala (jfr fotojobb_match).
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fotojobb_notering (
          fotojobb_id TEXT PRIMARY KEY,
          notering    TEXT NOT NULL
        )""")
    if fran_version < 20:
        # v20: lagets logga speglad till R2 (publik URL). Molnrendern (Mobil
        # Live Etapp 2) kan inte läsa `lag.logga`/~/.config/dpt/loggor — utan
        # en URL faller den tyst tillbaka på monogram i stället för klubbmärke.
        if _har_tabell(conn, "lag") and not _har_kolumn(conn, "lag", "logga_url"):
            conn.execute("ALTER TABLE lag ADD COLUMN logga_url TEXT;")
    if fran_version < 21:
        # v21: fotoackreditering för matcher. Status per fotojobb (egen tabell —
        # jobben bor hos Calendar Sync-tjänsten, jfr fotojobb_notering) +
        # arrangörens regler på tävlingen (press-adress, "begär senast"-dagar).
        conn.execute("""
        CREATE TABLE IF NOT EXISTS ackreditering (
          fotojobb_id        TEXT PRIMARY KEY,
          status             TEXT NOT NULL DEFAULT 'ejbegard'
                               CHECK (status IN ('ejbegard','begard','beviljad','nekad')),
          note               TEXT NOT NULL DEFAULT '',
          paminnelse_jobb_id TEXT
        )""")
        if _har_tabell(conn, "tavling"):
            for kol, ddl in (
                ("press_email", "ALTER TABLE tavling ADD COLUMN press_email TEXT"),
                ("ackr_dagar", "ALTER TABLE tavling ADD COLUMN ackr_dagar INTEGER"),
            ):
                if not _har_kolumn(conn, "tavling", kol):
                    conn.execute(ddl)
    if fran_version < 22:
        # v22: i seriespel hanterar HEMMAKLUBBEN ackrediteringen för sina
        # hemmamatcher — samma regelfält på laget. Tävlingens fält blir
        # fallback (mästerskap/turneringar där arrangören äger processen).
        if _har_tabell(conn, "lag"):
            for kol, ddl in (
                ("press_email", "ALTER TABLE lag ADD COLUMN press_email TEXT"),
                ("ackr_dagar", "ALTER TABLE lag ADD COLUMN ackr_dagar INTEGER"),
            ):
                if not _har_kolumn(conn, "lag", kol):
                    conn.execute(ddl)
    if fran_version < 23:
        # v23: innehållstyp 'sportevent' (Event/mästerskap — egen hero, eget
        # galleri, underartiklar i frontmatter; handoff "sportsidor & menyer"
        # 11 jul 2026). typ-CHECK:en kan inte ALTER:as i SQLite → leaf-tabellen
        # skrivs om (inga inkommande FK:er; 'portratt' försvann redan i v12).
        # Samma guard som v12 — äldre syntetiska testdatabaser saknar innehall.
        if _har_tabell(conn, "innehall"):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
            CREATE TABLE innehall_ny (
              id          TEXT PRIMARY KEY,
              typ         TEXT NOT NULL CHECK (typ IN ('match','sportevent','event','landskap','blogg')),
              match_id    TEXT REFERENCES matchen(id) ON DELETE SET NULL,
              status      TEXT,
              frontmatter TEXT,
              body        TEXT,
              export_path TEXT,
              publicerad  INTEGER NOT NULL DEFAULT 0,
              synkad_tid  TEXT,
              skapad      TEXT
            );
            INSERT INTO innehall_ny
              SELECT id,typ,match_id,status,frontmatter,body,export_path,
                     publicerad,synkad_tid,skapad FROM innehall;
            DROP TABLE innehall;
            ALTER TABLE innehall_ny RENAME TO innehall;
            """)
            conn.execute("PRAGMA foreign_keys=ON")
    if fran_version < 24:
        # v24: innehållstyp 'film' (den handskrivna film.astro-sidan blir en
        # redigerbar innehållsrad — hero + ingress + bildlista i frontmatter).
        # Samtidigt återinförs 'portratt' i CHECK:en så migrations- och
        # färskinstallations-vägen (schema.sql) stämmer överens igen.
        # typ-CHECK kan inte ALTER:as i SQLite → leaf-tabellen skrivs om.
        if _har_tabell(conn, "innehall"):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
            CREATE TABLE innehall_ny (
              id          TEXT PRIMARY KEY,
              typ         TEXT NOT NULL CHECK (typ IN ('match','sportevent','event','landskap','portratt','blogg','film')),
              match_id    TEXT REFERENCES matchen(id) ON DELETE SET NULL,
              status      TEXT,
              frontmatter TEXT,
              body        TEXT,
              export_path TEXT,
              publicerad  INTEGER NOT NULL DEFAULT 0,
              synkad_tid  TEXT,
              skapad      TEXT
            );
            INSERT INTO innehall_ny
              SELECT id,typ,match_id,status,frontmatter,body,export_path,
                     publicerad,synkad_tid,skapad FROM innehall;
            DROP TABLE innehall;
            ALTER TABLE innehall_ny RENAME TO innehall;
            """)
            conn.execute("PRAGMA foreign_keys=ON")

    if fran_version < 25:
        # v25 (p.5): heldagsevent = match utan motståndare. Explicit flagga så
        # ett event skiljs från en match där borta bara råkar vara okänd.
        if _har_tabell(conn, "matchen") and not _har_kolumn(conn, "matchen", "event"):
            conn.execute(
                "ALTER TABLE matchen ADD COLUMN event INTEGER NOT NULL DEFAULT 0")

    if fran_version < 26:
        # v26 (tennis Fas 3): turnerings-SoMe = publicering mot en hel turnering
        # (t.ex. Nordea Open-veckan) i stället för en enskild match. Additivt,
        # nullbart — befintliga match-material rörs inte (mal_typ defaultar 'match').
        if _har_tabell(conn, "some_material") and not _har_kolumn(conn, "some_material", "tavling_id"):
            conn.execute("ALTER TABLE some_material ADD COLUMN tavling_id TEXT")
        if _har_tabell(conn, "publicera_material"):
            if not _har_kolumn(conn, "publicera_material", "mal_typ"):
                conn.execute(
                    "ALTER TABLE publicera_material ADD COLUMN mal_typ TEXT "
                    "NOT NULL DEFAULT 'match'")
            if not _har_kolumn(conn, "publicera_material", "tavling_id"):
                conn.execute("ALTER TABLE publicera_material ADD COLUMN tavling_id TEXT")

    if fran_version < 27:
        # v27: 'friidrott' läggs till sport-enumen på tavling/lag/matchen. Precis
        # som 'innebandy'/'tennis' tidigare kan CHECK inte ALTER:as i SQLite, så
        # tabellerna skrivs om i tur och ordning (samma FK-avstängning +
        # efterkontroll som v13). Guardad: hoppa om tavling redan tillåter
        # friidrott (idempotent) eller om kärntabellerna saknas (äldre testdb:er).
        if (_har_tabell(conn, "tavling") and _har_tabell(conn, "lag")
                and _har_tabell(conn, "matchen")
                and "friidrott" not in (conn.execute(
                    "SELECT sql FROM sqlite_master WHERE name='tavling'"
                ).fetchone()[0] or "")):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
            CREATE TABLE tavling_ny (
              id        TEXT PRIMARY KEY,
              typ       TEXT NOT NULL CHECK (typ IN ('liga','turnering','masterskap')),
              sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
              gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
              namn      TEXT NOT NULL,
              hemsida   TEXT,
              fran      TEXT,
              till      TEXT,
              ort       TEXT,
              arena     TEXT,
              logga     TEXT,
              kalender  INTEGER NOT NULL DEFAULT 0,
              press_email TEXT,
              ackr_dagar  INTEGER
            );
            INSERT INTO tavling_ny (id,typ,sport,gren,namn,hemsida,fran,till,ort,arena,logga,kalender,press_email,ackr_dagar)
              SELECT id,typ,sport,gren,namn,hemsida,fran,till,ort,arena,logga,kalender,press_email,ackr_dagar FROM tavling;
            DROP TABLE tavling;
            ALTER TABLE tavling_ny RENAME TO tavling;

            CREATE TABLE lag_ny (
              id           TEXT PRIMARY KEY,
              namn         TEXT NOT NULL,
              kind         TEXT NOT NULL DEFAULT 'team'
                             CHECK (kind IN ('team','individ')),
              sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
              gren         TEXT CHECK (gren IN ('dam','herr','mixed')),
              hemsida      TEXT,
              instagram    TEXT,
              logga        TEXT,
              stall_hemma  TEXT,
              stall_borta  TEXT,
              stall_tredje TEXT,
              profilfarg   TEXT,
              klubb        TEXT,
              trupp_kalla  TEXT,
              arkiverad    INTEGER NOT NULL DEFAULT 0,
              logga_url    TEXT,
              press_email  TEXT,
              ackr_dagar   INTEGER
            );
            INSERT INTO lag_ny (id,namn,kind,sport,gren,hemsida,instagram,logga,
                                stall_hemma,stall_borta,stall_tredje,profilfarg,klubb,trupp_kalla,
                                arkiverad,logga_url,press_email,ackr_dagar)
              SELECT id,namn,kind,sport,gren,hemsida,instagram,logga,
                     stall_hemma,stall_borta,stall_tredje,profilfarg,klubb,trupp_kalla,
                     arkiverad,logga_url,press_email,ackr_dagar FROM lag;
            DROP TABLE lag;
            ALTER TABLE lag_ny RENAME TO lag;

            CREATE TABLE matchen_ny (
              id           TEXT PRIMARY KEY,
              tavling_id   TEXT REFERENCES tavling(id) ON DELETE SET NULL,
              sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
              lag_hemma_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
              lag_borta_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
              datum        TEXT,
              tid          TEXT,
              arena        TEXT,
              resultat     TEXT,
              mellan       TEXT,
              malskyttar   TEXT,
              status       TEXT NOT NULL DEFAULT 'kommande'
                             CHECK (status IN ('kommande','pagaende','avslutad')),
              galleri      TEXT,
              sida_url     TEXT,
              omslag       TEXT,
              event        INTEGER NOT NULL DEFAULT 0,
              skapad       TEXT NOT NULL
            );
            INSERT INTO matchen_ny (id,tavling_id,sport,lag_hemma_id,lag_borta_id,datum,
                                     tid,arena,resultat,mellan,malskyttar,status,galleri,
                                     sida_url,omslag,event,skapad)
              SELECT id,tavling_id,sport,lag_hemma_id,lag_borta_id,datum,
                     tid,arena,resultat,mellan,malskyttar,status,galleri,
                     sida_url,omslag,event,skapad FROM matchen;
            DROP TABLE matchen;
            ALTER TABLE matchen_ny RENAME TO matchen;
            CREATE INDEX idx_match_datum   ON matchen(datum);
            CREATE INDEX idx_match_tavling ON matchen(tavling_id);
            """)
            conn.execute("PRAGMA foreign_keys=ON")
            problem = conn.execute("PRAGMA foreign_key_check").fetchall()
            if problem:
                raise RuntimeError(
                    f"v27-migrering: FK-integritet trasig efter ombyggnad: {problem}")

    if fran_version < 28:
        # v28 (D1 tennis-overlay): turneringsrond på matchen ("Åttondel",
        # "Semifinal"…) — stort ord i individ-sporternas Horisont-overlay.
        # Additivt, nullbart.
        if _har_tabell(conn, "matchen") and not _har_kolumn(conn, "matchen", "rond"):
            conn.execute("ALTER TABLE matchen ADD COLUMN rond TEXT")

    if fran_version < 29:
        # v29 (B-001 deltagarhantering): tävlingens grenar/discipliner +
        # deltagare per disciplin (friidrott: Längd, Tresteg…). Additiva
        # tabeller — `disciplin` i koden, `gren` betyder redan dam/herr/mixed.
        if not _har_tabell(conn, "disciplin"):
            conn.executescript("""
            CREATE TABLE disciplin (
              id         TEXT PRIMARY KEY,
              tavling_id TEXT NOT NULL REFERENCES tavling(id) ON DELETE CASCADE,
              namn       TEXT NOT NULL,
              typ        TEXT NOT NULL DEFAULT 'hoppkast'
                           CHECK (typ IN ('sprint','medel','hoppkast','mangkamp')),
              ordning    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX idx_disciplin_tavling ON disciplin(tavling_id);
            CREATE TABLE disciplin_deltagare (
              disciplin_id TEXT NOT NULL REFERENCES disciplin(id) ON DELETE CASCADE,
              lag_id       TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
              PRIMARY KEY (disciplin_id, lag_id)
            );
            """)

    if fran_version < 30:
        # v30 (På gång-kryssrutor): per-post synlighet i webbens På gång —
        # enskilda matcher under en turnering ska kunna döljas när heldags-
        # aktiviteten täcker dem (och omvänt). Default synlig. Additivt.
        for tabell in ("matchen", "tavling"):
            if _har_tabell(conn, tabell) and not _har_kolumn(conn, tabell,
                                                             "pagang_dold"):
                conn.execute(f"ALTER TABLE {tabell} ADD COLUMN pagang_dold "
                             "INTEGER NOT NULL DEFAULT 0")

    if fran_version < 31:
        # v31 (V5-B, eventmodell-epiken): Liga + Event ersätter Tävling — nya
        # registren liga/event/individ/event_deltagare/kategori + matchens
        # valfria liga_id/event_id. `tavling` LÄMNAS ORÖRD som skrivyta under
        # övergången; store speglar varje sparning in i liga/event (samma id)
        # och backfillen här speglar det som redan finns. Additivt + idempotent.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS liga (
          id        TEXT PRIMARY KEY,
          sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
          gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
          namn      TEXT NOT NULL,
          hemsida   TEXT,
          fran      TEXT,
          till      TEXT,
          ort       TEXT,
          arena     TEXT,
          logga     TEXT,
          kalender  INTEGER NOT NULL DEFAULT 0,
          press_email TEXT,
          ackr_dagar  INTEGER,
          pagang_dold INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS event (
          id        TEXT PRIMARY KEY,
          typ       TEXT NOT NULL DEFAULT 'ovrigt'
                      CHECK (typ IN ('masterskap','cup','turnering','varldscup','ovrigt')),
          sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
          gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
          namn      TEXT NOT NULL,
          hemsida   TEXT,
          fran      TEXT,
          till      TEXT,
          ort       TEXT,
          arena     TEXT,
          logga     TEXT,
          liga_id   TEXT REFERENCES liga(id) ON DELETE SET NULL,
          kalender  INTEGER NOT NULL DEFAULT 0,
          pagang_lage TEXT NOT NULL DEFAULT 'auto'
                        CHECK (pagang_lage IN ('auto','heldag','matcher')),
          press_email TEXT,
          ackr_dagar  INTEGER,
          pagang_dold INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS individ (
          id        TEXT PRIMARY KEY,
          namn      TEXT NOT NULL,
          sport     TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
          klubb     TEXT,
          instagram TEXT,
          bild      TEXT
        );
        CREATE TABLE IF NOT EXISTS event_deltagare (
          event_id   TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
          individ_id TEXT NOT NULL REFERENCES individ(id) ON DELETE CASCADE,
          grenar     TEXT,
          PRIMARY KEY (event_id, individ_id)
        );
        CREATE INDEX IF NOT EXISTS idx_event_deltagare_individ
          ON event_deltagare(individ_id);
        CREATE TABLE IF NOT EXISTS kategori (
          id     TEXT PRIMARY KEY,
          topp   TEXT NOT NULL CHECK (topp IN ('sport','landskap','manniskor','film')),
          namn   TEXT NOT NULL,
          gallringsprofil TEXT CHECK (gallringsprofil IN ('sport','brollop','landskap','portratt')),
          some_moment TEXT,
          ordning INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO kategori(id, topp, namn, gallringsprofil, some_moment, ordning) VALUES
          ('portratt', 'manniskor', 'Porträtt', 'portratt', '["tjuvkik","leverans-klar"]', 0),
          ('brollop',  'manniskor', 'Bröllop',  'brollop',  '["tjuvkik","leverans-klar"]', 1),
          ('student',  'manniskor', 'Student',  'portratt', '["tjuvkik","leverans-klar"]', 2),
          ('foretag',  'manniskor', 'Företag',  NULL,       '["tjuvkik","leverans-klar"]', 3),
          ('mode',     'manniskor', 'Mode',     NULL,       '["tjuvkik","leverans-klar"]', 4),
          ('ovrigt-manniskor', 'manniskor', 'Övrigt', NULL, '["tjuvkik","leverans-klar"]', 5);
        """)
        if _har_tabell(conn, "matchen"):
            for kol, ref in (("liga_id", "liga"), ("event_id", "event")):
                if not _har_kolumn(conn, "matchen", kol):
                    conn.execute(f"ALTER TABLE matchen ADD COLUMN {kol} TEXT "
                                 f"REFERENCES {ref}(id) ON DELETE SET NULL")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_match_liga ON matchen(liga_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_match_event ON matchen(event_id)")
        # Backfill: spegla befintliga tävlingar in i liga/event (samma id) och
        # sätt matchernas nya referenser. Lokal import — store importerar inte
        # db. Mycket gamla databaser (före tavling-tabellen) har inget att fylla.
        if _har_tabell(conn, "tavling"):
            from dpt2.data import store as _store
            for r in conn.execute("SELECT id FROM tavling").fetchall():
                _store.spegla_tavling_v5(conn, r[0])

    if fran_version < 32:
        # v32 (V5-C skiva 2): tävlings-typerna utökas med eventmodellens
        # etiketter (cup, varldscup, ovrigt) så event-editorn kan använda samma
        # skrivyta som allt annat under övergången (spegeln mappar typerna till
        # event-registret). CHECK kan inte ändras i SQLite → tabell-rebuild
        # (samma mönster som lag/matchen-rebuilden). Refererande tabeller
        # (matchen, disciplin, tavling_lag, fotojobb_utkast …) pekar på namnet
        # och tar den nya tabellen när den byter namn tillbaka. Guardad som
        # v13-rebuilden: uråldriga (test-)scheman utan typ/sport hoppar över.
        if (_har_tabell(conn, "tavling")
                and _har_kolumn(conn, "tavling", "typ")
                and _har_kolumn(conn, "tavling", "sport")
                and _har_kolumn(conn, "tavling", "pagang_dold")):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
            CREATE TABLE tavling_ny (
              id        TEXT PRIMARY KEY,
              typ       TEXT NOT NULL CHECK (typ IN ('liga','turnering','masterskap','cup','varldscup','ovrigt')),
              sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
              gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
              namn      TEXT NOT NULL,
              hemsida   TEXT,
              fran      TEXT,
              till      TEXT,
              ort       TEXT,
              arena     TEXT,
              logga     TEXT,
              kalender  INTEGER NOT NULL DEFAULT 0,
              press_email TEXT,
              ackr_dagar  INTEGER,
              pagang_dold INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO tavling_ny (id,typ,sport,gren,namn,hemsida,fran,till,
                                    ort,arena,logga,kalender,press_email,
                                    ackr_dagar,pagang_dold)
              SELECT id,typ,sport,gren,namn,hemsida,fran,till,
                     ort,arena,logga,kalender,press_email,
                     ackr_dagar,pagang_dold FROM tavling;
            DROP TABLE tavling;
            ALTER TABLE tavling_ny RENAME TO tavling;
            """)
            conn.execute("PRAGMA foreign_keys=ON")
            problem = conn.execute("PRAGMA foreign_key_check").fetchall()
            if problem:
                raise RuntimeError(
                    f"v32-migreringen lämnade brutna referenser: {problem[:5]}")

    if fran_version < 33:
        # v33 (FEAT-14 skiva 1): Gmails tråd-id sparas på ackrediteringen vid
        # utskicket → skiva 2:s läsväg hittar svar-i-tråd utan manuell gest.
        if (_har_tabell(conn, "ackreditering")
                and not _har_kolumn(conn, "ackreditering", "thread_id")):
            conn.execute("ALTER TABLE ackreditering ADD COLUMN thread_id TEXT")

    if fran_version < 34:
        # v34 (F18FM-2): referatet sparas som EGET källfält på materialet —
        # webbkanalen byggs från det i stället för att strippa sociala texten
        # (som läckte rubrikblock/länkrad/@?-taggar till webben).
        if (_har_tabell(conn, "publicera_material")
                and not _har_kolumn(conn, "publicera_material", "referat")):
            conn.execute("ALTER TABLE publicera_material ADD COLUMN referat TEXT")

    if fran_version < 35:
        # v35 (UX-lyftet §10): publiceringskön — materialet kan schemaläggas
        # (`publiceras` = ISO-tidpunkt). Steg 1 är manuell påminnelse i kön;
        # auto-utskick per kanal är ett senare beslut (per handoffen).
        if (_har_tabell(conn, "publicera_material")
                and not _har_kolumn(conn, "publicera_material", "publiceras")):
            conn.execute("ALTER TABLE publicera_material ADD COLUMN publiceras TEXT")

    if fran_version < 36:
        # v36 (UX-lyftet §10 skiva 3): momentmallen gäller ALLA jobbtyper, inte
        # bara matcher — landskaps-/människo-/filmjobb har egna moment (Ny
        # serie, Tjuvkik, Ny film …). Publicerade poster kunde bara knytas till
        # match/tävling → ✓-status fanns inte för dem. `jobb_id` = fotojobbets
        # id (Calendar Sync/lokalt utkast).
        for tabell in ("some_material", "publicera_material"):
            if _har_tabell(conn, tabell) and not _har_kolumn(conn, tabell, "jobb_id"):
                conn.execute(f"ALTER TABLE {tabell} ADD COLUMN jobb_id TEXT")


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
