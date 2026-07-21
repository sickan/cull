# Design-handoff D25 — Var bor tävlingen i den mergade Jobb-listan?

*2026-07-21 · Från: Code · Till: Claude Design*
*Uppföljning på D14/D15 §B. Brief/fråga — bygget ligger efter SM. Svar väntas som `HANDOFF-D25-SVAR-*.md`.*

## Var vi står
D15 §B besvarade match-halvan av D14: matchen är en **facett av ett jobb**, Matcher-
fliken tas bort, matcher når man via **Jobb**-segmenten (Kommande / Denna vecka / Alla),
och mästerskap/cuper/enstaka matcher listas som **jobbkort med kategorikant**.

Fas 1 av det byggdes + installerades på telefonen 21/7 (view-lager: fristående matcher
som jobbkort i Fotojobb-listan, tidssegment, tap → MatchHub). **Det avslöjade två saker
som D15 inte stängde**, och Stig skärpte modellen. Detta är inte en om-fråga — det är den
enda kvarvarande designfrågan + två konkreta fynd.

## Stigs skärpta modell (21/7)
> "En match kan inte finnas utan att det är ett Jobb. Däremot kan det finnas jobb som
> inte är matcher. Det kan finnas t.ex. tävlingar som har många matcher, grenar och
> utövare."

Alltså, bekräftat och skärpt:
- **Jobb = behållaren.** Kan vara en enskild match, en **tävling** (många matcher/grenar/
  utövare), eller ett icke-match-jobb (bröllop/landskap/porträtt).
- **Match ⊂ Jobb alltid** — aldrig lösryckt (matchar D15:s "facett av ett jobb").
- **Tävling ⊃ många jobb/dagar** (1:många) — ligger *ovanför* jobbet, inte en facett av det.

## Fynd 1 — dubbla poster (kärnfrågan)
På telefonen syns **Friidrotts-SM 2026 två gånger** i Jobb-listan:
- som **heldags-fotojobb**: "Heldag · 24–26 jul · Uppsala friidrottsarena"
- som **fristående match**: "24 juli 08:00 · Uppsala friidrottsarena · FRISTÅENDE"

Orsak: view-mergen slår ihop två separata källor (`JobbService` + `MatchService`) och
dedupen är bara 1:1 (`jobb.matchId`). En **tävling med både ett heldags-jobb och många
egna matcher/grenar** fångas inte av den kopplingen → samma verkliga event dubbleras.

**Designfrågan D14-tillägg §D Q2 lämnade öppen:** *var bor tävlingen* i den mergade
Jobb-listan?
- **Blir listraden tävlingen** (en behållar-rad "Friidrotts-SM", matcherna/grenarna
  inuti via Programmet från D15 §B/Q1) — och det underliggande per-dag-fotojobbet syns
  *inte* som egen rad?
- **Eller blir raden per-dag-fotojobbet** (24–26 jul som en heldagsrad) med matcherna
  under den dagen — och tävlingen är ett lager man zoomar till?
- Hur garanteras **exakt en rad per event** oavsett hur många matcher/dagar/grenar det
  har? (Det är detta som brister nu.)

Kardinaliteten (D14-tillägg §B) måste hållas: **1:1-matchen viker in i sitt jobb; men
tävlingen (1:många) kan inte bara bli "ett stort fotojobb".**

## Fynd 2 — sortering & scroll (hittbarhet, DPT-paritet)
I **Kommande** sorteras fallande, så längst-bort-i-framtiden (handboll/volley 2027-
säsongen) hamnar överst och den **närmaste** (SM i juli) begravs längst ner. I DPT2
sorterar vi fallande men **auto-scrollar till närmast kommande** så man landar på
"vad är näst". Bekräfta modellen för den mergade listan:
- **(i)** fallande + auto-scroll-till-närmast (DPT-paritet), eller
- **(ii)** i *Kommande* stigande (närmast först) — förflutet är ändå bortfiltrerat.

## Invarianter (oförändrade från D14/D15)
- Match/tävling finns **bara** för Sport; den mergade Jobb-ryggen spänner över ALLA
  kategorier — aldrig match-/tävlings-grepp eller sport-ord på bröllop/landskap/porträtt.
- "Del av {tävling}" — aldrig lösryckt. Grenkant utan textetikett. Heldag = bara dagen.
- Fältflödet oförändrat; Programmet (D15 Q1) matar in i det.

## Timing / beroende
- **Bygget efter SM** — matchflödet får inte destabiliseras under säsong (merge skiva 4).
- Fas 1 (view-lagret) är installerat men **parkerat** tills detta är avgjort; Matcher-
  fliken är kvar som jämförelseyta t.v. Fas 2 (ta bort fliken) + fas 3 (Programmet i
  JobbDetalj) väntar på svaret.
- `fotojobb.tavling_id` (M-11) finns → tävling↔jobb är en pålitlig relation att luta på
  för dedupen, inte namn-gissning.
