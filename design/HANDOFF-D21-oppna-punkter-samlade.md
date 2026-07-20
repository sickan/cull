# Design-handoff D21 — Samlade frågetecken och luckor efter D19

*2026-07-20 · Från: Code · Till: Claude Design*
*Ersätter inte `HANDOFF-D20-kvittens-och-toppbaren.md` — kompletterar den. D20 bar bekräftelserna (A4, C3) och de två Inställnings-inkonsistenserna; detta är en full genomgång av allt som fortfarande står öppet, tvärs samtliga handoffs D10–D19.*

Metod: varje handoff i paketet lästes mot faktisk UI-yta i DPT2 (`src/dpt2/ui/src/`) och iOS (`ios-nef-brygga/Sources/`), och mot prototypernas verkliga innehåll (inte handoffarnas beskrivning av dem).

Fyra delar: **§0** ett missförstånd som måste rättas först · **§1** ytor som saknar skiss · **§2** motsägelser att reda ut · **§3** besked från Stig på era öppna frågor.

---

## §0 · "Tjänst 2431" betyder **vädertjänst**, inte tjänstgöringspass

Detta är rundans viktigaste punkt, för det bär ett helt widgetläge.

I den byggda appen är HÄR-underraden `Borlänge · MET/Yr` — **GPS-orten plus vilken vädertjänst dagens väder kom ur**. Koden är entydig:

```
Sources/SnapshotSkrivare.swift:140
// Stigs "tjänst" = vilken VÄDERTJÄNST HÄR-vädret kom ur
```

Samma sak i `Widgets/NastaJobbWidget.swift:771` (*"'Borlänge · MET/Yr' — GPS-orten (här) och vädertjänsten vädret kom ur"*) och i `HarIdagWidget`s egen beskrivning: *"Dagens väder där du är — plus ort och vädertjänst."* Det finns en **Väderkälla**-picker i iOS Inställningar som styr värdet (`Settings.Vaderkalla`, MET/Yr default).

`HANDOFF-D16` §B och `HANDOFF-D15` §C läser "Tjänst 2431" som Stigs **dagliga tjänstgöring** och bygger tre saker på den läsningen:

1. Underraden `Borlänge · Tjänst 2431` beskriven som *"din dagliga tjänst ur kalender/manuell"*
2. Datakällan *"tjänst (kalender/manuell)"* i App Group-snapshoten — **den finns inte, och har aldrig funnits**
3. Läget **"Ledig dag"** — *"'Ledig' när du är det"* — ett av widgetens tre lägen, som saknar motsvarighet i verkligheten

**Konsekvens:** inline-raden ovanför klockan (`Tjänst 2431 · Friidrotts-SM 14:00 · åk 12:15`) lägger låsskärmens mest värdefulla rad delvis på ett leverantörsnamn. Och "Ledig dag" behöver ett nytt begrepp för att existera.

**Vad vi behöver från er:**
- Ska vädertjänsten alls synas på låsskärmen? Vår hållning: den hör hemma i **Inställningar**, inte på en yta där varje tecken är dyrt. Den är felsökningsinformation, inte dagsinformation.
- Vad ska HÄR-underraden bära i stället — bara orten, ort + soltider, ort + temperaturspann?
- Vad blir det tredje läget när "Ledig dag" faller? *"Inget jobb bokat"* finns redan som tomläge i `HANDOFF-widget-lasskarm.md` Q5 (dagens soltider + senaste leverans) — går de att slå ihop till ett läge?
- Inline-raden ovanför klockan: vad ska stå där när tjänsten utgår?

Stig har ingen tjänstgöringskalender som DPT känner till. Bygg inte vidare på den.

---

## §1 · Ytor som fortfarande saknar skiss

### 1a · Rörligt-panelen på riktigt (störst)
D19 markerar **A4 ✓**, men A4 var *placeringsfrågan* — och den är nu besvarad (egen navpost under Efter jobb, se D20). Själva panelen i prototypen är en platshållare: tre flikar (Klipp / Format / Publiceringskö) och två exempelkort.

`HANDOFF-D10-rorligt.md` specificerar fyra leverabler som ingen av dem finns:

- **1b Snabbplock för klipp** — rutnät av poster-JPEG:ar, hover spelar tyst, klick väljer. D10 kallar den *hemmet* och rekommenderar den byggd först.
- **1a Granskningsbord** — stor spelare, scrub, filmstrip, enkel in/ut. Detaljvyn bakom dubbelklick.
- **Plan-listan med async reel-status** — 🔵 inskickat → 🟡 bearbetas → 🟢 publicerat / 🔴 fel, per rad, tillstånd som överlever panelbyte. Plus kanalgränserna (IG Reel > 1:30, story-segment > 60 s) som gula informerande rader.
- **Kundleveransen (F6)** — fotografens leveranskort (signerad R2-länk, öppningsräknare, utgång, Kopiera/Förläng/Återkalla) **och** kundens egna mörka sida med sigillet + "Ladda ner 4K". Den sistnämnda är en helt egen publik yta.

