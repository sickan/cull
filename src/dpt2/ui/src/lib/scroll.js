import { tick } from 'svelte'

/** Närmaste förälder som faktiskt scrollar, eller null. */
function scrollForalder(el) {
  let p = el.parentElement
  while (p) {
    const o = getComputedStyle(p).overflowY
    if ((o === 'auto' || o === 'scroll') && p.scrollHeight > p.clientHeight) return p
    p = p.parentElement
  }
  return null
}

/**
 * Lägger raden överst i sin scroll-container. Används vid klick-till-ändra:
 * det utfällda formuläret kan vara högre än vyn, så raden måste flyttas upp
 * för att formuläret ska rymmas under den. Väntar på Sveltes DOM-uppdatering
 * (tick) eftersom formuläret inte finns ännu i klick-ögonblicket.
 */
export async function radTillToppen(el, marginal = 12) {
  if (!el) return
  await tick()
  const box = scrollForalder(el)
  if (!box) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return }
  const d = el.getBoundingClientRect().top - box.getBoundingClientRect().top - marginal
  box.scrollBy({ top: d, behavior: 'smooth' })
}
