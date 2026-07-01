<script>
  // Sökbar väljare matad ur registret (lag/tävlingar). Port av Design-
  // komponenten Combobox.dc.html + inline-skapa (hybrid: välj ur register
  // ELLER skapa nytt). Sparar ref, inte fri sträng.
  import { createEventDispatcher } from 'svelte'

  export let options = []          // [{ id, namn }]
  export let value = ''            // valt namn (visas)
  export let placeholder = 'Välj…'
  export let allowCreate = true

  const dispatch = createEventDispatcher()

  let open = false
  let q = null                     // null = inte skrivande; visa value
  let stangTimer = null

  $: skriver = q !== null
  $: shown = skriver ? q : value
  $: filtrerade = skriver && q.trim()
    ? options.filter((o) => o.namn.toLowerCase().includes(q.trim().toLowerCase()))
    : options
  $: exaktFinns = options.some((o) => o.namn.toLowerCase() === (q || '').trim().toLowerCase())
  $: kanSkapa = allowCreate && skriver && q.trim() && !exaktFinns

  function oppna() { clearTimeout(stangTimer); open = true }
  function stangSnart() { stangTimer = setTimeout(() => { open = false; q = null }, 130) }

  function valj(o) {
    clearTimeout(stangTimer)
    open = false; q = null
    dispatch('pick', o)
  }
  function skapa() {
    const namn = (q || '').trim()
    clearTimeout(stangTimer)
    open = false; q = null
    if (namn) dispatch('create', namn)
  }
  function caret(e) { e.preventDefault(); clearTimeout(stangTimer); open = !open; q = null }
  function tangent(e) {
    if (e.key === 'Escape') { open = false; q = null; e.target.blur() }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (filtrerade.length) valj(filtrerade[0])
      else if (kanSkapa) skapa()
    }
  }
</script>

<div class="cb">
  <input
    value={shown}
    on:input={(e) => { q = e.target.value; open = true }}
    on:focus={oppna}
    on:blur={stangSnart}
    on:keydown={tangent}
    {placeholder}
    class:oppen={open} />
  <span class="caret" class:upp={open} role="button" tabindex="-1"
    aria-label="Öppna lista" on:mousedown={caret}>▾</span>

  {#if open}
    <div class="pop">
      {#each filtrerade as o (o.id)}
        <button type="button" class="rad" class:vald={o.namn === value}
          on:mousedown|preventDefault={() => valj(o)}>
          <span class="etikett">{o.namn}</span>
          {#if o.namn === value}<span class="bock">✓</span>{/if}
        </button>
      {/each}
      {#if kanSkapa}
        <button type="button" class="rad skapa" on:mousedown|preventDefault={skapa}>
          + Skapa ”{q.trim()}”
        </button>
      {:else if filtrerade.length === 0}
        <div class="tom">Ingen träff{q ? ` på ”${q.trim()}”` : ''}</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .cb { position: relative; width: 100%; }
  input {
    width: 100%; padding: 8px 26px 8px 10px; border: 1px solid var(--div);
    border-radius: 8px; background: var(--panel); color: var(--t-head);
    font: inherit; font-size: 13px; font-weight: 400; text-transform: none;
    letter-spacing: 0; outline: none;
  }
  input.oppen { border-color: var(--acc); }
  .caret {
    position: absolute; right: 9px; top: 50%; transform: translateY(-50%);
    color: var(--t-mut); font-size: 11px; cursor: pointer; transition: transform 0.12s;
  }
  .caret.upp { transform: translateY(-50%) rotate(180deg); }
  .pop {
    position: absolute; z-index: 30; top: calc(100% + 4px); left: 0; right: 0;
    background: var(--kort); border: 1px solid var(--div); border-radius: 9px;
    box-shadow: 0 10px 28px rgba(40, 32, 16, 0.22); overflow: hidden auto;
    max-height: 216px;
  }
  .rad {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    width: 100%; padding: 8px 12px; border: 0; background: transparent;
    text-align: left; font: inherit; font-size: 13px; color: var(--t-head);
    cursor: pointer;
  }
  .rad:hover { background: var(--div3); }
  .rad.vald { background: var(--acc-soft); font-weight: 600; }
  .etikett { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bock { color: var(--acc); font-size: 12px; flex: none; }
  .skapa { color: var(--acc); font-weight: 600; }
  .tom { padding: 10px 12px; font-size: 12.5px; color: var(--t-mut); }
</style>
