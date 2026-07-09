<script>
  // Hero-bild + fokuspunkt (object-position) för Innehåll-panelen. Visar HELA
  // källbilden (obeskuren, i sitt riktiga bildförhållande) och ritar en
  // beskärningsram ovanpå som visar exakt hur den beskärs i valt format
  // (Webb-hero 21:9 / Kort 16:9 / Story 9:16) — allt utanför mörkläggs.
  // Fokuspunkten (markören) styr var ramen hamnar. Sparfältet är oförändrat
  // `heroPosition` ("x% y%") — det som sport.astro/landskap.astro läser via
  // object-position på hemsidan. Formaten är bara olika vyer av samma punkt.
  //
  // Miniatyren (dataUri) hålls i synk med `heroKalla` (den lokala källfilen):
  // väljer man en ny bild ELLER öppnar ett sparat utkast där heroKalla redan
  // är satt, återskapas förhandsvisningen automatiskt — annars vore rutan tom
  // vid "gå in på senaste sparat".
  import { valjFil, thumbForBild } from './api.js'
  import { createEventDispatcher } from 'svelte'

  export let hero = ''                      // filnamn, skrivs till frontmatter
  export let heroPosition = 'center center' // CSS object-position, sparas som heroPosition
  export let heroKalla = ''                 // lokal källfil (för export-kopiering, aldrig publik)
  export let visaFormatval = true           // false → lås till 21:9 (B4: Innehålls-hero, ingen formatväxlare)

  const dispatch = createEventDispatcher()

  let dataUri = ''
  let laddar = false
  let fel = ''
  let format = 'hero'                        // hero | kort | story — bara förhandsvisning
  $: if (!visaFormatval) format = 'hero'     // låst 21:9-vy
  let imgRatio = 16 / 9                      // bildens riktiga bredd/höjd (sätts vid inläsning)
  let drar = false
  let boxEl

  const FMT_RATIO = { hero: 21 / 9, kort: 16 / 9, story: 9 / 16 }
  const klamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

  function positionTillPunkt(pos) {
    const m = (pos || '').match(/(-?\d+(?:\.\d+)?)%\s+(-?\d+(?:\.\d+)?)%/)
    return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]) } : { x: 50, y: 50 }
  }
  $: punkt = positionTillPunkt(heroPosition)

  // Beskärningsram i % av HELA bilden: bredast/högsta rektangel med formatets
  // bildförhållande som får plats i bilden, centrerad på fokuspunkten och
  // klampad så den aldrig hamnar utanför.
  $: ram = (() => {
    const a = FMT_RATIO[format]
    if (a >= imgRatio) { const h = (imgRatio / a) * 100; return { l: 0, t: klamp(punkt.y - h / 2, 0, 100 - h), w: 100, h } }
    const w = (a / imgRatio) * 100; return { l: klamp(punkt.x - w / 2, 0, 100 - w), t: 0, w, h: 100 }
  })()

  // Håll miniatyren i synk med heroKalla (nyval + återöppnat utkast + matchbyte).
  let _kallaLaddad = null
  $: synkaForhandsvisning(heroKalla)
  async function synkaForhandsvisning(k) {
    if (k === _kallaLaddad) return
    _kallaLaddad = k
    if (!k) { dataUri = ''; return }
    laddar = true; fel = ''
    const t = await thumbForBild(k)
    if (_kallaLaddad !== k) return          // en nyare källa hann bytas in
    laddar = false
    if (t?.ok) { dataUri = t.data_uri; if (t.filnamn) hero = t.filnamn }
    else { fel = t?.fel || 'Kunde inte skapa miniatyr.'; dataUri = '' }
  }

  function paBildLast(e) {
    const im = e.currentTarget
    if (im.naturalWidth && im.naturalHeight) imgRatio = im.naturalWidth / im.naturalHeight
  }

  async function valjBild() {
    const r = await valjFil('Välj hero-bild', ['Bilder (*.jpg;*.jpeg;*.nef;*.dng;*.cr2;*.cr3;*.arw)'])
    if (!r?.ok || !r.path) return
    laddar = true; fel = ''
    const t = await thumbForBild(r.path)
    laddar = false
    if (!t?.ok) { fel = t?.fel || 'Kunde inte skapa miniatyr.'; return }
    dataUri = t.data_uri
    hero = t.filnamn
    heroKalla = r.path
    _kallaLaddad = r.path                    // reaktiven ska inte ladda om samma fil
    heroPosition = 'center center'
    dispatch('change', { hero, heroPosition, heroKalla })
  }

  function satt(e) {
    const rekt = (boxEl || e.currentTarget).getBoundingClientRect()
    const x = Math.round(klamp(((e.clientX - rekt.left) / rekt.width) * 100, 0, 100))
    const y = Math.round(klamp(((e.clientY - rekt.top) / rekt.height) * 100, 0, 100))
    heroPosition = `${x}% ${y}%`
    dispatch('change', { hero, heroPosition })
  }
  function ned(e) { if (!dataUri) return; try { e.currentTarget.setPointerCapture(e.pointerId) } catch (_) {} drar = true; satt(e) }
  function ror(e) { if (drar) satt(e) }
  function upp() { drar = false }
