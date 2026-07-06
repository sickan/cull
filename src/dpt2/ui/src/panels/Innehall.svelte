<script>
  import { onMount } from 'svelte'
  import { forhandsgranskaInnehall, exporteraInnehall, publiceraInnehallNatet, statusInnehall, listaMatcher, hamtaMatch, genereraBildsvep, forhandsgranskaBildsvepFraga, valjMapp, valjFil, thumbForBild, urvalHojdpunkter, slugga, sportprofiler, hamtaUtkast, sparaUtkast, aktivMatch, listaLag } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import BildvaljareFokuspunkt from '../lib/BildvaljareFokuspunkt.svelte'
  import ResultatRemsa from '../lib/ResultatRemsa.svelte'
  import AktivMatchRad from '../lib/AktivMatchRad.svelte'
  import PaGang from './PaGang.svelte'
  import { testMode } from '../lib/testlage.js'

  // Fyra färgkodade typer (DATAMODELL.md). Porträtt är en Event-kategori,
  // inte en egen typ. match = "Sport" utåt; sajtens collection heter matcher.
  const CTYPER = [
    { id: 'blogg', namn: 'Blog', farg: '#7A8794', sub: 'journal & resor', mapp: 'blogg' },
    { id: 'match', namn: 'Sport', farg: '#2F7CB0', sub: 'från match', mapp: 'matcher' },
    { id: 'landskap', namn: 'Landskap', farg: '#C9871F', sub: 'bildserier', mapp: 'landskap' },
    { id: 'event', namn: 'Event', farg: '#C9657F', sub: 'porträtt, bröllop…', mapp: 'event' },
    { id: 'pagang', namn: 'På gång', farg: '#A0653B', sub: 'kommande på webben', mapp: 'pagang' },
  ]
  const STATUSAR = ['kommande', 'pagaende', 'avslutad']
  const STATUS_ETI = { kommande: 'Kommande', pagaende: 'Pågående', avslutad: 'Avslutad' }
  const EVENT_KAT = ['Porträtt', 'Bröllop', 'Student', 'Företag', 'Mode', 'Övrigt']

  let ctyp = 'match'
  let matcher = []
  let pick = ''
  let auto = true
  let cms = { status: 'kommande', hem: '', borta: '', sport: '', resultat: '', mellan: '',
    datum: '', serie: '', arena: '', galleri: '', malskyttar: '', svep: '', figurer: [],
    hero: '', heroPosition: 'center center', heroKalla: '' }
  let profiler = {}
  $: profil = profiler[cms.sport] || profiler.fotboll || { mid_label: 'Halvtid', has_scorers: true }
  // §4: matchfältens frivilliga koppling. matchFull = fullständig matchdata
  // (mellan/malskyttar/galleri finns inte i den lätta matcher-listan).
  // cmsOwn[fält] = true när användaren skrivit över — bruten koppling för
  // just det fältet, tills "↺ Hämta från match" trycks.
  let matchFull = null
  let cmsOwn = {}
  const CMS_MATCHFALT = { hem: 'lag_hemma', borta: 'lag_borta', resultat: 'resultat',
    mellan: 'mellan', malskyttar: 'malskyttar', datum: 'datum', serie: 'liga',
    arena: 'arena', galleri: 'galleri' }
  let cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '',
    galleri: '', ingress: '', figurer: [] }
  let cmsLandskap = { titel: '', plats: '', period: '', ingress: '', figurer: [] }
  let cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '',
    platser: [], figurer: [] }
  let md = ''
  let exportDirs = { match: '', event: '', landskap: '', blogg: '' }
  let sparad = false
  let sparadPath = ''
  let synkar = false
  let synkFel = ''
  let synkad = false
  let synkadPath = ''
  let publiceradId = ''
  let statusInfo = null
  let statusLaddar = false
  let genKor = false
  let genFel = ''
  let genGranska = null      // frågetext när förhandsgranskningen är öppen, annars null
  let genLaddarFraga = false
  let genSekunder = 0
  let genTimer = null
  let hlKalla = ''       // källetikett för hämtade höjdpunkter (urval/match)
  let hlFlash = false

  $: akt = ctyp === 'match' ? cms
    : ctyp === 'event' ? cmsEvent
    : ctyp === 'landskap' ? cmsLandskap : cmsBlogg
  $: typinfo = CTYPER.find((t) => t.id === ctyp)
  // Landskap & Event = bild-only-galleri (härledd /bilder/{slug}/{n}.jpg-ref,
  // ingen alt/bildtext) — speglar _innehall_md. Bildkatalogen = titelns slug
  // utan bloggens datum-prefix.
  $: galText = ctyp !== 'landskap' && ctyp !== 'event'
  $: aktSlug = slugga(ctyp === 'match' ? `${cms.hem} – ${cms.borta}` : akt.titel)
  $: hlAntal = ctyp === 'match' ? cms.figurer.filter((f) => f.src).length : 0
  $: hlVisaKalla = ctyp === 'match' && !!hlKalla && hlAntal > 0

  let lagAlla = []

  onMount(async () => {
    let akt = null
    // Bryggan kan (kända, ospårade race i store.lista_lag/hamta_match delad
    // self.conn) tappa ett enstaka anrop — try/catch så panelen faller
    // tillbaka på tomma listor i stället för att fastna, samma mönster som
    // Publicera.svelte:s onMount.
    try {
      ;[matcher, profiler, akt, lagAlla] = await Promise.all(
        [listaMatcher(), sportprofiler(), aktivMatch(), listaLag()])
    } catch (e) {
      console.error('Innehåll: kunde inte läsa matcher/lag/aktiv match', e)
    }
    // §5: förvalt = aktiv match (samma som Live &amp; SoMe) — annars första i listan.
    const forval = (akt && matcher.some((m) => m.id === akt.id)) ? akt.id : (matcher[0] && matcher[0].id)
    if (forval) { pick = forval; await fyllFranMatch(forval) }
    await forhandsgranska()
  })

  function harledStatus(datum, tid, resultat) {
    if (resultat) return 'avslutad'
    if (!datum) return 'kommande'
    const d = datum.split('-').map(Number)
    if (d.length !== 3) return 'kommande'
    const t = (tid || '00:00').split(':').map(Number)
    const start = new Date(d[0], d[1] - 1, d[2], t[0] || 0, t[1] || 0)
    return new Date() >= start ? 'pagaende' : 'kommande'
  }

  // ── Autospar per match (dpt2.drafts) — arbetsytans minne för Sport-
  // formuläret, skilt från explicit "Spara"/"Publicera" (se DATAMODELL-
  // UTKAST-RESULTAT.md §2). cmsUtkastLaddar spärrar autospar under
  // fyllFranMatch så den inbyggda länkningen (matchFull → cms) inte tolkas
  // som en användarredigering och sparas tillbaka i onödan.
  let cmsUtkastLaddar = true
  let cmsDraftTimer = null

  async function fyllFranMatch(matchId) {
    matchFull = await hamtaMatch(matchId)
    if (!matchFull) return
    cmsUtkastLaddar = true
    cms.hem = matchFull.lag_hemma || ''; cms.borta = matchFull.lag_borta || ''
    cms.sport = matchFull.sport || ''
    cms.resultat = matchFull.resultat || ''; cms.mellan = matchFull.mellan || ''
    cms.malskyttar = matchFull.malskyttar || ''
    cms.datum = matchFull.datum || ''; cms.arena = matchFull.arena || ''
    cms.serie = matchFull.liga || ''; cms.galleri = matchFull.galleri || ''
    if (auto) cms.status = harledStatus(matchFull.datum, matchFull.tid, matchFull.resultat)
    cmsOwn = {}
    const d = await hamtaUtkast(matchId)
    if (d) {
      cmsOwn = d.cms_own || {}
      if (d.cms) {
        // Länkade fält (CMS_MATCHFALT): återställ BARA om användaren skrivit
        // över just det fältet (cmsOwn[falt]) — annars ska det alltid spegla
        // matchens FÄRSKA värde (redan satt ovan från matchFull), inte en
        // gammal utkast-ögonblicksbild. Utan detta villkor skrev en tidigare
        // sparad draft tillbaka ett förlegat resultat även efter att
        // resultat-remsan skrivit ett nytt (bekräftat live: "2-1" stod kvar
        // i CMS-fältet trots att matchen redan visade "6-0").
        for (const falt of Object.keys(CMS_MATCHFALT)) {
          if (cmsOwn[falt] && falt in d.cms) cms[falt] = d.cms[falt]
        }
        // Fält utan matchmotsvarighet (svep/galleribilder/hero) saknar en
        // "färsk" källa att falla tillbaka på — återställ alltid.
        for (const falt of ['svep', 'figurer', 'hero', 'heroPosition', 'heroKalla']) {
          if (falt in d.cms) cms[falt] = d.cms[falt]
        }
        if (!auto && 'status' in d.cms) cms.status = d.cms.status
      }
    }
    cms = cms
    figThumbs = {}                       // rensa förra matchens miniatyrer
    aterupplosaFigThumbs(cms.figurer)    // återskapa ur figurernas sökvägar
    setTimeout(() => (cmsUtkastLaddar = false), 0)
  }

  function scheduleCmsUtkast() {
    if (cmsUtkastLaddar || ctyp !== 'match' || !pick) return
    if (cmsDraftTimer) clearTimeout(cmsDraftTimer)
    cmsDraftTimer = setTimeout(() => { sparaUtkast(pick, { cms, cms_own: cmsOwn }) }, 500)
  }
  $: if (ctyp === 'match' && pick) { cms; cmsOwn; scheduleCmsUtkast() }
  async function cmsFetchAll() {
    if (pick) await fyllFranMatch(pick)
    forhandsgranska()
  }
  // Fältet skrivs över av användaren — kopplingen till matchen bryts för
  // just det fältet (visas som "eget" tills "↺ Hämta från match" trycks).
  function cmsSetOwn(falt, varde) {
    cms[falt] = varde
    cmsOwn = { ...cmsOwn, [falt]: true }
    cms = cms
    forhandsgranska()
  }
  function cmsFetchField(falt) {
    if (!matchFull) return
    cms[falt] = matchFull[CMS_MATCHFALT[falt]] || ''
    cmsOwn = { ...cmsOwn, [falt]: false }
    cms = cms
    forhandsgranska()
  }
  $: if (auto) cms.status = harledStatus(cms.datum, '', cms.resultat)

  function bytTyp(id) {
    ctyp = id
    forhandsgranska()
  }

  function data() {
    if (ctyp === 'match') return { typ: 'match', titel: `${cms.hem} – ${cms.borta}`,
      hem: cms.hem, borta: cms.borta, serie: cms.serie, sport: cms.sport,
      status: cms.status, datum: cms.datum, resultat: cms.resultat, mellan: cms.mellan,
      arena: cms.arena, malskyttar: cms.malskyttar,
      pixieset: cms.galleri, body: cms.svep, figurer: cms.figurer,
      hero: cms.hero, heroPosition: cms.heroPosition, heroKalla: cms.heroKalla }
    if (ctyp === 'event') return { typ: 'event', ...cmsEvent }
    if (ctyp === 'landskap') return { typ: 'landskap', ...cmsLandskap }
    return { typ: 'blogg', ...cmsBlogg }
  }

  async function forhandsgranska() {
    const r = await forhandsgranskaInnehall(data())
    md = r?.md || ''
  }

  function pinga() { cms = cms; cmsEvent = cmsEvent; cmsLandskap = cmsLandskap; cmsBlogg = cmsBlogg }
  function laggBild() { akt.figurer = [...akt.figurer, { bild: '', alt: '', bildtext: '', src: '' }]; pinga(); forhandsgranska() }
  function taBild(i) {
    akt.figurer = akt.figurer.filter((_, j) => j !== i)
    const novo = {}
    Object.keys(figThumbs).map(Number).filter((k) => k !== i)
      .forEach((k) => { novo[k > i ? k - 1 : k] = figThumbs[k] })
    figThumbs = novo
    pinga(); forhandsgranska()
  }
  // Miniatyr-cache (index → data-URI) — transient, skickas ALDRIG till
  // backend (bara den lokala källsökvägen i figurer[i].bild gör det).
  let figThumbs = {}
  async function valjFigurBild(i) {
    const r = await valjFil('Välj bild', ['Bilder (*.jpg;*.jpeg;*.png;*.nef;*.dng;*.cr2;*.cr3;*.arw)'])
    if (!r?.ok || !r.path) return
    const t = await thumbForBild(r.path)
    if (!t?.ok) return
    akt.figurer[i] = { ...akt.figurer[i], bild: r.path }
    figThumbs = { ...figThumbs, [i]: t.data_uri }
    pinga(); forhandsgranska()
  }
  function laggPlats() { cmsBlogg.platser = [...cmsBlogg.platser, { plats: '', tips: '' }] }
  function taPlats(i) { cmsBlogg.platser = cmsBlogg.platser.filter((_, j) => j !== i); forhandsgranska() }

  // Sport: fyll höjdpunktsgalleriet från det aktiva Publicera-urvalet (topp-
  // rankade filer). Utan urval → fallback på aktiva matchen som källetikett.
  async function hamtaHojdpunkter() {
    const r = await urvalHojdpunkter(6)
    const filer = (r?.ok && r.filer) || []
    const sokvagar = (r?.ok && r.sokvagar) || []
    const antal = Math.min(filer.length || (r?.ok && r.urval?.bilder) || 6, 6)
    hlKalla = (r?.ok && r.namn) || `${cms.hem} – ${cms.borta}`.replace(/\s+/g, ' ').trim()
    const matchinfo = `${cms.hem} ${cms.resultat} ${cms.borta}`.replace(/\s+/g, ' ').trim()
    // bild = upplöst full sökväg (för miniatyr + export-kopiering), src = stam
    // (proveniens/räkning). Tidigare lagrades bara stammen → tomma rutor + ingen
    // export-kopiering.
    cms.figurer = Array.from({ length: antal }, (_, i) => ({
      bild: sokvagar[i] || '', alt: `${matchinfo} — höjdpunkt ${i + 1}`, bildtext: '', src: filer[i] || '' }))
    figThumbs = {}
    hlFlash = true
    setTimeout(() => (hlFlash = false), 2200)
    forhandsgranska()
    aterupplosaFigThumbs(cms.figurer)
  }

  // Återskapa miniatyr-cachen ur figurernas lokala källsökväg (figurer[i].bild).
  // Körs efter höjdpunkts-hämtning OCH när ett sparat utkast öppnas — annars är
  // rutorna tomma (figThumbs är transient, sparas aldrig). Parallellt; hoppar
  // figurer utan sökväg eller som redan har en miniatyr.
  async function aterupplosaFigThumbs(figs) {
    const arr = figs || (akt && akt.figurer) || []
    const jobb = []
    arr.forEach((f, i) => {
      if (f && f.bild && !figThumbs[i]) {
        jobb.push(thumbForBild(f.bild).then((t) => (t?.ok ? { i, u: t.data_uri } : null)))
      }
    })
    if (!jobb.length) return
    const res = await Promise.all(jobb)
    const novo = { ...figThumbs }
    for (const x of res) if (x) novo[x.i] = x.u
    figThumbs = novo
  }

  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }
  // §10: matchfakta appen REDAN har (cms speglar länkade/egna fält) — vävs
  // in i Claude-frågan så websökning inte behöver leta upp sånt som redan
  // är känt. cms.sport (inte hårdkodat 'fotboll') styr sport-emoji/format.
  const _svepInfo = () => `${cms.hem}–${cms.borta}${cms.resultat ? ' ' + cms.resultat : ''}`
  function _svepFakta() {
    return { sport: cms.sport || '', hemma_farg: fargForLag(cms.hem) || '',
      resultat: cms.resultat || '', mellan: cms.mellan || '', malskyttar: cms.malskyttar || '',
      arena: cms.arena || '', datum: cms.datum || '', liga: cms.serie || '' }
  }
  async function genOppnaGranska() {
    genFel = ''
    genLaddarFraga = true
    const r = await forhandsgranskaBildsvepFraga(_svepInfo(), _svepFakta())
    genLaddarFraga = false
    if (r?.ok) genGranska = r.fraga
    else genFel = r?.fel || 'Kunde inte bygga frågan.'
  }
  const genAvbryt = () => (genGranska = null)
  async function genSkicka() {
    const info = _svepInfo()
    const fakta = _svepFakta()
    genGranska = null
    genKor = true
    genFel = ''
    genSekunder = 0
    genTimer = setInterval(() => (genSekunder += 1), 1000)
    try {
      const r = await genereraBildsvep(info, fakta.sport, fakta.hemma_farg, fakta)
      if (r?.ok) { cms.svep = r.bildsvep; forhandsgranska() }
      else genFel = r?.fel || 'Kunde inte generera bildtexten.'
    } catch (e) {
      genFel = 'Kunde inte generera bildtexten.'
    } finally {
      genKor = false
      clearInterval(genTimer); genTimer = null
    }
  }

  // §5: "↺ Hämta från SoMe" — samma token-upplösning som SoMe-bildtexten i
  // Publicera.svelte (_resolveTokens/handle/_hashtagify, dupliceras hellre
  // än att brytas ut för en tio-radig hjälpfunktion).
  let svepHamtadFlash = false
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
  async function hamtaSvepFranSome() {
    if (!matchFull) return
    const d = await hamtaUtkast(matchFull.id)
    if (!d?.some_caption) return
    cms.svep = _resolveTokens(d.some_caption, matchFull, profil, lagAlla)
    cms = cms
    forhandsgranska()
    svepHamtadFlash = true
    setTimeout(() => (svepHamtadFlash = false), 2200)
  }
  async function spara() {
    // Testläge: skriver till test-output/content/ i stället — kräver ingen
    // export-katalog, så prompten för att välja en hoppas helt över.
    if (!$testMode && !exportDirs[ctyp]) {
      const r = await valjMapp(`Välj content/${typinfo.mapp}-katalog`)
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
    if (synkad) { publiceradId = r.id; setTimeout(() => (synkad = false), 2600) }
    else synkFel = r?.fel || 'Kunde inte publicera — kontrollera anslutningen.'
  }

  async function kollaStatus() {
    if (!publiceradId) return
    statusLaddar = true
    statusInfo = await statusInnehall(ctyp, publiceradId)
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

<div class="panel">
  <header>
    <h1 class="scd">Innehåll</h1>
    <span class="sub">Skapa innehåll till hemsidan — frontmatter och bilder blir en färdig .md-fil</span>
  </header>

  <div class="typkort">
    {#each CTYPER as ct}
      <button class="tkort" class:on={ctyp === ct.id}
        style="--tf:{ct.farg}" on:click={() => bytTyp(ct.id)}>
        <span class="tik">
          {#if ct.id === 'blogg'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
          {:else if ct.id === 'match'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/></svg>
          {:else if ct.id === 'landskap'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 17l5-8 4 6 3-4 6 6"/><circle cx="17.5" cy="7.5" r="1.8"/></svg>
          {:else if ct.id === 'pagang'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="4.5" width="17" height="16" rx="2.4"/><path d="M3.5 9h17M8 3v3M16 3v3"/><path d="M8 13.5l2.5 2.5L16 11"/></svg>
          {:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>{/if}
        </span>
        <span class="tnamn scd">{ct.namn}</span>
        <span class="tsub">{ct.sub}</span>
      </button>
    {/each}
  </div>

  {#if ctyp === 'pagang'}
    <PaGang on:navigera />
  {:else}
  {#if ctyp === 'match'}
    <AktivMatchRad on:navigera />
    {#if pick && matchFull}<ResultatRemsa match={matchFull} {profil} {lagAlla} />{/if}
    <div class="kort">
      <div class="caps">Publicera till hemsidan</div>
      {#if pick}
        <div class="lankinfo">
          <span>Fälten följer <b>{cms.hem} – {cms.borta}</b> tills du skriver över dem</span>
          <button class="lank" on:click={cmsFetchAll}>↺ Hämta allt</button>
        </div>
      {/if}
      <div class="grid2">
        <div class="f">
          <div class="statushuvud"><label>Status på hemsidan</label><button class="autochip" class:on={auto} on:click={() => (auto = !auto)}>Auto</button></div>
          <div class="seg">
            {#each STATUSAR as s}<button class:on={cms.status === s} on:click={() => { if (!auto) cms.status = s }} disabled={auto}>{STATUS_ETI[s]}</button>{/each}
          </div>
          <div class="hint">Härleds från datum & tid · Avslutad sätts när du skapar Resultat-story</div>
        </div>
      </div>

      <div class="grid2 mt">
        <div class="f"><label>Hemmalag {#if pick}<span class="linktag" class:own={cmsOwn.hem}>{cmsOwn.hem ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.hem} on:input={(e) => cmsSetOwn('hem', e.target.value)} />
          {#if pick && cmsOwn.hem}<button class="lank sm" on:click={() => cmsFetchField('hem')}>↺ Hämta från match</button>{/if}</div>
        <div class="f"><label>Bortalag {#if pick}<span class="linktag" class:own={cmsOwn.borta}>{cmsOwn.borta ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.borta} on:input={(e) => cmsSetOwn('borta', e.target.value)} />
          {#if pick && cmsOwn.borta}<button class="lank sm" on:click={() => cmsFetchField('borta')}>↺ Hämta från match</button>{/if}</div>
        <div class="f"><label>Resultat {#if pick}<span class="linktag" class:own={cmsOwn.resultat}>{cmsOwn.resultat ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.resultat} on:input={(e) => cmsSetOwn('resultat', e.target.value)} />
          {#if pick && cmsOwn.resultat}<button class="lank sm" on:click={() => cmsFetchField('resultat')}>↺ Hämta från match</button>{/if}</div>
        <div class="f"><label>{profil.mid_label} {#if pick}<span class="linktag" class:own={cmsOwn.mellan}>{cmsOwn.mellan ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.mellan} on:input={(e) => cmsSetOwn('mellan', e.target.value)} />
          {#if pick && cmsOwn.mellan}<button class="lank sm" on:click={() => cmsFetchField('mellan')}>↺ Hämta från match</button>{/if}</div>
        <div class="f"><label>Datum {#if pick}<span class="linktag" class:own={cmsOwn.datum}>{cmsOwn.datum ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.datum} on:input={(e) => cmsSetOwn('datum', e.target.value)} />
          {#if pick && cmsOwn.datum}<button class="lank sm" on:click={() => cmsFetchField('datum')}>↺ Hämta från match</button>{/if}</div>
        <div class="f"><label>Serie {#if pick}<span class="linktag" class:own={cmsOwn.serie}>{cmsOwn.serie ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.serie} on:input={(e) => cmsSetOwn('serie', e.target.value)} />
          {#if pick && cmsOwn.serie}<button class="lank sm" on:click={() => cmsFetchField('serie')}>↺ Hämta från match</button>{/if}</div>
      </div>
      <div class="f mt"><label>Arena {#if pick}<span class="linktag" class:own={cmsOwn.arena}>{cmsOwn.arena ? 'eget' : '↺ länkad'}</span>{/if}</label>
        <input value={cms.arena} on:input={(e) => cmsSetOwn('arena', e.target.value)} />
        {#if pick && cmsOwn.arena}<button class="lank sm" on:click={() => cmsFetchField('arena')}>↺ Hämta från match</button>{/if}</div>
      <div class="f mt"><label>Galleri-URL (Pixieset) {#if pick}<span class="linktag" class:own={cmsOwn.galleri}>{cmsOwn.galleri ? 'eget' : '↺ länkad'}</span>{/if}</label>
        <input class="mono" value={cms.galleri} on:input={(e) => cmsSetOwn('galleri', e.target.value)} />
        {#if pick && cmsOwn.galleri}<button class="lank sm" on:click={() => cmsFetchField('galleri')}>↺ Hämta från match</button>{/if}</div>
      {#if profil.has_scorers}
        <div class="f mt"><label>{profil.scorers_label || 'Målskyttar'} {#if pick}<span class="linktag" class:own={cmsOwn.malskyttar}>{cmsOwn.malskyttar ? 'eget' : '↺ länkad'}</span>{/if}</label>
          <input value={cms.malskyttar} on:input={(e) => cmsSetOwn('malskyttar', e.target.value)} />
          {#if pick && cmsOwn.malskyttar}<button class="lank sm" on:click={() => cmsFetchField('malskyttar')}>↺ Hämta från match</button>{/if}</div>
      {/if}
      <div class="f mt">
        <label>Hero-bild &amp; fokuspunkt</label>
        <BildvaljareFokuspunkt bind:hero={cms.hero} bind:heroPosition={cms.heroPosition} bind:heroKalla={cms.heroKalla} on:change={forhandsgranska} />
      </div>
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
        <div class="f"><label>Galleri-URL (Pixieset)</label><input class="mono" bind:value={cmsEvent.galleri} on:change={forhandsgranska} /></div>
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
  {:else}
    <div class="kort">
      <div class="caps">Journal / reseberättelse</div>
      <div class="grid2">
        <div class="f"><label>Titel</label><input bind:value={cmsBlogg.titel} on:change={forhandsgranska} /></div>
        <div class="f"><label>Kategori</label><input bind:value={cmsBlogg.kategori} on:change={forhandsgranska} placeholder="t.ex. Resor" /></div>
        <div class="f"><label>Datum</label><input type="date" bind:value={cmsBlogg.datum} on:change={forhandsgranska} /></div>
      </div>
      <div class="f mt"><label>Ingress</label><textarea rows="2" bind:value={cmsBlogg.ingress} on:change={forhandsgranska}></textarea></div>
      <div class="f mt"><label>Brödtext (markdown)</label><textarea rows="6" bind:value={cmsBlogg.body} on:change={forhandsgranska}></textarea></div>
    </div>

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
    <div class="galhuvud">
      <span class="caps nomarg">{ctyp === 'match' ? 'Bilder · höjdpunkter' : 'Galleri'}</span>
      {#if ctyp === 'match'}
        <div class="galknappar">
          {#if hlFlash}<span class="hlok">✓ {hlAntal} hämtade</span>{/if}
          <button class="hamta" on:click={hamtaHojdpunkter}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5v5h5M20 19v-5h-5"/><path d="M18.5 9A7 7 0 0 0 6 6.5L4 9M5.5 15A7 7 0 0 0 18 17.5l2-2.5"/></svg>
            Hämta från Publicera-urvalet
          </button>
        </div>
      {/if}
    </div>
    {#if hlVisaKalla}
      <div class="hlkalla"><span class="hlprick"></span>{hlAntal} höjdpunkt{hlAntal === 1 ? '' : 'er'} hämtade från {hlKalla}</div>
    {/if}
    <div class="figurer">
      {#each akt.figurer as b, i}
        <div class="figrad">
          <button type="button" class="figbild" class:has={!!figThumbs[i]}
            style={figThumbs[i] ? `background-image:url(${figThumbs[i]})` : ''}
            on:click={() => valjFigurBild(i)} title="Välj bild">
            {#if !figThumbs[i]}<span>+ bild {i + 1}</span>{/if}
          </button>
          <div class="figin">
            {#if galText}
              {#if b.src}<div class="figsrc">från urval · {b.src}</div>{/if}
              <input bind:value={b.alt} on:change={forhandsgranska} placeholder="Alt-text (tillgänglighet)" />
              <input bind:value={b.bildtext} on:change={forhandsgranska} placeholder="Bildtext" />
            {:else}
              <div class="figref">/bilder/{aktSlug}/{i + 1}.jpg</div>
              <div class="fighint">Bild {i + 1} · endast bild, ingen bildtext</div>
            {/if}
          </div>
          <button class="figx" class:armerad={$armerad === `fig-${i}`}
            title={$armerad === `fig-${i}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
            on:click={taBortKlick(`fig-${i}`, () => taBild(i))}>{$armerad === `fig-${i}` ? 'Ta bort?' : '×'}</button>
        </div>
      {/each}
      <button class="figadd" on:click={laggBild}>+ Lägg till bild</button>
    </div>
  </div>

  {#if ctyp === 'match'}
    <div class="kort svepkort">
      <span class="svepik"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 20l1-4 11-11 3 3-11 11z"/><path d="M14 6l3 3"/></svg></span>
      <div class="sveptxt"><div class="svt">Instagram Bildsvepet</div><div class="svs">Genereras från matchinfo</div></div>
      {#if svepHamtadFlash}<span class="ok">✓ Hämtad från SoMe</span>{/if}
      <button class="lank" on:click={hamtaSvepFranSome}>↺ Hämta från SoMe</button>
      <button class="prim" on:click={genOppnaGranska} disabled={genKor || genLaddarFraga}>{genLaddarFraga ? 'Bygger fråga…' : (genKor ? 'Genererar…' : 'Generera')}</button>
    </div>
    {#if genFel}<div class="kort felbox">⚠ {genFel}</div>{/if}
    {#if genGranska}
      <div class="kort genGranska">
        <div class="genGranskaTitel">Granska frågan innan den skickas till Claude</div>
        <div class="genGranskaHint">Tar cirka 2 minuter — websökning används bara för det som inte redan står här (nästa match, tabellkontext, @-handles).</div>
        <pre class="genGranskaFraga">{genGranska}</pre>
        <div class="genGranskaKnappar">
          <button class="lank" on:click={genAvbryt}>Avbryt</button>
          <button class="prim" on:click={genSkicka}>Skicka till Claude ›</button>
        </div>
      </div>
    {:else if genKor}
      <div class="kort genProgress"><span class="genspin"></span>Genererar… {genSekunder}s (websöker matchfakta, tar ofta ~2 min)</div>
    {/if}
    <div class="kort nogap">
      <textarea bind:value={cms.svep} on:change={forhandsgranska} rows="4" placeholder="Klicka Generera så skriver bildsvep.py en bildtext från matchinfo — redigerbar."></textarea>
    </div>
  {/if}

  <div class="kort">
    <div class="mdhuvud"><span class="caps">Markdown · förhandsvisning</span></div>
    <pre>{md}</pre>
    <div class="mdfot">
      <button class="prim" on:click={spara}>Spara .md-fil</button>
      {#if sparad}
        {#if $testMode}<span class="ok testhint">✓ Test — exempelfil: <span class="testpath">{sparadPath}</span> · rensas vid omstart</span>
        {:else}<span class="ok">✓ Sparad till content/{typinfo.mapp}/</span>{/if}
      {/if}
      <button class="prim" on:click={publicera} disabled={synkar}>{synkar ? 'Publicerar…' : 'Publicera till hemsidan'}</button>
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
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }

  /* Fyra färgkodade typkort (Blog · Sport · Landskap · Event) */
  .typkort { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 16px; }
  .tkort { display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
    padding: 12px 14px; border: 1px solid var(--div); border-radius: 12px;
    background: var(--kort); box-shadow: var(--skugga); text-align: left; }
  .tkort .tik { width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center;
    justify-content: center; color: var(--tf); background: color-mix(in srgb, var(--tf) 14%, transparent); }
  .tkort .tik svg { width: 17px; height: 17px; }
  .tkort .tnamn { font-size: 14.5px; font-weight: 700; color: var(--t-head); }
  .tkort .tsub { font-size: 10.5px; color: var(--t-mut); }
  .tkort.on { background: var(--tf); border-color: var(--tf); }
  .tkort.on .tik { background: rgba(255,255,255,.18); color: #fff; }
  .tkort.on .tnamn, .tkort.on .tsub { color: #fff; }
  .tkort:hover:not(.on) { border-color: var(--tf); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; margin-top: 14px; }
  .kort.nogap { margin-top: -8px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-bottom: 12px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .mt { margin-top: 12px; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  label { font-size: 11px; color: var(--t-mut); }
  input, select, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 10px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, select:focus, textarea:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12.5px; }
  textarea { line-height: 1.55; resize: vertical; }

  .statushuvud { display: flex; align-items: center; justify-content: space-between; }
  .autochip { border: 1px solid var(--div); background: var(--panel); border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-mut); }
  .autochip.on { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .seg { display: flex; background: var(--div3); border-radius: 8px; padding: 3px; gap: 3px; }
  .seg button { flex: 1; padding: 6px; border: 0; border-radius: 6px; background: transparent; color: var(--t-mut); font-size: 12px; font-weight: 600; }
  .seg button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }
  .seg button:disabled { cursor: default; }
  .hint { font-size: 10.5px; color: var(--t-help); margin-top: 5px; line-height: 1.45; }

  .lankinfo { display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: var(--acc-soft); border: 1px solid var(--acc-border); border-radius: 8px;
    padding: 8px 12px; font-size: 11.5px; color: var(--t-head); margin-bottom: 12px; }
  .linktag { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--ok); margin-left: 6px; }
  .linktag.own { color: var(--varn); }
  .lank { border: 0; background: none; color: var(--acc); font-size: 11.5px; font-weight: 600;
    padding: 0; cursor: pointer; }
  .lank.sm { font-size: 10px; margin-top: 2px; text-align: left; }

  /* Låst tema-indikator (temat härleds ur typen; Landskap = Sol) */
  .temalast { display: inline-flex; align-items: center; gap: 9px; background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 8px 12px; align-self: flex-start; }
  .temaprick { width: 9px; height: 9px; border-radius: 50%; background: #C9871F; flex: none; }
  .temanamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .temainfo { font-size: 11px; color: var(--t-mut); }

  /* Galleri-rubrik med Sport-hämtknappen */
  .galhuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .caps.nomarg { margin-bottom: 0; }
  .galknappar { display: flex; align-items: center; gap: 10px; }
  .hlok { font-size: 11.5px; color: var(--ok); font-weight: 600; }
  .hamta { display: inline-flex; align-items: center; gap: 6px; background: var(--acc-soft);
    color: var(--acc); border: 1px solid var(--acc-border); border-radius: 7px; padding: 6px 12px;
    font-size: 12px; font-weight: 600; }
  .hamta svg { width: 13px; height: 13px; }
  .hlkalla { font-size: 11px; color: var(--t-mut); margin: -4px 0 10px; display: flex; align-items: center; gap: 6px; }
  .hlprick { width: 6px; height: 6px; border-radius: 50%; background: var(--acc); flex: none; }

  .figurer { display: flex; flex-direction: column; gap: 10px; }
  .figrad { display: flex; gap: 12px; align-items: flex-start; border: 1px solid var(--div3); border-radius: 10px; padding: 10px; background: var(--panel); }
  .figbild { width: 92px; height: 69px; flex: none; border-radius: 6px; display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--div); padding: 0; cursor: pointer; background-size: cover; background-position: center;
    background-repeat: no-repeat; background-color: var(--kort);
    background-image: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .figbild:hover { border-color: var(--acc); }
  .figbild.has { border-style: solid; }
  .figbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 9.5px; color: var(--t-mut); text-align: center; padding: 0 4px; }
  .figin { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; justify-content: center; }
  .figin input { background: var(--kort); font-size: 12.5px; padding: 7px 9px; }
  .figsrc { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--t-help); }
  .figref { font-family: var(--mono, ui-monospace, monospace); font-size: 11.5px; color: var(--t-head); }
  .fighint { font-size: 11px; color: var(--t-help); }
  .figx { flex: none; width: 28px; height: 28px; border-radius: 7px; border: 1px solid var(--div); background: var(--kort); color: var(--t-mut); font-size: 16px; }
  .figx.armerad { width: auto; padding: 0 10px; background: #C0453E; border-color: #C0453E; color: #fff; font-size: 11.5px; font-weight: 600; }
  .figadd { display: flex; align-items: center; justify-content: center; gap: 8px; border: 1.5px dashed var(--div); border-radius: 10px; padding: 11px; color: var(--t-mut); font-size: 13px; font-weight: 500; background: transparent; }
  .figadd:hover { border-color: var(--acc); color: var(--acc); }

  .platsrad { display: flex; gap: 8px; align-items: center; }
  .platsrad .pl { width: 38%; flex: none; background: var(--kort); font-size: 12.5px; padding: 7px 9px; }
  .platsrad .pt { flex: 1; min-width: 0; background: var(--kort); font-size: 12.5px; padding: 7px 9px; }

  .svepkort { display: flex; align-items: center; gap: 14px; }
  .svepik { width: 38px; height: 38px; border-radius: 10px; background: var(--acc-soft); color: var(--acc); display: flex; align-items: center; justify-content: center; flex: none; }
  .svepik svg { width: 18px; height: 18px; }
  .sveptxt { flex: 1; min-width: 0; }
  .svt { font-size: 14.5px; font-weight: 600; color: var(--t-head); }
  .svs { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }

  /* §10: godkänn prompten + generera-progress (Instagram Bildsvepet) */
  .felbox { border: 1px solid var(--div3); color: var(--varn); background: color-mix(in srgb, var(--varn) 8%, transparent); font-size: 12.5px; }
  .genGranska { border: 1px solid var(--acc-border); background: var(--acc-soft); }
  .genGranskaTitel { font-size: 12.5px; font-weight: 700; color: var(--t-head); }
  .genGranskaHint { font-size: 11px; color: var(--t-mut); margin-top: 2px; }
  .genGranskaFraga { margin-top: 9px; max-height: 220px; overflow-y: auto; font-size: 11.5px; }
  .genGranskaKnappar { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
  .genProgress { display: flex; align-items: center; gap: 9px; font-size: 12px; color: var(--t-head); }
  .genspin { width: 15px; height: 15px; border-radius: 50%; border: 2px solid var(--acc-soft); border-top-color: var(--acc);
    flex: none; animation: gospin 0.8s linear infinite; }
  @keyframes gospin { to { transform: rotate(360deg); } }

  .mdhuvud { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  pre { margin: 0; background: var(--panel); border: 1px solid var(--div3); border-radius: 8px; padding: 14px;
    font-family: var(--mono, ui-monospace, monospace); font-size: 12px; line-height: 1.6; color: var(--t-head);
    white-space: pre-wrap; word-break: break-word; max-height: 260px; overflow: auto; }
  .mdfot { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 16px; font-size: 13px; font-weight: 600; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .testhint { color: var(--varn); }
  .testpath { font-family: var(--mono, ui-monospace, monospace); font-size: 11.5px; }
  .synkfel { font-size: 12.5px; color: #C0453E; font-weight: 600; }
  .statusbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 7px;
    padding: 8px 14px; font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }
  .statusbtn:disabled { opacity: 0.5; }
  .deploystatus { font-size: 12.5px; color: var(--t-mut); font-weight: 600; }
</style>
