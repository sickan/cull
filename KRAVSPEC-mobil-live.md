# Kravspec — Mobil Live (DPT2)

**Status:** Design-runda KLAR (2026-07-09). Byggklar för Etapp 1.
**Datum:** 2026-07-09 (uppdaterad med Designs svar samma dag).
**Use-case (Stigs formulering):** "Jag kanske inte har möjlighet att jobba på datorn med
DPT2 desktop när jag är ute på en match live. Live ska kunna initieras eller hanteras i
mobilen — i sömlös synk med appen så man kan välja, växla, fortsätta."
**Låsta vägval:** (1) *Moln-relä via det befintliga worker-mönstret* — inte LAN-server
(Macen är hemma när use-caset gäller), inte native app (ingen app store), inte SQLite-
filsynk (konfliktfälla). (2) *Etappindelning* — Etapp 1 = matchtillståndet i molnet +
mobil-PWA för att *föra* matchen; Etapp 2 = *publicera* stories utan Macen; Etapp 3 =
närvaro/växling-polish. **Design ritade hela målbilden, Etapp 1 är byggmålet.**

**Designbeslut inbakade (handoff `Mobil Live.dc.html`, 7 skärmar 1a–1h):**
- **Tema låst till Skagen Hav (Sport)** — Mobil Live är bara Sport, ingen temaväljare (ändrar B2).
- **Minut på mål är VALFRI + editerbar i efterhand** — `malskyttar` lagras som strukturerade
  poster (namn + valfri minut), inte en färdig sträng (ändrar A1/B2).
- **Halvtid-trycket fångar `mellan` med synlig, ångerbar bekräftelse** ("Halvtid 1–0 sparad · Ångra").
- **Matchvy = variant 1b (Kompakt), målskytt = egen helskärm (1e).**
- **Set-baserade sporter (volleyboll, 1h) = uppföljning, inte Etapp 1** (egen scoring-modell).

> **OBS för granskning:** Del A/B är specade mot faktisk kod (`src/dpt2/app.py`,
> `data/store.py` + `schema.sql`, `panels/Publicera.svelte`, `tjanster/innehall_synk.py`,
> `motorer/story_overlay.py`) och den deployade content-sync-workern
> (`~/dalecarlia-photo/content-sync`). `[BEKRÄFTA]` markerar produktval som är Stigs.

---

## Nuläge (diagnos)

Live bor i **Matchpublicering** (`Publicera.svelte`): matchväljare → `ResultatRemsa`
(resultat/mellanresultat/målskyttar, sparas fältvis via `store.satt_resultat`) → slide-over
**"Live nu"** med moment ur **sportprofilen** (`start_moment` t.ex. Avspark · `mid_label`
t.ex. Halvtid · Målgörare om `has_scorers` · Slutresultat), eget bildrutnät
(`liveFolderPath`), tema Hav/Sol/Rosé, Horisont-render server-side
(`motorer/story_overlay.skapa_story`, 9x16) → `app.publicera_live_story` → Meta.

**Allt kräver Macen:** SQLite:n är lokal (`~/.config/dpt2/dpt.db`), rendern är Pillow,
fotona ligger på disk/Dropbox, Meta-publiceringen går genom `app.py`.

**Två saker finns redan som gör det här litet:**

- **"Fortsätt där du var" finns redan lokalt** — `arbetsyta_utkast` autosparar per match
  (`live_moment`, `live_tema`, `live_cfg`, `cms`, …, `uppdaterad`). Det som saknas är
  samma sak *över enheter*.
- **Moln-mönstret finns redan i drift** — content-sync-workern (D1, Bearer-auth,
  `InnehallSynk`-klienten med `CONTENT_SYNC_BASE_URL`/`CONTENT_SYNC_API_KEY`), R2-bildlagring,
  deploy-flödet. Mobil Live = samma mönster en gång till, med ett live-dokument i stället
  för .md-innehåll.

**Nyckelinsikt:** Live är två lager. *Matchtillståndet* (resultat, målskyttar, moment —
små textfält) är trivialt att molnsynka. *Rendering+publicering* (Pillow, foton, Meta)
är tungt och stannar på Macen i Etapp 1.

---

## Del A — Live-tillstånd i molnet (synk-fundamentet, inget UI)

### A1. Datamodell: live-dokument per match

