# Design-handoff D11 — Event, individer och fältflödet (NYTT design-jobb)

*2026-07-19 · Till: Claude Design · Från: Code*
*Stigs beställning: "ta ett helhetsgrepp på Event, individer, tävling, hur
individ är kopplat, hur man hittar och hanterar de olika. Hur man kan klicka
från ett ställe till ett annat utan att leta i menyer."*

*Brådskande kontext: **Friidrotts-SM 24–26 juli** är första skarpa provet.
Modellen bakom fungerar redan (108 deltillfällen, 845 starter går att läsa in)
— det som saknas är att det ska gå att ARBETA i.*

---

## Varför nu

Eventmodellen har vuxit fram i skivor under fem dagar (V5-B→E plus §8
program/pass). Varje skiva fungerar för sig. Tillsammans har de blivit en
struktur som Code kan navigera men Stig inte kan.

Tre buggar 19/7 var egentligen samma sak i olika förklädnader:

- Programmet läckte till ALLA jobb i iOS — för att **jobbet inte vet vilket
  event det hör till**. Kopplingen är i dag en namnjämförelse.
- `100m` och `100 m` blev två grenar — för att **samma sak kommer in genom
  två dörrar** utan att någon vy visar att de är dubbletter.
- Startlistan satte klass på grenen men inte på individen — för att
  **individen bor på två ställen** och ingen yta visar båda.

Det går att lappa var för sig. Men Stig har rätt: det behövs ett helhetsgrepp,
och designen måste komma före nästa lager kod.

---

## Dagens läge (fakta)

### Registren — och deras dubbelhet

| Register | Roll | Skrivs var |
|---|---|---|
| `tavling` | **Skrivytan**, alla typer | Tävlings-editorn (under Lag & ligor) + Event-sektionens egen editor |
| `liga` / `event` | **Speglingar** av tavling, samma id | Automatiskt (`spegla_tavling_v5`) |
| `disciplin` ("gren") | Grenar under ett event, bär nu klass dam/herr | Event-sektionen + import |
| `pass` | Grenens tidsatta deltillfällen | Import + för hand |
| `lag` med `kind='individ'` | Utövare (B-001, äldre) | Lag-editorn, trupp-import, startlisteimport |
| `individ` | Individregistret (V5-B, nyare) | Deltagare-kortet |

**Två problem syns direkt.** Tävling är skrivytan medan Event är läsytan — så
Stig redigerar ett event på ett ställe och kopplar det på ett annat. Och en
utövare kan bo i `lag`, i `individ`, eller i båda; Deltagare-kortet visar
unionen, men inget säger vilken post man faktiskt rör.

Det här är arv, inte design. **Det är fritt fram att föreslå att de slås ihop.**

### Var saker görs i dag

- **Planera › Event** — lista + detaljvy. Äger kopplingarna: På gång-läge,
  matcher, grenar, deltagare, program.
- **Planera › Lag & ligor** — tävlings-editorn (namn, typ, period, ort, arena)
  och lag-/utövarregistret.
- **Planera › Matcher** — matchformuläret har Liga- och Event-fält ("två dörrar").
- **Planera › Fotojobb** — jobben. **Har ingen koppling till event alls.**

### Program-kortet och importen

Kortet visar det härledda dagsprogrammet: dagflikar, tid, gren · pass, vilka
som deltar, handles att kopiera, NÄST-markering. Det fungerar.

Importen gör det inte. Den har i dag **fem vägar in** i ett kort:

1. "Klistra in / CSV" → läge **Tidsprogram** (fri text eller CSV)
2. samma knapp → läge **Startlista med tider** (arrangörens startlistesida)
3. samma knapp → läge **Bara deltagare**
4. knappen "Läs PDF…" inuti läge 1
5. "+ Pass" för hand

Stig: *"Importdelen är också förvirrande."* Han har rätt. Han ska inte behöva
veta vilken sorts dokument han har — parsern kan gissa och fråga.

Vad källorna faktiskt bär (uppmätt mot SM 2026):

| Källa | Program | Deltagare | Klass | Handles |
|---|---|---|---|---|
| Arrangörens PDF | ✅ 108 rader | ❌ | ✅ (kolumn) | ❌ |
| easyrecord.se startlista | ✅ 121 pass | ✅ 845 starter | ✅ (rubrik) | ❌ |

**Handles finns inte i någon källa.** De måste sättas för hand — i dag ett
fält per deltagarrad. Det är den enda vägen, och den behöver bli bra.

### Synken

Paketen pushas till molnet **automatiskt** vid två tillfällen: när DPT2 startar,
och när man publicerar i På gång. Det finns ingen manuell synk någon annanstans
i appen.

