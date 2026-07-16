# Design-svar D6 — Låsskärm & widgets (B-010 + B-009 + B-011)

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D6-lasskarm-widgets.md`. Mockups: `iOS D6 - Lasskarm och widgets.dc.html`
(Live Activity ×3 + widget small/medium + låsskärm ×1).*

## 1 · Live Activity — match

**Kompakt (Dynamic Island):** vänster röd LIVE-puls + "KIK 2–1 BRG" (lagkoder, 3 tecken),
höger matchklocka i accent (`#F0B45A`, tabular nums — bredden får aldrig hoppa).
Ställningen är alltid synlig — det är den kompakta ytans enda jobb.

**Expanderad (håll på Island):** moment-rad ("LIVE · 2:A HALVLEK") + klocka · lag +
ställning stort i mitten · **nästa åtgärd-rad**: senaste händelsen som väntar på
foto-action ("Mål KIK 68' — plocka målbilden") med Öppna-knapp som deep-linkar rakt in
i LIVE-vyn/Snabbplock. Ingen händelse som väntar → raden visar nästa hållpunkt
("Halvtid om ~6 min") utan knapp.

**Låsskärmskortet har två lägen:**
- **Före avspark (MATCHDAG):** matchen + avsparkstid, **"Åk senast 17:40 · 24 min
  restid"** i accent + väder vid arenan — och en tidsprogress Nu → Åk → Avspark.
  Detta är B-011-spikens hem: restiden ÄR kortets poäng före match.
- **Från avspark:** samma innehåll som expanderade Island-layouten (lag, ställning,
  klocka, nästa åtgärd).

**Icke-match-jobb** (bröllop/porträtt/landskap): samma före-läge (jobb + starttid + åk
senast + väder). Under jobbet: nästa hållpunkt från jobbets tidplan ("Vigsel 14:00 ·
Sofiero") i stället för ställning/klocka. Ingen åtgärdsrad.

**Triggerregler:**
- **Start:** automatiskt på jobbdagen när `nu ≥ åk-senast − 60 min` (restid + väder är
  då relevanta). LIVE-läge startat i appen startar alltid aktiviteten direkt oavsett tid.
- **Lägesbyte:** före → under vid avspark/jobbstart.
- **Slut:** match — 30 min efter slutsignal (hinner visa slutresultatet); övriga jobb —
  vid jobbets sluttid + 30 min. Manuellt svep bort respekteras alltid (ingen re-spawn
  samma jobb).

## 2 · Widgets

- **Small:** NÄSTA-etikett + dag/tid stort i accent + jobbtitel + väder/plats-rad.
  Ett jobb, punkt slut — ytan tål inte mer.
- **Medium:** nästa jobb (samma block) vänster + avdelare + **de tre därpå** höger
  (titel + kompakt tid) = På gång-listan. Deadlines får plats som rader ("Leverans KDFF ·
  tis deadline") — samma källa som Fotojobb-listan (45-dagarsfönstret).
- **Låsskärm rektangulär (EN variant i v1):** "📷 Ons 19:00 · Kvarnsveden – Brage · ⛅ 17°"
  — nästa jobb med tid är den enda raden som är värd låsskärmsplatsen.
  Cirkulär + inline utgår i v1 (ytorna är för små för att slå en blick i appen).
- Tap-mål: small/rektangulär → jobbet; medium vänster → jobbet, höger rader → Fotojobb.
- Uppdatering: timeline per dygn räcker (nästa-jobb ändras sällan); väder refreshas
  var 3:e timme via samma MET/Yr-cache som appen.

## Formspråk
Svart/nästan-svart bakgrund (Island är alltid svart; widgets `#0B0E13`), Saira,
dalahäst-orange kvadraten (`#C96A28`) som avsändarmärke, accent `#F0B45A` för tid/
ställning, väder alltid som symbol + grader i dämpad vit. Kategorifärgerna (Hav/Sol/
Rosé) används INTE här — på systemytor är appens avsändaridentitet viktigare än
kategorin, och färgbruset ska vara minimalt.
