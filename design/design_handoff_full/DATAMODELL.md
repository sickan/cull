# Datamodell — Dalecarlia Photo Tools (hela appen)

Komplett datamodell. Fältnamn speglar prototypens `state`. Typer i TypeScript-stil; `?` = valfritt.
Enum-värden är exakta strängar appen använder.

---

## Register: Lag & utövare

```ts
interface Team {
  kind: 'team' | 'individ';
  sport: 'Fotboll' | 'Handboll' | 'Volleyboll' | 'Beachvolley' | 'Tennis';
  gren: 'Dam' | 'Herr' | 'Mixed';       // 'Mixed' endast när kind==='team'
  comps: string[];                       // referenser (Competition.id) — many-to-many, kan vara []
  name: string;                          // lagnamn ELLER utövarens namn; landslag "Sverige" särskiljs av sport
  site: string;                          // hemsida
  ig: string;                            // @instagram
  // lag:
  home?: string; away?: string; third?: string;   // ställfärger (hex)
  players?: number;                      // = roster.length när trupp inläst
  squadSource?: 'från hemsida' | 'CSV' | 'bild' | 'PDF';
  roster?: Player[];                     // hela truppen
  squadUrl?: string;                     // källa vid inläsning
  // individ:
  home?: string;                         // profilfärg (återanvänder home)
  club?: string;                         // klubb/land
  logoId?: string;                       // image-slot-id för logga/porträtt (härleds ur namn)
}

interface Player { nr: string; namn: string; pos: string; }  // pos = fri text (MV/FB/MF/ANF…)
```

- **Landslag per sport:** `name:'Sverige', sport:'Volleyboll'` och `name:'Sverige', sport:'Handboll'`
  är två skilda poster.
- **Trupp-inläsning:** från URL/hemsida, CSV, bild (JPG/PNG/HEIF, OCR) eller PDF → normaliseras
  till `Player[]`. Visar progress under hämtning/tolkning, öppnar sedan redigerbar lista.

## Register: Tävlingar

```ts
interface Competition {
  id: string;                            // slug/nyckel, refereras av Team.comps och Match.comp
  typ: 'Liga' | 'Turnering' | 'Mästerskap';
  sport: 'Fotboll' | 'Handboll' | 'Volleyboll' | 'Beachvolley' | 'Tennis';
  gren: 'Dam' | 'Herr' | 'Mixed';
  name: string;
  site: string;                          // hemsida
  period: string;                        // "apr–okt 2026"
  from: string; to: string;              // YYYY-MM-DD (för flerdagars kalenderuppdrag)
  ort: string;
  arena: string;
  logoId?: string;                       // image-slot för tävlingslogga
}
```

## Match

```ts
interface Match {
  home: string; away: string;            // referens till Team.name (+ sport/gren för unikhet)
  comp: string;                          // referens till Competition.id
  league: string;                        // visningsnamn (härlett ur comp)
  sport: string;                         // driver uträknad matchlängd
  date: string;                          // YYYYMMDD (UI konverterar ↔ YYYY-MM-DD för datepicker)
  time: string;                          // "HH:MM" = matchstart (avspark)
  arena: string;
  day: number; mon: string;              // visningsfält
  roster?: boolean;                      // uttaget klart?
  result?: string;                       // "6–0" (avslutad match) — visas i aktiv-match-raden
  pixieset?: string;                     // Pixieset-galleri-URL (matas in på matchen, oftast morgonen efter)
  siteUrl?: string;                      // publicerad hemsideslänk (URL)
}
```

**Uträknad sluttid** (visas, sparas på kalenderhändelsen): `slut = time + normallängd`.
Normallängd per sport (minuter):

| Sport | Längd |
|-------|-------|
| Fotboll | 120 |
| Volleyboll | 150 |
| Handboll | 90 |
| Beachvolley | 90 |
| Innebandy | 120 |
| Tennis | 120 |
| (default) | 120 |

## Matchdaguttag (lineups)

```ts
// per match, indexerat på matchens position/id
interface Lineup { homeStart: number; awayStart: number; }  // antal i startelvan (delmängd av truppen)
```
Startelvan laddas per lag på matchdagen (matchblad/CSV/foto), matchas mot lagets `roster` och
sparas på matchen. Hela truppen bor på laget (`Team.roster`); ingen separat "övrig trupp".

---

## Fotojobb (kalender)

```ts
interface Job {
  id: string;
  title: string;
  category: 'Sport' | 'Landskap' | 'Event' | 'Övrigt' | null;  // null = Okategoriserat
  start: string;                         // ISO (datetime-local) el. YYYY-MM-DD för heldag
  end: string;
  allDay: boolean;                       // heldag → visas som datumintervall
  location?: string;
  note?: string;
  matchRef?: string;                     // koppling till Match (endast när category==='Sport') — så jobbet hittas via matchen
  synced?: boolean;                      // speglad mot Google Calendar
}
```
Passerade jobb dimmas; dagens (idag inom `[start,end]`) markeras. Sortering fallande, grupperad
per månad.

