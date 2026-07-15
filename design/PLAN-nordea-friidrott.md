# Plan — Tennis · iOS telefon · Friidrott · iPad

*Uppdaterad 2026-07-15. Konsoliderar backloggen (B-001…B-011) med öppna trådar
från pågående arbete. Arbetsmodell: **alla UX/UI/mall-frågor bryts ut som
Design-jobb** — prototyper & förslag tas fram i Claude Design, det vi landar i
kommer tillbaka hit som handoff och implementeras av Code. Levande dokument.*

## Prioritering (Stigs ordning)

1. **Tennis** — Nordea Open, i helgen (Båstad)
2. **iOS telefon** — fältflödena i appen
3. **Friidrott** — Friidrotts-SM **24–26/7** (Uppsala)
4. **iOS iPad** — Snabbplock med arbetsyta bredvid LR Mobile

## Bärande principer

1. **Sport-medvetenhet är ryggraden.** `data/sportprofil.py` finns redan
   (fotboll → tennis → friidrott: res_label, has_scorers, squad, individ).
   Code bygger overlay-motorn **datadriven av profilen en gång** — Designs
   mallar per sport blir då konfig/layout, inte ny kod per sport.
2. **Design och Code går parallellt.** Code bygger motor/datamodell medan
   Design tar fram mallarna — handoffen kopplas in när den landar.
3. **Moln = sanning** (arkitekturspecen) är målbild för event-strukturen —
   vi bygger minsta användbara skiva per deadline, inte hela specen.

---

## DESIGN-SPÅRET — jobb till Claude Design

*Prototyper & förslag tas fram där; det vi landar i kommer tillbaka hit.
Ordnade efter prio ovan.*

| ID | Jobb | Innehåll | Behövs till |
|----|------|----------|-------------|
| **D1** | **Horisont tennis-mall** | Overlay-varianter för tennis: spelarnamn som primär rad, rond/omgång ("Åttondel", "Semifinal") i st f "Avspark", set-resultat. Samma 6 tillstånd/3 teman som fotbolls-Horisont. | **Nordea Open (helgen)** |
| **D2** | **Horisont friidrott-mallar** (B-002) | Gren + moment ("Längd — kval", "Tresteg — final"), idrottarnamn primärt, resultat efter grentyp (längd/tid/höjd). Definiera grentyp→resultatformat-tabellen. | **Friidrotts-SM 24/7** |
| **D3** | **iPad-layout Snabbplock** (del av B-008) | Hur Snabbplock nyttjar iPad Air-ytan: plockgrid + previews bredvid LR Mobile (Split View/Stage Manager). Kompakt/regular size classes. | iPad-spåret (prio 4) |
| **D4** | **Sportsidans struktur** (B-006) | Enhetlig ordning galleri/matcher: förslag galleri vänster + matcher höger (desktop), definiera mobilordning. Samma struktur Sport + alla undersidor. | P2 |
| **D5** | **Lightbox-spec** (B-007) | Overlay, pilnavigering (tangentbord/svep), stäng-beteende, ev. bildtext. Lätt spec. | P2 |
| **D6** | **Låsskärm/Live Activity** (B-010) | Vad får plats: kompakt + expanderad + Dynamic Island. Bär även restid/väder (B-011). | P3 |

*Ej design-jobb:* B-001-admin-UI:t (deltagare) följer befintligt
Lag & tävlingar-mönster i DPT2 — Code direkt. Röst→action-bekräftelsevyn (B-003)
börjar enkel — designlyft senare vid behov.

---

## CODE-SPÅRET

### Prio 1 — Tennis (Nordea Open, helgen)

Tennis är till stor del byggt (individmatch, turnering, turnerings-SoMe v26 —
pushat). Luckan är overlayn + skarp verifiering.

- [ ] **Verifiera turneringsflödet skarpt:** Nordea Open-tävling → sportevent
      binds → matcher fylls → publicera webb + På gång.
- [ ] **Datadriven overlay-motor:** gör Horisont-fälten profildrivna
      (individ, res_label, moment-etiketter) så D1-mallen kan kopplas in
      direkt när den landar. *Byggs parallellt med D1.*
