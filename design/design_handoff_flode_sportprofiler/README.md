# Handoff Design → Code: Flöde & data-nav + sportprofiler (DPT2)

**Datum:** 5 juli 2026 · **Prototyp:** `Dalecarlia Photo Tools.dc.html` (bifogad i denna mapp, körbar direkt i webbläsare)
**Läst innan denna handoff:** er `UI-SYNK-2026-07.md` — inget nedan om-speccar det ni redan byggt (punkt 1–6 där). Er öppna lucka "Delvis publicerad" täcks i §10.

**Bärande princip:** matchen är navet — allt annat *refererar*, inget kopierar. Alla kopplingar är **frivilliga**: varje del (matcher, lag, fotojobb, gallring, SoMe, webb) fungerar fristående och i valfri ordning. Ingen del är grindvakt för en annan. Webb är större än Sport — landskap/porträtt/blogg berörs inte av något nedan.

---

## ⚠ Låsta ytor — upprepas för att inget ska backas

1. **Live-förhandsvisningen är den RIKTIGA server-renderade Horisont-bilden** (debounce ~500 ms, senaste lyckade rendering ligger kvar, "Renderar…"-badge, gren-CSS-ramen stängs av när riktig render visas). Prototypens box är en CSS-SKISS — en prototyp-begränsning, INTE en spec. Förenkla aldrig den riktiga förhandsvisningen.
2. **Gren-markering = färgad kant + mjuk glow, ALDRIG textetikett.** Palett fast: Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Ingen kant om gren okänd. Gäller preview-boxen, matchradens markör och Horisont-grafikens 18px-kant.
3. Horisont-grafikens liga-text (Saira 600, tracking .24em, `rgba(255,255,255,.66)`) och Skagen Hav-märket 80 % — orört.

---

## 1. Sportprofiler — resultatmodell per sport (störst datamodell-ändring)

Resultat/Halvtid/Målskyttar var fotbollslåsta. Nu styr en profil per sport fältmodellen överallt:

| Sport | Resultat | Mellanresultat | Målskyttar | Uppställning | Typ |
|---|---|---|---|---|---|
| Fotboll | Slutresultat (6–0) | Halvtid (3–0) | Ja | Startelva (11) | Lag |
| Handboll | Slutresultat (28–24) | Halvtid (14–11) | Ja | Startsju (7) | Lag |
| Innebandy | Slutresultat (4–1) | **Periodsiffror** (1–0, 2–1, 1–0) | Ja | Femma (5) | Lag |
| Volleyboll | **Resultat i set** (3–1) | **Setsiffror** (25–21, 23–25, …) | Nej | Startsexa (6) | Lag |
| Beachvolley | Resultat i set (2–0) | Setsiffror | Nej | Par (2) | Lag/par |
| Tennis | Resultat i set (2–1) | **Gamesiffror** (6–4, 3–6, 7–5) | Nej | — | **Individ** |

Referens i prototypen: `_sportProf(sport)` (en tabell, ~10 rader per sport).

**Lagring:** matchen bär oförändrat `result` + ett mellanresultat-fält (prototypen återanvänder nyckeln `halvtid` för alla sporter — döp gärna om till `mellan`/`score_detail` i skarpt schema) + `malskyttar` (bara scorer-sporter). **`.md`-frontmattern byter nyckel per sport:** `halvtid:` / `set:` / `perioder:` + `sport:`-fält.

**Profilen styr:**
- Slutsignal-formuläret (§3): etiketter, placeholders, målskyttar-fältet döljs för set-sporter.
- Live-mallens moment & fält: "Avspark"→"Matchstart"/"Nedsläpp", "Halvtid"→"Mellan set"/"Periodpaus", "Startelva"→profilens uppställningsnamn; momentet **Målgörare döljs** för set-sporter; Resultat-momentet visar setsiffror istället för målskyttar under siffran.
  ⚠ **OBS:** detta är ändringar i *fältmodellen och datan som skickas till Horisont-renderaren* (den behöver kunna rendera set-/periodsträngar där målskyttar-raden sitter idag). Förhandsvisnings-mekaniken (låst yta §1 ovan) ändras inte.
