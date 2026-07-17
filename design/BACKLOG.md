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

## B · DPT2 — features/changes

| ID | Vad | Anteckning |
|----|-----|-----------|
| FEAT-13 | Purge/spegling av bygg-repot före publicering | ✅ **KLAR 17/7** (`1c0abe7`): reconciling publish per typ (skyddsvakt mot tom lokal DB) + radera_innehall propagerar till live |
| FEAT-09 | Auto-status efter publicering (polla → realtid, bort med manuella "Kolla status") | ✅ **KLAR 17/7** (`3972fe8`): auto-poll var 10:e sek efter publicering — bygger-puls → Live/Fel per D9 §3, Kolla status-knappen borta |
| FEAT-12 | Statusfärger + fasa ut utkastknappen (D9) | ✅ **SKIVA 1 KLAR 17/7** (`0e04977`): StatusChip + radstatus + filterchips + hörnbåge i statusfärg + Spara utkast borta. Kvar: fel-radens per-kanal-expansion (Matchpubliceringen) + Sport-vyns kort |
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
| IPTC | Leverera fas 3: IPTC-bildtexter | Sparad sedan tidigare |
| C-försl | Beslut om C-förslagen (design/C-FORSLAG.md) | Stig-beslut |
| FEAT-14 | **EPIC: Ackrediteringssvar → DPT2** (svarsmail blir förslag Beviljad/Nekad + notering i appen) | Handoff §8 senare-fas; skivor nedan |
| V2-01 | Versionsvisning i ALLA appar (bokstaverat namn "två punkt ett" synligt + tekniskt byggnr under Om/Inställningar) | v2 §1 · litet, tre kodbaser |
| V2-02 | Väderväxling "där jag är" ↔ "dit jag ska" (plats från nästa match/heldagsevent i På gång; samma tidsspann) | v2 §2 · koppling V5 §4 (destinationsväder vid deltillfälle) |
| V2-10 | Leveranskrav per uppdragsgivare sparas + visas i publiceringsflödet (ex CEV: 30 JPG, 2500×1500, ≤7 MB, efter set 1) | v2 §10 |
| V2-12 | Utrustningspackning: packmallar per eventtyp → packlista vid planering | v2 §12 · matas av V2-06-noteringar |
| V2-13 | Publiceringsstatistik: vad publicerats var, per match/event och kanal (underlag åt klubbar/sponsorer) | v2 §13 · bygger naturligt på V5 §10 publiceringskö |
| V2-17 | **EPIC: Matchlathund** — Claude-genererad matchplan (betydelse/tabelläge, spelare att följa, praktiskt, foto-inställningar ur väder, arenan/solen). Läsbar i iOS på matchdagen, PDF-export offline, skicka till mejl | v2 §17 · underlag: matchdata + väder (V2-02) + packmallar (V2-12) + egna arenanoteringar (V2-06) |

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

