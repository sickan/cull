# Design-svar D5 — Lightbox i sajtens gallerier

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D5-lightbox.md` (B-007). Spec-sida: `Webb D5 - Lightbox.dc.html`
(desktop + mobil i skala + måttavla). Mörkt tema per D4.*

## Beslut på fråga 1–4

**1. Overlay:** scrim `rgba(5,7,10,.96)` (D4:s bakgrundston, nästan tät). Bild max
**82vw × 78vh** på desktop (lämnar luft åt pilar + textrad), **100vw × 76vh** mobil.
Mjuk skugga (`0 30px 80px rgba(0,0,0,.6)`). Pilar och kryss är **rena tecken** ‹ › ✕
i 55 %-vit — ingen cirkel, ingen platta; hover → 100 % vit. Träffyta 44–48px.
Mobil har inga pilar (svep) och bara krysset som krom.

**2. Bildtext: under bilden, aldrig på den** (fotot ska vara orört). Rad i bildens
bredd: kursiv 14px 60 %-vit vänster + räknare höger. Saknas `cap` → räknaren står ensam.

**3. Räknare: ja** — spärrad "3 / 14" (Saira Condensed 600, `.22em`, 40 %-vit) i
textradens högerkant. **Zoom: v2** — kräver gesture-hantering som krockar med svep-nav;
inget Stig bett om. **Loop: ja** (14 → 1 utan stopp).

**4. Upplevelsen (Code löser tekniken):**
- Öppna: scrim fade 180ms + bilden skala .97→1. Stäng: omvänt, snabbare (120ms).
- Bildbyte: **crossfade 160ms** — inget slide (lugnare, och riktningen känns via svepet
  på mobil ändå).
- **±1 bild förladdas** direkt vid öppning och efter varje byte — **aldrig spinner**.
  Händer onådd bild ändå: visa galleri-preview:n (finns redan lågupplöst) och låt den
  skärpas — upplevd väntan noll.
- Stäng: ✕, Esc, klick utanför bilden, svep ned på mobil. Tangentbord: ←/→ nav,
  Esc stäng. Body-scroll låses medan öppen.

## Scope
Gäller alla sajtens gallerier (Sport, Landskap, Människor, Film, event-sidor).
En komponent, `cap`-fältet från galleridatat återanvänds rakt av.
