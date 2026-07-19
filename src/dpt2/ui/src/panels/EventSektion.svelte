<script>
  // V5-C skiva 1 (handoff §2): Event-sektionen — lista + detaljvy med På gång-
  // läge, kopplade matcher, grenar och deltagare (individregistret).
  // Event skapas/redigeras än så länge i tävlings-editorn (Lag & ligor);
  // sektionen äger KOPPLINGARNA. Mockup: DPT v5 — Event.dc.html.
  import { onMount, createEventDispatcher } from 'svelte'
  import { listaEventer, listaTavlingar, hamtaEventDetalj, sattEventPagangLage,
    kopplaMatchEvent, sparaIndivid, listaIndividKandidater, kopplaEventIndivid,
    kopplaEventIndividGren, kopplaBortEventIndivid, sattDeltagareHandle,
    sparaDisciplin, raderaDisciplin, sparaTavling, sportprofiler,
    hamtaProgram, sparaPass, raderaPass,
    tolkaProgramPdf, importeraProgram, synkaLivePaket,
    lasIn as lasInApi, forhandsgranskaImport } from '../lib/api.js'
  import { kopieraText } from '../lib/kopiera.js'

  const dispatch = createEventDispatcher()

  let eventer = []
  let laddar = true
  let filter = 'alla'          // alla | pagaende | kommande | avslutade
  let vald = null              // event-id → detaljvy
  let detalj = null

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
    detalj = await hamtaEventDetalj(id).catch(() => null)
    dagIx = 0
    await laddaProgram()
  }
  async function tillbaka() {
    vald = null; detalj = null
    await ladda()
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
  }
  // Synken körs annars bara vid appstart och På gång-publicering. Efter en
  // import behöver programmet kunna skickas direkt — annars ligger det kvar
  // lokalt tills DPT2 startas om nästa gång.
  let synkar = false
  let synkkvitto = ''
  async function synka() {
    synkar = true; synkkvitto = ''
    const r = await synkaLivePaket().catch(() => null)
    synkar = false
    synkkvitto = r?.ok
      ? `Skickat — ${r.antal} paket i molnet${r.borttagna ? `, ${r.borttagna} borttagna` : ''}.`
      : `Kunde inte skicka: ${r?.fel || 'okänt fel'}`
    setTimeout(() => (synkkvitto = ''), 6000)
  }

  async function taBortPass(id) {
    await raderaPass(id)
    passOppen = false; pas = null
    await laddaProgram()
  }

  // ── Läs in (C8–C10): en väg in ───────────────────────────────────────────
  // Parsern GISSAR dokumenttyp (C8) — Stig väljer bara om vid osäkerhet.
  // Granskningen visar som standard BARA avvikelser (C9) — 800 rena rader ska
  // inte kräva ögon. En omimport visar sin diff innan något sparas (C10).
  let inlasOppen = false
  let inlasText = ''
  let granskning = null              // { sort, sakerhet, skal, rader, deltagare, sammanfattning }
  let baraAvvik = true
  let forhands = null                // C10-diff efter "Granska ändringar"
  let inlasFel = ''
  let inlasKvitto = ''

  const SORTNAMN = { tidsprogram: 'Tidsprogram', startlista_tider: 'Startlista med tider', startlista: 'Bara deltagare' }
  const AVVIKNAMN = { tidskrock: 'Tidskrockar', dubblett: 'Dubbletter (samma gren, olika stavning)', okand_klass: 'Okänd klass', flaggad: 'Behöver din blick' }
  const AVVIKORDNING = ['tidskrock', 'dubblett', 'okand_klass', 'flaggad']
  const BYTBARA = ['tidsprogram', 'startlista_tider', 'startlista']

  function oppnaInlas() {
    inlasOppen = true; inlasText = ''; granskning = null
    forhands = null; inlasKvitto = ''; inlasFel = ''
  }
  async function lasIn(sort = 'auto') {
    if (!inlasText.trim()) return
    inlasFel = ''; forhands = null
    granskning = await lasInApi(vald, inlasText, sort).catch(() => null)
    if (granskning) baraAvvik = (granskning.sammanfattning?.avvikande || 0) > 0
  }
  // PDF: arrangörens fil läses direkt, med kolumnlayouten. Klassen (dam/herr)
  // följer med ur kolumnen och blir grenmarkörens färg.
  async function lasPdf() {
    inlasFel = ''; forhands = null
    const r = await tolkaProgramPdf(vald).catch(() => null)
    if (!r?.ok) { inlasFel = r?.fel || 'Kunde inte läsa PDF:en'; return }
    granskning = r
    baraAvvik = (granskning.sammanfattning?.avvikande || 0) > 0
  }

  // Programrad duger med gren+datum; deltagarrad med namn+gren. (Pass utan
  // fas-ord ÄR sitt eget pass — grenen ensam räcker då.)
  const radOk = (r, grund) => grund === 'deltagare' ? (r.namn && r.gren) : (r.datum && r.gren)
  $: grund = granskning?.sort === 'startlista' ? 'deltagare' : 'program'
  $: passRader = granskning && grund === 'program' ? granskning.rader : []
  $: deltRader = granskning ? (granskning.deltagare?.length ? granskning.deltagare
                  : grund === 'deltagare' ? granskning.rader : []) : []
  $: granskadePass = passRader.filter((r) => radOk(r, 'program'))
  $: granskadeDelt = deltRader.filter((r) => radOk(r, 'deltagare'))
  $: sparaAntal = granskadePass.length + granskadeDelt.length
  // Vad granskningen visar just nu: filtrerat på avvikelser, eller allt.
  const synligt = (lista) => baraAvvik ? lista.filter((r) => r.avvik) : lista

  // Ta bort en rad ur inläsningen innan den sparas. Raden ligger antingen bland
  // pass eller deltagare — filtrera båda, så identiteten avgör.
  function taBortRad(r) {
    if (!granskning) return
    forhands = null
    granskning = { ...granskning,
      rader: (granskning.rader || []).filter((x) => x !== r),
      deltagare: (granskning.deltagare || []).filter((x) => x !== r) }
  }

  // Argument till import/förhandsgranskning i rätt form per sort. startlista →
  // deltagarna ÄR raderna; startlista_tider → pass som rader, deltagare vid sidan.
  function importArgs() {
    const s = granskning.sort
    if (s === 'startlista') return [granskadeDelt, s, null]
    if (s === 'startlista_tider') return [granskadePass, s, granskadeDelt]
    return [granskadePass, s, null]
  }
  async function granskaAndringar() {
    const [rader, sort, delt] = importArgs()
    forhands = await forhandsgranskaImport(vald, rader, sort, delt).catch(() => null)
  }
  async function sparaInlas() {
    const [rader, sort, delt] = importArgs()
    if (!rader.length && !(delt && delt.length)) return
    const sam = await importeraProgram(vald, rader, sort, delt)
    inlasKvitto = sort === 'startlista'
      ? `${sam.deltagare_nya || 0} nya deltagare, ${sam.deltagare_befintliga || 0} fanns redan`
      : `${sam.pass_nya || 0} nya pass, ${sam.pass_uppdaterade || 0} uppdaterade`
        + (sort === 'startlista_tider'
           ? ` · ${sam.deltagare_nya || 0} nya deltagare` : '')
    if (sam.grenar_skapade?.length)
      inlasKvitto += ` · nya grenar: ${sam.grenar_skapade.join(', ')}`
    if (sam.hopslagna?.length)
      inlasKvitto += ` · ${sam.hopslagna.length} dubblerade grenar slogs ihop`
    if (sam.klass_satt)
      inlasKvitto += ` · klass satt på ${sam.klass_satt} deltagare`
    if (sam.oklara?.length)
      inlasKvitto += ` · ${sam.oklara.length} hoppades över, välj klass: ${sam.oklara.join(', ')}`
    granskning = null; inlasText = ''; forhands = null
    await laddaProgram()
    detalj = await hamtaEventDetalj(vald)
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
      if (vald) detalj = await hamtaEventDetalj(vald)
      else if (r.id) await oppna(r.id)
    }
  }
