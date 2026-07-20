# HANDOFF — D10 Rörligt material (designsvar)

*2026-07-19 · Till: Code · Från: Claude Design*
*Svar på er D10. Mockup: `DPT v5 - Rörligt.dc.html`. Ingen look & feel-ändring i DPT2 — nya ytor i befintligt språk.*

---

## Kort version

Klipp beter sig som NEF:er: hittas → granskas → paketeras → publiceras → levereras, i samma ytor. Allt UI visar **proxyn**; mastern stannar på Macen. Fyra leverabler + svar på F1–F7. Inget bryter er låsta arkitektur (proxy-principen, en renderare, async reel, tre ingångar).

---

## F1 · Namn & hem
**Rörligt** (domän) · **klipp** (enhet) — som ni föreslog. "Film" lämnas orört (analog film).
**Hem:** egen panel i DPT2:s rail **+ ett litet spår** där bild redan bor (Leverera/Publicera) — INTE en till flik i den redan långa Publicera-panelen (samma oro som §5.4). Panelen äger granskning/urval; spåret bara påminner om att rörligt finns på jobbet.

## F2 · Granskning — två ytor, inte en (se `#1a`/`#1b` i mockupen)
- **1b Snabbplock för klipp** = *hemmet*: rutnät av poster-JPEG:ar, hover = klippet spelar tyst i rutan, klick = väljer (samma gest/muskelminne som Snabbplock för stillbild). Bäst för snabbt urval ur många klipp.
- **1a Granskningsbord** = *detaljen bakom dubbelklick*: stor spelare, scrub, filmstrip, **enkel in/ut för snabbklipp**. Djuptrim är alltid Resolves jobb.
- De konkurrerar inte — 1b är listan, 1a är detaljvyn. Rekommendation: bygg båda, 1b först.

## F3 · Blandade paket
**Fotografen väljer per paket.** Blandat tillåts (8 bilder + 2 klipp) → plan-listan sorterar ut karusell / reel / story. Vill man hålla listan enkel läggs rörligt som eget paket. Valet bor på paketet, inte globalt.

## F4 · Async reel i plan-listan
Återanvänd **D9:s statusspråk** rakt av: 🔵 inskickat → 🟡 bearbetas → 🟢 publicerat, 🔴 fel. Foto är fortsatt synkront (🟢 direkt). Ett reel-radens **pågår-tillstånd överlever panelbyte** — det bor i publiceringskön, inte i panelens minne. Fel kan inträffa *efter* stängd panel → kön visar felet + "gör om". I ett blandat paket kan raderna stå i olika status samtidigt; det är meningen. `Post n/tot` ersätts av per-rads-status (den gamla progressen bryts av async).

## F5 · Grafik ovanpå rörligt
Ingen ny grafik — **samma moment/tema/format-chips och samma Pillow-PNG** som stillbildsstoryn (matchgrafiken ser identisk ut). Förhandsvisningen står **frusen som standard** (första rutan i urvalet); ▶ spelar proxyn med överlägget levande. **Överläggets placering är väljbar per klipp:** Hela klippet / Första 3 s / Endcard.

## F6 · Kundleverans
**R2 + signerad länk med utgångsdatum** (er lutning). Leveransstatus i `dpt.db` bredvid fotojobbet ("levererat 14:20, öppnat 2 ggr, utgår om 12 d"). Två vyer i mockupen:
- **Fotografen (DPT2):** leveranskort med länk, öppningsräknare, utgång, och Kopiera / Förläng / Återkalla.
- **Kunden:** en enkel, mörk sida som bär DPT-signaturen (sigill-märket) — spelare + "Ladda ner 4K" + personlig länk med slutdatum. `<video poster>` mot R2 räcker; ingen HLS.

## F7 · Ingest-tillstånd
**En färgprick, inte en teknisk statuslista.** På varje klipp: ⚪ oproxat · 🔵 proxas… · 🟢 redo · 🔴 master saknas (disk urkopplad) · 🟣 Resolve-export. Källa som liten glyf (📱 iPhone · 🎥 Pocket · 🎬 Resolve-mapp). Detaljen syns på hover / i granskningsbordet — aldrig teknisk text i ansiktet på Stig. "Proxas…" bär en tunn progress; "master saknas" är enda röda och blockerar bara export, inte visning av proxyn.

---

