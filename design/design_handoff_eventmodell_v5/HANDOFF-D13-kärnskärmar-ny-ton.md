# Design-handoff D13 — Kärnskärmarna i ny grafisk ton (iOS v2)

*2026-07-20 · Från: Claude Design · Till: Code*
*Gäller Hem, Bilder, Ny story och Matchdetalj. Ingen funktion ändras — bara den grafiska tonen. Mockup: `DPT iOS v2 - Kärnskärmar.dc.html` (levande).*

## Tonen (samma på alla skärmar)
- **Bakgrund:** `#0a0d11` med Skagen Hav-glimt `radial-gradient(circle at 28% -5%, #12171d, #0b0e12 62%)`. Inte platt svart.
- **Accent:** mässing `#F0B45A` (→ `#E39C3E` i knapp-gradient) — **enda** accentfärgen. Inget rent orange/gult.
- **Typ:** Saira Condensed 700 i rubriker/siffror (nedräkning, matchnamn, sektionstitlar), Saira i brödtext.
- **Kort:** `rgba(255,255,255,.04)` fyllnad, `1px rgba(255,255,255,.08)` kant, radie 16–20px. Lugnt, inte hårda svarta rutor.
- **Grenfärg som kant** (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`) — vänsterkant, ingen textetikett.
- **Kategorifärger** på ikonrutor (Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`).
- **Inga emoji** — rena SVG-ikoner i ikonrutor.

## Per skärm

### Hem — Matchdag
- Nedräkningen bor i **sigillet**: hästmärket svagt (opacity ~.13) inuti dubbel mässingsring, "AVSPARK OM / 5 dagar / 16° prognos · kl 08:00" ovanpå. Samma märke som låsskärmens gauge — återanvänd komponenten.
- Foto fyller toppen (~430px) med mörk vinjett ner mot `#0a0d11`. Header (logga + DPT + synk-chip) ligger **på** fotot i glas-pill.
- "HÄR I DAG"-kort: 5 tidpunkter 08–20 med mässings-väderikoner, restidsrad, ankomst/uppvärmning/avspark (avspark i mässing).
- CTA "Till matchen →" = mässings-gradient, mörk text.

### Bilder (På telefonen / Kortet / Kameran)
- Titel "Bilder" i Saira Condensed, sigill-diskret rund knapp uppe till höger.
- Segmenterad flikrad i kort-stil. **FTP-adressen `192.168.1.181:2121` i Saira Condensed mässing** — det enda man skriver av, så det ska sticka ut.
- Statuspunkt följer synk-systemet (gul = väntar, grön = uppe, röd = fel). Tomlägen: dämpad SVG-ikon + Saira Condensed rubrik.

### Ny story
- "MOMENT"-rutnät: valt moment i mässings-gradient med mörk text, övriga i kort-stil. Sektionsetiketter i mässing-caps `.14em`.
- Foto- och Overlay-väljare som segmenterade kontroller i kort. LR-export-raden i mässing.
- **"Rendera & dela"** tänds (mässing) först när en foto-källa är vald — annars nedtonad. (I mockupen: LR = klar, Telefon = tom → nedtonad.)

### Matchdetalj
- Matchkort med **grenkant** (Damallsvenskan → Dam `#8E5A86`), arena/datum centrerat, sköldar som cirklar.
- "Starta LIVE-läge" i **statusrött** (`#E06A5A`, `rgba(224,106,90,.1)` fyllnad) — enda röda ytan, som färgsystemet föreskriver.
- Handlingsrader med **kategori-/grenfärgade SVG-ikonrutor**: Publicera story (mässing ✦), Matchtrupp (Sport-blå), Föra matchen (Herr-teal), Matchens bilder (Mixed-grön).

## Kvar / öppna
- Jobb-fliken och LIVE-läget är inte omgjorda än — säg till om de ska med i nästa runda.
- Fältflödet (`DPT iOS v2 - Fältflöde.dc.html`) är redan i denna ton och hänger ihop med "Publicera story" → "Skapa SoMe".