19/7 la Code till en knapp **"Skicka till telefonen"** i Program-kortet, för
att ett nyss inläst program annars låg kvar lokalt till nästa omstart. Stig:
*"skicka till telefonen känns inte i linje med all annan synk."* Han har rätt —
det är ett plåster på att synkmodellen är osynlig, inte en designad yta.

### iOS i dag

- **Hem** — nästa jobb/match/deltillfälle med nedräkning, restid, väder.
  Räknar nu på programmets pass (§8 S5).
- **Jobbdetalj** — när/var, DAGENS DELTILLFÄLLEN med vem + kopiera-handles.
- **Matchhubben** — trupp, målflöde, matchklocka, story-generering, LIVE-läge.
  **Allt är byggt för lagsport.**
- **Widget/låsskärm** — nästa jobb. Vet inget om deltillfällen.

### Kopplingar som saknas (navigationen Stig efterlyser)

| Från | Till | Finns? |
|---|---|---|
| Programrad | individen som tävlar | ❌ |
| Individ | hens event/grenar (historiken finns i data) | ❌ ingen vy |
| Individ | bilder/jobb där hen är med | ❌ |
| Fotojobb | eventet det hör till | ❌ **inte ens i datamodellen** |
| Event | fotojobbet | ❌ |
| Match | eventet | ✅ "Del av {event}" |
| Event | matchen | ✅ |
| Gren | deltagarna | ✅ (chips) |
| Deltagare | grenarna | ✅ (chips) |

Raden som gör mest ont är **Fotojobb ↔ Event**. Den saknas i datamodellen, och
det är därför iOS i dag kopplar ihop dem genom att jämföra jobbets titel med
eventets namn. Byter Stig namn på kalenderposten tappar programmet sin koppling
och försvinner tyst. Code kan lägga fältet — men VAR kopplingen görs, och om
den ska kunna vara automatisk, är en designfråga.

---

## Fältscenariot — det viktigaste i hela handoffen

Stig: *"Hur kan jag på fältet snabbt ange en vinnare, resultat och köra SoMe på
det med rätt person och dess IG handle."*

Så här ser verkligheten ut, med riktiga data ur SM:

> Fredag 24 juli, 20:25. **100 m dam, final.** 22 startande. Stig står vid
> mållinjen med telefonen i fickan och kameran i hand. Loppet tar 11 sekunder.
> Han vet vem som vann innan speakern hunnit säga det.
>
> Han vill: **markera vinnaren, skriva 11.48, och få ut en story med rätt
> namn, rätt klubb och rätt @-handle** — medan hon fortfarande står kvar och
> gratuleras. Inom en minut, med en hand, i solljus.

Det går inte i dag. Matchhubbens flöden förutsätter två lag, målskyttar och en
matchklocka. För ett grenpass finns startfältet i paketet, men ingen väg från
"det här passet" till "hon vann, tiden var 11.48, publicera".

**Det som redan finns att bygga på:**
- Passet vet vilka som deltar (härlett gren → deltagare) och deras handles
- D2:s resultatformat per grentyp (sprint `11.48` · hopp/kast `6.29` ·
  mångkamp `7976 p`) är specade och byggda i story-overlayn
- Story-generering, IG-delning och Live Activity fungerar skarpt för matcher
- `moment_status` (§10) har momentmallar per jobbtyp

**Det som saknas:** hela vägen från deltillfälle → resultat → SoMe för
individsport. Och: vad händer med resultatet? Ska det tillbaka till DPT2, till
webben, till eventsidan?

**Observera:** vid 20:25 har Stig 22 deltagare i det passet men bara ett fåtal
har handle. Designen måste tåla att handeln saknas — och helst göra det lätt
att lägga till den på plats, i samma andetag.

---

## Frågor att landa

### A · Modellen och orden

1. **Tävling vs Event vs Liga** — ska Stig se tre begrepp eller ett? Han säger
   "tävling" om allt. Om ett: vad heter det, och vad händer med
   redigera-på-ett-ställe-koppla-på-ett-annat?
2. **Individ på två ställen** — slå ihop `lag(kind=individ)` och `individ` till
   ett register? Vad heter det för Stig: "Utövare", "Personer", "Individer"?
3. **Ordet "gren"** betyder två saker: klassen (dam/herr) och disciplinen
   (100 m). I koden heter disciplinen `disciplin` just därför. **Vad ska de
   heta i gränssnittet?** Det här förvirrar redan.

### B · Att hitta och navigera

4. **En individsida.** Vad ska den visa — historik (härledd), kommande starter,
   handle, klubb, bilder? Och var nås den ifrån: programraden, deltagarlistan,
   sökningen, bildvyn?
5. **Global sökning?** I dag finns ingen. Ska det gå att skriva "Duplantis"
   var som helst och komma rätt?
6. **Fotojobb ↔ Event** — var knyts de ihop? När Stig skapar jobbet, när han
   skapar eventet, eller automatiskt på datum+namn med möjlighet att rätta?
