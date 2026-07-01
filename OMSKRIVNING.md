# DPT 2.0 — arkitektur- och migreringskarta

Arbetsdokument för den totala omskrivningen av Dalecarlia Photo Tools. Utgår från
Designers **DATAMODELL.md** (entiteterna) och en full inventering av nuvarande
`dpt`-paket (10 732 rader, 20 moduler).

## Två fattade beslut (styr allt nedan)

1. **Ny app, migrera in bit för bit.** Vi bygger den nya strukturen från grunden
   och flyttar in befintlig logik modul för modul. **Nuvarande DPT lever och
   fungerar** tills den nya är klar — ingen big-bang.
2. **Eget DPT-datalager som äger allt arbete.** Datalagret är sanningen för
   matcher, lag, tävlingar, urval, modeller, SoMe-material. Det **exporterar
   färdiga `.md` till Astro-sajten** vid publicering (inte tvärtom).

---

## 1. Den viktigaste insikten

**Det finns ingen Match-, Tävling- eller Sport-entitet i dagens kod.** En match är
en lös fri-textsträng (`matchinfo`, t.ex. `"(D) Malmö FF – Kristianstad 6–0 …"`)
som byggs på ett ställe och parsas med regex på flera andra:

- `core._iptc_metadata` (regex → hemma/borta/datum/arena för IPTC)
- `gui._formatera_matchinfo` (fritext → mappnamn)
- `story_overlay.tolka_matchinfo` (sträng → dict)
- `las_lineup.las` bygger strängen; `bildsvep`/`bildtext_ai` konsumerar den

**Tävling finns inte alls som kod.** Sport är genomgående en lös strängparameter,
aldrig ett objekt. Detta — att ersätta strängen med riktiga objekt i datalagret —
är hela poängen med omskrivningen, och det som låser upp Matcher, Lag & tävlingar,
status-härledning och datadriven Astro-export.

---

## 2. Modulinventering & klassning

Klassning: **KÄRNA** = ren logik/IP, migreras intakt · **GLUE** = orkestrering,
skrivs om/konsolideras · **DATA** = format/config, formaliseras · **UI** = kastas.

| Modul | Rader | Klass | Roll & migreringsbeslut |
|---|---|---|---|
| `bas.py` | 126 | **KÄRNA** | Klassiska bildmått (skärpa, exponering, motljus, rörelse, ögon/ansikten). Migreras rakt av. Gotcha: Haar-cascade per tråd (TLS). |
| `clip_lager.py` | 114 | **KÄRNA** | CLIP zero-shot semantiska features (firande, närkamp, porträtt…). Migreras. Tungt beroende, rent kontrakt. |
| `vision_lager.py` | 144 | **KÄRNA** | Apple Vision lokalt: horisont, saliens, estetik. Migreras. Gotcha: autorelease-pool per bild (annars OOM). |
| `matchfas.py` | 87 | **KÄRNA** | Matchfas-bonus ur tidsstämplar + avsparksgissning. Migreras. Bör sport-parametriseras (idag fotbollsantaganden). |
| `vitbalans.py` | 243 | **KÄRNA** | Vitbalans/färgstick-diagnostik (hud + vitpunkt). Helt I/O-fri. Migreras rakt av. |
| `xmp_writer.py` | 223 | **KÄRNA** | XMP-sidecars för Lightroom (crop, exp, WB, profil, brus, betyg/etikett). **Navet i Leverera (LR-vägen).** Migreras. |
| `roster.py` | 79 | **KÄRNA** | Roster-CSV → nummer→namn-uppslag (per lag). Migreras. CSV-vyn av rostermodellen. |
| `story_overlay.py` | 931 | **KÄRNA** | "Horisont"-grafik: 6 moment × 3 teman × 2 format. **Inga dpt-beroenden.** Migreras nästan oförändrad; parametrisera assets/logg-katalog; driv från SoMe-objekt i stället för lösa strängar. |
| `leverans.py` | 341 | **KÄRNA**+GLUE+DATA | Destruktiv JPEG-väg (CEV/Instagram). Geometrikärnan (`rakta`, `_komponera_4x5`, `crop_rect`, `passa_i_box`) = KÄRNA. `exportera`/AI-urval = GLUE. `PROFILER` = DATA. |
| `nummer_pass.py` | 407 | GLUE+**KÄRNA** | Tröjnummer-OCR → keywords i Lightroom. Kärna: `_las_nummer`, `_skriv_keywords`, `_hemma_andel_crop`. CLI-skalet `kor()` skrivs om in i Leverera. |
| `ai_lager.py` | 883 | **KÄRNA**+GLUE | Scoring-primitiv (YOLO/pose/firande/keeper/klunga/OCR/NIMA/komposition). Heuristikerna = kärn-IP, migreras intakt. `ladda_modeller`/`bonus_batch` = modellfabrik/orkestrering, moderniseras. |
| `inlarning.py` | 1042 | **KÄRNA**+GLUE+DATA | Träning ("din smak") + inferens. Träningskärnan + `poangsatt_med_modell` + `FEATURES`-kontraktet = KÄRNA. Facit-upptäckt/cache/sport-detektering = GLUE (hårt knutet till nuvarande mapplayout). |
| `core.py` | 2048 | GLUE/CLI + inbäddad KÄRNA | Cull-pipelinens orkestrering + CLI. **Bryt ut** poäng-/urvalsformeln (vikter, firande-boost, väst-straff, normalisering, burst-dedup, topp-N + garantiplatser) och upprätnings-pipen till en `gallring`-motor. Resten skrivs om. Cache/facit-format = DATA att formalisera. |
| `hamta_match.py` | 398 | GLUE+DATA | Trupp + startelva via Claude web search. `KLUBBAR`-registret = DATA. → Matcher/Lag. |
| `las_lineup.py` | 148 | GLUE+DATA | Läser laguppställnings-ark via Claude vision (primär roster-källa). → Matcher. |
| `bildsvep.py` | 160 | GLUE+DATA | "Bildsvepet"-IG-text via web search. `STILEXEMPEL`/`SYSTEM` = DATA. → Publicera/Bildsvepet + Innehåll. |
| `bildtext_ai.py` | 135 | GLUE+DATA | Per-bild-bildtext via vision + roster. Central punkt där Match→Roster→Urval möts. → Leverera/IPTC + Innehåll. |
| `gui.py` | 1803 | **UI** + inbäddad logik | Tkinter kastas. **Bryt ut först:** `bygg_kommando`, `SETTINGS_KEYS`+vallistor, sökvägsvalidering (`stadad_sokvag`, Nikon-kortskvirk), hela persistenslagret, `_extrahera_preview`, `_formatera_matchinfo`, stream-/progress-protokollet (regexar, PULS/SKRAP). |
| `gui_web.py` | 1347 | **UI**-brygga + mest logik | pywebview/HTML kastas. **Migreras rakt av:** matchdatabasen (`match_*`, `_slå_ihop_spelare`, `_skriv_roster_csv`, `_rensa_spelare`), alla kommandobyggande handlers, `_stream`, `lar_av_match`/facit-märkning, `osakra_*`, statistik-handlers, modellbibliotek. |
| `version.py`, `_buildstamp.py` | 73 | DATA | Versions-/build-metadata. Trivialt. |

