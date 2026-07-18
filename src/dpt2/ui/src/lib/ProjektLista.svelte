<script>
  // F18-8: "Tidigare projekt" som KOMPAKTA listrader i stället för stora kort
  // — sex kort fyllde en skärm. En rad per MATCH (senaste körningen vinner,
  // antalet körningar visas som badge — dubbletterna grupperas i stället för
  // att radas upp), 3 senaste + "Visa alla", relativ tid ("igår 21:30").
  import { createEventDispatcher } from 'svelte'
  const dispatch = createEventDispatcher()

  export let projekt = []

  let visaAlla = false

  $: grupper = gruppera(projekt)
  $: synliga = visaAlla ? grupper : grupper.slice(0, 3)

  function gruppera(lista) {
    const per = new Map()
    const sorterad = [...lista].sort((a, b) => (b.skapad || '').localeCompare(a.skapad || ''))
    for (const pr of sorterad) {
      const nyckel = pr.match_id || pr.kalla || pr.id
      if (!per.has(nyckel)) per.set(nyckel, { senaste: pr, antal: 0 })
      per.get(nyckel).antal += 1
    }
    return [...per.values()]
  }

  // "igår 21:30" / "i dag 09:12" / "12 jul" — ISO-stämpeln var ren brus.
  const MAN = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function relTid(s) {
    const d = new Date((s || '').replace(' ', 'T'))
    if (isNaN(d)) return s || ''
    const nu = new Date()
    const idag = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate())
    const dag = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diff = Math.round((idag - dag) / 86400000)
    const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    if (diff === 0) return `i dag ${hm}`
    if (diff === 1) return `igår ${hm}`
    return `${d.getDate()} ${MAN[d.getMonth()]}`
  }

  const namn = (pr) => pr.lag_hemma ? `${pr.lag_hemma} – ${pr.lag_borta}` : (pr.kalla || 'Urval').split('/').pop()
</script>

{#if grupper.length}
  <div class="plista">
    {#each synliga as g (g.senaste.id)}
      <button class="prad" on:click={() => dispatch('ateruppta', g.senaste)}>
        <span class="pinit scd">{(namn(g.senaste) || '?').slice(0, 2).toUpperCase()}</span>
        <span class="pnamn">{namn(g.senaste)}</span>
        <span class="pmeta">{[g.senaste.bilder ? `${g.senaste.bilder} bilder` : '', g.senaste.status,
          relTid(g.senaste.skapad)].filter(Boolean).join(' · ')}</span>
        {#if g.antal > 1}<span class="pfler" title="{g.antal} körningar på samma match — senaste visas">{g.antal}×</span>{/if}
        <span class="pater">Återuppta ›</span>
      </button>
    {/each}
    {#if grupper.length > 3}
      <button class="pvisa" on:click={() => (visaAlla = !visaAlla)}>
        {visaAlla ? 'Visa färre' : `Visa alla (${grupper.length})`}</button>
    {/if}
  </div>
{/if}

<style>
  .plista { display: flex; flex-direction: column; gap: 6px; }
  .prad { display: flex; align-items: center; gap: 11px; width: 100%; text-align: left;
    padding: 8px 12px; border: 1px solid var(--div); border-radius: 10px;
    background: var(--kort); cursor: pointer; }
  .prad:hover { border-color: var(--acc-border); }
  .pinit { width: 34px; height: 34px; border-radius: 8px; flex: none;
    background: var(--acc-soft); color: var(--acc); display: inline-flex;
    align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
  .pnamn { font-size: 13px; font-weight: 600; color: var(--t-head); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .pmeta { flex: 1; min-width: 0; font-size: 11px; color: var(--t-mut); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .pfler { flex: none; font-size: 10px; font-weight: 700; color: var(--t-mut);
    background: var(--div3); border-radius: 999px; padding: 2px 8px; }
  .pater { flex: none; font-size: 11.5px; font-weight: 600; color: var(--acc); white-space: nowrap; }
  .pvisa { align-self: flex-start; border: none; background: none; padding: 4px 2px;
    font-size: 12px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .pvisa:hover { color: var(--t-head); }
</style>
