// Brygga mot Python-datalagret. I appen finns window.pywebview.api (metoderna
// speglar dpt2.data.store). I webbläsaren (Vite-dev) saknas den → mockdata, så
// panelerna kan utvecklas och verifieras fristående.

const brygga = () =>
  (typeof window !== 'undefined' && window.pywebview && window.pywebview.api) || null

// ── Mockdata (formen matchar store.lista_matcher / store.hamta_match) ────────
const MOCK_MATCHER = [
  {
    id: 'fb9679db75f5', datum: '2026-08-15', tid: '15:00',
    arena: 'Malmö Idrottsplats', status: 'kommande', resultat: '',
    sport: 'fotboll', lag_hemma: 'FC Rosengård', lag_borta: 'Eskilstuna United',
    liga: 'OBOS Damallsvenskan',
  },
  {
    id: 'a1b2c3d4e5f6', datum: '2026-06-27', tid: '14:00',
    arena: 'Eleda Stadion', status: 'avslutad', resultat: '6-0',
    sport: 'fotboll', lag_hemma: 'Malmö FF', lag_borta: 'Kristianstads DFF',
    liga: 'OBOS Damallsvenskan',
  },
  {
    id: 'c0ffee001122', datum: '2026-09-03', tid: '19:00',
    arena: 'Baltiska Hallen', status: 'kommande', resultat: '',
    sport: 'handboll', lag_hemma: 'HK Malmö', lag_borta: 'IK Sävehof',
    liga: 'Handbollsligan',
  },
]

const MOCK_FULL = {
  fb9679db75f5: {
    ...MOCK_MATCHER[0],
    halvtid: '', malskyttar: '', galleri: '', omslag: '',
    spelare: [
      { nr: '1', namn: 'Moa Edrud', lag: 'hemma', handle: '', info: 'Målvakt, Sweden', start: false },
      { nr: '6', namn: 'Ria Öling', lag: 'hemma', handle: '@riaoling', info: 'Mittfältare, Finland', start: true },
      { nr: '9', namn: 'Loreta Kullashi', lag: 'borta', handle: '', info: 'Forward, Sweden', start: true },
    ],
  },
}

const MOCK_LAG = [
  { id: 'fc-rosengard', namn: 'FC Rosengård', instagram: '@fcrosengard', hemsida: 'fcrosengard.se', logga: null, stall_hemma: '#8b1f3a', stall_borta: '#ffffff', stall_tredje: '#16181c' },
  { id: 'eskilstuna-united', namn: 'Eskilstuna United', instagram: '@eskilstunaunited', hemsida: 'eskilstunaunited.se', logga: null, stall_hemma: '#1d2a6b', stall_borta: '#ffd200', stall_tredje: '' },
  { id: 'malmo-ff', namn: 'Malmö FF', instagram: '@malmoff_dam', hemsida: 'malmoff.se', logga: null, stall_hemma: '#8fb7de', stall_borta: '#ffffff', stall_tredje: '' },
  { id: 'hk-malmo', namn: 'HK Malmö', instagram: '@hkmhandboll', hemsida: '', logga: null, stall_hemma: '#0a2342', stall_borta: '#e23', stall_tredje: '' },
]

const MOCK_TAVLINGAR = [
  { id: 'obos-damallsvenskan', namn: 'OBOS Damallsvenskan', typ: 'liga', sport: 'fotboll', ort: '', arena: '', kalender: 0 },
  { id: 'handbollsligan', namn: 'Handbollsligan', typ: 'liga', sport: 'handboll', ort: '', arena: '', kalender: 0 },
]

const wait = (v) => new Promise((r) => setTimeout(() => r(v), 60))

export async function listaMatcher() {
  const api = brygga()
  if (api) return api.lista_matcher()
  return wait(structuredClone(MOCK_MATCHER))
}

export async function hamtaMatch(id) {
  const api = brygga()
  if (api) return api.hamta_match(id)
  return wait(structuredClone(MOCK_FULL[id] || { ...MOCK_MATCHER.find((m) => m.id === id), spelare: [] }))
}

export async function sparaMatch(match) {
  const api = brygga()
  if (api) return api.spara_match(match)
  return wait({ ok: true, id: match.id || 'ny' })
}

export async function listaLag() {
  const api = brygga()
  if (api) return api.lista_lag()
  return wait(structuredClone(MOCK_LAG))
}

export async function listaTavlingar() {
  const api = brygga()
  if (api) return api.lista_tavlingar()
  return wait(structuredClone(MOCK_TAVLINGAR))
}

export async function sparaLag(lag) {
  const api = brygga()
  if (api) return api.spara_lag(lag)
  return wait({ ok: true, id: lag.id || 'nytt' })
}

export async function hamtaTrupp(matchId) {
  const api = brygga()
  if (api) return api.hamta_trupp(matchId)
  // Mock: returnera matchen med ett par "hämtade" spelare ihopslagna.
  const full = MOCK_FULL[matchId] || {
    ...MOCK_MATCHER.find((m) => m.id === matchId), spelare: [],
  }
  const nya = [
    { nr: '7', namn: 'Thea Sørbo', lag: 'hemma', handle: '@theasoerbo', info: 'Mittfältare, Norway', start: false },
    { nr: '11', namn: 'Molly Johansson', lag: 'hemma', handle: '', info: 'Back, Sweden', start: false },
  ]
  const fanns = new Set((full.spelare || []).map((p) => p.nr + p.lag))
  const merge = [...(full.spelare || []), ...nya.filter((p) => !fanns.has(p.nr + p.lag))]
  return wait({ ok: true, match: { ...full, spelare: merge } })
}

export const ARMOCK = !brygga()
