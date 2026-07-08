<script>
  import { createEventDispatcher } from 'svelte'
  import logoHast from './assets/logo-hast.png'
  export let aktiv = 'matcher'
  export let delvis = false        // minst ett material är "Delvis publicerad"
  const dispatch = createEventDispatcher()
  // __BUILD_NR__ injiceras av vite.config.js (git rev-list --count HEAD vid bygget).
  const buildNr = typeof __BUILD_NR__ !== 'undefined' ? __BUILD_NR__ : '?'

  const grupper = [
    { rubrik: 'Planera', poster: [
      { id: 'fotojobb', namn: 'Fotojobb' },
      { id: 'matcher', namn: 'Matcher' },
      { id: 'lag', namn: 'Lag & tävlingar' },
    ] },
    { rubrik: 'Efter match', poster: [
      { id: 'gallra', namn: 'Gallra', nr: 1 },
      { id: 'leverera', namn: 'Leverera', nr: 2 },
      { id: 'publicera', namn: 'Matchpublicering', nr: 3 },
    ] },
    { rubrik: 'Webb', poster: [{ id: 'innehall', namn: 'Innehåll' }] },
    { rubrik: 'System', poster: [
      { id: 'trana', namn: 'Träna' },
      { id: 'logg', namn: 'Logg' },
      { id: 'installningar', namn: 'Inställningar' },
    ] },
  ]
</script>

<nav>
  <div class="brand">
    <img class="mark" src={logoHast} alt="" />
    <div class="ord scd">Dalecarlia Photo<span>Photo Tools · v3.0 · Build {buildNr}</span></div>
  </div>
  {#each grupper as g}
    <div class="rubrik">{g.rubrik}</div>
    {#each g.poster as p}
      <button class="post" class:aktiv={aktiv === p.id} on:click={() => dispatch('valj', p.id)}>
        {#if p.nr}
          <span class="nr">{p.nr}{#if p.id === 'publicera' && delvis}<span class="dot" title="Delvis publicerat material väntar"></span>{/if}</span>
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
  .nr {
    width: 18px; height: 18px; flex: none; border-radius: 5px;
    background: var(--div3); color: var(--t-mut);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; position: relative;
  }
  .post.aktiv .nr { background: var(--acc); color: var(--kort); }
  .dot {
    position: absolute; top: -3px; right: -3px; width: 9px; height: 9px;
    border-radius: 50%; background: #B0483A; box-shadow: 0 0 0 2px var(--panel);
  }
</style>
