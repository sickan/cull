# Design-svar D11 — Event, individer & fältflödet

*2026-07-19 · Till: Code · Från: Claude Design*
*Svar på D11 (`uploads/HANDOFF-D11-event-individ-falt.md`). Fältflödet först — SM är 24–26 juli.*

Beslut fattade med Stig via frågerunda. Fyra mockups levereras (levande, klickbara):

- **`DPT iOS v2 - Fältflöde.dc.html`** — deltillfälle → vinnare → resultat → SoMe *(leverabel 5, prio)*
- **`DPT v5 - Begrepp & Navigation.dc.html`** — begreppskarta, klickvägar, synk-språk *(1, 2, 6)*
- **`DPT v5 - Event Import & Deltagare.dc.html`** — en väg in + skalande granskning + handles *(3)*
- **`DPT v5 - Utövare.dc.html`** — individsidan, härledd historik *(4)*

---

## Tvärgående beslut (påverkar all kod)

### Orden Stig ser (A1–A3)
- **”Event” visas aldrig i UI.** Skrivytan heter **Tävling** (en editor, inte två — slå ihop tävlings-editorn och Event-sektionens editor). En tidsbegränsad tävling visas som **sin typ**: Mästerskap · Cup · Turnering · Världscup. **Liga** behålls för det långlivade. `tavling`/`liga`/`event` förblir samma post i koden, speglad — bara etiketten byter.
- **Utövare** = ett register. Slå ihop `lag(kind=individ)` + `individ`. Historiken **härleds**, aldrig dubbellagrad. (Ordval: *Utövare*. Personer som andrahand.)
- **Gren = disciplinen** (100 m). **Klass** (dam/herr) = enbart färgkant (`#8E5A86`/`#3E7C87`/`#6E8757`), ingen textetikett, ingen kant om okänd. I nav: menyposten *Lag & ligor* kompletteras med **Utövare**; *Event* → **Tävlingar**.

### Fotojobb ↔ Tävling (B6) — den som gör mest ont
Nytt fält i datamodellen. Kopplas **automatiskt på datum + namn** när jobbet skapas, med en synlig, rättbar ”Del av {tävling}”. **Sluta med den tysta namnjämförelsen** — den tappar kopplingen så fort Stig byter namn på kalenderposten.

### Global sökning (B5)
Ny. ⌘K var som helst → utövare, tävling, jobb, gren; tar dig raka vägen dit. Se sökfältet i Utövare-headern.

### Synk-språket (D11–12) — ett tillstånd
Ta bort **”Skicka till telefonen”**. Ersätt osynlig automatik + utstickande knapp med **ett litet synk-märke på samma plats i varje yta** (DPT2: titelraden längst till höger; iOS: Hem-huvudet). Fyra statuslägen med systemets statusfärger:
- **ALLT UPPE** (grön) · **N VÄNTAR** (gul, räknar ner, pushar själv) · **SYNKAR** (blågrå, roterande) · **FEL** (röd — enda läget som ber om ett tryck).
Inget ska normalt behöva tryckas; allt pushas automatiskt (vid start + publicering + när något ändras). Märket säger bara *var* det står.

---

## Fältflödet i iOS (E13–E18) — bygg detta först

Ingång **ur Jobbdetalj**: tryck ett pass i *Dagens deltillfällen* → passet i fokus. Ingen ny flik. Fyra steg med stegindikator (Pass · Vinnare · Resultat · SoMe).

1. **Pass** — ”Del av Friidrotts-SM”, gren med klass-färgkant, PÅGÅR-status, hela startlistan. Stig **stjärnmärker favoriter före loppet**. Primärknapp: *Loppet är kört — välj vinnare*.
2. **Vinnare (E14)** — favoriterna ligger överst som stora tryckytor; annars **slå startnumret** på en numpad (validerar mot startlistan). Ingen scroll bland 22.
3. **Resultat (E15)** — **tangentbordet formar sig efter grenen**: sprint → tid (`11.48`), hopp/kast → längd (`6.29 m`), mångkamp → poäng (`7976 p`). Vinnaren räcker i steg 1; *+ 2:a, 3:a eller annan placering* är valfritt — **och en sämre placering går att lyfta** (lokalfavoriten på plats 5 kan vara storyn).
4. **SoMe (E16–E17)** — story-preview (9:16, sigill + klass-färgkant). **Handle får saknas**: publiceras **utan tagg** direkt, gul notis ”lägg till i lugn och ro i DPT2 sen”. Delningen väntar **aldrig** på handeln. IG + FB. **Ren SoMe** — resultatet lever i storyn, skrivs **inte** tillbaka till DPT2/eventsidan (inget dataspår att städa).

**Momentmall (E18):** Sport-mallen (Startelva·Avspark…) passar inte. Grenpassets moment: *Startlista · Pågår · Resultat · Story*.

---

## Importen (C8–C10) — en väg in

Ersätt de fem vägarna (Tidsprogram / Startlista / Bara deltagare / Läs PDF / +Pass) med **”Läs in…”**: släpp fil, klistra in text eller länk. Parsern **känner igen** dokumenttyp (tidsprogram vs startlista vs bara deltagare) och frågar bara vid osäkerhet.

- **Igenkänt (C8):** sammanfattning i klartext — *3 dagar · 79 grenar · 845 starter · 121 pass* + *”12 rader behöver din blick”*.
- **Granskning som skalar (C9):** aldrig 845 rader i en ruta. Visa **bara avvikelserna**, grupperat: dubbletter (`100 m` vs `100 m `), okänd klass, tidskrockar. Toggle *Bara avvikelser / Alla*. Resten (833 rader) går rent och nämns i en rad.
- **Omimport (C10):** idempotent men **inte tyst** — visa diffen (”100 m final flyttad 20:25 → 20:35”, restid i iOS räknas om). Stig godkänner eller behåller.

**Handles finns i ingen källa** → sätts för hand i **Deltagare & @-konton** på tävlingen (en gång), filtrera på *Utan @*. Sen bär fältflödet dem.

---

## Individsidan (B4) — `DPT v5 - Utövare.dc.html`

Ett kort, samma oavsett väg in (**programrad · deltagarlista · ⌘K · taggad bild**). Innehåll: profil med klass-färgkant + inline **@-konto** (sätts i lugn och ro här), snabbstatistik, **Kommande starter** (härledda pass, ”Del av {tävling}”), **Historik** (härledd tidslinje med gren + resultat, medalj = orange prick), **Bilder & jobb** (taggade, klick → jobbet). Öppen fråga: spegla till publik profil på webben under Sport — härledd historik funkar lika bra där.

---

## Låsta invarianter — bekräftade i alla mockups
Klass-palett (Dam/Herr/Mixed) som färgkant utan etikett · kategori-palett · ”Del av {tävling}” aldrig lösryckt · programmet härlett aldrig lagrat · max två mättade färger per kort · eventtyp = etikett utan egen färg.

## Öppna frågor kvar till Stig
- Ordet **Utövare** vs Personer — vilket sätter vi?
- Individsidan på **webben** — ja/nej för denna etapp?
- 2:a/3:a i fältflödet: alltid fråga, eller bara på Stigs initiativ? (mockup: valfritt)
