# Design-handoff D1 — Horisont-mall för TENNIS

*2026-07-15 · Till: Claude Design · Från: Code-sessionen (DPT2)*
*Deadline: **Nordea Open i helgen** (Båstad). Kort och fokuserad — hellre en
landad mall än fem utkast.*

## Uppdraget i en mening

Ta fram tennis-varianten av Horisont story-overlayen: **spelarnamn som primär
rad i stället för lag+loggor, rond/omgång i stället för "Avspark", och
set-resultat i stället för målsiffror** — inom Horisonts befintliga formspråk.

## Så funkar Horisont idag (fakta ur renderaren — kanonisk)

Pillow-renderaren (`dpt2/motorer/story_overlay.py`, 1159 rader) ritar en
overlay på ett foto. Detta ligger fast och ska INTE göras om:

- **Format:** 9:16 (1080×1920) och 4:5 (1080×1350). Overlay kan slås av.
- **Tre teman:** Hav `#8FD0E8` · Sol `#F4C77A` · Rosé `#EBB3C4` (accent +
  brandfärg per tema, temalogga uppe till vänster).
- **Typografi:** Saira (samma familj som appen/sajten).
- **Gren-markör:** färgad kant längst till vänster (18 px), dam/herr/mixed —
  samma färgkodning som matchkorten i appen.
- **Sex tillstånd** i fyra layoutblock:

| Tillstånd (fotboll) | Block | Innehåll idag |
|---|---|---|
| Avspark | PREVIEW | Stort ord "AVSPARK", lag + loggor, tid, arena, liga-logga |
| Nästa match | PREVIEW | "NÄSTA MATCH", lag + loggor, "Lör 14 jun · 16:00" |
| Halvtid | SCORE | Stor sifferställning, etikett, lag + loggor |
| Slutresultat | SCORE | Ställning + målskyttelista (rad/chips/spalter) |
| Startelva | LINEUP | Spelarlista i kolumner |
| Målgörare | MÅLGÖRARE | "MÅLGÖRARE" + namn + minut + ställning |

- Renderaren är redan **delvis sport-medveten**: etiketterna för
  Halvtid/Slutresultat hämtas ur sportprofilen — men **blockens layout är
  fotbollstänkt** (två lag, loggor, målskyttar). Det är layouten D1 ska lösa.

## Tennis-datat som finns (sportprofilen + matchmodellen)

Ur `data/sportprofil.py` — tennis:

- `individ: True` — matchen står mellan **två spelare**, inte två lag.
  Spelare har **ingen logga** (profilfärg finns; klubb/land som text, t.ex.
  "Sverige").
- Resultat: **"Resultat i set"**, t.ex. `2–1`.
- Mellanresultat: **"Gamesiffror"**, t.ex. `6–4, 3–6, 7–5`.
- Startmoment heter **"Matchstart"** (inte Avspark).
- Inga målskyttar, ingen startelva/lineup.
- Turneringen (t.ex. "Nordea Open ATP250") ligger i matchens liga/tävling-fält
  och kan ha egen logga.

**Finns INTE i datat idag:** rond/omgång (Åttondel/Kvartsfinal/Semifinal/
Final). Om mallen behöver den (troligen ja) — föreslå var den ska stå, så
lägger Code till fältet.

## Designfrågor att landa (kärnan i jobbet)

1. **PREVIEW-blocket (Matchstart / Nästa match):** vad ersätter det stora
   "AVSPARK"? Förslag att pröva: rond som stort ord ("KVARTSFINAL") eller
   "MATCHSTART" + rond som underrad. Och: **hur visas två spelare utan
   loggor?** (Enbart namn i stor stil? Namn + land? Monogram-badge finns som
   fallback i renderaren.)
2. **SCORE-blocket (Mellan set / Slutresultat):** set-siffran stor (`2–1`) med
   gamesiffrorna (`6–4, 3–6, 7–5`) som underrad? Eller gamesiffrorna som
   primär? Vinnarens namn — markeras hur?
3. **MÅLGÖRARE-motsvarighet:** utgår helt för tennis, eller finns ett
   "ögonblicks"-tillstånd värt att ha (t.ex. "SETVINST — Peterson 6–4")?
   Utgår är helt OK — säg det i så fall explicit.
4. **STARTELVA:** utgår för individ-sporter (bekräfta).
5. **Rond/turnering-hierarkin:** turneringsnamn ("Nordea Open ATP250") vs rond
   ("Semifinal") — vilken är visuellt primär, var sitter respektive?

## Tänk ett steg fram (men designa inte det nu)

Direkt efter D1 kommer **D2: friidrott** (SM 24–26/7) — idrottarnamn primärt,
"Längd — kval", resultat som längd/tid/höjd. Välj mallspråk för D1 som tål
att en idrott har **en person och ett resultat** i stället för två sidor —
Code bygger en gemensam profildriven motor för båda.

## Leverabel tillbaka till Code

1. Mockups för tennis-tillstånden (de som ska finnas) i **ett tema** (Hav) ×
   9:16 — övriga teman är färgbyten, 4:5 är beskärning.
2. En **fältlista per tillstånd**: vilka datafält som visas, var, och vad som
   händer när ett saknas (t.ex. ingen rond angiven).
3. Beslut på fråga 1–5 ovan (kort text räcker där mockup inte behövs).

## Referenser

- Befintlig Horisont-design: `design/` (Saira, 6 tillstånd/3 teman-arbetet).
- Sportprofilen: `src/dpt2/data/sportprofil.py` (tennis + friidrott).
- Renderaren: `src/dpt2/motorer/story_overlay.py`.
- Plan: `design/PLAN-nordea-friidrott.md` (D1 är översta design-jobbet).
