# Handoff — Begrepp & Navigation (implementering)

*2026-07-19 · Till: Code · Från: Claude Design*
*Mockup: `DPT v5 - Begrepp & Navigation.dc.html`. Detta är den kod-nära delen av D11-svaret (`HANDOFF-D11-SVAR-event-individ-falt.md` §Tvärgående).*

Fyra ändringar. Ingen är en storrelease — mergas löpande. Ordning nedan = föreslagen ordning (1 låser upp resten).

---

## 1 · Begreppen — rename i UI, inte i schemat

Schemat rörs **inte** (`tavling`/`liga`/`event` förblir samma speglade post). Detta är ett **presentationslager**:

| Kod idag | Visas för Stig |
|---|---|
| `event` (tidsbegränsad) | tävlingens **typ**: Mästerskap · Cup · Turnering · Världscup |
| `liga` | **Liga** |
| skrivytan | **Tävling** (en editor) |
| `disciplin` | **Gren** |
| gren = dam/herr | **Klass** — enbart färgkant, aldrig ord |

**Att göra**
- Ordet **”Event” försvinner ur alla UI-strängar.** En tävlingsinstans renderas med sin `typ` som etikett (ingen egen färg — ärver kategori).
- Nav: `Event` → **Tävlingar**. Lägg **Utövare** som egen post (bredvid Lag & ligor).
- **Slå ihop de två tävlings-editorerna** (Lag & ligor + Event-sektionen) till en. Stig redigerar på ett ställe, kopplar på samma.

## 2 · Utövare — ett register

Slå ihop `lag(kind='individ')` + `individ` → **`utovare`**.
- Migrering: deduplicera på namn+klubb+födelseår; behåll bägge id:n som alias tills allt pekar rätt.
- **Historiken härleds** ur tävlingarnas grenar → deltagare. Lagra aldrig resultat/historik på utövaren.
- Utövarsidan (`DPT v5 - Utövare.dc.html`) läser: profil, härledda *kommande starter*, härledd *historik*, taggade *bilder/jobb*, ett **@-handle-fält** (enda skrivbara på kortet).

## 3 · Fotojobb ↔ Tävling — nytt fält (den viktigaste)

Idag kopplas de av en **namnjämförelse** → tappas tyst när Stig byter namn.
- Lägg `fotojobb.tavling_id` (nullable) i datamodellen.
- Sätts **automatiskt på datum + namn-match** vid jobbskapande, men **synligt och rättbart** (”Del av {tävling}” med byt-knapp). Aldrig implicit-only.
- När fältet finns: iOS slutar gissa via titel. Byte av kalendernamn påverkar inte längre kopplingen.

## 4 · Global sökning + synk-märke

**Sökning (⌘K):** ett index över utövare · tävling · fotojobb · gren. Träff → djuplänk till rätt kort. Nås var som helst i DPT2 (fältet sitter i headern).

**Synk — ett tillstånd, ett märke.** Ta bort **”Skicka till telefonen”** i Program-kortet.
- En delad status, renderad på **samma plats** överallt (DPT2: titelraden höger; iOS: Hem-huvudet).
- Fyra lägen (systemets statusfärger): `ALLT UPPE` (grön) · `N VÄNTAR` (gul, räknar ner, pushar själv) · `SYNKAR` (blågrå) · `FEL` (röd — enda som ber om tryck).
- Push sker automatiskt: vid start, vid publicering, **och när något ändras lokalt** (det var det ”Skicka till telefonen” löste — nu implicit). Klick på märket = liten logg (vad väntar / senast pushat).

---

## Klart-kriterier
- [ ] Inga UI-strängar innehåller ”Event”; instanser visar sin typ.
- [ ] En tävlings-editor; `Utövare` i nav.
- [ ] `utovare`-register; historik 100 % härledd (inga dubbelskrivna rader).
- [ ] `fotojobb.tavling_id` finns; iOS läser fältet, inte titeln.
- [ ] ⌘K-sökning live; synk-märket ersätter ”Skicka till telefonen”.

## Öppet till Stig
- Ordet **Utövare** vs *Personer*.
- Utövarsidan på **webben** (spegling under Sport) — denna etapp eller senare?
