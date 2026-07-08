# Handoff → Claude Design: UI-synk efter implementation av **Matchpublicering**

**Vad det här är:** en statusrapport tillbaka till dig efter att vi byggt din
`handoff-matchpublicering` (HANDOFF.md + `.dc.html`-prototyp + 5 skärmdumpar) skarpt i DPT2-appen.
Det mesta är byggt precis enligt din spec — men flera ytor **utvecklades/klarnade under skarp
testning med Stig** och avviker nu från prototypen. De är markerade **⚠ AVVIKELSE** nedan;
uppdatera gärna din prototyp så bilderna matchar den byggda appen igen.

**Datum:** 2026-07-08.
**Gren/repo:** `dpt` → `dpt2-fas0` (pushad till origin). Commit-serie `cf09648 … bd8ad7e` (+ efterföljande
preview-/logo-fixar `73a5813`, `85246d0`, `8d9c800`, `32492e1`, `09a9d33`).
**Alla ändringar i:** `dpt/src/dpt2/` (backend `app.py`/`story_overlay.py` + Svelte i `ui/src/`).

---

## Kort sammanfattning

Din prototyp beskrev en **enhetlig publiceringsyta**: skapa ett matchinnehåll EN gång → publicera det
till alla kanaler. Den är byggd och ersätter helt den gamla `Publicera: Live + SoMe`-panelen.
Navigationen heter nu **"Matchpublicering"** (behöll intern id `publicera`, fortfarande steg 3 "Efter match").

Två strukturbeslut Stig tog (via frågeval i appen) styr resten:
1. **Full omfattning inkl. ny backend** — inte bara ett UI-skal.
2. **"På gång" = ren match-synk** — den kurerade aktivitets-CMS:en för den ytan är **borttagen** och
   ersatt av automatisk synk av kommande matcher. (Se §6 — påverkar även Innehåll-panelen.)

---

## Låst (oförändrat, respekterat)

- **Gren = färg utan textetikett:** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757` (ingen kant om gren okänd).
  Används som vänsterkant + mjuk glow på ResultatRemsa, kanalkort (låst) och På gång-prickar.
- **Horisont-grafiken** (Live-story-renderingen) och lag-loggornas contain-fallback.
- **Frontmatter-kontraktet mot webben** — På gång-synken speglar `_aktivitet_md`s frontmatter EXAKT
  (inga nya nycklar; Astro-schemat är strikt).

---

## 1. Hela appen är nu **mörk-först + full bredd** (⚠ VIKTIG synk)

Din prototyp (`.dc.html` bakgrund `#07090c`) och alla 5 skärmdumpar är **mörka och i full bredd**.
I första passet blev det ljust — panelen använder temavariabler och appens default-tema var `light`,
vilket dolde att designen var mörk-först.

**Fixat:** `App.svelte` default `tema='dark'` (mörkt vid start, `#0a0d11`; toggle finns kvar), och
`Publicera.svelte` tappade sin `max-width:1060px` → panelen sträcker sig över full bredd. Steg 2:s
fyra kanalkort sprider nu över hela ytan precis som i din prototyp.

> **Lärdom för framtida handoffs:** ange gärna uttryckligen om prototypen är mörk-först — temavariabler
> gör att en mörk design annars kan renderas ljus i appens default utan att det syns i spec:en.

---

## 2. Enhetlig panel: struktur (KLAR — enligt din spec)

Ny `Publicera.svelte` (~740 rader, ersätter den 1501-radiga Live+SoMe-panelen). Uppifrån och ned:

1. **Kicker + H1 + "Live nu"-knapp** (öppnar slide-over, se §7).
2. **Matchväljare** (dropdown över matcher).
3. **ResultatRemsa** (delad komponent, gren-kant, redigerbart resultat/mellanresultat/målskyttar,
   låst/read-only-läge när relevant). Previews auto-uppdateras när resultatet ändras.
4. **Steg 1 — Innehåll:** katalogväljare → bildrutnät (`listaSomeBilder`) med omslag, brödtext + tokens,
   länkar (galleri / hemsida).
