# Claude Designer Brief — Dalecarlia Photo Tools (DPT)

## Vad är DPT?

Ett skrivbordsverktyg (macOS, pywebview-window 860×860 px) för sportfotografer.
Varje uppdrag går genom ett flöde: välj kort → förbered match → gallra bilder (AI) → leverera → publicera på Instagram → träna modellen.

Gränssnittet är en enfils-HTML (`gui.html`) som pywebview lastar. Vi migrerar till Astro,
men designspråket och komponenterna ska bevaras och förbättras.

---

## Nuläge — arkitektur

```
┌─ Topbar ──────────────────────────────────────────────────────┐
│  Logo  App-namn v2.1.0   [Aktivt urval-chip]   [Arbetar…]  🌙 │
└───────────────────────────────────────────────────────────────┘
┌─ Rail (172px) ─┐  ┌─ Main content (flex 1) ──────────────────┐
│ 📷 Urval        │  │  <panel data-panel="valj">               │
│ ⚡ Snabbplock   │  │  <panel data-panel="snabb">              │
│ ─────────────  │  │  …                                       │
│  1  Förbered   │  │                                          │
│  2  Gallra     │  │                                          │
│  3  Leverera   │  │                                          │
│  4  Publicera  │  │                                          │
│  5  Träna      │  └──────────────────────────────────────────┘
│ ─────────────  │  ┌─ Footer ─────────────────────────────────┐
│ ›_  Logg       │  │  Progressbar (3px) + hint + primär knapp │
└────────────────┘  └──────────────────────────────────────────┘
```

---

## Design-tokens (CSS custom properties)

### Ljust läge (default)
```css
--accent:           #E8820C   /* Dalecarlia-orange, primär action */
--accent-hover:     #D4760A
--accent-soft:      #FFF5EA   /* bakgrund för markerade element */
--accent-softborder:#F3C896

--win:              #F4F4F6   /* app-bakgrund */
--title:            #ECECEE   /* topbar + sheet-header */
--bottom:           #FAFAFB   /* footer */
--rail:             #F0F0F2   /* sidebar */
--seg:              #E4E4E6   /* segmented control bg */

--card:             #FFFFFF
--card-border:      #E6E6E8

--field:            #FBFBFC
--field-border:     #D4D4D8

--t-head:           #1C1C1E   /* rubrik */
--t-body:           #3A3A3E   /* brödtext */
--t-label:          #6B6B70   /* formuläretiketter */
--t-mut:            #9A9A9E   /* nedtonad text */
--t-help:           #B0B0B4   /* hjälptext */
--t-caps:           #A0A0A4   /* small caps-etiketter */

--div:              #DEDEDF
--div2:             #E2E2E4
--div3:             #EAEAEC
```

### Mörkt läge (`html[data-theme="dark"]`)
```css
--accent:           #E8820C   /* oförändrad */
--accent-hover:     #F0922A

--win:              #1C1C1F
--title:            #252528
--bottom:           #202023
--rail:             #202023
--seg:              #2E2E32
--card:             #252528
--card-border:      #37373C
--field:            #202023
--field-border:     #45454B

--t-head:           #F2F2F4
--t-body:           #DCDCE0
--t-label:          #A6A6AD
--t-mut:            #8A8A90
```

### Typografi
- **UI-font:** `-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif`
- **Monospace:** `'SF Mono', Menlo, monospace` (logg, tekniska värden)
- **Story-overlay-font:** Saira Condensed Bold/SemiBold/Medium (assets/fonts/)
- Fontstorlekar: rubrik 17px/700, sektionsrubrik 11px/700/caps, brödtext 13px, hjälp 11px, etikett 12px

---

## Komponent-inventarium

