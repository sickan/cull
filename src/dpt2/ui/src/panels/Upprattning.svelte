<script>
  import { onMount } from 'svelte'
  import { rataUppMapp, valjMapp } from '../lib/api.js'

  let valtMapp = ''
  let laddar = true
  let kor = false
  let status = ''
  let resultat = null

  onMount(async () => {
    laddar = false
  })

  async function valjRawMapp() {
    const r = await valjMapp('Välj mapp med raw-filer för upprätning')
    if (r.ok) valtMapp = r.path
  }

  async function korUppratning() {
    if (!valtMapp) return
    kor = true
    status = ''
    resultat = null
    const r = await rataUppMapp(valtMapp)
    kor = false
    if (r.ok) {
      status = `✓ XMP-sidecars skrivna för ${r.n_skriv}/${r.n_raw} raw-filer`
      resultat = r
    } else {
      status = r.fel || 'Fel vid upprätning'
    }
  }
</script>

<div class="panel">
  <header><h1 class="scd">Upprätning</h1></header>
  <p class="sub">Skriver XMP-sidecars för Lightroom-upprätning — ej förstörande, betyg & etiketter bevaras.</p>

  <div class="mapp">
    <div class="caps">Mapp med raw-filer</div>
    <div class="frad">
      <input class="mono" bind:value={valtMapp} placeholder="~/…välj en mapp" />
      <button class="valj" on:click={valjRawMapp}>Välj…</button>
    </div>
    <button class="btn-primary" on:click={korUppratning} disabled={kor || !valtMapp}>
      {kor ? 'Skriver…' : 'Kör upprätning'}
    </button>
    {#if status}
      <p class={resultat?.ok ? 'status-ok' : 'status-err'}>{status}</p>
    {/if}
  </div>
</div>

<style>
  .panel { padding: 1rem; }
  header { margin-bottom: 1rem; }
  .caps { font-size: 0.75rem; font-weight: 600; opacity: 0.6; text-transform: uppercase; margin-bottom: 0.5rem; }
  .sub { opacity: 0.7; margin-bottom: 1rem; }
  .mapp { border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; }
  .frad { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.75rem; }
  input { flex: 1; padding: 0.5rem; border: 1px solid var(--border); border-radius: 0.25rem; font-size: 0.9rem; }
  .valj { padding: 0.5rem 1rem; cursor: pointer; }
  .btn-primary { width: 100%; padding: 0.75rem; background: var(--accent); color: var(--text); border: none; border-radius: 0.25rem; cursor: pointer; font-weight: 600; margin-top: 1rem; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .status-ok { color: var(--success); margin-top: 1rem; }
  .status-err { color: var(--error); margin-top: 1rem; }
</style>
