<script>
  import { onMount } from 'svelte'
  import { forhandsgranskaInnehall, exporteraInnehall, listaMatcher, genereraBildsvep, valjMapp } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'

  const CTYPER = [
    { id: 'match', namn: 'Matcher', soon: false },
    { id: 'landskap', namn: 'Landskap', soon: true },
    { id: 'portratt', namn: 'Porträtt', soon: true },
    { id: 'blogg', namn: 'Blogg', soon: true },
  ]
  const STATUSAR = ['kommande', 'pagaende', 'avslutad']
  const STATUS_ETI = { kommande: 'Kommande', pagaende: 'Pågående', avslutad: 'Avslutad' }

  let ctyp = 'match'
  let matcher = []
  let pick = ''
  let auto = true
  let cms = { status: 'kommande', hem: '', borta: '', resultat: '', halvtid: '',
    datum: '', serie: '', arena: '', galleri: '', malskyttar: '', svep: '', figurer: [] }
  let md = ''
  let exportDir = ''
  let sparad = false
  let genKor = false

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

  async function forhandsgranska() {
    const data = { typ: 'match', titel: `${cms.hem} – ${cms.borta}`, status: cms.status,
      datum: cms.datum, resultat: cms.resultat, malskyttar: cms.malskyttar,
      pixieset: cms.galleri, body: cms.svep, figurer: cms.figurer }
    const r = await forhandsgranskaInnehall(data)
    md = r?.md || ''
  }

  function laggBild() { cms.figurer = [...cms.figurer, { bild: '', alt: '', bildtext: '' }] }
  function taBild(i) { cms.figurer = cms.figurer.filter((_, j) => j !== i) }

  async function genereraSvep() {
    genKor = true
    const info = `${cms.hem}–${cms.borta}${cms.resultat ? ' ' + cms.resultat : ''}`
    const r = await genereraBildsvep(info, 'fotboll', '')
    genKor = false
    if (r?.ok) { cms.svep = r.bildsvep; forhandsgranska() }
  }
  async function spara() {
    if (!exportDir) { const r = await valjMapp('Välj content/matcher-katalog'); if (r.ok) exportDir = r.path; else return }
    const data = { typ: 'match', titel: `${cms.hem} – ${cms.borta}`, status: cms.status,
      datum: cms.datum, resultat: cms.resultat, malskyttar: cms.malskyttar, pixieset: cms.galleri,
      body: cms.svep, figurer: cms.figurer }
    const r = await exporteraInnehall(data, exportDir)
    sparad = !!r?.ok
    if (sparad) setTimeout(() => (sparad = false), 2600)
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Innehåll</h1>
    <span class="sub">Skapa innehåll till hemsidan — frontmatter och bilder blir en färdig .md-fil</span>
  </header>

  <div class="ctabs">
    {#each CTYPER as ct}
      <button class:on={ctyp === ct.id} disabled={ct.soon} on:click={() => (ctyp = ct.id)}>
        {ct.namn}{#if ct.soon}<span class="soon">snart</span>{/if}
      </button>
    {/each}
  </div>

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
      <div class="f"><label>Halvtid</label><input bind:value={cms.halvtid} /></div>
      <div class="f"><label>Datum</label><input bind:value={cms.datum} on:change={forhandsgranska} /></div>
      <div class="f"><label>Serie</label><input bind:value={cms.serie} /></div>
    </div>
    <div class="f mt"><label>Arena</label><input bind:value={cms.arena} /></div>
    <div class="f mt"><label>Galleri-URL (Pixieset)</label><input class="mono" bind:value={cms.galleri} on:change={forhandsgranska} /></div>
    <div class="f mt"><label>Målskyttar</label><input bind:value={cms.malskyttar} on:change={forhandsgranska} /></div>
  </div>

  <div class="kort">
    <div class="caps">Bilder · höjdpunkter</div>
    <div class="figurer">
      {#each cms.figurer as b, i}
        <div class="figrad">
          <div class="figbild"><span>figur {i + 1}</span></div>
          <div class="figin">
            <input bind:value={b.alt} placeholder="Alt-text (tillgänglighet)" />
            <input bind:value={b.bildtext} on:change={forhandsgranska} placeholder="Bildtext" />
          </div>
          <button class="figx" class:armerad={$armerad === `fig-${i}`}
            title={$armerad === `fig-${i}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
            on:click={taBortKlick(`fig-${i}`, () => taBild(i))}>{$armerad === `fig-${i}` ? 'Ta bort?' : '×'}</button>
        </div>
      {/each}
      <button class="figadd" on:click={laggBild}>+ Lägg till bild</button>
    </div>
  </div>

  <div class="kort svepkort">
    <span class="svepik"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 20l1-4 11-11 3 3-11 11z"/><path d="M14 6l3 3"/></svg></span>
    <div class="sveptxt"><div class="svt">Instagram Bildsvepet</div><div class="svs">Genereras från matchinfo</div></div>
    <button class="prim" on:click={genereraSvep} disabled={genKor}>{genKor ? 'Genererar…' : 'Generera'}</button>
  </div>
  <div class="kort nogap">
    <textarea bind:value={cms.svep} on:change={forhandsgranska} rows="4" placeholder="Klicka Generera så skriver bildsvep.py en bildtext från matchinfo — redigerbar."></textarea>
  </div>

  <div class="kort">
    <div class="mdhuvud"><span class="caps">Markdown · förhandsvisning</span></div>
    <pre>{md}</pre>
    <div class="mdfot">
      <button class="prim" on:click={spara}>Spara .md-fil</button>
      {#if sparad}<span class="ok">✓ Sparad till content/matcher/</span>{/if}
    </div>
  </div>
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 760px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }

  .ctabs { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
  .ctabs button { padding: 8px 15px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
  .ctabs button.on { background: var(--acc); border-color: var(--acc); color: #fff; }
  .ctabs button:disabled { opacity: 0.6; }
  .soon { font-size: 9px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.8; }

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

  .figurer { display: flex; flex-direction: column; gap: 10px; }
  .figrad { display: flex; gap: 12px; align-items: flex-start; border: 1px solid var(--div3); border-radius: 10px; padding: 10px; background: var(--panel); }
  .figbild { width: 92px; height: 69px; flex: none; border-radius: 6px; display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .figbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-mut); }
  .figin { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
  .figin input { background: var(--kort); font-size: 12.5px; padding: 7px 9px; }
  .figx { flex: none; width: 28px; height: 28px; border-radius: 7px; border: 1px solid var(--div); background: var(--kort); color: var(--t-mut); font-size: 16px; }
  .figx.armerad { width: auto; padding: 0 10px; background: #C0453E; border-color: #C0453E; color: #fff; font-size: 11.5px; font-weight: 600; }
  .figadd { display: flex; align-items: center; justify-content: center; gap: 8px; border: 1.5px dashed var(--div); border-radius: 10px; padding: 11px; color: var(--t-mut); font-size: 13px; font-weight: 500; background: transparent; }
  .figadd:hover { border-color: var(--acc); color: var(--acc); }

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
</style>
