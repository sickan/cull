# Handoff → Claude Design: UI-synk 7 juli — Match-flödet + Innehåll & webb (DPT2)

**Vad det här är:** en statusrapport i samma anda som `UI-SYNK-2026-07.md` — inte en beställning
av ny design, utan en uppdatering så din bild av appen matchar vad som faktiskt är byggt, testat
och kör skarpt just nu. Avgränsat till de två flöden vi ska jobba igenom igen: **Match-flödet**
och **Innehåll & webb**. Ren backend (schema, PIL-rendering, trådsäkerhet, DB-fixar) är utelämnat
— bara det som syns eller beter sig annorlunda i UI:t.

**Läs innan:** `UI-SYNK-2026-07.md` (punkt 1–8) täcker det tidigare passet (Live-förhandsvisning,
Sparade material, Horisont-grafik, lag-loggor, hero-fokuspunkt v1, publicera-till-hemsidan). Inget
nedan om-speccar det. Där något i den bilden inte längre stämmer flaggas det uttryckligen.

**Färskt källkod:** hela `kallkod/`-mappen bredvid är en snapshot av de faktiska Svelte-filerna
(paneler + delade komponenter + `tokens.css`), tagen 7 juli. Använd den som grundsanning om något
nedan är otydligt — inget här är gissat från minnet.

---

## ⚠ Låsta ytor — upprepas så inget backas

1. **Gren-paletten är fast:** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Ingen markering när
   gren saknas. I *grafiken* och Live-förhandsvisningens ram: aldrig textetikett, bara färg.
   (Etiketten "Herr/Dam/Mix" är OK i *listrader* som har etikettplats.)
2. **Publicera → Live-förhandsvisningen är den riktiga server-renderingen** (Horisont-mallen).
   Prototypens CSS-skiss är en prototyp-begränsning, inte en spec.
3. **Matchen är navet — allt refererar, inget kopierar. Alla kopplingar frivilliga.** Chipsen och
   länkningen nedan är genvägar och härledd status; ingenting dubbellagras.

---

# DEL A — MATCH-FLÖDET

## A1. Sportprofiler per sport (KLAR — byggd enligt din `flode_sportprofiler`-handoff)

Sex sporter stöds genomgående: **Fotboll, Handboll, Innebandy, Volleyboll, Beachvolley, Tennis**.
En profil per sport styr fältmodellen i Slutsignal-formuläret, Matchdaguttaget och ResultatRemsan.
Profilen hämtas reaktivt när en match öppnas (`uttagProfil`, backend-anropet `sportprofiler()`) med
fotboll som fallback.

Profilen styr konkret:
- **Uppställning:** `squad` sant → laguppställnings-UI (två lag-kolumner, startuppställning);
  falskt → individuell sport, hela trupp-blocket ersätts av info-raden *"Individuell sport — inga
  trupper eller startuppställningar för {Sport}."* `lineup`/`lineup_n` sätter etiketten
  ("Startelva (11)", "Startsju (7)", "Femma (5)" osv).
- **Resultat:** `res_label` + `res_ph` (etikett/placeholder).
- **Mellanresultat:** `mid_label` + `mid_ph` — "Halvtid" (fotboll/handboll), periodsiffror
  (innebandy), setsiffror (volley/beach/tennis).
- **Målskyttar:** `has_scorers` styr om fältet renderas alls; döljs helt för set-sporter (volley/
  tennis). `scorers_label` för etiketten, placeholder hårdkodad "Efternamn, efternamn…".
- **Matchlängd** per sport driver sluttids-texten i editorn (fotboll 120, volley 150, handboll/
  beach 90, innebandy/tennis 120 min). Ny match utan avsparkstid visar *"Heldag · tid ej
  fastställd"* / *"sätts när avsparkstid är klar"*.

> **Notering för dig:** profilobjektet är samma form överallt (även prop `profil` i ResultatRemsa,
> default `res_label: 'Slutresultat'`, `mid_label: 'Halvtid'`, `has_scorers: true`). Om du designar
> vidare på slutsignal/scoreboard: det är dessa sex fält som avgör vad som syns per sport.

