<script>
  import { onMount } from 'svelte'
  import { aktivMatch, genereraBildsvep, skapaStory } from '../lib/api.js'

  let match = null
  let laddar = true

  // Bildsvepet
  let bs = { matchinfo: '', sport: '', hemmafarg: '' }
  let bsKor = false
  let bsResultat = null
  let kopierad = false

  // Matchdag (story)
  const MOMENT = ['Avspark', 'Startelva', 'Halvtid', 'Slutresultat', 'Målgörare', 'Nästa match']
  const TEMAN = ['Hav', 'Sol', 'Rosé']
  const FORMAT = [
    { id: '9x16', namn: 'Story 9:16' },
    { id: '4x5', namn: 'Inlägg 4:5' },
  ]
  let story = { moment: 'Avspark', tema: 'Hav', format: '9x16', foto: '' }
  let storyKor = false
  let storyResultat = null

  const FARGER = ['', 'vit', 'svart', 'röd', 'blå', 'gul', 'grön', 'orange']

  onMount(async () => {
    match = await aktivMatch()
    if (match) {
      bs.matchinfo = `${match.lag_hemma}–${match.lag_borta}` +
        (match.resultat ? ` ${match.resultat}` : '')
      bs.sport = match.sport || ''
    }
    laddar = false
  })

  async function korBildsvep() {
    bsKor = true; bsResultat = null; kopierad = false
    bsResultat = await genereraBildsvep(bs.matchinfo, bs.sport, bs.hemmafarg)
    bsKor = false
  }

  async function kopiera() {
    try {
      await navigator.clipboard.writeText(bsResultat.bildsvep)
      kopierad = true
      setTimeout(() => (kopierad = false), 1800)
    } catch (_) { /* clipboard kan saknas i pywebview */ }
  }

  async function korStory() {
    storyKor = true; storyResultat = null
    storyResultat = await skapaStory(story)
    storyKor = false
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Publicera</h1>
    <span class="sub">Bildsvepet-text för Instagram och Matchdag-stories</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar…</p>
  {:else}
    {#if match}
      <div class="aktiv">
        <span class="prick"></span>
        <div>
          <div class="caps">Aktiv match</div>
          <div class="namn scd">{match.lag_hemma} – {match.lag_borta}</div>
          <div class="meta">{match.datum}{match.arena ? ' · ' + match.arena : ''}</div>
        </div>
      </div>
    {:else}
      <div class="ingen">Ingen aktiv match — aktivera en i <b>Matcher</b> för automatisk ifyllnad (valfritt).</div>
    {/if}

    <!-- Bildsvepet -->
    <div class="kort">
      <div class="cardH">Bildsvepet — Instagram-bildtext</div>
      <label class="full">Matchrad
        <input bind:value={bs.matchinfo} placeholder="Malmö FF–Växjö DFF 3–0" />
      </label>
      <div class="grid2">
        <label>Sport
          <input bind:value={bs.sport} placeholder="fotboll" />
        </label>
        <label>Hemmafärg
          <select bind:value={bs.hemmafarg}>
            {#each FARGER as f}<option value={f}>{f || '(ingen)'}</option>{/each}
          </select>
        </label>
      </div>
      <div class="kor">
        <button class="prim" on:click={korBildsvep} disabled={bsKor || !bs.matchinfo}>
          {bsKor ? 'Skriver…' : 'Generera ›'}
        </button>
      </div>

      {#if bsResultat && !bsResultat.ok}
        <div class="fel">{bsResultat.fel}</div>
      {/if}
      {#if bsResultat && bsResultat.ok}
        <div class="utdata">
          <textarea readonly rows="14">{bsResultat.bildsvep}</textarea>
          <div class="utfot">
            <span class="hint">Granska fakta och verifiera @-handles (markerade med ?) innan du postar.</span>
            <button class="sek" on:click={kopiera}>{kopierad ? '✓ Kopierat' : 'Kopiera'}</button>
          </div>
        </div>
      {/if}
    </div>

    <!-- Matchdag / story -->
    <div class="kort">
      <div class="cardH">Matchdag — story-overlay</div>
      <div>
        <div class="caps">Moment</div>
        <div class="chips">
          {#each MOMENT as m}
            <button class="chip" class:on={story.moment === m} on:click={() => (story.moment = m)}>{m}</button>
          {/each}
        </div>
      </div>
      <div class="grid2">
        <div>
          <div class="caps">Tema</div>
          <div class="chips">
            {#each TEMAN as t}
              <button class="chip" class:on={story.tema === t} on:click={() => (story.tema = t)}>{t}</button>
            {/each}
          </div>
        </div>
        <div>
          <div class="caps">Format</div>
          <div class="chips">
            {#each FORMAT as f}
              <button class="chip" class:on={story.format === f.id} on:click={() => (story.format = f.id)}>{f.namn}</button>
            {/each}
          </div>
        </div>
      </div>
      <label class="full">Källfoto
        <div class="filrad">
          <input bind:value={story.foto} placeholder="(valfritt nu) /sökväg/bild.jpg" />
          <button class="sek" title="Native filväljare i appen">Välj…</button>
        </div>
      </label>
      <div class="kor">
        {#if storyResultat}
          <span class="status" class:ok={storyResultat.ok}>{storyResultat.meddelande || storyResultat.fel}</span>
        {/if}
        <button class="prim" on:click={korStory} disabled={storyKor}>
          {storyKor ? 'Skapar…' : 'Skapa story ›'}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .aktiv { display: flex; gap: 12px; align-items: center; margin: 18px 0;
    padding: 12px 14px; background: var(--acc-soft); border-radius: var(--r); }
  .prick { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); flex: none; }
  .ingen { margin: 18px 0; padding: 12px 14px; background: var(--panel);
    border: 1px dashed var(--div); border-radius: var(--r); font-size: 13px; color: var(--t-mut); }
  .namn { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .meta { font-size: 12px; color: var(--t-mut); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 18px; display: flex; flex-direction: column; gap: 16px;
    margin-bottom: 16px; }
  .cardH { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-caps); }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-caps); margin-bottom: 8px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); }
  .full { width: 100%; }
  .filrad { display: flex; gap: 8px; }
  .filrad input { flex: 1; }
  input, select, textarea { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--acc); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .chips { display: flex; gap: 7px; flex-wrap: wrap; }
  .chip { padding: 6px 13px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--panel); color: var(--t-mut); font-size: 12.5px; }
  .chip.on { background: var(--acc); border-color: var(--acc); color: var(--kort); font-weight: 600; }

  .kor { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
  .status { font-size: 12.5px; color: var(--t-mut); }
  .status.ok { color: var(--ok); }
  .fel { font-size: 12.5px; color: var(--varn); }

  .utdata { display: flex; flex-direction: column; gap: 8px; }
  textarea { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; line-height: 1.5;
    resize: vertical; white-space: pre-wrap; }
  .utfot { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .hint { font-size: 11.5px; color: var(--t-help); }

  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
