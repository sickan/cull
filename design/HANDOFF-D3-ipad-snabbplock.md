# Design-handoff D3 — iPad-layout för Snabbplock

*2026-07-16 · Till: Claude Design · Från: Code · Prio 4-spåret (efter friidrott).*

## Uppdraget

Hur DPT-appen nyttjar **iPad Air (gen 4)-ytan**, med Snabbplock som huvudfall:
plocka bilder med mer arbetsyta, sida vid sida med **Lightroom Mobile**
(Split View/Stage Manager).

## Fakta

- Appen är idag iPhone-designad (5 flikar, mörk Skagen Hav, Saira).
  På iPad körs den uppskalad — ingen anpassning finns.
- DPT2-desktopens Snabbplock: 5-stegs flöde Kort in → Plocka (grid med
  RAW-previews) → Mata ut → Granska → Lightroom.
- Code kör parallellt en teknisk spike (B-008: universal app vs uppskalad,
  size classes) — designens svar och spikens rekommendation möts.

## Frågor att landa

1. **Plockgriden på iPad:** kolumner/storlekar i regular width? Previews +
   snabbval (stjärna/flagga) med touch — och Apple Pencil som bonus?
2. **Split View-läget bredvid LR Mobile:** vad visar appen i halv/tredjedels
   bredd — komprimerad plockgrid eller kölista?
3. **Övriga flikar på iPad:** bara skala upp, eller sidebar-navigation
   (NavigationSplitView) i stället för tabbar?
4. Stage Manager: något särskilt värt att utnyttja, eller ignorera v1?

## Leverabel

Mockups för plockgriden (fullskärm + Split View) + beslut på fråga 3.
Referens: `BACKLOG.md` (B-008, D3), DPT2 `Snabbplock.svelte`-flödet.