- Webb-formuläret i Innehåll (§4): samma etiketter/fält.
- Matchdaguttaget i Matcher: "Startelva" → profilens namn; för **Tennis (individ)** och **Beachvolley (par)** döljs hela trupp/uppställnings-blocket och ersätts av en info-rad ("Individuell sport — inga trupper…").
- Innebandy är tillagd som sport i alla sport-selects + färg `#6E8B5E`.

## 2. Matchraden som nav — statuschips

Överst i den expanderade matchraden: en chips-rad **Kalender · Gallrat · Live · SoMe · Webb**. Varje chip visar härledd status och hoppar till respektive del med matchen förvald.

Härledningar (allt beräknas, inget dubbellagras):
- **Kalender:** synk-flaggan ELLER att ett Sport-fotojobb med båda lagnamnen finns.
- **Gallrat:** antal bilder från gallringskörningen kopplad till matchen (`culled[date]` i prototypen).
- **Live/SoMe:** räknas ur Sparade material via match-referens (✓ publicerade, gul chip vid utkast).
- **Webb:** `siteUrl` satt → "Webb · publicerad"; webb-utkast finns → gul "Webb · utkast"; match spelad men webb saknas → **accent-knapp "Webb saknas · Skapa ›"** (hoppar till Innehåll med matchen förvald och fälten hämtade); ospelad match → neutral "Webb".

Chipsen är genvägar, inte steg — ingen ordning krävs. Referens: `navChips` i `renderVals`, `goFromMatch(i, dest)`.

## 3. Slutsignal — skriv resultatet en gång

Sektion i den expanderade matchraden (ihopfälld rubrikrad, expanderas på klick):
- Fält enligt sportprofilen: Resultat + mellanresultat (+ målskyttar för scorer-sporter). Förifylls från matchen om värden finns.
- Tre kryss (alla förvalda): **Resultat-story (Live)** · **SoMe-paket med ifylld bildtext** · **Webb-utkast (match-md)**.
- "Spara & skapa utkast": skriver värdena **på matchen** (enda källan), synkar Live-mallens fält, skapar valda utkast i Sparade material med status Utkast, sätter matchen som aktiv. **Inget publiceras.**
- ⚠ Utkasten skapas **utan bildval** — de ska öppnas med tomt bildval i respektive flik (er bildvals-persistens från UI-SYNK §3 behålls som den är; förenkla den inte).
- Referens: `slutForm`, `toggleSlut`, `slutSave`.

## 4. Innehåll → match: härledda fält med frivillig koppling

När en match är vald i "Match / event" (kopplingen är frivillig — fälten är annars helt fria):
- Info-rad överst: "Fälten följer *\<match\>* tills du skriver över dem" + knapp **"↺ Hämta allt"**.
- Varje matchfält har länk-status: **länkad** (länk-ikon, följer matchen) eller **egen text** (visas när användaren skrivit över; per-fält-knapp **"↺ Hämta från match"** återkopplar).
- Väljs en match i pickern hämtas ALLA fält (inkl. resultat/mellanresultat/målskyttar/galleri-URL) och alla länkar återställs.
- Fältuppsättning + etiketter följer sportprofilen (§1). Landskap/porträtt/blogg orörda.
- Referens: `cmsOwn`, `cmsSetOwn`, `cmsFetchField`, `cmsFetchAll`, `cmsMatchFields`.

## 5. SoMe-bildtext som mall (tokens)

