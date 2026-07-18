// Kopiera text till urklipp med kvittens i knappen. Delad så alla ytor
// beter sig lika: klick → "✓ Kopierat" i ~1,6 s → tillbaka.
//
// Tre led, för webviewen är inte en vanlig webbläsare: pywebview kör UI:t
// från file:// och WKWebView nekar ibland Clipboard API utan användargest.
// Faller allt, MARKERAR vi texten i stället och säger till — då räcker ⌘C.
// (Att bara returnera false vore ett tyst misslyckande: knappen skulle se
// oförändrad ut och Stig inte veta om texten låg i urklippet eller inte.)

/** Kopierar text. Returnerar 'kopierat' | 'markerat' | 'fel'. */
export async function kopieraText(text, element = null) {
  const s = String(text ?? '')
  if (!s.trim()) return 'fel'
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(s)
      return 'kopierat'
    }
  } catch (_) { /* faller igenom */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = s
    ta.setAttribute('readonly', '')
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) return 'kopierat'
  } catch (_) { /* faller igenom */ }
  // Sista utvägen: markera texten på skärmen så ⌘C tar den.
  if (element && markera(element)) return 'markerat'
  return 'fel'
}

function markera(el) {
  try {
    const range = document.createRange()
    range.selectNodeContents(el)
    const sel = window.getSelection()
    sel.removeAllRanges()
    sel.addRange(range)
    return true
  } catch (_) {
    return false
  }
}
