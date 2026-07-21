// D11b §4: ⌘K-djuplänk. Kommandopaletten sätter {mal, id}; App byter panel och
// målpanelen läser storen för att öppna rätt post raka vägen. Nollas när den
// konsumerats.
import { writable } from 'svelte/store'

export const oppnaMal = writable(null)

export function oppna(mal, id) {
  oppnaMal.set({ mal, id })
}

// Tillbaka-navigering: när man djuplänkar från Idags åtgärdskö sätts panelen man
// kom ifrån här, så toppraden kan visa "← Tillbaka". Nollas vid manuell nav.
export const tillbaka = writable(null)

// Idags utfällda åtgärdskö (kö-typ) persistas här så listan finns kvar när man
// öppnat en post och kommer tillbaka — då plockar man nästa direkt.
export const idagOppet = writable(null)
