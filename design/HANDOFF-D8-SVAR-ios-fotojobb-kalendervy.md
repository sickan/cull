# Design-svar D8 — iOS: kalender som visningsläge under Fotojobb

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D8-ios-fotojobb-kalendervy.md` (FEAT-iOS-03).
Klickbar mockup: `iOS D8 – Fotojobb Kalender.dc.html` — växla Lista ⇄ Kalender, tappa dagar.*

## Beslut på fråga 1–5

**1. Månad först, med dag-panel — ingen veckovy.** Stigs behov ("se helgens/veckans jobb
i tidssammanhang, upptäcka krockar") täcks av månaden + dag-panelen; en veckovy blir ett
tredje läge att underhålla utan eget jobb att göra. Månadsgridden är kompakt (~290px hög)
så dag-panelen får resten av ytan. Månadsbyte med ‹ › vid månadsrubriken; utanför
45-dagarsfönstret dimmas dagarna (datat finns inte).

**2. Cellspråket** (se annotationstavlan i mockupen):
- **Fylld prick** (5px) = jobb med tid den dagen, i kanonisk kategorifärg
  (Hav `#2F7CB0` · Sol `#C9871F` · Rosé `#C9657F` · Övrigt grå `#9AA3AD`; Film utgår —
  inga film-jobb i kalendern i v1).
  Max 3 prickar per cell; fler → tredje ersätts med "+".
- **Ring** (ofylld prick, kategorifärg) = leverans-deadline — inget fysiskt jobb men dagen
  är inte fri. (Deadlines VISAS alltså i kalendern, till skillnad från listan där de är
  en rad på jobbkortet.)
- **Spann-stapel** (4px, cellens fot, kategorifärg) = heldags-/flerdagarsjobb; löper
  obruten över celler, rundade ändar vid start/slut. Heldag en dag = kort stapel med båda
  ändar rundade. Spannjobb får INGEN prick (stapeln är markeringen).
- **Krock** = 1.5px röd ring (`#E06A5A`) runt dagsiffran. Bara indikatorn i cellen —
  detaljerna bor i dag-panelen.
- **Idag** = fylld accentcirkel (`#F0B45A`, mörk siffra). **Vald dag** = tonad
  accentplatta + ram.
- Legend-rad under gridden (kategorier + deadline-ring), 9.5px.

**3. Dag-interaktion: inline-panel under gridden — inget ark.** Tap på dag uppdaterar
panelen direkt (gridden står kvar → krock-jämförelse och snabb dag-hoppning). Panelen:
rubrik "Ons 16 juli · idag", därunder **samma jobbkort som listan** (kategoripunkt +
titel + metarad + status-badge + väder-badge) i samma skrollyta. Tom dag: "Inga jobb —
dagen är fri." Tap på jobbkort → samma detalj som från listan (befintlig navigering).

**4. Väder + krockar:** **liten vädersymbol i cellens övre högra hörn** för kommande
~10 dagar (7.5px, 40 %-vit, samma prognoskälla som listans badge; historik och bortom
fönstret = ingen symbol). Bara symbolen i cellen — grader och detaljer bor i
**dag-panelens jobbkort** (samma väder-badge som listan).
Krock: ring i cellen (beslut 2) + **eget krock-kort i dag-panelen** (röd-tonad bakgrund
`rgba(224,106,90,.08)`, etikett "KROCK · PRIVAT KALENDER", privata händelsens titel/tid
och vad den överlappar).

**5. Växlaren: text-segment "Lista | Kalender"** uppe till höger i titelraden — samma
segmentkomponent som Bilder-vyn redan har (bakgrund `rgba(255,255,255,.07)`, radie 9,
aktiv flik accent-tonad). Ikon-toggle avvisad: två ord är tydligare än två ikoner, och
mönstret finns redan i appen. **Valet persistas** (UserDefaults) — den som lever i
kalendern ska landa där nästa gång. Filter-chipsen (kategori) ligger kvar ovanför båda
lägena och filtrerar även kalenderns prickar/staplar.

## Implementation-noter

- Kalendern är en vy över SAMMA data/källa som listan (`/api/jobb`, 45-dagars fönster) —
  ingen ny fetch. `KalenderView.swift`s per-dag-gruppering kan återanvändas.
- Vecka börjar på måndag; veckodagsrad M T O T F L S (9.5px, spärrad).
- Cellhöjd ~52px, radie 9, gap 4 — gridden ryms i ~290px och lämnar >40 % av skärmen
  till dag-panelen på en 6.1".
- Auto-scroll-beteendet från listan motsvaras av att **idag är förvald dag** vid öppning.
- Offerter utan datum syns inte i kalendern (bara i listan) — medvetet; kalendern visar
  tid, listan visar pipeline.
