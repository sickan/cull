"""SQLite-anslutning + schema-applicering för dpt2-datalagret.

Enkelt och beroendefritt (bara stdlib `sqlite3`). Schemaversionen spåras via
`PRAGMA user_version`; `init_db` applicerar `schema.sql` första gången och är
idempotent. Tunga binärer (modell-pickles, feature-vektorer i .npz) ligger som
filer — DB:n lagrar sökvägar, inte blobbar.
"""

import sqlite3
from pathlib import Path

# Schemaversion. Höj vid migrering och lägg migreringssteg i _migrera().
SCHEMA_VERSION = 2

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