## A2. Matchradens statuschips-nav (KLAR — byggd enligt `flode_sportprofiler` §2)

Överst i den expanderade matchraden ligger en chips-rad — **fem chips, alltid i denna ordning:
Kalender · Gallrat · Live · SoMe · Webb**. Varje chip visar *härledd* status och är en genväg
(inget steg, inget dubbellagras). Klick sätter matchen som aktiv och hoppar till rätt flik.

- **Kalender** — grön om match har kopplat fotojobb (`synk_jobb_id`), annars neutral → *Fotojobb*.
- **Gallrat** — "Gallrat · {antal}" (summerar bilder från gallringskörningar på matchen), grön vid
  träff → *Gallra*.
- **Live** / **SoMe** — grön om något material är publicerat, gul (utkast) om rader finns men inget
  publicerat, annars neutral → *Publicera*.
- **Webb** — mest tillståndsrik: utan innehåll men med resultat → **"Webb saknas · Skapa ›"** (fylld
  accent-chip); med innehåll → **"Webb · publicerad"** (grön) eller **"Webb · utkast"** (gul);
  annars neutral → *Innehåll*.

Toner: grön = `ok`, gul = `--varn` (utkast), accent = fylld knapp (uppmaning). För nya, osparade
matcher (`id` börjar med `ny-`) är chipsen inaktiva.

## A3. ResultatRemsa (NY delad komponent)

En fristående scoreboard-remsa (mörk `#23201a`) som visas i **Publicera (Live + SoMe)** och
**Innehåll → Sport**, alltid direkt under aktiv-match-raden. Har medvetet **ingen egen "Byt
match"-knapp** (aktiv-match-raden ovanför äger matchvalet). Fyra zoner:
- **Vänster:** hemma-Lagbricka (32px) — stort resultatinput (26px, streckad understrykning) —
  borta-Lagbricka. Placeholder ur `profil.res_ph`.
- **Mitt:** "Hemma – Borta" + mellanresultat-input (`profil.mid_ph`) + `· {liga}`.
- **Målskyttar:** bara om `profil.has_scorers`. Pill-chips + "+ mål"-knapp som öppnar fält
  (placeholder "Efternamn 10', efternamn 25'…"). Poster utan namn grupperas till föregående
  spelares chip → "Kanutte Fornes 50', 58', 80'". Utan scorers visas i stället ett brett
  mellanresultat-input.
- **Höger:** autospar-kvittens **"✓ Sparad HH:MM"** (grön). Autospar med 500 ms debounce.

## A4. Matcher — grupperingsval Datum ⇄ Liga/Tävling (NY)

Segmentkontroll överst: **"Gruppera: Datum / Liga/Tävling"**.
- **Datum** — grupperat per år-månad (versal månad+år, t.ex. "Juli 2026"), matcher utan datum sist
  under "Utan datum". **Paginerat** ("Visa 12 till ›", "visar X av Y").
- **Liga/Tävling** — grupperat per tävling med rik gruppheader: färgplatta (Sport-blått `#2F7CB0`)
  med initialer som "logga", tävlingsnamn, meta (sport · period · ort), versal typ-tagg
  ("Liga"/"Turnering"/"Mästerskap"). Ej paginerat.

Ovanpå ligger sport-filterchips, sökfält (lag/liga/arena) och säsongschips (aktivt år + arkivår).
Väljs ett **arkivår** byter vyn till en platt, icke-expanderbar arkivlista oavsett grupperingsval.

## A5. Aktiv match-rad slimmad (AktivMatchRad — omgjord)

Kompakt horisontell remsa överst i de andra stegen (Gallra/Publicera/Leverera). Vänster→höger:
versal-etikett "AKTIV MATCH" · två överlappande runda lag-brickor (22px) · fixtur + undertext
(liga · datum · resultat) · pill-knappar **"Pixieset"** (om galleri), **"På hemsidan"** (om
sida_url), primär **"Byt match"**. Tomt läge: streckad ruta *"Ingen aktiv match — stegen fungerar
ändå, men koppla en match för genvägar och auto-ifyllnad."* + "Välj match i Matcher ›".

