# Design-handoff D8 — iOS: kalender som visningsläge under Fotojobb

*2026-07-16 · Till: Claude Design · Från: Code*
*FEAT-iOS-03. DPT-appen (mörk premium Skagen Hav, Saira, 5 flikar).*

## Dagens faktiska vy (ur koden — FotojobbView.swift)

- Horisontella **filter-chips** överst (kategori: Sport/Landskap/Människor/
  Film/Övrigt — kanoniska färgerna Hav `#2F7CB0` · Sol `#C9871F` · Rosé
  `#C9657F` · Film `#8A6FB0`)
- Därunder **kronologisk lista** (LazyVStack), auto-scroll till närmaste
  jobb, väder-badge per rad (~10 dagars prognos), heldags-/flerdagarsjobb
  som spann, krock-indikering mot privata kalendrar
- Datakälla: DPT2:s riktiga fotojobb via `/api/jobb` (kategoriserade,
  45-dagars fönster)

DPT2-desktopen har redan Lista/Tidslinje/Vecka/Månad-flikar — appen har bara
listan.

## Uppdraget

Ett **kalender-visningsläge** som alternativ till listan (växlare Lista ⇄
Kalender). Telefonyta — kompakt.

## Frågor att landa

1. **Månad eller vecka först?** (eller månad med expanderbar dag?) Stigs
   användning: se helgens/veckans jobb i tidssammanhang, upptäcka krockar.
2. **Cellspråket:** hur visas jobb i en trång månadscell — kategorifärgade
   prickar? staplar? Flerdagarsjobb som spann över celler?
3. **Dag-interaktion:** tap på dag → dagens jobb (ark? inline-expansion?).
   Därifrån samma jobbkort som listan har.
4. **Väder + krockar i kalenderytan** — får de plats, eller bara i
   dag-detaljen?
5. **Växlaren:** segment i toppen (som DPT2:s Lista/Vecka/Månad) eller
   ikon-toggle? Ska valet persistas?

## Leverabel tillbaka till Code

1. Mockup månads-/veckovyn (mörkt tema, iPhone-yta)
2. Cellspråket + flerdagarsspann
3. Dag-detaljens form
4. Växlarens placering

## Referenser
- `~/Claude/ios-nef-brygga/Sources/FotojobbView.swift` (+ KalenderView.swift
  — Kalender-fliken som redan visar jobb per dag, kan vara startpunkt/delas)
- Total backlog: `dpt/design/BACKLOG.md` (FEAT-iOS-03 → D8)
