# Design-handoff D4 — Webb-paketet: struktur · arkiv · indikator · mörkt tema

*2026-07-16 · Till: Claude Design · Från: Code*
*Fyra sammanhängande jobb på samma sidfamilj (dalecarliaphoto.se) — ta dem som
EN designomgång så språket hänger ihop. Ingen hård deadline, men Code
implementerar skivvis så snart delar landar.*

## Dagens faktiska struktur (ur koden — kanonisk)

**Sport-sidan (`sport.astro`), uppifrån och ner:**
1. Hero — senaste matchen (eller kurerad "topp"), resultat + referat-länk
2. Höjdpunkter — masonry-GALLERI (många bilder = lång skroll)
3. På gång — kommande matcher/aktiviteter
4. Ligor & Tävlingar — sportevent-kort
5. Tidigare matcher

**Sportevent-undersidan (`/sportevent/[slug]`):** matcherna FÖRST, galleriet
sist — alltså omvänd ordning mot Sport-sidan. Det är Stigs huvudirritation:
*sidorna måste vara lika.*

**Startsidan** är statisk HTML (`public/index.html`) med fyra motivkort
(Sport · Landskap · Människor · Film) — ingen dynamik alls idag.

**Teman:** sajten har ljust läge idag; FEAT-WEB-04 vill standardisera MÖRKT.

## De fyra jobben

### 1. Enhetlig sidstruktur (B-006)
Stigs förslag att pröva: **galleri till vänster, matcher till höger**
(tvåkolumn på desktop). Definiera mobilordningen (vad kommer först när
kolumnerna staplas?). Samma struktur på Sport-sidan OCH alla undersidor
(sportevent, ev. framtida liga-/matcharkiv). Hero-blocket ligger fast överst.

### 2. Arkiv-/landningssidor (FEAT-WEB-01/02)
Två nya sidtyper: **Ligor & Tävlingar-arkiv** (alla sportevent, inte bara
senaste) och **Matcher-arkiv** (alla publicerade matcher). Frågor: gruppering
(per säsong? sport? tävling?), filter, kortdesign, paginering vs allt-på-en.

### 3. Nyhetsindikator "Sport" på startsidan (FEAT-WEB-03)
Startsidans Sport-motivkort ska signalera "nytt innehåll". Hur? (badge,
datum, senaste-titel-rad?) Obs: startsidan är statisk HTML — indikatorn
måste kunna genereras vid publicering (Code löser tekniken, designa uttrycket).

### 4. Mörkt tema som standard (FEAT-WEB-04)
Definiera mörka paletten för hela sajten (Skagen-språket finns i DPT2/appen:
mörk premium med Hav/Sol/Rosé-accenter). Beslut: enbart mörkt, eller mörkt
som default med ljust som val?

## Leverabel tillbaka till Code

1. Strukturskiss desktop + mobil (Sport + undersida — samma mall)
2. Arkivsidornas kort + gruppering (mockup räcker för en av dem + regler)
3. Nyhetsindikatorns uttryck
4. Mörk palett (tokens: bakgrund/yta/text/accent — gärna som CSS-variabler)

## Referenser
- Sajtrepo: `/Users/sickan/dalecarlia-photo` (sport.astro, sportevent/[slug].astro, public/index.html)
- Total backlog: `dpt/design/BACKLOG.md` (E-sektionen)
