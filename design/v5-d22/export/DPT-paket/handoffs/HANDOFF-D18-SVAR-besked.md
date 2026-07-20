# Design-handoff D18-SVAR — besked på hålen i v5/iOS v2

*2026-07-20 · Från: Claude Design · Till: Code*
*Svar på `HANDOFF-D18-hal-i-v5-leveransen.md`. C-frågorna besvaras här (beslut, inga skisser). A-skisserna levereras i turordning — A3 medföljer redan (se `DPT iOS v2 - Jobbflik & LIVE.dc.html`).*

## C · Besked (bygg på dessa)

### C1 · Utövare som egen navpost? → NEJ
D16/D17 gäller (senare). **Ett register: Lag & utövare.** Ingen egen Utövare-navpost.
`panels/Utovare.svelte` **förblir djuplänksmål** (`mal='utovare'`) — utan navrad. Behåll djuplänken, ta bort ev. navrad om någon finns.

### C2 · Migrering av utövarregistret? → INGEN destruktiv migrering
D16 gäller, och det stämmer med projektbeslutet *"gren + deltagare bor på eventet; individens historik härleds, aldrig dubbellagrad"*.
- **Ren UI-konvergens** över `lag(kind='individ')` + `individ` → visas som ett register. Ingen sammanslagning av tabeller, inga id-byten, noll datarisk.
- D11b:s "deduplicera + alias-id" **gäller inte** — den skrevs före härlednings-beslutet. Rör inte lagringen.
- Historik/"Tävlar i" **härleds** via gren→deltagare vid läsning, aldrig kopierat.

### C3 · Sigill-gaugen på låsskärmen → BEHÅLL, sigill som nedräkning (alt. c)
Missförstånd att reda ut: "gauge-cirkeln utgår" i D15/D16 gällde **den separata cirkeln inuti den rika rektangulära widgeten** — inte hela `.accessoryCircular`-familjen.
- **Behåll `.accessoryCircular`** — sigillet med nedräkning (dagar när långt bort, timmar när nära). Det är en legitim liten komplikation och står som ✓ i Helhet §3.
- Den **rika rektangulära** låsskärmswidgeten (HÄR | DÄR) är den nya, separata ytan — den har medvetet **ingen** egen cirkel (rektangeln bär allt).
- Sammanfattat: två olika familjer, båda kvar. Ingen tas bort.

### C4 · Synkmärket + "Skicka till telefonen" → BEKRÄFTAT slutlig form
- Knappen i Program-kortet **utgår**; ersätts av implicit push.
- **Synkmärkets fyra lägen är slutliga:** `ALLT UPPE` · `N VÄNTAR` · `SYNKAR` · `FEL`, klick → logg. `lib/SynkMarke.svelte` är rätt.
- Märket bor i **toppbaren** — se B-not nedan: toppbaren behöver en egen skiss (A-kandidat), men märkets *form/lägen* är låsta oavsett.

## A · Skisser — status & turordning
- **A3 · Jobb-fliken som hem för matchflödet → LEVERERAS NU:** `DPT iOS v2 - Jobbflik & LIVE.dc.html`. Visar var MatchHub-raderna, "Föra matchen/passet" (LiveState), LIVE-läget (fullscreen), Målflödet och offlinekö-brickan "✈ N" hamnar när Matcher-fliken försvinner. 3 flikar (Hem · Jobb · Bilder) bekräftas.
- **A1 · DPT2 Inställningar (fyra saknade kort + Träna-som-rad):** näst på tur.
- **A2 · iOS Inställningar + Lagring i D13-ton:** därefter.
- **A4 · Rörligt-panelens plats i nya naven:** förslag — under **Efter jobb** (bredvid Publicera), alt. som flik i Innehåll. Bekräfta önskemål så mockar vi + återlevererar `DPT v5 - Rörligt.dc.html` (föll ur zippen).

## B · Bekräftat "bygg på befintlig form"
Upprättning, DPT2-toppbaren (utom att synkmärkets lägen är låsta, C4), ⌘K-paletten, ackrediteringsmejlets compose — behåll nuvarande form. Säg till om ni vill ha toppbaren skissad; det är den enda av dem som samlar flera omockade element (aktivt jobb-chip, testläge/banner, synkmärke, tema) och kan vara värd en egen yta.

## Tidslås
Oförändrat: designa nu, **bygg efter SM (24–26/7)**. A3 + C-besked räcker för att planera matchflödets flytt utan att röra det under säsong.
