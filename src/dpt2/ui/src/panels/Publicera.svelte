<script>
  // Matchpublicering — enhetlig publiceringsyta (f.d. Publicera: Live + SoMe).
  // Skapa en gång → publicera överallt. Delad resultatremsa (ResultatRemsa,
  // skriver på matchposten) matar alla utgångar; Steg 1 Innehåll (katalog +
  // text + länkar) återanvänds; Steg 2 Skicka till renderar en riktig,
  // server-renderad förhandsvisning per kanal (Horisont) med fokus + zoom som
  // matas till skarp rendering. Gren-signalen = färgad kant + glow (låst,
  // ingen textetikett). Design: handoff-matchpublicering (8 jul 2026).
  import { onMount, createEventDispatcher } from 'svelte'
  import {
    listaMatcher, hamtaMatch, aktivMatch, sattAktivMatch, sportprofiler, listaLag,
    valjMapp, listaSomeBilder, thumbForBild,
    forhandsgranskaStory, publiceraLiveStory, publiceraTillSoMe, nyTestPaketMapp,
    publiceraInnehallNatet, listaMaterial, sparaMaterial,
    listaMinneskort, exporteraSkyddade,
    pagangMatcher, sattPagangVisa, publiceraPagangMatcher,
  } from '../lib/api.js'
  import ResultatRemsa from '../lib/ResultatRemsa.svelte'
  import { grenFarg } from '../lib/gren.js'
  import { testMode } from '../lib/testlage.js'

  const dispatch = createEventDispatcher()

  // ── Grunddata ──────────────────────────────────────────────────────────────
  let matcher = []
  let lagAlla = []
  let profiler = {}
  let match = null                 // fullständig aktiv match
  let materials = []
  const tema = 'Hav'               // Skagen-tema för rendern (gren styr kanten, inte temat)

  $: profil = profiler[match?.sport] || profiler.fotboll ||
    { res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid', mid_ph: '3–0',
      has_scorers: true, scorers_label: 'Målskyttar', start_moment: 'Avspark' }

  onMount(async () => {
    try {
      let akt
      ;[matcher, profiler, lagAlla, akt, materials] = await Promise.all(
        [listaMatcher(), sportprofiler(), listaLag(), aktivMatch(), listaMaterial()])
      const id = akt?.id || matcher[0]?.id
      if (id) await laddaMatch(id)
    } catch (e) { console.error('Matchpublicering: init', e) }
    laddaPagang()
  })

  async function laddaMatch(id) {
    match = await hamtaMatch(id)
    galleriUrl = match?.galleri || galleriUrl
    hemsidaUrl = match?.sida_url || hemsidaUrl
    scheduleAll()
  }

  // ── Matchväljare ───────────────────────────────────────────────────────────
  let matchOpen = false
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function datumTxt(iso) { const d = (iso || '').split('-').map(Number); return d.length === 3 ? `${d[2]} ${MK[d[1] - 1]}` : '' }
  $: matchMeta = match ? [datumTxt(match.datum), match.resultat || 'Kommande'].filter(Boolean).join(' · ') : ''
  async function valjMatch(id) {
    matchOpen = false
    if (id === match?.id) return
    await sattAktivMatch(id)
    await laddaMatch(id)
  }

  // ── Steg 1: Innehåll ───────────────────────────────────────────────────────
  let folderPath = ''
  let photos = []                  // {path, sel, cover}
  let laddarBilder = false
  // Appen laddas från file:// → WKWebView blockerar <img src="file://…"> mot
  // andra kataloger. Bilder visas därför som base64 data-URI:er via
  // thumbForBild (samma bevisade mekanism som Innehåll/BildvaljareFokuspunkt).
  let thumbs = {}                  // sökväg → data-URI (source-foton)
  async function laddaThumbs(paths) {
    const jobb = (paths || []).filter((p) => p && !thumbs[p]).map(async (p) => {
      const t = await thumbForBild(p)
      if (t?.ok) thumbs[p] = t.data_uri
    })
    if (!jobb.length) return
    await Promise.all(jobb)
    thumbs = thumbs
  }
  $: selCount = photos.filter((p) => p.sel).length
  $: coverPath = (photos.find((p) => p.sel && p.cover) || photos.find((p) => p.sel) || {}).path || ''
  $: selectedPaths = photos.filter((p) => p.sel).map((p) => p.path)

  async function valjKatalog() {
    const r = await valjMapp('Välj katalog med redigerade bilder (Lightroom-export)')
    if (r?.ok && r.path) { folderPath = r.path; await lasKatalog() }
  }
  async function lasKatalog() {
    if (!folderPath) return
    laddarBilder = true
    const lista = await listaSomeBilder(folderPath)
    laddarBilder = false
    photos = (lista || []).map((p, i) => ({ path: p, sel: i < 6, cover: i === 0 }))
    laddaThumbs(photos.map((p) => p.path))
    scheduleAll()
  }
  function klickaBild(i) {
    const p = photos[i]
    if (p.sel && !p.cover) { photos = photos.map((x, j) => ({ ...x, cover: j === i })) }  // vald igen → omslag
    else {
      const sel = !p.sel
      photos[i] = { ...p, sel, cover: sel ? p.cover : false }
      if (!sel && p.cover) { const f = photos.findIndex((x) => x.sel); if (f >= 0) photos[f].cover = true }
      if (sel && !photos.some((x, j) => x.sel && x.cover && j !== i)) photos[i].cover = true
      photos = photos
    }
    scheduleAll()
  }

  // Text + tokens
  let caption = 'Stabil hemmaseger på {arena}! {resultat}. Mål: {målskyttar}. {@lag} {#liga} #dalecarliaphoto'
  let capEl
  const TOKENS = ['{resultat}', '{målskyttar}', '{arena}', '{@lag}', '{galleri}', '{hemsida}']
  function insertToken(tok) {
    const el = capEl
    const s = el ? el.selectionStart : caption.length
    const e = el ? el.selectionEnd : caption.length
    caption = caption.slice(0, s) + tok + caption.slice(e)
    if (el) setTimeout(() => { el.focus(); el.selectionStart = el.selectionEnd = s + tok.length }, 0)
  }

  // Länkar
  let galleriUrl = ''
  let hemsidaUrl = ''

  // Token-upplösning (samma modell som Innehåll/SoMe-bildtexten)
  const _hashtag = (s) => (s || '').replace(/[^\p{L}\p{N}]/gu, '')
  function handle(namn) { return (lagAlla.find((x) => x.namn === namn)?.instagram || '').replace(/^@/, '') }
  function losText(text, { web = false } = {}) {
    const vals = {
      resultat: match?.resultat || '', målskyttar: match?.malskyttar || '',
      arena: match?.arena || '', motståndare: match?.lag_borta || '',
      '@lag': handle(match?.lag_hemma) ? '@' + handle(match?.lag_hemma) : '',
      '#liga': match?.liga ? '#' + _hashtag(match.liga) : '',
      galleri: galleriUrl || '', hemsida: web ? '' : (hemsidaUrl || ''),  // webben självlänkar inte
    }
    let ut = (text || '').replace(/\{([^{}]+)\}/g, (whole, key) => (key in vals ? vals[key] : whole))
    if (web) ut = ut.replace(/[#@][\p{L}\p{N}_]+/gu, '').replace(/ *\n/g, '\n').trim()
    return ut.replace(/[ \t]{2,}/g, ' ').trim()
  }

  // ── Steg 2: Skicka till (kanaler + beskärning) ──────────────────────────────
  // Format-koder = backendens (story_overlay.FORMAT_H). Etikett = kod med ':'.
  const KANALER = [
    { key: 'live', namn: 'Live-story', under: 'Instagram Story', format: ['9x16'], wide: false },
    { key: 'ig', namn: 'IG-inlägg', under: 'Instagram · karusell', format: ['4x5', '1x1'], wide: false },
    { key: 'fb', namn: 'Facebook', under: 'Facebook-sida', format: ['1x1', '4x5', '1.91x1'], wide: false },
    { key: 'webb', namn: 'Webbartikel', under: 'Hemsida · Hero', format: ['2x1', '16x9'], wide: true },
  ]
  const fmtEti = (f) => f.replace('x', ':')
  const fmtRatio = (f) => { const [a, b] = f.split('x'); return `${a}/${b}` }
  let ch = {
    live: { on: true, fmt: '9x16', fokus: { x: 50, y: 33 }, zoom: 1 },
    ig: { on: true, fmt: '4x5', fokus: { x: 50, y: 40 }, zoom: 1 },
    fb: { on: false, fmt: '1x1', fokus: { x: 50, y: 45 }, zoom: 1 },
    webb: { on: true, fmt: '2x1', fokus: { x: 50, y: 40 }, zoom: 1 },
  }
  let preview = { live: '', ig: '', fb: '', webb: '' }   // renderad data-URI per kanal
  let renderar = { live: false, ig: false, fb: false, webb: false }

  function toggleCh(k) { ch[k].on = !ch[k].on; ch = ch; if (ch[k].on) scheduleRender(k) }
  function sattFmt(k, f) { ch[k].fmt = f; ch = ch; scheduleRender(k) }
  function sattZoom(k, v) { ch[k].zoom = parseFloat(v) || 1; ch = ch; scheduleRender(k) }
  function sattFokus(k, e) {
    const r = e.currentTarget.getBoundingClientRect()
    const x = Math.max(0, Math.min(100, Math.round(((e.clientX - r.left) / r.width) * 100)))
    const y = Math.max(0, Math.min(100, Math.round(((e.clientY - r.top) / r.height) * 100)))
    ch[k].fokus = { x, y }; ch = ch; scheduleRender(k)
  }

  const _rtimers = {}
  function scheduleRender(k) {
    if (_rtimers[k]) clearTimeout(_rtimers[k])
    _rtimers[k] = setTimeout(() => renderChannel(k), 480)
  }
  function scheduleAll() { KANALER.forEach((k) => ch[k.key].on && scheduleRender(k.key)) }
  async function renderChannel(k) {
    const c = ch[k]
    if (!c.on) { preview[k] = ''; preview = preview; return }
    const foto = coverPath
    if (!foto || !match) { preview[k] = ''; preview = preview; return }
    renderar[k] = true; renderar = renderar
    const r = await forhandsgranskaStory({
      foto, moment: 'resultat', match_id: match.id, tema, format: c.fmt,
      fokus: c.fokus, zoom: c.zoom, preview_slot: k,
      stallning: match.resultat || '', mellan: match.mellan || '', mal_rad: match.malskyttar || '',
    })
    renderar[k] = false; renderar = renderar
    if (r?.ok && r.path) {
      const t = await thumbForBild(r.path)   // fil → data-URI (file:// blockeras i WKWebView)
      preview[k] = t?.ok ? t.data_uri : ''
      preview = preview
    }
  }
  // Ny resultatremsa-sparning speglas i previews: läs om matchen + rita om.
  async function uppdateraPreviews() {
    if (match?.id) match = await hamtaMatch(match.id)
    scheduleAll()
  }

  // ── Publiceringsrad (fan-out) ───────────────────────────────────────────────
  $: aktiva = KANALER.filter((k) => ch[k.key].on)
  let pubKor = false
  let pubResultat = []             // [{kanal, ok, text}]
  let pubFlash = false

  async function spara() {
    if (!match) return
    await sparaMaterial({ kind: 'some', status: 'utkast', match_id: match.id,
      match_namn: `${match.lag_hemma} – ${match.lag_borta}`, caption,
      channels: JSON.stringify(Object.fromEntries(KANALER.map((k) => [k.key, ch[k.key]]))),
      foto: coverPath })
    materials = await listaMaterial()
    pubFlash = true; setTimeout(() => (pubFlash = false), 1800)
  }

  async function publicera() {
    if (!match || !aktiva.length) return
    pubKor = true; pubResultat = []
    const test = $testMode
    const test_mapp = test ? (await nyTestPaketMapp())?.path : undefined
    const ut = []
    for (const k of aktiva) {
      try {
        if (k.key === 'live') {
          const r = await publiceraLiveStory({ foto: coverPath, moment: 'resultat', tema,
            match_id: match.id, fokus: ch.live.fokus, zoom: ch.live.zoom,
            stallning: match.resultat || '', mellan: match.mellan || '', mal_rad: match.malskyttar || '', test })
          ut.push({ kanal: k.namn, ok: !!r?.ok && (r.publicerad !== false), text: r?.fel || (r?.test ? 'Testfil' : 'Story ute') })
        } else if (k.key === 'ig' || k.key === 'fb') {
          const mal = k.key === 'ig' ? { ig_inlagg: true } : { fb: true }
          const r = await publiceraTillSoMe({ bilder: selectedPaths, caption: losText(caption),
            mal, match_id: match.id, moment: 'resultat', tema, test, test_mapp })
          ut.push({ kanal: k.namn, ok: !!r?.ok, text: r?.fel || `${r?.sparade ?? (r?.resultat?.length || 0)} post(er)` })
        } else if (k.key === 'webb') {
          const r = await publiceraInnehallNatet({
            typ: 'match', match_id: match.id, titel: `${match.lag_hemma} – ${match.lag_borta}`,
            hem: match.lag_hemma, borta: match.lag_borta, serie: match.liga, sport: match.sport,
            datum: match.datum, resultat: match.resultat, mellan: match.mellan, arena: match.arena,
            malskyttar: match.malskyttar, pixieset: galleriUrl, body: losText(caption, { web: true }),
            figurer: selectedPaths.map((p) => ({ bild: p, alt: '', bildtext: '', src: '' })),
            hero: (coverPath.split('/').pop() || ''), heroKalla: coverPath,
            heroPosition: `${ch.webb.fokus.x}% ${ch.webb.fokus.y}%` }, test)
          ut.push({ kanal: k.namn, ok: !!r?.ok, text: r?.fel || (test ? 'Testfil' : 'Publicerad') })
        }
      } catch (e) { ut.push({ kanal: k.namn, ok: false, text: 'Fel: ' + (e?.message || e) }) }
    }
    pubResultat = ut
    pubKor = false
    materials = await listaMaterial()
    dispatch('materialAndrat')
  }

  // ── På gång (webb) — härledd ur matchlistan ─────────────────────────────────
  let pagang = []
  let pagangVisa = true
  let pagangKor = false
  let pagangFlash = ''
  async function laddaPagang() {
    const r = await pagangMatcher()
    if (r?.ok) { pagang = r.matcher || []; pagangVisa = r.visa }
  }
  async function togglePagangVisa() { pagangVisa = !pagangVisa; await sattPagangVisa(pagangVisa) }
  async function uppdateraSajten() {
    pagangKor = true; pagangFlash = ''
    const r = await publiceraPagangMatcher($testMode)
    pagangKor = false
    pagangFlash = r?.ok ? ($testMode ? '✓ Testfiler skrivna' : `✓ Uppdaterad · ${r.antal} matcher`) : (r?.fel || 'Kunde inte uppdatera')
    setTimeout(() => (pagangFlash = ''), 2600)
  }

  // ── Live nu (snabbflöde) ────────────────────────────────────────────────────
  let liveOpen = false
  let liveMoment = 'result'
  let livePhoto = ''
  let livePreview = ''
  let liveTest = false
  let liveFas = 'compose'          // compose | publishing | done
  let liveResultat = null
  $: liveMoms = (() => {
    const l = [{ k: 'start', label: profil.start_moment || 'Avspark' }, { k: 'mid', label: profil.mid_label || 'Halvtid' }]
    if (profil.has_scorers) l.push({ k: 'scorer', label: 'Målgörare' })
    l.push({ k: 'result', label: profil.res_label || 'Resultat' })
    return l
  })()
  const LIVEMOM = { start: 'avspark', mid: 'halvtid', scorer: 'malgorare', result: 'resultat' }
  function liveOppna() { liveOpen = true; liveFas = 'compose'; if (!livePhoto && coverPath) livePhoto = coverPath; liveRendera() }
  function liveStang() { liveOpen = false }
  function liveSattMoment(k) { liveMoment = k; liveRendera() }
  function liveSattFoto(p) { livePhoto = p; liveRendera() }
  let _lpt
  function liveRendera() {
    if (_lpt) clearTimeout(_lpt)
    _lpt = setTimeout(async () => {
      if (!livePhoto || !match) return
      const r = await forhandsgranskaStory({ foto: livePhoto, moment: LIVEMOM[liveMoment] || 'resultat',
        match_id: match.id, tema, format: '9x16', preview_slot: 'livenu',
        stallning: match.resultat || '', mellan: match.mellan || '', mal_rad: match.malskyttar || '' })
      if (r?.ok && r.path) { const t = await thumbForBild(r.path); livePreview = t?.ok ? t.data_uri : '' }
    }, 400)
  }
  async function livePublicera() {
    liveFas = 'publishing'
    const r = await publiceraLiveStory({ foto: livePhoto, moment: LIVEMOM[liveMoment] || 'resultat',
      tema, match_id: match?.id, test: liveTest })
    liveResultat = r
    liveFas = 'done'
    materials = await listaMaterial(); dispatch('materialAndrat')
  }
  function liveReset() { liveFas = 'compose'; liveResultat = null }

  // ── Hämta bilder (ingest) ───────────────────────────────────────────────────
  let ingestOpen = false
  let ingKort = []
  let ingValt = ''
  let ingProt = ''
  let ingSteg = 0                  // 0 kort valt, 1 exporterat
  let ingKor = false
  async function ingestOppna() { ingestOpen = true; ingSteg = 0; const r = await listaMinneskort(); ingKort = r?.kort || []; if (ingKort[0]) ingValt = ingKort[0].path }
  function ingestStang() { ingestOpen = false }
  $: ingSkyddade = ingKort.find((k) => k.path === ingValt)?.skyddade ?? 0
  async function ingValjExport() { const r = await valjMapp('Exportera skyddade bilder till…'); if (r?.ok) ingProt = r.path }
  async function ingExportera() {
    if (!ingValt || !ingProt) return
    ingKor = true
    const r = await exporteraSkyddade(ingValt, ingProt, true)
    ingKor = false
    if (r?.ok) ingSteg = 1
  }
  async function ingValjKatalog() {
    const r = await valjMapp('Välj katalog med de färdigredigerade bilderna')
    if (r?.ok && r.path) { folderPath = r.path; await lasKatalog(); ingestOpen = false }
  }
</script>

<div class="panel">
  <!-- Huvud -->
  <div class="topp">
    <div>
      <div class="kicker">Skapa en gång · publicera överallt</div>
      <h1 class="scd">Matchpublicering</h1>
    </div>
    <button class="livenu" on:click={liveOppna}><span class="ldot"></span>Live nu — story direkt</button>
  </div>

  <!-- Matchväljare -->
  <div class="matchrad">
    <span class="mlbl">Match</span>
    <div class="mdd">
      <button class="mddbtn" on:click={() => (matchOpen = !matchOpen)}>
        <span class="mddnamn">{match ? `${match.lag_hemma} – ${match.lag_borta}` : 'Ingen match'}</span>
        <span class="mddmeta">{matchMeta}</span><span class="mddpil">▾</span>
      </button>
      {#if matchOpen}
        <button class="mddskArm" on:click={() => (matchOpen = false)} aria-label="stäng"></button>
        <div class="mddlista">
          <div class="mddcaps">Välj match</div>
          {#each matcher as m (m.id)}
            <button class="mddrad" class:pa={m.id === match?.id} on:click={() => valjMatch(m.id)}>
              <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
              <div class="mddi"><div class="mddf">{m.lag_hemma} – {m.lag_borta}</div>
                <div class="mdds">{[datumTxt(m.datum), m.sport].filter(Boolean).join(' · ')}</div></div>
              {#if m.resultat}<span class="mddres scd">{m.resultat}</span>{:else}<span class="mddkom">Kommande</span>{/if}
            </button>
          {/each}
        </div>
      {/if}
    </div>
    <span class="mhint">— resultatmodellen följer matchens sport</span>
  </div>

  <!-- Delad resultatremsa -->
  {#if match}
    <ResultatRemsa {match} {profil} {lagAlla} />
    <div class="remstext">Resultat &amp; målgörare fylls i <b>en gång här</b> — samma värden matas in i story, inlägg och webbartikel.
      <button class="minilank" on:click={uppdateraPreviews}>↻ Uppdatera förhandsvisningar</button></div>
  {/if}

  <!-- Steg 1: Innehåll -->
  <div class="steg"><span class="stegnr scd">1</span><span class="stegnamn">Innehåll</span>
    <span class="steghint">— skapas en gång, återanvänds i alla utgångar</span></div>
  <div class="grid2 s1">
    <!-- Bilder -->
    <div class="kort">
      <div class="korthuvud"><span class="caps">Bilder</span><span class="valda">{selCount} valda</span></div>
      <div class="katrad">
        <span class="klbl">Katalog</span>
        <input class="mono" bind:value={folderPath} on:change={lasKatalog} placeholder="Lightroom-exportens mapp" />
        <button class="sek" on:click={valjKatalog}>Välj katalog…</button>
      </div>
      {#if laddarBilder}<div class="hint">Läser katalogen…</div>{/if}
      {#if photos.length}
        <div class="bildrutnat">
          {#each photos as p, i}
            <button class="bild" class:sel={p.sel} class:tom={!thumbs[p.path]} style={thumbs[p.path] ? `background-image:url(${thumbs[p.path]})` : ''} on:click={() => klickaBild(i)}>
              {#if p.sel}<span class="bock">✓</span>{/if}
              {#if p.cover}<span class="omslag">OMSLAG</span>{/if}
            </button>
          {/each}
        </div>
        <div class="hint">Klicka för att lägga till/ta bort · klicka den valda igen för omslag. Varje utgång beskär till sitt format.</div>
      {:else}
        <div class="tombild">Peka ut Lightroom-exportens katalog för att välja bilder — eller använd <button class="minilank" on:click={ingestOppna}>Hämta bilder</button>.</div>
      {/if}
    </div>
    <!-- Text -->
    <div class="kort">
      <div class="korthuvud"><span class="caps">Text</span></div>
      <textarea class="cap" rows="4" bind:this={capEl} bind:value={caption}></textarea>
      <div class="tokrad"><span class="tlbl">Infoga:</span>
        {#each TOKENS as t}<button class="tok" on:click={() => insertToken(t)}>{t}</button>{/each}</div>
      <div class="hint">Sociala kanaler får @ och #. <b>Webben får samma text utan @/#</b> (rena namn, inga hashtags).</div>
    </div>
  </div>

  <!-- Länkar -->
  <div class="kort lankkort">
    <div class="korthuvud"><span class="caps">Länkar</span><span class="hint2">Fylls i en gång · bifogas per kanal</span></div>
    <div class="grid2">
      <div class="f"><label>Galleri <span class="lmut">— fler bilder / köp</span></label>
        <input class="mono" bind:value={galleriUrl} placeholder="foto.dalecarliaphoto.se/…" /></div>
      <div class="f"><label>Hemsida <span class="lmut">— matchreferat</span></label>
        <input class="mono" bind:value={hemsidaUrl} placeholder="dalecarliaphoto.se/matcher/…" /></div>
    </div>
    <div class="placering">
      <span class="pcaps">Så placeras de:</span>
      <span class="pchip">Live-story · länk-sticker</span>
      <span class="pchip">IG · bio + första kommentar</span>
      <span class="pchip">Facebook · i inlägget</span>
      <span class="pchip">Webb · galleri i texten (ingen hemsida-länk)</span>
    </div>
  </div>

  <!-- Steg 2: Skicka till -->
  <div class="steg"><span class="stegnr scd">2</span><span class="stegnamn">Skicka till</span>
    <span class="steghint">— klicka i varje förhandsvisning för fokus, dra reglaget för zoom · gren-kant + glow följer varje utgång</span></div>
  <div class="kanaler">
    {#each KANALER as k}
      <div class="kanal" class:av={!ch[k.key].on} class:wide={k.wide}>
        <div class="kanalhuvud" on:click={() => toggleCh(k.key)}>
          <span class="chk" class:pa={ch[k.key].on}>{ch[k.key].on ? '✓' : ''}</span>
          <div class="kmeta"><div class="knamn">{k.namn}</div><div class="kunder">{k.under}</div></div>
        </div>
        <div class="kanalkropp">
          {#if k.format.length > 1}
            <div class="fmtchips">
              {#each k.format as f}<button class="fmtchip" class:on={ch[k.key].fmt === f} on:click={() => sattFmt(k.key, f)}>{fmtEti(f)}</button>{/each}
            </div>
          {/if}
          <div class="prevbox" class:wide={k.wide} style="aspect-ratio:{fmtRatio(ch[k.key].fmt)};border-color:{grenFarg(match?.hem_gren)};box-shadow:0 0 12px {grenFarg(match?.hem_gren)}55"
            on:click={(e) => sattFokus(k.key, e)}>
            {#if preview[k.key]}
              <img class="previmg" src={preview[k.key]} alt="" />
            {:else}
              <div class="prevtom">{ch[k.key].on ? (coverPath ? 'Renderar…' : 'Välj omslag i Steg 1') : 'Avstängd'}</div>
            {/if}
            <span class="fokusdot" style="left:{ch[k.key].fokus.x}%;top:{ch[k.key].fokus.y}%"></span>
            {#if renderar[k.key]}<span class="renderbadge">Renderar…</span>{/if}
          </div>
          <div class="zoomrad">
            <input type="range" min="1" max="2.6" step="0.05" value={ch[k.key].zoom} on:input={(e) => sattZoom(k.key, e.target.value)} />
            <span class="zoomtxt">{Math.round(ch[k.key].zoom * 100)}%</span>
          </div>
        </div>
      </div>
    {/each}
  </div>

  <!-- På gång (webb) -->
  <div class="steg"><span class="stegnr scd">W</span><span class="stegnamn">På gång <span class="wmut">(webb)</span></span>
    <span class="steghint">— kommande matcher som schema-modul på sajten</span></div>
  <div class="kort">
    <div class="korthuvud">
      <span class="caps">Kommande matcher · {pagang.length} st</span>
      <button class="visatoggle" on:click={togglePagangVisa}>
        <span class="chk sm" class:pa={pagangVisa}>{pagangVisa ? '✓' : ''}</span>Visa på sajten</button>
    </div>
    <div class="pglista">
      {#each pagang.slice(0, 6) as m (m.id)}
        <div class="pgrad">
          <div class="pgdatum"><div class="pgdag scd">{(m.datum || '').split('-')[2] || '–'}</div>
            <div class="pgmon">{MK[(Number((m.datum || '').split('-')[1]) || 1) - 1]?.toUpperCase()}</div></div>
          <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
          <div class="pgi"><div class="pgf">{m.lag_hemma} – {m.lag_borta}</div><div class="pgl">{m.liga || ''}</div></div>
        </div>
      {/each}
      {#if !pagang.length}<div class="hint">Inga kommande matcher i Matcher.</div>{/if}
    </div>
    <div class="pgfot">
      <span class="hint">Synkas automatiskt från Matcher — publiceras som "På gång"-widget på sajten.</span>
      {#if pagangFlash}<span class="ok">{pagangFlash}</span>{/if}
      <button class="sek" on:click={uppdateraSajten} disabled={pagangKor}>{pagangKor ? 'Uppdaterar…' : 'Uppdatera sajten'}</button>
    </div>
  </div>
</div>

<!-- Publiceringsrad -->
<div class="pubrad">
  <div class="pubinfo">
    <div class="pubtitel">Skickas till <b>{aktiva.length} {aktiva.length === 1 ? 'kanal' : 'kanaler'}</b></div>
    <div class="publista">{aktiva.length ? aktiva.map((k) => k.namn).join(' · ') : 'Inga kanaler valda'}</div>
    {#if pubResultat.length}
      <div class="pubres">{#each pubResultat as r}<span class="prc" class:ok={r.ok} class:fel={!r.ok}>{r.ok ? '✓' : '⚠'} {r.kanal}: {r.text}</span>{/each}</div>
    {/if}
  </div>
  {#if pubFlash}<span class="ok">✓ Utkast sparat</span>{/if}
  <button class="sek" on:click={spara} disabled={!match}>Spara utkast</button>
  <button class="prim" on:click={publicera} disabled={!match || !aktiva.length || pubKor}>{pubKor ? 'Publicerar…' : `Publicera ${aktiva.length}`}</button>
</div>

<!-- Live nu — slide-over -->
{#if liveOpen}
  <div class="slide">
    <button class="slidebak" on:click={liveStang} aria-label="stäng"></button>
    <div class="slidepanel">
      <div class="slidehuvud"><span class="ldot"></span>
        <div class="slidetitel"><div class="scd st">Live nu</div><div class="ss">{match ? `${match.lag_hemma} – ${match.lag_borta}` : ''} · story direkt</div></div>
        <button class="stang" on:click={liveStang}>✕</button></div>

      {#if liveFas === 'compose'}
        <div class="slidekropp">
          <div class="scaps">1 · Moment</div>
          <div class="momrad">{#each liveMoms as m}<button class="mom" class:on={liveMoment === m.k} on:click={() => liveSattMoment(m.k)}>{m.label}</button>{/each}</div>
          <div class="scaps mt">2 · Bild <button class="minilank hb" on:click={ingestOppna}>Hämta / uppdatera ›</button></div>
          <div class="livebilder">
            {#each photos.filter((p) => p.sel).slice(0, 8) as p, i}
              <button class="livebild" class:on={livePhoto === p.path} class:tom={!thumbs[p.path]} style={thumbs[p.path] ? `background-image:url(${thumbs[p.path]})` : ''} on:click={() => liveSattFoto(p.path)}>
                {#if i === 0}<span class="senast">SENAST</span>{/if}</button>
            {/each}
            {#if !photos.some((p) => p.sel)}<div class="hint">Välj bilder i Steg 1 eller Hämta bilder.</div>{/if}
          </div>
          <div class="scaps mt">3 · Förhandsvisning</div>
          <div class="liveprevwrap">
            <div class="liveprev" style="border-color:{grenFarg(match?.hem_gren)};box-shadow:0 0 20px {grenFarg(match?.hem_gren)}66">
              {#if livePreview}<img src={livePreview} alt="" />{:else}<div class="prevtom">Renderar…</div>{/if}
            </div>
          </div>
          <div class="hint c">Riktig 9:16 renderas server-side. Gren-kant + glow följer dam/herr/mixed.</div>
        </div>
        <div class="slidefot">
          <button class="testtoggle" on:click={() => (liveTest = !liveTest)}><span class="chk sm" class:pa={liveTest}>{liveTest ? '✓' : ''}</span>Testläge — inget publiceras</button>
          <button class="prim bred" on:click={livePublicera} disabled={!livePhoto}>{liveTest ? 'Skapa testfil' : 'Publicera story'}</button>
          <div class="hint c">Renderas server-side → IG Story → sparas i Dropbox &amp; som material</div>
        </div>
      {:else if liveFas === 'publishing'}
        <div class="slidemitt"><div class="scd pubbig">Publicerar…</div></div>
      {:else}
        <div class="slidemitt">
          <div class="klarcirkel">✓</div>
          <div class="scd pubbig">{liveResultat?.test ? 'Testfil skapad' : (liveResultat?.publicerad ? 'Ute på Instagram' : 'Renderad')}</div>
          {#if liveResultat?.fel}<div class="synkfel">{liveResultat.fel}</div>{/if}
          {#if liveResultat?.path}<div class="livepath mono">{liveResultat.path}</div>{/if}
          <div class="klarknappar"><button class="sek" on:click={liveReset}>Ny story</button><button class="prim" on:click={liveStang}>Klar</button></div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<!-- Hämta bilder — slide-over -->
{#if ingestOpen}
  <div class="slide">
    <button class="slidebak" on:click={ingestStang} aria-label="stäng"></button>
    <div class="slidepanel">
      <div class="slidehuvud">
        <div class="slidetitel"><div class="scd st">Hämta bilder</div><div class="ss">Minneskort → Lightroom → katalog</div></div>
        <button class="stang" on:click={ingestStang}>✕</button></div>
      <div class="slidekropp">
        <div class="ingsteg">
          <span class="ingnr" class:klar={ingSteg >= 1}>{ingSteg >= 1 ? '✓' : '1'}</span>
          <div class="ingi"><div class="ingt">Minneskort</div>
            <div class="hint">Bara <b>skyddade</b> (låsta på kameran) bilder tas med.</div>
            <select class="ingsel" bind:value={ingValt}>
              {#each ingKort as k}<option value={k.path}>{k.namn} — {k.path}</option>{/each}
              {#if !ingKort.length}<option value="">Inga kort hittades</option>{/if}
            </select>
            {#if ingValt}<div class="ok sm">{ingSkyddade} skyddade bilder hittades</div>{/if}
          </div>
        </div>
        <div class="ingsteg">
          <span class="ingnr" class:klar={ingSteg >= 1}>{ingSteg >= 1 ? '✓' : '2'}</span>
          <div class="ingi"><div class="ingt">Exportera skyddade &amp; öppna Lightroom</div>
            <div class="ingrad"><input class="mono" bind:value={ingProt} placeholder="Exportera till…" /><button class="sek" on:click={ingValjExport}>Välj…</button></div>
            <button class="prim sm" on:click={ingExportera} disabled={!ingValt || !ingProt || ingKor}>{ingKor ? 'Exporterar…' : (ingSteg >= 1 ? '✓ Exporterat · öppnat i Lightroom' : 'Exportera skyddade + öppna i Lightroom →')}</button>
          </div>
        </div>
        <div class="ingsteg">
          <span class="ingnr" class:klar={photos.length > 0}>{photos.length ? '✓' : '3'}</span>
          <div class="ingi"><div class="ingt">Katalog med redigerade bilder</div>
            <div class="hint">Peka ut mappen där Lightroom exporterat de färdigredigerade bilderna — de blir matchens urval.</div>
            <button class="prim sm" on:click={ingValjKatalog}>Välj katalog + läs in →</button>
          </div>
        </div>
      </div>
      <div class="slidefot"><button class="prim bred" on:click={ingestStang}>Klar</button></div>
    </div>
  </div>
{/if}

<style>
  .panel { padding: 22px 28px 20px; max-width: 1060px; }
  .topp { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
  .kicker { font-size: 10.5px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--acc); margin-bottom: 6px; }
  h1 { margin: 0; font-size: 27px; font-weight: 700; color: var(--t-head); }
  .livenu { display: inline-flex; align-items: center; gap: 8px; background: var(--acc-soft); border: 1px solid var(--acc-border);
    color: var(--t-head); border-radius: 10px; padding: 9px 14px; font-size: 12.5px; font-weight: 600; }
  .ldot { width: 7px; height: 7px; border-radius: 50%; background: #E0607F; box-shadow: 0 0 8px #E0607F; flex: none; }

  .matchrad { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
  .mlbl { font-size: 10.5px; color: var(--t-mut); }
  .mdd { position: relative; }
  .mddbtn { display: flex; align-items: center; gap: 10px; background: var(--kort); border: 1px solid var(--div); border-radius: 9px; padding: 8px 13px; }
  .mddnamn { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .mddmeta { font-size: 11px; color: var(--t-mut); }
  .mddpil { font-size: 10px; color: var(--t-mut); }
  .mddskArm { position: fixed; inset: 0; z-index: 30; background: transparent; border: 0; }
  .mddlista { position: absolute; top: calc(100% + 6px); left: 0; z-index: 31; width: 380px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 12px; box-shadow: var(--skugga); padding: 6px; max-height: 360px; overflow-y: auto; }
  .mddcaps { font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); padding: 8px 11px 6px; }
  .mddrad { display: flex; align-items: center; gap: 11px; width: 100%; text-align: left; padding: 9px 11px; border: 0; background: transparent; border-radius: 8px; }
  .mddrad:hover, .mddrad.pa { background: var(--acc-soft); }
  .mddi { flex: 1; min-width: 0; }
  .mddf { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .mdds { font-size: 10.5px; color: var(--t-mut); }
  .mddres { font-size: 15px; font-weight: 700; color: var(--t-head); font-family: var(--font-c); }
  .mddkom { font-size: 10px; color: var(--t-mut); border: 1px solid var(--div); border-radius: 999px; padding: 2px 8px; }
  .grendot { width: 9px; height: 9px; border-radius: 2px; flex: none; }
  .mhint { font-size: 10.5px; color: var(--t-help); }

  .remstext { font-size: 11px; color: var(--t-mut); margin: -8px 0 22px 2px; }
  .minilank { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: inherit; padding: 0; cursor: pointer; }

  .steg { display: flex; align-items: center; gap: 10px; margin: 26px 0 12px; flex-wrap: wrap; }
  .stegnr { width: 24px; height: 24px; border-radius: 7px; background: var(--div3); color: var(--acc);
    display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex: none; }
  .stegnamn { font-size: 16px; font-weight: 600; color: var(--t-head); }
  .wmut { color: var(--t-mut); font-weight: 500; }
  .steghint { font-size: 12px; color: var(--t-mut); }

  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .grid2.s1 { margin-bottom: 8px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: 13px; box-shadow: var(--skugga); padding: 16px 18px; margin-bottom: 14px; }
  .korthuvud { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 10px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-caps); }
  .valda { font-size: 11.5px; color: var(--acc); font-weight: 600; }
  .hint2 { font-size: 11px; color: var(--t-mut); }
  .katrad { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; flex-wrap: wrap; }
  .klbl { font-size: 10.5px; color: var(--t-mut); }
  .katrad input { flex: 1; min-width: 180px; }
  input, select, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 11px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, select:focus, textarea:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 11.5px; }
  .sek { flex: none; background: var(--panel); border: 1px solid var(--div); border-radius: 8px; padding: 8px 13px; font-size: 11.5px; font-weight: 600; color: var(--t-head); }
  .sek:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .sek:disabled { opacity: 0.5; }
  .bildrutnat { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
  .bild { position: relative; aspect-ratio: 4/5; border-radius: 6px; border: 1px solid var(--div); background-size: cover; background-position: center; opacity: 0.5; padding: 0; }
  .bild.sel { outline: 2px solid var(--acc); opacity: 1; }
  .bild.tom, .livebild.tom { background-image: repeating-linear-gradient(135deg, var(--div3), var(--div3) 7px, var(--kort) 7px, var(--kort) 14px); }
  .bock { position: absolute; top: 3px; right: 3px; width: 15px; height: 15px; border-radius: 50%; background: var(--acc); color: #100c05; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; }
  .omslag { position: absolute; bottom: 3px; left: 3px; font-size: 7px; font-weight: 700; background: var(--acc); color: #100c05; border-radius: 3px; padding: 1px 4px; letter-spacing: 0.03em; }
  .tombild { font-size: 12px; color: var(--t-mut); line-height: 1.5; padding: 8px 0; }
  .cap { line-height: 1.5; resize: vertical; }
  .tokrad { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 11px; align-items: center; }
  .tlbl { font-size: 10.5px; color: var(--t-mut); margin-right: 2px; }
  .tok { font-size: 10.5px; background: var(--acc-soft); border: 1px dashed var(--acc-border); color: var(--acc); border-radius: 6px; padding: 3px 8px; }
  .hint { font-size: 10.5px; color: var(--t-help); margin-top: 10px; line-height: 1.45; }
  .hint.c { text-align: center; }

  .lankkort .grid2 { margin-bottom: 14px; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  label { font-size: 11px; color: var(--t-mut); }
  .lmut { color: var(--t-help); }
  .placering { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; padding-top: 13px; border-top: 1px solid var(--div3); }
  .pcaps { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-caps); }
  .pchip { font-size: 10.5px; color: var(--t-mut); background: var(--div3); border-radius: 999px; padding: 4px 10px; }

  .kanaler { display: flex; gap: 16px; flex-wrap: wrap; }
  .kanal { flex: 1 1 210px; min-width: 200px; background: var(--kort); border: 1px solid var(--div); border-radius: 13px; padding: 15px 16px; transition: opacity 0.15s; }
  .kanal.wide { flex-basis: 100%; }
  .kanal.av { opacity: 0.5; }
  .kanalhuvud { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; cursor: pointer; }
  .chk { width: 20px; height: 20px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex: none;
    font-size: 12px; font-weight: 700; border: 1.6px solid var(--div); color: transparent; }
  .chk.pa { background: var(--acc); color: #100c05; border-color: var(--acc); }
  .chk.sm { width: 17px; height: 17px; border-radius: 5px; font-size: 11px; }
  .kmeta { flex: 1; }
  .knamn { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .kunder { font-size: 10px; color: var(--t-mut); }
  .kanalkropp { display: flex; flex-direction: column; align-items: center; gap: 8px; }
  .fmtchips { display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; }
  .fmtchip { padding: 3px 8px; border-radius: 6px; border: 0; font-size: 10px; font-weight: 600; background: var(--panel); color: var(--t-mut); }
  .fmtchip.on { background: var(--acc); color: #100c05; font-weight: 700; }
  .prevbox { position: relative; width: 118px; border-radius: 8px; overflow: hidden; background: var(--div3); border: 2px solid var(--div); cursor: crosshair; }
  .prevbox.wide { width: 100%; }
  .previmg { display: block; width: 100%; height: 100%; object-fit: cover; }
  .prevtom { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; min-height: 90px; font-size: 10px; color: var(--t-mut); text-align: center; padding: 8px; }
  .fokusdot { position: absolute; width: 15px; height: 15px; margin: -7.5px 0 0 -7.5px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 0 2px rgba(0,0,0,.45); pointer-events: none; }
  .renderbadge { position: absolute; top: 6px; right: 6px; font-size: 8px; font-weight: 700; background: rgba(0,0,0,.6); color: #fff; padding: 2px 6px; border-radius: 5px; }
  .zoomrad { display: flex; align-items: center; gap: 8px; width: 100%; justify-content: center; }
  .zoomrad input { width: 60%; accent-color: var(--acc); }
  .zoomtxt { font-size: 10px; color: var(--t-mut); }

  .visatoggle { display: flex; align-items: center; gap: 8px; background: none; border: 0; font-size: 11.5px; color: var(--t-mut); font-weight: 600; }
  .pglista { display: flex; flex-direction: column; }
  .pgrad { display: flex; align-items: center; gap: 13px; padding: 10px 4px; border-top: 1px solid var(--div3); }
  .pgdatum { text-align: center; width: 38px; flex: none; }
  .pgdag { font-size: 19px; font-weight: 700; color: var(--t-head); line-height: 1; font-family: var(--font-c); }
  .pgmon { font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: var(--t-mut); }
  .pgi { flex: 1; min-width: 0; }
  .pgf { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .pgl { font-size: 10.5px; color: var(--t-mut); }
  .pgfot { display: flex; align-items: center; gap: 12px; margin-top: 13px; padding-top: 13px; border-top: 1px solid var(--div3); flex-wrap: wrap; }
  .pgfot .hint { flex: 1; margin-top: 0; min-width: 200px; }
  .ok { font-size: 11.5px; color: var(--ok); font-weight: 600; }
  .ok.sm { margin-top: 6px; }

  .pubrad { position: sticky; bottom: 0; z-index: 6; display: flex; align-items: center; gap: 14px;
    border-top: 1px solid var(--div); background: var(--panel); padding: 13px 28px; }
  .pubinfo { flex: 1; min-width: 0; }
  .pubtitel { font-size: 12.5px; color: var(--t-head); }
  .publista { font-size: 11px; color: var(--t-mut); margin-top: 1px; }
  .pubres { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; }
  .prc { font-size: 11px; font-weight: 600; }
  .prc.ok { color: var(--ok); }
  .prc.fel { color: #C0453E; }
  .prim { background: var(--acc); color: #100c05; border: 0; border-radius: 9px; padding: 10px 18px; font-size: 13px; font-weight: 700; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .prim.sm { padding: 8px 13px; font-size: 12px; }
  .prim.bred { width: 100%; }

  /* Slide-overs */
  .slide { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; }
  .slidebak { position: absolute; inset: 0; background: rgba(0,0,0,.5); border: 0; }
  .slidepanel { position: relative; width: 440px; max-width: 92vw; height: 100%; background: var(--panel); border-left: 1px solid var(--div);
    box-shadow: -24px 0 60px rgba(0,0,0,.4); display: flex; flex-direction: column; }
  .slidehuvud { flex: none; padding: 18px 22px; border-bottom: 1px solid var(--div); display: flex; align-items: center; gap: 11px; }
  .slidetitel { flex: 1; }
  .st { font-size: 18px; font-weight: 700; color: var(--t-head); }
  .ss { font-size: 11px; color: var(--t-mut); margin-top: 1px; }
  .stang { width: 30px; height: 30px; border-radius: 8px; background: var(--kort); border: 1px solid var(--div); color: var(--t-mut); font-size: 14px; flex: none; }
  .slidekropp { flex: 1; overflow-y: auto; padding: 20px 22px; }
  .slidefot { flex: none; padding: 14px 22px; border-top: 1px solid var(--div); display: flex; flex-direction: column; gap: 10px; }
  .slidemitt { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 30px; text-align: center; }
  .scaps { font-size: 10.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
  .scaps.mt { margin-top: 20px; }
  .hb { font-size: 10.5px; }
  .momrad { display: flex; gap: 7px; }
  .mom { flex: 1; text-align: center; padding: 9px 6px; border-radius: 9px; font-size: 12px; font-weight: 600; background: var(--kort); border: 1px solid var(--div); color: var(--t-mut); }
  .mom.on { background: var(--acc); color: #100c05; border-color: var(--acc); font-weight: 700; }
  .livebilder { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px; }
  .livebild { position: relative; width: 58px; height: 82px; flex: none; border-radius: 7px; border: 1px solid var(--div); background-size: cover; background-position: center; opacity: 0.6; padding: 0; }
  .livebild.on { outline: 2px solid var(--acc); opacity: 1; }
  .senast { position: absolute; bottom: 3px; left: 50%; transform: translateX(-50%); font-size: 6.5px; font-weight: 700; background: rgba(0,0,0,.62); color: #fff; border-radius: 3px; padding: 1px 4px; white-space: nowrap; }
  .liveprevwrap { display: flex; justify-content: center; }
  .liveprev { width: 170px; aspect-ratio: 9/16; border-radius: 12px; border: 3px solid var(--div); overflow: hidden; background: var(--div3); }
  .liveprev img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .testtoggle { display: flex; align-items: center; gap: 9px; background: none; border: 0; font-size: 12px; color: var(--t-mut); font-weight: 600; }
  .pubbig { font-size: 20px; font-weight: 700; color: var(--t-head); }
  .klarcirkel { width: 56px; height: 56px; border-radius: 50%; background: rgba(47,158,110,.15); border: 1.5px solid var(--ok); color: var(--ok); display: flex; align-items: center; justify-content: center; font-size: 25px; }
  .livepath { font-size: 10.5px; color: var(--t-mut); font-family: var(--mono, monospace); word-break: break-all; }
  .synkfel { font-size: 12px; color: #C0453E; font-weight: 600; }
  .klarknappar { display: flex; gap: 10px; }

  .ingsteg { display: flex; gap: 13px; margin-bottom: 20px; }
  .ingnr { width: 25px; height: 25px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center; font-family: var(--font-c); font-weight: 700; font-size: 13px; background: var(--div3); color: var(--t-mut); }
  .ingnr.klar { background: var(--ok); color: #fff; }
  .ingi { flex: 1; min-width: 0; }
  .ingt { font-size: 13.5px; font-weight: 600; color: var(--t-head); margin-bottom: 4px; }
  .ingsel { margin-top: 8px; }
  .ingrad { display: flex; gap: 8px; margin: 8px 0 10px; }
  .ingrad input { flex: 1; min-width: 0; }
</style>
