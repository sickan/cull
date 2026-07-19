# TOTAL BACKLOG — DPT2 · iOS · Webb

*Skapad 2026-07-16. ENDA SANNINGEN för allt öppet arbete — konsoliderar Stigs
båda listor (B-001…011 + BUG/FEAT/SPIKE 15–16 jul), alla öppna trådar ur
tidigare sessioner och dagens fynd. Prioriteras GEMENSAMT (görs härnäst);
`PLAN-nordea-friidrott.md` blir prio-vyn ovanpå den här.*

*Arbetssätt: agilt och iterativt — leverera värde löpande i små, testade,
robusta skivor. Vänta aldrig på att allt är klart.*

*17/7 kväll insynkat: **backlogg-överlämning v2** (Stigs punkt 1–20, IDs
`V2-xx` = punktnumren; källa `backlogg-overlamning-v2.md`) + **komplett
design-handoff för eventmodell-epiken/DPT v5 & iOS v2** (sektion C nedan,
källa `design_handoff_eventmodell_v5/`). Prio-vyn i `PLAN-nordea-friidrott.md`
uppdaterad till v4.*

**VECKOPRIO (Stig 18/7 kväll): SM-PAKETET ✅ KOMPLETT 18/7** — CULL-02 sportneutral gallring ✅ + M18-9 hemresan ✅ (+ bifynd CULL-04 behåll-valet ✅). **B-012 skiva 1+2 ✅ samma kväll** (skiva 3 = skarpkörning m Z8, Stigs recept §8). Nästa: klockmodulen skarptest → B-012 skiva 3 → §11 (§10 helt klar).

**KVÄLLENS SLUT 19/7 00:5x — allt committat+pushat i alla tre repon.** Utöver ovan: §10 skiva 3 (v36) · kategorifacit Sport/Landskap/Människor/Film + underkategorier (v37) · BUG-DEPLOY-01 (byggfelet var CF:s byggkö, sajten omkörd och live) · kopiera-knappar för Claude-texterna i Publicera. **Stigs kö:** DPT2-omstart (plockar v37) · verifiera ⌘C-vägen i kopiera-knapparna (bara fallbacken är bevisad) · B-012 skiva 3 (Z8-receptet) · M18-8 (vilken yta har gradienten?).

**VECKOPRIO (Stig 19/7 kväll — NY): ① Mästerskap · ② Lag & Utövare · ③ iOS v2 (ny startskärm + ny widget).** Underlaget är Designs
19/7-leverans (`Dalecarlia Photo Tools version 5 iOS version 2.zip`, insynkad i
`design_handoff_eventmodell_v5/`). Se **sektion C12** (D12-svaret: Mästerskap +
Lag & Utövare) och **sektion C-iOS** (widget/låsskärm, signatur, färgsystem,
jobbdetalj). Allt annat i C/V5 fortsätter som löpande merge.

**Stigs prio-signaler (16 jul):** ① buggar generellt först — särskilt att
Innehåll inte känns robust (= dubbletterna/publiceringskedjan) · ② iOS
trupp/startelvor inför FOTBOLLSHELGEN · ③ tennis under veckan · ④ B-003
röst→action är LÅG prio.

---

## A · DPT2 — buggar

| ID | Vad | Källa/anteckning |
|----|-----|------------------|
| BUG-03 | Färgklickar på Fotojobb uppdateras inte reaktivt (kräver flikbyte) | **KAN EJ REPRODUCERAS i mock** — hela kedjan verifierad färsk (D1 skrivs synkront, ingen klient-cache, laddaOm körs). Behöver Stigs exakta repro: vilken åtgärd + vilken färgklick |
| BUG-06 | Dubbletter i "Publicerat"-katalogen — ska spegla exakt det som är live | ✅ **LÖST 17/7** (`1c0abe7`): rot = id-trådning saknades; lokala dubbletter städade (29/29-spegel mot live) |
| BUG-07 | Dubbletter under "Utkast" — version vs bugg? Gruppera eller rensa | ✅ **LÖST 17/7** (`8ee7e37`): bugg, inte versioner — nytt utkast per redigeringssession; nu deterministiskt utkast-id per post + sanering vid inläsning + publicering städar postens alla utkast |
| BUG-08 | Dubbletter under Människor vid ompublicering | ✅ **LÖST 17/7** (`1c0abe7`): samma rot som BUG-10 (id-trådning) |
| BUG-10 | Slug-byte vid ompublicering lämnar föräldralösa rader i live-D1 | ✅ **LÖST 17/7** (`1c0abe7`): editorn trådar innehallId för ALLA typer + reconciling publish + radering propagerar; live-D1 engångsstädad (1:1-spegel verifierad) |
| HDA-a | Heldagsaktivitet-väljaren: synkade tävlingsjobb saknar tavling_id → inget gren·sport-suffix | Kräver ny länktabell (schema v29) för måttligt visningsvärde → föreslagen P2 |
| BUG-MP-01 | Matchpublicering sparade inte status/texter vid återbesök — man fick börja om | ✅ **LÖST 17/7 sen kväll** (`07fe18c`): materialet SPARADES men lästes aldrig tillbaka — laddaMatch återställer nu caption/kanaler/bildval+crop ur senaste materialraden, utkast sparar även banor, caption-läcka till färska matcher täppt, materialrad-klick öppnar matchen i Innehålls-fliken. Webbläsar-verifierad |
| BUG-CULL-01 | Modellvalet nådde aldrig gallringen (etikett vs typnyckel) | ✅ **LÖST 17/7** (`1ff5a07` main, pushad): `_modell_typ` normaliserar UI-etikett→typnyckel (täcker gamla sparade jobb), selecten skickar typnycklar, vald-men-oladdbar modell loggas högt ("⚠ kunde inte laddas"). **SKARPVERIFIERAD av Stig 17/7 kväll** (efter omstart): "Poängsatt med modell (arkiv)" i loggen, urvalet skiljer 10/12 mot handsatta körningen på samma 117 bilder — modellen väljer på riktigt. Kvar (medvetet): Hybrid otränad (ger nu synlig ⚠-rad) + pkl_path pekar på gamla `~/.config/dpt/modeller/` (funkar, men skört — flytt vid tillfälle) |
| BUG-CULL-02 | Handsatt poängformel är **rent fotbollsspecifik** — tennis/friidrott/övrigt gallras med fel signaler | ✅ **LÖST 18/7 kväll (SM-paketet).** `aktiva_signaler(profil, sport)` väljer signaluppsättning: lagsport (sportprofilens `squad`) = hela matchformeln (bit-identisk med arvet); individsport (friidrott/tennis/beachvolley) = bas+ögon+armar (jubel/ansträngning), boll/hemma/tröjnr/klunga/fas/väst/firande AV; brollop/portratt = bas+ögon (1× vikt); landskap = bara skärpa/exp/estetik. Profil+sport rundresar via `cull_jobb.vikter`-JSON (ingen migrering); `starta_cull` slår upp matchens sport. Vikterna i sig orörda (frysta). SM-redo: friidrottsgallring använder inte längre bollsignaler |
| BUG-DEPLOY-01 | "Bygget misslyckades" utan orsak (Stigs publicering natten 18/7, Malmö FF–Bröndby) | ✅ **LÖST 19/7** (dpt `8956053` + sajt `bf0e565`, worker deployad): roten var **Cloudflares egen byggkö** — fas `initialize` dog efter 4 ms med "Failed: unable to submit build job", INTE vår kod/data (lokalt bygge grönt, 14 andra byggen samma dygn OK). Omkörd via Pages retry-API → live, matchsidan verifierad (1–1, Träningsmatch). Statusremsan skiljer nu infrafel ("Cloudflare kunde inte starta bygget — försök igen") från riktiga byggfel (fas + sista loggraden, hela i title); mockläget kan spela upp båda via `?deployfel=infra\|build` |
| BUG-CULL-04 | §9-Gallra-panelens **behåll-val nådde aldrig backend** — panelen skickar `behall`/`enhet`, `_gallring_av_config` läste `behall_varde`/`behall_enhet` → varje körning föll tyst till 10 %-defaulten (dagens 2250→225 = exakt 10 %). Samma nyckelmiss för bevaka-numren (`nummer`-kommasträng → hade blivit TECKENmängd) | ✅ **LÖST 18/7 kväll** i samma pass: båda nyckeluppsättningarna tas emot + `_bevaka_av` parsar kommasträngen. Hittad under CULL-02-trådningen |
| BUG-CULL-03 | Gallra **hänger vid upprepad körning** (fastnar på "5% Laddar modeller…", 3:e körningen i rad) | **EJ REPRODUCERAD — hypotes:** varje cull startar en FRÄSCH `dpt2.worker`-subprocess som laddar hela ML-stacken (YOLO+MediaPipe+NIMA+CLIP på MPS) från grunden; ingen varm återanvändning/cache mellan körningar → MPS/Metal-minne hinner ej frigöras → häng/OOM vid upprepade laddningar. INTE "Din smak"-specifik (modellen laddas ändå aldrig, CULL-01). Jfr minnesnot om PyObjC/Vision-OOM. Behöver repro + ev. modell-warmup/återanvändning. Clearcut/MediaPipe-`W0000`/`E0000`-raderna = ofarligt Google-telemetri-brus |

## B · DPT2 — features/changes

| ID | Vad | Anteckning |
|----|-----|-----------|
| FEAT-13 | Purge/spegling av bygg-repot före publicering | ✅ **KLAR 17/7** (`1c0abe7`): reconciling publish per typ (skyddsvakt mot tom lokal DB) + radera_innehall propagerar till live |
| FEAT-09 | Auto-status efter publicering (polla → realtid, bort med manuella "Kolla status") | ✅ **KLAR 17/7** (`3972fe8`): auto-poll var 10:e sek efter publicering — bygger-puls → Live/Fel per D9 §3, Kolla status-knappen borta |
| FEAT-12 | Statusfärger + fasa ut utkastknappen (D9) | ✅ **HELT KLAR 18/7**: skiva 1 (`0e04977`) + skiva 2 fel-raden (`033e251`) + Sport-vyns kort (`7e7ca18`: hörnbåge i radens statusfärg + statusord i metaraden, fel-röd ram) |
| FEAT-08 | Avpublicera match/tävling från DPT2 | Raderaflöde finns för vissa typer — utöka |
| FEAT-07 | Varningsmodal vid radering av länkade objekt | |
| FEAT-01 | Drag-n-drop för bilder (Innehåll, särskilt galleri) | |
| FEAT-03 | Rich text-editor i ackrediteringsmallen (format + klickbara länkar) | |
| FEAT-02 | "Featured"-markering → prio på startsidan | → **D7** (design först) |
| FEAT-04 | Större färgklickar på jobbkorten | Småputs, code direkt |
| FEAT-06 | Skiljelinje i dolt jobbs färg vid sportfilter | Småputs |
| FEAT-10 | Galleri: sökvägs-UI (mindre typsnitt, `…/`-trunkering, filnamn ovanför) | Småputs |
| FEAT-11 | Kopiera mappsökväg-knapp i galleriet | Småputs |
| B-004 | Enhetligt skapa/ändra-mönster (fotojobb/matcher/lag/liga) | Absorberar B-005 ("Ny" utan ändring), #26, FEAT-07-mönstret |
| T-auto | Turnerings-autospar (tennis fas 3-rest) | Tennis-minnet |
| SP-pers | Snabbplock: persist urval per jobb | Ej kritiskt |
| SPORT-ORD | **Startmomentets ord per sport** (Stig 18/7): heter inte alltid "Avspark" — fotboll Avspark · handboll **Avkast** (✅ rättad 18/7, låg fel som Avspark) · innebandy Nedsläpp · tennis/volleyboll/beachvolley Matchstart · friidrott Start. Bors i `sportprofil.start_moment` och följer med matchpaketet → overlay + appens momentknappar. **Vid NY sport: sätt rätt startord i profilen direkt** (t.ex. ishockey Nedsläpp, löpning/lopp Starttid) | Princip, inte öppen bugg — profilen är enda källan |
| IPTC | Leverera fas 3: IPTC-bildtexter | Sparad sedan tidigare |
| C-försl | Beslut om C-förslagen (design/C-FORSLAG.md) | Stig-beslut |
| FEAT-14 | **EPIC: Ackrediteringssvar → DPT2** (svarsmail blir förslag Beviljad/Nekad + notering i appen) | Handoff §8 senare-fas; skivor nedan |
| V2-01 | Versionsvisning i ALLA appar (bokstaverat namn synligt + tekniskt byggnr under Om/Inställningar) | ✅ **KLAR 19/7** (dpt `537d69d` DPT5 · ios `d0be161` v2 — "plisten som aldrig lyssnade"). Sajten kvar |
| V2-02 | Väderväxling "där jag är" ↔ "dit jag ska" | ✅ **KLAR 18/7** (ios `d5d6ac0`, INSTALLERAD): tap på väderremsan växlar GPS ↔ arenan (nästa match/deltillfälle), samma tidsspann; "DIT JAG SKA"-etikett + växlingspil. Destinationsväder vid deltillfälle (V5 §4) fanns redan i cirkeln (arena + deltillfälletid) |
| V2-10 | Leveranskrav per uppdragsgivare sparas + visas i publiceringsflödet (ex CEV: 30 JPG, 2500×1500, ≤7 MB, efter set 1) | v2 §10 |
| V2-12 | Utrustningspackning: packmallar per eventtyp → packlista vid planering | v2 §12 · matas av V2-06-noteringar |
| V2-13 | Publiceringsstatistik: vad publicerats var, per match/event och kanal (underlag åt klubbar/sponsorer) | v2 §13 · bygger naturligt på V5 §10 publiceringskö |
| V2-17 | **EPIC: Matchlathund** — Claude-genererad matchplan (betydelse/tabelläge, spelare att följa, praktiskt, foto-inställningar ur väder, arenan/solen). Läsbar i iOS på matchdagen, PDF-export offline, skicka till mejl | v2 §17 · underlag: matchdata + väder (V2-02) + packmallar (V2-12) + egna arenanoteringar (V2-06) |
| FEAT-15 | **Hämta uppladdade original i DPT2** — Mac-sidan av kort→telefon→moln-bryggan (Stig-beslut 18/7): DPT2 listar originalen på molnets privata /api/original-yta per grupp/match och hämtar hem dem ("bilderna väntar när du kommer hem"), så appens Ladda upp-knapp blir en riktig brygga i stället för ren backup | ✅ **KLAR 18/7** (dpt `8907798` + worker `4403e0b` DEPLOYAD): workern fick list/hämta/städa-rutter (auth, streamad GET), DPT2-tjänst `original_synk` + "Från telefonen"-kort i Gallra (hämta → auto-källmapp; städa molnet-kryss, tas bort först efter verifierad hemkomst; idempotent omkörning). 13 nya tester (668 gröna), skarpverifierad mot riktiga NEF:er i molnet |

