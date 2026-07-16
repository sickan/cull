# Design-handoff D7 — Startsidans kuratering (Featured + visningslogik)

*2026-07-16 · Till: Claude Design · Från: Code*
*Produktfråga mer än pixelfråga: VAD visas VAR och NÄR — och hur styr Stig det
utan att kurera varje dag. Slår ihop FEAT-02 (Featured) + SPIKE-02 (Idag vs
Framtiden).*

## Dagens faktiska logik (ur koden)

- **Sport-sidans hero:** redan kurerbar — Innehålls-panelen i DPT2 har
  "Topp: Senaste matchen / Kommande / Välj själv…" (`topp`-flagga på
  matchen). Fallback: senast avslutade matchen.
- **Tidigare matcher / Ligor & Tävlingar:** ren datumsortering, nyast först.
- **Startsidan** (`public/index.html`): statiska motivkort, ingen dynamik.
- **På gång:** kurerad lista (Stig väljer i DPT2), redan byggd.

## Stigs önskan (FEAT-02)

Kunna markera en Liga & Tävling ELLER en match som **"Featured"** → kortet
prioriteras på hemsidans startsida före standardlogiken (senaste datum).

## Frågor att landa (kärnan)

1. **Var syns Featured?** Startsidan är idag fyra motivkort utan innehålls-
   kort. Ska Featured (a) lyfta in ett innehållskort PÅ startsidan (ny
   sektion), (b) styra vad Sport-motivkortet visar/länkar till, eller
   (c) bara styra ordningen inne på Sport-sidan? Skissa förslaget.
2. **Idag vs Framtiden (SPIKE-02):** vad är standardlogiken när inget är
   Featured? T.ex: pågående event vinner över senaste resultat; kommande
   helgs matcher lyfts fram torsdag–söndag; annars senaste. Definiera
   regelverket i prosa — Code kodar det.
3. **Hur många Featured samtidigt?** En (enkel, tydlig) eller flera med
   ordning? Vad händer när ett Featured-event passerat — auto-släpp?
4. **DPT2-kontrollen:** var sitter markeringen? (Förslag: samma mönster som
   befintliga "Topp"-väljaren i Innehåll — en stjärna/flagga på kortet i
   Matcher resp. Lag & tävlingar.)

## Leverabel tillbaka till Code

1. Beslut/skiss på fråga 1 (var Featured syns)
2. Regelverket för standardlogiken (fråga 2) som punktlista
3. Featured-reglerna (antal, auto-släpp)
4. Mini-mockup av DPT2-kontrollen (eller peka på befintligt mönster)

## Referenser
- `dalecarlia-photo/src/pages/sport.astro` (topp-logiken, rad ~17)
- DPT2 Innehåll-panelen ("Topp: Senaste/Kommande/Välj själv")
- Total backlog: `dpt/design/BACKLOG.md` (FEAT-02, SPIKE-02 → D7)
