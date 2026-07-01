<script>
  import { onMount } from 'svelte'
  import { listaUrval, levereraUrval, startaNummer, valjMapp } from '../lib/api.js'

  let urval = []
  let mal = null                // urvalet som levereras (senaste gallrade)
  let laddar = true
  let levererar = false
  let nummerKor = false
  let status = ''
  let nummerStatus = ''

  let cfg = { exportRot: '', fotograf: 'Stig Johansson – Dalecarlia Photo AB',
    iptc: true, oppnaI: 'Lightroom', husstil: '(ingen)', expKnuff: '0.5' }

  onMount(async () => {
    urval = await listaUrval()
    mal = urval.find((u) => u.status === 'gallrad') || urval[0] || null
    laddar = false
  })

  const urvalLabel = (u) => !u ? '' : (u.lag_hemma ? `${u.lag_hemma} – ${u.lag_borta}` : (u.kalla || '').split('/').pop())

  async function valjRot() {
    const r = await valjMapp('Välj export-rot')
    if (r.ok) cfg.exportRot = r.path
  }
  async function levereraNu() {
    if (!mal) return
    levererar = true; status = ''
    const r = await levereraUrval(mal.id, cfg)
    levererar = false
    status = r.ok ? (r.skrivna ? `${r.skrivna} sidecars skrivna.` : 'Levererat.') : (r.fel || 'Fel vid leverans.')
    if (r.ok) { mal = { ...mal, status: 'levererad' } }
  }
  async function korNummer() {
    if (!mal) return
    nummerKor = true; nummerStatus = ''
    const r = await startaNummer(mal.id)
    nummerKor = false
    nummerStatus = r.ok ? (r.meddelande || 'Tröjnummer skrivna.') : (r.fel || 'Fel.')
  }
</script>

<div class="panel">
  <header><h1 class="scd">Leverera</h1></header>
  <p class="sub">Exportera urvalet med metadata, husstil och tröjnummer.</p>

  {#if laddar}
    <p class="tom">Laddar…</p>
  {:else}
    {#if mal}
      <div class="urvalrad">Urval: <b>{urvalLabel(mal)}</b> · {mal.bilder} bilder · <span class="st">{mal.status}</span></div>
    {:else}
      <div class="urvalrad tom">Inget urval att leverera — gallra en match först.</div>
    {/if}

    <div class="grid2">
      <div class="kort">
        <div class="caps">Export</div>
        <div class="frad"><span class="fl">Export-rot</span>
          <input class="mono" bind:value={cfg.exportRot} placeholder="/Volumes/…" />
          <button class="valj" on:click={valjRot}>Välj…</button>
        </div>
        <div class="frad"><span class="fl">Fotograf</span><input bind:value={cfg.fotograf} /></div>
        <button class="chk" on:click={() => (cfg.iptc = !cfg.iptc)}>
          <span class="box" class:pa={cfg.iptc}>{cfg.iptc ? '✓' : ''}</span> IPTC-bildtexter
        </button>
      </div>

      <div class="kort">
        <div class="caps">Efterbehandling</div>
        <div class="frad"><span class="fl2">Öppna i</span>
          <select bind:value={cfg.oppnaI}><option>Lightroom</option><option>Capture One</option></select>
        </div>
        <div class="frad"><span class="fl2">Husstil</span>
          <select bind:value={cfg.husstil}><option>(ingen)</option><option>Sport varm</option><option>Sport neutral</option></select>
        </div>
        <div class="frad"><span class="fl2">Exp-knuff</span><input class="liten" bind:value={cfg.expKnuff} /><span class="ev">EV</span></div>
      </div>
    </div>

    <div class="nummerkort">
      <span class="hash">#</span>
      <div class="ntxt">
        <div class="nt">Läs nummer</div>
        <div class="ns">OCR av tröjnummer på urvalet → skrivs som keywords i Lightroom</div>
      </div>
      {#if nummerStatus}<span class="nstat">{nummerStatus}</span>{/if}
      <button class="sek" on:click={korNummer} disabled={nummerKor || !mal}>{nummerKor ? 'Kör…' : 'Kör'}</button>
    </div>

    <div class="levrad">
      {#if status}<span class="ok">✓ {status}</span>{/if}
      <button class="prim" on:click={levereraNu} disabled={levererar || !mal}>{levererar ? 'Levererar…' : 'Leverera urval ›'}</button>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 780px; }
  header { display: flex; align-items: baseline; gap: 10px; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { margin: 7px 0 16px; font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .urvalrad { font-size: 12.5px; color: var(--t-mut); margin-bottom: 14px; }
  .urvalrad b { color: var(--t-head); }
  .urvalrad .st { color: var(--acc); font-weight: 600; }
  .urvalrad.tom { color: var(--t-help); }

  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-bottom: 14px; }
  .frad { display: flex; align-items: center; gap: 8px; margin-bottom: 11px; }
  .fl { font-size: 12.5px; color: var(--t-mut); width: 72px; flex: none; }
  .fl2 { font-size: 12.5px; color: var(--t-mut); width: 78px; flex: none; }
  input, select { font-family: inherit; padding: 7px 9px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 12.5px; outline: none; flex: 1; min-width: 0; }
  input:focus, select:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .liten { flex: none; width: 60px; text-align: center; }
  .ev { font-size: 11px; color: var(--t-mut); }
  .valj { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 7px 11px; font-size: 12px; color: var(--t-mut); }
  .chk { display: flex; align-items: center; gap: 10px; border: 0; background: none; padding: 0; font-size: 13px; color: var(--t-head); }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel); color: var(--acc); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }

  .nummerkort { display: flex; align-items: center; gap: 14px; background: var(--kort); border: 1px solid var(--div);
    border-radius: var(--r); box-shadow: var(--skugga); padding: 14px 16px; margin-top: 14px; }
  .hash { width: 40px; height: 40px; border-radius: 10px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; font-size: 18px; font-weight: 700; }
  .ntxt { flex: 1; min-width: 0; }
  .nt { font-size: 14.5px; font-weight: 600; color: var(--t-head); }
  .ns { font-size: 12px; color: var(--t-mut); margin-top: 2px; }
  .nstat { font-size: 12px; color: var(--ok); font-weight: 600; }
  .sek { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 8px; padding: 9px 14px; font-size: 13px; color: var(--t-head); }
  .sek:disabled { opacity: 0.5; }

  .levrad { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 16px; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; }
</style>