## A6. Lagbricka (delad komponent, contain)

Rund bricka. **Med logga:** fast ljus platta `#FBF8F1` (oavsett appens tema — loggorna är ritade
för ljus botten), loggan `object-fit: contain` på 78 % av brickan, aldrig beskuren. **Utan logga:**
färgad botten + initialer (lumjusterad text), korta versala ord behålls helt ("FF"). Storlekar i
bruk: 28px (Lag-listan), 30px (Matchdaguttag), 32px (ResultatRemsa).

---

# DEL B — INNEHÅLL & WEBB

## B1. På gång — femte innehållstypen (HELT NY, oskissad)

Typkort-raden i Innehåll är nu **fem** typer (5-kolumns-grid): **Blog · Sport · Landskap · Event ·
På gång**. Nya "På gång" (`id: pagang`, färg brun `#A0653B`, sub "kommande på webben", kalender-med-
bock-ikon). Väljs den ersätts hela Sport/Event-formuläret av en egen panel (`PaGang.svelte`) — en
kurerad lista av kommande aktiviteter som driver "På gång"-sektionen på sport-sidan. **Live i
produktion sedan 7 juli.**

Tre-korts-layout (kollapsar till en kolumn < 720px):

**Lista** — "+ Ny aktivitet"-knapp; grupp **"Kommande · {antal}"** (rad = datumbox [stor dag +
3-bokstavs månad] · kategori-eyebrow i brunt · titel · meta [tid · plats] · badge **"Publik"**/
**"Dold"**); grupp **"Passerade · visas inte på webben"** (dämpade rader). Fot förklarar: nästa
kommande visas stort på webben, 2–3 därefter kompakt, passerade filtreras bort automatiskt.

