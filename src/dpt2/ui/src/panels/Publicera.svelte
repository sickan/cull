<script>
  // Matchpublicering — enhetlig publiceringsyta (f.d. Publicera: Live + SoMe).
  // Skapa en gång → publicera överallt. Delad resultatremsa (ResultatRemsa,
  // skriver på matchposten) matar alla utgångar; Steg 1 Innehåll (katalog +
  // text + länkar) återanvänds; Steg 2 Skicka till renderar en riktig,
  // server-renderad förhandsvisning per kanal (Horisont) med fokus + zoom som
  // matas till skarp rendering. Gren-signalen = färgad kant + glow (låst,
  // ingen textetikett). Design: handoff-matchpublicering (8 jul 2026).
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import {
    listaMatcher, hamtaMatch, aktivMatch, sattAktivMatch, sportprofiler, listaLag,
    listaTavlingar, listaDiscipliner,
    valjMapp, listaSomeBilder, thumbForBild,
    forhandsgranskaStory, publiceraLiveStory, publiceraKanal, nyTestPaketMapp,
    publiceraInnehallNatet, listaMaterial, sparaMaterial, raderaMaterial, genereraBildsvep,
    forhandsgranskaBildsvepFraga,
    listaMinneskort, exporteraSkyddade,
    hamtaLive,
  } from '../lib/api.js'
  import ResultatRemsa from '../lib/ResultatRemsa.svelte'
  import { losText as losTextDelad, tokenVals } from '../lib/webtext.js'
  import { farskaFalt } from '../lib/live_merge.js'
  import { grenFarg } from '../lib/gren.js'
  import { testMode } from '../lib/testlage.js'

  const dispatch = createEventDispatcher()

  // ── Flikar (backlog p.1) ────────────────────────────────────────────────────
  // Sidan behåller sitt gemensamma huvud (match/event-väljare + resultat-remsa)
  // men resten delas i tre flikar. Publiceringsraden (sidfot) döljs på Publicerat.
  let mpTab = 'innehall'           // innehall | kanaler | publicerat
  const MP_FLIKAR = [
    ['innehall', '1 · Innehåll'],
    ['kanaler', '2 · Kanaler & publicera'],
    ['publicerat', 'Publicerat'],
  ]

  // ── Grunddata ──────────────────────────────────────────────────────────────
  let matcher = []
  let tavlingar = []               // för turnerings-SoMe-målet (Fas 3)
  let lagAlla = []
  let profiler = {}
  let match = null                 // fullständig aktiv match ELLER syntetiskt turneringsmål
  // Turnerings-SoMe: målet är hela tävlingen, inte en enskild match. `match`
  // bär då ett syntetiskt objekt (arTurnering=true, event=true → resultatremsan
  // göms och momentet blir generellt, precis som ett heldagsevent).
  $: arTurnering = !!match?.arTurnering
  let materials = []
  // Färsk resultat/mellan/målskyttar-spegel — matas av ResultatRemsas 'sparat'-
  // event (den skriver på matchposten, panelen känner annars inte till ändringen)
  // så previews + publicering använder det inskrivna värdet direkt, inte matchens
  // gamla, utan att röra remsans interna state.
  let resNu = { resultat: '', mellan: '', malskyttar: '' }
  function speglaRes(m) { resNu = { resultat: m?.resultat || '', mellan: m?.mellan || '', malskyttar: m?.malskyttar || '' } }
  const tema = 'Hav'               // Skagen-tema för rendern (gren styr kanten, inte temat)

  $: profil = profiler[match?.sport] || profiler.fotboll ||
    { res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid', mid_ph: '3–0',
      has_scorers: true, scorers_label: 'Målskyttar', start_moment: 'Avspark' }

  onMount(async () => {
    try {
      let akt
      ;[matcher, profiler, lagAlla, akt, materials, tavlingar] = await Promise.all(
        [listaMatcher(), sportprofiler(), listaLag(), aktivMatch(), listaMaterial(),
         listaTavlingar()])
      const id = akt?.id || matcher[0]?.id
      if (id) await laddaMatch(id)
    } catch (e) { console.error('Matchpublicering: init', e) }
    livePoll = setInterval(pollaLive, 10000)     // första hämtningen sker i laddaMatch
  })

  async function laddaMatch(id) {
    match = await hamtaMatch(id)
    speglaRes(match)
    galleriUrl = match?.galleri || galleriUrl
    hemsidaUrl = match?.sida_url || hemsidaUrl
    // Materialraden följer matchen. Återanvänd matchens SENASTE SoMe-rad så att
    // spara/publicera uppdaterar den i stället för att lämna dubbletter efter sig.
    const mt = (materials || [])
      .filter((m) => m.match_id === id && m.kind === 'some')
      .sort((a, b) => (b.uppdaterad || '').localeCompare(a.uppdaterad || ''))[0] || null
    materialId = mt?.id || null
    await aterstallFranMaterial(mt)
    // En öppen prompt-granskning hör till FÖRRA matchen — annars skulle man
    // godkänna en fråga och skicka en annan.
    granska = null; genFel = ''
    nollstallLive()
    pollaLive()          // visa mobilens tillstånd direkt vid matchbyte
  }

  // BUGG (Stig 17/7): panelen SPARADE material (caption, kanaler, bildval)
  // men läste aldrig tillbaka det — öppnade man samma match igen efter
  // publicering var allt borta och man fick börja om. Återställ hela
  // arbetsytan ur matchens senaste materialrad.
  async function aterstallFranMaterial(mt) {
    // Utan material: nollställ texten till mallen — förra matchens caption
    // ska inte läcka in i en färsk match. (Kanal-/bildval lämnas som de är —
    // fotografens arbetsinställningar, inte innehåll.)
    if (!mt) { caption = CAPTION_DEFAULT; referat = ''; publiceras = ''; return }
    if (mt.caption) caption = mt.caption
    referat = mt.referat || ''
    publiceras = mt.publiceras || ''
    const banor = mt.banor || {}
    const kanaler = mt.channels || []
    if (kanaler.length) {
      for (const k of Object.keys(ch)) {
        ch[k].on = kanaler.includes(k)
        const cfg = banor[k]?.payload
        if (cfg?.format) ch[k].fmt = cfg.format
        if (cfg?.bilder?.length) ch[k].antal = cfg.bilder.length
        if (k === 'ig' && cfg?.vag) ch.ig.vag = cfg.vag
      }
      ch = ch
    }
    // Bildvalet: största kanal-listan är ordnadeFoton från sparningen
    // (omslaget först). Ladda katalogen igen och applicera sel/cover/crop.
    const bilder = Object.values(banor)
      .map((c) => c?.payload?.bilder || [])
      .sort((a, b) => b.length - a.length)[0] || []
    const forsta = bilder[0]?.path || mt.foto
    if (!forsta) return
    const mapp = forsta.split('/').slice(0, -1).join('/')
    if (mapp && mapp !== folderPath) { folderPath = mapp; await lasKatalog() }
    if (!bilder.length) return
    const perPath = new Map(bilder.map((b, i) => [b.path, { ...b, i }]))
    photos = photos.map((p) => {
      const b = perPath.get(p.path)
      return b
        ? { ...p, sel: true, cover: b.i === 0,
            fokus: b.fokus || p.fokus, zoom: b.zoom || p.zoom }
        : { ...p, sel: false, cover: false }
    })
  }

  // ── Mobil Live: poll + fältvis merge in i remsan ────────────────────────────
  // Mobilen (DPT2 Live-PWA:n) kan föra samma match från läktaren. Vi pollar
  // workern och tar bara in fält som är FÄRSKARE än vår egen senaste sparning.
  // Själva regeln bor i lib/live_merge.js (ren + enhetstestad).
  let liveExtern = null            // fälten som ska in i remsan
  let liveRev = 0                  // triggerpuls till ResultatRemsa
  let forsFran = null              // {enhet, tid} → närvaro-pill
  let senastEgen = ''              // ISO för vår senaste egna sparning
  let livePoll = null

  function nollstallLive() { liveExtern = null; forsFran = null; senastEgen = '' }

  async function pollaLive() {
    if (!match?.id || arTurnering) return   // turnering har ingen enskild match att polla
    let r
    try { r = await hamtaLive(match.id) } catch { return }   // offline → tyst
    const live = r?.live
    if (!live) return
    forsFran = live.fors_fran || null
    const diff = farskaFalt(live, resNu, senastEgen)
    if (Object.keys(diff).length) {
      resNu = { ...resNu, ...diff }    // panelens spegel (previews/tokens)
      liveExtern = diff
      liveRev += 1                     // pulsen som får remsan att applicera
    }
  }

  onDestroy(() => {
    if (livePoll) clearInterval(livePoll)
    if (genTimer) clearInterval(genTimer)   // panelen kan lämnas mitt i ett 2-min-anrop
  })

  // ── Matchväljare ───────────────────────────────────────────────────────────
  let matchOpen = false
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function datumTxt(iso) { const d = (iso || '').split('-').map(Number); return d.length === 3 ? `${d[2]} ${MK[d[1] - 1]}` : '' }
  // p.5: ett event är en "match utan motståndare" i samma datamodell/flöde
  // (heldagsevent, t.ex. "Partille Cup"). Resultatsiffrorna är irrelevanta då.
  $: isEvent = !!(match && (match.event || match.heldag || !(match.lag_borta || '').trim()))
  $: matchTitel = match ? (isEvent ? match.lag_hemma : `${match.lag_hemma} – ${match.lag_borta}`) : 'Ingen match'
  $: matchMeta = match
    ? [datumTxt(match.datum), arTurnering ? 'Turnering' : (isEvent ? 'Heldagsevent' : (match.resultat || 'Kommande'))].filter(Boolean).join(' · ')
    : ''
  async function valjMatch(id) {
    matchOpen = false
    if (id === match?.id) return
    await sattAktivMatch(id)
    await laddaMatch(id)
  }
  // Turnerings-SoMe: bygg ett syntetiskt match-liknande mål ur en tävling så att
  // resten av panelen (bilder, caption, kanaler) fungerar oförändrat. event=true
  // → resultatremsan göms, momentet blir 'nasta_match'. Ingen mobil-live.
  function byggTurneringsMal(t) {
    return { id: `T:${t.id}`, arTurnering: true, tavling_id: t.id,
      lag_hemma: t.namn, lag_borta: '', event: true, sport: t.sport,
      arena: t.ort || '', datum: t.datum || t.fran || '', liga: t.namn,
      resultat: '', mellan: '', malskyttar: '', galleri: '', sida_url: '' }
  }
  async function valjTurnering(id) {
    matchOpen = false
    const t = tavlingar.find((x) => x.id === id)
    if (!t || match?.tavling_id === id) return
    if (livePoll) { clearInterval(livePoll); livePoll = null }   // ingen mobil-live för turnering
    match = byggTurneringsMal(t)
    speglaRes(match); galleriUrl = ''; hemsidaUrl = ''
    materialId = (materials || []).find((m) => m.tavling_id === id && m.kind === 'some')?.id || null
    granska = null; genFel = ''; nollstallLive()
    // Friidrott (B-002): tävlingens grenar driver story-overlayn (D2-mallarna).
    discipliner = t.sport === 'friidrott' ? await listaDiscipliner(t.id) : []
    fri = { ...FRI_TOM, disciplinId: discipliner[0]?.id || '' }
  }

  // ── Friidrotts-story (B-002): disciplin + tillstånd + resultatfält ────────
  const FRI_TOM = { disciplinId: '', tillstand: 'resultat', moment: '',
    deltagareId: '', resultat: '', serie: '', placering: '' }
  let discipliner = []
  let fri = { ...FRI_TOM }
  $: friAktiv = arTurnering && match?.sport === 'friidrott'
  $: friDisc = discipliner.find((d) => d.id === fri.disciplinId)
  // Payload till publicera_kanal — deltagarens namn/klubb slås upp ur
  // disciplinen; start-tillståndet tar disciplinens (max 3) deltagare.
  function friPayload() {
    const d = friDisc || {}
    const p = (d.deltagare || []).find((x) => x.id === fri.deltagareId) || {}
    const start = (d.deltagare || []).slice(0, 3)
    // Kantfärgen följer INDIVIDEN (SM är mixed men man tävlar dam/herr):
    // resultat/placering = vald deltagares gren; start = fältets gemensamma
    // gren (blandat fält → tomt → tävlingens gren vinner i backend).
    const startGren = start.length && start.every((x) => x.gren === start[0].gren)
      ? (start[0].gren || '') : ''
    return { tillstand: fri.tillstand, gren_namn: d.namn || '',
      grentyp: d.typ || 'hoppkast', moment: fri.moment,
      namn: p.namn || '', klubb: p.klubb || '',
      gren: fri.tillstand === 'start' ? startGren : (p.gren || ''),
      resultat: fri.resultat, serie: fri.serie, placering: fri.placering,
      idrottare: start.map((x) => ({ namn: x.namn, klubb: x.klubb || '' })) }
  }

  // ── Steg 1: Innehåll ───────────────────────────────────────────────────────
  let folderPath = ''
  let photos = []                  // {path, sel, cover, fokus:{x,y}, zoom}
  let laddarBilder = false
  // Appen laddas från file:// → WKWebView blockerar <img src="file://…"> mot
  // andra kataloger. Bilder visas därför som base64 data-URI:er via thumbForBild.
  let thumbs = {}                  // sökväg → data-URI (source-foton)
  let ratios = {}                  // sökväg → bredd/höjd (för crop-ramen)
  async function laddaThumbs(paths) {
    const jobb = (paths || []).filter((p) => p && !thumbs[p]).map(async (p) => {
      const t = await thumbForBild(p)
      if (t?.ok) thumbs[p] = t.data_uri
    })
    if (!jobb.length) return
    await Promise.all(jobb)
    thumbs = thumbs
  }
  $: selCount = photos.filter((p) => p.sel).length
  $: selectedPhotos = photos.filter((p) => p.sel)
  $: coverPhoto = photos.find((p) => p.sel && p.cover) || selectedPhotos[0] || null
  $: coverPath = coverPhoto?.path || ''
  $: selectedPaths = selectedPhotos.map((p) => p.path)
  // Omslaget först, sedan övriga valda — ordningen overlay/karusell får.
  $: ordnadeFoton = coverPhoto ? [coverPhoto, ...selectedPhotos.filter((p) => p !== coverPhoto)] : []

  let aktivIdx = null              // index i photos för bilden som redigeras i crop-editorn
  $: aktivFoto = aktivIdx != null ? photos[aktivIdx] : null

  async function valjKatalog() {
    const r = await valjMapp('Välj katalog med redigerade bilder (Lightroom-export)')
    if (r?.ok && r.path) { folderPath = r.path; await lasKatalog() }
  }
  async function lasKatalog() {
    if (!folderPath) return
    laddarBilder = true
    const lista = await listaSomeBilder(folderPath)
    laddarBilder = false
    // Inget förvalt — fotografen väljer själv. Varje foto bär sin EGEN crop.
    photos = (lista || []).map((p) => ({ path: p, sel: false, cover: false, fokus: { x: 50, y: 50 }, zoom: 1 }))
    aktivIdx = null
    laddaThumbs(photos.map((p) => p.path))
  }
  // Klick på ett foto: markera + gör aktiv i crop-editorn (avmarkera via ×).
  function valjAktiv(i) {
    if (!photos[i].sel) {
      photos[i] = { ...photos[i], sel: true }
      if (!photos.some((x, j) => x.sel && x.cover && j !== i)) photos[i].cover = true
      photos = photos
    }
    aktivIdx = i
  }
  function avvalj(i) {
    const varCover = photos[i].cover
    photos[i] = { ...photos[i], sel: false, cover: false }
    if (varCover) { const f = photos.findIndex((x) => x.sel); if (f >= 0) photos[f].cover = true }
    photos = photos
    if (aktivIdx === i) aktivIdx = photos.some((x) => x.sel) ? photos.findIndex((x) => x.sel) : null
  }
  function sattOmslag(i) { photos = photos.map((x, j) => ({ ...x, cover: j === i })) }
  // Stega mellan de valda bilderna i crop-editorn.
  function stega(delta) {
    const valda = photos.map((p, j) => (p.sel ? j : -1)).filter((j) => j >= 0)
    const pos = valda.indexOf(aktivIdx)
    if (pos < 0) return
    aktivIdx = valda[(pos + delta + valda.length) % valda.length]
  }

  // ── Crop-editor (per foto): hel bild + ram (formatets ratio, zoom, fokus,
  // mörklagt utanför). Fokus/zoom lagras PÅ fotot och följer det till alla
  // kanaler; ramen omformas per format. ratio skickas som arg så Svelte spårar.
  const FMT_A = { '9x16': 9 / 16, '4x5': 4 / 5, '1x1': 1, '1.91x1': 1.91, '2x1': 2, '16x9': 16 / 9 }
  const _klamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
  let previewFmt = '4x5'           // vilket format editorns ram visar (bara preview)
  function paFotoLast(e, path) { const im = e.currentTarget; if (im.naturalWidth && im.naturalHeight) { ratios[path] = im.naturalWidth / im.naturalHeight; ratios = ratios } }
  function ramFor(fokus, zoom, fmt, ratio) {
    const a = FMT_A[fmt] || 1
    let baseW, baseH
    if (a >= ratio) { baseW = 100; baseH = (ratio / a) * 100 } else { baseH = 100; baseW = (a / ratio) * 100 }
    const w = baseW / zoom, h = baseH / zoom
    return { w, h, l: _klamp(fokus.x - w / 2, 0, 100 - w), t: _klamp(fokus.y - h / 2, 0, 100 - h) }
  }
  function sattFokus(i, e) {
    const r = e.currentTarget.getBoundingClientRect()
    photos[i].fokus = { x: _klamp(Math.round(((e.clientX - r.left) / r.width) * 100), 0, 100),
                        y: _klamp(Math.round(((e.clientY - r.top) / r.height) * 100), 0, 100) }
    photos = photos
  }
  function sattFotoZoom(i, v) { photos[i].zoom = parseFloat(v) || 1; photos = photos }
  let _drar = false
  function fokusNed(i, e) { try { e.currentTarget.setPointerCapture(e.pointerId) } catch (_) {} _drar = true; sattFokus(i, e) }
  function fokusRor(i, e) { if (_drar) sattFokus(i, e) }
  function fokusUpp() { _drar = false }

  // Text + tokens
  const CAPTION_DEFAULT = 'Stabil hemmaseger på {arena}! {resultat}. Mål: {målskyttar}. {@lag} {#liga} #dalecarliaphoto'
  let caption = CAPTION_DEFAULT
  // F18FM-2: referatet är ett EGET källfält — webben byggs från det, aldrig
  // genom att strippa sociala texten (som läckte rubrikblock/länkrad/@?-taggar).
  let referat = ''
  // §10 publiceringskön: schemalagd tidpunkt (fältdelta `publiceras`) —
  // steg 1 = manuell påminnelse i kön, inget auto-utskick.
  let publiceras = ''
  let capEl
  const TOKENS = ['{resultat}', '{målskyttar}', '{arena}', '{@lag}', '{galleri}', '{hemsida}']
  function insertToken(tok) {
    const el = capEl
    const s = el ? el.selectionStart : caption.length
    const e = el ? el.selectionEnd : caption.length
    caption = caption.slice(0, s) + tok + caption.slice(e)
    if (el) setTimeout(() => { el.focus(); el.selectionStart = el.selectionEnd = s + tok.length }, 0)
  }

  // B2: generera bildtexten med Claude (riktigt anrop via genereraBildsvep →
  // backend bildsvep.generera). Ton + kända matchfakta (resultat/mellan/
  // målskyttar/arena/datum/liga) matas in i prompten. ~2 min i skarpt läge.
  //
  // Flödet är TVÅ steg: bygg frågan lokalt (inget nätverk) → låt användaren
  // granska den → skicka. Det skarpa anropet tar ~2 minuter, så man ska veta
  // exakt vad som skickas innan man startar det, och se att det pågår.
  const TONER = ['Neutral', 'Peppig', 'Kort']
  let ton = 'Neutral'
  // p.6: egna inspel till Claude-genereringen — utöver ton + matchfakta.
  const VINKLAR = [['stamning', 'Stämning'], ['matchfakta', 'Matchfakta'], ['vinkel', 'Vinkel'], ['publik', 'Publiken']]
  let vinklar = []                 // valda vinkel-nycklar (flerval)
  let inspel = ''                  // fritext ("avgörande i 90:e, publikrekord…")
  function toggleVinkel(v) { vinklar = vinklar.includes(v) ? vinklar.filter((x) => x !== v) : [...vinklar, v] }
  let genererar = false
  let genFel = ''
  let granska = null            // frågetexten medan granskningen är öppen
  let laddarFraga = false
  let genSek = 0
  let genTimer = null

  // Delade byggare — granskad fråga och skickad fråga MÅSTE utgå från samma data.
  const genInfo = () => (isEvent ? match.lag_hemma : `${match.lag_hemma} – ${match.lag_borta}`) + (resNu.resultat ? ` ${resNu.resultat}` : '')
  const genFakta = () => ({
    resultat: resNu.resultat, mellan: resNu.mellan, malskyttar: resNu.malskyttar,
    arena: match.arena || '', datum: match.datum || '', liga: match.liga || '', ton,
    // p.6: styrning utöver matchfakta — vinklar (valda chips) + fritext.
    vinklar: vinklar.map((v) => (VINKLAR.find((x) => x[0] === v) || [])[1]).filter(Boolean),
    inspel: inspel.trim(),
  })

  async function oppnaGranska() {
    if (!match || genererar || laddarFraga) return
    genFel = ''; laddarFraga = true
    try {
      const r = await forhandsgranskaBildsvepFraga(genInfo(), genFakta())
      if (r?.ok) granska = r.fraga
      else genFel = r?.fel || 'Kunde inte bygga frågan.'
    } catch (e) {
      genFel = 'Kunde inte bygga frågan.'
    }
    laddarFraga = false
  }
  const avbrytGranska = () => (granska = null)

  async function skickaTillClaude() {
    if (!match || genererar) return
    const info = genInfo(), fakta = genFakta()
    granska = null; genererar = true; genFel = ''; genSek = 0
    genTimer = setInterval(() => (genSek += 1), 1000)
    try {
      const r = await genereraBildsvep(info, match.sport || '', '', fakta)
      if (r?.ok && r.bildsvep) {
        caption = r.bildsvep
        // Källfältet följer med från Generera — webbtexten byggs härifrån.
        if (r.referat) referat = r.referat
      }
      else genFel = r?.fel || 'Kunde inte generera texten.'
    } catch (e) {
      genFel = 'Kunde inte generera texten.'
    } finally {
      // finally: knappen får aldrig fastna på "Genererar…" om anropet kastar
      genererar = false
      clearInterval(genTimer); genTimer = null
    }
  }

  // Länkar
  let galleriUrl = ''
  let hemsidaUrl = ''

  // Token-upplösning — delad modell i lib/webtext.js (Innehåll läser samma
  // referat till matchartikeln och måste tolka texten exakt lika).
  function handle(namn) { return (lagAlla.find((x) => x.namn === namn)?.instagram || '').replace(/^@/, '') }
  function losText(text, { web = false } = {}) {
    return losTextDelad(text,
      tokenVals({ match, res: resNu, handle: handle(match?.lag_hemma), galleriUrl, hemsidaUrl, web }),
      { web })
  }
  // B2: realtidsförhandsvisning kopplad till texten (social med @/#, webb utan).
  $: capSocial = losText(caption)
  // Webben = referat-källfältet (F18FM-2); strippad social text bara som
  // fallback för material sparade före v34.
  $: capWebb = referat.trim() ? losText(referat, { web: true }) : losText(caption, { web: true })

  // ── Steg 2: Skicka till (kanaler + beskärning) ──────────────────────────────
  // Format-koder = backendens (story_overlay.FORMAT_H). Etikett = kod med ':'.
  // §4 (handoff 11 jul): Webbartikel-kanalen borttagen — webbartikeln byggs i
  // Innehåll (matchartikel-editorn). Matchpublicering gör Live/SoMe och
  // PRODUCERAR referatet/materialet som Innehåll hämtar.
  const KANALER = [
    { key: 'live', namn: 'Live-story', under: 'Instagram Story', format: ['9x16'], wide: false },
    { key: 'ig', namn: 'IG-inlägg', under: 'Instagram · karusell', format: ['4x5', '1x1'], wide: false },
    { key: 'fb', namn: 'Facebook', under: 'Facebook-sida', format: ['1x1', '4x5', '1.91x1'], wide: false },
  ]
  const fmtEti = (f) => f.replace('x', ':')
  // Kanaler bär format + på/av + bildantal (p.4) — beskärningen (fokus/zoom)
  // sitter på FOTOT (Steg 1), delas av alla kanaler; kanalens format omformar
  // bara ramen.
  // p.3: IG-inlägget har två vägar med olika tak: posta direkt via
  // integrationen (API-gräns 10 för karusell) eller exportera till disk (20).
  const IG_TAK = { direkt: 10, disk: 20 }
  // p.4: valbart bildantal per kanal, kanalens tak synligt. Inget fast antal.
  let ch = {
    live: { on: true, fmt: '9x16', antal: 1 },
    ig: { on: true, fmt: '4x5', antal: 6, vag: 'direkt' },
    fb: { on: false, fmt: '1x1', antal: 6 },
  }
  const CH_TAK = { live: 10, fb: 20 }
  function takFor(k) { return k === 'ig' ? IG_TAK[ch.ig.vag] : CH_TAK[k] }
  function toggleCh(k) { ch[k].on = !ch[k].on; ch = ch }
  function sattFmt(k, f) { ch[k].fmt = f; ch = ch }
  function sattAntal(k, d) {
    ch[k].antal = Math.max(1, Math.min(takFor(k), (ch[k].antal || 1) + d)); ch = ch
  }
  // Byte av IG-väg klampar bildantalet mot vägens tak (§A3).
  function sattVag(v) { ch.ig.vag = v; ch.ig.antal = Math.min(ch.ig.antal, IG_TAK[v]); ch = ch }

  // ResultatRemsan sparade → spegla värdet (används vid publicering + token).
  // Stämpla tiden: pollen ska inte dra tillbaka ett äldre mobil-värde ovanpå
  // det vi just skrev (och backend har redan speglat ut vår ändring).
  function onResSparat(e) { resNu = e.detail; senastEgen = new Date().toISOString() }

  // ── Publiceringsrad (fan-out) ───────────────────────────────────────────────
  $: aktiva = KANALER.filter((k) => ch[k.key].on)
  let pubKor = false
  let pubResultat = []             // [{kanal, ok, text}]
  let pubFlash = false

  let materialId = null            // raden vi skriver utkast/utfall till för aktuellt mål
  $: fixtur = match ? (isEvent ? match.lag_hemma : `${match.lag_hemma} – ${match.lag_borta}`) : ''
  // Målfälten som spar-/publicerings-raderna bär: match ELLER turnering.
  $: malFalt = arTurnering
    ? { mal_typ: 'turnering', tavling_id: match.tavling_id, match_id: null }
    : { mal_typ: 'match', match_id: match?.id }

  async function spara() {
    if (!match) return
    // channels lagras som ren array — store json-kodar själv (JSON.stringify här
    // gav en json-sträng inuti en json-sträng).
    const r = await sparaMaterial({ id: materialId || undefined,
      kind: 'some', status: 'utkast', ...malFalt,
      match_namn: fixtur, caption, referat, publiceras: publiceras || null,
      channels: aktiva.map((k) => k.key), foto: coverPath,
      // Bildval + kanalconfig följer med även i UTKAST (tidigare bara vid
      // publicering) — annars går bildvalet inte att återställa vid återbesök.
      banor: Object.fromEntries(aktiva.map((k) => [k.key, kanalConfig(k.key)])) })
    if (r?.ok) materialId = r.id
    materials = await listaMaterial()
    pubFlash = true; setTimeout(() => (pubFlash = false), 1800)
  }

  // Radera en materialrad (MP-död: raderaMaterial var en tappad funktion —
  // väckt med två-klicks-armering).
  let raderaArm = null
  async function taBortMaterial(mt) {
    if (raderaArm !== mt.id) { raderaArm = mt.id; setTimeout(() => { if (raderaArm === mt.id) raderaArm = null }, 2600); return }
    raderaArm = null
    await raderaMaterial(mt.id)
    if (materialId === mt.id) materialId = null
    materials = await listaMaterial()
    dispatch('materialAndrat')
  }

  // ── Ett kanalanrop, byggt som ÅTERKÖRBAR config ────────────────────────────
  // "Försök igen" måste rendera exakt samma bilder som första försöket. Därför
  // byggs varje kanals anrop som ett rent data-objekt som sparas på materialet,
  // och körs av EN funktion — både vid publicering och vid omförsök.
  const _crop = (p) => ({ path: p.path, fokus: p.fokus, zoom: p.zoom })
  function kanalConfig(key) {
    // p.4: varje kanal tar sitt valda antal foton (omslaget först). Live-storyn
    // är en enda overlay-frame → minst omslaget, men respekterar taket uppåt.
    const antal = Math.max(1, Math.min(ch[key].antal || 1, takFor(key)))
    const bilder = ordnadeFoton.slice(0, antal).map(_crop)
    const payload = { kanal: key, format: ch[key].fmt, bilder,
      moment: isEvent ? 'nasta_match' : 'resultat', tema, ...malFalt,
      caption: losText(caption),
      stallning: resNu.resultat, mellan: resNu.mellan, mal_rad: resNu.malskyttar,
      // Friidrott: disciplin/tillstånd/resultat → skapa_friidrott_story (D2)
      ...(friAktiv && fri.disciplinId ? { friidrott: friPayload() } : {}) }
    // p.3: IG-vägen (direkt via integrationen / export till disk) följer med.
    if (key === 'ig') payload.vag = ch.ig.vag
    return { typ: 'kanal', payload }
  }

  // Legacy-rader (sparade före den här formen) saknar `typ`/payload och går inte
  // att köra om — deras bildvägar pekar på ett annat renderflöde.
  const kanKoraOm = (cfg) => !!cfg && (cfg.typ === 'webb' || cfg.typ === 'kanal')

  async function korKanal(key, cfg, test, test_mapp) {
    try {
      // 'webb' skapas inte längre här (§4) — grenen finns kvar för "Försök
      // igen" på material sparade FÖRE borttagningen (config bor på raden).
      if (cfg.typ === 'webb') {
        const r = await publiceraInnehallNatet({ ...cfg.payload, test_mapp }, test)
        return { ok: !!r?.ok, text: r?.fel || (test ? 'Testfil · 1 bild' : 'Publicerad') }
      }
      const r = await publiceraKanal({ ...cfg.payload, test, test_mapp })
      const antal = r?.antal ?? 0
      const bildord = `${antal} bild${antal === 1 ? '' : 'er'}`
      // p.3: IG "Exportera till disk" postar inte — visa att den exporterats.
      const text = r?.fel
        || (r?.exporterad ? `Exporterat till disk · ${bildord}`
            : test ? `Testfil · ${bildord}` : bildord)
      return { ok: !!r?.ok && (r.publicerad !== false), text }
    } catch (e) {
      return { ok: false, text: 'Fel: ' + (e?.message || e) }
    }
  }

  // 'story' är den gamla nyckeln för Live-storyn — legacy-rader bär den ännu.
  // 'webb' likaså: kanalen är borta ur "Skicka till" (§4) men gamla material-
  // rader kan bära den och måste kunna visas + köras om.
  const KANALNAMN = { ...Object.fromEntries(KANALER.map((k) => [k.key, k.namn])),
    story: 'IG Story', webb: 'Webbartikel' }
  const felKanaler = (chRes) => Object.keys(chRes).filter((k) => chRes[k] !== 'ok')

  // Skriver utfallet på materialraden: status + per-kanal-resultat + configen
  // som krävs för ett omförsök. Utan den här raden kan Rails "delvis"-prick
  // aldrig tändas och "Försök igen" har inget att köra om.
  // `bas` bär radens IDENTITET (id/match/bildtext) — ett omförsök kan gälla ett
  // material för en annan match än den som är öppen, och får inte skriva om den.
  async function sparaUtfall(bas, chRes, cfgs, note) {
    const fel = felKanaler(chRes)
    const r = await sparaMaterial({ ...bas, kind: 'some',
      status: fel.length ? 'delvis' : 'publicerad',
      channels: Object.keys(chRes), banor: cfgs, ch_results: chRes,
      historik_note: note !== undefined ? note
        : (fel.length ? `${fel.map((k) => KANALNAMN[k] || k).join(', ')} föll` : '') })
    materials = await listaMaterial()
    dispatch('materialAndrat')
    return r
  }

  async function publicera() {
    if (!match || !aktiva.length) return
    pubKor = true; pubResultat = []
    const test = $testMode
    const test_mapp = test ? (await nyTestPaketMapp())?.path : undefined   // gemensam mapp för hela fan-out:en
    const cfgs = {}
    const chRes = {}
    const ut = []
    for (const k of aktiva) {
      const cfg = kanalConfig(k.key)
      cfgs[k.key] = cfg
      const r = await korKanal(k.key, cfg, test, test_mapp)
      chRes[k.key] = r.ok ? 'ok' : 'fail'
      ut.push({ kanal: k.namn, ok: r.ok, text: r.text })
    }
    pubResultat = ut
    pubKor = false
    // Testläge persisterar aldrig material (samma kontrakt som lib/testlage.js).
    if (!test) {
      const r = await sparaUtfall({ id: materialId || undefined, ...malFalt,
        match_namn: fixtur, caption, referat, publiceras: publiceras || null, foto: coverPath }, chRes, cfgs)
      if (r?.ok) materialId = r.id
    }
  }

  // ── Materiallistan ────────────────────────────────────────────────────────
  // Visar vad som faktiskt gick ut. Utan den pekar Rails "delvis"-prick på tomma
  // luften och en fallen kanal går inte att försöka om.
  let matFilter = 'alla'
  let historikOppen = {}
  const toggleHistorik = (id) => (historikOppen = { ...historikOppen, [id]: !historikOppen[id] })

  const MKR = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function nartext(iso) {
    const [datum, tid] = (iso || '').replace(' ', 'T').split('T')
    const [, m, d] = (datum || '').split('-').map(Number)
    return d ? `${d} ${MKR[m - 1]} ${(tid || '').slice(0, 5)}` : (iso || '')
  }

  // §10: kön — schemalagda utkast överst (närmast tid först), sedan övrigt
  // nyast först. Ett schemalagt material vars tid passerat är "försenat".
  const arSchemalagd = (m) => m.status === 'utkast' && (m.publiceras || '').trim()
  $: matSorterat = [...(materials || [])]
    .sort((a, b) => {
      const sa = arSchemalagd(a), sb = arSchemalagd(b)
      if (sa !== sb) return sa ? -1 : 1
      if (sa && sb) return (a.publiceras || '').localeCompare(b.publiceras || '')
      return (b.uppdaterad || '').localeCompare(a.uppdaterad || '')
    })
  $: matFiltrerat = matSorterat.filter((m) => matFilter === 'alla' || m.status === matFilter)
  $: matVy = matFiltrerat.map((m) => {
    const chRes = m.ch_results || {}
    const cfgs = m.banor || {}
    const fel = felKanaler(chRes)
    const schemalagd = arSchemalagd(m)
    const forsenad = schemalagd && m.publiceras.replace(' ', 'T') < new Date().toISOString().slice(0, 16)
    return { ...m,
      schemalagd, forsenad,
      titel: m.kind === 'live' ? `${m.moment || 'Story'}-story` : 'SoMe-paket',
      nar: nartext(m.uppdaterad),
      kanaler: m.channels || Object.keys(chRes),
      chRes, fel,
      // En legacy-rad har sparat bildvägar för ett annat renderflöde — att köra
      // om den skulle posta andra bilder än första försöket gjorde.
      omkorbara: fel.filter((k) => kanKoraOm(cfgs[k])),
      historik: (m.history || []).map((h) => ({ ...h, nar: nartext(h.when) })) }
  })
  $: matAntal = {
    alla: matSorterat.length,
    utkast: matSorterat.filter((m) => m.status === 'utkast').length,
    publicerad: matSorterat.filter((m) => m.status === 'publicerad').length,
    delvis: matSorterat.filter((m) => m.status === 'delvis').length,
  }
  const STATUSTEXT = { utkast: 'Utkast', publicerad: 'Publicerad', delvis: 'Delvis publicerad' }

  // ── Försök igen: kör om ENDAST felkanalerna, med sparad config ─────────────
  let retryId = null
  let retryKlar = null
  async function forsokIgen(mt) {
    // Testläget får inte röra en persisterad materialrad — och ett omförsök är
    // per definition en skrivning på den. Knappen är avstängd i testläge.
    if (retryId || $testMode) return
    const cfgs = mt.banor || {}
    const fel = felKanaler(mt.ch_results || {}).filter((k) => kanKoraOm(cfgs[k]))
    if (!fel.length) return
    retryId = mt.id; retryKlar = null
    const test = false
    const test_mapp = undefined
    const nya = { ...mt.ch_results }
    for (const key of fel) {
      const r = await korKanal(key, cfgs[key], test, test_mapp)
      nya[key] = r.ok ? 'ok' : 'fail'
    }
    // Historiken namnger vilka kanaler DETTA försök gällde — inte de som är kvar.
    await sparaUtfall({ id: mt.id, match_id: mt.match_id, match_namn: mt.match_namn,
      caption: mt.caption, referat: mt.referat, publiceras: mt.publiceras, foto: mt.foto }, nya, cfgs,
      `omförsök — ${fel.map((k) => KANALNAMN[k] || k).join(', ')}`)
    retryId = null
    if (!felKanaler(nya).length) {
      retryKlar = mt.id
      setTimeout(() => (retryKlar = retryKlar === mt.id ? null : retryKlar), 2600)
    }
  }

  // På gång (webb) + mobilsynk flyttade HÄRIFRÅN: På gång bor nu under
  // Webb → På gång (egen nav-post, §C); mobilsynken sker automatiskt i
  // bakgrunden (p.2) — ingen knapp i Matchpublicering längre.

  // ── Live nu (snabbflöde) ────────────────────────────────────────────────────
  let liveOpen = false
  let liveMoment = 'result'
  let livePhoto = ''
  let livePreview = ''
  let liveTest = false
  let liveFas = 'compose'          // compose | publishing | done
  let liveResultat = null
  // Live-flödet har sitt EGET bildurval (skilt från Steg 1) — under match vill
  // man posta senaste bilden ur live-katalogen, inte den kurerade delmängden.
  let liveFolderPath = ''
  let livePhotos = []              // sökvägar (egen lista, delar bara thumb-cachen)
  let liveLaddar = false
  async function liveLasKatalog() {
    if (!liveFolderPath) return
    liveLaddar = true
    const lista = await listaSomeBilder(liveFolderPath)
    liveLaddar = false
    livePhotos = lista || []
    laddaThumbs(livePhotos)
    if ((!livePhoto || !livePhotos.includes(livePhoto)) && livePhotos[0]) livePhoto = livePhotos[0]
    liveRendera()
  }
  async function liveValjKatalog() {
    const r = await valjMapp('Välj katalog för Live-story (senaste bilderna)')
    if (r?.ok && r.path) { liveFolderPath = r.path; await liveLasKatalog() }
  }
  $: liveMoms = (() => {
    const l = [{ k: 'start', label: profil.start_moment || 'Avspark' }, { k: 'mid', label: profil.mid_label || 'Halvtid' }]
    if (profil.has_scorers) l.push({ k: 'scorer', label: 'Målgörare' })
    l.push({ k: 'result', label: profil.res_label || 'Resultat' })
    return l
  })()
  const LIVEMOM = { start: 'avspark', mid: 'halvtid', scorer: 'malgorare', result: 'resultat' }
  function liveOppna() {
    liveOpen = true; liveFas = 'compose'
    // Ladda Live-katalogen om den är tom — startpunkt = huvudkatalogen, men egen lista.
    if (!livePhotos.length) { if (!liveFolderPath) liveFolderPath = folderPath; if (liveFolderPath) liveLasKatalog() }
    liveRendera()
  }
  function liveStang() { liveOpen = false }
  function liveSattMoment(k) { liveMoment = k; liveRendera() }
  function liveSattFoto(p) { livePhoto = p; liveRendera() }
  let _lpt
  function liveRendera() {
    if (_lpt) clearTimeout(_lpt)
    _lpt = setTimeout(async () => {
      if (!livePhoto || !match) return
      const r = await forhandsgranskaStory({ foto: livePhoto, moment: LIVEMOM[liveMoment] || 'resultat',
        match_id: match.id, tema, format: '9x16', preview_slot: 'livenu',
        stallning: resNu.resultat, mellan: resNu.mellan, mal_rad: resNu.malskyttar })
      if (r?.ok && r.path) { const t = await thumbForBild(r.path); livePreview = t?.ok ? t.data_uri : '' }
    }, 400)
  }
  async function livePublicera() {
    liveFas = 'publishing'
    const r = await publiceraLiveStory({ foto: livePhoto, moment: LIVEMOM[liveMoment] || 'resultat',
      tema, match_id: match?.id, test: liveTest })
    liveResultat = r
    liveFas = 'done'
    materials = await listaMaterial(); dispatch('materialAndrat')
  }
  function liveReset() { liveFas = 'compose'; liveResultat = null }

  // ── Hämta bilder (ingest) ───────────────────────────────────────────────────
  let ingestOpen = false
  let ingKort = []
  let ingValt = ''
  let ingProt = ''
  let ingSteg = 0                  // 0 kort valt, 1 exporterat
  let ingKor = false
  async function ingestOppna() { ingestOpen = true; ingSteg = 0; const r = await listaMinneskort(); ingKort = r?.kort || []; if (ingKort[0]) ingValt = ingKort[0].path }
  function ingestStang() { ingestOpen = false }
  $: ingSkyddade = ingKort.find((k) => k.path === ingValt)?.skyddade ?? 0
  async function ingValjExport() { const r = await valjMapp('Exportera skyddade bilder till…'); if (r?.ok) ingProt = r.path }
  async function ingExportera() {
    if (!ingValt || !ingProt) return
    ingKor = true
    const r = await exporteraSkyddade(ingValt, ingProt, true)
    ingKor = false
    if (r?.ok) ingSteg = 1
  }
  async function ingValjKatalog() {
    const r = await valjMapp('Välj katalog med de färdigredigerade bilderna')
    if (r?.ok && r.path) { folderPath = r.path; await lasKatalog(); ingestOpen = false }
  }
