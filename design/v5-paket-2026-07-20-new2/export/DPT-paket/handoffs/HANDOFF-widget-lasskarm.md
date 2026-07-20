# HANDOFF — Widget & låsskärm (svar på B-009)

*2026-07-19 · Till: Code (iOS) · Från: Claude Design*
*Underlag: er handoff B-009 (`~/Claude/ios-nef-brygga`, 8b88f79) · Mockup: `DPT iOS v2 — Widget & Låsskärm.dc.html`*
*Egen branch. Löpande leverans. Detta är designöversynen ni bad om — riv isär vidare.*

---

## Kort version

Ytan ni byggde är rätt. Sex familjer, en datakälla, statisk snapshot — allt behållet. Ändringarna nedan är **beslut på era sex öppna frågor** plus två saker ni inte frågade om. Ingen ny datakälla krävs; ett par av besluten kräver ett nytt fält i App Group-snapshoten (utpekat per punkt).

Mockupen visar alla sex ytorna i kontext (låsskärm + hemskärm), specialfallen, och ett A/B för identiteten.

---

## Beslut på era öppna frågor (§5)

### Q1 · Cirkeln — behåll men bygg om
Väder + två siffror bär inte sin plats. Gör `accessoryCircular` till en **nedräkningsgauge**: `Gauge`/`ProgressView(timerInterval:)` där ringen töms mot *åk senast*, med kvarvarande tid i mitten (`ÅK OM 1:02`). Ringen är det enda cirkeln gör bättre än rektangeln. **Vädret utgår ur cirkeln** och bärs av rektangeln istället — då slutar de dubbleras.

### Q2 · Väderremsan — jobbnära, inte dygnsrutnät
På widgeten byt de fasta 08–20 mot **tre punkter runt starten**: `−1 h / START / +2 h`. Widgeten handlar om nästa jobb; timmarna runt jobbet är det relevanta. Det fasta 08–20-rutnätet **stannar på Hem-vyn** i appen (oförändrat där).

### Q3 · Två låsskärmsytor för samma jobb — låt dem veta om varandra
När Live Activityns FÖRE-kort är aktivt för ett jobb ska widgetens `accessoryRectangular` **hoppa fram till nästa jobb** (visar "NÄSTA" istället). En yta = ett budskap.
**Kräver:** appen skriver ett fält i App Group-snapshoten, t.ex. `liveActivityAktivFor: <jobbId?>`. Widgeten jämför mot sitt eget "aktuella jobb" och stegar fram vid träff. Ingen kommunikation mellan extensionerna behövs — bara den delade filen.

### Q4 · DÄREFTER i large — krymp vädret, inte listan
Med jobbnära väder (Q2) ryms väder på **en** rad och soltiderna komprimeras till samma rad (`☀ 04:02 · 21:50`). Det frigör plats för **3 DÄREFTER-rader** (mot 2). Ingen separat väder/sol-widget behövs.

### Q5 · Tomläget — dagens ljus + senaste leverans
"Inget bokat" ensamt är för lite. Visa **dagens soltider** (upp/ned) och **senaste leverans** ("EuroVolley levererad 22/7"). En fotograf med tom kalender vill veta ljuset idag och se att förra jobbet är ute. Gäller small/medium/large i stigande detalj.

### Q6 · Eget uttryck — erbjud båda som val (standard = ljust)
Stig får **välja** mellan variant A (system-ljust + orange accent) och variant B (DPT-mörk / Skagen Hav) via **widgetkonfigurationen** (`AppIntentConfiguration` → parameter "Utseende: Ljust / DPT-mörk"). **Standard = A.** Identiteten bärs oavsett av **hästmärket**, den **orange åk-siffran** och **kategoripricken**; behåll SF Pro, **ingen egen font**. Båda varianterna finns i mockupens *Identitet*-sektion.
**Kräver:** en enum-parameter i widgetens intent + två renderingsgrenar (ljus/mörk) som delar samma layout.

---

## Dessutom — inte frågor ni ställde

**Färskhet:** dimningen till 55–60 % är rätt men räcker inte ensam. Lägg en diskret tidsstämpel i dagsraden (`IDAG 07:01`). Ett blekt kort *utan* tid läses som "fel", inte "gammalt".

**Okänd arena (§4):** låt inte raderna försvinna tyst. Ersätt restid/väder/karta med en lugn uppmaning — "Plats ej satt — lägg till i DPT för restid & väder" — och en dämpad platshållare där väder/karta annars satt. Se mockupens *Okänd arena · Medium*.

