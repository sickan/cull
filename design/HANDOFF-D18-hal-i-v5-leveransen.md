# Design-handoff D18 — Hål i v5/iOS v2-leveransen

*2026-07-20 · Från: Code · Till: Claude Design*
*Underlag: `Dalecarlia Photo Tools version 5 och iOS v2.zip` (uppackad i `design/v5-paket-2026-07-20/`), jämförd rad för rad mot faktisk UI-yta i DPT2 (`src/dpt2/ui/src/`) och iOS-appen (`~/Claude/ios-nef-brygga/Sources/`).*

Leveransen är stark där den träffar — Idag, Tävlingar, Lag & utövare, rik låsskärmswidget och D13-tonen räcker för att bygga. Detta dokument listar bara det som **saknas eller motsäger sig**, så vi vet vad vi kan börja på och vad vi ska vänta med.

Tre kategorier: **A** = be om skisser · **B** = bygg på befintlig form, säg till om ni vill rita · **C** = frågor som bara behöver ett besked, inte en mockup.

---

## A · Skisser vi behöver

### A1 · DPT2 Inställningar i sin helhet
Prototypens Inställningar innehåller **två kort**: Målmappar och Google Calendar. Den riktiga panelen (`panels/Installningar.svelte`) har fyra kort till:

| Kort | Innehåll som saknar form |
|---|---|
| **Realtidsnotiser** | Statuspill, flödesdiagram `Google Calendar → Webhook → DPT`, knapparna *Synka nu* (med synkar-tillstånd) och *Förnya push-kanal* |
| **Privata kalendrar** | **Tre distinkta tillstånd:** (1) ej konfigurerad → Client ID + Client secret + *Spara uppgifter*; (2) ej inloggad → *Logga in med Google* + *Byt uppgifter*; (3) inloggad → kalenderlista med kryssruta, färgprick, "Din"-tagg för primär, **inline-namnredigering** via pennknapp vid hover (Enter sparar, Esc avbryter), *Logga ut* |
| **Modell & träning** | En Visa/Dölj-rad som fäller ut **hela Träna-panelen** inbäddad (modellstatus, manuell omträning, Five-Star-import, granskningsmodal) |
| **Om** | Version, byggnummer, commit + fotnot om gammal dist |

Dessutom raden **API-nyckel** i Google Calendar-kortet (`satt (server-side)` / `saknas — sätt CALENDAR_SYNC_API_KEY`).

**Särskilt:** `HANDOFF-etapp-2-4.md` §9 beslutar att Träna flyttar ur nav och in i Inställningar "som rad, inte sektion" — och noterar själv "ej mockad ännu". Det är leveransens tyngsta omockade beslut: en 550-raders panel ska rymmas i en utfällbar rad. Vi vill inte gissa den formen.

### A2 · iOS Inställningar + Lagring i D13-ton
`SettingsView.swift` är i dag en rå SwiftUI-`Form` med **nio** sektioner. I den nya tonen (Skagen Hav-mörk, mässing, Saira Condensed, kortstil) kommer en systemform se ut som en främmande kropp.

1. **Om** — NEF-brygga, version, byggnummer, commit
2. **Server** — Bas-URL (URL-tangentbord)
3. **API-nyckel** — SecureField + hjälptext om Keychain
4. **Hemresa** — hemadress (matar hemresetexten på Hem)
5. **Kamerabrygga (FTP)** — lösenord + hjälptext (användare `dpt`, port 2121, adress). Jfr D13:s beslut att FTP-adressen ska sticka ut i mässing på Bilder — samma sträng, två ytor
6. **Väder** — väderkälla-picker
7. **Arenakoordinater** — lista namn + lat/lon, **swipe-to-delete**, plus tre fält och *Lägg till*. Detta är ett litet register i en inställningsvy — behöver en form
8. **Lagring — original på telefonen** → egen sheet `LagringView`: totalsumma, en sektion per importgrupp (namn + antal + storlek), *Radera hela gruppen*, swipe-to-delete per fil, tomläge
9. **Köade sändningar** — visas bara när kön > 0; rader per köad operation + *Skicka nu* (inaktiv offline). Hänger ihop med offlinekö-brickan "✈ N" i MatchHubs toolbar

### A3 · Jobb-fliken som nytt hem för matchflödet (blockerande)
D15 §B Q2 beslutar att **Matcher-fliken tas bort** (4 flikar → 3). Under den fliken bor i dag:

- `MatchHubView` — radlistan Publicera story · Matchtrupp & startelva · Föra matchen · Matchen är slut · Matchens bilder + utkastrader + live-CTA
- `TruppView` med sheet **OCRGranskningArk**
- `LiveStateView` ("Föra matchen")
- `LiveLageView` som **fullScreenCover**, med `MalFlodeView` som ännu en fullScreenCover ovanpå
- `MatchdataInfoArk`
- Offlinekö-brickan "✈ N" i toolbaren

