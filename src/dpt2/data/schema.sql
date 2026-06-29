-- dpt2 datalager — SQLite-schema (v1)
-- Grundat i Designers DATAMODELL.md + befintlig data (matcher.json, facit_markt/,
-- manuella_etiketter, par_etiketter, history, settings, modeller/).
--
-- Konventioner:
--   * TEXT-id (slug eller hex) som primärnyckel — matchar DATAMODELL (id: malmo-ff)
--     och befintliga match-id i matcher.json (hex). App genererar id.
--   * Datum lagras som ISO-TEXT 'YYYY-MM-DD', tid som 'HH:MM' (SQLite saknar datumtyp).
--   * Booleska värden som INTEGER 0/1.
--   * JSON-fält som TEXT (json1-funktioner finns i SQLite).
--   * Tunga binärer (modell-pickles) ligger som FILER, DB lagrar sökväg.
--   * Tabellen för match heter `matchen` — `match` är reserverat (MATCH-operatorn).
--   * Foreign keys förutsätter `PRAGMA foreign_keys=ON` (sätts i db.oppna).

-- ── Referensdata som matcherna delar ────────────────────────────────────────

CREATE TABLE tavling (
  id        TEXT PRIMARY KEY,
  typ       TEXT NOT NULL CHECK (typ IN ('liga','turnering','masterskap')),
  sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
  namn      TEXT NOT NULL,
  fran      TEXT,                       -- ISO-datum (period.från)
  till      TEXT,                       -- ISO-datum (period.till)
  ort       TEXT,
  arena     TEXT,
  logga     TEXT,                       -- filsökväg
  kalender  INTEGER NOT NULL DEFAULT 0  -- utlagd i Google Calendar (bool)
);

CREATE TABLE lag (
  id           TEXT PRIMARY KEY,
  namn         TEXT NOT NULL,
  hemsida      TEXT,
  instagram    TEXT,
  logga        TEXT,                     -- filsökväg
  stall_hemma  TEXT,                     -- hex-färg
  stall_borta  TEXT,
  stall_tredje TEXT
);

CREATE TABLE spelare (
  id        TEXT PRIMARY KEY,
  lag_id    TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
  nr        TEXT,                        -- tröjnummer (TEXT: kan vara tomt/ledande nolla)
  namn      TEXT NOT NULL,
  position  TEXT,                        -- t.ex. anf/mitt/back/mv (eller fri info)
  handle    TEXT,                        -- @instagram (osäkra markeras med '?' av hämtaren)
  info      TEXT                         -- kort spelarinfo (position, land …)
);
CREATE INDEX idx_spelare_lag ON spelare(lag_id);

-- ── Match ────────────────────────────────────────────────────────────────────

CREATE TABLE matchen (
  id           TEXT PRIMARY KEY,
  tavling_id   TEXT REFERENCES tavling(id) ON DELETE SET NULL,
  sport        TEXT CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
  lag_hemma_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
  lag_borta_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
  datum        TEXT,                     -- ISO-datum
  tid          TEXT,                     -- 'HH:MM'
  arena        TEXT,
  resultat     TEXT,                     -- sätts efteråt, t.ex. '6-0'
  halvtid      TEXT,                     -- '3-0'
  malskyttar   TEXT,
  status       TEXT NOT NULL DEFAULT 'kommande'
                 CHECK (status IN ('kommande','pagaende','avslutad')),
  galleri      TEXT,                     -- Pixieset-URL
  omslag       TEXT,                     -- omslagsbild (filsökväg)
  skapad       TEXT NOT NULL
);
CREATE INDEX idx_match_datum   ON matchen(datum);
CREATE INDEX idx_match_tavling ON matchen(tavling_id);

-- Uttagen trupp per match (subset av lagets spelare) + vem som startade.
CREATE TABLE match_trupp (
  match_id   TEXT NOT NULL REFERENCES matchen(id) ON DELETE CASCADE,
  spelare_id TEXT NOT NULL REFERENCES spelare(id) ON DELETE CASCADE,
  start      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (match_id, spelare_id)
);

-- ── Urval & cull-jobb (verktygets state) ─────────────────────────────────────

CREATE TABLE urval (
  id       TEXT PRIMARY KEY,
  match_id TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  kalla    TEXT,                         -- källmapp/kort
  kamera   TEXT,                         -- t.ex. 'NIKON Z 8' / 'NIKON D5'
  bilder   INTEGER,                      -- antal i urvalet
  status   TEXT NOT NULL DEFAULT 'gallrad'
             CHECK (status IN ('gallrad','levererad','publicerad')),
  skapad   TEXT NOT NULL
);
CREATE INDEX idx_urval_match ON urval(match_id);

