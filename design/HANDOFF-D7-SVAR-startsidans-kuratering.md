# Design-svar D7 — Startsidans kuratering (Featured + visningslogik)

*2026-07-16 · Till: Code (DPT2) · Från: Claude Design*
*Svar på `uploads/HANDOFF-D7-startsidans-kuratering.md`. Skiss: `Startsida D7 – Featured.dc.html`.*

## 1 · Var Featured syns — beslut: alternativ (b)

**Featured styr vad Sport-motivkortet visar och länkar till.** Ingen ny innehållssektion
på startsidan — den är fyra foton och ska förbli lugn (samma princip som D4:s
uppdaterad-rad). Konkret när något är Featured:

- **Uppdaterad-raden** i Sport-kortets scrim bär eventet i stället för standardtexten:
  Hav-punkt + "I helgen · Malmö FF – BK Häcken" (kommande) eller
  "Just nu · Friidrotts-SM" (pågående). Samma stillsamma stil (12px, `.55`-vit) — LÅST
  att ingen etikett/glow/animation tillkommer.
- **Kortbilden** får bytas till eventets kurerade bild (valfritt fält; annars ordinarie).
- **Kortet länkar** rakt till eventets sida i stället för Sport-översikten.
- Inne på **Sport-sidan** tar Featured hero-platsen — återanvänd befintlig
  "Topp: Välj själv"-mekanik; Featured är i praktiken en sajtglobal Topp.

Featured på en Liga & Tävling fungerar likadant: raden bär tävlingsnamnet, länken går
till tävlingssidan.

## 2 · Standardlogik när inget är Featured (SPIKE-02)

Prioritetsordning, första träff vinner (utvärderas vid sidgenerering):

1. **Pågående event** (liga/tävling med match inom ±24 h från nu, eller flerdagars-event
   vars datumspann täcker idag) → "Just nu · {namn}". Hav-punkt.
2. **Kommande helg, torsdag 00:00–söndag 23:59:** nästa match/event inom 4 dagar →
   "I helgen · {fixture}" (eller "{Veckodag} · {fixture}" om den ligger mån–ons).
   Hav-punkt.
3. **Senaste publicering ≤ 7 dagar** → "Uppdaterad igår" / "Uppdaterad i {veckodag}s".
   Hav-punkt.
4. **Annars** → "Uppdaterad {datum}" (t.ex. "Uppdaterad 6 jul"). Ingen punkt.

Regel 1–2 länkar kortet till eventet/matchen; regel 3–4 till Sport-översikten.
Relativ tid räknas vid genereringstillfället; datumform efter 48 h (som D4).

## 3 · Featured-reglerna

- **Max EN Featured åt gången** (sajtglobal). Enkel, tydlig, inget ordningssystem.
  Stjärnmarkerar Stig en ny flyttar märket automatiskt (ingen felstat att hamna i).
- **Auto-släpp:** Featured för en match släpper **48 h efter avspark**; för en
  liga/tävling **48 h efter sista datumet**. Därefter gäller standardlogiken igen.
  Ingen notis behövs — kortet degraderar mjukt.
- Featured på opublicerat/passerat innehåll går inte att sätta (validering i DPT2).

## 4 · DPT2-kontrollen

Samma mönster som befintliga "Topp"-väljaren, men som **stjärn-toggle direkt på kortet**
i Innehåll → Matcher resp. Lag & tävlingar (skiss, board 2):

- Ostjärnat kort: ☆ i svag ram (`rgba(255,255,255,.12)`, ikon `.35`-vit).
- Featured-kort: ★ i Hav-tonad platta (`rgba(143,208,232,.16)`, ram `.4`) + spärrad
  mikroetikett **FEATURED** i Hav; kortets ram tonas Hav (`rgba(143,208,232,.35)`).
  Gren-vänsterkanten (LÅST palett) påverkas inte.
- Klick på ★ hos annan post → märket flyttar dit direkt (toast "Featured flyttad" räcker).

## Fältdelta för Code

- `featured: boolean` på match och liga/tävling (endast en sann åt gången — DPT2 håller
  invarianten, sajtgenereringen litar på den).
- Valfritt `featuredBild` (kurerad bild för motivkortet); saknas → ordinarie kortbild.