---

## 3. Tvärgående arkitekturfynd (måste hanteras i omskrivningen)

1. **`FEATURES`-listan är det centrala kontraktet** (`inlarning.py`) som binder
   `bas` + `ai_lager` + `clip_lager` → träning → cull. Versionerad ordning, ingår
   i cache-fingerprint. Måste bevaras/formaliseras — eller planeras för ren
   ombyggnad av cache + modeller.
2. **Två parallella feature-extraktionsvägar** som måste ge identiska värden:
   träning (`inlarning.features_for_uppdrag`) och cull (`ai_lager.bonus_batch`).
   **Förena till EN extraktionsfunktion** — annars drift.
3. **Två leveransvägar:** `leverans.py` (destruktiv JPEG, CEV/IG) och
   `xmp_writer.py` (icke-destruktiv Lightroom). Nya **Leverera = LR-vägen**, med
   `xmp_writer` som nav och `nummer_pass`-kärnan för tröjnummer-keywords.
4. **Fyra Claude-API-moduler** (`hamta_match`, `las_lineup`, `bildsvep`,
   `bildtext_ai`) duplicerar samma mönster (`tillganglig()`, `_parsa()`,
   `MODELL="claude-opus-4-8"`, pause_turn/web_search-loop, kostnads-/timeout-tak).
   **Konsolidera till EN `dpt.claude`-tjänst.**
5. **Roster produceras av tre källor** (`las_lineup` vision, `hamta_match` web,
   `roster` CSV) i tre format. Ena till EN rostermodell som datalagret äger.
6. **State är spritt** över `~/.cache/dpt/` och `~/.config/dpt/` (matcher.json,
   settings, historik, facit_markt, modell.pkl + modeller/, manuella/par-etiketter,
   sport-cache, osakra_nummer, nummer_cache, bas/ai-cache…). Nya datalagret ska
   **äga och formalisera** dessa.

---

## 4. Mål-arkitektur (ny app)

Ny pakethierarki vid sidan av gamla `dpt` (som lever vidare). Förslag på lager:

