# Design-handoff D5 — Lightbox i sajtens gallerier

*2026-07-16 · Till: Claude Design · Från: Code · P2 (B-007). Litet jobb —
en spec-sida räcker.*

## Uppdraget

Klick på en galleribild (Sport, Landskap, Människor, Film) öppnar större vy
med navigering mellan bilderna.

## Krav (från Stigs backlog)

- Pilnavigering: tangentbordspilar på desktop, svep på mobil
- Stäng: Esc + klick utanför
- Ev. bildtext (galleribilderna har ibland `cap`)

## Frågor att landa

1. Overlay-utseendet: scrim-opacitet, bildens maxyta, pilarnas/krysset form
   (diskret i Skagen-språket — sajten går mot mörkt tema per D4)
2. Bildtextens placering (under bilden? overlay i nederkant?)
3. Räknare ("3 / 14")? Zoom (dubbeltap/pinch på mobil) — v1 eller senare?
4. Preload-känsla: nästa bild direkt (Code löser tekniken — definiera bara
   önskad upplevelse, t.ex. ingen spinner)

## Leverabel

En spec-sida (skiss + måtten ovan). Hänger ihop med D4 (mörkt tema) — samma
formspråk. Referens: `BACKLOG.md` (B-007 → D5).