Dessutom saknas **ingest-prickarna** (⚪ oproxad · 🔵 proxas · 🟢 redo · 🔴 master saknas · 🟣 Resolve) och **spåret** i Leverera/Publicera ("Rörligt · N klipp" + Öppna Rörligt →) som D10 §F1/§05 beskriver.

**Vi behöver panelen designad innan vi bygger den.** Alternativt: säg att den ska byggas rakt ur D10:s text, så tar vi den utan mockup — men då vill vi ha det uttryckligen.

### 1b · Snabbplock som flöde
Panelen är i verkligheten ett femstegsflöde och inget av det finns i prototypen:

- Kortdetektering med tre lägen: *Sätt i ett minneskort* / *Kort upptäckt* / *Kort genomgånget*
- Plockrutnätet med RAW-previews
- **⏏ Mata ut kortet**
- **Granska urvalet** som eget steg
- **Öppna i Lightroom · N bilder** + Lightroom-status/felvyer

Prototypen har bara målmapps-överstyrningen ("Ändra för denna körning…"). `HANDOFF-etapp-2-4.md` §12 säger att det mönstret "ska in i Snabbplock- och Gallra-panelerna (ej mockat där — följ Leverera)" — men det gäller bara mappraden, inte flödet runt omkring.

### 1c · Läs in-granskningen i skala
`HANDOFF-D12-SVAR` fråga 6 noterar själv: *"granskningen bör låna samma skal-tänk: gruppera avvikelser per gren/klass, inte 845 rader rakt ned. (Utanför denna leverans; noteras.)"*

Efter Friidrotts-SM blir detta akut — det är den ytan där en felinläst startlista upptäcks eller missas. Ska den med i nästa runda?

### 1d · iOS Live Activity — fyra ytor, noll skisser
`HANDOFF-widget-lasskarm.md` Q3 beslutar att widgeten ska *veta om* Live Activityn (`liveActivityAktivFor` i App Group-snapshoten), men själva LA-ytorna är aldrig ritade i D13-tonen:

- Dynamic Island **kompakt** (LIVE-puls, lagkoder, ställning, klocka)
- Dynamic Island **expanderad** (moment, lag, stor ställning, senaste händelsen)
- Låsskärmskort **före avspark** (åk senast / restid)
- Låsskärmskort **live**

De är byggda i gammal ton och kommer se främmande ut bredvid den rika låsskärmswidgeten, som ligger direkt intill dem på samma skärm.

### 1e · Levererad-stämpeln och ★-bakgrunden på iOS-sidan
`HANDOFF-00-Helhet.md` §3 och §5 listar båda som **○ att bygga**:

- **Levererad-stämpeln** — sigillet som våttstämpel ("LEVERERAD · datum") på klara jobb, "sätts i leverera-flödet". DPT2-sidan finns (Leverera-kortet med ★ iOS-bakgrund), men stämpelns utseende och var den syns i appen är inte ritat.
- **Dynamisk bakgrund ★** — ★-pott per kategori → egen bild → standard. Rotationen och fallback-kedjan har ingen visuell form.

### 1f · iOS Hem för Människor-jobb
`HANDOFF-etapp-2-4.md` §14 mockar **landskapsjobbet** (blå timmen / gyllene timmen / soluppgång i stället för matchtider) och säger att Människor-jobb följer "samma mönster — schema ur jobbet: vigsel/utspring osv. Ingen ny skärm."

Bröllopsschemat är dock inte som ett landskapsschema: förberedelser, first look, vigsel, gruppfoton, tal, dans. Vi vill inte gissa vilka hållpunkter som är kanoniska — och det är precis den kategori där [SPORT-ORD-städningen] är känsligast (en bröllopsplats är ingen arena, det finns ingen avspark).

### 1g · Utövarsidan på webben — **Stig säger ja, denna etapp**
Ni frågade i D11b §Öppet och D11-SVAR. Svaret är **ja, nu** (se §3). Det ger sportsidorna djup inför SM och EuroVolley.

DPT2-sidan är designad (`DPT v5 - Utövare.dc.html`), men den publika spegeln under **Sport** på dalecarliaphoto.se är det inte. Vi behöver veta hur mycket som speglas: profil + härledda kommande starter + härledd historik, eller ett smalare publikt kort? @-handle-fältet är redaktionellt och ska rimligen inte med. Historiken härleds redan ur grendeltagandet, så datamässigt är den gratis — det är den publika formen som saknas.

### 1h · Toppbaren
Begärd i D20 §3 — upprepas här bara för fullständighetens skull. Ingen ny information.

---

## §2 · Motsägelser att reda ut

### 2a · Målmappar — två blad säger olika
Utförligt i **D20 §2a**. Kort: fristående `DPT v5 - Inställningar.dc.html` visar två fält (Leverans/Publicering), kanon är tre (Snabbplock · Gallring · Generera media) + originalnoten. Vi bygger efter prototypen.

### 2b · Widgetens ljus/mörk-val beskrivs i gammalt färgspråk
`HANDOFF-widget-lasskarm.md` Q6: *"variant A (system-ljust + **orange accent**) … Standard = A"*, och identiteten sägs bäras av *"den **orange** åk-siffran"*.

