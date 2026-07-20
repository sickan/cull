# Design-handoff D10 — Rörligt material (NYTT design-jobb)

*2026-07-19 · Till: Claude Design · Från: Code · Grön mark: det finns
inget videostöd någonstans i stacken idag. Designen behövs INNAN första
skivan byggs — därför tas den nu, medan bara datamodellen är påbörjad.*

## Bakgrund

Stig vill få in rörligt material i flödet: snabba klipp från mobilen,
tagningar från **DJI Pocket 4 Pro**, och färdigredigerat material
exporterat ur **DaVinci Resolve**. Två mottagare: **SoMe** (främst
Instagram) och **kundleverans**.

Idag stannar allt rörligt utanför systemet — det klipps och postas för
hand. Målet är att klipp ska bete sig som NEF:er redan gör: hittas,
kopplas till ett fotojobb/en match, förhandsvisas, publiceras och
levereras ur samma ytor som stillbilderna.

## Dagens läge (fakta — verifierat i koden 19/7)

- **Noll videostöd.** Inga `.mp4`/`.mov`/ffmpeg-spår i `src/dpt2/`,
  `content-sync/` eller Astro-sajten. Enda träffen är en testfixtur.
- **"Film" är upptaget och betyder något annat.** Innehållstypen `film`
  (`app.py:3365`, `Innehall.svelte:30`) och `src/pages/film.astro` är
  **analog film** — Nikon FM3A, Kodak Portra 400. Rörligt måste heta
  något annat. Code föreslår domännamnet **Rörligt** och enheten
  **klipp**. *Namnet är en designfråga — se F1.*
- **Publiceringsmodellen finns.** `PUBLICERA-SOME-HANDOVER.md` definierar
  `Paket { bilder, caption, mal }` → förhandsvisad **plan-lista** → dry-run
  eller skarp körning med per-post-utfall. Rörligt ska in i *samma* modell,
  inte i ett parallellt flöde.
- **Horisont-renderaren** (`motorer/story_overlay.py`, Pillow) är enda
  grafik-implementationen och körs både på Macen och i molncontainern.
- **iOS-appen** har background-URLSession mot privat R2-prefix (NEF idag).

## Låst i arkitekturen (designa runt — hitta inte på nytt)

Detta är beslutat av Code och ändras inte av designen:

1. **Proxy-principen.** En 4K-tagning från Pocket 4 Pro är 1,5–4 GB.
   Mastern stannar alltid lokalt på Macen. Vid ingest skapas en
   **proxy** (720p H.264) + en **poster-JPEG**. Det är proxyn som reser —
   till molnet, till telefonen, till alla förhandsvisningar. Samma
   icke-destruktiva tanke som NEF → XMP → Lightroom.
   *Designkonsekvens:* allt UI visar proxy. Det finns alltid ett litet
   glapp mellan "klippet finns" och "proxyn är klar" — det behöver ett
   tillstånd.

2. **En renderare gäller fortfarande.** Pillow ritar, ffmpeg
   **komponerar** — Pillow producerar ett transparent PNG-överlägg med
   samma moment/tema/format som stillbildsstoryn, ffmpeg lägger det på
   videon. Ingen andra grafikimplementation. Matchgrafiken på ett reel
   ser alltså **exakt** ut som på en stillbildsstory.
   *Designkonsekvens:* du designar ingen ny grafik — du designar hur man
   väljer och förhandsvisar den befintliga ovanpå rörligt.

3. **Reels-publicering är asynkron.** Meta Graph API tar emot, returnerar
   ett container-id, och man måste polla tills `FINISHED`. Ett reel är
   alltså inte "postat" när knappen släpper — det tar typiskt 20–60 s.
   Foto är synkront. *Detta bryter dagens `Post n/tot`-progress.*

4. **Tre ingångar:** iPhone (proxy exporteras på telefonen och laddas
   upp), Pocket-kort (kortläsare på Macen, som Z8), och en **bevakad
   Resolve-exportmapp** (färdigt material — ingen proxy behövs).

## Kanalernas hårda gränser (ska kommuniceras i UI:t, som FB-kapet idag)

| Mål | Gräns | Vad UI:t måste säga |
|---|---|---|
| IG Reel | 9:16, ≤ 90 s | "2:14 → för långt för reel (max 1:30)" |
| IG Story (video) | ≤ 60 s/segment | "1:45 → 2 story-segment" |
| FB Reel | egen endpoint, caption strippas på `#`/`@` | samma diff-vy som idag |

