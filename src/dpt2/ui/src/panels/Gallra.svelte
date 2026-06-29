<script>
  import { onMount } from 'svelte'
  import { aktivMatch, startaCull } from '../lib/api.js'

  export let aktivMatchData = null   // skickas av "Aktivera match" (annars hämtas)

  let match = null
  let laddar = true
  let kor = false
  let resultat = null

  let cfg = {
    kalla: '', behall_varde: 40, behall_enhet: 'bilder',
    verktyg: 'ai', modell: 'din_smak', burst: 2.0, hemmafarg: '',
  }

  const VERKTYG = [
    { id: 'ai', namn: 'AI-gallring', info: 'Poängsätter hela tagningen, behåller de bästa' },
    { id: 'snabb', namn: 'Snabb', info: 'AI bara på topp-kandidater' },
    { id: 'rapport', namn: 'Rapport', info: 'Poängsätter utan att kopiera' },
  ]
  const MODELLER = [
    { id: 'din_smak', namn: 'Din smak' },
    { id: 'arkiv', namn: 'Arkiv' },
    { id: 'hybrid', namn: 'Hybrid' },
  ]
  const FARGER = ['', 'vit', 'svart', 'röd', 'blå', 'gul', 'grön', 'orange']

  onMount(async () => {
    match = aktivMatchData || (await aktivMatch())
    laddar = false
  })

  async function kor_gallring() {
    kor = true; resultat = null
    const c = { ...cfg, match_id: match?.id || null }
    resultat = await startaCull(c)
    kor = false
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Gallra</h1>
    <span class="sub">Poängsätter och plockar de bästa bilderna ur tagningen</span>
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
      <div class="ingen">Ingen aktiv match — aktivera en i <b>Matcher</b> först (valfritt, men ger metadata).</div>
    {/if}

    <div class="kort">
      <label class="full">Källmapp (kort / katalog)
        <div class="filrad">
          <input bind:value={cfg.kalla} placeholder="/Volumes/NIKON Z 8/DCIM/277Z8_01" />
          <button class="sek" title="Native filväljare i appen">Välj…</button>
        </div>
      </label>

      <div class="grid2">
        <div>
          <div class="caps">Verktyg</div>
          <div class="chips">
            {#each VERKTYG as v}
              <button class="chip" class:on={cfg.verktyg === v.id} on:click={() => (cfg.verktyg = v.id)} title={v.info}>{v.namn}</button>
            {/each}
          </div>
        </div>
        <div>
          <div class="caps">Behåll</div>
          <div class="behall">
            <input type="number" min="1" bind:value={cfg.behall_varde} />
            <button class="chip" class:on={cfg.behall_enhet === 'bilder'} on:click={() => (cfg.behall_enhet = 'bilder')}>bilder</button>
            <button class="chip" class:on={cfg.behall_enhet === 'procent'} on:click={() => (cfg.behall_enhet = 'procent')}>%</button>
          </div>
        </div>
      </div>

      <div class="grid3">
        <label>Modell
          <select bind:value={cfg.modell}>
            {#each MODELLER as m}<option value={m.id}>{m.namn}</option>{/each}
          </select>
        </label>
        <label>Burst-gräns (sek)
          <input type="number" step="0.5" min="0" bind:value={cfg.burst} />
        </label>
        <label>Hemmafärg
          <select bind:value={cfg.hemmafarg}>
            {#each FARGER as f}<option value={f}>{f || '(ingen)'}</option>{/each}
          </select>
        </label>
      </div>

      <div class="kor">
        {#if resultat}
          <span class="status" class:ok={resultat.ok}>{resultat.meddelande}</span>
        {/if}
        <button class="prim" on:click={kor_gallring} disabled={kor || !cfg.kalla}>
          {kor ? 'Kör…' : 'Kör gallring ›'}
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
    box-shadow: var(--skugga); padding: 18px; display: flex; flex-direction: column; gap: 18px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
    text-transform: uppercase; color: var(--t-caps); margin-bottom: 8px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); }
  .full { width: 100%; }
  .filrad { display: flex; gap: 8px; }
  .filrad input { flex: 1; }
  input, select { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .grid2 { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  .chips { display: flex; gap: 7px; flex-wrap: wrap; }
  .chip { padding: 6px 13px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--panel); color: var(--t-mut); font-size: 12.5px; }
  .chip.on { background: var(--acc); border-color: var(--acc); color: var(--kort); font-weight: 600; }
  .behall { display: flex; align-items: center; gap: 7px; }
  .behall input { width: 80px; }

  .kor { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
  .status { font-size: 12.5px; color: var(--t-mut); }
  .status.ok { color: var(--ok); }
  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
