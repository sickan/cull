<script>
  import { onMount, createEventDispatcher } from 'svelte'
  const dispatch = createEventDispatcher()
  import {
    forhandsgranskaInnehall, exporteraInnehall, publiceraInnehallNatet, statusInnehall,
    valjMapp, valjFil, thumbForBild, slugga, listaInnehall, raderaInnehall, sparaInnehall,
    listaMatcher, hamtaMatch, aktivMatch, sportprofiler, listaLag, listaMaterial,
    listaFotojobb, urvalHojdpunkter, genereraBildsvep, forhandsgranskaBildsvepFraga,
    pagangMatcher, sportTopp, sattSportTopp,
  } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { testMode } from '../lib/testlage.js'
  import { grenFarg } from '../lib/gren.js'
  import { losText, tokenVals, strippaSocialt } from '../lib/webtext.js'
  import BildvaljareFokuspunkt from '../lib/BildvaljareFokuspunkt.svelte'
  import Hornmarkor from '../lib/Hornmarkor.svelte'
  import ResultatRemsa from '../lib/ResultatRemsa.svelte'

  // ── Handoff "sportsidor & menyer" (11 jul 2026) ─────────────────────────────
  // Innehåll är ett BIBLIOTEK (typ-nav Sport · Landskap · Människor · Blogg, en
  // typ i taget) som öppnar en FOKUSERAD editor. Sport-vyn ÄR startside-
  // kureringen (hero-val, artikelkort, På gång). Matchartikeln byggs HÄR —
  // Matchpublicering gör Live/SoMe och producerar referatet vi hämtar (§4).
  const LIBTYPER = [
    { id: 'sport', namn: 'Sport', farg: '#2F7CB0', hint: 'Startsidan för sport — hero, matchartiklar, event & På gång.' },
    { id: 'landskap', namn: 'Landskap', farg: '#C9871F', hint: 'Bildserie — landskap & natur, endast bilder.' },
    { id: 'event', namn: 'Människor', farg: '#C9657F', hint: 'Porträtt, bröllop, student & företag.' },
    { id: 'blogg', namn: 'Blogg', farg: '#7A8794', hint: 'Journal, resor & fritext — en fristående bloggpost.' },
    { id: 'film', namn: 'Film', farg: '#8A6FB0', hint: 'Analog / film — hero, ingress och ett bildgalleri.' },
  ]
  const EVENT_KAT = ['Porträtt', 'Bröllop', 'Student', 'Företag', 'Mode', 'Övrigt']
  // Editor-typ → export-mapp (content-collection). 'match' = matcher.
  const EDITOR_MAPP = { match: 'matcher', sportevent: 'sportevent', blogg: 'blogg', landskap: 'landskap', event: 'event', film: 'film' }

  let libType = 'sport'               // bibliotekets typ-nav
  let editorMode = false              // false = bibliotek, true = fokuserad editor
  let ctyp = 'match'                  // editorns typ: match|sportevent|blogg|landskap|event

  // ── Editor-state per typ ────────────────────────────────────────────────────
  let cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '',
    ingress: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
  let cmsLandskap = { titel: '', plats: '', period: '', ingress: '',
    hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
  let cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '',
    hero: '', heroPosition: 'center center', heroKalla: '', platser: [], figurer: [] }
  let cmsFilm = { titel: '', ingress: '',
    hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
  // Blogg inline-bilder: högerklicksmeny som infogar en [bild N]-token vid
  // markören i brödtexten. blImgMeny = {x, y, pos} när menyn är öppen.
  let blImgMeny = null
  // Matchartikeln: fälten är KOPPLADE till matchen tills man skriver eget
  // (own[f]=true bryter kopplingen; "↺ Hämta" återkopplar) — prototypens cmsOwn.
  const tomMatchArt = () => ({ innehallId: null, hem: '', borta: '', resultat: '',
    mellan: '', datum: '', serie: '', arena: '', pixieset: '', malskyttar: '',
    svep: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [], own: {} })
  let cmsMatch = tomMatchArt()
  let artMatchId = null               // vald match (cmsPick)
  let artMatch = null                 // fullständig matchpost (ResultatRemsa)
  const tomSportevent = () => ({ innehallId: null, fotojobbId: '', titel: '', period: '',
    plats: '', datum: '', ingress: '', hero: '', heroPosition: 'center center',
    heroKalla: '', figurer: [], underartiklar: [] })
  let cmsSportevent = tomSportevent()

  let md = ''
  let exportDirs = { event: '', landskap: '', blogg: '', match: '', sportevent: '' }
  let sparad = false
  let sparadPath = ''
  let synkar = false
  let synkFel = ''
  let synkad = false
  let synkadPath = ''
  let publiceradId = ''
  let statusInfo = null
  let statusLaddar = false

  // ── Grunddata ───────────────────────────────────────────────────────────────
  let matcher = []
  let lagAlla = []
  let profiler = {}
  let materials = []
  let fotojobb = []

  $: akt = ctyp === 'event' ? cmsEvent
    : ctyp === 'landskap' ? cmsLandskap
    : ctyp === 'match' ? cmsMatch
    : ctyp === 'sportevent' ? cmsSportevent
    : ctyp === 'film' ? cmsFilm : cmsBlogg
  $: libinfo = LIBTYPER.find((t) => t.id === libType)
  // Bildtext per bild: match & blogg. Landskap/Människor/Sportevent = bild-only
  // (speglar _innehall_md:s gal_text).
  $: galText = ctyp === 'match' || ctyp === 'blogg'
  // Gallerindex som refereras av [bild N]-token i bloggbrödtexten (för "I TEXTEN"-
  // badgen + för att veta vilka bilder som ligger inline).
  $: blUsed = (() => {
    const s = new Set()
    if (ctyp !== 'blogg') return s
    const re = /\[bild\s+(\d+)\]/gi; let m
    while ((m = re.exec(cmsBlogg.body || ''))) { const i = parseInt(m[1], 10) - 1; if (i >= 0) s.add(i) }
    return s
  })()
  $: aktTitel = ctyp === 'match' ? `${cmsMatch.hem} – ${cmsMatch.borta}` : (akt.titel || '')
  $: aktSlug = slugga(aktTitel)
  $: profil = profiler[artMatch?.sport] || profiler.fotboll ||
    { res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid', mid_ph: '3–0',
      has_scorers: true, scorers_label: 'Målskyttar', start_moment: 'Avspark' }

  let editorEl                        // editorns topp (scroll vid öppning)

  onMount(async () => {
    lasUtkast()
    ;[matcher, lagAlla, profiler, materials, fotojobb] = await Promise.all(
      [listaMatcher(), listaLag(), sportprofiler(), listaMaterial(), listaFotojobb()])
    await Promise.all([laddaOversikt(), laddaPagang(), laddaTopp()])
    // Matchartikeln utgår från aktiv match tills man byter (README §3).
    const am = await aktivMatch()
    if (am?.id) artMatchId = am.id
  })

  function setLibType(t) { libType = t }
  function oppnaEditor(typ) {
    ctyp = typ
    editorMode = true
    forhandsgranska()
    _scrollTop()
  }
  function stangEditor() { editorMode = false; laddaOversikt() }

  // ── Bibliotek: publicerat & utkast ─────────────────────────────────────────
  const TYP_NAMN = { match: 'Matchartikel', sportevent: 'Event/mästerskap',
    blogg: 'Blogg', event: 'Människor', landskap: 'Landskap', film: 'Film' }
  const DRAFTS_KEY = 'dpt2.drafts.v1'
  let overviewTab = 'publicerat'
  let poster = []                     // alla innehåll-rader (DB via listaInnehall)
  let utkast = []                     // localStorage-utkast
  let draftId = null                  // id på utkastet som redigeras nu
  let sparTimer

  async function laddaOversikt() { poster = (await listaInnehall()) || [] }
  function lasUtkast() {
    try { utkast = JSON.parse(localStorage.getItem(DRAFTS_KEY) || '[]') } catch (_) { utkast = [] }
  }
  function skrivUtkast() { try { localStorage.setItem(DRAFTS_KEY, JSON.stringify(utkast)) } catch (_) {} }

  const publiceradPost = (p) => !!(p.publicerad || p.synkad_tid)
  const titelAv = (p) => p.frontmatter?.titel
    || (p.frontmatter?.hem ? `${p.frontmatter.hem} – ${p.frontmatter.borta}` : '')
    || p.titel || '(utan titel)'
  function datumText(iso, prefix) {
    if (!iso) return ''
    try { return `${prefix} ${new Date(iso).toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' })}` } catch (_) { return '' }
  }

  // Enkeltyps-vyer (Landskap/Människor/Blogg): rader av vald typ.
  $: libPoster = poster.filter((p) => p.typ === libType && publiceradPost(p))
  $: libUtkastDb = poster.filter((p) => p.typ === libType && !publiceradPost(p))
  $: libUtkast = utkast.filter((u) => u.typ === libType)

  // Autospar (debounce) → localStorage, så en påbörjad post överlever omstart.
  function autospar() {
    if (!editorMode) return
    const titel = ctyp === 'match' ? (cmsMatch.hem && aktTitel) : akt.titel
    if (!titel) return              // spara inte tomma utkast
    if (!draftId) draftId = 'd' + Date.now()
    const extra = ctyp === 'match' ? { matchId: artMatchId } : {}
    const d = { id: draftId, typ: ctyp, titel,
                sparad: new Date().toISOString(), ...extra,
                data: JSON.parse(JSON.stringify(akt)) }
    utkast = [d, ...utkast.filter((u) => u.id !== draftId)]
    skrivUtkast()
  }
  function schemalaggAutospar() { clearTimeout(sparTimer); sparTimer = setTimeout(autospar, 800) }

  function _scrollTop() { setTimeout(() => editorEl?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0) }

  // Klick på rad/kort = öppna för redigering.
  function laddaPost(p) {
    const fm = p.frontmatter || {}
    if (p.typ === 'match') { laddaMatchPost(p); return }
    if (p.typ === 'sportevent') {
      cmsSportevent = { ...tomSportevent(), innehallId: p.id, titel: fm.titel || '',
        period: fm.period || '', plats: fm.plats || '', datum: fm.datum || '',
        ingress: fm.ingress || '', hero: fm.hero || '',
        heroPosition: fm.heroPosition || 'center center',
        underartiklar: (fm.underartiklar || []).map((u) => ({ ...u })) }
      draftId = null; oppnaEditor('sportevent'); return
    }
    const bas = { titel: fm.titel || '', ingress: fm.ingress || '',
                  hero: fm.hero || '', heroPosition: fm.heroPosition || 'center center', heroKalla: '', figurer: [] }
    const bilderTillFig = (fm.bilder || []).map((url) => ({ bild: url, alt: '', bildtext: '', src: '', thumb: '' }))
    if (p.typ === 'event') cmsEvent = { ...cmsEvent, ...bas, kategori: fm.kategori || 'Porträtt', kund: fm.kund || '', datum: fm.datum || '', plats: fm.plats || '', figurer: bilderTillFig }
    else if (p.typ === 'landskap') cmsLandskap = { ...cmsLandskap, ...bas, plats: fm.plats || '', period: fm.period || '', figurer: bilderTillFig }
    else if (p.typ === 'film') cmsFilm = { ...cmsFilm, ...bas, figurer: bilderTillFig }
    else cmsBlogg = { ...cmsBlogg, ...bas, kategori: fm.kategori || '', datum: fm.datum || '', body: fm.body || p.body || '', platser: [], figurer: bilderTillFig }
    draftId = null
    oppnaEditor(p.typ)
  }
  function laddaUtkast(u) {
    if (u.typ === 'event') cmsEvent = { ...cmsEvent, ...u.data }
    else if (u.typ === 'landskap') cmsLandskap = { ...cmsLandskap, ...u.data }
    else if (u.typ === 'film') cmsFilm = { ...cmsFilm, ...u.data }
    else if (u.typ === 'blogg') cmsBlogg = { ...cmsBlogg, ...u.data }
    else if (u.typ === 'sportevent') cmsSportevent = { ...tomSportevent(), ...u.data }
    else if (u.typ === 'match') { cmsMatch = { ...tomMatchArt(), ...u.data }; artMatchId = u.matchId || artMatchId; laddaArtMatch(false) }
    draftId = u.id
    oppnaEditor(u.typ)
  }
  async function raderaPost(p) { await raderaInnehall(p.id); await laddaOversikt() }
  function raderaUtkast(id) { utkast = utkast.filter((u) => u.id !== id); skrivUtkast(); if (draftId === id) draftId = null }

  // ── Sport-startsidan (bibliotekets sport-vy) ────────────────────────────────
  // Kort = DB-rader (matchartiklar + sportevent), publicerade OCH utkast.
  const fmDatum = (p) => p.frontmatter?.datum || p.skapad || ''
  $: sportKort = poster
    .filter((p) => p.typ === 'match' || p.typ === 'sportevent')
    .sort((a, b) => (fmDatum(b) < fmDatum(a) ? -1 : fmDatum(b) > fmDatum(a) ? 1 : 0))

  // Topp-väljare: 'senaste' (härledd) | 'valj' (kurerad topp-flagga på sajten).
  // 'Kommande' kräver hero utan matchbild på sajten — finns inte ännu (avstängd).
  let toppLage = 'senaste'
  let toppValId = null
  let toppSparar = false
  let toppFlash = ''
  let toppFel = ''
  async function laddaTopp() {
    const r = await sportTopp()
    if (r?.ok) { toppLage = r.lage || 'senaste'; toppValId = r.innehall_id || null }
  }
  $: toppKandidater = sportKort.filter((p) => p.typ === 'match' && publiceradPost(p))
  async function valjTopp(lage, id = null) {
    toppLage = lage; toppValId = id; toppFel = ''; toppFlash = ''
    toppSparar = true
    const r = await sattSportTopp(lage, id, $testMode)
    toppSparar = false
    if (r?.ok) {
      toppFlash = r.test ? '✓ Sparat (testläge — sajten orörd)'
        : lage === 'valj' ? '✓ Vald som topp på sport-sidan' : '✓ Sajten härleder senaste matchen'
      setTimeout(() => (toppFlash = ''), 3000)
    } else toppFel = r?.fel || 'Kunde inte uppdatera kureringen.'
  }
  $: heroPost = (toppLage === 'valj' && toppValId && sportKort.find((p) => p.id === toppValId))
    || sportKort.find((p) => p.typ === 'match' && publiceradPost(p) && p.frontmatter?.resultat)
    || sportKort[0] || null
  // Publicerat innehåll refererar bilder på flera sätt: absoluta URL:er
  // (event/blogg/film → pixieset/R2), sajt-absoluta sökvägar (match-galleri
  // /assets/photos/…) och bara filnamn (match-hero "01.jpg" → /sport/{slug}/).
  // För VISNING i DPT2 resolvas de relativa mot den skarpa sajten — den
  // kanoniska publiceringsdatan lämnas orörd (ingen mutation).
  const SAJT = 'https://dalecarliaphoto.se'
  const bildUrl = (ref, slug) => {
    const r = ref || ''
    if (!r) return ''
    if (/^https?:\/\//.test(r)) return r
    if (r.startsWith('/')) return SAJT + r
    return slug ? `${SAJT}/sport/${slug}/${r}` : ''
  }
  // Kortens hero: explicit hero, annars bilder[0] (event/landskap härleder hero
  // därifrån på sajten). Resolvas till en visningsbar URL.
  const heroBildUrl = (p) => {
    const fm = p?.frontmatter || {}
    return bildUrl(fm.hero || (fm.bilder && fm.bilder[0]) || '', fm.slug || p?.id || '')
  }
  // Galleri-miniatyr: lokal miniatyr (thumb) vinner, annars figurens bild-URL
  // (resolvad om den är sajt-absolut/relativ).
  const figThumbSrc = (b) => b?.thumb || bildUrl(b?.bild || '', '')

  // "Öppna matchartikel för match X" — från sportevent-underartiklar & kort.
  async function oppnaMatchArtikel(matchId = null, post = null) {
    if (post) { laddaMatchPost(post); return }
    artMatchId = matchId || artMatchId || matcher[0]?.id || null
    cmsMatch = tomMatchArt(); draftId = null
    await laddaArtMatch(true)
    oppnaEditor('match')
  }

  // ── På gång (förhandslista på Sport-startsidan) ────────────────────────────
  // Kureringen (visa-toggle + sajt-synk) bor nu i den egna Webb → På gång-posten
  // (§C). Här visas bara en förhandslista; "Ordna ›" navigerar dit.
  let pagang = []
  async function laddaPagang() {
    const r = await pagangMatcher()
    if (r?.ok) pagang = r.matcher || []
  }
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const datumKort = (iso) => { const d = (iso || '').split('-').map(Number); return d.length === 3 ? `${d[2]} ${MK[d[1] - 1]}` : '' }

  // ── Matchartikel-editorn ────────────────────────────────────────────────────
  // "Artikel för match": väljaren byter källmatch; kopplade fält fylls om.
  const MATCHFALT = ['hem', 'borta', 'resultat', 'mellan', 'datum', 'serie', 'arena', 'pixieset', 'malskyttar']
  const falt_fran_match = (m) => ({ hem: m?.lag_hemma || '', borta: m?.lag_borta || '',
    resultat: m?.resultat || '', mellan: m?.mellan || '', datum: m?.datum || '',
    serie: m?.liga || '', arena: m?.arena || '', pixieset: m?.galleri || '',
    malskyttar: m?.malskyttar || '' })

  async function laddaArtMatch(fyllFalt) {
    artMatch = artMatchId ? await hamtaMatch(artMatchId) : null
    if (!artMatch) return
    if (fyllFalt) {
      // Befintlig artikelrad för matchen? Återuppta den i stället för att börja om.
      const rad = poster.find((p) => p.typ === 'match' && p.match_id === artMatchId)
      cmsMatch = { ...tomMatchArt(), ...falt_fran_match(artMatch) }
      if (rad) {
        const fm = rad.frontmatter || {}
        cmsMatch.innehallId = rad.id
        cmsMatch.heroPosition = fm.heroPosition || 'center center'
        if (fm.pixieset) cmsMatch.pixieset = fm.pixieset
        // Referatet bor i body — utan galleri-markdownen (![…]-raderna).
        cmsMatch.svep = (rad.body || '').split('\n')
          .filter((l) => !l.trim().startsWith('![')).join('\n').trim()
      }
      cmsMatch = cmsMatch
    }
    forhandsgranska()
  }
  function laddaMatchPost(p) {
    artMatchId = p.match_id || artMatchId
    draftId = null
    const fm = p.frontmatter || {}
    cmsMatch = { ...tomMatchArt(), innehallId: p.id,
      hem: fm.hem || '', borta: fm.borta || '', resultat: fm.resultat || '',
      mellan: fm.halvtid || fm.set || fm.perioder || '', datum: fm.datum || '',
      serie: fm.serie || '', arena: fm.arena || '', pixieset: fm.pixieset || '',
      malskyttar: Array.isArray(fm.malskyttar) ? fm.malskyttar.join(', ') : (fm.malskyttar || ''),
      // Hero resolvad för VISNING (match-hero "01.jpg" → /sport/{slug}/01.jpg) så
      // fältet visar bilden i stället för bara filnamnet. Vid skarp publicering
      // vinner ändå R2-URL:en (bild_urls['hero']); lokala utkast berörs ej.
      hero: bildUrl(fm.hero, fm.slug || p.id), heroPosition: fm.heroPosition || 'center center',
      // Publicerade galleribilder (frontmatterns bilder[]) in i galleriet så de
      // syns när man öppnar en publicerad matchartikel — precis som event/film.
      // "Hämta höjdpunkter" ersätter dem med ett färskt Gallra-urval vid behov.
      figurer: (fm.bilder || []).map((url) => ({ bild: url, alt: '', bildtext: '', src: '', thumb: '' })),
      svep: (p.body || '').split('\n').filter((l) => !l.trim().startsWith('![')).join('\n').trim() }
    laddaArtMatch(false)
    oppnaEditor('match')
  }
  async function cmsPick(e) {
    artMatchId = e.target.value || null
    cmsMatch = tomMatchArt(); draftId = null
    await laddaArtMatch(true)
  }
  // Skriva i ett kopplat fält = eget värde (bryter kopplingen).
  function sattEget(f, v) { cmsMatch[f] = v; cmsMatch.own = { ...cmsMatch.own, [f]: true }; forhandsgranska() }
  function hamtaFalt(f) {
    cmsMatch[f] = falt_fran_match(artMatch)[f]
    cmsMatch.own = { ...cmsMatch.own, [f]: false }
    forhandsgranska()
  }
  function hamtaAllt() {
    cmsMatch = { ...cmsMatch, ...falt_fran_match(artMatch), own: {} }
    forhandsgranska()
  }
  // ResultatRemsan skriver på matchen → spegla in i icke-egna fält.
  function onResSparat(e) {
    const d = e.detail || {}
    artMatch = { ...artMatch, ...d }
    for (const f of ['resultat', 'mellan', 'malskyttar']) {
      if (!cmsMatch.own[f] && f in d) cmsMatch[f] = d[f] || ''
    }
    cmsMatch = cmsMatch
    forhandsgranska()
  }

  // Referat: hämta från Matchpublicering (§4 — panelen PRODUCERAR, vi hämtar).
  let svepFlash = ''
  $: artMaterial = (materials || []).find((m) => m.match_id === artMatchId && m.kind === 'some' && m.caption)
  function handle(namn) { return (lagAlla.find((x) => x.namn === namn)?.instagram || '').replace(/^@/, '') }
  function pullFromSome() {
    if (!artMaterial) return
    cmsMatch.svep = losText(artMaterial.caption,
      tokenVals({ match: artMatch, res: cmsMatch, handle: handle(artMatch?.lag_hemma),
        galleriUrl: cmsMatch.pixieset, hemsidaUrl: '', web: true }), { web: true })
    cmsMatch = cmsMatch
    svepFlash = '✓ Hämtat från Matchpublicering'
    setTimeout(() => (svepFlash = ''), 2400)
    forhandsgranska()
  }
  $: svepWebb = strippaSocialt(cmsMatch.svep) || '—'

  // Regenerera med Claude — samma tvåstegsflöde som Matchpublicering
  // (granska frågan → skicka; skarpt anrop tar ~2 min).
  let genererar = false
  let genFel = ''
  let granska = null
  let laddarFraga = false
  let genSek = 0
  let genTimer = null
  const genInfo = () => `${cmsMatch.hem} – ${cmsMatch.borta}` + (cmsMatch.resultat ? ` ${cmsMatch.resultat}` : '')
  const genFakta = () => ({ resultat: cmsMatch.resultat, mellan: cmsMatch.mellan,
    malskyttar: cmsMatch.malskyttar, arena: cmsMatch.arena, datum: cmsMatch.datum,
    liga: cmsMatch.serie, ton: 'Neutral' })
  async function oppnaGranska() {
    if (genererar || laddarFraga) return
    genFel = ''; laddarFraga = true
    try {
      const r = await forhandsgranskaBildsvepFraga(genInfo(), genFakta())
      if (r?.ok) granska = r.fraga
      else genFel = r?.fel || 'Kunde inte bygga frågan.'
    } catch (_) { genFel = 'Kunde inte bygga frågan.' }
    laddarFraga = false
  }
  async function skickaTillClaude() {
    const info = genInfo(), fakta = genFakta()
    granska = null; genererar = true; genFel = ''; genSek = 0
    genTimer = setInterval(() => (genSek += 1), 1000)
    try {
      const r = await genereraBildsvep(info, artMatch?.sport || '', '', fakta)
      if (r?.ok && r.bildsvep) { cmsMatch.svep = r.bildsvep; cmsMatch = cmsMatch }
      else genFel = r?.fel || 'Kunde inte generera texten.'
    } catch (_) { genFel = 'Kunde inte generera texten.' } finally {
      genererar = false
      clearInterval(genTimer); genTimer = null
      forhandsgranska()
    }
  }

  // Höjdpunkter från aktivt urval → galleriet (riktig källa, inte mock).
  let hpFel = ''
  async function pullHighlights() {
    hpFel = ''
    const r = await urvalHojdpunkter(6)
    if (!r?.ok) { hpFel = r?.fel || 'Inget aktivt urval.'; setTimeout(() => (hpFel = ''), 3200); return }
    const nya = []
    for (const [i, p] of (r.sokvagar || []).entries()) {
      const t = await thumbForBild(p)
      nya.push({ bild: p, alt: '', bildtext: '', src: r.filer?.[i] || '', thumb: t?.ok ? t.data_uri : '' })
    }
    akt.figurer = [...akt.figurer, ...nya]
    pinga(); forhandsgranska()
  }

  // ── Sportevent-editorn ──────────────────────────────────────────────────────
  // Skapas från en HELDAGSAKTIVITET i Fotojobb (skiss 1e) — kopplingen
  // förifyller titel/period/plats.
  $: heldagsJobb = (fotojobb || []).filter((j) => j.all_day)
  function valjSporteventJobb(e) {
    const id = e.target.value
    cmsSportevent.fotojobbId = id
    const j = heldagsJobb.find((x) => x.id === id)
    if (j) {
      if (!cmsSportevent.titel) cmsSportevent.titel = j.title || ''
      if (!cmsSportevent.plats) cmsSportevent.plats = j.location || ''
      if (!cmsSportevent.datum) cmsSportevent.datum = (j.start_at || '').slice(0, 10)
      if (!cmsSportevent.period) {
        const a = (j.start_at || '').slice(0, 10), b = (j.end_at || '').slice(0, 10)
        cmsSportevent.period = a && b && a !== b ? `${datumKort(a)} – ${datumKort(b)}` : datumKort(a)
      }
      cmsSportevent = cmsSportevent
    }
    forhandsgranska()
  }
  let subValOppen = false
  function laggUnderartikel(m) {
    const titel = `${m.lag_hemma} – ${m.lag_borta}`
    if (cmsSportevent.underartiklar.some((u) => u.match_id === m.id)) { subValOppen = false; return }
    cmsSportevent.underartiklar = [...cmsSportevent.underartiklar,
      { match_id: m.id, titel, slug: slugga(titel) }]
    subValOppen = false
    forhandsgranska()
  }
  function taUnderartikel(i) {
    cmsSportevent.underartiklar = cmsSportevent.underartiklar.filter((_, j) => j !== i)
    forhandsgranska()
  }
  // Grön prick = matchartikeln finns (egen artikel), annars "vald, ej skapad".
  const subArtikel = (u) => poster.find((p) => p.typ === 'match' && p.match_id === u.match_id)
  async function oppnaUnderartikel(u) {
    autospar()
    await oppnaMatchArtikel(u.match_id, subArtikel(u) || null)
  }
  async function sparaUtkastDb() {
    const r = await sparaInnehall(data())
    if (r?.ok) {
      if (ctyp === 'match') cmsMatch.innehallId = r.id
      else if (ctyp === 'sportevent') cmsSportevent.innehallId = r.id
      sparadDb = true; setTimeout(() => (sparadDb = false), 2400)
      await laddaOversikt()
    }
  }
  let sparadDb = false

  // ── Gemensam editor-mekanik (befintlig) ────────────────────────────────────
  const utanThumb = (arr) => (arr || []).map(({ thumb, ...r }) => r)
  function data() {
    if (ctyp === 'event') return { typ: 'event', ...cmsEvent, figurer: utanThumb(cmsEvent.figurer) }
    if (ctyp === 'landskap') return { typ: 'landskap', ...cmsLandskap, figurer: utanThumb(cmsLandskap.figurer) }
    if (ctyp === 'film') return { typ: 'film', ...cmsFilm,
      bilder: cmsFilm.figurer.map((f) => f.bild).filter(Boolean), figurer: utanThumb(cmsFilm.figurer) }
    if (ctyp === 'match') {
      const c = cmsMatch
      return { typ: 'match', id: c.innehallId || undefined, match_id: artMatchId || null,
        titel: `${c.hem} – ${c.borta}`, hem: c.hem, borta: c.borta, serie: c.serie,
        sport: artMatch?.sport || '', datum: c.datum, arena: c.arena,
        resultat: c.resultat, mellan: c.mellan, malskyttar: c.malskyttar,
        status: c.resultat ? 'avslutad' : 'kommande', pixieset: c.pixieset,
        body: strippaSocialt(c.svep),                     // webben får texten utan @/#
        hero: c.hero, heroPosition: c.heroPosition, heroKalla: c.heroKalla,
        figurer: utanThumb(c.figurer) }
    }
    if (ctyp === 'sportevent') {
      const c = cmsSportevent
      return { typ: 'sportevent', id: c.innehallId || undefined,
        titel: c.titel, period: c.period, plats: c.plats, datum: c.datum,
        ingress: c.ingress, hero: c.hero, heroPosition: c.heroPosition,
        heroKalla: c.heroKalla, figurer: utanThumb(c.figurer),
        underartiklar: c.underartiklar }
    }
    return { typ: 'blogg', ...cmsBlogg, figurer: utanThumb(cmsBlogg.figurer) }
  }

  async function forhandsgranska() {
    const r = await forhandsgranskaInnehall(data())
    md = r?.md || ''
    schemalaggAutospar()
  }

  function pinga() { cmsEvent = cmsEvent; cmsLandskap = cmsLandskap; cmsBlogg = cmsBlogg; cmsMatch = cmsMatch; cmsSportevent = cmsSportevent }
  function heroAndrad() { pinga(); forhandsgranska() }
  function laggBild() { akt.figurer = [...akt.figurer, { bild: '', alt: '', bildtext: '', src: '', thumb: '' }]; pinga(); forhandsgranska() }
  function taBild(i) { akt.figurer = akt.figurer.filter((_, j) => j !== i); pinga(); forhandsgranska() }
  async function valjFigurBild(i) {
    const r = await valjFil('Välj bild', ['Bilder (*.jpg;*.jpeg;*.png;*.nef;*.dng;*.cr2;*.cr3;*.arw)'])
    if (!r?.ok || !r.path) return
    const t = await thumbForBild(r.path)
    if (!t?.ok) return
    akt.figurer[i] = { ...akt.figurer[i], bild: r.path, thumb: t.data_uri }
    pinga(); forhandsgranska()
  }

  let dragIdx = null
  function dragStart(i) { dragIdx = i }
  function dragOver(i, e) { e.preventDefault() }
  function slapp(i) {
    if (dragIdx === null || dragIdx === i) { dragIdx = null; return }
    const arr = [...akt.figurer]
    const [flyttad] = arr.splice(dragIdx, 1)
    arr.splice(i, 0, flyttad)
    akt.figurer = arr
    dragIdx = null
    pinga(); forhandsgranska()
  }
  function laggPlats() { cmsBlogg.platser = [...cmsBlogg.platser, { plats: '', tips: '' }] }
  function taPlats(i) { cmsBlogg.platser = cmsBlogg.platser.filter((_, j) => j !== i); forhandsgranska() }

  // ── Blogg inline-bilder: högerklick i brödtexten → infoga [bild N]-token ─────
  function blCtx(e) {
    e.preventDefault()
    blImgMeny = { x: e.clientX, y: e.clientY, pos: e.target.selectionStart }
  }
  function blImgClose() { if (blImgMeny) blImgMeny = null }
  function blInsertImg(i) {
    if (!blImgMeny) return
    const body = cmsBlogg.body || ''
    const p = Math.max(0, Math.min(blImgMeny.pos == null ? body.length : blImgMeny.pos, body.length))
    cmsBlogg.body = body.slice(0, p) + `[bild ${i + 1}]` + body.slice(p)
    blImgMeny = null
    forhandsgranska()
  }
  // Menyns position: klampad mot fönsterkanterna (som prototypen).
  $: blImgMenyStil = blImgMeny
    ? `position:fixed;left:${Math.max(8, Math.min(blImgMeny.x, (typeof window !== 'undefined' ? window.innerWidth : 1200) - 290))}px;`
      + `top:${Math.max(8, Math.min(blImgMeny.y, (typeof window !== 'undefined' ? window.innerHeight : 800) - (60 + cmsBlogg.figurer.length * 47)))}px;`
      + 'z-index:410;width:270px;'
    : 'display:none;'

  async function spara() {
    if (!$testMode && !exportDirs[ctyp]) {
      const r = await valjMapp(`Välj content/${EDITOR_MAPP[ctyp]}-katalog`)
      if (r.ok) exportDirs[ctyp] = r.path; else return
    }
    const r = await exporteraInnehall(data(), exportDirs[ctyp], $testMode)
    sparad = !!r?.ok
    sparadPath = r?.path || ''
    if (sparad) setTimeout(() => (sparad = false), 2600)
  }

  async function publicera() {
    synkar = true
    synkFel = ''
    statusInfo = null
    const r = await publiceraInnehallNatet(data(), $testMode)
    synkar = false
    synkad = !!r?.ok
    synkadPath = r?.path || ''
    if (synkad) {
      publiceradId = r.id
      if (ctyp === 'match' && r.id) cmsMatch.innehallId = r.id
      if (draftId) { raderaUtkast(draftId); draftId = null }
      if (!$testMode) await laddaOversikt()
      setTimeout(() => (synkad = false), 2600)
    } else synkFel = r?.fel || 'Kunde inte publicera — kontrollera anslutningen.'
  }

  async function kollaStatus() {
    if (!publiceradId) return
    statusLaddar = true
    statusInfo = await statusInnehall(ctyp === 'match' ? 'match' : ctyp, publiceradId)
    statusLaddar = false
  }

  const DEPLOY_ETI = { success: 'Live', building: 'Bygger…', queued: 'Köad', failure: 'Fel', canceled: 'Avbruten' }
  $: deployText = statusInfo?.deploy
    ? (DEPLOY_ETI[statusInfo.deploy.status] || statusInfo.deploy.status)
      + (statusInfo.deploy.status === 'success' && statusInfo.deploy.skapad
          ? ' sedan ' + new Date(statusInfo.deploy.skapad).toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' })
          : '')
    : statusInfo ? 'Ingen deploy-status tillgänglig (CF-nycklar ej satta i workern)' : ''
</script>

<div class="panel" bind:this={editorEl}>
  {#if !editorMode}
    <!-- ══ BIBLIOTEKET ══ -->
    <header>
      <h1 class="scd">Innehåll</h1>
      <span class="sub">Biblioteket för hemsidan — en typ i taget, klick öppnar editorn</span>
    </header>

    <!-- Typ-nav: fyra jämbördiga val + Skapa nytt (Sport-artiklar skapas från match/event) -->
    <div class="libnav">
      <div class="cmstabs">
        {#each LIBTYPER as lt}
          <button class="cmstab" class:on={libType === lt.id} style="--tf:{lt.farg}" on:click={() => setLibType(lt.id)}>
            <span class="cmstik">
              {#if lt.id === 'sport'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v5l4.3 3.1-1.6 5H9.3l-1.6-5L12 8.5"/></svg>
              {:else if lt.id === 'landskap'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 17l5-8 4 6 3-4 6 6"/><circle cx="17.5" cy="7.5" r="1.8"/></svg>
              {:else if lt.id === 'event'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.6"/><path d="M5 20c0-3.5 3.1-5.5 7-5.5s7 2 7 5.5"/></svg>
              {:else if lt.id === 'film'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M8 5v14M16 5v14M4 9.5h4M4 14.5h4M16 9.5h4M16 14.5h4"/></svg>
              {:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>{/if}
            </span>
            <span class="cmstnamn scd">{lt.namn}</span>
          </button>
        {/each}
      </div>
      {#if libType !== 'sport'}
        <button class="nyknapp" on:click={() => {
          if (libType === 'blogg') cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '', hero: '', heroPosition: 'center center', heroKalla: '', platser: [], figurer: [] }
          else if (libType === 'landskap') cmsLandskap = { titel: '', plats: '', period: '', ingress: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
          else if (libType === 'film') cmsFilm = { titel: '', ingress: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
          else cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '', ingress: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
          draftId = null
          oppnaEditor(libType)
        }}>+ Ny {libType === 'blogg' ? 'blogg' : libType === 'landskap' ? 'landskap' : libType === 'film' ? 'film' : 'människa'}</button>
      {/if}
    </div>
    <div class="cmssub">{libinfo?.hint}
      {#if libType === 'sport'}<span class="cmshint2">Matchartiklar skapas från en match · event/mästerskap från en heldagsaktivitet i Fotojobb.</span>{/if}
    </div>

    {#if libType === 'sport'}
      <!-- ── Sport = startsidan (4a) ── -->
      <div class="kort sportstart">
        <div class="ovhuvud">
          <span class="caps nomarg">Sport-startsidan</span>
          <div class="toppval">
            <span class="tvlbl">Topp:</span>
            <button class="tvchip" class:on={toppLage === 'senaste'} disabled={toppSparar}
              on:click={() => valjTopp('senaste')}>Senaste matchen</button>
            <button class="tvchip" disabled title="Kräver sajtstöd för hero utan matchbild — inte byggt ännu">Kommande</button>
            <button class="tvchip" class:on={toppLage === 'valj'} disabled={toppSparar || !toppKandidater.length}
              title={toppKandidater.length ? 'Välj en publicerad matchartikel som topp' : 'Publicera en matchartikel först'}
              on:click={() => (toppLage === 'valj' ? null : valjTopp('valj', toppKandidater[0]?.id))}>Välj själv…</button>
            {#if toppLage === 'valj'}
              <select class="tvselect" value={toppValId} on:change={(e) => valjTopp('valj', e.target.value)}>
                {#each toppKandidater as p (p.id)}<option value={p.id}>{titelAv(p)}</option>{/each}
              </select>
            {/if}
          </div>
        </div>
        {#if toppFlash}<div class="ok sm">{toppFlash}</div>{/if}
        {#if toppFel}<div class="synkfel">{toppFel}</div>{/if}

        {#if heroPost}
          <button class="herokort" on:click={() => laddaPost(heroPost)} title="Öppna för redigering">
            {#if heroBildUrl(heroPost)}<img class="herobild" src={heroBildUrl(heroPost)} alt="" />{:else}<div class="herobild platt"></div>{/if}
            <div class="herotext">
              <div class="herokicker">{[heroPost.frontmatter?.serie, datumKort(heroPost.frontmatter?.datum)].filter(Boolean).join(' · ')}</div>
              <div class="herotitel scd">{titelAv(heroPost)}{#if heroPost.frontmatter?.resultat}&nbsp; {heroPost.frontmatter.resultat}{/if}</div>
            </div>
            {#if toppLage === 'valj' && heroPost.id === toppValId}<span class="toppbadge">Topp</span>{/if}
          </button>
        {/if}

        <div class="ovhuvud mt14"><span class="caps nomarg">Matcher &amp; tävlingar</span></div>
        <div class="sportgrid">
          {#each sportKort as p (p.id)}
            <button class="sportkort" on:click={() => laddaPost(p)} title="Öppna för redigering">
              {#if publiceradPost(p)}<Hornmarkor farg="#6FB35A" r={10} titel="Publicerad" />{/if}
              {#if p.typ === 'sportevent'}<span class="tavlingbadge">Tävling</span>{/if}
              <div class="skthumb">{#if heroBildUrl(p)}<img src={heroBildUrl(p)} alt="" loading="lazy" />{/if}</div>
              <div class="sktitel">{titelAv(p)}</div>
              <div class="skmeta">{[p.frontmatter?.resultat, datumKort(p.frontmatter?.datum),
                publiceradPost(p) ? '' : 'utkast'].filter(Boolean).join(' · ') || '—'}</div>
            </button>
          {/each}
          <button class="sportkort nyartikel" on:click={() => oppnaMatchArtikel()}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>
            <span>+ Ny artikel</span>
          </button>
          <button class="sportkort nyartikel" on:click={() => { cmsSportevent = tomSportevent(); draftId = null; oppnaEditor('sportevent') }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>
            <span>+ Nytt event/mästerskap</span>
          </button>
        </div>

        {#if libUtkast.length || utkast.some((u) => u.typ === 'match' || u.typ === 'sportevent')}
          <div class="ovhuvud mt14"><span class="caps nomarg">Påbörjade utkast</span></div>
          {#each utkast.filter((u) => u.typ === 'match' || u.typ === 'sportevent') as u (u.id)}
            <div class="ovrad" role="button" tabindex="0" on:click={() => laddaUtkast(u)}
              on:keydown={(e) => e.key === 'Enter' && laddaUtkast(u)}>
              <div class="ovthumb"></div>
              <div class="ovmitt"><div class="ovtitel">{u.titel || '(utan titel)'}</div>
                <div class="ovmeta">{TYP_NAMN[u.typ]} · {datumText(u.sparad, 'sparad')}</div></div>
              <button class="ovx" class:armerad={$armerad === `utk-${u.id}`}
                on:click|stopPropagation={taBortKlick(`utk-${u.id}`, () => raderaUtkast(u.id))}>
                {#if $armerad === `utk-${u.id}`}Ta bort?{:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>{/if}
              </button>
            </div>
          {/each}
        {/if}

        <!-- På gång — bara sport, härlett ur Matcher. "Ordna ›" öppnar nu den
             egna Webb → På gång-posten (§C); kureringen bor där, inte inline. -->
        <div class="ovhuvud mt14">
          <span class="caps nomarg">På gång <span class="capshint">· kommande matcher &amp; tävlingar</span></span>
          <button class="ordna" on:click={() => dispatch('navigera', 'pagang')}>Ordna ›</button>
        </div>
        <div class="pgrad2">
          {#each pagang.slice(0, 4) as m (m.id)}
            <div class="pgkort">
              <div class="pgdatum"><span class="pgdag scd">{(m.datum || '').split('-')[2] || '–'}</span>
                <span class="pgmon">{MK[(Number((m.datum || '').split('-')[1]) || 1) - 1]?.toUpperCase()}</span></div>
              <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
              <div class="pgi"><div class="pgf">{m.lag_hemma}{m.lag_borta ? ` – ${m.lag_borta}` : ''}</div><div class="pgl">{m.liga || ''}</div></div>
            </div>
          {/each}
          {#if !pagang.length}<div class="ovtom">Inga kommande matcher i Matcher.</div>{/if}
        </div>
      </div>
    {:else}
      <!-- ── Enkeltyps-bibliotek (Landskap / Människor / Blogg) ── -->
      <div class="kort oversikt">
        <div class="ovhuvud">
          <span class="caps nomarg">Publicerat &amp; utkast</span>
          <div class="ovtabs">
            <button class:on={overviewTab === 'publicerat'} on:click={() => (overviewTab = 'publicerat')}>Publicerat {#if libPoster.length}<span class="ovn">{libPoster.length}</span>{/if}</button>
            <button class:on={overviewTab === 'utkast'} on:click={() => (overviewTab = 'utkast')}>Utkast {#if libUtkast.length + libUtkastDb.length}<span class="ovn ac">{libUtkast.length + libUtkastDb.length}</span>{/if}</button>
          </div>
        </div>

        {#if overviewTab === 'publicerat'}
          {#each libPoster as p (p.id)}
            <div class="ovrad" role="button" tabindex="0" title="Klicka för att ändra"
              on:click={() => laddaPost(p)} on:keydown={(e) => e.key === 'Enter' && laddaPost(p)}>
              <Hornmarkor farg="#6FB35A" r={10} titel="Publicerad" />
              <div class="ovthumb">{#if heroBildUrl(p)}<img src={heroBildUrl(p)} alt="" loading="lazy" />{/if}</div>
              <div class="ovmitt"><div class="ovtitel">{titelAv(p)}</div><div class="ovmeta">{datumText(p.synkad_tid || p.frontmatter?.datum, 'Publicerad')}</div></div>
              <button class="ovx" class:armerad={$armerad === `pub-${p.id}`}
                title={$armerad === `pub-${p.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                on:click|stopPropagation={taBortKlick(`pub-${p.id}`, () => raderaPost(p))}>
                {#if $armerad === `pub-${p.id}`}Ta bort?{:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>{/if}
              </button>
            </div>
          {:else}<div class="ovtom">Inget publicerat ännu.</div>{/each}
        {:else}
          {#each libUtkast as u (u.id)}
            <div class="ovrad" role="button" tabindex="0" title="Klicka för att fortsätta"
              on:click={() => laddaUtkast(u)} on:keydown={(e) => e.key === 'Enter' && laddaUtkast(u)}>
              <div class="ovthumb"></div>
              <div class="ovmitt"><div class="ovtitel">{u.titel || '(utan titel)'}</div><div class="ovmeta">{datumText(u.sparad, 'Sparad')}</div></div>
              <button class="ovx" class:armerad={$armerad === `utk-${u.id}`}
                title={$armerad === `utk-${u.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                on:click|stopPropagation={taBortKlick(`utk-${u.id}`, () => raderaUtkast(u.id))}>
                {#if $armerad === `utk-${u.id}`}Ta bort?{:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>{/if}
              </button>
            </div>
          {/each}
          {#each libUtkastDb as p (p.id)}
            <div class="ovrad" role="button" tabindex="0" title="Klicka för att fortsätta"
              on:click={() => laddaPost(p)} on:keydown={(e) => e.key === 'Enter' && laddaPost(p)}>
              <div class="ovthumb">{#if heroBildUrl(p)}<img src={heroBildUrl(p)} alt="" loading="lazy" />{/if}</div>
              <div class="ovmitt"><div class="ovtitel">{titelAv(p)}</div><div class="ovmeta">{datumText(p.skapad, 'Skapad')} · utkast</div></div>
              <button class="ovx" class:armerad={$armerad === `pub-${p.id}`}
                on:click|stopPropagation={taBortKlick(`pub-${p.id}`, () => raderaPost(p))}>
                {#if $armerad === `pub-${p.id}`}Ta bort?{:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>{/if}
              </button>
            </div>
          {/each}
          {#if !libUtkast.length && !libUtkastDb.length}<div class="ovtom">Inga sparade utkast.</div>{/if}
        {/if}
        <div class="ovfot">Status = grön hörnmarkering (publicerad) · klick på raden öppnar för ändring · utkast sparas löpande.</div>
      </div>
    {/if}
  {:else}
    <!-- ══ FOKUSERAD EDITOR ══ -->
    <div class="returrad">
      <button class="retur" on:click={stangEditor}>‹ Biblioteket</button>
      <span class="retursub">Redigerar {TYP_NAMN[ctyp]?.toLowerCase() || ctyp} · utkast sparas löpande</span>
    </div>

    {#if ctyp === 'match'}
      <!-- ── Matchartikel (4b) ── -->
      <div class="kort">
        <div class="caps">Artikel för match</div>
        <select class="artval" value={artMatchId} on:change={cmsPick}>
          {#each matcher as m (m.id)}
            <option value={m.id}>{m.lag_hemma} – {m.lag_borta} · {datumKort(m.datum) || 'utan datum'}{m.resultat ? ` · ${m.resultat}` : ''}</option>
          {/each}
        </select>
      </div>

      {#if artMatch}
        <ResultatRemsa match={artMatch} {profil} {lagAlla} on:sparat={onResSparat} />
        <div class="remstext">Delad matchdata — samma värden som Live &amp; SoMe. Etikett: Live · SoMe · Webb.</div>
      {/if}

      <div class="kort">
        <div class="korthuvud"><span class="caps nomarg">Publicera till hemsidan</span>
          <button class="minilank" on:click={hamtaAllt} title="Återkoppla alla fält till matchen">↺ Hämta allt</button>
        </div>
        <div class="grid2">
          {#each [
            { f: 'hem', lbl: 'Hemmalag' }, { f: 'borta', lbl: 'Bortalag' },
            { f: 'resultat', lbl: profil.res_label || 'Slutresultat' },
            { f: 'mellan', lbl: profil.mid_label || 'Halvtid' },
            { f: 'datum', lbl: 'Datum', typ: 'date' }, { f: 'serie', lbl: 'Serie' },
            { f: 'arena', lbl: 'Arena' }, { f: 'pixieset', lbl: 'Galleri-URL (Pixieset)' },
            ...(profil.has_scorers ? [{ f: 'malskyttar', lbl: profil.scorers_label || 'Målskyttar' }] : []),
          ] as falt (falt.f)}
            <div class="f">
              <label>{falt.lbl}
                {#if cmsMatch.own[falt.f]}
                  <button class="fkoppel egen" on:click={() => hamtaFalt(falt.f)} title="Egen text — klicka för att hämta från matchen">egen · ↺</button>
                {:else if artMatch}
                  <span class="fkoppel" title="Kopplat till matchen">⛓</span>
                {/if}
              </label>
              {#if falt.typ === 'date'}
                <input type="date" value={cmsMatch[falt.f]} on:input={(e) => sattEget(falt.f, e.target.value)} />
              {:else}
                <input value={cmsMatch[falt.f]} on:input={(e) => sattEget(falt.f, e.target.value)} />
              {/if}
            </div>
          {/each}
        </div>
      </div>

      <div class="kort">
        <div class="korthuvud">
          <span class="caps nomarg">Referat</span>
          <div class="genrad">
            <button class="statusbtn" on:click={pullFromSome} disabled={!artMaterial}
              title={artMaterial ? 'Hämta texten Matchpublicering producerade' : 'Inget material för matchen i Matchpublicering ännu'}>
              ↓ Hämta från Matchpublicering</button>
            <button class="genbtn" on:click={oppnaGranska} disabled={genererar || laddarFraga} title="Skriv referatet med Claude">
              <svg viewBox="0 0 24 24" fill="currentColor" class="stjarna"><path d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/></svg>
              {laddarFraga ? 'Bygger fråga…' : genererar ? 'Genererar…' : 'Regenerera'}
            </button>
          </div>
        </div>
        {#if granska}
          <div class="granska">
            <div class="granskaTitel">Granska frågan innan den skickas till Claude</div>
            <pre class="granskaFraga">{granska}</pre>
            <div class="granskaKnappar">
              <button class="statusbtn" on:click={() => (granska = null)}>Avbryt</button>
              <button class="prim" on:click={skickaTillClaude}>Skicka till Claude ›</button>
            </div>
          </div>
        {:else if genererar}
          <div class="genprog"><span class="genspin"></span>Genererar… {genSek}s (websöker matchfakta, tar ofta ~2 min)</div>
        {/if}
        {#if genFel}<div class="synkfel">{genFel}</div>{/if}
        {#if svepFlash}<div class="ok sm">{svepFlash}</div>{/if}
        <textarea rows="5" value={cmsMatch.svep} on:input={(e) => { cmsMatch.svep = e.target.value; forhandsgranska() }}></textarea>
        <div class="webprev">
          <div class="prevlbl">Så publiceras texten (utan # / @)</div>
          <div class="prevtext">{svepWebb}</div>
        </div>
      </div>
    {:else if ctyp === 'sportevent'}
      <!-- ── Event/mästerskap (1e) ── -->
      <div class="kort">
        <div class="korthuvud"><span class="caps nomarg">Kopplad till heldagsaktivitet</span>
          <span class="capshint">skapas från Fotojobb</span></div>
        <select class="artval" value={cmsSportevent.fotojobbId} on:change={valjSporteventJobb}>
          <option value="">— Välj heldagsaktivitet…</option>
          {#each heldagsJobb as j (j.id)}
            <option value={j.id}>{j.title} · {(j.start_at || '').slice(0, 10)}</option>
          {/each}
        </select>
        {#if !heldagsJobb.length}<div class="ovtom">Inga heldagsaktiviteter i Fotojobb — skapa en där först.</div>{/if}
      </div>
      <div class="kort">
        <div class="caps">Event/mästerskap</div>
        <div class="grid2">
          <div class="f"><label>Titel</label><input bind:value={cmsSportevent.titel} on:change={forhandsgranska} /></div>
          <div class="f"><label>Period</label><input bind:value={cmsSportevent.period} on:change={forhandsgranska} placeholder="t.ex. 29 jun – 5 jul" /></div>
          <div class="f"><label>Plats</label><input bind:value={cmsSportevent.plats} on:change={forhandsgranska} /></div>
          <div class="f"><label>Datum</label><input type="date" bind:value={cmsSportevent.datum} on:change={forhandsgranska} /></div>
        </div>
        <div class="f mt"><label>Ingress</label><textarea rows="3" bind:value={cmsSportevent.ingress} on:change={forhandsgranska}></textarea></div>
      </div>
      <div class="kort">
        <div class="korthuvud"><span class="caps nomarg">Underartiklar</span>
          <span class="capshint">manuellt valda matcher — egna artiklar, egna gallerier</span></div>
        {#each cmsSportevent.underartiklar as u, i (u.match_id)}
          {@const art = subArtikel(u)}
          <div class="subrad">
            <span class="subprick" class:klar={!!art}></span>
            <div class="submitt">
              <div class="subtitel">{u.titel}</div>
              <div class="submeta">{art ? `egen artikel${art.frontmatter?.resultat ? ' · ' + art.frontmatter.resultat : ''}` : 'vald, ej skapad'}</div>
            </div>
            <button class="statusbtn sm" on:click={() => oppnaUnderartikel(u)}>{art ? 'Öppna artikel ›' : 'Skapa artikel ›'}</button>
            <button class="ovx" class:armerad={$armerad === `sub-${i}`}
              on:click={taBortKlick(`sub-${i}`, () => taUnderartikel(i))}>{$armerad === `sub-${i}` ? 'Ta bort?' : '×'}</button>
          </div>
        {/each}
        <div class="subval">
          <button class="figadd" on:click={() => (subValOppen = !subValOppen)}>+ Lägg till match</button>
          {#if subValOppen}
            <div class="sublista">
              {#each matcher.filter((m) => !cmsSportevent.underartiklar.some((u) => u.match_id === m.id)) as m (m.id)}
                <button class="subvalrad" on:click={() => laggUnderartikel(m)}>
                  <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
                  {m.lag_hemma} – {m.lag_borta} <span class="submeta">· {datumKort(m.datum)}{m.resultat ? ` · ${m.resultat}` : ''}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
        <div class="ovfot">Underartiklarna länkas från eventsidan på sajten (/sportevent/{aktSlug || '…'}).</div>
      </div>
    {:else if ctyp === 'event'}
      <div class="kort">
        <div class="caps">Fotouppdrag — ej match-relaterat</div>
        <div class="grid2">
          <div class="f"><label>Titel</label><input bind:value={cmsEvent.titel} on:change={forhandsgranska} /></div>
          <div class="f"><label>Kategori</label>
            <select bind:value={cmsEvent.kategori} on:change={forhandsgranska}>
              {#each EVENT_KAT as k}<option value={k}>{k}</option>{/each}
            </select>
          </div>
          <div class="f"><label>Kund</label><input bind:value={cmsEvent.kund} on:change={forhandsgranska} /></div>
          <div class="f"><label>Datum</label><input type="date" bind:value={cmsEvent.datum} on:change={forhandsgranska} /></div>
          <div class="f"><label>Plats</label><input bind:value={cmsEvent.plats} on:change={forhandsgranska} /></div>
        </div>
        <div class="f mt"><label>Ingress</label><textarea rows="3" bind:value={cmsEvent.ingress} on:change={forhandsgranska}></textarea></div>
      </div>
    {:else if ctyp === 'landskap'}
      <div class="kort">
        <div class="caps">Bildserie</div>
        <div class="grid2">
          <div class="f"><label>Titel</label><input bind:value={cmsLandskap.titel} on:change={forhandsgranska} /></div>
          <div class="f"><label>Tema</label>
            <div class="temalast" title="Temat härleds ur innehållstypen — Landskap är alltid Sol">
              <span class="temaprick"></span><span class="temanamn">Sol</span>
              <span class="temainfo">· låst för Landskap</span>
            </div>
          </div>
          <div class="f"><label>Plats</label><input bind:value={cmsLandskap.plats} on:change={forhandsgranska} /></div>
          <div class="f"><label>Period</label><input bind:value={cmsLandskap.period} on:change={forhandsgranska} placeholder="t.ex. sep–okt 2026" /></div>
        </div>
        <div class="f mt"><label>Ingress</label><textarea rows="3" bind:value={cmsLandskap.ingress} on:change={forhandsgranska}></textarea></div>
      </div>
    {:else if ctyp === 'film'}
      <div class="kort">
        <div class="caps">Film — analog / stillbild</div>
        <div class="grid2">
          <div class="f"><label>Titel</label><input bind:value={cmsFilm.titel} on:change={forhandsgranska} /></div>
          <div class="f"><label>Tema</label>
            <div class="temalast" title="Temat härleds ur innehållstypen">
              <span class="temaprick"></span><span class="temanamn">Sol</span>
              <span class="temainfo">· låst för Film</span>
            </div>
          </div>
        </div>
        <div class="f mt"><label>Ingress</label><textarea rows="3" bind:value={cmsFilm.ingress} on:change={forhandsgranska}></textarea></div>
      </div>
    {:else}
      <div class="kort">
        <div class="caps">Journal / reseberättelse</div>
        <div class="grid2">
          <div class="f"><label>Titel</label><input bind:value={cmsBlogg.titel} on:change={forhandsgranska} /></div>
          <div class="f"><label>Kategori</label><input bind:value={cmsBlogg.kategori} on:change={forhandsgranska} placeholder="t.ex. Resor" /></div>
          <div class="f"><label>Datum</label><input type="date" bind:value={cmsBlogg.datum} on:change={forhandsgranska} /></div>
        </div>
        <div class="f mt"><label>Ingress</label><textarea rows="2" bind:value={cmsBlogg.ingress} on:change={forhandsgranska}></textarea></div>
        <div class="f mt"><label>Brödtext (markdown) · högerklick infogar bild</label>
          <textarea rows="6" bind:value={cmsBlogg.body} on:change={forhandsgranska} on:contextmenu={blCtx}></textarea>
        </div>
        <div class="blimghjalp">Högerklicka i texten för att infoga en bild ur galleriet där markören står — <span class="mono">[bild 2]</span> byts mot bilden vid publicering. Bilder utan token hamnar som galleri sist i inlägget.</div>
        {#if (cmsBlogg.body || '').trim()}
          <div class="f mt"><label>Förhandsvisning</label>
            <div class="bodyprev">{@html cmsBlogg.body}</div>
          </div>
        {/if}
      </div>

      {#if blImgMeny}
        <div class="blimgoverlay" on:click={blImgClose} on:contextmenu|preventDefault={blImgClose} role="presentation"></div>
        <div class="blimgmeny" style={blImgMenyStil}>
          <div class="blimgrubrik">Infoga bild vid markören</div>
          {#each cmsBlogg.figurer as b, i (b)}
            <button type="button" class="blimgrad" on:click={() => blInsertImg(i)}>
              <span class="blimgtn">{#if figThumbSrc(b)}<img src={figThumbSrc(b)} alt="" />{:else}<span class="blimgn">{i + 1}</span>{/if}</span>
              <span class="blimgtxt">
                <span class="blimglbl">{b.alt || `Bild ${i + 1}`}</span>
                <span class="blimgtok mono">[bild {i + 1}]</span>
              </span>
            </button>
          {/each}
          {#if !cmsBlogg.figurer.length}<div class="blimgtom">Inga bilder i galleriet ännu.</div>{/if}
        </div>
      {/if}

      <div class="kort">
        <div class="caps">Platser &amp; tips</div>
        <div class="figurer">
          {#each cmsBlogg.platser as p, i}
            <div class="platsrad">
              <input class="pl" bind:value={p.plats} on:change={forhandsgranska} placeholder="Plats" />
              <input class="pt" bind:value={p.tips} on:change={forhandsgranska} placeholder="Tips" />
              <button class="figx" class:armerad={$armerad === `plats-${i}`}
                title={$armerad === `plats-${i}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                on:click={taBortKlick(`plats-${i}`, () => taPlats(i))}>{$armerad === `plats-${i}` ? 'Ta bort?' : '×'}</button>
            </div>
          {/each}
          <button class="figadd" on:click={laggPlats}>+ Lägg till plats</button>
        </div>
      </div>
    {/if}

    <div class="kort">
      <div class="caps">Hero-bild <span class="capshint">· 21:9, fokuspunkten styr beskärningen på sajten</span></div>
      {#key ctyp}
        <BildvaljareFokuspunkt visaFormatval={false}
          bind:hero={akt.hero} bind:heroPosition={akt.heroPosition} bind:heroKalla={akt.heroKalla}
          on:change={heroAndrad} />
      {/key}
    </div>

    <div class="kort">
      <div class="galhuvud">
        <span class="caps nomarg">Galleri</span>
        <div class="genrad">
          {#if ctyp === 'match'}
            <button class="statusbtn sm" on:click={pullHighlights} title="Fyll galleriet med toppbilder ur det aktiva urvalet (Gallra)">Hämta höjdpunkter</button>
          {/if}
          <span class="galhint">{galText ? 'dra för att ordna om · bildtext per bild' : 'dra för att ordna om · endast bild'}</span>
        </div>
      </div>
      {#if hpFel}<div class="synkfel">{hpFel}</div>{/if}
      <div class="galgrid">
        {#each akt.figurer as b, i (b)}
          <div class="figtile" class:drar={dragIdx === i} draggable="true"
            on:dragstart={() => dragStart(i)} on:dragover={(e) => dragOver(i, e)} on:drop={() => slapp(i)} on:dragend={() => (dragIdx = null)}>
            <button type="button" class="figthumb" class:has={!!figThumbSrc(b)}
              on:click={() => valjFigurBild(i)} title="Välj bild">
              {#if figThumbSrc(b)}<img src={figThumbSrc(b)} alt="" draggable="false" />{:else}<span>+ bild {i + 1}</span>{/if}
              {#if ctyp === 'blogg' && blUsed.has(i)}<span class="itexten">I TEXTEN</span>{/if}
            </button>
            <button class="figx" class:armerad={$armerad === `fig-${i}`}
              title={$armerad === `fig-${i}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
              on:click={taBortKlick(`fig-${i}`, () => taBild(i))}>{$armerad === `fig-${i}` ? 'Ta bort?' : '×'}</button>
            {#if galText}
              {#if b.src}<div class="figsrc">från urval · {b.src}</div>{/if}
              <input class="figcap" bind:value={b.bildtext} on:change={forhandsgranska} placeholder="Bildtext…" />
              <input class="figalt" bind:value={b.alt} on:change={forhandsgranska} placeholder="Alt-text (tillgänglighet)" />
            {:else}
              <div class="figref">{(b.bild || '').startsWith('http') ? b.bild : `/bilder/${aktSlug}/${i + 1}.jpg`}</div>
            {/if}
          </div>
        {/each}
        <button class="figaddtile" on:click={laggBild}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>
          <span>Lägg till</span>
        </button>
      </div>
    </div>

    <div class="kort">
      <div class="mdhuvud"><span class="caps">Markdown · förhandsvisning</span></div>
      <pre>{md}</pre>
      <div class="mdfot">
        {#if ctyp === 'match' || ctyp === 'sportevent'}
          <button class="statusbtn" on:click={sparaUtkastDb}>Spara utkast</button>
          {#if sparadDb}<span class="ok">✓ Utkast sparat</span>{/if}
        {/if}
        <button class="prim" on:click={spara}>Spara .md-fil</button>
        {#if sparad}
          {#if $testMode}<span class="ok testhint">✓ Test — exempelfil: <span class="testpath">{sparadPath}</span> · rensas vid omstart</span>
          {:else}<span class="ok">✓ Sparad till content/{EDITOR_MAPP[ctyp]}/</span>{/if}
        {/if}
        <button class="prim" on:click={publicera} disabled={synkar}>
          {synkar ? 'Publicerar…' : 'Publicera till hemsidan'}</button>
        {#if synkad}
          {#if $testMode}<span class="ok testhint">✓ Test — exempelfil: <span class="testpath">{synkadPath}</span> · rensas vid omstart</span>
          {:else}<span class="ok">✓ Publicerad</span>{/if}
        {/if}
        {#if synkFel}<span class="synkfel">{synkFel}</span>{/if}
        {#if publiceradId}
          <button class="statusbtn" on:click={kollaStatus} disabled={statusLaddar}>{statusLaddar ? 'Kollar…' : 'Kolla status'}</button>
          {#if deployText}<span class="deploystatus">{deployText}</span>{/if}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 760px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--t-head); }   /* 6a: paneltitel 20px */
  .sub { font-size: 13px; color: var(--t-mut); }

  /* Typ-nav (bibliotek) + Skapa nytt */
  .libnav { display: flex; align-items: center; gap: 10px; margin-top: 16px; }
  .cmstabs { flex: 1; display: flex; gap: 4px; padding: 4px; border: 1px solid var(--div);
    border-radius: 12px; background: var(--panel); box-shadow: var(--skugga); }
  .cmstab { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    padding: 9px 10px; border: none; border-radius: 9px; background: transparent; color: var(--t-mut);
    font-size: 13.5px; font-weight: 600; }
  .cmstab .cmstik { display: inline-flex; align-items: center; justify-content: center; color: currentColor; }
  .cmstab .cmstik svg { width: 16px; height: 16px; }
  .cmstab .cmstnamn { font-weight: 700; }
  .cmstab.on { background: var(--tf); color: #fff; box-shadow: var(--skugga); }
  .cmstab:hover:not(.on) { color: var(--tf); background: color-mix(in srgb, var(--tf) 10%, transparent); }
  .nyknapp { flex: none; background: var(--acc); color: #fff; border: 0; border-radius: 9px;
    padding: 10px 15px; font-size: 12.5px; font-weight: 600; }
  .cmssub { font-size: 11.5px; color: var(--t-mut); margin: 8px 2px 0; }
  .cmshint2 { color: var(--t-help); }

  /* Bibliotekets rader (publicerat & utkast) */
  .oversikt { margin-top: 14px; }
  .ovhuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .ovhuvud.mt14 { margin-top: 18px; }
  .ovtabs { display: flex; gap: 3px; background: var(--div3); border-radius: 9px; padding: 3px; }
  .ovtabs button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 13px; border: 0; border-radius: 7px;
    background: transparent; color: var(--t-mut); font-size: 12px; font-weight: 600; }
  .ovtabs button.on { background: var(--kort); color: var(--t-head); box-shadow: var(--skugga); }
  .ovn { font-size: 10px; font-weight: 700; color: var(--t-mut); background: var(--div); border-radius: 999px; padding: 1px 6px; }
  .ovn.ac { color: var(--ink); background: var(--acc); }
  .ovrad { position: relative; overflow: hidden; display: flex; align-items: center; gap: 11px; cursor: pointer;
    background: var(--panel); border: 1px solid var(--div3); border-radius: 10px; padding: 9px 12px; margin-bottom: 7px; }
  .ovrad:hover { border-color: var(--acc); }
  .ovthumb { width: 42px; height: 42px; flex: none; border-radius: 7px; overflow: hidden;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 6px, var(--kort) 6px, var(--kort) 12px); }
  .ovthumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .ovmitt { flex: 1; min-width: 0; }
  .ovtitel { font-size: 13px; font-weight: 600; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ovmeta { font-size: 11px; color: var(--t-mut); margin-top: 2px; }
  .ovx { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 7px;
    border: 1px solid var(--div); background: var(--kort); color: var(--t-mut); }
  .ovx svg { width: 14px; height: 14px; }
  .ovx:hover { border-color: #C0453E; color: #C0453E; }
  .ovx.armerad { width: auto; padding: 0 10px; background: #C0453E; border-color: #C0453E; color: #fff; font-size: 11px; font-weight: 600; }
  .ovtom { font-size: 12.5px; color: var(--t-help); padding: 4px 2px; }
  .ovfot { font-size: 11px; color: var(--t-help); margin-top: 10px; }

  /* Sport-startsidan */
  .sportstart { margin-top: 14px; }
  .toppval { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .tvlbl { font-size: 11px; color: var(--t-mut); }
  .tvchip { padding: 6px 12px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 11.5px; font-weight: 600; }
  .tvchip.on { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .tvchip:disabled { opacity: 0.45; }
  .tvselect { width: auto; font-size: 12px; padding: 6px 8px; }
  .herokort { position: relative; display: block; width: 100%; border: 1px solid var(--div); border-radius: 12px;
    overflow: hidden; padding: 0; background: var(--panel); text-align: left; cursor: pointer; }
  .herokort:hover { border-color: var(--acc); }
  .herobild { display: block; width: 100%; aspect-ratio: 16/6; object-fit: cover; }
  .herobild.platt { background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 10px, var(--kort) 10px, var(--kort) 20px); }
  .herotext { position: absolute; left: 0; right: 0; bottom: 0; padding: 26px 16px 12px;
    background: linear-gradient(transparent, rgba(7, 9, 12, 0.78)); }
  .herokicker { font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #E8E4DC; }
  .herotitel { font-size: 19px; font-weight: 700; color: #fff; }
  .toppbadge { position: absolute; top: 10px; right: 10px; font-size: 9.5px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; background: var(--acc); color: #fff; padding: 3px 9px; border-radius: 999px; }
  .sportgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .sportkort { position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 6px; text-align: left;
    border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 10px; cursor: pointer; }
  .sportkort:hover { border-color: var(--acc); }
  .skthumb { width: 100%; aspect-ratio: 4/3; border-radius: 7px; overflow: hidden;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 7px, var(--kort) 7px, var(--kort) 14px); }
  .skthumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .sktitel { font-size: 12.5px; font-weight: 700; color: var(--t-head); }
  .skmeta { font-size: 10.5px; color: var(--t-mut); }
  .tavlingbadge { position: absolute; top: 16px; left: 16px; z-index: 2; font-size: 9px; font-weight: 700;
    letter-spacing: 0.06em; text-transform: uppercase; background: #C9871F; color: #fff; padding: 2px 8px; border-radius: 999px; }
  .sportkort.nyartikel { align-items: center; justify-content: center; gap: 8px; border-style: dashed;
    color: var(--t-mut); font-size: 12px; font-weight: 600; min-height: 130px; }
  .sportkort.nyartikel svg { width: 18px; height: 18px; }
  .sportkort.nyartikel:hover { color: var(--acc); }

  /* På gång */
  .ordna { border: 1px solid var(--div); background: var(--kort); border-radius: 999px; padding: 5px 12px;
    font-size: 11.5px; font-weight: 600; color: var(--t-mut); }
  .ordna:hover { border-color: var(--acc); color: var(--acc); }
  .pgrad2 { display: flex; flex-direction: column; gap: 6px; }
  .pgkort { display: flex; align-items: center; gap: 11px; border: 1px solid var(--div3); border-radius: 9px;
    background: var(--panel); padding: 7px 11px; }
  .pgdatum { width: 34px; text-align: center; flex: none; }
  .pgdag { display: block; font-size: 15px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .pgmon { font-size: 8.5px; font-weight: 700; letter-spacing: 0.1em; color: var(--t-help); }
  .grendot { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  .pgi { flex: 1; min-width: 0; }
  .pgf { font-size: 12px; font-weight: 600; color: var(--t-head); }
  .pgl { font-size: 10.5px; color: var(--t-mut); }
  /* På gång-kureringens stilar (visatoggle/chk/pgfot) flyttade till PaGang.svelte (§C). */

  /* Fokuserad editor: retur-rad */
  .returrad { display: flex; align-items: center; gap: 12px; }
  .retur { border: 1px solid var(--div); background: var(--kort); border-radius: 999px; padding: 8px 15px;
    font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .retur:hover { border-color: var(--acc); color: var(--acc); }
  .retursub { font-size: 11.5px; color: var(--t-mut); }

  /* Matchartikel */
  .artval { width: 100%; }
  .remstext { font-size: 11px; color: var(--t-mut); margin: 6px 0 0 2px; }
  .fkoppel { margin-left: 6px; font-size: 9.5px; color: var(--t-help); border: 0; background: none; padding: 0; }
  .fkoppel.egen { color: var(--acc); font-weight: 700; cursor: pointer; }
  .korthuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .minilank { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: 11.5px; padding: 0; cursor: pointer; }
  .genrad { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .genbtn { display: inline-flex; align-items: center; gap: 7px; background: var(--acc-soft);
    border: 1px solid var(--acc-border); color: var(--t-head); border-radius: 8px; padding: 7px 12px;
    font-size: 12px; font-weight: 600; }
  .genbtn:disabled { opacity: 0.55; }
  .stjarna { width: 13px; height: 13px; color: var(--acc); }
  .granska { border: 1px solid var(--acc-border); border-radius: 10px; padding: 12px; margin-bottom: 12px; background: var(--panel); }
  .granskaTitel { font-size: 12.5px; font-weight: 700; color: var(--t-head); margin-bottom: 8px; }
  .granskaFraga { max-height: 180px; }
  .granskaKnappar { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
  .genprog { display: flex; align-items: center; gap: 9px; font-size: 12px; color: var(--t-mut); margin-bottom: 10px; }
  .genspin { width: 13px; height: 13px; border: 2px solid var(--div); border-top-color: var(--acc);
    border-radius: 50%; animation: snurr 0.8s linear infinite; flex: none; }
  @keyframes snurr { to { transform: rotate(360deg); } }
  .webprev { margin-top: 10px; border-top: 1px dashed var(--div); padding-top: 10px; }
  .prevlbl { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--t-caps); margin-bottom: 5px; }
  .prevtext { font-size: 12.5px; color: var(--t-head); white-space: pre-wrap; line-height: 1.55; }

  /* Sportevent: underartiklar */
  .subrad { display: flex; align-items: center; gap: 10px; border: 1px solid var(--div3); border-radius: 9px;
    background: var(--panel); padding: 8px 11px; margin-bottom: 7px; }
  .subprick { width: 9px; height: 9px; border-radius: 50%; background: #C9871F; flex: none; }
  .subprick.klar { background: #6FB35A; }
  .submitt { flex: 1; min-width: 0; }
  .subtitel { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .submeta { font-size: 10.5px; color: var(--t-mut); }
  .subval { position: relative; }
  .sublista { margin-top: 8px; border: 1px solid var(--div); border-radius: 10px; background: var(--kort);
    max-height: 240px; overflow-y: auto; padding: 5px; }
  .subvalrad { display: flex; align-items: center; gap: 9px; width: 100%; text-align: left; border: 0;
    background: transparent; border-radius: 7px; padding: 8px 10px; font-size: 12.5px; color: var(--t-head); }
  .subvalrad:hover { background: var(--acc-soft); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; margin-top: 14px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-bottom: 12px; }
  .caps.nomarg { margin-bottom: 0; }
  .capshint { font-weight: 600; text-transform: none; letter-spacing: 0; color: var(--t-help); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .mt { margin-top: 12px; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  label { font-size: 11px; color: var(--t-mut); display: flex; align-items: center; }
  input, select, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 10px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, select:focus, textarea:focus { border-color: var(--acc); }
  textarea { line-height: 1.55; resize: vertical; }

  .temalast { display: inline-flex; align-items: center; gap: 9px; background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 8px 12px; align-self: flex-start; }
  .temaprick { width: 9px; height: 9px; border-radius: 50%; background: #C9871F; flex: none; }
  .temanamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .temainfo { font-size: 11px; color: var(--t-mut); }

  .galhuvud { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .galhint { font-size: 11px; color: var(--t-help); }

  .galgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; align-items: start; }
  .blimghjalp { font-size: 11px; color: var(--t-help); margin-top: 6px; line-height: 1.5; }
  .blimghjalp .mono { font-family: var(--mono, ui-monospace, monospace); }
  .blimgoverlay { position: fixed; inset: 0; z-index: 409; }
  .blimgmeny { background: var(--kort, var(--panel)); border: 1px solid var(--div);
    border-radius: 10px; box-shadow: 0 12px 34px rgba(0, 0, 0, 0.4); padding: 5px;
    display: flex; flex-direction: column; gap: 1px; }
  .blimgrubrik { font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--t-caps, var(--t-mut)); padding: 7px 9px 5px; }
  .blimgrad { display: flex; align-items: center; gap: 9px; width: 100%; text-align: left;
    background: transparent; border: none; border-radius: 7px; padding: 6px 8px; cursor: pointer;
    font-family: inherit; }
  .blimgrad:hover { background: var(--div3); }
  .blimgtn { position: relative; width: 44px; height: 33px; flex: none; border-radius: 5px;
    overflow: hidden; border: 1px solid var(--div3); display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 5px, var(--kort) 5px, var(--kort) 10px); }
  .blimgtn img { width: 100%; height: 100%; object-fit: cover; }
  .blimgn { font-family: var(--mono, ui-monospace, monospace); font-size: 9px; color: var(--t-mut); }
  .blimgtxt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .blimglbl { font-size: 12px; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .blimgtok { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-mut); }
  .blimgtom { font-size: 11.5px; color: var(--t-mut); padding: 7px 9px; }
  .itexten { position: absolute; left: 6px; bottom: 6px; font-size: 9px; font-weight: 700;
    letter-spacing: 0.05em; background: rgba(10, 13, 17, 0.72); color: var(--acc);
    border: 1px solid var(--div); border-radius: 5px; padding: 2px 6px; font-family: inherit; }
  .figtile { position: relative; display: flex; flex-direction: column; gap: 7px;
    border: 1px solid var(--div3); border-radius: 10px; padding: 8px; background: var(--panel); }
  .figtile.drar { opacity: 0.4; }
  .figthumb { width: 100%; min-height: 96px; border-radius: 7px; overflow: hidden; padding: 0; cursor: pointer;
    display: flex; align-items: center; justify-content: center; border: 1px solid var(--div); background: var(--kort);
    background-image: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .figthumb.has { border-style: solid; background-image: none; }
  .figthumb img { display: block; width: 100%; height: auto; }
  .figthumb span { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-mut); }
  .figthumb:hover { border-color: var(--acc); }
  .figcap, .figalt { background: var(--kort); font-size: 12px; padding: 6px 8px; }
  .figalt { font-size: 11px; color: var(--t-mut); }
  .figsrc { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-help); }
  .figref { font-family: var(--mono, ui-monospace, monospace); font-size: 11px; color: var(--t-mut); }
  .figx { position: absolute; top: 12px; right: 12px; z-index: 2; width: 26px; height: 26px; border-radius: 7px;
    border: 1px solid var(--div); background: color-mix(in srgb, var(--kort) 85%, transparent); color: var(--t-head); font-size: 15px; }
  .figx:hover { border-color: #C0453E; color: #C0453E; }
  .figx.armerad { width: auto; padding: 0 9px; background: #C0453E; border-color: #C0453E; color: #fff; font-size: 11px; font-weight: 600; }
  .figaddtile { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
    min-height: 120px; border: 1.5px dashed var(--div); border-radius: 10px; color: var(--t-mut); font-size: 12.5px; font-weight: 500; background: transparent; }
  .figaddtile svg { width: 20px; height: 20px; }
  .figaddtile:hover { border-color: var(--acc); color: var(--acc); }

  .bodyprev { border: 1px solid var(--div); border-radius: 9px; padding: 14px 16px;
    background: var(--panel); max-height: 520px; overflow-y: auto; font-size: 14px;
    line-height: 1.6; color: var(--t-body, var(--t-head)); }
  .bodyprev :global(img) { max-width: 100%; height: auto; border-radius: 6px; display: block; margin: 12px 0; }
  .bodyprev :global(figure) { margin: 14px 0; }
  .bodyprev :global(figcaption) { font-size: 12px; color: var(--t-mut); margin-top: 5px; }
  .bodyprev :global(blockquote) { margin: 14px 0; padding-left: 14px; border-left: 3px solid var(--acc);
    color: var(--t-mut); font-style: italic; }
  .bodyprev :global(h1), .bodyprev :global(h2), .bodyprev :global(h3) { color: var(--t-head); margin: 16px 0 8px; }
  .figurer { display: flex; flex-direction: column; gap: 10px; }
  .figadd { display: flex; align-items: center; justify-content: center; gap: 8px; border: 1.5px dashed var(--div); border-radius: 10px; padding: 11px; color: var(--t-mut); font-size: 13px; font-weight: 500; background: transparent; width: 100%; }
  .figadd:hover { border-color: var(--acc); color: var(--acc); }

  .platsrad { display: flex; gap: 8px; align-items: center; }
  .platsrad .pl { width: 38%; flex: none; background: var(--kort); font-size: 12.5px; padding: 7px 9px; }
  .platsrad .pt { flex: 1; min-width: 0; background: var(--kort); font-size: 12.5px; padding: 7px 9px; }

  .mdhuvud { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  pre { margin: 0; background: var(--panel); border: 1px solid var(--div3); border-radius: 8px; padding: 14px;
    font-family: var(--mono, ui-monospace, monospace); font-size: 12px; line-height: 1.6; color: var(--t-head);
    white-space: pre-wrap; word-break: break-word; max-height: 260px; overflow: auto; }
  .mdfot { display: flex; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 16px; font-size: 13px; font-weight: 600; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .ok.sm { font-size: 11.5px; margin-bottom: 8px; display: inline-block; }
  .testhint { color: var(--varn); }
  .testpath { font-family: var(--mono, ui-monospace, monospace); font-size: 11.5px; }
  .synkfel { font-size: 12.5px; color: #C0453E; font-weight: 600; }
  .statusbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 7px;
    padding: 8px 14px; font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }
  .statusbtn:disabled { opacity: 0.5; }
  .statusbtn.sm { padding: 6px 11px; font-size: 11.5px; }
  .deploystatus { font-size: 12.5px; color: var(--t-mut); font-weight: 600; }
</style>
