# Handoff-paket: UI-synk efter implementation (DPT2 → Claude Design)

**Datum:** 7 juli 2026 · **Riktning:** Code → Design (statusrapport)
**Svar på:** `design_handoff_matchhuvud_webb` (din Design→Code-handoff)
**Syfte:** synka din prototyps bild med det vi faktiskt byggde — särskilt de ytor som utvecklades
under skarp testning och nu avviker från prototypen.

## Innehåll
| Fil / mapp | Vad |
|---|---|
| `HANDOFF.md` | Huvuddokumentet. §1–7 speglar din handoffs sektioner (KLAR / ⚠ AVVIKELSE), + sammanfattning av vad som behöver uppdateras. |
| `kallkod/` | Färsk snapshot av de faktiska filerna (7 juli). |

### `kallkod/`
`MatchHuvud.svelte` (ny), `ResultatRemsa.svelte`, `Publicera.svelte` (all SoMe-logik),
`Innehall.svelte`, `PaGang.svelte`, `gren.js`, `tokens.css`.

## Viktigast
- **§5 SoMe overlay-omslag** blev annorlunda än din spec: overlayen läggs **ovanpå den bild man
  valt som omslag** (inte fristående moment-kort), och omslagsbilden lämnar karusellen. Detta är
  huvudsaken att ta in i prototypen.
- **§2 Innehåll → Sport:** Aktiv match-remsan står kvar ovanför den ljusa tavlan — ditt beslut om
  match-huvudet ska in där också.

## Status
Allt är byggt, verifierat, mergat till main (`dpt` PR #9) och heldag-webbkedjan live på
dalecarlia-photo. Detta paket är bara synk tillbaka till dig — ingen kodåtgärd väntar.
