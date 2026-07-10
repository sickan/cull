// Datumhjälpare för Fotojobbs vecko- och månadsvy. Allt räknas i LOKAL tid och
// via Date-konstruktorn (aldrig +86400000): dagöverflöd normaliseras och
// sommartidsskiften flyttar inte dygnsgränserna.

const pad2 = (n) => String(n).padStart(2, '0')

export const dagNyckel = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
export const midnatt = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
export const addDagar = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)

/** Måndagen i samma vecka (veckan börjar på måndag, inte söndag som getDay()). */
export function mandagen(d) {
  const x = midnatt(d)
  return addDagar(x, -((x.getDay() + 6) % 7))
}

/** Halvöppet dygnsspann [00:00, nästa 00:00) i ms. */
export function dygnSpann(d) {
  const s = midnatt(d)
  return [s.getTime(), addDagar(s, 1).getTime()]
}

export const overlappar = (aS, aE, bS, bE) => aS < bE && bS < aE

export const VECKODAG_KORT = ['Mån', 'Tis', 'Ons', 'Tor', 'Fre', 'Lör', 'Sön']
export const MANAD_NAMN = ['januari', 'februari', 'mars', 'april', 'maj', 'juni',
  'juli', 'augusti', 'september', 'oktober', 'november', 'december']
