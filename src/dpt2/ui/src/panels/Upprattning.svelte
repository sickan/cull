<script>
  import { onMount } from 'svelte'
  import { rataUppMappBakgrund, uppratStatus, valjMapp } from '../lib/api.js'

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

  // Vinkelräkningen (preview-extraktion + Hough per raw) tar minuter för en
  // matchmapp — bakgrundstråd + poll driver progressbaren.
  let prog = null
  async function korUppratning() {
    if (!valtMapp) return
    kor = true; status = ''; resultat = null; prog = null
    const start = await rataUppMappBakgrund(valtMapp)
    if (!start?.ok) { kor = false; status = start?.fel || 'Kunde inte starta.'; return }
    const poll = setInterval(async () => {
      const st = await uppratStatus().catch(() => null)
      if (!st) return
      prog = { fas: st.fas, klara: st.klara, totalt: st.totalt }
      if (!st.pagar) {
        clearInterval(poll)
        kor = false; prog = null
        const r = st.resultat || {}
        if (r.ok) {
          status = `✓ ${r.meddelande || `${r.n_skriv}/${r.n_raw} sidecars skrivna`}`
          resultat = r
        } else {
          status = r.fel || 'Fel vid upprätning'
        }
      }
    }, 400)
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
      {kor ? (prog?.totalt ? `${prog.fas} ${prog.klara}/${prog.totalt}…` : 'Räknar…') : 'Kör upprätning'}
    </button>
    {#if kor && prog?.totalt}
      <div class="uprog">
        <div class="ubar"><div class="ufyll" style="width:{Math.round(prog.klara / prog.totalt * 100)}%"></div></div>
        <span class="utxt">{prog.klara}/{prog.totalt}</span>
      </div>
    {/if}
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
  .uprog { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .ubar { flex: 1; height: 6px; border-radius: 4px; background: var(--div3); overflow: hidden; }
  .ufyll { height: 100%; background: var(--acc); border-radius: 4px; transition: width 0.3s; }
  .utxt { font-size: 11px; color: var(--t-mut); white-space: nowrap; font-variant-numeric: tabular-nums; }
</style>
