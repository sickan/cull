// D11b §4: ETT synk-tillstånd, ETT märke. Ersätter "Skicka till telefonen" —
// inget ska normalt behöva tryckas. En lokal ändring markeras och pushas själv
// (debounce); märket säger bara VAR det står. Fyra lägen med systemets
// statusfärger: uppe (grön) · vantar (gul) · synkar (blågrå) · fel (röd, enda
// som ber om ett tryck). (Skild från synk.js, som är kalender-synk-paletten.)
import { writable } from 'svelte/store'
import { synkaLivePaket } from './api.js'

export const livesynk = writable({ lage: 'uppe', antal: 0, senast: null, fel: null })

let timer = null
let korsNu = false

export async function synka() {
  if (korsNu) return
  korsNu = true
  clearTimeout(timer)
  livesynk.update((s) => ({ ...s, lage: 'synkar', fel: null }))
  const r = await synkaLivePaket().catch(() => null)
  korsNu = false
  if (r && r.ok) {
    livesynk.set({ lage: 'uppe', antal: 0, senast: new Date().toISOString(), fel: null })
  } else {
    livesynk.update((s) => ({ ...s, lage: 'fel', fel: (r && r.fel) || 'Synk misslyckades' }))
  }
  return r
}

// En lokal ändring behöver pushas: räkna upp och pusha själv efter en kort
// paus (så flera ändringar i rad blir en enda push).
export function markeraAndring(n = 1) {
  livesynk.update((s) => ({ ...s, lage: 'vantar', antal: s.antal + n, fel: null }))
  clearTimeout(timer)
  timer = setTimeout(synka, 1500)
}
