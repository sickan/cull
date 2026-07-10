<script>
  import { onMount, onDestroy, tick, createEventDispatcher } from 'svelte'
  import { listaFotojobb, sparaFotojobb, raderaFotojobb, kalenderStatus, aktiveraSynkFotojobb, listaMatcher, listaLag,
    privatKalendrar, privatHandelser } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { grenFarg } from '../lib/gren.js'
  import Hornmarkor from '../lib/Hornmarkor.svelte'
  import KrockPop from '../lib/KrockPop.svelte'
  import FotojobbVecka from '../lib/FotojobbVecka.svelte'
  import FotojobbManad from '../lib/FotojobbManad.svelte'
  import { synkFarg, jobbSynkStatus } from '../lib/synk.js'
  import { radTillToppen } from '../lib/scroll.js'
  import { krockKarta, synligaPrivata } from '../lib/privat.js'

  const dispatch = createEventDispatcher()

  let jobb = []
  let matcher = []
  let lagAlla = []
  let status = null            // null = okänd (visa ej offline-banner förrän känd)
  let laddar = true
  let layout = 'lista'          // lista | tidslinje | vecka | manad
  let katFilter = 'Alla'

  // ── Privata kalendrar (skrivskyddat tillgänglighetslager) ──────────────────
  // Hämtas via bryggan → tjanster/privat_kalender.py → Google direkt (mock i
  // webbläsaren ger seed). Ingenting härifrån sparas eller skickas vidare.
  let kalendrar = []            // valda privata kalendrar (etikett + färg)
  let privata = []              // Upptaget-poster för det laddade spannet
  let aktivaKal = new Set()     // vilka källor som är TÄNDA (styr bara visning)
  let laddatSpan = null         // [fran, till] vi redan hämtat — undvik omhämtning
  let hoverJobb = null          // jobb-id vars krock-utfällning visas vid hover
  let pinnadJobb = null         // jobb-id vars utfällning är fäst med klick
  let vyAnkare = new Date()     // vilken vecka/månad Vecka- och Månadsvyn visar

  const isoDag = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

  // Navigerar användaren Vecka/Månad utanför det laddade spannet → hämta den
  // omgivande månaden. Bara i vy-lägena; listan lever på startspannet.
  $: if ((layout === 'vecka' || layout === 'manad') && vyAnkare) {
    laddaPrivata(isoDag(new Date(vyAnkare.getFullYear(), vyAnkare.getMonth() - 1, 1)),
                 isoDag(new Date(vyAnkare.getFullYear(), vyAnkare.getMonth() + 2, 1)))
  }

  // Hämta privata poster för [fran, till) och väv in dem, dedupat på id. Backend
  // spannbegränsar (README §4: hämta per synligt tidsspann, inte allt) — vi
  // vidgar bara laddatSpan när användaren navigerar utanför det redan hämtade.
  async function laddaPrivata(fran, till) {
    if (laddatSpan && fran >= laddatSpan[0] && till <= laddatSpan[1]) return
    const nyFran = laddatSpan ? (fran < laddatSpan[0] ? fran : laddatSpan[0]) : fran
    const nyTill = laddatSpan ? (till > laddatSpan[1] ? till : laddatSpan[1]) : till
    const poster = await privatHandelser(nyFran, nyTill).catch(() => [])
    const seen = new Map(poster.map((p) => [p.id, p]))
    privata = [...seen.values()]
    laddatSpan = [nyFran, nyTill]
  }

  function toggleKalender(id) {
    aktivaKal = new Set(aktivaKal.has(id) ? [...aktivaKal].filter((x) => x !== id) : [...aktivaKal, id])
  }
  // Klick på röda hörnet fäster utfällningen — och får ALDRIG öppna redigeringen.
  function krockKlick(e, id) {
    e.stopPropagation()
    pinnadJobb = pinnadJobb === id ? null : id
  }
  // Härledd variabel, inte en hjälpfunktion: Svelte spårar bara de variabler som
  // NÄMNS i malluttrycket. `visaKrock(j.id)` hade läst hoverJobb i sin closure
  // utan att kompilatorn såg beroendet — utfällningen hade aldrig ritats om.
  // Fäst post vinner över hover.
  $: krockVisas = pinnadJobb ?? hoverJobb
  let bodyEl                    // scroll-container (för "Till idag")
  let now = new Date()          // live-klocka
  let klockIv

  let modal = null              // redigeringsutkast för "＋ Nytt fotojobb" eller null
  let jobEditId = null          // id på fotojobbet vars redigeringskort är utfällt
  let redigerar = null          // redigeringsutkast för jobEditId (seedas vid öppning)
  const GREN_ETIKETT = { dam: 'Dam', herr: 'Herr', mixed: 'Mixed' }

  const MAN = ['Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni', 'Juli',
    'Augusti', 'September', 'Oktober', 'November', 'December']
  const MAN_KORT = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const VD = ['sön', 'mån', 'tis', 'ons', 'tor', 'fre', 'lör']
  const KATEGORIER = ['Sport', 'Landskap', 'Event', 'Övrigt']
  const KAT_FARG = { Sport: '#2F7CB0', Landskap: '#C9871F', Event: '#C9657F', 'Övrigt': '#6E8B5E' }
  const NULLKAT = 'rgba(35,32,26,.45)'
  const FILTER = ['Alla', ...KATEGORIER, 'Okategoriserat']

  const WDAG = ['söndag', 'måndag', 'tisdag', 'onsdag', 'torsdag', 'fredag', 'lördag']
  const pad = (n) => String(n).padStart(2, '0')
  $: liveDate = `${WDAG[now.getDay()]} ${now.getDate()} ${MAN[now.getMonth()].toLowerCase()} ${now.getFullYear()} · ${pad(now.getHours())}:${pad(now.getMinutes())}`

  onMount(async () => {
    klockIv = setInterval(() => (now = new Date()), 30000)
    try {
      // Matcher/lag laddas TILLSAMMANS med jobben (inte efter) — grenForJobb()
      // läser dem i en {@const}, och Svelte upptäcker inte det beroendet om de
      // sätts i ett separat steg efter att listan redan renderats en gång.
      const [j, m, l] = await Promise.all([
        listaFotojobb().catch(() => []),
        listaMatcher().catch(() => []),
        listaLag().catch(() => []),
      ])
      jobb = Array.isArray(j) ? j : []
      matcher = m
      lagAlla = l
    } finally {
      laddar = false        // släpp ALLTID laddningsläget, även vid fel/timeout
    }
    // Synk-status i bakgrunden — blockera inte agendan på hälsokollen (kall Worker).
    kalenderStatus().then((s) => (status = s)).catch(() => {})
    // Privata kalendrar + ett startspann runt idag. Bara de som MARKERATS som
    // privata i Inställningar hör hemma här — calendarList innehåller även brus
    // (Helgdagar, prenumerationer, jobbkalendern själv) som inte ska bli chips.
    // Alla valda tänds som default; ägaren släcker per källa i filterraden.
    privatKalendrar().then((r) => {
      const alla = r?.kalendrar || []
      const valda = r?.valda?.length ? r.valda : alla.map((k) => k.id)
      kalendrar = alla.filter((k) => valda.includes(k.id))
      aktivaKal = new Set(valda)
    }).catch(() => {})
    const idag = new Date()
    laddaPrivata(isoDag(new Date(idag.getFullYear(), idag.getMonth() - 2, 1)),
                 isoDag(new Date(idag.getFullYear(), idag.getMonth() + 4, 1)))
    await tick()
    setTimeout(scrollTillIdag, 80)
  })
  onDestroy(() => clearInterval(klockIv))

  function dateKey(iso) {
    const d = del(iso)
    return d.length === 3 ? d[0] * 10000 + d[1] * 100 + d[2] : 0
  }
  function scrollTillIdag() {
    if (!bodyEl) return
    const kort = [...bodyEl.querySelectorAll('[data-jobdate]')]
    if (!kort.length) return
    const t = new Date()
    const idag = t.getFullYear() * 10000 + (t.getMonth() + 1) * 100 + t.getDate()
    const ix = kort.findIndex((c) => +c.getAttribute('data-jobdate') <= idag)
    const malIx = ix < 0 ? kort.length - 1 : ix
    // Ankra en post OVANFÖR dagens/närmaste (listan är fallande sorterad):
    // minst en kommande post syns ovanför och de dimmade passerade under —
    // kontext åt båda håll i stället för att dagens rad klistras i toppen.
    // Headern ligger utanför scroll-ytan, så ingen sticky-kompensation behövs.
    const mal = kort[Math.max(0, malIx - 1)]
    const br = bodyEl.getBoundingClientRect()
    bodyEl.scrollTop += mal.getBoundingClientRect().top - br.top - 14
  }
  function scrollTopp() { if (bodyEl) bodyEl.scrollTo({ top: 0, behavior: 'smooth' }) }

  // Dagens post (intervall-medvetet: idag inom [start, end] — även heldag).
  function arIdag(j) {
    const t = new Date()
    const idag = t.getFullYear() * 10000 + (t.getMonth() + 1) * 100 + t.getDate()
    const s = dateKey(j.start_at), e = dateKey(j.end_at) || s
    return s && idag >= s && idag <= e
  }
  // Passerad post (dimmas): heldag räknas passerad först när SLUTdatumet är
  // förbi (ett flerdagarsuppdrag är inte förbi bara för att det börjat);
  // tidssatta poster räknas passerade så fort startdagen är förbi.
  function arForfluten(j) {
    const t = new Date()
    const idag = t.getFullYear() * 10000 + (t.getMonth() + 1) * 100 + t.getDate()
    const s = dateKey(j.start_at), e = dateKey(j.end_at) || s
    return j.all_day ? e < idag : s < idag
  }

  const katFarg = (c) => (c ? KAT_FARG[c] || NULLKAT : NULLKAT)
  const del = (iso) => (iso || '').split('T')[0].split('-').map(Number)
  function veckodag(iso) {
    const d = del(iso); if (d.length !== 3) return ''
    return VD[new Date(d[0], d[1] - 1, d[2]).getDay()] || ''
  }
  const klocka = (iso) => ((iso || '').split('T')[1] || '').slice(0, 5)
  function manadNyckel(iso) {
    const d = del(iso)
    return d.length >= 2 ? `${MAN[d[1] - 1]} ${d[0]}` : 'Utan datum'
  }
  function heldagText(j) {
    const a = del(j.start_at), b = del(j.end_at)
    if (a.length < 3) return ''
    const s = `${a[2]} ${MAN_KORT[a[1] - 1]}`
    if (b.length < 3 || (a[1] === b[1] && a[2] === b[2])) return s
    return a[1] === b[1] ? `${a[2]}–${b[2]} ${MAN_KORT[b[1] - 1]}` : `${s} – ${b[2]} ${MAN_KORT[b[1] - 1]}`
  }
  const synkad = (j) => !!j.google_event_id
  const synkText = (j) => (j.utkast ? 'Utkast' : synkad(j) ? 'Google ✓' : 'Väntar')

  // Utkast (tävling → Fotojobb): sparas bara lokalt tills detta anropas —
  // pushar då till Calendar Sync-tjänsten på riktigt och tar bort utkastet.
  let synkFelId = null
  let synkFelMsg = ''
  async function aktiveraSynk(j) {
    synkFelId = null
    const r = await aktiveraSynkFotojobb(j.id)
    if (r?.ok) await laddaOm()
    else { synkFelId = j.id; synkFelMsg = r?.fel || 'Kunde inte aktivera synk.' }
  }

  $: filtrerade = jobb.filter((j) =>
    katFilter === 'Alla' ? true
      : katFilter === 'Okategoriserat' ? !j.category : j.category === katFilter)

  // Bara krockar är intressanta i DPT2 — de privata posterna visas inte som egna
  // rader/band längre, de lever bara som krock-signal på själva jobbet. En källa
  // som släckts i filterraden räknas då inte heller som krock: att släcka "Anna"
  // betyder "jag bryr mig inte om krockar mot hennes kalender".
  $: aktivaPrivata = synligaPrivata(privata, aktivaKal)
  $: krockar = krockKarta(jobb, aktivaPrivata)

  // Lista + Tidslinje delar gruppering och visar bara jobb; krock-signalen bärs
  // av det röda hörnet + utfällningen på jobbet.
  $: poster = filtrerade.map((j) => ({ typ: 'jobb', id: `j${j.id}`, start: j.start_at, j }))
  $: grupper = gruppera(poster)

  function gruppera(lista) {
    // Fallande: senaste aktiviteterna överst (framtid → historik), scroll-till-idag hittar dagens.
    const sorted = [...lista].sort((a, b) => (b.start || '').localeCompare(a.start || ''))
    const m = new Map()
    for (const post of sorted) {
      const k = manadNyckel(post.start)
      if (!m.has(k)) m.set(k, [])
      m.get(k).push(post)
    }
    return [...m.entries()].map(([label, poster]) => ({ label, poster, jobb: poster.filter((x) => x.typ === 'jobb') }))
  }

  async function laddaOm() { jobb = await listaFotojobb(); if (!Array.isArray(jobb)) jobb = [] }

  function nyttJobb() {
    // notering speglas som Google-description av backend (tvåvägs) — UI:t
    // skickar bara fältet, app.py bygger beskrivningen.
    modal = { title: '', start_at: '', end_at: '', location: '', notering: '', category: '', all_day: false, match_id: '' }
  }
  // datetime-local kräver 'YYYY-MM-DDTHH:mm' — heldagsjobb lagras som rent datum
  // ('2026-10-24') och skulle annars lämna fältet tomt (placeholder).
  const tillLokal = (v) => {
    const s = (v || '').slice(0, 16)
    return !s ? '' : s.includes('T') ? s : s + 'T00:00'
  }
  // Vecka/Månad har ingen rad att fälla ut ett kort under — de redigerar i modalen.
  // Månad borrar först ner till veckan (drill-down), veckan öppnar modalen.
  function oppnaModalFor(j) {
    modal = { ...j, category: j.category || '', match_id: j.match_id || '', notering: j.notering || '',
      start_at: tillLokal(j.start_at), end_at: tillLokal(j.end_at) }
  }
  function visaVeckaFor(dag) { vyAnkare = dag; bytLayout('vecka') }

  // Lista/Tidslinje ankras vid "idag" långt ner i den fallande listan. Vecka och
  // Månad börjar överst — annars öppnas de mitt i sitt eget rutnät med rubrik och
  // veckodagsrad utanför skärmen.
  function bytLayout(ny) {
    layout = ny
    if (ny === 'vecka' || ny === 'manad') tick().then(() => bodyEl && (bodyEl.scrollTop = 0))
  }

  // Redigering flyttad in i listan (utfällt kort) — modalen är kvar bara för "＋ Nytt fotojobb".
  // Ingen Ändra-knapp: raden är klickytan. `rad` skickas med så formuläret kan
  // ankras överst i vyn istället för att fällas ut nedanför skärmkanten.
  function oppnaRedigering(j, rad = null) {
    if (jobEditId === j.id) { stangRedigering(); return }     // klick igen stänger
    redigerar = { ...j, category: j.category || '', match_id: j.match_id || '',
      notering: j.notering || '',
      start_at: tillLokal(j.start_at), end_at: tillLokal(j.end_at) }
    jobEditId = j.id
    radTillToppen(rad)
  }
  function stangRedigering() { jobEditId = null; redigerar = null }
  async function sparaRedigering() {
    const d = { ...redigerar, category: redigerar.category || null }
    d.match_id = d.category === 'Sport' ? (d.match_id || null) : null
    if (d.all_day) {          // heldag lagras som rent datum (inklusivt slut)
      d.start_at = (d.start_at || '').slice(0, 10)
      d.end_at = (d.end_at || d.start_at || '').slice(0, 10)
    }
    await sparaFotojobb(d)
    stangRedigering()
    await laddaOm()
  }
  function onKeydown(e) {
    if (e.key !== 'Escape') return
    if (pinnadJobb != null) pinnadJobb = null
    else if (jobEditId != null) stangRedigering()
    else if (modal) modal = null
  }

  // §3: passerade matchjobb visar slutresultatet i raden. Matchen är sanningen
  // (matchposten bär resultatet), jobbet bara pekar på den. Visas inte för
  // kommande matcher — där finns inget resultat att visa.
  function resultatForJobb(j) {
    if (!j.match_id || !arForfluten(j)) return ''
    return matcher.find((x) => x.id === j.match_id)?.resultat || ''
  }

  // Gren-markör (DAM/HERR/MIXED) för match-kopplade fotojobb, framför titeln.
  // Riktig matchreferens (match_id → matchens hem_gren) i första hand;
  // titel-parsning ("Match – <hemma> / <borta>" → lag i registret) som fallback.
  function grenForJobb(j) {
    if (j.match_id) {
      const m = matcher.find((x) => x.id === j.match_id)
      if (m?.hem_gren) return m.hem_gren
    }
    const mm = /^Match\s*[–-]\s*(.+?)\s*\/\s*(.+)$/.exec(j.title || '')
    if (!mm) return null
    const hemma = mm[1].trim()
    const lag = lagAlla.find((l) => l.namn === hemma)
      || lagAlla.find((l) => l.namn.startsWith(hemma) || hemma.startsWith(l.namn))
    return lag?.gren || null
  }
  async function taBort(j) {
    await raderaFotojobb(j.id)
    await laddaOm()
  }
  async function sparaModal() {
    const d = { ...modal, category: modal.category || null }
    d.match_id = d.category === 'Sport' ? (d.match_id || null) : null
    if (d.all_day) {          // heldag lagras som rent datum (inklusivt slut)
      d.start_at = (d.start_at || '').slice(0, 10)
      d.end_at = (d.end_at || d.start_at || '').slice(0, 10)
    }
    await sparaFotojobb(d)
    modal = null
    await laddaOm()
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="panel">
  <div class="topp">
    <div class="head">
      <div>
        <span class="kicker">Fotojobb</span>
        <h1 class="scd">Kommande</h1>
        <div class="livedate">{liveDate}</div>
      </div>
      <div class="hverktyg">
        <div class="seg">
          <button class:on={layout === 'lista'} on:click={() => bytLayout('lista')}>Lista</button>
          <button class:on={layout === 'tidslinje'} on:click={() => bytLayout('tidslinje')}>Tidslinje</button>
          <button class:on={layout === 'vecka'} on:click={() => bytLayout('vecka')}>Vecka</button>
          <button class:on={layout === 'manad'} on:click={() => bytLayout('manad')}>Månad</button>
        </div>
        <button class="prim" on:click={nyttJobb}>+ Nytt fotojobb</button>
      </div>
    </div>
    <div class="filterrad">
      <div class="chips">
        {#each FILTER as f}
          <button class="chip" class:on={katFilter === f}
            style={katFilter === f ? `background:${f === 'Alla' ? 'var(--acc)' : f === 'Okategoriserat' ? NULLKAT : katFarg(f)};border-color:transparent;color:#fff` : ''}
            on:click={() => (katFilter = f)}>{f}</button>
        {/each}
        <span class="kallrubrik scd">Kalendrar</span>
        <!-- Jobbkalendern är låst på: DPT äger den och skriver till den. De privata
             läses skrivskyddat och kan släckas — men krocken varnar ändå. -->
        <span class="chip kalla last" style="--kf:var(--acc)"><span class="prick"></span>Jobb</span>
        {#each kalendrar as k (k.id)}
          <button class="chip kalla" class:on={aktivaKal.has(k.id)} style="--kf:{k.farg}"
            aria-pressed={aktivaKal.has(k.id)} on:click={() => toggleKalender(k.id)}>
            <span class="prick"></span>{k.etikett}
          </button>
        {/each}
      </div>
      <!-- Scroll-hoppen hör till de scrollade vyerna; Vecka/Månad navigerar själva. -->
      {#if layout === 'lista' || layout === 'tidslinje'}
        <div class="hopp">
          <button class="tillidag" on:click={scrollTopp}>↑ Till toppen</button>
          <button class="tillidag" on:click={scrollTillIdag}>↓ Till idag</button>
        </div>
      {/if}
    </div>
  </div>

  <div class="body" bind:this={bodyEl}>
    {#if laddar}
      <p class="tom">Laddar fotojobb…</p>
    {:else}
      {#if status && status.har_nyckel === false}
        <div class="offline">
          <span>Inte ansluten till Google Calendar-tjänsten — sätt <code>CALENDAR_SYNC_API_KEY</code> och anslut i Inställningar.</span>
          <button class="prim liten" on:click={() => dispatch('navigera', 'installningar')}>Inställningar ›</button>
        </div>
      {/if}

      {#if layout === 'vecka'}
        <FotojobbVecka bind:ankare={vyAnkare} jobb={filtrerade}
          {kalendrar} {krockar} {katFarg} on:redigera={(e) => oppnaModalFor(e.detail)} />
      {:else if layout === 'manad'}
        <FotojobbManad bind:ankare={vyAnkare} jobb={filtrerade}
          {krockar} {katFarg} on:visaVecka={(e) => visaVeckaFor(e.detail)} />
      {:else if grupper.length === 0}
        <div class="empty">
          <div class="etxt">Inga fotojobb i den här vyn.</div>
          <div class="ehelp">Lägg till ett så speglas det till din kalender.</div>
        </div>
      {:else}
        {#each grupper as g}
          <div class="manad scd">{g.label}</div>
          {#if layout === 'tidslinje'}
            <div class="tidslinje">
              {#each g.jobb as post (post.id)}
                {@const j = post.j}
                {@const gren = grenForJobb(j)}
                {@const res = resultatForJobb(j)}
                {@const krock = krockar.get(j.id)}
                <div class="tlrad" data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)}>
                  <div class="tltid scd">
                    <div class="tlt">{j.all_day ? '–' : klocka(j.start_at)}</div>
                    <div class="tld">{veckodag(j.start_at)} {del(j.start_at)[2] || ''}</div>
                  </div>
                  <div class="tlspar" style="border-left-color:{katFarg(j.category)}">
                    <span class="tldot" style="background:{katFarg(j.category)}"></span>
                    <div class="kortwrap">
                    {#if krock && krockVisas === j.id}<KrockPop krockar={krock} {kalendrar} heldag={j.all_day} />{/if}
                    <div class="tlkort" role="button" tabindex="0" class:forfluten={arForfluten(j)}
                      on:click={(e) => oppnaRedigering(j, e.currentTarget)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j, e.currentTarget)}>
                      <Hornmarkor farg={synkFarg(jobbSynkStatus(j))} r={12} titel={synkText(j)} />
                      {#if krock}
                        <Hornmarkor farg="var(--krock)" r={10} horn="nere-hoger" titel="Krockar med privat kalender" />
                        <button class="krocktapp" aria-label="Visa krock" on:click={(e) => krockKlick(e, j.id)}
                          on:mouseenter={() => (hoverJobb = j.id)} on:mouseleave={() => (hoverJobb = null)}></button>
                      {/if}
                      <div class="tlinfo">
                        <div class="rtitel stor">{#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}{j.title}{#if res}<span class="resultat scd">{res}</span>{/if}</div>
                        <div class="when">{j.all_day ? 'Heldag · ' + heldagText(j) : ''}{j.location ? (j.all_day ? ' · ' : '') + j.location : ''}</div>
                        {#if j.notering}<div class="notering">{j.notering}</div>{/if}
                        {#if synkFelId === j.id}<div class="synkfel">⚠ {synkFelMsg}</div>{/if}
                      </div>
                      {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                      <button class="mini papperskorg" class:armerad={$armerad === `fj-${j.id}`} aria-label="Ta bort"
                        title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                        on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg>
                      </button>
                    </div>
                    </div>
                    {#if jobEditId === j.id && redigerar}
                      <div class="redigerakort">
                        <label class="full">Titel<input bind:value={redigerar.title} placeholder="Titel" /></label>
                        <div class="tva">
                          <label>Start<input type="datetime-local" bind:value={redigerar.start_at} /></label>
                          <label>Slut<input type="datetime-local" bind:value={redigerar.end_at} /></label>
                        </div>
                        <label class="full">Plats<input bind:value={redigerar.location} placeholder="t.ex. Rättvik" /></label>
                        <label class="full">Anteckning<textarea bind:value={redigerar.notering} rows="2" placeholder="Kund, paket, övrigt…"></textarea></label>
                        <div class="katblock">
                          <span class="lbl">Kategori</span>
                          <div class="katseg">
                            {#each KATEGORIER as k}
                              <button class:on={redigerar.category === k}
                                style={redigerar.category === k ? `background:${katFarg(k)};border-color:transparent;color:#fff` : ''}
                                on:click={() => (redigerar.category = redigerar.category === k ? '' : k)}>{k}</button>
                            {/each}
                          </div>
                        </div>
                        <div class="rkfoot">
                          <button class="prim" on:click={sparaRedigering} disabled={!redigerar.title || !redigerar.start_at}>Spara ändringar</button>
                          <button class="sek" on:click={stangRedigering}>Avbryt</button>
                        </div>
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="lista">
              {#each g.poster as post (post.id)}
                {@const j = post.j}
                {@const gren = grenForJobb(j)}
                {@const res = resultatForJobb(j)}
                {@const krock = krockar.get(j.id)}
                <div class="radwrap">
                {#if krock && krockVisas === j.id}<KrockPop krockar={krock} {kalendrar} heldag={j.all_day} />{/if}
                {#if j.all_day}
                  <div class="rad heldag" role="button" tabindex="0" class:idag={arIdag(j)} class:forfluten={arForfluten(j)} data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)} style="border-left-color:{katFarg(j.category)}"
                    on:click={(e) => oppnaRedigering(j, e.currentTarget)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j, e.currentTarget)}>
                    <Hornmarkor farg={synkFarg(jobbSynkStatus(j))} r={12} titel={synkText(j)} />
                    {#if krock}
                      <Hornmarkor farg="var(--krock)" r={12} horn="nere-hoger" titel="Krockar med privat kalender" />
                      <button class="krocktapp" aria-label="Visa krock" on:click={(e) => krockKlick(e, j.id)}
                        on:mouseenter={() => (hoverJobb = j.id)} on:mouseleave={() => (hoverJobb = null)}></button>
                    {/if}
                    <span class="hrange scd" style="color:{katFarg(j.category)}">{heldagText(j)}</span>
                    {#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}
                    <span class="rtitel">{j.title}</span>
                    {#if res}<span class="resultat scd">{res}</span>{/if}
                    <!-- heldagsraden är enradig: noteringen inline istället för egen rad -->
                    {#if j.notering}<span class="notering inline">{j.notering}</span>{/if}
                    <span class="hlbl">Heldag</span>
                    {#if arIdag(j)}<span class="idagbricka">Idag</span>{/if}
                    <span class="spacer"></span>
                    {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                    <button class="mini papperskorg" class:armerad={$armerad === `fj-${j.id}`} aria-label="Ta bort"
                      title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                      on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg>
                    </button>
                    {#if synkFelId === j.id}<div class="synkfel">⚠ {synkFelMsg}</div>{/if}
                  </div>
                {:else}
                  <div class="rad" role="button" tabindex="0" class:idag={arIdag(j)} class:forfluten={arForfluten(j)} data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)} style="border-left-color:{katFarg(j.category)}"
                    on:click={(e) => oppnaRedigering(j, e.currentTarget)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j, e.currentTarget)}>
                    <Hornmarkor farg={synkFarg(jobbSynkStatus(j))} r={12} titel={synkText(j)} />
                    {#if krock}
                      <Hornmarkor farg="var(--krock)" r={12} horn="nere-hoger" titel="Krockar med privat kalender" />
                      <button class="krocktapp" aria-label="Visa krock" on:click={(e) => krockKlick(e, j.id)}
                        on:mouseenter={() => (hoverJobb = j.id)} on:mouseleave={() => (hoverJobb = null)}></button>
                    {/if}
                    <div class="datum scd">
                      <div class="d" style="color:{katFarg(j.category)}">{del(j.start_at)[2] || '–'}</div>
                      <div class="wd">{veckodag(j.start_at)}</div>
                    </div>
                    <div class="mitt">
                      <div class="rtitel stor">{#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}{j.title}{#if res}<span class="resultat scd">{res}</span>{/if}{#if arIdag(j)}<span class="idagbricka">Idag</span>{/if}</div>
                      <div class="when">{klocka(j.start_at)}{j.end_at ? '–' + klocka(j.end_at) : ''}{j.location ? ' · ' + j.location : ''}</div>
                      {#if j.notering}<div class="notering">{j.notering}</div>{/if}
                      {#if synkFelId === j.id}<div class="synkfel">⚠ {synkFelMsg}</div>{/if}
                    </div>
                    <div class="rknapp">
                      {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                      <button class="mini papperskorg" class:armerad={$armerad === `fj-${j.id}`} aria-label="Ta bort"
                        title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                        on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg>
                      </button>
                    </div>
                  </div>
                {/if}
                {#if jobEditId === j.id && redigerar}
                  <div class="redigerakort">
                    <label class="full">Titel<input bind:value={redigerar.title} placeholder="Titel" /></label>
                    <div class="tva">
                      <label>Start<input type="datetime-local" bind:value={redigerar.start_at} /></label>
                      <label>Slut<input type="datetime-local" bind:value={redigerar.end_at} /></label>
                    </div>
                    <label class="full">Plats<input bind:value={redigerar.location} placeholder="t.ex. Rättvik" /></label>
                    <label class="full">Anteckning<textarea bind:value={redigerar.notering} rows="2" placeholder="Kund, paket, övrigt…"></textarea></label>
                    <div class="katblock">
                      <span class="lbl">Kategori</span>
                      <div class="katseg">
                        {#each KATEGORIER as k}
                          <button class:on={redigerar.category === k}
                            style={redigerar.category === k ? `background:${katFarg(k)};border-color:transparent;color:#fff` : ''}
                            on:click={() => (redigerar.category = redigerar.category === k ? '' : k)}>{k}</button>
                        {/each}
                      </div>
                    </div>
                    <label class="check" on:click={() => (redigerar.all_day = !redigerar.all_day)}>
                      <span class="box" class:pa={redigerar.all_day}>{redigerar.all_day ? '✓' : ''}</span> Heldag
                    </label>
                    <div class="rkfoot">
                      <button class="prim" on:click={sparaRedigering} disabled={!redigerar.title || !redigerar.start_at}>Spara ändringar</button>
                      <button class="sek" on:click={stangRedigering}>Avbryt</button>
                    </div>
                  </div>
                {/if}
                </div>
              {/each}
            </div>
          {/if}
        {/each}
      {/if}
    {/if}
  </div>

  <div class="foot">Fotojobb speglas tvåvägs med Google Calendar</div>
</div>

{#if modal}
  <div class="overlay" on:click|self={() => (modal = null)}>
    <div class="dialog">
      <div class="dhead">
        <span class="scd">{modal.id ? 'Ändra fotojobb' : 'Nytt fotojobb'}</span>
        <button class="stang" on:click={() => (modal = null)}>×</button>
      </div>
      <div class="dbody">
        <label class="full">Titel<input bind:value={modal.title} placeholder="t.ex. Bröllop – Anna & Erik" /></label>
        <div class="tva">
          <label>Start<input type="datetime-local" bind:value={modal.start_at} /></label>
          <label>Slut<input type="datetime-local" bind:value={modal.end_at} /></label>
        </div>
        <div class="katblock">
          <span class="lbl">Kategori</span>
          <div class="katseg">
            {#each KATEGORIER as k}
              <button class:on={modal.category === k}
                style={modal.category === k ? `background:${katFarg(k)};border-color:transparent;color:#fff` : ''}
                on:click={() => (modal.category = modal.category === k ? '' : k)}>{k}</button>
            {/each}
          </div>
        </div>
        {#if modal.category === 'Sport'}
          <label class="full">Koppla till match
            <select bind:value={modal.match_id}>
              <option value="">Ingen match</option>
              {#each matcher as m}
                <option value={m.id}>{m.lag_hemma} – {m.lag_borta}{m.datum ? ` (${m.datum})` : ''}</option>
              {/each}
            </select>
          </label>
        {/if}
        <div class="rad2">
          <label class="check" on:click={() => (modal.all_day = !modal.all_day)}>
            <span class="box" class:pa={modal.all_day}>{modal.all_day ? '✓' : ''}</span> Heldag
          </label>
          <label class="vaxa">Plats<input bind:value={modal.location} placeholder="t.ex. Rättvik" /></label>
        </div>
        <label class="full">Anteckning<textarea bind:value={modal.notering} rows="2" placeholder="Kund, paket, övrigt…"></textarea></label>
        <div class="dfoot">
          <button class="prim" on:click={sparaModal} disabled={!modal.title || !modal.start_at}>
            {modal.id ? 'Spara ändringar' : 'Lägg till fotojobb'}
          </button>
          <button class="sek" on:click={() => (modal = null)}>Avbryt</button>
          <span class="dnot">Speglas till Google Calendar</span>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .panel { display: flex; flex-direction: column; height: 100%; }
  .topp { padding: 26px 30px 14px; border-bottom: 1px solid var(--div3); }
  .head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .kicker { font-size: 11px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--acc); font-weight: 600; }
  h1 { margin: 2px 0 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .hverktyg { display: flex; align-items: center; gap: 10px; }
  .seg { display: flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; }
  .seg button { padding: 7px 14px; border: 0; border-radius: 7px; background: transparent;
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .seg button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 9px 15px;
    font-size: 13px; font-weight: 600; }
  .prim.liten { padding: 7px 13px; font-size: 12.5px; }
  .prim:disabled { opacity: 0.5; }

  .livedate { font-size: 12px; color: var(--t-mut); margin-top: 3px; font-variant-numeric: tabular-nums; }
  .filterrad { margin-top: 13px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .hopp { display: flex; gap: 7px; flex: none; }
  .tillidag { display: inline-flex; align-items: center; gap: 6px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 999px; padding: 6px 13px; font-size: 12.5px;
    font-weight: 600; color: var(--t-mut); flex: none; }
  .tillidag:hover { border-color: var(--acc); color: var(--acc); }
  .idagbricka { display: inline-block; margin-left: 8px; font-size: 10px; font-weight: 700;
    letter-spacing: 0.04em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px;
    background: var(--acc); color: #fff; vertical-align: middle; }
  /* §3: slutresultat på passerat matchjobb. Passerade rader dämpas, men siffran
     är själva poängen med raden — den behåller full brödtextkontrast. */
  .resultat { display: inline-block; margin-left: 8px; padding: 1px 7px; border-radius: 6px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.02em; vertical-align: middle;
    color: var(--t-head); background: var(--div3); border: 1px solid var(--div); }
  /* Dagens rad: en antydan räcker — Idag-brickan bär beskedet. Full accent-ram
     + gloria drog blicken från själva innehållet. */
  .rad.idag { border-color: var(--acc-border); box-shadow: var(--skugga); }
  /* A1 · passerade poster: nedtona accenten (datum/heldags-etikett) + ta bort
     skuggan — men stapla ALDRIG opacity på texten (den håller AA via tokens). */
  .rad.forfluten, .tlkort.forfluten { box-shadow: none; }
  .rad.forfluten .datum .d, .rad.forfluten .hrange { opacity: 0.62; }
  .rad.forfluten { border-left-color: var(--div) !important; }
  .chips { display: flex; gap: 7px; flex-wrap: wrap; }
  .chip { padding: 5px 13px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--kort); color: var(--t-mut); font-size: 12.5px; font-weight: 600; }

  .body { flex: 1; overflow-y: auto; padding: 16px 30px 30px; }
  .tom { color: var(--t-help); font-size: 13px; }
  .offline { display: flex; align-items: center; gap: 12px; background: var(--acc-soft);
    border: 1px solid var(--acc-border); border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;
    font-size: 13px; color: var(--t-head); }
  .offline span { flex: 1; }
  .offline code { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .empty { text-align: center; padding: 54px 0; color: var(--t-mut); }
  .etxt { font-size: 14px; } .ehelp { font-size: 12.5px; color: var(--t-help); margin-top: 3px; }

  .manad { font-weight: 700; font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--t-mut); margin: 18px 2px 12px; }
  .lista { display: flex; flex-direction: column; gap: 10px; }
  .rad { position: relative; overflow: hidden; display: flex; align-items: center; gap: 16px; background: var(--kort);
    border: 1px solid var(--div); border-left: 3px solid var(--acc); border-radius: var(--r);
    padding: 12px 16px; box-shadow: var(--skugga); cursor: pointer; }
  .rad:hover { background: var(--div3); }
  .datum { width: 44px; flex: none; text-align: center; }
  .datum .d { font-size: 24px; font-weight: 700; line-height: 1; }
  .datum .wd { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--t-mut); margin-top: 3px; }
  .mitt { flex: 1; min-width: 0; }
  .rtitel { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .rtitel.stor { font-size: 15px; }
  .when { font-size: 12.5px; color: var(--t-mut); margin-top: 2px; }
  /* §3 p.2: fotografens anteckning (kund/paket/utrustning). Egen rad under
     tid+plats, avkortad — den kan vara godtyckligt lång och får inte bryta raden. */
  .notering { font-size: 11.5px; color: var(--t-body); margin-top: 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .notering.inline { margin-top: 0; max-width: 240px; flex: none; }
  .rknapp { display: flex; gap: 6px; flex: none; }
  .mini { border: 1px solid var(--div); background: var(--kort); border-radius: 7px; padding: 6px 12px;
    font-size: 12.5px; color: var(--t-mut); }
  .mini:hover { border-color: var(--acc); color: var(--acc); }
  /* §2: papperskorgen är borttagningsknappen överallt — tvåstegs behålls:
     första klicket armar (röd), andra raderar. Titeln vägleder. */
  .mini.papperskorg { width: 30px; height: 30px; padding: 0; flex: none;
    display: inline-flex; align-items: center; justify-content: center; }
  .mini.armerad, .mini.armerad:hover { background: #C0453E; border-color: #C0453E; color: #fff; font-weight: 600; }

  .rad.heldag { padding: 11px 16px; flex-wrap: wrap; }
  .hrange { font-size: 12px; font-weight: 700; letter-spacing: 0.03em; white-space: nowrap; flex: none; }
  .hlbl { font-size: 10px; font-weight: 600; color: var(--t-mut); text-transform: uppercase; letter-spacing: 0.07em; flex: none; }
  .spacer { flex: 1; }
  .rad.heldag .rtitel { flex: none; }
  .rad.heldag .synkfel { flex-basis: 100%; }

  /* A2: den stora synk-etiketten ersatt av <Hornmarkor> (hörnbåge, färgen bär signalen).
     Listjusteringar §1: kategori-dropdownen är borta ur raderna — kategori
     sätts bara i editorn (segment-knapparna); färgen bär den i listan. */
  .synkbtn { border-color: var(--acc); color: var(--acc); font-weight: 600; }
  .synkfel { font-size: 11px; color: var(--rose); }

  /* ── Privata kalendrar ─────────────────────────────────────────────────── */
  .kallrubrik { font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--t-caps); align-self: center; margin-left: 6px; padding-left: 12px;
    border-left: 1px solid var(--div); }
  .chip.kalla { display: inline-flex; align-items: center; gap: 7px; }
  .chip.kalla .prick { width: 8px; height: 8px; border-radius: 2px; background: var(--kf); flex: none; }
  .chip.kalla.on { border-color: var(--kf); color: var(--t-head); }
  /* Släckt källa: pricken tappar färgen, inte bara chipet — annars läser den som tänd. */
  .chip.kalla:not(.on):not(.last) .prick { background: var(--div); }
  .chip.kalla.last { border-color: var(--kf); color: var(--t-head); cursor: default; }

  /* Radwrap bär popovern. .rad har overflow:hidden (hörnbågarna klipps mot
     kortet) och kan därför inte hysa den själv. */
  .radwrap, .kortwrap { position: relative; }

  /* Klickyta över den röda hörnbågen (som själv har pointer-events:none).
     Fäster utfällningen — öppnar aldrig redigeringen. */
  .krocktapp { position: absolute; right: 0; bottom: 0; width: 30px; height: 30px; z-index: 5;
    border: 0; background: transparent; padding: 0; cursor: pointer; }

  /* Tidslinje */
  .tidslinje { display: flex; flex-direction: column; }
  .tlrad { display: grid; grid-template-columns: 56px 1fr; gap: 14px; }
  .tltid { text-align: right; padding-top: 14px; }
  .tlt { font-size: 13px; font-weight: 700; color: var(--t-head); font-variant-numeric: tabular-nums; }
  .tld { font-size: 10px; color: var(--t-mut); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
  /* min-width:0 — grid-items har min-width:auto och skulle annars växa förbi sitt
     spår istället för att låta noteringen avkortas (spränger tidslinjen i sidled). */
  .tlspar { position: relative; min-width: 0; border-left: 2px solid var(--div); padding: 0 0 12px 22px; }
  .tldot { position: absolute; left: -6px; top: 20px; width: 10px; height: 10px; border-radius: 50%;
    border: 2px solid var(--kort); }
  /* position/overflow krävs för att <Hornmarkor> ska ankras och klippas av kortet. */
  .tlkort { position: relative; overflow: hidden; background: var(--kort); border: 1px solid var(--div); border-radius: 10px; box-shadow: var(--skugga);
    padding: 11px 13px; display: flex; align-items: center; gap: 11px; cursor: pointer; }
  .tlkort:hover { background: var(--div3); }
  .tlinfo { flex: 1; min-width: 0; }

  .foot { padding: 10px 30px; border-top: 1px solid var(--div3); font-size: 12px; color: var(--t-help); }

  .overlay { position: fixed; inset: 0; z-index: 50; background: rgba(28,24,16,.44);
    display: flex; align-items: flex-start; justify-content: center; padding: 56px 20px; overflow-y: auto; }
  .dialog { width: 100%; max-width: 520px; background: var(--sand); border: 1px solid var(--div);
    border-radius: 16px; box-shadow: 0 24px 60px rgba(40,32,16,.32); overflow: hidden; }
  .dhead { display: flex; align-items: center; gap: 10px; padding: 18px 22px 15px; border-bottom: 1px solid var(--div3); }
  .dhead span { font-size: 20px; font-weight: 700; color: var(--t-head); }
  .stang { margin-left: auto; width: 30px; height: 30px; border: 1px solid var(--div);
    background: var(--kort); border-radius: 8px; font-size: 17px; color: var(--t-mut); }
  .dbody { padding: 18px 22px 22px; display: flex; flex-direction: column; gap: 13px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px; color: var(--t-caps);
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  input, textarea { font-family: inherit; }
  .dbody input, .dbody textarea, .dbody select { padding: 9px 11px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; outline: none; }
  .dbody input:focus, .dbody textarea:focus, .dbody select:focus { border-color: var(--acc); }

  /* Redigeringskort — utfällt direkt under raden (Fotojobb: Lista + Tidslinje) */
  .redigerakort { display: flex; flex-direction: column; gap: 10px; margin-top: 10px;
    border: 1.5px solid var(--acc-border); border-radius: 10px; padding: 12px; background: var(--kort); }
  .redigerakort input, .redigerakort textarea { padding: 9px 11px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; outline: none; }
  .redigerakort textarea { resize: vertical; width: 100%; box-sizing: border-box; }
  .redigerakort input:focus, .redigerakort textarea:focus { border-color: var(--acc); }
  .rkfoot { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
  .grenlbl3 { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-right: 8px; }

  .tva { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .katblock { display: flex; flex-direction: column; gap: 6px; }
  .lbl { font-size: 11px; color: var(--t-caps); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  .katseg { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
  .katseg button { padding: 7px; border: 1px solid var(--div); border-radius: 8px; background: var(--kort);
    color: var(--t-mut); font-size: 12px; font-weight: 600; }
  .rad2 { display: flex; align-items: flex-end; gap: 18px; flex-wrap: wrap; }
  .check { flex-direction: row; align-items: center; gap: 9px; text-transform: none; letter-spacing: 0;
    font-size: 13px; font-weight: 400; color: var(--t-head); cursor: pointer; }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel);
    display: inline-flex; align-items: center; justify-content: center; font-size: 12px; color: var(--acc); }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }
  .vaxa { flex: 1; min-width: 200px; }
  .dfoot { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
  .sek { background: var(--kort); border: 1px solid var(--div); border-radius: 8px; padding: 10px 15px;
    font-size: 13px; color: var(--t-head); }
  .dnot { margin-left: auto; font-size: 11.5px; color: var(--t-help); }
</style>