```
live_state {
  match_id, resultat, mellan,                    -- resultat/mellanresultat (satt_resultat)
  malskyttar: [ { namn, minut|null, lag } ],     -- STRUKTURERAT (minut valfri + editerbar)
  moment,                                         -- speglar arbetsyta_utkast.live_moment
  tema,                                           -- alltid "Hav" från mobilen (låst); fältet kvar för desktop
  fors_fran,                                      -- "mobil" | "desktop" + tidsstämpel (Del D)
  falt_uppdaterad { <fält>: ISO-tid }            -- fältvis LWW
}
```

**`malskyttar` är en lista av poster, inte en sträng** (Designkrav): ett mål kan sparas
utan minut och minuten fyllas i/ändras senare (tryck på minut-chippen). En post kan
patchas individuellt. Desktop serialiserar listan till appens `"Namn MM', Namn MM'"`-
konvention vid inläsning (`ResultatRemsa._chipify` renderar redan namn utan minut) — poster
utan minut visar bara namnet tills minuten fylls i. `falt_uppdaterad` spårar `malskyttar`
som helhet för LWW; individuell minut-edit bumpar samma tidsstämpel.

Plus ett **match-paket** som desktop pushar upp (mobilen har ingen egen matchdatabas):
lag hemma/borta (namn + brickfärger/logga-URL), avspark, arena, sport + sportprofilens
etiketter (`res_label`/`mid_label`/`has_scorers`/`start_moment`), samt **spelarlistan**
(nr/namn ur `match_trupp`) — den driver målskytte-inmatningen i B2.

### A2. Worker-rutter

- `GET /api/live` — kommande matcher med ev. live-state (mobilens matchval).
- `GET/PUT /api/live/:matchId` — läs/skriv live-dokumentet. PUT är **partiell** (bara
  angivna fält rörs — samma filosofi som `store.spara_utkast`), merge fältvis på
  `falt_uppdaterad` (last-write-wins per fält).
- `PUT /api/live/:matchId/paket` — desktop pushar match-paketet (A1).
- **VIKTIGT:** live-rutterna får **ALDRIG** trigga content-syncs deploy-hook — annars
  bygger Cloudflare Pages om sajten vid varje målskytte.
- **BESLUT (Stig 2026-07-09): utöka content-sync** med `/api/live/*` (auth, D1, R2, deploy
  finns redan; hooken anropas idag per rutt, så det är bara att inte anropa den från
  live-rutterna). Ingen fjärde worker att deploya/underhålla.

### A3. Desktop-synken (ändringar i DPT2)

- Ny tunn klient `tjanster/live_synk.py` — samma injicerings-/env-mönster som
  `InnehallSynk` (nyckeln bara i Python-backend, aldrig i Svelte-bundlen).
- **Push:** `ResultatRemsa`s debounce:ade `sattResultat` + Live nu:s moment/tema-ändringar
  pushar även till workern (best-effort, blockerar aldrig UI offline — samma hållning som
  `InnehallSynk.radera`).
- **Pull:** Publicera-panelen pollar `GET /api/live/:matchId` var ~10 s när panelen är
  öppen (+ vid mount/matchbyte), merge:ar fältvis in i remsan + `arbetsyta_utkast`.
  Fältvis LWW räcker — en användare, konflikter är i praktiken "mobilen skrev nyss".
- **Match-paketet — BESLUT (Stig 2026-07-09): alla kommande matcher pushas automatiskt**,
  piggyback på **På gång-synkens befintliga trigger** (återanvänder listan `pagang_matcher`
  redan räknar ut). Premissen är "jag är kanske inte vid datorn" → ingen förberedelse-ritual;
  varje kommande match finns redo på telefonen. **Roster följer med när den finns** (`match_trupp`
  ofta tom tills "Hämta match" körts → målskytt faller tillbaka på fritext, ofarligt). Ev. även
  en manuell "Synka till mobilen"-knapp som säkerhet.

### A4. Hemresan ("fortsätta")

Ingen ny mekanik behövs: när Publicera-panelen öppnas hemma drar pollen ner mobilens
fält → remsan och utkastet är redan ifyllda → render/publicering/gallring som vanligt.
Det är hela sömlösheten i Etapp 1.

---

## Del B — Mobil-PWA "DPT2 Live" (det Design ska rita)

### B1. Ramar

- **En sida, servad av workern**, installerbar PWA (hemskärmsikon, fullskärm). Ingen app store.
- **Mörk-först** (appen är numera mörk-default), **portrait**, **tumvänlig** — byggd för
  läktare: sol, handskar, en hand. Stora tryckytor, inget pyssel.
- **Offline-kö**: arenanät är opålitligt. Service worker köar skrivningar och flushar när
  nätet återvänder. Kön ska *synas* (B2).
