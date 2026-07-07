# Handoff → Claude Design: UI-synk efter implementation av match-huvud/Publicera/WEBB

**Vad det här är:** en statusrapport tillbaka till dig efter att vi byggt din
`design_handoff_matchhuvud_webb` skarpt. Det mesta är byggt precis enligt din spec — men
några ytor **utvecklades under skarp testning** och avviker nu från prototypen. De är
markerade **⚠ AVVIKELSE** nedan; uppdatera gärna din prototyp så bilderna matchar igen.

**Färsk kod:** `kallkod/` = snapshot av de faktiska filerna (7 juli). `MatchHuvud.svelte` är den
nya komponenten; `Publicera.svelte` bär hela SoMe-logiken.

**Låst (oförändrat, respekterat):** gren = färg utan textetikett (Dam `#8E5A86` · Herr `#3E7C87`
· Mixed `#6E8757`, ingen kant om gren okänd) · Live:s riktiga server-renderade förhandsvisning ·
Horisont-grafiken · lag-loggornas contain-fallback.

---

## 1. Sammanhållet match-huvud (KLAR — enligt din §1–2)

Byggt som `MatchHuvud.svelte` — ETT ljust huvud i Publicera (Live + SoMe) som ersätter forna
"Aktiv match"-remsan + svarta resultattavlan. Innehåller: lag-brickor + redigerbart resultat +
målskytt-chips · fixtur + mellanresultat · **● AKTIV** (grön prick) · **Byt ▾** (inline
matchlista med gren-prick per rad + bekräftelse *"Byt aktiv match till X? Pågående arbete sparas
kvar på nuvarande match."* → Avbryt / Byt match) · **Inaktivera** (→ tomlägesruta) · nedre rad
med Pixieset / På hemsidan + arena + **kopplat material** (`X utkast · Y publicerat` + piller
**Live / SoMe / Webb** med ✓ publicerat / · utkast / – inget).

Gren-färg = **5px vänsterkant + mjuk glow-ring**, ljus botten (temavariabler, följer mörkt läge).

## 2. Ljus resultattavla (KLAR — din §2)

`ResultatRemsa` (matchreferat-tavlan i Innehåll → Sport) är nu ljus + gren-behandlad, inte svart
`#23201a`. Samma komponent, temastyrd.

> ⚠ **Liten avvikelse:** i Innehåll → Sport står `AktivMatchRad`-remsan **kvar** ovanför den ljusa
> tavlan (din skärmbild `04` visade bara tavlan). Vi rörde inte den i detta pass — säg till om du
> vill att match-huvudet (§1) ska ersätta remsan även i Innehåll.

## 3. Kompakt typväljare (KLAR — din §3)

Fem stora kort → **segment-rad** (ikon + etikett, aktivt segment i kategorifärg) + hjälptext för
aktiv typ under raden. Texterna vi satte (`cmsTabSub`):
- Blog — "Journal, resor & fritext — en fristående bloggpost."
- Sport — "Matchreferat — hämtar resultat, lag & galleri från Matcher."
- Landskap — "Bildserie — landskap & natur, endast bilder."
- Event — "Porträtt, bröllop, student & företag."
- På gång — "Kurerad lista som driver webbens Sport → På gång."

## 4. SoMe: infoga token vid markören (KLAR — din §4)

Token infogas vid markörens position (med mellanslag runt), markören flyttas efter. Etikett
**"Infoga vid markören:"**.

## 5. SoMe: overlay-omslag — ⚠ AVVIKELSE (utvecklades under testning)

Din §5 beskrev: *"Live-overlay 4:5 = listar matchens skapade Live-moment som 4:5-kort i temafärg;
klick väljer overlayen som omslag."* Efter skarp testning blev flödet konceptuellt annorlunda —
**detta är den viktigaste ytan att uppdatera i prototypen:**

**Overlayen läggs OVANPÅ den bild man valt som omslag i SoMe** — den är inte ett fristående kort,
och den renderas inte på momentets eget foto. Flödet:
1. Växla omslag: **Vald bild ↔ Live-overlay 4:5** (som förut).
2. I overlay-läge: välj **moment** (chips, bara om flera skapade Live-moment finns; annars
   auto-valt) + välj **vilken bild overlayen läggs på** (samma klickbara omslagsrad som foto-läget).
3. En **4:5-förhandsvisning** visar Live-momentets Horisont-grafik renderad ovanpå den valda bilden
   (riktig render, 1080×1350, samma pipe som Live-storyn — momentets tema hämtas från materialet).
4. **Omslagsbilden tas UT ur karusellen** — den är "förbrukad" som overlay-bakgrund, så den dubblas
   inte som bild 2. Totalt antal slides oförändrat (overlayen = slide 1).
5. I "Kanaler & bildset · Instagram-inlägg" markeras overlayen som `omslag` (i stället för ett foto).

*Kort: "Live-overlay" = "ta Live-momentets grafik och lägg den på den bild jag valt som omslag,
i 4:5". Designnotering: en tydligare visuell koppling mellan den valda bilden och det renderade
resultatet (t.ex. pil/överlägg) vore en naturlig polering — idag är det väljarrad + separat preview.*

## 6. SoMe/Live: "Nästa match" auto-hämtas (KLAR — din §6)

Momentet Nästa match har rad *"Nästa i schemat: <lag · datum tid>"* + **"Hämta från Matcher →"**
som fyller motståndare/datum/tid/arena ur nästa kommande match för aktivt lag. Redigerbart efteråt.

## 7. På gång: specifik match + heldag (KLAR — din §7, + webbkedja)

- **Matchväljare** (dropdown över kommande matcher) i Förifyll — pekar på en *specifik* match.
- **Heldag**-växel bredvid Tid: på → döljer tidsfältet ("Heldag — ingen specifik tid"), listan/
  förhandsvisningen visar "Heldag".
- **Heldag går hela vägen till webben:** nytt `heldag`-fält i .md-frontmattern → content-sync →
  Astro (sport-sidan visar "Heldag" i stället för klockslag). Live i produktion.

---

## Sammanfattning — vad som behöver uppdateras i prototypen

1. **SoMe overlay-omslag (§5)** är den stora förändringen — overlayen läggs på en **vald bild**,
   inte som fristående moment-kort, och omslagsbilden lämnar karusellen. Ta in det i prototypen.
2. **Innehåll → Sport (§2)** har fortfarande kvar Aktiv match-remsan ovanför tavlan — beslut om
   match-huvudet ska in där också väntar på dig.
3. Allt annat (§1, 3, 4, 6, 7) är byggt enligt din spec och kan speglas rakt av.
