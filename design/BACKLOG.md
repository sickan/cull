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
| BUG-10 | Slug-byte vid ompublicering lämnar föräldralösa rader i live-D1 → dubblettkort (3 st städade manuellt 16/7) | **Full skrivning: design/BUGG-slug-byte-ompublicering.md.** Rot: DPT2 nytt id/slug vid ompublicering (innehall_synk) ELLER reconciling publish saknas för event-typen. Sannolikt den KONKRETA mekanismen bakom BUG-08 — tas ihop med FEAT-13 |
| HDA-a | Heldagsaktivitet-väljaren: synkade tävlingsjobb saknar tavling_id → inget gren·sport-suffix | Kräver ny länktabell (schema v29) för måttligt visningsvärde → föreslagen P2 |

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

## D · iOS

| ID | Vad | Anteckning |
|----|-----|-----------|
| iOS-trupp-2/3 | Trupp skiva 2: Vision-OCR förifyller ur uppställningsfotot · skiva 3: DPT2-reconciliation av mobilsatt roster | Skiva 1 KLAR + installerad |
| iOS-notis | Skarp notis-landning ("påminn när matchdata landat" — Stigs knapptryck end-to-end) | Kvar från design-lyftet etapp 3 |
| iOS-story | Story-text-override | Kvar från lyftet |
| iOS-lev | Leverans-progress-datakälla | Kvar från lyftet |
| FEAT-iOS-01 | Logotyp på lag i appen | Blockerare: **loggor → R2** (delas med mobil-live E2 + #27-polish) |
| FEAT-iOS-02 | SoMe-inlägg från heldagsevent i Kalendern | Blockerad: mobil render-väg (Pillow är Mac-bunden — se ML-E2) |
| FEAT-iOS-03 | Kalender som visningsläge under Fotojobb | → **D8** (design först) |
| FEAT-iOS-04 | Systemstyrt mörkt tema | Litet (samma princip som DPT2 #25) |
| B-012 | Kamerabrygga FTP: Z8 → telefon utan kortdrag (ersätter SPIKE-iOS-01) | **Design KLAR** (`ios-nef-brygga/design/PLAN-kamera-ftp.md`) — 3 skivor: FTP-motor+tester → Kameran-segment i Bilder → skarpkörning m Z8 |
| SPIKE-iOS-02 | Översyn "Matchdata klar" | Liten, ihop med notis-flödet |
| B-003 | Röst → transkribering → action | **LÅG prio (Stig 16 jul)** |
| B-008 | iPad-spike + D3-implementation | Stigs prio 4-spår |
| B-009 | Widgets (hem + låsskärm) | |
| B-010 | Låsskärm som startsida (Live Activity) | → **D6** |
| B-011 | Realtid utan batteridränering (spike) | Läs-features utbrutna till iOS-läs ovan |
| IG-schema | ev. instagram-stories://-scheme för direktdelning | Gammal ev-punkt |

## E · Webb/sajt

| ID | Vad | Anteckning |
|----|-----|-----------|
| BUG-WEB-01 | Sessioner cachas under Människor i Chrome | Utred cache-headers/stale HTML |
| FEAT-WEB-01 | Arkiv-/landningssida Ligor & Tävlingar | → **D4** |
| FEAT-WEB-02 | Arkiv-/landningssida Matcher | → **D4** |
| FEAT-WEB-03 | Nyhetsindikator "Sport" på startsidan | → **D4** |
| FEAT-WEB-04 | Standardisera mörkt tema | → **D4** |
| B-006 | Sportsidans struktur (galleri/matcher-ordning enhetlig) | → **D4** |
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
| D2 | Horisont friidrott-mallar | ✅ **SVAR INNE + IMPLEMENTERAD** |
| D3 | iPad-layout Snabbplock | ✅ **SVAR INNE** (HANDOFF-D3-SVAR-…) — väntar implementation |
| D4 | Webb-paketet (B-006 + FEAT-WEB-01…04) | ✅ **SVAR INNE** — väntar implementation |
| D5 | Lightbox-spec | ✅ **SVAR INNE** (HANDOFF-D5-SVAR-…) — väntar implementation |
| D6 | Låsskärm & widgets (UTÖKAT: B-010 + B-009) | ✅ **SVAR INNE** (HANDOFF-D6-SVAR-…) — väntar implementation |
| D7 | Startsidans kuratering (FEAT-02 + SPIKE-02) | ✅ **SVAR INNE** (HANDOFF-D7-SVAR-…) — väntar implementation |
| D8 | iOS Fotojobb-kalendervy | ✅ **SVAR INNE** (HANDOFF-D8-SVAR-…) — väntar implementation |
| D9 | Publiceringsstatus-språket | ✅ **SVAR INNE** (komplett spec: StatusChip, hörnbåge i statusfärg, filterchips ersätter flikarna, fel-expansion m per-kanal + Försök igen, puls vid bygge, autospar ersätter utkastknappen, färgtokens ljust/mörkt) — **publiceringskedjan v2 helt oblockerad** |

## Stig — användarsteg (inget kodande)

- [ ] Starta om DPT2 (v27→v28-migrering + alla pushade fixar)
- [ ] Reparera Nordea Open - ATP (typ Turnering, 13–19 jul, Båstad, arenan, kalender) — nollades av BUG-01 före fixen
- [ ] Lägg in Nordea-spelare + matcher (+ rond per match)
- [ ] Google om-auth: `https://dpt-calendar-sync.stig-johansson.workers.dev/auth/login` (gmail.send)
- [ ] Ta D2-handoffen till Claude Design
- [ ] MP-död-beslutet: väck eller radera raderaMaterial/sparaUtkast (autospar)
- [ ] C-förslagen (design/C-FORSLAG.md): besluta

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
