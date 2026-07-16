# Design-svar D3 — iPad-layout för Snabbplock

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D3-ipad-snabbplock.md` (B-008). Mockups: `iOS D3 - iPad Snabbplock.dc.html`
(fullskärm 1180×820 + Split View halv/tredjedel).*

## Beslut på fråga 1–4

**1. Plockgriden fullskärm (regular width):**
- **5 kolumner**, celler ~180×132 (3:2-previews), gap 10, radie 8. 248 RAW ryms i ~4
  skärmhöjder — snabbt nog att svepa igenom.
- **Tap på bilden = plocka/avplocka** (hela cellen är träffytan, inte en liten knapp).
  Plockad cell får 2px accent-outline + ★ uppe vänster.
- Nedre högra hörnet: **★- och ⚑-knappar 30×30** (över 44pt träffyta med padding) för
  stjärna respektive flagga utan att växla plockstatus.
- **Håll = 100 % loupe** (samma som telefonen). **Apple Pencil: hover = förhandsloupe**
  (Pencil 2/Pro hover-event), tap med pennan = samma som finger. Bonus, aldrig krav —
  allt går med touch.
- Stegraden (Kort in › Plocka › Mata ut › Granska › Lightroom) blir en kompakt
  brödsmula i headern i stället för telefonens fullbredds-stepper.
- Primärknappen ("Mata ut 31 →") ligger i en fast bottenlist, höger.

**2. Split View bredvid LR Mobile:**
- **Halv bredd (~590pt): samma plockgrid i 3 kolumner** — plocket fungerar på riktigt
  sida vid sida med Lightroom. ⚑ flyttar till håll-menyn (bara ★ synlig knapp);
  stegraden reduceras till aktivt stegnamn.
- **Tredjedels bredd (~390pt): Utmatningskön** — INTE en hoptryckt grid. I det läget är
  Lightroom huvudytan; DPT:s jobb är att visa vad som är plockat och var det är i kedjan:
  radlista med thumb + filnummer + status-chip (I kö · Matar ut… · I Lightroom).
  Brytpunkt: grid < 500pt bredd → kölistan.
- Statusspråket i kön återanvänder D9-chipen (kompakt-läget).

**3. Navigation på iPad: sidebar (NavigationSplitView), inte tabbar.**
Vänsterkolumn 224pt: Hem · Matcher · Kalender · Fotojobb · Bilder + sektionen
**VERKTYG** (Snabbplock, Story/SoMe) + Inställningar i botten. Motiv: 5 tabbar centrerade
på 1180pt är ödsligt; sidebaren ger Verktygs-gruppen ett hem (Snabbplock är ett verktyg,
inte en flik — idag gömd bakom Hem-kort på telefonen). iPhone behåller tabbaren
oförändrad. I kompakt width på iPad (Split View smal) faller sidebaren tillbaka till
tabbar — standard NavigationSplitView-beteende, ingen egen kod.

**4. Stage Manager: ignoreras i v1.** Kravet är bara att appen beter sig väl i godtycklig
fönsterbredd — och det får vi gratis via size class-brytpunkterna ovan (regular = sidebar
+ 5 kolumner; ~600pt = 3 kolumner; <500pt = kölista). Inga Stage Manager-specifika ytor.

## Till spiken (B-008)
Designen förutsätter **universal app med size classes** — inte uppskalad iPhone-app
(Split View/Pencil/sidebar finns inte annars). Brytpunkterna ovan är designens kontrakt:
`regular ≥ 700pt` → 5 kol + sidebar · `500–700pt` → 3 kol + kompakt header ·
`< 500pt` → kölista + tabbar.
