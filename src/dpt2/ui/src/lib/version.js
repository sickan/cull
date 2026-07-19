// V2-01 — versionsvisning.
//
// Konstanterna injiceras av vite.config.js vid bygget: __VERSION__ läses ur
// src/dpt2/__init__.py, __BUILD_NR__/__COMMIT__ ur git. Fallbacken '?' gäller
// när UI:t körs utan vite-define (t.ex. enhetstester).
//
// Poängen med bokstaveringen: när Stig läser upp versionen eller jämför mot
// telefonen ska "två punkt noll" inte kunna förväxlas med något annat — siffran
// ensam är för lätt att läsa fel.

export const version = typeof __VERSION__ !== 'undefined' ? __VERSION__ : '?'
export const buildNr = typeof __BUILD_NR__ !== 'undefined' ? __BUILD_NR__ : '?'
export const commit = typeof __COMMIT__ !== 'undefined' ? __COMMIT__ : '?'

const ORD = ['noll', 'ett', 'två', 'tre', 'fyra', 'fem', 'sex', 'sju', 'åtta',
             'nio', 'tio', 'elva', 'tolv']

function ordFor(tal) {
  const n = Number(tal)
  if (!Number.isInteger(n) || n < 0) return String(tal)
  if (n < ORD.length) return ORD[n]
  return String(tal).split('').map(d => ORD[Number(d)]).join(' ')
}

/**
 * "2.0.0" → "två punkt noll". Bara major.minor bokstaveras — patch-siffran är
 * brus i en talad version. Okänd version ('?') passerar rakt igenom.
 */
export function bokstaverad(v = version) {
  if (!v || v === '?') return v || '?'
  const delar = String(v).split('.').slice(0, 2)
  return delar.map(ordFor).join(' punkt ')
}
