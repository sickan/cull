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
  gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
  namn      TEXT NOT NULL,
  hemsida   TEXT,                       -- tävlingens webbplats
  fran      TEXT,                       -- ISO-datum (period.från)
  till      TEXT,                       -- ISO-datum (period.till)
  ort       TEXT,
  arena     TEXT,
  logga     TEXT,                       -- filsökväg
  kalender  INTEGER NOT NULL DEFAULT 0  -- fotojobb-utkast skapat (se fotojobb_utkast)
);

-- Lokalt fotojobb-utkast (tävling → "Lägg i Google Calendar"). Väntar på att
-- fotografen kategoriserar och uttryckligen aktiverar synk i Fotojobb-panelen
-- — pushas ALDRIG till Calendar Sync-tjänsten (och därmed Google) förrän dess.
CREATE TABLE fotojobb_utkast (
  id         TEXT PRIMARY KEY,
  tavling_id TEXT UNIQUE REFERENCES tavling(id) ON DELETE CASCADE,
  title      TEXT NOT NULL,
  start_at   TEXT NOT NULL,
  end_at     TEXT NOT NULL,
  all_day    INTEGER NOT NULL DEFAULT 1,
  location   TEXT,
  category   TEXT,
  skapad     TEXT NOT NULL
);

CREATE TABLE lag (
  id           TEXT PRIMARY KEY,
  namn         TEXT NOT NULL,
  kind         TEXT NOT NULL DEFAULT 'team'
                 CHECK (kind IN ('team','individ')),  -- lagsport vs individuell utövare
  sport        TEXT CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
                                         -- landslag ("Sverige") särskiljs av sport
  gren         TEXT CHECK (gren IN ('dam','herr','mixed')),  -- mixed bara för team
  hemsida      TEXT,
  instagram    TEXT,
  logga        TEXT,                     -- filsökväg (logga/porträtt)
  stall_hemma  TEXT,                     -- hex-färg (team)
  stall_borta  TEXT,
  stall_tredje TEXT,
  profilfarg   TEXT,                     -- hex-färg (individ: en enda)
  klubb        TEXT,                     -- individ: klubb/land (ersätter trupp)
  trupp_kalla  TEXT                      -- senaste trupp-inläsningens källa
                                         --   ('från hemsida'/'CSV'/'bild'/'PDF')
);

-- Vilka lag som deltar i en tävling (tävling äger sina lag). Fyller lagväljaren
-- i Matcher: hemma/borta filtreras till den valda tävlingens lag.
CREATE TABLE tavling_lag (
  tavling_id TEXT NOT NULL REFERENCES tavling(id) ON DELETE CASCADE,
  lag_id     TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
  PRIMARY KEY (tavling_id, lag_id)
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
  sida_url     TEXT,                     -- publicerad hemsideslänk
  omslag       TEXT,                     -- omslagsbild (filsökväg)
  skapad       TEXT NOT NULL
);
CREATE INDEX idx_match_datum   ON matchen(datum);
CREATE INDEX idx_match_tavling ON matchen(tavling_id);

-- Fotojobb → match ("Koppla till match" när kategori=Sport). Lokal länk,
-- fristående från Calendar Sync-tjänsten (som inte känner till matcher).
-- fotojobb_id är antingen ett utkasts id (fotojobb_utkast) eller tjänstens
-- jobb-id — samma textnyckel-rymd.
CREATE TABLE fotojobb_match (
  fotojobb_id TEXT PRIMARY KEY,
  match_id    TEXT NOT NULL REFERENCES matchen(id) ON DELETE CASCADE
);

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

-- Per-bild-urval: vilka bilder gallringen behöll (grund för Leverera/nummer).
CREATE TABLE urval_bild (
  urval_id TEXT NOT NULL REFERENCES urval(id) ON DELETE CASCADE,
  stem     TEXT NOT NULL,
  behall   INTEGER NOT NULL DEFAULT 0,     -- 1 = behållen av gallringen
  poang    REAL,                            -- modell/handsatt-poäng
  PRIMARY KEY (urval_id, stem)
);

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

-- ── Sparade material + utkast (Publicera-panelens "Sparade material") ────────
-- Skilt från some_material ovan: det är en logg över FAKTISKT publicerade
-- poster, det här är arbetsytan (utkast + publicerat) man öppnar/redigerar/
-- fortsätter på. match_namn denormaliseras vid skrivning (matchen kan bytas
-- ut/tas bort utan att gamla material tappar sin etikett).

CREATE TABLE publicera_material (
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL CHECK (kind IN ('live','some')),
  match_id   TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  match_namn TEXT,
  status     TEXT NOT NULL CHECK (status IN ('utkast','publicerad','delvis')),
  moment     TEXT,                       -- live: mall-moment
  tema       TEXT,                       -- live: Hav/Sol/Rosé
  dropbox    TEXT,                       -- live: käll-mapp (steg 2)
  foto       TEXT,                       -- live: vald bildfil (steg 2)
  channels   TEXT,                       -- some: json-lista ['story','ig','fb']
  caption    TEXT,                       -- some: bildtext
  banor      TEXT,                       -- some: json {story:{mapp,bilder},ig:{...},fb:{...}}
  ch_results TEXT,                       -- some: json {story:'ok'|'fail',ig:...,fb:...} — driver delvis-läget & retry
  uppdaterad TEXT NOT NULL
);
CREATE INDEX idx_pubmat_uppdaterad ON publicera_material(uppdaterad DESC);

-- Publiceringshistorik — en rad per FAKTISKT publiceringsförsök (utkast loggas
-- aldrig). "Redigerar"-läget uppdaterar fälten på materialet men lägger alltid
-- till en ny historikpost här när man publicerar om.
CREATE TABLE publicera_material_historik (
  id          TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES publicera_material(id) ON DELETE CASCADE,
  tid         TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('publicerad','delvis')),
  note        TEXT
);
CREATE INDEX idx_pubmathist_material ON publicera_material_historik(material_id, tid DESC);

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