7. **Klickvägarna i tabellen ovan** — vilka är värda att bygga, och hur ser
   en länk ut så den inte drunknar i DPT2:s täta layout?

### C · Importen

8. **En väg in i stället för fem.** Kan det vara *"Läs in…"* som tar emot fil
   eller inklistrad text, känner igen vad det är, och säger vad den hittade
   ("3 dagar, 79 grenar, 845 deltagare — 12 rader behöver din blick")?
9. **Granskningen skalar inte.** 845 rader i en 260px-ruta. Vad ersätter den —
   gruppering per gren, bara avvikelserna, en diff mot det som redan finns?
10. **Omimport.** Arrangören ändrar tider löpande. I dag är importen idempotent
    och skriver tyst över. Ska Stig se vad som ÄNDRADES ("100 m final flyttad
    20:25 → 20:35")?

### D · Synken

11. **Vad är synk för Stig?** I dag: osynlig automatik + en knapp som sticker
    ut. Ska det finnas ett synligt, gemensamt tillstånd ("allt uppe" / "3 väntar"
    / "fel") — och i så fall var, en gång för hela appen?
12. Ska något över huvud taget behöva tryckas, eller ska allt gå automatiskt när
    något ändras?

### E · Fältflödet (iOS) — tyngdpunkten

13. **Vägen från deltillfälle till resultat.** Öppnar Stig passet i
    jobbdetaljen? Får Hem ett läge när ett pass pågår? Ska Live Activity
    kunna bära det?
14. **Att peka ut vinnaren bland 22.** Sökfält, favoritmarkering i förväg,
    startnummer, eller de senast fotograferade överst? Kom ihåg: en hand,
    solljus, bråttom.
15. **Resultatinmatningen.** D2:s format är kända per grentyp — kan tangent-
    bordet anpassas (tid vs längd vs poäng)? Behövs placering 2 och 3, eller
    räcker vinnaren i steg 1?
16. **Handle saknas — då?** Hoppa över taggen, eller be om den där och då?
    Om det senare: hur ser "lägg till @-konto" ut mitt i ett flöde där det är
    bråttom?
17. **Vad händer efter delningen?** Går resultatet tillbaka till DPT2 och
    vidare till eventsidan, eller är det en ren SoMe-handling?
18. **Momentmallen för ett grenpass** — Sport-mallen (Startelva · Avspark …)
    passar inte friidrott. Vad heter momenten här?

---

## Låsta invarianter (får inte regreras)

- **Gren-paletten:** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`.
  Färgad kant/markör, **ingen** textetikett, **ingen kant om klassen är okänd**.
- **Kategori:** Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` ·
  Film `#8A6FB0`.
- **"Del av {event}"** — ett deltillfälle eller en match visas aldrig lösryckt.
- **Programmet är härlett**, aldrig lagrat. Ändras ett pass följer allt med.
- **Publicera → Live** visar den server-renderade Horisont-bilden.
- **Max två mättade färger per kort** (D-paketets färgsystem).

---

## Leverabel

1. **En begreppskarta** — vad heter sakerna för Stig, och vad slås ihop.
2. **Navigationsskiss** — vilka ytor finns, vad länkar till vad.
3. **Event-sidan omdesignad** — inklusive import och deltagarhantering.
4. **Individsidan** — ny yta, DPT2 (och webben om det är rimligt).
5. **Fältflödet i iOS** — deltillfälle → vinnare → resultat → SoMe, som
   skisser. Det här är den del Stig behöver först.
6. **Synk-språket** — ett gemensamt tillstånd över alla ytor.

Ta gärna 5 före 1–4 om det behövs för att hinna: **SM är 24–26 juli**, och
fältflödet är det enda som inte går att jobba runt med tangentbord och tålamod.

---

## Underlag i repot

- `design/design_handoff_eventmodell_v5/` — DATAMODELL v5, HANDOFF §1–8,
  HANDOFF-etapp-2-4, HANDOFF-00-Helhet, samt mockuparna för Event,
  Event Program, iOS Event/Jobbdetalj/Signatur/Färgsystem/Widget
- `design/HANDOFF-D2-SVAR-horisont-friidrott.md` — resultatformaten per grentyp
- `design/HANDOFF-D6-SVAR-lasskarm-widgets.md` + `HANDOFF-widget-lasskarm.md` —
  widget/låsskärm, JobbDetaljView-designen
- `design/LATHUND-friidrotts-sm-2026.md` — Stigs eget SM-underlag
- `src/dpt2/motorer/testdata/sm26-tidsprogram.pdf` och
  `sm26-startlista-utdrag.txt` — verkliga källfiler
- Startlistan live: `easyrecord.se/startlist?c=wNEmOO`
