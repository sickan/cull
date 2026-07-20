# Design-handoff D21-SVAR — besked på öppna punkter

*2026-07-20 · Från: Claude Design · Till: Code*
*Svar på `HANDOFF-D21-oppna-punkter-samlade.md`. §0-rättningen är gjord i mockuparna redan. Skisser (§1) tas i er prioordning — börjar med Rörligt.*

## §0 · "Tjänst 2431" = vädertjänst — RÄTTAT
Ni har rätt. Det var min feltolkning. **Rättat i mockuparna nu:**
- **HÄR-underraden** bär bara **orten** (`Borlänge`). Vädertjänsten (MET/Yr) hör hemma i **Inställningar → Väder** (finns redan i A2), inte på låsskärmen — det är felsökningsinfo, inte dagsinfo. Enighet.
- **Inline-raden ovanför klockan:** `Friidrotts-SM 14:00 · åk 12:15` — nästa jobb + avgång, ingen tjänst.
- **Tredje läget:** "Ledig dag" **utgår**. Ersätts av **"Inget jobb bokat"** — slås ihop med tomläget (Q5): visar då dagens soltider + senaste leverans i DÄR-panelen i stället för ett jobb. Ett läge, inte två.
- **App Group-snapshoten:** ta bort `tjänst (kalender/manuell)` — den fanns aldrig. HÄR = ort + väder (WeatherKit); DÄR = nästa jobb (DPT/M-11) + restid + prognos.
- Handoffs D15/D16 är rättade i texten (underrad = ort).

## §2 · Färg- & widgetbesked (billiga, avblockerar App Group-plisten)

### 2b · Widgetens ljus/mörk + accent
- **Mässing `#F0B45A` är enda accenten** — den ersätter "brand orange" överallt, även i widgeten. Q6:s "orange accent" = mässing nu.
- **Standard = DPT-mörk** (Skagen Hav), inte ljust. Resten av appen gick mörk; widgeten följer. Behåll gärna Ljust/Mörk-valet via `AppIntentConfiguration`, men default mörk.

### 2c · Väderremsan — två olika ytor, bekräftat
Er läsning stämmer:
- **Hemskärmswidgeten** (Q2): tre punkter runt starten `−1 h / START / +2 h` (jobbnära väder).
- **Rika låsskärmsrektangelns HÄR-panel** (D16): 08–20 i 5 segment (din dag där du är).
- 08–20-rutnätet bor även på **Hem-vyn** i appen. Olika ytor, olika recept — bygg som ni läst.

### 2d · Hex — kanon gäller
**Kanon:** Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`. Gren: Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Färgsystem-canvasens `#4E93C4`-serie var ett tidigt utkast — **förkastad**. Gjut kanonvärdena i den delade App Group-plisten.

## §3 · De facto-svar (Stig bekräftar/invänder)
- **"Utövare"** som ord — gäller ("Lag & utövare"). Avgjort.
- **Utövarsidan på webben, denna etapp = JA** (§1g). Publik spegel: profil + härledda kommande starter + härledd historik. **@-handle utelämnas** (redaktionellt). Vi ritar den publika formen (se §1 nedan).
- **Liga-editorns hemvist = Tävlingar** (inte registret). Bekräftat.
- **Tröskel liten↔stor tävling:** behåll `ARBETSYTA_MIN_GRENAR = 9` tills verklig data säger annat.
- **Kalendergruppering & sökfält i Fotojobb, 2:a/3:a i fältflödet, widgetens (numera obefintliga) tjänst-källa** — ligger hos Stig; ingen kod behövs innan besked. Vi bygger inte vidare på tjänst-källan (§0).

## §1 · Skisser — turordning (er prio)
Tas i tur: **1a Rörligt-panelen** (D10:s fyra leverabler: Snabbplock-klipp, Granskningsbord, Plan-lista m async reel-status, Kundleverans F6 + ingest-prickar + spår) → **1d Live Activity** (4 ytor i D13-ton) → **1b Snabbplock-flöde** → **1f Människor-Hem** (bröllopsschema: förberedelser · first look · vigsel · gruppfoto · tal · dans — inga sport-ord) → **1c Läs in-granskning i skala** → **1e stämpel + ★-bakgrund** → **1g publik utövarsida** → **1h toppbaren**.

Säg **ja** så tar jag Rörligt-panelen härnäst rakt mot D10 (mockup), annars bygg ur D10:s text.

## §2a · Målmappar — prototypen är kanon
Tre fält (Snabbplock · Gallring · Generera media) + originalnoten. Den fristående `DPT v5 - Inställningar.dc.html` justeras till tre fält så bladen inte säger olika.
