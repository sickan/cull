# Design-svar D2 — Horisont-mallar för FRIIDROTT

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D2-horisont-friidrott.md`. Facit: `Horisont Friidrott D2.dc.html`
(Tweaks: tillstånd/grentyp/fält). Hav × 9:16. Bygger på D1 — allt låst från D1 orört.*

## Tillstånd (3 st)

`Start` (preview) · `Resultat` · `Placering`. Eventnamnet ("Friidrotts-SM 2026") sitter
alltid uppe till höger som spärrad text (samma stil/plats som turneringen i tennis).

## Beslut på fråga 1–5

**1. Gren + moment:** kombineras ALDRIG till ett ord — **grenen är det stora ordet ensam**
("LÄNGD", "TRESTEG", "100 M") och **momentet bor i accent-etiketten** ("START · KVAL",
"RESULTAT · LÄNGD — FINAL"). Långa kombos uppstår därmed inte. Långa grennamn auto-krymps
i ETT steg per tröskel, alltid en rad: ≤9 tecken 150px · 10–13 tecken 118px ·
>13 tecken 96px (700 Saira Condensed). "STAVHOPP — KVALGRUPP A" blir alltså stort ord
"STAVHOPP" + etikett "START · KVALGRUPP A".

**2. Grentyp → resultatformat (konfig till sportprofilen):**

| Grentyp | Format | Exempel | Regler |
|---|---|---|---|
| Sprint (≤400 m, häck) | sekunder, 2 dec | `10,12` | decimalkomma, ingen enhet |
| Medel/lång (≥800 m) | min.sek,hundradelar | `1.45,32` | punkt min/sek, komma före hundradelar |
| Hopp/kast | meter, 2 dec | `6,42 m` | enhet **m** i dämpad mindre stil (600 80px Saira Condensed, `rgba(255,255,255,.55)`), baseline-linjerad efter siffran |
| Mångkamp | poäng | `8 421 p` | tusentalsmellanslag, enhet **p** dämpad som ovan |
| Placering | ordinal | `1:a`, `4:e` | suffix `:a` (1–2) / `:e` (3+), 600 90px, 75 % opacitet |

Stora siffran: 700 220px Saira Condensed — samma som tennis-setsiffran.
**Medaljfärg vid 1–3** (siffra + ordinal, INTE emoji, ingen "GULD"-text):
Guld `#D9B24C` · Silver `#C7CDD4` · Brons `#C08A5A`. Plats 4+ vit.

**3. Serie:** visas **under avdelaren** (som gamesiffrorna i tennis: 600 38px Saira
Condensed, `.08em`) — bara för hopp/kast, bara när serien finns. Formatet är en textsträng
från renderaren: `6,21 · 6,42 · × · 6,38`. **Övertramp = tecknet ×** i stället för siffra
(inget eget färgläge — strängen är enhetligt dämpad vit `.85`). Bästa resultatet markeras
INTE i serien — den stora siffran ÄR bästa. Löpning: ingen serie, avdelare + rad utgår.

**4. START/preview:** stödjer **1–3 idrottare** i samma bild. Varje idrottare = namn
(600 52px Saira Condensed, vitt) + **klubb som spärrad underrad** (samma stil som land i
tennis), centrerad kolumn, 26px mellanrum mellan idrottare. En idrottare ser ut exakt som
tennis-previewens ena sida. Fler än 3: ta de 3 främsta — mallen är en story, inte en startlista.
Underraden under stora ordet: "LÖR 25 JUL · 14:30 · UPPSALA" (starttid + venue, samma
fallbacks som D1).

**5. DNF/DNS/DQ:** visas i Placering-tillståndet som **stort ord i dämpad vit**
(`rgba(255,255,255,.6)`, 220px) i stället för siffra — ingen ordinal, ingen medaljfärg,
ingen resultat-underrad. Rekommendation till redaktören (inte kod): publicera bara när det
har nyhetsvärde. Storyn utgår alltså INTE automatiskt — beslutet är mänskligt.

## Fältlista per tillstånd

Gemensamt: `bgSrc`, `event` (uppe höger; tomt = raden utgår), `gren` → kantfärg
(Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`; okänd = ingen kant — LÅST),
`grenNamn`, `moment` (tomt = utgår ur etiketten), `grentyp` (styr format enligt tabellen).

**Start**
- Etikett "START · {moment}". Stort ord = `grenNamn`.
- `startWhen` + `venue` → underrad; samma utelämnings-fallbacks som D1.
- 1–3 × (`namn`, `klubb`); klubb tom → underraden utgår för den idrottaren.

**Resultat**
- Etikett "RESULTAT · {gren} — {moment}".
- `resultat` → stor siffra enligt formatTabellen; hopp/kast får dämpad enhet.
- `namnA`/`klubbA` under siffran.
- `serie` (endast hopp/kast) → avdelare + rad; tom → utgår.

**Placering**
- Etikett "PLACERING · {gren} — {moment}".
- `placering` numerisk → siffra + ordinal, medaljfärg 1–3; `DNS`/`DNF`/`DQ` → dämpat stort ord.
- `namnA`/`klubbA` under.
- `resultat` → underrad under avdelare ("6,42 m"); tom eller DNS/DNF/DQ → utgår.

## PIL-noter (delta mot D1)

- Enhets-suffix: 600 80px Saira Condensed `rgba(255,255,255,.55)`, gap 16px, baseline.
- Ordinal-suffix: 600 90px, medaljfärg × 75 % opacitet, gap 6px, baseline.
- Idrottar-lista i preview: kolumn, gap 26px.
- Allt övrigt (canvas, scrims, 60px-marginaler, avdelare 3px `.22`, spärrade stilar) = D1.