**Kategorifärg som sanning:** era duplicerade Hav/Sol/Rosé/Film driftar isär om paletten ändras. Lägg färgerna som en **delad resurs i App Group** (plist eller genererad Swift-fil från samma källa som `Theme.swift`) så extension och app läser samma värde. Kanonvärden (från branch-CLAUDE): Sport/Hav `#2F7CB0` · Landskap/Sol `#C9871F` · Människor/Rosé `#C9657F` · Film `#8A6FB0`.

---

## Oförändrat / bekräftat

- Sex familjer, en snapshot, statiskt — behåll.
- Klickmål enligt er tabell (large/medium multi-target; small + låsskärm single-target → Jobb-fliken). Oförändrat.
- "Dagen först" (`IDAG 07:01`) och "Heldag = bara dagen" — behåll, de fungerar i mockupen.
- Låsskärm = monokromt (ingen kategorifärg där) · hemskärm = alltid ljust läge. Designen respekterar båda.

## Kända hål (ligger kvar hos er, kod ej design)
- Sun Surveyor / Yr djuplänkar — designen förutsätter garanterad fallback; oförändrat.
- `JobbDetaljView` (den ni tvingades bygga) — **bokad: egen designrunda** (Stig sa ja). Kommer som separat handoff; bygg vidare på det funktionella tills vidare, ingen omdesign behövs innan dess.

## Leveransordning (förslag)
1. Q1 (gauge) + Q2 (jobbnära väder) — ren UI, ingen ny data.
2. Q5 (tomläge) + okänd arena + färskhetsstämpel — ren UI.
3. Q4 (large-omflödet) — följer av Q2.
4. Q6 (ljus/mörk-val) — kräver enum-parameter i widgetens intent.
5. Q3 (LA-medvetenhet) — kräver `liveActivityAktivFor`-fältet i snapshoten.
6. Kategorifärg → delad App Group-resurs — städning, kan gå när som helst.
7. *(separat)* JobbDetaljView-designrunda — se HANDOFF nedan.

---

## JobbDetaljView — designrunda (mockup: `DPT iOS v2 - Jobbdetalj.dc.html`)

Den detaljvy ni tvingades bygga odesignad (§7 i er handoff) är nu ritad. Fokus denna runda = **när/var/tid**. Grundton **mörk Skagen Hav** (som appens hemskärm), inte en ljus systemvy.

**Ingång:** samma vy öppnas från både widget/låsskärm (nästa jobb) och jobblistan. En vy, två dörrar.

**Uppifrån och ned:**
- **Hero:** kategoribadge (Hav-prick + "SPORT · MÄSTERSKAP"), jobbtitel (Saira Condensed), undertitel (t.ex. "Dag 1 av 3 · fotouppdrag"), och — om jobbet hör till ett event — **"Del av {event}"** som klickbar rad. Visas ALLTID när koppling finns; jobbet ska aldrig kännas lösryckt. Toppen tonas av kategorifärgen.
- **Signatur-sigillet:** samma märke som widgeten — hästen i mitten, nedräkning till avgång som orange ring runt om ("ÅK OM 1:02"). Under: tre tal — **Åk senast · Restid · Start**. Detta är vyns hjärta och den visuella länken till widget/låsskärm.
- **Sikta på annan tid:** samma sheet som Hem-vyn (deltillfälle eller eget klockslag). Återanvänd komponenten.
- **Dagens deltillfällen:** tidslinje (prick + tid + namn + not), nästa markeras med orange prick + "NÄST"-badge. Data = eventets/jobbets schemapunkter för dagen.
- **Karta:** kort mot arenan med pin + avstånd/restid + **Navigera** (Google Maps, samma som widgeten). Skisskartan i mockupen är platshållare — riktig karta = MapKit/server. Under kartan: **Sätt / ändra plats** (samma verkan som "okänd arena"-flödet).
- **Vid arenan:** jobbnära väder (−1h/start/+2h/+4h), samma serie som widgeten.
- **Ljuset idag:** blå timmen · gyllene timmen · soluppgång · solnedgång.

**Handlingar denna runda:** *Sätt/ändra plats* + *Sikta på annan tid*. Navigera finns på kartkortet. **Senare runda:** ring kontakt, öppna gallring/leverera.

**Okänd arena:** samma logik som widgeten — ingen karta/restid/väder, "Sätt plats"-uppmaningen bär tomrummet.

