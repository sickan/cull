# Dalecarlia Photo Tools v5 — datamodell (eventmodell-epiken)

Bygger vidare på DPT:s befintliga datamodell. Ändringen i denna epik:
**Tävling delas i två register — Liga och Event** (skiss 1a), plus två nya
byggklossar: **Gren** och **Individ**. Allt annat (Lag, Match, Urval,
SoMe-material, Innehåll) ligger kvar som idag med små tillägg.

```
Sport ──< Liga ────────────┐
Sport ──< Event ──< Gren   │        Individ (register, som Lag)
            │        └──⟂──┼──────────┘   (individ ⟂ gren, n:n)
            │              │
Lag >──── Match ──(liga?)──┘   Match ──(event?)── Event
            │
          Urval ──< SoMe-material
```

---

## Liga (`content/liga/*.md`) — NY, ersätter Tävling typ: liga
Långlivad struktur över säsonger. Ska på sikt bära historik
(tabeller, tidigare möten, hur säsong 2026 slutade).

```yaml
id: damallsvenskan
sport: fotboll
namn: OBOS Damallsvenskan
logga: /bilder/liga/damallsvenskan.png
sasonger:                 # historik-krok, fylls på sikt
  - { ar: 2026, status: pagaende }
```

## Event (`content/event/*.md`) — NY, ersätter Tävling typ: turnering|masterskap
Tidsbegränsat: mästerskap, cup, turnering, världscup, heldagsuppdrag.
Lever året runt — inte bara mästerskap.

```yaml
id: em-volley-2026
typ: masterskap           # masterskap | cup | turnering | varldscup | ovrigt  (etikett, ej beteende)
sport: volleyboll
namn: EuroVolley 2026
period: { fran: 2026-08-21, till: 2026-08-27 }
ort: Göteborg
arena: Scandinavium
logga: /bilder/event/em-volley.png
liga: null                # valfri ref — t.ex. SM-slutspel i en liga
kalender: true            # Google Calendar (flerdagarsuppdrag)
pagang_lage: auto         # auto | heldag | matcher   (skiss 1h)
grenar:
  - { id: herr, namn: Herr }
  - { id: dam,  namn: Dam }
```

Event kräver varken matcher eller grenar — en cup-kväll med en enda
match använder samma struktur.

## Gren — byggkloss under Event (inbäddad i eventet)
Generell för alla sporter: 100 m häck, 10 km klassisk, sprint, herr/dam.
Individer kopplas per gren (n:n) — se Individ.

## Individ (`content/individ/*.md`) — NY, register som Lag
Långlivad mellan event (Duplantis finns kvar).

```yaml
id: a-duplantis
namn: Armand Duplantis
sport: friidrott
instagram: "@mondo_duplantis"
bild: /bilder/individ/a-duplantis.jpg
```

Kopplingen individ ⟂ gren lagras på eventet (en källa, ingen dubblering):

```yaml
# i event-frontmatter
deltagare:
  - { individ: e-andersson, grenar: [10km-k, 50km-f] }
  - { individ: j-nilsson,   grenar: [sprint] }
```

**Individens historik är härledd:** individvyn (DPT2 och hemsidan) frågar
alla event efter `deltagare.individ == id` och visar tidslinjen —
"Skid-VC Falun 2026: 10 km K, 50 km F · Friidrotts-SM 2025: …".
Inget skrivs på individen; historiken kan aldrig komma i osynk.

## Match — ändringar
`tavling:` ersätts av två **valfria** fält:

```yaml
liga: damallsvenskan      # valfri — träningsmatch kan sakna liga
event: null               # valfri — em-volley-2026 när matchen ingår i ett event
```

En match kan ha liga, event, båda eller ingen. Migration: befintliga
`tavling:`-värden mappas till `liga:` (typ liga) eller `event:` (övriga).

---

## På gång-logik (skiss 1h)
Automatik per event, styrd av `pagang_lage` + kalendern:

- **auto** (default): på avstånd → heldagskort för eventet;
  under perioden → dagens/nästa kopplade matcher som egna kort;
  efter → resultat.
- **heldag** / **matcher**: manuell override av auto-beteendet.
- En match med `event:` visas **aldrig lösryckt** — kortet bär alltid
  "Del av {event.namn}".

## iOS v2 — nya fält
- **Dynamisk bakgrund (1j):** bilder flaggas i DPT2 med `ios_bakgrund: true`
  (+ sport-tagg ur matchen/eventet). Appen väljer: ★-pott för aktuell sport
  → egen uppladdad → standard.
- **Restid (1k):** efter eventstart räknas restid mot **nästa deltillfälle**
  (kopplad match/gren med klockslag). Manuell override: annat deltillfälle
  eller eget klockslag.

## Kategori — statisk toppnivå, dynamiska underkategorier
Toppnivån är **fast** (styr hemsidans toppmeny och tema-koppling):
`sport · landskap · manniskor · film`. I **Innehåll** finns dessutom `blogg`
som femte innehållstyp (typ-naven blir Sport · Landskap · Människor · Blogg · Film).

Underkategorier är ett **redigerbart register** (`content/kategori/*.md`
eller data-collection) — läggs till/döps om utan kodändring:

```yaml
id: brollop
topp: manniskor            # låst lista: sport | landskap | manniskor | film
namn: Bröllop
# dagens set under Människor: Porträtt · Bröllop · Student · Företag · Mode · Övrigt
gallringsprofil: brollop   # valfri — styr Gallra-signaler (4d)
some_moment: [tjuvkik, leverans-klar]   # valfri — momentmall (4c)
```

**SoMe per kategori (beslutat):**
- Människor (Bröllop/Student/Företag/Mode): momentmall Tjuvkik · Leverans klar,
  men **per jobb-flagga** `some: true|false` avgör om flödet alls erbjuds.
  Samtycket bor i avtalet — verktyget lagrar det inte.
- Landskap: momentmall Ny serie · Platsen · Bakom kulisserna · Blogg-puff.
  Länk till hemsidan är valfri per inlägg.
- Kanaler: samma som sport (Instagram + Facebook).

Fotojobb/uppdrag pekar på en underkategori; toppnivån härleds därifrån.
Innehåll under Människor bär sin underkategori (Porträtt · Bröllop · Student ·
Företag · Mode · Övrigt) som filter/etikett — hemsidans toppmeny påverkas inte.
Kategorifärgerna (iOS-kalendern m.m.) ligger på toppnivån:
Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`.

---

## DPT2 — fristående backlogpunkter (kan gå till Code direkt)
- **Målmappar per flöde:** default i Inställningar, override i flödet.
  `mapp_snabbplock` (fungerar som backup), `mapp_gallring`, `mapp_media`
  (Dropbox för delning).
- **Original utan overlay:** vid generering med overlay sparas originalet
  alltid bredvid exporten (`namn.jpg` + `namn-original.jpg`).

---

## Astro content collections (uppdaterat förslag)
```
src/content/
  liga/        # NY — ersätter tavling/ (typ liga)
  event/       # event + grenar + deltagare (ersätter tavling/ övriga)
  individ/     # NY — register
  lag/         # oförändrat
  matcher/     # + liga?/event?-fält
  landskap/ portratt/ blogg/   # oförändrat
```
