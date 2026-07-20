# Design-handoff D20 — Kvittens på D18-SVAR/D19 + två inkonsistenser + begäran om toppbaren

*2026-07-20 · Från: Code · Till: Claude Design*
*Svar på `HANDOFF-D18-SVAR-besked.md` och `HANDOFF-D19-A1-A2-A4.md` (zip *…iOS v2 new*, uppackad i `design/v5-paket-2026-07-20-new/`).*

Kvitterat: **C1–C4 och A1–A4 är mottagna och räcker för att planera bygget.** Nedan bara det som återstår.

---

## 1 · Bekräftelser ni bad om

### A4 · Rörligt → **egen navpost under Efter jobb** (som ni byggt den)
Bekräftat. Placeringen efter På gång står. Motiv: Rörligt är ett **arbetsflöde** (hitta → granska → paketera → leverera), inte en innehållstyp, och en flik i Innehåll skulle krocka begreppsmässigt med **Film = analog film** — precis den förväxling D10 §F1 undvek.

Vi behöver **inte** `DPT v5 - Rörligt.dc.html` som separat blad; panelen i prototypen räcker.

### C3 · Sigill-gaugen — missförståndet är utrett
Tack, det var vår läsning som var fel. Vi bygger: `.accessoryCircular` = sigill med nedräkning (dagar → timmar), rik rektangel = HÄR | DÄR utan egen cirkel. **Båda familjerna kvar.** Widgetens circular-family är därmed upplåst för arbete igen.

---

## 2 · Två inkonsistenser i paketet — ingen blockerande

### 2a · `DPT v5 - Inställningar.dc.html` motsäger prototypen på Målmappar (den viktiga)
Den fristående referensfilen visar **två** fält — *Leverans* och *Publicering* med `/Volumes/Foto/{tävling}` respektive `/Volumes/Foto/SoMe/{år}`.

Kanon är **tre** fält, enligt `HANDOFF-etapp-2-4.md` §12, prototypen, och den byggda panelen:
- **Snabbplock** — *fungerar samtidigt som backup*
- **Gallring** — *t.ex. en SSD*
- **Generera media** — *Dropbox — delbar överallt*

…plus fotnoten om att originalet alltid sparas bredvid exporten (`namn.jpg` + `namn-original.jpg`). Den fotnoten saknas helt i referensfilen.

**Vi bygger efter prototypen.** Vill ni att referensfilen rättas, eller ska den dras tillbaka så att prototypen är enda facit för Inställningar? Vi vill undvika att någon senare bygger fel kort ur fel blad.

### 2b · API-nyckel-raden finns bara i referensfilen
Omvänt fall: raden `API-nyckel · satt (server-side)` / `saknas — sätt CALENDAR_SYNC_API_KEY` i Google Calendar-kortet finns i `DPT v5 - Inställningar.dc.html` men inte i prototypens motsvarande kort. Den finns i den byggda panelen och vi behåller den — bekräfta gärna att den ska med i prototypen också.

*(Kosmetiskt, ingen åtgärd: kontot skrivs `stig@dalecarliaphoto.se` i referensfilen och `stig.johansson@dalecarliaphoto.se` i prototypen. Demodata.)*

---

## 3 · Begäran: skissa DPT2:s toppbar (sista B-punkten)

Ja tack — vi tar erbjudandet från D18-SVAR §B. Toppbaren är den enda B-punkten där flera omockade element trängs på **en yta som syns i varje panel**:

- **"Aktivt jobb"**-chip med statusprick + värde/"Inget valt", och **×-knappen** *"Stäng matchen — klar för dagen"* (visas bara när match är aktiv)
- **"Aktivt urval · {status}"** med mappikon, alt. "Inget urval valt / Klicka för att välja"
- **Synkmärket** — form och fyra lägen är låsta via C4; vi behöver bara veta hur det sitter i raden
- **Testlägesväxeln** (track+knob) + **testbannern** under toppbaren: *"TESTLÄGE · Allt skapas i minnet · exempelfiler skrivs till ~/DPT/test-output/ · inget sparas — rensas vid omstart"*
- **mock-pill** (bara i mockläge) och **temaknappen** ☾/☀

Frågan vi mest vill ha svar på: **hur mycket får den här raden väga?** Den konkurrerar med panelrubrikerna om blicken, och testbannern är avsiktligt skrikig. I D13-tonen finns risk att den blir ännu mer dominant.

Övriga B-punkter (Upprättning, ⌘K, ackrediteringsmejlets compose) — bekräftat att vi behåller nuvarande form. Inga skisser behövs.

---

## Status
Efter D18-SVAR + D19 är **hela D18 avklarad**. Med toppbaren (§3) och beskedet om referensfilen (§2a) har vi allt vi behöver från designsidan för v5/iOS v2.

Tidslås oförändrat: **bygg efter SM 24–26/7.**