### Strukturella komponenter
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Topbar | `.topbar` | Fäst överst, innehåller logo + chip + working-indikator + theme-toggle |
| Rail/sidebar | `.rail` | 172px, scrollbar, steps med nummerindex |
| Step (nav-item) | `.step` | Aktiv = `.on` → orange-soft-bg; busy-dot vid körning |
| Panel | `.panel` | En åt gången, dold med `.hidden` |
| Footer | `.footer` | 3px progressbar + hinttext + primär-knapp höger |

### Kort & layout
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Card | `.card` | White, 12px radius, 1px border, 16px padding |
| Card-header | `.cardH` | 11px/700/caps/uppercase, `--t-caps` |
| Grid | `.grid` | 2-kolumns, gap 16px |
| Tool-card | `.tool` | Klickbar rad: stor ikon + titel + beskrivning, hover = accent-border |
| Stat-block | `.stat` / `.statN` / `.statL` | 4-kolumns statistik-grid |

### Form-element
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Input | `input.f` | 8px radius, accent focus-ring |
| Select | `select.f` | Samma stil |
| Checkbox | `.chk` + `.box` | Custom, checked = orange fill |
| Range/slider | `.srow` | Label + range + värde-badge |
| Primär knapp | `.btn.primary` | Orange, shadow, inline-flex med gap |
| Sekundär knapp | `.btn` | Border, hover = accent-border |
| Soft knapp | `.btn.soft` | Orange-soft bg, accent text |
| Story-moment | `.btn.storyMoment` | Toggle-knapp, `.on` = orange |

### Overlay & sheet
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Overlay | `.overlay` | Glassmorphism-bakgrund rgba(20,20,22,.42) |
| Sheet | `.sheet` | Modal: max-width 920px, 16px radius, drop-shadow |
| Sheet-header | `.sheetH` | Titel + valfri sub + stäng-knapp (X) |

### Urvals-galleri
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Gal | `.gal` | auto-fill grid, minmax(180px,1fr) |
| UV-kort | `.uv` | 4:3 bildyta + cap + eye-button overlay |
| Browse-kort | `.uv.browse` | Dashed border, folder-ikon, klicka för OS-dialog |

### Feedback
| Komponent | Klass | Notering |
|-----------|-------|----------|
| Working-dots | `.work` | 3 orange pulsande dots i topbaren |
| Progress-bar | `.ffill` | 3px footer-bar, pulse-animation vid lång op |
| Console | `.console` | SF Mono, scrollbar, `.err`=röd `.ok`=grön |

---

## Flödet idag (8 steg i rail)

1. **Urval** — galleri med senaste urval-mappar; klicka = aktivera
2. **Snabbplock** — kopiera kameralåsta bilder + Story-skapare (6 tillstånd × 3 teman × 2 format)
3. **Förbered** — matchdatabas (hemma/borta, datum, tid, arena, liga, spelare med handles)
4. **Gallra** — AI-cull-inställningar → kör → loggas
5. **Leverera** — export-rot, husstil, IPTC, tröjnummer OCR, XMP-sidecars
6. **Publicera** — Instagram 4:5 urval + Bildsvepet (Claude skriver bildtexter)
7. **Träna** — lär av egna val, A/B-testa modeller, granska osäkra, jämför par
8. **Logg** — live-terminal-output med progress-parsing

---

## Förändringen: Cull → Tool

**Vad som händer:** Gallra-steget (cull) omarbetas från ett formulär med checkbox-inställningar
till ett **Tool** — ett mer modulärt, verktygsbaserat paradigm där varje operation
är ett explicit verktyg användaren väljer och konfigurerar. Liknar mer hur Snabbplock
idag exponerar diskreta actions än hur Gallra exponerar en formsida med gömda avancerade inställningar.

**Implikationen för UI:**
- Tools behöver en tydligare visuell hierarki än dagens `.tool`-rader
- Konfiguration per tool (inte global settings-sida)
- Progressindikation per tool-körning (inte bara footer-baren)
- Rail-strukturen kan behöva förändras — kanske "Tools" ersätter workflow-stegen