- Designspråk: DPT2:s mörka tema-tokens + etablerade mönster — `Lagbricka`,
  `ResultatRemsa`-scoreboarden, gren-kantkonventionen. Baslinje: `design/UI-SYNK-2026-07.md`.

### B2. Vyer

**Vy 1 · Matchval** — kommande matcher ur `GET /api/live` (lagbrickor, datum/avspark,
arena). En match med pågående live-state visar tydlig **"● Live — fortsätt"**-badge.
Tänk: På gång-listans kort, fast tryckbara.

**Vy 2 · Matchvyn — variant 1b Kompakt (VALD; 1c Tumzon / 1d Fokuserad förkastade)**
(kärnan — där hela matchen förs, allt på en skärm):

- **Scoreboard överst** — mobil-ResultatRemsa: brickor + stort resultat. **+1 per lag som
  primärknapp** (stegare), inte ett textfält. "Rätta resultat" för feltryck.
- **Halvtid-bekräftelse** — grön ångerbar rad "Halvtid 1–0 sparad · Ångra" (aldrig tyst).
- **Moment-rad** — chips ur sportprofilen: `start_moment` (Avspark) · `mid_label`
  (Halvtid) · Målgörare (om `has_scorers`) · Slutresultat. **Halvtid-trycket fångar
  aktuellt resultat till `mellan`** med bekräftelsen ovan (Designbeslut, ersätter tidigare
  `[BEKRÄFTA]`).
- **Målskyttelista + inmatning** — se **1e (egen helskärm)** nedan. Listan visar "Namn MM′";
  minut som **tryckbar chip**, mål utan minut visar "+ minut" (fyll i senare).
- **Synk-status, alltid synlig** (toppbaren) — se Del B4. Förtroendeytan: användaren måste
  *se* att läktartrycken faktiskt når hem.
- **Inget tema-val** — Skagen Hav är låst (Mobil Live = bara Sport).

**Vy 2b · Målskytt — egen helskärm (1e)**, öppnas vid +1 / "Lägg till målgörare":

- **Preview** överst: "Läggs till: Hansson 41′".
- **Minut · valfri** — stepper −/+ och fritext, med **"Lämna tom"**. Ingen matchklocka —
  minuten skrivs själv och kan lämnas tom nu, fyllas i senare. Målet sparas ändå.
- **Roster** ur match-paketet (nr + namn, sorterad på tröjnummer), tryck för att välja.
  **Fritext-fallback** ("Annan / skriv namn…") när rostern saknar spelaren.
- Primär "Spara mål → 2–0". Post läggs i `malskyttar`-listan (A1).

**Vy 3 · Publicera** (Etapp 2, ritas nu om Design vill) — story-preview av Horisont-
grafiken för valt moment + "Publicera story". Grånad/dold i Etapp 1.

**Vy 4 · Set-baserade sporter (1h, `has_scorers=false`) — UPPFÖLJNING, ej Etapp 1.**
Design ritade fallet (volleyboll: "+1 set", setsiffror-fält, moment Matchstart/Mellan set/
Resultat) men det är en **egen scoring-modell** (set i stället för mål+målskytt). Etapp 1
bygger fotboll/målskytt-modellen; set-modellen tas när en set-sport ska föras live.

### B3. Vad mobilen medvetet INTE har

Ingen matchredigering (lag/datum/arena), ingen gallring, inget bildbibliotek, ingen
webbpublicering, ingen temaväljare, inga inställningar utöver API-nyckel vid första start.
Mobilen är en **matchförare**, inte en liten DPT2.

---

## Del C — Etapp 2: publicera stories utan Macen (rita ev., bygg senare)

- **C1. Render i molnet — INRIKTNING (Stig 2026-07-09, ej bindande, beslutas vid bygge):**
  **Cloudflare Browser Rendering** screenshotar en HTML/CSS-version av Horisont (designen
  *föddes* som HTML-prototyp — Pillow-rendern är porten) med matchdata + tema → PNG 1080×1920
  → R2. Alternativ som förkastades som inriktning men kan omprövas: canvas-render i PWA:n
  (renderdrift mellan mobiler), eller samma Pillow i en molncontainer (ingen drift men mer
  infra). **Ärlig avvägning: en renderare eller två** — Browser Rendering innebär att HTML:en
  på sikt blir den kanoniska källan och Pillow-porten regenereras/pensioneras. Låses skarpt
  när Etapp 2 byggs.
