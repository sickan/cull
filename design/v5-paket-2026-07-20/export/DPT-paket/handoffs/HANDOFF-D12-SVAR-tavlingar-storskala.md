# Design-svar D12 — Tävlingar + Lag & Utövare i stor skala

*2026-07-19 · Till: Code · Från: Claude Design*
*Svar på D12 (`uploads/HANDOFF-D12-tavlingar-storskala.md`). Ingen datamodell-ändring krävs — ren presentation/UX.*

Tre mockups (levande, klickbara):

- **`DPT v5 - Mästerskap.dc.html`** — adaptiv arbetsyta för stora tävlingar *(fråga 1–6)*
- **`DPT v5 - Lag & Utövare.dc.html`** — delad editor + register *(fråga 7–8)*
- *(liten cup/turnering behåller `DPT v5 - Event Import & Deltagare.dc.html`s kort-stapel)*

---

## Grundgrepp: adaptiv detaljvy (fråga 4)

En tävling renderas efter **skala**, inte efter typ:
- **Liten** (≤ ~8 grenar, en handfull deltagare) → kort-stapeln som redan finns (D11 Event-sidan). Rör den inte.
- **Stort mästerskap / flergrens** (friidrott, skidåkning) → **arbetsyta**: grenar som navigator (vänster) → gren-detalj (höger). Tröskeln är en gräns i koden, inte ett val Stig gör.

Skidåkning faller in i samma form (fråga 5): många åk/heat, klasser, kval/final = grenar + pass + klass. Arbetsytan är byggd generellt för flergrens-/flerklass-mästerskap.

---

## Grenar i skala (fråga 2) — `Mästerskap`, läge *Grenar & deltagare*

Vänster **navigator** ersätter den platta 79-radslistan:
- **Gruppera** växlingsbart: **Klass** (Dam/Herr/Mixed-sektioner) · **Typ** (Löpning/Hopp/Kast/Mångkamp) · **Dag**.
- **Fri sök** ovanpå vald gruppering. **★-filter** (bara favoriter).
- Varje gren-rad: **klass-färgkant** + namn + ev. kat-chip + deltagarantal + ★.

**Dam/herr med samma namn** känns inte som dubbletter: default-grupperingen *Klass* lägger dem i skilda sektioner; i övriga grupperingar skiljer färgkanten dem (två ”Diskus”, en lila en teal). **Kat** (I-20, R, S-klass, para) = liten **textchip**, INTE färg — färgpaletten är låst till kön (dam/herr/mixed). Det löser klass-tvetydigheten utan att bryta invarianten.

## Deltagare i skala (fråga 1) — gren-först

47-chips-per-person är dött. **Kopplingen bor på grenen:** öppna en gren → dess deltagarlista → *”Lägg till utövare — sök ur registret”*. Importen (`Läs in…`) fyller de flesta; manuell koppling är **rättning/komplettering**, inte primärvägen. Handle-status (`N av M har @`) syns per gren; ”Visa alla N” fällder ut hela listan. Personen bär aldrig 79 gren-chips.

## Program i skala (fråga 3) — läge *Program*

- **Dagflikar** (Dag 1/2/3) + **tidsaxel** i stället för platt lista: tid i vänsterkolumn, klass-färgkant per kort, ”Del av” implicit.
- **Favoritfokus** (samma mönster som mobilen): ★ Bara favoritgrenar → 37 rader blir de 3–4 Stig faktiskt jobbar med. Överblick (hela dagen) + fokus (favoriter) i en vy.

## Läs in / granskning (fråga 6)
C8–C10 håller — men granskningen bör låna samma skal-tänk: gruppera avvikelser per gren/klass, inte 845 rader rakt ned. (Utanför denna leverans; noteras.)

---

## Lag & Utövare (fråga 7–8) — `Lag & Utövare`

**En delad editor, rätt fält per slag** (fråga 7). Ett register (`lag` kind=team/individ), ett *Slag*-val (Utövare/Lag) som byter formulär:

**Utövare** — bara det som hör en person till: **Porträtt · Namn · Klubb · Klass (personens egen) · @-konto · Anteckning.**
Bort: profilfärg, ställfärger, ”arkiverat — matcher påverkas inte”-lagspråk, flat tävling-chip. (Visas som överstruket i mockupen så Code ser exakt vad som lyfts ut.)

**Lag** — behåller lag-behoven: Lagnamn · Förening · **Ställfärger** · **Trupp** · **Arkivera** (med matchspråket — här hör det hemma).

**Klass-krocken löst (fråga 8) — båda:**
1. På utövaren visas **bara personens klass** (Dam/Herr som färgkant-val). Tävlingens/grenens klass syns **på grenen**, inte på personen.
2. Kopplingen går via **grenen** (`disciplin_deltagare`) — sektionen *”Tävlar i”* listar grenar med deras egen färgkant + ”Del av {tävling}”, och det driver *Kommande starter*. **Ingen flat tävling-chip** på personen (det tredje, krockande sättet är borta).

Utövarsidan (D11b) och denna editor delar nu modell: sidan läser, editorn skriver; historik + kommande starter härleds ur grendeltagandet.

---

## Låsta invarianter — bekräftade
Klass-färgkant utan textetikett (Dam #8E5A86 · Herr #3E7C87 · Mixed #6E8757); ”Del av {tävling}” aldrig lösryckt; program härlett aldrig lagrat; eventtyp = etikett utan färg; DPT2:s look & feel i övrigt. **Nytt mönster, inte ny färg:** kat (I-20/R/S) = neutral textchip.

## iOS — Dagens deltillfällen (kopplat, byggt i `DPT iOS v2 - Jobbdetalj.dc.html`)
- **Bort med "@ N"-chippet** (kopiera-IG-konto) i listan. Handles hanteras i fältflödet / sätts i DPT2 — inte som en knapp per rad.
- **Varje gren är tappbar → Skapa SoMe**, även utan startlista/handle. Tap öppnar en sheet: **Skapa SoMe** (→ välj vinnare · resultat · story = fältflödet) + *Öppna passet*.
- Klass som **färgkant** per rad (dam/herr/mixed), favoritstjärna kvar, NÄST-markering kvar. Hållpunkter (Invigning m.m.) har ingen SoMe-väg.

## Öppna frågor till Stig
- Var går tröskeln liten↔stor tävling (grenantal? deltagarantal?) — eller alltid arbetsyta för mästerskap oavsett storlek?
- Ska granskningen (Läs in) byggas om i samma skala nu, eller räcker den till nästa stora inläsning?
