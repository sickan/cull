<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import { aktivMatch, genereraBildsvep, valjMapp, listaLag,
    listaSomeBilder, publiceraTillSoMe, oppnaILightroom, publiceraLiveStory,
    forhandsgranskaStory, listaMaterial, sparaMaterial, raderaMaterial,
    forsokIgenMaterial, sportprofiler, listaMatcher, nyTestPaketMapp } from '../lib/api.js'
  import AktivMatchRad from '../lib/AktivMatchRad.svelte'
  import Lagbricka from '../lib/Lagbricka.svelte'
  import { grenFarg } from '../lib/gren.js'
  import { testMode, testMaterial, nyttTestMaterial, uppdateraTestMaterial,
    raderaTestMaterial } from '../lib/testlage.js'

  const dispatch = createEventDispatcher()
  const bytMatch = () => dispatch('navigera', 'matcher')

  let flik = 'live'             // live | some
  let match = null
  let lagAlla = []
  let laddar = true

  // ── Live · steg 1: Favoriter → Lightroom ───────────────────────────────────
  let favKalla = ''
  let favStatus = ''
  let lrStatus = ''

  // ── Live · steg 2: välj bild ur Dropbox ────────────────────────────────────
  let liveDropbox = ''
  let liveBilder = []
  let liveVald = null           // index i liveBilder
  let brutna = {}               // filväg → true när miniatyren inte kan läsas

  // ── Live · steg 3: skapa story ─────────────────────────────────────────────
  const MOMENT = ['Avspark', 'Halvtid', 'Resultat', 'Startelva', 'Målgörare', 'Nästa match']
  const TEMAN = ['Hav', 'Sol', 'Rosé']
  const TEMAFARG = { Hav: '#2F7CB0', Sol: '#C9871F', 'Rosé': '#C9657F' }
  // Mall-specifika inputfält. multi → textarea, annars input (type styr, t.ex. time).
  const MALLFALT = {
    Avspark: [{ k: 'avspark', label: 'Avsparkstid', ph: '14:00', type: 'time' }],
    Halvtid: [{ k: 'halvtid', label: 'Ställning i halvtid', ph: '1–0' }],
    Resultat: [{ k: 'slutresultat', label: 'Slutresultat', ph: '6–0' },
      { k: 'malskyttar', label: 'Målskyttar', ph: 'Efternamn, efternamn…', multi: true }],
    Startelva: [{ k: 'startelva', label: 'Startelva (11)', ph: 'Målvakt · försvar · mittfält · anfall', multi: true }],
    'Målgörare': [{ k: 'malskott', label: 'Målskytt', ph: 'Efternamn' },
      { k: 'minut', label: 'Minut', ph: "58'" }],
    'Nästa match': [{ k: 'motstandare', label: 'Motståndare', ph: 'Lag' },
      { k: 'nextdatum', label: 'Datum & tid', ph: '12 jul 15:00' }],
  }
  // Svelte-gotcha: bind:value kan inte binda till funktionsanrop — en cfg-map
  // med alla nycklar initierad, bind till cfg.<fält>.
  let cfg = { avspark: '', halvtid: '', slutresultat: '', malskyttar: '',
    startelva: '', malskott: '', minut: '', motstandare: '', nextdatum: '' }
  let moment = 'Avspark'
  let tema = 'Hav'
  let livePub = { kor: false, klar: false, publicerad: false, fel: '', url: '', path: '' }
  let profiler = {}
  const PROFIL_FALLBACK = { start_moment: 'Avspark', mid_moment: 'Halvtid', mid_label: 'Halvtid',
    mid_ph: '1–0', mid_token: 'halvtid', res_label: 'Slutresultat', res_ph: '6–0', has_scorers: true,
    lineup: 'Startelva', lineup_n: '(11)', squad: true }
  $: profil = profiler[match?.sport] || profiler.fotboll || PROFIL_FALLBACK
  // Moment-namn i UI:t översätts från profilen; interna nycklar (kanoniska
  // Avspark/Halvtid/Resultat/Startelva/Målgörare/Nästa match) rör sig aldrig
  // — story_overlays _STATE_MAP och renderaren förblir opåverkade.
  $: momentLabel = { Avspark: profil.start_moment, Halvtid: profil.mid_moment,
    Resultat: 'Resultat', Startelva: `${profil.lineup}${profil.lineup_n ? ' ' + profil.lineup_n : ''}`,
    'Målgörare': 'Målgörare', 'Nästa match': 'Nästa match' }
  $: momentList = MOMENT.filter((m) =>
    (profil.has_scorers || m !== 'Målgörare') && (profil.squad || m !== 'Startelva'))
  $: if (!momentList.includes(moment)) moment = momentList[0] || 'Avspark'

  $: mallfalt = (MALLFALT[moment] || []).map((f) => {
    if (moment === 'Halvtid' && f.k === 'halvtid') return { ...f, label: profil.mid_label, ph: profil.mid_ph }
    if (moment === 'Resultat' && f.k === 'slutresultat') return { ...f, label: profil.res_label, ph: profil.res_ph }
    // Set-sporter saknar målskyttar — samma platsrad visar istället mellan-
    // resultatet (setsiffror), bundet till samma cfg-nyckel som Halvtid-
    // momentets fält (ingen dubblerad inmatning).
    if (moment === 'Resultat' && f.k === 'malskyttar' && !profil.has_scorers)
      return { k: 'halvtid', label: profil.mid_label, ph: profil.mid_ph, multi: false }
    if (moment === 'Startelva' && f.k === 'startelva') return { ...f, label: momentLabel.Startelva }
    return f
  })
  // Gren-markör i previewn: bara när en bild är vald + aktiva matchens gren är känd.
  // Samexisterar med tema-kickern — tema = innehållstyp, gren = kön/klass.
  $: ovGren = liveVald !== null ? (match?.hem_gren || '') : ''
  $: ovGrenStil = ovGren ? `border-color:${grenFarg(ovGren)};box-shadow:0 0 0 3px ${_rgba(grenFarg(ovGren), 0.16)}` : ''
  // 9:16-förhandsvisning: kicker = mall, stor text = mallens nyckelfält.
  $: fixtur = match ? `${match.lag_hemma} – ${match.lag_borta}` : 'Hemma – Borta'
  $: ov = {
    Avspark: { big: fixtur, small: profil.start_moment + ' ' + (cfg.avspark || '14:00') },
    Halvtid: { big: cfg.halvtid || '—', small: profil.mid_moment + ' · ' + fixtur },
    Resultat: { big: cfg.slutresultat || '—', small: (profil.has_scorers ? cfg.malskyttar : '') || '' },
    Startelva: { big: profil.lineup || 'Startelva', small: cfg.startelva || '' },
    'Målgörare': { big: 'MÅL ' + (cfg.minut || ''), small: cfg.malskott || '' },
    'Nästa match': { big: cfg.motstandare || '—', small: cfg.nextdatum || '' },
  }[moment] || { big: '', small: '' }

  async function valjFavKalla() { const r = await valjMapp('Välj källmapp'); if (r.ok) favKalla = r.path }
  async function lasFavoriter() {
    if (!favKalla) { const r = await valjMapp('Välj källmapp'); if (r.ok) favKalla = r.path; else return }
    favStatus = 'Läser favoritmärkta…'
    setTimeout(() => (favStatus = 'Favoriter inlästa (kör i workern).'), 400)
  }
  async function oppnaLR() {
    lrStatus = 'Öppnar Lightroom…'
    const r = await oppnaILightroom(favKalla)
    lrStatus = r?.ok ? '✓ Lightroom öppnad' : (r?.fel || 'Kunde inte öppna Lightroom.')
    setTimeout(() => (lrStatus = ''), 3200)
  }

  async function valjLiveDropbox() {
    const r = await valjMapp('Välj Dropbox-exportmapp')
    if (r.ok) { liveDropbox = r.path; await uppdateraDropbox() }
  }
  async function uppdateraDropbox() {
    if (!liveDropbox) return valjLiveDropbox()
    liveBilder = await listaSomeBilder(liveDropbox)
    if (liveVald !== null && liveVald >= liveBilder.length) liveVald = null
  }
  const bildUrl = (p) => (/^(https?|file):/.test(p) ? p : 'file://' + p)
  const bildNamn = (p) => (p || '').split('/').pop().replace(/\.[^.]+$/, '')

  function storyConfig() {
    const c = { foto: liveVald !== null ? liveBilder[liveVald] : '',
      moment, tema, ut_mapp: liveDropbox, match_id: match?.id, sport: match?.sport }
    if (moment === 'Avspark') c.avspark_tid = cfg.avspark
    if (moment === 'Halvtid') c.stallning = cfg.halvtid
    if (moment === 'Resultat') { c.stallning = cfg.slutresultat
      c.mal_rad = profil.has_scorers ? cfg.malskyttar : cfg.halvtid }
    if (moment === 'Startelva') c.startelva = cfg.startelva
    if (moment === 'Målgörare') c.mal_rad = [cfg.malskott, cfg.minut].filter(Boolean).join(' ')
    if (moment === 'Nästa match') { c.lag_borta = cfg.motstandare; c.next_when = cfg.nextdatum }
    return c
  }
  // Riktig förhandsvisning — samma Horisont-mall PIL renderar vid publicering,
  // inte bara CSS-approximationen. Debounce:ad (fältändringar/bildval) så vi
  // inte renderar på varje tangenttryck.
  let previewPath = ''
  let previewTick = 0
  let previewLoading = false
  let previewFel = ''
  let previewTimer = null
  function schedulePreview() {
    // Rör INTE previewPath här — senaste renderingen ska stå kvar (med en
    // "Renderar…"-badge ovanpå) tills nästa är klar, i stället för att blinka
    // tillbaka till CSS-skissen vid varje fältändring.
    if (previewTimer) clearTimeout(previewTimer)
    previewTimer = setTimeout(genereraForhandsvisning, 500)
  }
  async function genereraForhandsvisning() {
    if (liveVald === null) { previewPath = ''; previewFel = ''; return }
    previewLoading = true
    const r = await forhandsgranskaStory(storyConfig())
    previewLoading = false
    if (r?.ok) { previewPath = r.path; previewTick += 1; previewFel = '' }
    else previewFel = r?.fel || 'Kunde inte rendera förhandsvisningen.'
  }
  $: if (flik === 'live') { liveVald; moment; tema; cfg; schedulePreview() }

  async function publiceraStory() {
    livePub = { kor: true, klar: false, publicerad: false, fel: '', url: '', path: '' }
    const r = await publiceraLiveStory({ ...storyConfig(), test: $testMode })
    livePub = { kor: false, klar: !!r?.ok, publicerad: !!r?.publicerad,
      fel: r?.fel || (r?.ok ? '' : 'Fel vid publicering.'), url: r?.url || '', path: r?.path || '' }
    if (r?.ok && r?.publicerad) {
      await upsertMaterial(_liveMat('publicerad', livePub.path))
      setTimeout(() => (livePub = { ...livePub, klar: false }), 4200)
    }
  }

  // ── SoMe · Målbanor: ett paket, eget bildset per kanal ──────────────────────
  let someCaption = ''
  let someGen = false
  let someGenFel = ''

  // §5: bildtext-tokens — {resultat} {halvtid|setsiffror|periodsiffror|
  // gamesiffror beroende på sportprofil} {målskyttar} {arena} {motståndare}
  // {@lag} {#liga} {galleri} {datum} {tid}. Okända brickor lämnas orörda.
  const _hashtagify = (s) => (s || '').replace(/[^\p{L}\p{N}]/gu, '')
  function _resolveTokens(text, m, prof, lag) {
    if (!text) return ''
    const handle = (namn) => (lag.find((x) => x.namn === namn)?.instagram || '').replace(/^@/, '')
    const vals = {
      resultat: m?.resultat || '', [prof.mid_token]: m?.mellan || '',
      målskyttar: m?.malskyttar || '', arena: m?.arena || '', motståndare: m?.lag_borta || '',
      '@lag': handle(m?.lag_hemma) ? '@' + handle(m?.lag_hemma) : '',
      '#liga': m?.liga ? '#' + _hashtagify(m.liga) : '',
      galleri: m?.galleri || '', datum: m?.datum || '', tid: m?.tid || '',
    }
    return text.replace(/\{([^{}]+)\}/g, (whole, key) => (key in vals ? vals[key] : whole))
  }
  $: someCaptionResolved = _resolveTokens(someCaption, match, profil, lagAlla)
  $: someTokens = ['resultat', profil.mid_token].concat(profil.has_scorers ? ['målskyttar'] : [])
    .concat(['arena', 'motståndare', '@lag', '#liga', 'galleri', 'datum', 'tid'])
  function insertToken(tok) {
    someCaption += (someCaption && !/\s$/.test(someCaption) ? ' ' : '') + `{${tok}}`
  }
  let banor = {
    story: { pa: true, mapp: '', bilder: [] },
    ig: { pa: true, mapp: '', bilder: [] },
    fb: { pa: false, mapp: '', bilder: [] },
  }
  let someLage = 'idle'         // idle | dry | progress | done | delfel | fel
  let someResultat = []         // [{kanal, form, del, av, status, url, fel?}]
  let someFel = ''
  let someTestPath = ''         // testläge: gemensam mapp för senaste paket-körningen

  // Delplaner härleds live per bana — samma LÅSTA regler som backend.
  const _strippaFb = (t) => (t || '').replace(/[#@][\wåäöÅÄÖ]+/g, '').replace(/[ \t]{2,}/g, ' ')
    .replace(/ *\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
  // Tokenisering för FB-diffen — fångar taggar även intill skiljetecken ("#kdff.").
  const fbTokens = (t) => (t || '').split(/([#@][\wåäöÅÄÖ]+)/).filter((s) => s !== '')
    .map((s) => ({ s, bort: /^[#@][\wåäöÅÄÖ]+$/.test(s) }))

  $: storyPlanN = banor.story.pa ? banor.story.bilder.length : 0
  $: igBitar = (() => {
    const b = []; for (let i = 0; i < banor.ig.bilder.length; i += 10) b.push(banor.ig.bilder.slice(i, i + 10))
    return b
  })()
  $: igPlanN = banor.ig.pa ? igBitar.length : 0
  $: igVarning = banor.ig.pa && banor.ig.bilder.length > 10
    ? `${banor.ig.bilder.length} bilder → ${igBitar.length} IG-inlägg (max 10/karusell).` : ''
  $: fbPlanN = banor.fb.pa && banor.fb.bilder.length ? 1 : 0
  $: fbVarning = banor.fb.pa && banor.fb.bilder.length > 4
    ? `${banor.fb.bilder.length} bilder → kapas till 4 på Facebook.` : ''
  $: someRunCount = storyPlanN + igPlanN + fbPlanN
  $: someHarBilder = (banor.story.pa && banor.story.bilder.length) ||
    (banor.ig.pa && banor.ig.bilder.length) || (banor.fb.pa && banor.fb.bilder.length)

  function somePlanLista() {
    const p = []
    if (banor.story.pa) banor.story.bilder.forEach((_b, i) =>
      p.push({ kanal: 'instagram', form: 'story', n: 1, del: i + 1, av: banor.story.bilder.length }))
    if (banor.ig.pa) igBitar.forEach((bit, i) =>
      p.push({ kanal: 'instagram', form: 'inlägg', n: bit.length, del: i + 1, av: igBitar.length }))
    if (banor.fb.pa && banor.fb.bilder.length)
      p.push({ kanal: 'facebook', form: 'inlägg', n: Math.min(banor.fb.bilder.length, 4), del: 1, av: 1 })
    return p
  }
  const postLabel = (p) => `${p.kanal === 'instagram' ? 'Instagram' : 'Facebook'} · ${p.form === 'story' ? 'Story' : 'Inlägg'}${p.av > 1 ? ' ' + p.del + '/' + p.av : ''}`

  async function valjBanMapp(nyckel) {
    const r = await valjMapp('Välj mapp med färdiga bilder')
    if (!r.ok) return
    const bilder = await listaSomeBilder(r.path)
    banor = { ...banor, [nyckel]: { ...banor[nyckel], mapp: r.path, bilder } }
  }
  function togglaBana(nyckel) {
    banor = { ...banor, [nyckel]: { ...banor[nyckel], pa: !banor[nyckel].pa } }
  }

  async function someGenerera() {
    someGen = true
    someGenFel = ''
    const info = match ? `${match.lag_hemma}–${match.lag_borta}${match.resultat ? ' ' + match.resultat : ''}` : ''
    try {
      const r = await genereraBildsvep(info, match?.sport || '', fargForLag(match?.lag_hemma) || '')
      if (r?.ok) someCaption = r.bildsvep
      else someGenFel = r?.fel || 'Kunde inte generera bildtexten.'
    } catch (e) {
      someGenFel = 'Kunde inte generera bildtexten.'
    } finally {
      someGen = false
    }
  }

  function someTestkor() { if (someHarBilder) { someLage = 'dry'; someResultat = [] } }
  async function somePublicera() {
    if (!someHarBilder || someLage === 'progress') return
    someLage = 'progress'; someResultat = []; someFel = ''; someTestPath = ''
    // Ett paket, olika bildset per kanal → ett brygganrop per aktiv bana
    // (kontraktet {bilder, caption, mal} är stabilt; mal = enbart banans kanal).
    const korningar = [
      { nyckel: 'story', mal: { story: true, ig_inlagg: false, fb: false } },
      { nyckel: 'ig', mal: { story: false, ig_inlagg: true, fb: false } },
      { nyckel: 'fb', mal: { story: false, ig_inlagg: false, fb: true } },
    ].filter((k) => banor[k.nyckel].pa && banor[k.nyckel].bilder.length)
    // Testläge: EN gemensam mapp för hela paket-körningen (delas av alla
    // kanal-anropen nedan) i stället för en per kanal.
    let testMapp = ''
    if ($testMode) { const r = await nyTestPaketMapp(); testMapp = r?.path || '' }
    let fel = 0
    const chResults = {}
    for (const k of korningar) {
      const r = await publiceraTillSoMe({ bilder: banor[k.nyckel].bilder,
        caption: someCaptionResolved, mal: k.mal, match_id: match?.id,
        ...($testMode ? { test: true, test_mapp: testMapp } : {}) })
      chResults[k.nyckel] = r?.ok ? 'ok' : 'fail'
      if (r?.ok) {
        someResultat = [...someResultat, ...(r.resultat || [])]
      } else {
        fel++
        someResultat = [...someResultat, { kanal: k.nyckel === 'fb' ? 'facebook' : 'instagram',
          form: k.nyckel === 'story' ? 'story' : 'inlägg', del: 1, av: 1,
          status: 'fel', fel: r?.fel || 'Fel vid publicering.' }]
        someFel = r?.fel || 'Fel vid publicering.'
      }
    }
    someLage = fel === 0 ? 'done' : (fel === korningar.length ? 'fel' : 'delfel')
    someTestPath = $testMode ? testMapp : ''
    // Sparas ALLTID (inte bara vid full framgång) — en delvis publicering ska
    // synas i Sparade material med rätt kanalresultat och gå att försöka igen.
    const status = fel === 0 ? 'publicerad' : 'delvis'
    const felKanaler = korningar.filter((k) => chResults[k.nyckel] !== 'ok').map((k) => CHLABEL[k.nyckel])
    const historik_note = fel === 0 ? '' : `${felKanaler.join(', ')} föll`
    await upsertMaterial({ ..._someMat(status, someTestPath), ch_results: chResults, historik_note })
  }
  const someReset = () => { someLage = 'idle'; someResultat = []; someFel = '' }

  // ── Sparade material + utkast ────────────────────────────────────────────
  const CHLABEL = { story: 'IG Story', ig: 'IG-inlägg', fb: 'Facebook' }
  let materials = []
  let editMatId = null
  let matFilter = 'alla'
  let liveDraftFlash = false
  let someDraftFlash = false
  let retryingId = null
  let retryFlashId = null
  let historyOpen = {}
  const toggleHistory = (id) => (historyOpen = { ...historyOpen, [id]: !historyOpen[id] })

  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function prettyWhen(iso) {
    const [datum, tid] = (iso || '').replace(' ', 'T').split('T')
    const [y, m, d] = (datum || '').split('-').map(Number)
    if (!d) return iso || ''
    return `${d} ${MK[m - 1]} ${(tid || '').slice(0, 5)}`
  }

  async function retryMaterial(id) {
    if (retryingId) return
    retryingId = id
    const r = await forsokIgenMaterial(id)
    retryingId = null
    if (r?.ok && r.material?.status === 'publicerad') {
      retryFlashId = id
      setTimeout(() => (retryFlashId = retryFlashId === id ? null : retryFlashId), 2600)
    }
    await laddaMaterial()
  }

  async function laddaMaterial() { materials = await listaMaterial(); dispatch('materialAndrat') }
  // dropbox/foto och banor sparas med utkastet — annars återställer "Fortsätt"
  // bara moment/tema/caption och förhandsvisningen står tom (bildvalet borta).
  // path anges bara när ett riktigt (test-)flöde faktiskt skrev en fil —
  // aldrig vid "Spara utkast" (ingen rendering sker då, varken skarpt eller i
  // testläge — att visa en sökväg där vore att hitta på en fil som inte finns).
  const _liveMat = (status, path) => ({ kind: 'live', status, match_id: match?.id || null,
    match_namn: fixtur, moment, tema, dropbox: liveDropbox,
    foto: liveVald !== null ? liveBilder[liveVald] : null,
    ...(path ? { path } : {}) })
  const _someMat = (status, path) => ({ kind: 'some', status, match_id: match?.id || null,
    match_namn: fixtur, channels: Object.keys(banor).filter((k) => banor[k].pa), caption: someCaptionResolved,
    banor: { story: { mapp: banor.story.mapp, bilder: banor.story.bilder },
      ig: { mapp: banor.ig.mapp, bilder: banor.ig.bilder },
      fb: { mapp: banor.fb.mapp, bilder: banor.fb.bilder } },
    ...(path ? { path } : {}) })
  // Testläge: material skapas/uppdateras ENDAST i minnet (lib/testlage.js),
  // aldrig via sparaMaterial → publicera_material-tabellen (kontraktet: allt
  // testmaterial exkluderas ur persistens och försvinner vid omstart).
  async function upsertMaterial(data) {
    if ($testMode) {
      if (editMatId && $testMaterial.some((m) => m.id === editMatId)) {
        uppdateraTestMaterial(editMatId, data)
      } else {
        editMatId = nyttTestMaterial(data).id
      }
      return
    }
    const r = await sparaMaterial({ ...data, id: editMatId || undefined })
    if (r?.ok) editMatId = r.id
    await laddaMaterial()
  }
  async function saveLiveDraft() {
    await upsertMaterial(_liveMat('utkast'))
    liveDraftFlash = true
    setTimeout(() => (liveDraftFlash = false), 1800)
  }
  async function saveSomeDraft() {
    await upsertMaterial(_someMat('utkast'))
    someDraftFlash = true
    setTimeout(() => (someDraftFlash = false), 1800)
  }
  async function openMaterial(id) {
    const m = [...materials, ...$testMaterial].find((x) => x.id === id)
    if (!m) return
    editMatId = id
    if (m.kind === 'live') {
      flik = 'live'
      if (m.moment) moment = m.moment
      if (m.tema) tema = m.tema
      liveVald = null
      if (m.dropbox) {
        liveDropbox = m.dropbox
        await uppdateraDropbox()
        const i = m.foto ? liveBilder.indexOf(m.foto) : -1
        liveVald = i >= 0 ? i : null
      }
    } else {
      flik = 'some'
      someCaption = m.caption != null ? m.caption : someCaption
      const ch = m.channels || []
      const b = m.banor || {}
      banor = { story: { pa: ch.includes('story'), mapp: b.story?.mapp || '', bilder: b.story?.bilder || [] },
        ig: { pa: ch.includes('ig'), mapp: b.ig?.mapp || '', bilder: b.ig?.bilder || [] },
        fb: { pa: ch.includes('fb'), mapp: b.fb?.mapp || '', bilder: b.fb?.bilder || [] } }
    }
  }
  async function deleteMaterial(id) {
    if ($testMaterial.some((m) => m.id === id)) {
      raderaTestMaterial(id)
      if (editMatId === id) editMatId = null
      return
    }
    await raderaMaterial(id)
    if (editMatId === id) editMatId = null
    await laddaMaterial()
  }
  const setMatFilter = (v) => (matFilter = v)
  const newMaterial = () => (editMatId = null)

  // Testmaterial (in-memory, se lib/testlage.js) slås ihop med de sparade
  // (DB) materialen för listan/filtren/räkningarna — det är annars osynligt
  // trots att det ligger kvar tills omstart (kontraktet, punkt 2).
  $: allMaterial = [...materials, ...$testMaterial]
    .slice().sort((a, b) => (b.uppdaterad || '').localeCompare(a.uppdaterad || ''))
  $: matMatches = [...new Set(allMaterial.map((m) => m.match_namn).filter(Boolean))]
  $: matFiltered = allMaterial.filter((m) => matFilter === 'alla' ? true
    : matFilter === 'utkast' ? m.status === 'utkast'
    : matFilter === 'publicerad' ? m.status === 'publicerad'
    : matFilter === 'delvis' ? m.status === 'delvis'
    : m.match_namn === matFilter)
  $: materialsV = matFiltered.map((m) => ({
    id: m.id, isLive: m.kind === 'live', isTest: !!m.test, testPath: m.path || '',
    title: m.kind === 'live' ? `${m.moment || 'Story'}-story` : 'SoMe-paket',
    sub: m.match_namn || '—',
    meta: m.kind === 'live' ? `Live · tema ${m.tema || '—'}`
      : ((m.channels || []).map((c) => CHLABEL[c] || c).join(' · ') || 'inga kanaler'),
    when: prettyWhen(m.uppdaterad),
    status: m.status, openLabel: m.status === 'utkast' ? 'Fortsätt ›' : 'Öppna ›',
    channels: m.channels || [], chResults: m.ch_results || {},
    history: (m.history || []).map((h) => ({ ...h, when: prettyWhen(h.when) })) }))
  $: matFilterChips = [['alla', 'Alla'], ['utkast', 'Utkast'], ['publicerad', 'Publicerade'], ['delvis', 'Delvis'],
    ...matMatches.map((mm) => [mm, mm.length > 24 ? mm.slice(0, 22) + '…' : mm])]
  $: materialsEmpty = materialsV.length === 0
  $: draftCount = allMaterial.filter((m) => m.status === 'utkast').length
  $: delvisCount = allMaterial.filter((m) => m.status === 'delvis').length
  $: matEditing = editMatId != null
  $: matEdit = matEditing ? materials.find((m) => m.id === editMatId) : null
  $: matEditLabel = matEdit ? (matEdit.kind === 'live' ? `${matEdit.moment || 'Story'}-story` : 'SoMe-paket') : ''

  onMount(async () => {
    // Om bryggan hakar upp sig (eller kastar) ska panelen ändå lämna
    // "Laddar…" — annars sitter den fast tills man navigerar bort och
    // tillbaka (remount = ny chans). try/finally garanterar det.
    try {
      ;[match, lagAlla, profiler, allaMatcher] = await Promise.all(
        [aktivMatch(), listaLag(), sportprofiler(), listaMatcher()])
    } catch (e) {
      console.error('Publicera: kunde inte läsa aktiv match/lag', e)
    } finally {
      laddar = false
    }
    laddaMaterial()
  })

  // ── §8: Schemalagd publicering — UI-skiss, ingen bakgrundskörning ännu.
  // Rad-tillstånd är bara lokalt UI-state (nollställs vid omstart); manuell
  // körning ovan förblir oförändrad. Platshållare för en kommande handoff.
  let allaMatcher = []
  $: kommandeMatcher = allaMatcher.filter((m) => m.status !== 'avslutad')
    .sort((a, b) => (a.datum || '9999').localeCompare(b.datum || '9999')).slice(0, 5)
  let schedPa = {}   // `${matchId}:${radNyckel}` → true/false, förvalt PÅ
  // pa skickas in explicit (inte bara stängd över) — annars ser Svelte
  // aldrig att {#each schedRader(m)} beror på schedPa (samma reaktivitets-
  // gotcha som {@const}-funktioner: variabler lästa INNE i en funktionskropp
  // spåras inte, bara de som syns i själva mall-uttrycket).
  function schedRader(m, pa) {
    return [
      { key: 'ig', label: 'Nästa match · IG-inlägg', villkor: 'dagen före kl 18:00', redo: true },
      { key: 'uppst', label: 'Uppställnings-grafik · IG Story',
        villkor: '1 h före avspark · villkorad på uppställning', redo: (m.trupp_n || 0) > 0 },
      { key: 'galleri', label: 'Galleri-story', villkor: 'när Pixieset-länk finns', redo: !!m.galleri },
    ].map((r) => { const k = `${m.id}:${r.key}`; return { ...r, k, pa: pa[k] ?? true } })
  }
  function toggleSched(k) { schedPa = { ...schedPa, [k]: !(schedPa[k] ?? true) } }

  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }
  function loggaForLag(namn) { return lagAlla.find((x) => x.namn === namn)?.logga || '' }
  function _rgba(hex, a) { const n = parseInt((hex || '').replace('#', ''), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})` }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Publicera</h1>
    <span class="sub">Skapa och publicera material för sociala medier och hemsidan</span>
  </header>
  <AktivMatchRad on:navigera />

  <div class="tabs">
    <button class:on={flik === 'live'} on:click={() => (flik = 'live')}>Live</button>
    <button class:on={flik === 'some'} on:click={() => (flik = 'some')}>SoMe</button>
  </div>

  {#if laddar}
    <p class="tom">Laddar…</p>
  {:else if flik === 'live'}
    <div class="stack">
      <!-- Steg 1 · Favoriter → Lightroom -->
      <div class="kort">
        <div class="khuvud">
          <span class="steg scd">1</span>
          <div class="ktxt"><span class="kt scd">Favoriter → Lightroom</span><span class="ks">Hämtar de stjärnmärkta från kortet och öppnar dem i Lightroom för snabbredigering</span></div>
        </div>
        <div class="frad"><span class="fl">Källmapp</span><input class="mono" bind:value={favKalla} placeholder="/Volumes/NIKON Z 8/DCIM/…" /><button class="valj" on:click={valjFavKalla}>Välj…</button></div>
        <div class="hoger">
          {#if favStatus}<span class="ok">{favStatus}</span>
          {:else}<span class="hint fl1">Redigera i Lightroom, exportera sedan till Dropbox-mappen i steg 2.</span>{/if}
          {#if lrStatus}<span class="ok">{lrStatus}</span>{/if}
          <button class="sek" on:click={lasFavoriter}>Läs in favoriter</button>
          <button class="prim" on:click={oppnaLR}>Öppna i Lightroom ›</button>
        </div>
      </div>

      <!-- Steg 2 · Välj bild ur Dropbox -->
      <div class="kort">
        <div class="khuvud">
          <span class="steg scd">2</span>
          <div class="ktxt"><span class="kt scd">Välj bild ur Dropbox</span><span class="ks">De du exporterat ur Lightroom — välj en att göra story på</span></div>
        </div>
        <div class="frad"><span class="fl">Dropbox</span><input class="mono" bind:value={liveDropbox} placeholder="~/Dropbox/DPT/Live/…" /><button class="valj" on:click={valjLiveDropbox}>Välj…</button><button class="valj" on:click={uppdateraDropbox}>↻ Uppdatera</button></div>
        {#if liveBilder.length}
          <div class="dbgrid">
            {#each liveBilder as b, i (b)}
              <button class="dbtile" class:vald={liveVald === i} on:click={() => (liveVald = i)}>
                {#if !brutna[b]}
                  <img src={bildUrl(b)} alt="" loading="lazy" on:error={() => (brutna = { ...brutna, [b]: true })} />
                {/if}
                <span class="dbnamn">{bildNamn(b)}</span>
                {#if liveVald === i}<span class="bock">✓</span>{/if}
              </button>
            {/each}
          </div>
        {:else}
          <div class="hint mt">Inga bilder ännu — exportera från Lightroom och tryck ↻ Uppdatera.</div>
        {/if}
      </div>

      <!-- Steg 3 · Skapa story -->
      <div class="kort">
        <div class="khuvud">
          <span class="steg scd">3</span>
          <div class="ktxt"><span class="kt scd">Skapa story</span><span class="ks">9:16 med overlay-mall — publiceras som IG Story och sparas till Dropbox</span></div>
        </div>

        <div class="tvakol">
          <div class="kol1">
            <div class="capsrad"><span class="caps">Overlay-mall</span><span class="note">alla 9:16</span></div>
            <div class="rutnat3">{#each momentList as m}<button class="seg-b" class:on={moment === m} on:click={() => (moment = m)}>{momentLabel[m]}</button>{/each}</div>

            <div class="caps">Innehåll i mallen</div>
            <div class="falt">
              {#each mallfalt as f (moment + f.k)}
                <div>
                  <span class="flabel">{f.label}</span>
                  {#if f.multi}
                    <textarea bind:value={cfg[f.k]} placeholder={f.ph} rows="2"></textarea>
                  {:else if f.type === 'time'}
                    <input type="time" bind:value={cfg[f.k]} placeholder={f.ph} />
                  {:else}
                    <input bind:value={cfg[f.k]} placeholder={f.ph} />
                  {/if}
                </div>
              {/each}
            </div>

            <div class="caps">Tema</div>
            <div class="rutnat3">{#each TEMAN as t}<button class="tema-b" class:on={tema === t} style={tema === t ? `background:${TEMAFARG[t]};border-color:${TEMAFARG[t]}` : ''} on:click={() => (tema = t)}>{t}</button>{/each}</div>
          </div>

          <div class="kol2">
            <div class="caps mitt">Förhandsvisning</div>
            <div class="ovbox" class:harbild={liveVald !== null} class:ovgrenram={!!ovGren && !previewPath} style={previewPath ? '' : ovGrenStil}>
              {#if liveVald !== null}
                {#if previewPath}
                  <img class="ovfoto" src="file://{previewPath}?v={previewTick}" alt="" />
                {:else}
                  {#if !brutna[liveBilder[liveVald]]}
                    <img class="ovfoto" src={bildUrl(liveBilder[liveVald])} alt="" on:error={() => (brutna = { ...brutna, [liveBilder[liveVald]]: true })} />
                  {/if}
                  <div class="ovscrim">
                    <span class="ovkick" style="background:{TEMAFARG[tema]}">{moment}</span>
                    <div class="ovbig scd">{ov.big}</div>
                    {#if ov.small}<div class="ovsmall">{ov.small}</div>{/if}
                  </div>
                {/if}
                {#if previewLoading}<div class="ovladdar">Renderar…</div>{/if}
              {:else}
                <div class="ovtom">Välj en bild i steg 2</div>
              {/if}
            </div>
            {#if liveVald !== null}<div class="ovnamn">{bildNamn(liveBilder[liveVald])}</div>{/if}
            {#if previewFel}<div class="ovfel">⚠ {previewFel}</div>{/if}
          </div>
        </div>

        <div class="korrad">
          <span class="hint fl1" class:testhint={$testMode}>
            {$testMode ? 'Testläge — ingen riktig publicering · exempelfil skrivs till disk'
              : 'Publiceras som IG Story via SoMe API · filen sparas till Dropbox'}
          </span>
          {#if liveDraftFlash}<span class="ok">✓ Sparat</span>{/if}
          {#if livePub.klar && livePub.publicerad}
            <span class="ok">✓ Publicerad &amp; sparad{#if livePub.url}&nbsp;<a class="oppna" href={livePub.url} target="_blank" rel="noreferrer">öppna ›</a>{/if}</span>
            {#if $testMode && livePub.path}<span class="testpath">{livePub.path}</span>{/if}
          {/if}
          <button class="sek" on:click={saveLiveDraft} disabled={liveVald === null}>Spara utkast</button>
          <button class="prim" on:click={publiceraStory} disabled={livePub.kor || liveVald === null}>{livePub.kor ? 'Publicerar…' : 'Publicera story ›'}</button>
        </div>
        {#if livePub.fel}<div class="felbox">⚠ {livePub.fel}</div>{/if}
      </div>
    </div>
  {:else if flik === 'some'}
    <div class="stack">
      <div class="kort">
        <div class="khuvud">
          <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4M12 2v13"/></svg></span>
          <div class="ktxt"><span class="kt scd">Publicera till SoMe</span><span class="ks">Ett paket — välj bildset och text per kanal, se planen, publicera. Fungerar för Sport, Landskap och Event.</span></div>
        </div>

        <div class="matchrad">
          {#if match}
            <span class="brickor">
              <Lagbricka namn={match.lag_hemma} farg={fargForLag(match.lag_hemma)} logga={loggaForLag(match.lag_hemma)} storlek={30} />
              <span class="away"><Lagbricka namn={match.lag_borta} farg={fargForLag(match.lag_borta)} logga={loggaForLag(match.lag_borta)} storlek={30} /></span>
            </span>
            <div class="mrinfo"><div class="mrfix">{match.lag_hemma} – {match.lag_borta}</div><div class="mrsub">Sport · knyter match, moment &amp; tema till paketet</div></div>
          {:else}
            <div class="mrinfo"><div class="mrfix">Inget innehåll knutet</div><div class="mrsub">Paketet fungerar för Sport, Landskap och Event — matchkontext skickas med när den finns</div></div>
          {/if}
          <button class="lank" on:click={bytMatch}>Byt ›</button>
        </div>

        <div class="capsrad2"><span class="caps">Bildtext (delas av alla kanaler)</span><button class="genlank" on:click={someGenerera} disabled={someGen}>{someGen ? 'Genererar…' : '✨ Generera'}</button></div>
        {#if someGenFel}<div class="felbox">⚠ {someGenFel}</div>{/if}
        <textarea class="somecap" bind:value={someCaption} rows="3" placeholder="Bildsvep-text med #hashtags och @mentions…"></textarea>
        <div class="tokenrad">
          <span class="tokenlbl">Infoga bricka</span>
          {#each someTokens as t}<button class="tokenchip" on:click={() => insertToken(t)}>{'{' + t + '}'}</button>{/each}
        </div>
        <div class="somepreview">
          <div class="capsrad2"><span class="caps">Förhandsvisning</span>
            <span class="hint">{match ? `hämtat från ${match.lag_hemma} – ${match.lag_borta}` : 'ingen aktiv match kopplad'}</span></div>
          <div class="previewbox">{someCaptionResolved || '—'}</div>
        </div>

        <div class="caps mt">Kanaler &amp; bildset</div>
        <div class="kanaler">
          <!-- Story-banan -->
          <div class="kanal">
            <div class="krad">
              <button class="ktoggle" on:click={() => togglaBana('story')}><span class="box" class:pa={banor.story.pa}>{banor.story.pa ? '✓' : ''}</span><span class="knamn">Instagram Story</span></button>
              {#if banor.story.pa}
                {#if banor.story.bilder.length}<span class="antal">{banor.story.bilder.length} bilder → {banor.story.bilder.length} stories</span>{/if}
                <button class="valjbild" on:click={() => valjBanMapp('story')}>{banor.story.bilder.length ? 'byt bildset…' : 'Välj bildset…'}</button>
              {/if}
            </div>
            {#if banor.story.pa && banor.story.bilder.length}
              <div class="strip">{#each banor.story.bilder as _b, i}<span class="thumb"><b>{i + 1}</b></span>{/each}</div>
            {/if}
          </div>

          <!-- IG-inläggs-banan -->
          <div class="kanal">
            <div class="krad">
              <button class="ktoggle" on:click={() => togglaBana('ig')}><span class="box" class:pa={banor.ig.pa}>{banor.ig.pa ? '✓' : ''}</span><span class="knamn">Instagram-inlägg</span></button>
              {#if banor.ig.pa}
                {#if banor.ig.bilder.length}<span class="antal">{banor.ig.bilder.length === 1 ? 'enkel' : (igBitar.length > 1 ? igBitar.length + ' inlägg' : 'karusell · ' + banor.ig.bilder.length)}</span>{/if}
                <button class="valjbild" on:click={() => valjBanMapp('ig')}>{banor.ig.bilder.length ? 'byt bildset…' : 'Välj bildset…'}</button>
              {/if}
            </div>
            {#if banor.ig.pa && banor.ig.bilder.length}
              <div class="strip">{#each banor.ig.bilder.slice(0, 10) as _b, i}<span class="thumb">{#if i === 0}<em>omslag</em>{/if}</span>{/each}{#if banor.ig.bilder.length > 10}<span class="thumb plus">+{banor.ig.bilder.length - 10}</span>{/if}</div>
              {#if igVarning}<div class="varn">⚠ {igVarning}</div>{/if}
            {/if}
          </div>

          <!-- FB-banan -->
          <div class="kanal">
            <div class="krad">
              <button class="ktoggle" on:click={() => togglaBana('fb')}><span class="box" class:pa={banor.fb.pa}>{banor.fb.pa ? '✓' : ''}</span><span class="knamn">Facebook-sida</span></button>
              {#if banor.fb.pa}
                {#if banor.fb.bilder.length}<span class="antal">{Math.min(banor.fb.bilder.length, 4)} bilder · max 4</span>{/if}
                <button class="valjbild" on:click={() => valjBanMapp('fb')}>{banor.fb.bilder.length ? 'byt bildset…' : 'Välj bildset…'}</button>
              {/if}
            </div>
            {#if banor.fb.pa && banor.fb.bilder.length}
              <div class="strip">{#each banor.fb.bilder.slice(0, 6) as _b, i}<span class="thumb" class:dim={i >= 4}></span>{/each}</div>
              {#if fbVarning}<div class="varn">⚠ {fbVarning}</div>{/if}
            {/if}
            {#if banor.fb.pa}
              <div class="fbdiff"><div class="fbdifflbl">Facebook-text (utan #/@)</div><div class="fbtokens">{#each fbTokens(someCaptionResolved) as tk}<span class:bort={tk.bort}>{tk.s}</span>{/each}</div></div>
            {/if}
          </div>
        </div>

        {#if someLage === 'dry'}
          <div class="drybanner">Testkörning — <b>inget postades</b>. Planen är vad som skulle skickas.</div>
          <div class="planlista">{#each somePlanLista() as p}<div class="planrad"><span class="pdot"></span><span class="pl">{postLabel(p)}</span><span class="pn">{p.n} bild{p.n > 1 ? 'er' : ''}</span></div>{/each}</div>
        {:else if someLage === 'progress'}
          <div class="progress"><span class="spin"></span><div><div class="pt">Postar… {someRunCount} poster</div><div class="ps">Avbryt inte — poster som gått igenom rullas inte tillbaka.</div></div></div>
        {:else if someLage === 'done' || someLage === 'delfel'}
          <div class="donebox">
            <div class="donehuvud">
              {#if someLage === 'done'}<span class="okc">✓</span><span>Klart · {someResultat.filter((p) => p.status === 'postad').length} poster publicerade</span>
              {:else}<span class="felc">!</span><span>Delvis klart — {someResultat.filter((p) => p.status === 'postad').length} av {someResultat.length} gick fram</span>{/if}
              <button class="lank rst" on:click={someReset}>Nytt paket</button>
            </div>
            {#if $testMode && someTestPath}
              <div class="testrow">
                <span class="testbadge">TEST</span>
                <span>inget postades på riktigt · exempelfiler:</span>
                <span class="testpath">{someTestPath}</span>
              </div>
            {/if}
            {#each someResultat as p}
              <div class="donerad">
                {#if p.status === 'postad'}<span class="okc">✓</span>{:else}<span class="felc">✗</span>{/if}
                <span class="dl">{postLabel(p)}{#if p.fel}<span class="dfel"> — {p.fel}</span>{/if}</span>
                {#if p.url}<a class="oppna" href={p.url} target="_blank" rel="noreferrer">öppna ›</a>{/if}
              </div>
            {/each}
          </div>
        {:else if someLage === 'fel'}
          <div class="felbox">⚠ {someFel}</div>
          <div class="hint mt">Testkörning fungerar utan Meta-token — koppla kontot i Inställningar för skarp publicering.</div>
        {/if}

        <div class="korrad">
          {#if someDraftFlash}<span class="ok">✓ Sparat</span>{/if}
          <button class="prim" on:click={somePublicera} disabled={!someHarBilder || someLage === 'progress'}>Publicera skarpt · {someRunCount} poster</button>
          <button class="sek" on:click={someTestkor} disabled={!someHarBilder}>Testkör</button>
          <button class="sek" on:click={saveSomeDraft}>Spara utkast</button>
          <span class="summa">{someHarBilder ? someRunCount + ' poster' : 'Välj bilder i minst en kanal'}</span>
        </div>
      </div>
    </div>
  {/if}

  {#if !laddar && kommandeMatcher.length}
    <div class="schedsek">
      <div class="matrubrik"><span class="caps">Schemalagd publicering</span>
        <span class="hint">skiss — körs ännu bara manuellt ovan</span></div>
      <div class="schedlista">
        {#each kommandeMatcher as m (m.id)}
          <div class="schedkort">
            <div class="schedfix">{m.lag_hemma} – {m.lag_borta}<span class="scheddatum">{m.datum}{m.tid ? ' · ' + m.tid : ''}</span></div>
            {#each schedRader(m, schedPa) as r (r.k)}
              <button class="schedrad" on:click={() => toggleSched(r.k)}>
                <span class="box" class:pa={r.pa}>{r.pa ? '✓' : ''}</span>
                <span class="schedtxt"><span class="schedlbl">{r.label}</span><span class="schedvillkor">{r.villkor}{!r.redo ? ' · väntar på data' : ''}</span></span>
                {#if r.pa}<span class="schedstatus">Väntar</span>{/if}
              </button>
            {/each}
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#if !laddar}
    <div class="matsek">
      <div class="mathuvud">
        <div class="matrubrik"><span class="caps">Sparade material</span>
          <span class="hint">{allMaterial.length} totalt · {draftCount} utkast{delvisCount ? ` · ${delvisCount} delvis` : ''}</span></div>
        {#if matEditing}
          <div class="matbanner">
            <span>Redigerar: {matEditLabel}</span>
            <button class="nyknapp" on:click={newMaterial}>Nytt ＋</button>
          </div>
        {/if}
      </div>
      <div class="matchips">
        {#each matFilterChips as [id, label]}
          <button class="seg-b" class:on={matFilter === id} on:click={() => setMatFilter(id)}>{label}</button>
        {/each}
      </div>
      {#if materialsEmpty}
        <div class="mattom">Inga material här — spara ett utkast eller publicera för att se det.</div>
      {:else}
        <div class="matlista">
          {#each materialsV as mt (mt.id)}
            <div class="matrad">
              <span class="maticon" class:live={mt.isLive}>
                {#if mt.isLive}
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="3" width="16" height="18" rx="3"/><circle cx="12" cy="10" r="3"/><path d="M8 21v-1M16 21v-1"/></svg>
                {:else}
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4M12 2v13"/></svg>
                {/if}
              </span>
              <div class="mattxt">
                <div class="matrad1"><span class="matnamn">{mt.title}</span>
                  <span class="matstatus" class:pa={mt.status === 'publicerad'} class:delvis={mt.status === 'delvis'}>
                    {mt.status === 'utkast' ? 'Utkast' : mt.status === 'delvis' ? 'Delvis publicerad' : 'Publicerad'}
                  </span>
                  {#if mt.isTest}<span class="testbadge">TEST</span>{/if}
                  {#if mt.history.length > 1}
                    <button class="histchip" on:click={() => toggleHistory(mt.id)}>
                      {mt.history.length} publiceringar {historyOpen[mt.id] ? '▴' : '▾'}
                    </button>
                  {/if}
                </div>
                <div class="matsub">{mt.sub} · {mt.meta}</div>
                {#if mt.isTest && mt.testPath}<div class="testpathrow">{mt.testPath}</div>{/if}

                {#if mt.status === 'delvis'}
                  <div class="chrad">
                    {#each mt.channels as c (c)}
                      <span class="chchip" class:ok={mt.chResults[c] === 'ok'}
                        class:run={retryingId === mt.id && mt.chResults[c] !== 'ok'}>
                        {CHLABEL[c] || c} {retryingId === mt.id && mt.chResults[c] !== 'ok' ? '↻' : (mt.chResults[c] === 'ok' ? '✓' : '✗')}
                      </span>
                    {/each}
                    <button class="retrybtn" disabled={retryingId === mt.id} on:click={() => retryMaterial(mt.id)}>
                      {retryingId === mt.id ? 'Publicerar…'
                        : `Försök igen — ${mt.channels.filter((c) => mt.chResults[c] !== 'ok').map((c) => CHLABEL[c] || c).join(', ')} ›`}
                    </button>
                  </div>
                {:else if retryFlashId === mt.id}
                  <div class="retryflash">✓ Alla kanaler publicerade</div>
                {/if}

                {#if historyOpen[mt.id] && mt.history.length > 1}
                  <div class="histline">
                    {#each mt.history as h, i (h.when + i)}
                      <div class="histrad">
                        <span class="histtid mono">{h.when}</span>
                        <span class="histtag" class:pa={h.status === 'publicerad'} class:delvis={h.status === 'delvis'}>
                          {h.status === 'publicerad' ? 'Publicerad' : 'Delvis'}
                        </span>
                        {#if i === 0 ? (h.note || 'senaste') : h.note}
                          <span class="histnote">{i === 0 ? (h.note || 'senaste') : h.note}</span>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
              <span class="mattid mono">{mt.when}</span>
              <button class="sek" on:click={() => openMaterial(mt.id)}>{mt.openLabel}</button>
              <button class="papperskorg" title="Ta bort" on:click={() => deleteMaterial(mt.id)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/></svg>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 760px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .tabs { display: inline-flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; margin: 14px 0 0; }
  .tabs button { padding: 8px 16px; border: 0; border-radius: 7px; background: transparent; color: var(--t-mut); font-size: 13px; font-weight: 600; }
  .tabs button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }

  .stack { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; }
  .khuvud { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
  .steg { width: 26px; height: 26px; border-radius: 50%; background: var(--acc); color: #fff; display: flex; align-items: center; justify-content: center; flex: none; font-size: 14px; font-weight: 700; }
  .kic { width: 42px; height: 42px; border-radius: 11px; background: var(--acc-soft); color: var(--acc); display: flex; align-items: center; justify-content: center; flex: none; }
  .kic svg { width: 20px; height: 20px; }
  .ktxt { flex: 1; min-width: 0; }
  .kt { font-size: 17px; font-weight: 700; color: var(--t-head); display: block; }
  .ks { display: block; font-size: 12.5px; color: var(--t-mut); margin-top: 2px; }

  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin: 16px 0 10px; }
  .caps.mitt { text-align: center; margin-top: 0; }
  .capsrad { display: flex; align-items: baseline; gap: 8px; margin: 0 0 10px; }
  .capsrad .caps { margin: 0; }
  .note { font-size: 11px; color: var(--t-help); }
  .rutnat3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .seg-b { padding: 8px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-mut); font-size: 12.5px; font-weight: 500; }
  .seg-b.on { background: var(--acc); border-color: var(--acc); color: #fff; font-weight: 600; }
  .tema-b { padding: 9px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-mut); font-size: 12.5px; font-weight: 500; }
  .tema-b.on { color: #fff; font-weight: 600; }

  .frad { display: flex; align-items: center; gap: 8px; }
  .fl { font-size: 12.5px; color: var(--t-mut); width: 78px; flex: none; }
  .fl1 { flex: 1; }
  input, textarea { font-family: inherit; padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); font-size: 12.5px; font-weight: 400; outline: none; flex: 1; min-width: 0; width: 100%; box-sizing: border-box; }
  input:focus, textarea:focus { border-color: var(--acc); }
  textarea { resize: vertical; line-height: 1.5; }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .valj { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 8px 12px; font-size: 12px; color: var(--t-mut); }
  .valj:hover { border-color: var(--acc); color: var(--acc); }

  .hoger { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 14px; }
  .ok { font-size: 12px; color: var(--ok); font-weight: 600; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 18px; font-size: 13px; font-weight: 600; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .sek { background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 8px 13px; font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }
  .sek:disabled { opacity: 0.5; }
  .hint { font-size: 11.5px; color: var(--t-help); }
  .mt { margin-top: 14px; }

  /* Live · steg 2: Dropbox-grid */
  .dbgrid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin-top: 14px; }
  .dbtile { position: relative; aspect-ratio: 9 / 16; border-radius: 7px; overflow: hidden; padding: 0;
    border: 2px solid var(--div); cursor: pointer;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--panel) 8px, var(--panel) 16px); }
  .dbtile.vald { border-color: var(--acc); box-shadow: 0 0 0 3px var(--acc-soft); }
  .dbtile img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .dbnamn { position: absolute; bottom: 2px; left: 3px; right: 3px; font-size: 8.5px; font-family: var(--mono, monospace);
    color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,.8); text-align: left; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .dbtile:not(:has(img)) .dbnamn { color: var(--t-mut); text-shadow: none; }
  .bock { position: absolute; top: 3px; right: 3px; width: 16px; height: 16px; border-radius: 50%; background: var(--acc); color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }

  /* Live · steg 3 */
  .tvakol { display: flex; gap: 18px; align-items: flex-start; }
  .kol1 { flex: 1; min-width: 0; }
  .kol2 { flex: none; }
  .falt { display: flex; flex-direction: column; gap: 10px; }
  .flabel { display: block; font-size: 11px; color: var(--t-mut); margin-bottom: 5px; }
  .ovbox { position: relative; width: 150px; aspect-ratio: 9 / 16; border-radius: 12px; overflow: hidden;
    border: 1px solid var(--div); display: flex; flex-direction: column; justify-content: flex-end;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 10px, var(--panel) 10px, var(--panel) 20px); }
  .ovbox.harbild { background: linear-gradient(160deg, #5a6b7a, #2c3742); }
  .ovbox.ovgrenram { border-width: 2.5px; }
  .ovfoto { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .ovscrim { position: relative; padding: 14px 12px; background: linear-gradient(to top, rgba(0,0,0,.72), rgba(0,0,0,0)); }
  .ovkick { display: inline-block; font-size: 9px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #fff; padding: 2px 7px; border-radius: 4px; margin-bottom: 7px; }
  .ovbig { font-size: 20px; font-weight: 700; color: #fff; line-height: 1.05; overflow-wrap: break-word; }
  .ovsmall { font-size: 10px; color: rgba(255,255,255,.85); margin-top: 4px; line-height: 1.35; white-space: pre-line; }
  .ovtom { flex: 1; display: flex; align-items: center; justify-content: center; padding: 16px; text-align: center; font-size: 11px; color: var(--t-mut); }
  .ovnamn { font-size: 10px; color: var(--t-help); text-align: center; margin-top: 6px; font-family: var(--mono, monospace); }
  .ovladdar { position: absolute; top: 8px; right: 8px; z-index: 3; background: rgba(0,0,0,.6); color: #fff;
    font-size: 9.5px; font-weight: 600; padding: 3px 8px; border-radius: 999px; }
  .ovfel { font-size: 10.5px; color: var(--varn); text-align: center; margin-top: 6px; max-width: 150px; }

  /* SoMe · Målbanor */
  .matchrad { display: flex; align-items: center; gap: 11px; border: 1px solid var(--div3);
    border-radius: 10px; background: var(--panel); padding: 10px 13px; margin-bottom: 16px; }
  .brickor { display: flex; align-items: center; flex: none; }
  .brickor .away { margin-left: -8px; display: flex; border-radius: 50%; box-shadow: 0 0 0 2px var(--kort); }
  .mrinfo { flex: 1; min-width: 0; }
  .mrfix { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .mrsub { font-size: 11px; color: var(--t-mut); }
  .lank { border: 0; background: none; color: var(--acc); font-size: 11.5px; font-weight: 600; padding: 0; }
  .capsrad2 { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0 8px; }
  .capsrad2 .caps { margin: 0; }
  .genlank { border: 0; background: none; color: var(--acc); font-size: 11px; font-weight: 600; }
  .somecap { width: 100%; background: var(--panel); border: 1px solid var(--div); border-radius: 8px;
    padding: 9px 11px; font-size: 12.5px; line-height: 1.55; color: var(--t-head); font-family: inherit; outline: none; resize: vertical; }
  .somecap:focus { border-color: var(--acc); }
  .tokenrad { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
  .tokenlbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--t-help); margin-right: 2px; }
  .tokenchip { border: 1px solid var(--div); background: var(--panel); border-radius: 999px;
    padding: 3px 9px; font-size: 11px; font-family: var(--mono, ui-monospace, monospace);
    color: var(--t-mut); }
  .tokenchip:hover { border-color: var(--acc); color: var(--acc); }
  .somepreview { margin-top: 12px; }
  .previewbox { background: var(--panel); border: 1px dashed var(--div); border-radius: 8px;
    padding: 10px 12px; font-size: 12.5px; line-height: 1.55; color: var(--t-head); white-space: pre-wrap; }
  .valjbild { border: 1px solid var(--div); background: var(--kort); border-radius: 7px; padding: 5px 10px;
    font-size: 11.5px; font-weight: 600; color: var(--t-mut); flex: none; }
  .valjbild:hover { border-color: var(--acc); color: var(--acc); }

  .kanaler { display: flex; flex-direction: column; gap: 10px; }
  .kanal { border: 1px solid var(--div3); border-radius: 11px; background: var(--panel); overflow: hidden; }
  .krad { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px 13px; }
  .ktoggle { display: flex; align-items: center; gap: 10px; border: 0; background: transparent; padding: 0; flex: 1; text-align: left; }
  .knamn { flex: 1; font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--kort); color: var(--acc); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }
  .antal { font-size: 11px; font-weight: 600; color: var(--acc); background: var(--acc-soft); padding: 3px 9px; border-radius: 999px; flex: none; }
  .strip { display: flex; gap: 6px; padding: 0 13px 11px; overflow-x: auto; }
  .thumb { width: 44px; height: 55px; border-radius: 5px; flex: none; position: relative;
    border: 1px solid var(--div); display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .thumb b { font-family: var(--font-c); font-size: 11px; color: var(--t-mut); }
  .thumb em { position: absolute; top: 2px; left: 3px; font-size: 8px; font-style: normal;
    font-family: var(--mono, monospace); background: var(--kort); border-radius: 3px; padding: 0 3px; color: var(--t-mut); }
  .thumb.plus { background: var(--kort); font-size: 11px; color: var(--t-mut); }
  .thumb.dim { opacity: 0.4; }
  .varn { display: flex; align-items: center; gap: 7px; padding: 9px 13px; border-top: 1px solid var(--div3);
    background: color-mix(in srgb, var(--varn) 9%, transparent); font-size: 11.5px; color: var(--varn); }
  .fbdiff { padding: 11px 13px; border-top: 1px solid var(--div3); }
  .fbdifflbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); margin-bottom: 6px; }
  .fbtokens { font-size: 12px; line-height: 1.5; color: var(--t-head); font-family: var(--mono, monospace); white-space: pre-wrap; }
  .fbtokens .bort { color: var(--rose); text-decoration: line-through; opacity: 0.6; }

  .drybanner { margin-top: 14px; border: 1px solid var(--acc-border); border-radius: 10px; background: var(--acc-soft); padding: 11px 13px; font-size: 12px; color: var(--t-head); }
  .planlista { margin-top: 8px; display: flex; flex-direction: column; gap: 2px; }
  .planrad { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--t-head); padding: 3px 0; }
  .pdot { width: 7px; height: 7px; border-radius: 50%; background: var(--acc); flex: none; }
  .pl { flex: 1; } .pn { color: var(--t-mut); font-size: 11px; }
  .progress { margin-top: 14px; display: flex; align-items: center; gap: 11px; border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 13px; }
  .spin { width: 24px; height: 24px; border-radius: 50%; border: 3px solid var(--acc-soft); border-top-color: var(--acc); flex: none; animation: sospin 0.8s linear infinite; }
  @keyframes sospin { to { transform: rotate(360deg); } }
  .pt { font-size: 13.5px; font-weight: 600; color: var(--t-head); } .ps { font-size: 11.5px; color: var(--t-mut); }
  .donebox { margin-top: 14px; border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 13px; }
  .donehuvud { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .okc { color: var(--ok); font-weight: 700; }
  .felc { color: var(--varn); font-weight: 700; }
  .rst { margin-left: auto; }
  .donerad { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--t-head); padding: 3px 0; }
  .dl { flex: 1; } .dfel { color: var(--varn); }
  .oppna { color: var(--acc); text-decoration: none; font-weight: 600; }
  .felbox { margin-top: 14px; border: 1px solid var(--div3); border-radius: 10px; padding: 11px 13px; font-size: 12.5px; color: var(--varn); background: color-mix(in srgb, var(--varn) 8%, transparent); }
  .korrad { display: flex; align-items: center; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--div3); }
  .summa { margin-left: auto; font-size: 11.5px; color: var(--t-help); }

  /* §8: Schemalagd publicering (UI-skiss) */
  .schedsek { margin-top: 28px; }
  .schedlista { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
  .schedkort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
  .schedfix { font-size: 13px; font-weight: 600; color: var(--t-head); display: flex; align-items: baseline; gap: 8px; }
  .scheddatum { font-size: 11px; font-weight: 500; color: var(--t-mut); }
  .schedrad { display: flex; align-items: center; gap: 10px; border: 0; background: none; padding: 6px 0; text-align: left; }
  .schedtxt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .schedlbl { font-size: 12.5px; font-weight: 500; color: var(--t-head); }
  .schedvillkor { font-size: 10.5px; color: var(--t-help); }
  .schedstatus { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--varn); background: color-mix(in srgb, var(--varn) 14%, transparent);
    padding: 2px 8px; border-radius: 999px; flex: none; }

  /* Sparade material */
  .matsek { margin-top: 28px; }
  .mathuvud { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .matrubrik { display: flex; align-items: baseline; gap: 10px; }
  .matrubrik .caps { margin: 0; }
  .matbanner { display: flex; align-items: center; gap: 9px; background: var(--acc-soft); border-radius: 999px; padding: 4px 6px 4px 13px; font-size: 11.5px; font-weight: 600; color: var(--acc); }
  .nyknapp { background: var(--kort); border: 1px solid var(--div); border-radius: 999px; padding: 4px 11px; font-size: 11.5px; font-weight: 600; color: var(--t-body); }
  .matchips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
  .matchips .seg-b { border-radius: 999px; padding: 5px 12px; }
  .mattom { border: 1px dashed var(--div); border-radius: 11px; padding: 22px; text-align: center; font-size: 12.5px; color: var(--t-mut); background: var(--panel); }
  .matlista { display: flex; flex-direction: column; gap: 9px; }
  .matrad { display: flex; align-items: flex-start; gap: 13px; background: var(--kort); border: 1px solid var(--div); border-radius: 12px; box-shadow: var(--skugga); padding: 12px 14px; }
  .maticon { width: 34px; height: 34px; border-radius: 9px; flex: none; display: flex; align-items: center; justify-content: center; background: rgba(47,124,176,.14); color: #2F7CB0; }
  .maticon.live { background: var(--acc-soft); color: var(--acc); }
  .mattxt { flex: 1; min-width: 0; }
  .matrad1 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .matnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .matstatus { font-size: 9.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; flex: none; color: var(--varn); background: color-mix(in srgb, var(--varn) 13%, transparent); }
  .matstatus.pa { color: var(--ok); background: color-mix(in srgb, var(--ok) 13%, transparent); }
  .matstatus.delvis { color: #B0483A; background: rgba(176,72,58,.12); }
  .histchip { border: 0; background: var(--acc-soft); color: var(--acc); font-size: 10.5px; font-weight: 700;
    padding: 3px 9px; border-radius: 999px; flex: none; }
  .matsub { font-size: 11.5px; color: var(--t-mut); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mattid { font-size: 10.5px; color: var(--t-help); flex: none; margin-top: 2px; }
  .papperskorg { flex: none; width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center; border: 0; background: transparent; color: var(--t-mut); }
  .papperskorg svg { width: 15px; height: 15px; }
  .papperskorg:hover { color: #C0453E; }

  /* Delvis publicerad: kanalchips + försök-igen */
  .chrad { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-top: 8px; }
  .chchip { font-size: 10.5px; font-weight: 600; padding: 3px 9px; border-radius: 999px;
    color: var(--rose); background: color-mix(in srgb, var(--rose) 12%, transparent); }
  .chchip.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
  .chchip.run { color: var(--varn); background: color-mix(in srgb, var(--varn) 13%, transparent); }
  .retrybtn { border: 1px solid #B0483A; background: transparent; color: #B0483A; border-radius: 999px;
    padding: 4px 12px; font-size: 11px; font-weight: 600; }
  .retrybtn:hover:not(:disabled) { background: rgba(176,72,58,.1); }
  .retrybtn:disabled { opacity: 0.6; }
  .retryflash { margin-top: 8px; font-size: 11.5px; font-weight: 600; color: var(--ok); }

  /* Testläge — amber (samma ton som befintlig "Utkast"/varnings-amber, var(--varn)) */
  .testhint { color: var(--varn); font-weight: 600; }
  .testpath { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--varn);
    max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .testrow { display: flex; align-items: center; gap: 8px; margin-top: 8px; padding-top: 8px;
    border-top: 1px solid var(--div3); font-size: 11.5px; color: var(--varn); }
  .testbadge { font-size: 9.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
    padding: 2px 8px; border-radius: 6px; flex: none; color: var(--varn);
    border: 1px solid color-mix(in srgb, var(--varn) 55%, transparent); }
  .testpathrow { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--varn);
    margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* Historik-tidslinje */
  .histline { margin-top: 9px; padding-left: 10px; border-left: 2px solid var(--div3);
    display: flex; flex-direction: column; gap: 6px; }
  .histrad { display: flex; align-items: center; gap: 9px; font-size: 11px; }
  .histtid { color: var(--t-help); flex: none; }
  .histtag { font-size: 9px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
    padding: 2px 6px; border-radius: 5px; flex: none; color: var(--ok); background: color-mix(in srgb, var(--ok) 13%, transparent); }
  .histtag.delvis { color: #B0483A; background: rgba(176,72,58,.12); }
  .histnote { color: var(--t-mut); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
