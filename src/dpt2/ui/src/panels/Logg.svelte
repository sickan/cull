<script>
  import { onMount } from 'svelte'
  import { hamtaLogg, rensaLogg, korDemoJobb } from '../lib/api.js'

  let events = []
  let kor = false
  let kopierad = false

  $: senasteProgress = [...events].reverse().find((e) => e.typ === 'progress')

  onMount(async () => { events = await hamtaLogg() })

  async function demo() {
    kor = true
    await korDemoJobb(6)
    events = await hamtaLogg()
    kor = false
  }

  async function rensa() {
    await rensaLogg()
    events = []
  }

  function radtext(e) {
    if (e.typ === 'start') return `▸ start: ${e.jobb}`
    if (e.typ === 'progress') return `  ${Math.round((e.andel || 0) * 100)}%  ${e.text || ''}`
    if (e.typ === 'klar') return `✓ klar  ${JSON.stringify(e.resultat || {})}`
    if (e.typ === 'fel') return `✗ fel: ${e.text || ''}`
    return e.text || ''
  }

  function klass(e) {
    if (e.typ === 'fel' || e.niva === 'fel') return 'fel'
    if (e.typ === 'klar' || e.niva === 'ok') return 'ok'
    if (e.typ === 'start' || e.typ === 'progress') return 'acc'
    return 'info'
  }

  async function kopiera() {
    try {
      await navigator.clipboard.writeText(events.map(radtext).join('\n'))
      kopierad = true; setTimeout(() => (kopierad = false), 1600)
    } catch (_) { /* clipboard kan saknas */ }
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Logg</h1>
    <span class="sub">Live-events från worker-processen (strukturerad IPC)</span>
  </header>

  <div class="verktyg">
    <button class="prim" on:click={demo} disabled={kor}>{kor ? 'Kör…' : 'Kör demo-jobb ›'}</button>
    <button class="sek" on:click={rensa} disabled={!events.length}>Rensa</button>
    <button class="sek" on:click={kopiera} disabled={!events.length}>{kopierad ? '✓ Kopierat' : 'Kopiera'}</button>
    {#if senasteProgress}
      <div class="bar"><div class="fill" style="width:{Math.round((senasteProgress.andel || 0) * 100)}%"></div></div>
    {/if}
  </div>

  <div class="console">
    {#if events.length === 0}
      <div class="tom">Tom konsol. Kör demo-jobbet för att se worker-event-strömmen.</div>
    {:else}
      {#each events as e}
        <div class="rad {klass(e)}">{radtext(e)}</div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }

  .verktyg { display: flex; align-items: center; gap: 10px; margin: 18px 0 12px; }
  .bar { flex: 1; height: 4px; border-radius: 999px; background: var(--div3); overflow: hidden; }
  .fill { height: 100%; background: var(--acc); transition: width 0.2s; }

  .console { background: var(--t-head); border: 1px solid var(--div); border-radius: var(--r);
    padding: 14px 16px; min-height: 280px; max-height: 56vh; overflow-y: auto;
    font-family: var(--mono, ui-monospace, monospace); font-size: 12.5px; line-height: 1.65; }
  .tom { color: color-mix(in srgb, var(--sand) 60%, transparent); }
  .rad { white-space: pre-wrap; color: color-mix(in srgb, var(--sand) 86%, transparent); }
  .rad.acc { color: #8fd0e8; }
  .rad.ok { color: #7fd99a; }
  .rad.fel { color: #f08a8a; }
  .rad.info { color: color-mix(in srgb, var(--sand) 70%, transparent); }

  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .sek:disabled { opacity: 0.5; cursor: default; }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
