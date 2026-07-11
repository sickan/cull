// Delad text-modell för publiceringstexter: token-upplösning ({resultat},
// {@lag}, {#liga}…) + webbvarianten utan @/#. Bor här för att Matchpublicering
// (producerar referatet) och Innehåll (hämtar det till matchartikeln) MÅSTE
// tolka texten exakt lika — annars visar editorn en annan webbtext än den som
// publicerades.

export const hashtag = (s) => (s || '').replace(/[^\p{L}\p{N}]/gu, '')

// Strippar sociala tokens för webben: varje #tagg/@handle bort, hängande
// blanksteg och dubbelspace kollapsas. ("# och @ strippas för webben".)
export const strippaSocialt = (s) => (s || '')
  .replace(/[#@][\p{L}\p{N}_]+/gu, '')
  .replace(/ *\n/g, '\n')
  .replace(/[ \t]{2,}/g, ' ')
  .trim()

// Ersätter {token} mot värden ur vals; okända tokens lämnas orörda.
// web:true → @/# strippas och webben självlänkar inte (hemsida-token töms av
// anroparen via vals).
export function losText(text, vals, { web = false } = {}) {
  let ut = (text || '').replace(/\{([^{}]+)\}/g, (whole, key) => (key in vals ? vals[key] : whole))
  if (web) ut = strippaSocialt(ut)
  return ut.replace(/[ \t]{2,}/g, ' ').trim()
}

// Bygger token-värdena ur en match + länkar — samma modell i båda panelerna.
// handle = hemmalagets IG-handle utan @ (tomt om okänt).
export function tokenVals({ match, res, handle, galleriUrl, hemsidaUrl, web = false }) {
  return {
    resultat: res?.resultat || '',
    målskyttar: res?.malskyttar || '',
    arena: match?.arena || '',
    motståndare: match?.lag_borta || '',
    '@lag': handle ? '@' + handle : '',
    '#liga': match?.liga ? '#' + hashtag(match.liga) : '',
    galleri: galleriUrl || '',
    hemsida: web ? '' : (hemsidaUrl || ''),   // webben självlänkar inte
  }
}
