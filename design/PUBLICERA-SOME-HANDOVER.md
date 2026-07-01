# Handover → Claude Design: Publicera till SoMe (DPT2)

**Vad:** designa UI:t för att publicera matchbilder till **Instagram (story + inlägg)** och
**Facebook** direkt ur DPT2:s Publicera-panel. Logiken bakom är redan byggd, testad och
committad (`bea5ae7` på `origin/dpt2-fas0`) — **detta är steg 4 (UI) av 4**. TikTok kommer
senare (separat, kräver audit) och ingår **inte** här.

**Var det landar:** en ny sektion i den befintliga panelen
[`src/dpt2/ui/src/panels/Publicera.svelte`](../src/dpt2/ui/src/panels/Publicera.svelte),
under de två kort som redan finns (Bildsvepet + Matchdag). Designspråket är **"Skagen Hav"**
(ljust + mörkt), samma tokens som resten av appen — se token-listan sist.

> Viktigt: **reglerna nedan är låsta i backend.** UI:t ska *exponera* och *förhandsvisa* dem,
> inte hitta på nya. Designa runt dem.

---

## 1. Mentalt: en "publicering" = ett paket

Fotografen sätter ihop **ETT paket** och skickar ut det till en eller flera kanaler:

```
Paket {
  bilder:  [sökväg, …]   // ordnad lista FÄRDIGA kompositioner (från Matchdag/leverans)
  caption: string        // "Bildsvepet"-texten (med #hashtags och @mentions)
  mal:     { story: bool, ig_inlagg: bool, fb: bool }   // en eller flera
}
```

Samma paket fläkas ut olika per kanal (**fotografens regler, hårdkodade**):

