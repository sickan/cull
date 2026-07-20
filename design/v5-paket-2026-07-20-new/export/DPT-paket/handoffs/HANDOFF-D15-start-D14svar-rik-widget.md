# Design-handoff D15 — Startskärm (DPT2), D14-svar (jobbet äger matcher) & rik låsskärmswidget

*2026-07-20 · Från: Claude Design · Till: Code*
*Tre leveranser i en runda. Alla mockups är levande (klickbara).*
*Innehåller även **svaret på D14** (avsnitt B) — ersätter separat `HANDOFF-D14-SVAR-*.md`.*

Gemensam ton (oförändrad, se D13): Skagen Hav-mörk `#0a0d11`, mässing `#F0B45A` som enda accent, Saira Condensed i rubriker/siffror, grenkant utan textetikett (Dam `#8E5A86` · Herr `#3E7C87` · Mixed `#6E8757`), kategorifärger (Sport `#2F7CB0` · Landskap `#C9871F` · Människor `#C9657F` · Film `#8A6FB0`), inga emoji.

---

## A · Startskärm "Idag" (DPT2 / desktop)
**Mockup:** `DPT v5 - Start.dc.html` · ny toppnivå i nav ("Idag", ovanför Planera).

En lugn kommandobrygga — det första du ser på morgonen. Ljus (Sol) standard, mörk (Hav) via temaväxel; samma var-system som resten av DPT2.

**Layout:** hälsningsrad överst (veckodag + "God morgon" + summering) → resume-rad ("Fortsätt där du var", aktivt jobb + progress) → två kolumner.

- **Kräver åtgärd** (vänster, brett) — den prioriterade kön. Rad = severitetsfärgad ikonruta + titel/kontext + åtgärdsknapp (mässing). Täcker: ackreditering ej inskickad (`--danger`), plats saknas (`--danger`), startlista saknas (`--warn`), gallring pågår (`--info` + progressbar), leverans väntar (`--warn`).
- **Närmast på tur** (vänster) — kommande jobb, närmast först. Kategorikant + nedräkning/datum + namn + arena + beredskaps-chip (Klar / Saknar info / SoMe: kundens ok).
- **Statistik** (höger) — 2×2 brickor med vecka/månad-växel (Fotojobb, Bilder levererade, Publiceringar, Ø dygn till leverans).
- **Inkorg & svar** (höger) — inkomna svar: ackreditering beviljad (grön ✓), pressvärd svarade (info), ny förfrågan (kategorifärg), startlista uppdaterad (dämpad).
- **Snabbvägar** (höger) — Nytt fotojobb · Läs in spelschema · Nytt event · Öppna aktivt jobb.

**Nya färg-tokens** att gjuta i temat (båda teman): `--danger` (ljus `#B0483A` / mörk `#E06A5A`), `--warn` (`#B5791C` / `#E0A93E`), `--info` (`#2F7CB0` / `#5EA6D8`).

**Kvar/öppet:** allt innehåll är exempeldata — kön/statistik/inkorg ska matas ur riktiga källor (M-11 jobb↔tävling, ackrediteringsstatus, leverans-/gallringsläge). Radernas åtgärdsknappar leder in i respektive flöde.

---

## B · Svar på D14 — jobbet äger sina matcher (iOS)
**Mockup:** `DPT iOS v2 - Jobbet äger matcher.dc.html`

### Q1 — Hur äger ett jobb sina matcher i JobbDetalj
"Dagens deltillfällen" växer till **Program · hela jobbet**, grupperat per dag.
- **Dagrubrik** (kollapsbar): "Dag N · veckodag datum", idag auto-öppen, övriga hopfällda med sammanfattning ("22 pass · 4 finaler · 2 ★"). Tryck rubriken för att fälla ut/ihop.
- **Rader** per dag, tidssorterat: grenpass + kopplade matcher + fria hållpunkter. Grenkant (klassfärg), tid i Saira Condensed. **"Nästa" framhävt** i eget topp-kort ovanför programmet + `NÄST`-badge i listan. Finaler får `FINAL`-badge. ★-favorit per rad.
- **Skalar** (Friidrotts-SM 79 grenar, EuroVolley en vecka): dag-kollaps + filter **Alla / ★ Mina / Finaler** + sökfält. Filter tvingar fram öppna dagar och döljer tomma.
- Tryck en gren → **sheet** med "Skapa SoMe" (mässing) + "Öppna passet" — matar in i befintliga fältflödet, oförändrat. Hållpunkter (invigning o.d.) är inte tappbara, ingen SoMe.

