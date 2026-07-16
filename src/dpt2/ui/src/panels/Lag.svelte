<script>
  import { onMount, tick } from 'svelte'
  import {
    listaLag, listaTavlingar, sparaLag, sparaTavling, raderaLag, raderaTavling,
    valjFil, lasLagTrupp, hamtaLagTrupp, sparaSpelare, raderaSpelare,
    laggTavlingIKalender, taBortTavlingUrKalender, kopplaLagTavling,
  } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import Lagbricka from '../lib/Lagbricka.svelte'
  import { grenFarg } from '../lib/gren.js'
  import { radTillToppen } from '../lib/scroll.js'

  let lag = []
  let tavlingar = []
  let laddar = true
  let sparad = null

  const SPORTER = ['fotboll', 'handboll', 'innebandy', 'volleyboll', 'beachvolley', 'tennis', 'friidrott']
  const SPORT_ETIKETT = {
    fotboll: 'Fotboll', handboll: 'Handboll', innebandy: 'Innebandy', volleyboll: 'Volleyboll',
    beachvolley: 'Beachvolley', tennis: 'Tennis', friidrott: 'Friidrott',
  }
  const TYPER = ['liga', 'turnering', 'masterskap']
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }
  const GRENAR = ['dam', 'herr', 'mixed']
  const GREN_ETIKETT = { dam: 'Dam', herr: 'Herr', mixed: 'Mixed' }
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']

  onMount(async () => {
    ;[lag, tavlingar] = await Promise.all([listaLag(), listaTavlingar()])
    laddar = false
  })

  function initial(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }
  function flash(id) {
    sparad = id
    setTimeout(() => (sparad = sparad === id ? null : sparad), 1400)
  }

  // Serialisera lag-sparningar. Annars kan namn-fältets on:change och ett gren-/
  // kind-val på en NY rad spara samtidigt medan l.id fortfarande är 'nytt-…' →
  // två parallella upserts av samma slug där den stale (gren=dam-default) kan
  // vinna → laget blir Dam trots valt Herr. Kedjan gör att första create sätter
  // id:t innan nästa spar körs (som då blir en update).
  let sparKo = Promise.resolve()
  function gerLag(l) {
    sparKo = sparKo.then(() => _gerLag(l)).catch(() => {})
    return sparKo
  }
  async function _gerLag(l) {
    // Skicka id för befintliga rader — annars kan ett namnbyte aldrig uttryckas
    // (namn-slugen pekar då ut en annan post). Nya rader ('nytt-…') saknar id.
    const arNy = String(l.id).startsWith('nytt-')
    const res = await sparaLag({ ...l, id: arNy ? null : l.id })
    if (!res?.ok) return
    if (res.id && res.id !== l.id) {
      const gammalt = l.id
      l.id = res.id
      if (teamOpen === gammalt) teamOpen = res.id
      if (rosterOppen === gammalt) rosterOppen = res.id
      if (truppOppen === gammalt) truppOppen = res.id
      // Den frysta ordningen pekar på id:n — följ med när utkastet får sitt
      // riktiga id, annars försvinner raden man just skriver i ur listan.
      if (frystaGrupper) frystaGrupper = frystaGrupper
        .map((g) => ({ ...g, ids: g.ids.map((x) => (x === gammalt ? res.id : x)) }))
      lag = lag
    }
    flash(l.id)
  }
  // Samma spar-kö + id-återmappning som lagen (BUG-01): nya rader ('ny-…')
  // skickas utan id → backend skapar (suffixat id vid namnkrock med annan
  // gren/sport); raden tar sedan sitt riktiga id så nästa spar blir en update
  // på RÄTT rad (namnbyte + dam/herr-dubbletter fungerar).
  function gerTavling(t) {
    sparKo = sparKo.then(() => _gerTavling(t)).catch(() => {})
    return sparKo
  }
  async function _gerTavling(t) {
    const arNy = String(t.id).startsWith('ny-')
    const res = await sparaTavling({ ...t, id: arNy ? null : t.id })
    if (!res?.ok) return
    if (res.id && res.id !== t.id) {
      const gammalt = t.id
      t.id = res.id
      if (compOpen === gammalt) compOpen = res.id
      tavlingar = tavlingar
    }
    flash(t.id)
  }

  function sattKind(l, kind) {
    if (l.kind === kind) return
    l.kind = kind
    if (kind === 'individ' && l.gren === 'mixed') l.gren = null  // mixed bara team
    lag = lag                     // trigga re-render av villkorsfälten
    gerLag(l)
  }
  function sattGren(l, gren) {
    if (l.gren === gren) return
    l.gren = gren
    lag = lag
    gerLag(l)
  }

  // ── Flikar, sök, gren-filter, A–Ö-sortering ────────────────────────────────
  let lagTab = 'lag'             // 'lag' | 'tavlingar'
  let lagSearch = ''
  let lagGren = 'alla'           // 'alla' | 'dam' | 'herr' | 'mixed'
  let visaArkiv = false          // B1: växlar listan mellan aktiva och arkiverade
  const norm = (s) => (s || '').toLowerCase()

  const sorteraLag = (lista) => [...lista].sort((a, b) => (a.namn || '').localeCompare(b.namn || '', 'sv'))
  // Ta gren/sök som ARGUMENT — inte via closure. Ett reaktivt `$:`-block spårar
  // bara variabler som nämns i själva satsen, inte sådana som läses inne i en
  // anropad funktion. Med closure-varianten (`filtreraLag(basLag)`) blev varken
  // gren-chipsen eller sökrutan en dependency → listan filtrerades aldrig om
  // fast chip/räknare uppdaterades. Explicita argument gör dem spårbara.
  const filtreraLag = (lista, gren = lagGren, sok = lagSearch) => lista
    .filter((l) => gren === 'alla' || l.gren === gren)
    .filter((l) => !sok || norm(l.namn).includes(norm(sok)))
  // B1: gruppera efter sport för visning (fotboll/handboll/etc)
  function grupperaPerSport(lista) {
    const g = {}
    lista.forEach((l) => {
      const s = l.sport || 'fotboll'
      if (!g[s]) g[s] = []
      g[s].push(l)
    })
    return SPORTER.map((s) => ({ sport: s, lag: g[s] || [] })).filter((x) => x.lag.length)
  }

  $: lagSorterad = sorteraLag(lag)
  // B1: arkiverade lag göms i registret men raderas inte — gamla matcher pekar
  // fortfarande på dem. Arkivvyn är enda vägen tillbaka.
  $: aktivaLag = lagSorterad.filter((l) => !l.arkiverad)
  $: arkiveradeLag = lagSorterad.filter((l) => l.arkiverad)
  $: basLag = visaArkiv ? arkiveradeLag : aktivaLag
  $: lagGrenCounts = {
    alla: basLag.length,
    dam: basLag.filter((l) => l.gren === 'dam').length,
    herr: basLag.filter((l) => l.gren === 'herr').length,
    mixed: basLag.filter((l) => l.gren === 'mixed').length,
  }
  $: lagFiltrerat = filtreraLag(basLag, lagGren, lagSearch)

  // Ordningen FRYSES medan en rad redigeras: namn-sortering, sport-gruppering och
  // arkiv-filter är alla reaktiva på fälten man skriver i, så utan frysning
  // hoppar posten runt i listan för varje tangenttryck. Strukturen (id per
  // sportgrupp) fångas när raden öppnas och renderas mot LIVE-objekten; när
  // redigeringen stängs släpps ordningen och posten scrollas till sin rätta plats.
  let frystaGrupper = null       // [{sport, ids}] eller null = normal reaktiv ordning
  $: if (teamOpen == null) frystaGrupper = null    // varje stängningsväg släpper

  function fangaOrdning() {
    let bas = filtreraLag(sorteraLag(lag).filter((l) => (visaArkiv ? l.arkiverad : !l.arkiverad)))
    // Raden som öppnas ska alltid med i frysningen — annars göms en nyskapad
    // post av aktiva gren-/sökfilter innan den ens hunnit få sina fält satta.
    if (teamOpen != null && !bas.some((l) => l.id === teamOpen)) {
      const oppen = lag.find((l) => l.id === teamOpen)
      if (oppen) bas = [...bas, oppen]
    }
    frystaGrupper = grupperaPerSport(bas).map((g) => ({ sport: g.sport, ids: g.lag.map((l) => l.id) }))
  }

  $: lagGrupperat = frystaGrupper
    ? frystaGrupper
        .map((fg) => ({ sport: fg.sport, lag: fg.ids.map((id) => lag.find((x) => x.id === id)).filter(Boolean) }))
        .filter((fg) => fg.lag.length)
    : grupperaPerSport(lagFiltrerat)

  // §7 (Skala UX): hopfällbara sport-sektioner. En öppen redigering pinnar upp
  // sin sektion — annars försvinner formuläret man skriver i när man fäller.
  let lagCollapsed = {}          // sport → true (hopfälld)
  function toggleLagSport(sport) { lagCollapsed = { ...lagCollapsed, [sport]: !lagCollapsed[sport] } }
  const sektionOppen = (grupp) => !lagCollapsed[grupp.sport]
    || (teamOpen != null && grupp.lag.some((l) => l.id === teamOpen))

  // Tydlig tom-status: gren-filtret kan träffa 0 aktiva men N arkiverade
  // (upplevdes som en bugg — laget fanns, men bara i arkivet).
  $: arkivTraff = filtreraLag(arkiveradeLag, lagGren, lagSearch).length
  $: aktivTraff = filtreraLag(aktivaLag, lagGren, lagSearch).length

  function hexToRgba(hex, a) {
    const n = parseInt((hex || '').replace('#', ''), 16)
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
  }
  function grenChipStil(g) {
    if (g === 'alla' || lagGren !== g) return ''
    return `color:${grenFarg(g)};background:${hexToRgba(grenFarg(g), 0.14)}`
  }

  function periodText(t) {
    const f = t.fran || '', ti = t.till || ''
    if (/^\d{4}-\d{2}/.test(f) && /^\d{4}-\d{2}/.test(ti)) {
      const a = f.split('-'), b = ti.split('-')
      const yr = b[0] === a[0] ? a[0] : `${a[0]}–${b[0]}`
      return `${MK[+a[1] - 1]}–${MK[+b[1] - 1]} ${yr}`
    }
    return f || ti || ''
  }

  // ── Kompakt lista + redigering i utfälld rad (matcher-stil) ────────────────
  let teamOpen = null            // lag-id vars rad är utfälld
  let compOpen = null            // tävling-id vars rad är utfälld

  function apnaLag(l, rad = null) {
    if (teamOpen === l.id) { stangLagRedigering(); return }
    teamOpen = l.id; compOpen = null
    fangaOrdning()                 // lås listordningen medan raden är öppen
    radTillToppen(rad)
  }
  // Stäng + placera: ordningen släpps (posten sorteras/grupperas rätt) och den
  // nu rätt placerade raden scrollas i synfältet med spara-markeringen som fokus.
  async function stangLagRedigering() {
    const id = teamOpen
    teamOpen = null
    if (id == null) return
    await tick()
    const el = document.querySelector(`[data-lagid="${CSS.escape(String(id))}"]`)
    if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); flash(id) }
  }
  function apnaTavling(t, rad = null) {
    if (compOpen === t.id) { compOpen = null; return }
    compOpen = t.id; teamOpen = null
    radTillToppen(rad)
  }
  function stangRad() { stangLagRedigering(); compOpen = null }
  function onKeydown(e) {
    if (e.key === 'Escape' && (teamOpen != null || compOpen != null)) stangRad()
  }

  function metaRad(l) {
    return [
      SPORT_ETIKETT[l.sport], GREN_ETIKETT[l.gren],
      l.kind === 'individ' ? 'Individ' : 'Lag',
      l.trupp_n ? `${l.trupp_n} spelare` : null,
    ].filter(Boolean).join(' · ')
  }
  function tavlingNamn(tid) {
    return tavlingar.find((t) => t.id === tid)?.namn || tid
  }
  // BUG-09: två tävlingar kan heta lika (European League 2026 dam/herr) —
  // etiketten i chips + Koppla till…-listan måste bära gren·sport.
  function tavlingEtikett(t) {
    const gs = [GREN_ETIKETT[t.gren], SPORT_ETIKETT[t.sport]].filter(Boolean).join(' · ')
    return gs ? `${t.namn} · ${gs}` : t.namn
  }
  function tavlingChip(tid) {
    const t = tavlingar.find((x) => x.id === tid)
    return t ? tavlingEtikett(t) : tid
  }
  function kopplingsText(l) {
    const namn = (l.comps || []).map(tavlingNamn)
    return namn.length ? namn.join(' · ') : ''
  }

  // ── Tävlingskoppling (chips, many-to-many via tavling_lag) ────────────────
  async function kopplaTill(l, tavlingId) {
    if (!tavlingId || (l.comps || []).includes(tavlingId)) return
    l.comps = [...(l.comps || []), tavlingId]
    lag = lag
    await kopplaLagTavling(l.id, tavlingId, true)
  }
  async function kopplaBort(l, tavlingId) {
    l.comps = (l.comps || []).filter((x) => x !== tavlingId)
    lag = lag
    await kopplaLagTavling(l.id, tavlingId, false)
  }

  async function valjLoggaLag(l) {
    const f = await valjFil('Välj logga/porträtt (bild)', ['Bilder (*.png;*.jpg;*.jpeg;*.webp)'])
    if (f.ok) { l.logga = f.path; lag = lag; gerLag(l) }
  }
  async function valjLoggaTavling(t) {
    const f = await valjFil('Välj tävlingslogga (bild)', ['*.png', '*.jpg', '*.jpeg', '*.webp'])
    if (f.ok) { t.logga = f.path; tavlingar = tavlingar; gerTavling(t) }
  }
  async function nyttLag() {
    const id = 'nytt-' + Date.now()
    lag = [...lag, { id, namn: '', kind: 'team', sport: 'fotboll', gren: 'dam',
      instagram: '', hemsida: '', logga: null, stall_hemma: '#2f7cb0',
      stall_borta: '#ffffff', stall_tredje: '#16181c', profilfarg: '#2f7cb0',
      klubb: '', comps: [], arkiverad: false, press_email: '', ackr_dagar: null }]
    apnaLag({ id })
    // Direkt in i namnfältet — det är det enda obligatoriska på en ny post.
    await tick()
    document.querySelector(`[data-lagid="${id}"] .namn-in`)?.focus()
  }
  function nyTavling() {
    const id = 'ny-' + Date.now()
    tavlingar = [...tavlingar, { id, namn: '', typ: 'liga',
      sport: 'fotboll', gren: 'dam', fran: '', till: '', ort: '', arena: '',
      hemsida: '', logga: null, kalender: 0, press_email: '', ackr_dagar: null }]
    apnaTavling({ id })
  }

  // Tävling → fotojobb-utkast (Okategoriserat, ej synkat). Aktiveras/kategoriseras
  // sedan i Fotojobb-panelen — knappen här bara SKAPAR utkastet lokalt.
  let kalFelId = null
  let kalFelMsg = ''
  async function vaxlaTavlingKalender(t) {
    kalFelId = null
    if (t.kalender) {
      t.kalender = 0
      tavlingar = tavlingar
      await taBortTavlingUrKalender(t.id)
      return
    }
    const r = await laggTavlingIKalender(t.id)
    if (r?.ok) { t.kalender = 1; tavlingar = tavlingar }
    else { kalFelId = t.id; kalFelMsg = r?.fel || 'Kunde inte lägga till i kalendern.' }
  }

  // ── Trupp-källväljare (URL / CSV / bild / PDF) ─────────────────────────────
  let truppOppen = null          // lag-id vars källväljare är utfälld
  let truppLaddar = null         // lag-id som just läses in (spinner-läge)
  let truppUrl = ''              // URL-fältet (förifylls med lagets hemsida)
  let truppFel = ''

  function togglaTrupp(l) {
    if (truppOppen === l.id) { truppOppen = null; return }
    truppOppen = l.id
    truppUrl = l.hemsida || ''
    truppFel = ''
  }

  async function lasTrupp(l, kalla) {
    let arg = ''
    if (kalla === 'url') {
      arg = (truppUrl || '').trim()
    } else {
      const filter = { csv: ['CSV (*.csv)'], bild: ['Bilder (*.jpg;*.jpeg;*.png;*.heic;*.heif)'],
        pdf: ['PDF (*.pdf)'] }[kalla]
      const f = await valjFil('Välj spelarlista', filter)
      if (!f.ok) { if (f?.fel) truppFel = f.fel; return }
      arg = f.path
    }
    truppLaddar = l.id; truppFel = ''
    const r = await lasLagTrupp(l.id, kalla, arg)
    truppLaddar = null
    if (r?.ok) {
      l.trupp_n = r.antal; l.trupp_kalla = r.trupp_kalla; l.roster = r.roster || []
      lag = lag; truppOppen = null
      rosterOppen = l.id           // öppna direkt för granskning/rättning
      flash(l.id)
    } else {
      truppFel = r?.fel || 'Kunde inte läsa in truppen.'
    }
  }

  function truppEtikett(l) {
    if (!l.trupp_n) return 'ingen trupp inläst'
    return `${l.trupp_n} spelare i trupp${l.trupp_kalla ? ' · ' + l.trupp_kalla : ''}`
  }

  // ── Visa & redigera trupp ────────────────────────────────────────────────
  let rosterOppen = null         // lag-id vars redigerbara trupplista är utfälld

  async function togglaRoster(l) {
    if (rosterOppen === l.id) { rosterOppen = null; return }
    if (!l.roster) { l.roster = await hamtaLagTrupp(l.id); lag = lag }
    rosterOppen = l.id
  }
  function laggTillSpelare(l) {
    l.roster = [...(l.roster || []), { id: null, nr: '', namn: '', position: '' }]
    l.trupp_n = l.roster.length
    lag = lag
  }
  async function sparaSpelareRad(l, p) {
    if (!(p.namn || '').trim()) return       // tomma rader sparas inte förrän namngivna
    const r = await sparaSpelare(l.id, { id: p.id, nr: p.nr, namn: p.namn, position: p.position })
    if (r?.ok) { p.id = r.id; l.trupp_n = l.roster.length; l.roster = l.roster; lag = lag }
  }
  async function taBortSpelareRad(l, p) {
    l.roster = l.roster.filter((x) => x !== p)
    l.trupp_n = l.roster.length
    lag = lag
    if (p.id) await raderaSpelare(p.id)
  }

  async function taBortLag(l) {
    lag = lag.filter((x) => x !== l)
    if (teamOpen === l.id) teamOpen = null
    if (!String(l.id).startsWith('nytt-')) await raderaLag(l.id)
  }
  async function taBortTavling(t) {
    tavlingar = tavlingar.filter((x) => x !== t)
    if (compOpen === t.id) compOpen = null
    if (!String(t.id).startsWith('ny-')) await raderaTavling(t.id)
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="panel">
  <header>
    <h1 class="scd">Lag &amp; tävlingar</h1>
    <span class="sub">Registret som matcherna delar — loggor, hemsidor och Instagram</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar register…</p>
  {:else}
    <div class="tabs">
      <button class:on={lagTab === 'lag'} on:click={() => (lagTab = 'lag')}>Lag &amp; utövare · {aktivaLag.length}</button>
      <button class:on={lagTab === 'tavlingar'} on:click={() => (lagTab = 'tavlingar')}>Tävlingar · {tavlingar.length}</button>
    </div>

    {#if lagTab === 'lag'}
      <div class="toolrad">
        <div class="sokbox">
          <svg class="sokik" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
          <input bind:value={lagSearch} placeholder="Sök lag eller utövare…" />
        </div>
        <div class="grenchips">
          {#each ['alla', ...GRENAR] as g (g)}
            <button class="grenchip" class:on={lagGren === g} style={grenChipStil(g)} on:click={() => (lagGren = g)}>
              {g === 'alla' ? 'Alla' : GREN_ETIKETT[g]} · {lagGrenCounts[g]}
            </button>
          {/each}
        </div>
        {#if arkiveradeLag.length || visaArkiv}
          <button class="grenchip arkivchip" class:on={visaArkiv}
            on:click={() => { visaArkiv = !visaArkiv; teamOpen = null }}>
            Arkiv · {arkiveradeLag.length}
          </button>
        {/if}
        <!-- 7A: "+ Nytt" ligger i filterraden, utanför scroll-ytan. -->
        <button class="ny irad" on:click={nyttLag}>+ Nytt lag</button>
      </div>

      {#if !lagGrupperat.length}
        {#if !visaArkiv && arkivTraff}
          <p class="tom">{aktivTraff} aktiva · {arkivTraff} arkiverade —
            <button class="tomlank" on:click={() => { visaArkiv = true; teamOpen = null }}>visa arkivet ›</button></p>
        {:else}
          <p class="tom">{visaArkiv ? 'Inget arkiverat.' : 'Inga lag eller utövare hittades.'}</p>
        {/if}
      {:else}
        <div class="lista">
          {#each lagGrupperat as grupp (grupp.sport)}
            <div class="sportgrupp">
              <button class="sportnamn" on:click={() => toggleLagSport(grupp.sport)}
                title={sektionOppen(grupp) ? 'Fäll ihop' : 'Fäll ut'}>
                <span class="sportchev">{sektionOppen(grupp) ? '▾' : '▸'}</span>
                {SPORT_ETIKETT[grupp.sport]} <span class="sportantal">· {grupp.lag.length}</span>
              </button>
              {#if sektionOppen(grupp)}
              {#each grupp.lag as l (l.id)}
            <div class="kkort" data-lagid={l.id} style={l.gren ? `border-left:3px solid ${grenFarg(l.gren)}` : ''}>
              <div class="krad" role="button" tabindex="0" on:click={(e) => apnaLag(l, e.currentTarget)}
                on:keydown={(e) => e.key === 'Enter' && apnaLag(l, e.currentTarget)}>
                <button class="logoslot" on:click|stopPropagation={() => valjLoggaLag(l)} title="Välj logga/porträtt">
                  <Lagbricka namn={l.namn} farg={(l.kind === 'individ' ? l.profilfarg : l.stall_hemma) || '#8A8172'} logga={l.logga} storlek={28} />
                </button>
                <div class="ktxt2">
                  <div class="rad1b">
                    {#if l.gren}<span class="grenlbl2 scd" style="color:{grenFarg(l.gren)}">{GREN_ETIKETT[l.gren]}</span>{/if}
                    <span class="namn2 scd">{l.namn || 'Namnlöst lag'}</span>
                  </div>
                  <div class="kmeta2">{[metaRad(l) || 'Ofullständig post', kopplingsText(l)].filter(Boolean).join(' · ')}</div>
                </div>
                {#if sparad === l.id}<span class="flash">✓</span>{/if}
                <button class="x" class:armerad={$armerad === `lag-${l.id}`}
                  title={$armerad === `lag-${l.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                  on:click|stopPropagation={taBortKlick(`lag-${l.id}`, () => taBortLag(l))}>{$armerad === `lag-${l.id}` ? 'Ta bort?' : '×'}</button>
              </div>

              {#if teamOpen === l.id}
                <div class="inlineform">
                  <div class="falt">
                    <div class="rad1">
                      <div class="seg">
                        <button class:on={l.kind !== 'individ'} on:click={() => sattKind(l, 'team')}>Lag</button>
                        <button class:on={l.kind === 'individ'} on:click={() => sattKind(l, 'individ')}>Individ</button>
                      </div>
                      <input class="namn-in scd" bind:value={l.namn} on:change={() => gerLag(l)}
                        placeholder={l.kind === 'individ' ? 'Namn' : 'Lagnamn'} />
                      <div class="seg">
                        {#each GRENAR as g}
                          {#if g !== 'mixed' || l.kind !== 'individ'}
                            <button class:on={l.gren === g} on:click={() => sattGren(l, g)}>{GREN_ETIKETT[g]}</button>
                          {/if}
                        {/each}
                      </div>
                    </div>
                    <label class="sportrad">
                      <span class="lbl">Sport</span>
                      <select bind:value={l.sport} on:change={() => gerLag(l)}>
                        <option value={null}>Välj sport…</option>
                        {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                      </select>
                    </label>
                    <label class="arkivrad">
                      <input type="checkbox" bind:checked={l.arkiverad} on:change={() => gerLag(l)} />
                      <span class="lbl">Arkiverat</span>
                      <span class="help">Göms i registret. Matcher som redan använder laget påverkas inte.</span>
                    </label>
                    <div class="dubbel">
                      <input bind:value={l.hemsida} on:change={() => gerLag(l)} placeholder="Hemsida" />
                      <input bind:value={l.instagram} on:change={() => gerLag(l)} placeholder="@instagram" />
                    </div>
                    {#if l.kind !== 'individ'}
                      <!-- Ackreditering: i seriespel äger HEMMAKLUBBEN processen för
                           sina hemmamatcher — klubbens fält vinner över tävlingens
                           (som är fallback för mästerskap/turneringar). -->
                      <div class="dubbel">
                        <input bind:value={l.press_email} on:change={() => gerLag(l)} placeholder="Pressadress (ackreditering hemmamatcher)" />
                        <input bind:value={l.ackr_dagar} on:change={() => gerLag(l)} inputmode="numeric" placeholder="Ackr: dagar före match" />
                      </div>
                    {/if}

                    {#if l.kind === 'individ'}
                      <div class="stall">
                        <span class="lbl">Profil</span>
                        <input type="color" bind:value={l.profilfarg} on:change={() => gerLag(l)} title="Profilfärg" />
                        <input class="klubb" bind:value={l.klubb} on:change={() => gerLag(l)} placeholder="Klubb / land" />
                        {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                      </div>
                    {:else}
                      <div class="stall">
                        <span class="lbl">Ställ</span>
                        <input type="color" bind:value={l.stall_hemma} on:change={() => gerLag(l)} title="Hemma" />
                        <input type="color" bind:value={l.stall_borta} on:change={() => gerLag(l)} title="Borta" />
                        <input type="color" bind:value={l.stall_tredje} on:change={() => gerLag(l)} title="Tredje" />
                        <span class="lbl mut">hemma · borta · tredje</span>
                        {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                      </div>
                      <div class="trupprad">
                        <button class="spelarbtn" on:click={() => togglaTrupp(l)} disabled={truppLaddar === l.id}>Läs in spelare…</button>
                        <span class="truppinfo">{truppEtikett(l)}</span>
                        {#if l.trupp_n}<button class="visaredigera" on:click={() => togglaRoster(l)}>Visa &amp; redigera ›</button>{/if}
                      </div>

                      {#if rosterOppen === l.id}
                        <div class="rosterbox">
                          <div class="rosterhuvud"><span class="rnr">Nr</span><span class="rnamn">Namn</span><span class="rpos">Pos</span><span class="rx"></span></div>
                          {#each l.roster || [] as p, pi (p)}
                            <div class="rosterrad">
                              <input class="rnr" bind:value={p.nr} on:change={() => sparaSpelareRad(l, p)} />
                              <input class="rnamn" bind:value={p.namn} on:change={() => sparaSpelareRad(l, p)} />
                              <input class="rpos" bind:value={p.position} on:change={() => sparaSpelareRad(l, p)} />
                              <button class="rx" class:armerad={$armerad === `sp-${l.id}-${pi}`}
                                title={$armerad === `sp-${l.id}-${pi}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                                on:click={taBortKlick(`sp-${l.id}-${pi}`, () => taBortSpelareRad(l, p))}>{$armerad === `sp-${l.id}-${pi}` ? 'Ta bort?' : '×'}</button>
                            </div>
                          {/each}
                          <button class="rosteradd" on:click={() => laggTillSpelare(l)}>+ Lägg till spelare</button>
                        </div>
                      {/if}

                      {#if truppLaddar === l.id}
                        <div class="truppladdar">
                          <span class="spin"></span>
                          <div><div class="tlt">Läser in trupp…</div><div class="tls">Hämtar och tolkar laguppställningen.</div></div>
                        </div>
                      {:else if truppOppen === l.id}
                        <div class="truppvaljare">
                          <div class="truppcaps">Läs in trupp från</div>
                          <div class="truppurl">
                            <input bind:value={truppUrl} placeholder="Hemsida eller URL till laguppställning…" />
                            <button class="hamta" on:click={() => lasTrupp(l, 'url')}>Hämta</button>
                          </div>
                          <div class="avdelare"><span class="linje"></span><span class="eller">eller ladda upp fil</span><span class="linje"></span></div>
                          <div class="filknappar">
                            <button on:click={() => lasTrupp(l, 'csv')}>CSV</button>
                            <button on:click={() => lasTrupp(l, 'bild')}>Bild · JPG / PNG / HEIF</button>
                            <button on:click={() => lasTrupp(l, 'pdf')}>PDF</button>
                          </div>
                          {#if truppFel}<div class="truppfel">⚠ {truppFel}</div>
                          {:else}<div class="trupphint">Sidan/filen tolkas och spelarna läggs i lagets trupp.</div>{/if}
                        </div>
                      {/if}
                    {/if}

                    <div class="kopplbox">
                      <div class="truppcaps">Kopplad till liga / tävling / mästerskap</div>
                      <div class="chips">
                        {#each l.comps || [] as tid (tid)}
                          <span class="chip">{tavlingChip(tid)}
                            <button class="chipx" title="Koppla bort" on:click={() => kopplaBort(l, tid)}>×</button>
                          </span>
                        {/each}
                        {#if (tavlingar.filter((t) => !(l.comps || []).includes(t.id))).length}
                          <select class="chipny" value="" on:change={(e) => { kopplaTill(l, e.target.value); e.target.value = '' }}>
                            <option value="" disabled>+ Koppla till…</option>
                            {#each tavlingar.filter((t) => !(l.comps || []).includes(t.id)) as t (t.id)}
                              <option value={t.id}>{tavlingEtikett(t)}</option>
                            {/each}
                          </select>
                        {:else if !(l.comps || []).length}
                          <span class="kmeta">Inga tävlingar i registret ännu.</span>
                        {/if}
                      </div>
                    </div>
                  </div>
                </div>
                <div class="formfot"><button class="klart" on:click={stangRad}>Klart</button></div>
              {/if}
            </div>
              {/each}
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {:else}
      {#if !tavlingar.length}
        <p class="tom">Inga tävlingar ännu.</p>
      {:else}
        <div class="lista">
          {#each tavlingar as t (t.id)}
            <div class="kkort" style={t.gren ? `border-left:3px solid ${grenFarg(t.gren)}` : ''}>
              <div class="krad" role="button" tabindex="0" on:click={(e) => apnaTavling(t, e.currentTarget)}
                on:keydown={(e) => e.key === 'Enter' && apnaTavling(t, e.currentTarget)}>
                <button class="logoslot" on:click|stopPropagation={() => valjLoggaTavling(t)} title="Välj logga">
                  <Lagbricka namn={t.namn} farg={'#8A8172'} logga={t.logga} storlek={28} />
                </button>
                <div class="ktxt2">
                  <div class="rad1b">
                    {#if t.gren}<span class="grenlbl2 scd" style="color:{grenFarg(t.gren)}">{GREN_ETIKETT[t.gren]}</span>{/if}
                    <span class="namn2 scd">{t.namn || 'Namnlös tävling'}</span>
                  </div>
                  <div class="kmeta2">{[TYP_ETIKETT[t.typ], SPORT_ETIKETT[t.sport], periodText(t), t.ort].filter(Boolean).join(' · ')}</div>
                </div>
                {#if t.kalender}<span class="ikalendern">I kalendern</span>{/if}
                {#if sparad === t.id}<span class="flash">✓</span>{/if}
                <button class="x" class:armerad={$armerad === `tavling-${t.id}`}
                  title={$armerad === `tavling-${t.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                  on:click|stopPropagation={taBortKlick(`tavling-${t.id}`, () => taBortTavling(t))}>{$armerad === `tavling-${t.id}` ? 'Ta bort?' : '×'}</button>
              </div>

              {#if compOpen === t.id}
                <div class="inlineform">
                  <div class="falt">
                    <input class="namn-in scd" bind:value={t.namn} on:change={() => gerTavling(t)} placeholder="Tävlingens namn" />
                    <div class="trippel">
                      <select bind:value={t.typ} on:change={() => gerTavling(t)}>
                        {#each TYPER as ty}<option value={ty}>{TYP_ETIKETT[ty]}</option>{/each}
                      </select>
                      <select bind:value={t.sport} on:change={() => gerTavling(t)}>
                        {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                      </select>
                      <select bind:value={t.gren} on:change={() => gerTavling(t)}>
                        <option value={null}>Gren…</option>
                        {#each GRENAR as g}<option value={g}>{GREN_ETIKETT[g]}</option>{/each}
                      </select>
                    </div>
                    <div class="dubbel">
                      <label class="datumf"><span class="lbl">Start</span><input type="date" bind:value={t.fran} on:change={() => gerTavling(t)} /></label>
                      <label class="datumf"><span class="lbl">Slut</span><input type="date" bind:value={t.till} on:change={() => gerTavling(t)} /></label>
                    </div>
                    <div class="dubbel">
                      <input bind:value={t.ort} on:change={() => gerTavling(t)} placeholder="Ort" />
                      <input bind:value={t.arena} on:change={() => gerTavling(t)} placeholder="Arena" />
                    </div>
                    <input bind:value={t.hemsida} on:change={() => gerTavling(t)} placeholder="Hemsida" />
                    <!-- Ackreditering: arrangörens regler — pressadressen förifyller
                         mailet, dagarna ger "begär senast" (tomt = 10 dagar). -->
                    <div class="dubbel">
                      <input bind:value={t.press_email} on:change={() => gerTavling(t)} placeholder="Pressadress (ackreditering)" />
                      <input bind:value={t.ackr_dagar} on:change={() => gerTavling(t)} inputmode="numeric" placeholder="Ackr: dagar före match (10)" />
                    </div>
                    {#if sparad === t.id}<span class="flash">✓ sparat</span>{/if}
                    <div class="kalfot">
                      <span class="kalik">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                      </span>
                      <span class="kaltxt">Läggs som ett Okategoriserat utkast i Fotojobb — du kategoriserar och aktiverar synk dit</span>
                      <button class="kalbtn" class:i={t.kalender} on:click={() => vaxlaTavlingKalender(t)}>
                        {t.kalender ? 'Utkast i Fotojobb ✓' : 'Lägg i Google Calendar ›'}
                      </button>
                    </div>
                    {#if kalFelId === t.id}<div class="kalfel">⚠ {kalFelMsg}</div>{/if}
                  </div>
                </div>
                <div class="formfot"><button class="klart" on:click={stangRad}>Klart</button></div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
      <button class="ny" on:click={nyTavling}>+ Ny tävling</button>
    {/if}
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 900px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--t-head); }   /* 6a: paneltitel 20px */
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .tabs { display: inline-flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; margin: 16px 0 0; }
  .tabs button { padding: 8px 16px; border: 0; border-radius: 7px; background: transparent; color: var(--t-mut); font-size: 13px; font-weight: 600; }
  .tabs button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }

  .toolrad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 16px 2px 14px; }
  .sokbox { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 8px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort); padding: 8px 14px; }
  .sokik { width: 15px; height: 15px; color: var(--t-help); flex: none; }
  .sokbox input { flex: 1; min-width: 0; border: 0; background: transparent; padding: 0;
    font-size: 13px; color: var(--t-head); outline: none; }
  .grenchips { display: flex; gap: 6px; flex-wrap: wrap; flex: none; }
  .grenchip { padding: 7px 13px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .grenchip.on { border-color: var(--acc-border); }
  .grenchip.on:first-child { background: var(--acc-soft); color: var(--acc); }

  .kmeta { font-size: 12px; color: var(--t-mut); }
  .lista { display: flex; flex-direction: column; gap: 12px; }

  .sportgrupp { display: flex; flex-direction: column; gap: 6px; }
  .sportnamn { display: flex; align-items: center; gap: 6px; border: 0; background: transparent; text-align: left;
    font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-label); padding: 0 4px; cursor: pointer; }
  .sportnamn:hover { color: var(--t-head); }
  .sportchev { font-size: 10px; color: var(--t-help); width: 11px; flex: none; }
  .sportantal { font-weight: 600; color: var(--t-help); letter-spacing: 0; }
  .tomlank { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: inherit; padding: 0; cursor: pointer; }

  /* Kortskal (rad + ev. utfälld redigering) — matcher-stil */
  .kkort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); overflow: hidden; }
  /* Kompakt rad (~40 px) */
  .krad { display: flex; align-items: center; gap: 12px; padding: 8px 12px; cursor: pointer; }
  .krad:hover { background: var(--div3); }
  .logoslot { border: 0; background: transparent; padding: 0; border-radius: 50%; flex: none; cursor: pointer; }
  .logoslot:hover { outline: 2px solid var(--acc); outline-offset: 1px; }
  .ktxt2 { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .rad1b { display: flex; align-items: center; gap: 7px; }
  .namn2 { font-size: 12.5px; font-weight: 700; color: var(--t-head); }
  .grenlbl2 { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; flex: none; }
  .kmeta2 { font-size: 11px; color: var(--t-mut); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ikalendern { font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--ok); background: color-mix(in srgb, var(--ok) 13%, transparent); padding: 3px 8px;
    border-radius: 6px; flex: none; }

  .falt { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .rad1 { display: flex; gap: 8px; align-items: center; }
  .rad1 .namn-in { flex: 1; min-width: 0; }
  .dubbel { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .trippel { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }

  /* Tävlingskoppling: chips (many-to-many, borttagbara) */
  .kopplbox { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 8px; }
  .chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 5px; background: var(--acc-soft);
    color: var(--acc); border-radius: 999px; padding: 4px 6px 4px 11px; font-size: 12px;
    font-weight: 600; }
  .chipx { border: 0; background: transparent; color: inherit; font-size: 13px;
    line-height: 1; width: 17px; height: 17px; border-radius: 50%; padding: 0; }
  .chipx:hover { background: var(--acc); color: var(--kort); }
  .chipny { border: 1.5px dashed var(--div); border-radius: 999px; background: transparent;
    color: var(--t-mut); font-size: 12px; padding: 4px 9px; max-width: 150px; }
  .chipny:hover { border-color: var(--acc); color: var(--acc); }
  .sportrad { display: flex; align-items: center; gap: 10px; }
  .sportrad select { flex: 1; min-width: 0; }
  .arkivrad { display: flex; align-items: center; gap: 8px; }
  .arkivrad input[type="checkbox"] { flex: none; }
  .arkivrad .lbl { font-size: 13px; }
  .arkivrad .help { font-size: 11px; color: var(--t-help); }
  .datumf { display: flex; flex-direction: column; gap: 4px; }
  .datumf input { width: 100%; box-sizing: border-box; }
  .kalfot { display: flex; align-items: center; gap: 10px; margin-top: 4px; padding: 10px 12px;
    background: var(--panel); border: 1px solid var(--div3); border-radius: 9px; }
  .kalik { width: 30px; height: 30px; border-radius: 8px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .kalik svg { width: 16px; height: 16px; }
  .kaltxt { flex: 1; min-width: 0; font-size: 12px; color: var(--t-mut); }
  .kalbtn { flex: none; background: var(--acc); color: #fff; border: 0; border-radius: 7px;
    padding: 8px 13px; font-size: 12.5px; font-weight: 600; }
  .kalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .kalfel { font-size: 11px; color: var(--rose); margin-top: -2px; }
  .trupprad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .spelarbtn { background: var(--kort); border: 1px solid var(--div); border-radius: 8px;
    padding: 8px 12px; font-size: 12.5px; color: var(--t-mut); font-weight: 500; flex: none; }
  .spelarbtn:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .spelarbtn:disabled { opacity: 0.5; }
  .truppinfo { font-size: 11px; color: var(--t-mut); }
  .visaredigera { border: 0; background: none; font-size: 11.5px; color: var(--acc);
    font-weight: 600; padding: 0; flex: none; }
  .truppladdar { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 14px; display: flex; align-items: center; gap: 12px; }
  .spin { width: 22px; height: 22px; border-radius: 50%; flex: none;
    border: 3px solid var(--acc-soft); border-top-color: var(--acc); animation: lagspin 0.8s linear infinite; }
  @keyframes lagspin { to { transform: rotate(360deg); } }
  .tlt { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .tls { font-size: 11px; color: var(--t-mut); }
  .rosterbox { margin-left: 0; border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 6px; }
  .rosterhuvud { display: flex; align-items: center; gap: 8px; padding: 0 2px 2px; font-size: 9.5px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  .rosterhuvud .rnr { width: 34px; flex: none; }
  .rosterhuvud .rnamn { flex: 1; }
  .rosterhuvud .rpos { width: 52px; flex: none; }
  .rosterhuvud .rx { width: 28px; flex: none; }
  .rosterrad { display: flex; align-items: center; gap: 8px; }
  .rosterrad input.rnr { width: 34px; flex: none; text-align: center; padding: 6px 4px; font-size: 12px; background: var(--kort); }
  .rosterrad input.rnamn { flex: 1; min-width: 0; padding: 6px 9px; font-size: 12.5px; background: var(--kort); }
  .rosterrad input.rpos { width: 52px; flex: none; text-align: center; padding: 6px 6px; font-size: 12px; background: var(--kort); }
  .rosterrad button.rx { width: 28px; height: 28px; flex: none; border-radius: 6px; border: 1px solid var(--div);
    background: var(--kort); color: var(--t-mut); font-size: 15px; line-height: 1; }
  .rosterrad button.rx:hover { background: var(--rose); border-color: var(--rose); color: #fff; }
  .rosterrad button.rx.armerad { width: auto; padding: 0 10px; background: #C0453E; border-color: #C0453E;
    color: #fff; font-size: 11.5px; font-weight: 600; }
  .rosteradd { display: flex; align-items: center; justify-content: center; gap: 7px; margin-top: 2px;
    border: 1.5px dashed var(--div); border-radius: 8px; padding: 8px; color: var(--t-mut);
    font-size: 12px; background: transparent; }
  .rosteradd:hover { border-color: var(--acc); color: var(--acc); }
  .truppvaljare { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 9px; }
  .truppcaps { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  .truppurl { display: flex; gap: 6px; }
  .truppurl input { flex: 1; min-width: 0; background: var(--kort); font-size: 12px; padding: 7px 9px; }
  .hamta { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 7px 13px;
    font-size: 12px; font-weight: 600; flex: none; }
  .hamta:disabled { opacity: 0.5; }
  .avdelare { display: flex; align-items: center; gap: 8px; }
  .linje { height: 1px; flex: 1; background: var(--div3); }
  .eller { font-size: 10px; color: var(--t-help); }
  .filknappar { display: flex; gap: 6px; flex-wrap: wrap; }
  .filknappar button { background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 6px 11px; font-size: 12px; color: var(--t-head); }
  .filknappar button:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .filknappar button:disabled { opacity: 0.5; }
  .trupphint { font-size: 10px; color: var(--t-help); line-height: 1.45; }
  .truppfel { font-size: 11px; color: var(--rose); }
  input, select { padding: 7px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .namn-in { font-size: 15px; font-weight: 700; }

  .seg { display: flex; flex: none; border: 1px solid var(--div); border-radius: 8px; overflow: hidden; }
  .seg button { padding: 6px 12px; border: 0; background: var(--panel); color: var(--t-mut);
    font-size: 12px; font-weight: 600; cursor: pointer; }
  .seg button.on { background: var(--acc); color: var(--kort); }

  .stall { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .klubb { flex: 1; min-width: 120px; }
  .lbl { font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--t-caps); }
  .lbl.mut { font-weight: 500; color: var(--t-help); text-transform: none; letter-spacing: 0; }
  input[type='color'] { width: 30px; height: 28px; padding: 2px; border-radius: 7px; cursor: pointer; }
  .flash { font-size: 11.5px; font-weight: 600; color: var(--ok); align-self: center; flex: none; }

  .x { width: 26px; height: 26px; flex: none; border: 1px solid var(--div);
    border-radius: 7px; background: var(--kort); color: var(--t-mut); font-size: 16px;
    line-height: 1; align-self: center; }
  .x:hover { background: var(--rose); border-color: var(--rose); color: #fff; }
  /* Beväpnad tvåstegsknapp: × expanderar till rött "Ta bort?", andra klicket raderar. */
  .x.armerad { width: auto; padding: 0 10px; height: 26px; background: #C0453E; border-color: #C0453E;
    color: #fff; font-size: 11.5px; font-weight: 600; }

  .ny { margin-top: 10px; padding: 11px; width: 100%; border: 1.5px dashed var(--div);
    border-radius: var(--r); background: transparent; color: var(--t-mut);
    font-size: 13px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
  /* 7A: samma knapp, men kompakt i filterraden. */
  .ny.irad { margin-top: 0; width: auto; flex: none; margin-left: auto; padding: 8px 14px;
    border-radius: 999px; font-size: 12.5px; }
  /* Arkivchipet står för sig — skilt från gren-chipsen det ligger bredvid. */
  .arkivchip { margin-left: 6px; border-style: dashed; }

  /* Utfälld redigering — inline i radens kort (matcher-stil) */
  .inlineform { border-top: 1px solid var(--div3); padding: 16px 14px; }
  .formfot { padding: 12px 14px; border-top: 1px solid var(--div3); }
  .klart { width: 100%; padding: 10px; border: 0; border-radius: 8px; background: var(--acc);
    color: #fff; font-size: 13.5px; font-weight: 600; }
  .klart:hover { filter: brightness(1.05); }
</style>
