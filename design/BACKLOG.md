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
| BUG-CULL-02 | Handsatt poängformel är **rent fotbollsspecifik** — tennis/friidrott/övrigt gallras med fel signaler | **BEKRÄFTAD.** `poangsatt_handsatt` väger armar (jubel), boll, hemmafärg, tröjnummer, klunga, matchfas (minut-sedan-avspark), väst-straff, firande-boost — alla fotboll. `poangsatt_med_modell` ÄR sport-medveten (sport_modeller), men når aldrig fram pga BUG-CULL-01. Behöver sport-neutral fallback + ev. sportprofil för handsatta vikter (jfr V5 sportprofil). Blockeras delvis av CULL-01 |
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
| V2-01 | Versionsvisning i ALLA appar (bokstaverat namn "två punkt ett" synligt + tekniskt byggnr under Om/Inställningar) | v2 §1 · litet, tre kodbaser |
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
| V5-UX | **Etapp 2–4 UX-lyftet**: **§10 SKIVA 1 KLAR 18/7** (`pass4`): publiceringskön — v35 `publiceras`-fält, schemafält vid Spara utkast, kön sorterar schemalagda överst m "Dags att publicera"-puls när tiden passerat (manuell påminnelse per handoffen; momentmallar per kategori = nästa skiva, kräver jobbkontext i panelen) · **§8 ✅ KLAR 18/7** (`8692312` main): "Aktivt jobb"-chip+remsa, "Efter jobb", "Publicera", Träna ur nav · **§9 RAM KLAR 18/7** (samma commit): stegindikator Mål→Kör→Granska, profilkort (4 profiler m signal-chips, förval ur jobbet, `profil` följer med cull-config åt CULL-02), Träna→Inställningar-rad (inbäddad panel). **§9-rest:** tyst träning kräver per-bild Behåll/Släng-UI i granskningen (finns ej ännu — egen skiva, hänger ihop m Leverera-urvalsvyn) · §10 momentmallar per kategori (Landskap: Ny serie/Platsen/Bakom kulisserna/Blogg-puff; Människor: Tjuvkik/Leverans klar ENDAST vid jobb-flagga `some:true`; Film: Ny film/Stillbilder/Bakom kameran) + publiceringskö m schemaläggning (`publiceras:`) · §11 Innehåll: "Att granska"-remsa + Film-typ i typ-naven · §13 ★ iOS-bakgrund flaggas i Leverera · §14 iOS Hem per jobbtyp (landskaps-/människojobb: blå/gyllene timmen, schema ur jobbet) | varje § separat mergebar; §10 ↔ V2-13 statistik · §10 some-flaggan ↔ V2-KUND · kategorifärger topp: Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0` |

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
| iOS-trupp-2/3 | Trupp skiva 2: Vision-OCR förifyller ur uppställningsfotot · skiva 3: DPT2-reconciliation av mobilsatt roster | **Skiva 2 ✅ KLAR 18/7** (ios `c65f70a`, INSTALLERAD): "Läs uppställningen ur bilden"-knapp → Vision-OCR (sv/en, utan språkkorrektion) → ren matchningslogik (efternamn+nr, Levenshtein-tolerans, efternamnskrock→osäkra, nakna nummer bär aldrig bevisvikt) → obligatoriskt granskningsark → fyller startelvan. 10 tester (31 gröna). Skiva 3 kvar |
| iOS-notis | Skarp notis-landning ("påminn när matchdata landat" — Stigs knapptryck end-to-end) | Kvar från design-lyftet etapp 3 |
| iOS-story | Story-text-override | Kvar från lyftet |
| iOS-lev | Leverans-progress-datakälla | Kvar från lyftet |
| FEAT-iOS-01 | Logotyp på lag i appen | ✅ **LÖST 18/7 av IB-3** (ios `c1791c0`) — R2-vägen fanns redan serverside; appen renderar nu URL:erna |
| FEAT-iOS-02 | SoMe-inlägg från heldagsevent i Kalendern | Blockerad: mobil render-väg (Pillow är Mac-bunden — se ML-E2) |
| FEAT-iOS-03 | Kalender som visningsläge under Fotojobb | ✅ **SKIVA 1 KLAR 17/7** (ios `99973cd`): Lista\|Kalender-segment, månadsgrid + dag-panel, Kalender-fliken BORT (4 flikar). Skiva 2 kvar: deadline-ringar + krock (kräver /api/jobb-data) |
| FEAT-iOS-04 | Systemstyrt mörkt tema | Litet (samma princip som DPT2 #25) |
| B-012 | Kamerabrygga FTP: Z8 → telefon utan kortdrag (ersätter SPIKE-iOS-01) | **Design KLAR** (`ios-nef-brygga/design/PLAN-kamera-ftp.md`) — 3 skivor: FTP-motor+tester → Kameran-segment i Bilder → skarpkörning m Z8 |
| SPIKE-iOS-02 | Översyn "Matchdata klar" | Liten, ihop med notis-flödet |
| B-003 | Röst → transkribering → action | **LÅG prio (Stig 16 jul)** |
| B-008 | iPad-spike + D3-implementation | Stigs prio 4-spår |
| B-009 | Widgets (hem + låsskärm) | |
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
| M18-1 | Startelva-overlayn ritar inte spelarnamnen — bara rubriken "startelva" | Trolig: rostern når inte renderaren (spec-bygget i workern skickar inte roster till skapa_story, eller lineup-grenen läser fel nyckel). Felsök hela kedjan app→worker→render |
| M18-6 | Snabbplockade bilder går inte att återfinna i Lightroom mobil — flödet BRUTET | Hög prio. Öppen designfråga: eget album/mapp som LR ser, kopierbar filnamnslista, eller tumnaglar m filnamn i plockordning |
| M18-2 | Klockmodulen: manuell tidssynk mot hallens matchur ("sätt matchtid": skriv 07:32 → synka; inte +/−) | Täcker sen avspark + utdragna pauser. Paket med M18-4/5 |
| M18-4 | Tilläggstid + räkning per halvlek (fotboll): 0–45 → 45+X; 2:a halvlek STARTAR alltid 45:00 → 90 → 90+X; händelser loggas "45+2"; "Starta andra halvlek" = synkpunkt som nollar till 45:00 | Klockmodul-paketet |
| M18-5 | Automatisk halvleksdetektering ur klockslaget (0–45 = första; efter ~60 min = andra) — följer manuell synk när den finns | Klockmodul-paketet |
| M18-3 | Snabbredigering av mål: korrigera minut/målskytt direkt på händelsen i matchflödet (utan ta bort + lägg om) | Hänger ihop m klocksynken (fel minuter) men behövs oavsett |
| M18-8 | Gradienten över loggorna för kraftig — MFF-märket äts upp | Tona ner opacitet eller korta räckvidden (var? overlay-rendern eller appens brickor — verifiera vilken yta han såg) |
| M18-9 | Automatisk HEMRESA efter match: som resan till, default Kajgatan 2B Lomma; överstyrbar (nästa uppdrag/hotell) — enkel inmatning i matchvyn/inställningar | Restidsinfran finns (RestidService); hemadress = ny inställning |

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
