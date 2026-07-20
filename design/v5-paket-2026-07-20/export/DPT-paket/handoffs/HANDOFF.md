# HANDOFF — Eventmodell-epiken + fristående backlogpunkter

*2026-07-17 · Till: Code (DPT2 + iOS) · Från: Claude Design*
*Underlag: `DATAMODELL v5.md` · Mockups: `DPT v5 — Event.dc.html`, `DPT iOS v2 — Event.dc.html`, `Webb v5 — Eventsida.dc.html`*
*Egen branch. Löpande leverans — mergeordningen nedan är designens förslag.*

---

## Leveransordning (förslag)

1. **Steg A — fristående, kan gå direkt:** målmappar per flöde (§5) + original utan overlay (§6). Rör inte datamodellen.
2. **Steg B — datamodellen:** Liga/Event/Individ-registren + matchens två fält + migration (§1). Ingen UI-förändring krävs ännu — befintliga vyer läser `liga:` där de idag läser `tavling:`.
3. **Steg C — DPT2 Event-sektionen** (§2) + På gång-logiken (§3).
4. **Steg D — iOS v2** (§4): restid mot deltillfälle + dynamisk bakgrund (kräver B, ★-flaggan i C-flödena).
5. **Steg E — hemsidans eventsida** (§7, kräver B).

---

## §1 · Datamodell — Liga + Event ersätter Tävling

Fullständig spec i `DATAMODELL v5.md`. Kärnan:

- **Liga** (`content/liga/`): långlivad, säsonger, framtida historik. **Event** (`content/event/`): tidsbegränsat; `typ` är en ETIKETT (`masterskap | cup | turnering | varldscup | ovrigt`) — ingen typ-styrd logik.
- **Match:** `tavling:` ersätts av två valfria fält `liga:` + `event:` (båda kan finnas samtidigt; träningsmatch kan sakna båda).
- **Migration:** befintliga `tavling:` med typ `liga` → `liga:`; typ `turnering|masterskap` → `event:`. Inga andra fält röstas.
- **Gren** bäddas in i eventet; **deltagare** = `{ individ: <ref>, grenar: [...] }` på eventet. **Individ** = eget register (som Lag). Individens eventhistorik HÄRLEDS genom att fråga eventen — skriv aldrig historik på individen.
- **Kategori:** toppnivå statisk (`sport · landskap · manniskor · film`), underkategorier = redigerbart register (se `DATAMODELL v5.md`). Byggs i steg B men används brett först i senare epiker.

## §2 · DPT2 — Event-sektionen (mockup: `DPT v5 — Event.dc.html`)

- Ny nav-post **Event** under Planera (mellan Matcher och Lag & ligor; "Lag & tävlingar" döps om till **Lag & ligor**).
- **Lista:** rader med typ-badge (kantlinje i typfärg: mästerskap amber, cup `#3E7C87`, turnering `#6E8757`, världscup `#2F7CB0`), namn, sport, metarad (period · ort · arena · antal grenar/matcher/individer), statuspill (pågående = amber). Filter: Alla/Pågående/Kommande/Avslutade. Status härleds av period mot idag, som matchens statuslogik.
- **Detaljvy:** rubrik + typ/status-badges, metarad, sedan:
  - **På gång-kort:** segmentkontroll Auto/Heldag/Matcher (default Auto) + textrad som förklarar aktuellt beteende (se §3).
  - **Matcher-kort:** kopplade matcher (lagbrickor, fixture, tid/resultat). "+ Koppla match…" öppnar lista över okopplade matcher i samma sport → klick kopplar. Tomläge: "Inga matcher — grenarna är programmet."
  - **Grenar-kort:** rad per gren (namn + antal individer/matcher). "+ Ny gren".
  - **Deltagare-kort:** individ (initial-bricka) + grenar. "+ Ur individregistret". Fotnot om härledd historik.
- Kopplingen ska OCKSÅ gå från matchens formulär: två fält Liga ▾ / Event ▾ (+ "skapa nytt event") — samma data, två dörrar.

## §3 · På gång-logik (DPT2 + hemsida)

Per event, styrt av `pagang_lage` (default `auto`):

- **auto:** före perioden → ett heldagskort för eventet. Under perioden → dagens/nästa kopplade matcher som egna kort. Efter → resultat.
- **heldag / matcher:** manuell override av respektive läge.
- **Invariant (viktigast):** en match med `event:` visas ALDRIG utan sitt sammanhang — kortet bär alltid "Del av {event.namn}" med länk till eventet. Gäller På gång, hemsidan och iOS.

## §4 · iOS v2 (mockup: `DPT iOS v2 — Event.dc.html`)

**Restid efter eventstart (backlog §3):**
- Restidsbegreppet försvinner INTE när heldagsevent passerat 08:00. Målet blir **nästa deltillfälle**: nästa kopplade match/gren med klockslag.
- Hemkortet visar: "NÄSTA DELTILLFÄLLE" + namn + "Del av {event} · kl HH:MM" + ÅK SENAST (stort, Sol-färg) + restid.
- "Sikta på annan tid ▾" → bottenark: lista över dagens/kommande deltillfällen (auto-valet markerat) + rad "Eget klockslag". Badge AUTO/VALD visar källan. Ingen avstängning behövs.
- Väderraden "HÄR I DAG": 5 tidpunkter 08–20 (befintligt mönster) + gyllene timmen; destinationsväder vid deltillfället i kortets subrad.

