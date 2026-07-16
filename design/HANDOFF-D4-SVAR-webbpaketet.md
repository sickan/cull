# Design-handoff D4→Webbplats — helheten uppdaterad

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Facit: `webbplats/Dalecarlia Photo - Webbplats.dc.html` — hela sajtprototypen med D4-besluten
inarbetade. Detta dokument listar deltat mot tidigare version; D4-besluten i detalj finns i
`HANDOFF-D4-SVAR-webbpaketet.md`.*

## Vad som ändrats i sajtprototypen

### 1 · Sport-sidan → D4-strukturen (B-006)
- Hero oförändrad överst (senaste matchen).
- Därunder **tvåkolumn `1fr 420px`**: höjdpunkts-galleriet vänster (masonry, 2 kolumner),
  **match-rail höger**: uppifrån **På gång** (max 3 kompakta datumkort) → **Matcher**
  (EN lista, senaste + tidigare, med länk "Matcharkivet →").
- **"Tidigare matcher"-sektionen (3 stora bildkort) är borttagen** — arkivsidan tar den rollen.
- Gamla stora "På gång"-sektionen (utförligt nästa-kort + lista) är borttagen från Sport —
  railen ersätter den. (Datamodellen `aktiviteter` är oförändrad; bara vyn.)
- **Ligor & Tävlingar** ny full-bredd-sektion under kolumnerna: 3-korts-grid (namn + metarad),
  länk "Hela arkivet →". Textkort i v1 — kurerad bild kan läggas till senare.
- Pixieset-CTA:n ligger kvar mellan tvåkolumnen och Ligor.

### 2 · Matchraden (rail + arkiv, samma komponent)
- Kort `--dp-yta`, 1px `--dp-linje`, **3px vänsterkant i gren-färg**:
  **Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757` — ⚠ LÅST palett; okänd gren = ingen kant.**
- Lag + resultat (resultatet i Hav `#8FD0E8`), metarad dämpad: datum · arena · fotoantal.
- Nytt fält i matchkontraktet: **`gren`** (Dam | Herr | Mixed) — prototypens matcher har
  `gren:'Dam'`. Härled INTE ur serienamnet; explicit fält.

### 3 · Uppdaterad-rad på startsidans motivkort
- Bor **i bildens scrim direkt under korttiteln** — inget eget band, ingen etikett.
- Svag 12px Saira `rgba(255,255,255,.55)`: "Uppdaterad igår" / "Uppdaterad 26 juni".
- **Nytt ≤ 7 dagar = Hav-punkt 5px** framför texten (ingen glow, ingen animation).
  I prototypen: Sport har punkt, övriga tre bara text.
- Genereras statiskt vid publicering; relativ tid vid genereringstillfället, datum efter 48 h.

### 4 · Typografi — ordmärke
- **Montserrat Light 300** ersätter spärrad Saira Condensed i header ("Dalecarlia" 24px +
  "photo" 14px i `--dp-text-dim`) och footer (26/15px). Google Fonts: Montserrat 300/400.
- Endast identitetsytor (ordmärke, sidrubriker på Landskap/Människor/Blogg/Om vid behov) —
  aldrig brödtext/UI. Saira + Saira Condensed oförändrat överallt annars.

### 5 · Tema
- **Mörkt är default** (props-default `Mörk`; Ljus-läget finns kvar i prototypen endast som
  jämförelse — bygg inte ljus-tema i v1).
- Mörka paletten alignad mot D4-tokens: bg `#0A0D11` · yta/kort `#12171F` · yta-2/tile
  `#1A2029` · text `#EDF1F5` · dim 62 % · svag 40 % · linje `rgba(255,255,255,.08)`.

## Oförändrat (rör ej)
Startsidans hero + "Samma blick"-grid + Från journalen; Landskap/Människor/Event/Film/
#projekt26/Kommun/Om/Kontakt/Journal-sidorna; alla datakontrakt utom nya `gren`-fältet;
accentlogik per sektion (Sol/Hav/Rosé-loggor och accenter).

## Öppet
- Arkivsidorna (Matcher-arkiv + Ligor-arkiv) är specade i `HANDOFF-D4-SVAR-webbpaketet.md`
  (säsongsgruppering, filterchips med gren-punkt, "Visa fler" 24 åt gången) — inte mockade
  i sajtprototypen; bygg mot D4-canvasen `Webb D4 – struktur arkiv mörkt.dc.html`.
- Mobilordning (Hero → chip-rad → galleri → matcher → ligor) finns i D4-canvasen, board 1b.
