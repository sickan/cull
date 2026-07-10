// Privata kalendrar = ett SKRIVSKYDDAT tillgänglighetslager ovanpå fotojobben.
//
// Datat lämnar aldrig maskinen: DPT2 läser Google direkt (tjanster/privat_kalender.py),
// inte via Calendar Sync-workern. Workern äger bara jobbkalendern (dalecarliaphoto.se)
// och har läs+skriv-scope mot exakt det kontot. Privata poster lagras aldrig i DPT:s
// databas, skickas aldrig till workern och skrivs aldrig tillbaka till Google.
//
// Kalendrarna är en LISTA, inte ett par. Fruns kalender är delad till ägarens
// sjuab.se-konto och dyker alltså upp i samma calendarList — en inloggning, N
// kalender-id:n. Att lägga till barn/förening blir därför en rad i inställningar,
// inte en kodändring.

/** Skrivskyddad post: { id, kalender_id, titel, start, slut, heldag }.
 *  `slut` är INKLUSIVT för heldag (samma konvention som DPT:s egna fotojobb).
 *  Google levererar exklusivt slutdatum — Python-lagret normaliserar innan det
 *  når hit. */

// Steg 1 kör mot seed. Steg 2 byter dessa två mot riktiga hämtningar.
export const SEED_KALENDRAR = [
  { id: 'jag', etikett: 'Jag', farg: '#5C93C9' },
  { id: 'frun', etikett: 'Frun', farg: '#C77BA6' },
]

export const SEED_PRIVATA = [
  // p8/p9 ligger inuti heldagsjobbet "Mässa & workshop" (29 jun–3 jul) — det är
  // dem heldagsräknaren summerar.
  { id: 'p8', kalender_id: 'frun', titel: 'Bilbesiktning', start: '2026-06-30T10:00', slut: '2026-06-30T11:00', heldag: false },
  { id: 'p9', kalender_id: 'jag', titel: 'Tandläkare', start: '2026-07-02T08:30', slut: '2026-07-02T09:15', heldag: false },
  { id: 'p1', kalender_id: 'jag', titel: 'Läkartid', start: '2026-07-12T05:00', slut: '2026-07-12T06:00', heldag: false },
  { id: 'p2', kalender_id: 'frun', titel: 'Tandläkare', start: '2026-07-19T14:00', slut: '2026-07-19T15:00', heldag: false },
  { id: 'p3', kalender_id: 'jag', titel: 'Gym', start: '2026-07-15T17:00', slut: '2026-07-15T18:00', heldag: false },
  { id: 'p4', kalender_id: 'frun', titel: 'Yoga', start: '2026-07-22T09:00', slut: '2026-07-22T10:00', heldag: false },
  { id: 'p5', kalender_id: 'jag', titel: 'Föräldramöte', start: '2026-07-28T18:00', slut: '2026-07-28T19:30', heldag: false },
  { id: 'p6', kalender_id: 'frun', titel: 'Middag med Ekstedts', start: '2026-08-08T18:00', slut: '2026-08-08T20:00', heldag: false },
  { id: 'p7', kalender_id: 'jag', titel: 'Kräftskiva', start: '2026-08-22', slut: '2026-08-23', heldag: true },
]

const TIMME_MS = 3600000

// 'YYYY-MM-DD' och 'YYYY-MM-DDTHH:mm' tolkas båda som LOKAL tid. Det gör inte
// new Date(): ett rent datum tolkas som UTC och hamnar ett dygn fel i västliga
// tidszoner. Heldagsposter måste därför parsas komponentvis.
function tillMs(iso) {
  const [datum, tid] = String(iso || '').split('T')
  const [ar, man, dag] = datum.split('-').map(Number)
  if (!ar || !man || !dag) return NaN
  const [h, min] = (tid || '').split(':').map(Number)
  return new Date(ar, man - 1, dag, h || 0, min || 0).getTime()
}

// Midnatt dygnet EFTER `iso` — heldagsposter har inklusivt slutdatum men behöver
// ett exklusivt spann för överlappstestet. Date normaliserar dagöverflöd
// (2026-08-32 → 2026-09-01) och gör det över lokal midnatt, så sommartidsskiften
// inte skjuter spannet en timme som en rå +86400000 skulle göra.
function midnattEfter(iso) {
  const [ar, man, dag] = String(iso || '').split('T')[0].split('-').map(Number)
  if (!ar || !man || !dag) return NaN
  return new Date(ar, man - 1, dag + 1).getTime()
}

// Halvöppet spann [start, slut) i ms för ett fotojobb.
export function jobbSpann(j) {
  if (j.all_day) return [tillMs(j.start_at), midnattEfter(j.end_at || j.start_at)]
  const start = tillMs(j.start_at)
  const slut = j.end_at ? tillMs(j.end_at) : NaN
  // Saknat eller trasigt slut: räkna jobbet som en timme långt hellre än som
  // nollängd — ett nollängdsspann kan per definition inte överlappa något.
  return [start, Number.isFinite(slut) && slut > start ? slut : start + TIMME_MS]
}

// Samma sak för en privat post.
export function privatSpann(p) {
  if (p.heldag) return [tillMs(p.start), midnattEfter(p.slut || p.start)]
  const start = tillMs(p.start)
  const slut = tillMs(p.slut)
  return [start, Number.isFinite(slut) && slut > start ? slut : start + TIMME_MS]
}

const overlappar = (aS, aE, bS, bE) => aS < bE && bS < aE

/**
 * Map: jobb-id → privata poster som överlappar det, tidsordnade.
 *
 * Anropas EN gång per ändring av jobb eller privata poster och skickas sedan
 * ner i vyerna. Beräknas alltid mot ALLA privata poster, aldrig mot de filtrerade:
 * släcker man en kalender ska hennes rader döljas, men jobbet ska fortfarande
 * varna. Att släcka döljer — det avvarnar aldrig.
 */
export function krockKarta(jobb, privata) {
  const spann = privata.map((p) => [p, privatSpann(p)])
  const karta = new Map()
  for (const j of jobb) {
    const [jS, jE] = jobbSpann(j)
    if (!Number.isFinite(jS) || !Number.isFinite(jE)) continue
    const traffar = spann.filter(([, [pS, pE]]) => overlappar(jS, jE, pS, pE))
    if (traffar.length) {
      traffar.sort((a, b) => a[1][0] - b[1][0])
      karta.set(j.id, traffar.map(([p]) => p))
    }
  }
  return karta
}

/** Privata poster från de kalendrar användaren har tända. Styr bara VISNING. */
export function synligaPrivata(privata, aktiva) {
  return privata.filter((p) => aktiva.has(p.kalender_id))
}

export const kalenderFarg = (kalendrar, id) => kalendrar.find((k) => k.id === id)?.farg || '#888'
export const kalenderEtikett = (kalendrar, id) => kalendrar.find((k) => k.id === id)?.etikett || id
