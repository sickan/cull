# DPT2 & iOS — Designunderlag och backlog
*2026-07-17*

## Arbetssätt (viktigt för Design)

- Epiken utvecklas i en **egen branch** så att arbetet kan ske parallellt med att befintlig lösning trimmas vidare.
- Planen ska läggas upp för **löpande leverans**: ny funktionalitet mergas in i befintliga lösningen allteftersom delar blir klara, inte som en stor release i slutet.
- Ordningen: Design tar först fram lösning för modell, UX/UI och presentation. Därefter överlämning till Code med datamodellen.

---

## EPIC: Gemensam evenemangsmodell — koppling mellan event, ligor och matcher

### Bakgrund

Idag finns tre olika mönster för matcher:

1. **Fotboll**: matcher ägs av klubbarna, tillhör en liga som spänner över en hel säsong, men hanteras enskilt.
2. **Friidrott**: mästerskap över flera dagar, individer och grenar hanteras på eget vis (mönstret från Friidrotts-SM).
3. **Tennis**: heldagsevent för en turnering (t.ex. Nordea Open), men respektive match hanteras enskilt precis som fotboll.

Det som saknas är en enkel och tydlig koppling mellan heldagsevent och matcher. Kopplingen ska vara valfri.

### Varför

- Förenklar arbetet med matcher vid bildurval och skapande av sociala medier, både i DPT2 och iOS-appen.
- Styr presentationen på hemsidan: hålla ihop ett mästerskap med dess matcher.
- Styr var och hur material visas under På gång.

### Klargjorda designbeslut (frågor och svar)

**1. Är eventkopplingen frivillig?**
Ja. Fotbollsmatcher är typiskt kopplade till sin liga (t.ex. Damallsvenskan), men kopplingen måste vara frivillig eftersom t.ex. träningsmatcher kan sakna liga helt. En match kan stå fri, men kopplas när det finns en naturlig hemvist.

**2. Är liga och event samma sak?**
Nej, två separata begrepp:
- **Liga**: långlivad struktur över säsonger. Ska på sikt kunna bära historik: tidigare möten mellan lag, hur säsong 2026 slutade, osv.
- **Event**: tidsbegränsat, ett mästerskap eller en turnering över en eller flera dagar.
- En match kan ha ligakoppling, eventkoppling, båda eller ingen.

**3. Grenar och individer**
Dagens grundstruktur från Friidrotts-SM behålls som utgångspunkt: individer kopplas till eventet, eventet har grenar, individerna kopplas till en eller flera grenar. Design tar fram en enklare, generell modell som spänner över alla sporttyper. Grenperspektivet är inte unikt för friidrott utan en generell byggkloss under event.

*Testfall utöver friidrott*: skidåkningens världscup. En åkare kan tävla i flera distanser, och tävlingen består av grenarna, t.ex. 10 km klassisk, sprint och avslutande fem mil i skate.

**4. På gång-logiken**
Så automatisk som möjligt, styrd av det som redan finns inlagt i applikationen, men med manuell override när det behövs.

Exempel på önskat beteende: volleybollmästerskapet i slutet av augusti visas som heldagsevent på avstånd. Mitt i mästerskapet visas i stället Sveriges enskilda matcher som På gång. När en enskild match visas under ett pågående mästerskap ska eventtillhörigheten alltid framgå, t.ex. att matchen är en del av EuroVolley 2026. En match presenteras aldrig lösryckt när den har ett event bakom sig.

---

## Övriga backlogpunkter

### 2. iOS: dynamisk bakgrund på startsidan
Bakgrunden på startsidan är idag hårdkodad till en fotbollsbild. Önskad lösning i prioritetsordning:
1. Hämta en bild som redan finns i lösningen, kopplad till rätt idrott.
2. Möjlighet att ladda upp en egen bild.
3. Fallback: standardbakgrund.

### 3. iOS: restid även efter att heldagsevent startat
Idag försvinner restidsbegreppet ("starta nu för att hinna fram till klockslag") när ett heldagsevent har passerat sin standardstarttid 08:00. Restiden ska kunna visas även efter att eventet konceptuellt har startat, eftersom man kan komma senare under dagen till en viss match eller ett visst tillfälle.
*Koppling till epiken*: när event och matcher är kopplade kan restiden riktas mot nästa deltillfälle i stället för eventets starttid.

### 4. DPT2: konfigurerbara målmappar per flöde
Snabbplock, gallring och generering av material behöver separata, valbara utmappar:
- **Snabbplock**: utpekad mapp som samtidigt fungerar som backup.
- **Gallring**: utpekad mapp, t.ex. på en SSD.
- **Generera media** (sociala medier m.m.): exporteras till en annan utmapp på Dropbox så att materialet blir åtkomligt överallt och kan delas med andra.

### 5. DPT2: spara original utan overlay vid generering
När material genereras med overlay ska originalbilden sparas undan tillsammans med exporten. Dels för att originalet kan behöva redigeras, dels för att varje some-export alltid ska ha en motsvarande version utan overlay.
