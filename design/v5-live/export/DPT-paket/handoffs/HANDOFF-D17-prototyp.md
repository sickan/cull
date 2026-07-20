# Design-handoff D17 — DPT v5 klickbar prototyp (spec)

*2026-07-20 · Från: Claude Design · Till: Code*
*Fil: `DPT v5 - Prototyp.dc.html` (kopia — spec-filen `DPT v5.dc.html` orörd).*

## Vad den är
En sammanhållen, klickbar desktop-prototyp byggd på UX-lyftet i `DPT v5.dc.html`, med **dagens D16-strukturbeslut inbyggda** och en ny **Idag**-landning som ytterdörr. Tänkt som klickbar spec — navigera hela vägen, inte lösryckta skärmar.

## Nytt i denna prototyp (utöver befintliga flöden)
1. **Idag (landning, ny toppnivå i nav).** Öppnar som startpanel.
   - *Kräver åtgärd* — kön härleds ur riktig state (ackreditering ej beviljad, matcher utan inläst trupp, pågående gallring, utkast ej levererade, delvis publicering). Varje rad navigerar in i rätt panel.
   - *Närmast på tur* — nästa matcher ur `upcoming`; klick → befintligt matchflöde (`goFromMatch`). Statistik, Inkorg & svar, Snabbvägar.
2. **Nav enligt D16:** `Idag · Fotojobb · Tävlingar · Lag & utövare` + Efter jobb/Webb/System oförändrat.
   - **Matcher** borttagen som egen nav-post → **genväg i Fotojobb-headern** (öppnar matchvyn).
   - **Event → Tävlingar**, som nu rymmer **Event + Ligor** via segment högst upp. Ligor-listan byggs ur `state.comps`; noten pekar på `tavling_id`-kopplingen.
   - **Lag & ligor → Lag & utövare.** Ligor-fliken **borttagen ur registret** (bor nu i Tävlingar). Registret = Lag + Individer, editor auto-morphar (Lag/Individ per vald post).

## Bevarat / invarianter
- Inga låsta funktioner rörda: Gren-palett (färgad kant, ingen textetikett) och Publicera→Live står kvar. Fältflödet, Gallra/Leverera/Publicera, Innehåll/På gång, Inställningar/målmappar oförändrade.
- Demo-scenariot är befintligt (Damallsvenskan: MFF/Kristianstad/Rosengård/Hammarby + EM Volleyboll) — Idag-kön speglar det.

## Att notera för Code
- Idag-kön/statistik/inkorg är härledda i prototypen men ska mot riktiga källor (ackrediteringsstatus, leverans-/gallringsläge, `tavling_id`).
- Tävlingars Ligor-vy är i prototypen en läslista; full liga-editor finns kvar (nås i denna prototyp ej från registret — flyttas dit i bygget). Event↔Ligor under en gemensam Tävlingar-datamodell är den återstående datastrukturen (M-11 bär kopplingen).
- Bygg **efter SM**, löpande merge — samma tidslås som D14/D16.

## Relation till tidigare handoffs
- **D16** (struktur, widget, Idag) är besluten; D17 är dem inbyggda i den körbara prototypen.
- iOS-sidan (D14 jobbet äger matcher, rik låsskärm) speglar samma merge på telefon — separat spår.
