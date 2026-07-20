<script>
  // Rund lagbricka — logga (ljus platta, contain) eller initialer (lumfärgad
  // text). Plattan bakom loggan är medvetet fast ljus (ej temavariabel): lag-
  // loggor är ritade för ljus bakgrund oavsett appens tema.
  export let namn = ''
  export let farg = '#8A8172'
  export let logga = ''
  export let storlek = 34

  const bildUrl = (p) => (/^(https?|file):/.test(p) ? p : 'file://' + p)

  function initialer(n) {
    const ord = String(n || '').trim().split(/\s+/).filter(Boolean)
    if (!ord.length) return '?'
    let init = ord.map((w) => (w.length <= 3 && w === w.toUpperCase()) ? w : w[0]).join('')
    if (ord.length === 1) init = ord[0].slice(0, 3)
    return init.slice(0, 4).toUpperCase()
  }
  function lum(hex) {
    const h = String(hex || '').replace('#', '')
    if (h.length < 6) return 0
    const r = parseInt(h.slice(0, 2), 16) / 255
    const g = parseInt(h.slice(2, 4), 16) / 255
    const b = parseInt(h.slice(4, 6), 16) / 255
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }

  $: init = initialer(namn)
  $: harLogga = !!logga
  $: fgColor = lum(farg) > 0.6 ? 'rgba(24,22,18,.9)' : '#fff'
  $: initSize = Math.round(storlek * (init.length >= 4 ? 0.26 : 0.34))
</script>

<div class="bricka" title={namn}
  style="width:{storlek}px;height:{storlek}px;background:{harLogga ? '#FBF8F1' : farg}">
  {#if harLogga}
    <img src={bildUrl(logga)} alt="" style="width:78%;height:78%" />
  {:else}
    <span class="scd" style="color:{fgColor};font-size:{initSize}px">{init}</span>
  {/if}
</div>

<style>
  .bricka { border-radius: 50%; border: 1px solid var(--div); flex: none;
    display: flex; align-items: center; justify-content: center; overflow: hidden; }
  .bricka img { object-fit: contain; display: block; }
  .bricka span { font-weight: 700; letter-spacing: 0.02em; line-height: 1; }
</style>
