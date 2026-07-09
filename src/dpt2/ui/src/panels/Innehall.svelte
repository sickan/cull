<script>
  import { onMount } from 'svelte'
  import { forhandsgranskaInnehall, exporteraInnehall, publiceraInnehallNatet, statusInnehall, valjMapp, valjFil, thumbForBild, slugga } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { testMode } from '../lib/testlage.js'
  import BildvaljareFokuspunkt from '../lib/BildvaljareFokuspunkt.svelte'

  // Tre match-oberoende webbtyper. Sport (matchreferat) och På gång har
  // flyttat till Matchpublicering — Innehåll äger nu bara Blog/Landskap/Event.
  // B4: "Event" heter numera "Människor" (personikon). Interna nyckeln/mappen
  // är kvar som 'event' (sajtens content-collection-kontrakt orört).
  const CTYPER = [
    { id: 'blogg', namn: 'Blog', farg: '#7A8794', sub: 'journal & resor', hint: 'Journal, resor & fritext — en fristående bloggpost.', mapp: 'blogg' },
    { id: 'landskap', namn: 'Landskap', farg: '#C9871F', sub: 'bildserier', hint: 'Bildserie — landskap & natur, endast bilder.', mapp: 'landskap' },
    { id: 'event', namn: 'Människor', farg: '#C9657F', sub: 'porträtt, bröllop…', hint: 'Porträtt, bröllop, student & företag.', mapp: 'event' },
  ]
  const EVENT_KAT = ['Porträtt', 'Bröllop', 'Student', 'Företag', 'Mode', 'Övrigt']

  let ctyp = 'blogg'
  // A3/B4: hero-bild med fokus (21:9) på alla tre typer. hero=filnamn (frontmatter),
  // heroPosition=object-position ("x% y%"), heroKalla=lokal källfil (export, aldrig publik).
  let cmsEvent = { kategori: 'Porträtt', titel: '', kund: '', datum: '', plats: '',
    ingress: '', hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
  let cmsLandskap = { titel: '', plats: '', period: '', ingress: '',
    hero: '', heroPosition: 'center center', heroKalla: '', figurer: [] }
  let cmsBlogg = { kategori: '', titel: '', datum: '', ingress: '', body: '',
    hero: '', heroPosition: 'center center', heroKalla: '', platser: [], figurer: [] }
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
  // Landskap & Människor = bild-only-galleri (härledd /bilder/{slug}/{n}.jpg-ref,
  // ingen alt/bildtext) — speglar _innehall_md. Blog har bildtext per bild.
  // (Bildtext för Människor kräver bilder[]-objekt + sajt-render → Fas 3b.)
  $: galText = ctyp !== 'landskap' && ctyp !== 'event'
  $: aktSlug = slugga(akt.titel)

  onMount(async () => { await forhandsgranska() })

  function bytTyp(id) { ctyp = id; forhandsgranska() }

  // Miniatyrerna (data-URI) bor på figur-objektet som `thumb` men skickas
  // ALDRIG till backend — bara den lokala källsökvägen (`bild`) exporteras.
  const utanThumb = (arr) => (arr || []).map(({ thumb, ...r }) => r)
  function data() {
    if (ctyp === 'event') return { typ: 'event', ...cmsEvent, figurer: utanThumb(cmsEvent.figurer) }
    if (ctyp === 'landskap') return { typ: 'landskap', ...cmsLandskap, figurer: utanThumb(cmsLandskap.figurer) }
    return { typ: 'blogg', ...cmsBlogg, figurer: utanThumb(cmsBlogg.figurer) }
  }

  async function forhandsgranska() {
    const r = await forhandsgranskaInnehall(data())
    md = r?.md || ''
  }

  function pinga() { cmsEvent = cmsEvent; cmsLandskap = cmsLandskap; cmsBlogg = cmsBlogg }
  // Hero-bild (fokuskomponenten binder in hero/heroPosition/heroKalla i akt) —
  // uppdatera .md-förhandsvisningen när bild eller fokuspunkt ändras.
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

  // B3/B4: dra för att ordna om galleriet. Miniatyren följer objektet, så
  // omordning är en ren array-flytt (ingen index→thumb-remappning).
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
          {:else}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.6"/><path d="M5 20c0-3.5 3.1-5.5 7-5.5s7 2 7 5.5"/></svg>{/if}
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
      <span class="galhint">{galText ? 'Bilderna visas i sitt eget format · dra för att ordna om · bildtext per bild' : 'Bilderna visas i sitt eget format · dra för att ordna om'}</span>
    </div>
    <div class="galgrid">
      {#each akt.figurer as b, i (b)}
        <div class="figtile" class:drar={dragIdx === i} draggable="true"
          on:dragstart={() => dragStart(i)} on:dragover={(e) => dragOver(i, e)} on:drop={() => slapp(i)} on:dragend={() => (dragIdx = null)}>
          <button type="button" class="figthumb" class:has={!!b.thumb}
            on:click={() => valjFigurBild(i)} title="Välj bild">
            {#if b.thumb}<img src={b.thumb} alt="" draggable="false" />{:else}<span>+ bild {i + 1}</span>{/if}
          </button>
          <button class="figx" class:armerad={$armerad === `fig-${i}`}
            title={$armerad === `fig-${i}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
            on:click={taBortKlick(`fig-${i}`, () => taBild(i))}>{$armerad === `fig-${i}` ? 'Ta bort?' : '×'}</button>
          {#if galText}
            {#if b.src}<div class="figsrc">från urval · {b.src}</div>{/if}
            <input class="figcap" bind:value={b.bildtext} on:change={forhandsgranska} placeholder="Bildtext…" />
            <input class="figalt" bind:value={b.alt} on:change={forhandsgranska} placeholder="Alt-text (tillgänglighet)" />
          {:else}
            <div class="figref">/bilder/{aktSlug}/{i + 1}.jpg</div>
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
  .capshint { font-weight: 600; text-transform: none; letter-spacing: 0; color: var(--t-help); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .mt { margin-top: 12px; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  label { font-size: 11px; color: var(--t-mut); }
  input, select, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 10px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, select:focus, textarea:focus { border-color: var(--acc); }
  textarea { line-height: 1.55; resize: vertical; }

  /* Låst tema-indikator (temat härleds ur typen; Landskap = Sol) */
  .temalast { display: inline-flex; align-items: center; gap: 9px; background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 8px 12px; align-self: flex-start; }
  .temaprick { width: 9px; height: 9px; border-radius: 50%; background: #C9871F; flex: none; }
  .temanamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .temainfo { font-size: 11px; color: var(--t-mut); }

  .galhuvud { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .caps.nomarg { margin-bottom: 0; }
  .galhint { font-size: 11px; color: var(--t-help); }

  /* B3/B4: galleri som rutnät — bilderna i sitt eget format (ingen beskärning),
     dra för att ordna om, bildtext per bild (blogg + Människor). */
  .galgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; align-items: start; }
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

  /* Platser & tips (blogg) — kvar som lista */
  .figurer { display: flex; flex-direction: column; gap: 10px; }
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