5. **Steg 2 — Skicka till:** fyra kanalkort **live · ig · fb · webb** (se §3–4).
6. **Publiceringsrad "Publicera N"** = fan-out till de valda kanalerna (se §5).
7. **På gång (match-synk)-sektion** (se §6).
8. **Slide-overs:** "Live nu" (§7) och "Hämta bilder" (§8, ny ingest-yta).

---

## 3. Kanalformat (KLAR)

De fyra kanalkorten renderar i rätt bildförhållanden:

| Kanal | Format |
|-------|--------|
| live  | 9:16   |
| ig    | 4:5    |
| fb    | 1:1    |
| webb  | 2:1    |

Backend (`story_overlay.py`) fick nya format i `FORMAT_H` (`1x1` / `1.91x1` / `2x1` / `16x9` utöver
9x16 / 4x5) samt fokus- + zoom-crop (cover-crop runt fokuspunkten, behåller målformatets ratio).

---

## 4. ⚠ AVVIKELSE: crop-modellen — **fokus/crop per FOTO (i Steg 1), inte per kanal**

Din prototyp lät varje kanal i Steg 2 ha egen crop. Under byggandet valde Stig (frågeval) i stället
**"Fokus per bild i Steg 1"**, och modellen landade slutgiltigt så här:

- **Steg 1 bär croppen.** Klicka ett foto → en **crop-editor** öppnas under rutnätet: hela bilden visas
  + en **ram** (formatets ratio, storlek styrd av zoom, centrerad på fokus, mörklagt utanför via
  `box-shadow: 0 0 0 9999px …`), klick/dra flyttar fokus. ‹ ›-stegare mellan valda bilder,
  format-preview-chips, "Sätt som omslag", ✕ tar bort, aktiv bild = ring. (Samma UX som din tidigare
  `BildvaljareFokuspunkt`, nu inlinead i panelen.)
- **Varje foto bär sin egen `fokus` + `zoom`** och tar med sig den till alla kanaler — kanalens format
  omformar bara ramen kring samma fokuspunkt.
- **Steg 2-kanalkorten är därför READ-ONLY previews** — de visar omslaget beskuret till kanalens format
  med omslagets fokus. Ingen per-kanal-crop-kontroll längre. Kanalkortet har bara **på/av + format**.

**Rendering är helt server-side** (verktyget bestämmer, ingen "förhands-crop" i webbläsaren): varje kanal
renderas med kanalens format på croppen från fotot.

> **Att uppdatera i prototypen:** flytta crop-kontrollen från Steg 2-kanalerna till Steg 1
> (foto-editorn), och rita Steg 2-korten som låsta previews (format + på/av).

---

## 5. Publicering = fan-out (KLAR, med en öppen punkt)

"Publicera N" skickar till alla påslagna kanaler i ett svep:

- **live** → Horisont-story renderad i 9:16 (omslag + overlay).
- **ig / fb** → server-renderad grafik i kanalens format; postar hela det valda bildsetet
  (ig ≤10 karusell, fb ≤4, första med overlay).
- **webb** → artikel + hero (omslaget server-croppat till hero-format), texten skickas UTAN @/# och
  utan self-hemsidalänk.

Testläget exporterar HELA urvalet numrerat till en delad testmapp (fångade en regression där bara
första bilden exporterades — nu åtgärdad).

> ⚠ **Öppen punkt (kanske inte prototyp-synligt):** per-foto-croppen (fokus+zoom) för IG/FB driver just nu
> previewen; själva fotona postas som Lightroom-exporten. Skarp server-crop-per-foto för IG/FB är en
> separat framtida bit. Ingen designåtgärd krävs — noteras för fullständighet.

---

## 6. ⚠ STOR AVVIKELSE: "På gång" = ren match-synk (kurerad aktivitets-CMS BORTTAGEN)

Detta är den största strukturändringen mot tidigare bild.

- **På gång-sektionen i Matchpublicering** listar kommande matcher (ur `matchen`, inget resultat +
  datum ≥ idag) med en visa/dölj-flagga. "Publicera På gång" gör en **FULL SYNK**: den äger hela
  `pagang`-samlingen på webben och reconcile-raderar allt annat. Ersätter alltså de tidigare
  kurerade aktiviteterna.
