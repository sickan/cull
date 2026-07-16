# Design-handoff D6 — Låsskärm & widgets (UTÖKAT: B-010 + B-009)

*2026-07-16 · Till: Claude Design · Från: Code · P3, men designen kan mogna
parallellt. Ett paket: allt som syns UTANFÖR appen på telefonen.*

## Uppdraget i två delar

### 1. Live Activity — "låsskärmen som startsida" (B-010)
Under pågående jobb/match ska det viktigaste finnas direkt på låsskärmen.
Tre format att designa (hårda storleksbegränsningar):
- **Kompakt** (Dynamic Island sidor): t.ex. ställning · matchklocka
- **Expanderad** (Island håll-inne): lag, ställning, moment, nästa åtgärd?
- **Låsskärmskort:** matchen/jobbet + restid/väder? (B-011-spiken vill lägga
  restid + väder här — designa med den tanken)

Frågor: vad triggar aktiviteten (matchdag? LIVE-läge startat?), vad visas
för icke-match-jobb (bröllop/landskap), när försvinner den.

### 2. Widgets (B-009)
- **Hemskärm** (small + medium): nästa jobb/match med tid/plats/väder?
  senaste publicering? På gång-lista?
- **Låsskärm** (cirkulär/rektangulär/inline — mycket små ytor): börja med EN
  kompakt variant — vad är den enda viktigaste raden?

## Fakta

- Datakällor som finns: fotojobb-API (45-dagars kurerade jobb), matchpaket
  (lag/avspark/ställning), väder-API (MET/Yr per plats), restid byggs nu
  (MapKit, "när måste jag åka").
- Appens språk: mörk Skagen Hav, Saira, kategorifärger Hav/Sol/Rosé/Film.
  Widgets/Live Activity ska kännas som samma app på systemets villkor.

## Leverabel

Mockups per format (Live Activity ×3, widget small/medium, låsskärm ×1) +
triggerreglerna (fråga ovan). Referens: `BACKLOG.md` (B-009/B-010/B-011 → D6).
