<script>
  // V5-C skiva 1 (handoff §2): Event-sektionen — lista + detaljvy med På gång-
  // läge, kopplade matcher, grenar och deltagare (individregistret).
  // Event skapas/redigeras än så länge i tävlings-editorn (Lag & ligor);
  // sektionen äger KOPPLINGARNA. Mockup: DPT v5 — Event.dc.html.
  import { onMount, createEventDispatcher } from 'svelte'
  import { listaEventer, listaTavlingar, hamtaEventDetalj, sattEventPagangLage,
    kopplaMatchEvent, sparaIndivid, listaIndividKandidater, kopplaEventIndivid,
    kopplaEventIndividGren, kopplaBortEventIndivid, sattDeltagareHandle,
    sparaDisciplin, raderaDisciplin, sattDisciplinFavorit, sparaTavling, sportprofiler,
    hamtaMasterskapGrenar, hamtaGrenDetalj, hamtaMasterskapProgram,
    hamtaProgram, sparaPass, raderaPass } from '../lib/api.js'
  import LasInTavling from '../lib/LasInTavling.svelte'
  import { markeraAndring } from '../lib/livesynk.js'
  import { oppnaMal } from '../lib/oppna.js'
  import { kopieraText } from '../lib/kopiera.js'

  const dispatch = createEventDispatcher()

  let eventer = []
  let laddar = true
  let filter = 'alla'          // alla | pagaende | kommande | avslutade
  let vald = null              // event-id → detaljvy
  let detalj = null
  let detaljFel = ''           // synligt felläge — aldrig tyst evig "Laddar…"

  // Typ-etikett + kantfärg (handoff §2: mästerskap amber, cup #3E7C87,
  // turnering #6E8757, världscup #2F7CB0; övrigt neutral).
  const TYP = {
    masterskap: { namn: 'Mästerskap', farg: 'var(--acc)' },
    cup:        { namn: 'Cup',        farg: '#3E7C87' },
    turnering:  { namn: 'Turnering',  farg: '#6E8757' },
    varldscup:  { namn: 'Världscup',  farg: '#2F7CB0' },
    ovrigt:     { namn: 'Övrigt',     farg: 'var(--t-mut)' },
    liga:       { namn: 'Liga',       farg: '#C9871F' },   // D11b §1 (Option A): ligor bor nu här
  }
  const LAGEN = [
    { id: 'auto', namn: 'Auto', text: 'Före perioden ett heldagskort, under perioden dagens matcher, efteråt resultatet.' },
    { id: 'heldag', namn: 'Heldag', text: 'Visas alltid som ett heldagskort.' },
    { id: 'matcher', namn: 'Matcher', text: 'Visas alltid som matchernas egna kort.' },
  ]

  // Status härleds ur perioden mot idag (samma logik som matchens statuspill).
  function status(e) {
    const idag = new Date().toISOString().slice(0, 10)
    const fran = e.fran || '', till = e.till || e.fran || ''
    if (fran && idag < fran) return { id: 'kommande', namn: 'Kommande' }
    if (till && idag > till) return { id: 'avslutade', namn: 'Avslutad' }
    if (fran) return { id: 'pagaende', namn: 'Pågående' }
    return { id: 'kommande', namn: 'Kommande' }
  }

  function period(e) {
    if (!e.fran) return ''
    return e.till && e.till !== e.fran ? `${e.fran} – ${e.till}` : e.fran
  }
  function metarad(e) {
    const antal = []
    if (e.antal_grenar) antal.push(`${e.antal_grenar} grenar`)
    if (e.antal_matcher) antal.push(`${e.antal_matcher} matcher`)
    if (e.antal_deltagare) antal.push(`${e.antal_deltagare} deltagare`)
    return [period(e), e.ort, e.arena, antal.join(' · ')]
      .filter(Boolean).join(' · ')
  }

  $: filtrerade = eventer.filter((e) => filter === 'alla' || status(e).id === filter)
  $: antalPer = eventer.reduce((a, e) => {
    a[status(e).id] = (a[status(e).id] || 0) + 1; return a
  }, {})

  let profiler = {}
  onMount(async () => {
    profiler = await sportprofiler().catch(() => ({}))
    await ladda()
  })
  async function ladda() {
    laddar = true
    // D11b §1 (Option A): Tävlingar äger ALLA tävlingar — events (rikt detaljvy)
    // + ligor (metadata-editor). Ligor läses ur skrivytan; events kommer
    // berikade med antal grenar/matcher/deltagare.
    const [ev, tav] = await Promise.all([
      listaEventer().catch(() => []), listaTavlingar().catch(() => [])])
    eventer = [...ev, ...tav.filter((t) => t.typ === 'liga')]
    laddar = false
  }
  // Grenar & individer hör till GRENSPORTERNA (friidrott; skid-VC när den
  // kommer) — profilens grenar-flagga. Lagsport OCH matchbaserad individsport
  // (tennis: spelarna ÄR matcherna) visar bara Matcher (Stigs fynd ×2).
  $: arIndividSport = !!profiler[detalj?.event?.sport]?.grenar

  async function oppna(id) {
    vald = id
    detalj = null; detaljFel = ''
    try {
      // Timeout-vakt: en hängd brygga får aldrig fastna som evig "Laddar…".
      detalj = await Promise.race([
        hamtaEventDetalj(id),
        new Promise((_, rej) => setTimeout(() => rej(new Error('tidsgräns (8s)')), 8000))])
      if (!detalj) detaljFel = 'Tävlingen kunde inte laddas.'
    } catch (e) {
      detaljFel = 'Kunde inte ladda tävlingen: ' + (e?.message || 'okänt fel') +
        '. Starta om appen om det står kvar.'
    }
    dagIx = 0
    // M-3: arbetsytan börjar om per tävling (läge, gruppering, sök, val).
    laget = 'grenar'; gruppera = 'klass'; grenSok = ''; baraFavoriter = false
    valdGren = null; grenDetalj = null; allaDeltagare = false
    mastDag = 1; tidsaxel = null
    if (detalj) await laddaProgram()
  }
  async function tillbaka() {
    vald = null; detalj = null; mast = null
    valdGren = null; grenDetalj = null
    await ladda()
  }
  // D11b §4: ⌘K-djuplänk. Event → detaljvyn; liga (saknar detalj) → editorn.
  $: if ($oppnaMal && $oppnaMal.mal === 'eventsektion' && $oppnaMal.id) {
    djupoppna($oppnaMal.id)
    oppnaMal.set(null)
  }
  async function djupoppna(id) {
    if (!eventer.length) await ladda()
    await oppna(id)
    if (!detalj) {
      const rad = eventer.find((e) => e.id === id)
      if (rad) { vald = null; redigeraRad(rad) } else vald = null
    }
  }

  async function sattLage(lage) {
    if (!detalj) return
    const r = await sattEventPagangLage(vald, lage)
    if (r?.ok) detalj = { ...detalj, event: { ...detalj.event, pagang_lage: lage } }
  }

  async function koppla(matchId) {
    await kopplaMatchEvent(matchId, vald)
    detalj = await hamtaEventDetalj(vald)
  }
  async function kopplaBort(matchId) {
    await kopplaMatchEvent(matchId, null)
    detalj = await hamtaEventDetalj(vald)
  }

  // ── Grenar ────────────────────────────────────────────────────────────────
  let nyGrenOppen = false
  let nyGrenNamn = ''
  async function sparaGren() {
    const namn = nyGrenNamn.trim()
    if (!namn) return
    await sparaDisciplin({ tavling_id: vald, namn })
    nyGrenNamn = ''; nyGrenOppen = false
    detalj = await hamtaEventDetalj(vald)
  }
  async function taBortGren(id) {
    await raderaDisciplin(id)
    detalj = await hamtaEventDetalj(vald)
  }
  // M-7: stjärnmärkningen är persistent och bor på grenen (tävling + namn +
  // klass) — dam- och herr-varianten av samma gren markeras var för sig.
  // Bär M-3:s navigator och M-4:s "★ Bara favoritgrenar" när de byggs.
  let baraFavoriter = false
  async function vaxlaFavorit(g) {
    const svar = await sattDisciplinFavorit(g.id, !g.favorit)
    g.favorit = svar?.favorit ?? !g.favorit
    detalj = detalj                       // rör listan så Svelte ritar om
  }
  $: synligaGrenar = (detalj?.grenar || []).filter(
    (g) => !baraFavoriter || g.favorit)
  $: antalFavoriter = (detalj?.grenar || []).filter((g) => g.favorit).length

  // ── Mästerskaps-arbetsytan (C12/M-3) ─────────────────────────────────────
  // En tävling renderas efter SKALA, inte typ (D12 "adaptiv detaljvy"): liten
  // cup → kort-stapeln nedan (rör den inte), stort mästerskap → arbetsytan
  // med gren-navigator + gren-detalj. Tröskeln är EN konstant i backend
  // (motorer/masterskap.py:ARBETSYTA_MIN_GRENAR) — se M-5-noteringen där.
  // Grupperingar, kat-chips, dagnummer och @-status HÄRLEDS i backend; den
  // här komponenten ritar bara.
  let mast = null                 // navigator-svaret (grupper + arbetsyta-flagga)
  let laget = 'grenar'            // grenar | program
  let gruppera = 'klass'          // klass (default) | typ | dag
  let grenSok = ''
  let valdGren = null
  let grenDetalj = null
  let allaDeltagare = false

  // Filterinput skickas som ARGUMENT — `$:` spårar inte closure-variabler
  // som läses inuti en anropad funktion (lärdomen från lag-panelen).
  async function laddaNavigator(id, efter, sok, favs) {
    if (!id) { mast = null; return }
    mast = await hamtaMasterskapGrenar(id, efter, sok, favs).catch(() => null)
    if (!mast?.arbetsyta) return
    const finns = (mast.grupper || []).some(
      (g) => g.grenar.some((x) => x.id === valdGren))
    if (!finns && !valdGren) await valjGren(mast.grupper?.[0]?.grenar?.[0]?.id)
  }
  $: laddaNavigator(vald, gruppera, grenSok, baraFavoriter)

  async function valjGren(id, alla = false) {
    if (!id) { valdGren = null; grenDetalj = null; return }
    valdGren = id
    allaDeltagare = alla
    grenDetalj = await hamtaGrenDetalj(id, alla).catch(() => null)
  }
  async function vaxlaFavoritArbetsyta(id, pa) {
    await sattDisciplinFavorit(id, pa)
    await laddaNavigator(vald, gruppera, grenSok, baraFavoriter)
    await laddaTidsaxel(vald, mastDag, baraFavoriter)   // ★ styr båda lägena
    if (valdGren === id) await valjGren(id, allaDeltagare)
  }

  // ── Läge Program (C12/M-4): dagflikar + tidsaxel ─────────────────────────
  // 37 deltillfällen per dag rakt ned ger varken överblick eller väg att jobba
  // fokuserat. Dagflikarna ger överblicken, ★-filtret fokus (de 3–4 grenar
  // Stig faktiskt jobbar med) — i EN vy, samma favoritfokus som mobilen.
  //
  // ⚠️ Programmet HÄRLEDS i backend ur den ENDA härledningen (store.program:
  // grenarnas pass + tidsatta matcher som pekar hit + fria hållpunkter) och
  // lagras ALDRIG. Den här komponenten ritar bara.
  let tidsaxel = null
  let mastDag = 1
  // Filterinput som ARGUMENT — `$:` spårar inte closure-variabler som läses
  // inuti en anropad funktion (lärdomen från lag-panelen).
  async function laddaTidsaxel(id, dag, favs) {
    if (!id) { tidsaxel = null; return }
    tidsaxel = await hamtaMasterskapProgram(id, dag, favs).catch(() => null)
    if (tidsaxel && tidsaxel.dag !== dag) mastDag = tidsaxel.dag
  }
  $: laddaTidsaxel(vald, mastDag, baraFavoriter)
  // "24–26 jul" — metaradens period, kort som i mockupen.
  function periodKort(e) {
    if (!e?.fran) return ''
    const dat = (s) => new Date(s + 'T00:00:00')
    const man = (d) => d.toLocaleDateString('sv-SE', { month: 'short' }).replace('.', '')
    const f = dat(e.fran)
    if (!e.till || e.till === e.fran) return `${f.getDate()} ${man(f)}`
    const t = dat(e.till)
    return man(f) === man(t)
      ? `${f.getDate()}–${t.getDate()} ${man(t)}`
      : `${f.getDate()} ${man(f)} – ${t.getDate()} ${man(t)}`
  }
  $: mastMeta = detalj ? [periodKort(detalj.event), detalj.event.ort,
    mast?.antal_grenar ? `${mast.antal_grenar} grenar` : '',
    mast?.antal_starter ? `${mast.antal_starter} starter` : '']
    .filter(Boolean).join(' · ') : ''

  // ── Deltagare (skiva 1.5): individ ⟂ gren ────────────────────────────────
  // Väljaren söker utövar-lagen (B-001:s befintliga deltagare) ∪ individ-
  // registret; gren-chipsen på varje rad skriver SAMMA koppling som Grenar &
  // deltagare-editorn (disciplin_deltagare) — appens paket ser allt.
  let valjareOppen = false
  let individer = []
  let sok = ''
  let nyIndividNamn = ''
  async function oppnaValjare() {
    valjareOppen = !valjareOppen
    if (valjareOppen) individer = await listaIndividKandidater(vald).catch(() => [])
  }
  $: kopplade = new Set((detalj?.deltagare || []).map((d) => d.id))
  $: traffar = individer.filter((i) =>
    !kopplade.has(i.id) && (!sok || i.namn.toLowerCase().includes(sok.toLowerCase())))
  async function valjIndivid(i) {
    await kopplaEventIndivid(vald, i.id)
    detalj = await hamtaEventDetalj(vald)
  }
  async function skapaIndivid() {
    const namn = nyIndividNamn.trim()
    if (!namn) return
    const r = await sparaIndivid({ namn, sport: detalj?.event?.sport })
    if (r?.ok) {
      await kopplaEventIndivid(vald, r.id)
      nyIndividNamn = ''
      individer = await listaIndividKandidater(vald)
      detalj = await hamtaEventDetalj(vald)
    }
  }
  async function togglaGren(individId, grenId, pa) {
    await kopplaEventIndividGren(vald, individId, grenId, pa)
    detalj = await hamtaEventDetalj(vald)
  }
  async function sparaHandle(d, varde) {
    const ny = (varde || '').trim()
    if (ny === (d.handle || '')) return          // orört fält — rör inte databasen
    await sattDeltagareHandle(d.id, ny)
    detalj = await hamtaEventDetalj(vald)
    await laddaProgram()                          // handles syns i programraden
  }

  async function taBortDeltagare(id) {
    await kopplaBortEventIndivid(vald, id)
    detalj = await hamtaEventDetalj(vald)
  }
  const grenNamn = (grenId) =>
    (detalj?.grenar || []).find((g) => g.id === grenId)?.namn || grenId

  const initialer = (namn) => (namn || '').split(/\s+/).map((d) => d[0]).slice(0, 2).join('').toUpperCase()
  const matchNar = (m) => [m.datum, m.tid].filter(Boolean).join(' · ')

  // ── Program & deltillfällen (V5 §8) ──────────────────────────────────────
  // Programmet HÄRLEDS i backend ur pass + tidsatta matcher — kortet visar,
  // det äger ingenting. Vem-kolumnen och handles finns här för att dagen ska
  // gå att tagga direkt ur programmet, utan att leta i deltagarlistan.
  const GRENFARG = { dam: '#8E5A86', herr: '#3E7C87', mixed: '#6E8757' }
  let program = []
  let dagIx = 0
  let laddarProgram = false

  async function laddaProgram() {
    if (!vald) return
    laddarProgram = true
    program = await hamtaProgram(vald).catch(() => [])
    // Håll dagvalet på dagens datum när eventet pågår — annars första dagen.
    const idag = new Date().toISOString().slice(0, 10)
    const i = program.findIndex((d) => d.datum === idag)
    dagIx = i >= 0 ? i : Math.min(dagIx, Math.max(program.length - 1, 0))
    laddarProgram = false
  }
  $: dag = program[dagIx] || null

  // "NÄST" = första raden framåt i tiden. Bara på dagens datum — en framtida
  // dag har ingen "näst", den har bara en första rad.
  $: nastId = (() => {
    const nu = new Date()
    const idag = nu.toISOString().slice(0, 10)
    if (!dag || dag.datum !== idag) return null
    const kl = nu.toTimeString().slice(0, 5)
    return (dag.rader.find((r) => (r.tid || '99:99') >= kl) || {}).id || null
  })()

  const dagEtikett = (d, i) => {
    const dat = new Date(d.datum + 'T00:00:00')
    const kort = dat.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' })
    return `Dag ${i + 1} · ${kort}`
  }
  const handlar = (r) => (r.deltagare || []).map((d) => d.handle).filter(Boolean)
  function vemText(r) {
    const n = (r.deltagare || []).length
    if (!n) return r.slag === 'match' ? '' : 'inga deltagare än'
    if (n <= 3) return r.deltagare.map((d) => d.namn).join(' · ')
    return `${n} deltagare`
  }

  let kopiestatus = {}
  async function kopieraHandlar(r, ev) {
    const h = handlar(r)
    if (!h.length) return
    const utfall = await kopieraText(h.join(' '), ev.currentTarget)
    kopiestatus = { ...kopiestatus, [r.id]: utfall }
    setTimeout(() => {
      const { [r.id]: _, ...rest } = kopiestatus
      kopiestatus = rest
    }, 1600)
  }

  // ── Pass för hand ────────────────────────────────────────────────────────
  let passOppen = false
  let pas = null
  function nyttPass() {
    pas = { id: null, disciplin_id: (detalj?.grenar || [])[0]?.id || '',
      namn: '', datum: dag?.datum || detalj?.event?.fran || '', tid: '', plats: '' }
    passOppen = true
  }
  function redigeraPass(r) {
    if (r.slag !== 'pass') return
    pas = { id: r.id, disciplin_id: r.gren_id, namn: r.namn, datum: r.datum,
      tid: r.tid || '', plats: r.plats || '' }
    passOppen = true
  }
  async function sparaPasset() {
    if (!pas?.namn?.trim() || !pas?.datum || !pas?.disciplin_id) return
    await sparaPass(pas)
    passOppen = false; pas = null
    await laddaProgram()
    detalj = await hamtaEventDetalj(vald)
    markeraAndring()
  }
  // D11b §4: "Skicka till telefonen" är borta. En ändring markeras och pushas
  // automatiskt (synk-märket i titelraden visar läget). Se lib/livesynk.js.

  async function taBortPass(id) {
    await raderaPass(id)
    passOppen = false; pas = null
    await laddaProgram()
    markeraAndring()
  }

  // ── Läs in (C8–C10) ─────────────────────────────────────────────────────
  // Hela inläsningen bor i lib/LasInTavling.svelte — EN implementation som
  // både kort-stapeln och M-3:s arbetsyta öppnar.
  let inlasOppen = false
  function oppnaInlas() { inlasOppen = true }
  async function inlasKlar() {
    await laddaProgram()
    detalj = await hamtaEventDetalj(vald)
    await laddaNavigator(vald, gruppera, grenSok, baraFavoriter)
    markeraAndring()   // D11b §4: pushas automatiskt, synk-märket visar läget
  }

  // ── Event-editorn (V5-C skiva 2) ─────────────────────────────────────────
  // Skriver via tävlings-skrivytan (v32: alla fem typerna ryms) → spegeln
  // håller event-registret i synk. Samma editor för nytt + redigering.
  const SPORTER = ['fotboll', 'handboll', 'innebandy', 'volleyboll', 'beachvolley', 'tennis', 'friidrott']
  const EVENTTYPER = [['masterskap', 'Mästerskap'], ['cup', 'Cup'],
    ['turnering', 'Turnering'], ['varldscup', 'Världscup'], ['liga', 'Liga'],
    ['ovrigt', 'Övrigt']]
  let editorOppen = false
  let ev = null
  function nyttEvent() {
    ev = { id: null, namn: '', typ: 'turnering', sport: 'fotboll', gren: '',
      fran: '', till: '', ort: '', arena: '' }
    editorOppen = true
  }
  // En liga har ingen grendetalj/program — klick i listan öppnar metadata-
  // editorn direkt (Option A: ligor bor i Tävlingar men saknar event-detaljvyn).
  function redigeraRad(e) {
    ev = { id: e.id, namn: e.namn, typ: e.typ, sport: e.sport,
      gren: e.gren || '', fran: e.fran || '', till: e.till || '',
      ort: e.ort || '', arena: e.arena || '' }
    editorOppen = true
  }
  function redigeraEvent() {
    const e = detalj.event
    ev = { id: e.id, namn: e.namn, typ: e.typ, sport: e.sport,
      gren: e.gren || '', fran: e.fran || '', till: e.till || '',
      ort: e.ort || '', arena: e.arena || '' }
    editorOppen = true
  }
  async function sparaEvent() {
    if (!ev?.namn?.trim()) return
    const r = await sparaTavling({ ...ev, id: ev.id || undefined })
    editorOppen = false
    if (r?.ok) {
      await ladda()
      // Ligor saknar detaljvy (de öppnas i editorn via redigeraRad) — försök
      // aldrig öppna en liga som event-detalj, då blir det "kunde inte laddas".
      if (vald) detalj = await hamtaEventDetalj(vald)
      else if (r.id && ev.typ !== 'liga') await oppna(r.id)
    }
  }
