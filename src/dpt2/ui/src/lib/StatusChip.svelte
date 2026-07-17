<script>
  // D9 §5: gemensam statuschip — prick + etikett i statusfärgen på tonad
  // platta (kompakt = prick + etikett utan platta, för trånga rader).
  // Chip visas normalt bara vid Live/Bygger/Fel (utkast bär sin status via
  // hörnbåge + metarad) — det avgör anroparen, inte komponenten.
  export let status = 'utkast'      // utkast | publicerad | bygger | live | fel
  export let sedan = ''             // valfri tidstext efter etiketten
  export let kompakt = false

  // Ljusa temats jordton (D9); appens mörka ytor använder systervarianterna.
  const FARG = { utkast: '#3E7CB0', publicerad: '#B07A2A', bygger: '#B07A2A',
                 live: '#5C8F4A', fel: '#C0492F' }
  const ETIKETT = { utkast: 'Utkast', publicerad: 'Publicerad',
                    bygger: 'Publicerad · bygger…', live: 'Live', fel: 'Fel' }
  $: farg = FARG[status] || FARG.utkast
  $: text = (ETIKETT[status] || status) + (sedan ? ` ${sedan}` : '')
</script>

<span class="chip" class:kompakt style="--sc:{farg}">
  <span class="prick" class:puls={status === 'bygger'}></span>{text}
</span>

<style>
  .chip { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
    font-size: 11.5px; font-weight: 600; color: var(--sc);
    padding: 3px 9px; border-radius: 999px; background: color-mix(in srgb, var(--sc) 11%, transparent); }
  .chip.kompakt { padding: 0; background: none; }
  .prick { width: 7px; height: 7px; border-radius: 50%; background: var(--sc); flex: none; }
  .prick.puls { animation: scpuls 1.6s ease-in-out infinite; }
  @keyframes scpuls { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  @media (prefers-reduced-motion: reduce) { .prick.puls { animation: none; } }
</style>
