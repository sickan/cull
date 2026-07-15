// Härleder landslags-flagga ur lagets NAMN (namn = land → flagga).
// Flaggorna är flag-icons (MIT), vendrade i ../assets/flags/1x1 — se
// ../assets/flags/HERKOMST.md för licens/upphovsrätt.

// Bundlade flagg-URL:er keyade på ISO2 ('se' → url). Vite ersätter globen vid
// bygge och serverar URL:erna samma-origin (funkar i WKWebView, till skillnad
// från file://).
const FLAGG_URL = {}
{
  const mods = import.meta.glob('../assets/flags/1x1/*.svg', {
    eager: true, query: '?url', import: 'default',
  })
  for (const [sokvag, url] of Object.entries(mods)) {
    const iso = sokvag.split('/').pop().replace('.svg', '') // 'se', 'gb-eng'
    FLAGG_URL[iso] = url
  }
}

const norm = (s) => String(s || '').trim().toLowerCase()

// Namn Intl.DisplayNames inte ger oss rakt av: brittiska landslag (egna
// flaggor i flag-icons) + vanliga vardagsnamn.
const ALIAS = {
  england: 'gb-eng', wales: 'gb-wls', skottland: 'gb-sct', nordirland: 'gb-nir',
  storbritannien: 'gb', 'united kingdom': 'gb',
  usa: 'us', 'förenta staterna': 'us', 'united states': 'us',
  ryssland: 'ru', tjeckien: 'cz', sydkorea: 'kr', nordkorea: 'kp',
}

// Svenskt landsnamn (gemener) → ISO2. Byggs lazily via Intl.DisplayNames så vi
// slipper handunderhålla ~250 landsnamn.
let NAMN_ISO = null
function bygg() {
  NAMN_ISO = { ...ALIAS }
  let dn
  try { dn = new Intl.DisplayNames(['sv'], { type: 'region' }) } catch { dn = null }
  if (!dn) return // Intl.DisplayNames saknas → bara ALIAS gäller
  for (const iso of Object.keys(FLAGG_URL)) {
    // Bara riktiga 2-bokstavs landskoder. flag-icons har även organisations-
    // flaggor (arab, asean, cefta…) och subdivisioner (gb-eng) — dn.of() kastar
    // RangeError på dem, så de filtreras bort här (nås vid behov via ALIAS).
    if (!/^[a-z]{2}$/.test(iso)) continue
    let namn
    try { namn = dn.of(iso.toUpperCase()) } catch { continue }
    if (namn && norm(namn) !== iso) NAMN_ISO[norm(namn)] = iso
  }
}

// ISO-kod för ett landsnamn (namn = land), annars ''.
export function isoForLand(namn) {
  if (!NAMN_ISO) bygg()
  return NAMN_ISO[norm(namn)] || ''
}

// Bundlad flagg-URL för ett landsnamn, annars '' (inte ett land vi känner).
export function flaggaForLand(namn) {
  const iso = isoForLand(namn)
  return iso ? FLAGG_URL[iso] || '' : ''
}