### EPIC V2-KUND · Eventpublicering, kundgodkännande & kundregister (v2 §3 + §14 + §7)

*Hänger ihop som ett spår — och förutsätter V5-kategoriregistret + `some`-flaggan
(sektion C §10) för Människor-publicering.*

- **V2-03 Eventpublicering + kundgodkännande:** tre faser (före/under/efter) för
  bröllop/student/porträtt m.m. Godkännandeformulär (motiv · tid/plats · namn ·
  kanaler) via unik länk per event → svaret sparas på eventet och styr vad
  publiceringsflödet tillåter. Autogenererat kundmejl per eventtyp (varm
  inledning, kontakt, användningsrätt + formulärlänk, Pixieset-leveransinfo).
  **Teknik:** kräver publik endpoint + lagring för formulärsvar —
  content-sync-workermönstret, till skillnad från övriga DPT2.
- **V2-14 Kundregister-light:** per kund samla event, godkännandeformulär,
  fakturanr/status, gallerilänk. "Litet CRM utan att bli ett."
- **V2-07 SpeedLedger:** inget öppet API (verifierat juli 2026). Grundlösning:
  fält för fakturanr per betaluppdrag + statusflagga (ej fakturerad/fakturerad/
  betald), manuellt. Ev. tillägg: CSV-export av ny kund i SpeedLedgers
  kundregisterformat. SIE4-omvänd matchning = överkurs.

### EPIC FEAT-14 · Ackrediteringssvar in i DPT2

*Bakgrund 17/7: första skarpa utskicket (MFF–Bröndby) besvarades av MFF;
status+notering registrerades manuellt i db. Det steget ska bli en funktion.
Vald väg (resonerad 17/7): Gmail-etikett som "peka ut"-gest + trådspårning —
INTE Apps Script-add-on (för mycket ceremoni för enanvändarbruk).*

1. ~~**Skiva 1 — trådspårning vid utskick**~~ ✅ **KLAR 18/7** (worker
   `9f9e623` DEPLOYAD + dpt `8388de6`): /api/mail/send returnerar `threadId`,
   schema v33 `ackreditering.thread_id` sätts vid utskick. Svar-i-tråd kan nu
   hittas utan gest (skiva 2).
2. **Skiva 2 — läsväg i workern:** scope `gmail.readonly` (kräver om-auth,
   Stig-steg) + endpoint som samlar (a) nya meddelanden i kända trådar,
   (b) mail med etiketten **DPT2-ackr** (fristående svar = Stigs gest, funkar
   i mobil-Gmail). Logg över behandlade message-ids så inget föreslås två ggr.
