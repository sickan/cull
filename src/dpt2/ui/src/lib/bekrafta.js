import { writable } from 'svelte/store'

// Tvåstegsborttagning: första klicket beväpnar knappen (varning), andra
// klicket inom TIMEOUT_MS utför borttagningen — annars återställs knappen
// automatiskt. Exakt en knapp är beväpnad åt gången i hela appen.
const TIMEOUT_MS = 3500

export const armerad = writable(null)

let aktuell = null
let timer = null
armerad.subscribe((v) => (aktuell = v))

export function taBortKlick(token, kor) {
  return (e) => {
    if (e?.stopPropagation) e.stopPropagation()
    clearTimeout(timer)
    if (aktuell === token) {
      armerad.set(null)
      kor()
    } else {
      armerad.set(token)
      timer = setTimeout(() => {
        if (aktuell === token) armerad.set(null)
      }, TIMEOUT_MS)
    }
  }
}