</script>

<div class="panel">
  <!-- Huvud — 6a: enrads, ingen kicker; primär åtgärd till höger. -->
  <div class="topp">
    <div class="topptitel">
      <h1 class="scd">Matchpublicering</h1>
      <span class="toppsub">Skapa en gång · publicera överallt</span>
    </div>
    <button class="livenu" on:click={liveOppna}><span class="ldot"></span>Live nu — story direkt</button>
  </div>

  <!-- Match / event / turnering-väljare (p.5: event = match utan motståndare;
       Fas 3: turnering = SoMe mot hela tävlingen, ingen enskild match) -->
  <div class="matchrad">
    <span class="mlbl">Mål</span>
    <div class="mdd">
      <button class="mddbtn" on:click={() => (matchOpen = !matchOpen)}>
        <span class="mddnamn">{matchTitel}</span>
        <span class="mddmeta">{matchMeta}</span><span class="mddpil">▾</span>
      </button>
      {#if matchOpen}
        <button class="mddskArm" on:click={() => (matchOpen = false)} aria-label="stäng"></button>
        <div class="mddlista">
          <div class="mddcaps">Välj match eller heldagsevent</div>
          {#each matcher as m (m.id)}
            {@const mEvent = m.event || m.heldag || !(m.lag_borta || '').trim()}
            <button class="mddrad" class:pa={m.id === match?.id} on:click={() => valjMatch(m.id)}>
              <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
              <div class="mddi"><div class="mddf">{mEvent ? m.lag_hemma : `${m.lag_hemma} – ${m.lag_borta}`}</div>
                <div class="mdds">{[datumTxt(m.datum), mEvent ? 'Heldagsevent' : m.sport].filter(Boolean).join(' · ')}</div></div>
              {#if mEvent}<span class="mddkom event">Event</span>
              {:else if m.resultat}<span class="mddres scd">{m.resultat}</span>
              {:else}<span class="mddkom">Kommande</span>{/if}
            </button>
          {/each}
          {#if tavlingar.length}
            <div class="mddcaps">Turnering — publicera mot hela tävlingen</div>
            {#each tavlingar as t (t.id)}
              <button class="mddrad" class:pa={match?.tavling_id === t.id} on:click={() => valjTurnering(t.id)}>
                <span class="grendot turn"></span>
                <div class="mddi"><div class="mddf">{t.namn}</div>
                  <div class="mdds">{[t.sport, t.ort].filter(Boolean).join(' · ')}</div></div>
                <span class="mddkom turn">Turnering</span>
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </div>
    <span class="mhint">{arTurnering ? '— publicering för hela turneringen, utan enskild match' : '— resultatmodellen följer matchens sport'}</span>
  </div>

  <!-- Delad resultatremsa (p.5: gömd för heldagsevent — resultat är irrelevant) -->
  {#if match && !isEvent}
    <ResultatRemsa {match} {profil} {lagAlla} extern={liveExtern} externRev={liveRev}
      {forsFran} on:sparat={onResSparat} />
    <div class="remstext">Resultat &amp; målgörare fylls i <b>en gång här</b> — samma värden matas in i story,
      inlägg och webbartikel. Mobilsynken sker <b>automatiskt i bakgrunden</b> — ingen knapp behövs.</div>
  {:else if match && friAktiv}
    <!-- Friidrott (B-002): grenens story-fält — driver D2-overlayn på omslaget -->
    <div class="frirad">
      {#if !discipliner.length}
        <span class="remstext eventrem">Inga grenar på tävlingen ännu — lägg upp dem under Lag &amp; tävlingar (Grenar &amp; deltagare).</span>
      {:else}
        <select bind:value={fri.disciplinId} title="Gren">
          {#each discipliner as d (d.id)}<option value={d.id}>{d.namn}</option>{/each}
        </select>
        <select bind:value={fri.tillstand} title="Tillstånd">
          <option value="start">Start</option>
          <option value="resultat">Resultat</option>
          <option value="placering">Placering</option>
        </select>
        <input bind:value={fri.moment} placeholder="Moment (Kval/Final…)" />
        {#if fri.tillstand !== 'start'}
          <select bind:value={fri.deltagareId} title="Deltagare">
            <option value="">Deltagare…</option>
            {#each (friDisc?.deltagare || []) as p (p.id)}
              <option value={p.id}>{p.namn}{p.klubb ? ` · ${p.klubb}` : ''}</option>
            {/each}
          </select>
        {/if}
        {#if fri.tillstand === 'resultat'}
          <input bind:value={fri.resultat} placeholder={friDisc?.typ === 'sprint' ? '10,12' : friDisc?.typ === 'medel' ? '1.45,32' : friDisc?.typ === 'mangkamp' ? '8 421' : '6,42'} title="Resultat" />
          {#if friDisc?.typ === 'hoppkast'}
            <input class="friserie" bind:value={fri.serie} placeholder="Serie: 6,21 6,42 x 6,38" title="Hoppserie (x = övertramp)" />
          {/if}
        {:else if fri.tillstand === 'placering'}
          <input bind:value={fri.placering} placeholder="1 / DNF" title="Placering (siffra eller DNF/DNS/DQ)" />
          <input bind:value={fri.resultat} placeholder="Resultat (valfritt)" />
        {/if}
      {/if}
    </div>
    <div class="remstext eventrem">Friidrott — omslaget renderas med grenens story-mall (start · resultat · placering). Start tar grenens deltagare (max 3) automatiskt.</div>
  {:else if match && arTurnering}
    <div class="remstext eventrem">Turnering — publicering för hela tävlingen (t.ex. dagens matcher eller vecko-svep). Inga resultatsiffror; samma bilder, text och kanaler som en match.</div>
  {:else if match && isEvent}
    <div class="remstext eventrem">Heldagsevent — inga resultatsiffror. Samma bilder, text och kanaler som en match.</div>
  {/if}

  <!-- Flikar (p.1): Innehåll · Kanaler & publicera · Publicerat -->
  <div class="mpflikar">
    {#each MP_FLIKAR as [k, etikett] (k)}
      <button class="mpflik" class:on={mpTab === k} on:click={() => (mpTab = k)}>{etikett}</button>
    {/each}
  </div>

  <!-- ===== Flik: Innehåll ===== -->
  {#if mpTab === 'innehall'}
  <div class="steg"><span class="stegnr scd">1</span><span class="stegnamn">Innehåll</span>
    <span class="steghint">— skapas en gång, återanvänds i alla utgångar</span></div>
  <div class="grid2 s1">
    <!-- Bilder -->
    <div class="kort">
      <div class="korthuvud"><span class="caps">Bilder</span><span class="valda">{selCount} valda</span></div>
      <div class="katrad">
        <span class="klbl">Katalog</span>
        <input class="mono" bind:value={folderPath} on:change={lasKatalog} placeholder="Lightroom-exportens mapp" />
        <button class="sek" on:click={valjKatalog}>Välj katalog…</button>
        <button class="sek" on:click={ingestOppna}>Hämta bilder…</button>
      </div>
      {#if laddarBilder}<div class="hint">Läser katalogen…</div>{/if}
      {#if photos.length}
        <div class="bildrutnat">
          {#each photos as p, i}
            <div class="bild" class:sel={p.sel} class:aktiv={aktivIdx === i} class:tom={!thumbs[p.path]}
              style={thumbs[p.path] ? `background-image:url(${thumbs[p.path]})` : ''}
              role="button" tabindex="0" on:click={() => valjAktiv(i)} on:keydown={(e) => e.key === 'Enter' && valjAktiv(i)}>
              {#if p.sel}<button class="bavvalj" title="Ta bort" on:click|stopPropagation={() => avvalj(i)}>✕</button>{/if}
              {#if p.cover}<span class="omslag">OMSLAG</span>{/if}
            </div>
          {/each}
        </div>
        <div class="hint">Klicka en bild för att välja + justera dess beskärning nedan · ✕ tar bort · sätt omslag i editorn.</div>

        {#if aktivFoto}
          <div class="cropeditor">
            <div class="cehuvud">
              <span class="cecaps">Beskärning · bild {selectedPhotos.indexOf(aktivFoto) + 1} av {selCount}</span>
              <div class="cenav">
                <button class="cebtn" on:click={() => stega(-1)} disabled={selCount < 2} title="Föregående">‹</button>
                <button class="cebtn" on:click={() => stega(1)} disabled={selCount < 2} title="Nästa">›</button>
                <button class="ceomslag" class:on={aktivFoto.cover} on:click={() => sattOmslag(aktivIdx)}>{aktivFoto.cover ? '★ Omslag' : '☆ Sätt som omslag'}</button>
              </div>
            </div>
            <div class="cropbox"
              on:pointerdown={(e) => fokusNed(aktivIdx, e)} on:pointermove={(e) => fokusRor(aktivIdx, e)}
              on:pointerup={fokusUpp} on:pointerleave={fokusUpp}>
              {#if thumbs[aktivFoto.path]}
                <img class="cropimg" src={thumbs[aktivFoto.path]} alt="" draggable="false" on:load={(e) => paFotoLast(e, aktivFoto.path)} />
                {@const ram = ramFor(aktivFoto.fokus, aktivFoto.zoom, previewFmt, ratios[aktivFoto.path] || 1.5)}
                <div class="cropram" style="left:{ram.l}%;top:{ram.t}%;width:{ram.w}%;height:{ram.h}%;border-color:{grenFarg(match?.hem_gren)};box-shadow:0 0 14px {grenFarg(match?.hem_gren)}66, 0 0 0 9999px rgba(7,9,12,.6)"></div>
                <span class="fokusdot" style="left:{aktivFoto.fokus.x}%;top:{aktivFoto.fokus.y}%"></span>
              {/if}
            </div>
            <div class="ceverktyg">
              <div class="fmtprev"><span class="ftxt">Visa som</span>
                {#each ['9x16', '4x5', '1x1'] as f}<button class="fmtchip" class:on={previewFmt === f} on:click={() => (previewFmt = f)}>{fmtEti(f)}</button>{/each}
              </div>
              <div class="zoomrad">
                <input type="range" min="1" max="2.6" step="0.05" value={aktivFoto.zoom} on:input={(e) => sattFotoZoom(aktivIdx, e.target.value)} />
                <span class="zoomtxt">Zoom {Math.round(aktivFoto.zoom * 100)}%</span>
              </div>
            </div>
            <div class="crophint">Klicka/dra i bilden för fokus. Fokus + zoom följer bilden till alla kanaler; ramen visar valt format.</div>
          </div>
        {/if}
      {:else}
        <div class="tombild">Peka ut Lightroom-exportens katalog för att välja bilder — eller använd <button class="minilank" on:click={ingestOppna}>Hämta bilder</button>.</div>
      {/if}
    </div>
    <!-- Text -->
    <div class="kort">
      <div class="korthuvud">
        <span class="caps">Text</span>
        <div class="genrad">
          <button class="genbtn" on:click={oppnaGranska} disabled={!match || genererar || laddarFraga} title="Skriv bildtexten med Claude">
            <svg viewBox="0 0 24 24" fill="currentColor" class="stjarna"><path d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/></svg>
            {laddarFraga ? 'Bygger fråga…' : genererar ? 'Genererar…' : 'Generera med Claude'}
          </button>
          {#if caption && !genererar && !laddarFraga}<button class="genigen" on:click={oppnaGranska} disabled={!match} title="Generera igen">↻ Igen</button>{/if}
        </div>
      </div>
      {#if granska}
        <div class="granska">
          <div class="granskaTitel">Granska frågan innan den skickas till Claude</div>
          <div class="granskaHint">Tar cirka 2 minuter — websökning används bara för det som inte redan står här
            (nästa match, tabellkontext, @-handles).</div>
          <pre class="granskaFraga">{granska}</pre>
          <div class="granskaKnappar">
            <button class="sek" on:click={avbrytGranska}>Avbryt</button>
            <button class="prim" on:click={skickaTillClaude}>Skicka till Claude ›</button>
          </div>
        </div>
      {:else if genererar}
        <div class="genprog"><span class="genspin"></span>Genererar… {genSek}s (websöker matchfakta, tar ofta ~2 min)</div>
      {/if}
      <textarea class="cap" rows="4" bind:this={capEl} bind:value={caption}></textarea>
      <div class="tokrad"><span class="tlbl">Infoga:</span>
        {#each TOKENS as t}<button class="tok" on:click={() => insertToken(t)}>{t}</button>{/each}</div>
      <div class="tokrad"><span class="tlbl">Ton:</span>
        {#each TONER as t}<button class="tonchip" class:on={ton === t} on:click={() => (ton = t)}>{t}</button>{/each}</div>
      <!-- p.6: egna inspel till Claude-genereringen (utöver ton + matchfakta) -->
      <div class="inspel">
        <div class="inspelcaps">Inspel till genereringen</div>
        <div class="vinkelchips">
          {#each VINKLAR as [v, etikett] (v)}
            <button class="vinkelchip" class:on={vinklar.includes(v)} on:click={() => toggleVinkel(v)}>{etikett}</button>
          {/each}
        </div>
        <input class="inspelfalt" bind:value={inspel}
          placeholder="Egna detaljer — avgörande i 90:e, publikrekord, lyft målvakten…" />
        <div class="inspelhint">Skickas med som styrning när texten genereras — utöver matchfakta.</div>
      </div>
      {#if genFel}<div class="genfel">{genFel}</div>{/if}
      <div class="f"><label>Referat <span class="lmut">— webbens källtext (utan rubrik/länkar/taggar)</span></label>
        <textarea rows="4" bind:value={referat} placeholder="Fylls av ✨ Generera — eller skriv själv. Tomt = webben faller tillbaka på strippad social text."></textarea></div>
      <div class="hint">Sociala kanaler får @ och #. <b>Webben byggs från referatet</b> (F18FM-2)
        — webbartikeln byggs i <b>Innehåll</b>, som hämtar referatet härifrån.</div>
      <div class="prevgrid">
        <div class="prevkol">
          <div class="prevlbl">Förhandsvisning · sociala</div>
          <div class="prevtext">{capSocial || '—'}</div>
        </div>
        <div class="prevkol">
          <div class="prevlbl">Förhandsvisning · webb</div>
          <div class="prevtext">{capWebb || '—'}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Länkar -->
  <div class="kort lankkort">
    <div class="korthuvud"><span class="caps">Länkar</span><span class="hint2">Fylls i en gång · bifogas per kanal</span></div>
    <div class="grid2">
      <div class="f"><label>Galleri <span class="lmut">— fler bilder / köp</span></label>
        <input class="mono" bind:value={galleriUrl} placeholder="foto.dalecarliaphoto.se/…" /></div>
      <div class="f"><label>Hemsida <span class="lmut">— matchreferat</span></label>
        <input class="mono" bind:value={hemsidaUrl} placeholder="dalecarliaphoto.se/matcher/…" /></div>
    </div>
    <!-- §4: webb-placeringschipet borta — webbartikeln byggs i Innehåll. -->
    <div class="placering">
      <span class="pcaps">Så placeras de:</span>
      <span class="pchip">Live-story · länk-sticker</span>
      <span class="pchip">IG · bio + första kommentar</span>
      <span class="pchip">Facebook · i inlägget</span>
    </div>
  </div>
  {/if}

  <!-- ===== Flik: Kanaler & publicera ===== -->
  {#if mpTab === 'kanaler'}
  <div class="steg"><span class="stegnr scd">2</span><span class="stegnamn">Kanaler &amp; publicera</span>
    <span class="steghint">— format, bildantal + på/av per kanal · beskärningen sätts per foto i Innehåll och följer med hit</span></div>
  <div class="kanaler">
    {#each KANALER as k}
      <!-- Inline (inte takFor()) så Svelte spårar ch.ig.vag och räknar om taket
           när IG-vägen byts — en funktion döljer ch-beroendet för reaktiviteten. -->
      {@const tak = k.key === 'ig' ? IG_TAK[ch.ig.vag] : CH_TAK[k.key]}
      <div class="kanal" class:av={!ch[k.key].on} class:wide={k.wide}>
        <div class="kanalhuvud" on:click={() => toggleCh(k.key)}>
          <span class="chk" class:pa={ch[k.key].on}>{ch[k.key].on ? '✓' : ''}</span>
          <div class="kmeta"><div class="knamn">{k.namn}</div><div class="kunder">{k.under}</div></div>
        </div>
        <div class="kanalkropp">
          {#if k.format.length > 1}
            <div class="fmtchips">
              {#each k.format as f}<button class="fmtchip" class:on={ch[k.key].fmt === f} on:click={() => sattFmt(k.key, f)}>{fmtEti(f)}</button>{/each}
            </div>
          {/if}
          <!-- p.3: IG-inlägget — valbar väg (klampar bildantalet mot vägens tak) -->
          {#if k.key === 'ig'}
            <div class="igvag">
              <button class="igval" class:on={ch.ig.vag === 'direkt'} on:click={() => sattVag('direkt')}>
                <span class="igdot" class:pa={ch.ig.vag === 'direkt'}></span><span class="igtxt">Posta direkt via integrationen</span><span class="igmax">max {IG_TAK.direkt}</span></button>
              <button class="igval" class:on={ch.ig.vag === 'disk'} on:click={() => sattVag('disk')}>
                <span class="igdot" class:pa={ch.ig.vag === 'disk'}></span><span class="igtxt">Exportera till disk</span><span class="igmax">max {IG_TAK.disk}</span></button>
            </div>
          {/if}
          <!-- p.4: valbart bildantal med kanalens tak synligt -->
          <div class="antalrad">
            <span class="antallbl">Bilder</span>
            <div class="stepper">
              <button class="stepbtn" on:click={() => sattAntal(k.key, -1)} disabled={ch[k.key].antal <= 1}>−</button>
              <span class="stepval scd">{ch[k.key].antal}</span>
              <button class="stepbtn" on:click={() => sattAntal(k.key, 1)} disabled={ch[k.key].antal >= tak}>+</button>
            </div>
            <span class="antaltak">av max {tak}</span>
          </div>
          <div class="cropbox ro" class:av={!ch[k.key].on}>
            {#if coverPath && thumbs[coverPath] && coverPhoto}
              <img class="cropimg" src={thumbs[coverPath]} alt="" on:load={(e) => paFotoLast(e, coverPath)} />
              {@const ram = ramFor(coverPhoto.fokus, coverPhoto.zoom, ch[k.key].fmt, ratios[coverPath] || 1.5)}
              <div class="cropram" style="left:{ram.l}%;top:{ram.t}%;width:{ram.w}%;height:{ram.h}%;border-color:{grenFarg(match?.hem_gren)};box-shadow:0 0 12px {grenFarg(match?.hem_gren)}55, 0 0 0 9999px rgba(7,9,12,.55)"></div>
            {:else}
              <div class="prevtom">Välj omslag i Innehåll</div>
            {/if}
          </div>
          <div class="crophint">{k.key === 'live' ? 'Omslaget med overlay' : 'Omslag + valda foton, var sin crop'} · {fmtEti(ch[k.key].fmt)}</div>
        </div>
      </div>
    {/each}
  </div>
  {/if}

  <!-- ===== Flik: Publicerat ===== -->
  {#if mpTab === 'publicerat'}
  <!-- Material: vad som faktiskt gick ut, och vägen tillbaka när en kanal föll.
       (På gång-sektionen + mobilsynk-UI är borttagna härifrån — På gång bor nu
       under Webb → På gång, mobilsynken sker automatiskt i bakgrunden.) -->
  <div class="kort">
    <div class="korthuvud">
      <span class="caps">Publicerat &amp; utkast · {matAntal.alla} st</span>
      <div class="matfilter">
        {#each [['alla', 'Alla'], ['utkast', 'Utkast'], ['publicerad', 'Publicerade'], ['delvis', 'Delvis']] as [v, etikett] (v)}
          <button class="matchip" class:on={matFilter === v} on:click={() => (matFilter = v)}>
            {etikett} · {matAntal[v]}
          </button>
        {/each}
      </div>
    </div>

    {#if !matVy.length}
      <div class="hint">{matFilter === 'alla' ? 'Inget material än — spara ett utkast eller publicera.' : 'Inget material i det läget.'}</div>
    {:else}
      <div class="matlista">
        {#each matVy as mt (mt.id)}
          <div class="matrad">
            <div class="matrad1">
              <!-- Klick öppnar materialets match med arbetsytan återställd -->
              <button class="matnamn" title="Öppna i arbetsytan"
                on:click={async () => { if (mt.match_id) { await valjMatch(mt.match_id); mpTab = 'innehall' } }}>{mt.titel}</button>
              <span class="matstatus" class:pub={mt.status === 'publicerad'} class:delvis={mt.status === 'delvis'}
                class:schemalagd={mt.schemalagd} class:forsenad={mt.forsenad}>
                {mt.schemalagd
                  ? (mt.forsenad ? `Dags att publicera · ${nartext(mt.publiceras)}` : `Schemalagd · ${nartext(mt.publiceras)}`)
                  : (STATUSTEXT[mt.status] || mt.status)}
              </span>
              {#if mt.historik.length > 1}
                <button class="histchip" on:click={() => toggleHistorik(mt.id)}>
                  {mt.historik.length} publiceringar {historikOppen[mt.id] ? '▴' : '▾'}
                </button>
              {/if}
              <span class="matnar">{mt.nar}</span>
              <button class="matx" class:armerad={raderaArm === mt.id}
                title={raderaArm === mt.id ? 'Klicka igen för att ta bort' : 'Ta bort materialet'}
                on:click={() => taBortMaterial(mt)}>{raderaArm === mt.id ? 'Ta bort?' : '×'}</button>
            </div>
            <div class="matsub">{mt.match_namn || '—'}</div>

            {#if mt.status === 'delvis'}
              <div class="chrad">
                {#each mt.kanaler as k (k)}
                  <span class="chchip" class:ok={mt.chRes[k] === 'ok'}
                    class:kor={retryId === mt.id && mt.chRes[k] !== 'ok'}>
                    {KANALNAMN[k] || k}
                    {retryId === mt.id && mt.chRes[k] !== 'ok' ? '↻' : (mt.chRes[k] === 'ok' ? '✓' : '✗')}
                  </span>
                {/each}
                {#if mt.omkorbara.length}
                  <button class="retrybtn" disabled={!!retryId || $testMode}
                    title={$testMode ? 'Testläge: publicerar aldrig skarpt' : 'Kör om enbart de kanaler som föll'}
                    on:click={() => forsokIgen(mt)}>
                    {retryId === mt.id ? 'Publicerar…'
                      : `Försök igen — ${mt.omkorbara.map((k) => KANALNAMN[k] || k).join(', ')} ›`}
                  </button>
                {:else}
                  <span class="matvarn">Sparad före uppdateringen — publicera om för att kunna försöka igen</span>
                {/if}
              </div>
            {:else if retryKlar === mt.id}
              <div class="retryklar">✓ Alla kanaler publicerade</div>
            {/if}

            {#if historikOppen[mt.id] && mt.historik.length > 1}
              <div class="histlista">
                {#each mt.historik as h, i}
                  <div class="histrad">
                    <span class="histnar">{h.nar}</span>
                    <span class="histstatus" class:pub={h.status === 'publicerad'}>{STATUSTEXT[h.status] || h.status}</span>
                    <span class="histnote">{[h.note, i === 0 ? 'senaste' : ''].filter(Boolean).join(' · ')}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
    <div class="hint">Klick öppnar materialet för ändring i Innehåll/Kanaler — utkast sparas löpande.</div>
  </div>
  {/if}
</div>

<!-- Publiceringsrad — sidfot, dold på Publicerat-fliken (p.1) -->
{#if mpTab !== 'publicerat'}
<div class="pubrad">
  <div class="pubinfo">
    <div class="pubtitel">Skickas till <b>{aktiva.length} {aktiva.length === 1 ? 'kanal' : 'kanaler'}</b></div>
    <div class="publista">{aktiva.length ? aktiva.map((k) => k.namn).join(' · ') : 'Inga kanaler valda'}</div>
    {#if pubResultat.length}
      <div class="pubres">{#each pubResultat as r}<span class="prc" class:ok={r.ok} class:fel={!r.ok}>{r.ok ? '✓' : '⚠'} {r.kanal}: {r.text}</span>{/each}</div>
    {/if}
  </div>
  {#if pubFlash}<span class="ok">✓ Utkast sparat</span>{/if}
  <!-- §10: schemaläggning — sparas med utkastet, kön visar/påminner. -->
  <label class="schemafalt" title="Schemalägg — materialet hamnar överst i kön och flaggas när tiden är inne (utskicket är fortfarande ditt knapptryck)">
    <span>Publiceras</span>
    <input type="datetime-local" bind:value={publiceras} />
    {#if publiceras}<button class="schemarensa" on:click={() => (publiceras = '')} title="Rensa schemaläggningen">×</button>{/if}
  </label>
  <button class="sek" on:click={spara} disabled={!match}>Spara utkast</button>
  <button class="prim" on:click={publicera} disabled={!match || !aktiva.length || pubKor}>{pubKor ? 'Publicerar…' : `Publicera ${aktiva.length}`}</button>
</div>
{/if}

<!-- Live nu — slide-over -->
{#if liveOpen}
  <div class="slide">
    <button class="slidebak" on:click={liveStang} aria-label="stäng"></button>
    <div class="slidepanel">
      <div class="slidehuvud"><span class="ldot"></span>
        <div class="slidetitel"><div class="scd st">Live nu</div><div class="ss">{match ? `${match.lag_hemma} – ${match.lag_borta}` : ''} · story direkt</div></div>
        <button class="stang" on:click={liveStang}>✕</button></div>

      {#if liveFas === 'compose'}
        <div class="slidekropp">
          <div class="scaps">1 · Moment</div>
          <div class="momrad">{#each liveMoms as m}<button class="mom" class:on={liveMoment === m.k} on:click={() => liveSattMoment(m.k)}>{m.label}</button>{/each}</div>
          <div class="scaps mt">2 · Bild <button class="minilank hb" on:click={liveLasKatalog}>↻ Uppdatera</button></div>
          <div class="livekat">
            <input class="mono" bind:value={liveFolderPath} on:change={liveLasKatalog} placeholder="Live-katalog (senaste bilderna)" />
            <button class="sek sm" on:click={liveValjKatalog}>Välj…</button>
          </div>
          <div class="livebilder">
            {#each livePhotos.slice(0, 12) as p, i}
              <button class="livebild" class:on={livePhoto === p} class:tom={!thumbs[p]} style={thumbs[p] ? `background-image:url(${thumbs[p]})` : ''} on:click={() => liveSattFoto(p)}>
                {#if i === 0}<span class="senast">SENAST</span>{/if}</button>
            {/each}
            {#if liveLaddar}<div class="hint">Läser katalogen…</div>{:else if !livePhotos.length}<div class="hint">Välj en Live-katalog eller Hämta bilder.</div>{/if}
          </div>
          <div class="scaps mt">3 · Förhandsvisning</div>
          <div class="liveprevwrap">
            <div class="liveprev" style="border-color:{grenFarg(match?.hem_gren)};box-shadow:0 0 20px {grenFarg(match?.hem_gren)}66">
              {#if livePreview}<img src={livePreview} alt="" />{:else}<div class="prevtom">Renderar…</div>{/if}
            </div>
          </div>
          <div class="hint c">Riktig 9:16 renderas server-side. Gren-kant + glow följer dam/herr/mixed.</div>
        </div>
        <div class="slidefot">
          <button class="testtoggle" on:click={() => (liveTest = !liveTest)}><span class="chk sm" class:pa={liveTest}>{liveTest ? '✓' : ''}</span>Testläge — inget publiceras</button>
          <button class="prim bred" on:click={livePublicera} disabled={!livePhoto}>{liveTest ? 'Skapa testfil' : 'Publicera story'}</button>
          <div class="hint c">Renderas server-side → IG Story → sparas i Dropbox &amp; som material</div>
        </div>
      {:else if liveFas === 'publishing'}
        <div class="slidemitt"><div class="scd pubbig">Publicerar…</div></div>
      {:else}
        <div class="slidemitt">
          <div class="klarcirkel">✓</div>
          <div class="scd pubbig">{liveResultat?.test ? 'Testfil skapad' : (liveResultat?.publicerad ? 'Ute på Instagram' : 'Renderad')}</div>
          {#if liveResultat?.fel}<div class="synkfel">{liveResultat.fel}</div>{/if}
          {#if liveResultat?.path}<div class="livepath mono">{liveResultat.path}</div>{/if}
          <div class="klarknappar"><button class="sek" on:click={liveReset}>Ny story</button><button class="prim" on:click={liveStang}>Klar</button></div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<!-- Hämta bilder — slide-over -->
{#if ingestOpen}
  <div class="slide">
    <button class="slidebak" on:click={ingestStang} aria-label="stäng"></button>
    <div class="slidepanel">
      <div class="slidehuvud">
        <div class="slidetitel"><div class="scd st">Hämta bilder</div><div class="ss">Minneskort → Lightroom → katalog</div></div>
        <button class="stang" on:click={ingestStang}>✕</button></div>
      <div class="slidekropp">
        <div class="ingsteg">
          <span class="ingnr" class:klar={ingSteg >= 1}>{ingSteg >= 1 ? '✓' : '1'}</span>
          <div class="ingi"><div class="ingt">Minneskort</div>
            <div class="hint">Bara <b>skyddade</b> (låsta på kameran) bilder tas med.</div>
            <select class="ingsel" bind:value={ingValt}>
              {#each ingKort as k}<option value={k.path}>{k.namn} — {k.path}</option>{/each}
              {#if !ingKort.length}<option value="">Inga kort hittades</option>{/if}
            </select>
            {#if ingValt}<div class="ok sm">{ingSkyddade} skyddade bilder hittades</div>{/if}
          </div>
        </div>
        <div class="ingsteg">
          <span class="ingnr" class:klar={ingSteg >= 1}>{ingSteg >= 1 ? '✓' : '2'}</span>
          <div class="ingi"><div class="ingt">Exportera skyddade &amp; öppna Lightroom</div>
            <div class="ingrad"><input class="mono" bind:value={ingProt} placeholder="Exportera till…" /><button class="sek" on:click={ingValjExport}>Välj…</button></div>
            <button class="prim sm" on:click={ingExportera} disabled={!ingValt || !ingProt || ingKor}>{ingKor ? 'Exporterar…' : (ingSteg >= 1 ? '✓ Exporterat · öppnat i Lightroom' : 'Exportera skyddade + öppna i Lightroom →')}</button>
          </div>
        </div>
        <div class="ingsteg">
          <span class="ingnr" class:klar={photos.length > 0}>{photos.length ? '✓' : '3'}</span>
          <div class="ingi"><div class="ingt">Katalog med redigerade bilder</div>
            <div class="hint">Peka ut mappen där Lightroom exporterat de färdigredigerade bilderna — de blir matchens urval.</div>
            <button class="prim sm" on:click={ingValjKatalog}>Välj katalog + läs in →</button>
          </div>
        </div>
      </div>
      <div class="slidefot"><button class="prim bred" on:click={ingestStang}>Klar</button></div>
    </div>
  </div>
{/if}

<style>
  .panel { padding: 22px 30px 20px; }   /* full bredd (designen fyller hela ytan) */
  .topp { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
  .topptitel { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .toppsub { font-size: 12.5px; color: var(--t-mut); }
  h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--t-head); }   /* 6a: paneltitel 20px */
  .livenu { display: inline-flex; align-items: center; gap: 8px; background: var(--acc-soft); border: 1px solid var(--acc-border);
    color: var(--t-head); border-radius: 10px; padding: 9px 14px; font-size: 12.5px; font-weight: 600; }
  .ldot { width: 7px; height: 7px; border-radius: 50%; background: #E0607F; box-shadow: 0 0 8px #E0607F; flex: none; }

  .matchrad { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
  .mlbl { font-size: 10.5px; color: var(--t-mut); }
  .mdd { position: relative; }
  .mddbtn { display: flex; align-items: center; gap: 10px; background: var(--kort); border: 1px solid var(--div); border-radius: 9px; padding: 8px 13px; }
  .mddnamn { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .mddmeta { font-size: 11px; color: var(--t-mut); }
  .mddpil { font-size: 10px; color: var(--t-mut); }
  .mddskArm { position: fixed; inset: 0; z-index: 30; background: transparent; border: 0; }
  .mddlista { position: absolute; top: calc(100% + 6px); left: 0; z-index: 31; width: 380px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 12px; box-shadow: var(--skugga); padding: 6px; max-height: 360px; overflow-y: auto; }
  .mddcaps { font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); padding: 8px 11px 6px; }
  .mddrad { display: flex; align-items: center; gap: 11px; width: 100%; text-align: left; padding: 9px 11px; border: 0; background: transparent; border-radius: 8px; }
  .mddrad:hover, .mddrad.pa { background: var(--acc-soft); }
  .mddi { flex: 1; min-width: 0; }
  .mddf { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .mdds { font-size: 10.5px; color: var(--t-mut); }
  .mddres { font-size: 15px; font-weight: 700; color: var(--t-head); font-family: var(--font-c); }
  .mddkom { font-size: 10px; color: var(--t-mut); border: 1px solid var(--div); border-radius: 999px; padding: 2px 8px; }
  .grendot { width: 9px; height: 9px; border-radius: 2px; flex: none; }
  .mhint { font-size: 10.5px; color: var(--t-help); }

  .remstext { font-size: 11px; color: var(--t-mut); margin: -8px 0 22px 2px; }
  .matx { border: 0; background: transparent; color: var(--t-help); font-size: 15px;
    padding: 2px 7px; border-radius: 6px; flex: none; }
  .matx:hover { color: var(--fel, #c0492f); background: var(--div3); }
  .matx.armerad { color: #fff; background: var(--fel, #c0492f); font-size: 11.5px; font-weight: 700; }
  /* Friidrotts-storyns fältrad (B-002) */
  .frirad { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 0 0 8px; }
  .frirad select, .frirad input { padding: 7px 10px; font-size: 12.5px; }
  .frirad input { max-width: 170px; }
  .frirad .friserie { max-width: 230px; }
  .minilank { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: inherit; padding: 0; cursor: pointer; }

  .steg { display: flex; align-items: center; gap: 10px; margin: 26px 0 12px; flex-wrap: wrap; }
  .stegnr { width: 24px; height: 24px; border-radius: 7px; background: var(--div3); color: var(--acc);
    display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex: none; }
  .stegnamn { font-size: 16px; font-weight: 600; color: var(--t-head); }
  .steghint { font-size: 12px; color: var(--t-mut); }

  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .grid2.s1 { margin-bottom: 8px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: 13px; box-shadow: var(--skugga); padding: 16px 18px; margin-bottom: 14px; }
  .korthuvud { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 10px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-caps); }
  .valda { font-size: 11.5px; color: var(--acc); font-weight: 600; }
  .hint2 { font-size: 11px; color: var(--t-mut); }
  .katrad { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; flex-wrap: wrap; }
  .klbl { font-size: 10.5px; color: var(--t-mut); }
  .katrad input { flex: 1; min-width: 180px; }
  input, select, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 11px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, select:focus, textarea:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 11.5px; }
  .sek { flex: none; background: var(--panel); border: 1px solid var(--div); border-radius: 8px; padding: 8px 13px; font-size: 11.5px; font-weight: 600; color: var(--t-head); }
  .sek:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .sek:disabled { opacity: 0.5; }
  .bildrutnat { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
  .bild { position: relative; aspect-ratio: 4/5; border-radius: 6px; border: 1px solid var(--div); background-size: cover; background-position: center; opacity: 0.5; padding: 0; cursor: pointer; }
  .bild.sel { outline: 2px solid var(--acc); opacity: 1; }
  .bild.aktiv { outline: 3px solid var(--acc); box-shadow: 0 0 0 2px var(--acc-soft); }
  .bild.tom, .livebild.tom { background-image: repeating-linear-gradient(135deg, var(--div3), var(--div3) 7px, var(--kort) 7px, var(--kort) 14px); }
  .bavvalj { position: absolute; top: 3px; right: 3px; width: 16px; height: 16px; border-radius: 50%; border: 0; background: rgba(7,9,12,.7); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; cursor: pointer; }
  .bavvalj:hover { background: #C0453E; }
  .omslag { position: absolute; bottom: 3px; left: 3px; font-size: 7px; font-weight: 700; background: var(--acc); color: #100c05; border-radius: 3px; padding: 1px 4px; letter-spacing: 0.03em; }

  /* Crop-editor (per foto) i Steg 1 */
  .cropeditor { margin-top: 14px; border: 1px solid var(--div); border-radius: 11px; background: var(--panel); padding: 12px; }
  .cehuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .cecaps { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: var(--t-caps); }
  .cenav { display: flex; align-items: center; gap: 6px; }
  .cebtn { width: 26px; height: 26px; border-radius: 7px; border: 1px solid var(--div); background: var(--kort); color: var(--t-head); font-size: 15px; font-weight: 700; }
  .cebtn:disabled { opacity: 0.4; }
  .ceomslag { border: 1px solid var(--div); background: var(--kort); border-radius: 7px; padding: 5px 11px; font-size: 11.5px; font-weight: 600; color: var(--t-mut); }
  .ceomslag.on { border-color: var(--acc-border); background: var(--acc-soft); color: var(--acc); }
  .cropbox.ro { cursor: default; }
  .ceverktyg { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
  .fmtprev { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
  .ftxt { font-size: 10.5px; color: var(--t-mut); margin-right: 2px; }
  .tombild { font-size: 12px; color: var(--t-mut); line-height: 1.5; padding: 8px 0; }
  .cap { line-height: 1.5; resize: vertical; }
  .tokrad { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 11px; align-items: center; }
  .tlbl { font-size: 10.5px; color: var(--t-mut); margin-right: 2px; }
  .tok { font-size: 10.5px; background: var(--acc-soft); border: 1px dashed var(--acc-border); color: var(--acc); border-radius: 6px; padding: 3px 8px; }
  .hint { font-size: 10.5px; color: var(--t-help); margin-top: 10px; line-height: 1.45; }

  /* ── Materiallistan ─────────────────────────────────────────────────────── */
  .matfilter { display: flex; gap: 6px; flex-wrap: wrap; }
  .matchip { border: 1px solid var(--div); background: var(--panel); color: var(--t-mut);
    border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; }
  .matchip.on { background: var(--acc); border-color: var(--acc); color: var(--kort); }
  .matlista { display: flex; flex-direction: column; gap: 9px; margin-top: 12px; }
  .matrad { background: var(--panel); border: 1px solid var(--div); border-radius: 11px; padding: 11px 13px; }
  .matrad1 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .matnamn { font-size: 13px; font-weight: 600; color: var(--t-head);
    border: 0; background: none; padding: 0; font-family: inherit; text-align: left; cursor: pointer; }
  .matnamn:hover { color: var(--acc); }
  .matnar { margin-left: auto; font-size: 10.5px; color: var(--t-help); }
  .matsub { font-size: 11.5px; color: var(--t-mut); margin-top: 2px; }
  .matstatus { font-size: 9.5px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 6px; flex: none;
    color: var(--varn); background: color-mix(in srgb, var(--varn) 13%, transparent); }
  .matstatus.pub { color: var(--ok); background: color-mix(in srgb, var(--ok) 13%, transparent); }
  .matstatus.delvis { color: var(--delvis); background: color-mix(in srgb, var(--delvis) 13%, transparent); }
  .histchip { border: 1px solid var(--div); background: transparent; color: var(--t-mut);
    border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 600; cursor: pointer; }

  .chrad { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-top: 9px; }
  .chchip { font-size: 10.5px; font-weight: 600; padding: 3px 9px; border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--delvis) 40%, var(--div));
    color: var(--delvis); background: color-mix(in srgb, var(--delvis) 8%, transparent); }
  .chchip.ok { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 40%, var(--div));
    background: color-mix(in srgb, var(--ok) 8%, transparent); }
  .chchip.kor { color: var(--t-mut); border-color: var(--div); background: var(--kort); }
  .retrybtn { margin-left: auto; border: 1px solid var(--acc-border); background: var(--acc-soft);
    color: var(--acc); border-radius: 8px; padding: 5px 11px; font-size: 11.5px; font-weight: 600; cursor: pointer; }
  .retrybtn:disabled { opacity: 0.55; cursor: default; }
  .matvarn { margin-left: auto; font-size: 10.5px; color: var(--t-help); }
  .retryklar { margin-top: 8px; font-size: 11.5px; font-weight: 600; color: var(--ok); }

  .histlista { margin-top: 9px; border-top: 1px solid var(--div3); padding-top: 8px;
    display: flex; flex-direction: column; gap: 5px; }
  .histrad { display: flex; align-items: center; gap: 9px; font-size: 10.5px; }
  .histnar { color: var(--t-help); min-width: 84px; }
  .histstatus { font-weight: 700; color: var(--delvis); }
  .histstatus.pub { color: var(--ok); }
  .histnote { color: var(--t-mut); }

  /* B2: Generera med Claude + ton */
  .genrad { display: flex; align-items: center; gap: 8px; }
  .genbtn { display: inline-flex; align-items: center; gap: 6px; background: var(--acc); color: var(--ink);
    border: 0; border-radius: 8px; padding: 7px 13px; font-size: 12px; font-weight: 700; }
  .genbtn:disabled { opacity: 0.5; }
  .genbtn .stjarna { width: 13px; height: 13px; }
  .genigen { background: var(--kort); border: 1px solid var(--div); color: var(--t-mut);
    border-radius: 8px; padding: 7px 11px; font-size: 12px; font-weight: 600; }
  .genigen:hover { border-color: var(--acc); color: var(--acc); }
  .tonchip { font-size: 11.5px; font-weight: 600; padding: 3px 11px; border-radius: 999px;
    border: 1px solid var(--div); background: transparent; color: var(--t-mut); }
  .tonchip.on { background: var(--acc); border-color: var(--acc); color: var(--ink); }
  .genfel { font-size: 11.5px; color: var(--rose); font-weight: 600; margin-top: 9px; }

  /* Flikar (p.1) */
  .mpflikar { display: flex; gap: 6px; background: var(--panel); border: 1px solid var(--div);
    border-radius: 11px; padding: 4px; margin: 6px 0 20px; }
  .mpflik { flex: 1; padding: 9px 14px; border-radius: 8px; border: 0; font-size: 12.5px;
    font-weight: 600; background: transparent; color: var(--t-mut); cursor: pointer; }
  .mpflik.on { background: var(--acc); color: var(--ink); font-weight: 700; }
  .eventrem { color: var(--t-mut); }
  .mddkom.event { color: var(--acc); border-color: var(--acc-border); background: var(--acc-soft); }
  .mddkom.turn { color: var(--acc); border-color: var(--acc-border); background: var(--acc-soft); }
  .grendot.turn { border-radius: 999px; background: var(--acc); }

  /* p.6: Inspel till genereringen */
  .inspel { border: 1px solid var(--div); border-radius: 10px; background: var(--panel); padding: 10px 12px; margin-top: 10px; }
  .inspelcaps { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--t-caps); margin-bottom: 8px; }
  .vinkelchips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 9px; }
  .vinkelchip { font-size: 11px; font-weight: 600; padding: 3px 11px; border-radius: 999px;
    border: 1px solid var(--div); background: transparent; color: var(--t-mut); cursor: pointer; }
  .vinkelchip.on { background: var(--acc); border-color: var(--acc); color: var(--ink); }
  .inspelfalt { width: 100%; box-sizing: border-box; background: var(--kort); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 10px; font-size: 12px; color: var(--t-head); }
  .inspelhint { font-size: 10px; color: var(--t-help); margin-top: 6px; }

  /* p.3: IG-väg */
  .igvag { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
  .igval { display: flex; align-items: center; gap: 9px; background: var(--kort); border: 1px solid var(--div);
    border-radius: 8px; padding: 8px 10px; font-size: 11.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .igval.on { border-color: var(--acc-border); background: var(--acc-soft); color: var(--t-head); }
  .igdot { width: 13px; height: 13px; border-radius: 50%; border: 2px solid var(--div2, var(--t-mut)); flex: none; }
  .igdot.pa { border-color: var(--acc); background: var(--acc); box-shadow: inset 0 0 0 2.5px var(--kort); }
  .igtxt { flex: 1; text-align: left; }
  .igmax { font-size: 9.5px; color: var(--t-help); }

  /* p.4: bildantal-stepper */
  .antalrad { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
  .antallbl { font-size: 10.5px; font-weight: 600; color: var(--t-mut); }
  .stepper { display: inline-flex; align-items: center; gap: 2px; background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 2px; }
  .stepbtn { width: 26px; height: 26px; border: 0; border-radius: 6px; background: transparent;
    color: var(--t-head); font-size: 16px; font-weight: 700; cursor: pointer; }
  .stepbtn:hover:not(:disabled) { background: var(--acc-soft); color: var(--acc); }
  .stepbtn:disabled { opacity: 0.35; cursor: default; }
  .stepval { min-width: 22px; text-align: center; font-size: 15px; font-weight: 700; color: var(--t-head); }
  .antaltak { font-size: 9.5px; color: var(--t-help); }

  /* Godkänn prompten: exakt frågetexten som skickas, byggd lokalt utan nätanrop. */
  .granska { border: 1px solid var(--div3); border-radius: 10px; background: var(--panel);
    padding: 11px 12px; margin: 10px 0 4px; }
  .granskaTitel { font-size: 12px; font-weight: 700; color: var(--t-head); }
  .granskaHint { font-size: 11px; color: var(--t-help); margin-top: 3px; line-height: 1.5; }
  .granskaFraga { margin: 9px 0; padding: 9px 10px; max-height: 190px; overflow: auto;
    background: var(--kort); border: 1px solid var(--div3); border-radius: 8px;
    font-size: 11px; line-height: 1.55; white-space: pre-wrap; word-break: break-word;
    color: var(--t-mut); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .granskaKnappar { display: flex; justify-content: flex-end; gap: 8px; }

  /* Progress: det skarpa anropet tar ~2 min — utan detta känns knappen trasig. */
  .genprog { display: flex; align-items: center; gap: 8px; margin: 10px 0 4px;
    font-size: 11.5px; color: var(--t-mut); }
  .genspin { width: 12px; height: 12px; flex: none; border-radius: 50%;
    border: 2px solid var(--div3); border-top-color: var(--acc);
    animation: gensnurr 0.8s linear infinite; }
  @keyframes gensnurr { to { transform: rotate(360deg); } }
  .prevgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
  .prevkol { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel); padding: 10px 12px; min-width: 0; }
  .prevlbl { font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--t-caps); margin-bottom: 6px; }
  .prevtext { font-size: 12px; color: var(--t-body); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .hint.c { text-align: center; }

  .lankkort .grid2 { margin-bottom: 14px; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  label { font-size: 11px; color: var(--t-mut); }
  .lmut { color: var(--t-help); }
  .placering { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; padding-top: 13px; border-top: 1px solid var(--div3); }
  .pcaps { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-caps); }
  .pchip { font-size: 10.5px; color: var(--t-mut); background: var(--div3); border-radius: 999px; padding: 4px 10px; }

  .kanaler { display: flex; gap: 16px; flex-wrap: wrap; }
  .kanal { flex: 1 1 210px; min-width: 200px; background: var(--kort); border: 1px solid var(--div); border-radius: 13px; padding: 15px 16px; transition: opacity 0.15s; }
  .kanal.wide { flex-basis: 100%; }
  .kanal.av { opacity: 0.5; }
  .kanalhuvud { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; cursor: pointer; }
  .chk { width: 20px; height: 20px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex: none;
    font-size: 12px; font-weight: 700; border: 1.6px solid var(--div); color: transparent; }
  .chk.pa { background: var(--acc); color: #100c05; border-color: var(--acc); }
  .chk.sm { width: 17px; height: 17px; border-radius: 5px; font-size: 11px; }
  .kmeta { flex: 1; }
  .knamn { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .kunder { font-size: 10px; color: var(--t-mut); }
  .kanalkropp { display: flex; flex-direction: column; align-items: center; gap: 8px; }
  .fmtchips { display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; }
  .fmtchip { padding: 3px 8px; border-radius: 6px; border: 0; font-size: 10px; font-weight: 600; background: var(--panel); color: var(--t-mut); }
  .fmtchip.on { background: var(--acc); color: #100c05; font-weight: 700; }
  /* Crop-editor: hela omslaget + ram som visar utsnittet (mörklagt utanför) */
  .cropbox { position: relative; width: 100%; border-radius: 8px; overflow: hidden; background: var(--div3);
    cursor: crosshair; touch-action: none; user-select: none; line-height: 0; }
  .cropbox.av { pointer-events: none; }
  .cropimg { display: block; width: 100%; height: auto; -webkit-user-drag: none; user-select: none; }
  .cropram { position: absolute; border: 2px solid #fff; border-radius: 3px; pointer-events: none;
    transition: left .08s ease-out, top .08s ease-out, width .08s ease-out, height .08s ease-out; }
  .prevtom { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 96px; font-size: 10.5px; color: var(--t-mut); text-align: center; padding: 8px; }
  .fokusdot { position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 0 1.5px rgba(0,0,0,.5), 0 1px 4px rgba(0,0,0,.4); background: radial-gradient(circle, rgba(255,255,255,.9) 0 2px, transparent 3px); pointer-events: none; }
  .zoomrad { display: flex; align-items: center; gap: 8px; width: 100%; justify-content: center; }
  .zoomrad input { width: 58%; accent-color: var(--acc); }
  .zoomtxt { font-size: 10px; color: var(--t-mut); }
  .crophint { font-size: 9.5px; color: var(--t-help); text-align: center; line-height: 1.35; }

  /* På gång-sektionens stilar flyttade till PaGang.svelte (§C). */
  .ok { font-size: 11.5px; color: var(--ok); font-weight: 600; }
  .ok.sm { margin-top: 6px; }

  .pubrad { position: sticky; bottom: 0; z-index: 6; display: flex; align-items: center; gap: 14px;
    border-top: 1px solid var(--div); background: var(--panel); padding: 13px 28px; }
  .pubinfo { flex: 1; min-width: 0; }
  .pubtitel { font-size: 12.5px; color: var(--t-head); }
  .publista { font-size: 11px; color: var(--t-mut); margin-top: 1px; }
  .pubres { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; }
  .prc { font-size: 11px; font-weight: 600; }
  .prc.ok { color: var(--ok); }
  .prc.fel { color: #C0453E; }
  .prim { background: var(--acc); color: #100c05; border: 0; border-radius: 9px; padding: 10px 18px; font-size: 13px; font-weight: 700; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .prim.sm { padding: 8px 13px; font-size: 12px; }
  .prim.bred { width: 100%; }

  /* Slide-overs */
  .slide { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; }
  .slidebak { position: absolute; inset: 0; background: rgba(0,0,0,.5); border: 0; }
  .slidepanel { position: relative; width: 440px; max-width: 92vw; height: 100%; background: var(--panel); border-left: 1px solid var(--div);
    box-shadow: -24px 0 60px rgba(0,0,0,.4); display: flex; flex-direction: column; }
  .slidehuvud { flex: none; padding: 18px 22px; border-bottom: 1px solid var(--div); display: flex; align-items: center; gap: 11px; }
  .slidetitel { flex: 1; }
  .st { font-size: 18px; font-weight: 700; color: var(--t-head); }
  .ss { font-size: 11px; color: var(--t-mut); margin-top: 1px; }
  .stang { width: 30px; height: 30px; border-radius: 8px; background: var(--kort); border: 1px solid var(--div); color: var(--t-mut); font-size: 14px; flex: none; }
  .slidekropp { flex: 1; overflow-y: auto; padding: 20px 22px; }
  .slidefot { flex: none; padding: 14px 22px; border-top: 1px solid var(--div); display: flex; flex-direction: column; gap: 10px; }
  .slidemitt { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 30px; text-align: center; }
  .scaps { font-size: 10.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
  .scaps.mt { margin-top: 20px; }
  .hb { font-size: 10.5px; }
  .momrad { display: flex; gap: 7px; }
  .mom { flex: 1; text-align: center; padding: 9px 6px; border-radius: 9px; font-size: 12px; font-weight: 600; background: var(--kort); border: 1px solid var(--div); color: var(--t-mut); }
  .mom.on { background: var(--acc); color: #100c05; border-color: var(--acc); font-weight: 700; }
  .livekat { display: flex; align-items: center; gap: 7px; margin-bottom: 9px; }
  .livekat input { flex: 1; min-width: 0; }
  .sek.sm { padding: 7px 11px; font-size: 11px; }
  .livebilder { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px; }
  .livebild { position: relative; width: 58px; height: 82px; flex: none; border-radius: 7px; border: 1px solid var(--div); background-size: cover; background-position: center; opacity: 0.6; padding: 0; }
  .livebild.on { outline: 2px solid var(--acc); opacity: 1; }
  .senast { position: absolute; bottom: 3px; left: 50%; transform: translateX(-50%); font-size: 6.5px; font-weight: 700; background: rgba(0,0,0,.62); color: #fff; border-radius: 3px; padding: 1px 4px; white-space: nowrap; }
  .liveprevwrap { display: flex; justify-content: center; }
  .liveprev { width: 170px; aspect-ratio: 9/16; border-radius: 12px; border: 3px solid var(--div); overflow: hidden; background: var(--div3); }
  .liveprev img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .testtoggle { display: flex; align-items: center; gap: 9px; background: none; border: 0; font-size: 12px; color: var(--t-mut); font-weight: 600; }
  .pubbig { font-size: 20px; font-weight: 700; color: var(--t-head); }
  .klarcirkel { width: 56px; height: 56px; border-radius: 50%; background: rgba(47,158,110,.15); border: 1.5px solid var(--ok); color: var(--ok); display: flex; align-items: center; justify-content: center; font-size: 25px; }
  .livepath { font-size: 10.5px; color: var(--t-mut); font-family: var(--mono, monospace); word-break: break-all; }
  .synkfel { font-size: 12px; color: #C0453E; font-weight: 600; }
  .klarknappar { display: flex; gap: 10px; }

  .ingsteg { display: flex; gap: 13px; margin-bottom: 20px; }
  .ingnr { width: 25px; height: 25px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center; font-family: var(--font-c); font-weight: 700; font-size: 13px; background: var(--div3); color: var(--t-mut); }
  .ingnr.klar { background: var(--ok); color: #fff; }
  .ingi { flex: 1; min-width: 0; }
  .ingt { font-size: 13.5px; font-weight: 600; color: var(--t-head); margin-bottom: 4px; }
  .ingsel { margin-top: 8px; }
  .ingrad { display: flex; gap: 8px; margin: 8px 0 10px; }
  .ingrad input { flex: 1; min-width: 0; }
  /* §10: publiceringskön */
  .schemafalt { display: inline-flex; align-items: center; gap: 7px; font-size: 11.5px;
    color: var(--t-mut); font-weight: 600; }
  .schemafalt input { padding: 6px 8px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 12px; font-family: inherit; }
  .schemarensa { border: none; background: none; color: var(--t-mut); font-size: 14px; cursor: pointer; padding: 0 2px; }
  .matstatus.schemalagd { color: var(--acc); background: color-mix(in srgb, var(--acc) 13%, transparent); }
  .matstatus.forsenad { color: #C0492F; background: rgba(192, 73, 47, 0.12); animation: fpuls2 1.4s ease-in-out infinite; }
  @keyframes fpuls2 { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
</style>
