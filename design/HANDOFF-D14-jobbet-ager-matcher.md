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

---

## Tillägg 20/7 — panel-sammanslagningen (Lag+Utövare, Fotojobb/Match/Tävling)

*Från: Code. Stig ställde en bredare fråga om att slå ihop paneler för bättre
UX ("Vi har diskuterat att slå ihop Lag och Utövare … och Fotojobb och Matcher,
men kanske Tävlingar ska in där. Allt är fotojobb, men allt är inte matcher").
D14 ovan är match-halvan av det — här är helheten så du kan svara på allt i ETT
sammanhang i stället för styckvis. Fortfarande brief, inget designat.*

### A · Lag + Utövare: redan ETT register i botten
`Utövare = lag(kind='individ')` sedan v40 (D11b §2) — `upsert_individ` slår in i
`upsert_lag(kind="individ")`, `lista_individer` är bara `SELECT … FROM lag WHERE
kind='individ'`. **Sammanslagningen är ren UI-konvergens: ingen schemaändring,
ingen migrering, noll datarisk.** Frågan är alltså inte "slå ihop två register"
(de ÄR ett) utan **hur en enda lista segmenteras** mellan lag och individ
(kind-chip / filter / underflik). Designa den UX:en, inte en datamodell-merge.

### B · Fotojobb / Match / Tävling har OLIKA kardinalitet — platta inte till dem lika
Detta är kärnan och måste hållas isär:
- **Match : Fotojobb ≈ 1:1** — matchen är en *facett* av ett jobb (en dag). Den
  kan vika IN i jobbet. Det är precis D14-riktningen "jobbet äger matchen".
- **Tävling : Fotojobb = 1:många** — en tävling *spänner över* flera jobb/dagar
  (Friidrotts-SM: 79 grenar × 3 dagar; EuroVolley: en veckas matcher). En tävling
  är en **behållare OVANFÖR jobben**, inte en facett av ett.

Så Stigs mening stämmer, skärpt: *"allt är fotojobb, men allt är inte matcher —
och en tävling är inte ett fotojobb, den binder ihop flera fotojobb."*
**Match viker in i jobbet; Tävling ligger ovanför det.** Blanda inte de två i
samma "fold-in" — en tävling ska inte bli "ett stort fotojobb".

### C · Rören finns redan (M-11)
`fotojobb.tavling_id` (byggt idag, schema v43) är den beständiga jobb↔tävling-
kopplingen. "Ett jobb tillhör en tävling" är alltså redan en pålitlig relation i
datan — luta dig på den, inte på namn-gissning. En tävling kan därmed lista
"sina" jobb genom att fråga baklänges på `tavling_id`.

### D · Uppgiften för Design (utöver D14:s två frågor)
Rita **navigations-ryggen** när panelerna konvergerar:
1. Är **Fotojobb** den enda topp-ytan (alla kategorier, kalenderdriven), där
   Sport-jobb *avslöjar* Match (facett) och *grupperas under* Tävling (behållare)?
2. Var bor **Tävling** då — som en vy/lager man kan zooma till från ett jobb, en
   egen ingång, eller båda? (Kom ihåg 1:många — den kan inte bara vara en flik
   inuti ett enskilt jobb.)
3. Blir **Lag/Utövare** ett stödregister man når *inifrån* (chips i editorn,
   deltagarval) snarare än en jämbördig topp-panel?

### Invarianter (utöver D14:s)
- **Kategorifacit** Sport · Landskap · Människor · Film — den hopslagna Fotojobb-
  ryggen spänner över ALLA. Match och Tävling finns **bara** för Sport. Den
  mergade vyn får aldrig visa match-/tävlings-grepp eller sport-ord på ett
  bröllops-/landskaps-/porträttjobb (samma SPORT-ORD-städning vi redan kört).
- **Lag ≠ Utövare i tonen** även om de delar tabell: ett lag har logga/ställ, en
  utövare har porträtt/klubb — segmenteringen måste kännas naturlig, inte som
  samma formulär två gånger.
- **Designa nu, bygg efter SM.** Match- och tävlingsflödena får inte
  destabiliseras under säsongen (samma tidslås som D14 / MERGE-spec skiva 4).
