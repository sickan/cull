# Handoff-paket: UI-synk Match-flödet + Innehåll & webb (DPT2 → Claude Design)

**Datum:** 7 juli 2026 · **Riktning:** Code → Design (statusrapport, inte designbeställning)
**Syfte:** synka Claude Design-prototypens bild med vad som faktiskt är byggt i DPT2, inför att vi
jobbar igenom **Match-flödet** och **Innehåll & webb** igen.

## Innehåll i paketet

| Fil / mapp | Vad |
|---|---|
| `HANDOFF.md` | Huvuddokumentet. Del A = Match-flödet (A1–A6), Del B = Innehåll & webb (B1–B7), plus flaggor mot baslinjen och öppna designytor. |
| `kallkod/` | Färsk snapshot (7 juli) av de faktiska Svelte-filerna — grundsanning om HANDOFF.md är otydlig. |

### `kallkod/` — filer
**Match-flödet:** `Matcher.svelte`, `AktivMatchRad.svelte`, `Lag.svelte`, `Lagbricka.svelte`,
`ResultatRemsa.svelte`, `gren.js`
**Innehåll & webb:** `Innehall.svelte`, `PaGang.svelte`, `Publicera.svelte`,
`BildvaljareFokuspunkt.svelte`, `testlage.js`
**Delat:** `Combobox.svelte`, `tokens.css` (Skagen Hav-designtokens, ljus + mörk)

## Baslinje (vad Design redan har)
`../UI-SYNK-2026-07.md` (punkt 1–8) + tidigare Design→Code-handoffar
(`design_handoff_flode_sportprofiler`, `design_handoff_radklick_grenkant` m.fl.). Det här paketet
om-speccar inte det — det beskriver deltat sedan dess.

## Så använder du det i Claude Design
1. Läs `HANDOFF.md` uppifrån — den är skriven att läsas fristående.
2. Öppna motsvarande fil i `kallkod/` när du vill se den exakta implementationen (etiketttexter,
   fältordning, tillstånd).
3. De fem flaggorna längst ner i `HANDOFF.md` är de aktiva designval som väntar på beslut.

## Ej med (medvetet)
- Inga skärmbilder (appen körs lokalt via pywebview — lägg gärna färska dumpar i en `skarmdumpar/`
  om vi vill referera dem per avsnitt, som i tidigare handoffar).
- Ingen `.dc.html`-prototyp — det är Design-sidans format; det här går andra vägen (kod → design).
