# Design-handoff D19 — A1/A2/A4 levererade + inbyggda i prototypen

*2026-07-20 · Från: Claude Design · Till: Code*
*Löser resten av D18:s A-lista. A1 & A4 är inbyggda i `DPT v5 - Prototyp.dc.html`; A2 är egen iOS-mockup.*

## A1 · DPT2 Inställningar — komplett
**I prototypen** (`DPT v5 - Prototyp.dc.html` → nav Inställningar) samt fristående referens `DPT v5 - Inställningar.dc.html`.
Fanns redan: Målmappar, Google Calendar (tre lägen: ansluten/ej ansluten/behörighet saknas + API-nyckel-rad), Realtidsnotiser (flödesdiagram, Synka nu, Förnya push-kanal).
**Nytt/tillagt:**
- **Privata kalendrar** — tre tillstånd: (1) ej konfigurerad → Client ID + secret + Spara; (2) ej inloggad → Logga in med Google + Byt uppgifter; (3) inloggad → kalenderlista med kryssruta, färgprick, "DIN"-tagg på primär, penna för inline-namnredigering (Enter/Esc), Logga ut.
- **Modell & träning** — Visa/Dölj-rad som fäller ut hela Träna-panelen inbäddad (modellstatus, Träna om, ★-import, Granska träningsdata). Uppfyller etapp 2–4 §9 ("rad, inte sektion").
- **Om** — fem punkt noll · 5.0.0 · build 615 · commit db9ad6f + fotnot om gammal dist.

## A2 · iOS Inställningar + Lagring — D13-ton
**Mockup:** `DPT iOS v2 - Inställningar & Lagring.dc.html`.
Nio sektioner lyfta från rå SwiftUI-Form till kortstil: Om (NEF-brygga/version) · Server (Bas-URL) · API-nyckel (Keychain) · Hemresa · **Kamerabrygga FTP** (adressen i mässing — samma sträng som Bilder) · Väder · **Arenakoordinater** (litet register: rader + swipe-radera + lägg till) · **Lagring** (eget ark: totalsumma + sektion per importgrupp + Radera hela + swipe per fil + tomläge) · **Köade sändningar** (visas bara när kö > 0; hänger ihop med ✈ N-brickan i Jobbdetalj/A3).

## A4 · Rörligt — plats + panel
**Inbyggt i prototypen:** ny navpost **Rörligt** under Efter jobb (efter På gång). Panel: Klipp/Format/Publiceringskö, 9:16-preset, delar publiceringskö & momentmallar med Publicera, samma kanaler (IG/FB).
- **Förslag att bekräfta:** placering under *Efter jobb*. Säg till om ni hellre vill ha den som flik i Innehåll. `DPT v5 - Rörligt.dc.html` (som föll ur zippen) ersätts av denna panel — säg till om ni vill ha den som separat blad också.

## Status hela D18
- **A1 ✓ · A2 ✓ · A3 ✓** (D18-SVAR, `Jobbflik & LIVE`) **· A4 ✓**
- **C1–C4 ✓** besvarade i `HANDOFF-D18-SVAR-besked.md`.
- **B** — bekräftat "bygg på befintlig form"; toppbaren kan skissas separat om ni vill.

## Paket
`export/DPT-paket/` uppdaterat: fristående HTML av prototyperna + widgets, `skärmdumpar/` (en PNG per leverans, inkl. Inställningar, Rörligt, A2, A3), och alla handoffs. Tidslås oförändrat: designa nu, bygg efter SM.
