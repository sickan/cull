<script>
  // D11b §4: synk-märket i titelraden. Samma plats, fyra lägen. Klick pushar nu
  // (behövs normalt bara i fel-läget); hover visar liten logg (senast pushat).
  import { livesynk, synka } from './livesynk.js'
  let visaLogg = false
  const ETIKETT = { uppe: 'Allt uppe', synkar: 'Synkar…', fel: 'Synkfel' }
  const tid = (iso) => iso
    ? new Date(iso).toLocaleTimeString('sv', { hour: '2-digit', minute: '2-digit' })
    : '—'
  function klick() { if ($livesynk.lage !== 'synkar') synka() }
</script>

<button class="synkmarke {$livesynk.lage}" on:click={klick}
  on:mouseenter={() => (visaLogg = true)} on:mouseleave={() => (visaLogg = false)}
  title="Synk till telefonen — klicka för att pusha nu">
  <span class="prick" class:snurr={$livesynk.lage === 'synkar'}></span>
  <span class="txt">{$livesynk.lage === 'vantar'
    ? `${$livesynk.antal} väntar` : ETIKETT[$livesynk.lage]}</span>
  {#if visaLogg}
    <span class="logg">{$livesynk.fel || `Senast pushat: ${tid($livesynk.senast)}`}</span>
  {/if}
</button>

<style>
  .synkmarke { position: relative; display: inline-flex; align-items: center; gap: 7px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    padding: 5px 12px; font-family: inherit; font-size: 12px; font-weight: 600;
    color: var(--t-mut); cursor: pointer; }
  .prick { width: 8px; height: 8px; border-radius: 50%; background: var(--t-mut); flex: none; }
  .uppe .prick   { background: #6FB35A; }
  .vantar .prick { background: #E0A341; }
  .synkar .prick { background: #6E8AA8; }
  .fel .prick    { background: #E07A6E; }
  .uppe   { color: #6FB35A; }
  .vantar { color: #E0A341; }
  .synkar { color: #6E8AA8; }
  .fel    { color: #E07A6E; border-color: #E07A6E; }
  .prick.snurr { animation: puls 1s ease-in-out infinite; }
  @keyframes puls { 50% { opacity: .35; } }
  .logg { position: absolute; top: calc(100% + 6px); right: 0; white-space: nowrap;
    background: var(--panel); border: 1px solid var(--div); border-radius: 8px;
    padding: 5px 10px; font-size: 11px; font-weight: 400; color: var(--t-help);
    z-index: 20; box-shadow: 0 4px 14px rgba(0,0,0,.12); }
</style>
