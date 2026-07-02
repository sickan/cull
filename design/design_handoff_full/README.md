# Dalecarlia Photo Tools — Komplett handoff

Fullständig referens av hela appen (`Dalecarlia Photo Tools.dc.html`) — alla vyer, dataflöden
och datamodell. Underlag för implementation i riktig kodbas (pywebview + Svelte enligt tidigare
handoffs). Skärmdumpar i `skarmdumpar/`. Datamodellen i sin helhet: `DATAMODELL.md`.

- Prototypen är en Design Component; `Combobox.dc.html` är en delkomponent den använder.
- Demodata i `state` är bara exempel — bygg mot `DATAMODELL.md`.
- Designspråk: **Skagen Hav** (ljust + mörkt tema). Tokens nedan är oförändrade genom hela projektet.

---

## Designsystem (tokens)

**Ljust tema:** accent `#C9871F` · accent-soft `rgba(201,135,31,.14)` · ink `#100c05` · fönster
`#F4EEE2` · rail `#ECE3D2` · kort `#FBF8F1` · fält `#FCF9F2` · seg `#E2D7C1`. Text: head `#23201a`,
body `.78`, label `.62`, mut `.5`, help `.4`. OK/grön `#4E8A3E`, varning `#B5791C`.
**Mörkt tema** (`[data-theme=dark]`): accent `#F0B45A`, fönster `#0a0d11`, kort `#12151b`.

**Kategorifärger (Fotojobb):** Sport `#2F7CB0` · Landskap `#C9871F` · Event `#C9657F` ·
Övrigt `#6E8B5E` · Okategoriserat (grå).
**Sportfärger:** Fotboll `#2F7CB0` · Handboll `#C9657F` · Volleyboll `#C9871F` ·
Beachvolley `#1F8A5B` · Tennis `#7A8794`.

**Typografi:** Saira (UI/brödtext) + Saira Condensed (rubriker, siffror, datum).
**Form:** kort radius 10–12px, 3px färgad vänsterkant per kategori, mjuk skugga, pills radius 999px.
Ikoner = tunna stroke-SVG. Ingen emoji.

---

## App-skal

- **Topbar:** logotyp · "PHOTO TOOLS · v2.1.0" · **Aktiv match**-chip · **Aktivt urval**-chip ·
  tema-toggle.
- **Sidomeny (grupperad):** Planera (Fotojobb · Matcher · Lag & tävlingar) · Efter match
  (① Gallra · ② Leverera · ③ Publicera) · Webb (Innehåll) · System (Träna · Logg · Inställningar).
  Aktiv post = accent-soft bakgrund + accent text.
- **Globalt:** aktiv match + aktivt urval ärvs av flera vyer.

---

## Vy för vy

### Fotojobb — `01-fotojobb.png`
Kalender-agenda, tvåvägssynk mot Google Calendar. Sticky topp (rubrik, **live datum/tid**,
Lista/Tidslinje-växel, + Nytt fotojobb), **kategori-filterchips** (Alla/Sport/Landskap/Event/
Övrigt/Okategoriserat), **↑ Till toppen** / **↓ Till idag** (auto vid start), **fallande sortering**
per månad. Kort: datumblock + titel + tid/plats, sync-badge, **inline kategori-select**,
Ändra/Ta bort. **Heldag** = kompakt rad med datumintervall. **Passerade datum dimmas**, dagens
poster markeras (accent-ring + "Idag"). Nytt/Ändra = **modal**. Offline-banner när ej ansluten.

### Matcher — `02-matcher.png`
Planera matcher (refererar registret). Sport-filter. Matcher grupperas under tävling. Expanderad
match: **Hemmalag/Bortalag/Tävling = sökbara comboboxes ur registret**, **datum (datepicker) +
tid (HH:MM) + arena**, och **uträknad sluttid** ur sportens normallängd (Fotboll/Innebandy/Tennis
2 tim, Volleyboll 2,5 tim, Handboll/Beachvolley 1,5 tim) visad vid tiden och i kalenderraden.
**Matchdaguttag:** per lag laddas **startelvan** (delmängd av lagets trupp, "11 av 16") — hela
truppen kommer från Lag & tävlingar. **Lägg i kalender** (start–slut), **Aktivera match**.
Tidigare projekt återupptas.

### Lag & tävlingar — `03-lag-tavlingar.png`, `03b-lag-editor.png`
Registret matcherna delar.
- **Tävlingar:** logga (slot) + namn + typ (Liga/Turnering/Mästerskap) + **sport** + **gren
  (Dam/Herr/Mixed)** + period + ort + arena + hemsida. "Lägg hela tävlingen i kalendern".
