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
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan',
    hemfarg: '#8b1f3a', bortafarg: '#1d2a6b', trupp_n: 3,
  },
  {
    id: 'a1b2c3d4e5f6', datum: '2026-06-27', tid: '14:00',
    arena: 'Eleda Stadion', status: 'avslutad', resultat: '6-0',
    sport: 'fotboll', lag_hemma: 'Malmö FF', lag_borta: 'Kristianstads DFF',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan',
    hemfarg: '#8fb7de', bortafarg: '#C0392B', trupp_n: 0,
  },
  {
    id: 'c0ffee001122', datum: '2026-09-03', tid: '19:00',
    arena: 'Baltiska Hallen', status: 'kommande', resultat: '',
    sport: 'handboll', lag_hemma: 'HK Malmö', lag_borta: 'IK Sävehof',
    liga: 'Handbollsligan', tavling_id: 'handbollsligan',
    hemfarg: '#0a2342', bortafarg: '#1E824C', trupp_n: 0,
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
  { id: 'fc-rosengard', namn: 'FC Rosengård', kind: 'team', instagram: '@fcrosengard', hemsida: 'fcrosengard.se', logga: null, stall_hemma: '#8b1f3a', stall_borta: '#ffffff', stall_tredje: '#16181c', profilfarg: '', klubb: '', trupp_n: 22, trupp_kalla: 'från hemsida' },
  { id: 'eskilstuna-united', namn: 'Eskilstuna United', kind: 'team', instagram: '@eskilstunaunited', hemsida: 'eskilstunaunited.se', logga: null, stall_hemma: '#1d2a6b', stall_borta: '#ffd200', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 0, trupp_kalla: '' },
  { id: 'malmo-ff', namn: 'Malmö FF', kind: 'team', instagram: '@malmoff_dam', hemsida: 'malmoff.se', logga: null, stall_hemma: '#8fb7de', stall_borta: '#ffffff', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 20, trupp_kalla: 'CSV' },
  { id: 'hk-malmo', namn: 'HK Malmö', kind: 'team', instagram: '@hkmhandboll', hemsida: '', logga: null, stall_hemma: '#0a2342', stall_borta: '#e23', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 0, trupp_kalla: '' },
  { id: 'rebecca-peterson', namn: 'Rebecca Peterson', kind: 'individ', instagram: '@rebeccapeterson', hemsida: '', logga: null, stall_hemma: '', stall_borta: '', stall_tredje: '', profilfarg: '#2F7CB0', klubb: 'Sverige' },
]

const MOCK_TAVLINGAR = [
  { id: 'obos-damallsvenskan', namn: 'OBOS Damallsvenskan', typ: 'liga', sport: 'fotboll', fran: 'apr–okt 2026', till: '', ort: 'Sverige', arena: '', hemsida: 'svenskelitfotboll.se', logga: null, kalender: 0 },
  { id: 'handbollsligan', namn: 'Handbollsligan', typ: 'liga', sport: 'handboll', fran: 'sep 2026 – apr 2027', till: '', ort: 'Sverige', arena: '', hemsida: '', logga: null, kalender: 0 },
]

// Mock: vilka lag som deltar i en tävling (tavling_lag). I appen kommer detta
// ur store.lista_lag_for_tavling; här räcker en enkel sport-baserad filtrering.
const MOCK_TAVLING_LAG = {
  'obos-damallsvenskan': ['fc-rosengard', 'eskilstuna-united', 'malmo-ff'],
  'handbollsligan': ['hk-malmo'],
}

