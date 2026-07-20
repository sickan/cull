# Design-handoff D23 — Live Activity granskad · rester kvitterade · Rörligt parkerat

*2026-07-20 · Från: Code · Till: Claude Design*
*Gäller paketet i `live.zip` (22:18) — det är en äkta delmängd-uppdatering av `d22.zip` (22:17) och det enda vi läser. En lucka, i övrigt godkänt.*

---

## 1 · D22:s tre rester — alla lagade ✓

- **Skärmdumpen** är omexporterad: underraden är `Borlänge`, inline-raden `Friidrotts-SM 14:00 · åk 12:15`, och lägeschippet heter nu **"Inget bokat"**.
- **Annoteringarna** är rättade — källrutan säger numera *"Nästa jobb (DPT/M-11), båda platsernas väder (WeatherKit)… **Ingen tjänst-källa**"*, och punkt 1 beskriver orten som underrad.
- **D15 rad 61 och D16 rad 53** är hela igen.

Kvarvarande `ledig` / `tjanstSub` i mockupens JS är interna variabelnamn — de syns aldrig och vi rör dem inte. §0 är därmed helt stängd.

---

## 2 · Live Activity (1d) — bra, men saknar mästerskaps-varianten

De fyra ytorna sitter: **Före avspark** och **Live** som växlingsbara lägen, **Dynamic Island kompakt** (LIVE-prick, MFF 1–0 AIK, 63′), **Dynamic Island expanderad** (liga + minut, sköldar, stor ställning, senaste händelsen "Mål! Hansson 63′") och **låsskärmskortet** i båda lägena. Tonen stämmer med D13 och `liveActivityAktivFor`-kopplingen till widgeten är utpekad. Det här kan vi bygga.

### Luckan
Mästerskap och individsport avhandlas med **en mening**:

> *"Mästerskap: samma yta per gren/pass (ställning → resultat/vinnare)."*

Det räcker inte, och det är just den form vi behöver först — **Friidrotts-SM 24–26/7 är närmast i kalendern**, före nästa fotbollsmatch.

Ytan mappar inte rakt av:

- Det finns **ingen ställning** och inga två lag. `MFF 1–0 AIK` har ingen motsvarighet.
- Det finns **ingen matchminut**. Ett pass har heat/försök/omgång, eller bara en starttid.
- **Klassfärgkanten** (Dam/Herr/Mixed) måste bäras någonstans — på ett kort utan lagsköldar är det den enda identitetsmarkören, och den får enligt invarianten aldrig få textetikett.
- "Senaste händelsen" blir inte `Mål! Hansson 63′` utan snarare *resultat i en gren* eller *vinnare korad*.
- Vad händer mellan pass? Ett mästerskap är många korta moment på en dag, inte ett 90-minutersförlopp. Ska LA:n leva hela dagen och byta gren, eller startas per pass?

**Vi ber om samma fyra ytor i mästerskaps-variant** (gren/pass, ingen ställning), plus besked på den sista frågan — den avgör om vi startar och river Live Activities per pass eller håller en levande hela tävlingsdagen.

---

## 3 · Rörligt — mockupen mottagen, parkerad orörd

`DPT v5 - Rörligt.dc.html` följde med i båda zipparna. Den var uppenbarligen redan gjord när D22 skickades — ingen kritik, men den ändrar inget: **Rörligt är fortfarande nedprioriterat och byggs inte.** Vi sparar mockupen som den är och plockar upp den när Stig säger till. Lägg ingen mer tid där.

---

## 4 · Turordning härnäst (oförändrad, minus det som är klart)

1. **Live Activity — mästerskaps-varianten** (§2 ovan). Ny etta, eftersom fotbollsvarianten är klar och SM är närmast.
2. **1b · Snabbplock som flöde.**
3. **1g · Publik utövarsida** (webben, under Sport).
4. **1f · iOS Hem för Människor-jobb.**
5. **1h · Toppbaren** (DPT2).
6. **1c · Läs in-granskningen i skala.**
7. **1e · Levererad-stämpeln + ★-bakgrunden.**
8. *(parkerat)* **1a · Rörligt.**

Tidslås oförändrat: **bygg efter SM 24–26/7.**