### Q2 — Matcher-fliken: **ta bort den**
En match är en **facett av ett jobb** (merge skiva 4). Konsekvens:
- **Flikar: `Hem · Matcher · Jobb · Bilder` → `Hem · Jobb · Bilder`** (3 flikar).
- Framtida & fristående matcher nås via **Jobb**-fliken: segment **Kommande / Denna vecka / Alla**. Mästerskap, cuper och enstaka matcher listas alla som jobbkort med **kategorikant** (ingen fotbollsikon). En lös match = ett jobb med match-facett ("FRISTÅENDE"-etikett).
- Ingen dubbelnavigation, och den sista tydligt sport-centrerade ytan avsportifieras.

**Invarianter bevarade:** "Del av {tävling}" i sheeten; grenkant utan textetikett; heldag = bara dagen; fältflödet oförändrat.

**Beroende:** M-11 (`fotojobb.tavling_id`) gör "jobbet äger matcherna" pålitligt. **Bygget sker efter SM** — matchflödet får inte destabiliseras under säsong.

### Bonus-check — accent
**Bekräftat: samma accent-roll, ny ton.** Mässing `#F0B45A` ersätter "brand orange" — det är **en** accent, inte två parallella. Gjut den delade färg-resursen (W-8/S-3) på `#F0B45A`.

---

## C · Rik låsskärmswidget (iOS)
**Mockup:** `DPT iOS v2 - Låsskärm rik widget.dc.html` · lägen: Idag / Flera dagar bort / Ledig dag.

En blick, två axlar — **din dag här** och **nästa fotojobb (oavsett avstånd)**. En enda rektangel (ingen separat nedräkningscirkel).

- **Monokromt med flit.** Systemet tonar låsskärmens widgets — ingen kategorifärg här (den bor på hemskärmen). Rikedomen ligger i informationstäthet.
- **HÄR (vänster):** rubrik `HÄR · IDAG`, väder **08–20 i 5 segment** (tid + mono linjeikon + temp), underrad `Borlänge · Tjänst 2431`. Tjänsten/passet = din dagliga tjänst ur kalendern (eller manuell); "Ledig" när du är det.
- **DÄR (höger):** rubrik = **jobbets faktiska dag** (t.ex. `TORS 24 JUL · 14:00`, `OM 12 D · 13 FEB`) — aldrig "IDAG" om det inte är jobbets dag. Namn (Saira Condensed), rad med bilrestid + prognosväder för jobbets dag, ort. Fungerar även när jobbet är veckor bort.
- **Nedräkning/avgång** bärs av **inline-raden ovanför klockan** (t.ex. "Tjänst 2431 · Friidrotts-SM 14:00 · åk 12:15") — inte av en gauge-cirkel.
- Panelerna är **topp-alignade** (HÄR-rubrik i linje med jobbets dag-rubrik).

**Datakällor (App Group snapshot):** tjänst/pass (kalender/manuell), nästa jobb (DPT / M-11), **WeatherKit ×2** — "nu" där du är + prognos för jobbets dag där jobbet är. Ingen restid/väder utan känd plats → ersätts av lugn uppmaning (se widget-handoffens §4/okänd arena).

**Notering (ryms det):** rektangeln är iOS bredaste låsskärmsyta; 5 väderpunkter + jobbblock ligger på taket. Vill vi ha mer (karta, soltider) hör det hemma på hemskärmens medium/large.

**Ändring mot tidigare `HANDOFF-widget-lasskarm.md`:** gauge-cirkeln som separat låsskärmsyta utgår i denna rikare variant (den stjäl bredd). Sigillet lever kvar i StandBy och i appen. Övriga beslut (Q1–Q6) i den handoffen står kvar.

---

## Kvar / öppet
- Startskärmens innehåll ska kopplas till riktiga källor (kö, statistik, inkorg).
- iOS Jobb-flik & LIVE-läge är fortfarande inte omgjorda i ny ton (D13:s öppna punkt kvarstår).
- Widgetens tjänst-källa: bekräfta att "tjänst/pass" hämtas ur kalender som antaget.
