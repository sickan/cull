<script>
  // Månadsvy: översikt, inte arbetsyta. Jobb som rader, privata poster som en
  // färgprick per KÄLLA (inte per post) — cellen ska säga "det finns något här",
  // inte vad. Krockdagar får röd ram och ett utropstecken, plus en räknare.
  // Klick på en dag borrar ner i veckovyn.
  import { createEventDispatcher } from 'svelte'
  import { jobbSpann, privatSpann, kalenderFarg } from './privat.js'
  import { mandagen, addDagar, midnatt, dygnSpann, overlappar, VECKODAG_KORT, MANAD_NAMN } from './vydatum.js'

  export let jobb = []
  export let privata = []       // källfiltrerade (visning)
  export let kalendrar = []
  export let krockar = new Map()
  export let katFarg = () => '#888'
  export let ankare = new Date()

  const dispatch = createEventDispatcher()
  const idagNyckel = new Date().toDateString()

  $: forsta = new Date(ankare.getFullYear(), ankare.getMonth(), 1)
  $: rutStart = mandagen(forsta)
  $: rubrik = `${MANAD_NAMN[forsta.getMonth()]} ${forsta.getFullYear()}`

  // Sex veckor täcker varje möjlig månadsplacering. Dagar utanför månaden ritas
  // dämpade i stället för att lämnas tomma — annars hoppar rutnätet mellan månader.
  $: celler = Array.from({ length: 42 }, (_, i) => bygg(addDagar(rutStart, i)))
  $: krockdagar = celler.filter((c) => c.iManaden && c.krock).length

  function bygg(dag) {
    const dygn = dygnSpann(dag)
    const dagJobb = jobb.filter((j) => overlappar(...jobbSpann(j), ...dygn))
    // En dag är en krockdag bara om BÅDA parterna ligger den dagen. Annars hade
    // en veckolång fotoresa färgat varenda dag röd så fort den krockade en gång.
    const krock = dagJobb.some((j) =>
      (krockar.get(j.id) || []).some((p) => overlappar(...privatSpann(p), ...dygn)))
    const kallor = [...new Set(privata.filter((p) => overlappar(...privatSpann(p), ...dygn))
      .map((p) => p.kalender_id))]
    return {
      dag, dagJobb, krock, kallor,
      iManaden: dag.getMonth() === forsta.getMonth(),
      idag: dag.toDateString() === idagNyckel,
    }
  }
  const navigera = (n) => (ankare = new Date(ankare.getFullYear(), ankare.getMonth() + n, 1))
</script>

<div class="manadsvy">
  <div class="mhuvud">
    <button class="nav" on:click={() => navigera(-1)} aria-label="Föregående månad">‹</button>
    <span class="mrubrik scd">{rubrik}</span>
    <button class="nav" on:click={() => navigera(1)} aria-label="Nästa månad">›</button>
    {#if krockdagar}
      <span class="krockrakning">⚠ {krockdagar} {krockdagar === 1 ? 'krockdag' : 'krockdagar'} den här månaden</span>
    {/if}
    <button class="nav idag" on:click={() => (ankare = new Date())}>Denna månad</button>
  </div>

  <div class="veckodagar">
    {#each VECKODAG_KORT as v}<div class="vd scd">{v}</div>{/each}
  </div>

  <div class="rutnat">
    {#each celler as c (c.dag.toDateString())}
      <button class="cell" class:utanfor={!c.iManaden} class:krock={c.krock} class:idag={c.idag}
        on:click={() => dispatch('visaVecka', c.dag)}>
        <div class="chuvud">
          <span class="cnr">{c.dag.getDate()}</span>
          {#if c.krock}<span class="utrop" title="Krockar med privat kalender">!</span>{/if}
          <span class="prickar">
            {#each c.kallor as k (k)}<span class="prick" style="background:{kalenderFarg(kalendrar, k)}"></span>{/each}
          </span>
        </div>
        {#each c.dagJobb.slice(0, 3) as j (j.id)}
          <div class="jrad" style="--f:{katFarg(j.category)}"><span class="jprick"></span>{j.title}</div>
        {/each}
        {#if c.dagJobb.length > 3}<div class="fler">+{c.dagJobb.length - 3} till</div>{/if}
      </button>
    {/each}
  </div>
</div>

<style>
  .manadsvy { display: flex; flex-direction: column; gap: 10px; }
  .mhuvud { display: flex; align-items: center; gap: 8px; }
  .mrubrik { font-size: 14px; font-weight: 700; color: var(--t-head); letter-spacing: 0.04em;
    text-transform: capitalize; min-width: 130px; }
  .nav { border: 1px solid var(--div); background: var(--kort); border-radius: 8px; padding: 5px 11px;
    font-size: 13px; color: var(--t-mut); }
  .nav:hover { border-color: var(--acc); color: var(--acc); }
  .nav.idag { margin-left: auto; font-size: 12.5px; font-weight: 600; }
  .krockrakning { margin-left: 10px; padding: 3px 10px; border-radius: 999px; font-size: 11.5px;
    font-weight: 700; color: var(--krock); background: var(--krock-soft); border: 1px solid var(--krock); }

  .veckodagar { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; padding: 0 1px; }
  .vd { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps);
    text-align: center; padding-bottom: 2px; }

  .rutnat { display: grid; grid-template-columns: repeat(7, 1fr); grid-auto-rows: minmax(92px, auto);
    gap: 1px; background: var(--div3); border: 1px solid var(--div); }
  .cell { display: flex; flex-direction: column; gap: 3px; align-items: stretch; text-align: left;
    background: var(--panel); border: 0; padding: 6px; cursor: pointer; }
  .cell:hover { background: var(--div3); }
  /* Utanför månaden: dämpa ramen/siffran, aldrig texten (AA-golvet i tokens). */
  .cell.utanfor .cnr { color: var(--t-caps); }
  .cell.utanfor { background: var(--sand); }
  .cell.idag .cnr { color: var(--acc); font-weight: 700; }
  /* Röd ram INUTI cellen (box-shadow), annars flyttar en 2px-ram rutnätet 2px. */
  .cell.krock { box-shadow: inset 0 0 0 1.5px var(--krock); }

  .chuvud { display: flex; align-items: center; gap: 5px; }
  .cnr { font-size: 12.5px; font-weight: 600; color: var(--t-head); font-variant-numeric: tabular-nums; }
  .utrop { font-size: 11px; font-weight: 800; color: var(--krock); line-height: 1; }
  .prickar { margin-left: auto; display: flex; gap: 3px; }
  .prick { width: 7px; height: 7px; border-radius: 2px; }

  .jrad { display: flex; align-items: center; gap: 5px; font-size: 10.5px; color: var(--t-body);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .jprick { width: 5px; height: 5px; border-radius: 50%; background: var(--f); flex: none; }
  .fler { font-size: 10px; color: var(--t-help); }
</style>