- [ ] **Koppla in D1** när handoffen landar.
- [ ] *Nice-to-have:* restid/väder Båstad (koordinat finns redan i appen).

### Prio 2 — iOS telefon

- [ ] **Tennis-story i appen:** minsta väg foto → overlay (D1) → dela IG med
      tennis-fälten. Hub/MÅL-flödet är fotbollstänkt — inte hela live-flödet nu.
- [ ] **B-003 Röst → action:** inspelningsknapp (en tryckning) → transkribering
      → Claude tolkar → strukturerad händelse → bekräftelsevy → spara.
      "Karlsson 6,42 i tredje hoppet" / "Mål av Johansson 22 i 34:e".
      Grundflödet först — trimmas efter SM.
- [ ] Kvar från design-lyftet: skarp notis-landning, story-text-override,
      leverans-progress-datakälla.

### Prio 3 — Friidrott (SM 24–26/7)

- [ ] **B-001 Deltagarhantering:** datamodell Event → Deltagare → Grenar
      (m2m — en deltagare i flera grenar, t.ex. Längd + Tresteg). Admin-UI i
      DPT2 (befintligt mönster). API/synk så iOS hämtar deltagarlista per
      event → snabb koppling deltagare → story-overlay på plats.
      **Är den konkreta skivan av #29 event-struktur.**
      *Deadline: klart och testat före avresa.*
- [ ] **B-002 Implementation:** koppla in D2-mallarna i overlay-motorn
      (grentyp styr etiketter + resultatformat). *Beroende: B-001 + D2.*
- [ ] **B-003-trim för friidrott** (grenar/resultat i rösttolkningen).

### Prio 4 — iOS iPad

- [ ] **B-008 Spike:** universal app vs uppskalad iPhone-app, layoutbehov,
      Split View/Stage Manager bredvid LR Mobile. Rekommendation + estimat.
- [ ] **Implementation av D3** (Snabbplock-layouten) efter spike + handoff.

---

## Track 0 — ✅ LANDAT & PUSHAT

Pushat till origin/main 2026-07-15 (`e56a9d0..3cdcb4b`):
#23 lag-gren-race · #24 Pixieset ny match · #25 tema följer OS · #27 landslag →
flagga · #28 gren·sport i väljare · sportevent↔tävling · heldagsaktivitet-fixen ·
denna plan. **Stig: starta om DPT2 → allt aktivt.**

## P2/P3 — senare (oförändrat från backloggen)

- [ ] **B-004 Enhetligt skapa/ändra** (absorberar **#26** id-baserade väljare + **B-005** "Ny"-buggen)
- [ ] **B-006/B-007** implementation efter D4/D5
- [ ] Heldagsaktivitet-rest: (a) tävlings-ref på synkade jobb, (b) filtrera Ackreditering-jobb
- [ ] #27-polish: backend-flagghärledning (renderare + iOS) + vajande vimpel
- [ ] **B-009 Widgets** · **B-010** impl efter D6 · **B-011 Realtid-spike** (batteribudget)
- [ ] Moln-som-sanning-utbyggnad (arkitekturspecen)

## Backlog ↔ öppna trådar

| Backlog | Öppen tråd | Var |
|---------|-----------|-----|
| B-001 | #29 gruppera under tävling/mästerskap | Prio 3 |
| B-002 | tennis/friidrotts-overlay, #27 backend-härledning | D1/D2 + Prio 1/3 |
| B-004 | #26 id-baserade väljare, B-005 | P2 |
| B-008 | iPad | Prio 4 (lyft från P3) |
| — | #23–25, #27, #28, heldagsaktivitet | Track 0 ✅ pushat |

## Nästa steg

1. **Design:** starta D1 (tennis-mall) direkt — mest tidskritisk. D2 (friidrott)
   strax efter, klar före 24/7.
2. **Code:** verifiera tennis-turneringsflödet + bygg overlay-motorn parallellt.
3. **Stig:** starta om DPT2 (Track 0 aktivt), dra igång D1 i Claude Design.
