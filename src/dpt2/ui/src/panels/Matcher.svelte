<script>
  import { onMount, createEventDispatcher, tick } from 'svelte'
  import {
    listaMatcher, hamtaMatch, sparaMatch, hamtaTrupp, sattAktivMatch,
    lasUttagFil, valjFil, listaTavlingar, listaLag, listaLagForTavling,
    listaUrval, raderaMatch, sattMatchSynk, sportprofiler, sattAktivtUrval,
    listaMaterial, listaInnehall, sparaMaterial, sparaInnehall, hamtaSpelschema,
    listaEventer, sparaTavling, importeraSpelschema,
  } from '../lib/api.js'
  import Combobox from '../lib/Combobox.svelte'
  import ProjektLista from '../lib/ProjektLista.svelte'
  import Lagbricka from '../lib/Lagbricka.svelte'
  import Hornmarkor from '../lib/Hornmarkor.svelte'
  import { synkFarg } from '../lib/synk.js'
  import { grenFarg, grenEtikett } from '../lib/gren.js'

  const dispatch = createEventDispatcher()

  let matcher = []
  let tavlingar = []
  let lagAlla = []
  let lagForTavling = []
  let projekt = []
  let laddar = true
  let sportFilter = 'alla'
  let matchGroupBy = 'datum'
  let oppen = null
  let utkast = null
  let bekraftaId = null
  let fel = ''
  let matchSearch = ''
  let matchSeasonSel = null      // null = aktiv säsong (se aktivAr nedan)
  let matchShowN = 12
  // §6 (Skala UX 5a+5b): statusflikar — spelad = har ifyllt resultat.
  let matchStatus = 'kommande'   // 'kommande' | 'spelade'
  let matchFilterOpen = false    // ⚙ Filter-popover (sport + säsong)

  const SPORTER = ['alla', 'fotboll', 'handboll', 'innebandy', 'volleyboll', 'beachvolley', 'tennis', 'friidrott']
  const SPORT_ETIKETT = { fotboll: 'Fotboll', handboll: 'Handboll', innebandy: 'Innebandy', volleyboll: 'Volleyboll', beachvolley: 'Beachvolley', tennis: 'Tennis', friidrott: 'Friidrott' }
  // Normallängd per sport (min) → uträknad sluttid; utan avsparkstid = heldag.
  // Speglar MATCH_LANGD_MIN i app.py (backend sätter kalenderjobbets sluttid).
  const MATCH_LANGD = { fotboll: 120, volleyboll: 150, handboll: 90, beachvolley: 90, innebandy: 120, tennis: 120, friidrott: 180 }
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const MANAD = ['Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni', 'Juli', 'Augusti', 'September', 'Oktober', 'November', 'December']
  const SPORT_FARG = '#2F7CB0'
  const PROFIL_FALLBACK = { lineup: 'Startelva', lineup_n: '(11)', squad: true, individ: false }
  let profiler = {}
  $: uttagProfil = profiler[utkast?.sport] || profiler.fotboll || PROFIL_FALLBACK
  let materialAlla = []
  let innehallAlla = []

  onMount(async () => {
    ;[matcher, tavlingar, lagAlla, projekt, profiler, materialAlla, innehallAlla, eventer] = await Promise.all(
      [listaMatcher(), listaTavlingar(), listaLag(), listaUrval(), sportprofiler(),
       listaMaterial(), listaInnehall('match'), listaEventer()])
    laddar = false
    // SYNK-DPT2: mobilens ändringar (resultat/trupp via molnet) → ladda om
    // matchlistan när delta-pollen signalerar. Lyssnaren städas vid unmount.
    const synka = async () => { matcher = await listaMatcher() }
    window.addEventListener('dpt-synk', synka)
    return () => window.removeEventListener('dpt-synk', synka)
  })

  // ── §2: matchradens statuschips (Kalender/Gallrat/Live/SoMe/Webb) ─────────
  // Allt härlett — inget nytt lagras. Chipsen är genvägar, inte steg.
  function navChips(m) {
    const gallrat = projekt.filter((p) => p.match_id === m.id)
      .reduce((s, p) => s + (p.bilder || 0), 0)
    const live = materialAlla.filter((x) => x.match_id === m.id && x.kind === 'live')
    const some = materialAlla.filter((x) => x.match_id === m.id && x.kind === 'some')
    // Fb1: en post kan ha status 'delvis' (någon kanal föll — se app.py), och
    // flera poster kan vara olika långt gångna. Förr räckte EN publicerad post
    // för grönt chip, så raden såg klar ut mitt i en publiceringsomgång.
    const lage = (rader) => {
      if (!rader.length) return { tone: 'neutral', suffix: '' }
      if (rader.some((x) => x.status === 'delvis')) return { tone: 'delvis', suffix: ' · delvis' }
      const pub = rader.filter((x) => x.status === 'publicerad').length
      if (pub === rader.length) return { tone: 'ok', suffix: ' · publicerad' }
      if (pub) return { tone: 'delvis', suffix: ` · ${pub} av ${rader.length}` }
      return { tone: 'draft', suffix: ' · utkast' }
    }
    const liveL = lage(live)
    const someL = lage(some)
    const inn = innehallAlla.find((x) => x.match_id === m.id)
    const webb = !inn
      ? (m.resultat ? { label: 'Webb saknas · Skapa ›', tone: 'accent' } : { label: 'Webb', tone: 'neutral' })
      : inn.synkad_tid ? { label: 'Webb · publicerad', tone: 'ok' }
      : inn.publicerad ? { label: 'Webb · utkast', tone: 'draft' }
      : { label: 'Webb', tone: 'neutral' }
    return [
      { key: 'kalender', label: 'Kalender', tone: m.synk_jobb_id ? 'ok' : 'neutral', dest: 'fotojobb' },
      { key: 'gallrat', label: gallrat ? `Gallrat · ${gallrat}` : 'Gallrat', tone: gallrat ? 'ok' : 'neutral', dest: 'gallra' },
      { key: 'live', label: `Live${liveL.suffix}`, tone: liveL.tone, dest: 'publicera' },
      { key: 'some', label: `SoMe${someL.suffix}`, tone: someL.tone, dest: 'publicera' },
      { key: 'webb', label: webb.label, tone: webb.tone, dest: 'innehall' },
    ]
  }
  async function goFromMatch(m, dest) {
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) return
    await sattAktivMatch(m.id)
    dispatch('gaTill', { match: m, dest })
  }

  // ── Sök, säsongsarkiv (demo: kalenderår ur datum) & paginering ────────────
  // Riktig säsongspartitionering + lazy-load per år är backend-arbete utanför
  // det här passet (se HANDOFF.md "Medvetet utanför / kvar") — här bucketas
  // matcherna client-side per kalenderår tills dess.
  const NU_AR = String(new Date().getFullYear())
  const norm = (s) => (s || '').toLowerCase()
  const matchesSok = (m, q) => !q || [m.lag_hemma, m.lag_borta, m.liga, m.arena].some((v) => norm(v).includes(q))

  // Nya utkast (id 'ny-…') saknar datum/sport/lag och skulle annars filtreras
  // bort av sport-, säsongs- och sökfiltren → "+ Ny match" verkar göra inget.
  // De passerar därför alltid och sorteras först (se sortDatum).
  //
  // Detsamma måste gälla en SPARAD match utan datum. Säsongsfiltret jämför
  // datum.slice(0,4) mot årtalet, och '' matchar inget år — så matchen skapades
  // men försvann ur listan i samma sekund den bytte utkast-id mot ett riktigt.
  // Symptomet: "listan laddar om och inget har skapats". Den ska synas, så att
  // man kan sätta datum eller ta bort den.
  const utanDatum = (m) => !(m.datum || '').trim()
  const alltidSynlig = (m) => arNy(m) || utanDatum(m)
  $: sportFiltrerade = matcher.filter((m) => arNy(m) || sportFilter === 'alla' || m.sport === sportFilter)
  $: matchArAlla = [...new Set(matcher.map((m) => (m.datum || '').slice(0, 4)).filter(Boolean))]
  $: aktivAr = matchArAlla.includes(NU_AR) ? NU_AR : ([...matchArAlla].sort().at(-1) || NU_AR)
  $: arkivAr = matchArAlla.filter((a) => a !== aktivAr).sort((a, b) => (a < b ? 1 : -1))
  $: aktivSasongCount = sportFiltrerade.filter((m) => (m.datum || '').slice(0, 4) === aktivAr).length
  $: sasong = matchSeasonSel || aktivAr
  $: iAktivSasong = sasong === aktivAr

  $: matchSearchQ = norm(matchSearch)
  $: sasongFiltrerade = sportFiltrerade
    .filter((m) => alltidSynlig(m) || (m.datum || '').slice(0, 4) === sasong)
    .filter((m) => alltidSynlig(m) || matchesSok(m, matchSearchQ))

  $: { matchSearch; matchSeasonSel; matchStatus; matchShowN = 12 }   // nollställ vid sök/säsongs-/statusbyte

  // Spelad = har ifyllt resultat (prototypens regel). Nya utkast och matcher
  // utan datum hör alltid hemma under Kommande — det är där de åtgärdas.
  $: nKommande = sasongFiltrerade.filter((m) => alltidSynlig(m) || !m.resultat).length
  $: nSpelade = sasongFiltrerade.filter((m) => !alltidSynlig(m) && !!m.resultat).length
  $: statusFiltrerade = sasongFiltrerade.filter((m) => matchStatus === 'spelade'
    ? (!alltidSynlig(m) && !!m.resultat)
    : (alltidSynlig(m) || !m.resultat))

  // Kommande: närmast först. Spelade: senast spelad först.
  $: datumSorterade = matchStatus === 'spelade' ? sortDatum(statusFiltrerade).reverse() : sortDatum(statusFiltrerade)
  $: datumSynliga = datumSorterade.slice(0, matchShowN)
  $: grupper = matchGroupBy === 'liga' ? grupperaLiga(statusFiltrerade)
    : matchGroupBy === 'sport' ? grupperaSport(statusFiltrerade)
    : grupperaDatum(datumSynliga)

  // ⚙ Filter-räknare: antal aktiva sällanfilter (sport + säsong).
  $: filterAntal = (sportFilter !== 'alla' ? 1 : 0) + (iAktivSasong ? 0 : 1)

  $: arkivLista = iAktivSasong ? [] : [...sasongFiltrerade].sort((a, b) => (a.datum < b.datum ? 1 : a.datum > b.datum ? -1 : 0))

  const GREN_ETIKETT = { dam: 'Dam', herr: 'Herr', mixed: 'Mixed' }
  // detalj (gren · sport) skiljer lag med samma namn åt (Malmö FF dam/herr).
  // Väljaren filtreras till matchens sport när den är känd (och till individ-
  // utövare för tennis), så man inte kan välja ett fotbollslag i en tennismatch.
  // Lag utan satt sport visas alltid (bakåtkomp. + inline-skapade). Är sporten
  // okänd (ny match utan tävling) visas allt — första valet sätter sporten.
  $: lagVal = (lagForTavling.length ? lagForTavling : lagAlla)
    .filter((l) => !utkast?.sport || !l.sport || l.sport === utkast.sport)
    .filter((l) => !uttagProfil.individ || !l.kind || l.kind === 'individ')
    .map((l) => ({
      id: l.id, namn: l.namn,
      detalj: [GREN_ETIKETT[l.gren], SPORT_ETIKETT[l.sport]].filter(Boolean).join(' · '),
    }))
  // Tävlingar kan finnas för både Dam och Herr (t.ex. European League 2026) →
  // visa gren · sport så man ser vilken man väljer.
  $: tavlingVal = tavlingar.map((t) => ({ id: t.id, namn: t.namn,
    detalj: [GREN_ETIKETT[t.gren], SPORT_ETIKETT[t.sport]].filter(Boolean).join(' · ') }))
  $: hemSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'hemma')
  $: bortaSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'borta')

  const del = (iso) => (iso || '').split('T')[0].split('-').map(Number)
  const harTid = (t) => /^\d{1,2}:\d{2}$/.test(t || '')
  const arNy = (x) => typeof x?.id === 'string' && x.id.startsWith('ny-')
  function plusMin(hhmm, min) {
    const [h, m] = hhmm.split(':').map(Number)
    const tot = (((h * 60 + m + min) % 1440) + 1440) % 1440
    return `${String(Math.floor(tot / 60)).padStart(2, '0')}:${String(tot % 60).padStart(2, '0')}`
  }
  const durEtikett = (min) => `${Math.floor(min / 60)} tim${min % 60 ? ` ${min % 60} min` : ''}`
  function slutFor(u) {
    if (!u || !harTid(u.tid)) return { slut: 'Heldag · tid ej fastställd', dur: 'sätts när avsparkstid är klar' }
    const d = MATCH_LANGD[u.sport] || 120
    return { slut: `slut ~${plusMin(u.tid, d)}`, dur: durEtikett(d) }
  }
  $: slutInfo = slutFor(utkast)
  $: oppenRad = matcher.find((x) => x.id === oppen)
  function periodText(t) {
    const f = (t.fran || ''), ti = (t.till || '')
    if (/^\d{4}-\d{2}/.test(f) && /^\d{4}-\d{2}/.test(ti)) {
      const a = f.split('-'), b = ti.split('-')
      const yr = b[0] === a[0] ? a[0] : `${a[0]}–${b[0]}`
      return `${MK[+a[1] - 1]}–${MK[+b[1] - 1]} ${yr}`
    }
    return f            // fri text ("apr–okt 2026")
  }
  function initialer(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }
  // #26: id-referensen vinner över namnet — Sverige finns som dam+herr (och
  // per sport), namn-uppslag kan träffa fel post (fel logga/färg/trupp).
  function lagPost(namn, id) {
    return (id && lagAlla.find((x) => x.id === id)) || lagAlla.find((x) => x.namn === namn)
  }
  function fargForLag(namn, id = null) {
    const l = lagPost(namn, id)
    return l ? (l.stall_hemma || l.profilfarg) : ''
  }
  function loggaForLag(namn, id = null) { return lagPost(namn, id)?.logga || '' }

  function grupperaLiga(lista) {
    const m = new Map()
    for (const x of lista) {
      const k = x.tavling_id || x.liga || 'ovrigt'
      if (!m.has(k)) m.set(k, { key: k, namn: x.liga || 'Övriga matcher', matcher: [] })
      m.get(k).matcher.push(x)
    }
    return [...m.values()].map((g) => {
      const t = tavlingar.find((tv) => tv.id === g.key || tv.namn === g.namn) || {}
      return { ...g, rich: true, badge: initialer(g.namn), typ: TYP_ETIKETT[t.typ] || 'Liga',
        meta: [SPORT_ETIKETT[t.sport] || '', periodText(t), t.ort].filter(Boolean).join(' · ') }
    })
  }

  // Matcher utan datum sorteras sist (nyckel '9999-99-99' vinner aldrig jämförelsen).
  function sortDatum(lista) {
    // Utkast ('ny-…') OCH sparade matcher utan datum först — de ryms alltid i
    // pagineringens första sida och är det man behöver åtgärda.
    const nyckel = (x) => alltidSynlig(x) ? '0000-00-00' : (x.datum && x.datum.length === 10) ? x.datum : '9999-99-99'
    return [...lista].sort((a, b) => (nyckel(a) < nyckel(b) ? -1 : nyckel(a) > nyckel(b) ? 1 : 0))
  }
  function grupperaDatum(lista) {
    const m = new Map()
    for (const x of lista) {
      const d = del(x.datum)
      const key = d.length === 3 ? `${d[0]}-${d[1]}` : 'zzz'
      const namn = d.length === 3 ? `${MANAD[d[1] - 1]} ${d[0]}` : 'Utan datum'
      if (!m.has(key)) m.set(key, { key, namn, matcher: [] })
      m.get(key).matcher.push(x)
    }
    return [...m.values()].map((g) => ({ ...g, rich: false }))
  }
  function grupperaSport(lista) {
    const m = new Map()
    for (const x of lista) {
      const key = x.sport || 'ovrig'
      if (!m.has(key)) m.set(key, { key, namn: SPORT_ETIKETT[x.sport] || 'Övrig sport', matcher: [] })
      m.get(key).matcher.push(x)
    }
    return [...m.values()].map((g) => ({ ...g, rich: false }))
  }

  async function toggla(m) {
    if (oppen === m.id) {
      // F18-6: en OSPARAD post har inget i databasen — spara fältdatat på
      // listraden vid kollaps så inget tappas och raden kan öppnas igen.
      if (String(m.id).startsWith('ny-') && utkast) {
        matcher = matcher.map((x) => (x.id === m.id ? { ...x, ...utkast } : x))
      }
      oppen = null; utkast = null; lagForTavling = []
      return
    }
    oppen = m.id
    // F18-6: osparad post → återställ ur listraden (hamtaMatch hittar den inte).
    utkast = String(m.id).startsWith('ny-')
      ? { spelare: [], ...m }
      : await hamtaMatch(m.id)
    await laddaLagForTavling(utkast.liga)
    slutFran(utkast)
  }
  async function laddaLagForTavling(ligaNamn) {
    // Id-refen vinner (BUG-01: två tävlingar kan heta lika) — namnet är
    // fallback för äldre matcher utan tavling_id.
    const t = tavlingar.find((x) => x.id === utkast?.tavling_id)
      || tavlingar.find((x) => x.namn === ligaNamn)
    lagForTavling = t ? await listaLagForTavling(t.id) : []
  }

  function nyMatch() {
    const tmp = { id: 'ny-' + Date.now(), datum: '', tid: '', arena: '', status: 'kommande', resultat: '', sport: '', lag_hemma: '', lag_borta: '', lag_hemma_id: null, lag_borta_id: null, liga: '', tavling_id: null, event_id: null, rond: '', event: false }
    matcher = [{ ...tmp, trupp_n: 0 }, ...matcher]
    matchStatus = 'kommande'                 // nya utkast bor under Kommande
    oppen = tmp.id; utkast = { ...tmp, spelare: [] }; lagForTavling = []
    slutFran(utkast)
  }

  async function valjTavling(o) {
    utkast.liga = o.namn
    // BUG-01: referera tävlingen med ID — två tävlingar kan heta lika
    // (European League dam/herr), namnet räcker inte för att peka rätt.
    utkast.tavling_id = o.id
    const t = tavlingar.find((x) => x.id === o.id)
    if (t?.sport) utkast.sport = t.sport
    await laddaLagForTavling(o.namn)
  }
  const skapaTavling = (namn) => { utkast.liga = namn; utkast.tavling_id = null; lagForTavling = [] }

  // ── Event-dörren (V5-C §2: "samma data, två dörrar") ─────────────────────
  // Tävlingsfältet ovan är liga-dörren (bär tavling_id som idag); det här
  // fältet sätter matchens event_id direkt — båda kan vara satta samtidigt
  // (seriematch som ingår i ett slutspels-event). "Skapa nytt" gör ett
  // event via tävlings-skrivytan (typ ovrigt — justeras sen i Event-sektionen).
  let eventer = []
  $: eventVal = eventer.map((e) => ({ id: e.id, namn: e.namn,
    sub: [e.typ, e.sport, e.fran].filter(Boolean).join(' · ') }))
  $: eventNamn = eventer.find((e) => e.id === utkast?.event_id)?.namn || ''
  const valjEvent = (o) => { utkast.event_id = o.id; utkast = utkast }
  const rensaEvent = () => { utkast.event_id = null; utkast = utkast }
  async function skapaEvent(namn) {
    const r = await sparaTavling({ namn, sport: utkast.sport || 'fotboll',
      typ: 'ovrigt' })
    if (r?.ok) { utkast.event_id = r.id; eventer = await listaEventer() }
  }
  // Utan vald tävling sätts matchens sport av den valda utövaren/laget (tävling
  // vinner annars, se valjTavling). Så en tennismatch utan tävling får sport=
  // tennis → rätt profil (individ-etiketter, ingen startelva) i stället för
  // fotbolls-fallbacken.
  function arvSportFran(id) {
    if (utkast.liga) return
    const l = lagAlla.find((x) => x.id === id)
    if (l?.sport) utkast = { ...utkast, sport: l.sport }
  }
  // Spara REF (lag-id), inte bara namnet — två lag kan heta lika (dam/herr).
  const valjHemma = (o) => { utkast.lag_hemma = o.namn; utkast.lag_hemma_id = o.id; arvSportFran(o.id) }
  const valjBorta = (o) => { utkast.lag_borta = o.namn; utkast.lag_borta_id = o.id; arvSportFran(o.id) }
  // p.5: heldagsevent visas utan motståndare (ingen efterhängande "– ").
  // F18-7: tom ny post får en riktig fallback-titel i stället för att rubriken
  // blir tom och "Heldag" ser ut som namn.
  const matchnamn = (m) => {
    const namn = (m?.event || !(m?.lag_borta || '').trim())
      ? (m?.lag_hemma || '') : `${m.lag_hemma} – ${m.lag_borta}`
    return namn || (m?.event ? 'Namnlöst event' : 'Ny match')
  }
  // p.5: heldagsevent = match utan motståndare. Slå på → rensa bortalaget.
  function sattEvent(v) {
    utkast = { ...utkast, event: v,
      ...(v ? { lag_borta: '', lag_borta_id: null } : {}) }
  }
  const skapaHemma = (namn) => { utkast.lag_hemma = namn; utkast.lag_hemma_id = null }
  const skapaBorta = (namn) => { utkast.lag_borta = namn; utkast.lag_borta_id = null }
  const arMatch = () => !utkast || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))

  // ── §3: Slutsignal — skriv resultatet en gång, på matchen ─────────────────
  let slutOpen = false
  let slutForm = { resultat: '', mellan: '', malskyttar: '', mkLive: true, mkSome: true, mkWeb: true }
  function slutFran(m) {
    slutOpen = false
    slutForm = { resultat: m?.resultat || '', mellan: m?.mellan || '', malskyttar: m?.malskyttar || '',
      mkLive: true, mkSome: true, mkWeb: true }
  }
  function slutSet(f, v) {
    slutForm = { ...slutForm, [f]: v }
    // Resultat/mellan/målskyttar hör till MATCHEN, inte bara till Slutsignal-
    // formuläret. Spegla in dem i utkast så att BÅDE "Spara & skapa utkast"
    // och den vanliga "Spara"-knappen persisterar dem. Utan detta tappades ett
    // resultat som skrevs i Slutsignalen tyst så fort man committade med den
    // vanliga Spara-knappen (som sparar utkast, inte slutForm).
    if (f === 'resultat' || f === 'mellan' || f === 'malskyttar') {
      utkast = { ...utkast, [f]: v }
    }
  }
  async function slutSave() {
    if (arMatch()) return
    const m = { ...utkast, resultat: slutForm.resultat, mellan: slutForm.mellan,
      malskyttar: slutForm.malskyttar }
    await sparaMatch(m)
    const namn = `${m.lag_hemma} – ${m.lag_borta}`
    if (slutForm.mkLive) {
      await sparaMaterial({ kind: 'live', status: 'utkast', match_id: m.id, match_namn: namn,
        moment: 'Resultat', tema: 'Hav', dropbox: '', foto: null })
    }
    if (slutForm.mkSome) {
      await sparaMaterial({ kind: 'some', status: 'utkast', match_id: m.id, match_namn: namn,
        channels: ['story', 'ig'], caption: `${slutForm.resultat} · ${namn}${m.liga ? ' · ' + m.liga : ''}`,
        banor: { story: { mapp: '', bilder: [] }, ig: { mapp: '', bilder: [] }, fb: { mapp: '', bilder: [] } } })
    }
    if (slutForm.mkWeb) {
      await sparaInnehall({ typ: 'match', match_id: m.id, hem: m.lag_hemma, borta: m.lag_borta,
        serie: m.liga, sport: m.sport, datum: m.datum, arena: m.arena, resultat: m.resultat,
        mellan: m.mellan, malskyttar: m.malskyttar, status: 'avslutad', pixieset: m.galleri })
    }
    await sattAktivMatch(m.id)
    ;[matcher] = await Promise.all([listaMatcher()])
    utkast = m; slutOpen = false
  }

  // ── §7: Importera spelschema (riktig hämtning via Claude-tjänsten) ────────
  let importOpen = false
  let importLag = ''
  let importUrl = ''
  let importSport = ''
  let importRader = []
  let importLaddar = false
  let importFel = ''
  let importSkapaFotojobb = true
  let importKor_ = false
  // F18-3: klistra-in-JSON-läget (färdiga spelscheman) + krock-resultat.
  let importJson = ''
  let importJsonRes = null
  // Grenen för HELA den inklistrade filen. Svenska herrserier är omärkta
  // ("Elitserien" = herr, "Elitserien Damer" = dam), så den går inte att
  // härleda ur liganamnet — utan valet faller herrlagen ihop med damlagen.
  let importGren = ''

  function importVaxla() {
    importOpen = !importOpen
    if (!importOpen) { importRader = []; importFel = ''; importJson = ''; importJsonRes = null }
    else tick().then(() => document.querySelector('.importkort')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  async function importHamta() {
    if (!importLag.trim()) { importFel = 'Ange ett lag.'; return }
    importFel = ''; importLaddar = true; importRader = []
    const r = await hamtaSpelschema(importLag.trim(), importUrl.trim(), importSport)
    importLaddar = false
    if (!r?.ok) { importFel = r?.fel || 'Kunde inte hämta spelschemat.'; return }
    importRader = (r.matcher || []).map((m) => {
      const hem = m.hemma ? importLag.trim() : m.motstandare
      const bort = m.hemma ? m.motstandare : importLag.trim()
      const dubblett = matcher.some((x) => x.datum === m.datum &&
        ((x.lag_hemma === hem && x.lag_borta === bort) || (x.lag_hemma === bort && x.lag_borta === hem)))
      return { ...m, hem, bort, dubblett, checked: !dubblett }
    })
    if (!importRader.length) importFel = 'Inga kommande matcher hittades.'
  }
  function importToggleRad(i) {
    if (importRader[i].dubblett) return
    importRader[i] = { ...importRader[i], checked: !importRader[i].checked }
    importRader = importRader
  }
  $: importValda = importRader.filter((r) => r.checked && !r.dubblett)
  async function importGenomfor() {
    if (!importValda.length || importKor_) return
    importKor_ = true
    for (const r of importValda) {
      const res = await sparaMatch({ lag_hemma: r.hem, lag_borta: r.bort, datum: r.datum,
        tid: r.tid || '', arena: r.arena || '', liga: r.liga || '', sport: importSport || '' })
      if (importSkapaFotojobb && res?.id) await sattMatchSynk(res.id, true)
    }
    matcher = await listaMatcher()
    importKor_ = false; importOpen = false; importRader = []; importLag = ''; importUrl = ''
  }

  // F18-3: importera ett färdigt spelschema (JSON-lista). Idempotent i backend;
  // visar counts + krockar (du väljer lag på krockdatum — ena/andra/båda).
  async function importFranJson() {
    importFel = ''; importJsonRes = null
    if (!importJson.trim()) { importFel = 'Klistra in ett spelschema (JSON) först.'; return }
    let fixtures
    try { fixtures = JSON.parse(importJson) }
    catch (e) { importFel = 'Ogiltig JSON: ' + (e?.message || e); return }
    if (!Array.isArray(fixtures)) { importFel = 'JSON ska vara en lista [ {…}, {…} ].'; return }
    importKor_ = true
    try {
      importJsonRes = await importeraSpelschema(fixtures, null, importGren || null)
      matcher = await listaMatcher()
    } catch (e) {
      importFel = 'Import misslyckades: ' + (e?.message || e)
    } finally {
      importKor_ = false
    }
  }

  let hamtar = false
  async function lasUttag(sida) {
    if (arMatch()) return
    // Etiketten följer sportprofilen — "startelva" är fotboll; volleyboll
    // har startsexa, handboll startsju osv.
    const f = await valjFil(`Välj ${lineupLc()} (matchblad/CSV/foto)`)
    if (!f.ok) return
    hamtar = true
    const res = await lasUttagFil(utkast.id, f.path, sida)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }
  const truppStorlek = (namn, id = null) => lagPost(namn, id)?.trupp_n || 0
  const truppNot = (namn, id = null) => {
    const n = truppStorlek(namn, id)
    return n ? `ur trupp · ${n} spelare` : 'ingen trupp i Lag & ligor'
  }
  const lineupLc = () => (uttagProfil.lineup || 'startuppställning').toLowerCase()
  const startelvaEtikett = (namn, nStart, id = null) => {
    if (!nStart) return 'ej uppladdad'
    const n = truppStorlek(namn, id)
    return n ? `${nStart} av ${n}` : `${nStart} spelare`
  }
  async function hamtaTruppen() {
    if (arMatch()) return
    hamtar = true
    const res = await hamtaTrupp(utkast.id)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }

  async function togglaSynk(m) {
    if (!m || arNy(m)) return
    fel = ''
    const r = await sattMatchSynk(m.id, !m.synk_jobb_id)
    if (!r?.ok) { fel = r?.fel || 'Kunde inte ändra kalendersynken.'; return }
    matcher = matcher.map((x) => (x.id === m.id ? { ...x, synk_jobb_id: r.synk_jobb_id } : x))
  }

  async function taBort(m) {
    bekraftaId = null
    fel = ''
    if (!arNy(m)) {
      const r = await raderaMatch(m.id)
      if (!r?.ok) { fel = r?.fel || 'Kunde inte ta bort matchen.'; return }
    }
    if (oppen === m.id) { oppen = null; utkast = null; lagForTavling = [] }
    matcher = matcher.filter((x) => x.id !== m.id)
  }

  async function spara() {
    const m = { ...utkast }
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) delete m.id
    fel = ''
    // Resultatet ignorerades tidigare: ett backend-fel blev "listan laddade om
    // och inget hände", utan förklaring.
    let r
    try {
      r = await sparaMatch(m)
    } catch (e) {
      fel = 'Kunde inte spara matchen.'; return
    }
    if (r && r.ok === false) { fel = r.fel || 'Kunde inte spara matchen.'; return }
    ;[matcher, lagAlla] = await Promise.all([listaMatcher(), listaLag()])
    oppen = null; utkast = null; lagForTavling = []
  }
  async function aktivera(m) {
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) return
    await sattAktivMatch(m.id)      // persistera FÖRE navigering — annars hinner
    dispatch('aktiverad', m)        // Gallra/Leverera/Publicera fråga aktivMatch() för tidigt
  }
  // BUG-02: projkorten var döda — dispatch('navigera') hade ingen lyssnare i
  // App, och projektets urval valdes aldrig. Nu: aktivera urvalet → Leverera.
  async function aterUppta(pr) {
    if (pr?.id) {
      await sattAktivtUrval(pr.id)
      dispatch('urval')                       // uppdatera topbar-widgeten
    }
    dispatch('navigera', 'leverera')
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Matcher</h1>
    <span class="sub">Planera kommande matcher och återuppta tidigare projekt</span>
    <!-- 7A: skapa-knapparna i rubrikraden, utanför den scrollande listan. -->
    <div class="huvudknappar">
      <button class="ny sek2" on:click={importVaxla}>Importera spelschema</button>
      <button class="ny" on:click={nyMatch}>+ Ny match</button>
    </div>
  </header>

  <!-- 6a: EN verktygsrad — statusflikar + gruppering + sök; sällanfilter
       (sport + säsong) bakom ⚙ Filter med räknare. -->
  <div class="toolrad">
    <div class="seg statusseg">
      <button class:on={matchStatus === 'kommande'} on:click={() => (matchStatus = 'kommande')}>Kommande · {nKommande}</button>
      <button class:on={matchStatus === 'spelade'} on:click={() => (matchStatus = 'spelade')}>Spelade · {nSpelade}</button>
    </div>
    <div class="seg">
      <button class:on={matchGroupBy === 'datum'} on:click={() => (matchGroupBy = 'datum')}>Datum</button>
      <button class:on={matchGroupBy === 'liga'} on:click={() => (matchGroupBy = 'liga')}>Liga/Tävling</button>
      <button class:on={matchGroupBy === 'sport'} on:click={() => (matchGroupBy = 'sport')}>Sport</button>
    </div>
    <div class="sokbox">
      <svg class="sokik" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input bind:value={matchSearch} placeholder="Sök lag, liga eller arena…" />
    </div>
    <div class="filterwrap">
      <button class="filterbtn" class:aktivt={filterAntal > 0}
        on:click={() => (matchFilterOpen = !matchFilterOpen)}>⚙ Filter{filterAntal ? ` · ${filterAntal}` : ''}</button>
      {#if matchFilterOpen}
        <button class="popskarm" on:click={() => (matchFilterOpen = false)} aria-label="stäng"></button>
        <div class="filterpop">
          <div class="fpcaps">Sport</div>
          <div class="chips">
            {#each SPORTER as s}
              <button class="chip" class:on={sportFilter === s} on:click={() => (sportFilter = s)}>{s === 'alla' ? 'Alla' : SPORT_ETIKETT[s]}</button>
            {/each}
          </div>
          <div class="fpcaps">Säsong</div>
          <div class="sasongchips">
            <button class="sasong" class:on={iAktivSasong} on:click={() => (matchSeasonSel = null)}>{aktivAr} · {aktivSasongCount}</button>
            {#each arkivAr as ar (ar)}
              <button class="sasong arkiv" class:on={sasong === ar} on:click={() => (matchSeasonSel = ar)}>{ar}</button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>

  {#if fel}<p class="fel">{fel}</p>{/if}

  {#if laddar}
    <p class="tom">Laddar matcher…</p>
  {:else if !iAktivSasong}
    <div class="arkivhuvud scd">Arkiv · säsong {sasong} · {arkivLista.length} matcher</div>
    {#if !arkivLista.length}
      <p class="tom">Inga matcher hittades i den här säsongen.</p>
    {:else}
      <div class="arkivlista">
        {#each arkivLista as m (m.id)}
          <div class="arkivrad" style="border-left:3px {m.hem_gren ? 'solid' : 'dashed'} {grenFarg(m.hem_gren)}">
            <div class="adatum scd">
              <span class="ad">{del(m.datum)[2] || '–'}</span>
              <span class="amon">{del(m.datum).length === 3 ? MK[del(m.datum)[1] - 1] : ''}</span>
            </div>
            <div class="afixtur">
              <div class="afx scd">{matchnamn(m)}
                {#if m.event}<span class="grenlbl scd" style="color:var(--acc)">Tävling</span>{/if}
                {#if m.hem_gren}<span class="grenlbl scd" style="color:{grenFarg(m.hem_gren)}">{grenEtikett(m.hem_gren)}</span>{/if}
              </div>
              <div class="ameta">{[m.liga, m.arena, m.resultat ? `slutresultat ${m.resultat}` : ''].filter(Boolean).join(' · ')}</div>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    {#if projekt.length}
      <div class="caps proj">Tidigare projekt</div>
      <!-- F18-8: kompakta rader, grupperade per match, 3 + Visa alla -->
      <ProjektLista {projekt} on:ateruppta={(e) => aterUppta(e.detail)} />
    {/if}
  {:else}
    <div class="grupper">
      {#each grupper as g (g.key)}
        <div class="grupp">
          {#if g.rich}
            <div class="ghuvud">
              <span class="glogo scd" style="background:{SPORT_FARG}">{g.badge}</span>
              <div class="gtxt">
                <div class="gnamn">{g.namn}</div>
                <div class="gmeta">{g.meta}</div>
              </div>
              <span class="gtyp">{g.typ}</span>
            </div>
          {:else}
            <div class="manad scd">{g.namn}</div>
          {/if}

          <div class="matcher">
            {#each g.matcher as m (m.id)}
              <div class="match"
                style="border-left:3px {m.hem_gren ? 'solid' : 'dashed'} {grenFarg(m.hem_gren)}">
                <Hornmarkor farg={m.synk_jobb_id ? synkFarg('synkad') : ''} r={12}
                  titel={m.synk_jobb_id ? 'Synkad med Google Kalender' : ''} />
                <div class="rad" role="button" tabindex="0" on:click={() => toggla(m)}
                  on:keydown={(e) => e.key === 'Enter' && toggla(m)}>
                  <div class="datum scd">
                    <div class="d">{del(m.datum)[2] || '–'}</div>
                    <div class="mon">{del(m.datum).length === 3 ? MK[del(m.datum)[1] - 1] : ''}</div>
                  </div>
                  <div class="fixtur">
                    <div class="fx scd">{matchnamn(m)}</div>
                    <div class="fmeta">
                      {#if m.hem_gren}<span class="grenlbl scd" style="color:{grenFarg(m.hem_gren)}">{grenEtikett(m.hem_gren)}</span>{/if}
                      <!-- Listjusteringar: liga + arena i metaraden (ligan doldes
                           annars helt när listan grupperas på datum). -->
                      <!-- F18-7: badgen ensam markerar heldag — utskrivna "Heldag" i metaraden
                           dubblerade den. -->
                      <span>{[SPORT_ETIKETT[m.sport] || '', m.liga, m.arena, harTid(m.tid) ? m.tid : ''].filter(Boolean).join(' · ')}</span>
                      {#if !harTid(m.tid)}<span class="heldagstagg">Heldag</span>{/if}
                    </div>
                  </div>
                  <!-- Listjusteringar §3: "Planera"-etiketten borta — radklick öppnar
                       redigeringen, ingen separat åtgärd behövs. Resultatchip så
                       fort resultat finns; annars "Roster klar" när truppen är inne. -->
                  {#if m.resultat}
                    <span class="status res scd">{m.resultat}</span>
                  {:else if m.trupp_n > 0}
                    <span class="status klar">Roster klar</span>
                  {/if}
                  <button class="papperskorg" title="Ta bort match"
                    on:click|stopPropagation={() => (bekraftaId = m.id)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg>
                  </button>
                  <span class="chev" class:upp={oppen === m.id}>›</span>
                </div>

                {#if bekraftaId === m.id}
                  <div class="bekrafta">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#C0453E" stroke-width="1.8"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg>
                    <div class="btxt">Ta bort <b>{matchnamn(m)}</b>? Kan inte ångras.</div>
                    <button class="bavbryt" on:click={() => (bekraftaId = null)}>Avbryt</button>
                    <button class="bta" on:click={() => taBort(m)}>Ta bort</button>
                  </div>
                {/if}

                {#if oppen === m.id && utkast}
                  <div class="editor">
                    <div class="navchips">
                      {#each navChips(utkast) as c (c.key)}
                        <button class="navchip" class:ok={c.tone === 'ok'} class:draft={c.tone === 'draft'}
                          class:delvis={c.tone === 'delvis'}
                          class:accent={c.tone === 'accent'} on:click={() => goFromMatch(utkast, c.dest)}>{c.label}</button>
                      {/each}
                    </div>
                    <!-- F18-5: kompakt vänsterställd toggle — hjälptexten bor i
                         tooltip så raden inte konkurrerar med HELDAG-badgen. -->
                    <label class="eventtogg"
                      title="Cup, mästerskap, läger… — matchen har inget bortalag; tävlingsnamnet blir rubriken.">
                      <input type="checkbox" checked={!!utkast.event} on:change={(e) => sattEvent(e.target.checked)} />
                      <span>Heldag <span class="eventmut">(utan motståndare)</span></span>
                    </label>
                    <div class="rad2" class:enkel={utkast.event}>
                      <label>{utkast.event ? 'Tävlingsnamn' : (uttagProfil.individ ? 'Spelare 1' : 'Hemmalag')}
                        <Combobox options={lagVal} value={utkast.lag_hemma} placeholder={uttagProfil.individ ? 'Välj spelare…' : 'Välj lag…'}
                          on:pick={(e) => valjHemma(e.detail)} on:create={(e) => skapaHemma(e.detail)} />
                      </label>
                      {#if !utkast.event}
                        <label>{uttagProfil.individ ? 'Spelare 2' : 'Bortalag'}
                          <Combobox options={lagVal} value={utkast.lag_borta} placeholder={uttagProfil.individ ? 'Välj spelare…' : 'Välj lag…'}
                            on:pick={(e) => valjBorta(e.detail)} on:create={(e) => skapaBorta(e.detail)} />
                        </label>
                      {/if}
                    </div>
                    <label class="full">Liga / Tävling
                      <Combobox options={tavlingVal} value={utkast.liga} placeholder="Välj tävling…"
                        on:pick={(e) => valjTavling(e.detail)} on:create={(e) => skapaTavling(e.detail)} />
                    </label>
                    <!-- V5-C: andra dörren — matchen kan ingå i en tävling
                         (mästerskap/cup/turnering) oberoende av ligan.
                         D11b §1: 'Event' försvinner ur UI, visas som Tävling. -->
                    <label class="full">Tävling
                      <div class="eventdorr">
                        <Combobox options={eventVal} value={eventNamn} placeholder="Del av tävling…"
                          on:pick={(e) => valjEvent(e.detail)} on:create={(e) => skapaEvent(e.detail)} />
                        {#if utkast.event_id}
                          <button type="button" class="eventrensa" title="Koppla bort tävlingen"
                            on:click={rensaEvent}>✕</button>
                        {/if}
                      </div>
                    </label>
                    {#if uttagProfil.individ}
                      <!-- D1: turneringsrond — stora ordet i story-overlayn (visas versalt). -->
                      <label class="full">Rond
                        <input bind:value={utkast.rond} placeholder="t.ex. Åttondel, Kvartsfinal, Semifinal, Final" />
                      </label>
                    {/if}
                    <div class="rad3">
                      <input type="date" bind:value={utkast.datum} />
                      <input type="time" bind:value={utkast.tid} />
                      <div class="slutkol">
                        <span class="slut">{slutInfo.slut}</span>
                        <span class="slutdur">{slutInfo.dur}</span>
                      </div>
                      <input bind:value={utkast.arena} placeholder="Arena" />
                    </div>

                    {#if uttagProfil.squad}
                      <div class="uttagrad"><span class="caps2">Matchdaguttag</span><span class="uttagnot">kopplat till matchen</span></div>
                      <div class="lagbox2">
                        {#each (utkast.event ? [{ sida: 'hemma', namn: utkast.lag_hemma, id: utkast.lag_hemma_id, lista: hemSpelare }] : [{ sida: 'hemma', namn: utkast.lag_hemma, id: utkast.lag_hemma_id, lista: hemSpelare }, { sida: 'borta', namn: utkast.lag_borta, id: utkast.lag_borta_id, lista: bortaSpelare }]) as kol}
                          {@const nStart = kol.lista.filter((p) => p.start).length}
                          <div class="lbox">
                            <div class="lhuvud">
                              <Lagbricka namn={kol.namn} farg={fargForLag(kol.namn, kol.id)} logga={loggaForLag(kol.namn, kol.id)} storlek={30} />
                              <div class="lnamn-wrap">
                                <div class="lnamn scd">{kol.namn || (kol.sida === 'hemma' ? 'Hemmalag' : 'Bortalag')}</div>
                                <div class="lsub">{kol.sida === 'hemma' ? 'Hemma' : 'Borta'} · {truppNot(kol.namn, kol.id)}</div>
                              </div>
                            </div>
                            <div class="grupplbl">{uttagProfil.lineup} <span class="grupplbl-sub">· delmängd av truppen</span></div>
                            <button class="lbtn" class:i={nStart > 0} on:click={() => lasUttag(kol.sida)} disabled={hamtar || arMatch()}>
                              <span>{nStart ? 'Byt fil…' : `Ladda upp ${lineupLc()}…`}</span>
                              <span class="lbtn-n">{startelvaEtikett(kol.namn, nStart, kol.id)}</span>
                            </button>
                          </div>
                        {/each}
                      </div>
                      <div class="hint">Hela truppen kommer från <b>Lag &amp; tävlingar</b>. {uttagProfil.lineup} är en delmängd som läses ur matchblad/CSV/foto strax innan match — matchas mot lagets trupp och sparas på matchen. <button class="lank" on:click={hamtaTruppen} disabled={hamtar || arMatch()}>{hamtar ? 'Hämtar…' : 'Hämta trupp automatiskt'}</button></div>
                    {:else}
                      <div class="uttagrad"><span class="caps2">Matchdaguttag</span></div>
                      <div class="hint">Individuell sport — inga trupper eller startuppställningar för {SPORT_ETIKETT[utkast.sport] || 'den här sporten'}.</div>
                    {/if}

                    <div class="gcalkort">
                      <span class="gcalik">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                      </span>
                      <div class="gcaltxt">
                        <div class="gt">Lägg i kalender</div>
                        <div class="gs">Lägg matchen i din Google Calendar så du har koll på uppdraget</div>
                      </div>
                      <button class="gcalbtn" class:i={!!oppenRad?.synk_jobb_id}
                        on:click={() => !oppenRad?.synk_jobb_id && togglaSynk(oppenRad)} disabled={arMatch()}>
                        {oppenRad?.synk_jobb_id ? 'I kalendern ✓' : 'Lägg i kalender ›'}
                      </button>
                    </div>

                    <div class="lankblock">
                      <span class="caps2">Efter match · länkar</span>
                      <div class="rad2">
                        <label>Pixieset-galleri
                          <input bind:value={utkast.galleri} placeholder="https://…pixieset.com/…" />
                        </label>
                        <label>Publicerad hemsideslänk
                          <input bind:value={utkast.sida_url} placeholder="https://dalecarliaphoto.se/…" />
                        </label>
                      </div>
                    </div>

                    <div class="slutblock">
                      <button class="sluthuvud" on:click={() => (slutOpen = !slutOpen)} disabled={arMatch()}>
                        <span class="caps2">Slutsignal</span>
                        <span class="uttagnot">skriv resultatet en gång</span>
                        <span class="slutchevron">{slutOpen ? '▴' : '▾'}</span>
                      </button>
                      {#if slutOpen}
                        <div class="slutform">
                          <div class="rad3">
                            <label>{uttagProfil.res_label || 'Resultat'}
                              <input value={slutForm.resultat} placeholder={uttagProfil.res_ph}
                                on:input={(e) => slutSet('resultat', e.target.value)} />
                            </label>
                            <label>{uttagProfil.mid_label || 'Halvtid'}
                              <input value={slutForm.mellan} placeholder={uttagProfil.mid_ph}
                                on:input={(e) => slutSet('mellan', e.target.value)} />
                            </label>
                            {#if uttagProfil.has_scorers}
                              <label>{uttagProfil.scorers_label || 'Målskyttar'}
                                <input value={slutForm.malskyttar} placeholder="Efternamn, efternamn…"
                                  on:input={(e) => slutSet('malskyttar', e.target.value)} />
                              </label>
                            {/if}
                          </div>
                          <div class="slutkryss">
                            <label><input type="checkbox" checked={slutForm.mkLive}
                              on:change={(e) => slutSet('mkLive', e.target.checked)} /> Resultat-story (Live)</label>
                            <label><input type="checkbox" checked={slutForm.mkSome}
                              on:change={(e) => slutSet('mkSome', e.target.checked)} /> SoMe-paket med ifylld bildtext</label>
                            <label><input type="checkbox" checked={slutForm.mkWeb}
                              on:change={(e) => slutSet('mkWeb', e.target.checked)} /> Webb-utkast (match-md)</label>
                          </div>
                          <div class="hint">Skriver värdena på matchen och skapar valda utkast utan bildval — öppnas tomma i respektive flik. Inget publiceras.</div>
                          <button class="prim" on:click={slutSave}>Spara &amp; skapa utkast ›</button>
                        </div>
                      {/if}
                    </div>

                    <div class="knappar">
                      <button class="prim" on:click={() => aktivera(utkast)}>Aktivera match ›</button>
                      <button class="sek" on:click={spara}>Spara</button>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}

      {#if matchGroupBy === 'datum' && datumSorterade.length > matchShowN}
        <div class="pagineringsrad">
          <button class="visafler" on:click={() => (matchShowN += 12)}>Visa 12 till ›</button>
          <span class="visarinfo">visar {datumSynliga.length} av {datumSorterade.length}</span>
        </div>
      {/if}

      {#if importOpen}
        <div class="importkort">
          <div class="caps">Importera spelschema</div>
          <div class="rad3">
            <label>Lag<input bind:value={importLag} placeholder="t.ex. Malmö FF" /></label>
            <label>URL (valfri)<input class="mono" bind:value={importUrl} placeholder="https://…/matcher" /></label>
            <label>Sport
              <select bind:value={importSport}>
                <option value="">Auto</option>
                {#each SPORTER.filter((s) => s !== 'alla') as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
              </select>
            </label>
          </div>
          <button class="sek" on:click={importHamta} disabled={importLaddar}>{importLaddar ? 'Hämtar…' : 'Hämta ›'}</button>
          {#if importFel}<div class="importfel">⚠ {importFel}</div>{/if}

          {#if importRader.length}
            <div class="importlista">
              {#each importRader as r, i}
                <button class="importrad" class:dubblett={r.dubblett} disabled={r.dubblett}
                  on:click={() => importToggleRad(i)}>
                  <span class="box" class:pa={r.checked}>{r.checked ? '✓' : ''}</span>
                  <span class="irtxt">
                    <span class="irfix">{r.hem} – {r.bort}</span>
                    <span class="irsub">{r.datum}{r.tid ? ' · ' + r.tid : ''}{r.arena ? ' · ' + r.arena : ''}{r.liga ? ' · ' + r.liga : ''}</span>
                  </span>
                  {#if r.dubblett}<span class="irdub">finns redan</span>{/if}
                </button>
              {/each}
            </div>
            <button class="chk" on:click={() => (importSkapaFotojobb = !importSkapaFotojobb)}>
              <span class="box" class:pa={importSkapaFotojobb}>{importSkapaFotojobb ? '✓' : ''}</span>
              Skapa även fotojobb i kalendern (kategori Sport)
            </button>
            <button class="prim" on:click={importGenomfor} disabled={!importValda.length || importKor_}>
              {importKor_ ? 'Importerar…' : `Importera ${importValda.length} matcher`}
            </button>
          {/if}

          <div class="importeller">— eller klistra in ett färdigt spelschema (JSON) —</div>
          <textarea class="mono importjson" rows="4" bind:value={importJson}
            placeholder={'[{"league":"Handbollsligan","sport":"handboll","home_team":"HK Malmö","away_team":"…","date":"2026-09-26","kickoff":"16:00"}]'}></textarea>
          <div class="importgren">
            <span class="caps">Gren</span>
            {#each [['dam', 'Dam'], ['herr', 'Herr'], ['mixed', 'Mixed']] as [v, etikett]}
              <button class="grenval" class:pa={importGren === v}
                on:click={() => (importGren = importGren === v ? '' : v)}>{etikett}</button>
            {/each}
            <span class="grennot">
              {importGren ? 'sätts på alla lag i filen' : 'härleds ur liganamnet — "Elitserien" blir grenlös'}
            </span>
          </div>
          <button class="prim" on:click={importFranJson} disabled={importKor_}>
            {importKor_ ? 'Importerar…' : 'Importera JSON ›'}
          </button>
          {#if importFel}<div class="importfel">⚠ {importFel}</div>{/if}

          {#if importJsonRes}
            <div class="importresultat">
              ✓ {importJsonRes.skapade} skapade · {importJsonRes.uppdaterade} uppdaterade{importJsonRes.hoppade ? ` · ${importJsonRes.hoppade} hoppade` : ''}
            </div>
            {#if importJsonRes.krockar?.length}
              <div class="krockrubrik">⚠ {importJsonRes.krockar.length} krockdatum — förslag markerat, du väljer:</div>
              {#each importJsonRes.krockar as k}
                <div class="krock">
                  <span class="krockdatum">{k.datum}</span>
                  {#each k.alternativ as alt, ai}
                    <span class="krockalt" class:forslag={ai === 0}>
                      {alt.arena}{ai === 0 ? ' ★' : ''} · {alt.matcher.map((m) => `${m.hemma}–${m.borta}`).join(' + ')}
                    </span>
                  {/each}
                </div>
              {/each}
            {/if}
          {/if}
        </div>
      {/if}
    </div>

    {#if projekt.length}
      <div class="caps proj">Tidigare projekt</div>
      <!-- F18-8: kompakta rader, grupperade per match, 3 + Visa alla -->
      <ProjektLista {projekt} on:ateruppta={(e) => aterUppta(e.detail)} />
    {/if}
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 920px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--t-head); }   /* 6a: paneltitel 20px */
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: var(--t-caps); }
  .seg { display: flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; }
  .seg button { padding: 7px 14px; border: 0; border-radius: 7px; background: transparent;
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .seg button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { padding: 5px 13px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; }
  .chip.on { background: var(--acc); border-color: var(--acc); color: #fff; font-weight: 600; }

  /* 6a: EN verktygsrad — statusflikar + gruppering + sök + ⚙ Filter */
  .toolrad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 18px 2px 16px; }
  .statusseg button.on { color: var(--acc); }
  .filterwrap { position: relative; flex: none; }
  .filterbtn { padding: 8px 14px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .filterbtn:hover { border-color: var(--acc); color: var(--acc); }
  .filterbtn.aktivt { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .popskarm { position: fixed; inset: 0; z-index: 30; background: transparent; border: 0; }
  .filterpop { position: absolute; top: calc(100% + 6px); right: 0; z-index: 31; width: 340px;
    background: var(--kort); border: 1px solid var(--div); border-radius: 12px; box-shadow: var(--skugga); padding: 14px; }
  .fpcaps { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--t-caps); margin: 0 0 8px; }
  .fpcaps:not(:first-child) { margin-top: 14px; }
  .filterpop .chips, .filterpop .sasongchips { flex-wrap: wrap; }
  .sokbox { flex: 1; min-width: 220px; display: flex; align-items: center; gap: 8px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort); padding: 8px 14px; }
  .sokik { width: 15px; height: 15px; color: var(--t-help); flex: none; }
  .sokbox input { flex: 1; min-width: 0; border: 0; background: transparent; padding: 0;
    font-size: 13px; color: var(--t-head); outline: none; }
  .sasongchips { display: flex; gap: 6px; flex: none; }
  .sasong { padding: 7px 14px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .sasong.on { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .sasong.arkiv.on { background: var(--div3); border-color: var(--div); color: var(--t-head); }

  /* Arkivvy: platt, icke-expanderbar lista */
  .arkivhuvud { font-size: 13px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--t-mut); margin: 4px 2px 12px; }
  .arkivlista { display: flex; flex-direction: column; gap: 8px; }
  .arkivrad { display: flex; align-items: center; gap: 14px; background: var(--kort); border: 1px solid var(--div);
    border-radius: var(--r); box-shadow: var(--skugga); padding: 8px 12px; }
  .adatum { width: 36px; flex: none; text-align: center; }
  .adatum .ad { font-size: 17px; font-weight: 700; color: var(--t-head); line-height: 1; display: block; }
  .adatum .amon { font-size: 9px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-help); }
  .afixtur { flex: 1; min-width: 0; }
  .afx { font-size: 14.5px; font-weight: 700; color: var(--t-head); display: flex; align-items: center; gap: 7px; }
  .ameta { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }

  /* Paginering (Datum-vyn) */
  .pagineringsrad { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 4px; }
  .visafler { padding: 8px 16px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-head); font-size: 12.5px; font-weight: 600; }
  .visafler:hover { border-color: var(--acc); color: var(--acc); }
  .visarinfo { font-size: 11px; color: var(--t-help); }

  .grupper { display: flex; flex-direction: column; gap: 20px; }
  .manad { font-weight: 700; font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--t-mut); margin-bottom: 10px; }
  .ghuvud { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .glogo { width: 34px; height: 34px; border-radius: 8px; color: #fff; display: flex; align-items: center;
    justify-content: center; flex: none; font-size: 12px; font-weight: 700; }
  .gtxt { flex: 1; min-width: 0; }
  .gnamn { font-size: 14px; font-weight: 600; color: var(--t-head); }
  .gmeta { font-size: 11.5px; color: var(--t-mut); }
  .gtyp { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--t-mut); background: var(--div3); padding: 3px 9px; border-radius: 6px; flex: none; }

  .matcher { display: flex; flex-direction: column; gap: 10px; }
  .match { position: relative; background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); overflow: hidden; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%; padding: 8px 12px; border: 0;
    background: transparent; text-align: left; cursor: pointer; }
  .rad:hover { background: var(--div3); }
  .datum { width: 36px; flex: none; text-align: center; }
  .datum .d { font-size: 17px; font-weight: 700; color: var(--acc); line-height: 1; }
  .datum .mon { font-size: 9px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--acc); margin-top: 1px; }
  .fixtur { flex: 1; min-width: 0; }
  .fx { font-size: 14.5px; font-weight: 700; color: var(--t-head); }
  .fmeta { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--t-mut); margin-top: 2px; }
  .grenlbl { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; flex: none; }
  .heldagstagg { font-size: 9.5px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--acc); background: var(--acc-soft); padding: 2px 7px; border-radius: 5px; flex: none; }
  .status { font-size: 13px; font-weight: 600; color: var(--t-mut); flex: none; }
  .status.klar { color: var(--ok); }
  .status.res { font-size: 20px; font-weight: 700; color: var(--t-head); }
  /* A2: kalendersynk visas nu som <Hornmarkor> (hörnbåge) — synkpillen borttagen.
     Synk togglas i den utfällda editorn ("Lägg i kalender") + Kalender-chippet. */
  .navchips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  .navchip { display: inline-flex; align-items: center; padding: 6px 12px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    font-size: 12px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .navchip:hover { border-color: var(--acc); color: var(--t-head); }
  .navchip.ok { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 40%, var(--div)); }
  .navchip.draft { color: var(--varn); border-color: color-mix(in srgb, var(--varn) 40%, var(--div)); }
  .navchip.delvis { color: var(--delvis); border-color: color-mix(in srgb, var(--delvis) 45%, var(--div));
    background: color-mix(in srgb, var(--delvis) 10%, var(--kort)); }
  .navchip.accent { color: #fff; background: var(--acc); border-color: var(--acc); font-weight: 700; }
  .papperskorg { flex: none; width: 30px; height: 30px; display: inline-flex; align-items: center;
    justify-content: center; border: 1px solid var(--div); border-radius: 7px; background: var(--kort);
    color: var(--t-mut); }
  .papperskorg svg { width: 14px; height: 14px; }
  .papperskorg:hover { color: #C0453E; border-color: #C0453E; }
  .chev { width: 18px; text-align: center; color: var(--t-mut); font-size: 17px; transition: transform 0.15s; flex: none; }
  .chev.upp { transform: rotate(90deg); }

  .bekrafta { border-top: 1px solid var(--div3); padding: 12px 14px; display: flex; align-items: center;
    gap: 12px; background: rgba(192, 69, 62, 0.06); }
  .bekrafta svg { width: 17px; height: 17px; flex: none; }
  .btxt { flex: 1; font-size: 12.5px; color: var(--t-head); }
  .bavbryt { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 7px 13px; font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .bta { flex: none; background: #C0453E; border: 0; border-radius: 7px; padding: 7px 13px;
    font-size: 12.5px; font-weight: 600; color: #fff; }
  .fel { color: #C0453E; font-size: 12.5px; margin: 0 2px 10px; }

  .editor { border-top: 1px solid var(--div3); padding: 16px 14px; display: flex; flex-direction: column; gap: 12px; }
  .rad2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .rad2.enkel { grid-template-columns: 1fr; }
  .eventtogg { display: flex; align-items: center; gap: 9px; margin: 2px 0 4px; font-size: 12.5px; font-weight: 600; color: var(--t-head); cursor: pointer; }
  .eventtogg input { width: 15px; height: 15px; accent-color: var(--acc); }
  .eventmut { font-weight: 400; color: var(--t-mut); }
  .rad3 { display: flex; gap: 10px; }
  .eventdorr { display: flex; align-items: center; gap: 6px; }
  .eventdorr :global(.cb) { flex: 1; min-width: 0; }
  .eventrensa { flex: none; border: 0; background: none; color: var(--t-mut);
    cursor: pointer; font-size: 12px; padding: 4px 6px; }
  .eventrensa:hover { color: var(--krock, #b03838); }
  .rad3 input:nth-of-type(1) { width: 150px; flex: none; }
  .rad3 input:nth-of-type(2) { width: 104px; flex: none; }
  .rad3 input:nth-of-type(3) { flex: 1; min-width: 0; }
  .slutkol { display: flex; flex-direction: column; justify-content: center; flex: none; }
  .slut { font-size: 12px; color: var(--t-mut); font-variant-numeric: tabular-nums; }
  .slutdur { font-size: 10px; color: var(--t-help); }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  label.full { width: 100%; }
  input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel);
    color: var(--t-head); font-size: 13px; font-weight: 400; text-transform: none; letter-spacing: 0; outline: none; }
  input:focus { border-color: var(--acc); }
  .caps2 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-top: 4px; }

  .lagbox2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .lbox { border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .lhuvud { display: flex; align-items: center; gap: 9px; }
  .lnamn-wrap { min-width: 0; }
  .lnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lsub { font-size: 10.5px; color: var(--t-mut); }
  .uttagrad { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
  .uttagnot { font-size: 10px; color: var(--t-help); }
  .grupplbl { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-help); margin-bottom: 4px; }
  .grupplbl-sub { font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--t-help); }
  .lbtn { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px;
    background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 7px 10px;
    font-size: 12px; color: var(--t-mut); }
  .lbtn.i { border-color: color-mix(in srgb, var(--acc) 45%, var(--div)); color: var(--t-head); }
  .lbtn-n { font-size: 10.5px; color: var(--t-mut); flex: none; }
  .lbtn:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .lbtn:disabled { opacity: 0.5; }
  .hint { font-size: 10.5px; color: var(--t-help); line-height: 1.45; }
  .lank { border: 0; background: none; color: var(--acc); font-size: 10.5px; font-weight: 600; padding: 0; }
  .lank:disabled { opacity: 0.5; }

  .gcalkort { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--div3);
    border-radius: 10px; background: var(--panel); }
  .gcalik { width: 36px; height: 36px; border-radius: 9px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .gcalik svg { width: 18px; height: 18px; }
  .gcaltxt { flex: 1; min-width: 0; }
  .gt { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .gs { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }
  .gcalbtn { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 14px; font-size: 13px; font-weight: 600; flex: none; }
  .gcalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .gcalbtn:disabled { opacity: 0.5; }

  .lankblock { display: flex; flex-direction: column; gap: 8px; }

  .slutblock { border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); overflow: hidden; }
  .sluthuvud { width: 100%; display: flex; align-items: center; gap: 8px; padding: 12px 14px;
    background: none; border: 0; text-align: left; cursor: pointer; }
  .sluthuvud:disabled { opacity: 0.5; cursor: default; }
  .sluthuvud .caps2 { margin: 0; }
  .slutchevron { margin-left: auto; color: var(--t-mut); }
  .slutform { display: flex; flex-direction: column; gap: 12px; padding: 0 14px 14px; }
  .slutkryss { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; color: var(--t-head); }
  .slutkryss label { display: flex; flex-direction: row; align-items: center; gap: 8px;
    text-transform: none; letter-spacing: normal; font-size: 12.5px; font-weight: 500; color: var(--t-head); }
  .slutkryss input[type="checkbox"] { width: auto; padding: 0; }

  .knappar { display: flex; gap: 10px; }
  .prim { padding: 9px 16px; border: 0; border-radius: 7px; background: var(--acc); color: #fff; font-size: 13px; font-weight: 600; }
  .sek { padding: 9px 14px; border: 1px solid var(--div); border-radius: 7px; background: var(--kort); color: var(--t-head); font-size: 13px; }

  /* 7A: kompakta rubrikknappar istället för fullbreddsknappar under listan. */
  .huvudknappar { display: flex; gap: 8px; margin-left: auto; }
  .ny { padding: 8px 14px; border: 1.5px dashed var(--div); border-radius: 999px;
    background: transparent; color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
  .ny.sek2 { border-style: solid; }

  .importkort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 16px; margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
  .importfel { font-size: 12px; color: var(--fel, #c0453e); }
  .importeller { font-size: 11px; color: var(--t-mut); text-align: center; margin-top: 4px; }
  .importjson { font-size: 12px; padding: 10px 12px; border: 1px solid var(--div); border-radius: 9px;
    background: var(--panel); color: var(--t-head); resize: vertical; width: 100%; box-sizing: border-box; }
  .importresultat { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .importgren { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .grenval { font-size: 12px; padding: 5px 12px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-mut); cursor: pointer; }
  .grenval.pa { border-color: var(--accent, #c8963c); color: var(--t-head); font-weight: 600; }
  .grennot { font-size: 11px; color: var(--t-mut); }
  .krockrubrik { font-size: 12px; font-weight: 600; color: var(--fel, #c0453e); margin-top: 4px; }
  .krock { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--div); }
  .krockdatum { font-size: 12px; font-weight: 700; color: var(--t-head); min-width: 88px; }
  .krockalt { font-size: 11px; color: var(--t-mut); padding: 3px 8px; border: 1px solid var(--div); border-radius: 7px; }
  .krockalt.forslag { color: var(--t-head); border-color: var(--accent, #c8963c); font-weight: 600; }
  .importlista { display: flex; flex-direction: column; gap: 8px; }
  .importrad { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--div);
    border-radius: 9px; background: var(--panel); text-align: left; }
  .importrad.dubblett { opacity: 0.55; }
  .irtxt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .irfix { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .irsub { font-size: 11px; color: var(--t-mut); }
  .irdub { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--t-help); flex: none; }
  .chk { display: flex; align-items: center; gap: 10px; border: 0; background: none; padding: 0; font-size: 13px; color: var(--t-head); }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel);
    color: var(--acc); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }

  .proj { margin: 26px 2px 12px; }
  .projgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .projkort { border: 1px solid var(--div); border-radius: var(--r); overflow: hidden; background: var(--kort);
    box-shadow: var(--skugga); padding: 0; text-align: left; }
  .projkort:hover { border-color: var(--acc); }
  .projbild { aspect-ratio: 4 / 3; display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 9px, var(--panel) 9px, var(--panel) 18px); }
  .projbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--t-mut); }
  .projtxt { padding: 10px 12px; }
  .projnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .projsub { font-size: 11px; color: var(--t-mut); margin-top: 2px; }
  .projater { font-size: 12px; font-weight: 600; color: var(--acc); margin-top: 8px; }
</style>
