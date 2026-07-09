<script>
  // A2 · variant F — kort hörnbåge i övre HÖGER hörn. Tjockast i mitten,
  // fasar ut mot ändarna. Färgen bär hela signalen (ingen text). Radien följer
  // kortets hörnradie: matchkort r=12, jobbkort r=10.
  // Kräver att föräldern har position:relative + overflow:hidden.
  export let farg = ''     // hex; tom sträng = ingen markör
  export let r = 12
  export let titel = ''
  // Unikt gradient-id per instans (annars delar SVG-instanser samma stop-färg).
  const uid = 'hm' + Math.random().toString(36).slice(2, 8)
  $: S = r + 24                       // ritruta med plats för de fasande svansarna
  $: cx = S - r                       // hörnrundningens centrum-x
  $: d = `M${cx - 3} 0 L${cx} 0 A${r} ${r} 0 0 1 ${S} ${r} L${S} ${r + 3}`
</script>

{#if farg}
  <svg class="hm" width={S} height={S} viewBox="0 0 {S} {S}" aria-hidden="true">
    {#if titel}<title>{titel}</title>{/if}
    <defs>
      <linearGradient id={uid} x1={cx - 3} y1="0" x2={S} y2={r + 3} gradientUnits="userSpaceOnUse">
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
</style>
