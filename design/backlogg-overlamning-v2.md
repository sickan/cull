# Backlogg — överlämning till Code och Design
*Insamlat juli 2026, uppdaterad 17 juli. Prioritering diskuteras separat.*
*Punkt 15 (sportanpassade moment och poänglogik i Ny story) är redan överlämnad separat till Code och ingår inte här.*

## Alla appar (DPT2, iOS, hemsidan)

### 1. Versionsvisning
- Versionsnummer visas tydligt i alla appar.
- Synligt versionsnamn bokstaveras: "två", "två punkt ett" (aldrig 2 eller 2.1).
- Fullständigt byggnummer i tekniskt format (t.ex. 2.1.0 build 47) under "Om" eller "Inställningar".

## DPT2

### 2. Väderväxling
- Idag visas väder för hela dagen på nuvarande plats.
- Ny funktion: växla mellan "där jag är" och "dit jag ska".
- "Dit jag ska" hämtas från nästa match eller nästa heldagsevent i på gång-listan. Endast platsen skiftar; tidsspannet är detsamma (hela dagen från nu).

### 3. Eventpublicering + kundgodkännande
Publicering av material från övriga event (bröllop, student, porträtt m.m.) i tre faser: före ("på gång", t.ex. "bröllop på lördag"), under (behind the scenes), efter (färdigt material).

**Godkännandeformulär** där kunden kryssar i:
- Motiv: miljöbilder / kunden specifikt (t.ex. brudparet) / alla (gäster, familj m.m.)
- Tid och plats: får anges / skyddat
- Namn: får publiceras / inte
- Kanaler: sociala medier / dalecarliaphoto.se / övrig marknadsföring

**Flöde:** DPT2 genererar unik länk per event → länken skickas till kunden → kunden fyller i och skickar tillbaka → svaret sparas på eventet och styr vad publiceringsflödet tillåter.

**Kundmejl, autogenererat per eventtyp:**
1. Varm inledning: "snart är det dags för er stora dag / vår fotografering / vårt samarbete", jag ser fram emot detta.
2. Frågor? Hör av dig. Annars ses vi på avtalad tid och plats. Jag nås på mitt telefonnummer.
3. Stycke om användningsrätt med formulärslänken.
4. Stycke om leveransen: dagen efter eventet kommer en unik gallerilänk med kod (Pixieset) för att se, välja, ladda ner och beställa utskrifter.

**Teknisk notering:** kräver publik endpoint och lagring för formulärsvar, till skillnad från övriga DPT2.

### 7. SpeedLedger-koppling
- Inget öppet API finns (verifierat juli 2026); SIE4-import gäller endast bokföringsverifikationer, inte fakturaskapande.
- Grundlösning: fält för SpeedLedger-fakturanummer per betaluppdrag, statusflagga (ej fakturerad / fakturerad / betald), manuell uppdatering.
- Möjligt tillägg: export av ny kund som CSV i SpeedLedgers kundregisterformat.
- Omvänd matchning via SIE4-export är teoretiskt möjlig men överkurs.

### 10. Leveranskrav per uppdragsgivare
- Specifikationer per förbund/klubb sparas och visas automatiskt i publiceringsflödet för matchen.
- Exempel CEV: 30 JPG, exakt 2500×1500 px, max 7 MB, uppladdning efter set 1.

### 12. Utrustningspackning
- Packmallar per eventtyp som genererar packlista när eventet planeras.
- Kompletteras med lärdomar från eventnoteringarna (punkt 6).

### 13. Publiceringsstatistik
- Överblick över vad som publicerats var, per match/event och kanal.
- Underlag vid frågor från klubbar och sponsorer.

### 14. Kundregister-light
- Samlar per kund: event, godkännandeformulär (punkt 3), fakturanummer/status (punkt 7), gallerilänk.
- Litet CRM utan att bli ett.

### 17. Matchlathund / fotografens matchplan (Claude-genererad)
Har tidigare skapats manuellt via AI-tjänster inför matcher, tävlingar och mästerskap. Gedigen men kortfattad plan för matchen och matchdagen.