**Dynamisk bakgrund (backlog §2):**
- Fallordning: **★-pott för dagens sport/kategori → egen uppladdad bild → standardgradient**.
- ★-flaggan sätts i DPT2 (Leverera/Publicera — bild markeras "iOS-bakgrund", taggas med sport/kategori ur jobbet). Fältdelta: `ios_bakgrund: true` på bild i urval/leverans.
- iOS Inställningar → "Startsidans bakgrund": radioval Automatisk (rek.) / Egen bild / Standard + read-only-grid som visar ★-potten för aktuell sport (märk vilken som visas nu).

## §5 · DPT2 — målmappar per flöde (backlog §4)

- Tre separata målmappar: **Snabbplock** (fungerar samtidigt som backup), **Gallring** (t.ex. SSD), **Generera media** (Dropbox-mapp för delning).
- **Default i Inställningar** (tre fält med mappväljare) + **override i respektive flöde** (mappväljare i flödets körpanel, förifylld med default; overriden gäller den körningen, inte som ny default).

## §6 · DPT2 — original utan overlay (backlog §5)

- Vid generering med overlay sparas originalbilden alltid bredvid exporten: `namn.jpg` + `namn-original.jpg` i samma utmapp.
- Gäller varje some-export med overlay, utan opt-in. Syfte: originalet redigerbart + varje export har alltid en ren tvilling.

## §7 · Hemsidan — eventsida (mockup: `Webb v5 — Eventsida.dc.html`)

- Eventsida per event: hero (bild, typ-badge, statusrad "Pågår · dag X av Y", namn, sport · period · ort/arena), gren-filterchips, **matcher grupperade per dag** (dagrubrik + fas): spelad rad = resultat + "Se bilderna →" (galleri), kommande = tid + Kommande-badge.
- Gren-markör på matchrad: 4px stapel i **låsta paletten** (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`) + neutral textetikett. Ingen färgad text, ingen "DAM"-etikett.
- Matchsidor/matchkort bär "Del av {event}"-badge som länkar till eventsidan (§3-invarianten).
- Eventsidan byggs ur samma data som På gång — uppdateras när matcher kopplas/avslutas.

## Fältdelta (sammanfattning för Code)

- NYA collections: `liga/`, `event/` (ersätter `tavling/`), `individ/`, `kategori/` (underkategorier).
- Match: `liga: <ref|null>`, `event: <ref|null>` (ersätter `tavling:`).
- Event: `typ`, `period`, `ort`, `arena`, `liga?`, `kalender`, `pagang_lage: auto|heldag|matcher`, `grenar[]` (nu med `pass[{namn, datum, tid, plats?}]`), `hallpunkter[]` (fria, valfria), `deltagare[{individ, grenar[]}]`.
- Bild (urval/leverans): `ios_bakgrund: bool`.
- Inställningar: `mapp_snabbplock`, `mapp_gallring`, `mapp_media`.
- iOS: UserDefaults för restid-override per event (deltillfälle-id eller klockslag; nollas när tillfället passerat).

## §8 · Tidsatt program / deltillfällen — NY (spec: `DATAMODELL v5.md` → Program/deltillfällen)

Mockupen `DPT iOS v2 - Jobbdetalj.dc.html` visade "dagens deltillfällen" — en tidslinje appen inte har stöd för idag. Beslutat att bygga.

- **Gren (= disciplin) får `pass[]`:** valfria tidsatta tillfällen, var och en med **egen** `datum` + `tid` (+ valfri `plats`). Kval kan gå dag 1 morgon, final dag 2 kväll — därför tid på passet, inte på grenen.
- **Program är härlett, inte lagrat:** eventets dagsprogram = alla `pass` + alla `event:`-kopplade matcher med klockslag + eventets fria hållpunkter, sorterat på datum+tid, grupperat per dag. Ändra passets tid → programmet följer med. Ingen dubbellagring.
- **Matcher oförändrade** som sådana (fristående / liga-kopplade). Det är bara *inom ett event* de vävs in i samma tidslinje som grenpassen.
- **Individer per deltillfälle härleds:** pass → gren → `deltagare`. Aldrig skrivet på passet.
- **Nästa deltillfälle** (iOS restid, §4) = första pass/match med klockslag framåt. Nu väldefinierat.
- **DPT2-UI:** event-detaljen får ett **Program-kort** (pass per gren + hållpunkter, tidslinje per dag, "näst"-markering). Lägg till/ändra/ta bort pass manuellt.
- **Läs in spelschema — utökning:** importören (idag matchtider för ligor/säsonger) läser även ett events **startlista/program** → skapar grenar om de saknas, fyller `pass`. Plus **klistra in / CSV** från arrangörens PDF. Allt manuellt justerbart efteråt.

## Utanför denna handoff — SE `HANDOFF-etapp-2-4.md`

UX-lyftet (gallring som ett flöde, träning som biprodukt, momentmallar per jobbtyp, publiceringskö, Innehåll som granskningskö, jobbet som nav, individregister, målmappar i UI) är nu designat och inbyggt i `DPT v5.dc.html` — spec i `design_handoff_eventmodell/HANDOFF-etapp-2-4.md`.
