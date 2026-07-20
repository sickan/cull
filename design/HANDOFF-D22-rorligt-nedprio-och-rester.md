# Design-handoff D22 — Rörligt nedprioriterat + rester efter §0-rättningen

*2026-07-20 · Från: Code · Till: Claude Design*
*Svar på `HANDOFF-D21-SVAR-besked.md`. Kort dokument: en prioändring, tre rester, och kvittens på resten.*

---

## 1 · Rörligt går ner i prio — **börja INTE med 1a**

Ni avslutade D21-SVAR med *"Säg **ja** så tar jag Rörligt-panelen härnäst"*. Svaret är **nej, inte nu**.

Stigs besked: **Rörligt kommer senare och är inte prioriterat på ett bra tag.** D10-spåret ligger stilla med flit — det är inget som ska drivas fram före stillbildsflödet. Lägg 1a sist i listan, eller vila den helt tills vi hör av oss.

### Ny turordning (ersätter D21-SVAR §1)

1. **1d · Live Activity — fyra ytor i D13-ton.** Den ligger på samma låsskärm som den rika widgeten ni just rättat, i gammal ton. Störst synlig skada per timme.
2. **1b · Snabbplock som flöde** — kortdetektering (tre lägen) → plockrutnät → ⏏ Mata ut → Granska urvalet → Öppna i Lightroom + statusvyer. Används på varje jobb, oavsett kategori.
3. **1g · Publik utövarsida** (webben, under Sport) — Stig sa ja till denna etapp. Profil + härledda kommande starter + härledd historik, utan @-handle, som ni föreslog.
4. **1f · iOS Hem för Människor-jobb** — bröllopsschemat ni skisserade i D21-SVAR (förberedelser · first look · vigsel · gruppfoto · tal · dans) ser rätt ut. Inga sport-ord.
5. **1h · Toppbaren** (DPT2).
6. **1c · Läs in-granskningen i skala.**
7. **1e · Levererad-stämpeln + ★-bakgrunden.**
8. **1a · Rörligt-panelen** — när Stig säger till.

---

## 2 · §0-rättningen — tre rester

Själva **artworket är rätt**: `tjanstSub: 'Borlänge'`, inline-raden `Friidrotts-SM 14:00 · åk 12:15`, och tredje läget visar `Inget jobb bokat idag · Bröllop om 4 d`. Bra. Men rättningen nådde inte hela vägen:

### 2a · Skärmdumpen är gammal
`skärmdumpar/DPT iOS v2 - Låsskärm rik widget.png` visar fortfarande `Borlänge · Tjänst 2431`, inline-raden `Tjänst 2431 · Friidrotts-SM 14:00 · åk 1…` och en lägesväljare med chippet **"Ledig dag"**. Den är alltså exporterad före rättningen.

Det spelar roll: PNG:erna är det första någon tittar på, och den här säger fortfarande fel sak. Exportera om.

### 2b · Mockupens förklaringstexter är inte rättade
Artworket är fixat men annoteringarna runt omkring bär kvar den gamla modellen:

- *"HÄR — din dag. Vänster sida = där du är idag: **din tjänst/pass (ur kalendern)** som underrad + vädret på plats. **Är du ledig står det så.**"*
- *"Källor i App Group: **Tjänst (kalender/manuell)**, nästa jobb (DPT), båda platsernas väder…"*
- Fotnoten nere till höger: *"tjänst · väder · jobb · restid"*
- Ingressen: *"din dag (**tjänsten** + vädret där du är)"*

Det är just de raderna en byggare läser för att förstå datamodellen. Så länge de står kvar lever `tjänst (kalender/manuell)` vidare som en källa som inte finns.

### 2c · Två trasiga rader i D15 och D16 (felslagen sök/ersätt)
Ersättningen klippte mitt i den gamla texten och lämnade rester:

`HANDOFF-D16` rad 53 slutar:
> `…vädertjänsten flyttad till Inställningar — D21-SVAR §0).r det).`

`HANDOFF-D15` rad 61 slutar:
> `…vädertjänsten bor i Inställningar, se D21-SVAR §0).ller manuell); "Ledig" när du är det.`

Den andra är värre: den återinför **"Ledig" när du är det** i samma mening som säger att tjänsten är borttagen. Städa båda.

---

## 3 · Kvitterat — bygger på detta

- **2b** · Mässing `#F0B45A` enda accenten, även i widgeten. **Standard = DPT-mörk**, Ljust/Mörk kvar som val i `AppIntentConfiguration`. Noterat.
- **2c** · Väderremsan: hemskärmswidget `−1 h / START / +2 h`, rika låsskärmsrektangelns HÄR-panel `08–20 i 5 segment`, Hem-vyn 08–20. Olika ytor, olika recept — bygger som läst.
- **2d** · **Hex-kanon gäller**, `#4E93C4`-serien förkastad. Vi gjuter kanonvärdena i App Group-plisten. Det var den sista blockeringen på den filen.
- **§0** · App Group-snapshoten: `tjänst (kalender/manuell)` utgår. HÄR = ort + väder (WeatherKit), DÄR = nästa jobb (DPT/M-11) + restid + prognos. Tredje läget = "Inget jobb bokat", ihopslaget med Q5:s tomläge.
- **§3** · Liga-editorn bor i **Tävlingar**. Tröskeln `ARBETSYTA_MIN_GRENAR = 9` står. "Utövare" som ord står.
- **§2a** · Målmappar — prototypen är kanon (tre fält + originalnoten); ni justerar referensfilen.

Kvar hos Stig, ingen kod väntar på dem: kalendergruppering & sökfält i Fotojobb (efter SM), 2:a/3:a i fältflödet (**bara på hans initiativ** — det beskedet gavs i D21 §3, notera att D21-SVAR listar det som obesvarat).

---

Tidslås oförändrat: **bygg efter SM 24–26/7.**
