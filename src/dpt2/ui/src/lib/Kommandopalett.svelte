<script>
  // D11b §4: ⌘K global sökning. Öppnas var som helst, tar dig raka vägen till
  // utövare · tävling · fotojobb · gren. Pilar + Enter, Esc stänger.
  import { createEventDispatcher, tick } from 'svelte'
  import { sokGlobalt } from './api.js'

  const dispatch = createEventDispatcher()
  const TYPNAMN = { utovare: 'Utövare', tavling: 'Tävling', fotojobb: 'Fotojobb', gren: 'Gren' }
  let q = ''
  let traffar = []
  let markerad = 0
  let input
  let korning = 0

  tick().then(() => input && input.focus())

  async function sok() {
    const eget = ++korning
    const r = await sokGlobalt(q).catch(() => [])
    if (eget !== korning) return          // en nyare sökning hann före
    traffar = r || []
    markerad = 0
  }
  $: q, sok()

  function valj(t) {
    if (!t) return
    dispatch('valj', { mal: t.mal, id: t.id })
  }
  function tangent(e) {
    if (e.key === 'Escape') { dispatch('stang'); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); markerad = Math.min(markerad + 1, traffar.length - 1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); markerad = Math.max(markerad - 1, 0) }
    else if (e.key === 'Enter') { e.preventDefault(); valj(traffar[markerad]) }
  }
</script>

<svelte:window on:keydown={tangent} />
<button class="overlay" on:click={() => dispatch('stang')} aria-label="Stäng"></button>
<div class="palett" role="dialog" aria-label="Sök">
  <input bind:this={input} bind:value={q} placeholder="Sök utövare, tävling, fotojobb, gren…" />
  {#if q.trim().length >= 2}
    {#if traffar.length}
      <div class="traffar">
        {#each traffar as t, i}
          <button class="traff" class:pa={i === markerad}
            on:mouseenter={() => (markerad = i)} on:click={() => valj(t)}>
            <span class="ttyp">{TYPNAMN[t.typ] || t.typ}</span>
            <span class="tnamn scd">{t.namn}</span>
            <span class="tsub">{t.sub || ''}</span>
          </button>
        {/each}
      </div>
    {:else}
      <p class="inga">Inga träffar.</p>
    {/if}
  {:else}
    <p class="inga">Skriv minst två tecken.</p>
  {/if}
</div>

<style>
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.35); border: 0;
    z-index: 90; cursor: default; }
  .palett { position: fixed; top: 14vh; left: 50%; transform: translateX(-50%);
    width: min(560px, 92vw); background: var(--panel); border: 1px solid var(--div);
    border-radius: 14px; box-shadow: 0 18px 50px rgba(0,0,0,.35); z-index: 91;
    overflow: hidden; }
  .palett input { width: 100%; box-sizing: border-box; border: 0; border-bottom: 1px solid var(--div);
    background: transparent; color: var(--t-head); font-family: inherit; font-size: 16px;
    padding: 16px 18px; outline: none; }
  .traffar { max-height: 52vh; overflow-y: auto; padding: 6px; }
  .traff { display: flex; align-items: baseline; gap: 10px; width: 100%; text-align: left;
    border: 0; background: transparent; border-radius: 9px; padding: 9px 12px;
    font-family: inherit; cursor: pointer; }
  .traff.pa { background: var(--kort); }
  .ttyp { flex: 0 0 72px; font-size: 10.5px; letter-spacing: .05em; text-transform: uppercase;
    color: var(--t-help); }
  .tnamn { flex: 1; color: var(--t-head); font-size: 14px; }
  .tsub { color: var(--t-help); font-size: 12px; }
  .inga { color: var(--t-help); font-size: 13px; padding: 16px 18px; margin: 0; }
</style>