</script>

<div class="panel" class:arbetsyta={vald && mast?.arbetsyta}>
  {#if !vald}
    <div class="topp">
      <div>
        <span class="kicker">Planera</span>
        <h1 class="scd">Tävlingar <span class="sub">Ligor, mästerskap, cuper, turneringar — allt som binder ihop matcher, grenar och utövare</span></h1>
      </div>
      <button class="prim" on:click={nyttEvent}>+ Ny tävling</button>
    </div>

    {#if editorOppen && ev}
      <div class="kort editor">
        <span class="caps">{ev.id ? 'Redigera tävling' : 'Ny tävling'}</span>
        <div class="edrad">
          <label class="edfalt vaxa">Namn<input bind:value={ev.namn} placeholder="EuroVolley 2026" /></label>
          <label class="edfalt">Typ<select bind:value={ev.typ}>{#each EVENTTYPER as [v, n]}<option value={v}>{n}</option>{/each}</select></label>
          <label class="edfalt">Sport<select bind:value={ev.sport}>{#each SPORTER as s}<option value={s}>{s}</option>{/each}</select></label>
          <label class="edfalt">Gren<select bind:value={ev.gren}><option value="">—</option><option value="dam">dam</option><option value="herr">herr</option><option value="mixed">mixed</option></select></label>
        </div>
        <div class="edrad">
          <label class="edfalt">Från<input type="date" bind:value={ev.fran} /></label>
          <label class="edfalt">Till<input type="date" bind:value={ev.till} /></label>
          <label class="edfalt vaxa">Ort<input bind:value={ev.ort} placeholder="Uppsala" /></label>
          <label class="edfalt vaxa">Arena<input bind:value={ev.arena} placeholder="Uppsala Friidrottsarena" /></label>
        </div>
        <div class="edknappar">
          <button class="prim liten" on:click={sparaEvent} disabled={!ev.namn.trim()}>Spara</button>
          <button class="avbryt" on:click={() => (editorOppen = false)}>Avbryt</button>
        </div>
      </div>
    {/if}

    <div class="chips">
      {#each [['alla', 'Alla'], ['pagaende', 'Pågående'], ['kommande', 'Kommande'], ['avslutade', 'Avslutade']] as [id, namn]}
        <button class="chip" class:pa={filter === id} on:click={() => (filter = id)}>
          {namn}{#if id !== 'alla' && antalPer[id]}<span class="antal">{antalPer[id]}</span>{/if}
        </button>
      {/each}
    </div>

    {#if laddar}
      <p class="tom">Laddar tävlingar…</p>
    {:else if !filtrerade.length}
      <p class="tom">Inga tävlingar{filter !== 'alla' ? ' i det här filtret' : ' än — skapa en med + Ny tävling'}.</p>
    {:else}
      <div class="lista">
        {#each filtrerade as e (e.id)}
          {@const t = TYP[e.typ] || TYP.ovrigt}
          {@const s = status(e)}
          <button class="rad" style="--typfarg:{t.farg}" on:click={() => e.typ === 'liga' ? redigeraRad(e) : oppna(e.id)}>
            <span class="typbadge" style="color:{t.farg};border-color:{t.farg}">{t.namn}</span>
            <span class="mitt">
              <span class="namn scd">{e.namn} <span class="sport">{e.sport}{e.gren ? ` · ${e.gren}` : ''}</span></span>
              <span class="meta">{metarad(e)}</span>
            </span>
            <span class="pill" class:amber={s.id === 'pagaende'}>{s.namn}</span>
            <span class="chev">›</span>
          </button>
        {/each}
      </div>
    {/if}
  {:else if detalj}
    {@const e = detalj.event}
    {@const t = TYP[e.typ] || TYP.ovrigt}
    {@const s = status(e)}
    {#if mast?.arbetsyta}
      <!-- ═══ M-3: mästerskaps-arbetsytan ═══════════════════════════════════
           Adaptivt: den här ytan ritas bara för STORA tävlingar. Små behåller
           kort-stapeln i {:else}-grenen nedan, orörd. -->
      <div class="atopp">
        <button class="tillbaka" on:click={tillbaka}>‹ Alla tävlingar</button>
        <div class="arubrik">
          <h1 class="scd">{e.namn}</h1>
          <!-- Eventtyp = etikett UTAN egen färg (invariant): accent-outline. -->
          <span class="atypbadge">{t.namn}</span>
          <span class="pill" class:amber={s.id === 'pagaende'}>{s.namn}</span>
          <span class="ameta">{mastMeta}</span>
          <span class="spacer"></span>
          <button class="alasin" on:click={oppnaInlas}>↓ Läs in / uppdatera</button>
        </div>
        <div class="lagen">
          <button class="lagflik" class:pa={laget === 'grenar'}
            on:click={() => (laget = 'grenar')}>Grenar &amp; deltagare</button>
          <!-- M-4 bygger läget Program (dagflikar + tidsaxel) bakom den här
               fliken; växeln finns redan så det bara är att haka på. -->
          <button class="lagflik" class:pa={laget === 'program'}
            on:click={() => (laget = 'program')}>Program</button>
        </div>
      </div>

      <LasInTavling bind:oppen={inlasOppen} eventId={vald} on:klar={inlasKlar} />

      {#if laget === 'grenar'}
        <div class="ayta">
          <!-- vänster: grenar-navigator -->
          <div class="navigator">
            <div class="navtopp">
              <input class="navsok" bind:value={grenSok} placeholder="Sök gren…" />
              <div class="navfilter">
                <span class="caps mini">Gruppera</span>
                <div class="segment">
                  {#each [['klass', 'Klass'], ['typ', 'Typ'], ['dag', 'Dag']] as [id, namn]}
                    <button class="segknapp" class:pa={gruppera === id}
                      on:click={() => (gruppera = id)}>{namn}</button>
                  {/each}
                </div>
                <span class="spacer"></span>
                <button class="favfilter" class:pa={baraFavoriter}
                  title="Bara favoritgrenar"
                  on:click={() => (baraFavoriter = !baraFavoriter)}>★ {mast.antal_favoriter}</button>
              </div>
            </div>
            <div class="navlista">
              {#each mast.grupper as grp (grp.nyckel)}
                <div class="navgrupp">
                  <div class="grupprubrik">
                    <!-- Färgmarkör bara i klass-grupperingen — paletten är
                         låst till kön, och okänd klass får ingen kant alls. -->
                    {#if grp.kant}<span class="kant" style="background:{grp.kant}"></span>{/if}
                    <span class="caps mini">{grp.etikett}</span>
                    <span class="gruppantal">{grp.antal_text}</span>
                  </div>
                  {#each grp.grenar as g (g.id)}
                    <div class="grenrad" class:vald={g.id === valdGren}
                      role="button" tabindex="0"
                      on:click={() => valjGren(g.id)}
                      on:keydown={(k) => k.key === 'Enter' && valjGren(g.id)}>
                      {#if g.farg}<span class="grenkant" style="background:{g.farg}"></span>
                      {:else}<span class="grenkant tom"></span>{/if}
                      <span class="grenmitt">
                        <span class="grennamn">{g.namn}{#if g.kat}<span class="kat">{g.kat}</span>{/if}</span>
                        <span class="grensub">{g.sub}</span>
                      </span>
                      <span class="grenantal">{g.antal_deltagare}</span>
                      <button class="stjarna" class:pa={g.favorit}
                        title={g.favorit ? 'Favoritgren' : 'Stjärnmärk grenen'}
                        on:click|stopPropagation={() => vaxlaFavoritArbetsyta(g.id, !g.favorit)}>★</button>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="tomkort">{baraFavoriter ? 'Inga stjärnmärkta grenar.' : 'Ingen gren matchar sökningen.'}</p>
              {/each}
            </div>
          </div>

          <!-- höger: gren-detalj -->
          <div class="grendetalj">
            {#if grenDetalj}
              <div class="drubrik2">
                {#if grenDetalj.farg}<span class="stapel" style="background:{grenDetalj.farg}"></span>{/if}
                <div class="dmitt">
                  <div class="dtitel">
                    <h2 class="scd">{grenDetalj.namn}</h2>
                    {#if grenDetalj.kat}<span class="kat">{grenDetalj.kat}</span>{/if}
                    <span class="klasstext">{grenDetalj.klasstext}</span>
                  </div>
                  <p class="dmeta2">{grenDetalj.antal_deltagare} deltagare · {grenDetalj.pass_text}{grenDetalj.tavling_namn ? ` · Del av ${grenDetalj.tavling_namn}` : ''}</p>
                </div>
                <button class="favknapp" class:pa={grenDetalj.favorit}
                  on:click={() => vaxlaFavoritArbetsyta(grenDetalj.id, !grenDetalj.favorit)}>
                  ★ {grenDetalj.favorit ? 'Favorit' : 'Markera'}</button>
              </div>

              <div class="kort">
                <span class="caps">Pass (tidsatta deltillfällen)</span>
                <div class="passbrickor">
                  {#each grenDetalj.pass as p (p.id)}
                    <div class="passbricka">
                      <span class="passtyp">{p.typ}</span>
                      <span class="passnar scd">{p.nar || '—'}</span>
                      <span class="passantal">{p.antal}</span>
                    </div>
                  {/each}
                  <button class="passny" on:click={nyttPass}>+ Pass</button>
                </div>
              </div>

              <div class="kort">
                <div class="krubrik">
                  <span class="caps">Deltagare i {grenDetalj.namn}</span>
                  <span class="khint">{grenDetalj.handletext}</span>
                </div>
                <!-- D12 fråga 1: kopplingen bor på GRENEN, inte på personen. -->
                <p class="khint">Importen fyllde de flesta — koppla eller rätta här. Kopplingen bor på grenen, inte på personen.</p>
                <div class="laggtill">
                  <input placeholder="Lägg till utövare — sök namn ur registret…"
                    bind:value={sok} on:focus={() => (valjareOppen || oppnaValjare())} />
                </div>
                {#if valjareOppen && traffar.length}
                  <div class="valjare">
                    {#each traffar.slice(0, 6) as i (i.id)}
                      <button class="ival" on:click={async () => {
                        await kopplaEventIndividGren(vald, i.id, valdGren, true)
                        await valjGren(valdGren, allaDeltagare)
                        await laddaNavigator(vald, gruppera, grenSok, baraFavoriter)
                      }}>
                        <span class="bricka">{initialer(i.namn)}</span>{i.namn}
                        {#if i.klubb}<span class="nar">{i.klubb}</span>{/if}
                      </button>
                    {/each}
                  </div>
                {/if}
                <div class="deltlista">
                  {#each grenDetalj.deltagare as p (p.id)}
                    <div class="deltrad">
                      {#if p.nr}<span class="deltnr">{p.nr}</span>{/if}
                      <span class="bricka">{p.initialer}</span>
                      <span class="deltmitt">
                        <span class="deltnamn">{p.namn}</span>
                        <span class="deltklubb">{p.klubb}</span>
                      </span>
                      {#if p.har_handle}<span class="harhandle">{p.handle}</span>
                      {:else}<span class="saknarhandle">saknar @</span>{/if}
                    </div>
                  {:else}
                    <p class="tomkort">Inga deltagare kopplade till grenen än.</p>
                  {/each}
                </div>
                {#if grenDetalj.mer_deltagare}
                  <button class="visaalla" on:click={() => valjGren(valdGren, true)}>Visa alla {grenDetalj.antal_deltagare} deltagare ›</button>
                {/if}
              </div>
            {:else}
              <p class="tomkort">Välj en gren till vänster.</p>
            {/if}
          </div>
        </div>
      {:else}
        <!-- ═══ M-4: läge Program — dagflikar + tidsaxel ════════════════════
             Programmet HÄRLEDS i backend (pass + tidsatta matcher + fria
             hållpunkter) och lagras aldrig; här ritas det bara. -->
        <div class="dagrad">
          <div class="segment">
            {#each (tidsaxel?.dagar || []) as d (d.nr)}
              <button class="segknapp" class:pa={mastDag === d.nr}
                title={d.datum} on:click={() => (mastDag = d.nr)}>{d.etikett}</button>
            {/each}
          </div>
          <span class="spacer"></span>
          <!-- Samma favoritfokus som mobilen: 37 rader blir de 3–4 Stig
               faktiskt jobbar med. -->
          <button class="favfilter" class:pa={baraFavoriter}
            on:click={() => (baraFavoriter = !baraFavoriter)}>★ Bara favoritgrenar ({tidsaxel?.antal_favoriter ?? 0})</button>
        </div>
        <div class="tidsaxelyta">
          <p class="ledtext">{tidsaxel?.ledtext || ''}</p>
          {#each (tidsaxel?.rader || []) as p, i (p.slag + p.id)}
            <div class="tidrad">
              <span class="tidkol scd">{p.tid || '—'}</span>
              <span class="tidspar">
                <!-- Prick i klassfärg; hållpunkt utan gren får neutral prick
                     — paletten gissas aldrig (låst invariant). -->
                <span class="prick" class:neutral={!p.farg}
                  style={p.farg ? `background:${p.farg}` : ''}></span>
                <span class="linje" class:sista={i === tidsaxel.rader.length - 1}></span>
              </span>
              <span class="tidkort">
                <span class="tidkant" style={p.farg ? `background:${p.farg}` : ''}></span>
                <span class="tidmitt">
                  <span class="tidtitel">
                    <span class="tidgren">{p.gren}</span>
                    {#if p.kat}<span class="kat">{p.kat}</span>{/if}
                    {#if p.typ}<span class="tidtyp">{p.typ}</span>{/if}
                  </span>
                  {#if p.antal || p.arena}
                    <span class="tidsub">{[p.antal, p.arena].filter(Boolean).join(' · ')}</span>
                  {/if}
                </span>
                {#if p.favorit}<span class="tidstjarna">★</span>{/if}
              </span>
            </div>
          {:else}
            <p class="tomkort">{baraFavoriter
              ? 'Ingen favoritgren har något deltillfälle den här dagen.'
              : 'Inget program den här dagen än — läs in tidsprogrammet eller lägg pass på grenarna.'}</p>
          {/each}
        </div>
      {/if}
    {:else}
    <button class="tillbaka" on:click={tillbaka}>‹ Alla tävlingar</button>
    <div class="drubrik">
      <h1 class="scd">{e.namn}</h1>
      <span class="typbadge stor" style="color:{t.farg};border-color:{t.farg}">{t.namn}</span>
      <span class="pill" class:amber={s.id === 'pagaende'}>{s.namn}</span>
      <button class="plus" on:click={redigeraEvent}>Redigera</button>
    </div>

    {#if editorOppen && ev}
      <div class="kort editor">
        <span class="caps">Redigera tävling</span>
        <div class="edrad">
          <label class="edfalt vaxa">Namn<input bind:value={ev.namn} /></label>
          <label class="edfalt">Typ<select bind:value={ev.typ}>{#each EVENTTYPER as [v, n]}<option value={v}>{n}</option>{/each}</select></label>
          <label class="edfalt">Sport<select bind:value={ev.sport}>{#each SPORTER as sp}<option value={sp}>{sp}</option>{/each}</select></label>
          <label class="edfalt">Gren<select bind:value={ev.gren}><option value="">—</option><option value="dam">dam</option><option value="herr">herr</option><option value="mixed">mixed</option></select></label>
        </div>
        <div class="edrad">
          <label class="edfalt">Från<input type="date" bind:value={ev.fran} /></label>
          <label class="edfalt">Till<input type="date" bind:value={ev.till} /></label>
          <label class="edfalt vaxa">Ort<input bind:value={ev.ort} /></label>
          <label class="edfalt vaxa">Arena<input bind:value={ev.arena} /></label>
        </div>
        <div class="edknappar">
          <button class="prim liten" on:click={sparaEvent} disabled={!ev.namn.trim()}>Spara</button>
          <button class="avbryt" on:click={() => (editorOppen = false)}>Avbryt</button>
        </div>
      </div>
    {/if}
    <p class="dmeta">{[e.sport, period(e), e.ort, e.arena].filter(Boolean).join(' · ')}</p>

    <div class="kort pagang">
      <span class="caps">På gång</span>
      <div class="seg">
        {#each LAGEN as l}
          <button class="segval" class:pa={e.pagang_lage === l.id} on:click={() => sattLage(l.id)}>{l.namn}</button>
        {/each}
      </div>
      <span class="lagetext">{(LAGEN.find((l) => l.id === e.pagang_lage) || LAGEN[0]).text}
        En match med event visas aldrig utan "Del av {e.namn}".</span>
    </div>

    <div class="kort program">
      <div class="krubrik">
        <span class="caps">Program</span>
        <span class="khint">härleds ur pass och tidsatta matcher — inget eget register</span>
        <span class="spacer"></span>
        <button class="plus" on:click={oppnaInlas}>Läs in…</button>
        {#if detalj.grenar.length}
          <button class="plus" on:click={nyttPass}>+ Pass</button>
        {/if}
      </div>

      <LasInTavling bind:oppen={inlasOppen} eventId={vald} on:klar={inlasKlar} />


      {#if passOppen}
        <div class="nyrad passrad">
          <select bind:value={pas.disciplin_id}>
            {#each detalj.grenar as g (g.id)}<option value={g.id}>{g.namn}</option>{/each}
          </select>
          <input class="smal" bind:value={pas.namn} placeholder="Försök, Final…" />
          <input class="smal" type="date" bind:value={pas.datum} />
          <input class="mini" bind:value={pas.tid} placeholder="19:10" />
          <input class="smal" bind:value={pas.plats} placeholder="Plats (valfri)" />
          <button class="prim liten" on:click={sparaPasset}
            disabled={!pas.namn.trim() || !pas.datum || !pas.disciplin_id}>Spara</button>
          {#if pas.id}<button class="bort" title="Ta bort pass" on:click={() => taBortPass(pas.id)}>✕</button>{/if}
          <button class="avbryt liten" on:click={() => (passOppen = false)}>Avbryt</button>
        </div>
      {/if}

      {#if laddarProgram}
        <p class="tomkort">Läser programmet…</p>
      {:else if !program.length}
        <p class="tomkort">Inget program än — klistra in arrangörens tidsprogram, eller lägg pass på grenarna för hand. Kopplade matcher med klockslag dyker upp här av sig själva.</p>
      {:else}
        <div class="dagar">
          {#each program as d, i}
            <button class="dagflik" class:pa={i === dagIx} on:click={() => (dagIx = i)}>{dagEtikett(d, i)}</button>
          {/each}
          <span class="spacer"></span>
          <span class="khint">{dag ? `${dag.rader.length} ${dag.rader.length === 1 ? 'deltillfälle' : 'deltillfällen'}` : ''}</span>
        </div>

        {#each (dag?.rader || []) as r (r.id)}
          <div class="prad" class:nast={r.id === nastId}
            style={r.gren_kant ? `--grenfarg:${GRENFARG[r.gren_kant]}` : ''}
            class:harkant={!!r.gren_kant}>
            <span class="ptid scd">{r.tid || '—'}</span>
            <div class="pmitt">
              <span class="pnamn">
                {#if r.gren && r.gren !== r.namn}<span class="pgren">{r.gren}</span> · {/if}{r.namn}
                {#if r.slag === 'match'}<span class="pmatch">match</span>{/if}
              </span>
              <span class="pvem">
                {vemText(r)}{#if r.plats}{vemText(r) ? ' · ' : ''}{r.plats}{/if}
                {#if r.resultat} · <b>{r.resultat}</b>{/if}
              </span>
            </div>
            {#if handlar(r).length}
              <button class="handleknapp" title={handlar(r).join(' ')}
                on:click={(ev) => kopieraHandlar(r, ev)}>
                {#if kopiestatus[r.id] === 'kopierat'}✓ Kopierat
                {:else if kopiestatus[r.id] === 'markerat'}Markerat — ⌘C
                {:else if kopiestatus[r.id] === 'fel'}Kunde inte kopiera
                {:else}@ {handlar(r).length}{/if}
              </button>
            {/if}
            {#if r.id === nastId}<span class="nastbadge caps">Näst</span>{/if}
            {#if r.slag === 'pass'}
              <button class="bort" title="Ändra passet" on:click={() => redigeraPass(r)}>✎</button>
              <button class="bort" title="Ta bort deltillfället"
                on:click={() => taBortPass(r.id)}>✕</button>
            {/if}
          </div>
        {/each}
      {/if}
    </div>

    <div class="tvakol" class:enkol={!arIndividSport}>
      <div class="kort">
        <div class="krubrik"><span class="caps">Matcher</span><span class="khint">kopplas här eller från matchen</span></div>
        {#if detalj.matcher.length}
          {#each detalj.matcher as m (m.id)}
            <div class="mrad">
              <span class="fixture">{m.lag_hemma}{m.lag_borta ? ` – ${m.lag_borta}` : ''}</span>
              <span class="nar">{matchNar(m)}</span>
              {#if m.resultat}<span class="res scd">{m.resultat}</span>{/if}
              <button class="bort" title="Koppla bort" on:click={() => kopplaBort(m.id)}>✕</button>
            </div>
          {/each}
        {:else}
          <p class="tomkort">Inga matcher — grenarna är programmet. En tävling kräver varken matcher eller grenar.</p>
        {/if}
        {#if detalj.okopplade.length}
          <div class="okrubrik caps">Okopplade matcher i {e.sport}</div>
          {#each detalj.okopplade as m (m.id)}
            <div class="mrad ok">
              <span class="fixture">{m.lag_hemma}{m.lag_borta ? ` – ${m.lag_borta}` : ''}</span>
              <span class="nar">{matchNar(m)}</span>
              <button class="kopplaknapp" on:click={() => koppla(m.id)}>Koppla ›</button>
            </div>
          {/each}
        {/if}
      </div>

      {#if arIndividSport}
      <div class="hoger">
        <div class="kort">
          <div class="krubrik"><span class="caps">Grenar</span>
            {#if antalFavoriter}
              <button class="favfilter" class:pa={baraFavoriter}
                title="Visa bara stjärnmärkta grenar"
                on:click={() => (baraFavoriter = !baraFavoriter)}>★ {antalFavoriter}</button>
            {/if}
            {#if detalj.kan_grenar}<button class="plus" on:click={() => (nyGrenOppen = !nyGrenOppen)}>+ Ny gren</button>{/if}
          </div>
          {#if nyGrenOppen}
            <div class="nyrad">
              <input placeholder="Grenens namn (Längd, 100 m …)" bind:value={nyGrenNamn}
                on:keydown={(ev) => ev.key === 'Enter' && sparaGren()} />
              <button class="prim liten" on:click={sparaGren} disabled={!nyGrenNamn.trim()}>Spara</button>
            </div>
          {/if}
          {#if detalj.grenar.length}
            {#each synligaGrenar as g (g.id)}
              <div class="mrad">
                <button class="stjarna" class:pa={g.favorit}
                  title={g.favorit ? 'Favoritgren — klicka för att ta bort' : 'Stjärnmärk grenen'}
                  on:click={() => vaxlaFavorit(g)}>★</button>
                <span class="fixture">{g.namn}</span>
                <span class="nar">{g.antal_deltagare ? `${g.antal_deltagare} deltagare` : ''}</span>
                <button class="bort" title="Ta bort gren" on:click={() => taBortGren(g.id)}>✕</button>
              </div>
            {/each}
            {#if baraFavoriter && !synligaGrenar.length}
              <p class="tomkort">Inga stjärnmärkta grenar.</p>
            {/if}
          {:else}
            <p class="tomkort">Inga grenar — behövs inte för {t.namn.toLowerCase()}.</p>
          {/if}
        </div>

        <div class="kort">
          <div class="krubrik"><span class="caps">Deltagare</span>
            <button class="plus" on:click={oppnaValjare}>+ Ur individregistret</button>
          </div>
          {#if valjareOppen}
            <div class="valjare">
              <input placeholder="Sök individ…" bind:value={sok} />
              {#each traffar.slice(0, 8) as i (i.id)}
                <button class="ival" on:click={() => valjIndivid(i)}>
                  <span class="bricka">{initialer(i.namn)}</span>{i.namn}
                  {#if i.klubb}<span class="nar">{i.klubb}</span>{/if}
                </button>
              {/each}
              <div class="nyrad">
                <input placeholder="Ny individ — namn" bind:value={nyIndividNamn}
                  on:keydown={(ev) => ev.key === 'Enter' && skapaIndivid()} />
                <button class="prim liten" on:click={skapaIndivid} disabled={!nyIndividNamn.trim()}>Skapa & koppla</button>
              </div>
            </div>
          {/if}
          {#if detalj.deltagare.length}
            {#each detalj.deltagare as d (d.id)}
              <div class="drad">
                <div class="dradtopp">
                  <span class="bricka">{initialer(d.namn)}</span>
                  <span class="fixture">{d.namn}</span>
                  <span class="nar">{d.klubb || ''}</span>
                  <!-- SoMe-kontot sätts HÄR, inte i lag-editorn: startlistor
                       bär sällan handles och de fylls på mitt i tävlingsdagen. -->
                  <input class="handlefalt" class:tom={!d.handle}
                    placeholder="@konto" value={d.handle || ''}
                    title="SoMe-konto — sparas när du lämnar fältet"
                    on:blur={(ev) => sparaHandle(d, ev.currentTarget.value)}
                    on:keydown={(ev) => ev.key === 'Enter' && ev.currentTarget.blur()} />
                  <button class="bort" title="Ta bort från tävlingen (alla grenar)" on:click={() => taBortDeltagare(d.id)}>✕</button>
                </div>
                {#if detalj.grenar.length}
                  <!-- Gren-chips: klick togglar deltagandet i grenen -->
                  <div class="grenchips">
                    {#each detalj.grenar as g (g.id)}
                      {@const pa = (d.grenar || []).includes(g.id)}
                      <button class="grenchip" class:pa
                        title={pa ? `Ta bort ur ${g.namn}` : `Lägg till i ${g.namn}`}
                        on:click={() => togglaGren(d.id, g.id, !pa)}>{g.namn}</button>
                    {/each}
                  </div>
                {:else}
                  <span class="dradhint">Lägg till grenar ovan för att koppla deltagandet per gren.</span>
                {/if}
              </div>
            {/each}
          {:else}
            <p class="tomkort">Inga individer kopplade.</p>
          {/if}
          <p class="fotnot">Gren-chipsen delar koppling med Grenar &amp; deltagare-editorn — appens tävlingspaket ser samma sak. Historiken härleds ur tävlingarna, aldrig lagrad på utövaren.</p>
        </div>
      </div>
      {/if}
    </div>
    {/if}
  {:else if detaljFel}
    <div class="tom">
      <p>⚠ {detaljFel}</p>
      <button class="sek" on:click={tillbaka} style="margin-right:8px">‹ Tillbaka</button>
      <button class="sek" on:click={() => oppna(vald)}>Försök igen</button>
    </div>
  {:else}
    <p class="tom">Laddar…</p>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 980px; }
  .kicker { font-size: 11px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--acc); font-weight: 600; }
  h1 { margin: 2px 0 4px; font-size: 25px; font-weight: 700; color: var(--t-head); }
  h1 .sub { font-size: 13.5px; font-weight: 400; color: var(--t-mut); margin-left: 10px; }
  .topp { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 9px 16px; font-size: 13px; font-weight: 600; cursor: pointer; }
  .prim.liten { padding: 7px 12px; font-size: 12.5px; }
  .prim:disabled { opacity: 0.5; }
  .tom { color: var(--t-help); font-size: 13px; margin-top: 18px; }

  .chips { display: flex; gap: 8px; margin: 16px 0 14px; }
  .chip { border: 1px solid var(--div); background: var(--kort); border-radius: 999px;
    padding: 6px 14px; font-size: 12.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .chip.pa { border-color: var(--acc); color: var(--acc); background: var(--acc-soft, color-mix(in srgb, var(--acc) 12%, transparent)); }
  .chip .antal { margin-left: 6px; font-size: 11px; opacity: 0.75; }

  .lista { display: flex; flex-direction: column; gap: 8px; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%; text-align: left;
    background: var(--kort); border: 1px solid var(--div); border-left: 3px solid var(--typfarg);
    border-radius: 12px; padding: 13px 16px; cursor: pointer; }
  .rad:hover { border-color: var(--acc); border-left-color: var(--typfarg); }
  .typbadge { flex: none; font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; border: 1px solid; border-radius: 999px; padding: 2px 9px; }
  .typbadge.stor { font-size: 11.5px; padding: 3px 11px; }
  .mitt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .namn { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .namn .sport { font-size: 12.5px; font-weight: 500; color: var(--t-mut); margin-left: 6px; }
  .meta { font-size: 12px; color: var(--t-help); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pill { flex: none; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 999px;
    color: var(--t-mut); background: color-mix(in srgb, var(--t-mut) 14%, transparent); }
  .pill.amber { color: var(--acc); background: color-mix(in srgb, var(--acc) 16%, transparent); }
  .chev { color: var(--t-mut); font-size: 16px; }

  .tillbaka { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: 13px;
    padding: 0 0 10px; cursor: pointer; }
  .drubrik { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .drubrik h1 { margin: 0; }
  .dmeta { margin: 6px 0 16px; font-size: 13.5px; color: var(--t-mut); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r, 12px);
    box-shadow: var(--skugga); padding: 16px 18px; margin-bottom: 14px; }
  .caps { font-size: 10.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--t-caps, var(--t-mut)); }
  .krubrik { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
  .khint { font-size: 11.5px; color: var(--t-help); }
  .plus { border: 0; background: none; color: var(--acc); font-weight: 600; font-size: 12.5px; cursor: pointer; }
  /* M-7: stjärnmärkning per gren + filtret. Accent, ingen ny färg. */
  .stjarna { border: 0; background: none; cursor: pointer; font-size: 13px; padding: 0 4px 0 0;
    color: var(--t-mut); opacity: 0.45; flex: none; line-height: 1; }
  .stjarna:hover { opacity: 0.9; }
  .stjarna.pa { color: var(--acc); opacity: 1; }
  .favfilter { border: 1px solid var(--linje, rgba(128,128,128,.3)); background: none; color: var(--t-mut);
    border-radius: 8px; padding: 2px 8px; font-size: 11.5px; cursor: pointer; margin-left: auto; }
  .favfilter.pa { border-color: var(--acc); color: var(--acc); }

  .pagang { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .seg { display: inline-flex; border: 1px solid var(--div); border-radius: 9px; overflow: hidden; }
  .segval { border: 0; background: var(--kort); padding: 7px 14px; font-size: 12.5px; font-weight: 600;
    color: var(--t-mut); cursor: pointer; }
  .segval.pa { background: var(--acc); color: #fff; }
  .lagetext { flex: 1; min-width: 220px; font-size: 12px; color: var(--t-help); line-height: 1.5; }

  /* ── Program & deltillfällen (V5 §8) ─────────────────────────────────── */
  .spacer { flex: 1; }
  .program .krubrik { align-items: center; }
  .dagar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
    border-bottom: 1px solid var(--div); padding-bottom: 8px; margin-bottom: 10px; }
  .dagflik { border: 0; background: none; padding: 5px 11px; border-radius: 8px;
    font-size: 12.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .dagflik.pa { background: var(--acc); color: #fff; }

  .prad { display: flex; align-items: center; gap: 12px; padding: 9px 12px;
    border: 1px solid var(--div3, var(--div)); border-radius: 9px;
    margin-bottom: 6px; background: var(--panel); }
  /* Gren-markören är en kant i låst palett — ingen textetikett, och ingen
     kant alls när grenen är okänd (invariant). */
  .prad.harkant { border-left: 3px solid var(--grenfarg); }
  .prad.nast { border-color: var(--acc); }
  .ptid { flex: none; width: 52px; font-size: 14px; font-weight: 700; color: var(--t-head); }
  .pmitt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .pnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pgren { color: var(--t-mut); font-weight: 500; }
  .pmatch { font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--t-help); margin-left: 6px; }
  .pvem { font-size: 11.5px; color: var(--t-help); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .nastbadge { flex: none; background: var(--acc); color: #fff;
    border-radius: 999px; padding: 2px 8px; font-size: 9.5px; }
  .handleknapp { flex: none; border: 1px solid var(--div); background: var(--kort);
    color: var(--t-mut); border-radius: 8px; padding: 4px 10px; font-size: 11.5px;
    font-weight: 600; cursor: pointer; white-space: nowrap; }
  .handleknapp:hover { border-color: var(--acc); color: var(--acc); }
  .prad .bort { opacity: 0; }
  .prad:hover .bort { opacity: 1; }

  /* SoMe-kontot på deltagarraden (kort-stapeln) */
  .handlefalt { flex: 0 0 132px; border: 1px solid var(--div); border-radius: 7px;
    padding: 4px 8px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 11.5px; }
  .handlefalt.tom { border-style: dashed; color: var(--t-mut); }
  .handlefalt:focus { border-color: var(--acc); border-style: solid; outline: none; }

  /* Pass-editorn (delas av kort-stapeln och arbetsytan) */
  .passrad select, .passrad input { border: 1px solid var(--div); border-radius: 7px;
    padding: 6px 9px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 12.5px; }
  .passrad .smal { flex: 0 0 132px; }
  .passrad .mini { flex: 0 0 72px; }

  .tvakol { display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px; align-items: start; }
  .tvakol.enkol { grid-template-columns: 1fr; max-width: 640px; }   /* lagsport: bara Matcher */
  @media (max-width: 900px) { .tvakol { grid-template-columns: 1fr; } }

  .mrad { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--div3, var(--div));
    border-radius: 9px; margin-bottom: 6px; background: var(--panel); }
  .mrad.ok { border-style: dashed; }
  .fixture { flex: 1; min-width: 0; font-size: 13.5px; font-weight: 600; color: var(--t-head);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nar { font-size: 11.5px; color: var(--t-mut); flex: none; }
  .res { font-size: 15px; font-weight: 700; color: var(--t-head); }
  .bort { border: 0; background: none; color: var(--t-mut); cursor: pointer; font-size: 12px; padding: 2px 5px; opacity: 0; }
  .mrad:hover .bort { opacity: 1; }
  .bort:hover { color: var(--krock, #b03838); }
  .kopplaknapp { border: 1px solid var(--acc); background: none; color: var(--acc); border-radius: 8px;
    padding: 4px 11px; font-size: 12px; font-weight: 600; cursor: pointer; }
  .kopplaknapp:hover { background: color-mix(in srgb, var(--acc) 12%, transparent); }
  .okrubrik { margin: 14px 0 8px; }
  .tomkort { font-size: 12.5px; color: var(--t-help); margin: 4px 0 2px; }
  .fotnot { font-size: 11px; color: var(--t-help); margin: 10px 0 0; }

  .nyrad { display: flex; gap: 8px; margin-bottom: 10px; }
  .nyrad input { flex: 1; min-width: 0; padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-family: inherit; }
  .nyrad input:focus { border-color: var(--acc); outline: none; }

  .valjare { border: 1px solid var(--div); border-radius: 10px; padding: 10px; margin-bottom: 10px;
    display: flex; flex-direction: column; gap: 6px; background: var(--panel); }
  .valjare > input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-family: inherit; }
  .ival { display: flex; align-items: center; gap: 9px; border: 0; background: none; text-align: left;
    padding: 6px 6px; border-radius: 7px; font-size: 13px; color: var(--t-head); cursor: pointer; }
  .ival:hover { background: var(--div3, color-mix(in srgb, var(--t-mut) 10%, transparent)); }
  .bricka { flex: none; width: 26px; height: 26px; border-radius: 50%; display: inline-flex;
    align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700;
    background: color-mix(in srgb, var(--acc) 18%, transparent); color: var(--acc); }

  /* Event-editorn (skiva 2) */
  .editor { margin: 0 0 16px; }
  .edrad { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
  .edfalt { display: flex; flex-direction: column; gap: 4px; font-size: 10.5px;
    font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--t-caps, var(--t-mut)); }
  .edfalt.vaxa { flex: 1; min-width: 160px; }
  .edfalt input, .edfalt select { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-family: inherit;
    font-weight: 400; letter-spacing: 0; text-transform: none; }
  .edfalt input:focus, .edfalt select:focus { border-color: var(--acc); outline: none; }
  .edknappar { display: flex; gap: 8px; margin-top: 12px; }
  .avbryt { border: 1px solid var(--div); background: var(--kort); border-radius: 8px;
    padding: 7px 12px; font-size: 12.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }

  /* ── Mästerskaps-arbetsytan (C12/M-3) ─────────────────────────────────
     Tvåpanelsyta: gren-navigator (322 px) → gren-detalj. Klass-paletten är
     den ENDA färgen som får bära betydelse här; kat är alltid neutral. */
  .panel.arbetsyta { max-width: none; padding: 0; display: flex;
    flex-direction: column; height: 100%; min-height: 0; }
  .atopp { flex: none; padding: 16px 22px 0; border-bottom: 1px solid var(--div2, var(--div)); }
  .atopp .tillbaka { padding-bottom: 6px; }
  .arubrik { display: flex; align-items: center; gap: 11px; flex-wrap: wrap; }
  .arubrik h1 { margin: 0; font-size: 23px; }
  /* Eventtyp = etikett utan egen färg (invariant) — accent-outline, aldrig
     en egen hex som konkurrerar med klass-paletten. */
  .atypbadge { flex: none; font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--acc); border: 1px solid var(--acc);
    border-radius: 5px; padding: 2px 7px; }
  .ameta { font-size: 11.5px; color: var(--t-mut); }
  .alasin { border: 1px solid var(--div); background: none; color: var(--t-body, var(--t-head));
    border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600;
    cursor: pointer; font-family: inherit; }
  .alasin:hover { border-color: var(--acc); color: var(--acc); }
  .lagen { display: flex; gap: 2px; margin-top: 12px; }
  .lagflik { border: 0; border-bottom: 2px solid transparent; background: none;
    padding: 7px 15px; font-family: inherit; font-size: 13px; font-weight: 600;
    color: var(--t-mut); cursor: pointer; }
  .lagflik.pa { border-bottom-color: var(--acc); color: var(--t-head); font-weight: 700; }

  .ayta { flex: 1; display: flex; min-height: 0; }
  .navigator { width: 322px; flex: none; display: flex; flex-direction: column;
    min-height: 0; border-right: 1px solid var(--div2, var(--div)); }
  .navtopp { flex: none; padding: 12px 14px 10px; border-bottom: 1px solid var(--div3, var(--div)); }
  .navsok { width: 100%; box-sizing: border-box; border: 1px solid var(--div);
    border-radius: 8px; padding: 7px 10px; background: var(--kort);
    color: var(--t-head); font-family: inherit; font-size: 12.5px; }
  .navsok:focus { border-color: var(--acc); outline: none; }
  .navfilter { display: flex; align-items: center; gap: 8px; margin-top: 9px; }
  .caps.mini { font-size: 9.5px; letter-spacing: 0.1em; }
  .segment { display: inline-flex; background: var(--panel); border: 1px solid var(--div);
    border-radius: 7px; padding: 2px; }
  .segknapp { border: 0; background: none; border-radius: 5px; padding: 3px 10px;
    font-family: inherit; font-size: 11px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .segknapp.pa { background: var(--kort); color: var(--t-head);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12); }
  .navlista { flex: 1; overflow-y: auto; padding: 6px 10px 14px; }
  .navgrupp { margin-top: 8px; }
  .grupprubrik { display: flex; align-items: center; gap: 8px; padding: 5px 6px 4px; }
  .kant { width: 4px; height: 13px; border-radius: 2px; flex: none; }
  .gruppantal { font-size: 10px; color: var(--t-help); }
  .grenrad { display: flex; align-items: center; gap: 9px; padding: 6px; border-radius: 8px;
    border: 1px solid transparent; cursor: pointer; }
  .grenrad:hover { background: color-mix(in srgb, var(--t-mut) 8%, transparent); }
  .grenrad.vald { background: color-mix(in srgb, var(--acc) 14%, transparent);
    border-color: color-mix(in srgb, var(--acc) 42%, transparent); }
  /* Klassens färgkant — aldrig en textetikett, och ingen kant vid okänd klass. */
  .grenkant { width: 4px; height: 26px; border-radius: 2px; flex: none; }
  .grenkant.tom { background: none; }
  .grenmitt { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .grennamn { font-size: 12.5px; font-weight: 600; color: var(--t-head);
    display: flex; align-items: center; gap: 6px; }
  .grensub { font-size: 10px; color: var(--t-mut); }
  .grenantal { font-size: 11px; font-weight: 700; color: var(--t-mut);
    font-variant-numeric: tabular-nums; }
  /* Kat (I-20, R, S-klass, para) = NEUTRAL grå textchip. Aldrig färg —
     paletten är låst till kön, och det är så dam/herr-varianten av samma
     grennamn slutar läsas som dubbletter. */
  .kat { font-size: 8.5px; font-weight: 700; letter-spacing: 0.04em;
    color: var(--t-mut); background: color-mix(in srgb, var(--t-mut) 15%, transparent);
    border-radius: 4px; padding: 1px 5px; }

  .grendetalj { flex: 1; min-width: 0; overflow-y: auto; padding: 18px 22px 40px; }
  .drubrik2 { display: flex; align-items: stretch; gap: 12px; }
  .stapel { width: 5px; border-radius: 3px; flex: none; }
  .dmitt { flex: 1; min-width: 0; }
  .dtitel { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
  .dtitel h2 { margin: 0; font-size: 26px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .klasstext { font-size: 11.5px; color: var(--t-mut); }
  .dmeta2 { margin: 4px 0 0; font-size: 12px; color: var(--t-mut); }
  .favknapp { flex: none; align-self: flex-start; border: 1px solid var(--div);
    background: none; color: var(--t-mut); border-radius: 8px; padding: 6px 12px;
    font-family: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
  .favknapp.pa { border-color: color-mix(in srgb, var(--acc) 42%, transparent);
    background: color-mix(in srgb, var(--acc) 14%, transparent); color: var(--acc); }
  .grendetalj .kort { margin-top: 14px; }
  .passbrickor { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 9px; }
  .passbricka { background: var(--panel); border: 1px solid var(--div);
    border-radius: 9px; padding: 8px 12px; min-width: 120px;
    display: flex; flex-direction: column; }
  .passtyp { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; color: var(--t-mut); }
  .passnar { font-size: 16px; font-weight: 700; color: var(--t-head);
    font-variant-numeric: tabular-nums; }
  .passantal { font-size: 10px; color: var(--t-help); }
  .passny { background: none; border: 1px dashed var(--div); border-radius: 9px;
    padding: 8px 14px; font-family: inherit; font-size: 12px; font-weight: 600;
    color: var(--acc); cursor: pointer; }
  .laggtill { display: flex; margin: 10px 0; }
  .laggtill input { flex: 1; border: 1px solid color-mix(in srgb, var(--acc) 42%, transparent);
    border-radius: 8px; padding: 7px 11px; background: var(--panel);
    color: var(--t-head); font-family: inherit; font-size: 12.5px; }
  .laggtill input:focus { border-color: var(--acc); outline: none; }
  .deltlista { display: flex; flex-direction: column; max-height: 250px; overflow-y: auto; }
  .deltrad { display: flex; align-items: center; gap: 10px; padding: 6px 4px;
    border-bottom: 1px solid var(--div3, var(--div)); }
  .deltnr { font-size: 11px; font-weight: 700; color: var(--t-mut); min-width: 30px;
    text-align: center; font-variant-numeric: tabular-nums; }
  .deltmitt { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .deltnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); line-height: 1.1; }
  .deltklubb { font-size: 10.5px; color: var(--t-mut); }
  .harhandle { flex: none; font-size: 11px; font-weight: 600; color: var(--acc); }
  .saknarhandle { flex: none; font-size: 9.5px; font-weight: 700; color: var(--t-help);
    border: 1px dashed var(--div); border-radius: 5px; padding: 1px 6px; }
  .visaalla { margin-top: 9px; border: 0; background: none; font-family: inherit;
    font-size: 12px; font-weight: 600; color: var(--acc); cursor: pointer; padding: 0; }
  .programtom { padding: 22px; }

  /* ── Läge Program (C12/M-4): dagflikar + tidsaxel ─────────────────────
     Tid i egen 56 px-kolumn (tabular-nums), prick i klassfärg med ringkant,
     vertikal linje mellan raderna och kort med 3 px klass-vänsterkant. */
  .dagrad { flex: none; display: flex; align-items: center; gap: 12px;
    padding: 12px 22px; border-bottom: 1px solid var(--div2, var(--div)); }
  .tidsaxelyta { flex: 1; overflow-y: auto; padding: 16px 22px 40px; }
  .ledtext { margin: 0 0 14px; font-size: 11.5px; color: var(--t-mut); }
  .tidrad { display: flex; gap: 14px; align-items: stretch; }
  .tidkol { width: 56px; flex: none; text-align: right; padding-top: 11px;
    font-size: 15px; font-weight: 700; color: var(--t-head);
    font-variant-numeric: tabular-nums; }
  .tidspar { display: flex; flex-direction: column; align-items: center;
    width: 14px; flex: none; }
  .prick { width: 11px; height: 11px; border-radius: 50%; flex: none;
    margin-top: 11px; border: 2px solid var(--panel);
    box-shadow: 0 0 0 1px var(--div); }
  /* Hållpunkt utan gren: neutral prick — klassfärgen gissas aldrig. */
  .prick.neutral { background: var(--div); }
  .linje { width: 2px; flex: 1; background: var(--div); }
  .linje.sista { background: none; }
  .tidkort { flex: 1; min-width: 0; margin-bottom: 11px; display: flex;
    align-items: stretch; gap: 10px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 10px;
    padding: 10px 13px 10px 0; overflow: hidden; }
  /* 3 px klass-vänsterkant — färg, aldrig textetikett; tom vid okänd klass. */
  .tidkant { width: 3px; flex: none; margin: -10px 0; }
  .tidmitt { flex: 1; min-width: 0; display: flex; flex-direction: column;
    justify-content: center; padding-left: 10px; }
  .tidtitel { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
  .tidgren { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .tidtyp { font-size: 11px; color: var(--t-mut); }
  .tidsub { font-size: 10.5px; color: var(--t-help); margin-top: 1px; }
  .tidstjarna { align-self: center; flex: none; font-size: 13px; color: var(--acc); }

  /* Deltagarrad m gren-chips (skiva 1.5) */
  .drad { border: 1px solid var(--div3, var(--div)); border-radius: 9px; padding: 8px 10px;
    margin-bottom: 6px; background: var(--panel); }
  .dradtopp { display: flex; align-items: center; gap: 10px; }
  .drad .bort { opacity: 0; }
  .drad:hover .bort { opacity: 1; }
  .grenchips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 2px 36px; }
  .grenchip { border: 1px solid var(--div); background: var(--kort); border-radius: 999px;
    padding: 3px 11px; font-size: 11.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .grenchip.pa { border-color: var(--acc); color: var(--acc);
    background: color-mix(in srgb, var(--acc) 14%, transparent); }
  .dradhint { display: block; margin: 6px 0 2px 36px; font-size: 11px; color: var(--t-help); }
</style>
