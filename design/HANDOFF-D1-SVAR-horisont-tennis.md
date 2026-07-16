# Design-svar D1 — Horisont-mall för TENNIS

*2026-07-15 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `HANDOFF-D1-horisont-tennis.md`. Facit: `Horisont Tennis D1.dc.html` (öppna i
webbläsare, växla tillstånd via Tweaks). Hav × 9:16. Övriga teman = färgbyte, 4:5 = beskärning.*

## Tillstånd som finns (3 st)

`Matchstart` · `Nästa match` (PREVIEW-blocket) — `Slutresultat` (SCORE-blocket).
**Mellan set utgår i D1** (behövs inte nu; SCORE-blocket tål det om det tillkommer — utan
vinnarmarkering). **Startelva utgår** för individ-sporter (bekräftat). **Målgörare utgår helt** för tennis —
inget ögonblicks-tillstånd i D1 (se beslut 3).

Allt utanför innehållsblocket är oförändrat mot kanonisk Horisont: full-bleed foto, scrims,
temalogga (80 % opacitet), turneringsnamn som spärrad text uppe höger (i stället för liga-logga),
vertikal URL, 18 px gren-kant (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757` — LÅST).

## Beslut på fråga 1–5

**1. PREVIEW:** **Ronden är det stora ordet** ("SEMIFINAL", 700 150px Saira Condensed) och
momentet blir accent-etiketten ovanför ("MATCHSTART" / "NÄSTA MATCH"). Saknas rond: momentet
blir stort ord och etiketten blir turneringsnamnet. Spelare visas **utan loggor och utan
monogram-badge** — namn i stor stil (600 52px Saira Condensed, vitt) med **land som spärrad
underrad** (600 21px Saira, `.24em`, `rgba(255,255,255,.58)`), centrerad rad med accentfärgat
"–" emellan, baseline-linjerad. Monogram-fallbacken behövs inte här.

**2. SCORE:** **Set-siffran är primär** (`2 – 1`, 700 220px, tunna mellanslag U+2009 — samma
som fotbollens resultat) med **gamesiffrorna som underrad under avdelaren**
(`6–4, 3–6, 7–5`, 600 38px Saira Condensed, `.08em`, `rgba(255,255,255,.85)`).
Namnraden ligger direkt under set-siffran (600 48px Saira Condensed).
**Vinnare markeras med accentfärgat namn** (temats accent, Hav `#8FD0E8`); förloraren dämpas
till `rgba(255,255,255,.6)`. Vinnaren härleds ur set-siffrorna (fler set = vinnare). Vänster spelare = första siffran, alltid.

**3. MÅLGÖRARE-motsvarighet: utgår helt.** Explicit: inget "SETVINST"-tillstånd i D1.
Kan läggas till senare som generiskt "Ögonblick"-tillstånd om behov uppstår — designa då, inte nu.

**4. STARTELVA: utgår** för individ-sporter. Bekräftat.

**5. Rond vs turnering:** **Ronden är visuellt primär** (stort ord i PREVIEW, del av
etiketten i SCORE: "SLUTRESULTAT · SEMIFINAL"). **Turneringen sitter alltid uppe till höger**
som den spärrade texten (samma plats/stil som liga-namnet i fotboll: 600 27px Saira, `.24em`,
`rgba(255,255,255,.66)`) och dubbleras inte i innehållsblocket — utom i PREVIEW-fallbacken
när rond saknas.

**Nytt fält Code lägger till:** `rond` (text, valfritt) på matchen — t.ex. "Åttondel",
"Kvartsfinal", "Semifinal", "Final". Visas versalt. Tomt fält = fallbacks ovan, inget hål.

## Fältlista per tillstånd

Gemensamt (alla tillstånd): `bgSrc` (foto), `turnering` (uppe höger; tomt = raden utgår),
`gren` (kantfärg; okänd = ingen kant — LÅST beteende).

**Matchstart / Nästa match**
- `rond` → stort ord. Saknas → momentordet stort, turnering som etikett.
- `kickoff` (Matchstart) / `nextWhen` (Nästa match) + `venue` → underrad "13:00 · BÅSTAD".
  Saknas venue → bara tiden. Saknas tid → bara venue.
- `playerA/playerB` → namnrad. `landA/landB` → underrad per spelare; saknas → raden utgår
  (namnet centreras ensamt, layouten tål det).

**Slutresultat**
- `rond` → etikett "SLUTRESULTAT · SEMIFINAL"; saknas → bara momentordet.
- `setA/setB` → stor siffra ("Resultat i set").
- `playerA/playerB` → namnrad; vinnarmarkering enligt beslut 2.
- `games` → underrad ("Gamesiffror", t.ex. "6–4, 3–6, 7–5"); saknas → avdelare + rad utgår.
- Etikett-texten ("Slutresultat") hämtas ur sportprofilen som idag.

## PIL-noter (delta mot fotbolls-README:n)

- Inga klubbmärkes-cirklar i något tennis-tillstånd → hela mask/skugg-hjälparen för brickor
  används inte här.
- Nya textstilar: spelarnamn 52/48px Saira Condensed 600; land 21px Saira 600 tracking ≈ 5px
  (`.24em`); gamesiffror 38px Saira Condensed 600 tracking ≈ 3px (`.08em`).
- Vinnarfärg = temats `accent` (samma konstant som etiketterna).
- Allt annat (canvas, scrims, marginaler 60px, avdelare, spärrad text) exakt som README +
  gren-kant-handoffen.

## Blick mot D2 (friidrott)

Mallspråket tål en person + ett resultat: PREVIEW = stort ord (moment/gren, t.ex. "LÄNGD — KVAL")
+ en namnkolumn i stället för två; SCORE = stor siffra (längd/tid/höjd) + namnrad under.
Inga block bygger på "två sidor" — dash-raden är det enda tvåparts-elementet och kan utgå.