1. **Skiva 1 — trådspårning vid utskick:** workern returnerar Gmails
   `threadId`/`messageId` från send; schema v-next: `ackreditering.thread_id`.
   Därmed kan svar-i-tråd hittas utan gest.
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
| V5-A | **Steg A — fristående quick wins:** målmappar per flöde (Snabbplock=backup · Gallring/SSD · Generera media/Dropbox; default i Inställningar + override per körning) + original utan overlay (`namn.jpg` + `namn-original.jpg` vid varje overlay-export) | §5–6, §12 · rör INTE datamodellen — kan gå direkt |
| V5-B | **Steg B — datamodellen:** collections `liga/`, `event/` (typ=etikett, period, `pagang_lage`, grenar[], deltagare[]), `individ/`, `kategori/` (statisk toppnivå + redigerbara underkategorier); match får valfria `liga:`+`event:` (ersätter `tavling:`); migration typ liga→liga, övriga→event. Individhistorik HÄRLEDS ur eventen — skrivs aldrig | §1 · grunden för C/D/E; befintliga vyer läser `liga:` där de idag läser `tavling:` |
| V5-C | **Steg C — DPT2 Event-sektionen** (ny nav-post under Planera; lista m typfärgade badges, detaljvy m På gång-/Matcher-/Grenar-/Deltagare-kort; koppling även från matchformuläret: Liga ▾/Event ▾) + **På gång-logiken** (auto: avstånd→heldagskort, under→dagens matcher, efter→resultat; override heldag/matcher; INVARIANT: match med event visas aldrig utan "Del av {event}") | §2–3 · kräver B |
| V5-D | **Steg D — iOS v2:** restid mot NÄSTA DELTILLFÄLLE efter eventstart (+ "Sikta på annan tid"-ark: deltillfällen/eget klockslag, AUTO/VALD-badge) + dynamisk Hem-bakgrund (★-pott per sport → egen bild → standard; Inställningar-radioval + pott-grid) | §4 · kräver B + ★-flödet i V5-UX §13 |
| V5-E | **Steg E — hemsidans eventsida:** hero m typ-badge + "Pågår dag X av Y", gren-filterchips, matcher grupperade per dag (spelad→resultat+"Se bilderna", kommande→tid), gren-stapel i låsta paletten, "Del av {event}"-badge på matchkort/-sidor | §7 · kräver B; byggs ur samma data som På gång |
| V5-UX | **Etapp 2–4 UX-lyftet** (mockup `DPT v5.dc.html`): §8 jobbet som nav ("Aktivt jobb", "Efter jobb", "Publicera") · §9 Gallra som ETT flöde (Mål→Kör→Granska) + profiler (Sport/Bröllop/Landskap/Porträtt) + Träna UT ur nav (tyst träning via granskningsval, status→Inställningar) · §10 momentmallar per kategori (Landskap: Ny serie/Platsen/Bakom kulisserna/Blogg-puff; Människor: Tjuvkik/Leverans klar ENDAST vid jobb-flagga `some:true`; Film: Ny film/Stillbilder/Bakom kameran) + publiceringskö m schemaläggning (`publiceras:`) · §11 Innehåll: "Att granska"-remsa + Film-typ i typ-naven · §13 ★ iOS-bakgrund flaggas i Leverera · §14 iOS Hem per jobbtyp (landskaps-/människojobb: blå/gyllene timmen, schema ur jobbet) | varje § separat mergebar; §10 ↔ V2-13 statistik · §10 some-flaggan ↔ V2-KUND · kategorifärger topp: Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0` |

## D · iOS

| ID | Vad | Anteckning |
|----|-----|-----------|
| V2-19 | Malmö FF–Bröndby saknades i kalendervyn + väder | ✅ **LÖST 17/7** (ios `9f24628` + dpt `02410b1`): rot = formulärets datetime-local ger minutprecisa tider ("T14:00") som mobilparsern missade. Fix i BÅDA ändar (parser + `_iso_sekunder` vid källan/bron) + synlig flagga för datumlösa poster (lista + kalender-banner). **Bron-datat normaliserat live** (22 fält) → installerade appen visar matchen DIREKT, före ominstallation. Svar på öppna frågan: inlagd via DPT2 = formulärvägen, precis som rotorsaken förutsade |
| V2-16 | IG Stories-delningen felade ("går inte att skicka filen") | ✅ **LÖST 17/7** (ios `9f24628`): `instagram-stories://`-schemat + bilddata på pasteboarden ersätter fil-URL-ShareLink; + "Spara till Bilder"-knapp (interim & permanent fallback); generiska arket kvar som "Dela på annat sätt". **Kräver appinstallation** — oskarpkört mot riktiga Instagram |
| V2-05 | Förhandsgranskningen utanför synfältet | ✅ **LÖST 17/7** (ios `9f24628`): autoscroll till preview-sektionen när renderingen landar |
| V2-20 | **Verifiera SoMe-flödet för friidrott FÖRE Friidrotts-SM 24–26/7 (Uppsala):** moment (Grenstart · Försök/Kval · Final · Resultat · Rekord SM/PB · Nästa gren/pass) · overlay = resultat per gren (tider "10,42", höjder "2,01 m", placeringar) INTE ställningssiffror · vyer + matchfakta-pålägget får inte anta två lag (mästerskap = heldagsevent m många grenar/aktiva) | v2 §20 · P15-fixen (tennis) är grunden; deadline-styrd |
| V2-06 | Noteringar på event/matcher: snabbt i iOS under eventet, utförligt i DPT2 efteråt; sökbara vid planering av liknande event | v2 §6 · iOS+DPT2 · **BESLUT (Stig 17/7): TVÅVÄGS synk iOS ↔ DPT2** · matar V2-12 packning + V2-17 lathundens arenadel |
| V2-11 | Filmlogg: rulle i vilken kamera, exponeringsanteckningar, status (i kamera/hos lab/skannad), kopplad till frysinventariet | v2 §11 · iOS+DPT2 |
| V2-18 | Nyckelspelare → publiceringsflödet: lathundens "spelare att följa" blir objekt m storyline per match → snabbval vid bildval/SoMe + overlay-text kombinerar händelse + kontext ("mål i sin första match för MFF!") | v2 §18 · bygger på V2-17; samma JSON som Damallsvenskan-research |
| iOS-trupp-2/3 | Trupp skiva 2: Vision-OCR förifyller ur uppställningsfotot · skiva 3: DPT2-reconciliation av mobilsatt roster | Skiva 1 KLAR + installerad |
| iOS-notis | Skarp notis-landning ("påminn när matchdata landat" — Stigs knapptryck end-to-end) | Kvar från design-lyftet etapp 3 |
| iOS-story | Story-text-override | Kvar från lyftet |
| iOS-lev | Leverans-progress-datakälla | Kvar från lyftet |
| FEAT-iOS-01 | Logotyp på lag i appen | Blockerare: **loggor → R2** (delas med mobil-live E2 + #27-polish) |
| FEAT-iOS-02 | SoMe-inlägg från heldagsevent i Kalendern | Blockerad: mobil render-väg (Pillow är Mac-bunden — se ML-E2) |
| FEAT-iOS-03 | Kalender som visningsläge under Fotojobb | ✅ **SKIVA 1 KLAR 17/7** (ios `99973cd`): Lista\|Kalender-segment, månadsgrid + dag-panel, Kalender-fliken BORT (4 flikar). Skiva 2 kvar: deadline-ringar + krock (kräver /api/jobb-data) |
| FEAT-iOS-04 | Systemstyrt mörkt tema | Litet (samma princip som DPT2 #25) |
| B-012 | Kamerabrygga FTP: Z8 → telefon utan kortdrag (ersätter SPIKE-iOS-01) | **Design KLAR** (`ios-nef-brygga/design/PLAN-kamera-ftp.md`) — 3 skivor: FTP-motor+tester → Kameran-segment i Bilder → skarpkörning m Z8 |
| SPIKE-iOS-02 | Översyn "Matchdata klar" | Liten, ihop med notis-flödet |
| B-003 | Röst → transkribering → action | **LÅG prio (Stig 16 jul)** |
| B-008 | iPad-spike + D3-implementation | Stigs prio 4-spår |
| B-009 | Widgets (hem + låsskärm) | |
| B-010 | Låsskärm som startsida (Live Activity) | → **D6** |
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
| W-friidrott | Verifiera att Mästerskap/kategori+Friidrott-sajtkoden är deployad (var "EJ deployat" 14/7) | Status osäker — kolla |
| V2-04 | Mobil sport-layout: tidig liten "nästa event"-notis m ankarlänk ner till På gång-sektionen (ordningen behålls; desktop är rätt) | v2 §4 · litet, ovanpå D4-leveransen |
| V2-08 | Presskort (Svenska Journalistförbundet + IFJ) under Om + standardiserad mejlsidfot (kontakt, länkar, presskortsinfo) — gäller även ackrediterings- och V2-KUND-mejlen | v2 §8 · exakt formulering = copyarbete (öppen) |
| V2-09 | Tjänstesektion m ingångar från startsida + nav: Sport (match/lagfoto/dokumentation/bildbyrå) · Människor (bröllop/student/dop/porträtt/familj/djur) · Kommersiellt (produkt/mode/artister) · Landskap (urval + försäljning) | v2 §9 · bildbyrån ev. egen ingång (annan målgrupp); mappar mot V5-kategoritoppnivån + temana Hav/Rosé/Sol |

## F · Mobil-live

| ID | Vad | Anteckning |
|----|-----|-----------|
| ML-E1-skarp | Etapp 1 skarpkörning telefon↔desktop under riktig match | Byggd, ej skarpkörd |
| ML-E2 | Etapp 2: publicera stories utan Macen (Browser Rendering-inriktning) | Blockerare: **loggor → R2** · låser upp FEAT-iOS-02 |

## G · Spikes DPT2

SPIKE-01 importera spelschema (URL/fil) · SPIKE-03 ML/modell-bibliotek ·
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