</script>

<div class="panel">
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
        {#if program.length}
          <!-- Synken går annars bara vid appstart och På gång-publicering: ett
               nyss inläst program hade legat kvar lokalt till nästa omstart. -->
          <button class="plus" on:click={synka} disabled={synkar}>
            {synkar ? 'Skickar…' : 'Skicka till telefonen'}</button>
        {/if}
        <button class="plus" on:click={oppnaInlas}>Läs in…</button>
        {#if detalj.grenar.length}
          <button class="plus" on:click={nyttPass}>+ Pass</button>
        {/if}
      </div>

      {#if inlasOppen}
        <div class="inlas">
          <div class="seg liten">
            <span class="caps">Läs in program eller startlista</span>
            <span class="spacer"></span>
            <button class="bort" title="Stäng" on:click={() => (inlasOppen = false)}>✕</button>
          </div>
          {#if !granskning}
            <textarea rows="7" bind:value={inlasText} placeholder={'Släpp en fil eller klistra in — tidsprogram, startlista med tider eller bara deltagare. Typen känns igen automatiskt.\n\nKvinnor 100 m\nFörsök Fredag, 18:20\nFinal Fredag, 20:25\n80\tEsther Sahlqvist\t06\tHammarby IF'}></textarea>
            <div class="inlasfot">
              <button class="avbryt liten" on:click={lasPdf}>Läs PDF…</button>
              <span class="khint">Inget sparas förrän du granskat.</span>
              <span class="spacer"></span>
              <button class="prim liten" on:click={() => lasIn('auto')} disabled={!inlasText.trim()}>Läs in ›</button>
            </div>
            {#if inlasFel}<div class="kvitto fel">{inlasFel}</div>{/if}
          {:else}
            <!-- C8: sammanfattning i klartext + typen som gissades. -->
            {@const s = granskning.sammanfattning || {}}
            <div class="granskrubrik">
              <span class="caps">{SORTNAMN[granskning.sort] || granskning.sort}</span>
              <span class="summa">{s.dagar ? `${s.dagar} dagar · ` : ''}{s.grenar || 0} grenar{s.pass ? ` · ${s.pass} pass` : ''}{s.starter ? ` · ${s.starter} starter` : ''}</span>
              {#if s.behover_blick}<span class="varn">· {s.behover_blick} behöver din blick</span>{/if}
            </div>
            {#if granskning.kalla !== 'pdf'}
              <div class="bytsort {granskning.sakerhet === 'osaker' ? 'osaker' : ''}">
                {granskning.sakerhet === 'osaker' ? 'Osäker på typen — stämmer detta? Byt:' : 'Tolkad som ovan. Byt vid behov:'}
                {#each BYTBARA as bs}
                  <button class="minichip" class:pa={granskning.sort === bs}
                    on:click={() => lasIn(bs)}>{SORTNAMN[bs]}</button>
                {/each}
              </div>
            {/if}

            <!-- C9: som standard bara avvikelserna; toggla för alla rader. -->
            <div class="avviktoggle">
              <button class="minichip" class:pa={baraAvvik} on:click={() => (baraAvvik = true)}>Bara avvikelser ({s.avvikande || 0})</button>
              <button class="minichip" class:pa={!baraAvvik} on:click={() => (baraAvvik = false)}>Alla ({s.totalt || 0})</button>
              {#if baraAvvik && s.rena}<span class="khint">· {s.rena} rena rader visas inte</span>{/if}
            </div>

            <div class="gransktabell">
              {#if baraAvvik && !(s.avvikande)}
                <p class="tomkort liten">Inga avvikelser — allt gick rent. Spara direkt.</p>
              {/if}
              {#each AVVIKORDNING as kat}
                {@const passK = (baraAvvik ? passRader.filter((r) => r.avvik === kat) : (kat === AVVIKORDNING[0] ? passRader : []))}
                {#if passK.length}
                  {#if baraAvvik}<div class="avvikrubrik caps">{AVVIKNAMN[kat]} · {passK.length}</div>{/if}
                  {#each passK as r}
                    <div class="gr" class:ofullstandig={!radOk(r, 'program')}>
                      <input class="gf smal" bind:value={r.datum} placeholder="Datum" />
                      <input class="gf mini" bind:value={r.tid} placeholder="Tid" />
                      <input class="gf" bind:value={r.gren} placeholder="Gren" />
                      <input class="gf" bind:value={r.pass} placeholder="Pass (valfritt)" />
                      <select class="gf mini" bind:value={r.klass} title="Klass — styr grenmarkörens färg">
                        <option value="">–</option><option value="dam">Dam</option>
                        <option value="herr">Herr</option><option value="mixed">Mixed</option>
                      </select>
                      <input class="gf smal" bind:value={r.plats} placeholder="Plats" />
                      {#if r.varning}<span class="varn" title={r.varning}>⚠</span>{/if}
                      <button class="bort synlig" title="Ta bort raden" on:click={() => taBortRad(r)}>✕</button>
                    </div>
                  {/each}
                {/if}
              {/each}
              {#if deltRader.length}
                {#each AVVIKORDNING as kat}
                  {@const deltK = (baraAvvik ? deltRader.filter((r) => r.avvik === kat) : (kat === AVVIKORDNING[0] ? deltRader : []))}
                  {#if deltK.length}
                    {#if baraAvvik}<div class="avvikrubrik caps">{AVVIKNAMN[kat]} · deltagare · {deltK.length}</div>{/if}
                    {#each deltK as r}
                      <div class="gr" class:ofullstandig={!radOk(r, 'deltagare')}>
                        <input class="gf" bind:value={r.gren} placeholder="Gren" />
                        <select class="gf mini" bind:value={r.klass} title="Klass — krävs när grenen finns i flera">
                          <option value="">–</option><option value="dam">Dam</option>
                          <option value="herr">Herr</option><option value="mixed">Mixed</option>
                        </select>
                        <input class="gf" bind:value={r.namn} placeholder="Namn" />
                        <input class="gf" bind:value={r.klubb} placeholder="Klubb" />
                        <input class="gf smal" bind:value={r.handle} placeholder="@handle" />
                        {#if r.varning}<span class="varn" title={r.varning}>⚠</span>{/if}
                        <button class="bort synlig" title="Ta bort raden" on:click={() => taBortRad(r)}>✕</button>
                      </div>
                    {/each}
                  {/if}
                {/each}
              {/if}
            </div>

            <!-- C10: omimport är idempotent men inte tyst — visa diffen. -->
            {#if forhands}
              <div class="diff">
                <div class="caps">Vad ändras</div>
                <div class="diffrad">{forhands.pass_nya || 0} nya pass · {forhands.pass_uppdaterade || 0} flyttade · {forhands.pass_oforandrade || 0} oförändrade{forhands.deltagare_nya != null ? ` · ${forhands.deltagare_nya} nya deltagare (${forhands.deltagare_befintliga} fanns)` : ''}</div>
                {#if forhands.grenar_nya?.length}<div class="diffrad">Nya grenar: {forhands.grenar_nya.join(', ')}</div>{/if}
                {#each (forhands.flyttningar || []) as f}<div class="diffrad flytt">{f}</div>{/each}
              </div>
            {/if}

            <div class="inlasfot">
              <button class="avbryt liten" on:click={() => { granskning = null; forhands = null }}>‹ Tillbaka</button>
              <span class="spacer"></span>
              <button class="avbryt liten" on:click={granskaAndringar} disabled={!sparaAntal}>Granska ändringar</button>
              <button class="prim liten" on:click={sparaInlas} disabled={!sparaAntal}>
                Spara {sparaAntal} rader</button>
            </div>
          {/if}
        </div>
      {/if}

      {#if inlasKvitto}<div class="kvitto">{inlasKvitto}</div>{/if}
      {#if synkkvitto}<div class="kvitto">{synkkvitto}</div>{/if}

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
            {#each detalj.grenar as g (g.id)}
              <div class="mrad">
                <span class="fixture">{g.namn}</span>
                <span class="nar">{g.antal_deltagare ? `${g.antal_deltagare} deltagare` : ''}</span>
                <button class="bort" title="Ta bort gren" on:click={() => taBortGren(g.id)}>✕</button>
              </div>
            {/each}
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

  .inlas { border: 1px solid var(--div); border-radius: 10px; padding: 12px;
    margin-bottom: 12px; background: var(--panel); }
  .seg.liten { margin-bottom: 10px; display: flex; width: 100%; border: 0; }
  .seg.liten .segval { border: 1px solid var(--div); border-radius: 8px; margin-right: 6px; }
  .inlas textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--div);
    border-radius: 8px; padding: 9px 11px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 12.5px; line-height: 1.6; resize: vertical; }
  .inlasfot { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .granskrubrik { margin-bottom: 8px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .granskrubrik .summa { font-size: 12.5px; color: var(--t-help); }
  .varn { color: var(--acc); font-weight: 700; }
  .bytsort { font-size: 11.5px; color: var(--t-help); margin-bottom: 8px;
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .bytsort.osaker { color: var(--acc); font-weight: 600; }
  .minichip { border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-head); padding: 3px 11px; font-size: 11.5px; font-family: inherit;
    font-weight: 600; cursor: pointer; }
  .minichip.pa { background: var(--acc); color: #fff; border-color: var(--acc); }
  .avviktoggle { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
  .avvikrubrik { margin: 8px 0 2px; font-size: 11px; color: var(--acc); }
  .tomkort.liten { padding: 8px 0; font-size: 12.5px; }
  .diff { margin-top: 10px; border: 1px solid var(--div); border-radius: 8px;
    padding: 9px 11px; background: var(--panel); }
  .diff .caps { display: block; margin-bottom: 4px; }
  .diffrad { font-size: 12px; color: var(--t-help); line-height: 1.6; }
  .diffrad.flytt { color: var(--acc); }
  .gransktabell { max-height: 260px; overflow-y: auto; display: flex;
    flex-direction: column; gap: 4px; }
  .gr { display: flex; align-items: center; gap: 5px; }
  .gr.ofullstandig { opacity: 0.55; }
  .gf { flex: 1; min-width: 0; border: 1px solid var(--div); border-radius: 7px;
    padding: 5px 8px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 12px; }
  .gf.smal { flex: 0 0 108px; }
  .gf.mini { flex: 0 0 62px; }
  .kvitto { font-size: 12px; color: var(--t-help); background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 7px 11px; margin-bottom: 10px; }
  .kvitto.fel { color: var(--krock, #b03838); border-color: var(--krock, #b03838); margin-top: 10px; }
  .gransktabell select.gf { padding: 5px 4px; }
  .bort.synlig { opacity: 0.65; }
  .bort.synlig:hover { opacity: 1; }
  .handlefalt { flex: 0 0 132px; border: 1px solid var(--div); border-radius: 7px;
    padding: 4px 8px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 11.5px; }
  .handlefalt.tom { border-style: dashed; color: var(--t-mut); }
  .handlefalt:focus { border-color: var(--acc); border-style: solid; outline: none; }
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
