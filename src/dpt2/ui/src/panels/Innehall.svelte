<script>
  import { onMount } from 'svelte'
  import { forhandsgranskaInnehall, exporteraInnehall, publiceraInnehallNatet, statusInnehall, listaMatcher, genereraBildsvep, valjMapp, urvalHojdpunkter, slugga } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import BildvaljareFokuspunkt from '../lib/BildvaljareFokuspunkt.svelte'

  // Fyra färgkodade typer (DATAMODELL.md). Porträtt är en Event-kategori,
  // inte en egen typ. match = "Sport" utåt; sajtens collection heter matcher.
  const CTYPER = [
    { id: 'blogg', namn: 'Blog', farg: '#7A8794', sub: 'journal & resor', mapp: 'blogg' },
    { id: 'match', namn: 'Sport', farg: '#2F7CB0', sub: 'från match', mapp: 'matcher' },
    { id: 'landskap', namn: 'Landskap', farg: '#C9871F', sub: 'bildserier', mapp: 'landskap' },
    { id: 'event', namn: 'Event', farg: '#C9657F', sub: 'porträtt, bröllop…', mapp: 'event' },
  ]
  const STATUSAR = ['kommande', 'pagaende', 'avslutad']
  const STATUS_ETI = { kommande: 'Kommande', pagaende: 'Pågående', avslutad: 'Avslutad' }
  const EVENT_KAT = ['Porträtt', 'Bröllop', 'Student', 'Företag', 'Mode', 'Övrigt']

  let ctyp = 'match'
  let matcher = []
  let pick = ''
  let auto = true
  let cms = { status: 'kommande', hem: '', borta: '', resultat: '', halvtid: '',
    datum: '', serie: '', arena: '', galleri: '', malskyttar: '', svep: '', figurer: [],
    hero: '', heroPosition: 'center center' }
  let cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '',
    galleri: '', ingress: '', figurer: [] }
  let cmsLandskap = { titel: '', plats: '', period: '', ingress: '', figurer: [] }
  let cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '',
    platser: [], figurer: [] }
  let md = ''
  let exportDirs = { match: '', event: '', landskap: '', blogg: '' }
  let sparad = false
  let synkar = false
  let synkFel = ''
  let synkad = false
  let publiceradId = ''
  let statusInfo = null
  let statusLaddar = false
  let genKor = false
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

  onMount(async () => {
    matcher = await listaMatcher()
    if (matcher[0]) { pick = matcher[0].id; fyllFranMatch(matcher[0]) }
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

  function fyllFranMatch(m) {
    cms.hem = m.lag_hemma || ''; cms.borta = m.lag_borta || ''
    cms.resultat = m.resultat || ''; cms.datum = m.datum || ''
    cms.arena = m.arena || ''; cms.serie = m.liga || ''
    if (auto) cms.status = harledStatus(m.datum, m.tid, m.resultat)
    cms = cms
  }
  function valjMatch(e) {
    pick = e.target.value
    const m = matcher.find((x) => x.id === pick)
    if (m) fyllFranMatch(m)
    forhandsgranska()
  }
  $: if (auto) cms.status = harledStatus(cms.datum, '', cms.resultat)

  function bytTyp(id) {
    ctyp = id
    forhandsgranska()
  }

  function data() {
    if (ctyp === 'match') return { typ: 'match', titel: `${cms.hem} – ${cms.borta}`,
      hem: cms.hem, borta: cms.borta, serie: cms.serie,
      status: cms.status, datum: cms.datum, resultat: cms.resultat, halvtid: cms.halvtid,
      arena: cms.arena, malskyttar: cms.malskyttar,
      pixieset: cms.galleri, body: cms.svep, figurer: cms.figurer,
      hero: cms.hero, heroPosition: cms.heroPosition }
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
  function taBild(i) { akt.figurer = akt.figurer.filter((_, j) => j !== i); pinga(); forhandsgranska() }
  function laggPlats() { cmsBlogg.platser = [...cmsBlogg.platser, { plats: '', tips: '' }] }
  function taPlats(i) { cmsBlogg.platser = cmsBlogg.platser.filter((_, j) => j !== i); forhandsgranska() }

  // Sport: fyll höjdpunktsgalleriet från det aktiva Publicera-urvalet (topp-
  // rankade filer). Utan urval → fallback på aktiva matchen som källetikett.
  async function hamtaHojdpunkter() {
    const r = await urvalHojdpunkter(6)
    const filer = (r?.ok && r.filer) || []
    const antal = Math.min(filer.length || (r?.ok && r.urval?.bilder) || 6, 6)
    hlKalla = (r?.ok && r.namn) || `${cms.hem} – ${cms.borta}`.replace(/\s+/g, ' ').trim()
    const matchinfo = `${cms.hem} ${cms.resultat} ${cms.borta}`.replace(/\s+/g, ' ').trim()
    cms.figurer = Array.from({ length: antal }, (_, i) => ({
      bild: '', alt: `${matchinfo} — höjdpunkt ${i + 1}`, bildtext: '', src: filer[i] || '' }))
    hlFlash = true
    setTimeout(() => (hlFlash = false), 2200)
    forhandsgranska()
  }

  async function genereraSvep() {
    genKor = true
    const info = `${cms.hem}–${cms.borta}${cms.resultat ? ' ' + cms.resultat : ''}`
    const r = await genereraBildsvep(info, 'fotboll', '')
    genKor = false
    if (r?.ok) { cms.svep = r.bildsvep; forhandsgranska() }
  }
  async function spara() {
    if (!exportDirs[ctyp]) {
      const r = await valjMapp(`Välj content/${typinfo.mapp}-katalog`)
      if (r.ok) exportDirs[ctyp] = r.path; else return
    }
    const r = await exporteraInnehall(data(), exportDirs[ctyp])
    sparad = !!r?.ok
    if (sparad) setTimeout(() => (sparad = false), 2600)
  }

  async function publicera() {
    synkar = true
    synkFel = ''
    statusInfo = null
    const r = await publiceraInnehallNatet(data())
    synkar = false
    synkad = !!r?.ok
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
          {:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>{/if}
        </span>
        <span class="tnamn scd">{ct.namn}</span>
        <span class="tsub">{ct.sub}</span>
      </button>
    {/each}
  </div>

  {#if ctyp === 'match'}
    <div class="kort">
      <div class="caps">Publicera till hemsidan</div>
      <div class="grid2">
        <div class="f"><label>Match / event</label>
          <select value={pick} on:change={valjMatch}>
            {#each matcher as m}<option value={m.id}>{m.lag_hemma} – {m.lag_borta}{m.datum ? ' · ' + m.datum : ''}</option>{/each}
          </select>
        </div>
        <div class="f">
          <div class="statushuvud"><label>Status på hemsidan</label><button class="autochip" class:on={auto} on:click={() => (auto = !auto)}>Auto</button></div>
          <div class="seg">
            {#each STATUSAR as s}<button class:on={cms.status === s} on:click={() => { if (!auto) cms.status = s }} disabled={auto}>{STATUS_ETI[s]}</button>{/each}
          </div>
          <div class="hint">Härleds från datum & tid · Avslutad sätts när du skapar Resultat-story</div>
        </div>
      </div>

      <div class="grid2 mt">
        <div class="f"><label>Hemmalag</label><input bind:value={cms.hem} on:change={forhandsgranska} /></div>
        <div class="f"><label>Bortalag</label><input bind:value={cms.borta} on:change={forhandsgranska} /></div>
        <div class="f"><label>Resultat</label><input bind:value={cms.resultat} on:change={forhandsgranska} /></div>
        <div class="f"><label>Halvtid</label><input bind:value={cms.halvtid} on:change={forhandsgranska} /></div>
        <div class="f"><label>Datum</label><input bind:value={cms.datum} on:change={forhandsgranska} /></div>
        <div class="f"><label>Serie</label><input bind:value={cms.serie} on:change={forhandsgranska} /></div>
      </div>
      <div class="f mt"><label>Arena</label><input bind:value={cms.arena} on:change={forhandsgranska} /></div>
      <div class="f mt"><label>Galleri-URL (Pixieset)</label><input class="mono" bind:value={cms.galleri} on:change={forhandsgranska} /></div>
      <div class="f mt"><label>Målskyttar</label><input bind:value={cms.malskyttar} on:change={forhandsgranska} /></div>
      <div class="f mt">
        <label>Hero-bild &amp; fokuspunkt</label>
        <BildvaljareFokuspunkt bind:hero={cms.hero} bind:heroPosition={cms.heroPosition} on:change={forhandsgranska} />
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
          <div class="figbild"><span>figur {i + 1}</span></div>
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
      <button class="prim" on:click={genereraSvep} disabled={genKor}>{genKor ? 'Genererar…' : 'Generera'}</button>
    </div>
    <div class="kort nogap">
      <textarea bind:value={cms.svep} on:change={forhandsgranska} rows="4" placeholder="Klicka Generera så skriver bildsvep.py en bildtext från matchinfo — redigerbar."></textarea>
    </div>
  {/if}

  <div class="kort">
    <div class="mdhuvud"><span class="caps">Markdown · förhandsvisning</span></div>
    <pre>{md}</pre>
    <div class="mdfot">
      <button class="prim" on:click={spara}>Spara .md-fil</button>
      {#if sparad}<span class="ok">✓ Sparad till content/{typinfo.mapp}/</span>{/if}
      <button class="prim" on:click={publicera} disabled={synkar}>{synkar ? 'Publicerar…' : 'Publicera till hemsidan'}</button>
      {#if synkad}<span class="ok">✓ Publicerad</span>{/if}
      {#if synkFel}<span class="synkfel">{synkFel}</span>{/if}
      {#if publiceradId}
        <button class="statusbtn" on:click={kollaStatus} disabled={statusLaddar}>{statusLaddar ? 'Kollar…' : 'Kolla status'}</button>
        {#if deployText}<span class="deploystatus">{deployText}</span>{/if}
      {/if}
    </div>
  </div>
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 760px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }

  /* Fyra färgkodade typkort (Blog · Sport · Landskap · Event) */
  .typkort { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 16px; }
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
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .figbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-mut); }
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

  .mdhuvud { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  pre { margin: 0; background: var(--panel); border: 1px solid var(--div3); border-radius: 8px; padding: 14px;
    font-family: var(--mono, ui-monospace, monospace); font-size: 12px; line-height: 1.6; color: var(--t-head);
    white-space: pre-wrap; word-break: break-word; max-height: 260px; overflow: auto; }
  .mdfot { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 16px; font-size: 13px; font-weight: 600; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .synkfel { font-size: 12.5px; color: #C0453E; font-weight: 600; }
  .statusbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 7px;
    padding: 8px 14px; font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }
  .statusbtn:disabled { opacity: 0.5; }
  .deploystatus { font-size: 12.5px; color: var(--t-mut); font-weight: 600; }
</style>
