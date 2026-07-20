# HANDOFF — Etapp 2–4: UX-lyftet (gallring, publicering, Innehåll, jobbnav)

*2026-07-17 · Till: Code (DPT2 + iOS) · Från: Claude Design*
*Bygger på `HANDOFF.md` (etapp 1). Mockup för allt nedan: `DPT v5.dc.html` (+ `DPT iOS v2 — Event.dc.html` frame C). Löpande merge — varje § kan tas separat.*

---

## §8 · Jobbet som nav (skiss 4a)

- Toppradens chip + arbetsflödenas remsa heter **"Aktivt jobb"** (inte "Aktiv match"). Sportjobb visar match-/eventdata som idag; andra kategorier visar jobbets namn + schema.
- Nav-sektionen **"Efter match" → "Efter jobb"**; "Matchpublicering" → **"Publicera"**.
- Tomläge: "Inget aktivt jobb — stegen fungerar ändå, men koppla ett jobb (match, event, bröllop…)".
- Kategorier: toppnivå statisk (Sport/Landskap/Människor/Film), underkategorier redigerbart register — se `DATAMODELL v5.md`.

## §9 · Gallra som ett flöde (3a) + tyst träning (3b) + profiler (4d)

- Stegindikator överst: **1 Mål → 2 Kör → 3 Granska**. Snabb-/rapportläge är växlar under Kör, inte egna verktygskort (befintliga verktygskort behålls tills vidare — indikatorn är ramen).
- **Profilkort** under stegen: segmentval Sport · Bröllop · Landskap · Porträtt/Student, förvald ur jobbets kategori. Profilen styr vilka signaler som väger (mockupen listar signal-chips per profil). Din smak-modellen är gemensam.
- **Träna försvinner ur nav.** Varje Behåll/Släng-val i granskningen blir träningsdata tyst. Modellstatus + manuell omträning + Five-Star-import flyttar till Inställningar (rad, inte sektion) — ej mockad ännu, ta befintliga Träna-panelens innehåll dit.

## §10 · Publicera: momentmallar (3c/4c) + publiceringskö (3d)

- **Momentkort** överst: jobbets momentmall som chips med status (✓ klar / accent = nästa / streckad = ej påbörjad). Mallar per kategori:
  - Sport (match): Startelva · Avspark · Halvtid · Målgörare · Resultat · Nästa match (befintligt).
  - Landskap: **Ny serie · Platsen · Bakom kulisserna · Blogg-puff.** Länk till hemsidan valfri per inlägg.
  - Människor (Porträtt/Bröllop/Student/Företag/Mode): **Tjuvkik · Leverans klar** — visas ENDAST när jobbets flagga `some: true` är satt. Samtycket bor i avtalet; verktyget lagrar det inte.
  - Film: Ny film · Stillbilder · Bakom kameran.
  - Kanaler: IG + FB för alla kategorier (befintliga formatregler per kanal gäller).
- **Publiceringskö-kort**: alla material på väg ut med status ✓ publicerad HH:MM / schemalagd (tid) / utkast. Löser "delvis publicerad"-luckan. Schemaläggning = fältdelta `publiceras: <tidpunkt>`; själva API-utskicket per kanal är Codes avvägning (manuell påminnelse duger i steg 1).

## §11 · Innehåll: granskningskö (3e) + Film-typ

- **"Att granska"-remsa** överst i Innehåll: auto-utkast som väntar (matchartikel efter Resultat-story; eventsida som auto-uppdateras). Klick → respektive editor. Editorn är steg 2, inte startpunkten.
- Typ-naven blir **Sport · Landskap · Människor · Blogg · Film** (Film ny, tom lista + "+ Ny film"-mönster som övriga). Människor filtreras vidare på underkategori.

## §12 · Målmappar (backlog §4) + original utan overlay (§5) — nu även i UI

- **Inställningar → Målmappar**: tre fält med mappväljare — Snabbplock (även backup), Gallring (SSD), Generera media (Dropbox). Not om original-utan-overlay-regeln visas här.
- **Override i flödet**: Leverera visar målmappen förifylld + "Ändra för denna körning…" (gäller bara körningen). Samma mönster ska in i Snabbplock- och Gallra-panelerna (ej mockat där — följ Leverera).

## §13 · ★ iOS-bakgrund — DPT2-sidan (1j)

- I **Leverera**: "★ iOS-bakgrund"-block — bildgrid där klick togglar ★ (accent-outline + stjärna). Flaggade bilder taggas med jobbets sport/kategori och utgör appens bakgrundspott.
- Fältdelta: `ios_bakgrund: true` per bild (redan i etapp 1-handoffens delta). Appen roterar i potten för dagens kategori → egen bild → standard.

## §14 · iOS Hem per jobbtyp (4b)

- Hemskärmens byggklossar är generella; innehållet följer jobbtypen. Mockad: **landskapsjobb** (frame C) — kategoribadge (Landskap-amber), plats, väder vid målet, **Blå timmen / Gyllene timmen / Soluppgång** i stället för matchtider, "nästa schemapunkt" + ÅK SENAST med restid inkl. vandring.
- Samma mönster för Människor-jobb (schema ur jobbet: vigsel/utspring osv). Ingen ny skärm — samma Hem.

## Fältdelta (etapp 2–4)

- Jobb: `some: bool` (Människor-jobb), kategori/underkategori-ref (etapp 1).
- Kategori-register: `gallringsprofil`, `some_moment[]` per underkategori.
- SoMe-material: `publiceras: <tidpunkt|null>`, status `publicerad|schemalagd|utkast` + publicerad-tid per kanal.
- Inställningar: `mapp_snabbplock`, `mapp_gallring`, `mapp_media` (etapp 1) + per-körning-override (ej persistent).
- Gallring: `profil: sport|brollop|landskap|portratt` på cull-jobbet (default ur jobbets kategori).
- Träning: oförändrad datamodell — bara ny källa (granskningsval) och ny plats (Inställningar).
