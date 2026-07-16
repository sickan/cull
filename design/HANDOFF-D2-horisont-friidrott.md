# Design-handoff D2 — Horisont-mallar för FRIIDROTT

*2026-07-16 · Till: Claude Design · Från: Code (DPT2)*
*Deadline: **Friidrotts-SM 24–26/7** (Uppsala) — mallarna behöver landa i god
tid före 24/7 så Code hinner koppla in dem.*

## Uppdraget i en mening

Ta fram friidrotts-varianterna av Horisont story-overlayen: **en idrottare +
en gren/ett moment + ett resultat** — på samma mallspråk som tennis-mallen
(D1) som redan är implementerad och skarp.

## Bygg vidare på D1 (viktigt)

D1-svaret är implementerat i renderaren exakt som specat — samma motor kör
friidrott. Ert eget "Blick mot D2" i D1-svaret är startpunkten:

> Mallspråket tål en person + ett resultat: PREVIEW = stort ord (moment/gren,
> t.ex. "LÄNGD — KVAL") + en namnkolumn i stället för två; SCORE = stor siffra
> (längd/tid/höjd) + namnrad under. Inga block bygger på "två sidor" —
> dash-raden är det enda tvåparts-elementet och kan utgå.

Låst från D1 (ändra inte): full-bleed foto, scrims, temalogga, spärrad
tävlingstext uppe höger, 18 px gren-kant (Dam `#8E5A86` · Herr `#3E7C87` ·
Mixed `#6E8757`), Saira-typografin, vinnar-accent = temats accentfärg.

## Friidrotts-datat (sportprofil + kommande deltagarmodell)

- Profil (`data/sportprofil.py`): `individ: True`, res_label "Resultat"
  (ph "10,12 s"), mid_label "Placering" (ph "1"), start_moment "Start".
- **Deltagarmodellen byggs parallellt (B-001):** Event → Deltagare → Grenar
  (en deltagare kan ha flera grenar, t.ex. Längd + Tresteg). Overlayn kommer
  kunna få: idrottarens namn, klubb, gren, moment (kval/final), resultat,
  placering.
- SM är EN tävling (eventet) — "Friidrotts-SM 2026" står uppe till höger
  (som turneringen i tennis). Grenen + momentet är det som varierar per story.

## Designfrågor att landa

1. **Gren + moment som stort ord:** "LÄNGD — KVAL", "TRESTEG — FINAL",
   "100 M — SEMIFINAL". Hur bryts långa kombinationer (t.ex. "STAVHOPP —
   KVALGRUPP A")? En rad med auto-krymp eller två rader?
2. **Resultat-tillståndet per grentyp** — definiera **grentyp →
   resultatformat-tabellen** (kärnleverabeln!):
   - Sprint/löpning: tid ("10,12" / "1.45,32") — sekunder vs min.sek-format?
   - Hopp/kast: längd/höjd ("6,42" / "2,05") — med enhet ("m")? antal decimaler?
   - Placering: siffra, medaljfärg vid 1–3? ("GULD"/🥇/accentfärg — välj)
3. **Serie-resultat:** ett hopp är en serie ("6,21 · 6,42 × 6,38 — bästa
   6,42"). Visas serien (som gamesiffrorna i tennis, under avdelaren) eller
   bara bästa? Vad betyder × (övertramp) visuellt?
4. **PREVIEW ("Start"):** en idrottare (namn + klubb som underrad, som
   land i tennis) — eller flera samtidigt (Stig bevakar ofta 2–3 deltagare i
   samma gren)? Om flera: hur ser namnlistan ut?
5. **Placering utan mätbart resultat** (t.ex. DNF/DNS/DQ) — visas hur, eller
   utgår storyn då?

## Leverabel tillbaka till Code

1. Mockups (Hav × 9:16) för: Start/preview, Resultat (tid-gren), Resultat
   (längd/höjd-gren med serie), Placering/medalj — de tillstånd ni landar i.
2. **Grentyp → resultatformat-tabellen** (fråga 2) som text — den blir
   konfig i sportprofilen.
3. Fältlista per tillstånd + fallbacks (samma form som D1-svaret — den var
   utmärkt att implementera från).

## Referenser

- D1-svaret + facit: `design/HANDOFF-D1-SVAR-horisont-tennis.md` (mallspråket)
- Sportprofilen: `src/dpt2/data/sportprofil.py` (friidrott längst ner)
- Renderaren: `src/dpt2/motorer/story_overlay.py` (individ-blocken från D1)
- Plan: `design/PLAN-nordea-friidrott.md`
