# Plan — Nordea Open & Friidrotts-SM (konsoliderad)

*Skapad 2026-07-15. Slår ihop DPT2/iOS-backloggen (B-001…B-011) med de öppna
trådarna från pågående arbete (DPT2-bugglistan #23–#29, heldagsaktivitet,
landslagsflagga m.m.). Levande dokument — bocka av och uppdatera.*

## Två deadlines styr allt

- **Nordea Open — i helgen** (tennis, Båstad). Turneringen pågår 13–19 juli;
  Stig fotar helgen. Ambition: så mycket som möjligt användbart **nu**.
- **Friidrotts-SM — nästa vecka** (Uppsala, friidrott). Backloggens P1.

## Bärande principer

1. **Sport-medvetenhet är ryggraden.** `data/sportprofil.py` finns redan
   (fotboll, handboll, innebandy, volleyboll, beachvolley, **tennis**,
   **friidrott** — resultat-etiketter, `has_scorers`, `squad`, `individ`).
   Gör overlays + väljare **datadrivna av profilen en gång** → varje ny sport
   blir konfig, inte kod. Gemensam nämnare för B-001, B-002 och öppna #26/#27.
2. **Land det som redan är byggt först.** Flera fixar ligger committade lokalt
   men okörda. In, verifiera, (beslut) pusha — innan nytt staplas på.
3. **Moln = sanning** (arkitekturspecen) är målbilden för B-001/#29
   event-strukturen — men vi bygger minsta användbara skiva för helgen, inte
   hela specen.

---

## Track 0 — Land pågående arbete  ·  P0, denna vecka

Committat lokalt, EJ pushat — bygg dist, Stig startar om DPT2, verifiera:

- [ ] #23 lag-gren-race · #24 Pixieset på ny match · #25 tema följer OS (`1d7e4f9`)
- [ ] #27 landslag → flagga som logga (`48ac2f4`)
- [ ] Heldagsaktivitet: rätt lista (matcher bortfiltrerade) + gren·sport (`cccec2a`)
- [ ] **Beslut:** pusha Track 0 till origin/main? (delad worktree — koordinera)

Små restfixar (gör om de hjälper helgen, annars P2):

- [ ] Heldagsaktivitet (a) tävlings-ref på *synkade* jobb → gren·sport på alla rader
- [ ] Heldagsaktivitet (b) filtrera bort "Ackreditering …"-jobb ur väljaren
- [ ] #26 id-baserade `loggaForLag`/`truppStorlek` (fel logga/trupp för Sverige dam/herr)

---

## P1a — Nordea Open (helgen · TENNIS)

Tennis är till stor del redan byggt (individmatch, turnering, turnerings-SoMe
schema v26 — pushat). Fokus: **verifiera end-to-end + täppa den enda riktiga
luckan (story-overlay för tennis).**

- [ ] **Verifiera turneringsflödet skarpt:** ladda Nordea Open-tävlingen →
      sportevent binds → matcher fylls → publicera till webb + På gång.
      (Bygger på "Sportevent binds till tävling".)
- [ ] **Tennis-overlay** *(Design → Code · tennis-skivan av B-002)*: overlay-texten
      är fotbollsflavored ("Avspark/Halvtid"). Tennis behöver spelarnamn som
      primär rad, rond/omgång ("Åttondel", "Semifinal") i st f "Avspark", och
      set-resultat. Gör overlay-fälten datadrivna av `sportprofil` (individ +
      res_label "Resultat i set"). Claude Design → tennis-mallvariant, Code kopplar.
- [ ] **iOS matchdag + story för tennis:** hub/MÅL-flödet är fotbollstänkt
      (startelva/45+/straff). Tennis: minsta väg foto → overlay → dela IG med
      tennis-fälten. Inte hela live-flödet.
- [ ] *Nice-to-have:* restid/väder på plats — Båstad-koordinat finns redan i appen.

*Medvetet UTE ur helgen:* B-003 röst→action (för stort), full live-inmatning.

---

## P1b — Friidrotts-SM (nästa vecka · FRIIDROTT)

