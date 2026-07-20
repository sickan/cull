# Design-handoff D16 — Ny struktur (register + nav) · rik låsskärmswidget · startskärm "Idag"

*2026-07-20 · Från: Claude Design · Till: Code*
*Tre leveranser samlade. Struktur-delen (A) är ny och svarar på ditt tillägg 20/7 om panel-sammanslagningen. Widget (B) och Idag (C) är samma beslut som i D15 — här ihoppackade så allt ligger i ett dokument.*

Gemensam ton (oförändrad, se D13): Skagen Hav-mörk `#0a0d11` / Sol-ljus `#F4EEE2`, mässing `#F0B45A` (mörk) / `#C9871F` (ljus) som **enda** accent, Saira Condensed i rubriker/siffror, grenkant utan textetikett (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`), kategorifärger (Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`), inga emoji.

---

## A · Ny struktur — Fotojobb / Tävlingar / Lag & utövare (DPT2)
**Mockup:** `DPT v5 - Struktur (register + nav).dc.html` (levande — nav, filter, tävlings-expand och register-editor är klickbara).

### Grundprincip
> **Match viker in i jobbet. Tävling ligger ovanför det.**
- **Match : Fotojobb ≈ 1:1** — matchen är en *facett* av ett sport-jobb (en dag). Viker in i jobbet.
- **Tävling : Fotojobb = 1:många** — en tävling *spänner över* flera jobb/dagar. En **behållare ovanför** jobben, aldrig "ett stort fotojobb".
- **Match & tävling finns bara för Sport.** Fotojobb-ryggen spänner över alla kategorier; bröllop/landskap/porträtt/film visar aldrig match- eller tävlingsgrepp (samma SPORT-ORD-städning).

### Nav: före → efter (Planera)
`Fotojobb · Matcher · Event · Lag & ligor`  →  **`Fotojobb · Tävlingar · Lag & utövare`**
- **Matcher** utgår som egen post → blir ett **filter/vy inuti Fotojobb**.
- **Event** → **Tävlingar** (rymmer både **Ligor** långlivade + **Event** mästerskap/cup/turnering).
- **Ligor** flyttar in under Tävlingar (bort från "Lag & ligor").
- Registret heter **Lag & utövare**.

### Fotojobb (enda toppytan)
- Alla uppdrag, kalenderdriven, basenheten. Kategori-chips (Alla · Sport · Landskap · Människor · Film) med färgprick; kategorikant per rad.
- Segment **Alla jobb / Matcher** — visas bara när Sport/Alla är valt. "Matcher" = en vy av Fotojobb (sport-jobb med match-facett), inte en egen nav-post.
- Sport-match-rad visar `MATCH`-facett + "Del av {tävling}" (eller "Fristående"). Icke-sport-jobb visar inget av det.

### Tävlingar (behållare, 1:många)
- Egen ingång. Segment Alla · Ligor · Event. Kort med typ-badge (Liga/Mästerskap/Cup), sport, period, **N jobb**.
- Expandera → listar **sina kopplade fotojobb via `tavling_id` (M-11)** — baklänges-fråga, inte namn-gissning.
- Härifrån bor grenar, deltagare och program; jobben hänger under. En tävling kan **inte** vika in i ett enskilt jobb.

### Lag & utövare (ett register, UI-segmenterat)
- Delar tabell i datan (`kind='individ'`, D11b §2) — **ren UI-konvergens, ingen migrering, noll datarisk.**
- En lista, segmenterad med chip **Alla · Lag · Utövare**. Sök på namn/klubb.
- **Editorn auto-morphar efter vald post** — ingen manuell "Slag"-växel. Typ väljs **bara** vid `+ Nytt lag` / `+ Ny utövare`.
- **Lag ≠ utövare i tonen** (samma tabell, olika formulär): lag = logga/ställfärger/trupp; utövare = porträtt/klubb/klass/@-konto + "Tävlar i" (härlett via grenen, aldrig lös tävling-chip på personen).
- Nås oftast **inifrån** (deltagarval i tävling/gren) snarare än som jämbördig topp-panel — men finns kvar i nav.

### Öppet
- Kalendergruppering & sökfält i Fotojobb (fråga ställd till Stig — inte byggt än).
- Bygget sker **efter SM** (samma tidslås som D14 / MERGE-spec skiva 4).

---

## B · Rik låsskärmswidget (iOS)
**Mockup:** `DPT iOS v2 - Låsskärm rik widget.dc.html` · lägen Idag / Flera dagar bort / Ledig dag. *(Standalone-export: `export/D15-rik-widget/`.)*

En rektangel, två axlar — ingen separat nedräkningscirkel. Monokromt (systemet tonar låsskärmen).
- **HÄR (vänster):** rubrik `HÄR · IDAG`, väder **08–20 i 5 segment** (tid + mono ikon + temp), underrad **`Borlänge`** (bara orten; vädertjänsten flyttad till Inställningar — D21-SVAR §0).r det).
- **DÄR (höger):** rubrik = **jobbets faktiska dag** (`TORS 24 JUL · 14:00`, `OM 12 D · 13 FEB`) — aldrig "IDAG" om det inte är jobbets dag. Namn, rad med bilrestid + prognosväder för jobbets dag, ort. Fungerar veckor bort.
- Panelerna är **topp-alignade**. Avgång/nedräkning bärs av **inline-raden ovanför klockan** (`Friidrotts-SM 14:00 · åk 12:15`). *(RÄTTAT D21 §0.)*
- **Data (App Group snapshot):** tjänst (kalender/manuell), nästa jobb (DPT/M-11), WeatherKit ×2 (nu här + prognos för jobbets dag där jobbet är).
- **Ändring mot `HANDOFF-widget-lasskarm.md`:** den separata gauge-cirkeln utgår i denna rikare variant. Sigillet lever kvar i StandBy & appen.

---

## C · Startskärm "Idag" (DPT2)
**Mockup:** `DPT v5 - Start.dc.html` · ny toppnivå i nav ("Idag", ovanför Planera).

Lugn kommandobrygga på morgonen. Ljus standard, mörk via temaväxel.
- Hälsningsrad → resume-rad ("Fortsätt där du var", aktivt jobb + progress) → två kolumner.
- **Kräver åtgärd** — prioriterad kö: ackreditering ej inskickad (`--danger`), plats saknas (`--danger`), startlista saknas (`--warn`), gallring pågår (`--info` + progress), leverans väntar (`--warn`).
- **Närmast på tur** — kommande jobb, kategorikant + nedräkning + beredskaps-chip.
- **Statistik** (vecka/månad), **Inkorg & svar** (ackreditering beviljad, svar, förfrågan), **Snabbvägar**.
- **Nya färg-tokens** (båda teman): `--danger` `#B0483A`/`#E06A5A`, `--warn` `#B5791C`/`#E0A93E`, `--info` `#2F7CB0`/`#5EA6D8`.
- **Öppet:** innehållet är exempeldata — koppla kö/statistik/inkorg till riktiga källor.

---

## Sammanhang / beroenden
- **M-11** (`fotojobb.tavling_id`, byggt) bär både "jobbet äger matchen" (D14/iOS) och "tävlingen listar sina jobb" (A ovan).
- **D14** (`HANDOFF-D14…` / D15-svaret) är match-halvan av samma merge på iOS; A är desktop-ryggen. Håll dem i synk.
- **Designa nu, bygg efter SM** genomgående.
