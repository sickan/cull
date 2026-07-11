<script>
  import { onMount } from 'svelte'
  import { snabbplockKortrot, valjMapp, listaMinnesKort } from '../lib/api.js'

  let kort = []
  let valtKort = ''
  let utMapp = ''
  let laddar = true
  let kor = false
  let status = ''
  let resultat = null

  onMount(async () => {
    const r = await listaMinnesKort()
    if (r.ok) kort = r.kort || []
    valtKort = kort[0]?.path || ''
    laddar = false
  })

  async function valjUtMapp() {
    const r = await valjMapp('Välj utgångsmapp för snabbplock')
    if (r.ok) utMapp = r.path
  }

  async function korSnabbplock() {
    if (!valtKort) return
    kor = true
    status = ''
    resultat = null
    const r = await snabbplockKortrot(valtKort, utMapp || undefined)
    kor = false
    if (r.ok) {
      status = `✓ ${r.antal} bilder kopierade till ${r.path}`
      resultat = r
    } else {
      status = r.fel || 'Fel vid snabbplock'
    }
  }
</script>

<div class="panel">
  <header><h1 class="scd">Snabbplock</h1></header>
  <p class="sub">Kopiera kameralåsta bilder från kort — fristående snabbväg för paus-fotografering.</p>

  {#if laddar}
    <p class="tom">Läser minneskort…</p>
  {:else}
    <div class="kort">
      <div class="caps">Minneskort</div>
      {#if kort.length}
        <div class="frad">
          <span class="fl">Kort</span>
          <select bind:value={valtKort}>
            {#each kort as k}
              <option value={k.path}>{k.namn} ({k.skyddade} låsta)</option>
            {/each}
          </select>
        </div>
        <div class="frad">
          <span class="fl">Utgångsmapp (opt.)</span>
          <input class="mono" bind:value={utMapp} placeholder="~/…eller lämna tomt för Snabbplock/" />
          <button class="valj" on:click={valjUtMapp}>Välj…</button>
        </div>
        <button class="btn-primary" on:click={korSnabbplock} disabled={kor || !valtKort}>
          {kor ? 'Kopierar…' : 'Kör snabbplock'}
        </button>
        {#if status}
          <p class={resultat?.ok ? 'status-ok' : 'status-err'}>{status}</p>
        {/if}
      {:else}
        <p class="tom">Inget minneskort monterat. Sätt in kortet och försök igen.</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .panel { padding: 1rem; }
  header { margin-bottom: 1rem; }
  .caps { font-size: 0.75rem; font-weight: 600; opacity: 0.6; text-transform: uppercase; margin-bottom: 0.5rem; }
  .sub { opacity: 0.7; margin-bottom: 1rem; }
  .kort { border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; }
  .frad { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.75rem; }
  .fl { min-width: 100px; font-size: 0.9rem; }
  input, select { flex: 1; padding: 0.5rem; border: 1px solid var(--border); border-radius: 0.25rem; font-size: 0.9rem; }
  .valj { padding: 0.5rem 1rem; cursor: pointer; }
  .btn-primary { width: 100%; padding: 0.75rem; background: var(--accent); color: var(--text); border: none; border-radius: 0.25rem; cursor: pointer; font-weight: 600; margin-top: 1rem; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .status-ok { color: var(--success); margin-top: 1rem; }
  .status-err { color: var(--error); margin-top: 1rem; }
  .tom { opacity: 0.6; font-style: italic; }
</style>
