# Kravspec — Matcher ⇄ Lag/Tävlingar + Google Calendar two-way sync (DPT2)

**Status:** draft för överlämning till Claude Design.
**Datum:** 2026-07-01.
**Låsta vägval:** (1) *Tävling äger sina lag* (relation). (2) *Fokuserad omgång* — knyt ihop
kopplingen, inga nya storvyer (säsong/serietabell/match-hub sparas till senare).
**Egentliga jobbet:** skruva in den redan utvecklade **DPT Google Calendar two-way sync**
i DPT2. Kopplingen matcher/lag/tävlingar är bärytan syncen landar i.

> **OBS för granskning:** Del A är specad mot faktisk kod (`src/dpt2/data/store.py`,
> `schema.sql`, `panels/Matcher.svelte`, `panels/Lag.svelte`). Del B är specad mot den
> färdiga tjänstens integrationsguide (`~/Downloads/INTEGRATION.md`) — DPT2 bygger ingen
> sync, bara en klient. `[BEKRÄFTA]` markerar produktval som fortfarande är Stigs att välja.

---

## Nuläge (diagnos)

Schemat är redan relationellt korrekt: `matchen` har FK `tavling_id`, `lag_hemma_id`,
`lag_borta_id` mot registertabellerna `tavling` och `lag`. `Lag & tävlingar`-panelen
underhåller registret (logga, @instagram, ställfärger).

**Men UI + `spara_match` behandlar lag/tävling som lös fritext:**

- `Matcher.svelte`: Hemmalag / Bortalag / Tävling är fria textfält.
- `store.spara_match` gör `upsert_lag(namn)` / `upsert_tavling(namn)` — matchar/skapar
  register­poster **på namn**. "Malmö FF" i matchen vs "MFF" i registret → två lag.
  Registret och matcherna kan glida isär (dubbletter, föräldralösa poster).
- Ingen väg från registrerat lag (med ställ/logga/IG) till laget man skrev i matchen.
- En tävling vet inte vilka lag som spelar i den.

Kalender: `tavling.kalender` (bool, "utlagd i Google Calendar") + TODO i OMSKRIVNING
("Google Calendar-integration — 'Lägg i kalender'"). Ingen faktisk sync-kod finns.

---

## Del A — Knyt ihop matcher, lag och tävlingar

### A1. Datamodell

- **Ny join-tabell `tavling_lag(tavling_id, lag_id)`** — tävling äger sina deltagande lag.
  PK `(tavling_id, lag_id)`, FK CASCADE. Ett lag kan delta i flera tävlingar.
- `matchen` behåller `tavling_id` + `lag_hemma_id`/`lag_borta_id` (oförändrat).
- `lag` förblir sport-agnostiskt; **sport härleds ur tävlingen** (Sport→Tävling→Lag→Match).

### A2. Registerväljare i matchen (ersätter fritextfälten)

Flöde i match-editorn, som konsekvens av "tävling äger sina lag":

1. **Välj tävling** ur registret (dropdown mot `lista_tavlingar`). Sätter matchens sport.
2. **Hemmalag / Bortalag = registerväljare filtrerad till tävlingens lag.**
   *Hybrid-modell* `[BEKRÄFTA att detta är önskad väljarmodell]`: sökfält mot registret;
   finns laget → välj (får ställ/logga/IG på köpet); finns det inte → `+ Skapa "X"` inline
   → skapas i `lag` **och** kopplas till tävlingen (`tavling_lag`).
3. Arena kan förifyllas ur tävlingens/lagets hemmaarena.

### A3. Store-ändringar

- `spara_match` tar emot **id:n** (`tavling_id`, `lag_hemma_id`, `lag_borta_id`) från UI,
  inte fria namn. Sluta `upsert_lag(namn)` som default-väg.
- Ny `koppla_lag_till_tavling(tavling_id, lag_id)` (idempotent) — anropas av inline-skapa
  och när en match sätter lag i en tävling (löser upp "vilka lag spelar i tävlingen").
- `lista_lag(tavling_id=None)` — filtrerad laglista för väljaren.

### A4. Lag & tävlingar-panelen

- Tävlingskortet visar/redigerar sin **laglista** (lägg till ur register / skapa nytt / ta bort).
- I övrigt oförändrad (loggor, @instagram, ställfärger).

### A5. Engångs-dedup av befintlig lös data

Migreringssteg som slår ihop namn-dubbletter i `lag`/`tavling` (case/whitespace/kända
alias), pekar om matchernas FK, och tar bort dubbletterna. Loggas, körs en gång.

---

## Del B — Integrera mot "DPT Calendar Sync" (färdig, deployad tjänst)

Two-way-synken är **redan byggd**: en fristående Cloudflare Workers-tjänst som håller
fotojobb i tvåvägssynk med Google Calendar. **DPT2 bygger ingen sync** — DPT2 blir en
**HTTP-klient** mot tjänstens API. Tjänsten äger OAuth, Google-push och avstämning.

- **Bas-URL:** `https://dpt-calendar-sync.stig-johansson.workers.dev`
- **Publikt (ingen auth):** `GET /api/public/events` — kommande jobb, säkra fält (ingen
  `description`). Även färdig HTML-vy `GET /kommande`.
- **Skyddat (server-till-server, `Authorization: Bearer <API_KEY>`):**
  `GET/POST /api/events`, `GET/PUT/DELETE /api/events/:id`.
