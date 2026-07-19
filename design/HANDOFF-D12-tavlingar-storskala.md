# Design-handoff D12 — Tävlingar i stor skala (NYTT design-jobb)

*2026-07-19 · Till: Claude Design · Från: Code*

*Stigs beställning: "Vi måste se över Tävlingar och t.ex. Friidrott även om det
inte är så många sådana tävlingar. Men skidåkning är lite på samma håll. Sidan
är helt ohållbar nu. Ta ett helt nytt grepp."*

*Kontext: eventmodellen + fältflödet (D11-svaret) är byggda och SM-testade. Det
som nu visat sig är att Tävlingar-DETALJVYN i DPT2 inte skalar för ett stort
flergrensmästerskap. Friidrotts-SM 2026 (24–26 juli) är provet; **skidåkning
(t.ex. Skid-VC/VM med många åk, klasser, kval/final) har samma form.** Detta är
en OMDESIGN av detaljvyn, inte en puts.*

---

## Vad som är ohållbart (konkret, från skärmdumpar 19/7)

Friidrotts-SM 2026 i siffror: **79 grenar · 845 starter · 37 deltillfällen per
dag · 100 m har 47 deltagare.** Tre kort i detaljvyn kollapsar under det:

### 1. Deltagare-kortet — per-person-chips över ALLA grenar
En deltagare (Albin Edin, IFK Göteborg) visas med **en togglebar gren-chip för
VARJE gren i hela tävlingen** — Längd, Diskus, 100 m, Tresteg, Spjut, Kula,
Höjd, 800m, Slägga, Tiokamp 100m, I-20 Diskus, I-20/R-stående 100m, … 79 chips.
Att koppla en person till sina 1–3 grenar genom att leta i 79 chips är omöjligt,
och kortet blir metershögt per person. Med hundratals deltagare är kortet
obrukbart. (Chip-modellen kom från D11-svaret och fungerar för en handfull
grenar — inte för ett mästerskap.)

### 2. Grenar-kortet — platt lista på 79 rader
En osorterad, ogrupperad, osökbar lista: Längd · Diskus (1 deltagare) · 100 m
(47 deltagare) · Tresteg · Spjut · Kula · Höjd · 800m · Slägga … Ingen klass
syns (dam/herr/I-20/R/S-12/mångkamp), ingen gruppering, ingen sök. Dam- och
herr-varianten av samma gren har samma namn ("Diskus", "Diskus") och går bara
att skilja på färgkanten — i en platt lista är det förvirrande (Stig trodde
först att de var dubbletter).

### 3. Program-kortet — 37 deltillfällen/dag som platt lista
Dagflikar finns (Dag 1/2/3) men varje dag är 37 rader rakt ned, "inga deltagare
än" på de flesta. Fungerar att scrolla, men ger ingen överblick och ingen väg
att jobba fokuserat (jfr mobilens favoritgrenar, som vi redan byggt där).

**Gemensam rot:** modellen är rik och rätt (grenar, pass, klass, härlett
program, deltagare per gren), men detaljvyn presenterar allt platt och
allt-på-en-gång. Det som saknas är STRUKTUR för skala: gruppering, klass,
sök/filter, och en arbetsyta byggd för hundratals rader.

---

## Vad som finns att designa emot (datamodell + invarianter)

Modellen bär redan allt som behövs — omdesignen är ren presentation/UX, inga
nya fält behövs (om inte Design vill).

- **Gren (disciplin)** bär `namn` ("100 m") + `klass` (dam/herr/mixed, låst
  palett) + `pass[]` (tidsatta tillfällen med datum+tid). **Dam och herr är
  SKILDA grenar med samma namn** — skiljs på klass/färg.
- **Deltagare ⟂ gren:** n:n via `disciplin_deltagare` (utövare ur ETT register,
  D11b §2). En utövare tävlar oftast i 1–3 grenar; en gren har 1–48 deltagare.
- **Program HÄRLEDS** (aldrig eget register): pass + tidsatta matcher +
  hållpunkter, sorterat/grupperat per dag. "Del av {tävling}" alltid.
- **Läs in…** (C8–C10, byggt): en väg in som gissar dokumenttyp, visar
  sammanfattning + BARA avvikelser, och en icke-tyst omimport-diff. Fungerar,
  men granskningens skala kan behöva samma nytänk.
- **Mobilen (byggt):** favoritgrenar per sport fokuserar Dagens deltillfällen
  (stjärnmärk → visa bara dem + "Visa alla"). Ett möjligt mönster även för
  desktop.

**Låsta invarianter (får ej regreras):** klass-palett som färgkant utan
textetikett (Dam #8E5A86 · Herr #3E7C87 · Mixed #6E8757); "Del av {tävling}"
aldrig lösryckt; programmet härlett aldrig lagrat; eventtyp = etikett utan egen
färg; DPT2:s look & feel i övrigt.

---

## Frågor till Design (ta ett helhetsgrepp)

1. **Deltagare i skala:** hur kopplar man en utövare till sina grenar när det
   finns 79 grenar och hundratals utövare? (Sök-driven koppling? Utgå från
   grenen i stället för personen? Import bär redan det mesta — ska manuell
   koppling ens vara den primära vägen?)
2. **Grenar i skala:** gruppering (klass? grentyp löp/hopp/kast/mångkamp?
   I-20/R/S-klasser?), sök, och hur dam/herr-varianter av samma namn visas utan
   att kännas som dubbletter.
3. **Program i skala:** överblick + fokus för 37 deltillfällen/dag. Kan
   mobilens favoritgren-fokus återanvändas? Vad är "arbetsläget" vid datorn
   dagarna före tävlingen vs på plats?
4. **En vy eller flera?** Är "allt i ett kort-staplat detaljkort" fel form för
   ett mästerskap? Behövs en egen mästerskaps-arbetsyta (grenar som nav →
   gren-detalj med deltagare + pass), skild från en liten cup/turnering?
5. **Skidåkning:** samma form (många åk/heat, klasser, kval/final) — designen
   bör täcka flergrens-/flerklass-mästerskap generellt, inte bara friidrott.
6. **Läs in / granskning:** räcker C8–C10-granskningen för 845 rader, eller
   behöver den samma skal-tänk?

---

## Avgränsning
- Detaljvyn för STORA tävlingar (mästerskap/flergrens). Små cups/turneringar med
  en handfull grenar fungerar redan — men en gemensam form som klarar båda är
  önskvärd.
- Ingen datamodell-ändring krävs (men Design får föreslå fält om det behövs).
- Rör inte fältflödet (D11) eller mobilens favoritgrenar — de är byggda och
  fungerar; de kan tvärtom vara mönster att låna.

## Underlag för Design
- Skärmdumpar 19/7 (Deltagare-chips, Grenar-lista, Program) — se Stigs meddelande.
- Byggda referenser: `HANDOFF-D11-SVAR-event-individ-falt.md` (eventmodellen),
  mobilens favoritgrenar (JobbDetaljView), Läs in-flödet (EventSektion).