Men D13/D15 slår fast att **mässing `#F0B45A` är enda accenten** och att den *ersätter* brand orange — "en accent, inte två parallella". Q6 skrevs före den låsningen.

**Fråga:** står Q6:s tvåvägsval (Ljust/DPT-mörk via `AppIntentConfiguration`) kvar, och i så fall — är variant A:s accent mässing nu? Och är standard fortfarande ljust, när resten av appen gick mörk?

### 2c · Widgetens väderremsa — två olika recept
- `HANDOFF-widget-lasskarm.md` Q2: byt fasta 08–20 mot **tre punkter runt starten** (`−1 h / START / +2 h`); 08–20-rutnätet *"stannar på Hem-vyn i appen"*.
- `HANDOFF-D16` §B (rik låsskärmswidget): HÄR-panelen visar **08–20 i 5 segment**.

Vi läser det som att de gäller **olika ytor** — Q2 hemskärmswidgeten (jobbnära väder), D16 den rika låsskärmsrektangelns HÄR-panel (din dag där du är). Bekräfta att den läsningen stämmer, så vi inte bygger fel remsa på fel yta.

### 2d · Hex-konflikten — bekräfta innan App Group-plisten gjuts
Färgsystem-canvasen från 19/7 bar `#4E93C4` · `#D19A3E` · `#D07E93` · `#A188C4`, medan kanon (och D13/D16) är `#2F7CB0` · `#C9871F` · `#C9657F` · `#8A6FB0`. D13 använder kanonvärdena, så vi utgår från att frågan är avgjord.

Men `HANDOFF-00-Helhet.md` §4 gör den **delade plisten i App Group till enda källan** för kategori/gren/status. Gjuter vi fel värden där driver allt isär på en gång. Vi vill ha ett uttryckligt "kanon gäller" innan vi rör den filen.

---

## §3 · Besked från Stig på era öppna frågor

Frågorna nedan har legat som "Öppet till Stig" i era handoffs sedan D11b. Här är svaren — de är beslut, inte diskussionsunderlag.

| Fråga | Ställdes i | **Besked** |
|---|---|---|
| **Tröskeln liten↔stor tävling** | D12-SVAR | **9 grenar.** Provisoriet `masterskap.ARBETSYTA_MIN_GRENAR = 9` blir beslut. Omprövas efter SM när arbetsytan körts skarpt. |
| **2:a/3:a i fältflödet** — alltid fråga? | D11-SVAR | **Bara på Stigs initiativ.** Fältflödet får inte bli längre — han kör många grenar per dag under SM. Mockupens "valfritt" är rätt. |
| **Utövarsidan på webben** | D11b, D11-SVAR | **Ja, denna etapp.** Se §1g — den publika formen behöver skissas. |
| **Widgetens tjänst-källa** | D15 §Kvar/öppet | **Frågan bygger på ett missförstånd — se §0.** "Tjänst" = vädertjänst. Det finns ingen tjänstgöringskalender. |
| **Utövare** vs *Personer* | D11b, D11-SVAR | **"Utövare" står.** Koden, D16 och D17 säger alla "Lag & utövare" — de facto avgjort. |
| **Kalendergruppering & sökfält i Fotojobb** | D16 §A | **Skjuts till efter SM.** Ny funktionalitet i just den panel Stig lever i under tävlingsdagarna — fel tillfälle. |

### Kvarstående fråga till er (den enda i denna del)
**Liga-editorns hemvist.** D17 §Att notera skriver: *"full liga-editor finns kvar (nås i denna prototyp ej från registret — flyttas dit i bygget)"*. Dit = **Tävlingar**, under Ligor-segmentet? Vi läser det så, men "dit" saknar syftning.

---

## Vad som INTE är öppet

För tydlighetens skull, så ingen runda går åt till att ta upp dem igen:

- **C1–C4** — besvarade i D18-SVAR, bygger på dem.
- **A1–A3** — levererade och granskade. A3:s "Var allt hamnar"-karta löste blockeringen av D15 Q2.
- **A4:s placeringsfråga** — besvarad i D20 (egen navpost under Efter jobb). Det är *panelinnehållet* som saknas, inte platsen.
- **Upprättning · ⌘K · ackrediteringsmejlets compose** — bekräftat "bygg på befintlig form".
- **Idag-skärmens exempeldata** — vi vet att kö/statistik/inkorg ska mot riktiga källor; det är vårt jobb, inte en designfråga.

---

## Prioordning, om ni behöver en

**§0 tjänst-missförståndet** (blockerar den rika låsskärmswidgeten, som annars är redo att byggas) → **1a Rörligt-panelen** (störst, hela D10-spåret står stilla utan den) → **2b/2c/2d färgbeskeden** (billiga, men blockerar App Group-plisten och widgetarbetet) → **1d Live Activity** (syns bredvid den nya låsskärmswidgeten) → **1g utövarsidan på webben** (Stig sa ja till denna etapp) → **1b Snabbplock** → **1f Människor-Hem** → **1c Läs in-granskningen** → **1e stämpel + ★-bakgrund**.

Tidslås oförändrat: **bygg efter SM 24–26/7.**
