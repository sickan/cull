<script>
  import { createEventDispatcher, onMount } from 'svelte'
  import { aktivMatch, listaLag } from './api.js'
  import { loggor, begarLogga } from './loggacache.js'

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
  function loggaForLag(namn) { return lagAlla.find((x) => x.namn === namn)?.logga || '' }
  // Loggor visas som data-URI ($loggor måste synas i uttrycket för att spåras).
  $: hemLoggaPath = loggaForLag(match?.lag_hemma)
  $: bortaLoggaPath = loggaForLag(match?.lag_borta)
  $: { begarLogga(hemLoggaPath); begarLogga(bortaLoggaPath) }
  $: hemLoggaUri = !hemLoggaPath ? '' : (/^(data:|https?:)/.test(hemLoggaPath) ? hemLoggaPath : ($loggor[hemLoggaPath] || ''))
  $: bortaLoggaUri = !bortaLoggaPath ? '' : (/^(data:|https?:)/.test(bortaLoggaPath) ? bortaLoggaPath : ($loggor[bortaLoggaPath] || ''))
</script>

{#if !laddar}
  {#if match}
    <div class="amrad">
      <span class="amcaps">Aktiv match</span>
      <span class="ambrickor">
        <span class="ambricka" style={brickStil(fargForLag(match.lag_hemma))}>{#if hemLoggaUri}<img src={hemLoggaUri} alt="" />{:else}{initialer(match.lag_hemma)}{/if}</span>
        <span class="ambricka away" style={brickStil(fargForLag(match.lag_borta))}>{#if bortaLoggaUri}<img src={bortaLoggaUri} alt="" />{:else}{initialer(match.lag_borta)}{/if}</span>
      </span>
      <div class="aminfo">
        <span class="amfix scd">{match.lag_hemma} – {match.lag_borta}</span>
        <span class="amsub">{[match.liga, datumTxt(match.datum), match.resultat].filter(Boolean).join(' · ')}</span>
      </div>
      <div class="amknappar">
        {#if match.galleri}<a class="ampill" href={match.galleri} target="_blank" rel="noreferrer">Pixieset</a>{/if}
        {#if match.sida_url}<a class="ampill" href={match.sida_url} target="_blank" rel="noreferrer">På hemsidan</a>{/if}
        <button class="ampill prim" on:click={bytMatch}>Byt match</button>
      </div>
    </div>
  {:else}
    <div class="amtom">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--t-mut)" stroke-width="1.7"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
      <div class="amtomtxt">Ingen aktiv match — stegen fungerar ändå, men koppla en match för genvägar och auto-ifyllnad.</div>
      <button class="amtombtn" on:click={bytMatch}>Välj match i Matcher ›</button>
    </div>
  {/if}
{/if}

<style>
  .amrad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; background: var(--kort); border: 1px solid var(--div);
    border-left: 3px solid var(--hav); border-radius: 10px; box-shadow: var(--skugga); padding: 6px 12px; margin-bottom: 12px; }
  .amcaps { font-size: 9.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--t-caps); flex: none; }
  .ambrickor { display: flex; align-items: center; flex: none; }
  .ambricka { width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
    font-family: var(--font-c); font-size: 9px; font-weight: 700; border: 2px solid var(--kort); overflow: hidden; }
  .ambricka img { width: 100%; height: 100%; object-fit: contain; }
  .ambricka.away { margin-left: -7px; }
  .aminfo { flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 8px; white-space: nowrap; overflow: hidden; }
  .amfix { font-size: 13px; font-weight: 600; color: var(--t-head); flex: none; }
  .amsub { font-size: 11px; color: var(--t-mut); overflow: hidden; text-overflow: ellipsis; }
  .amknappar { display: flex; align-items: center; gap: 7px; flex: none; flex-wrap: wrap; }
  .ampill { display: inline-flex; align-items: center; padding: 3px 9px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--panel); color: var(--t-mut); font-size: 11px; font-weight: 600; text-decoration: none; }
  .ampill:hover { border-color: var(--acc); color: var(--acc); }
  .ampill.prim { color: var(--acc); border-color: var(--acc-border); background: var(--kort); }

  .amtom { display: flex; align-items: center; gap: 12px; background: var(--panel); border: 1px dashed var(--div);
    border-radius: 11px; padding: 10px 14px; margin-bottom: 12px; }
  .amtom svg { flex: none; }
  .amtomtxt { flex: 1; min-width: 0; font-size: 12.5px; color: var(--t-mut); }
  .amtombtn { flex: none; background: var(--acc); color: var(--ink); border: none; border-radius: 7px;
    padding: 6px 12px; font-size: 12px; font-weight: 600; }
</style>
