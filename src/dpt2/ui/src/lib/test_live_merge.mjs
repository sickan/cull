// Enhetstester för fältvis LWW på klientsidan (live_merge.js).
// Kör: node src/dpt2/ui/src/lib/test_live_merge.mjs
//
// Den viktigaste raden i hela Mobil Live-kedjan: ett ÄLDRE mobilvärde får
// aldrig skriva över det man just knappat in på datorn.

import assert from 'node:assert/strict'
import { farskaFalt, LIVE_FALT } from './live_merge.js'

const T0 = '2026-07-10T19:40:00.000Z'   // gammalt
const T1 = '2026-07-10T19:42:00.000Z'   // vår sparning
const T2 = '2026-07-10T19:50:00.000Z'   // färskt (mobilen)

const tom = { resultat: '', mellan: '', malskyttar: '' }
let körda = 0
const test = (namn, fn) => { fn(); körda++; console.log('  ✓', namn) }

test('inget live-state → inget att göra', () => {
  assert.deepEqual(farskaFalt(null, tom, ''), {})
})

test('vi har inte skrivit → mobilens värden tas in oavsett stämpel', () => {
  const live = { resultat: '2-0', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T0 } }
  assert.deepEqual(farskaFalt(live, tom, ''), { resultat: '2-0' })
})

test('identiskt värde ger ingen puls (undviker onödig omrendering)', () => {
  const live = { resultat: '2-0', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T2 } }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '2-0' }, T1), {})
})

test('ÄLDRE mobilvärde skriver INTE över vår färska desktop-ändring', () => {
  const live = { resultat: '0-0', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T0 } }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '9-9' }, T1), {})
})

test('FÄRSKARE mobilvärde vinner över vår äldre sparning', () => {
  const live = { resultat: '3-1', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T2 } }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '9-9' }, T1), { resultat: '3-1' })
})

test('samma stämpel som vår sparning vinner inte (strikt >)', () => {
  const live = { resultat: '3-1', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T1 } }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '9-9' }, T1), {})
})

test('fältvis: bara det färska fältet tas in', () => {
  const live = { resultat: '3-1', mellan: '0-0', malskyttar: '',
                 falt_uppdaterad: { resultat: T2, mellan: T0 } }
  const ut = farskaFalt(live, { resultat: '9-9', mellan: '1-1', malskyttar: '' }, T1)
  assert.deepEqual(ut, { resultat: '3-1' })   // mellan är äldre → orört
})

test('saknad stämpel för ett fält behandlas som äldst', () => {
  const live = { resultat: '3-1', mellan: '', malskyttar: '', falt_uppdaterad: {} }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '9-9' }, T1), {})
})

test('målskyttar med mål utan minut kommer igenom', () => {
  const live = { resultat: '', mellan: '', malskyttar: "Hansson 14', Berg",
                 falt_uppdaterad: { malskyttar: T2 } }
  assert.deepEqual(farskaFalt(live, tom, T1), { malskyttar: "Hansson 14', Berg" })
})

test('mobilen rensade ett fält → tomsträngen tas in', () => {
  const live = { resultat: '', mellan: '', malskyttar: '', falt_uppdaterad: { resultat: T2 } }
  assert.deepEqual(farskaFalt(live, { ...tom, resultat: '2-0' }, T1), { resultat: '' })
})

test('LIVE_FALT är precis de tre remsfälten', () => {
  assert.deepEqual(LIVE_FALT, ['resultat', 'mellan', 'malskyttar'])
})

console.log(`\n${körda} tester gröna (live_merge)`)