- **Följd i Innehåll-panelen:** `Innehall.svelte` är omskriven — flikarna **Sport (`match`)** och
  **På gång (`pagang`)** är **borttagna** tillsammans med all match-only-logik (autofill, auto-status,
  Bildsvep-generatorn, hero-fältet). Innehåll har nu bara tre typer kvar: **Blog · Landskap · Event**.
- Den gamla `PaGang.svelte`-panelen och hela aktivitet-CMS-backenden (store/app/api/schema + `aktivitet`-
  tabellen) är **helt borttagna** (schema v16→v17 droppar tabellen).

> **Att uppdatera i prototypen:** (a) Innehåll-typväljaren visar bara Blog/Landskap/Event (inte fem typer).
> (b) "På gång"-redigeringen är inte längre ett kurerat listformulär — det är en matchlista med visa/dölj +
> en "Publicera På gång"-knapp inne i Matchpublicering.

---

## 7. Live nu (slide-over) — eget bildrutnät (⚠ liten avvikelse)

"Live nu"-slide-overn (snabbpublicering av ett live-moment) hade först Steg 1:s urval. Stig: *"Live-flödet
måste ha en egen grid, kan inte delas."* Nu har Live **eget urval** — egen katalogväljare (Välj…) +
"↻ Uppdatera", startar i huvudkatalogen men är en helt egen lista (delar bara thumbnail-cachen).
Sport-anpassade moment: **Slutresultat · Avspark · Halvtid · Målgörare**.

---

## 8. Hämta bilder (slide-over) — NY ingest-yta

Ny ingång "Hämta bilder…" (permanent knapp bredvid "Välj katalog…", samt i tom-katalog-läget):

- Scannar minneskort (`/Volumes` med DCIM), räknar **skyddade** (låsta/read-only) bilder.
- Exporterar BARA de skyddade bilderna till en mapp och öppnar Lightroom.
- Tredelat flöde med kortväljare.

Detta motsvarar "hämta in råmaterial före redigering" och är en ny yta jämfört med tidigare prototyper —
värd att rita in om du vill ha den i designbilden.

---

## Teknisk gotcha som påverkar design-previews (bra att känna till)

Appen laddas från `file://` och pywebviews WKWebView **blockerar `<img src="file://…">`**. Allt
diskbild-visande (source-foton, renderade previews, lag-loggor) går därför nu via **base64 data-URI**.
Det betyder bara: i den byggda appen visas riktiga miniatyrer/loggor korrekt (mot tidigare tomma rutor).
Ingen designåtgärd — men förklarar varför tidigare "Live-preview visades inte"-rapporter uppstod.

---

## Status & verifiering

- `vite build` grön; preview-verifierad i mock (mörkt tema): kicker/H1/Live nu-knapp, matchväljare,
  ResultatRemsa med gren-kant, Steg 1, Steg 2 fyra kanaler i rätt ratios + gren-glow, På gång med
  gren-prickar, Live nu-slide-over, Hämta bilder, Innehåll = Blog/Landskap/Event. Inga konsollfel.
- `pytest src/dpt2` = 415 gröna (1 förbefintlig, orelaterad cv2/Hough-röd).
- **Pushad** till `origin/dpt2-fas0`.
- **Återstår (kräver Stigs skarpa pywebview-körning, ej headless-verifierbart):** minneskort-ingest mot
  riktigt kort, content-sync På gång-synk mot deployad worker, riktiga Meta-publiceringar, renders med
  spaces-i-sökväg. Dessa är inga designändringar.

---

## Att göra i Claude Design (sammanfattat)

1. Sätt prototypen **mörk-först + full bredd** som appens grundläge (§1).
2. Flytta crop-kontrollen till **Steg 1 (foto-editor)**; rita Steg 2-kanalkorten som **låsta previews**
   (format + på/av) (§4).
3. Rita **På gång** som en matchlista med visa/dölj + "Publicera På gång" inne i Matchpublicering, och
   **Innehåll** med bara tre typer (Blog/Landskap/Event) (§6).
4. Ge **Live nu** ett eget bildrutnät (§7).
5. Rita in **Hämta bilder**-ingest-slide-overn om den ska vara med i designbilden (§8).
