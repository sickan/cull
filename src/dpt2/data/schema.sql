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
  sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
  gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
  namn      TEXT NOT NULL,
  hemsida   TEXT,                       -- tävlingens webbplats
  fran      TEXT,                       -- ISO-datum (period.från)
  till      TEXT,                       -- ISO-datum (period.till)
  ort       TEXT,
  arena     TEXT,
  logga     TEXT,                       -- filsökväg
  kalender  INTEGER NOT NULL DEFAULT 0, -- fotojobb-utkast skapat (se fotojobb_utkast)
  press_email TEXT,                     -- arrangörens press/ackrediteringsadress
  ackr_dagar  INTEGER,                  -- "begär senast" = matchdatum − dagar (tom = default)
  pagang_dold INTEGER NOT NULL DEFAULT 0 -- v30: dölj i webbens På gång (heldagsaktiviteten)
);

-- ── V5-B (eventmodell-epiken): Liga + Event ersätter Tävling ────────────────
-- Tävling delas i två register (DATAMODELL v5): LIGA (långlivad struktur —
-- säsongs-HISTORIK byggs på sikt, fran/till bär aktuell säsong så länge) och
-- EVENT (tidsbegränsat; typ är en ETIKETT, ingen typ-styrd logik). Under
-- övergången är `tavling` kvar som skrivyta: store speglar varje sparning hit
-- med SAMMA id (matchers/disciplinernas referenser förblir giltiga), och
-- V5-C flyttar läsarna. Migrering: v31.

CREATE TABLE liga (
  id        TEXT PRIMARY KEY,
  sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
  gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
  namn      TEXT NOT NULL,
  hemsida   TEXT,
  fran      TEXT,                       -- ISO-datum (aktuell säsong)
  till      TEXT,
  ort       TEXT,
  arena     TEXT,
  logga     TEXT,
  kalender  INTEGER NOT NULL DEFAULT 0,
  press_email TEXT,
  ackr_dagar  INTEGER,
  pagang_dold INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE event (
  id        TEXT PRIMARY KEY,
  typ       TEXT NOT NULL DEFAULT 'ovrigt'
              CHECK (typ IN ('masterskap','cup','turnering','varldscup','ovrigt')),
  sport     TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
  gren      TEXT CHECK (gren IN ('dam','herr','mixed')),
  namn      TEXT NOT NULL,
  hemsida   TEXT,
  fran      TEXT,                       -- ISO-datum (period.från)
  till      TEXT,
  ort       TEXT,
  arena     TEXT,
  logga     TEXT,
  liga_id   TEXT REFERENCES liga(id) ON DELETE SET NULL,  -- t.ex. SM-slutspel i en liga
  kalender  INTEGER NOT NULL DEFAULT 0,
  pagang_lage TEXT NOT NULL DEFAULT 'auto'
                CHECK (pagang_lage IN ('auto','heldag','matcher')),  -- skiss 1h
  press_email TEXT,
  ackr_dagar  INTEGER,
  pagang_dold INTEGER NOT NULL DEFAULT 0
);

-- Individ: eget register (som Lag) — långlivad mellan event. Historiken
-- HÄRLEDS genom att fråga event_deltagare; inget skrivs på individen.
CREATE TABLE individ (
  id        TEXT PRIMARY KEY,
  namn      TEXT NOT NULL,
  sport     TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
  klubb     TEXT,
  instagram TEXT,
  bild      TEXT
);

-- Kopplingen individ ⟂ gren lagras på EVENTET (en källa, ingen dubblering).
CREATE TABLE event_deltagare (
  event_id   TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
  individ_id TEXT NOT NULL REFERENCES individ(id) ON DELETE CASCADE,
  grenar     TEXT,                      -- json-lista med gren-/disciplin-id:n
  PRIMARY KEY (event_id, individ_id)
);
CREATE INDEX idx_event_deltagare_individ ON event_deltagare(individ_id);

-- Kategorier: toppnivån är STATISK (sport/landskap/manniskor/film — checks i
-- kod), underkategorierna ett redigerbart register (läggs till/döps om utan
-- kodändring). gallringsprofil styr Gallra-signalerna (4d), some_moment är
-- momentmallen (4c) som json-lista.
CREATE TABLE kategori (
  id     TEXT PRIMARY KEY,
  topp   TEXT NOT NULL CHECK (topp IN ('sport','landskap','manniskor','film')),
  namn   TEXT NOT NULL,
  gallringsprofil TEXT CHECK (gallringsprofil IN ('sport','brollop','landskap','portratt')),
  some_moment TEXT,
  ordning INTEGER NOT NULL DEFAULT 0
);

-- Dagens set under Människor (DATAMODELL v5) — redigerbart efteråt.
INSERT OR IGNORE INTO kategori(id, topp, namn, gallringsprofil, some_moment, ordning) VALUES
  ('portratt', 'manniskor', 'Porträtt', 'portratt', '["tjuvkik","leverans-klar"]', 0),
  ('brollop',  'manniskor', 'Bröllop',  'brollop',  '["tjuvkik","leverans-klar"]', 1),
  ('student',  'manniskor', 'Student',  'portratt', '["tjuvkik","leverans-klar"]', 2),
  ('foretag',  'manniskor', 'Företag',  NULL,       '["tjuvkik","leverans-klar"]', 3),
  ('mode',     'manniskor', 'Mode',     NULL,       '["tjuvkik","leverans-klar"]', 4),
  ('ovrigt-manniskor', 'manniskor', 'Övrigt', NULL, '["tjuvkik","leverans-klar"]', 5);

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
  sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
                                         -- landslag ("Sverige") särskiljs av sport
  gren         TEXT CHECK (gren IN ('dam','herr','mixed')),  -- mixed bara för team
  hemsida      TEXT,
  instagram    TEXT,
  logga        TEXT,                     -- filsökväg (logga/porträtt)
  logga_url    TEXT,                     -- speglad till R2 (molnrendern läser den)
  stall_hemma  TEXT,                     -- hex-färg (team)
  stall_borta  TEXT,
  stall_tredje TEXT,
  profilfarg   TEXT,                     -- hex-färg (individ: en enda)
  klubb        TEXT,                     -- individ: klubb/land (ersätter trupp)
  trupp_kalla  TEXT,                     -- senaste trupp-inläsningens källa
                                         --   ('från hemsida'/'CSV'/'bild'/'PDF')
  arkiverad    INTEGER NOT NULL DEFAULT 0, -- gömt i registret men bevarat: gamla
                                         -- matcher pekar fortfarande på laget
  press_email  TEXT,                     -- klubbens press/ackrediteringsadress
                                         -- (hemmaklubben äger seriematcherna;
                                         -- vinner över tävlingens fält)
  ackr_dagar   INTEGER                   -- klubbens "begär senast"-dagar
);

