# Plan — Tennis · iOS telefon · Friidrott · iPad

*Uppdaterad 2026-07-16 (v3): Stigs backlog från användning 15–16 jul insynkad
(claude_code_backlog.md: BUG-01…08, FEAT-01…13, SPIKE-01…07, iOS + webb).
Arbetsmodell oförändrad: **alla UX/UI/mall-frågor bryts ut som Design-jobb** —
prototyper i Claude Design, landat resultat kommer tillbaka hit som handoff.
Levande dokument.*

## Prioritering (Stigs ordning)

1. **Tennis** — Nordea Open, NU i helgen (Båstad)
2. **iOS telefon** — fältflödena i appen
3. **Friidrott** — Friidrotts-SM **24–26/7** (Uppsala)
4. **iOS iPad** — Snabbplock bredvid LR Mobile

---

## DESIGN-SPÅRET — jobb till Claude Design

| ID | Jobb | Innehåll | Status / behövs till |
|----|------|----------|----------------------|
| ~~**D1**~~ | ~~Horisont tennis-mall~~ | Levererad + implementerad (`16d4420`) | ✅ KLAR |
| **D2** | **Horisont friidrott-mallar** (B-002) | Gren+moment, idrottarnamn, resultat per grentyp. D1-svarets "Blick mot D2" är starten. | **AKUT — före 24/7** |
| **D3** | iPad-layout Snabbplock (B-008) | Plockgrid + previews bredvid LR Mobile, size classes | Prio 4 |
| **D4** | **Webb-paketet** (UTÖKAT) | B-006 sportsidans struktur (galleri/matcher-ordning) **+ FEAT-WEB-01/02 arkiv-/landningssidor för Ligor & Tävlingar resp. Matcher + FEAT-WEB-03 nyhetsindikator "Sport" på startsidan + FEAT-WEB-04 standardisera mörkt tema**. Ett sammanhållet paket — samma sidfamilj. | P2 |
| **D5** | Lightbox-spec (B-007) | Overlay, pil/svep, Esc, bildtext | P2 |
| **D6** | Låsskärm/Live Activity (B-010) | Kompakt + expanderad + Dynamic Island | P3 |
| **D7** *(ny)* | **Startsidans kuratering** | FEAT-02 "Featured"-logik (märk tävling/match → prio på startsidan) + SPIKE-02 visningslogik (Idag vs Framtiden). Produktfråga: vad visas när, hur slår Featured igenom. | P2 |
| **D8** *(ny)* | **iOS Fotojobb-kalendervy** | FEAT-iOS-03: kalender som visningsläge under Fotojobb i appen | P2 |

*Ej design-jobb (Stig har redan specat / trivialt):* FEAT-12 statusfärger
(blå/gul/grön/röd — färgerna givna), FEAT-04 större färgklickar, FEAT-06
skiljelinje för dolda jobb, FEAT-10/11 galleri-sökvägs-UI. → Code direkt.

---

## CODE-SPÅRET

### P0 — akut (helgen / pågående event)

- [x] ~~D1 tennis-overlay~~ + turneringskanal-buggen + profildrivet startord (PUSHAT `16d4420`)
- [ ] **BUG-04 Bosnien & Hercegovina-flaggan** — alias-miss i `lander.js`
      (Intl: "och", laget: "&"). Minutfix. *Sverige–Bosnien ligger live.*
- [ ] **BUG-01 Tävlingar med samma namn skriver över varandra** — `upsert_tavling`
      sluggar på namn → "European League 2026" dam raderar herr. Unicitet =
      namn+gren+sport (id-baserad). **Tennis-relevant nu** (Nordea dam/herr).
      Måste ta hänsyn till befintliga referenser (matchen.tavling_id).
- [ ] **BUG-05 gmail.send** — INGEN kodbugg: scopet finns i deployade tjänsten.
      **Stigs steg:** om-auktorisera Google via calendar-sync `/auth/login`.
- [ ] **FEAT-05 "Stäng match"** — explicit stänga aktiv match (litet, fältnytta).

### Prio 2 — iOS telefon

- [ ] **B-003 Röst → action:** inspelning → transkribering → Claude-tolkning →
      bekräftelsevy → händelse. Grundflöde före SM, trimmas efter.