| Mål | Antal bilder | Caption | Blir |
|-----|-------------|---------|------|
| **IG Story** | 1 bild/post → N bilder = **N stories i följd** | full (#/@ kvar)* | en story-post per bild |
| **IG-inlägg** | 1 = enkel, 2–10 = karusell, **11–20 = delas i flera inlägg** | full (#/@ kvar) | 1 eller flera inlägg |
| **FB-sida** | **max 4** (kapas + varnas) | **strippad** på #/@ | ett foto/multi-foto-inlägg |

\* Story skickar tekniskt ingen caption till API:t — texten ligger redan *i* den komponerade
story-bilden. UI:t behöver inte visa caption-fält för story separat, men det stör inte om det gör det.

**Två hårda gränser UI:t MÅSTE kommunicera:**
1. **IG-inlägg kapas vid 10 bilder/post.** Appen tillåter 20, men Graph API (som vi använder)
   gör inte det. 11–20 bilder → automatiskt **2 poster** (10 + resten). UI:t ska varna: *"15 bilder
   → 2 IG-inlägg (max 10/karusell)."*
2. **FB tar max 4 bilder.** Fler kapas → varning: *"6 bilder → kapat till 4 på Facebook."*

---

## 2. Kärn-UX: hela flödet i tre lägen

Föreslagen (men öppen för din design) uppdelning av det nya kortet **"Publicera till SoMe"**:

**A · Ställ in**
- Välj **bilder** (se öppen fråga i §5 om källan).
- **Caption** — förifylld från Bildsvepet-kortet ovan (den texten finns redan i panelen), redigerbar.
- **Mål** — kryssrutor/toggles: `Story` · `IG-inlägg` · `Facebook` (minst ett).

**B · Förhandsgranska plan** (detta är hela poängen — visa exakt vad som händer INNAN)
- En **plan-lista**: varje rad = en faktisk post som kommer ut, t.ex.:
  - `Instagram · Story 1/3` (1 bild)
  - `Instagram · Story 2/3` (1 bild)
  - `Instagram · Story 3/3` (1 bild)
  - `Instagram · Inlägg` (karusell, 10 bilder)
  - `Instagram · Inlägg 2/2` (5 bilder)
  - `Facebook · Inlägg` (4 bilder)
- **Varningar** synliga (split, FB-kap) — gula, inte blockerande.
- **FB-caption-förhandsvisning:** visa den **strippade** FB-texten sida vid sida med originalet, så
  fotografen ser exakt vad som försvinner (`#malmöff`, `@kdff` → borta). Detta är ett uttalat krav.

**C · Kör**
- **"Testkör (dry-run)"** — kör hela flödet utan att posta; visar planen som "skulle postas". Ofarlig.
- **"Publicera skarpt"** — postar på riktigt. Bör ha en lätt bekräftelse ("Postar N poster till 2 kanaler").
- **Progress** under körning: `Post 3/6 …` (backend strömmar exakt detta).
- **Resultat:** per post ✓/✗ + länk till den publicerade posten; ev. felrad (t.ex. "token utgången").

---

## 3. Tillstånd att designa (states)

1. **Ingen aktiv match** — panelen har redan ett tomt-läge ("Välj match ›"); SoMe-kortet kan vara nedtonat.
2. **Inga bilder valda** — "Publicera skarpt" disabled; hint om att välja bilder.
3. **Plan klar (förhandsvisad)** — plan-lista + varningar + FB-caption-diff.
4. **Dry-run-resultat** — samma lista men märkt "test — inget postades".
5. **Postar (progress)** — spinner + `Post n/tot`, knappar disabled.
6. **Klart (skarpt)** — per-post ✓ med länkar; sammanfattning "4 poster · 2 kanaler".
7. **Delfel** — några ✓, någon ✗ med felmeddelande; tydligt att resten gick fram.
8. **Saknar token** — om skarp körning saknar Meta-token: informativt läge ("Koppla Meta-konto för att
   publicera skarpt" — se §4 om att detta är en config-sak, inte ett fel i UI:t). Dry-run ska ändå funka.

---

## 4. Datakontrakt (exakt — så integrationen blir mekanisk)

UI:t pratar med backend via `window.pywebview.api` (samma mönster som `skapaStory`/`genereraBildsvep`).
**Två nya bryggmetoder** kommer läggas till (jag bygger dem vid integrationen — designa mot dessa):

```js
// api.js — förhandsvisa planen (dry-run, rör inga API:er). För läge B/state 3.
await publiceraForhandsvisa({ bilder, caption, mal })
//  → { ok: true,
//      poster: [ { kanal:'instagram', form:'story',  bilder:[…], text, del:1, av:3 },
//                { kanal:'instagram', form:'inlägg', bilder:[…], text, del:1, av:2 },
//                { kanal:'facebook',  form:'inlägg', bilder:[…], text /* strippad */, del:1, av:1 } ],
//      varningar: [ '15 bilder till IG-inlägg → 2 poster (Graph API tar max 10/karusell).' ] }
//  → { ok:false, fel:'Välj minst ett mål (story/ig_inlagg/fb).' }   // validering

// api.js — skarp publicering. För läge C/state 5–7.
await publiceraTillSoMe({ bilder, caption, mal, match_id, moment, tema })
//  → { ok:true, resultat:[ { …post, status:'postad', url:'https://…' } … ],
//      sparade: 4, varningar:[…] }
//  → { ok:false, fel:'Skarp publicering saknar Meta-token …' }      // state 8
```

- **`form`** är antingen `'story'` eller `'inlägg'`; **`kanal`** `'instagram'` eller `'facebook'`.
- **`del`/`av`** numrerar uppdelade poster (för "Story 1/3", "Inlägg 2/2").
- **`text`** i FB-posterna är REDAN strippad av backend — men för diff-vyn (§2B) ska du visa både
  original-captionen (från paketet) och FB-`text` bredvid varandra.
- Skarp körning strömmar `progress`-event (`Post n/tot`) till Logg-panelen; om du vill ha inline-progress
  i kortet kan integrationen exponera dem — designa gärna för det, men det är inte kritiskt.

**FB-strip-regeln** (så du kan mocka diffen exakt): allt som matchar `#ord` eller `@ord` (inkl. å/ä/ö)
tas bort, dubbla mellanslag/tomrader städas. Story och IG behåller texten oförändrad.

---

## 5. Öppna designfrågor (välj/föreslå — dessa är genuint dina att forma)

1. **Varifrån väljs bilderna?** Detta är den största UX-frågan. Kandidater:
   - (a) ur **redan renderade Matchdag-bilder** för matchen (backend har en `some_material`-historik
     per match — renderade stories/inlägg),
   - (b) ur en **levererad mapp** (färdiga JPG:er),
   - (c) **filväljare** (appen har native `valjFil`).
   Troligen en kombination + en liten **miniatyr-strip** där man ordnar/väljer bort. Ordningen spelar roll
   (första bilden = karusellens omslag). Föreslå det du tror är renast.
2. **Ett paket, flera mål — eller ett kort per kanal?** Regeltabellen pekar mot *ett* paket → flera mål
   (mindre dubbelarbete), men om story och inlägg oftast har olika bildset kan separata val vara bättre.
3. **Dry-run som eget steg eller "smygförhandsvisning"?** Planen (§2B) kan visas live medan man bockar mål,
   så "dry-run"-knappen blir överflödig. Din bedömning.
4. **Var bor kortet?** Under Matchdag-kortet i samma panel, eller en egen flik? Panelen börjar bli lång.

---

## 6. Passa in i befintlig panel (så integrationen blir copy-paste-nära)

Panelen använder redan dessa mönster — **återanvänd dem** så det ser ut som en familj:
- **Kort:** `.kort` (vit yta, `var(--div)`-kant, `var(--skugga)`), rubrik `.cardH` (versal, `--t-caps`).
- **Aktiv-match-block** överst: par-brickor i lagens ställfärg + "Byt i Matcher ›". Finns redan — SoMe-kortet
  ärver den kontexten (matchen ger `match_id`/`moment`/`tema`).
- **Chips** (`.chip` / `.chip.on`) för val (moment/tema/format). Passar utmärkt för **mål-val** också.
- **Primär/sekundär knapp:** `.prim` (accent-fylld) / `.sek` (kantad). Kör-raden `.kor` är högerställd.
- **Status/fel:** `.status.ok` (grön), `.fel` (`--varn`). **Utdata/caption:** `textarea` + `.utfot`
  (finns i Bildsvepet-kortet — återanvänd för FB-caption-diffen).

Befintliga kort att matcha visuellt: Bildsvepet (caption + kopiera) och Matchdag (chips för
moment/tema/format + filväljare + "Skapa story ›").

---

## 7. Design-tokens (Skagen Hav — använd variablerna, inga hårdkodade färger)

Ur panelens CSS (ljus + mörk tema definieras globalt):
- **Yta:** `--kort` (kort-bakgrund), `--panel` (fält-bakgrund), `--acc-soft` (mjuk accent-yta).
- **Kant/skugga:** `--div`, `--div3` (hover), `--skugga`, `--r` (radie).
- **Accent:** `--acc` (primär/blå Sport-accent — knappar, aktiva chips).
- **Text:** `--t-head` (rubrik), `--t-mut` (dämpad), `--t-caps` (versal-etikett), `--t-help` (hjälptext).
- **Status:** `--ok` (grön), `--varn` (varning/gul-röd).
- **Typ:** brödtext systemfont; brickor/tal i **Saira Condensed**; caption i mono (`--mono`).

Panelen är `max-width: 820px`, `padding: 22px 26px`.

---

## 8. Efter design → integration i DPT2 (så du vet var det tar vägen)

När mockupen är klar skruvar jag in den i DPT2 (samma väg som design-slice 1–4):
1. Ny sektion i `Publicera.svelte` (Svelte 4) enligt din mockup.
2. `api.js`: `publiceraForhandsvisa` + `publiceraTillSoMe` (med mock-fallback för preview-läge).
3. `app.py`: bryggmetoder `publicera_forhandsvisa` / `publicera_till_some` → anropar redan-byggda
   `tjanster/publicera_korning.py` (jobbet `publicera` finns i workern).
4. `npm run build` i `ui/`, verifiera i preview mot mock, sen commit.

Backend-kontraktet i §4 är stabilt — bygg mot det.

**Gotchas (Svelte i pywebview, från tidigare slicer):** `bind:value` kan inte binda till funktionsanrop
(init en cfg-map, bind till `cfg.x`); `createEventDispatcher`-dispatch EFTER `await` navigerar opålitligt
(dispatcha synkront); en modal måste vara **top-level sibling**, inte inne i ett panel-kort.

---

### Sammanfattning för dig, designer
Bygg kortet **"Publicera till SoMe"**: välj bilder + caption + mål → **förhandsvisa exakt plan**
(med split-varning och FB-caption-diff) → **testkör** eller **publicera skarpt** med per-post-resultat.
Reglerna är låsta (§1), kontraktet är stabilt (§4), tokens är Skagen Hav (§7). Forma §5 fritt.
