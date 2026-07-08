// Delad cache: laglogotyp-sökväg → base64 data-URI.
//
// Appen laddas från file:// (app.py DIST_INDEX.as_uri) och pywebviews WKWebView
// blockerar <img src="file://…"> mot andra kataloger — så en logga som är en
// lokal sökväg (lag.logga) visas inte direkt. Konvertera den till en data-URI
// via thumbForBild (samma bevisade mekanism som Innehåll/Matchpublicering) och
// dela resultatet mellan alla lagbrickor så samma logga bara läses en gång.
import { writable } from 'svelte/store'
import { thumbForBild } from './api.js'

export const loggor = writable({}) // sökväg → data-URI
const _pending = new Set()
let _nu = {}
loggor.subscribe((v) => (_nu = v))

// Redan en data-/http-URL behöver ingen konvertering.
const _klar = (p) => /^(data:|https?:)/.test(p || '')

// Begär (idempotent) att en logga läses in som data-URI. Trigga från ett
// reaktivt block ($: begarLogga(sokvag)); komponenten läser sedan $loggor.
export function begarLogga(path) {
  if (!path || _klar(path) || _nu[path] || _pending.has(path)) return
  _pending.add(path)
  thumbForBild(path).then((t) => {
    _pending.delete(path)
    if (t?.ok && t.data_uri) loggor.update((c) => ({ ...c, [path]: t.data_uri }))
  })
}
