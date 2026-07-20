# Design-handoff D14 — Jobbet äger sina matcher (iOS-navigation)

*2026-07-20 · Från: Code · Till: Claude Design*
*Brief/fråga — inget är designat än. Svar väntas som `HANDOFF-D14-SVAR-*.md`.*

## Bakgrund
Under en testsession 20/7 formulerade Stig en strukturell riktning för iOS-appen:

> "På samma sätt som gren ligger under tävlingen Friidrotts-SM och fotojobb,
> borde t.ex. ett mästerskap hantera matcherna — nu ser jag bara nästa. Men om
> vi tar bort Matcher-fliken behöver jag kunna fälla ut hela listan under jobbet."

Det är UI-uttrycket av **merge-riktningen** vi redan har på backloggen (sektion
MERGE i `BACKLOG.md`): *fotojobbet är basenheten, matchen en valfri facett av
det.* Ett jobb/mästerskap som pågår ska alltså **äga sina matcher/deltillfällen**
i gränssnittet — inte bara peka på "nästa".

## Nuläge i appen (vad Design ersätter)
- **Hem-hjälten** visar bara **nästa** deltillfälle/match under ett pågående
  heldagsevent (restid/nedräkning mot nästa).
- **JobbDetalj** har "Dagens deltillfällen" — men bara **dagens**, inte hela
  programmet över alla dagar.
- **En separat "Matcher"-flik** i nedre menyn (med fotbollsikon) listar alla
  matcher fristående från jobben. Den är **sport-centrerad** (samma "sporttänk"
  som SPORT-ORD-arbetet just rättat på andra ytor — Avspark→Start, arena→plats).

## Uppgiften för Design (två sammanhängande frågor)

**1 · Hur äger ett jobb/mästerskap sina matcher i JobbDetalj?**
Designa hur **hela match-/deltillfälle-listan** visas under jobbet — utfällbar,
grupperad per dag (inte bara "idag", inte bara "nästa"). För ett stort mästerskap
(Friidrotts-SM: 79 grenar, EuroVolley: en veckas matcher) måste det skala. Tänk
in: kollaps/expandera per dag, "nästa" fortfarande framhävt, snabbväg till
"Skapa SoMe" per match/pass (fältflödet finns redan).

**2 · Matcher-flikens vara eller icke-vara.**
Om jobbet äger matcherna — **ska den separata "Matcher"-fliken tas bort?**
- Om JA: hur når fotografen matcher som **inte** hör till ett aktivt jobb den
  dagen (framtida matcher, fristående enstaka matcher utan heldagsevent)? Via
  jobblistan? En vy inuti Jobb? ⌘K-sökningen (finns på desktop, ej mobil)?
- Om NEJ (behåll fliken): hur undviker vi dubbel navigation (samma match nås
  både under jobbet och i fliken) och den sport-centrerade tonen?

Stigs önskade valmängd när han beslutar (per krock/överlapp i ett annat spår)
är inte relevant här — det här gäller *navigationsstrukturen*, inte urval.

## Invarianter att bevara
- **"Del av {tävling}"** — en match/deltillfälle visas aldrig lösryckt.
- **Gren-paletten** (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`), kant utan
  textetikett.
- **Kategorifacit** Sport · Landskap · Människor · Film.
- **Fältflödet** (pass → vinnare → resultat → SoMe) är redan byggt och i D13:s ton
  — den nya strukturen ska mata in i det, inte ersätta det.
- Heldag = bara dagen (presentationsinvarianten från widget/hem).

## Kopplingar / beroenden
- **Merge-spec skiva 4** (`BACKLOG.md`, sektion MERGE): iOS konvergerar sina två
  modeller (`Match` + `Jobb`) till en — jobb med valfri match-facett. D14 är
  UI-sidan av det. Bygget sker EFTER SM (matchflödet får inte destabiliseras
  under säsongen).
- **M-11** (`fotojobb.tavling_id`, byggt): den beständiga jobb↔tävling-kopplingen
  som gör "jobbet äger sina matcher" pålitlig i stället för namn-gissad.
- **SPORT-ORD / de-sportifieringen**: Matcher-fliken är den sista tydligt
  sport-centrerade ytan.

## Bonus-check (litet, samma runda)
D13 införde **mässing `#F0B45A`** som appens enda accent, medan tidigare underlag
säger "brand orange". Bekräfta att det är **samma accent-roll, ny ton** — inte
två parallella accenter — innan den delade färg-resursen (W-8/S-3) gjuts.
