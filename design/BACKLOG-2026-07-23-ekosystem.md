# DPT2 / App-ekosystem — Backlog (Stig 2026-07-23)

**Session:** 2026-07-23 · **Omfattning:** DPT2 (desktop), iOS, iPad, webb (dalecarliaphoto.se)
**Status:** Insamlad och strukturerad av Stig. Öppna frågor besvarade där inget annat anges. Ej implementerad — för handover till Claude Code och Design.
*Routing-kommentarer (kopplingar till pågående spår) tillagda av Code längst ner per punkt-ID — Stigs text är oförändrad.*

---

## Buggar

### B1. Klickmål på utövare stjärnmarkerar felaktigt
**Plattform:** DPT2 (desktop) + iOS
Klick på hela raden/kortet för en utövare triggar stjärnmarkering. Fel beteende. Att välja en utövare ska enbart markera/välja den. Stjärnmarkering ska ske **endast** vid klick på själva stjärnikonen.

---

## Förändringar

### F1. Stjärnmärkta överst som standardsortering
**Plattform:** DPT2 (desktop) + iOS
Stjärnmärkta lag/spelare/grenar ska ligga överst i alla relevanta listor som default. Gäller **endast** när ingen annan sortering är aktivt vald av användaren. Väljer användaren en egen sortering gäller den istället.

### F2. Automatisk stjärnmarkering från inklistrad text
**Plattform:** DPT2 (desktop) + iOS
Kunna klistra in en fritext (sammanfattning av spelare/utövare att hålla extra koll på). Appen tolkar namnen, matchar mot startlistan/utövarlistan och stjärnmarkerar de som nämns automatiskt.
- Bygger på befintlig inläsning av startlistor och grenar.
- **Att definiera vid spec:** matchningslogik för namn i fritext mot utövarlista (exakt/fuzzy, hantering av dubbletter och ofullständiga namn).

---

## Epic: Enhetligt publiceringsflöde med genreprofiler

Flera punkter i sessionen är samma epic sett från olika håll: generalisera Bildsvepet/publiceringsflödet bort från det sportspecifika. **En gemensam motor, olika genreprofiler** (sport / landskap / människor) som styr ton, overlay-innehåll och taggförslag. Samma princip som story moments (punkt 15) redan följer.

### E1. Generalisera publiceringsflödet till alla genrer
**Plattform:** iOS + iPad (primärt) + DPT2 + webb
Kunna plocka upp en bild eller bildserie och publicera som med matcher: overlay på förstabilden, automatgenererad beskrivande text, taggar och omnämnanden. Idag finns webbpublicering för landskap, men de sociala flödena i iPhone/iPad är begränsade för icke-sport.

### E2. Enhetliga sociala flöden över genrer
**Plattform:** iOS + iPad + DPT2
Publiceringsflödena ska se likadana ut oavsett genre. Gemensamma val:
- Publiceringstyp: **story**, **inlägg**, **Facebook**.
- Bildantal (som i sportflödet): upp till **10 bilder automatiskt** (direktintegration) eller upp till **20 bilder via disk**.
- **Att utreda (research, ej beslut):** stories via API är begränsat. Behöver klargöras vad som går att automatisera mot Instagram/Facebook stories vs. vad som kräver manuell postning från appen.

### E3. Overlay per genre (utan matchdata)
**Plattform:** iOS + iPad + DPT2
Overlayen behöver ett läge bortom scoreboard-logiken.
- **Sport:** scoreboard (resultat / lag / tid). Befintligt.
- **Landskap:** **plats + logga.** Diskret logga som signatur plus ortnamn för geografisk förankring. **Inget datum** (drar mot det dokumentära; hör hemma i metadata/bildtext). Gäller både sociala flöden och portfolio/hemsida.
- **Människor:** egen profil, definieras när den genren tas.

### E4. Genrespecifik captionton
**Plattform:** iOS + iPad + DPT2
Textgenereringen ska följa olika ton per genre.
- **Sport:** befintliga regler (hashtags per sport, länk till /sport, 📷-signatur m.m.).
- **Landskap:** nedtonad ton närmare webbcopyn för Skagen Sol. Återanvänd **inte** sportreglerna rakt av.
- **Taggar/omnämnanden:** sport = klubbar + verifierade konton; landskap = platser, regioner, turism-/vandringskonton. Annan förslagslogik per genre.