- **C2. Foto — ÖPPEN:** mobilfoto/kamerarulle → R2 (bildhosting-mönstret finns). En
  **fotolös grafikvariant** som snabbväg (Horisont kräver foto idag) är önskad inriktning
  men ospecad — tas i Etapp 2-designen.
- **C3. Meta-publicering från workern** — samma tokens som `tjanster/meta_api.py`, flyttas
  till worker-secrets.
- **C4. Risk att äga:** två render-implementationer (HTML-mall + Pillow) kan glida isär.
  På sikt bör EN utses till källa. `[BEKRÄFTA på sikt]`

---

## Del D — Växling & närvaro (Etapp 3, billig)

- `fors_fran` i live-dokumentet sätts av den som skriver ("mobil"/"desktop" + tid).
- Desktop: liten pill i `ResultatRemsa` — **"📱 Förs från mobilen · 19:42"**. Mobilen
  visar motsvarande. Ingen låsning — fältvis LWW + indikatorn räcker för en person.

---

## Säkerhet

Bearer-nyckel (samma modell som `CONTENT_SYNC_API_KEY`), matas in EN gång i PWA:n vid
första start (localStorage), allt över HTTPS. Nyckeln hamnar aldrig i sajtens publika
bundle — PWA:n är en privat yta bakom nyckeln. **BESLUT (Stig 2026-07-09): delad nyckel
räcker för Etapp 1.** Per-enhets-token är lätt att lägga till senare om det behövs.

---

## Byggordning (efter Design-rundan)

Mest rör *inte* DPT2-repot — worker + PWA byggs isolerat, desktop-krokarna hakas på sist.

1. **Worker** — `/api/live/*` i content-sync (auth/D1/R2/deploy finns). `live_state` +
   match-paket, deploy-hook aldrig på live-rutter. Testbart med curl, ingen DPT2-ändring.
2. **PWA** — egen kodbas servad av workern, mot färdig worker. Vy 1 + Vy 2 (1b) + målskytt (1e).
3. **Desktop-krokar** — `tjanster/live_synk.py` + push på `sattResultat`/moment + poll i
   Publicera + närvaro-pill (Del D). Additivt.
   **OBS:** Design antog att desktop-krokarna måste vänta på Matchpublicering-ombygget, men
   **det är redan klart och pushat** (`b645919` m.fl., 2026-07-08) — den delade ytan
   (`ResultatRemsa`/`Publicera.svelte`) står. Krokarna kan landas när som helst.
   (Rör Publicera.svelte försiktigt — den öppna Generera-regressionen sitter i samma fil.)

Steg 1–2 kan deployas (samma Cloudflare-flöde som content-sync) utan att röra desktop-appen.

## UI-leverabler till Design (sammanfattning)

1. **Mobil Vy 1** — matchval med live-badge.
2. **Mobil Vy 2** — matchvyn: scoreboard-stepper, moment-chips, roster-målskytt, tema,
   synk-status/offline-kö. *Detta är huvudleverabeln.*
3. **Mobil Vy 3** — story-preview + publicera (Etapp 2, om den ritas nu).
4. **Desktop-tillägg** — synk/närvaro-pill i ResultatRemsa + Live nu (Del D).
5. **Tillstånd att designa:** offline med kö · "förs från andra enheten" · match utan
   roster (fritext-fallback) · sport utan målskyttar (`has_scorers=false`, t.ex. res_label/
   mid_label från annan sportprofil) · tom matchlista.

---

## Öppna frågor

**Lösta i Design-rundan (2026-07-09):**
- ~~3. Scope~~ → hela målbilden ritad, **Etapp 1 byggs** (Vy 1+2 + desktop-pill). ✓
- ~~4. Målskyttar~~ → roster-picker + minut, **ingen matchklocka**, minut valfri + editerbar. ✓
- ~~5. Halvtid-automatik~~ → **ja, med synlig ångerbar bekräftelse.** ✓
- ~~Tema~~ → **Skagen Hav låst, ingen väljare.** ✓

**Infra-val — LÅSTA (Stig 2026-07-09):**
- ~~1. Worker-placering~~ → **utöka content-sync** med `/api/live/*`. ✓
- ~~2. Match-paket~~ → **alla kommande automatiskt, via På gång-triggern**; roster när den finns. ✓
- ~~6. Etapp 2 render~~ → **Browser Rendering som inriktning** (ej bindande, beslutas vid bygge);
  fotolös variant önskad, ospecad. ✓
- ~~7. Auth~~ → **delad nyckel räcker för Etapp 1.** ✓

Inga öppna frågor kvar för Etapp 1 — byggklar.
