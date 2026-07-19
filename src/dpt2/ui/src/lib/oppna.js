// D11b §4: ⌘K-djuplänk. Kommandopaletten sätter {mal, id}; App byter panel och
// målpanelen läser storen för att öppna rätt post raka vägen. Nollas när den
// konsumerats.
import { writable } from 'svelte/store'

export const oppnaMal = writable(null)

export function oppna(mal, id) {
  oppnaMal.set({ mal, id })
}
