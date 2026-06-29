<script>
  import { createEventDispatcher } from 'svelte'
  export let aktiv = 'matcher'
  const dispatch = createEventDispatcher()

  const grupper = [
    { rubrik: 'Planera', poster: [
      { id: 'matcher', namn: 'Matcher' },
      { id: 'lag', namn: 'Lag & tävlingar' },
    ] },
    { rubrik: 'Efter match', poster: [
      { id: 'gallra', namn: 'Gallra', nr: 1 },
      { id: 'leverera', namn: 'Leverera', nr: 2 },
      { id: 'publicera', namn: 'Publicera', nr: 3 },
    ] },
    { rubrik: 'Webb', poster: [{ id: 'innehall', namn: 'Innehåll' }] },
    { rubrik: 'System', poster: [
      { id: 'trana', namn: 'Träna' },
      { id: 'logg', namn: 'Logg' },
    ] },
  ]
</script>

<nav>
  <div class="brand scd">Dalecarlia<span>Photo Tools</span></div>
  {#each grupper as g}
    <div class="rubrik">{g.rubrik}</div>
    {#each g.poster as p}
      <button class="post" class:aktiv={aktiv === p.id} on:click={() => dispatch('valj', p.id)}>
        {#if p.nr}<span class="nr">{p.nr}</span>{/if}
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
  .brand {
    font-weight: 700; font-size: 16px; color: var(--t-head);
    padding: 6px 8px 4px; line-height: 1.1; display: flex; flex-direction: column;
  }
  .brand span { font-family: var(--font); font-weight: 500; font-size: 11px;
    letter-spacing: 0.14em; text-transform: uppercase; color: var(--acc); }
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
    font-size: 11px; font-weight: 700;
  }
  .post.aktiv .nr { background: var(--acc); color: var(--kort); }
</style>