- [ ] **FEAT-iOS-04 systemstyrt mörkt tema** (samma princip som DPT2 #25). Litet.
- [ ] **FEAT-iOS-01 logotyp på lag** — hänger på loggor→R2 (känd blockerare,
      samma väg som #27-polish backend-flaggor). Medel.
- [ ] FEAT-iOS-02 SoMe från heldagsevent i Kalendern — kräver mobil render-väg
      (mobil-live etapp 2-spiken: Pillow-renderaren är Mac-bunden) → P3 tills
      render-frågan är löst.
- [ ] SPIKE-iOS-02 översyn "Matchdata klar" (litet, ihop med push-flödet).

### Prio 3 — Friidrott (SM 24–26/7)

- [ ] **B-001 Deltagarhantering:** Event → Deltagare → Grenar (m2m). Admin-UI i
      DPT2 (befintligt mönster), API/synk till appen. = skivan av #29.
      *Deadline: före avresa.*
- [ ] **B-002/D2-implementation:** friidrotts-mallarna in i overlay-motorn
      (grentyp → etiketter/resultatformat). *Beroende: B-001 + D2.*
- [ ] **B-003-trim** för friidrott ("Karlsson 6,42 i tredje hoppet").

### Prio 4 — iOS iPad

- [ ] **B-008 spike** (universal vs uppskalad, Split View) → **D3-implementation**.

### P2 — Publiceringskedjan v2 (temapaket — efter SM)

*Rotorsaks-kluster: dubbletterna och otydlig status är sannolikt samma
pipeline-problem. FEAT-13 först — den kan lösa BUG-06/08 på köpet.*

- [ ] **FEAT-13 Purge/spegling av bygg-repot** — raderade DPT2-objekt ligger
      kvar i repot och följer med ut. Strikt clean före generering + validerad
      tillståndssynk. **Trolig rotorsak till BUG-06/BUG-08.**
- [ ] **BUG-08** dubbletter Människor vid ompublicering (om ej löst av FEAT-13)
- [ ] **BUG-06** dubbletter "Publicerat"-katalogen — spegla exakt det som är live
- [ ] **BUG-07** dubbletter Utkast — utred version vs bugg; gruppera eller rensa
- [ ] **FEAT-08** avpublicera match/tävling från DPT2 (raderaflöde finns för
      vissa typer — utöka)
- [ ] **FEAT-09** auto-status efter publicering (polla → realtid, bort med
      manuella "Kolla status")
- [ ] **FEAT-12** statusfärger 🔵utkast 🟡publicerad 🟢live 🔴fel + fasa ut
      utkastknappen (färgerna specade av Stig — code direkt; bygger på FEAT-09)

### P2 — övrigt DPT2/webb

- [ ] **B-004 Enhetligt skapa/ändra** (absorberar #26 id-uppslag, B-005
      "Ny"-buggen, FEAT-07 varning vid radering av länkade objekt — och
      BUG-01-mönstret långsiktigt)
- [ ] **BUG-02** döda kort under "Tidigare projekt" i Matcher
- [ ] **BUG-03** färgklickar på Fotojobb uppdateras inte reaktivt
- [ ] **FEAT-01** drag-n-drop för bilder (Innehåll/galleri)
- [ ] **FEAT-03** rich text i ackrediteringsmallen (formaterad text + länkar)
- [ ] Småputs (code direkt): **FEAT-04** större färgklickar · **FEAT-06**
      skiljelinje för dolt jobb i sportfilter · **FEAT-10** sökvägs-UI i galleri
      (mindre typsnitt, trunkera med `…/`, filnamn ovanför bilden) · **FEAT-11**
      kopiera mappsökväg-knapp
- [ ] **BUG-WEB-01** sessions-cache under Människor i Chrome (utred cache-headers/
      stale HTML)
- [ ] D4/D5/D7/D8-implementation när handoffs landar
- [ ] Heldagsaktivitet-rest: (a) tävlings-ref på synkade jobb, (b) filtrera
      Ackreditering-jobb ur väljaren
- [ ] #27-polish: backend-flagghärledning (renderare + iOS) + vajande vimpel
      (delar väg med FEAT-iOS-01 loggor→R2)

### P3 — senare

- [ ] **Spikes DPT2:** SPIKE-01 importera spelschema (URL/fil) · SPIKE-03
      ML/modell-bibliotek · SPIKE-04 PM-mapp · SPIKE-05 platshållare i ML-bildvyer ·
      SPIKE-06 push-notiser/kanaler i Inställningar · SPIKE-07 galleri-sökvägar
      (SPIKE-02 flyttad in i D7)
- [ ] **SPIKE-iOS-01** trådlös Nikon Z8 (stor)
- [ ] FEAT-iOS-02 (när mobil render-väg finns)
- [ ] B-009 widgets · B-010/D6 låsskärm · B-011 realtid/batteri-spike
- [ ] Moln-som-sanning-utbyggnad (arkitekturspecen)

---

## Track 0 + Tennis — ✅ LANDAT & PUSHAT

- Track 0 (`e56a9d0..3cdcb4b`): #23/#24/#25, #27 flagga, #28, sportevent↔tävling,
  heldagsaktivitet. **Kräver DPT2-omstart.**
- Tennis (`c028fd7..16d4420`): profildriven motor, turneringskanal-fixen,
  D1-overlayn, schema v28 (rond). **Omstart migrerar v27→v28.**

## Nyckelkopplingar (så inget dubbeljobbas)

| Nytt | Kopplar till |
|------|--------------|
| BUG-01 unika tävlingar | #26 id-uppslag, B-004 entitetsidentitet |
| BUG-04 Bosnien-flaggan | #27 lander.js (alias) |
| BUG-06/07/08 + FEAT-08/09/12/13 | ETT pipeline-tema — FEAT-13 är roten |
| FEAT-02 + SPIKE-02 | D7 startsidans kuratering |
| FEAT-WEB-01…04 + B-006 | D4 webb-paketet |
| FEAT-iOS-01 loggor | #27-polish, loggor→R2-blockeraren |
| FEAT-iOS-02 | mobil-live etapp 2-spiken (render Mac-bunden) |

## Nästa steg

1. **Code nu:** BUG-04 (minuter) → BUG-01 (tennis-kritisk) → FEAT-05.
2. **Design:** dra igång **D2 (friidrott)** — deadline 24/7. D4-paketet + D7/D8
   när D2 är i hamn.
3. **Stig:** DPT2-omstart (v28) · lägg in Nordea-spelare/matcher · om-auktorisera
   Google för ackr-mail (BUG-05 = bara det).
