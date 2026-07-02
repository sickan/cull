# Handoff → Claude Code: Innehåll-panelen — fast tema, bild-only-galleri, Sport-höjdpunkter

Avgränsade ändringar i **Innehåll** (panel `innehall`, appens CMS) som gör att appen och
webbplatsen delar samma innehållsmodell. Speglar prototypen (`Dalecarlia Photo Tools.dc.html`).
Tokens = Skagen Hav (oförändrade).

> Gren-markören (Herr/Dam/Mix) är ett **separat** pass — se `design_handoff_gren_markor/`.
> Webbsidans motsvarande ändringar finns i `design_handoff_webb_synk/`.

Skärmdumpar: `skarmdumpar/01-landskap.png` (låst Sol + bild-only-galleri),
`skarmdumpar/02-sport-hojdpunkter.png` (Hämta från Publicera-urvalet).

---

## 1. Fast tema per typ — Landskap-temaväljaren borttagen

Temat (Skagen) härleds nu ur innehållstypen, inte ur ett val i posten:
**Sport = Hav, Landskap = Sol, Event = Rosé, Blog = ärver.** Färgerna finns redan i
`CATCOL = { matcher:'#2F7CB0', landskap:'#C9871F', event:'#C9657F', blogg:'#6E8B5E' }` (styr flik-korten).

- Landskaps **Sol/Hav/Rosé-väljare är borttagen**, ersatt med en **låst indikator** ("Tema · Sol
  · låst för Landskap").
- `tema`-raden är borttagen ur landskap-frontmatter (`fmLines`). Ingen typ skriver längre `tema:`.
- I appen: temat är en fast egenskap av `typ`. Webben sätter accent per sektion (se webb-handoff).

## 2. Galleri utan textfält för Landskap & Event

```js
const galText = !(isLa || isEvt); // Sport & Blog = alt+bildtext; Landskap & Event = endast bild
```

- **Sport & Blog:** galleriraden har `alt` + `bildtext` (som förr). Markdown:
  `![{alt}](/bilder/{slug}/{n}.jpg)` + rad `*{cap}*`.
- **Landskap & Event:** raden visar bara **bild + filreferens** (ingen input). Markdown:
  `![](/bilder/{slug}/{n}.jpg)` (ingen bildtextrad).
- Styrs i template av `cmsGalText` / `cmsGalImgOnly` (`<sc-if>`), och i `galleryMd`-genereringen.

## 3. Sport — "Hämta från Publicera-urvalet"

Knapp i galleri-kortets rubrik (**endast Sport**, `isCmsMatch`) som fyller höjdpunktsgalleriet från
det aktiva urvalet:

```js
pullHighlights(){
  const c=this.state.cms, sel=this.state.sel;
  const n = Math.min((sel && sel.n) || 6, 6);           // upp till 6 höjdpunkter
  const src = (sel && sel.name) || (c.hem+' – '+c.borta); // fallback = aktiva matchen
  const blocks = Array.from({length:n}).map((_,i)=>({
    alt: (c.hem+' '+c.resultat+' '+c.borta).trim()+' — höjdpunkt '+(i+1),
    cap: '',
    src: 'DSC_0'+(417+i)+'.jpg'                          // provenienstagg (fil ur urvalet)
  }));
  this.setState(s=>({ cms:{...s.cms, blocks}, hlSource:src, hlFlash:true }));
  setTimeout(()=>this.setState({hlFlash:false}), 2200);
}
```

- Varje bildrad förifylls med **alt ur matchinfo** och en **provenienstagg** ("från urval · DSC_0417.jpg").
- Rubrikraden visar källan: *"N höjdpunkter hämtade från {urval/match}"* (`hlHasSource` / `hlSourceMsg`).
- Bilderna hamnar direkt i markdown-förhandsvisningen och sparas med `.md`-filen.
- **I produktion:** `sel` = det gallrade urvalet (Gallra→Leverera). Hämta de favoritmarkerade/topp-
  rankade filerna därifrån istället för de simulerade `DSC_0###.jpg`. Bildreferensen i `.md` blir
  `/bilder/{slug}/{n}.jpg`; `src` är spårbarhet till originalfilen.

## Kodreferenser (renderVals + metod)
- `pullHighlights()` — metod på `Component`.
- renderVals: `galText`, `cmsGalText`, `cmsGalImgOnly`, `hlFlash`, `hlFlashMsg`, `hlHasSource`,
  `hlSourceMsg`; per bildblock `fileRef`, `hasSrc`, `srcLabel`.
- `fmLines` (landskap) — `tema`-raden borttagen. `galleryMd` — villkorad på `galText`.
- `cmsBlocksLabel` — `'Bilder · höjdpunkter'` för Sport, annars `'Galleri'`.

## Oförändrat
- Sport-formuläret återanvänder redan match-väljaren (lag/ligor/matcher ur **Matcher**) + Bildsvepet
  (`svep`) ur **Publicera** — det är avsiktligt kvar.
- Blog: `body` + "Platser & tips" oförändrat.

---

## Filer

| Fil | Vad |
|-----|-----|
| `Dalecarlia Photo Tools.dc.html` | Hela appen (senaste, med Innehåll-ändringarna). |
| `Combobox.dc.html`, `support.js`, `image-slot.js` | Delkomponent + runtime + bild-platshållare. |
| `skarmdumpar/` | Landskap (låst Sol + bild-only); Sport med höjdpunktshämtning. |
