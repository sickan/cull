# HANDOFF — Helheten (master-index)

*2026-07-19 · Till: Code (DPT2 + iOS) · Från: Claude Design*
*Ingångsdokument. Läs detta först — det binder ihop allt och pekar vidare.*
*Egen branch. Löpande leverans — inget storsläpp.*

---

## Vad detta är

En sammanhållen tråd genom fyra ytor — **låsskärm → widget → iOS-app → DPT2** — som vuxit fram ur eventmodell-epiken och skissrundorna. Vissa delar är ren **design**, andra **datamodell**, flera **både och**. Denna fil är kartan; detaljerna ligger i dokumenten nedan.

**Två saker binder ihop allt:**
1. **Signatur-sigillet** — hästmärket i en graverad ring, där nedräkningen till avgång ritas som en orange båge. Samma märke på splash, hemskärm, låsskärm, widget och jobbdetalj. En igenkännbar underskrift (även som "levererad"-stämpel på klara jobb).
2. **Färgsystemet** — varje färg får *en roll, en zon, en form* så kategori, gren, status och lagfärger samsas utan att slåss. Sigillets orange är den enda konstanten.

---

## Dokument & mockups

| Dokument | Innehåll |
|---|---|
| `DATAMODELL v5.md` | Liga/Event/Individ, Gren + **pass**, härlett **Program/deltillfällen**, kategori |
| `HANDOFF.md` | Eventmodell-epiken (§1–7) + **§8 Program/deltillfällen** + fältdelta |
| `HANDOFF-etapp-2-4.md` | UX-lyftet i DPT2 (gallring, publiceringskö, innehåll, individregister) |
| `HANDOFF-widget-lasskarm.md` | Widgetens 6 ytor (svar på B-009) + **JobbDetaljView**-designrundan |
| `HANDOFF-D10-rorligt.md` | **Rörligt material** — klipp-vy, plan-lista, grafik, leverans (svar på F1–F7) |
| **Denna fil** | Master-index + byggplan tvärs ytorna |

| Mockup | Yta |
|---|---|
| `DPT iOS v2 - Widget & Låsskärm.dc.html` | Widget/låsskärm — 6 ytor, identitet A/B, specialfall, StandBy, sigill |
| `DPT iOS v2 - Jobbdetalj.dc.html` | iOS jobbdetalj — sigill, dagsprogram, karta, väder, soltider |
| `DPT iOS v2 - Signatur.dc.html` | Sigillet genom appen — splash, hemskärm, låsskärm, levererad-stämpel |
| `DPT iOS v2 - Färgsystem.dc.html` | Färg-governance — roller, zoner, samspel på kort, status |
| `DPT v5 - Event Program.dc.html` | DPT2:s Program-kort (tidslinje per dag) |
| `DPT v5 - Rörligt.dc.html` | Rörligt — klipp-vy (1a/1b), plan-lista, grafik, leverans |
| `DPT v5 - Helhetsöversikt.dc.html` | Matrisen nedan, visuellt |

---

## Byggplan tvärs ytorna

Taggar: **[D]** design · **[M]** datamodell · **[DM]** både. Status: ✓ mockat · ○ att bygga.

### 1 · Datamodell — grunden (allt annat hänger på denna)  **[M]**
- **Pass på gren:** `grenar[].pass[{namn, datum, tid, plats?}]` — varje pass egen datum+tid (kval dag 1, final dag 2). Gren = disciplin.
- **Fria hållpunkter:** `event.hallpunkter[]` (utan gren, t.ex. medaljceremoni).
- **Program härleds** (aldrig eget register): pass + `event:`-kopplade matcher med tid + hållpunkter, sorterat/grupperat per dag.
- **Individer per pass härleds:** pass → gren → `deltagare`.
- Bygger vidare på Liga/Event/Individ + `liga:`/`event:` på match (se `HANDOFF.md §1`).

### 2 · DPT2 — Program-kort + import  **[DM]**  ○  (mockup: `DPT v5 - Event Program`)
- Nytt kort i event-detaljen: **tidslinje per dag** (dag-tabbar), pass per gren med gren-kant i låst palett, härledda individantal, hållpunkter utan kant, "NÄST"-markering.
- **Läs in spelschema — utökas:** läser events startlista/program (skapar grenar, fyller pass), plus **klistra in / CSV** från arrangörens PDF. Allt manuellt justerbart.
- DPT2:s befintliga look & feel rörs inte i övrigt.

### 3 · iOS — signatur-sigillet  **[D]**  (mockups: Widget & Låsskärm, Signatur, Jobbdetalj)
- **Låsskärm** ✓: `accessoryCircular` = sigill-gauge (häst + fyllnadsring, mono). Rektangel bär dag/väder/åk. Inline ovanför klockan.
- **Widget** ✓: samma gauge; hemskärmsytorna small/medium/large i live-kvalitet (jobbnära väder, 3 DÄREFTER, färskhetsstämpel).
- **iOS-app** ✓: splash med sigillet, hemskärmens nedräkning = sigill, litet sigill-märke i sidhuvudet.
- **Levererad-stämpel** ○: sigillet som våttstämpel ("LEVERERAD · datum") på klara jobb — sätts i leverera-flödet.
- Detaljbeslut (Q1–Q6, identitet ljus/mörk-val, LA-medvetenhet, tomläge, okänd arena, färskhet): se `HANDOFF-widget-lasskarm.md`.

