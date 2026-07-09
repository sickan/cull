// A2 · Kalender-synk-palett (LÅST). Färgen bär hela signalen — ingen text.
// Samma markör (hörnbåge, variant F) på fotojobb och matcher; grön hörnmarkering
// återanvänds även för publiceringsstatus i Innehåll (B5).
export const SYNK = {
  synkad: '#6FB35A',   // kopplad till Google Kalender
  vantar: '#E0A341',   // väntar på synk / utkast
  konflikt: '#E07A6E', // konflikt mot kalendern
}

export const synkFarg = (status) => SYNK[status] || ''

// Fotojobb: tri-läge. Matcher använder bool (synkad → grön, annars ingen).
export function jobbSynkStatus(j) {
  if (j?.sync_konflikt) return 'konflikt'
  if (j?.google_event_id) return 'synkad'
  return 'vantar' // utkast eller ännu ej pushat
}