**Innehåll:**
1. **Matchens betydelse:** tabelläge och viktiga placeringar, sista omgången, slutspelsmatch, inbördes möten och historik, historiska perspektiv, derby, högriskmatch.
2. **Spelare att följa:** nya i laget, på väg bort, i god eller dålig form, nyckeldueller spelare mot spelare.
3. **Praktiskt kring matchdagen:** väderprognos vid matchstart, parkering i området, trafikläge.
4. **Foto:** relevant utrustning utifrån förhållandena, förslag på inställningar kopplade till vädret.
5. **Arenan:** var solen står och går ner, var man bör placera sig.

**Genomförande:** genereras per match i DPT2 via Claude API med matchdata, väder och arenainfo som underlag. Knyter an till på gång-matcherna, väderfunktionen (punkt 2), packmallarna (punkt 12) och eventnoteringarna (punkt 6) — egna lärdomar från förra besöket på samma arena är underlag för arenadelen.

**Tillgänglighet och export:**
- Läsbar i iOS-appen på matchdagen.
- Export som PDF till telefon, dator eller iPad (funkar även offline i arenamiljö).
- Ska kunna skickas till valfri mejladress.

## iOS-appen

### 5. Förhandsgranskning vid SoMe-generering
- Nuläge: förhandsgranskningen hamnar högst upp, utanför synfältet; man ser inte att den skapats utan att scrolla upp.
- Lösning: bättre modell. Alternativ att väga: autoscroll när klar, rendering där man befinner sig, eller tydlig indikator/knapp "Visa förhandsgranskning".

### 16. Delning till Instagram Stories misslyckas
- Nuläge: story renderas klart, men "Dela till Instagram Stories" ger felet "Det går inte att skicka filen. Försök skicka det som en annan filtyp."
- **Verifierat:** bilden i sig är okej. Workaround som fungerar: spara till Filer → flytta till Bilder → välja bilden i Instagram. Felet ligger i appens delningsväg, inte i den renderade filen.
- **För Code:** troligen fel filtyp/UTI eller fel mekanism. Rätt väg för direktdelning till Stories är Instagrams URL-schema `instagram-stories://share?source_application={bundle-id}` med bilddatan på UIPasteboard som `com.instagram.sharedSticker.backgroundImage` (PNG/JPG-data, inte fil-URL). Kräver `instagram-stories` i LSApplicationQueriesSchemes i Info.plist. Enklare alternativ: spara direkt till bildbiblioteket och öppna Instagram.
- **Interim:** en "Spara till Bilder"-knapp bredvid delningsknappen tills delningen är lagad. Buggen slår direkt mot värdet av hela story-funktionen.

### 19. Match saknas i kalendervyn
- Nuläge: Malmö FF – Bröndby IF (Eleda Stadion, lör 18 juli) syns i listvyn under Fotojobb men inte i kalendervyn. Den 18:e visar varken jobbprick eller väder, medan andra jobbdagar har båda.
- **Ledtråd:** i listan visar matchen ingen datumtext, bara namn och arena, till skillnad från alla andra poster. Tyder på saknat/felformaterat datumfält — kalendern kan inte placera posten och väderhämtningen triggas inte.
- **För Code:** kontrollera hur datumet lagras/parsas för denna post (annan källa/inmatningsväg än övriga?). Kalender- och listvy bör läsa samma fält. Robusthet: poster utan giltigt datum ska flaggas synligt, inte tyst försvinna ur kalendern.
- Öppen fråga: lades MFF-matchen in på annat sätt än övriga jobb (manuellt vs import)?

## iOS + DPT2

### 6. Noteringar på event och matcher
- Snabba noteringar i iOS-appen under eventet; utförligare i DPT2 efteråt.
- Innehåll: reflektioner och saker att komma ihåg (plats, ljus, tider, kontakter).
- Ska vara sökbara/synliga vid planering av liknande event framåt.
- Synk mellan iOS och DPT2 antas — bekräfta.

### 11. Filmlogg
- Vilken rulle sitter i vilken kamera, exponeringsanteckningar.
- Status: i kamera / hos lab / skannad.
- Kopplad till frysinventariet.

