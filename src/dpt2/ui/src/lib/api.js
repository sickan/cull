// Brygga mot Python-datalagret. I appen finns window.pywebview.api (metoderna
// speglar dpt2.data.store). I webbläsaren (Vite-dev) saknas den → mockdata, så
// panelerna kan utvecklas och verifieras fristående.

import { SEED_KALENDRAR, SEED_PRIVATA, kureradFarg } from './privat.js'

const brygga = () =>
  (typeof window !== 'undefined' && window.pywebview && window.pywebview.api) || null

// ── Mockdata (formen matchar store.lista_matcher / store.hamta_match) ────────
const MOCK_MATCHER = [
  {
    id: 'fb9679db75f5', datum: '2026-08-15', tid: '15:00',
    arena: 'Malmö Idrottsplats', status: 'kommande', resultat: '',
    sport: 'fotboll', lag_hemma: 'FC Rosengård', lag_borta: 'Eskilstuna United',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan', hem_gren: 'dam',
    hemfarg: '#8b1f3a', bortafarg: '#1d2a6b', trupp_n: 3, synk_jobb_id: null,
  },
  {
    id: 'a1b2c3d4e5f6', datum: '2026-06-27', tid: '14:00',
    arena: 'Eleda Stadion', status: 'avslutad', resultat: '6-0',
    sport: 'fotboll', lag_hemma: 'Malmö FF', lag_borta: 'Kristianstads DFF',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan', hem_gren: 'dam',
    hemfarg: '#8fb7de', bortafarg: '#C0392B', trupp_n: 0, synk_jobb_id: 'fj1',
    galleri: 'https://malmoff.pixieset.com/damallsvenskan-27jun/',
    sida_url: 'https://dalecarliaphoto.se/sport/2026-06-27-malmo-ff-kristianstad',
  },
  {
    id: 'c0ffee001122', datum: '2026-09-03', tid: '',   // tid ej fastställd → heldag
    arena: 'Baltiska Hallen', status: 'kommande', resultat: '',
    sport: 'handboll', lag_hemma: 'HK Malmö', lag_borta: 'IK Sävehof',
    liga: 'Handbollsligan', tavling_id: 'handbollsligan', hem_gren: 'herr',
    hemfarg: '#0a2342', bortafarg: '#1E824C', trupp_n: 0,
  },
  {
    id: 'dead00beef00', datum: '2026-07-18', tid: '11:00',
    arena: 'Båstad', status: 'kommande', resultat: '',
    sport: 'tennis', lag_hemma: 'Rebecca Peterson', lag_borta: 'Mirjam Björklund',
    liga: 'Nordea Open', tavling_id: 'nordea-open', hem_gren: '',   // individ utan gren → "ej satt"
    hemfarg: '#2F7CB0', bortafarg: '#C9657F', trupp_n: 0,
  },
  {
    id: 'dead00beef01', datum: '2026-07-17', tid: '13:00',
    arena: 'Båstad', status: 'avslutad', resultat: '2–0',
    sport: 'tennis', lag_hemma: 'Mirjam Björklund', lag_borta: 'Rebecca Peterson',
    liga: 'Nordea Open', tavling_id: 'nordea-open', hem_gren: '',
    hemfarg: '#C9657F', bortafarg: '#2F7CB0', trupp_n: 0,
  },
  {
    // p.5: heldagsevent = "match utan motståndare" i samma datamodell/flöde.
    id: 'event-partille', datum: '2026-07-06', tid: '', event: true,
    arena: 'Göteborg', status: 'kommande', resultat: '',
    sport: 'fotboll', lag_hemma: 'Partille Cup', lag_borta: '',
    liga: 'Heldagsevent', tavling_id: null, hem_gren: 'mixed',
    hemfarg: '#6E8757', bortafarg: '', trupp_n: 0,
  },
  // Säsongsarkiv-demo (matcher.svelte grupperar per kalenderår ur datum — riktig
  // säsongspartitionering + lazy-load per år är backend-arbete som är utanför
  // det här passet, se HANDOFF.md).
  {
    id: 'arkiv2025-01', datum: '2025-10-18', tid: '15:00',
    arena: 'Eleda Stadion', status: 'avslutad', resultat: '2-1',
    sport: 'fotboll', lag_hemma: 'Malmö FF', lag_borta: 'FC Rosengård',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan', hem_gren: 'dam',
    hemfarg: '#8fb7de', bortafarg: '#8b1f3a', trupp_n: 0,
  },
  {
    id: 'arkiv2025-02', datum: '2025-08-02', tid: '16:00',
    arena: '3Arena', status: 'avslutad', resultat: '0-3',
    sport: 'fotboll', lag_hemma: 'Hammarby IF', lag_borta: 'Malmö FF',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan', hem_gren: 'dam',
    hemfarg: '#1E824C', bortafarg: '#8fb7de', trupp_n: 0,
  },
  {
    id: 'arkiv2025-03', datum: '2025-06-14', tid: '13:00',
    arena: 'Kristianstads IP', status: 'avslutad', resultat: '1-1',
    sport: 'fotboll', lag_hemma: 'Kristianstads DFF', lag_borta: 'FC Rosengård',
    liga: 'OBOS Damallsvenskan', tavling_id: 'obos-damallsvenskan', hem_gren: 'dam',
    hemfarg: '#C0392B', bortafarg: '#8b1f3a', trupp_n: 0,
  },
  {
    id: 'arkiv2024-01', datum: '2024-09-21', tid: '14:00',
    arena: 'Baltiska Hallen', status: 'avslutad', resultat: '28-24',
    sport: 'handboll', lag_hemma: 'HK Malmö', lag_borta: 'IK Sävehof',
    liga: 'Handbollsligan', tavling_id: 'handbollsligan', hem_gren: 'herr',
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
  { id: 'fc-rosengard', namn: 'FC Rosengård', kind: 'team', sport: 'fotboll', gren: 'dam', instagram: '@fcrosengard', hemsida: 'fcrosengard.se', logga: null, stall_hemma: '#8b1f3a', stall_borta: '#ffffff', stall_tredje: '#16181c', profilfarg: '', klubb: '', trupp_n: 22, trupp_kalla: 'från hemsida', comps: ['obos-damallsvenskan'] },
  { id: 'eskilstuna-united', namn: 'Eskilstuna United', kind: 'team', sport: 'fotboll', gren: 'dam', instagram: '@eskilstunaunited', hemsida: 'eskilstunaunited.se', logga: null, stall_hemma: '#1d2a6b', stall_borta: '#ffd200', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 0, trupp_kalla: '', comps: ['obos-damallsvenskan'] },
  { id: 'malmo-ff', namn: 'Malmö FF', kind: 'team', sport: 'fotboll', gren: 'dam', instagram: '@malmoff_dam', hemsida: 'malmoff.se', logga: null, stall_hemma: '#8fb7de', stall_borta: '#ffffff', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 20, trupp_kalla: 'CSV', comps: ['obos-damallsvenskan'] },
  { id: 'hk-malmo', namn: 'HK Malmö', kind: 'team', sport: 'handboll', gren: 'herr', instagram: '@hkmhandboll', hemsida: '', logga: null, stall_hemma: '#0a2342', stall_borta: '#e23', stall_tredje: '', profilfarg: '', klubb: '', trupp_n: 0, trupp_kalla: '', comps: ['handbollsligan'] },
  { id: 'rebecca-peterson', namn: 'Rebecca Peterson', kind: 'individ', sport: 'tennis', gren: 'dam', instagram: '@rebeccapeterson', hemsida: '', logga: null, stall_hemma: '', stall_borta: '', stall_tredje: '', profilfarg: '#2F7CB0', klubb: 'Sverige', comps: [] },
  { id: 'mirjam-bjorklund', namn: 'Mirjam Björklund', kind: 'individ', sport: 'tennis', gren: 'dam', instagram: '@mirjambjorklund', hemsida: '', logga: null, stall_hemma: '', stall_borta: '', stall_tredje: '', profilfarg: '#C9657F', klubb: 'Sverige', comps: [] },
]

const MOCK_TAVLINGAR = [
  { id: 'obos-damallsvenskan', namn: 'OBOS Damallsvenskan', typ: 'liga', sport: 'fotboll', gren: 'dam', fran: '2026-04-01', till: '2026-10-31', ort: 'Sverige', arena: '', hemsida: 'svenskelitfotboll.se', logga: null, kalender: 0 },
  { id: 'handbollsligan', namn: 'Handbollsligan', typ: 'liga', sport: 'handboll', gren: 'herr', fran: '2026-09-01', till: '2027-04-30', ort: 'Sverige', arena: '', hemsida: '', logga: null, kalender: 0 },
  { id: 'nordea-open', namn: 'Nordea Open', typ: 'turnering', sport: 'tennis', gren: 'dam', fran: '2026-07-13', till: '2026-07-19', ort: 'Båstad', arena: 'Båstad Tennisstadion', hemsida: 'nordeaopen.se', logga: null, kalender: 0 },
]

// Mock: sportprofiler (statisk fältmodell, speglar dpt2.data.sportprofil).
const MOCK_SPORTPROFILER = {
  fotboll:    { namn: 'Fotboll', res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid', mid_ph: '3–0', mid_moment: 'Halvtid', mid_token: 'halvtid', start_moment: 'Avspark', has_scorers: true, scorers_label: 'Målskyttar', lineup: 'Startelva', lineup_n: '(11)', squad: true, individ: false, md_key: 'halvtid', farg: '#2F7CB0' },
  handboll:   { namn: 'Handboll', res_label: 'Slutresultat', res_ph: '28–24', mid_label: 'Halvtid', mid_ph: '14–11', mid_moment: 'Halvtid', mid_token: 'halvtid', start_moment: 'Avspark', has_scorers: true, scorers_label: 'Målskyttar', lineup: 'Startsju', lineup_n: '(7)', squad: true, individ: false, md_key: 'halvtid', farg: '#C9871F' },
  innebandy:  { namn: 'Innebandy', res_label: 'Slutresultat', res_ph: '4–1', mid_label: 'Periodsiffror', mid_ph: '1–0, 2–1, 1–0', mid_moment: 'Periodpaus', mid_token: 'periodsiffror', start_moment: 'Nedsläpp', has_scorers: true, scorers_label: 'Målskyttar', lineup: 'Femma', lineup_n: '(5)', squad: true, individ: false, md_key: 'perioder', farg: '#6E8B5E' },
  volleyboll: { namn: 'Volleyboll', res_label: 'Resultat i set', res_ph: '3–1', mid_label: 'Setsiffror', mid_ph: '25–21, 23–25, 25–19, 25–17', mid_moment: 'Mellan set', mid_token: 'setsiffror', start_moment: 'Matchstart', has_scorers: false, scorers_label: '', lineup: 'Startsexa', lineup_n: '(6)', squad: true, individ: false, md_key: 'set', farg: '#C9657F' },
  beachvolley:{ namn: 'Beachvolley', res_label: 'Resultat i set', res_ph: '2–0', mid_label: 'Setsiffror', mid_ph: '21–18, 21–15', mid_moment: 'Mellan set', mid_token: 'setsiffror', start_moment: 'Matchstart', has_scorers: false, scorers_label: '', lineup: 'Par', lineup_n: '(2)', squad: false, individ: false, md_key: 'set', farg: '#E0A040' },
  tennis:     { namn: 'Tennis', res_label: 'Resultat i set', res_ph: '2–1', mid_label: 'Gamesiffror', mid_ph: '6–4, 3–6, 7–5', mid_moment: 'Mellan set', mid_token: 'gamesiffror', start_moment: 'Matchstart', has_scorers: false, scorers_label: '', lineup: '', lineup_n: '', squad: false, individ: true, md_key: 'set', farg: '#7A8794' },
  friidrott:  { namn: 'Friidrott', res_label: 'Resultat', res_ph: '10,12 s', mid_label: 'Placering', mid_ph: '1', mid_moment: 'Delresultat', mid_token: 'placering', start_moment: 'Start', has_scorers: false, scorers_label: '', lineup: '', lineup_n: '', squad: false, individ: true, md_key: 'placering', farg: '#B5643C' },
}

// Mock: vilka lag som deltar i en tävling (tavling_lag). I appen kommer detta
// ur store.lista_lag_for_tavling; här räcker en enkel sport-baserad filtrering.
const MOCK_TAVLING_LAG = {
  'obos-damallsvenskan': ['fc-rosengard', 'eskilstuna-united', 'malmo-ff'],
  'handbollsligan': ['hk-malmo'],
}

// Fotojobb (Google Calendar via deployade tjänsten). Formen matchar tjänstens
// jobb-modell (INTEGRATION.md). Muteras lokalt i mock-läge.
let MOCK_FOTOJOBB = [
  { id: 'fj1', title: 'Match – Malmö / Kristianstad', start_at: '2026-07-19T14:00:00', end_at: '2026-07-19T16:30:00', all_day: false, location: 'Malmö IP', description: '', notering: '2 kort, 400/2.8 + 70-200', category: 'Sport', status: 'confirmed', google_event_id: 'g1', source: 'dpt', match_id: 'a1b2c3d4e5f6',
    ackreditering: { status: 'begard', note: '' }, begar_senast: '2026-07-09', press_email: 'press@arrangor.se' },
  { id: 'fj2', title: 'Möte (skapad i Google)', start_at: '2026-07-15T09:00:00', end_at: '2026-07-15T09:30:00', all_day: false, location: '', description: '', notering: '', category: null, status: 'confirmed', google_event_id: 'g2', source: 'google' },
  { id: 'fj3', title: 'Landskap – soluppgång vid Grenen', start_at: '2026-07-12T04:30:00', end_at: '2026-07-12T06:00:00', all_day: false, location: 'Grenen', description: '', notering: 'Stativ, ND-filter', category: 'Landskap', status: 'confirmed', google_event_id: null, source: 'dpt' },
  { id: 'fj4', title: 'Mässa & workshop', start_at: '2026-06-29', end_at: '2026-07-03', all_day: true, location: '', description: '', notering: 'Monter B12, workshop lör 10:00', category: 'Övrigt', status: 'confirmed', google_event_id: 'g4', source: 'dpt' },
  // Passerade jobb — så scroll-till-idag-beteendet (kommande ovanför, dimmade
  // passerade under) syns direkt i mock-läge.
  { id: 'fj5', title: 'Match – Malmö FF / Kristianstad', start_at: '2026-06-27T14:00:00', end_at: '2026-06-27T16:00:00', all_day: false, location: 'Eleda Stadion', description: '', notering: 'Presskort hämtas i receptionen', category: 'Sport', status: 'confirmed', google_event_id: 'g5', source: 'dpt', match_id: 'a1b2c3d4e5f6',
    ackreditering: { status: 'beviljad', note: 'Väst vid mittlinjen' }, begar_senast: '2026-06-17', press_email: 'press@arrangor.se' },
  { id: 'fj6', title: 'Landskap – midsommarkväll vid Siljan', start_at: '2026-06-20T20:00:00', end_at: '2026-06-20T22:30:00', all_day: false, location: 'Rättvik', description: '', notering: '', category: 'Landskap', status: 'confirmed', google_event_id: 'g6', source: 'dpt' },
  { id: 'fj7', title: 'Event – studentbal', start_at: '2026-06-13T17:00:00', end_at: '2026-06-13T21:00:00', all_day: false, location: 'Leksand', description: '', notering: 'Kund: Leksands gymnasium', category: 'Event', status: 'confirmed', google_event_id: 'g7', source: 'dpt' },
]

// Lokala fotojobb-utkast (tävling → "Lägg i Google Calendar", väntar på
// manuell synk). Muteras lokalt i mock-läge; sammanfogas med MOCK_FOTOJOBB i
// listaFotojobb — speglar app.py:s lista_fotojobb (utkast + riktiga jobb).
let MOCK_FOTOJOBB_UTKAST = []
const _utkastTillJobb = (u) => ({ id: u.id, title: u.title, start_at: u.start_at,
  end_at: u.end_at, all_day: u.all_day, location: u.location || '', description: '',
  category: u.category, status: 'confirmed', google_event_id: null, source: 'dpt', utkast: true })

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

let _matchSeq = 0
export async function sparaMatch(match) {
  const api = brygga()
  if (api) return api.spara_match(match)
  // Mock: en riktig upsert mot MOCK_MATCHER — annars försvinner nya/redigerade
  // matcher så fort panelen läser om listan efter en sparning.
  const id = (match.id && !String(match.id).startsWith('ny-')) ? match.id : `mock${++_matchSeq}`
  const rad = {
    id, datum: match.datum || '', tid: match.tid || '', arena: match.arena || '',
    status: match.resultat ? 'avslutad' : 'kommande', resultat: match.resultat || '',
    mellan: match.mellan || '', malskyttar: match.malskyttar || '',
    sport: match.sport || '', lag_hemma: match.lag_hemma || '', lag_borta: match.lag_borta || '',
    liga: match.liga || '', tavling_id: null, hem_gren: '', hemfarg: '', bortafarg: '',
    galleri: match.galleri || '', sida_url: match.sida_url || '',
    trupp_n: 0, synk_jobb_id: null,
  }
  const i = MOCK_MATCHER.findIndex((m) => m.id === id)
  if (i >= 0) MOCK_MATCHER[i] = { ...MOCK_MATCHER[i], ...rad }
  else MOCK_MATCHER.unshift(rad)
  return wait({ ok: true, id })
}

export async function raderaMatch(id) {
  const api = brygga()
  if (api) return api.radera_match(id)
  const i = MOCK_MATCHER.findIndex((m) => m.id === id)
  if (i >= 0) MOCK_MATCHER.splice(i, 1)
  return wait({ ok: true })
}

// Resultat-remsan (Publicera/Innehåll) — kontinuerlig fältvis redigering av
// resultat/mellan/malskyttar, skild från sparaMatch (Slutsignal/Matcher).
export async function sattResultat(matchId, resultat, mellan, malskyttar) {
  const api = brygga()
  if (api) return api.satt_resultat(matchId, resultat, mellan, malskyttar)
  const i = MOCK_MATCHER.findIndex((m) => m.id === matchId)
  if (i >= 0) MOCK_MATCHER[i] = { ...MOCK_MATCHER[i], resultat, mellan, malskyttar }
  if (MOCK_FULL[matchId]) MOCK_FULL[matchId] = { ...MOCK_FULL[matchId], resultat, mellan, malskyttar }
  return wait({ ok: true })
}

export async function sattMatchSynk(id, pa) {
  const api = brygga()
  if (api) return api.satt_match_synk(id, pa)
  const m = MOCK_MATCHER.find((x) => x.id === id)
  if (!m) return wait({ ok: false, fel: 'Okänd match.' })
  m.synk_jobb_id = pa ? 'fj-mock-' + id : null
  return wait({ ok: true, synk_jobb_id: m.synk_jobb_id })
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

export async function sportprofiler() {
  const api = brygga()
  if (api) return api.sportprofiler()
  return wait(structuredClone(MOCK_SPORTPROFILER))
}

export async function kopplaLagTavling(lagId, tavlingId, pa) {
  const api = brygga()
  if (api) return api.koppla_lag_tavling(lagId, tavlingId, pa)
  const ids = MOCK_TAVLING_LAG[tavlingId] || (MOCK_TAVLING_LAG[tavlingId] = [])
  if (pa && !ids.includes(lagId)) ids.push(lagId)
  if (!pa) MOCK_TAVLING_LAG[tavlingId] = ids.filter((x) => x !== lagId)
  const l = MOCK_LAG.find((x) => x.id === lagId)
  if (l) l.comps = Object.keys(MOCK_TAVLING_LAG).filter((t) => MOCK_TAVLING_LAG[t].includes(lagId))
  return wait({ ok: true })
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
  return wait([...MOCK_FOTOJOBB_UTKAST.map(_utkastTillJobb), ...structuredClone(MOCK_FOTOJOBB)])
}

export async function sparaFotojobb(jobb) {
  const api = brygga()
  if (api) return api.spara_fotojobb(jobb)
  if (jobb.utkast && jobb.id) {
    MOCK_FOTOJOBB_UTKAST = MOCK_FOTOJOBB_UTKAST.map((u) => (u.id === jobb.id ? { ...u, ...jobb } : u))
    return wait({ ok: true })
  }
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
  if (MOCK_FOTOJOBB_UTKAST.some((u) => u.id === id)) {
    MOCK_FOTOJOBB_UTKAST = MOCK_FOTOJOBB_UTKAST.filter((u) => u.id !== id)
    return wait({ ok: true })
  }
  MOCK_FOTOJOBB = MOCK_FOTOJOBB.filter((j) => j.id !== id)
  return wait({ ok: true })
}

// ── Ackreditering (bara matchjobb/Sport) ──────────────────────────────────────
export async function sattAckreditering(jobbId, { status = null, note = null } = {}) {
  const api = brygga()
  if (api) return api.satt_ackreditering(jobbId, status, note)
  MOCK_FOTOJOBB = MOCK_FOTOJOBB.map((j) => (j.id === jobbId
    ? { ...j, ackreditering: { status: status ?? j.ackreditering?.status ?? 'ejbegard',
        note: note ?? j.ackreditering?.note ?? '' } } : j))
  const a = MOCK_FOTOJOBB.find((j) => j.id === jobbId)?.ackreditering
  return wait({ ok: true, ackreditering: a || { status: 'ejbegard', note: '' } })
}

export async function skickaAckrMail(jobbId, till, amne, kropp) {
  const api = brygga()
  if (api) return api.skicka_ackr_mail(jobbId, till, amne, kropp)
  if (!(till || '').includes('@')) return wait({ ok: false, fel: 'Ange mottagarens e-postadress.' })
  return sattAckreditering(jobbId, { status: 'begard' })   // mock: "skickat" → Begärd
}

// ── Privata kalendrar (skrivskyddat tillgänglighetslager, läses lokalt) ───────
// Mock-läget svarar med seed (samma data UI:t verifierades mot i steg 1). Skarpt
// läge går via Python-bryggan → tjanster/privat_kalender.py → Google direkt.
export async function privatStatus() {
  const api = brygga()
  if (api) return api.privat_status()
  return wait({ har_klient: true, inloggad: true, kalendrar_valda: SEED_KALENDRAR.length })
}

// Färgen normaliseras till den kurerade paletten (privat.js) oavsett vad Google
// (eller seed) råkar leverera — rött är reserverat för krock-signalen, så en
// privat källa får aldrig en röd/korall färg som läser som ett krock-larm.
// Tilldelas stabilt per position i listan.
function _palettFarga(r) {
  const kalendrar = (r?.kalendrar || []).map((k, i) => ({ ...k, farg: kureradFarg(i) }))
  return { ...r, kalendrar }
}

// Mock-läget speglar backendens egna etiketter (config-lagrade omdöpningar).
const _mockEtiketter = {}

export async function privatKalendrar() {
  const api = brygga()
  if (api) return _palettFarga(await api.privat_kalendrar())
  const kalendrar = structuredClone(SEED_KALENDRAR)
    .map((k) => ({ ...k, etikett: _mockEtiketter[k.id] || k.etikett }))
  return _palettFarga({ kalendrar, valda: SEED_KALENDRAR.map((k) => k.id) })
}

export async function privatSattValda(ids) {
  const api = brygga()
  if (api) return api.privat_satt_valda(ids)
  return wait({ ok: true })
}

export async function privatSattEtikett(id, etikett) {
  const api = brygga()
  if (api) return api.privat_satt_etikett(id, etikett)
  const e = (etikett || '').trim()
  if (e) _mockEtiketter[id] = e
  else delete _mockEtiketter[id]
  return wait({ ok: true })
}

export async function privatHandelser(fran, till) {
  const api = brygga()
  if (api) return api.privat_handelser(fran, till)
  // Mock: filtrera seed till spannet (halvöppet på datumnivå) så vecko-/månadsbyten
  // beter sig som skarpt läge, där backend redan spannbegränsar.
  return wait(SEED_PRIVATA.filter((p) => (p.slut || p.start) >= fran && p.start < till + 'T99'))
}

export async function privatLoggaIn() {
  const api = brygga()
  if (api) return api.privat_logga_in()
  return wait({ ok: false, fel: 'Inloggning kräver den riktiga appen (pywebview).' })
}

export async function privatLoggaUt() {
  const api = brygga()
  if (api) return api.privat_logga_ut()
  return wait({ ok: true })
}

export async function privatSparaKlient(clientId, clientSecret) {
  const api = brygga()
  if (api) return api.privat_spara_klient(clientId, clientSecret)
  return wait({ ok: true })
}

export async function aktiveraSynkFotojobb(utkastId) {
  const api = brygga()
  if (api) return api.aktivera_synk_fotojobb(utkastId)
  const u = MOCK_FOTOJOBB_UTKAST.find((x) => x.id === utkastId)
  if (!u) return wait({ ok: false, fel: 'Utkastet finns inte längre.' })
  MOCK_FOTOJOBB_UTKAST = MOCK_FOTOJOBB_UTKAST.filter((x) => x.id !== utkastId)
  MOCK_FOTOJOBB = [...MOCK_FOTOJOBB, { id: 'fj' + Date.now(), title: u.title,
    start_at: u.start_at, end_at: u.end_at, all_day: u.all_day, location: u.location || '',
    description: '', category: u.category, status: 'confirmed', google_event_id: 'gmock', source: 'dpt' }]
  return wait({ ok: true })
}

export async function sparaLag(lag) {
  const api = brygga()
  if (api) return api.spara_lag(lag)
  return wait({ ok: true, id: lag.id || slug(lag.namn) })
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

// ── Tävling → Fotojobb-utkast (väntar på manuell synk) ──────────────────────
export async function laggTavlingIKalender(tavlingId) {
  const api = brygga()
  if (api) return api.lagg_tavling_i_kalender(tavlingId)
  const t = MOCK_TAVLINGAR.find((x) => x.id === tavlingId)
  if (!t?.fran || !t?.till) return wait({ ok: false, fel: 'Ange start- och slutdatum på tävlingen först.' })
  const finns = MOCK_FOTOJOBB_UTKAST.find((u) => u.tavling_id === tavlingId)
  if (finns) return wait({ ok: true, utkast_id: finns.id })
  const uid = 'utkast_' + Date.now()
  MOCK_FOTOJOBB_UTKAST = [...MOCK_FOTOJOBB_UTKAST, { id: uid, tavling_id: tavlingId,
    title: t.namn, start_at: t.fran, end_at: t.till, all_day: true,
    location: t.arena || t.ort || '', category: null }]
  return wait({ ok: true, utkast_id: uid })
}

export async function taBortTavlingUrKalender(tavlingId) {
  const api = brygga()
  if (api) return api.ta_bort_tavling_ur_kalender(tavlingId)
  MOCK_FOTOJOBB_UTKAST = MOCK_FOTOJOBB_UTKAST.filter((u) => u.tavling_id !== tavlingId)
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

// §7: Importera spelschema — riktig hämtning via Claude-tjänsten.
export async function hamtaSpelschema(lag, url = '', sport = '') {
  const api = brygga()
  if (api) return api.hamta_spelschema(lag, url, sport)
  return wait({ ok: true, lag, kallor: [`https://exempel.se/${slugga(lag)}/matcher`],
    matcher: [
      { motstandare: 'IK Exempel', hemma: true, datum: '2026-09-12', tid: '15:00', arena: 'Hemmaplan IP', liga: 'OBOS Damallsvenskan' },
      { motstandare: 'FC Rosengård', hemma: false, datum: '2026-09-20', tid: '14:00', arena: 'Malmö Idrottsplats', liga: 'OBOS Damallsvenskan' },
    ] })
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

// ── Arbetsyta — autosparade utkast (Live/SoMe/Webb-Sport, per match) ────────
const _mockUtkast = {}

export async function hamtaUtkast(matchId) {
  const api = brygga()
  if (api) return api.hamta_utkast(matchId)
  return wait(_mockUtkast[matchId] ? structuredClone(_mockUtkast[matchId]) : null)
}

export async function sparaUtkast(matchId, patch) {
  const api = brygga()
  if (api) return api.spara_utkast(matchId, patch)
  _mockUtkast[matchId] = { ...(_mockUtkast[matchId] || {}), ...patch }
  return wait({ ok: true })
}

// ── Aktivt urval (topbar-chippet; ①Gallra → ②Leverera → ③Publicera) ──────────
let _aktivtUrvalId = null

export async function sattAktivtUrval(id) {
  const api = brygga()
  if (api) return api.satt_aktivt_urval(id)
  _aktivtUrvalId = id
  return wait({ ok: true })
}

export async function aktivtUrval() {
  const api = brygga()
  if (api) return api.aktivt_urval()
  const u = MOCK_URVAL.find((x) => x.id === _aktivtUrvalId)
    || MOCK_URVAL.find((x) => x.status === 'gallrad') || MOCK_URVAL[0] || null
  return wait(u ? structuredClone(u) : null)
}

export async function urvalHojdpunkter(n = 6) {
  const api = brygga()
  if (api) return api.urval_hojdpunkter(n)
  const u = await aktivtUrval()
  if (!u) return wait({ ok: false, fel: 'Inget aktivt urval — gallra en match först.' })
  const namn = u.lag_hemma ? `${u.lag_hemma} – ${u.lag_borta}` : (u.kalla || '').split('/').pop()
  const antal = Math.min(u.bilder || n, n)
  return wait({ ok: true, urval: structuredClone(u), namn,
    filer: Array.from({ length: antal }, (_, i) => `DSC_0${417 + i}`),
    sokvagar: Array.from({ length: antal }, (_, i) => `/Users/sickan/Dropbox/DPT/Live/DSC_0${417 + i}.jpg`) })
}

// SoMe-bildbibliotekets "Publicera-urvalet"-källa — samma aktiva urval som
// urval_hojdpunkter, men riktiga sökvägar för ALLA behållna bilder (inte
// bara topp-N).
export async function bilderForUrval() {
  const api = brygga()
  if (api) return api.bilder_for_urval()
  const u = await aktivtUrval()
  if (!u) return wait({ ok: false, fel: 'Inget aktivt urval — gallra en match först.' })
  const antal = u.bilder || 12
  return wait({ ok: true, urval: structuredClone(u),
    bilder: Array.from({ length: antal }, (_, i) => `/mock/urval/DSC_0${417 + i}.jpg`) })
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

export async function levereraEgenMapp(mapp, config = {}) {
  const api = brygga()
  if (api) return api.leverera_egen_mapp(mapp, config)
  if (!mapp) return wait({ ok: false, fel: 'Ange en mapp.' })
  return wait({ ok: true, status: 'levererad', skrivna: 12, ratade: 0 })
}

export async function startaNummer(urvalId) {
  const api = brygga()
  if (api) return api.starta_nummer(urvalId)
  const u = MOCK_URVAL.find((x) => x.id === urvalId)
  const n = u ? u.bilder : 0
  return wait({ ok: true, resultat: { totalt: n, skrivna: Math.round(n * 0.8), luckor: Math.round(n * 0.1) },
    meddelande: `Tröjnummer skrivna på ${Math.round(n * 0.8)} av ${n} bilder.` })
}

export async function snabbplockKortrot(kortPath, utMapp = null) {
  const api = brygga()
  if (api) return api.snabbplock_kortrot(kortPath, utMapp)
  return wait({ ok: true, antal: 47, path: kortPath + '/Snabbplock',
    meddelande: '47 kameralåsta bilder kopierade.' })
}

export async function listaMinnesKort() {
  const api = brygga()
  if (api) return api.lista_minneskort()
  return wait({ ok: true, kort: [
    { namn: 'NIKON D5', path: '/Volumes/NIKON D5', skyddade: 12 },
    { namn: 'NIKON Z 8', path: '/Volumes/NIKON Z 8', skyddade: 8 }
  ]})
}

// Bildfilerna på ett kort, nyast först (RAW+JPEG-par ihopslagna, RAW föredras)
// — plockrutnätets källa. Varje ruta hämtar sedan sin preview via thumbForBild.
export async function listaKortBilder(kortPath, antal = 0) {
  const api = brygga()
  if (api) return api.lista_kort_bilder(kortPath, antal)
  const n = antal || 12 // demo: fast antal när antal=0 (alla)
  return wait({ ok: true, totalt: n, bilder: Array.from({ length: n }, (_, i) => ({
    path: `${kortPath}/DSC_${1000 + i}.NEF`, filnamn: `DSC_${1000 + i}.NEF`, skyddad: true })) })
}

// Snabbplockets skarpa 'Öppna i Lightroom' — kopierar de plockade filerna
// (fulla sökvägar) till en arbetsmapp, skriver Blue-etikett och öppnar LR.
export async function snabbplockExport(paths, utMapp = null, oppnaLr = true) {
  const api = brygga()
  if (api) return api.snabbplock_export(paths, utMapp, oppnaLr)
  return wait({ ok: true, antal: (paths || []).length,
    path: (utMapp || '~/Pictures/DPT2 Snabbplock/nu') })
}

export async function rataUppMapp(mapp) {
  const api = brygga()
  if (api) return api.rata_upp_mapp(mapp)
  return wait({ ok: true, n_raw: 247, n_skriv: 247,
    meddelande: 'XMP-sidecars skrivna för 247/247 raw-filer.' })
}

// fakta = redan kända matchfakta ({resultat, mellan, malskyttar, arena, datum,
// liga}) — vävs in i Claude-frågan så websökning inte behöver leta upp sånt
// appen redan vet (se tjanster/bildsvep.py:bygg_fraga).
export async function genereraBildsvep(matchinfo, sport = '', hemmaFarg = '', fakta = null) {
  const api = brygga()
  if (api) return api.generera_bildsvep(matchinfo, sport, hemmaFarg, fakta)
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

// "Godkänn prompten" — bygger (utan nätverksanrop) exakt den fråga som
// skulle skickas, för granskning innan det skarpa ~2-minuters Claude-anropet.
export async function forhandsgranskaBildsvepFraga(matchinfo, fakta = null) {
  const api = brygga()
  if (api) return api.forhandsgranska_bildsvep_fraga(matchinfo, fakta)
  return wait({ ok: true, fraga: `Match: ${matchinfo}.\n(mock — riktig fråga byggs i skarpa appen)` })
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
    match_id: 'a1b2c3d4e5f6', synkad_tid: '2026-06-27T16:45:00',
    export_path: '/sajt/src/content/match/malmo-ff-kristianstads-dff.md',
    frontmatter: { titel: 'Malmö FF – Kristianstads DFF', resultat: '6-0' } },
]

function mockMd(data) {
  const fm = ['---', `typ: ${data.typ || 'match'}`, `titel: "${data.titel || ''}"`]
  for (const k of ['kategori', 'kund', 'datum', 'plats', 'period',
    'ingress', 'liga', 'arena', 'resultat', 'halvtid', 'galleri']) {
    if (data[k]) fm.push(`${k}: "${data[k]}"`)
  }
  if (data.hero) fm.push(`hero: ${data.hero}`)
  if (data.heroPosition) fm.push(`heroPosition: "${data.heroPosition}"`)
  if (data.pixieset) fm.push(`pixieset: ${data.pixieset}`)
  const mal = (typeof data.malskyttar === 'string'
    ? data.malskyttar.split(',').map((s) => s.trim()).filter(Boolean)
    : data.malskyttar) || []
  if (mal.length) { fm.push('malskyttar:'); mal.forEach((m) => fm.push(`  - ${m}`)) }
  fm.push('---', '')
  // Speglar _innehall_md: härledda /bilder/{slug}/{n}.jpg-referenser;
  // Landskap & Event är bild-only (ingen alt/bildtext).
  const galText = !(data.typ === 'landskap' || data.typ === 'event')
  const figs = (data.figurer || []).map((f, i) => {
    const ref = f.bild || `/bilder/${slug(data.titel)}/${i + 1}.jpg`
    return galText
      ? `![${f.alt || ''}](${ref})` + (f.bildtext ? `\n*${f.bildtext}*` : '')
      : `![](${ref})`
  })
  const platser = (data.platser || []).filter((p) => (p.plats || '').trim())
    .map((p) => `- **${p.plats}** — ${p.tips || ''}`)
  const platsMd = platser.length ? '## Platser & tips\n\n' + platser.join('\n') : ''
  return fm.join('\n') + '\n'
    + [data.body || '', figs.join('\n\n'), platsMd].filter(Boolean).join('\n\n') + '\n'
}

const slug = (t) => (t || 'innehall').toLowerCase()
  .replace(/å|ä/g, 'a').replace(/ö/g, 'o').replace(/&/g, 'och')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'innehall'

// Exporterad för UI:t (Innehålls /bilder/{slug}/{n}.jpg-referenser).
export const slugga = slug

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

export async function exporteraInnehall(data, exportDir, test = false) {
  const api = brygga()
  if (api) return api.exportera_innehall(data, exportDir, test)
  if (test) return wait({ ok: true, id: null, path: `~/DPT/test-output/content/${slug(data.titel)}.md`, test: true })
  if (!exportDir) return wait({ ok: false, fel: 'Ange en export-katalog.' })
  return wait({ ok: true, id: data.id || 'i_ny', path: `${exportDir}/${slug(data.titel)}.md` })
}

export async function raderaInnehall(id) {
  const api = brygga()
  if (api) return api.radera_innehall(id)
  return wait({ ok: true })
}

// Publicerar direkt till hemsidan via content-sync-workern (skilt från
// exporteraInnehall, som bara skriver en lokal .md-fil).
export async function publiceraInnehallNatet(data, test = false) {
  const api = brygga()
  if (api) return api.publicera_innehall_natet(data, test)
  if (test) return wait({ ok: true, id: null, path: `~/DPT/test-output/content/${slug(data.titel)}.md`, test: true })
  return wait({ ok: true, id: data.id || 'i_ny' })
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

// Lär av match — märker ett gallrat urvals mapp som träningsdata (kör i workern).
export async function larAvMatch(mapp, matchNamn = '', sport = '') {
  const api = brygga()
  if (api) return api.lar_av_match(mapp, matchNamn, sport)
  if (!mapp) return wait({ ok: false, fel: 'Peka ut urvalets mapp.' })
  const antal = 40
  return wait({ ok: true, antal,
    meddelande: `${antal} bilder märkta som träningsdata — AI lär av denna gallring.` })
}

let MOCK_HISTORIK = [
  { id: 'f_rosengard', match_namn: 'FC Rosengård – Malmö FF', sport: 'fotboll', n: 38, skapad: '2026-07-04 14:20' },
  { id: 'f_kristianstad', match_namn: 'Malmö FF – Kristianstads DFF', sport: 'fotboll', n: 40, skapad: '2026-06-30 09:12' },
]

export async function traningshistorik() {
  const api = brygga()
  if (api) return api.traningshistorik()
  return wait(structuredClone(MOCK_HISTORIK))
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

// Miniatyr (base64 data-URI) för en vald hero-bild — raw extraheras, jpg
// öppnas direkt (samma logik som dpt v1:s "Visa urval"-miniatyrer).
export async function thumbForBild(path) {
  const api = brygga()
  if (api) return api.thumb_for_bild(path)
  const filnamn = (path || '').split('/').pop() || ''
  return wait({ ok: true, filnamn,
    data_uri: 'data:image/svg+xml;base64,' + btoa(
      `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">
        <rect width="100%" height="100%" fill="#cbb896"/>
        <text x="50%" y="50%" font-size="20" text-anchor="middle" fill="#5c4a2c">${filnamn}</text>
      </svg>`) })
}

// Live-status (senaste Cloudflare Pages-deploy) för en publicerad innehållsrad.
export async function statusInnehall(typ, id) {
  const api = brygga()
  if (api) return api.status_innehall(typ, id)
  return wait({ id, publicerad: true, deploy: { status: 'success', skapad: new Date().toISOString(), url: null } })
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
  if (config.test) {
    return wait({ ok: true, publicerad: true, test: true,
      path: `~/DPT/test-output/2026-01-01/live/story_${config.moment.toLowerCase()}.jpg` })
  }
  return wait({ ok: true, path: `${config.ut_mapp || '~/Dropbox/DPT/Live'}/story_${config.moment.toLowerCase()}.jpg`,
    publicerad: true, url: 'https://exempel/story/1' })
}

// Matchpublicering Steg 2: rendera + publicera EN kanal server-side med kanalens
// beskärning på varje bild. live=1 (omslag+overlay), ig≤10 (omslag+overlay +
// beskurna), fb≤4 (första overlay). Testläge renderar allt till testmappen.
export async function publiceraKanal(config) {
  const api = brygga()
  if (api) return api.publicera_kanal(config)
  const kanal = config?.kanal || 'ig'
  const cap = { live: 1, ig: 10, fb: 4 }[kanal] || 10
  const antal = Math.min((config?.bilder || []).length, cap)
  if (!antal) return wait({ ok: false, fel: 'Välj minst en bild i Steg 1.' })
  if (config.test) return wait({ ok: true, publicerad: true, test: true, antal,
    path: config.test_mapp || `~/DPT/test-output/2026-01-01/${kanal}` })
  return wait({ ok: true, publicerad: true, antal, url: `https://exempel/${kanal}/1` })
}

// Riktig förhandsvisning (samma Horisont-mall, renderad server-side) — i mock
// finns ingen PIL-motor, så vi "förhandsvisar" bara den valda källbilden själv.
export async function forhandsgranskaStory(config) {
  const api = brygga()
  if (api) return api.forhandsgranska_story(config)
  if (!config?.moment) return wait({ ok: false, fel: 'Välj ett moment.' })
  if (!config?.foto) return wait({ ok: false, fel: 'Välj en bild i steg 2.' })
  return wait({ ok: true, path: config.foto })
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
  if (config?.test) {
    const malnyckel = Object.keys(config.mal || {}).find((k) => config.mal[k])
    const [kanal, form] = { story: ['instagram', 'story'], ig_inlagg: ['instagram', 'inlägg'],
      fb: ['facebook', 'inlägg'] }[malnyckel] || ['instagram', 'inlägg']
    return wait({ ok: true, sparade: 0, varningar: [],
      resultat: [{ kanal, form, del: 1, av: 1, status: 'postad', test: true,
        antal_bilder: (config.bilder || []).length }],   // hela setet kopieras i testläget
      path: config.test_mapp || '~/DPT/test-output/2026-01-01/some_paket_120000' })
  }
  const plan = _mockPlanera(config || {})
  if (!plan.ok) return wait(plan)
  return wait({ ok: true, sparade: plan.poster.length, varningar: plan.varningar,
    resultat: plan.poster.map((p, i) => ({ ...p, status: 'postad', url: `https://exempel/post/${i + 1}` })) })
}

// Testläge: en gemensam mapp för en hel SoMe-paket-körning (se Publicera.svelte
// somePublicera — hämtas EN gång innan fan-out:en, återanvänds för alla kanaler).
export async function nyTestPaketMapp() {
  const api = brygga()
  if (api) return api.ny_test_paket_mapp()
  return wait({ ok: true, path: '~/DPT/test-output/2026-01-01/some_paket_120000' })
}

// ── Hämta bilder (minneskort → Lightroom → katalog) ──────────────────────────
export async function listaMinneskort() {
  const api = brygga()
  if (api) return api.lista_minneskort()
  return wait({ ok: true, kort: [
    { namn: 'NIKON Z 8', path: '/Volumes/NIKON Z 8', skyddade: 142 },
    { namn: 'EOS_DIGITAL', path: '/Volumes/EOS_DIGITAL', skyddade: 0 }] })
}
export async function raknaSkyddade(kortPath) {
  const api = brygga()
  if (api) return api.rakna_skyddade(kortPath)
  return wait({ ok: true, path: kortPath, skyddade: 142 })
}
export async function exporteraSkyddade(kortPath, malMapp, oppnaLr = true) {
  const api = brygga()
  if (api) return api.exportera_skyddade(kortPath, malMapp, oppnaLr)
  return wait({ ok: true, antal: 142, path: malMapp || '~/Export/skyddade' })
}

// ── På gång (webb) — härledd ur matchlistan ──────────────────────────────────
export async function pagangMatcher() {
  const api = brygga()
  if (api) return api.pagang_matcher()
  return wait({ ok: true, visa: true, matcher: [
    { id: 'p1', datum: '2026-07-31', tid: '19:00', lag_hemma: 'Malmö FF', lag_borta: 'Piteå IF DFF', liga: 'OBOS Damallsvenskan', hem_gren: 'dam' },
    { id: 'p2', datum: '2026-08-12', tid: '', lag_hemma: 'Malmö FF', lag_borta: 'Hammarby IF', liga: 'OBOS Damallsvenskan', hem_gren: 'dam' },
    { id: 'p3', datum: '2026-08-21', tid: '18:30', lag_hemma: 'Sverige', lag_borta: 'Italien', liga: 'EM Volleyboll', hem_gren: 'dam' },
    { id: 'p4', datum: '2026-09-02', tid: '', lag_hemma: 'Sverige', lag_borta: 'Danmark', liga: 'Landskamp herr', hem_gren: 'herr' }] })
}
export async function sattPagangVisa(pa) {
  const api = brygga()
  if (api) return api.satt_pagang_visa(pa)
  return wait({ ok: true, visa: !!pa })
}
export async function publiceraPagangMatcher(test = false) {
  const api = brygga()
  if (api) return api.publicera_pagang_matcher(test)
  return wait({ ok: true, antal: 4, borttagna: 0, visa: true, test })
}

// ── Sport-startsidan: hero-kurering (topp-flaggan i publicerad frontmatter) ──
export async function sportTopp() {
  const api = brygga()
  if (api) return api.sport_topp()
  return wait({ ok: true, lage: 'senaste', innehall_id: null })
}
export async function sattSportTopp(lage, innehallId = null, test = false) {
  const api = brygga()
  if (api) return api.satt_sport_topp(lage, innehallId, test)
  return wait({ ok: true, andrade: lage === 'valj' ? 1 : 0, test })
}

// ── Mobil Live ──────────────────────────────────────────────────────────────
// `hamtaLive` pollas av Publicera-panelen och returnerar mobilens live-tillstånd
// (malskyttar redan serialiserad till appens strängformat, + falt_uppdaterad så
// panelen kan avgöra vilka fält som är färskare än dess egna).
// I mock: sätt `window.__MOCK_LIVE` för att driva flödet i preview.
export async function hamtaLive(matchId) {
  const api = brygga()
  if (api) return api.hamta_live(matchId)
  return wait({ ok: true, live: (typeof window !== 'undefined' && window.__MOCK_LIVE) || null })
}

export async function synkaLivePaket() {
  const api = brygga()
  if (api) return api.synka_live_paket()
  return wait({ ok: true, antal: 3, borttagna: 0 })
}

// Sparade material + utkast (Publicera-panelens arbetsyta). Muteras lokalt i mock.
// Två seedade rader så "Delvis publicerad" + historik-tidslinjen syns direkt i
// mock-läge (utan pywebview-bryggan): en publicerad med flerfaldig historik,
// en delvis med en trasig kanal att öva "Försök igen" på.
let MOCK_MATERIAL = [
  {
    id: 'mat_seed_1', kind: 'some', status: 'publicerad',
    match_id: 'a1b2c3d4e5f6', match_namn: 'Malmö FF – Kristianstads DFF',
    channels: ['story', 'ig'], caption: 'Fullt hus på Eleda! 6–0 till damerna 💛 #malmoff',
    banor: { story: { mapp: '/bilder/resultat', bilder: ['bild_01.jpg', 'bild_02.jpg'] },
      ig: { mapp: '/bilder/resultat', bilder: ['bild_01.jpg'] }, fb: { mapp: '', bilder: [] } },
    ch_results: { story: 'ok', ig: 'ok' },
    uppdaterad: '2026-06-27T16:03:00',
    history: [
      { when: '2026-06-27T16:03:00', status: 'publicerad', note: '' },
      { when: '2026-06-27T15:58:00', status: 'delvis', note: 'Facebook föll' },
      { when: '2026-06-27T15:41:00', status: 'publicerad', note: '' },
    ],
  },
  {
    id: 'mat_seed_2', kind: 'some', status: 'delvis',
    match_id: 'a1b2c3d4e5f6', match_namn: 'Malmö FF – Kristianstads DFF',
    channels: ['story', 'ig', 'fb'], caption: 'Halvtidsställning 3–0 👏 #malmoff',
    banor: { story: { mapp: '/bilder/halvtid', bilder: ['h_01.jpg'] },
      ig: { mapp: '/bilder/halvtid', bilder: ['h_01.jpg'] },
      fb: { mapp: '/bilder/halvtid', bilder: ['h_01.jpg'] } },
    ch_results: { story: 'ok', ig: 'ok', fb: 'fail' },
    uppdaterad: '2026-06-27T15:41:00',
    history: [{ when: '2026-06-27T15:41:00', status: 'delvis', note: 'Facebook föll' }],
  },
  // Delvis publicerat med NYA formen på banor: varje kanal bär hela sitt
  // återkörbara anrop (typ + payload), så "Försök igen" renderar identiska
  // bilder. mat_seed_2 ovan behålls i den GAMLA formen — den ska visa
  // "sparad före uppdateringen" i stället för en knapp som postar fel bilder.
  {
    id: 'mat_seed_3', kind: 'some', status: 'delvis',
    match_id: 'a1b2c3d4e5f6', match_namn: 'Malmö FF – Kristianstads DFF',
    channels: ['live', 'ig', 'fb'], caption: 'Slutresultat 6–0 ⚽ #malmoff',
    foto: '/bilder/resultat/bild_01.jpg',
    banor: {
      live: { typ: 'kanal', payload: { kanal: 'live', format: '9x16', tema: 'Hav',
        bilder: [{ path: '/bilder/resultat/bild_01.jpg', fokus: { x: 0.5, y: 0.4 }, zoom: 1 }],
        moment: 'resultat', match_id: 'a1b2c3d4e5f6', caption: 'Slutresultat 6–0',
        stallning: '6-0', mellan: '3-0', mal_rad: '' } },
      ig: { typ: 'kanal', payload: { kanal: 'ig', format: '4x5', tema: 'Hav',
        bilder: [{ path: '/bilder/resultat/bild_01.jpg', fokus: { x: 0.5, y: 0.4 }, zoom: 1 }],
        moment: 'resultat', match_id: 'a1b2c3d4e5f6', caption: 'Slutresultat 6–0',
        stallning: '6-0', mellan: '3-0', mal_rad: '' } },
      fb: { typ: 'kanal', payload: { kanal: 'fb', format: '1x1', tema: 'Hav',
        bilder: [{ path: '/bilder/resultat/bild_01.jpg', fokus: { x: 0.5, y: 0.4 }, zoom: 1 }],
        moment: 'resultat', match_id: 'a1b2c3d4e5f6', caption: 'Slutresultat 6–0',
        stallning: '6-0', mellan: '3-0', mal_rad: '' } },
    },
    ch_results: { live: 'ok', ig: 'ok', fb: 'fail' },
    uppdaterad: '2026-06-27T16:20:00',
    history: [{ when: '2026-06-27T16:20:00', status: 'delvis', note: 'Facebook föll' }],
  },
]
let _matSeq = 2

export async function listaMaterial() {
  const api = brygga()
  if (api) return api.lista_material()
  return wait(structuredClone(MOCK_MATERIAL))
}

export async function sparaMaterial(data) {
  const api = brygga()
  if (api) return api.spara_material(data)
  const idx = data.id ? MOCK_MATERIAL.findIndex((m) => m.id === data.id) : -1
  const uppdaterad = new Date().toISOString()
  const nyPost = { when: uppdaterad, status: data.status, note: data.historik_note || '' }
  const loggaHistorik = data.status === 'publicerad' || data.status === 'delvis'
  if (idx >= 0) {
    const forra = MOCK_MATERIAL[idx]
    const history = loggaHistorik ? [nyPost, ...(forra.history || [])] : (forra.history || [])
    MOCK_MATERIAL[idx] = { ...forra, ...data, uppdaterad, history }
    return wait({ ok: true, id: MOCK_MATERIAL[idx].id })
  }
  const id = data.id || `mat_${++_matSeq}`
  const history = loggaHistorik ? [nyPost] : []
  MOCK_MATERIAL = [{ ...data, id, uppdaterad, history }, ...MOCK_MATERIAL]
  return wait({ ok: true, id })
}

export async function raderaMaterial(id) {
  const api = brygga()
  if (api) return api.radera_material(id)
  MOCK_MATERIAL = MOCK_MATERIAL.filter((m) => m.id !== id)
  return wait({ ok: true })
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
