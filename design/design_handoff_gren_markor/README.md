# Handoff → Claude Code: Gren-markör (Herr / Dam / Mix / ej satt)

Liten, avgränsad visuell markör som visar en matchs **gren** (kön/klass) på matchraden och i
story-förhandsvisningen. Speglar prototypen (`Dalecarlia Photo Tools.dc.html`). Tokens = Skagen
Hav (oförändrade).

Markören är **fristående från Skagen-temat** (Hav/Sol/Rosé, som kodar *innehållstyp*). Egen palett,
egen betydelse — de två axlarna lever bredvid varandra utan att krocka.

Skärmdumpar: `skarmdumpar/01-matcher-gren.png` (matchraden, skarpt i appen),
`skarmdumpar/02-treatment-1c.png` (de fyra lägena + matchrad), `skarmdumpar/03-inlagg-ribba.png`
(ribban i inlägg/story).

---

## 1. Datakälla — inget nytt fält behövs

`gren` finns **redan** på laget (`teams[].gren` = `'Dam' | 'Herr' | 'Mixed'`), satt via den
befintliga segmentväljaren i **Lag & tävlingar**. Matchens gren **härleds** från hemmalaget:

```js
const _grenOf = (nm) => { const t = _teamByName[nm]; return (t && t.gren) || ''; };
```

Saknas laget eller dess gren (t.ex. individ/utövare) → tom sträng = **"ej satt"**.

> Regel vid Herr–Dam-möte (ovanligt): hemmalagets gren styr. Vill man i stället ta gren från
> tävlingen/serien, byt `_grenOf(m.home)` mot en uppslagning på matchens `comp`.

## 2. Palett + hjälpare (fristående, INTE Hav/Sol/Rosé)

```js
const GRENCOL = { Herr:'#3E7C87', Dam:'#8E5A86', Mixed:'#6E8757' }; // teal · plommon · mossgrön
const _grenCol = (g) => GRENCOL[g] || '#8A8172';                    // fallback = neutral (ej satt)
const _grenLbl = (g) => ({ Herr:'Herr', Dam:'Dam', Mixed:'Mix' }[g] || ''); // ej satt = ingen label
```

Tonerna är avsiktligt dämpade så de sitter lugnt i den varma paletten och inte konkurrerar med
guld-accenten. Fungerar likadant i mörkt tema (rena hex, ej token-beroende).

## 3. Matchraden — kant-accent + liten label

Varje matchkort får en **färgad vänsterkant** efter gren, och en liten versal label i metaraden.

- Kant: läggs ovanpå det befintliga kort-objektet (`matchCard`) utan att röra resten:
  ```js
  card: Object.assign({}, matchCard(open), {
    borderLeft: '3px ' + (_grenOf(m.home) ? 'solid' : 'dashed') + ' ' + _grenCol(_grenOf(m.home))
  })
  ```
  **Ej satt ⇒ streckad** neutral kant (ingen färg­signal).
- Label: liten `Saira Condensed`, versal, i gren-färgen, **före** metatexten. Döljs helt när gren
  saknas (`grenHas = !!_grenOf(m.home)` gaterar en `<sc-if>`), så individ-/otaggade rader inte får
  ett stökigt "EJ SATT".

## 4. Story-förhandsvisning — ribba + hörn-label

I **Publicera → Live → Skapa story** får preview-rutan en 5px **ribba** i vänsterkanten + en diskret
versal label uppe till vänster, färgad efter den **aktiva matchens** gren:

```js
const _amGren   = _grenOf(_amHome);          // aktiv match, hemmalag
const ovGrenHas = liveHasSel && !!_amGren;    // visas bara när en bild är vald + gren känd
const ovGrenCol = _grenCol(_amGren);
const ovGrenLabel = _grenLbl(_amGren);
```

Ribban ligger `position:absolute` ovanpå bilden (`z-index:2`) och påverkar inte det befintliga
tema-kickern (`ovThemeCol`) — de samexisterar (posten är t.ex. *Hav* för att den är sport, och
*Dam* för gren). Se `03-inlagg-ribba.png`.

## 5. Rör INTE (utanför detta pass)

- **Lag & tävlingar**-korten och **SoMe-planen** (Publicera → SoMe) har medvetet *inte* fått
  markören ännu — lätt att lägga till med samma `_grenCol`/`_grenLbl` om det önskas.
- Skagen-temats mekanik (Hav/Sol/Rosé) är helt orörd.

---

## Filer

| Fil | Vad |
|-----|-----|
| `Dalecarlia Photo Tools.dc.html` | Hela appen (senaste, med gren-markören inbyggd). |
| `Combobox.dc.html`, `support.js`, `image-slot.js` | Delkomponent + runtime + bild-platshållare. |
| `skarmdumpar/` | Matchraden i appen; de fyra lägena; ribban i inlägg/story. |
