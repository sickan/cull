<script>
  import { createEventDispatcher, onMount } from 'svelte'
  import { aktivMatch, listaLag } from './api.js'

  const dispatch = createEventDispatcher()
  const bytMatch = () => dispatch('navigera', 'matcher')

  let match = null
  let lagAlla = []
  let laddar = true

  onMount(async () => {
    ;[match, lagAlla] = await Promise.all([aktivMatch(), listaLag()])
    laddar = false
  })

  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function datumTxt(iso) {
    const d = (iso || '').split('-').map(Number)
    return d.length === 3 ? `${d[2]} ${MK[d[1] - 1]}` : ''
  }
  function initialer(namn) { return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 3).toUpperCase() }
  function _lum(hex) {
    const h = (hex || '').replace('#', ''); if (h.length < 3) return 1
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
    return (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  }
  const brickStil = (f) => `background:${f || '#c9bfa8'};color:${_lum(f || '#c9bfa8') > 0.62 ? 'rgba(35,32,26,.85)' : '#fff'}`
  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }
</script>

{#if !laddar}
  <div class="amrad" class:tom={!match}>
    {#if match}
      <span class="ambrickor">
        <span class="ambricka" style={brickStil(fargForLag(match.lag_hemma))}>{initialer(match.lag_hemma)}</span>
        <span class="ambricka away" style={brickStil(fargForLag(match.lag_borta))}>{initialer(match.lag_borta)}</span>
      </span>
      <div class="aminfo">
        <div class="amkick">Aktiv match</div>
        <div class="amfix scd">{match.lag_hemma} – {match.lag_borta}</div>
        <div class="amsub">{[match.liga, datumTxt(match.datum), match.resultat].filter(Boolean).join(' · ')}</div>
      </div>
      <div class="amknappar">
        {#if match.galleri}<a class="ampill" href={match.galleri} target="_blank" rel="noreferrer">Pixieset</a>{/if}
        {#if match.sida_url}<a class="ampill" href={match.sida_url} target="_blank" rel="noreferrer">På hemsidan</a>{/if}
        <button class="ampill prim" on:click={bytMatch}>Byt match</button>
      </div>
    {:else}
      <div class="aminfo">
        <div class="amfix scd">Ingen aktiv match</div>
        <div class="amsub">Välj match i Matcher så följer den med genom Gallra, Leverera och Publicera</div>
      </div>
      <button class="ampill prim" on:click={bytMatch}>Välj match i Matcher ›</button>
    {/if}
  </div>
{/if}

<style>
  .amrad { display: flex; align-items: center; gap: 14px; background: var(--kort); border: 1px solid var(--div);
    border-left: 3px solid var(--hav); border-radius: var(--r); box-shadow: var(--skugga); padding: 12px 16px; margin-bottom: 16px; }
  .amrad.tom { border-left-color: var(--div); }
  .ambrickor { display: flex; align-items: center; flex: none; }
  .ambricka { width: 34px; height: 34px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
    font-family: var(--font-c); font-size: 12px; font-weight: 700; border: 2px solid var(--kort); }
  .ambricka.away { margin-left: -10px; }
  .aminfo { flex: 1; min-width: 0; }
  .amkick { font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-mut); }
  .amfix { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .amsub { font-size: 12px; color: var(--t-mut); margin-top: 1px; }
  .amknappar { display: flex; align-items: center; gap: 8px; flex: none; }
  .ampill { display: inline-flex; align-items: center; padding: 7px 14px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--panel); color: var(--t-head); font-size: 12.5px; font-weight: 600; text-decoration: none; }
  .ampill:hover { border-color: var(--acc); color: var(--acc); }
  .ampill.prim { color: var(--acc); border-color: var(--acc-border); background: var(--acc-soft); }
</style>
