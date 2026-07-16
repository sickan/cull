# TOTAL BACKLOG — DPT2 · iOS · Webb

*Skapad 2026-07-16. ENDA SANNINGEN för allt öppet arbete — konsoliderar Stigs
båda listor (B-001…011 + BUG/FEAT/SPIKE 15–16 jul), alla öppna trådar ur
tidigare sessioner och dagens fynd. Prioriteras GEMENSAMT (görs härnäst);
`PLAN-nordea-friidrott.md` blir prio-vyn ovanpå den här.*

*Arbetssätt: agilt och iterativt — leverera värde löpande i små, testade,
robusta skivor. Vänta aldrig på att allt är klart.*

**Stigs prio-signaler (16 jul):** ① buggar generellt först — särskilt att
Innehåll inte känns robust (= dubbletterna/publiceringskedjan) · ② iOS
trupp/startelvor inför FOTBOLLSHELGEN · ③ tennis under veckan · ④ B-003
röst→action är LÅG prio.

---

## A · DPT2 — buggar

| ID | Vad | Källa/anteckning |
|----|-----|------------------|
| BUG-03 | Färgklickar på Fotojobb uppdateras inte reaktivt (kräver flikbyte) | **KAN EJ REPRODUCERAS i mock** — hela kedjan verifierad färsk (D1 skrivs synkront, ingen klient-cache, laddaOm körs). Behöver Stigs exakta repro: vilken åtgärd + vilken färgklick |
| BUG-06 | Dubbletter i "Publicerat"-katalogen — ska spegla exakt det som är live | Stigs lista · trolig rot: FEAT-13 |
| BUG-07 | Dubbletter under "Utkast" — version vs bugg? Gruppera eller rensa | Stigs lista |
| BUG-08 | Dubbletter under Människor vid ompublicering | Stigs lista · trolig rot: FEAT-13 |
| HDA-a | Heldagsaktivitet-väljaren: synkade tävlingsjobb saknar tavling_id → inget gren·sport-suffix | Kräver ny länktabell (schema v29) för måttligt visningsvärde → föreslagen P2 |
| MP-död | Matchpub död kod: `MatchHuvud.svelte` + oanropade `oppnaILightroom`/`raderaMaterial`/`hamtaUtkast`/`sparaUtkast` — de två sista kan vara TAPPADE funktioner (materialradering, autospar). **Beslut Stig:** väck eller radera | Matchpub-regressionen |

## B · DPT2 — features/changes

| ID | Vad | Anteckning |
|----|-----|-----------|
| FEAT-13 | Purge/spegling av bygg-repot före publicering | **Rotorsak-kandidat för BUG-06/08** — tas först i publiceringskedjan |
| FEAT-09 | Auto-status efter publicering (polla → realtid) | Bygger mot FEAT-12 |
| FEAT-12 | Statusfärger 🔵utkast 🟡publicerad 🟢live 🔴fel + fasa ut utkastknappen | Färger specade av Stig → code direkt |
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

## C · Event/deltagare (friidrott m.m.)

| ID | Vad | Anteckning |
|----|-----|-----------|
| B-001 | Deltagarhantering: Event → Deltagare → Grenar (m2m), admin-UI, API till iOS | **Deadline före 24/7** · = skivan av #29 gruppera-under-tävling |
| B-002 | Friidrotts-overlays i motorn (grentyp → etiketter/resultatformat) | Beroende: B-001 + **D2** (handoff ute) |

## D · iOS

