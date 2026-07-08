<script>
  import { onMount } from 'svelte'
  import { forhandsgranskaInnehall, exporteraInnehall, publiceraInnehallNatet, statusInnehall, valjMapp, valjFil, thumbForBild, slugga } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { testMode } from '../lib/testlage.js'

  // Tre match-oberoende webbtyper. Sport (matchreferat) och På gång har
  // flyttat till Matchpublicering — Innehåll äger nu bara Blog/Landskap/Event.
  const CTYPER = [
    { id: 'blogg', namn: 'Blog', farg: '#7A8794', sub: 'journal & resor', hint: 'Journal, resor & fritext — en fristående bloggpost.', mapp: 'blogg' },
    { id: 'landskap', namn: 'Landskap', farg: '#C9871F', sub: 'bildserier', hint: 'Bildserie — landskap & natur, endast bilder.', mapp: 'landskap' },
    { id: 'event', namn: 'Event', farg: '#C9657F', sub: 'porträtt, bröllop…', hint: 'Porträtt, bröllop, student & företag.', mapp: 'event' },
  ]
  const EVENT_KAT = ['Porträtt', 'Bröllop', 'Student', 'Företag', 'Mode', 'Övrigt']

  let ctyp = 'blogg'
  let cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '',
    galleri: '', ingress: '', figurer: [] }
  let cmsLandskap = { titel: '', plats: '', period: '', ingress: '', figurer: [] }
  let cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '',
    platser: [], figurer: [] }
  let md = ''
  let exportDirs = { event: '', landskap: '', blogg: '' }
  let sparad = false
  let sparadPath = ''
  let synkar = false
  let synkFel = ''
  let synkad = false
  let synkadPath = ''
  let publiceradId = ''
  let statusInfo = null
  let statusLaddar = false

  $: akt = ctyp === 'event' ? cmsEvent
    : ctyp === 'landskap' ? cmsLandskap : cmsBlogg
  $: typinfo = CTYPER.find((t) => t.id === ctyp)
  // Landskap & Event = bild-only-galleri (härledd /bilder/{slug}/{n}.jpg-ref,
  // ingen alt/bildtext) — speglar _innehall_md. Blog har alt/bildtext.
  $: galText = ctyp !== 'landskap' && ctyp !== 'event'
  $: aktSlug = slugga(akt.titel)

  onMount(async () => { await forhandsgranska() })

  function bytTyp(id) { ctyp = id; forhandsgranska() }

  function data() {
    if (ctyp === 'event') return { typ: 'event', ...cmsEvent }
    if (ctyp === 'landskap') return { typ: 'landskap', ...cmsLandskap }
    return { typ: 'blogg', ...cmsBlogg }
  }

  async function forhandsgranska() {
    const r = await forhandsgranskaInnehall(data())
    md = r?.md || ''
  }

  function pinga() { cmsEvent = cmsEvent; cmsLandskap = cmsLandskap; cmsBlogg = cmsBlogg }
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

  <div class="cmstabs">
    {#each CTYPER as ct}
      <button class="cmstab" class:on={ctyp === ct.id}
        style="--tf:{ct.farg}" on:click={() => bytTyp(ct.id)}>
        <span class="cmstik">
          {#if ct.id === 'blogg'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
          {:else if ct.id === 'landskap'}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 17l5-8 4 6 3-4 6 6"/><circle cx="17.5" cy="7.5" r="1.8"/></svg>
          {:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>{/if}
        </span>
        <span class="cmstnamn scd">{ct.namn}</span>
      </button>
    {/each}
  </div>
  {#if typinfo}<div class="cmssub">{typinfo.hint}</div>{/if}

  {#if ctyp === 'event'}
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
      <span class="caps nomarg">Galleri</span>
    </div>
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
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 760px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }

  /* Kompakt typväljare (segment-rad, aktivt i kategorifärg) */
  .cmstabs { display: flex; gap: 4px; margin-top: 16px; padding: 4px; border: 1px solid var(--div);
    border-radius: 12px; background: var(--panel); box-shadow: var(--skugga); }
  .cmstab { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    padding: 9px 10px; border: none; border-radius: 9px; background: transparent; color: var(--t-mut);
    font-size: 13.5px; font-weight: 600; }
  .cmstab .cmstik { display: inline-flex; align-items: center; justify-content: center; color: currentColor; }
  .cmstab .cmstik svg { width: 16px; height: 16px; }
  .cmstab .cmstnamn { font-weight: 700; }
  .cmstab.on { background: var(--tf); color: #fff; box-shadow: var(--skugga); }
  .cmstab:hover:not(.on) { color: var(--tf); background: color-mix(in srgb, var(--tf) 10%, transparent); }
  .cmssub { font-size: 11.5px; color: var(--t-mut); margin: 8px 2px 0; }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; margin-top: 14px; }
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

  /* Låst tema-indikator (temat härleds ur typen; Landskap = Sol) */
  .temalast { display: inline-flex; align-items: center; gap: 9px; background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 8px 12px; align-self: flex-start; }
  .temaprick { width: 9px; height: 9px; border-radius: 50%; background: #C9871F; flex: none; }
  .temanamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .temainfo { font-size: 11px; color: var(--t-mut); }

  .galhuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .caps.nomarg { margin-bottom: 0; }

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