- **Jobb-modell:** `id, title, start_at, end_at, all_day, location, description (privat),
  category (Sport|Landskap|Event|Övrigt), status (confirmed|cancelled), google_event_id
  (null=Väntar), source (dpt|google)`. Tider = Europe/Stockholm.
- Referens: `~/Downloads/INTEGRATION.md` (integrationsguiden).

**Nyckelinsikt:** tjänsten är en *generell* fotojobbs-kalender (Sport/Landskap/Event/Övrigt).
En **match = ett Sport-jobb**. Sport-färgen `#2F7CB0` = samma blå som DPT2:s default-hemmaställ.

### B1. Klient-tjänst `tjanster/kalender.py`

- Tunn HTTP-klient (`httpx`, finns i venv). Klienten/nyckeln **injiceras** → testbar med
  fejk-klient, exakt samma mönster som `tjanster/claude.py`.
- Metoder: `publika_handelser()` (GET public), `lista_jobb()/hamta_jobb(id)/skapa_jobb()/
  uppdatera_jobb(id)/radera_jobb(id)` (Bearer).
- **API-nyckel via env `CALENDAR_SYNC_API_KEY`** (ur `.zshrc`, laddad av launchern precis
  som `ANTHROPIC_API_KEY`). Ligger **bara** i Python-backend bakom pywebview-bryggan —
  aldrig i Svelte-bundlen. Bryggan (`app.py`) exponerar bara färdiga resultat till UI.

### B2. Match → jobb-mappning

- `title` = "Hemma – Borta" · `start_at` = `datum`+`tid` (avspark) · `end_at` = start +
  varaktighet per sport `[BEKRÄFTA t.ex. fotboll 2h, handboll 1h30]` · `location` = arena ·
  `category` = "Sport" · `description` = tävling (+ ev. Pixieset-galleri; privat) · `all_day`=false.
- **Schema (litet tillägg, ersätter etag-maskineriet — tjänsten äger Google-länken):**
  `matchen.kalender_jobb_id TEXT` (tjänstens `id`) + `matchen.kalender_status TEXT`
  (cache av "Väntar/Synkad" ur `google_event_id`). Additiv migrering (SCHEMA_VERSION-bump).
- `tavling.kalender`-bool behålls = "lägg den här tävlingens matcher i kalendern"
  (default-val för nya matcher i tävlingen).

### B3. Riktning (vad "two-way" betyder för DPT2)

- **DPT2 → tjänst:** push. DPT2 äger matchdatan; skapa/ändra/radera speglas ut som jobb.
- **Tjänst → DPT2:** läs (`source`=`google` ⇒ någon ändrade i Google).
  `[BEKRÄFTA]` — ska en Google-sidig ändring av **tid/plats** dras *tillbaka in i matchen*
  (äkta two-way för matchfälten), eller bara **visas** som "ändrad i kalendern"? Rekommendation:
  börja med *visa + knapp "Uppdatera match ur kalendern"* (enkelt, ingen tyst överskrivning).

### B4. Trigger & radering

- "Lägg i kalender" / "Synka" per match **+** auto-push vid `spara_match` om matchens
  tävling är kalender-aktiverad. `[BEKRÄFTA auto vs bara manuellt]`
- Radera match → `DELETE /api/events/:id` (speglas till Google). Jobb utan match i DPT2
  (Landskap/Event/Övrigt) rörs inte.

### B5. Visning av kommande jobb

Tjänsten kan visa *alla* kategorier via publika API:t. Scope = inga nya storvyer, så minimalt:
en "Kommande"-strimma (Matcher-panelens topp eller en liten widget) som läser
`/api/public/events`. `[BEKRÄFTA]` — ska DPT2 visa kalendern alls, eller bara **pusha ut
matcher** och låta webbplatsen bädda in `/kommande` (iframe)?

### B6. Icke-match-jobb (Landskap/Event/Övrigt)

Denna omgång: **bara matcher → Sport-jobb**. Att skapa generella jobb (bröllop/porträtt)
från DPT2 = möjlig senare utökning (tjänsten stödjer det redan). `[BEKRÄFTA att det är utanför scope nu]`

### B7. UI-krav (till Design)

- Match-rad/-editor: liten kalender-status-pill (Väntar / Synkad ✓ / Ändrad i kalendern ⚠)
  + "Lägg i kalender"/"Synka".
- Tävlingskort (Lag & tävlingar): toggle "Lägg matcher i kalendern".
- Kategorifärger från INTEGRATION.md (Sport blå / Landskap orange / Event rosa / Övrigt grön);
  neutralt utseende för okänd/null-kategori (taxonomin kan växa).

---

## Öppna frågor till Stig

**Del A**
1. Väljarmodell A2 — hybrid (välj-ur-register-eller-skapa-inline) OK som default?

**Del B** (mycket mindre nu när syncen är en färdig tjänst)
2. **Riktning (B3):** ska Google-sidiga tid/plats-ändringar dras tillbaka *in i matchen*,
   eller bara visas med en manuell "uppdatera"-knapp?
3. **Visning (B5):** ska DPT2 visa kommande jobb (alla kategorier), eller bara pusha ut
   matcher och låta sajten sköta visningen?
4. **Scope (B6):** bara matcher denna omgång, eller vill du kunna skapa generella jobb
   (porträtt/bröllop) från DPT2 direkt?
5. **Varaktighet (B2):** default matchlängd per sport för `end_at` — fotboll 2h, handboll 1h30?
6. Har du **API-nyckeln** satt som `CALENDAR_SYNC_API_KEY` i `.zshrc` redan, eller ska den
   genereras/hämtas?