| ID | Vad | Anteckning |
|----|-----|-----------|
| iOS-trupp | Trupp/startelva från arenan | **SKIVA 1 KLAR 16/7** (TruppView: foto-referens + tap-startelva + stryk ur trupp; PUT /roster deployad; ios `e0e6472`). KVAR: installera på telefonen (kräver upplåst lur) + **skiva 2: Vision-OCR förifyller ur fotot** + skiva 3: DPT2-reconciliation av mobilsatt roster |
| iOS-läs | Läs-features ur arkitekturspecen: **väder-aggregat per dag + restid/"när måste jag åka"** (MapKit) | Stigs "väder, kör nu" — lyft ur B-011/P3 |
| iOS-notis | Skarp notis-landning ("påminn när matchdata landat" — Stigs knapptryck end-to-end) | Kvar från design-lyftet etapp 3 |
| iOS-story | Story-text-override | Kvar från lyftet |
| iOS-lev | Leverans-progress-datakälla | Kvar från lyftet |
| FEAT-iOS-01 | Logotyp på lag i appen | Blockerare: **loggor → R2** (delas med mobil-live E2 + #27-polish) |
| FEAT-iOS-02 | SoMe-inlägg från heldagsevent i Kalendern | Blockerad: mobil render-väg (Pillow är Mac-bunden — se ML-E2) |
| FEAT-iOS-03 | Kalender som visningsläge under Fotojobb | → **D8** (design först) |
| FEAT-iOS-04 | Systemstyrt mörkt tema | Litet (samma princip som DPT2 #25) |
| SPIKE-iOS-01 | Trådlös kommunikation Nikon Z8 | Stor utredning |
| SPIKE-iOS-02 | Översyn "Matchdata klar" | Liten, ihop med notis-flödet |
| B-003 | Röst → transkribering → action | **LÅG prio (Stig 16 jul)** |
| B-008 | iPad-spike + D3-implementation | Stigs prio 4-spår |
| B-009 | Widgets (hem + låsskärm) | |
| B-010 | Låsskärm som startsida (Live Activity) | → **D6** |
| B-011 | Realtid utan batteridränering (spike) | Läs-features utbrutna till iOS-läs ovan |
| IG-schema | ev. instagram-stories://-scheme för direktdelning | Gammal ev-punkt |
| iOS-remote | **ios-nef-brygga saknar git-remote** — backup-risk för hela appen | Infra, billig försäkring |

## E · Webb/sajt

| ID | Vad | Anteckning |
|----|-----|-----------|
| BUG-WEB-01 | Sessioner cachas under Människor i Chrome | Utred cache-headers/stale HTML |
| FEAT-WEB-01 | Arkiv-/landningssida Ligor & Tävlingar | → **D4** |
| FEAT-WEB-02 | Arkiv-/landningssida Matcher | → **D4** |
| FEAT-WEB-03 | Nyhetsindikator "Sport" på startsidan | → **D4** |
| FEAT-WEB-04 | Standardisera mörkt tema | → **D4** |
| B-006 | Sportsidans struktur (galleri/matcher-ordning enhetlig) | → **D4** |
| B-007 | Lightbox i gallerier (Sport/Landskap/Människor/Film) | → **D5** |
| W-friidrott | Verifiera att Mästerskap/kategori+Friidrott-sajtkoden är deployad (var "EJ deployat" 14/7) | Status osäker — kolla |

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

## Design-jobb (Claude Design)

| ID | Vad | Status |
|----|-----|--------|
| D2 | Horisont friidrott-mallar | **HANDOFF UTE** (design/HANDOFF-D2-…) — deadline före 24/7 |
| D3 | iPad-layout Snabbplock | **HANDOFF UTE** (HANDOFF-D3-…) |
| D4 | Webb-paketet (B-006 + FEAT-WEB-01…04) | **HANDOFF UTE** (HANDOFF-D4-…) |
| D5 | Lightbox-spec | **HANDOFF UTE** (HANDOFF-D5-…) |
| D6 | Låsskärm & widgets (UTÖKAT: B-010 + B-009) | **HANDOFF UTE** (HANDOFF-D6-…) |
| D7 | Startsidans kuratering (FEAT-02 + SPIKE-02) | **HANDOFF UTE** (HANDOFF-D7-…) |
| D8 | iOS Fotojobb-kalendervy | **HANDOFF UTE** (HANDOFF-D8-…) |
| D9 | Publiceringsstatus-språket (FEAT-12/09 UI — hur/var status visas) | **HANDOFF UTE** (HANDOFF-D9-…) — behövs före FEAT-12-bygget |

## Stig — användarsteg (inget kodande)

- [ ] Starta om DPT2 (v27→v28-migrering + alla pushade fixar)
- [ ] Reparera Nordea Open - ATP (typ Turnering, 13–19 jul, Båstad, arenan, kalender) — nollades av BUG-01 före fixen
- [ ] Lägg in Nordea-spelare + matcher (+ rond per match)
- [ ] Google om-auth: `https://dpt-calendar-sync.stig-johansson.workers.dev/auth/login` (gmail.send)
- [ ] Ta D2-handoffen till Claude Design
- [ ] MP-död-beslutet: väck eller radera raderaMaterial/sparaUtkast (autospar)
- [ ] C-förslagen (design/C-FORSLAG.md): besluta

## ✅ Levererat nyligen (rörligt — flyttas hit när klart)

- 16 jul em (steg 1): BUG-09 (gren·sport i koppla-chips/-lista) · #26-rest
  (id-baserade lag-uppslag i matchdaguttaget) · BUG-02 (Tidigare projekt-korten
  aktiverar nu urvalet → Leverera) · HDA-b (Ackreditering-filter)
- 15–16 jul: Track 0 (#23 #24 #25 · #27 flagga · #28 · sportevent↔tävling ·
  heldagsaktivitet-fixen) · tennis-paketet (profildriven motor, turneringskanal-
  buggen, D1-overlayn, schema v28 rond) · BUG-01 (unika tävlingar + match-spar
  rör inte tävlingen) · BUG-04 (Bosnien-flaggan) · BUG-05 (avskriven — bara
  om-auth) · FEAT-05 (stäng match) · D1 + D2-handoffs · plan v1–v3