-- Vilka lag som deltar i en tävling (tävling äger sina lag). Fyller lagväljaren
-- i Matcher: hemma/borta filtreras till den valda tävlingens lag.
CREATE TABLE tavling_lag (
  tavling_id TEXT NOT NULL REFERENCES tavling(id) ON DELETE CASCADE,
  lag_id     TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
  PRIMARY KEY (tavling_id, lag_id)
);

-- B-001 (friidrott m.fl. individ-sporter): tävlingens GRENAR ("Längd",
-- "100 m") — "disciplin" i koden eftersom `gren` redan betyder dam/herr/mixed.
-- `typ` styr resultatformatet i story-overlayn (D2-svarets formattabell).
CREATE TABLE disciplin (
  id         TEXT PRIMARY KEY,
  tavling_id TEXT NOT NULL REFERENCES tavling(id) ON DELETE CASCADE,
  namn       TEXT NOT NULL,
  typ        TEXT NOT NULL DEFAULT 'hoppkast'
               CHECK (typ IN ('sprint','medel','hoppkast','mangkamp')),
  ordning    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_disciplin_tavling ON disciplin(tavling_id);

-- Deltagare (individ-poster i lag-tabellen) per disciplin — en deltagare kan
-- ställa upp i flera grenar (Längd + Tresteg).
CREATE TABLE disciplin_deltagare (
  disciplin_id TEXT NOT NULL REFERENCES disciplin(id) ON DELETE CASCADE,
  lag_id       TEXT NOT NULL REFERENCES lag(id) ON DELETE CASCADE,
  PRIMARY KEY (disciplin_id, lag_id)
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
  sport        TEXT CHECK (sport IN ('fotboll','handboll','innebandy','volleyboll','beachvolley','tennis','friidrott')),
  lag_hemma_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
  lag_borta_id TEXT REFERENCES lag(id) ON DELETE SET NULL,
  datum        TEXT,                     -- ISO-datum
  tid          TEXT,                     -- 'HH:MM'
  arena        TEXT,
  resultat     TEXT,                     -- sätts efteråt, t.ex. '6-0'
  mellan       TEXT,                     -- mellanresultat: halvtid/set/perioder beroende på sportprofil
  malskyttar   TEXT,                     -- bara för scorer-sporter (se sportprofil.py)
  rond         TEXT,                     -- turneringsrond ("Kvartsfinal") — D1: stort ord i tennis-overlayn
  status       TEXT NOT NULL DEFAULT 'kommande'
                 CHECK (status IN ('kommande','pagaende','avslutad')),
  galleri      TEXT,                     -- Pixieset-URL
  sida_url     TEXT,                     -- publicerad hemsideslänk
  omslag       TEXT,                     -- omslagsbild (filsökväg)
  event        INTEGER NOT NULL DEFAULT 0, -- p.5: heldagsevent = match utan motståndare
  pagang_dold  INTEGER NOT NULL DEFAULT 0, -- v30: dölj i webbens På gång (t.ex. turneringens delmatcher)
  liga_id      TEXT REFERENCES liga(id)  ON DELETE SET NULL, -- v31 (V5-B): valfri ligakoppling
  event_id     TEXT REFERENCES event(id) ON DELETE SET NULL, -- v31 (V5-B): valfri eventkoppling
  skapad       TEXT NOT NULL
);
CREATE INDEX idx_match_datum   ON matchen(datum);
CREATE INDEX idx_match_tavling ON matchen(tavling_id);
CREATE INDEX idx_match_liga    ON matchen(liga_id);
CREATE INDEX idx_match_event   ON matchen(event_id);

-- Fotojobb → match ("Koppla till match" när kategori=Sport). Lokal länk,
-- fristående från Calendar Sync-tjänsten (som inte känner till matcher).
-- fotojobb_id är antingen ett utkasts id (fotojobb_utkast) eller tjänstens
-- jobb-id — samma textnyckel-rymd.
CREATE TABLE fotojobb_match (
  fotojobb_id TEXT PRIMARY KEY,
  match_id    TEXT NOT NULL REFERENCES matchen(id) ON DELETE CASCADE
);

-- Fotografens egen anteckning per jobb (kund, paket, utrustning). LOKAL —
-- speglas aldrig till Google Calendars `description`, så synken kan inte
-- skriva över den och den funkar även för jobb som importerats från Google.
-- Samma textnyckel-rymd som fotojobb_match (utkast-id eller tjänstens jobb-id).
CREATE TABLE fotojobb_notering (
  fotojobb_id TEXT PRIMARY KEY,
  notering    TEXT NOT NULL
);

-- Fotoackreditering per matchjobb (bara kategori Sport). Skild från jobbet
-- självt — jobben bor hos Calendar Sync-tjänsten, samma textnyckel-rymd som
-- fotojobb_match/fotojobb_notering. paminnelse_jobb_id pekar på tjänstens
-- "Begär ackreditering senast"-event (speglas till Google Calendar).
CREATE TABLE ackreditering (
  fotojobb_id        TEXT PRIMARY KEY,
  status             TEXT NOT NULL DEFAULT 'ejbegard'
                       CHECK (status IN ('ejbegard','begard','beviljad','nekad')),
  note               TEXT NOT NULL DEFAULT '',
  paminnelse_jobb_id TEXT
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
  tavling_id TEXT REFERENCES tavling(id) ON DELETE CASCADE, -- turnerings-SoMe (ej matchbunden)
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
  -- Målet är antingen en match (mal_typ='match', match_id satt) eller en hel
  -- turnering (mal_typ='turnering', tavling_id satt, match_id NULL) — turnerings-
  -- SoMe (t.ex. "Nordea Open dag 3") som inte hänger på en enskild match.
  mal_typ    TEXT NOT NULL DEFAULT 'match' CHECK (mal_typ IN ('match','turnering')),
  match_id   TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  tavling_id TEXT REFERENCES tavling(id) ON DELETE SET NULL,
  match_namn TEXT,                       -- denormaliserad etikett (match- ELLER tävlingsnamn)
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

-- Autosparat utkastinnehåll per match (Live/SoMe/Webb-Sport) — arbetsytans
-- minne. Skilt från publicera_material/innehall ovan/nedan, som bara skrivs
-- på explicit Spara-klick (se design_handoff_live_some_webb/DATAMODELL-
-- UTKAST-RESULTAT.md §2).
CREATE TABLE arbetsyta_utkast (
  match_id     TEXT PRIMARY KEY REFERENCES matchen(id) ON DELETE CASCADE,
  some_caption TEXT,
  some_targets TEXT,                     -- json {story,ig,fb: bool}
  some_lib     TEXT,                     -- json {source,target,picks:{story,ig,fb},cover}
  live_moment  TEXT,
  live_tema    TEXT,
  live_cfg     TEXT,                     -- json (mall-fälten, se MALLFALT i Publicera.svelte)
  live_dropbox TEXT,
  live_vald    TEXT,                     -- vald bilds fullständiga sökväg (Live steg 2)
  cms          TEXT,                     -- json snapshot av Innehålls `cms` (typ=match)
  cms_own      TEXT,                     -- json cmsOwn-karta (vilka fält är egna/länkade)
  uppdaterad   TEXT NOT NULL
);

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
  typ         TEXT NOT NULL CHECK (typ IN ('match','sportevent','event','landskap','portratt','blogg','film')),
  match_id    TEXT REFERENCES matchen(id) ON DELETE SET NULL,
  status      TEXT,                      -- frontmatter-status (kommande/avslutad…)
  frontmatter TEXT,                      -- json
  body        TEXT,
  export_path TEXT,                      -- skriven .md i sajt-repot
  publicerad  INTEGER NOT NULL DEFAULT 0, -- lokal .md skriven (export_path satt)
  synkad_tid  TEXT,                      -- senast publicerad till content-sync (nätet) — skilt från publicerad ovan
  skapad      TEXT
);

-- ── App-inställningar (ersätter settings.json; valfritt) ─────────────────────

CREATE TABLE installning (
  nyckel TEXT PRIMARY KEY,
  varde  TEXT
);