- **Lag & utövare** = **kompakt lista**: rad med logga, namn, `sport · gren · typ`, kopplings-
  sammanfattning. **Ändra**-länk fäller ut full editor (`03b-lag-editor.png`): Lag/Individ, namn,
  **gren-segment Dam/Herr/Mixed** (Mixed bara för lag), **sport**, hemsida/@IG, ställfärger (lag) /
  profilfärg + klubb (individ), **trupp** (läs in från URL/CSV/bild/PDF med progress → redigerbar
  Nr·Namn·Pos-lista), och **Kopplad till liga/tävling/mästerskap** (chips, many-to-many,
  borttagbar; lag kan vara okopplat). Landslag som "Sverige" kan finnas per sport tack vare
  sport-fältet (t.ex. Sverige Volleyboll vs Sverige Handboll).

### Gallra — `06-gallra.png`
Steg ①. AI-gallring (Behåll, burst-gräns, tröjnummer-OCR, hemmafärg, avspark), Snabb, Rapport.

### Leverera — `07-leverera.png`
Steg ②. Export (mapp, fotografnamn, IPTC), efterbehandling (Lightroom, husstil, EV), läs
tröjnummer (OCR → keywords).

### Publicera — `08-live.png`, `09-some.png`
Steg ③. Två flikar:
- **Live:** 9:16 story-snabbflöde i tre steg — Favoriter→Lightroom (öppnar LR), Välj bild ur
  Dropbox (↻ manuell uppdatering), Skapa story (overlay-mall med **mall-specifika fält**, tema,
  9:16-förhandsvisning). Publicerar via SoMe-API + sparar filen till Dropbox.
- **SoMe:** publiceringspaket, variant "Målbanor" — kontext-chip, delad bildtext (**✨ Generera**),
  kanalbanor (Story/IG-inlägg/Facebook) med eget bildset + live-plan/varningar (split, FB-kap),
  **FB-textdiff** (#/@ överstrukna). Publicera skarpt / Testkör. Körnings-tillstånd (progress/
  klart/delvis).

### Innehåll — `10-innehall.png`
CMS → `.md` till hemsidan. Fyra färgkodade typer: **Blog · Sport · Landskap · Event**. Se
`DATAMODELL.md` för fälten. Sport förifylls från Matcher; Event/Landskap/Blog manuellt.

### Träna — `11-trana.png`
Finjustera gallringsmodellen. Aktiv modell, Lär av match, samt granskning i modal: Granska osäkra
(behåll/kasta), Jämför par (A/B), Histogram (poängfördelning).

### Logg — `12-logg.png`
Händelselogg för synk/körningar.

### Inställningar — `13-installningar.png`
Google Calendar (konto, kalender, behörighet) + realtidssynk (webhook-kedja).

---

## Aktiv match genom efter-match-flödet

Gallra, Leverera och Publicera visar en **aktiv-match-rad** högst upp (`14-aktiv-match-rad.png`):
lagbrickor + fixtur + tävling/datum/resultat, **Byt match**, och — när de finns — klickbara
genvägar **Pixieset** och **På hemsidan**. Utan aktiv match visas ett tomt läge
("Välj match i Matcher ›") och stegen fungerar ändå.

- **Pixieset-galleri + publicerad hemsideslänk** matas in **på matchen** (Matcher, expanderad —
  "Efter match · länkar"), vanligen morgonen efter. När de finns dyker de upp som genvägar i
  aktiv-match-raden i alla efter-match-steg.
- **Fotojobb ↔ match:** i Fotojobb-modalen visas en **"Koppla till match"-väljare** när
  kategori = Sport (`15-fotojobb-match-koppling.png`), så jobbet kan hittas via matchen senare.

## Dataflöde

```
Lag & tävlingar (lag/utövare + tävlingar, many-to-many-koppling)
      │ refereras (sökbara comboboxes)
      ▼
   Matcher ──(Aktivera)──► AKTIV MATCH (global) ──► Publicera (Live/SoMe), Innehåll (Sport)
      │
 ① Gallra ─► URVAL ─► ② Leverera ─► ③ Publicera
   Träna finjusterar gallringsmodellen

Fotojobb ⇄ Google Calendar (tvåvägs). Inställningar styr anslutning.
```

- Lagfärger (ställ) och tävlingsnamn härleds ur registret överallt — spara **referens/slug**.
- Startelva = delmängd av lagets trupp, laddas på matchdagen, sparas på matchen.
- Matchens sluttid härleds ur sportens normallängd.

## Implementationsnoter

- Overlay-modaler (Fotojobb-modal, Granskning) ska ligga på **toppnivå**, inte i ett panel-kort.
- `isToday`/dimning för heldag jämförs mot hela `[start, end]`.
- Comboboxar matas ur registret; `onPick` sparar **referens**, inte fri sträng.
- Native datepicker (`type=date`) + tidsmask (`type=time`) för datum/tid överallt.
- Live-klocka (`state.now`) driver live-datum + dagens markering.

## Filer

| Fil | Vad |
|-----|-----|
| `Dalecarlia Photo Tools.dc.html` | Hela appen. |
| `Combobox.dc.html` | Sökbar väljare. |
| `DATAMODELL.md` | Komplett datamodell. |
| `support.js`, `image-slot.js` | Runtime + bild-platshållare. |
| `skarmdumpar/` | En bild per vy. |
