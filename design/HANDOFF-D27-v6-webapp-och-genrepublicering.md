# Design-handoff D27 — v6-webbappen + genrepublicering

*2026-07-24 · Från: Code → Till: Claude Design*
*Samlad UX/UI-handover för v6-spåret. Allt nedan är BYGGT och fungerar med temporära test-UIn — Design formar, Code implementerar pixel-perfekt efter svar (samma modell som D1–D26). Komplement till D26 (Vardag/Resa, iOS) — detta rör webbappen + de genreneutrala publiceringsytorna.*

## Kontext — vad som finns live

**Webbappen `app.dalecarliaphoto.se`** (Cloudflare Access/Google-login, read-only mot skarp data): **DPT v5:s skal är porterat rakt av** (Rail 216px m hästmärke + "webb"-etikett, samma nav-ikoner/stil, tunn topbar, OS-följande ljus/mörk, tokens.css delas). Fem vyer: **Idag** (åtgärdskö/närmast/statistik/inkorg) · **Platser** (karta + scouting + sol/måne/väder) · **Fotojobb** (per månad, kategorifärger) · **Matcher** (paket + live-läge) · **Innehåll** (lista + detaljvy m bilder). Skalet behöver alltså INGEN design — punkterna nedan gäller **vyernas inre + nya ytor**.

Backend (staging, klart att formge mot): berikat väder (molnlager/dimindex/solnedgångskvalitet/nederbörd), genrestyrda vädervarningar, scout-platser m målväder + status-ring, 7-dagars dagremsa, shot-planner-matte, Claude-text per genreprofil, röst→caption, news flash, Plats-overlay i renderaren.

## Punkterna (W1–W8)

- **W1 · Platser-vyns inre layout (inkl. MOBIL).** Karta (Leaflet, OSM + höjdkurve-läge) + högerlista (Fotojobb/Arenor/Scoutplatser) + Sol & ljus-kortet. Idag funktionellt men okomponerat; mobil = enkel stapling (karta 48 %/lista 52 %) + ikonrad. Behöver: hierarki, listtäthet, kort-form, kartkontrollernas placering, mobilform.
- **W2 · Kartans default-vy + pin-språk.** Öppnar utzoomad över Norden; pins är enfärgade prickar (blå jobb/arena, grön scout, orange vald, gul utkast). Behöver: `fitBounds`-beslut + visuellt språk för pins/urval/sol-linjer.
- **W3 · Sol/ljus/väder-kortet utan plotter.** Kortet bär idag: datum+tid-väljare, "solen nu"-rad, väderblock (temp/vind/moln/nederbörd/dimrisk/solnedgång X:10), 7-dagars klickbar dagremsa, gyllene/blå-timme-tabell, månrad, motivriktnings-fält. ALLT funkar — men det är mycket. Behöver: informationshierarki/gruppering (jfr D26:s "väder i tre lager"-tänk).
- **W4 · Shot-planner "Nål A → Nål B".** Temporärt: gradtal-fält → linje + "sol/måne i linje kl X". Riktiga interaktionen: kamera-nål + motiv-nål på kartan, bäring härleds; visning av alignments + fler-dygns-scan ("vilka datum går solen ned i den vinkeln").
- **W5 · Terminologi-vokabulär per kategori.** Funktionsmodul byggd (orden följer motivet): sport Arena/Match/Avspark · människor Plats/Uppdrag/Kund · landskap Plats/Motiv · film Location/Tagning. Bekräfta/finslipa orden.
- **W6 · Plats-overlayen (E3) — NY.** Renderaren har nu ett "Plats"-moment för landskap/icke-match: temaloggan diskret + ortnamn + valfri regionsrad, låg scrim, **inget datum**. Funktionellt utkast bifogat: `HANDOFF-D27-underlag/plats-overlay-utkast-{9x16,4x5}.jpg`. Behöver: typografi/placering/scrim-styrka, ev. tema-varianter (Sol/Hav/Rosé), och Människor-genrens variant (definieras när den genren tas — E3).
- **W7 · Genre-publiceringsflödet (E1/E2) — skärmar.** Backend klar: välj bild(er) → genreprofil styr caption (Claude), overlay (Plats/scoreboard), taggar; röst-in ger caption+overlay-rubrik. Story-API-utredningen klar: bild/video-stories automatiseras fullt (allt visuellt bakas in i bilden — länk-sticker/interaktivitet kräver manuellt spår). Behöver: publiceringsflödets UI utanför sport — kanalval (story/inlägg/FB), bildantal, förhandsvisning, röst-in-gesten. Primärt iOS (hör ihop med D26-familjen) men samma flöde ska finnas i webbappen/DPT.
- **W8 · News flash på startsidan.** Backend klar (3–5 senaste, publik läsning, ingen rebuild). Behöver: visningens form på dalecarliaphoto.se startsida (kort flöde, redaktionell låg ton, skild från journalen) + postnings-UI:t i iOS.

## Prioritetsförslag (Code)
W1+W2+W3 hänger ihop (Platser-vyn som helhet — störst upplevd nytta i webbappen) → W6 (liten, låser landskaps-publicering) → W8 (liten) → W4+W7 (störst nyheter, kan ta tid) → W5 (bekräftelse).

## Låsta invarianter (rör ej)
Skagen-palett + kanonfärger (Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`) · grenpalett (Dam/Herr/Mixed som kant) · Saira/Saira Condensed · v5-skalets Rail/topbar · EN renderare (Pillow) · "inget datum på landskaps-overlay" (Stig-beslut, E3).