### 18. Nyckelspelare kopplas till publiceringsflödet
Spelarna från lathundens "spelare att följa" (punkt 17) blir aktiva objekt i appen, inte bara text.

- Om en nyckelspelare finns i t.ex. startelvan görs hen extra lättillgänglig som snabbval vid bildval och SoMe-skapande.
- Nästa steg: lathundens berättelse flödar in i overlaytexterna, t.ex. "Hon gjorde mål i sin första match för Malmö FF!"
- Kärnan: lathunden vet *varför* spelaren är intressant (debut, på väg bort, formstark); när spelaren gör något i matchen kombinerar overlayn händelsen med kontexten.
- Datamodell: nyckelspelare med "storyline" per match, matchas mot startelva/händelser, exponeras som snabbval och som textunderlag för overlay-generering.
- Knyter an till Damallsvenskan-researchflödet — samma JSON per match kan bära storylines.

### 20. Verifiera SoMe-flödet för friidrott före Friidrotts-SM
Under tennisen 17 juli låg fotbollskänslan kvar i flera vyer (fel moment, "Gamesiffror" som etikett på setsiffror — se separat överlämnad punkt 15). Friidrott skiljer sig mer från fotboll än vad tennis gör; testa i god tid före Friidrotts-SM 24–26 juli i Uppsala.

**Att särskilt kontrollera:**
- **Moment i Ny story:** friidrott behöver t.ex. Grenstart, Försök/Kval, Final, Resultat, Rekord (SM-rekord, personbästa), Nästa gren/pass.
- **Overlay-etiketter och siffror:** inte ställningssiffror utan resultat per gren — tider ("10,42"), höjder/längder ("2,01 m", "62,44 m"), placeringar.
- **Struktur:** ett mästerskap är ett heldagsevent med många grenar och aktiva, inte hemmalag–bortalag. Vyer som antar två lag måste hantera det.
- **Matchfakta-pålägget:** det automatiska pålägget får inte anta två lag.

## Hemsidan

### 4. Mobil layout för sport + på gång
- Desktop är rätt. På mobil hamnar på gång-informationen långt ner efter matchreferat och galleribilder.
- Lösning: behåll ordningen, men lägg tidigt en liten notering om nästa event med ankarlänk ner till den utförliga på gång-sektionen.

### 8. Presskort i sidfot och kommunikation *(även DPT2-mejl)*
- Medlem i Svenska Journalistförbundet, svenskt och internationellt presskort (IFJ).
- Ska framgå: under Om på hemsidan samt i en standardiserad mejlsidfot (kontaktuppgifter, länkar, presskortsinfo).
- Gäller ackrediteringsmejl och kundmejlet i punkt 3.
- Exakt formulering finslipas i copyarbetet.

### 9. Tjänstesektion
Tydlig sektion med ingångar från startsida och navigation.

- **Sport:** matchfotografering inom alla sporter; lagfoton och individuella spelarbilder; dokumentation (träningsläger, sammandrag, cuper, konferenser, spelarutbildningar); bildgalleri/bildbyrå för sportbilder.
- **Människor:** bröllop, student, dop och andra högtider; porträtt, familj, sällskapsdjur.
- **Kommersiellt:** produkt, mode; artister (portfolio, konsert).
- **Landskap och natur:** litet urval på sajten, stort sortiment bakom; försäljning digitalt och som fysiska utskrifter.

Notering: bildbyrå-delen kan behöva egen ingång — annan målgrupp (medier, klubbar, spelare, föräldrar) än bokade fotograferingar. Passar temana: Hav (sport), Rosé (människor), Sol (landskap); Kommersiellt får eget uttryck eller sorteras in.

## Öppna frågor
- Punkt 6: synk av noteringar mellan iOS och DPT2 — bekräfta.
- Punkt 8: exakt formulering av presskortstexten.
- Punkt 19: lades MFF-matchen in på annan väg än övriga jobb?
- Redan hanterat, ej med här: ackrediteringsmodul finns med mejl, integration åt båda håll pågår. Punkt 15 (sportmoment + poänglogik i Ny story) överlämnad separat till Code.
