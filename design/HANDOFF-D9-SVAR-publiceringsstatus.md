# Design-svar D9 — Publiceringsstatus-språket

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D9-publiceringsstatus.md`. Mockup: `DPT2 D9 - Publiceringsstatus.dc.html`
(Innehåll · Människor i DPT2:s LJUSA tema, alla fyra statusar + expanderat fel).*

## Beslut på fråga 1–5

**1. Formen: chip med prick + text, före papperskorgen på raden.**
- Pill-chip — 7px prick + etikett i statusfärgen på tonad platta av samma färg
  (`{färg} @ 10–12 %`). Text behövs: färg ensam skiljer inte Publicerad från Live
  tillräckligt säkert.
- Radens anatomi oförändrad i övrigt: thumbnail · titel · metarad · [chip] · 🗑.
- **Hörnmarkeringen uppe till höger behålls i sin befintliga form** — bågen längs
  hörnradien med fade i båda ändar, samma komponent som Fotojobb/Matcher i DPT2 —
  men byter från alltid-grön till **statusens färg**. Ingen ny form; bara färgen
  blir semantisk. (Övriga hörn rörs inte av D9.) Vänsterkanten lämnas fri;
  på match-ytor är den grenens (⚠ LÅST palett).
- Metaraden bär tid/kontext i stället för dagens statiska "Publicerad 16 juli":
  Utkast → "Redigerad nyss · sparas löpande" · Publicerad → "Publicerad 15:57 ·
  bygget pågår ~2 min" · Live → "Live sedan 16 juli 14:04 · Visa på sajten ↗" ·
  Fel → "Publicering misslyckades 13:47".
- **Publicerat/Utkast-flikarna ersätts av filterchips** (Alla · Live · Utkast · Fel,
  med antal) — statusen sitter på raden, listan behöver inte delas i två vyer.
  Fel-chipen tonas röd när fel finns.

**Färger** (ljusa temats jordton — mockupen ligger i Innehålls-bibliotekets riktiga
crème-UI, inte appens mörka):
Utkast `#3E7CB0` · Publicerad `#B07A2A` · Live `#5C8F4A` · Fel `#C0492F`.
I appens/matchgrafikens mörka ytor används de ljusare systervarianterna
(`#5F9ED6` · `#E0B44F` · `#8CCB74` · `#E06A5A`) — samma semantik, per-tema-token.

**2. Fel-tillståndet: raden expanderar på plats.**
- Radens ram tonas röd (`rgba(192,73,47,.35)`, bakgrund `.04`), chip "Fel".
- Under en röd avdelare: **per-kanal-utfall** (✓/✕-rader — samma mönster som
  matchpubliceringens per-kanal-resultat, återanvänd komponenten) med orsak i klartext
  ("Sajt-deploy: workern svarade 502 (steg 3/4)").
- Åtgärder: primär **"Försök igen"** (kör bara de fallerade stegen) + sekundär
  "Visa logg". Ingen separat felsida.
- Fel-poster sorteras överst i sin grupp tills de är åtgärdade.

**3. Övergången publicerad→live: pulserande prick, ingen spinner.**
- Chipen visar **"Publicerad · bygger…"** och pricken pulserar mjukt
  (opacity 1→.35, 1.6s ease-in-out loop). Kortvyn: "Bygger…".
- Under pågående poll ändras inget annat på raden — inga procentsteg, ingen progressbar
  (bygget är 1–2 min och opåverkbart; pulsen säger "jobbar, lugn").
- När pollen bekräftar: chipen växlar till Live utan animation (statusskiftet ÄR
  belöningen). Timeout (>5 min utan svar) → Fel med orsak "Bygget svarar inte".

**4. Utkastknappen ersätts av autospar.**
- Allt sparas löpande som utkast; metaraden visar "Redigerad nyss · sparas löpande"
  (sedan "Redigerad 13:52"). Ingen knapp, ingen dialog.
- Den enda aktiva handlingen är **Publicera**. Utkast-status uppstår implicit vid första
  ändringen. "Utkast"-knappen tas bort när FEAT-09 landar (som Stig specat).

**5. En gemensam komponent: `StatusChip(status, sedan, kompakt)`.**
- Samma chip i Innehålls-biblioteket, Matchpublicerings-flödet och På gång.
- `kompakt`-läget (trånga rader, t.ex. På gång) = prick + kort etikett utan platta.
- Delvis publicerad (öppna luckan i statuskontexten): en post som är live i någon kanal
  men fel/pågående i annan visar den SÄMSTA statusen på chipen (Fel > Bygger > Live) —
  detaljerna syns i per-kanal-listan. Ingen egen femte färg.

## Tillgänglighet
Chipens text gör att färgblindhet aldrig är blockerande; prickens puls är enda rörelsen
och stannar med `prefers-reduced-motion`.

## Facit i prototypen
D9-språket är inarbetat i `Dalecarlia Photo Tools.dc.html` (Innehåll → Publicerat & utkast):
hörnbåge i statusfärg på varje rad, chip endast vid Fel/Bygger/Live (Utkast bär status via
båge + metarad "sparas löpande"), fel-rad expanderad med per-kanal-utfall + Försök igen,
filterchips Alla · Live · Utkast · Fel. Prototypen är facit för form och färg.
