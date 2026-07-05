<script>
  // Hero-bild + fokuspunkt (object-position) för Innehåll-panelen. Användaren
  // väljer en lokal bildfil (nativ dialog), ser en miniatyr och klickar i den
  // för att sätta fokuspunkten — samma object-fit:cover-beskärning som
  // sport.astro faktiskt använder på hemsidan.
  import { createEventDispatcher } from 'svelte'
  import { valjFil, thumbForBild } from './api.js'

  export let hero = ''                      // filnamn, skrivs till frontmatter
  export let heroPosition = 'center center' // CSS object-position

  const dispatch = createEventDispatcher()

  let dataUri = ''
  let laddar = false
  let fel = ''

  function positionTillPunkt(pos) {
    const m = (pos || '').match(/(-?\d+(?:\.\d+)?)%\s+(-?\d+(?:\.\d+)?)%/)
    return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]) } : { x: 50, y: 50 }
  }
  $: punkt = positionTillPunkt(heroPosition)

  async function valjBild() {
    const r = await valjFil('Välj hero-bild', ['Bilder (*.jpg;*.jpeg;*.nef;*.dng;*.cr2;*.cr3;*.arw)'])
    if (!r?.ok || !r.path) return
    laddar = true
    fel = ''
    const t = await thumbForBild(r.path)
    laddar = false
    if (!t?.ok) { fel = t?.fel || 'Kunde inte skapa miniatyr.'; return }
    dataUri = t.data_uri
    hero = t.filnamn
    heroPosition = 'center center'
    dispatch('change', { hero, heroPosition })
  }

  function klickPosition(e) {
    if (!dataUri) return
    const rekt = e.currentTarget.getBoundingClientRect()
    const x = Math.round(((e.clientX - rekt.left) / rekt.width) * 100)
    const y = Math.round(((e.clientY - rekt.top) / rekt.height) * 100)
    heroPosition = `${Math.max(0, Math.min(100, x))}% ${Math.max(0, Math.min(100, y))}%`
    dispatch('change', { hero, heroPosition })
  }
</script>

<div class="fokusfalt">
  <div class="fokusrad">
    <button type="button" class="valjbtn" on:click={valjBild} disabled={laddar}>
      {laddar ? 'Laddar…' : dataUri ? 'Byt bild' : 'Välj bild'}
    </button>
    {#if hero}<span class="filnamn mono">{hero}</span>{/if}
  </div>
  {#if dataUri}
    <div class="fokusbild" on:click={klickPosition}
      style="background-image:url({dataUri}); background-position:{heroPosition};">
      <span class="korsprick" style="left:{punkt.x}%; top:{punkt.y}%;"></span>
    </div>
    <div class="hint">Klicka i bilden för att sätta fokuspunkten (samma beskärning som hero:n på hemsidan) · {heroPosition}</div>
  {:else if hero}
    <div class="hint">Fältet innehåller redan "{hero}", men ingen bild är vald lokalt i den här sessionen — klicka "Byt bild" för att sätta fokuspunkten visuellt.</div>
  {/if}
  {#if fel}<div class="synkfel">{fel}</div>{/if}
</div>

<style>
  .fokusfalt { display: flex; flex-direction: column; gap: 8px; }
  .fokusrad { display: flex; align-items: center; gap: 10px; }
  .valjbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 7px;
    padding: 7px 12px; font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .valjbtn:disabled { opacity: 0.5; }
  .filnamn { font-size: 12px; color: var(--t-mut); }
  .mono { font-family: var(--mono, ui-monospace, monospace); }
  .fokusbild {
    position: relative; width: 100%; height: 160px; border-radius: 8px;
    background-size: cover; background-repeat: no-repeat; background-color: var(--div3);
    border: 1px solid var(--div3); cursor: crosshair; overflow: hidden;
  }
  .korsprick {
    position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px; border-radius: 50%;
    border: 2px solid #fff; box-shadow: 0 0 0 1.5px rgba(0,0,0,.55), 0 1px 4px rgba(0,0,0,.35);
    pointer-events: none;
  }
  .hint { font-size: 10.5px; color: var(--t-help); line-height: 1.45; }
  .synkfel { font-size: 12.5px; color: #C0453E; font-weight: 600; }
</style>
