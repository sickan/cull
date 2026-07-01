<script>
  import { onMount } from 'svelte'
  import {
    listaInnehall, forhandsgranskaInnehall, sparaInnehall,
    exporteraInnehall, raderaInnehall,
  } from '../lib/api.js'

  const TYPER = ['match', 'event', 'landskap', 'portratt', 'blogg']
  const HERO_POS = ['', 'center', 'top', 'bottom']

  let lista = []
  let laddar = true
  let form = null            // null = ingen redigering
  let preview = null         // genererad .md
  let exportDir = ''
  let status = null

  function tomForm() {
    return {
      id: null, typ: 'match', titel: '', datum: '', liga: '', arena: '',
      resultat: '', status: '', hero: '', heroPosition: '', pixieset: '',
      malskyttar: '', body: '', figurer: [],
    }
  }

  onMount(async () => {
    lista = await listaInnehall()
    laddar = false
  })

  async function ladda() { lista = await listaInnehall() }

  function nytt() { form = tomForm(); preview = null; status = null }
  function redigera(i) {
    const fm = i.frontmatter || {}
    form = {
      id: i.id, typ: i.typ, titel: fm.titel || '', datum: fm.datum || '',
      liga: fm.liga || '', arena: fm.arena || '', resultat: fm.resultat || '',
      status: i.status || fm.status || '', hero: fm.hero || '',
      heroPosition: fm.heroPosition || '', pixieset: fm.pixieset || '',
      malskyttar: (fm.malskyttar || []).join(', '), body: i.body || '', figurer: [],
    }
    preview = null; status = null
  }

  function laggFigur() { form.figurer = [...form.figurer, { bild: '', alt: '', bildtext: '' }] }
  function taFigur(ix) { form.figurer = form.figurer.filter((_, i) => i !== ix) }

  async function forhandsgranska() {
    const r = await forhandsgranskaInnehall(form)
    preview = r.md
  }

  async function spara() {
    const r = await sparaInnehall(form)
    status = r.ok ? 'Sparat.' : (r.fel || 'Fel.')
    if (r.ok) { form.id = r.id; await ladda() }
  }

  async function exportera() {
    const r = await exporteraInnehall(form, exportDir)
    status = r.ok ? `Exporterat → ${r.path}` : (r.fel || 'Fel.')
    if (r.ok) { form.id = r.id; await ladda() }
  }

  async function tabort(i) {
    await raderaInnehall(i.id)
    if (form && form.id === i.id) form = null
    await ladda()
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Innehåll</h1>
    <span class="sub">CMS för hemsidan — genererar Markdown och exporterar till sajt-repot</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar…</p>
  {:else}
    <div class="lista">
      {#each lista as i (i.id)}
        <div class="rad">
          <span class="badge">{i.typ}</span>
          <button class="titel scd" on:click={() => redigera(i)}>
            {(i.frontmatter && i.frontmatter.titel) || '(namnlöst)'}
          </button>
          {#if i.publicerad}<span class="pub">✓ publicerad</span>{/if}
          <button class="x" on:click={() => tabort(i)} title="Ta bort">×</button>
        </div>
      {/each}
      <button class="nytt" on:click={nytt}>+ Nytt innehåll</button>
    </div>

    {#if form}
      <div class="kort">
        <div class="grid2">
          <label>Typ
            <select bind:value={form.typ}>
              {#each TYPER as t}<option value={t}>{t}</option>{/each}
            </select>
          </label>
          <label>Status
            <input bind:value={form.status} placeholder="avslutad / kommande" />
          </label>
        </div>
        <label class="full">Titel
          <input bind:value={form.titel} placeholder="Malmö FF – Kristianstads DFF" />
        </label>
        <div class="grid3">
          <label>Datum<input bind:value={form.datum} placeholder="2026-06-27" /></label>
          <label>Liga<input bind:value={form.liga} /></label>
          <label>Arena<input bind:value={form.arena} /></label>
        </div>
        <div class="grid3">
          <label>Resultat<input bind:value={form.resultat} placeholder="6-0" /></label>
          <label>Hero (omslag)<input bind:value={form.hero} placeholder="bilder/hero.jpg" /></label>
          <label>Hero-position
            <select bind:value={form.heroPosition}>
              {#each HERO_POS as p}<option value={p}>{p || '(default)'}</option>{/each}
            </select>
          </label>
        </div>
        <label class="full">Pixieset (galleri-länk)
          <input bind:value={form.pixieset} placeholder="https://…pixieset.com/…" />
        </label>
        <label class="full">Målskyttar (kommaseparerat)
          <input bind:value={form.malskyttar} placeholder="Musovic 12', Persson 45'" />
        </label>
        <label class="full">Brödtext
          <textarea rows="5" bind:value={form.body} placeholder="Referat…"></textarea>
        </label>

        <div class="figurer">
          <div class="caps">Figurer (bild · alt · bildtext)</div>
          {#each form.figurer as f, ix}
            <div class="figrad">
              <input bind:value={f.bild} placeholder="bild.jpg" />
              <input bind:value={f.alt} placeholder="alt-text" />
              <input bind:value={f.bildtext} placeholder="bildtext" />
              <button class="x" on:click={() => taFigur(ix)}>×</button>
            </div>
          {/each}
          <button class="sek liten" on:click={laggFigur}>+ Figur</button>
        </div>

        <div class="exportrad">
          <input class="exp" bind:value={exportDir} placeholder="Export-katalog (sajt-repo)/src/content/match" />
          <button class="sek" on:click={forhandsgranska}>Förhandsgranska</button>
          <button class="sek" on:click={spara}>Spara</button>
          <button class="prim" on:click={exportera} disabled={!exportDir || !form.titel}>Exportera .md ›</button>
        </div>
        {#if status}<div class="status">{status}</div>{/if}

        {#if preview}
          <pre class="md">{preview}</pre>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .lista { display: flex; flex-direction: column; gap: 8px; margin: 18px 0; }
  .rad { display: flex; align-items: center; gap: 10px; padding: 10px 14px;
    background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); }
  .badge { padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600;
    text-transform: uppercase; background: var(--div3); color: var(--t-mut); }
  .titel { flex: 1; text-align: left; background: none; border: 0; font-size: 14px;
    font-weight: 600; color: var(--t-head); cursor: pointer; }
  .titel:hover { color: var(--acc); }
  .pub { font-size: 11.5px; color: var(--ok); }
  .x { width: 24px; height: 24px; border: 1px solid var(--div); border-radius: 6px;
    background: var(--kort); color: var(--t-mut); font-size: 15px; line-height: 1; }
  .x:hover { border-color: var(--varn); color: var(--varn); }
  .nytt { align-self: flex-start; padding: 8px 14px; border: 1px dashed var(--div);
    border-radius: 8px; background: none; color: var(--t-mut); font-size: 13px; }
  .nytt:hover { border-color: var(--acc); color: var(--acc); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 18px; display: flex; flex-direction: column; gap: 14px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); }
  .full { width: 100%; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-caps); margin-bottom: 8px; }
  input, select, textarea { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--acc); }
  textarea { font-family: inherit; resize: vertical; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }

  .figurer { display: flex; flex-direction: column; gap: 8px; }
  .figrad { display: grid; grid-template-columns: 1.2fr 1fr 1.4fr auto; gap: 8px; align-items: center; }
  .liten { align-self: flex-start; padding: 6px 12px; font-size: 12.5px; }

  .exportrad { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .exp { flex: 1; min-width: 220px; }
  .status { font-size: 12.5px; color: var(--ok); }
  .md { background: var(--panel); border: 1px solid var(--div); border-radius: 8px;
    padding: 14px; font-family: var(--mono, ui-monospace, monospace); font-size: 12px;
    line-height: 1.5; white-space: pre-wrap; color: var(--t-body); overflow-x: auto; }

  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