---

## Innehåll (CMS → .md)

Fyra typer, diskriminator `typ`. En post = `.md` under `content/<typ>/`. Gemensamt:
`bilder: {alt,cap}[]` (galleri, renderas `![alt](/bilder/{slug}/{n}.jpg)` + `*cap*`).
Slug: gemener, `å/ä→a`, `ö→o`, icke-alfanumeriskt→`-`.

```ts
interface SportContent {   // typ:'match' — förifylls från Matcher
  typ:'match'; status:'kommande'|'pagaende'|'avslutad';
  hem:string; borta:string; resultat:string; halvtid:string;
  datum:string; serie:string; arena:string; galleri:string; malskyttar:string;
  svep?:string;            // Bildsvepet-text (genereras), body: content/matcher/{datum}-{slug}.md
}
interface EventContent {   // typ:'event' — fotouppdrag, ej match-relaterat
  typ:'event'; kategori:'Porträtt'|'Bröllop'|'Student'|'Företag'|'Mode'|'Övrigt';
  titel:string; kund:string; datum:string; plats:string; galleri:string; ingress:string;
  // content/event/{slug}.md
}
interface LandskapContent {  // typ:'landskap' — bildserie
  typ:'landskap'; titel:string; tema:'Sol'|'Hav'|'Rosé'; plats:string; period:string; ingress:string;
  // content/landskap/{slug}.md
}
interface BlogContent {    // typ:'blogg' — journal/reseberättelse
  typ:'blogg'; kategori:string; titel:string; datum:string; ingress:string;
  body:string;             // markdown (kan genereras med draft.py, redigerbar)
  platser:{plats:string;tips:string}[];   // "Platser & tips"
  // content/blogg/{datum}-{slug}.md
}
```

---

## Live (story-snabbflöde)

```ts
interface Story {
  source: string;          // minneskort-mapp
  dropbox: string;         // Dropbox-exportmapp
  moment: 'Avspark'|'Halvtid'|'Resultat'|'Startelva'|'Målgörare'|'Nästa match';
  theme: 'Hav'|'Sol'|'Rosé';
  fields: Record<string,string>;   // mall-specifika (avspark:time, halvtid, slutresultat, malskyttar, startelva, motstandare, nastaDatum…)
  selectedImage?: string;  // en 9:16-bild i taget
}
```
Publicerar via SoMe-API (IG Story) + sparar renderad fil till Dropbox.

## SoMe (publiceringspaket)

```ts
interface SomePackage {
  caption: string;                 // delad bildtext (kan genereras)
  targets: { story:boolean; igpost:boolean; fb:boolean };
  images: { story:string[]; igpost:string[]; fb:string[] };  // eget bildset per kanal
  matchRef?: string;               // aktiv match (om Sport)
}
```
Härledd plan: Story = N bilder→N stories; IG = 1 enkel / 2–10 karusell / 11+ delas (max 10/karusell);
FB = max 4 (kapas). FB-text strippar `#tag`/`@mention`.

---

## Inställningar

```ts
interface Settings {
  gcalConnected: boolean; gcalAccount?: string; gcalCalendar?: string;  // "primary"
  gcalScope: 'läs' | 'läs & skriv';
  realtimeSync: boolean;           // webhook-kedja Google Calendar → Webhook → DPT
  theme: 'light' | 'dark';
}
```

## Globalt tillstånd

- `activeMatch: string|null` — aktiv match (topbar), ärvs av Publicera/Innehåll **och av Gallra/
  Leverera/Publicera (aktiv-match-rad)**. Pixieset-/hemsideslänkar hämtas från den kopplade matchen.
- `activeSelection` — aktivt urval (topbar), går ② Leverera → ③ Publicera.
- `now` — live-klocka (sekund), driver Fotojobbs live-datum + dagens markering.

## Enum-sammanfattning

| Fält | Värden |
|------|--------|
| Team.kind | team · individ |
| sport | Fotboll · Handboll · Volleyboll · Beachvolley · Tennis *(Innebandy planerad)* |
| gren | Dam · Herr · Mixed *(Mixed ej för individ)* |
| Competition.typ | Liga · Turnering · Mästerskap |
| Job.category | Sport · Landskap · Event · Övrigt · null(Okategoriserat) |
| CMS typ | match · event · landskap · blogg |
| Event.kategori | Porträtt · Bröllop · Student · Företag · Mode · Övrigt |
| Landskap.tema / Story.theme | Sol · Hav · Rosé |
| Story.moment | Avspark · Halvtid · Resultat · Startelva · Målgörare · Nästa match |