CREATE TABLE cull_jobb (
  id            TEXT PRIMARY KEY,
  urval_id      TEXT REFERENCES urval(id) ON DELETE CASCADE,
  verktyg       TEXT CHECK (verktyg IN ('ai','snabb','rapport')),
  behall_varde  REAL,
  behall_enhet  TEXT CHECK (behall_enhet IN ('bilder','procent')),
  burst_grans   REAL,
  trojnummer_ocr INTEGER DEFAULT 0,
  hemmafarg     TEXT,
  modell        TEXT,                    -- använd modell (din-smak/arkiv/hybrid)
  vikter        TEXT,                    -- json {pose:.., skarpa:..}
  skapad        TEXT NOT NULL
);

-- ── SoMe-material (Publicera) ────────────────────────────────────────────────

CREATE TABLE some_material (
  id       TEXT PRIMARY KEY,
  match_id TEXT REFERENCES matchen(id) ON DELETE CASCADE,
  kanal    TEXT CHECK (kanal IN ('instagram','facebook','tiktok')),
  format   TEXT,                         -- t.ex. 'Inlägg 4:5', '9:16'
  moment   TEXT,                         -- Avspark/Halvtid/Resultat/Startelva/Målgörare/Nästa match
  tema     TEXT CHECK (tema IN ('Hav','Sol','Rosé')),
  fil      TEXT,                         -- genererad bild (filsökväg)
  skapad   TEXT NOT NULL
);
CREATE INDEX idx_some_match ON some_material(match_id);

-- ── Modell (träning) ─────────────────────────────────────────────────────────

CREATE TABLE modell (
  id        TEXT PRIMARY KEY,
  typ       TEXT NOT NULL CHECK (typ IN ('din_smak','arkiv','hybrid')),
  aktiv     INTEGER NOT NULL DEFAULT 0,  -- vald i modell-växlaren
  pkl_path  TEXT NOT NULL,               -- filref till sklearn-pickle
  features  TEXT,                        -- json: FEATURES-kontraktets snapshot
  n_uppdrag INTEGER,
  n_valda   INTEGER,
  sparad    TEXT
);

-- ── Facit (grundsanning för träning) — den oersättliga tillgången ────────────

CREATE TABLE facit (
  id          TEXT PRIMARY KEY,
  match_id    TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  match_namn  TEXT,                      -- legacy matchinfo-sträng (spårbarhet)
  kalla       TEXT,
  kamera      TEXT,
  sport       TEXT,
  features    TEXT,                      -- json: feature-namn (versionssnapshot)
  n           INTEGER,
  behall_mapp TEXT,
  lev_mapp    TEXT,
  skapad      TEXT
);

CREATE TABLE facit_rad (
  facit_id TEXT NOT NULL REFERENCES facit(id) ON DELETE CASCADE,
  stem     TEXT NOT NULL,
  y        INTEGER,                      -- etikett (behållen = 1)
  w        REAL DEFAULT 1.0,            -- vikt (levererat väger tyngre)
  v        TEXT,                         -- json: feature-vektor
  PRIMARY KEY (facit_id, stem)
);

-- ── Aktiv inlärning ──────────────────────────────────────────────────────────

CREATE TABLE etikett (                   -- manuella_etiketter.json
  stem   TEXT PRIMARY KEY,
  behall INTEGER NOT NULL                -- 0/1
);

CREATE TABLE par (                       -- par_etiketter.json
  vinnare   TEXT NOT NULL,
  forlorare TEXT NOT NULL,
  PRIMARY KEY (vinnare, forlorare)
);

-- ── Urvalshistorik (history.json) ────────────────────────────────────────────

CREATE TABLE historik (
  id    INTEGER PRIMARY KEY,
  path  TEXT NOT NULL,
  antal INTEGER,
  tid   REAL                             -- unix-timestamp
);

-- ── Innehåll → hemsidan (CMS/Astro-export) — fylls i Fas 6 ───────────────────

CREATE TABLE innehall (
  id          TEXT PRIMARY KEY,
  typ         TEXT NOT NULL CHECK (typ IN ('match','event','landskap','portratt','blogg')),
  match_id    TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  status      TEXT,                      -- frontmatter-status (kommande/avslutad…)
  frontmatter TEXT,                      -- json
  body        TEXT,
  export_path TEXT,                      -- skriven .md i sajt-repot
  publicerad  INTEGER NOT NULL DEFAULT 0,
  skapad      TEXT
);

-- ── App-inställningar (ersätter settings.json; valfritt) ─────────────────────

CREATE TABLE installning (
  nyckel TEXT PRIMARY KEY,
  varde  TEXT
);