## Kanalgränser (gula, informerande — aldrig blockerande)
Samma anda som dagens FB-kap. Plan-listan visar:
- IG Reel > 1:30 → "2:14 → för långt för reel · trimma eller lägg som story"
- IG Story-video > 60 s/segment → "1:45 → 2 story-segment"
- FB Reel → caption strippas på `#`/`@`, samma diff-vy som idag.

## Leverabler i mockupen
1. **Klipp-vyn** (F1/F2/F7) — `#1a` granskningsbord + `#1b` snabbplock, med ingest-prickar.
2. **Plan-listan med rörligt** (F3/F4) — blandat paket, async reel-status, längd-varning.
3. **Grafik-förhandsvisning** (F5) — chips + Pillow-överlägg, frusen/spela, väljbar position.
4. **Leveransvy** (F6) — fotografens DPT2-kort + kundens sida.

## Utanför scope (bekräftat): TikTok, animerad grafik, video på publika sajten (`film.astro` orörd), HLS.

---

## Vända 2 — tillägg (samma mockup)

**Ljud i granskningsbordet (`#1a`):** waveform under scrubbern + mute-knapp. Originalljud som standard ("O-ton · orig"); ljudtrim/mix är Resolves jobb. Waveform hjälper bara att hitta målgång/reaktion.

**Spåret — där bild redan bor (§05):** Rörligt har egen panel, men ett **smalt spår** ligger i Leverera *och* Publicera (i Publicera före plan-listan), direkt under stillbildsurvalet. Det granskar inte — visar "Rörligt · N klipp" med poster-chips + ingest-prick + "Öppna Rörligt →". Ren närvaro + genväg, så klippen aldrig glöms där bilderna hanteras.

**iOS — granska & godkänn på plats (§06):** snabbklipp tas på mobilen, så Stig **grindar** dem på plats direkt efter en gren. Player + Godkänn/Förkasta + kö. Proxyn exporteras och laddas upp från telefonen (samma background-URLSession som NEF); mastern hämtas från Pocket-kortet hemma. **Ingen trim, ingen grafik i appen** — det är desktop/Resolve. "Duger-för" vägs mot kanalgränsen direkt ("Reel ✓"). Godkända klipp landar i jobbets Rörligt-spår i DPT2.

**Koppling till eventmodellen (F-tillägg):** ett klipp kopplas till **pass om det finns, annars jobbet/matchen** — exakt samma regel som stillbild. På ett event med Program/deltillfällen blir klippen därmed sökbara per pass ("100 m dam · Final"); utan pass hänger de på jobbet. Ingen dubbellagring — passets individer/gren härleds som vanligt.

---

## Vända 3 — beslut

**Förkasta på plats = göm, inte radera.** Ett förkastat klipp göms ur flödet men **mastern behålls på Macen** (icke-destruktivt, som NEF). Går att ångra. Ingen hård delete från telefonen.

**Ett klipp = ett reel (MVP).** Ingen söm av flera klipp i DPT2 i första skivan. Vill man ha flerdelat → Resolve → landar som ett färdigt klipp i Resolve-mappen. Söm i DPT2 kan bli en senare fråga, inte nu.

**Master-gapet visas diskret (mitt val på "decide for me").** Ett klipp godkänt på plats men vars Pocket-kort inte lästs hemma än får ett mjukt tillstånd: **"master väntar på import"** (samma ingest-språk, ingen röd larmfärg). Proxyn funkar överallt under tiden; publicering av proxy tillåts, men **kundleverans av 4K-master** kräver att gapet stängts. Ärlig, inte blockerande — matchar proxy-principen (glappet mellan "klippet finns" och "mastern hemma").

**Rörligt på publika sajten — tidig skiss finns (§07 i mockupen), egen handoff senare.** `<video poster>` mot R2, poster-JPEG som hjälte, samma Skagen Hav-grafik som stillbild, ingen HLS. **`film.astro` (analog film) rörs inte.** Hero-video/blogg-inbäddning/blädder tas i egen handoff **när ingesten (skiva 1) står** — inte i D10.

## Passar in i helheten
Statusspråket = samma 🔵🟡🟢🔴 som resten av v5 (se `HANDOFF-00-Helhet.md`, tråd "Status"). Kundsidan bär signatur-sigillet (tråd "Signaturen"). Ny tråd i helheten: **Rörligt/klipp** — [DM], mockat, DPT2 + kundsida.