Samma anda som de befintliga varningarna ("15 bilder → 2 IG-inlägg",
"6 bilder → kapat till 4 på Facebook"): gula, informerande, inte
blockerande.

## Frågor att landa

**F1 · Vad heter det, och var bor det?**
"Rörligt"? "Klipp"? "Video"? Och: egen panel i DPT2:s rail, eller en flik
inuti befintliga ytor (Leverera/Publicera)? Panelen Publicera är redan
lång — samma oro som §5.4 i SoMe-handovern.

**F2 · Klipp-vyn: hur granskar man rörligt?**
Stillbilder har miniatyr-strip och Snabbplock. Ett klipp går inte att
bedöma på en miniatyr. Behövs scrubbing? Hover-preview? In-/utpunkter
direkt i DPT2, eller är trimning alltid Resolves jobb? *Code:s hypotes:
enkel in/ut för snabbklipp, allt annat går via Resolve — men det är din
bedömning.*

**F3 · Blandade paket — bild och klipp i samma publicering?**
Ett matchpaket kan vara 8 bilder + 1 klipp. Går de i samma paket (och
plan-listan sorterar ut vad som blir karusell och vad som blir reel),
eller är rörligt ett eget paket? Karusell med blandad media är tekniskt
möjligt men gör plan-listan svårläst.

**F4 · Plan-listan när en post är asynkron.**
Idag: `Post 3/6 …` → ✓ med länk. Ett reel är "inskickat, bearbetas,
publicerat" — tre lägen, och det kan misslyckas *efter* att panelen
stängts. Hur visas det? Behövs ett "pågår"-tillstånd som överlever att
man byter panel? (Publiceringsstatus-språket från **D9** — 🔵🟡🟢🔴 —
ligger nära; kan samma språk återanvändas?)

**F5 · Grafik ovanpå rörligt — hur väljs och förhandsvisas den?**
Matchdag-kortet har chips för moment/tema/format och renderar en still.
För rörligt: samma chips, men vad visar förhandsvisningen — en frusen
ruta med överlägget, eller spelas proxyn upp? Och var i klippet ska
överlägget ligga (hela tiden / första 3 s / endcard)?

**F6 · Kundleverans — vilken form?**
Stillbilder går via Lightroom/Pixieset. För rörligt lutar Code åt **R2 +
signerad länk med utgångsdatum** (egen kedja, leveransstatus kan bo i
`dpt.db` bredvid fotojobbet — "levererat 14:20, öppnat 2 ggr") framför
Pixieset video (noll bygge men en sanning till att hålla reda på).
Designfrågan: hur ser **kundens** sida ut, och hur ser fotografens
leveransvy ut i DPT2?

**F7 · Ingest-tillstånden.**
Ett klipp kan vara: hittat men oproxat · proxas (progress) · redo ·
master saknas (extern disk urkopplad) · Resolve-export som just landat.
Hur syns de utan att bli en teknisk statuslista i ansiktet på Stig?

## Ej i scope för D10

- TikTok (kräver egen audit — samma avgränsning som SoMe-handovern gjorde).
- Animerad grafik / PNG-sekvenser. Statiskt Pillow-överlägg först.
- Video på publika sajten (hero-video, inbäddade klipp i blogg). Egen
  handoff när ingesten finns. **`film.astro` ska inte röras.**
- HLS/adaptiv streaming. En `<video>` med `poster` mot R2 räcker länge.

## Leverabel

1. Mockup av **klipp-vyn** (F1, F2, F7) — hur rörligt material ser ut och
   granskas i DPT2.
2. Mockup av **plan-listan med rörligt** (F3, F4) — inklusive det
   asynkrona reel-tillståndet och längd-varningarna.
3. Skiss/text för **grafik-förhandsvisningen** (F5).
4. Skiss för **leveransvyn**, både fotografens och kundens (F6).

Referenser: `PUBLICERA-SOME-HANDOVER.md` (paketmodell, plan-lista, FB-diff,
Skagen Hav-tokens §7), `HANDOFF-D9-publiceringsstatus.md` (statusspråket),
`~/Claude/dokumentation/ARKITEKTUR.md` (renderarprincipen, R2-ytorna).

## Tidsläge

Friidrotts-SM är 24–26/7. Skiva 1 (ingest: tabeller, kortdetektering,
Resolve-mapp, proxy-generering) rör inga filer som SM-spåret rör och kan
byggas parallellt. Skiva 2 och framåt (render, publicering, leverans)
väntar till efter SM. **Designsvaret behövs alltså inte i panik — men
det ska finnas innan skiva 2 påbörjas.**
