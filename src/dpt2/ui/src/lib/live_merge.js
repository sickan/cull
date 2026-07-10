// Fältvis last-write-wins för Mobil Live, klientsidan.
//
// Workern gör samma bedömning server-side (en fältstämpel skrivs bara över av
// en FÄRSKARE). Här speglar vi regeln åt andra hållet: panelen tar bara in de
// fält där mobilens stämpel är färskare än vår egen senaste sparning — annars
// skulle ett äldre mobilvärde kunna skriva över det man just knappat in på
// datorn (tio sekunder senare, när nästa poll råkar landa).
//
// Ren funktion, ingen Svelte — enhetstestas i test_live_merge.mjs.

export const LIVE_FALT = ['resultat', 'mellan', 'malskyttar']

/**
 * @param {object|null} live      svar från hamtaLive(): {resultat, mellan, malskyttar, falt_uppdaterad}
 * @param {object} lokala         panelens nuvarande värden {resultat, mellan, malskyttar}
 * @param {string} senastEgen     ISO för vår senaste egna sparning ('' = vi har inte skrivit)
 * @returns {object}              endast de fält som ska tas in (tomt objekt = inget att göra)
 */
export function farskaFalt(live, lokala, senastEgen) {
  if (!live) return {}
  const stampel = live.falt_uppdaterad || {}
  const diff = {}
  for (const f of LIVE_FALT) {
    const srv = live[f] || ''
    if (srv === (lokala?.[f] || '')) continue          // inget nytt
    // Har vi själva skrivit? Då krävs att mobilens stämpel är strikt färskare.
    // Stämplarna är ISO-8601 i UTC med 'Z' → lexikografisk jämförelse = kronologisk.
    if (senastEgen && !((stampel[f] || '') > senastEgen)) continue
    diff[f] = srv
  }
  return diff
}
