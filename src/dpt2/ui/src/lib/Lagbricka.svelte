<script>
  // Rund lagbricka — logga (ljus platta, contain) eller initialer (lumfärgad
  // text). Plattan bakom loggan är medvetet fast ljus (ej temavariabel): lag-
  // loggor är ritade för ljus bakgrund oavsett appens tema.
  import { loggor, begarLogga } from './loggacache.js'
  import { flaggaForLand } from './lander.js'
  export let namn = ''
  export let farg = '#8A8172'
  export let logga = ''
  export let storlek = 34
  // M-1 (registersammanslagning): brickan bär nu båda slagen.
  //   form   — 'cirkel' (utövare/porträtt, oförändrat) | 'kvadrat' (lag/emblem)
  //   farg2  — andra ställfärgen; satt → diagonal 50/50-gradient (lag-emblem)
  //   kant   — klass-färgkant (dam/herr/mixed). ALDRIG textetikett, och ingen
  //            kant alls när klassen är okänd (låst invariant).
  export let form = 'cirkel'
  export let farg2 = ''
  export let kant = ''

  // Loggan (lokal sökväg) visas som data-URI — file:// blockeras i WKWebView.
  $: begarLogga(logga)
  $: loggaUri = !logga ? '' : (/^(data:|https?:)/.test(logga) ? logga : ($loggor[logga] || ''))

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
  $: harLogga = !!loggaUri
  // Landslag utan egen uppladdad logga → härled flagga ur namnet (namn = land).
  // Manuell logga vinner alltid (ligger i harLogga-grenen ovan).
  $: flaggUri = harLogga ? '' : flaggaForLand(namn)
  $: harFlagga = !!flaggUri
  $: fgColor = lum(farg) > 0.6 ? 'rgba(24,22,18,.9)' : '#fff'
  $: initSize = Math.round(storlek * (init.length >= 4 ? 0.26 : 0.34))
  // Emblemets yta: logga/flagga vinner alltid, annars ställfärgerna som
  // diagonal 50/50 (två mättade färger — max enligt färgsystemet) eller en ton.
  $: yta = harLogga || harFlagga
    ? '#FBF8F1'
    : (farg2 ? `linear-gradient(135deg, ${farg} 50%, ${farg2} 50%)` : farg)
  $: kantStil = kant ? `border-left:3px solid ${kant};` : ''
</script>

<div class="bricka" class:kvadrat={form === 'kvadrat'} title={namn}
  style="width:{storlek}px;height:{storlek}px;background:{yta};{kantStil}">
  {#if harLogga}
    <img src={loggaUri} alt="" style="width:78%;height:78%" />
  {:else if harFlagga}
    <img class="flagga" src={flaggUri} alt="" />
  {:else}
    <span class="scd" style="color:{fgColor};font-size:{initSize}px">{init}</span>
  {/if}
</div>

<style>
  .bricka.kvadrat { border-radius: 8px; }
  .bricka { border-radius: 50%; border: 1px solid var(--div); flex: none;
    display: flex; align-items: center; justify-content: center; overflow: hidden; }
  .bricka img { object-fit: contain; display: block; }
  /* Flaggan fyller hela discen (cover, cirkelklippt) → tydlig landslags-markör. */
  .bricka img.flagga { width: 100%; height: 100%; object-fit: cover; }
  .bricka span { font-weight: 700; letter-spacing: 0.02em; line-height: 1; }
</style>