```
dpt2/
  data/          # SANNINGEN: entiteter + store (Sport, Tävling, Lag, Match,
                 #   Roster/Lineup, Urval, Cull-jobb, SoMe-material, Modell)
                 #   STORE (beslutat): SQLite från start — relationer + frågbarhet.
                 #   Relationell/metadata-sanning i tabeller; tunga binärer
                 #   (feature-vektorer .npz, modell.pkl) som filer refererade från DB.
  motorer/       # MIGRERAD KÄRNA (rena bibliotek, enhetstestbara):
                 #   bas, ai_lager(heuristik), clip_lager, vision_lager, matchfas,
                 #   vitbalans, xmp_writer, leverans(geometri), story_overlay,
                 #   roster, nummer(kärna)
                 #   + gallring   (poäng/urvalsmotor ur core.py)
                 #   + inlarning  (träning + inferens; EN feature-extraktion)
  tjanster/      # KONSOLIDERAD GLUE:
                 #   claude    (en Anthropic-klient: web_search, vision, kostnad,
                 #              timeout, JSON-parse — ersätter de 4 API-modulerna)
                 #   korning   (kör-/stream-/progress-protokoll ur gui:s _stream)
                 #   kommando  (om vi fortsatt shellar; annars direkta anrop)
  publicering/   # astro_export: skriver content/<typ>/*.md till sajt-repot,
                 #   kopierar hero/höjdpunkts-bilder, sätter status-frontmatter
  ui/            # NY app + paneler (Matcher, Lag & tävlingar, Gallra, Leverera,
                 #   Publicera[Matchdag|Bildsvepet], Innehåll, Träna, Logg)
                 #   STACK (beslutad): Svelte + Vite, hostad i pywebview-fönster.
                 #   Python-backend nås via pywebview-bryggan (window.pywebview.api),
                 #   samma mönster som dagens gui_web.Api — men handlers anropar
                 #   motorerna direkt (inga subprocess, se öppen fråga 4).
```

Panelerna är tunna Svelte-komponenter ovanpå `tjanster` + `data`. Designers prototyp
mappar mot komponenter (Rail, Panel, ToolCard, MatchCard, FormField …). Dev-loop:
Vite dev-server med HMR (pywebview pekar på `localhost:5173` i dev); prod = `npm run
build` → `dist/` bundlas in i paketet, pywebview laddar den byggda `index.html`.
Node/Vite finns redan i miljön (Astro-sajten använder det). Gamla `gui.py`/
`gui_web.py`/`assets/gui.html` kastas när panelerna är på plats.

---

## 5. Ny logik som ska BYGGAS (finns inte idag)

- **Datalager + entiteter** — Sport (enum), **Tävling** (helt ny), **Lag-register**
  (ställ-färger, IG, logga, trupp), **Match-objekt** (ersätter matchinfo-strängen),
  **Urval-status**-livscykel (gallrad→levererad→publicerad), **SoMe-material**-objekt,
  **Modell**-metadata. Formaliserar dagens lösa strängar/JSON.
- **Match-kalender / planering** (Matcher) — kommande matcher grupperade per tävling,
  **status-härledning** (kommande/pågående/avslutad ur datum+tid), "Tidigare projekt".
- **Lag & tävlingar-register** — CRUD för lag/tävlingar, loggor, ställ-färger,
  trupp-import. (Idag finns bara lös loggor-katalog + roster-CSV.)
- **Google Calendar-integration** — "Lägg i kalender" (ny).
- **Innehåll-CMS** — formulär → `.md` + Astro-export, med **hero/omslagsväljare**
  (obligatoriskt i schemat), `galleri`→**`pixieset`**-namnbyte, `malskyttar`,
  figur-block (bild+alt+bildtext), bildsvep-integration.
- **Astro-export** — skriv `.md` till sajt-repot, hantera hero/`hoejdpunkter`-bildkopiering,
  status-frontmatter. Avstämning mot `content.config.ts`: lägg till `malskyttar`;
  skapa `event`-collection; senare `landskap`/`portratt`/`blogg`.
- **Unified Claude-tjänst** — slå ihop de fyra API-modulerna.
- **Unified feature-extraktion** — slå ihop tränings- och cull-vägen.

---

## 6. Invarianter att bevara (migreringsrisk)

- **`FEATURES`-ordning + cache-fingerprint** — håll kompatibelt, eller planera ren
  ombyggnad av cacher/modeller medvetet.
- **`modell.pkl`-formatet** (din_smak/arkiv/hybrid) — driver modell-växlaren.
- **z-norm per uppdrag** måste matcha mellan träning och inferens.
- **Nikon-kortets volymnamn med efterföljande blanksteg** — `stadad_sokvag` får inte
  `.strip()`:a bort dem.
- **Trådsäkerhet:** Haar-cascade per tråd (`bas`), `_tysta_stderr` ej trådsäker
  (`ai_lager`), Vision autorelease-pool per bild.
