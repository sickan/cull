<script>
  // A2 · variant F — kort hörnbåge i ETT av kortets fyra hörn. Tjockast i
  // mitten, fasar ut mot ändarna. Färgen bär hela signalen (ingen text).
  // Radien följer kortets hörnradie: matchkort r=12, jobbkort r=10.
  // Kräver att föräldern har position:relative + overflow:hidden.
  //
  // Fyra hörn, fyra betydelser, samma familj (handoff Ackreditering §1):
  // kategori uppe-vänster · synk uppe-höger · krock mot privat kalender
  // nere-höger · ackreditering nere-vänster. De samexisterar på samma kort.
  export let farg = ''     // hex eller var(--…); tom sträng = ingen markör
  export let r = 12
  export let titel = ''
  export let horn = 'uppe-hoger'  // uppe-hoger | nere-hoger | uppe-vanster | nere-vanster
  // Unikt gradient-id per instans (annars delar SVG-instanser samma stop-färg).
  const uid = 'hm' + Math.random().toString(36).slice(2, 8)
  $: S = r + 24                       // ritruta med plats för de fasande svansarna
  $: cx = S - r                       // hörnrundningens centrum-x
  $: nere = horn.startsWith('nere')
  $: vanster = horn.endsWith('vanster')
  // Basbågen ritas för uppe-höger; nere är y-spegling (y → S − y), vänster är
  // x-spegling (x → S − x). Varje enkel spegling vänder bågens rotations-
  // riktning — sweep-flaggan är 1 när noll eller två speglingar gjorts.
  $: sx = (x) => (vanster ? S - x : x)
  $: sy = (y) => (nere ? S - y : y)
  $: sweep = nere === vanster ? 1 : 0
  $: d = `M${sx(cx - 3)} ${sy(0)} L${sx(cx)} ${sy(0)} ` +
    `A${r} ${r} 0 0 ${sweep} ${sx(S)} ${sy(r)} L${sx(S)} ${sy(r + 3)}`
</script>

{#if farg}
  <svg class="hm" class:nere class:vanster width={S} height={S} viewBox="0 0 {S} {S}" aria-hidden="true">
    {#if titel}<title>{titel}</title>{/if}
    <defs>
      <linearGradient id={uid} x1={sx(cx - 3)} y1={sy(0)} x2={sx(S)} y2={sy(r + 3)} gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color={farg} stop-opacity="0" />
        <stop offset="0.5" stop-color={farg} stop-opacity="1" />
        <stop offset="1" stop-color={farg} stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d={d} fill="none" stroke="url(#{uid})" stroke-width="3.2" stroke-linecap="round" />
  </svg>
{/if}

<style>
  .hm { position: absolute; top: 0; right: 0; pointer-events: none; }
  .hm.nere { top: auto; bottom: 0; }
  .hm.vanster { right: auto; left: 0; }
</style>