**Redigera aktivitet** — mono-filnamn `content/pagang/{datum}-{slug}.md` (live). Kategori-piller
**Match · Uppdrag · Utställning · Övrigt**. Vid **Match**: streckad "Förifyll från Matcher"-ruta med
"Hämta nästa match … (lag, serie, avspark, arena)" + **"Hämta →"** (fyller titel/datum/tid/plats/
etikett). Fält: Titel · Datum · Tid (ph "Avspark 16:00") · Plats · Etikett (hint "Liten rad ovanför
titeln på webben") · Beskrivning (hint "visas bara i stora nästa-kortet"). Fot: **Publicerad-toggle**
(pill-switch) + raderaflöde **"Ta bort aktivitet" → "Ta bort?"** (armering, andra klicket raderar).

**Webbförhandsvisning** — riktig webb-simulering (fejk-browserchrome, url "dalecarliaphoto.se/sport
#pa-gang") med stort "nästa"-kort (datumkolumn i Sport-blått + etikett/titel/meta/beskrivning).
Positions-indikator: "Visas som stort 'nästa'-kort" / "rad {n} i kompakta listan" / "Plats {n} i
kön". Dold-läge visar skäl ("Publicerad är avstängd" / "Datumet har passerat" / "Titel saknas").
Togglebar **"Visa .md-fil som synkas"** (mörk mono-ruta). Fot: **"Publicera till hemsidan"** +
**"Exportera .md-filer…"**. Klartext propagerar raderingar: "✓ {n} publicerade · {m} borttagna".

## B2. Hero-fokuspunkt OMGJORD (BildvaljareFokuspunkt — ersätter v1)

`UI-SYNK-2026-07.md` §7 beskrev v1 (bara klick, ingen ram, inget format). Nu rejält utbyggd:
- **Drag finns** (pointer-capture): "**Klicka eller dra** för att flytta punkten", cursor crosshair.
- **Format-väljare (nytt):** tre piller **"Webb-hero 21:9" · "Kort 16:9" · "Story 9:16"** — ändrar
  bara förhandsvisningen, inte sparat värde.
- **Hela bilden visas obeskuren** i sitt riktiga bildförhållande; ovanpå ritas en **vit
  beskärningsram** för valt format och allt utanför **mörkläggs** (`box-shadow 9999px rgba(...,.55)`).
  Ramen animeras mjukt vid ändring.
- **Markören** är nu en rund vit "korsprick" (20px, vit kant + mörk halo + mittprick).
- **Värdesvisning (nytt):** "Fokus x {x}% · y {y}%" live + "Sparas som heroPosition: '{x% y%}'".
- Knapp "Välj bild" → "Byt bild". Miniatyren återskapas när ett sparat utkast med källfil öppnas;
  saknas lokal källa visas hint om att klicka "Byt bild" för att sätta punkten visuellt igen.

## B3. SoMe-bildbibliotek (NY — ersätter per-kanal mappväljare)

Publicera → SoMe har nu **ett delat bildbibliotek** i stället för separata mappval per kanal.
- **Källflikar:** "Dropbox-export" · "Publicera-urvalet" · "Annan mapp…" (mono-sökväg för aktiv
  källa bredvid).
- **Målväljare "Lägger till i:":** piller **Story · IG-inlägg · FB**, var och en med räknar-badge.
- **Bildgrid** (3:4-tiles, lazy): vald bild accent-outlinad; per-tile badge-taggar **S/IG/FB** för
  kanaler bilden redan ligger i; **"OMSLAG"**-etikett för IG-omslaget. Omslagsrad (40px-tiles) visas
  när mål = IG.
- **"Kanaler & bildset"** nedanför visar enkel vs set per bana: Story ("{n} → {n} stories"),
  IG-inlägg ("enkel"/"karusell · {n}", varning > 10), FB ("max 4", dimmar överskott, **FB-diff**
  med #/@-taggar överstrukna).

## B4. Autospar (genomgående — ingen Spara-knapp för arbetsytan)

Tre autospar-mekanismer, 500 ms debounce, diskret feedback:
- **Innehåll → Sport-formuläret:** sparar löpande per match (ingen egen tidsstämpel-badge; men
  höjdpunkts-hämtning flashar "✓ {n} hämtade" och SoMe-hämtning "✓ Hämtad från SoMe").
- **På gång:** "✓ Sparas löpande · {HH:MM}" i preview-huvudet.
- **Publicera (Live + SoMe):** "✓ Sparad {HH:MM}" intill "Bildbibliotek". Detta är *arbetsytans
  minne* — skilt från explicit **"Spara utkast"** som skapar poster i "Sparade material".

## B5. Testläge (dry-run) — global switch (NY)

En global **testläge-switch i topbaren** (startar AV vid varje appstart, aldrig persisterad). Slår
den på hela publicerings­kedjan i torrläge — inget postas på riktigt, exempelfiler skrivs till disk
och rensas vid omstart. Färgkod genomgående **amber (`--varn`)**:
- Innehåll spara/publicera: "✓ Test — exempelfil: {path} · rensas vid omstart" (hoppar mappväljaren).
- På gång: "✓ Test — {n} .md-filer: {path}/ · rensas vid omstart".
- Publicera Live: hint blir "Testläge — ingen riktig publicering · exempelfil skrivs till disk".
- SoMe done-box + Sparade material: amber **"TEST"-badge** + test-path. Testmaterial hålls
  in-memory och försvinner vid omstart.

> **Design-notering:** testläge är ett rent visuellt lager ovanpå befintliga flöden (amber-omfärgning
> + TEST-badges + path-rader). Om du vill polera: en tydligare global "TESTLÄGE PÅ"-banner i topbaren
> vore en naturlig uppgradering — idag är switchen diskret.

## B6. SoMe bildtext-generering — "godkänn prompten"-flöde (NY mellansteg)

Finns på två ställen med identiskt flöde: Publicera → SoMe (**"✨ Generera"**) och Innehåll → Sport,
Instagram-Bildsvepet (**"Generera"**). Fyra UI-steg:
1. Klick → knappen visar **"Bygger fråga…"** (inget nätverk än). **Kända matchfakta skickas med**
   (sport, färg, resultat, mellanresultat, målskyttar, arena, datum, liga).
2. **Granska-panel** (accent-soft): rubrik **"Granska frågan innan den skickas till Claude"**, hint
   "Tar cirka 2 minuter — websökning används bara för det som inte redan står här (nästa match,
   tabellkontext, @-handles)", hela frågan i scrollbar mono-`<pre>`, knappar **"Avbryt"** +
   **"Skicka till Claude ›"**.
3. **Progress:** spinner + "Genererar… {n}s (websöker matchfakta, tar ofta ~2 min)" med live
   sekundräknare.
4. Resultat fyller bildtext-textarean. Under den: token-brickor ("Infoga bricka" + `{resultat}`,
   `{målskyttar}`, `{@lag}`, `{#liga}`…) och live-förhandsvisning som löser brickorna mot matchen.

## B7. Höjdpunkter — miniatyr & export (Innehåll → Sport)

I Sport-läget heter galleri-kortet **"Bilder · höjdpunkter"**. Knapp **"Hämta från Publicera-
urvalet"** fyller upp till 6 figurer från topp-rankade gallrade filer (flash "✓ {n} hämtade" +
källrad). Varje figrad: klickbar miniatyr-ruta (92×69px) → filväljare hämtar riktig thumbnail;
Alt-text + Bildtext (Sport/Blog) eller härledd bildref `/bilder/{slug}/{n}.jpg` (Landskap/Event).
Ta bort via armerings-mönster (× → "Ta bort?"). Export/publicering går oförändrat via nedersta
"Markdown"-kortets "Spara .md-fil" / "Publicera till hemsidan" / "Kolla status".

---

## ⚠ Flaggor mot baslinjen — värt att veta innan vi designar vidare

1. **Aktiv-match-raden saknar gren-kant.** `AktivMatchRad` har en fast **teal Hav-kant**
   (`var(--hav)`), inte gren-färg — komponenten känner inte till matchens gren. Om gren-signalen ska
   vara konsekvent även här är det ett aktivt designval att ta.
2. **Två olika lag-brick-implementationer.** Den delade `Lagbricka` (contain, ljus platta) används
   överallt UTOM i AktivMatchRad, som har en egen inline-bricka (färgad botten, 3-tecken-initialer,
   22px). De delar inte kod och kan divergera — värt att konsolidera om vi rör lagbrickor.
3. **"Mix" vs "Mixed".** Gren-etiketten i grafik/listrader är **"Mix"**, men select-menyerna i Lag
   säger **"Mixed"**. Liten inkonsekvens i ordval.
4. **Gren "ej satt" = streckad kant.** Matchrad/arkivrad ritar vänsterkanten *solid* när gren är
   satt och *streckad* när den saknas — den streckade varianten är en befintlig signal att bevara.
5. **Individuell sport döljer trupp-blocket** (tennis/beach som individ/par) — ersatt av en info-rad,
   inte en tom yta. Bra att känna till om slutsignal/matchdaguttag ritas om.

---

## Sammanfattning — de öppna designytorna

- **Match som nav** är nu byggt hela vägen: statuschips + sportprofiler + ResultatRemsa. Ytorna som
  vuxit oskissat och är mogna att ta in i designsystemet: **statuschips-raden**, **ResultatRemsan**
  (scoreboard) och **grupperingsväxlaren**.
- **På gång** är en helt ny, oskissad innehållsyta (lista + editor + webb-simulering) som redan kör
  live — bästa kandidaten att formalisera i designsystemet nu när den finns på riktigt.
- **Hero-fokuspunkten** har gått från klick-v1 till en fullständig format/beskärnings-widget — om vi
  polerar vidare (t.ex. per-format sparade fokuspunkter) är underlaget nu på plats.
- **Testläget** och **godkänn-prompten-flödet** är två nya funktionella lager utan egen design — bra
  att ge en medveten visuell identitet (banner respektive granska-panel).