</script>

<div class="fokusfalt">
  <div class="fokusrad">
    <button type="button" class="valjbtn" on:click={valjBild} disabled={laddar}>
      {laddar ? 'Laddar…' : dataUri ? 'Byt bild' : 'Välj bild'}
    </button>
    {#if hero}<span class="filnamn mono">{hero}</span>{/if}
    {#if dataUri && visaFormatval}
      <div class="chips">
        <button type="button" class:on={format === 'hero'} on:click={() => (format = 'hero')}>Webb-hero 21:9</button>
        <button type="button" class:on={format === 'kort'} on:click={() => (format = 'kort')}>Kort 16:9</button>
        <button type="button" class:on={format === 'story'} on:click={() => (format = 'story')}>Story 9:16</button>
      </div>
    {/if}
  </div>

  {#if dataUri}
    <div class="fokusgrid">
      <div class="fokusbild" bind:this={boxEl}
        on:pointerdown={ned} on:pointermove={ror} on:pointerup={upp} on:pointerleave={upp}>
        <img class="fokusfoto" src={dataUri} alt="" draggable="false" on:load={paBildLast} />
        <div class="ram" style="left:{ram.l}%; top:{ram.t}%; width:{ram.w}%; height:{ram.h}%;"></div>
        <span class="korsprick" style="left:{punkt.x}%; top:{punkt.y}%;"></span>
      </div>
      <div class="fokusinfo">
        <div class="hint">Hela bilden visas här. Ramen visar hur den beskärs i valt format och följer fokuspunkten — allt utanför mörkläggs. Klicka eller dra för att flytta punkten.</div>
        <div class="fokusval">Fokus <span class="mono">x {punkt.x}% · y {punkt.y}%</span></div>
        <div class="frag">Sparas i posten som <span class="mono">heroPosition: "{heroPosition}"</span> — hemsidan använder den för alla beskärningar.</div>
      </div>
    </div>
  {:else if laddar}
    <div class="hint">Laddar förhandsvisning…</div>
  {:else if hero}
    <div class="hint">Fältet innehåller redan "{hero}", men ingen lokal källfil är kopplad i den här sessionen — klicka "Byt bild" för att sätta fokuspunkten visuellt.</div>
  {/if}
  {#if fel}<div class="synkfel">{fel}</div>{/if}
</div>

<style>
  .fokusfalt { display: flex; flex-direction: column; gap: 10px; }
  .fokusrad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .valjbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 7px;
    padding: 7px 12px; font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .valjbtn:disabled { opacity: 0.5; }
  .filnamn { font-size: 12px; color: var(--t-mut); }
  .mono { font-family: var(--mono, ui-monospace, monospace); }

  .chips { display: flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }
  .chips button { font-size: 11.5px; font-weight: 600; padding: 5px 11px; border-radius: 999px;
    border: 1px solid var(--div); background: transparent; color: var(--t-mut); }
  .chips button.on { border-color: var(--acc); background: var(--acc); color: var(--ink); }

  .fokusgrid { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
  .fokusbild {
    position: relative; width: 100%; max-width: 420px; flex: none; border-radius: 9px;
    overflow: hidden; cursor: crosshair; background: var(--div3);
    touch-action: none; user-select: none; line-height: 0;
  }
  .fokusfoto { display: block; width: 100%; height: auto; user-select: none; -webkit-user-drag: none; }
  .ram {
    position: absolute; border: 2px solid #fff; border-radius: 4px;
    box-shadow: 0 0 0 9999px rgba(16, 12, 5, 0.55); pointer-events: none;
    transition: left 0.12s ease-out, top 0.12s ease-out, width 0.12s ease-out, height 0.12s ease-out;
  }
  .korsprick {
    position: absolute; width: 20px; height: 20px; margin: -10px 0 0 -10px; border-radius: 50%;
    border: 2px solid #fff; box-shadow: 0 0 0 1.5px rgba(0, 0, 0, 0.55), 0 1px 4px rgba(0, 0, 0, 0.35);
    background: radial-gradient(circle, rgba(255, 255, 255, 0.9) 0 2px, transparent 3px);
    pointer-events: none;
  }
  .fokusinfo { flex: 1; min-width: 220px; display: flex; flex-direction: column; gap: 9px; }
  .hint { font-size: 12.5px; color: var(--t-mut); line-height: 1.5; }
  .fokusval { font-size: 12px; color: var(--t-mut); }
  .fokusval .mono { color: var(--t-head); }
  .frag { font-size: 11px; color: var(--t-help); line-height: 1.45; }
  .synkfel { font-size: 12.5px; color: #c0453e; font-weight: 600; }
</style>