### 4 · iOS — färgsystemet  **[D]** (+ liten [M])  (mockup: Färgsystem)
- Fem roller, var sin zon/form: **Brand** (orange — sigill/handling), **Kategori** (Hav/Sol/Rosé/Film/Blogg — prick/kant, aldrig fyllda ytor), **Gren** (Dam/Herr/Mixed — kant/markör, bara i sport, ingen textetikett), **Status** (synk/klar/väntar/fel — pill/prick, fast betydelse), **Lagfärger** (klubbens egna, karantän i brickan).
- Regel: **max två mättade färger per kort.** Eventtyp får **ingen** egen färg (bara etikett) — dödar dagens krock där eventtyp återanvände grenens hex.
- **[M]-bit:** kategori/gren/status läses ur en **delad plist i App Group** (samma källa som widget-extensionen) så färger aldrig driver isär. Låsta hex oförändrade; bara ljushet justeras för mörkt läge.

### 5 · iOS — program/restid/bakgrund  **[DM]**  (mockups: Jobbdetalj, Widget & Låsskärm)
- **Jobbdetalj** ✓ (mock): dagens deltillfällen (läser §1-programmet), sigill-nedräkning, "Del av {event}", karta, jobbnära väder, soltider, Sätt/ändra plats + Sikta på annan tid.
- **Nästa deltillfälle** (restid): första pass/match med klockslag framåt. Override: deltillfälle eller eget klockslag.
- **Dynamisk bakgrund** ○: ★-pott per kategori → egen bild → standard (★-flagga sätts i DPT2 Leverera).

### 6 · Status överallt  **[DM]**
- Fyra betydelser, samma färger på alla ytor: **synk** (blågrå), **klar/live** (grön), **väntar/bygger** (gul), **fel** (röd). Liten form; vinner blicken bara vid handling. DPT2 har redan publiceringsstatus — iOS ärver samma fyra.

---

## Matris (samma som `DPT v5 - Helhetsöversikt.dc.html`)

| Tråd | Låsskärm | Widget | iOS-app | DPT2 |
|---|---|---|---|---|
| **Signaturen** [D] | ✓ gauge | ✓ cirkel-gauge | ✓ splash/nedräkn/märke/stämpel | — |
| **Program/deltillfällen** [DM] | ○ ”nästa” | ○ nästa-rad | ✓ dagsprogram | ✓ Program-kort + pass |
| **Färgsystem** [D] | ✓ mono | ✓ prick+status | ✓ roller/zoner | ○ delad plist |
| **Restid → nästa** [DM] | ✓ åk om | ✓ åk senast | ✓ hem+jobbdetalj | ○ matar tider ur pass |
| **Dynamisk bakgrund ★** [DM] | — | — | ✓ hemskärm | ○ ★-flagga i Leverera |
| **”Del av {event}”** [DM] | — | ○ titelrad | ✓ jobbdetalj-rad | ○ match↔event-fält |
| **Status** [DM] | — | ○ färskhet | ✓ statuspill | ✓ finns |
| **Levererad-stämpel** [DM] | — | — | ✓ leverera-kvitto | ○ sätts vid leverans |
| **Rörligt / klipp** [DM] | — | ○ granska/godkänn på plats | ✓ iOS grind + spår | ✓ klipp-vy·plan·leverans (D10) |

---

## Föreslagen ordning

1. **Datamodell** (§1) — pass + härlett program. Allt annat vilar på detta.
2. **DPT2 Program-kort + spelschema-import** (§2) — så fotografen kan mata in program.
3. **iOS färg-plist i App Group** (§4 [M]) + färgroller — städar grunden.
4. **iOS sigill-gauge** på lås/widget/hem (§3) — ren UI ovanpå färg + data.
5. **Jobbdetalj + nästa deltillfälle** (§5) — läser programmet.
6. **Resten** i valfri ordning: levererad-stämpel, ★-bakgrund, LA-medvetenhet, ljus/mörk-widgetval, tomläge.

---

## Låsta invarianter (får aldrig regreras)

- **Gren-palett (fast):** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Färgad kant/markör — **ingen** textetikett, ingen kant om gren okänd.
- **Kategori (statisk toppnivå):** Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`.
- **Match med event visas ALDRIG lösryckt** — alltid ”Del av {event}” med länk.
- **Publicera → Live:** appen visar den riktiga server-renderade Horisont-bilden; prototypernas CSS-skisser är prototyp-begränsningar, inte spec.
- **DPT2 look & feel** ändras inte i denna omgång — lyftet gäller iOS-appen.