3. **Skiva 3 — förslags-UI i DPT2:** badge i Fotojobb ("N ackrediteringssvar
   att granska") + förslagskort: kopplat jobb, föreslagen status, föreslagen
   notering — ALLTID godkänn-steg (samma princip som Generera-prompten),
   godkänn → `satt_ackreditering`.
4. **Skiva 4 — tolkningen:** Claude (befintlig nyckelväg, som Bildsvepet) får
   mailet + kandidatjobb (kommande Sport-jobb m status Begärd) → föreslår
   status/jobb/destillerad notering (ingång, uthämtningstid, legitimation…);
   regelbaserad fallback ("välkommen/bekräfta" vs "tyvärr") om API strular.
5. **Senare:** workerns poll → APNs-push till iOS-appen ("Svar från MFF —
   förslag: Beviljad") via befintlig push-infra.

*Öppet: etikettnamn (förslag `DPT2-ackr` så etiketter kan användas till fler
flöden). Alternativ väg om Google-scope ska hållas minimalt: Cloudflare Email
Routing (`ackr@dalecarliaphoto.se`) + Email Worker — noll nya Google-scopes
men ingen trådautomatik; dokumenterad som plan B.*

## C · V5 — Eventmodell-epiken + UX-lyftet (design-handoff INNE 17/7)

*Komplett handoff i `design_handoff_eventmodell_v5/`: `DATAMODELL v5.md`
(Liga + Event ersätter Tävling; nya register Individ + kategori/underkategori),
`HANDOFF.md` §1–7 (etapp 1) + `HANDOFF-etapp-2-4.md` §8–14 (UX-lyftet) +
5 mockups (`DPT v5.dc.html` m.fl.). **Egen branch, löpande merge** — varje
steg/§ mergas separat. Låsta funktioner får ej regreras: gren-paletten
(Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`, kant ej text) + Publicera→Live
visar riktiga server-renderade Horisont-bilden.*

| ID | Vad | Anteckning |
|----|-----|-----------|
| V5-A | **Steg A — fristående quick wins** | ✅ **KLAR 17/7** (gren `v5-eventmodell` `ca9a02e`, **FF-mergad till main + pushad**): målmappar per flöde (default i Inställningar-kort + per-körning-override i Leverera/Snabbplock, rör aldrig defaulten) + original utan overlay (`namn.jpg` + `namn-original.jpg` vid varje overlay-/kanalexport). 11 nya tester, 633 gröna, UI byggd + webbläsar-verifierad. Stig: DPT2-omstart (dist ombyggd) |
| V5-B | Steg B — datamodellen (DPT2-lagret) | ✅ **KLAR 17/7 sen kväll** (`7210b41` på grenen, **mergad till main `5a852e9`** + pushad): schema v31 — liga/event/individ/event_deltagare/kategori-registren, matchen liga_id+event_id, tavling kvar som skrivyta m spegling (samma id), migrering m backfill + Människor-kategoriseed. 11 tester (655 tot gröna), **dry-run-körd mot kopia av skarpa DB:n** (4 ligor + 6 event, 33/33 matchrefs konsistenta). Individhistorik HÄRLEDS (individ_historik). Stig: omstart migrerar v30→v31. Astro-collections kommer med V5-E; matchformulärets två dörrar + editorer = V5-C |
| V5-C | Steg C — Event-sektionen + På gång-logiken | **SKIVA 1 KLAR 17/7 sen kväll** (`31004d2`, mergad till main `1284449` + pushad, dist ombyggd): nav-post Event under Planera + "Lag & ligor"-rename, lista m typfärgade badges/status/filterchips, detaljvy m På gång-läge (Auto/Heldag/Matcher + invariant-text), Matcher-kort (koppla/koppla bort + okopplade), Grenar-kort, Deltagare-kort (individregistret m sök/skapa). 4 tester, webbläsar-verifierad. **SKIVA 1.5** (`cdc766e`): individ ⟂ gren-bron — Deltagare-kortet visar unionen m B-001:s gren-deltagare, sök hittar utövar-lagen, gren-chips skriver disciplin_deltagare (Stigs skarptest-fynd). **SKIVA 2 KLAR 17/7 natt** (`8bdc5d5`, mergad till main): schema v32 (tavling-typer + cup/varldscup/ovrigt, guardad rebuild, dry-run mot skarp kopia), egen event-editor (+Nytt/Redigera, alla fem typer), matchformulärets TVÅ DÖRRAR (Liga/Tävling + Event-combobox m skapa/rensa; event_id-nyckel vinner, COALESCE-skydd så dörren överlever omsparningar). 652 gröna. **SKIVA 3 KLAR 18/7** (`cc6a173` + sajt `4a7abf9`, mergad till main, Pages-deploy): På gång-AUTOMATIKEN (_pagang_auto: auto före→heldagskort/under→matcher + heldag/matcher-override; manuell kryssruta vinner ovanpå; panelen visar besluten m badge) + del_av-invarianten DPT2→pagang-md→sajtens kort ("Del av {event}" som eyebrow). 654 tester. **Kvar (rest):** ~~"efter→resultat"-kort~~ ✅ **KLAR 18/7** (dpt `0ffa092` + sajt `004c80c`): `_pagang_resultat` (fönster 7 dagar efter till-datum) → kategori Resultat-kort m länk till eventsidan, panelen visar dem överst m Visa-kryss (dold-flaggan speglas tavling→liga/event) | §2–3 |
| V5-D | Steg D — iOS v2 | **SKIVA 1 KLAR 18/7 natt** (ios `a1745bb` + dpt `26b221f`, mergade, appen INSTALLERAD): restid mot NÄSTA DELTILLFÄLLE — pågående heldagsevent efter 08:00 riktar Hem-hjälten mot nästa tidsatta match (HemLogik, ny Matchdag-case, "Del av {event}"-rad på hjälten OCH i matchlistans metarad; paketet bär event_id+del_av). 655+21 tester. **Skiva 2 ✅ KLAR 18/7** (ios `465640e`): Sikta-arket — deltillfällen (auto markerat) + eget klockslag (`Matchdag.egenTid`), AUTO/VALD-badge i glasarket, inaktuellt val faller tyst till auto. **EJ installerad** (telefonen otillgänglig — installeras vid hemkomst). **Kvar:** ★-bakgrundspotten (kräver bildkanal, delar loggor→R2-vägen) | §4 |
| V5-E | Steg E — hemsidans eventsida | **SKIVA 1 KLAR 18/7 natt** (sajt `73d6cb6` → Pages-deploy + dpt `d54a9d4`): sporteventsidan uppgraderad — PROGRAM per dag (spelade ur matchartiklar m resultat+"Se bilderna →", kommande ur pagang m tid+Kommande-chip, gren-stapel i låsta paletten), statusrad "Pågår · dag X av Y" ur pagang-perioden, "Del av {event}" på På gång-korten är nu LÄNK till eventsidan (del_av_slug). Byggd+verifierad (EL: fredag 12 juni · Litauen–Sverige · 0-3). **REST ✅ KLAR 18/7** (sajt `1f62fc9` + dpt `26e7863`): gren-filterchips (visas vid blandade grenar, DOM-filter m dagdöljning) · "Del av {event} →"-badge + rond i hero på matchARTIKELSIDAN (`_berika_matchkontext`: del_av/del_av_slug/rond ur matchraden) · fas-etikett per dag ur matchernas rond + "i dag"-markering. OBS: länken förutsätter att sporteventets titel = eventets namn (slug-join) | §7 |
| V5-UX | **Etapp 2–4 UX-lyftet**: **§10 SKIVA 1+2+3 KLARA 18/7** (kö `204aa6a` + momentkort kväll): momentkortet i Publicera (✓ ur some_material, nästa i accent, sportprofilens ord; Landskap/Människor/Film-mallar definierade) · **SKIVA 3 (`1c90ce8`, schema v36):** mallarna KOPPLADE — `moment_status(match_id, jobb_id, kategori)` ger jobbmall ur kategorin, some_material/publicera_material fick `jobb_id` (✓-status för icke-matchjobb), momentremsan syns i Fotojobb-kortet, Människors "Leverans klar" bara vid `some:true`-flagga. **KATEGORIFACIT (Stig 18/7 kväll, `520ddb5` schema v37):** kategorierna är **Sport · Landskap · Människor · Film** — Event/Övrigt var fel och går inte längre att välja (färgerna kvar för historiska jobb). **Människor har underkategorier** (Porträtt, Student, Bröllop m.fl.) i eget fält, lokal tabell `fotojobb_underkategori`, datalist-förslag + fritext som växer med Stigs ord; underkategorin delar momentmall. **Blogg** är en innehållstyp i Innehåll-panelen, inte ett fotojobb · kön — v35 `publiceras`-fält, schemafält vid Spara utkast, kön sorterar schemalagda överst m "Dags att publicera"-puls när tiden passerat (manuell påminnelse per handoffen; momentmallar per kategori = nästa skiva, kräver jobbkontext i panelen) · **§8 ✅ KLAR 18/7** (`8692312` main): "Aktivt jobb"-chip+remsa, "Efter jobb", "Publicera", Träna ur nav · **§9 RAM KLAR 18/7** (samma commit): stegindikator Mål→Kör→Granska, profilkort (4 profiler m signal-chips, förval ur jobbet, `profil` följer med cull-config åt CULL-02), Träna→Inställningar-rad (inbäddad panel). **§9-rest:** tyst träning kräver per-bild Behåll/Släng-UI i granskningen (finns ej ännu — egen skiva, hänger ihop m Leverera-urvalsvyn) · §10 momentmallar per kategori (Landskap: Ny serie/Platsen/Bakom kulisserna/Blogg-puff; Människor: Tjuvkik/Leverans klar ENDAST vid jobb-flagga `some:true`; Film: Ny film/Stillbilder/Bakom kameran) + publiceringskö m schemaläggning (`publiceras:`) · §11 Innehåll: "Att granska"-remsa + Film-typ i typ-naven · §13 ★ iOS-bakgrund flaggas i Leverera · §14 iOS Hem per jobbtyp (landskaps-/människojobb: blå/gyllene timmen, schema ur jobbet) | varje § separat mergebar; §10 ↔ V2-13 statistik · §10 some-flaggan ↔ V2-KUND · kategorifärger topp: Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0` |

## C19 · Levererat 19/7 (v5 §8 + D11/D11b) — grunden C12 vilar på

*Skrevs in 19/7 kväll. Detta ÄR byggt och SM-testat — behandla som facit när
D12/iOS v2 byggs ovanpå.*

| ID | Vad | Commit |
|----|-----|--------|
| V5-§8 | **Pass på gren + härlett dagsprogram** (schema **v38**) — gren bär `pass[{namn,datum,tid,plats}]`, programmet härleds (pass + tidsatta matcher + hållpunkter), aldrig lagrat | dpt `b8dd96b` |
| V5-§8-S2/S3 | Läs in tidsprogram + startlista via inklistring · Program-kortet i Event (tidslinje per dag, vem + handle) | `55c6ef0` · `fc87c87` |
| V5-§8-S4/PDF | Arrangörens PDF med kolumnlayout + klass på grenen (schema **v39**) · programmet med vem+handle ut i paketen | `bdd9eb1` · `a2c1b0a` |
| V5-§8-S5 | **iOS läser programmet** — Dagens deltillfällen med vem + handle | ios `46edbbd` (+ fix `9386fb2` programmet läckte till ALLA jobb) |
| C8–C10 | **Import-unifiering "Läs in…"** + **Utövare-registret** (schema **v40**) — en väg in, dokumenttypsgissning, avvikelsegranskning | dpt `c2fc84d` |
| D11b §1 | "Event" ur alla UI-strängar → **Tävlingar** · EN tävlings-editor (Tävlingar äger ligor, *Lag & ligor* → **Lag**) | `e3eefd3` · `6fde86c` |
| D11b §2 | **Utövare-sida** + nav-post | `4398b0b` |
| D11b §4 | **Synk-märket** ("Skicka till telefonen" borta) + **⌘K global sökning** | `9ffe62a` |
| D11 E13–E18 | **Fältflödet i iOS** — pass → vinnare → resultat → SoMe ur Jobbdetalj; CTA formas efter grentyp | ios `8041974`, `7ff73ac`, build 8→9 `a29944b` |
| iOS-fav | **Favoritgrenar på mobilen** — fokuserar Dagens deltillfällen per sport, nycklat på gren+klass | ios `3c01157`, `e6cbcf1` |
| M18-8 | Lagbrickan åt upp märket — roten var **masken**, inte gradienten | `3aec9c8` |
| V2-01 | Versionsvisning DPT5 (en sanning, bokstaverad) + iOS v2 | `537d69d` · ios `d0be161` |
| Fixar | "100m"≠"100 m" → en gren · startlistan satte ingen klass · färskare källa rättar stavning · dam-deltagare på herr-gren flyttas · ligamatcher bar hela seriesäsongen som dagsprogram · PDF-läsningen säger vad som är fel | `a9f4959` `55042a1` `9c4c8b6` `3f5bf8c` `5b0a91c` |

## C12 · PRIO ① + ② — Mästerskap · Lag & Utövare (Design-svar D12, 19/7)

*Källa: `design_handoff_eventmodell_v5/HANDOFF-D12-SVAR-tavlingar-storskala.md`
+ mockups `DPT v5 - Mästerskap.dc.html`, `DPT v5 - Lag & Utövare.dc.html`,
`DPT v5 - Utövare.dc.html`. **Design är tydlig: ingen datamodell-ändring krävs
— ren presentation/UX.** Bakgrund: Friidrotts-SM 2026 = 79 grenar · 845 starter
· 37 deltillfällen/dag · 100 m har 47 deltagare → dagens detaljvy kollapsar.*

**Grundgreppet:** en tävling renderas efter **skala, inte typ**. Liten (≤ ~8
grenar) → befintlig kort-stapel, rör den inte. Stort mästerskap/flergrens →
**arbetsyta** (grenar som navigator → gren-detalj). Skidåkning faller in i
samma form. Tröskeln är en gräns i koden, inget val Stig gör.

| ID | Vad | Anteckning |
|----|-----|-----------|
| M-1 | **Registersammanslagning + delad editor** (`DPT v5 - Lag & Utövare`) — ETT register, *Slag*-växel Utövare\|Lag som byter formulär. **Utövare:** Porträtt · Namn · Klubb · Klass (personens egen) · @-konto · Anteckning. **Lag:** Lagnamn · Förening · Ställfärger · Trupp · Arkivera (matchspråket hör hemma HÄR). **BORT från utövaren** (mockupen visar dem överstrukna): profilfärg · ställfärger · "Arkiverat — matcher påverkas inte" · flat tävling-chip | ✅ **KLAR 19/7** (`ca734b2`, **schema v41** — EJ pushad, KRÄVER DPT2-OMSTART): slaget bor redan i `lag.kind`, ingen ny datamodell utöver additiv nullable `lag.anteckning`. Registerlistan: sök på namn ELLER klubb, filterchips Alla/Utövare/Lag m antal (ersätter gren-filtret), utövar-avatar m klass-färgkant, lag-avatar m 50/50-gradient — `Lagbricka.svelte` bär båda via nya props `form`/`farg2`/`kant`. **Klass-textetiketten borta** (`.grenlbl2` + `GREN_ETIKETT`), ingen kant vid okänd klass. 11 nya tester, 863 gröna. **`profilfarg` går ej längre att redigera men kolumnen + värdena är kvar som fallback för lagfärg i Matcher/Gallra/ResultatRemsa** — inget gick sönder |
| M-2 | **Gren-först deltagarkoppling** — `disciplin_deltagare` blir ENDA kopplingen person↔tävling. Sektionen *"Tävlar i"* på utövaren är **härledd** (gren m egen färgkant + "Del av {tävling}") och driver Kommande starter. Den flata tävling-chippen tas bort | ✅ **KLAR 19/7** (`bc88fc4`, 876 gröna): **EN härledning** — `utovare_discipliner()` ur `disciplin_deltagare`, och `utovare_starter()` (Kommande starter) bygger nu på SAMMA väg → de två vyerna kan inte längre divergera. Nya `utovare_grenar()` + `gren_kandidater()`. Raden bärs av **grenens** klassfärg, aldrig personens — en dam kopplad till herr-gren ger teal rad (regressionstest); ingen kant vid okänd klass. **Bifynd åtgärdat:** `spara_disciplin` tappade `gren` på vägen till store → en handskapad grens klass kunde bara sättas av importen. Hemsida-fältet återställt separat (`d28e5dc`) — det ströks av misstag i M-1, D12 pekar ut exakt fyra fält |
| M-3 | **Mästerskaps-arbetsytan, läge *Grenar & deltagare*** — vänster navigator (322 px) m fri sök + växlingsbar **GRUPPERA: Klass (default) · Typ (löp/hopp/kast/mångkamp) · Dag** + **★-filter**. Gren-rad: klass-färgkant · namn · kat-chip · `Typ · dag N` · deltagarantal · ★. Höger gren-detalj: rubrik m klasstext + "Del av {tävling}", **PASS-kort** (passtyp · tid · antal, `+ Pass`), **DELTAGARE I {gren}** m sök "Lägg till utövare ur registret", startnummer, @-status per rad (`@handle` i accent / dashed "saknar @"), `N av M har @`, "Visa alla N" | ✅ **KLAR 19/7** (`f5969cc`, 903 gröna, **schema orört på v42**): ny modul `src/dpt2/motorer/masterskap.py` bär alla härledningar — kat, typgrupper, dagnummer och @-status räknas fram ur `disciplin` + `pass` + `disciplin_deltagare` som de redan ser ut. **Kat lyfts ur grennamnet som neutral grå textchip och färgsätts aldrig**; okänd klass → egen grupp "Utan klass", ingen kant. **Sidoeffekt värd att veta:** inläsningen (C8–C10) bröts ut till `lib/LasInTavling.svelte` — annars hade arbetsytan och kort-stapeln fått var sin kopia av 180 rader. Beteendet oförändrat. **Startnummer på deltagarraden finns inte i modellen (v42)** — fältet bärs men hittas aldrig på; kolumnen visas bara när värdet finns |
| M-4 | **Mästerskaps-arbetsytan, läge *Program*** — dagflikar (Dag 1/2/3) + **tidsaxel** (tid i 56 px vänsterkolumn, prick i klassfärg, kort m 3 px klass-vänsterkant) i stället för platt 37-radslista + toggle **★ Bara favoritgrenar** | ✅ **KLAR 19/7** (`0a9461f`, 917 gröna, **schema orört på v42**): härledningarna i M-3:s modul (`programrad`/`tidsaxel`/`programlead`/`dagflikar`), och `hamta_masterskap_program` läser den **befintliga och enda** `store.program()` (V5 §8) — ingen andra programhärledning. ★-filtret **delas med läge A** (M-7:s `disciplin.favorit`) så stjärnmärkning i navigatorn slår igenom i programmet direkt. **Bifynd åtgärdat:** M-3:s navigator räknade "dag N" bara ur PASS, medan programmet också bär matcher och hållpunkter → en hållpunkt på en passlös dag hade gett de två lägena olika dagnummer. Dagarna härleds nu i EN datumfråga (`app._tavlingsdagar`) som båda lägena läser, med regressionstest på exakt det fallet |
| M-5 | **Adaptiv växling liten↔stor** — tröskellogik i koden | ⚠️ **PROVISORIUM PÅ PLATS** (M-3): `masterskap.ARBETSYTA_MIN_GRENAR = 9`, ETT ställe, kommenterad som Stigs obesvarade beslut (Designs "liten = ≤ ~8 grenar"). Kort-stapeln för små tävlingar orörd — verifierat att EuroVolley fortfarande ritas som kort. **Ditt svar = enradsändring där.** ⛔ Kvarstår: grenantal? deltagarantal? eller alltid arbetsyta för typ Mästerskap? |
| M-6 | **Utövarsidan omtänkt** (`DPT v5 - Utövare`) — profil m klass-färgkant + **inline @-fält** ("sätts en gång — fältflödet taggar automatiskt sen", ✓ *bär till fältet*), fyra nyckeltal (starter · tävlingar · bilder · persrekord i accent), **Kommande starter** (härledda pass), **Historik** (härledd tidslinje, **medalj = accent-prick + accent-resultat**), **Bilder & jobb** (3-kolumnsgrid, klick → jobbet), "Nås ifrån"-pills | Sidan FINNS (`4398b0b`) men byggdes före D12 → omtag ihop m M-1/M-2. **Datakrav:** `disciplin_deltagare` måste bära **resultat per start** + medaljflagga, `tavling.ort/datum`; persrekord härleds; bildtaggning person→bild→jobb krävs för Bilder & jobb |
| M-7 | **Favoritmarkering per gren behöver persistens** (per tävling) — bara klient-state i mockupen, men M-3 och M-4 vilar båda på den | ✅ **KLAR 19/7** (`59b2d4a`, **schema v42**, 884 gröna): **nyckelfyndet — `disciplin`-raden är sedan v39 redan unik per tävling + grennamn + klass**, så en flagga på raden ger BÅDE per-tävling-scopning och dam/herr-separationen gratis ("Diskus dam" ≠ "Diskus herr"). Additiv `disciplin.favorit`, ingen ny tabell. ★ per gren-rad + "★ N"-filter i Grenar-kortet. **Mobilen (`FavoritGrenar.swift`) nycklar `"gren\|klass"` per SPORT i UserDefaults, desktop på disciplin-id per TÄVLING** — modellerna är förenliga, en framtida synk kan mappa utan datamodelländring; skillnaden per sport ↔ per tävling är det enda som måste lösas den dagen |
| M-8 | Nav-varianten: mockuparna spretar — `Lag & Utövare` som EN post (D12-filerna) vs `Utövare` + `Lag & ligor` (Utövare-filen). ⌘K + synk-märke ska samexistera i headern | ⛔ Stig-beslut, litet |
| M-9 | Läs in-granskningen i samma skal-tänk (gruppera avvikelser per gren/klass, inte 845 rader) | Design: "utanför denna leverans, noteras". ⛔ Stig: nu eller vid nästa stora inläsning? |
| M-11 | **`fotojobb.tavling_id` — D11b §3, "den viktigaste"** (ENDA obyggda punkten i D11b). Idag kopplas fotojobb↔tävling av en **tyst namnjämförelse** → tappas så fort Stig byter namn på kalenderposten. Lägg nullable-fältet, sätt **automatiskt på datum + namn-match** vid jobbskapande, men **synligt och rättbart** ("Del av {tävling}" m byt-knapp). Aldrig implicit-only. När fältet finns slutar iOS gissa via titeln | Ligger utanför D12 men blockerar "Del av"-kedjan i iOS |
| M-10 | **iOS-delta ur D12** (byggt i `DPT iOS v2 - Jobbdetalj`): bort med **"@ N"-chippet** i Dagens deltillfällen · **varje gren tappbar → sheet m "Skapa SoMe"** (→ fältflödet) + "Öppna passet", även utan startlista/handle · klass som färgkant per rad · hållpunkter har ingen SoMe-väg | ✅ **KLAR 19/7** (ios `b09bd2c`) — byggd ihop med **J-2**, se den raden |

**Låsta invarianter bekräftade:** klass-färgkant utan textetikett (Dam `#8E5A86`
· Herr `#3E7C87` · Mixed `#6E8757`) · "Del av {tävling}" aldrig lösryckt ·
programmet härlett aldrig lagrat · eventtyp = etikett utan egen färg · max två
mättade färger per kort · DPT2:s look & feel i övrigt orörd.

## C-iOS · PRIO ③ — iOS v2: ny startskärm + ny widget (Design-svar 19/7)

*Källa: `HANDOFF-widget-lasskarm.md` (svar på B-009) + `HANDOFF-00-Helhet.md`
+ mockups `DPT iOS v2 - Widget & Låsskärm` · `- Event` (startskärmen) ·
`- Jobbdetalj` · `- Signatur` · `- Färgsystem` · `- Fältflöde`.*

**Design säger rakt ut: ytan Code byggde (B-009) är RÄTT.** Sex familjer, en
snapshot, statiskt — allt behålls. Nedan är beslut på de sex öppna frågorna +
två saker Code inte frågade om. **Fältflödet (F-skivorna i Designs förslag) är
redan BYGGT 19/7** (ios `8041974`, `7ff73ac`, build 9) — bocka av det.

**Två trådar binder ihop allt:** (1) **signatur-sigillet** — hästmärket i
graverad ring där nedräkningen till avgång ritas som orange båge; samma märke på
splash, hemskärm, låsskärm, widget, jobbdetalj och som "levererad"-stämpel.
(2) **färgsystemet** — varje färg får en roll, en zon, en form.

### C-iOS-W · Widgeten (B-009 fortsättning)

| ID | Vad | Beroende |
|----|-----|----------|
| W-1 | **Q1: `accessoryCircular` → nedräkningsgauge med sigillet** | ✅ **KLAR 19/7** (ios `d989d14`, 113 tester gröna — EJ pushad, EJ installerad): ny fristående komponent `Widgets/Sigill.swift` (`SigillNedrakning`) så S-1 kan lyfta ut den till splash/hem/jobbdetalj. **`ProgressView(timerInterval:)` INTE `Gauge(value:)`** — en gauge räknas ut en gång per tidslinjepost och hade stått stilla mellan widgetens uppvakningar. Nedräkningsfönster **6 h** m brytpunkt i tidslinjen (utan tak står ringen stilla när avgången ligger dygn bort). Utan framtida avgång → märket + klockslag, aldrig tom yta. Hästmärket i egen `Widgets/WidgetAssets.xcassets` (app-targetens katalog nås ej från extensionen), template-renderat → låsskärmens mono-invariant håller |
| W-2 | **Q2: jobbnära väder** `−1h / START / +2h` på widgeten | ✅ **KLAR 19/7** (samma commit): `VaderService.hamtaPunkter(lat:lon:tider:)` ny; `hamtaSerie(dag:)` delegerar till den och **behåller 08–20 — HemView-filen är orörd** (verifierat). Heldag ankrar mitt på dagen (00:00 säger inget om vädret). **Etiketterna härleds vid LÄSNING** (`JobbSnapshot.vaderRemsa()`), inte i kontraktet → inga nya snapshotfält, och ett snapshot från äldre app faller tillbaka på klockslag i stället för att etiketteras "+9 h" (regressionstest finns) |
| W-3 | **Q5 tomläge + okänd arena + färskhetsstämpel.** Tomt = dagens soltider + senaste leverans ("EuroVolley levererad 22/7"), stigande detalj small→large — aldrig bara "Inget bokat". Okänd arena: raderna får INTE försvinna tyst → "Plats ej satt — lägg till i DPT för restid & väder" + dämpad platshållare. Färskhet: dimningen till 55–60 % räcker inte, lägg **`IDAG 07:01`** i dagsraden (blekt kort utan tid läses som "fel", inte "gammalt") | 2 nya snapshotfält: `senasteLeverans`, `platsOkand` |
| W-4 | **Q4: large omflödad till 3 DÄREFTER-rader** | ✅ **KLAR 19/7** (ios `37817a0`, 117 tester gröna): väder + sol delar EN rad (`vaderOchSol`/`solInnehall`), `prefix(2)`→`prefix(3)` — raderna var redan rika (kategoriprick + titel + plats + datum), skrivarsidan bar redan `prefix(4)` så ingen datamodell rördes. **Två klickmål bevarade** som syskon i HStacken (`dpt://vader` + `dpt://sol` — nästlade `Link` funkar inte i WidgetKit). ↑/↓-pilarna behålls bara när EN tid finns; med båda läses ordningen upp→ned ur raden. Kantfall: utan soltider ritas ingen solyta, utan väderremsa vänsterställs solen |
| W-5 | **Q6: ljus/mörk som VAL** — `AppIntentConfiguration` enum "Utseende: Ljust / DPT-mörk", **standard = Ljust (A)**, två renderingsgrenar delad layout. Behåll SF Pro, ingen egen font | intent-ändring. ⚠️ Se öppen punkt (b) nedan |
| W-6 | **Q3: LA-medvetenhet** — när Live Activityns FÖRE-kort är aktivt för jobbet ska `accessoryRectangular` **hoppa fram till nästa jobb** ("NÄSTA"). En yta = ett budskap. Ingen extension-till-extension-kommunikation | nytt fält `liveActivityAktivFor: <jobbId?>` i App Group-snapshoten |
| W-7 | **StandBy-yta** (liggande, laddar): hästen som vattenmärke, `ÅK SENAST OM 1:02` i orange, avgång+restid, dag/ort/titel/arena/temp/soluppgång | följer W-1 |
| W-8 | **Kategorifärg → delad App Group-resurs** (plist eller genererad Swift ur samma källa som `Theme.swift`) — de duplicerade Hav/Sol/Rosé/Film-värdena driftar isär när paletten ändras | ⚠️ klargör hex-konflikten först (punkt a) |

*Oförändrat/bekräftat: sex familjer · en snapshot · statiskt · klickmålstabellen
(large/medium multi-target, small + låsskärm single → Jobb) · "dagen först" ·
"heldag = bara dagen" · låsskärm monokrom utan kategorifärg · hemskärm ljus.*

### C-iOS-F · Fältfynd 19/7 kväll (skarpt på Stigs telefon, jobb = Friidrotts-SM heldag)

| ID | Vad | Anteckning |
|----|-----|-----------|
| F-1 | **Widgeten stod tom under mästerskap** — inget ÅK SENAST-block, ingen nedräkning, ingen temperatur | ✅ **LÖST 19/7** (ios `6cb2bba`, 165 gröna, INSTALLERAD+PUSHAD): roten var `SnapshotSkrivare` rad ~57 — restid räknades bara `if !j.heldag`, så ett heldagsjobb fick ALDRIG `akSenast`. **Ett heldagsjobb har ingen egen klocka, men dess deltillfällen har det.** Härledningen bor nu i `HemLogik.nastaSikte(event:matcher:)` som BÅDE `HemView.nasta` och `SnapshotSkrivare` läser (den låg inlinad i vyn förut) — fjärde dubbleringen som städats bort denna omgång. Nytt optionellt snapshotfält `siktarPa`/`maltid`; siktets egen arena vinner över eventets (en gren kan ligga på annan plan). **Presentationsinvarianten orörd** — heldag visar fortfarande bara dagen; heldag UTAN tidsatta punkter beter sig exakt som förut |
| F-2 | **Cirkeln ritade grå placeholder-block + en båge** på låsskärmen | ✅ **LÖST 19/7** (samma commit): `placeholder(in:)` satte `akSenast = nu + 1 h` → nedräkningsfönster → en båge. WidgetKit renderar platshållaren med `.redacted(.placeholder)` så text/bild blir grå block — **men bågen redigeras INTE bort, för `ProgressView(timerInterval:)` ritar ur tiden, inte ur innehåll som går att gråmarkera.** Platshållaren bär ingen avgång längre. Dessutom skiljer sig `getSnapshot(in:)` nu från `placeholder(in:)` som den ska — exempelkortet visas bara i galleriet (`context.isPreview`); förut gav `DelatLager.las() ?? placeholder(...)` en påhittad match med påhittad restid när snapshotet inte gick att läsa. **Uteslutet hårt:** `HastOrange` finns i extensionens byggda `Assets.car` (verifierat m `assetutil`) — template-bilden var aldrig problemet |
| F-3 | **Soltiderna räknades för `Date()` i stället för jobbets dygn** — ett jobb fem dagar bort visade DAGENS soluppgång som om den vore arenans den dagen | ✅ **LÖST 19/7** (samma commit). Bifynd |
| F-5 | **Appen och widgeten var oense om SAMMA jobb** — appens hjälte räknade mot 24 juli 08:00 ("AVSPARK OM 5 dagar", "16° prognos kl 08:00", "åk senast 00:27") medan widgeten inte fick någon tid alls | ✅ **LÖST 20/7** (ios `69bcc05`, 170 gröna, INSTALLERAD+PUSHAD): W-5 delade *siktes*-härledningen men inte **klockslags-konventionen**. `HemView` rad ~90 gav heldag 08:00 (`bySettingHour: 8`, Spec #20 sedan 16/7), snapshoten satte `malTid = nil` för heldag utan tidsatta punkter. Nu: `HemLogik.heldagStart()` = konventionen på ETT ställe (`Matchdag.start` läser den), `HemLogik.malTid()` = tidsatt deltillfälle → heldagens 08:00 → inget datum. Presentationsinvarianten orörd |
| F-6 | **Appen och widgeten läser OLIKA objekt för samma verkliga händelse** | `HemView.kandidater` = `matcher.map(Matchdag.match)` + heldagsjobb. Hjälten sa "AVSPARK OM", vilket `toppText` bara ger när `m.heldag == false` → **appens hjälte är MATCHPAKETET** (en `Match` m avspark 08:00 + ANKOMST/UPPVÄRMNING/AVSPARK), **widgetens hjälte är `Jobb`-posten** m `heldag: true`. De konvergerar på 08:00 efter F-5, men modellerna är två. `Jobb.matchId` finns REDAN i snapshotet och skulle kunna ge widgeten matchens avspark direkt — egen post |
| SPORT-ORD-iOS | **Hem-hjälten säger "MATCHDAG" · "AVSPARK OM" · "Till matchen →" för ett FRIIDROTTSMÄSTERSKAP** | Tre hårdkodade konstanter i `HemView.swift`: `Matchdag.etikett` (.match), `toppText` (~rad 642), och knapptexten. Ska komma ur **sportprofilens `start_moment`** — friidrott = "Start", inte "Avspark" (se SPORT-ORD i sektion B). Samma familj som handbollens `Avkast`-fix 18/7. Upptäckt på skärmbild 19/7, EJ byggt |
| F-4 | ⛔ **ÖPPET: väderremsan är tom i widgeten** (soltiderna syns, vädret inte) | **Horisonthypotesen MOTBEVISAD:** MET svarar utmärkt för Uppsala 24 juli (fyra punkter 00/06/12/18 UTC, 12:00Z = 22,2° "cloudy", serien går till 29 juli), och workern (`content-sync/src/vader.ts`) matchar med `narmast()` — inte exakt tidsstämpel — så en förfrågan blir aldrig tom av tidsskäl. Att soltiderna syns BEVISAR att arenakoordinaten var känd (båda räknas i samma `if let p = arena`), alltså gjordes väderanropen och kom tillbaka tomma. **Kvar att skilja på: saknad API-nyckel i Keychain · nätfel vid skrivtillfället · KV-cache (TTL 2 h) fylld med nullar.** Går inte att avgöra utan Stigs nyckel. **Ingen fallback byggd som döljer att vädret saknas.** ⚠️ **Frestande att avskriva 20/7 — gör INTE det:** appens "16° prognos" bevisar bara att nyckeln finns NU, inte vid skrivtillfället. Snapshotet skrivs EN gång och fryser. **Kortet på telefonen 19/7 skrevs av en app FÖRE W-5** — bevisat av soltiderna: widgeten visade 04:02 · 21:50 = Uppsala den **19 juli**; den 24 juli är det 04:13 · 21:40 (uträknat ur repots `SolTid`). Soltiderna finns ⇒ `arena != nil` (båda räknas i samma `if let p = arena`) ⇒ arenan gick att slå upp, och den GAMLA koden hämtade väder ändå (ankare 12:00). Att båda nätanropen gav tomt medan den rena matematiken lyckades pekar på att `Keychain.read()`/nätet fallerade **just då**. **Verifieringssignal:** byter soltiderna till 04:13 · 21:40 har kortet skrivits om |

### C-iOS-H · Ny startskärm (hemskärmen/hjälten)

| ID | Vad | Beroende |
|----|-----|----------|
| H-1 | **Startskärmens nya uppbyggnad** (`DPT iOS v2 - Event`): sidhuvud m ordmärke + version + **synkstatus med tid** ("synkad 14:02") + litet sigill-märke · **eventbanner** (`EUROVOLLEY 2026 · DAG 3 AV 7`, arena, `Mästerskap · volleyboll · 21–27 aug`) · **HÄR I DAG**-väderremsa (fast 08/11/14/17/20 + gyllene timmen) · **NÄSTA DELTILLFÄLLE** (namn, "Del av {event} · kl X · väder vid arenan", `ÅK SENAST` + restid) · **Sikta på annan tid**-sheet | ✅ **KLAR 19/7** (ios `6b9429e`, 137 gröna): `Eventbanner.harled()` — dagsräknaren ger `nil` för endagsevent och utanför perioden (aldrig "DAG 0 AV 7"); sporten via ny `Programkalla.sportFor` med **samma kopplingsregel som programmet** (match_id först, annars namnet) så ett främmande paket inte kan läcka in sin sport. `SynkPill` bär tidsstämpel ("Synkad 14:02" / annan dag → "Synkad 18/7 14:02"), satt bara vid lyckad hämtning. HÄR I DAG-remsan **oförändrad** `hamtaSerie(dag:)` 08/11/14/17/20. Nästa deltillfälle: källbadge PROGRAM/MATCH/EGEN TID; utan känd restid står "–:–" + "restid okänd" i stället för att raden försvinner. `SiktaArk` återanvänt — når nu även programpunkter (var onåbar på ett mästerskap utan matcher) |
| H-1b | **DPT2-delta för bannern:** eventtyp och sport finns INTE i `/api/jobb` — DPT2 skickar varken fältet, så bannerns metarad utelämnar typen tyst. `Eventbanner.harled` har parametern förberedd; det räcker att börja skicka fältet | Litet DPT2-jobb, inte iOS. Hänger ihop m **M-11** (`fotojobb.tavling_id`) — ta dem tillsammans |
| H-2 | **Dynamisk bakgrund ur ★-potten** — bakgrunden väljs automatiskt efter dagens kategori/sport. Kedja: **★-bild för kategorin → egen bild → standard** | ⛔ kräver **★-flagga i DPT2 Leverera/Publicera** + bildkanal till appen (delar loggor→R2-vägen). Detta är V5-D:s kvarvarande "★-bakgrundspott" |
| H-3 | **Jobbtypsvarianter** — hemskärmen byter INNEHÅLLSBLOCK efter jobbtyp, inte layout. Landskapsvariant: `LANDSKAP · LÖRDAG`, plats, "VID SJÖN I MORGON", vind, **ljusblock** (blå timmen/gyllene/soluppgång), "1 h 22 m bilväg + 25 min vandring", `ÅK SENAST 02:08` | H-1. = V5-UX §14 |

### C-iOS-J · JobbDetaljView (den Code tvingades bygga odesignad — nu ritad)

| ID | Vad | Beroende |
|----|-----|----------|
| J-1 | **Hero + sigill.** Grundton **mörk Skagen Hav**, inte ljus systemvy; toppen tonas av kategorifärgen. Kategoribadge (prick + `SPORT · MÄSTERSKAP`), titel i Saira Condensed, undertitel (`Dag 1 av 3 · fotouppdrag`), **`Del av {event} ›` som klickbar rad — visas ALLTID när koppling finns**. Under: sigillet m orange nedräkningsring (`ÅK OM 1:02`, ringtext `· DALECARLIA PHOTO · SEDAN 2003 ·`) + tre tal **Åk senast · Restid · Start**. En vy, två dörrar (widget/låsskärm + jobblistan) | ✅ **KLAR 19/7** (ios `06968a1`, 159 gröna): hero m kategoribadge, titel, `Del av {event} ›` (klickbar när vi vet vilket paket som bär eventet, annars stum men KVAR), kategoritonad topp. `SiktaArk` återanvänt — valet styr nedräkningens mål (`siktatStart`) så även ett heldagsjobb får en avgång att räkna mot; NÄR-raden visas bara när sigillet saknas (annars dubblett av de tre talen). Eventtyp-parametern förberedd men utelämnas tyst — samma lucka som **H-1b** |
| J-2 | **Dagens deltillfällen** — tidslinje (prick + tid + namn + not), nästa = orange prick + `NÄST`-badge, ★ kvar. **Varje gren tappbar → sheet: "Skapa SoMe" (→ fältflödet) + "Öppna passet"**. **"@ N"-chippet BORT** (= M-10) | ✅ **KLAR 19/7** (ios `b09bd2c`, 142 gröna — bygger även **M-10**): ny logikfil `Sources/Deltillfallen.swift` (NÄST-markering, gren vs hållpunkt, noten, arkets underrubrik) + `Sources/GrenArk.swift`. **Vakten mot hållpunkter är `gren`-fältet (`Deltillfallen.arGren`), inte namnet** — namnjämförelser är precis det D11b §3 river ut. `FaltflodeView` fick `startSteg` (default `.pass`, alla gamla anrop oförändrade): "Skapa SoMe" hoppar till vinnarsteget när startlista finns, annars passteget som redan förklarar att listan saknas. Tidigare svarade raden bara om `deltagare` var ifylld. "Del av"-invarianten i logiken: utan känd tävling skrivs bara grendelen — aldrig lösryckt |
| J-3 | **Karta + Vid arenan + Ljuset idag** — kartkort mot arenan m pin + avstånd/restid + **Navigera** (Google Maps) + **Sätt/ändra plats**; jobbnära väder −1h/start/+2h/+4h; blå timmen · gyllene timmen · upp · ned. Okänd arena: ingen karta/restid/väder, "Sätt plats"-uppmaningen bär tomrummet | ✅ **KLAR 19/7** (samma commit): MapKit m `interactionModes: []` + statisk region (lätt att öppna), Navigera via `Externa.oppnaKarta` (widgetens väg). Nytt `PlatsArk.swift` — namn + lat/lon, "Slå upp namnet" (CLGeocoder) + "Min position", sparas i `ArenaOverride` → **karta/restid/väder/widget hittar samma punkt**. VID ARENAN via `VaderService.hamtaPunkter` (W-2:s serie, ingen tredje väderväg), heldag ankras 12:00. LJUSET IDAG på ny `SolTid.passager(...)` som speglar godtycklig solhöjd kring middagshöjden precis som `dygn()` gör med soluppgången (blå −6°/−4°, gyllene ±6°, visar passagen framför `nu`; polarnatt → nil, testat). Okänd arena: raderna **nämns vid namn** (`Karta — Restid — Väder —`) m Sätt plats-knappen, och skiljer på "jobbet saknar plats" och "okänd arena" |

*Handlingar denna runda: Sätt/ändra plats + Sikta på annan tid. **Senare runda:**
ring kontakt, öppna gallring/leverera.*

### C-iOS-S · Signatursystemet + färgsystemet

| ID | Vad | Anteckning |
|----|-----|-----------|
| S-1 | **Sigillkomponent** — en komponent, fyra roller: **splash** (full prakt, **ringen roterar ett varv medan jobben synkar**) · **nedräkning** (hem/jobbdetalj/widget/låsskärm; på låsskärmen stort, centrerat, **mono utan kategorifärg**) · **sidhuvudsmärke** (litet, tyst, alltid uppe till höger) · appikonen = samma märke | ✅ **KLAR 19/7** (ios `233c5b5`, 131 tester gröna): `Delat/Sigill.swift` (`git mv` från Widgets/) — `SigillRoll`: `.splash(rotation:)` · `.nedrakning(andel:)` · `.marke`, alla mått **relativa `storlek`** så samma komponent bär 26 pt i ett sidhuvud och 232 pt på hemskärmen (proportioner ur mockupens viewBox). `SigillRingtext` placerar tecknen ett och ett — SwiftUI saknar `textPath`. **Delningen:** `Delat/` låg redan under `sources:` för BÅDA targeten → ingen duplicering; fällan var att `Theme.swift` INTE finns i extensionen, så brandfärgen bor i `SigillStil.brand` och typsnittet skickas in av anroparen (SF Pro i widgeten, Saira Condensed i appen). **Städning:** `NedrakningsRing` i DesignKit BORTTAGEN — den var appens andra ringimplementation vid sidan av widgetens, exakt den dubblering Design varnar för. Inkopplat: splash över roten, sidhuvudsmärke på Hem/Matcher/Jobb/Bilder, hemskärmens hjälte, samt **den del av J-1 som S-1 bär** (sigill-nedräkning + tre tal i jobbdetaljen) |
| S-2 | **Våttstämpel "LEVERERAD"** — samma sigill m ringtexten `· LEVERERAD · 22 JULI 2026 ·`, lätt lutad. Sätts när sista bilden gått till kund; syns på leverera-kvittot, jobbkortet i listan och som overlay på omslagsbilden | S-1 + leverera-flödet sätter flaggan |
| S-3 | **Färgsystemet: fem roller, var sin zon och form.** ① **Brand** orange — enda färgen som får *agera* (knapp/ring/siffra) ② **Kategori** — prick eller tunn vänsterkant, **aldrig fyllda ytor** ③ **Gren** — kant/markör, **endast i sport**, ingen textetikett ④ **Status** — fyra fasta betydelser (synk blågrå · klar grön · väntar gul · fel röd), liten prick/pill, vinner blicken bara vid handling ⑤ **Lagfärger** — **karantän inuti lagbrickan**. Regel: **max två mättade färger per kort.** **Eventtyp tappar sin egen färg** (den återanvände grenens hex — cup delade Herr-teal, turnering delade Mixed-olive) → bara etikett, ärver kategorin | **iOS-lyftet är INTE:** DPT desktop rörs, nya hex, ny navigation. Genomförs ihop m W-8 (delad plist) |

### ⚠️ Två punkter att stämma av INNAN bygge

**(a) Hex-konflikt.** Färgsystem-canvasen anger kategorierna som Sport/Hav
`#4E93C4` · Landskap/Sol `#D19A3E` · Människor/Rosé `#D07E93` · Film `#A188C4`,
medan widget-handoffen och branch-CLAUDE anger kanonvärdena
Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`.
Design skriver "inga nya hex, vi justerar bara ljushet för mörkt läge" — men det
måste bekräftas **innan den delade plisten (W-8) byggs**, annars gjuts fel
värden i den enda källan.

**(b) Q6-standardvalet.** Widgetens standard = **ljust**, medan appen i övrigt
är mörk Skagen Hav. Det är en medveten designskillnad (hemskärm = alltid ljus),
men värd Stigs bekräftelse.

### Snapshot-delta (App Group) — samlat

Nya/utökade fält som C-iOS kräver: `liveActivityAktivFor` (W-6) ·
`senasteLeverans` (W-3) · `platsOkand` (W-3) · jobbnära väderserie i stället för
dygnsrutnät (W-2) · soltider inkl. blå/gyllene timmen (W-3, J-3) ·
snapshot-tidsstämpeln ska **visas** (`IDAG 07:01`), inte bara styra dimning
(W-3) · 3 DÄREFTER-poster m titel/plats/datum/kategori (W-4) · delad färgresurs
(W-8). *Nuläge i `Delat/JobbSnapshot.swift`: `vaderSerie`, `soluppgang`,
`solnedgang`, `kommande[]` och `skrivenVid` finns redan — resten är nytt.*

## D · iOS

| ID | Vad | Anteckning |
|----|-----|-----------|
| V2-19 | Malmö FF–Bröndby saknades i kalendervyn + väder | ✅ **LÖST 17/7** (ios `9f24628` + dpt `02410b1`): rot = formulärets datetime-local ger minutprecisa tider ("T14:00") som mobilparsern missade. Fix i BÅDA ändar (parser + `_iso_sekunder` vid källan/bron) + synlig flagga för datumlösa poster (lista + kalender-banner). **Bron-datat normaliserat live** (22 fält) → installerade appen visar matchen DIREKT, före ominstallation. Svar på öppna frågan: inlagd via DPT2 = formulärvägen, precis som rotorsaken förutsade |
| V2-16 | IG Stories-delningen felade ("går inte att skicka filen") | ✅ **LÖST 17/7** (ios `9f24628`): `instagram-stories://`-schemat + bilddata på pasteboarden ersätter fil-URL-ShareLink; + "Spara till Bilder"-knapp (interim & permanent fallback); generiska arket kvar som "Dela på annat sätt". **Kräver appinstallation** — oskarpkört mot riktiga Instagram |
| V2-05 | Förhandsgranskningen utanför synfältet | ✅ **LÖST 17/7** (ios `9f24628`): autoscroll till preview-sektionen när renderingen landar |
| V2-20 | Verifiera SoMe-flödet för friidrott före SM 24–26/7 | ✅ **KLAR 17/7 kväll** (dpt `0554c89` + ios `b2568f1` + sajt `5628a0a`, dpt-render **1.3.0 DEPLOYAD**): hela D2-matrisen omrenderad + visuellt verifierad (start/resultat/placering × alla grentyper, DNF, resultatetiketter — inga ställningssiffror) · NYTT: rekord-fält → guldrad ("SM-REKORD"/"PERSONBÄSTA") + start_when/venue genom molnvägen ("Nästa gren/pass" med tid+plats) + iOS-fälten (installerade på telefonen) · två-lags-antaganden verifierade fria i worker/renderare/iOS (arEvent/arIndividSport) · E2E genom workern skarpkörd (temp-paket, städat). W-friidrott ✅: Mästerskap/Friidrott-koden LIVE på sajten (D4-deployen bar ut den) |
| V2-06 | Noteringar på event/matcher: snabbt i iOS under eventet, utförligt i DPT2 efteråt; sökbara vid planering av liknande event | v2 §6 · iOS+DPT2 · **BESLUT (Stig 17/7): TVÅVÄGS synk iOS ↔ DPT2** · matar V2-12 packning + V2-17 lathundens arenadel |
| V2-11 | Filmlogg: rulle i vilken kamera, exponeringsanteckningar, status (i kamera/hos lab/skannad), kopplad till frysinventariet | v2 §11 · iOS+DPT2 |
| V2-18 | Nyckelspelare → publiceringsflödet: lathundens "spelare att följa" blir objekt m storyline per match → snabbval vid bildval/SoMe + overlay-text kombinerar händelse + kontext ("mål i sin första match för MFF!") | v2 §18 · bygger på V2-17; samma JSON som Damallsvenskan-research |
| iOS-trupp-2/3 | Trupp skiva 2 + 3 | **SKIVA 3 ✅ KLAR 18/7 kväll** (`02da2db`): mobilens roster reconcilieras hem via SYNK-DPT2-deltan (deltan bär hela raderna) — start/med + OCR-nya spelare in i matchtruppen, mobilen auktoritativ, identisk roster no-op. Rot till 0-startande-fyndet: paket-pushen klobbar inte längre. | **Skiva 2 ✅ KLAR 18/7** (ios `c65f70a`, INSTALLERAD): "Läs uppställningen ur bilden"-knapp → Vision-OCR (sv/en, utan språkkorrektion) → ren matchningslogik (efternamn+nr, Levenshtein-tolerans, efternamnskrock→osäkra, nakna nummer bär aldrig bevisvikt) → obligatoriskt granskningsark → fyller startelvan. 10 tester (31 gröna). Skiva 3 kvar |
| iOS-notis | Skarp notis-landning ("påminn när matchdata landat" — Stigs knapptryck end-to-end) | Kvar från design-lyftet etapp 3 |
| iOS-story | Story-text-override | Kvar från lyftet |
| iOS-lev | Leverans-progress-datakälla | Kvar från lyftet |
| FEAT-iOS-01 | Logotyp på lag i appen | ✅ **LÖST 18/7 av IB-3** (ios `c1791c0`) — R2-vägen fanns redan serverside; appen renderar nu URL:erna |
| FEAT-iOS-02 | SoMe-inlägg från heldagsevent i Kalendern | Blockerad: mobil render-väg (Pillow är Mac-bunden — se ML-E2) |
| FEAT-iOS-03 | Kalender som visningsläge under Fotojobb | ✅ **SKIVA 1 KLAR 17/7** (ios `99973cd`): Lista\|Kalender-segment, månadsgrid + dag-panel, Kalender-fliken BORT (4 flikar). Skiva 2 kvar: deadline-ringar + krock (kräver /api/jobb-data) |
| FEAT-iOS-04 | Systemstyrt mörkt tema | Litet (samma princip som DPT2 #25) |
| B-012 | Kamerabrygga FTP: Z8 → telefon utan kortdrag (ersätter SPIKE-iOS-01) | **SKIVA 1+2 KLARA 18/7 kväll** (ios `df4e472`+`ec32b91`, INSTALLERAD på telefonen): FTP-motor på Network.framework (ren parser/tillståndsmaskin, atomisk STOR→importerade-hyllan, EPSV/PASV) + Kameran-segmentet i Bilder (PÅ/AV, adress stort, puls, remsa, Story av vald + Redigera i Lightroom, keep-awake) + FTP-lösen i Inställningar + **dpt://kamera**-deep-link (genväg/NFC → mottagaren PÅ). 16 nya tester; simulatorverifierad end-to-end m curl (byte-identisk fil, rätt grupp). **KVAR skiva 3:** skarpkörning m Z8 (recept §8 i planen: FTP-profil 172.20.10.1:2121, användare dpt, passivt läge PÅ, JPEG-sändning) + Vintage-preset-valideringen §6b |
| SPIKE-iOS-02 | Översyn "Matchdata klar" | Liten, ihop med notis-flödet |
| B-003 | Röst → transkribering → action | → **ABSORBERAD av K-3** (assistenten Dala, sektion K). Var LÅG prio 16 jul; lever nu vidare som Dalas kärna |
| B-008 | iPad-spike + D3-implementation | Stigs prio 4-spår |
| B-009 | Widgets (hem + låsskärm) | ✅ **BYGGD 19/7** (ios `8b88f79`, PUSHAD + installerad) — **Designöversynen är nu inne** (`HANDOFF-widget-lasskarm.md`): ytan är RÄTT, sex familjer/en snapshot/statiskt behålls. Fortsättningen = **C-iOS-W (W-1…W-8)** ovan |
| B-010 | Låsskärm som startsida (Live Activity) | **SKIVA 1 ✅ KLAR 18/7** (ios `ea9cb88`, INSTALLERAD): widget-extension NEFBryggaWidgets — kompakt Island (LIVE-puls + lagkoder + ställning, klocka accent/tabular via timerInterval), expanderad + låsskärmskort (från avspark-läget per D6); LIVE-läget startar/uppdaterar, slutsignal → SLUT + 30 min kvar. **D6-REST ✅ KLAR 18/7** (ios `5d85363`, INSTALLERAD): FÖRE-läget (MATCHDAG-kort: avsparkstid, "Åk senast · N min restid" i accent, arenaväder, tidsprogress Nu→Åk→Avspark; kompakta Island räknar ner till åk senast), auto-start på matchdagen (nu ≥ åk−60min, ur Hem-restidsberäkningen), deep-link `dpt://match/<id>` → matchhubben. **Kvar:** icke-match-jobb (bröllop/porträtt-läget) + B-009-widgets (small/medium/rektangulär) |
| B-011 | Realtid utan batteridränering (spike) | Läs-features utbrutna till iOS-läs ovan |

## E · Webb/sajt

| ID | Vad | Anteckning |
|----|-----|-----------|
| BUG-WEB-01 | Sessioner cachas under Människor i Chrome | Utred cache-headers/stale HTML |
| FEAT-WEB-01 | Arkiv-/landningssida Ligor & Tävlingar | → **D4** |
| FEAT-WEB-02 | Arkiv-/landningssida Matcher | → **D4** |
| FEAT-WEB-03 | Nyhetsindikator "Sport" på startsidan | → **D4** |
| FEAT-WEB-04 | Standardisera mörkt tema | → **D4** |
| B-006 | Sportsidans struktur (webb) | ✅ **HELA D4 LIVE 17/7** (sajt t.o.m. `334ef20`, dpt `536a18c`): tvåkolumn+rail+MatchRad m grenkant, Matcharkivet+Ligor-arkivet, startsidan→Astro m uppdaterad-rad, Montserrat-ordmärke, mörkt default. → D7 Featured oblockerad (index är Astro nu) |
| W-friidrott | Verifiera att Mästerskap/kategori+Friidrott-sajtkoden är deployad | ✅ **VERIFIERAD LIVE 17/7**: Friidrott/Tävling/Ligor på /sport + Mästerskap i Ligor-arkivet — D4-deployen bar ut den gamla koden |
| V2-04 | Mobil sport-layout: tidig liten "nästa event"-notis m ankarlänk ner till På gång-sektionen (ordningen behålls; desktop är rätt) | v2 §4 · litet, ovanpå D4-leveransen |
| V2-08 | Presskort (Svenska Journalistförbundet + IFJ) under Om + standardiserad mejlsidfot (kontakt, länkar, presskortsinfo) — gäller även ackrediterings- och V2-KUND-mejlen | v2 §8 · exakt formulering = copyarbete (öppen) |
| V2-09 | Tjänstesektion m ingångar från startsida + nav: Sport (match/lagfoto/dokumentation/bildbyrå) · Människor (bröllop/student/dop/porträtt/familj/djur) · Kommersiellt (produkt/mode/artister) · Landskap (urval + försäljning) | v2 §9 · bildbyrån ev. egen ingång (annan målgrupp); mappar mot V5-kategoritoppnivån + temana Hav/Rosé/Sol |

## F · Mobil-live

| ID | Vad | Anteckning |
|----|-----|-----------|
| ML-E1-skarp | Etapp 1 skarpkörning telefon↔desktop under riktig match | Byggd, ej skarpkörd |
| ML-E2 | Etapp 2: publicera stories utan Macen (Browser Rendering-inriktning) | Blockerare: **loggor → R2** · låser upp FEAT-iOS-02 |

## F18 · Stigs fynd 18/7 (källa: `~/Downloads/backlog-2026-07-18.md`)

*Numren = punkterna i Stigs lista. Föreslagen ordning (Stigs): 12 KRITISK före
MFF–Bröndby 14:00 → snabba fixar 1/4/10/7 → formulärsvepet 5+6 → utredningar
3/2 → UX-omtag 8/9/11 → ny funktion 13.*

| ID | Vad | Anteckning |
|----|-----|-----------|
| F18-12 | **KRITISK: Uppladdning av laglogga fungerar inte** (DPT2 lagvyn, Malmö FF) | ✅ **LÖST 18/7 fm** (`d6a943f`, FÖRE 14:00): rot = INTE handlern — PNG/WebP gick ner i `_thumb_for`:s raw-gren (exiftool-preview saknas i en PNG) → miniatyren None → loggan visades aldrig fast valet+sparningen lyckades. Fix: PIL-läsbara format direkt + transparens bevaras som PNG-data-URI. Bonus: tävlingsvyns filväljar-filter hade ogiltigt pywebview-format (kastade tyst). 2 regressionstester (677 gröna). **Kräver DPT2-omstart** |
| F18-1 | Bild 4 blinkar svart vid hover i sport-galleriet (Darderi–Borges, webben) | ⚠️ **KVARSTÅR efter första fixen** (fm-listan p.3): `backface-visibility`+`translateZ(0)` (sajt `c3abe57`) räckte inte — oskalat original REDAN motbevisat (alla fyra 1600×1067, 103–151 kB). **Utredning 18/7:** cache-headers verifierade PERFEKTA (immutable, 1 år — ingen omhämtning vid hover) + filstorlekar friade igen → ren rendering. `will-change: transform` tillagd ovanpå GPU-layer-fixen (sajt `will-change-commit`). **Om blinken ÄNDÅ kvarstår efter Pages-deployen:** nästa steg är att ersätta själva filen (omkoda 4.jpg) — allt annat är uteslutet |
| F18-2 | Automatisk nedskalning av galleribilder vid publicering (DPT2) | ✅ **VERIFIERAD REDAN UPPFYLLD 18/7**: ALLA bilduppladdningar går genom `bildoptimering.optimera` (2200px-tak, JPEG 85, sRGB, skärpning) i `ladda_upp_bild` — ingen väg ut för oskalade filer; Borges-bilderna bekräftade 1600px/103–151 kB. Varningsvalidering överflödig (taket är inbyggt) |
| F18-3 | "Importera spelschema"-knappen död (DPT2) | Handler saknas eller tyst krasch? Definiera sen källa (TheSportsDB 4347/5209, CSV, mff.unwi.se) → **absorberar SPIKE-01** |
| F18-4 | Ta bort utskrivet "Heldag" i På gång-högerspalten (webben) | ✅ **LÖST 18/7** (sajt `c3abe57`): heldag → tom tid-rad (nedre platsraden behålls = linjerar mot klockslags-poster); Resultat-kortets "Avslutat" kvar |
| F18-5 | Kompaktare heldagsval i matchformuläret (DPT2) | ✅ **KLAR 18/7** (`c9b4190`): kompakt vänsterställd toggle, hjälptexten i tooltip, heldag → fältet heter Eventnamn |
| F18-6 | Osparad post kan inte öppnas efter kollaps (DPT2 matchformuläret) | ✅ **KLAR 18/7** (`c9b4190`): rot = toggla körde hamtaMatch på 'ny-'-id (finns ej i db) → utkast null. Nu: kollaps skriver fältdatat till listraden, expand återställer därifrån. Webbläsar-verifierat att datat överlever cykeln |
| F18-7 | Rubrik-fallback dubblerar heldagsmarkering (DPT2 matchformuläret) | ✅ **LÖST 18/7** (dpt `dbe8b58`): matchnamn-fallback "Ny match"/"Namnlöst event", utskrivna Heldag borta ur metaraden — badgen ensam markör. Kräver omstart |
| F18-8 | Tidigare projekt tar för mycket plats + dubbletter | ✅ **KLAR 18/7** (`7e7ca18`): delad ProjektLista — kompakta rader (initialbricka, relativ tid "igår 21:30", Återuppta), EN rad per match (senaste vinner, N×-badge för dubbletter), 3 + Visa alla. Kvar (litet): riktig bild-tumnagel kräver backend-thumb per urval |
| F18-9 | Kalenderväljarna radbryter (DPT2 Fotojobb) | ✅ **KLAR 18/7** (`7e7ca18`): rena färgprickar (16px, aktiv=fylld, släckt=urtvättad ring) m namn+läge i tooltip — ingen text som radbryter |
| F18-10 | Hem-knappen gör inget från matchsidan (iOS) | ✅ **LÖST 18/7** (ios `aea3771`): flikbaren postar popp-signal vid tryck på aktiv flik → Hem/Matcher nollar sin NavigationPath (Jobb/Bilder pushar inget). 31 tester gröna. **Install väntar** — telefonens tunnel nere igen |
| F18-11 | Tydligare logotyp på startskärmen (iOS) | ✅ **KLAR 18/7** (ios `3980134`, INSTALLERAD): hästen template-renderad VIT (ingen ny asset behövdes) m drop shadow, 44px bär hörnet, DPT sekundär; versionsraden → Inställningar → Om |
| F18-13 | **NY: Ladda upp bilder från iOS-appen** | **AVGRÄNSAD (Stig 18/7): BÅDA** — (a) matchbilder från kamerarullen in i matchens bildflöde och (b) sätta/byta lagloggor från telefonen. Byggs som egen skiva; loggavägen återanvänder /api/bilder/lag + logga_url-mönstret (IB-3), matchbildsvägen angränsar original-bryggan |

## IB · iOS-backloggen 18/7 (källa: `~/Downloads/dpt2-ios-backlogg.md`)

| ID | Vad | Anteckning |
|----|-----|-----------|
| IB-3 | **KRITISK: Loggor synkas inte till iOS** — appen faller tillbaka på initialer fast DPT2 har loggorna | ✅ **LÖST 18/7** (ios `c1791c0`): felsökningen visade att SERVERSIDAN redan levererar (paketet bär `lag_*_logga_url`, R2-speglat, MFF-loggan verifierad 200/PNG live) — APPEN parsade aldrig fälten. Ny delad `LagCirkel` (AsyncImage på ljus platta, monogram-fallback) i matchlista/hubb/live-läget; Match-modellen bär hemmaLogga/bortaLogga. **Löste samtidigt FEAT-iOS-01.** 31 tester gröna. Bröndby-loggan dyker upp när Stig lagt in den (F18-12-fixen + omstart) och paketet omsynkats. **Install väntar på telefonen** |
| IB-1 | Trupp-OCR: inläsning mot valt lag + auto-komplettering | ✅ **KLAR 18/7** (ios `910c68f`, INSTALLERAD): mot-valt-lag fanns redan (skiva 2 matchar mot vald sida); NYTT: "NR NAMN"-rader utan match i truppen → egen sektion i granskningsarket (förbockade, amber) → läggs till m NY-badge i listan för nr/positions-verifiering. Nr måste vara radens FÖRSTA token (testfångad falsk positiv: "AVSPARK 14:00"). 6 nya tester (36 gröna) |
| IB-2 | Bilder → På telefonen: Töm-knapp m bekräftelse | ✅ **KLAR 18/7** (ios `ec508ea`): Töm-rad m antal+storlek + bekräftelsedialog; kort/moln rörs inte |
| IB-4 | Robustare DPT2↔iOS-synk: silent push + `updated_since`-delta | ✅ **BYGGD 18/7** (worker `2ce239a` DEPLOYAD + D1-migration 0005 + ios `8dd2291` INSTALLERAD): enhetsregister (`/api/push/enhet`, app registrerar vid start, döda tokens städas), tyst push `{match_id, changed}` i waitUntil vid paket-/roster-upsert → appen omhämtar, `?updated_since=` på /api/live (servern stämplar `nu`) + förgrundsdelta i appen. **Notis-landningen på köpet:** påminnelsen bär match_id → tap öppnar matchens hubb, banner även i förgrund. Delta+register skarpverifierade mot live; **första helkedje-provet sker när appen öppnats (registrering) + nästa DPT2-paketpush**. WS/SSE i live-läge = ev. steg 2 |
| IB-5 | **Fokuspunkt i iOS-appens story-flöde** (Stig 18/7) | ✅ **KLAR 18/7** (ios `ec508ea`): FokusValjare-sektion — dra på förhandsbilden (procent, samma modell som `_cover_crop`), zoom-slider 1–2.5×, 9:16-ramguide, Återställ; nollas vid fotobyte; overlay AV + fokus → hela bilden skickas så serverns crop får punkten. INSTALLERAD |

## F18FM · Förmiddagens genomgång 18/7 (källa: `~/Downloads/backlogg-2026-07-18-fm.md`)

| ID | Vad | Anteckning |
|----|-----|-----------|
| F18FM-1 | **Matchpubliceringens resultatfält ser inmatade ut** (UX) | ✅ **KLAR 18/7** (dpt `c476387` + ios `8e23f49`): resultatremsan — "–:–"-placeholder (dämpad), streckad→solid ram, per-fält-indikator tom cirkel→puls (sparar)→grön bock (facit = senast sparade värden; mobil-inkommande räknas som sparade). iOS: matchdata-arket visar resultat/mellan/målskyttar-status för pågående/avslutade matcher. Webbläsar-verifierad hela cykeln |
| F18FM-2 | **Webbkanalen läcker social text** (bugg) | ✅ **LÖST 18/7** (`37fcca5`, schema **v34**): rot = Generera returnerade redan `{referat, bildsvep}` men referatet KASTADES — webben strippade sociala texten. Nu: referat = eget källfält (kolumn på materialet, eget fält i panelen som Generera fyller), webben + Innehålls-hämtningen byggs från det; strippningen kvar som fallback för pre-v34-material och täcker nu @?-osäkra handles. Kräver omstart (v33→v34) + ompublicering av kvällens referat via ✨ Generera |
| F18FM-3 | Hover-blinken KVARSTÅR — se uppdaterad F18-1 ovan | Utredning: hämtas filen om vid hover? + `will-change: transform` |
| SYNK-DPT2 | **Tvåvägs-blixt även mot DPT2** | ✅ **KLAR 18/7** (`8f2da6b`): `live_synk.delta` (?updated_since, serverns nu-stämpel) + `synk_delta` som applicerar mobilens live-fält store-direkt (INTE satt_resultat — inget moln-eko/omstämpling), App.svelte pollar var 15s → `dpt-synk`-event → Matcher laddar om. 3 tester. Baslinje-anropet tyst |

## M18 · Matchens fynd 18/7 em (källa: `~/Downloads/dpt2-backlogg-match.md`)

*Skarptestet MFF–Bröndby: D6-kedjan fungerade före→live→slut. Punkterna =
Stigs numrering. 2+4+5 är ETT klockmodul-paket.*

| ID | Vad | Anteckning |
|----|-----|-----------|
| M18-7 | **AKUT: Avsluta live-match gick inte att hitta** — match låg kvar som live | ✅ **LÖST 18/7 em**: (a) datat sanerat direkt (KDFF-matchen 27/6 hade resultat 6-0 men status 'kommande' — pre-slutsignalfix-kvarleva; satt till avslutad) + (b) ios `4ac414a` (INSTALLERAD): "Matchen är slut"-raden PERMANENT för alla ostängda matcher med passerad avspark (krävde förr 'idag' → äldre häng gick ej att stänga) |
| M18-1 | Startelva-overlayn ritar inte spelarnamnen | ✅ **KEDJAN LÖST 18/7 em** (dpt `80a13a0` + worker `36226f0`, **dpt-render 1.4.0 byggd/pushad/deployad**): startelva saknades BÅDE i workerns spec-bygge (byggs nu ur paketets roster: hemmalagets start=true, "nr namn"-rader) och i containerns _GENOMSLAPP. Visuellt verifierad lokalt (namnen ritas). **OBS datalagret:** molnpaketets roster hade 0 startande — appens OCR-elva verkar inte ha sparats ELLER klobbats av desktopens paket-push (→ trupp skiva 3-reconciliation). Verifiera nästa matchdag |
| M18-6 | Snabbplock → Lightroom mobil | ✅ **KLAR 18/7 kväll** (ios `7f6144c`, INSTALLERAD): importen sparar plocken till "DPT Snabbplock"-albumet i kamerarullen (skapas vid behov, readWrite-behörighet) — telefon + moln + LR i ETT tryck |
| M18-2 | Klockmodulen: manuell tidssynk mot matchuret | ✅ **KLAR 18/7 kväll** (ios `d7459d1`+`1e676b9`, INSTALLERAD): tap på matchklockan → "Sätt matchtid" (halvleksminut 07:32 eller matchminut 52:10 → tolkas som 2:a halvlek) |
| M18-4 | Tilläggstid + räkning per halvlek | ✅ **KLAR 18/7 kväll** (samma commit): Matchklocka-modellen (ren, 4 testfall) — 0–45→45+X, 2:a halvlek startar ALLTID 45:00→90→90+X, "Starta 2:a halvlek"-knapp under klockan, målminut loggas 45+2; persistad per match (appomstart-säker) |
| M18-5 | Automatisk halvleksdetektering | ✅ **KLAR 18/7 kväll** (samma commit): `Matchklocka.auto(avspark:)` — <60 min = första, därefter andra (bas avspark+60); manuell synk vinner alltid |
| M18-3 | Snabbredigering av mål | ✅ **KLAR 18/7 kväll** (samma commit): alla mål som tappbara chips i målflödet — tap väljer händelsen, samma minut/tillägg/straff-reglage korrigerar den (synka+spara, inget ta bort+lägg om). Målminuten förifylls dessutom ur matchklockan |
| M18-8 | Gradienten över loggorna för kraftig — MFF-märket äts upp | ✅ **LÖST 19/7** (`3aec9c8`): roten var **cirkelmasken**, inte gradienten — transparent logga drogs in, saknad alfa gav ljus platta. Bröndby-filen är trasig i källan |
| M18-9 | Automatisk HEMRESA efter match | ✅ **KLAR 18/7 em** (ios `209939b`, INSTALLERAD): "Hem: X min · Kajgatan 2B"-rad i glasarket när en match avslutats senaste ~3h och GPS ≠ hemma (>1 km); destinationen = fritt adressfält i Inställningar → Hemresa (geokodas), överstyrbar till hotell/nästa uppdrag |

## K · Kalendern & assistenten "Dala" (NYTT SPÅR — källa: `~/Downloads/backlog_kalender.md`, 19/7)

*Två epiker + fem features. Spåret hänger ihop: den utökade kalendern är
underlaget, Dala är gränssnittet mot den, och Event-som-nav är vad det används
till. **Absorberar B-003** (röst → transkribering → action) — den posten är
Dalas kärna, inte ett eget spår längre.*

### ⚠️ Arkitekturbeslut som måste tas FÖRE K-1 (den enda riktiga blockeraren)

Kalendern har i dag **två medvetet åtskilda vägar**:

| Väg | Scope | Ägarskap |
|-----|-------|----------|
| `tjanster/kalender.py` → deployad Calendar Sync-Worker | `calendar.events` (**läs+skriv**) | äger **jobbkalendern** |
| `tjanster/privat_kalender.py` → direkt från Macen | `calendar.readonly` (**skrivskyddat**) | läser **privata kalendrar**, lagrar INGET (token i `~/.config/dpt/`, allt annat i RAM), skriver aldrig till DB eller worker |

Modulens egen dokumentation säger rakt ut: *"de privata kalendrarna rörs ALDRIG
av en skrivning"* — och att fruns delade kalender läses lokalt just för att
inte skickas via Cloudflare. **K-1, K-4 och K-6 bryter alla mot det.** Att lägga
aktiviteter i privat-/KH-kalendern kräver skrivscope på en yta som avsiktligt är
skrivskyddad, och inbjudningar kräver dessutom deltagarhantering.

**Vägval att besluta:** (a) utöka den **lokala** vägen till `calendar.events`
och behålla principen "privat data lämnar aldrig Macen" — mer kod, men bevarar
designen; (b) låta workern äga även privatkalendern — enklare, men fruns
kalenderdata börjar passera Cloudflare. **Rekommendation: (a).** Beslutet styr
allt annat i sektionen, så ta det först.

| ID | Vad | Anteckning |
|----|-----|-----------|
| K-1 | **EPIK: Utökad kalender — hela livet, inte bara fotoföretaget.** Befintlig kalender hanterar hela vardagen, inte enbart fotojobb; skiljer på och kategoriserar aktivitetstyper (fotojobb vs privat/övrigt); kopplar mot den Google-spegling som redan finns i fotojobb-flödet | ⛔ **Blockerad av arkitekturbeslutet ovan.** Bygger på FEAT-iOS-03 (kalendervyn) + `privat_kalender.py` |
| K-2 | **Assistenten "Dala" som genomgående persona** (hon). Arbetsnamnet är valt för **robust taligenkänning vid snabbt/otydligt tal** — två stavelser, öppna vokaler, inga närliggande svenska ord. Grund för röststyrning, kalenderdialog och framtida "companion på axeln" | Konceptbärare för K-3…K-7. Namnvalet är motiverat och bör inte ändras utan att skälet vägs in |
| K-3 | **Röststyrt aktivitetsskapande.** Fritt tal → färdig aktivitet. Exempel: *"Dala, skapa upp ett fotojobb, fotografera Lugi handboll, klockan 18 i Sparbanken Skåne Arena på torsdag."* → titel **Lugi handboll** · kategori **Sport** (härledd) · start **torsdag 18:00** (relativt datum → faktiskt) · plats **Sparbanken Skåne Arena**. Ställer följdfrågor vid ofullständig info (sluttid, motståndare, koppla till match). **Bekräftelse före sparning** så det går att justera | **Absorberar B-003.** Samma godkänn-steg-princip som Generera-prompten och FEAT-14 skiva 3 — Claude föreslår, Stig godkänner. Kategorihärledningen ska använda kategorifacit (Sport·Landskap·Människor·Film) |
| K-4 | **Dala väljer rätt kalender automatiskt** — jobb-kalendern · KH-kalendern · privata. Härleds ur sammanhanget (fotojobb → jobb, handbollsaktivitet → KH, övrigt → privat), **med möjlighet att korrigera** | ⛔ Arkitekturbeslutet. ⛔ Stig: **vad står "KH" för?** (handboll/Lugi — sonens lag?) Benämningen måste verifieras innan den kodas in |
| K-5 | **Smart mötesförslag** — Dala föreslår datum/tider ur luckorna i **hela** kalendern (fotojobb + privat), undviker krockar, ger flera alternativ som lätt förmedlas vidare. Tar hänsyn till arbetstid, restid och buffertar | Krockdetekteringen FINNS redan (privata kalendrar, byggd + live) — här vänds den till att hitta luckor i stället för konflikter. **Restidsdelen kan återanvända iOS restidsmotorn.** Kräver bara läsning → **minst blockerad, bra första skiva** |
| K-6 | **Skicka kalenderinbjudningar** till angivna personer — namn → mailadress via kontakter, läggs till som deltagare på aktiviteten | ⛔ Arkitekturbeslutet + deltagarhantering (`attendees` + `sendUpdates`). Workern har redan `calendar.events` + `gmail.send`. **Utskick till riktiga personer = samma försiktighet som ackrediteringsmailen — alltid godkänn-steg** |
| K-7 | **EPIK: Event som nav — koppla innehåll + smart uppföljning.** Bilder, röstnoteringar och annat material kopplas till eventet; Dala levererar **sammanfattning** · **förslag på fler aktiviteter** · **noteringar** · **uppföljning/påminnelser** (efterbearbetning, leverans, ackreditering nästa gång). Eventet blir navet för innehåll, kontext och nästa steg | Bygger på K-1 + V5-eventmodellen. Överlappar **V2-06** (noteringar tvåvägs iOS↔DPT2), **V2-13** (publiceringsstatistik) och **V2-17** (matchlathunden) — samordna, bygg inte tre gånger |

**Beslut redan fattat (röstnoteringar):** ljudfilen lagras **enbart för
träningsändamål**; allt tal **transkriberas till text**, och det är
transkriptionen som används för sammanfattning, uppföljning och event-koppling.

**Föreslagen ordning:** arkitekturbeslutet → **K-5** (bara läsning, fristående
värde, bevisar luck-logiken) → K-2/K-3 (Dala + röst→aktivitet, bekräftelsesteg)
→ K-1 (den stora kalenderomläggningen) → K-4/K-6 → K-7.

## R · Rörligt material (NYTT SPÅR — designsvar D10 inne 19/7, inget byggt)

*Källa: `HANDOFF-D10-rorligt.md` + mockup `DPT v5 - Rörligt.dc.html`. Låg prio
mot C12/C-iOS, men spåret finns nu ritat i sin helhet. **Namn:** domänen heter
**Rörligt**, enheten **klipp** — "Film" är och förblir analog film.*

**Bärande principer:** klipp beter sig som NEF:er (hittas → granskas →
paketeras → publiceras → levereras, i samma ytor). **Allt UI visar proxyn;
mastern stannar på Macen.** Statusspråket är D9:s (🔵🟡🟢🔴) rakt av.

| ID | Vad | Anteckning |
|----|-----|-----------|
| R-1 | **Ingest + ingest-tillstånd** — EN färgprick per klipp, aldrig teknisk text: ⚪ oproxat · 🔵 proxas… (tunn progress) · 🟢 redo · 🔴 master saknas · 🟣 Resolve-export. Källglyf 📱 iPhone · 🎥 Pocket · 🎬 Resolve-mapp | Skiva 1 — allt annat vilar på den |
| R-2 | **Snabbplock för klipp** (`#1b`) = HEMMET: rutnät av poster-JPEG:ar, hover = klippet spelar tyst, klick = väljer. Samma gest/muskelminne som stillbildens Snabbplock | Bygg FÖRE R-3 (Designs rekommendation) |
| R-3 | **Granskningsbord** (`#1a`) = detaljen bakom dubbelklick: stor spelare, scrub, filmstrip, enkel in/ut för snabbklipp, **waveform + mute** (originalljud "O-ton · orig"). Djuptrim är alltid Resolves jobb | |
| R-4 | **Blandade paket + async reel i plan-listan** — fotografen väljer per paket (8 bilder + 2 klipp OK). Reel-radens pågår-tillstånd **överlever panelbyte** (bor i publiceringskön, inte panelens minne); fel kan komma EFTER stängd panel → kön visar felet + "gör om". `Post n/tot` ersätts av per-rads-status | |
| R-5 | **Grafik ovanpå rörligt** — ingen ny grafik: samma moment/tema/format-chips och samma Pillow-PNG som stillbildsstoryn. Förhandsvisning **frusen som standard**, ▶ spelar proxyn med överlägget levande. **Överläggets placering väljbar per klipp:** Hela klippet / Första 3 s / Endcard | |
| R-6 | **Kundleverans** — R2 + signerad länk m utgångsdatum; status i `dpt.db` ("levererat 14:20, öppnat 2 ggr, utgår om 12 d"). Fotografens leveranskort (Kopiera/Förläng/Återkalla) + **kundens mörka sida m sigillet** (`<video poster>` mot R2, "Ladda ner 4K"). Ingen HLS | Delar S-1-sigillet |
| R-7 | **Spåret där bild redan bor** — smalt spår i Leverera OCH Publicera (före plan-listan): "Rörligt · N klipp" m poster-chips + ingest-prick + "Öppna Rörligt →". Ren närvaro + genväg. **INTE en till flik i Publicera** | |
| R-8 | **iOS: granska & godkänn på plats** — snabbklipp tas på mobilen, Stig grindar direkt efter en gren. Player + Godkänn/Förkasta + kö; proxyn laddas upp via samma background-URLSession som NEF. **Ingen trim, ingen grafik i appen.** "Duger-för" vägs mot kanalgränsen ("Reel ✓") | |
| R-9 | **Kanalgränser — gula, informerande, ALDRIG blockerande**: IG Reel > 1:30 → "2:14 → för långt · trimma eller lägg som story" · IG Story-video > 60 s → "1:45 → 2 story-segment" · FB Reel → caption strippas på `#`/`@` | Samma anda som dagens FB-kap |

**Beslut att koda in:** *Förkasta på plats = GÖM, inte radera* (mastern behålls,
ångerbart) · *ett klipp = ett reel i MVP* (ingen söm i DPT2 — flerdelat går via
Resolve) · *master-gapet visas diskret* ("master väntar på import", ingen röd
larmfärg; proxy får publiceras, men **kundleverans av 4K kräver stängt gap**) ·
*klipp kopplas till **pass om det finns**, annars jobbet/matchen* — samma regel
som stillbild, så klippen blir sökbara per pass.

**Utanför scope (bekräftat):** TikTok · animerad grafik · video på publika
sajten (`film.astro` orörd) · HLS. Publik rörligt-sida = egen handoff senare,
**när ingesten (R-1) står**.

## G · Spikes DPT2

SPIKE-01 importera spelschema → absorberad av F18-3 · SPIKE-03 ML/modell-bibliotek ·
SPIKE-04 PM-mapp · SPIKE-05 platshållare i ML-bildvyer · SPIKE-06
push-notiser/kanaler i Inställningar · SPIKE-07 galleri-sökvägar.
(SPIKE-02 visningslogik → **D7**.)

## H · Infra/underhåll

| ID | Vad |
|----|-----|
| GR-opencv | Ogmergad gren `fix/opencv5-cascade` (opencv-pin <5 — gallra kraschar utan) |
| GR-kortrot | Ogmergad gren `fix/gallra-kortrot` (gallra från kortets rot) |
| #27-polish | Backend-flagghärledning (renderare + iOS får landslagsflaggan) + vajande vimpel — delar loggor→R2-vägen |
| P15 | Sportanpassade moment + poänglogik i Ny story (iOS) — fältobs Nordea Open | ✅ **LÖST 17/7** (dpt `6258e98` + sajt `a75b9bc` + ios `3ae9090`, dpt-render 1.2.0 deployad): sportstyrda momentknappar (tennis: Matchstart·Set klart·Tiebreak·Slutresultat·Nästa match), overlay-etikett ur rätt nivå (Setsiffror/gamesiffror; Tiebreak-läge), byggSpec skickar mellan för icke-scorer-sporter. Skarpt E2E-verifierad mot Borges–Darderi |
| P16 | Slutsignal i appen — "Matchen är slut" → Hem visar nästa match | ✅ **LÖST 17/7** (ios `868b3c9`, installerad): arAvslutad släpper Hem-hjälten, hubbknapp sätter moment=Slutresultat |

## Design-jobb (Claude Design)

| ID | Vad | Status |
|----|-----|--------|
| D2 | Horisont friidrott-mallar | ✅ **SVAR INNE + IMPLEMENTERAD** |
| D3 | iPad-layout Snabbplock | ✅ **SVAR INNE** (HANDOFF-D3-SVAR-…) — väntar implementation |
| D4 | Webb-paketet (B-006 + FEAT-WEB-01…04) | ✅ **SVAR INNE** — väntar implementation |
| D5 | Lightbox-spec | ✅ **SVAR INNE** (HANDOFF-D5-SVAR-…) — väntar implementation |
| D6 | Låsskärm & widgets (UTÖKAT: B-010 + B-009) | ✅ **SVAR INNE** (HANDOFF-D6-SVAR-…) — väntar implementation |
| D7 | Startsidans kuratering (FEAT-02 + SPIKE-02) | ✅ **SVAR INNE** (HANDOFF-D7-SVAR-…) — väntar implementation |
| D8 | iOS Fotojobb-kalendervy | ✅ **IMPLEMENTERAD skiva 1 17/7** (ios `99973cd`); skiva 2 = deadline/krock-datat genom bron |
| D9 | Publiceringsstatus-språket | ✅ **SVAR INNE** (komplett spec: StatusChip, hörnbåge i statusfärg, filterchips ersätter flikarna, fel-expansion m per-kanal + Försök igen, puls vid bygge, autospar ersätter utkastknappen, färgtokens ljust/mörkt) — **publiceringskedjan v2 helt oblockerad** |
| D10 | **Eventmodell-epiken + UX-lyftet (DPT v5 / iOS v2)** | ✅ **SVAR INNE 17/7** — komplett handoff + datamodell + 5 mockups i `design_handoff_eventmodell_v5/` → sektion C ovan; väntar implementation (egen branch, löpande merge) |
| D10r | **Rörligt material** (video/klipp) | ✅ **SVAR INNE 19/7** (`HANDOFF-D10-rorligt.md` + mockup `DPT v5 - Rörligt.dc.html`) → **sektion R** nedan. Inget byggt |
| D11 | Event, individer & fältflödet | ✅ **SVAR INNE + IMPLEMENTERAT 19/7** — fältflödet E13–E18 i iOS, importen C8–C10, Utövare-registret (se C19) |
| D11b | Begrepp & navigation | ✅ **SVAR INNE + §1/§2/§4 IMPLEMENTERADE 19/7** (se C19). Kvar: `fotojobb.tavling_id` (§3) — se **M-11** |
| D12 | **Tävlingar i stor skala + Lag & Utövare** | ✅ **SVAR INNE 19/7** (`HANDOFF-D12-SVAR-tavlingar-storskala.md` + 3 mockups) → **sektion C12** ovan. **PRIO ①+②**, väntar implementation |
| D-widget | Widget & låsskärm (svar på B-009) + JobbDetaljView-designrunda | ✅ **SVAR INNE 19/7** → **sektion C-iOS** ovan. **PRIO ③** |

## Stig — användarsteg (inget kodande)

- [ ] Starta om DPT2 (v27→v28-migrering + alla pushade fixar)
- [ ] Reparera Nordea Open - ATP (typ Turnering, 13–19 jul, Båstad, arenan, kalender) — nollades av BUG-01 före fixen
- [ ] Lägg in Nordea-spelare + matcher (+ rond per match)
- [ ] Google om-auth: `https://dpt-calendar-sync.stig-johansson.workers.dev/auth/login` (gmail.send)
- [ ] Ta D2-handoffen till Claude Design
- [ ] MP-död-beslutet: väck eller radera raderaMaterial/sparaUtkast (autospar)
- [ ] C-förslagen (design/C-FORSLAG.md): besluta
- [x] ~~**V2-19:** hur lades MFF–Bröndby in?~~ — svar: via DPT2 (formulärvägen = rotorsaken, LÖST)
- [x] ~~**V2-06:** bekräfta noterings-synk~~ — beslut 17/7: TVÅVÄGS iOS ↔ DPT2
- [ ] **V2-08:** finslipa presskortsformuleringen (copy) när sidfoten byggs
- [ ] Skarptesta IG Stories-delningen (V2-16) mot riktiga Instagram — appen ominstallerad, oskarpkört

### Beslut som blockerar 19/7-designen (svara innan bygge)

- [ ] **M-5:** var går tröskeln liten↔stor tävling — grenantal, deltagarantal, eller *alltid* arbetsyta för typ Mästerskap?
- [ ] **M-8:** nav-varianten — `Lag & Utövare` som EN post, eller `Utövare` + `Lag & ligor` var för sig? (mockuparna spretar)
- [ ] **M-9:** ska Läs in-granskningen byggas om i samma skala nu, eller räcker den till nästa stora inläsning?
- [ ] **Ordvalet:** *Utövare* vs *Personer* — Design lutar åt Utövare, koden säger Utövare i dag
- [ ] **Utövarsidan på webben** — spegla publikt under Sport i denna etapp, eller senare?
- [ ] **C-iOS (a):** hex-konflikten — gäller kanonvärdena (`#2F7CB0` m.fl.) och färgsystem-canvasens värden är bara mörkt-läge-justering? **Måste bekräftas innan den delade färg-plisten byggs.**
- [ ] **W-1 (litet):** cirkeln visar bara `1:02` (mockupen) medan handoff-texten säger `ÅK OM 1:02` — "ÅK OM" får inte plats i 58 pt utan att tränga ut siffran, och rektangeln stavar ändå ut "Åk 08:03". Följde mockupen; ändras i `SigillNedrakning.mitten` om Design vill ha ordet med
- [ ] **C-iOS (b):** widgetens standardutseende = **ljust**, fast appen i övrigt är mörk Skagen Hav — OK?
- [ ] **M-3/fältflödet:** ska 2:a och 3:e plats alltid efterfrågas, eller bara på ditt initiativ? (mockupen: valfritt)

### Beslut som blockerar kalender-/Dala-spåret (sektion K)

- [ ] **Arkitekturvalet (blockerar K-1/K-4/K-6):** ska den LOKALA vägen få skrivscope (privat data lämnar aldrig Macen — min rekommendation), eller ska workern äga även privatkalendern (enklare, men fruns kalender passerar Cloudflare)?
- [ ] **K-4:** vad står **"KH-kalendern"** för — handboll/Lugi (sonens lag) eller annat? Behöver verifieras innan det kodas in.
- [ ] **K-2:** är arbetsnamnet **Dala** det som gäller, eller bara arbetsnamn? (valt för taligenkänning — byte har en kostnad)

## ✅ Levererat nyligen (rörligt — flyttas hit när klart)

- 16 jul sen kväll: B-001 deltagarhantering (schema v29 + Grenar & deltagare-
  editorn) · B-002/D2 friidrotts-overlays + desktop- OCH telefon-publicering
  (render-container 1.1.0) · tävlings-paket till appen · tennis komplett i appen
  (matchdata individ, sport-medveten hub + Föra matchen, GAME-förande m auto-set)
  · individ-gren-kanten · iOS väder+restid ("åk senast")
- 16 jul kväll: iOS heldag→08:00 + Uppdrag-knappen klickbar (installerade) ·
  ios-repot backat till privat GitHub (sickan/ios-nef-brygga) · B-007 lightbox
  LIVE på sajten (D5-facit) · MP-död avgjord (raderaMaterial väckt,
  MatchHuvud/oppnaILightroom bort, utkast-paret sparat åt D9-autosparen)
- 16 jul em (steg 1): BUG-09 (gren·sport i koppla-chips/-lista) · #26-rest
  (id-baserade lag-uppslag i matchdaguttaget) · BUG-02 (Tidigare projekt-korten
  aktiverar nu urvalet → Leverera) · HDA-b (Ackreditering-filter)
- 15–16 jul: Track 0 (#23 #24 #25 · #27 flagga · #28 · sportevent↔tävling ·
  heldagsaktivitet-fixen) · tennis-paketet (profildriven motor, turneringskanal-
  buggen, D1-overlayn, schema v28 rond) · BUG-01 (unika tävlingar + match-spar
  rör inte tävlingen) · BUG-04 (Bosnien-flaggan) · BUG-05 (avskriven — bara
  om-auth) · FEAT-05 (stäng match) · D1 + D2-handoffs · plan v1–v3