**Frågor till designen:**
1. Ska rail visa verktyg i stället för workflow-steg, eller är stegsmodellen fortfarande rätt?
2. Hur hanteras tool-konfiguration — inline-expansion, sidopanel, eller sheet?
3. Hur indikeras att ett tool körs vs väntar vs är klart (per tool, inte globalt)?
4. Urval-chipet i topbar är bra — vad mer kan vara globalt kontext (aktiv match)?

---

## Astro-migrering — varför det påverkar designen

Det nuvarande gränssnittet är en enda monolitisk HTML-fil (`gui.html`, ~1600 rader) med all CSS och JavaScript inlined. Vi migrerar till **Astro** som byggsystem, vilket innebär att varje panel och UI-komponent blir en egen `.astro`-fil.

**Vad detta betyder för designen:**
- Komponenter ska vara självständiga och återanvändbara — designa med tydliga gränser mellan t.ex. `Card`, `ToolCard`, `FormField`, `Rail`, `Panel`
- Varje panel (Urval, Snabbplock, Gallra osv.) blir en egen komponent — inget problem med att ha olika layout-principer per panel
- CSS custom properties (design tokens) lever i ett globalt `Base.astro`-lager — lätt att byta tema eller accentfärg i ett svep
- Vi kan använda Saira-typsnittet (redan inbäddat i assets) också i UI:t, inte bara i story-overlays som idag

**Flödet efter migrering:**
```
dpt-web (CLI) → astro build → dist/index.html ← pywebview laddar
```
Användaren ser fortfarande ett native macOS-fönster, men bakom kulisserna är det ett välstrukturerat Astro-projekt.

**Implikation för komponenter:** Om Designer identifierar ett nytt mönster (t.ex. ett "Tool runner"-kort med progress-indikation), behöver det inte passa in i den gamla CSS-strukturen — vi implementerar det rent i Astro från grunden.

---

## Tekniska constraints (för designer att känna till)

- Fönster: fast 860×860 px, minsize 700×640. Ingen responsivitet behövs utanför det.
- pywebview: native macOS-fönster, WebKit-rendering (Safari-motor). Inga custom fonts från CDN utan att bädda in.
- Typsnitt Saira finns inbäddad i assets/fonts/ — kan användas i UI också (används idag bara i story-overlay).
- Tema (ljust/mörkt) växlas runtime via `html[data-theme="dark"]`.
- Alla backend-anrop är `window.pywebview.api.*` — synkrona svar från Python. Inga REST-endpoints.

---

## Bifogade skärmdumpar (bifoga alla i Designer-sessionen)

Alla skärmdumpar är tagna live ur appen i ljust läge. Bifoga dem i ordning:

| # | Steg | Vad syns |
|---|------|----------|
| 1 | **Urval** | Tomt galleri, "Bläddra på disk"-kort |
| 2 | **Snabbplock (övre)** | Kort-sektion + Story-knappar (moment/format/tema) |
| 3 | **Snabbplock (nedre)** | Match-sammanfattning, Bild-picker, Skapa Story-knapp |
| 4 | **Förbered** | Matcher-kort (dropdown + fält), Källa & match, Laguppställning |
| 5 | **Gallra** | Urval + Match-kort, checkboxar, disclosure "Avancerat" expanderad |
| 6 | **Leverera** | Export + Efterbehandling, Räta upp, Tröjnummer & namn, Avancerat |
| 7 | **Publicera** | Två tool-cards (Instagram-urval, Bildsvepet) + Alternativ |
| 8 | **Träna (övre)** | Aktiv modell, Lär av match-sektion med sökvägar |
| 9 | **Träna (nedre)** | Tränings-rot, Granskning-tools (Granska osäkra, Jämför par, Histogram…) |
| 10 | **Logg** | Tom terminal-konsol, Kopiera-knapp |

Designens faktiska känsla: subtle Mac-native, orange accent, minimalistisk.
Notera hur Gallra (steget som blir Tool) idag är ett enkelt formulär — det är det som ska omtänkas.