- **`exiftool`** är hårt krav.

---

## 7. Byggsekvens (inkrementell — varje fas körbar, gamla DPT lever)

**Fas 0 — Skelett + datalager.** Nytt `dpt2`-paket + datalager (entiteter + store),
seedat ur befintliga `matcher.json`/roster/loggor. Migrera de beroendefria
KÄRN-biblioteken (`bas`, `ai_lager`, `clip`, `vision`, `matchfas`, `vitbalans`,
`xmp_writer`, `leverans`-geometri, `story_overlay`, `roster`) rakt in, oförändrade.
*Körbart:* importera + enhetstesta biblioteken.

**Fas 1 — Gallra (cull) end-to-end.** Bryt ut poäng-/urvalsmotorn ur `core.py` →
`motorer/gallring`; förena feature-extraktionen; koppla EN panel (Gallra) som kör
cull på en mapp → producerar ett **Urval**. Beviset på att datalager + motorer
håller. Återanvänder `inlarning`-inferens. *Körbart:* gallra ett riktigt kort.

**Fas 2 — Matcher + Lag & tävlingar.** Datalager-backad matchplanering; migrera
matchdatabasen ur `gui_web` (`match_*`, roster-CSV, merge); lägg till
laguppställnings-läsning (`las_lineup`) + trupp-hämtning (`hamta_match`) via nya
`claude`-tjänsten; status-härledning; kalender. *Nu kan ett cull-jobb knytas till en
riktig Match.*

**Fas 3 — Leverera.** LR-export (`xmp_writer` som nav) + `nummer_pass`-kärna
(tröjnummer-keywords) + IPTC/`bildtext_ai`. Urval-status → levererad.

**Fas 4 — Träna.** Migrera `inlarning` (träning + inferens), modellbibliotek/växlare,
lär-av-match (facit-märkning), granska osäkra / jämför par.

**Fas 5 — Publicera.** Matchdag (`story_overlay` ur SoMe-objekt: moment/format/tema)
+ Bildsvepet (`bildsvep` + IG-urval), publiceringsmål.

**Fas 6 — Innehåll + Astro-export.** CMS-panelen → `.md` + export till sajt-repot
(avstämt mot `content.config.ts`: hero/heroPosition, pixieset, malskyttar,
figur-block); `event`-collection; senare landskap/porträtt/blogg.

**Fas 7 — Logg + puts + cutover.** Pensionera `gui.py`/`gui_web.py`.

---

## 8. Beslut (alla fyra låsta 2026-06-29)

1. ~~**UI-ramverk för nya appen**~~ → **BESLUTAT (2026-06-29): Svelte + Vite i
   pywebview-fönster**, Python-backend via bryggan (handlers anropar motorerna
   direkt). Designers prototyp realiseras som Svelte-komponenter. Se §4.
2. ~~**Store-format**~~ → **BESLUTAT (2026-06-29): SQLite från start** — relationer
   (Tävling→Match→Urval, Lag↔Match) + frågbarhet (kalender, status). Relationell/
   metadata-sanning i tabeller; tunga binärer (feature-`.npz`, `modell.pkl`) som filer
   refererade från DB. Migrering av matcher.json/facit/labels → tabeller i Fas 0.
3. ~~**Cache/modell-kompatibilitet**~~ → **BESLUTAT (2026-06-29): frys `FEATURES`-
   kontraktet vid migreringen.** Unifiera de två feature-vägarna men så att de
   producerar exakt samma vektor som idag → `modell.pkl` + cacher + `facit_markt`-X
   förblir giltiga. **Facit + etiketter migreras in i SQLite — det är den oersättliga
   tillgången** (modell/cache är härledda). **Golden-test:** dpt2:s unifierade
   extraktion ska reproducera gamla `FEATURES`-vektorn bit-för-bit på ett stickprov
   innan överförd modell/cache litas på. Nya features = medveten fas EFTER migrering
   (ren omräkning + omträning då). Cacher är självskyddande (fingerprint = FEATURES).
4. ~~**Shell-ut vs direktanrop**~~ → **BESLUTAT (2026-06-29): hybrid.** Tunga/krasch-
   benägna/långa jobb (gallring, träning, nummer-pass, story-batch, AI-scoring) →
   **separat worker-process** (isolering mot native-krascher/OOM; håller process-global
   `_tysta_stderr` + trådfaror borta från UI:t; frigör modellminne per jobb) — men med
   **strukturerad IPC** (JSON-events/kö), INTE regex-på-loggrader. Lätta/säkra anrop
   (SQLite-CRUD, roster, cache-läs, fil-lista, previews) → **direkt i UI-processen** via
   bryggan. Migrerad stream-/progress-logik matas med JSON-events i stället för loggregex.
