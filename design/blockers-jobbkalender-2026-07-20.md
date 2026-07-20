# Referensunderlag — uttolkade blockers ur jobbkalendern (juli–aug 2026)

*Källa: Stigs handoff 20/7 (F20-9). Uttolkat ur skärmbild av jobbkalendern
(Outlook månadsvy). Detta är **facit/testdata** för OCR-tolkningen i F20-9 —
regler enligt backloggens F20-9. Default 60 min. Jobbkalendern har FÖRETRÄDE
över fotouppdrag.*

## Blocker-regler (sammanfattning)
- **Inställt** ("Inställt: …") → räknas som ledigt, **exkluderas**.
- **Namnlösa** poster (endast klockslag) → generiska **"upptaget"**-block.
- **Heldags/tidlösa** (Semester, Ledig, GBG) → **bakgrund**, ej klockslagsblock.
- **Default möteslängd 60 min** (ev. heuristik per typ senare: fika 30 · CAB 60 ·
  1:1 30 · avstämning 30 · genomgång 60 · synk 30). Exakt sluttid krävs inte.

## Blockers juli 2026

| Datum | Dag | Tid | Titel |
|---|---|---|---|
| 15/7 | ons | 10:00 | R50-Klaffbron-V7-P4 |
| 15/7 | ons | 13:00 | R50-Klaffbron-V7-P4 |
| 16/7 | tor | 15:00 | Frivillig fika |
| 17/7 | fre | 11:00 | Planera testning (Anna Säkerhet) |
| 17/7 | fre | 12:00 | (namnlös) |
| 20/7 | mån | 13:30 | (namnlös) |
| 20/7 | mån | 15:00 | (namnlös) |
| 21/7 | tis | 10:00 | Mira - genomgång (R50-Vågbrytaren-V13-P15) |
| 21/7 | tis | 13:00 | Genomgång konsultkostnader (R50-Projektet-V10-P10) |
| 22/7 | ons | 09:30 | (namnlös) |
| 22/7 | ons | 13:00 | (namnlös) |
| 23/7 | tor | 10:00 | (namnlös) |
| 24/7 | fre | 08:00 | (namnlös) |
| 27/7 | mån | 10:00 | LF Cloud migrering (R50-Bojen-V7-P6) |
| 30/7 | tor | 15:00 | Frivillig fika |
| 31/7 | fre | 10:00 | Catch-up LF & Mendix (Siemens) |
| 31/7 | fre | 10:00 | Mira "Roadmap" synk |

**Exkluderat (inställt):** 30/7 14:00 Architectural landscape progress.

## Blockers augusti 2026

| Datum | Dag | Tid | Titel |
|---|---|---|---|
| 6/8 | tor | 13:45 | 1:1 möte + genomgång rapport föregående månad (R50-Projektet-V10) |
| 6/8 | tor | 15:00 | Frivillig fika |
| 7/8 | fre | 08:15 | Avstämning utvecklingen varannan vecka |
| 12/8 | ons | 13:00 | Change Advisory Board (CAB) |
| 13/8 | tor | 10:00 | Avdelningsmöte Digitalisering och Teknik |
| 13/8 | tor | 15:00 | Frivillig fika |
| 14/8 | fre | 10:00 | Mira "Roadmap" synk |
| 17/8 | mån | 10:00 | Change Advisory Board (CAB) |
| 18/8 | tis | 13:00 | Next sprint update (R50-Projektet-V10-P10) |
| 19/8 | ons | 13:00 | Change Advisory Board (CAB) |
| 21/8 | fre | 08:15 | Avstämning utvecklingen varannan vecka |
| 24/8 | mån | 10:00 | Change Advisory Board (CAB) |
| 24/8 | mån | 13:00 | Genomgång ODL med LF Skåne (R50-Skutan-V7-P6) |
| 26/8 | ons | 11:00 | Styrgruppsmöte Migrering Fabric (R50-Bojen-V7-P6) |
| 26/8 | ons | 13:00 | Change Advisory Board (CAB) |
| 26/8 | ons | 13:30 | Fortsättning Mira GBG - Skåne |
| 27/8 | tor | 10:00 | Leverans och kvalitetsinformation - Operativ rapportering |
| 27/8 | tor | 13:00 | Work shop intern kontroll (R50-Sockenv...) |
| 28/8 | fre | 10:00 | Catch-up LF & Mendix (Siemens) |
| 28/8 | fre | 10:00 | Mira "Roadmap" synk |
| 31/8 | mån | 10:00 | Change Advisory Board (CAB) |

**Exkluderat (inställt):** 4/8 13:00 Next sprint update · 6/8 14:00 Architectural
landscape · 13/8 14:00 Architectural landscape · 20/8 14:00 Architectural landscape.

## Bakgrund (heldags/tidlöst, ej klockslagsblock)

- 22 jun–15 jul: Semester (v27–v29)
- 3/8 mån: 08:00 Ledig (heldag)
- 25/8 tis: GBG (heldag, ingen tid)

## Noteringar om tolkningen (osäkerheter att verifiera)
- 24/7 08:00 låg under "den 24" som är fredag i julivyn.
- Sept-poster i augustivyns nedersta rad utelämnade (ofullständig månad).
- Månadsvyn saknar sluttider → default 60 min; bekräftelse-/redigeringssteg
  behövs (OCR-osäkerhet).
