# Handoff Design → Code — Radklick öppnar redigering + gren-kant på Lag & Tävlingar

**Datum:** 4 juli 2026 · **Prototyp:** `Dalecarlia Photo Tools.dc.html`
**Skärmbilder:** `screenshots/` — refereras per avsnitt.

> **Bygger vidare på** `design_handoff_redigering_gren` (utfälld rad-redigering + DAM/HERR/MIXED-etikett).
> Två kompletteringar: (1) hela raden är nu klickyta för redigering, (2) Lag- och Tävlingsrader får
> gren-färgad vänsterkant. Punkt 2 **upphäver** förra handoffens §3 där gren-kant på Lag/Tävlingar
> uttryckligen valdes bort — den är nu vald.

---

## ⚠ Låsta funktioner — får inte regreras (se CLAUDE.md)

1. **Gren-paletten är fast:** Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`. Ingen markering när gren saknas.
   Text-etiketter (DAM/HERR/MIXED) är OK i **listor**; förbudet mot textetikett gäller matchgrafiken
   och Live-förhandsvisningens gren-ram.
2. **Publicera → Live-förhandsvisningen i appen är den riktiga server-renderingen.** Prototypens
   CSS-skiss är en prototyp-begränsning, inte en spec.

---

## 1. Radklick = redigera (Fotojobb, Lag, Tävlingar)

*Skärmbilder: `fotojobb-lista.png` → `fotojobb-radklick-redigering.png`, `lag-lista-grenkant.png` → `lag-radklick-oppen.png`, `tavlingar-lista-grenkant.png` → `tavlingar-radklick-redigering.png`*

- **Hela raden är klickbar** (`cursor: pointer`) och togglar redigeringsläget — samma beteende
  som matchraderna. Gäller alla tre listorna, och alla Fotojobb-radvarianter (Heldag, Lista, Tidslinje).
- **"Ändra" ⇄ "Stäng"**-knappen står kvar som synlig affordance och gör samma sak som radklicket.
  (Tävlingar: "Ändra ›" ⇄ "Stäng".)
- **Klick som INTE ska öppna redigering** (stoppar event-bubbling):
  - papperskorgen / "Ta bort" (radering ska aldrig gå via ett öppnat formulär)
  - logga-slotten på Lag/Tävlingsrader (drag-och-släpp av logga)
  - kategori-selecten på Fotojobb-rader
  - allt inne i det utfällda formuläret
- Max ett öppet redigeringskort per lista; klick på annan rad flyttar kortet dit. Esc stänger.

### UI-state (oförändrat, bara fler klickytor)
```
jobEditId / teamOpen / compOpen — som förra handoffen; radklick anropar samma toggle
```

---

## 2. Gren-kant på Lag- & Tävlingsrader

*Skärmbilder: `lag-lista-grenkant.png`, `tavlingar-lista-grenkant.png`*

- Radkortet får **3px vänsterkant i grenfärgen** ur låsta paletten — identiskt med match- och
  arkivraderna. Ingen gren-kant när gren saknas (behåll ordinarie 1px-kant runt om).
- **Gren-etiketten (DAM/HERR/MIXED) flyttar till vänster om namnet** — samma ordning som
  Fotojobb-raderna: etikett → namn. (Tidigare låg den efter namnet.)
- **Sportfärgspricken på lag-raderna utgår** — gren-kant + etikett + metaraden (sporten står där)
  räcker; två färgsystem i samma rad undviks.
- Tävlingar utan gren-fält defaultar till Dam i prototypen; i appen: visa ingen kant/etikett
  om gren faktiskt är okänd.

Gren läses nu identiskt i hela appen: **Matcher · Matcharkiv · Fotojobb · Lag · Tävlingar**
= 3px vänsterkant + färgkodad textetikett (där rad-layouten har etikettplats).

---

## 3. Skärmbilder

| Fil | Visar |
|---|---|
| `fotojobb-lista.png` | Fotojobb-listan, rader med cursor:pointer |
| `fotojobb-radklick-redigering.png` | Redigeringskortet öppnat via radklick ("Stäng"-läge) |
| `lag-lista-grenkant.png` | Lag-listan: gren-kant + DAM-etikett före namnet, pricken borta |
| `lag-radklick-oppen.png` | Malmö FF öppnad via radklick |
| `tavlingar-lista-grenkant.png` | Tävlingar: gren-kant + etikett före namnet |
| `tavlingar-radklick-redigering.png` | Tävlingsformuläret öppnat via radklick |

## 4. Känt / utanför
- Prototypens tävlings-seed saknar explicit gren på EM Volleyboll → visar Dam-default; i appen
  ska okänd gren ge omarkerad rad.
- Matchraderna hade redan radklick-beteendet — oförändrade detta pass.
