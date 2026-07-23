# Design-handoff D26 — Vardag/Resa-modellen (iOS v2 + DPT v5)

*2026-07-23 · Från: Claude Design · Till: Code*
*Löpande leverans. Mergas i befintlig lösning bit för bit — ingen storrelease.*

---

## ⚠ Bygg pixel-perfekt mot mockuparna
Skärmdumparna i `skärmdumpar/` och de bifogade standalone-HTML-filerna är **specen**, inte
inspiration. Håll dig till dem exakt:

- **Mått, spacing, radier, typsnittsstorlekar** — läs av från HTML-filerna (öppna dem, de är
  självständiga). Ändra inte "för att det blir snyggare".
- **Färger** — endast ur paletten nedan. Inga nya toner.
- **Typsnitt** — Saira (brödtext/UI) + Saira Condensed (rubriker, tal, klockslag). Aldrig andra.
- **Ikoner** — samma stroke-vikt (1.6–1.9) och linjestil som mockupen (feather-aktigt, rundade
  ändar). Inga fyllda/emoji-ikoner utom sigillets stjärna.
- **Vid tvekan:** fråga Design. Förenkla ALDRIG en panel till en enklare skiss på eget bevåg.

### Palett (låst, ärvd)
- Skagen-mässing (accent, iOS mörkt): `#F0B45A` · hover `#F4C277` · mjuk `rgba(240,180,90,.15)`
- DPT desktop ljus (parchment): fönster `#F4EEE2` · titel `#EFE7D6` · rail `#ECE3D2` · kort `#FBF8F1`
  · accent `#C9871F` · hover `#B5781A`
- Grenpalett: Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757` (färgad kant, ingen textetikett)
- Kategori: Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`
- Varning: `#E06A5A` (iOS) / `#D0563F` (desktop) · OK `#6FB35A`/`#4E8A3E`

---

## Kärnmodell (gäller BÅDE iOS och desktop)

**Vardag** är alltid hemvyn och default — läget mellan jobb, för att planera framåt och packa
rätt. **Resa** ersätter aldrig vardagen; ett **resekort stiger överst i samma ström** när ett
jobbs avresetid passeras. Timme-för-timme-detaljen bor först när man **öppnar jobbet**.

### Väder i tre lager
| Lager | Var | Innehåll |
|---|---|---|
| **Varning** | Vardag, alltid | Nästa relevanta jobb, **genrestyrt** (sport: vind/regn; bröllop/landskap: annat). T.ex. "Hård vind vid SM lör em · 12 m/s". |
| **Översikt** | Vardag | Destinationsväder för packning (24°/21°/22°, regn sön em). |
| **Detalj** | Öppnat jobb | Timme-för-timme **vid arenan** + ljusfönster (gyllene/blå). |

**HÄR vs DÄR:** HÄR = enhetens GPS-plats (CoreLocation → WeatherKit + soltider), uppdateras när
man flyttar sig. DÄR = prognos för jobbets plats/dag. På **Vardag-hemvyn** visas båda; **HÄR är
mindre viktigt i resa-läget** (nedtonat), DÄR/destination lyfts.

### Avresetröskel (per jobb, inte global)
- Manuell avresetid per jobb, med **rimligt default beräknat ur restid**.
- MFF-match 20 min bort, avspark 14:00 → resa aktiveras ~11:00.
- SM Uppsala 7 h restid + ev. övernattning → resa aktiveras när man sätter sig i bilen.
- **Att sitta hemma före avresa räknas fortfarande som vardag.**

### Flera resor samtidigt
Bara **närmaste resekort** överst. Svep/pil till nästa (prickar 1/2 visar antal). Ett kort i
fokus, resten en gest bort.

### Resekortets fält (Alt A) — BESLUTAT
Kortet visar alltid **det ben man är på nu**.
- **Dagsresa (utan boende):** ett ben — restid nu (+ live trafik), distans, arena öppnar.
- **Övernattning (med boende) → tvåbens-tidslinje:** klarade ben bockas av (grön), det **aktiva
  benet** (boende→arena) driver restid & avresetröskel. Den långa körningen hem→hotell ligger
  bakom som avbockat steg. Se `iOS - Resekort (varianter).html`, variant **B**.
- **Parkering / port / västhämtning** sitter **på arena-benet, direkt på kortet** (det man behöver
  i bilen sista milen). Full logistik finns kvar i öppnat jobb.
- Knappar: Vägbeskrivning/Kör till arenan · Öppna jobbet (övernattning: + Hotell).
- Scouting hör hemma i **vardag** (v6), även när den pekar mot ett kommande jobb.

---

## Filer i denna handover

### iOS v2
- **`iOS - Vardag & Resa (modell).html`** — ★ HUVUDSPEC. Tre skärmar: Vardag (lugn) ·
  Vardag+Resekort (Alt A) · Jobb öppnat (detalj). Rail förklarar de tre väderlagren + tröskeln.
- **`iOS - Idag & Widget.html`** — Idag-startsidan + låsskärms/hemskärmswidgets. HÄR i dag
  (väder 08–20 + sol upp/ner, GPS), PÅGÅR NU-kort (jobb som sker idag, live-puls), väder på
  Närmast på tur (inom 9-dagarshorisont).
- **`iOS - JobbDetalj (1b).html`** — JobbDetalj i vald riktning (hero bär åk-raden, NÄR-panel
  borttagen, sigill = widget-sak, ursprungs-chip). Tre lägen: vardag/resa/på jobbet.
- **`iOS - Panel-optimering (JobbDetalj).html`** — beslutsunderlaget bakom 1b (1a nuläge vs
  1b tät vs 1c adaptivt sigill). För kontext; bygg **1b**.
- **`iOS - Jobb-listan (tävling).html`** — SVAR D25: dedup-nyckel `tavling_id ?? jobb.id`,
  en rad per event, sortering per segment.
- **`iOS - Resekort (varianter).html`** — resekortets två varianter: A dagsresa (ett ben) ·
  B övernattning (boende→arena stegat, parkering på arena-benet). **Bygg B-modellen.**

### DPT v5 (desktop)
- **`DPT v5 - Vardag & Resa (förslag).html`** — **BESLUTAT: bygg 1a Dagbandet** (väder + resekort
  som horisontell remsa överst på Idag; resekortet fälls ut i bandet när avresetid passeras,
  additivt ovanpå nuvarande Idag). 1b Dagkolumnen utgår.

---

## Bygg-ordning (förslag)
1. **iOS Idag & Widget** — HÄR/PÅGÅR NU/väder-på-närmast (minst beroenden, störst dagligt värde).
2. **Väderlager-infra** — varning (genrestyrt) · översikt · detalj. Delas av iOS + desktop.
3. **Avresetröskel** per jobb + resekort-logik (Alt A). iOS först.
4. **JobbDetalj 1b** — hero-konsolidering, ursprungs-chip, NÄR-panel bort.
5. **D25 dedup** `tavling_id ?? jobb.id` + sortering (separat spår, efter SM-merge).
6. **DPT desktop** — efter Stigs val 1a/1b + DPT:s egna prioriteringar först.

## Öppna frågor till Stig
- (inga just nu — desktop 1a, resekort variant B, parkering på kortet är alla beslutade)