### E5. Inröstad text → caption + overlay-rubrik
**Plattform:** iOS + iPad + DPT2, alla genrer
I alla publiceringsflöden kunna tala in en text som Claude bearbetar. Två utdata från en inröstning:
1. Putsad brödtext/caption.
2. Kort overlay-rubrik. **Får formuleras om** för att passa overlay-formatet (längd/ton) — inte ordagrant plockad ur talet.
- Genreprofilen styr bearbetningen (sportton / landskapston / människor-ton).
- **Teknik:** ljudet skickas till Claude för transkribering + bearbetning i ett steg. Obs: Claude-API är textbaserat — kräver ett transkriberingssteg i kedjan på serversidan (t.ex. Whisper eller motsvarande) före Claude-bearbetningen, alternativt en multimodal väg. Väljs vid spec.

---

## Webb + sociala utskick från mobil

### W1. News flashes på startsidan
**Plattform:** iOS (avsändare) + webb (visning); DPT2/iPad senare
Kunna trycka ut korta redaktionella uppdateringar från mobilen till en liten sektion på startsidan på dalecarliaphoto.se. Rubrik, kort text, ev. liten bild. T.ex. "Nu är jag på plats på Uppsala friidrottsarena" eller en rad framför en fjällsjö.
- **Ton:** redaktionell, "var jag är / vad jag ser". Låg ton, ingen uppmaning.
- **Visning:** kort flöde, senaste **3-5** visas, nyast överst. Äldre rullar ur flödet.
- **Lagring:** Cloudflare KV/D1 (dynamiskt, ingen rebuild). iOS-appen skriver, startsidan läser.
- **Teknik:** kräver en skriv-endpoint (Cloudflare Worker) som appen anropar, med autentisering så bara Stig kan posta.
- **Avgränsning mot journal:** flash = kort, realtid, "här är jag nu", rullar ur flödet efterhand. Journal = längre, redaktionellt, permanent. Ingen överlappning.

### W2. Marknadsföringsutskick / snabba stories från mobil
**Plattform:** iOS (avsändare) + webb + Instagram/Facebook; DPT2 (publiceringsflödet)
Kunna skicka ut korta reklambetonade uppdateringar, primärt som **stories**, men även till hemsidan, Instagram och Facebook. T.ex. "Tävlar du på Uppsala friidrott i helgen? Är du intresserad av professionella bilder på ditt tävlande? Jag är där, hör av dig!"
- **Ton:** säljande, call-to-action, riktat mot potentiella kunder. Separat flöde och mall från W1 (news flash).
- **Koppling:** hör ihop med DPT2:s befintliga publiceringsflöde med per-kanal textkomposition (social/webb/iOS). Story-formatet blir troligen en ny kanaltyp där, inte något fristående.
- **Att utreda:** samma story-API-begränsning som E2.

**Not:** W1 och W2 delar teknisk grund (komponera i appen, tryck ut) men är **separata flöden** med olika mallar, ton och kanalval.

---

## Epic: Reseplanering med POI-lager

### R1. EV-ruttplanering som väger in trevliga stopp
**Plattform:** DPT2 + iOS (+ webb/iPad senare)
Planera resan med hänsyn till trevliga stopp (restauranger, sevärdheter) vid laddstoppen och längs rutten, inte bara laddhastighet och räckvidd.
- **Beslut:** appen **ersätter** ruttplaneringen med egen motor via **ABRP API** (Planning API ger rutt + laddstopp).
- POI-lager (Google Places / OSM) ovanpå: sampla POI:er runt varje laddstopp **och** i en korridor längs rutten. Rutt-geometrin från ABRP driver detta.
- **Att veta:** ABRP API har setup- + per-plan-kostnad (kontakta ABRP för villkor). Detta blir en egen reseplanerare med POI-lager — en rejäl epic, inte en liten funktion.
- ABRP föddes i Sverige 2016, ägs numera av Rivian.

### R2. Fototips på plats / vid destination / längs rutten
**Plattform:** DPT2 + iOS (+ webb/iPad senare)
Appen föreslår fotograferingsvärda platser baserat på var jag är, dit jag ska, eller längs körsträckan.
- **Beslut:** **platstips räcker** (utsiktspunkter, landmärken, natur). Ingen Locationscout-nivå av bildinspiration krävs.
- **Datakälla:** Google Places API (New) eller OpenStreetMap/Overpass. Locationscout har inget öppet API och faller bort.
- "Längs rutten" delar rutt-geometri med R1 — samma ABRP-rutt samplas för både laddstopp-POI och fototips.

