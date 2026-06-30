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

// Urval (Gallra producerar, Leverera konsumerar). Muteras lokalt i mock-läge.
let MOCK_URVAL = [
  { id: 'u_rosengard', kalla: '/Volumes/NIKON Z 8/DCIM/277Z8_01', kamera: 'NIKON Z 8',
    bilder: 38, status: 'gallrad', skapad: '2026-06-30 09:12',
    match_id: 'a1b2c3d4e5f6', lag_hemma: 'Malmö FF', lag_borta: 'Kristianstads DFF' },
  { id: 'u_handboll', kalla: '/Volumes/NIKON/DCIM/308D5_02', kamera: 'NIKON D5',
    bilder: 24, status: 'gallrad', skapad: '2026-06-29 20:05',
    match_id: null, lag_hemma: null, lag_borta: null },
  { id: 'u_levererad', kalla: '/Volumes/NIKON/DCIM/_leverans_CEV', kamera: 'NIKON Z 8',
    bilder: 30, status: 'levererad', skapad: '2026-06-28 21:40',
    match_id: 'fb9679db75f5', lag_hemma: 'FC Rosengård', lag_borta: 'Eskilstuna United' },
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

export async function sparaTavling(tavling) {
  const api = brygga()
  if (api) return api.spara_tavling(tavling)
  return wait({ ok: true, id: tavling.id || 'ny' })
}

export async function raderaLag(id) {
  const api = brygga()
  if (api) return api.radera_lag(id)
  return wait({ ok: true })
}

export async function raderaTavling(id) {
  const api = brygga()
  if (api) return api.radera_tavling(id)
  return wait({ ok: true })
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

let _aktivMock = null

export async function sattAktivMatch(id) {
  const api = brygga()
  if (api) return api.satt_aktiv_match(id)
  _aktivMock = await hamtaMatch(id)
  return wait({ ok: true, match: _aktivMock })
}

export async function aktivMatch() {
  const api = brygga()
  if (api) return api.aktiv_match()
  return wait(_aktivMock)
}

export async function startaCull(config) {
  const api = brygga()
  if (api) return api.starta_cull(config)
  return wait({
    ok: true, urval_id: 'mock', jobb_id: 'mock',
    meddelande: 'Cull-jobb skapat (mock). Gallringsmotorn körs i ML-miljö.',
  })
}

export async function listaUrval(status = null) {
  const api = brygga()
  if (api) return api.lista_urval(status)
  const lista = status ? MOCK_URVAL.filter((u) => u.status === status) : MOCK_URVAL
  return wait(structuredClone(lista))
}

export async function levereraUrval(urvalId, config = {}) {
  const api = brygga()
  if (api) return api.leverera_urval(urvalId, config)
  const u = MOCK_URVAL.find((x) => x.id === urvalId)
  if (!u) return wait({ ok: false, fel: 'Okänt urval.' })
  u.status = 'levererad'
  return wait({ ok: true, status: 'levererad', skrivna: u.bilder, ratade: 0 })
}

export async function genereraBildsvep(matchinfo, sport = '', hemmaFarg = '') {
  const api = brygga()
  if (api) return api.generera_bildsvep(matchinfo, sport, hemmaFarg)
  return wait({
    ok: true,
    referat: 'Malmö FF tog kommandot tidigt och Nellie Lilja sköt in 1–0 innan Izzy D’Aquila ökade på till 2–0 före paus.',
    bildsvep:
      '⚽ BILDSVEPET\n\n' + (matchinfo || 'Hemma–Borta 0–0') +
      ' · OBOS Damallsvenskan · Eleda Stadion\n\n📸 Fler bilder → www.dalecarliaphoto.se/sport\n\n' +
      'Malmö FF tog kommandot tidigt och Nellie Lilja sköt in 1–0 innan Izzy D’Aquila ökade på till 2–0 före paus.\n\n' +
      '#MalmöFF #Damallsvenskan #sportfoto #fotboll #Bildsvepet\n\n' +
      '@malmo_ff @?motstandare @obosdamallsvenskan @svenskfotboll @nikonsverige',
  })
}

export async function skapaStory(config) {
  const api = brygga()
  if (api) return api.skapa_story(config)
  if (!config.moment) return wait({ ok: false, fel: 'Välj ett moment.' })
  return wait({ ok: true, meddelande: `Story-val sparat: ${config.moment} · ${config.tema} · ${config.format} (mock).` })
}

// Innehåll (CMS → Astro-export). Muteras lokalt i mock-läge.
let MOCK_INNEHALL = [
  { id: 'i_match1', typ: 'match', status: 'avslutad', publicerad: true,
    export_path: '/sajt/src/content/match/malmo-ff-kristianstads-dff.md',
    frontmatter: { titel: 'Malmö FF – Kristianstads DFF', resultat: '6-0' } },
]

function mockMd(data) {
  const fm = ['---', `typ: ${data.typ || 'match'}`, `titel: "${data.titel || ''}"`]
  if (data.datum) fm.push(`datum: ${data.datum}`)
  if (data.resultat) fm.push(`resultat: "${data.resultat}"`)
  if (data.hero) fm.push(`hero: ${data.hero}`)
  if (data.pixieset) fm.push(`pixieset: ${data.pixieset}`)
  const mal = (typeof data.malskyttar === 'string'
    ? data.malskyttar.split(',').map((s) => s.trim()).filter(Boolean)
    : data.malskyttar) || []
  if (mal.length) { fm.push('malskyttar:'); mal.forEach((m) => fm.push(`  - ${m}`)) }
  fm.push('---', '')
  const figs = (data.figurer || []).filter((f) => f.bild)
    .map((f) => `![${f.alt || ''}](${f.bild})` + (f.bildtext ? `\n*${f.bildtext}*` : ''))
  return fm.join('\n') + '\n' + [data.body || '', figs.join('\n\n')].filter(Boolean).join('\n\n') + '\n'
}

const slug = (t) => (t || 'innehall').toLowerCase()
  .replace(/å|ä/g, 'a').replace(/ö/g, 'o').replace(/&/g, 'och')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'innehall'

export async function listaInnehall(typ = null) {
  const api = brygga()
  if (api) return api.lista_innehall(typ)
  const l = typ ? MOCK_INNEHALL.filter((i) => i.typ === typ) : MOCK_INNEHALL
  return wait(structuredClone(l))
}

export async function forhandsgranskaInnehall(data) {
  const api = brygga()
  if (api) return api.forhandsgranska_innehall(data)
  return wait({ slug: slug(data.titel), md: mockMd(data) })
}

export async function sparaInnehall(data) {
  const api = brygga()
  if (api) return api.spara_innehall(data)
  return wait({ ok: true, id: data.id || 'i_ny' })
}

export async function exporteraInnehall(data, exportDir) {
  const api = brygga()
  if (api) return api.exportera_innehall(data, exportDir)
  if (!exportDir) return wait({ ok: false, fel: 'Ange en export-katalog.' })
  return wait({ ok: true, id: data.id || 'i_ny', path: `${exportDir}/${slug(data.titel)}.md` })
}

export async function raderaInnehall(id) {
  const api = brygga()
  if (api) return api.radera_innehall(id)
  return wait({ ok: true })
}

// Modeller (din smak / arkiv / hybrid — modell-växlaren). Muteras lokalt i mock.
let MOCK_MODELLER = [
  { id: 'm_dinsmak', typ: 'din_smak', aktiv: true, pkl_path: '~/.config/dpt2/modeller/din_smak.pkl',
    n_uppdrag: 18, n_valda: 642, sparad: '2026-06-29 22:10' },
  { id: 'm_arkiv', typ: 'arkiv', aktiv: false, pkl_path: '~/.config/dpt2/modeller/arkiv.pkl',
    n_uppdrag: 51, n_valda: 2104, sparad: '2026-05-12 18:00' },
  { id: 'm_hybrid', typ: 'hybrid', aktiv: false, pkl_path: '~/.config/dpt2/modeller/hybrid.pkl',
    n_uppdrag: 69, n_valda: 2746, sparad: '2026-06-20 09:30' },
]

export async function listaModeller() {
  const api = brygga()
  if (api) return api.lista_modeller()
  return wait(structuredClone(MOCK_MODELLER))
}

export async function sattAktivModell(id) {
  const api = brygga()
  if (api) return api.satt_aktiv_modell(id)
  MOCK_MODELLER = MOCK_MODELLER.map((m) => ({ ...m, aktiv: m.id === id }))
  return wait({ ok: true, aktiv: MOCK_MODELLER.find((m) => m.id === id) })
}

export async function startaOmraknaArkiv(root) {
  const api = brygga()
  if (api) return api.starta_omrakna_arkiv(root)
  if (!root) return wait({ ok: false, fel: 'Ange en arkiv-katalog.' })
  return wait({ ok: true, resultat: { uppdrag: 3, bilder: 412, valda: 71 },
    events: [{ typ: 'klar', resultat: { uppdrag: 3, bilder: 412, valda: 71 } }] })
}

export async function startaTraning(config = {}) {
  const api = brygga()
  if (api) return api.starta_traning(config)
  return wait({ ok: true, resultat: { n_uppdrag: 3, n_valda: 71 },
    events: [{ typ: 'klar', resultat: { n_uppdrag: 3, n_valda: 71 } }] })
}

// Logg — worker-events (strukturerad IPC). Buffras i appen; mock genererar ström.
let MOCK_LOGG = []

function mockDemoEvents(steg) {
  const ev = [{ typ: 'start', jobb: 'demo' }]
  for (let i = 1; i <= steg; i++) {
    ev.push({ typ: 'progress', andel: +(i / steg).toFixed(3), text: `Steg ${i}/${steg}` })
    ev.push({ typ: 'logg', niva: 'info', text: `bearbetar enhet ${i}` })
  }
  ev.push({ typ: 'logg', niva: 'ok', text: 'demo färdig' })
  ev.push({ typ: 'klar', resultat: { steg } })
  return ev
}

export async function hamtaLogg() {
  const api = brygga()
  if (api) return api.hamta_logg()
  return wait(structuredClone(MOCK_LOGG))
}

export async function rensaLogg() {
  const api = brygga()
  if (api) return api.rensa_logg()
  MOCK_LOGG = []
  return wait({ ok: true })
}

export async function korDemoJobb(steg = 5) {
  const api = brygga()
  if (api) return api.kor_demo_jobb(steg)
  const events = mockDemoEvents(steg)
  MOCK_LOGG = [...MOCK_LOGG, ...events]
  return wait({ ok: true, events })
}

export const ARMOCK = !brygga()
