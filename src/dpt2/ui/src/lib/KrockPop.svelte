<script>
  // Utfällning för ett jobb som krockar med privata poster. Absolut positionerad
  // ovanför den röda hörnmarkören — den får aldrig knuffa raden i sidled eller höjd.
  // Kräver att föräldern har position:relative. Föräldern måste däremot INTE ha
  // overflow:hidden (till skillnad från <Hornmarkor>), annars klipps popovern bort.
  import { kalenderFarg, kalenderEtikett } from './privat.js'

  export let krockar = []
  export let kalendrar = []
  export let heldag = false      // heldagsjobb: antalet är informationen, inte att det finns ett

  const klocka = (iso) => ((iso || '').split('T')[1] || '').slice(0, 5)
  const tid = (p) => (p.heldag ? 'Heldag' : `${klocka(p.start)}–${klocka(p.slut)}`)
</script>

<div class="pop" role="tooltip">
  <div class="rubrik">
    {heldag ? `Krockar med ${krockar.length} privata poster` : 'Krockar med privat'}
  </div>
  {#each krockar as p (p.id)}
    <div class="krad">
      <span class="prick" style="background:{kalenderFarg(kalendrar, p.kalender_id)}"></span>
      <span class="vem">{kalenderEtikett(kalendrar, p.kalender_id)}</span>
      <span class="tit">{p.titel}</span>
      <span class="tid">{tid(p)}</span>
    </div>
  {/each}
</div>

<style>
  .pop {
    position: absolute; right: 10px; bottom: calc(100% - 6px); z-index: 20;
    min-width: 260px; max-width: 360px; padding: 10px 12px;
    background: var(--kort); border: 1px solid var(--krock); border-radius: 10px;
    box-shadow: 0 10px 30px rgba(20, 14, 10, 0.28);
    cursor: default; pointer-events: none;
  }
  .rubrik {
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase;
    color: var(--krock);
  }
  .krad { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: 12.5px; }
  .prick { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  .vem { color: var(--t-mut); flex: none; }
  /* Titeln får ta utrymmet och avkortas — tiden längst till höger är alltid läsbar. */
  .tit { color: var(--t-head); font-weight: 600; flex: 1; min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tid { color: var(--t-mut); flex: none; font-variant-numeric: tabular-nums; }
</style>