- Bildtexten kan innehålla brickor: `{resultat}` `{halvtid|setsiffror|periodsiffror|gamesiffror}` `{målskyttar}` `{arena}` `{motståndare}` `{@lag}` `{#liga}` `{galleri}` `{datum}` `{tid}`.
- Upplöses från aktiv match + lagregistret (`@lag` = lagets IG-handle, `{#liga}` = tävlingsnamn normaliserat) — rättas matchdatan följer texten med.
- UI: "Infoga bricka"-chips under textrutan (listan sport-filtrerad) + en "Förhandsvisning"-ruta med upplöst text och källmärkning.
- **Vid publicering/utkast sparas den UPPLÖSTA texten** på materialet (historiken ska visa vad som faktiskt postades). Okända brickor lämnas orörda i texten.
- Facebook-varianten (utan #/@) räknas på den upplösta texten.
- Referens: `_resolveTokens`, `insertToken`, `someCaptionResolved`.

## 6. Bildkälla i Leverera — gallrat var som helst

Radioval överst: **Från Gallra-körning** (förval när en körning finns, visar namn + antal) eller **Egen mapp** (sökvägsfält — t.ex. gallrat i Photo Mechanic). Nedströms steg pekar alltid på en bildmapp; Gallra är aldrig ett krav. Referens: `imgSource`, `imgFolder`.

## 7. Importera spelschema (Matcher)

Knapp bredvid "+ Ny match" → panel med: källfält (liga/lag/URL), förhandslista med kryssrader där **dubbletter känns igen** ("finns redan", avkryssade, ej klickbara), toggle **"Skapa även fotojobb i kalendern (kategori Sport)"** (förvald), knapp "Importera N matcher". Importerade matcher + fotojobb skapas kopplade från början (fotojobbet härleder titel/tid/arena/liga från matchen). Referens: `importRows`, `runImport`.

## 8. Schemalagd publicering (Publicera)

Ny sektion ovanför Sparade material: kö per kommande match med toggle-rader —
"Nästa match · IG-inlägg" (dagen före 18:00) · "Uppställnings-grafik · IG Story" (1 h före, villkorad på att uppställning finns) · "Galleri-story" (när Pixieset-länk finns på matchen). Tider relativt avspark; villkorade poster skickas först när datat finns; status-pill "Väntar". Allt av/på per rad, manuell körning oförändrad. Referens: `sched`, `toggleSched`.

## 9. Kalenderjobb för matcher — härlett, inte dubblat

Matchens kalenderjobb ska härledas från matchen (titel, tid, arena, liga i note) — resultatet ska INTE längre skrivas in i jobbets note (idag ligger "· 6–0" där = tredje kopian). Redigering av matchdata uppdaterar jobbet vid nästa synk.

## 10. Delvis publicerad — stäng er flaggade lucka enligt prototypen

Er UI-SYNK §3: listan uppdaterar ingen post vid delvis misslyckad publicering. Bygg prototypens modell:
- Materialstatus `delvis` med röd/amber statustagg **"Delvis publicerad"**.
- Kanal-chips per kanal: `IG Story ✓ · IG-inlägg ✓ · Facebook ✗`.
- Knapp **"Försök igen — \<fallna kanaler\> ›"** som bara kör de fallna kanalerna; vid framgång → status Publicerad + historikpost "omförsök — Facebook".
- Publiceringshistorik per material (chip "N publiceringar ▾" → tidslinje med status + notis).
- Filterchip "Delvis" + räknare i sektionshuvudet ("· N delvis").
- Prototypen har seed-exempel (Hammarby-paketet) — klicka runt där.

## Regressrisker — gör INTE detta

- Beskriv inte prototypens CSS-preview som målbild; ändra inte den riktiga renderingens beteende (låst).
- Återinför ingen "DAM"-etikett; ändra inte gren-paletten.
- Gör inte refs obligatoriska — allt ska gå att skapa fristående och i förväg, och webb får aldrig kräva att SoMe/Gallra körts.
- Ta inte bort er bildvals-persistens i Sparade material (Slutsignal-utkast öppnas bara med tomt bildval).
