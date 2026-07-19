# Projekt: DPT v5 & iOS v2 — eventmodell-branchen

Egen branch/projekt för version 5 av DPT2 (desktop) och version 2 av iOS-appen.
Bygger vidare på huvudprojektet "Dalecarlia Photo Tools UI (DPT2)" — dess CLAUDE.md-regler gäller även här.

## Handoff-riktning
- **Design → Code:** handoff-anvisningar skrivs TILL Code-teamet (`design_handoff_*/HANDOFF.md`).
- Leveransen är **löpande**: delar mergas till befintlig lösning allteftersom, ingen storrelease.

## ⚠ Låsta funktioner (ärvda från huvudprojektet — får ALDRIG regreras)
1. **Gren-palett (fast):** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Signalen är färgad kant/markör — ingen textetikett "DAM". Ingen kant om gren är okänd.
2. **Publicera → Live:** appen visar den riktiga server-renderade Horisont-bilden; prototypernas CSS-skisser är prototyp-begränsningar, INTE spec. Be aldrig Code "förenkla" till skissen.

## Beslut fattade i denna branch (skissrundor 1–4)
- **Modell 1a:** Tävling delas i två register — **Liga** (långlivad, historik) + **Event** (tidsbegränsat). Match har två valfria fält: `liga:` och `event:`. Se `DATAMODELL v5.md`.
- **Event i DPT2 (1e):** egen sektion under Planera — arbetsyta med matcher, grenar, deltagare. Mockup: `DPT v5 — Event.dc.html`.
- **Eventtyp är etikett** (mästerskap · cup · turnering · världscup…), inte beteende. Vi börjar med de typer vi känner till.
- **Gren + deltagare bor på eventet;** individens historik **härleds** (aldrig dubbellagrad). Individ = register som Lag.
- **På gång (1h):** auto per event (avstånd→heldag, under→matcher, efter→resultat) + override Heldag/Matcher. Match med event visas ALDRIG lösryckt — alltid "Del av {event}".
- **iOS:** restid mot nästa deltillfälle med override (deltillfälle eller eget klockslag, avstängning behövs ej); dynamisk bakgrund ur ★-pott kuraterad i DPT2 → egen bild → standard. Mockup: `DPT iOS v2 — Event.dc.html`. Vädret "här i dag" = 5 tidpunkter 08–20.
- **Kategorier:** toppnivå STATISK (Sport · Landskap · Människor · Film — styr hemsidans toppmeny; färger Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`). Underkategorier = redigerbart register (Människor: Porträtt, Bröllop, Student, Företag, Mode, Övrigt). Innehålls typ-nav: Sport · Landskap · Människor · Blogg · Film.
- **Konsert finns inte idag** — blir underkategori under Människor om det kommer.
- **UX-lyftet (byggt i `DPT v5.dc.html`, spec i `design_handoff_eventmodell/HANDOFF-etapp-2-4.md`):** jobbet som nav ("Aktivt jobb", "Efter jobb"), Gallra som ett flöde med stegindikator + profiler (Sport/Bröllop/Landskap/Porträtt), Träna borttagen ur nav (tyst träning via granskningsval, status → Inställningar), Publicera med momentmallar per kategori + publiceringskö, Innehåll med granskningskö + Film-typ, individregister med härledd historik, målmappar (Inställningar + flödesoverride), ★ iOS-bakgrund flaggas i Leverera.

- **SoMe utanför sporten (beslutat):** Bröllop/Student/Företag/Mode = per jobb-flagga `some: true|false` avgör ("Tjuvkik med kundens ok"); samtycket bor i avtalet, inte i verktyget. Landskapsmoment: Ny serie · Platsen · Bakom kulisserna · Blogg-puff. Länk till hemsidan valfri per inlägg. Samma kanaler som sport (IG + FB).

- **Tidsatt program / deltillfällen (beslutat, skiss-runda widget/app):** Gren (= disciplin) får valfria **pass** med egen datum+tid (kval dag 1, final dag 2). Eventets **program** för dagen HÄRLEDS = pass + kopplade matcher med tid + fria hållpunkter, sorterat/grupperat per dag (aldrig eget register). Individer per pass härleds via gren→deltagare. "Läs in spelschema" utökas att läsa events startlista/program (+ klistra in/CSV), manuellt justerbart. Kräver DATAMODELL + DPT2-uppdatering. Spec: `DATAMODELL v5.md` (Program/deltillfällen). Mockup som väckte det: `DPT iOS v2 - Jobbdetalj.dc.html`.

## Öppna frågor
- (inga just nu)