// Fotojobb (Google Calendar via deployade tjänsten). Formen matchar tjänstens
// jobb-modell (INTEGRATION.md). Muteras lokalt i mock-läge.
let MOCK_FOTOJOBB = [
  { id: 'fj1', title: 'Match – Malmö / Kristianstad', start_at: '2026-07-19T14:00:00', end_at: '2026-07-19T16:30:00', all_day: false, location: 'Malmö IP', description: '', category: 'Sport', status: 'confirmed', google_event_id: 'g1', source: 'dpt' },
  { id: 'fj2', title: 'Möte (skapad i Google)', start_at: '2026-07-15T09:00:00', end_at: '2026-07-15T09:30:00', all_day: false, location: '', description: '', category: null, status: 'confirmed', google_event_id: 'g2', source: 'google' },
  { id: 'fj3', title: 'Landskap – soluppgång vid Grenen', start_at: '2026-07-12T04:30:00', end_at: '2026-07-12T06:00:00', all_day: false, location: 'Grenen', description: '', category: 'Landskap', status: 'confirmed', google_event_id: null, source: 'dpt' },
  { id: 'fj4', title: 'Mässa & workshop', start_at: '2026-06-29', end_at: '2026-07-03', all_day: true, location: '', description: '', category: 'Övrigt', status: 'confirmed', google_event_id: 'g4', source: 'dpt' },
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

export async function listaLagForTavling(tavlingId) {
  const api = brygga()
  if (api) return api.lista_lag_for_tavling(tavlingId)
  const ids = MOCK_TAVLING_LAG[tavlingId] || []
  return wait(structuredClone(MOCK_LAG.filter((l) => ids.includes(l.id))))
}

export async function listaTavlingar() {
  const api = brygga()
  if (api) return api.lista_tavlingar()
  return wait(structuredClone(MOCK_TAVLINGAR))
}

// ── Fotojobb / Google Calendar ───────────────────────────────────────────────
export async function kalenderStatus() {
  const api = brygga()
  if (api) return api.kalender_status()
  return wait({ har_nyckel: false, ansluten: false, bas_url: 'https://dpt-calendar-sync.stig-johansson.workers.dev' })
}

export async function listaFotojobb() {
  const api = brygga()
  if (api) return api.lista_fotojobb()
  return wait(structuredClone(MOCK_FOTOJOBB))
}

export async function sparaFotojobb(jobb) {
  const api = brygga()
  if (api) return api.spara_fotojobb(jobb)
  if (jobb.id) {
    MOCK_FOTOJOBB = MOCK_FOTOJOBB.map((j) => (j.id === jobb.id ? { ...j, ...jobb } : j))
  } else {
    MOCK_FOTOJOBB = [...MOCK_FOTOJOBB, { ...jobb, id: 'fj' + Date.now(), google_event_id: null, source: 'dpt', status: 'confirmed' }]
  }
  return wait({ ok: true })
}

export async function raderaFotojobb(id) {
  const api = brygga()
  if (api) return api.radera_fotojobb(id)
  MOCK_FOTOJOBB = MOCK_FOTOJOBB.filter((j) => j.id !== id)
  return wait({ ok: true })
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

export async function lasLagTrupp(lagId, kalla, arg = '') {
  const api = brygga()
  if (api) return api.las_lag_trupp(lagId, kalla, arg)
  const etikett = { url: 'från hemsida', csv: 'CSV', bild: 'bild', pdf: 'PDF' }[kalla] || kalla
  const roster = Array.from({ length: 5 }, (_, i) => ({
    id: `mock-${lagId}-${i}`, nr: String(i + 1), namn: `Spelare ${i + 1}`, position: '' }))
  return wait({ ok: true, antal: roster.length, trupp_kalla: etikett, roster })
}

export async function hamtaLagTrupp(lagId) {
  const api = brygga()
  if (api) return api.hamta_lag_trupp(lagId)
  return wait(Array.from({ length: 3 }, (_, i) => ({
    id: `mock-${lagId}-${i}`, nr: String(i + 1), namn: `Spelare ${i + 1}`, position: '' })))
}

export async function sparaSpelare(lagId, spelare) {
  const api = brygga()
  if (api) return api.spara_spelare(lagId, spelare)
  if (!spelare?.namn?.trim()) return wait({ ok: false, id: null })
  return wait({ ok: true, id: spelare.id || 'sp_' + Date.now() })
}

export async function raderaSpelare(spelareId) {
  const api = brygga()
  if (api) return api.radera_spelare(spelareId)
  return wait({ ok: true })
}

export async function lasUttagFil(matchId, filsokvag, sida) {
  const api = brygga()
  if (api) return api.las_uttag_fil(matchId, filsokvag, sida)
  // Mock: startelvan ERSÄTTER sidans tidigare uttag (ingen bänk längre).
  const full = MOCK_FULL[matchId] || { ...MOCK_MATCHER.find((m) => m.id === matchId), spelare: [] }
  const nya = Array.from({ length: 11 }, (_, i) => ({
    nr: String(i + 1), namn: `Spelare ${i + 1}`, lag: sida, handle: '', info: '', start: true,
  }))
  const ovrigaSidan = (full.spelare || []).filter((p) => p.lag !== sida)
  return wait({ ok: true, match: { ...full, spelare: [...ovrigaSidan, ...nya] } })
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

export async function lasLineup(matchId, filsokvag) {
  const api = brygga()
  if (api) return api.las_lineup_fil(matchId, filsokvag)
  return hamtaTrupp(matchId)   // mock: samma sammanslagning
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
  return wait({ ok: true, urval_id: 'mock', jobb_id: 'mock',
    meddelande: 'Cull-jobb skapat.' })
}

export async function startaGallring(urvalId) {
  const api = brygga()
  if (api) return api.starta_gallring(urvalId)
  return wait({ ok: true,
    resultat: { totalt: 1184, behall: 118, modell: 'din_smak' },
    meddelande: 'Gallring klar: behåller 118 av 1184 (din_smak).' })
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

export async function startaNummer(urvalId) {
  const api = brygga()
  if (api) return api.starta_nummer(urvalId)
  const u = MOCK_URVAL.find((x) => x.id === urvalId)
  const n = u ? u.bilder : 0
  return wait({ ok: true, resultat: { totalt: n, skrivna: Math.round(n * 0.8), luckor: Math.round(n * 0.1) },
    meddelande: `Tröjnummer skrivna på ${Math.round(n * 0.8)} av ${n} bilder.` })
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
  if (!config.foto) return wait({ ok: false, fel: 'Ange ett källfoto.' })
  const prefix = config.format === '4x5' ? 'inlagg' : 'story'
  return wait({ ok: true, path: `~/.config/dpt2/stories/${prefix}_${config.moment.toLowerCase()}.jpg`,
    meddelande: `Story renderad: ${config.moment} · ${config.tema} · ${config.format}.` })
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

// Native filväljare — i appen via pywebview-dialog; i webbläsaren en prompt.
function _promptPath(titel) {
  const p = (typeof window !== 'undefined' && window.prompt)
    ? window.prompt(`${titel} (klistra in sökväg):`, '') : null
  return { ok: !!p, path: p || null }
}

export async function valjMapp(titel = 'Välj mapp') {
  const api = brygga()
  if (api) return api.valj_mapp(titel)
  return wait(_promptPath(titel))
}

export async function valjFil(titel = 'Välj fil', filter = null) {
  const api = brygga()
  if (api) return api.valj_fil(titel, filter)
  return wait(_promptPath(titel))
}

// ── Publicera → Live (snabb story) ───────────────────────────────────────────
export async function oppnaILightroom(sokvag = '') {
  const api = brygga()
  if (api) return api.oppna_i_lightroom(sokvag)
  return wait({ ok: true, app: 'Adobe Lightroom Classic (mock)' })
}

export async function publiceraLiveStory(config) {
  const api = brygga()
  if (api) return api.publicera_live_story(config)
  if (!config?.moment) return wait({ ok: false, fel: 'Välj ett moment.' })
  if (!config?.foto) return wait({ ok: false, fel: 'Välj en bild i steg 2.' })
  return wait({ ok: true, path: `${config.ut_mapp || '~/Dropbox/DPT/Live'}/story_${config.moment.toLowerCase()}.jpg`,
    publicerad: true, url: 'https://exempel/story/1' })
}

// ── Publicera till SoMe ──────────────────────────────────────────────────────
function _strippaFb(text) {
  return (text || '').replace(/[#@][\wåäöÅÄÖ]+/g, '').replace(/[ \t]{2,}/g, ' ')
    .replace(/ *\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
}
function _mockPlanera({ bilder = [], caption = '', mal = {} }) {
  if (!bilder.length) return { ok: false, fel: 'Paketet saknar bilder.' }
  if (!(mal.story || mal.ig_inlagg || mal.fb)) return { ok: false, fel: 'Välj minst ett mål (story/ig_inlagg/fb).' }
  const poster = [], varningar = []
  if (mal.story) bilder.forEach((b, i) => poster.push({ kanal: 'instagram', form: 'story', bilder: [b], text: caption, del: i + 1, av: bilder.length }))
  if (mal.ig_inlagg) {
    const bitar = []; for (let i = 0; i < bilder.length; i += 10) bitar.push(bilder.slice(i, i + 10))
    if (bitar.length > 1) varningar.push(`${bilder.length} bilder till IG-inlägg → ${bitar.length} poster (Graph API tar max 10/karusell).`)
    bitar.forEach((bit, i) => poster.push({ kanal: 'instagram', form: 'inlägg', bilder: bit, text: caption, del: i + 1, av: bitar.length }))
  }
  if (mal.fb) {
    const fb = bilder.slice(0, 4)
    if (bilder.length > 4) varningar.push(`${bilder.length} bilder till FB → kapat till 4 (FB-sidans multi-photo-gräns).`)
    poster.push({ kanal: 'facebook', form: 'inlägg', bilder: fb, text: _strippaFb(caption), del: 1, av: 1 })
  }
  return { ok: true, poster, varningar }
}

export async function listaSomeBilder(mapp) {
  const api = brygga()
  if (api) return api.lista_some_bilder(mapp)
  return wait(Array.from({ length: 15 }, (_, i) => `bild_${String(i + 1).padStart(2, '0')}.jpg`))
}
export async function publiceraForhandsvisa(config) {
  const api = brygga()
  if (api) return api.publicera_forhandsvisa(config)
  return wait(_mockPlanera(config || {}))
}
export async function publiceraTillSoMe(config) {
  const api = brygga()
  if (api) return api.publicera_till_some(config)
  const plan = _mockPlanera(config || {})
  if (!plan.ok) return wait(plan)
  return wait({ ok: true, sparade: plan.poster.length, varningar: plan.varningar,
    resultat: plan.poster.map((p, i) => ({ ...p, status: 'postad', url: `https://exempel/post/${i + 1}` })) })
}

// pywebview injicerar window.pywebview.api ASYNKRONT. VIKTIGT: api-OBJEKTET dyker
// upp innan alla METODER är påkopplade — så vi måste vänta tills en känd metod
// faktiskt är en funktion, annars kastar första panelens bridge-anrop (t.ex.
// Fotojobb.lista_fotojobb) och vyn blir tom tills panelen remountas.
const bryggaKlar = () => {
  const a = brygga()
  return !!(a && typeof a.lista_fotojobb === 'function')
}

export function vantaPaBrygga(timeout = 6000) {
  return new Promise((resolve) => {
    if (bryggaKlar()) return resolve(true)
    let klar = false
    const go = (v) => { if (!klar) { klar = true; resolve(v) } }
    const kolla = () => (bryggaKlar() ? (go(true), true) : false)
    if (typeof window !== 'undefined') {
      window.addEventListener('pywebviewready', kolla)
    }
    const t0 = Date.now()
    const iv = setInterval(() => {
      if (kolla()) clearInterval(iv)
      else if (Date.now() - t0 > timeout) { clearInterval(iv); go(false) }
    }, 50)
  })
}

export const erMock = () => !brygga()