- [ ] **B-001 Deltagarhantering** *(Code)*: datamodell Event → Deltagare → Grenar
      (m2m — en deltagare i flera grenar, t.ex. Längd + Tresteg). Admin-UI i DPT2.
      API/synk så iOS hämtar deltagarlista per event. Syfte: snabb koppling
      deltagare → story-overlay på plats. **Överlappar #29 event-struktur — bygg
      det här som den konkreta skivan.**
- [ ] **B-002 Horisont-mallar friidrott** *(Design → Code)*: gren+moment ("Längd —
      kval", "Tresteg — final"), idrottarnamn primärt, resultat efter grentyp
      (längd/tid/höjd). Datadrivet via sportprofil (utöka friidrott-profilen med
      grentyp → resultatformat). **Samma motor som tennis-overlayn i P1a.**
      *Beroende: B-001 (deltagardata).*
- [ ] **B-003 Röst → action** *(iOS · Code)*: spela in → transkribera → Claude
      tolkar → strukturerad händelse → bekräfta → spara. "Karlsson 6,42 i tredje
      hoppet" / "Mål av Johansson 22 i 34:e". Grundflödet först, trimma efter SM.

---

## P2 — Nästa sprint

- [ ] **B-004 Enhetligt skapa/ändra** *(Code, Change)*: inventera flödena för
      fotojobb/matcher/lag/liga, definiera gemensamt mönster, migrera alla dit.
      **Absorberar #26** (id-baserade sport-medvetna väljare) **och B-005.**
- [ ] **B-005 Bugg: "Ny" utan ändring** *(Code)*: ingen post sparas förrän något
      fyllts i / tydlig avbryt-hantering. Löses i B-004:s mönster.
- [ ] **B-006 Sportsidans struktur** *(Design → Code, Change)*: enhetlig ordning
      galleri/matcher (galleri vänster, matcher höger på desktop; definiera
      mobilordning) på Sport + alla undersidor. Idag skiljer Sport och
      Ligor & Tävlingar sig åt.
- [ ] **B-007 Lightbox** *(Code + lätt Design)*: klick → större vy, pil/svep-
      navigering, Esc/klick-ut, ev. bildtext. Sport/Landskap/Människor/Film.
- [ ] #27-polish: backend-flagghärledning (renderare + iOS får flaggan) + vajande vimpel.

---

## P3 — Senare

- [ ] **B-008 iPad-spike** *(Code)*: universal vs uppskalad app, Split View/Stage
      Manager bredvid LR Mobile (Snabbplock). Rekommendation + estimat.
- [ ] **B-009 Widgets** *(Code)*: hem + låsskärm, kompakt först — nästa jobb/match,
      På gång, senaste publicering.
- [ ] **B-010 Låsskärm = startsida** *(Design + Code)*: trolig teknik Live Activity
      (kompakt + expanderad + Dynamic Island).
- [ ] **B-011 Realtid utan batteridränering** *(spike)*: väder på plats + restid kvar
      under körning; Live Activities / background-budget / push vs polling; mätbart
      låg batteripåverkan under en hel matchdag. Hänger ihop med B-010.
- [ ] Arkitekturspecens moln-som-sanning-utbyggnad (läs-features väder/restid MapKit).

---

## Backlog ↔ öppna trådar (så inget tappas)

| Backlog | Öppen tråd från detta jobb | Hamnar i |
|---------|----------------------------|----------|
| B-001   | #29 gruppera matcher/fotojobb under tävling/mästerskap | P1b |
| B-002   | tennis-overlay + #27 backend-härledning | P1a / P2 |
| B-004   | #26 id-baserade sport-medvetna väljare | P2 |
| —       | #23 #24 #25 #27 + heldagsaktivitet + luckor (a)(b) | Track 0 |

## Ägarskap & beroenden

- **Claude Design först:** tennis-overlay (P1a, mest tidskritisk), B-002, B-006, B-010.
- **Code:** allt övrigt.
- **Beroendekedjor:** B-002 ⟵ B-001 (deltagardata) · tennis-overlay ⟵ verifierat
  turneringsflöde · overlays (tennis + friidrott) delar samma datadrivna motor.

## Öppna beslut

1. Pusha Track 0-commitsen till origin/main nu?
2. Nordea Open realistisk skiva: räcker "verifiera flöde + tennis-overlay + minimal
   iOS-story", eller vill du ha mer (restid/väder-polish)?
3. Vilka design-handoffs drar vi igång direkt? (tennis-overlay först)