Ingen skiss visar var något av detta hamnar när fliken försvinner. D13 medger själv att "Jobb-fliken och LIVE-läget är inte omgjorda än" — men den omgörningen är **förutsättningen** för att D15 Q2 ska gå att bygga. Vi vill inte flytta matchflödet på egen hand mitt i säsong.

### A4 · Rörligt — panel utan plats i naven
`HANDOFF-D10-rorligt.md` säger att Rörligt får "egen panel i DPT2:s rail". v5-prototypens nav är `Idag · Fotojobb · Tävlingar · Lag & utövare | Snabbplock · Gallra · Leverera · Publicera | Innehåll · På gång | Logg · Inställningar` — ingen Rörligt-post. Mockupen `DPT v5 - Rörligt.dc.html` följde inte heller med i zippen.

Var ska den ligga i den nya naven, och kan vi få mockupen?

---

## B · Ytor vi bygger på befintlig form om vi inte hör annat

Dessa finns i appen men inte i leveransen. Vi antar "oförändrad" och tar dem i nuvarande språk — säg till inom rimlig tid om ni vill rita dem.

- **Upprättning** — egen navpost under Efter jobb i den riktiga appen, saknas helt i prototypens nav. Vi behåller den där den är.
- **DPT2:s toppbar** — "Aktivt jobb"-chip med stäng-kryss, "Aktivt urval", synkmärke, **testlägesväxel + testbanner**, mock-pill, temaknapp. En egen yta ovanför alla paneler som ingen skiss rör. Notera att D11b §4 specificerar synkmärkets fyra lägen — de bor här.
- **Kommandopaletten ⌘K** — D11b §4 specificerar funktionen (index över utövare · tävling · fotojobb · gren, träff → djuplänk) men den har ingen visuell form. Den är redan byggd; vi låter den vara.
- **Ackrediteringsmejlets compose-dialog** i Fotojobb — egen overlay med mottagare + brödtext. Ingen motsvarighet i leveransen.

---

## C · Motsägelser — behöver besked, inte skisser

### C1 · Utövare som egen navpost?
`HANDOFF-D11b` §1: *"Lägg **Utövare** som egen post (bredvid Lag & ligor)."*
`HANDOFF-D16` §A + D17: ett register **Lag & utövare**, ingen egen Utövare-post.

D16 är senare och vi läser den som gällande. I koden finns `panels/Utovare.svelte` kvar med levande djuplänk (`mal='utovare'`) men utan navrad. Bekräfta att den ska förbli djuplänksmål och inte navpost.

### C2 · Migrering av utövarregistret — ja eller nej?
`HANDOFF-D11b` §2: slå ihop `lag(kind='individ')` + `individ` till ett nytt **`utovare`**-register, *"Migrering: deduplicera på namn+klubb+födelseår; behåll bägge id:n som alias"*.
`HANDOFF-D16` §A: *"Delar tabell i datan (`kind='individ'`) — **ren UI-konvergens, ingen migrering, noll datarisk**."*

Rakt motsatta instruktioner för samma register. Vi lutar åt D16 (senare + lägre risk), men detta är en datamodellfråga och vi vill ha det svart på vitt innan vi rör registret.

### C3 · Sigill-gaugen på låsskärmen — bort eller omfylld?
`HANDOFF-D15` §C och `D16` §B: den separata gauge-cirkeln *"utgår i denna rikare variant"*.
`HANDOFF-00-Helhet.md` §3: listar låsskärmens `accessoryCircular` sigill-gauge som **✓ levererad**.

`NastaJobbWidget` stöder i dag sex families, inklusive `.accessoryCircular`. Ska den familjen (a) tas bort ur widgeten, (b) behållas med sigillet som ren dekor utan nedräkning, eller (c) fyllas med något annat? Vi rör den inte förrän vi vet.

### C4 · "Skicka till telefonen" och synkmärket
D11b §4 säger att knappen i Program-kortet ska bort och ersättas av implicit push + ett synkmärke i fyra lägen. Märket finns byggt (`lib/SynkMarke.svelte`). Bekräfta att de fyra lägena (`ALLT UPPE` / `N VÄNTAR` / `SYNKAR` / `FEL`) och klick-för-logg är den slutliga formen — det ligger i toppbaren, som ingen mockup visar.

---

## Vad vi gör under tiden

Enligt tidslåset (*"designa nu, bygg efter SM"*) bygger vi inget av ovanstående före Friidrotts-SM 24–26/7. Vi fortsätter på det som redan är entydigt levererat och inte kolliderar med C1–C4.

Prioordning på svaren, om ni behöver en: **A3** (blockerar D15 Q2) → **C2** (datamodell, blockerar registret) → **A1** → **C1/C3/C4** → **A2** → **A4**.
