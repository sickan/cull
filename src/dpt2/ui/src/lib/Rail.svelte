<script>
  import { createEventDispatcher } from 'svelte'
  import logoHast from './assets/logo-hast.png'
  import { bokstaverad } from './version.js'
  export let aktiv = 'matcher'
  export let delvis = false        // minst ett material är "Delvis publicerad"
  const dispatch = createEventDispatcher()
  // V2-01: versionen kommer ur src/dpt2/__init__.py via vite — aldrig hårdkodad
  // här (raden sa 'v4.0' medan paketet sa något annat). Byggnummer/commit
  // ligger i Inställningar → Om, inte i naven.
  const versionsord = bokstaverad()

  // Nav-ikoner — extraherade EXAKT ur Designs prototyp (v5-snabb, 17px linje,
  // stroke-width 1.7, currentColor så de följer postens text/accentfärg). De
  // numrerade "Efter jobb"-posterna behåller nummer-märket (som mockupen);
  // Upprätning finns inte i mockupen → crop-ikon i samma stil.
  const IK = {
    idag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6.5 13a5.5 5.5 0 0 1 11 0"/><path d="M2.5 17.5h19M5.5 21h13M12 4V2M5 6.5 3.6 5.1M19 6.5l1.4-1.4"/></svg>',
    fotojobb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/><path d="M12 12.5v2.4l1.7 1.1"/></svg>',
    eventsektion: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3.5l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.2l5.4-.8z"/></svg>',
    lag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3l7 2.5v5c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9v-5z"/></svg>',
    snabbplock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M13 2L4.5 13.5H11L10 22l8.5-11.5H12z"/></svg>',
    upprattning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 2v14a2 2 0 0 0 2 2h14M2 6h14a2 2 0 0 1 2 2v14"/></svg>',
    innehall: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.6 2.6 15.4 0 18M12 3c-2.6 2.6-2.6 15.4 0 18"/></svg>',
    pagang: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17"/><path d="M7.5 13.5h5M7.5 16.5h8"/></svg>',
    logg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="2.6" y="4.5" width="18.8" height="15" rx="2.4"/><path d="M6.5 9.5l3 2.6-3 2.6M12.5 15h4.5"/></svg>',
    installningar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2L5.5 5.5"/></svg>',
  }

  const grupper = [
    { rubrik: 'Planera', poster: [
      { id: 'fotojobb', namn: 'Fotojobb' },
      // D17 (approach A): Matcher är inte längre en egen navpost — den nås som
      // segment "Alla jobb / Matcher" inifrån Fotojobb.
      { id: 'eventsektion', namn: 'Tävlingar' },          // V5-C (handoff §2); D11b §1: 'Event' försvinner ur UI
      { id: 'lag', namn: 'Lag & utövare' },               // D16 §A: ETT register (Utövare-posten borttagen; ligor bor i Tävlingar)
    ] },
    // §8 (UX-lyftet): jobbet som nav — "Efter jobb" + "Publicera" (inte
    // match-specifikt); §9: Träna har lämnat naven (tyst träning + rad i
    // Inställningar), gamla panelen nås därifrån.
    { rubrik: 'Efter jobb', poster: [
      { id: 'gallra', namn: 'Gallra', nr: 1 },
      { id: 'leverera', namn: 'Leverera', nr: 2 },
      { id: 'snabbplock', namn: 'Snabbplock' },
      { id: 'upprattning', namn: 'Upprätning' },
      { id: 'publicera', namn: 'Publicera', nr: 3 },
    ] },
    { rubrik: 'Webb', poster: [
      { id: 'innehall', namn: 'Innehåll' },
      { id: 'pagang', namn: 'På gång' },
    ] },
    { rubrik: 'System', poster: [
      { id: 'logg', namn: 'Logg' },
      { id: 'installningar', namn: 'Inställningar' },
    ] },
  ]
</script>

<nav>
  <div class="brand">
    <img class="mark" src={logoHast} alt="" />
    <div class="ord scd">Dalecarlia Photo Tools<span>{versionsord}</span></div>
  </div>
  <!-- D16 §C: "Idag" är en egen toppnivå ovanför Planera (kommandobryggan). -->
  <button class="post topp" class:aktiv={aktiv === 'idag'} on:click={() => dispatch('valj', 'idag')}>
    <span class="navik">{@html IK.idag}</span>
    <span>Idag</span>
  </button>
  {#each grupper as g}
    <div class="rubrik">{g.rubrik}</div>
    {#each g.poster as p}
      <button class="post" class:aktiv={aktiv === p.id} on:click={() => dispatch('valj', p.id)}>
        {#if p.nr}
          <span class="nr">{p.nr}{#if p.id === 'publicera' && delvis}<span class="dot" title="Delvis publicerat material väntar"></span>{/if}</span>
        {:else if IK[p.id]}
          <span class="navik">{@html IK[p.id]}</span>
        {/if}
        <span>{p.namn}</span>
      </button>
    {/each}
  {/each}
</nav>

<style>
  nav {
    width: 216px; flex: none; height: 100%; overflow-y: auto;
    background: var(--panel); border-right: 1px solid var(--div);
    padding: 14px 12px 24px;
  }
  .brand { display: flex; align-items: center; gap: 9px; padding: 6px 8px 4px; }
  .mark { width: 26px; height: 26px; flex: none; object-fit: contain; }
  .ord { font-weight: 700; font-size: 15px; color: var(--t-head); line-height: 1.05;
    display: flex; flex-direction: column; }
  .ord span { font-family: var(--font); font-weight: 600; font-size: 9px;
    letter-spacing: 0.22em; text-transform: uppercase; color: var(--acc); margin-top: 3px; }
  .rubrik {
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--t-caps); padding: 16px 10px 6px;
  }
  .post {
    display: flex; align-items: center; gap: 9px; width: 100%;
    padding: 8px 10px; border: 0; border-radius: 9px; background: transparent;
    color: var(--t-mut); font-size: 13.5px; font-weight: 500; text-align: left;
    transition: background 0.12s, color 0.12s;
  }
  .post:hover { background: var(--div3); color: var(--t-head); }
  .post.aktiv { background: var(--acc-soft); color: var(--acc); font-weight: 600; }
  .post.topp { margin-top: 10px; }
  .nr {
    width: 18px; height: 18px; flex: none; border-radius: 5px;
    background: var(--div3); color: var(--t-mut);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; position: relative;
  }
  .post.aktiv .nr { background: var(--acc); color: var(--kort); }
  /* Nav-ikoner (Design v5): 17px linje, ärver postens färg via currentColor. */
  .navik { width: 18px; height: 18px; flex: none; display: inline-flex;
    align-items: center; justify-content: center; opacity: 0.85; }
  .post.aktiv .navik { opacity: 1; }
  .navik :global(svg) { width: 17px; height: 17px; }
  .dot {
    position: absolute; top: -3px; right: -3px; width: 9px; height: 9px;
    border-radius: 50%; background: #B0483A; box-shadow: 0 0 0 2px var(--panel);
  }
</style>