### R3. Spegla fotojobb till privat Google-kalender för EX90
**Plattform:** iOS/DPT2 + Google Calendar
EX90 kan bara läsa ett privat (icke-företags) Google-konto. Fotojobb ligger i företagskontexten. Appen ska spegla jobb med plats till det privata kontot, så de dyker upp som destination i bilen.
- **Beslut:** appen läser fotojobben från **DPT2:s eventmodell direkt** (DPT2 = sanningskälla). Enkelriktad synk: DPT2-event → privat Google-kalender → bilen. Ändras jobbet uppdateras spegeln; avbokas det tas spegeln bort.
- Adressen läggs i events location-fält så bilen kan sätta destination.
- **Att verifiera i bilen (att-göra, ej fråga):** visar EX90 faktiskt kalender-events som navigeringsförslag, och kräver den giltig Maps-adress i location-fältet? Testa med ett vanligt privat event.

---

## Öppna att-göra (ej beslut från Stig)

- **EX90-verifiering** (R3): testa kalender-till-navigation i bilen.
- **Story-API-utredning** (E2/W2): kartlägg vad som går att automatisera mot Instagram/Facebook stories vs. manuell postning.
- **ABRP API-villkor** (R1): kontakta ABRP för setup- och per-plan-kostnad.

---
---

# Routing & kopplingar (Code, 23/7) — för vidare diskussion, inga beslut

*Var varje punkt hör hemma i pågående spår + vad som redan finns att bygga på.*

| ID | Spår/ägare | Kopplingar till pågående arbete |
|----|-----------|--------------------------------|
| **B1** | v5/iOS + DPT2 (buggfix, kan tas när som) | Stjärnlogik: `disciplin.favorit` (M-7) + iOS `FavoritGrenar` |
| **F1** | v5/iOS + DPT2 | iOS har redan "stjärnmärkta överst" för grenar (21/7) — generalisera mönstret |
| **F2** | v5/DPT2 | Bygger på C8–C10 "Läs in…"-unifieringen + Claude-tjänsten; fuzzy-matchning behöver spec |
| **E1–E5** | **Stor epic, spänner v5-publicering + v6-portering.** | Motorn finns till hälften: §10 momentmallar per kategori (Sport/Landskap/Människor/Film) är exakt "genreprofil"-principen; kategorifacit + kanonfärger låsta; **terminologi-per-kategori-modulen (v6 #6) är byggd** och är samma idé för ord — genreprofilen bör ÄGA båda. E3 landskaps-overlay: story_overlay har redan tema/format-axlar, behöver "utan matchdata"-läge. E4: bildsvep-tonen per genre ↔ webbcopy Skagen Sol. **E5 (röst→caption) överlappar Dala/B-003 (röst→action)** — samma transkriberings-infra, bygg EN röstkedja. Story-API-utredningen (E2) gäller även W2. Design-handover behövs för overlay-utseende per genre. |
| **W1** | Webb + iOS. **Passar content-sync-mönstret exakt** | = en mini-domän: D1-tabell + skriv-endpoint (Bearer finns) + publik läs-rutt; startsidan läser dynamiskt (ingen rebuild — OBS: startsidan är statisk idag → behöver klient-side fetch à la sidtexter, eller Worker-injektion). Avgränsning mot journal noterad. |
| **W2** | v5-publicering (ny kanaltyp i per-kanal-kompositionen) | Delar story-API-utredning med E2. Mallen är säljande ↔ V2-KUND-tonen |
| **R1** | **v6 spår ①-familjen** (Vardag/Resa!) | **D26 "Vardag/Resa"-modellen på hyllan är ramverket** (resekort, avresetröskel, ben) — R1 är dess ruttmotor-uppgradering. ABRP-API = extern kostnad, Stig kontaktar. Egen rejäl epic. |
| **R2** | **v6 spår ① scouting — direkt släkt** | Scout-domänen (byggd, ej prod) är lagringsplatsen; R2 = auto-FÖRSLAG (POI) bredvid manuella scout-platser. Karta+sol+väder finns redan. Overpass/OSM = gratis start, Places = bättre data m kostnad. |
| **R3** | **KROCKAR MED DALA-ARKITEKTURVALET** — samordna! | R3 kräver SKRIV till privat Google-konto — exakt samma gräns som Dala-valet (a)/(b) i `BESLUT-dala-assistent-v6.md` ("privata kalendrar rörs ALDRIG av skrivning" är dagens princip). Beslutet där bör fattas EN gång för båda. Speglingslogiken själv = enkel (samma mönster som calendar-sync:s jobbsynk). |

**Sammanfattning av naturlig ordning för diskussion:** B1/F1/F2 = små, v5-spåret tar dem · E-epiken = nästa stora publiceringsjobb, mycket grund redan lagd · W1 = liten och fristående, kan byggas tidigt · R-epiken = v6:s Vardag/Resa-familj (D26 + scouting), efter staging · R3+E5 = vänta in Dala-arkitekturbeslutet resp. röstkedjevalet så det byggs EN gång.
