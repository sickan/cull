<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import {
    listaMatcher, hamtaMatch, sparaMatch, hamtaTrupp, sattAktivMatch,
    lasUttagFil, valjFil, listaTavlingar, listaLag, listaLagForTavling,
    listaUrval, raderaMatch, sattMatchSynk,
  } from '../lib/api.js'
  import Combobox from '../lib/Combobox.svelte'
  import Lagbricka from '../lib/Lagbricka.svelte'
  import { grenFarg, grenEtikett } from '../lib/gren.js'

  const dispatch = createEventDispatcher()

  let matcher = []
  let tavlingar = []
  let lagAlla = []
  let lagForTavling = []
  let projekt = []
  let laddar = true
  let sportFilter = 'alla'
  let matchGroupBy = 'datum'
  let oppen = null
  let utkast = null
  let bekraftaId = null
  let fel = ''
  let matchSearch = ''
  let matchSeasonSel = null      // null = aktiv säsong (se aktivAr nedan)
  let matchShowN = 12

  const SPORTER = ['alla', 'fotboll', 'handboll', 'volleyboll', 'beachvolley', 'tennis']
  const SPORT_ETIKETT = { fotboll: 'Fotboll', handboll: 'Handboll', volleyboll: 'Volleyboll', beachvolley: 'Beachvolley', tennis: 'Tennis' }
  // Normallängd per sport (min) → uträknad sluttid; utan avsparkstid = heldag.
  // Speglar MATCH_LANGD_MIN i app.py (backend sätter kalenderjobbets sluttid).
  const MATCH_LANGD = { fotboll: 120, volleyboll: 150, handboll: 90, beachvolley: 90, innebandy: 120, tennis: 120 }
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const MANAD = ['Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni', 'Juli', 'Augusti', 'September', 'Oktober', 'November', 'December']
  const SPORT_FARG = '#2F7CB0'

  onMount(async () => {
    ;[matcher, tavlingar, lagAlla, projekt] = await Promise.all(
      [listaMatcher(), listaTavlingar(), listaLag(), listaUrval()])
    laddar = false
  })

  // ── Sök, säsongsarkiv (demo: kalenderår ur datum) & paginering ────────────
  // Riktig säsongspartitionering + lazy-load per år är backend-arbete utanför
  // det här passet (se HANDOFF.md "Medvetet utanför / kvar") — här bucketas
  // matcherna client-side per kalenderår tills dess.
  const NU_AR = String(new Date().getFullYear())
  const norm = (s) => (s || '').toLowerCase()
  const matchesSok = (m, q) => !q || [m.lag_hemma, m.lag_borta, m.liga, m.arena].some((v) => norm(v).includes(q))

  $: sportFiltrerade = matcher.filter((m) => sportFilter === 'alla' || m.sport === sportFilter)
  $: matchArAlla = [...new Set(matcher.map((m) => (m.datum || '').slice(0, 4)).filter(Boolean))]
  $: aktivAr = matchArAlla.includes(NU_AR) ? NU_AR : ([...matchArAlla].sort().at(-1) || NU_AR)
  $: arkivAr = matchArAlla.filter((a) => a !== aktivAr).sort((a, b) => (a < b ? 1 : -1))
  $: aktivSasongCount = sportFiltrerade.filter((m) => (m.datum || '').slice(0, 4) === aktivAr).length
  $: sasong = matchSeasonSel || aktivAr
  $: iAktivSasong = sasong === aktivAr

  $: matchSearchQ = norm(matchSearch)
  $: sasongFiltrerade = sportFiltrerade
    .filter((m) => (m.datum || '').slice(0, 4) === sasong)
    .filter((m) => matchesSok(m, matchSearchQ))

  $: { matchSearch; matchSeasonSel; matchShowN = 12 }   // nollställ vid sök/säsongsbyte

  $: datumSorterade = sortDatum(sasongFiltrerade)
  $: datumSynliga = datumSorterade.slice(0, matchShowN)
  $: grupper = matchGroupBy === 'liga' ? grupperaLiga(sasongFiltrerade) : grupperaDatum(datumSynliga)

  $: arkivLista = iAktivSasong ? [] : [...sasongFiltrerade].sort((a, b) => (a.datum < b.datum ? 1 : a.datum > b.datum ? -1 : 0))

  const GREN_ETIKETT = { dam: 'Dam', herr: 'Herr', mixed: 'Mixed' }
  // detalj (gren · sport) skiljer lag med samma namn åt (Malmö FF dam/herr).
  $: lagVal = (lagForTavling.length ? lagForTavling : lagAlla).map((l) => ({
    id: l.id, namn: l.namn,
    detalj: [GREN_ETIKETT[l.gren], SPORT_ETIKETT[l.sport]].filter(Boolean).join(' · '),
  }))
  $: tavlingVal = tavlingar.map((t) => ({ id: t.id, namn: t.namn }))
  $: hemSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'hemma')
  $: bortaSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'borta')

  const del = (iso) => (iso || '').split('T')[0].split('-').map(Number)
  const harTid = (t) => /^\d{1,2}:\d{2}$/.test(t || '')
  const arNy = (x) => typeof x?.id === 'string' && x.id.startsWith('ny-')
  function plusMin(hhmm, min) {
    const [h, m] = hhmm.split(':').map(Number)
    const tot = (((h * 60 + m + min) % 1440) + 1440) % 1440
    return `${String(Math.floor(tot / 60)).padStart(2, '0')}:${String(tot % 60).padStart(2, '0')}`
  }
  const durEtikett = (min) => `${Math.floor(min / 60)} tim${min % 60 ? ` ${min % 60} min` : ''}`
  function slutFor(u) {
    if (!u || !harTid(u.tid)) return { slut: 'Heldag · tid ej fastställd', dur: 'sätts när avsparkstid är klar' }
    const d = MATCH_LANGD[u.sport] || 120
    return { slut: `slut ~${plusMin(u.tid, d)}`, dur: durEtikett(d) }
  }
  $: slutInfo = slutFor(utkast)
  $: oppenRad = matcher.find((x) => x.id === oppen)
  function periodText(t) {
    const f = (t.fran || ''), ti = (t.till || '')
    if (/^\d{4}-\d{2}/.test(f) && /^\d{4}-\d{2}/.test(ti)) {
      const a = f.split('-'), b = ti.split('-')
      const yr = b[0] === a[0] ? a[0] : `${a[0]}–${b[0]}`
      return `${MK[+a[1] - 1]}–${MK[+b[1] - 1]} ${yr}`
    }
    return f            // fri text ("apr–okt 2026")
  }
  function initialer(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }
  function fargForLag(namn) {
    const l = lagAlla.find((x) => x.namn === namn)
    return l ? (l.stall_hemma || l.profilfarg) : ''
  }
  function loggaForLag(namn) { return lagAlla.find((x) => x.namn === namn)?.logga || '' }
  const bildUrl = (p) => (/^(https?|file):/.test(p) ? p : 'file://' + p)

  function grupperaLiga(lista) {
    const m = new Map()
    for (const x of lista) {
      const k = x.tavling_id || x.liga || 'ovrigt'
      if (!m.has(k)) m.set(k, { key: k, namn: x.liga || 'Övriga matcher', matcher: [] })
      m.get(k).matcher.push(x)
    }
    return [...m.values()].map((g) => {
      const t = tavlingar.find((tv) => tv.id === g.key || tv.namn === g.namn) || {}
      return { ...g, rich: true, badge: initialer(g.namn), typ: TYP_ETIKETT[t.typ] || 'Liga',
        meta: [SPORT_ETIKETT[t.sport] || '', periodText(t), t.ort].filter(Boolean).join(' · ') }
    })
  }

  // Matcher utan datum sorteras sist (nyckel '9999-99-99' vinner aldrig jämförelsen).
  function sortDatum(lista) {
    const nyckel = (x) => (x.datum && x.datum.length === 10) ? x.datum : '9999-99-99'
    return [...lista].sort((a, b) => (nyckel(a) < nyckel(b) ? -1 : nyckel(a) > nyckel(b) ? 1 : 0))
  }
  function grupperaDatum(lista) {
    const m = new Map()
    for (const x of lista) {
      const d = del(x.datum)
      const key = d.length === 3 ? `${d[0]}-${d[1]}` : 'zzz'
      const namn = d.length === 3 ? `${MANAD[d[1] - 1]} ${d[0]}` : 'Utan datum'
      if (!m.has(key)) m.set(key, { key, namn, matcher: [] })
      m.get(key).matcher.push(x)
    }
    return [...m.values()].map((g) => ({ ...g, rich: false }))
  }

  async function toggla(m) {
    if (oppen === m.id) { oppen = null; utkast = null; lagForTavling = []; return }
    oppen = m.id
    utkast = await hamtaMatch(m.id)
    await laddaLagForTavling(utkast.liga)
  }
  async function laddaLagForTavling(ligaNamn) {
    const t = tavlingar.find((x) => x.namn === ligaNamn)
    lagForTavling = t ? await listaLagForTavling(t.id) : []
  }

  function nyMatch() {
    const tmp = { id: 'ny-' + Date.now(), datum: '', tid: '', arena: '', status: 'kommande', resultat: '', sport: '', lag_hemma: '', lag_borta: '', lag_hemma_id: null, lag_borta_id: null, liga: '' }
    matcher = [{ ...tmp, trupp_n: 0 }, ...matcher]
    oppen = tmp.id; utkast = { ...tmp, spelare: [] }; lagForTavling = []
  }

  async function valjTavling(o) {
    utkast.liga = o.namn
    const t = tavlingar.find((x) => x.id === o.id)
    if (t?.sport) utkast.sport = t.sport
    await laddaLagForTavling(o.namn)
  }
  const skapaTavling = (namn) => { utkast.liga = namn; lagForTavling = [] }
  // Spara REF (lag-id), inte bara namnet — två lag kan heta lika (dam/herr).
  const valjHemma = (o) => { utkast.lag_hemma = o.namn; utkast.lag_hemma_id = o.id }
  const valjBorta = (o) => { utkast.lag_borta = o.namn; utkast.lag_borta_id = o.id }
  const skapaHemma = (namn) => { utkast.lag_hemma = namn; utkast.lag_hemma_id = null }
  const skapaBorta = (namn) => { utkast.lag_borta = namn; utkast.lag_borta_id = null }
  const arMatch = () => !utkast || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))

  let hamtar = false
  async function lasUttag(sida) {
    if (arMatch()) return
    const f = await valjFil('Välj startelva (matchblad/CSV/foto)')
    if (!f.ok) return
    hamtar = true
    const res = await lasUttagFil(utkast.id, f.path, sida)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }
  const truppStorlek = (namn) => lagAlla.find((x) => x.namn === namn)?.trupp_n || 0
  const truppNot = (namn) => {
    const n = truppStorlek(namn)
    return n ? `ur trupp · ${n} spelare` : 'ingen trupp i Lag & tävlingar'
  }
  const startelvaEtikett = (namn, nStart) => {
    if (!nStart) return 'ej uppladdad'
    const n = truppStorlek(namn)
    return n ? `${nStart} av ${n}` : `${nStart} spelare`
  }
  async function hamtaTruppen() {
    if (arMatch()) return
    hamtar = true
    const res = await hamtaTrupp(utkast.id)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }

  async function togglaSynk(m) {
    if (!m || arNy(m)) return
    fel = ''
    const r = await sattMatchSynk(m.id, !m.synk_jobb_id)
    if (!r?.ok) { fel = r?.fel || 'Kunde inte ändra kalendersynken.'; return }
    matcher = matcher.map((x) => (x.id === m.id ? { ...x, synk_jobb_id: r.synk_jobb_id } : x))
  }

  async function taBort(m) {
    bekraftaId = null
    fel = ''
    if (!arNy(m)) {
      const r = await raderaMatch(m.id)
      if (!r?.ok) { fel = r?.fel || 'Kunde inte ta bort matchen.'; return }
    }
    if (oppen === m.id) { oppen = null; utkast = null; lagForTavling = [] }
    matcher = matcher.filter((x) => x.id !== m.id)
  }

  async function spara() {
    const m = { ...utkast }
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) delete m.id
    await sparaMatch(m)
    ;[matcher, lagAlla] = await Promise.all([listaMatcher(), listaLag()])
    oppen = null; utkast = null; lagForTavling = []
  }
  async function aktivera(m) {
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) return
    await sattAktivMatch(m.id)      // persistera FÖRE navigering — annars hinner
    dispatch('aktiverad', m)        // Gallra/Leverera/Publicera fråga aktivMatch() för tidigt
  }
  function aterUppta() { dispatch('navigera', 'gallra') }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Matcher</h1>
    <span class="sub">Planera kommande matcher och återuppta tidigare projekt</span>
  </header>

  <div class="filterrad">
    <div class="filterleft">
      <div class="caps">Kommande</div>
      <div class="grupptoggle">
        <span class="grupplbl">Gruppera</span>
        <div class="seg">
          <button class:on={matchGroupBy === 'datum'} on:click={() => (matchGroupBy = 'datum')}>Datum</button>
          <button class:on={matchGroupBy === 'liga'} on:click={() => (matchGroupBy = 'liga')}>Liga/Tävling</button>
        </div>
      </div>
    </div>
    <div class="chips">
      {#each SPORTER as s}
        <button class="chip" class:on={sportFilter === s} on:click={() => (sportFilter = s)}>{s === 'alla' ? 'Alla' : SPORT_ETIKETT[s]}</button>
      {/each}
    </div>
  </div>

  <div class="toolrad">
    <div class="sokbox">
      <svg class="sokik" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input bind:value={matchSearch} placeholder="Sök lag, liga eller arena…" />
    </div>
    <div class="sasongchips">
      <button class="sasong" class:on={iAktivSasong} on:click={() => (matchSeasonSel = null)}>{aktivAr} · {aktivSasongCount}</button>
      {#each arkivAr as ar (ar)}
        <button class="sasong arkiv" class:on={sasong === ar} on:click={() => (matchSeasonSel = ar)}>{ar}</button>
      {/each}
    </div>
  </div>

  {#if fel}<p class="fel">{fel}</p>{/if}

  {#if laddar}
    <p class="tom">Laddar matcher…</p>
  {:else if !iAktivSasong}
    <div class="arkivhuvud scd">Arkiv · säsong {sasong} · {arkivLista.length} matcher</div>
    {#if !arkivLista.length}
      <p class="tom">Inga matcher hittades i den här säsongen.</p>
    {:else}
      <div class="arkivlista">
        {#each arkivLista as m (m.id)}
          <div class="arkivrad" style="border-left:3px {m.hem_gren ? 'solid' : 'dashed'} {grenFarg(m.hem_gren)}">
            <div class="adatum scd">
              <span class="ad">{del(m.datum)[2] || '–'}</span>
              <span class="amon">{del(m.datum).length === 3 ? MK[del(m.datum)[1] - 1] : ''}</span>
            </div>
            <div class="afixtur">
              <div class="afx scd">{m.lag_hemma} – {m.lag_borta}
                {#if m.hem_gren}<span class="grenlbl scd" style="color:{grenFarg(m.hem_gren)}">{grenEtikett(m.hem_gren)}</span>{/if}
              </div>
              <div class="ameta">{[m.liga, m.arena, m.resultat ? `slutresultat ${m.resultat}` : ''].filter(Boolean).join(' · ')}</div>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    {#if projekt.length}
      <div class="caps proj">Tidigare projekt</div>
      <div class="projgrid">
        {#each projekt as pr (pr.id)}
          <button class="projkort" on:click={aterUppta}>
            <div class="projbild"><span>{(pr.skapad || '').split(' ')[0]}</span></div>
            <div class="projtxt">
              <div class="projnamn">{pr.lag_hemma ? `${pr.lag_hemma} – ${pr.lag_borta}` : (pr.kalla || 'Urval').split('/').pop()}</div>
              <div class="projsub">{[pr.kamera, pr.bilder ? pr.bilder + ' bilder' : '', pr.status].filter(Boolean).join(' · ')}</div>
              <div class="projater">Återuppta ›</div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  {:else}
    <div class="grupper">
      {#each grupper as g (g.key)}
        <div class="grupp">
          {#if g.rich}
            <div class="ghuvud">
              <span class="glogo scd" style="background:{SPORT_FARG}">{g.badge}</span>
              <div class="gtxt">
                <div class="gnamn">{g.namn}</div>
                <div class="gmeta">{g.meta}</div>
              </div>
              <span class="gtyp">{g.typ}</span>
            </div>
          {:else}
            <div class="manad scd">{g.namn}</div>
          {/if}

          <div class="matcher">
            {#each g.matcher as m (m.id)}
              <div class="match"
                style="border-left:3px {m.hem_gren ? 'solid' : 'dashed'} {grenFarg(m.hem_gren)}">
                <div class="rad" role="button" tabindex="0" on:click={() => toggla(m)}
                  on:keydown={(e) => e.key === 'Enter' && toggla(m)}>
                  <div class="datum scd">
                    <div class="d">{del(m.datum)[2] || '–'}</div>
                    <div class="mon">{del(m.datum).length === 3 ? MK[del(m.datum)[1] - 1] : ''}</div>
                  </div>
                  <div class="fixtur">
                    <div class="fx scd">{m.lag_hemma} – {m.lag_borta}</div>
                    <div class="fmeta">
                      {#if m.hem_gren}<span class="grenlbl scd" style="color:{grenFarg(m.hem_gren)}">{grenEtikett(m.hem_gren)}</span>{/if}
                      <span>{[SPORT_ETIKETT[m.sport] || '', m.arena, harTid(m.tid) ? m.tid : 'Heldag'].filter(Boolean).join(' · ')}</span>
                      {#if !harTid(m.tid)}<span class="heldagstagg">Heldag</span>{/if}
                    </div>
                  </div>
                  {#if m.status === 'avslutad' && m.resultat}
                    <span class="status res scd">{m.resultat}</span>
                  {:else}
                    <span class="status" class:klar={m.trupp_n > 0}>{m.trupp_n > 0 ? 'Roster klar' : 'Planera'}</span>
                  {/if}
                  {#if !arNy(m)}
                    <button class="synkpill" class:pa={!!m.synk_jobb_id} title="Google Calendar-synk"
                      on:click|stopPropagation={() => togglaSynk(m)}>
                      <span class="prick"></span>{m.synk_jobb_id ? 'Synkad' : 'Ej synkad'}
                    </button>
                  {/if}
                  <button class="papperskorg" title="Ta bort match"
                    on:click|stopPropagation={() => (bekraftaId = m.id)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg>
                  </button>
                  <span class="chev" class:upp={oppen === m.id}>›</span>
                </div>

                {#if bekraftaId === m.id}
                  <div class="bekrafta">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#C0453E" stroke-width="1.8"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg>
                    <div class="btxt">Ta bort <b>{m.lag_hemma} – {m.lag_borta}</b>? Kan inte ångras.</div>
                    <button class="bavbryt" on:click={() => (bekraftaId = null)}>Avbryt</button>
                    <button class="bta" on:click={() => taBort(m)}>Ta bort</button>
                  </div>
                {/if}

                {#if oppen === m.id && utkast}
                  <div class="editor">
                    <div class="rad2">
                      <label>Hemmalag
                        <Combobox options={lagVal} value={utkast.lag_hemma} placeholder="Välj lag…"
                          on:pick={(e) => valjHemma(e.detail)} on:create={(e) => skapaHemma(e.detail)} />
                      </label>
                      <label>Bortalag
                        <Combobox options={lagVal} value={utkast.lag_borta} placeholder="Välj lag…"
                          on:pick={(e) => valjBorta(e.detail)} on:create={(e) => skapaBorta(e.detail)} />
                      </label>
                    </div>
                    <label class="full">Tävling
                      <Combobox options={tavlingVal} value={utkast.liga} placeholder="Välj tävling…"
                        on:pick={(e) => valjTavling(e.detail)} on:create={(e) => skapaTavling(e.detail)} />
                    </label>
                    <div class="rad3">
                      <input type="date" bind:value={utkast.datum} />
                      <input type="time" bind:value={utkast.tid} />
                      <div class="slutkol">
                        <span class="slut">{slutInfo.slut}</span>
                        <span class="slutdur">{slutInfo.dur}</span>
                      </div>
                      <input bind:value={utkast.arena} placeholder="Arena" />
                    </div>

                    <div class="uttagrad"><span class="caps2">Matchdaguttag</span><span class="uttagnot">kopplat till matchen</span></div>
                    <div class="lagbox2">
                      {#each [{ sida: 'hemma', namn: utkast.lag_hemma, lista: hemSpelare }, { sida: 'borta', namn: utkast.lag_borta, lista: bortaSpelare }] as kol}
                        {@const nStart = kol.lista.filter((p) => p.start).length}
                        <div class="lbox">
                          <div class="lhuvud">
                            <Lagbricka namn={kol.namn} farg={fargForLag(kol.namn)} logga={loggaForLag(kol.namn)} storlek={30} />
                            <div class="lnamn-wrap">
                              <div class="lnamn scd">{kol.namn || (kol.sida === 'hemma' ? 'Hemmalag' : 'Bortalag')}</div>
                              <div class="lsub">{kol.sida === 'hemma' ? 'Hemma' : 'Borta'} · {truppNot(kol.namn)}</div>
                            </div>
                          </div>
                          <div class="grupplbl">Startelva <span class="grupplbl-sub">· delmängd av truppen</span></div>
                          <button class="lbtn" class:i={nStart > 0} on:click={() => lasUttag(kol.sida)} disabled={hamtar || arMatch()}>
                            <span>{nStart ? 'Byt fil…' : 'Ladda upp startelva…'}</span>
                            <span class="lbtn-n">{startelvaEtikett(kol.namn, nStart)}</span>
                          </button>
                        </div>
                      {/each}
                    </div>
                    <div class="hint">Hela truppen kommer från <b>Lag &amp; tävlingar</b>. Startelvan är en delmängd som läses ur matchblad/CSV/foto strax innan match — matchas mot lagets trupp och sparas på matchen. <button class="lank" on:click={hamtaTruppen} disabled={hamtar || arMatch()}>{hamtar ? 'Hämtar…' : 'Hämta trupp automatiskt'}</button></div>

                    <div class="gcalkort">
                      <span class="gcalik">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                      </span>
                      <div class="gcaltxt">
                        <div class="gt">Lägg i kalender</div>
                        <div class="gs">Lägg matchen i din Google Calendar så du har koll på uppdraget</div>
                      </div>
                      <button class="gcalbtn" class:i={!!oppenRad?.synk_jobb_id}
                        on:click={() => !oppenRad?.synk_jobb_id && togglaSynk(oppenRad)} disabled={arMatch()}>
                        {oppenRad?.synk_jobb_id ? 'I kalendern ✓' : 'Lägg i kalender ›'}
                      </button>
                    </div>

                    <div class="lankblock">
                      <span class="caps2">Efter match · länkar</span>
                      <div class="rad2">
                        <label>Pixieset-galleri
                          <input bind:value={utkast.galleri} placeholder="https://…pixieset.com/…" disabled={arMatch()} />
                        </label>
                        <label>Publicerad hemsideslänk
                          <input bind:value={utkast.sida_url} placeholder="https://dalecarliaphoto.se/…" disabled={arMatch()} />
                        </label>
                      </div>
                    </div>

                    <div class="knappar">
                      <button class="prim" on:click={() => aktivera(utkast)}>Aktivera match ›</button>
                      <button class="sek" on:click={spara}>Spara</button>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}

      {#if matchGroupBy === 'datum' && datumSorterade.length > matchShowN}
        <div class="pagineringsrad">
          <button class="visafler" on:click={() => (matchShowN += 12)}>Visa 12 till ›</button>
          <span class="visarinfo">visar {datumSynliga.length} av {datumSorterade.length}</span>
        </div>
      {/if}

      <button class="ny" on:click={nyMatch}>+ Ny match</button>
    </div>

    {#if projekt.length}
      <div class="caps proj">Tidigare projekt</div>
      <div class="projgrid">
        {#each projekt as pr (pr.id)}
          <button class="projkort" on:click={aterUppta}>
            <div class="projbild"><span>{(pr.skapad || '').split(' ')[0]}</span></div>
            <div class="projtxt">
              <div class="projnamn">{pr.lag_hemma ? `${pr.lag_hemma} – ${pr.lag_borta}` : (pr.kalla || 'Urval').split('/').pop()}</div>
              <div class="projsub">{[pr.kamera, pr.bilder ? pr.bilder + ' bilder' : '', pr.status].filter(Boolean).join(' · ')}</div>
              <div class="projater">Återuppta ›</div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 920px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .filterrad { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin: 20px 2px 12px; }
  .filterleft { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: var(--t-caps); }
  .grupptoggle { display: flex; align-items: center; gap: 7px; }
  .grupplbl { font-size: 11px; color: var(--t-help); }
  .seg { display: flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; }
  .seg button { padding: 7px 14px; border: 0; border-radius: 7px; background: transparent;
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .seg button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { padding: 5px 13px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; }
  .chip.on { background: var(--acc); border-color: var(--acc); color: #fff; font-weight: 600; }

  /* Verktygsrad: sök + säsongsarkiv */
  .toolrad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 0 2px 16px; }
  .sokbox { flex: 1; min-width: 220px; display: flex; align-items: center; gap: 8px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort); padding: 8px 14px; }
  .sokik { width: 15px; height: 15px; color: var(--t-help); flex: none; }
  .sokbox input { flex: 1; min-width: 0; border: 0; background: transparent; padding: 0;
    font-size: 13px; color: var(--t-head); outline: none; }
  .sasongchips { display: flex; gap: 6px; flex: none; }
  .sasong { padding: 7px 14px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .sasong.on { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .sasong.arkiv.on { background: var(--div3); border-color: var(--div); color: var(--t-head); }

  /* Arkivvy: platt, icke-expanderbar lista */
  .arkivhuvud { font-size: 13px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--t-mut); margin: 4px 2px 12px; }
  .arkivlista { display: flex; flex-direction: column; gap: 8px; }
  .arkivrad { display: flex; align-items: center; gap: 14px; background: var(--kort); border: 1px solid var(--div);
    border-radius: var(--r); box-shadow: var(--skugga); padding: 8px 12px; }
  .adatum { width: 36px; flex: none; text-align: center; }
  .adatum .ad { font-size: 17px; font-weight: 700; color: var(--t-head); line-height: 1; display: block; }
  .adatum .amon { font-size: 9px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-help); }
  .afixtur { flex: 1; min-width: 0; }
  .afx { font-size: 14.5px; font-weight: 700; color: var(--t-head); display: flex; align-items: center; gap: 7px; }
  .ameta { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }

  /* Paginering (Datum-vyn) */
  .pagineringsrad { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 4px; }
  .visafler { padding: 8px 16px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-head); font-size: 12.5px; font-weight: 600; }
  .visafler:hover { border-color: var(--acc); color: var(--acc); }
  .visarinfo { font-size: 11px; color: var(--t-help); }

  .grupper { display: flex; flex-direction: column; gap: 20px; }
  .manad { font-weight: 700; font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--t-mut); margin-bottom: 10px; }
  .ghuvud { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .glogo { width: 34px; height: 34px; border-radius: 8px; color: #fff; display: flex; align-items: center;
    justify-content: center; flex: none; font-size: 12px; font-weight: 700; }
  .gtxt { flex: 1; min-width: 0; }
  .gnamn { font-size: 14px; font-weight: 600; color: var(--t-head); }
  .gmeta { font-size: 11.5px; color: var(--t-mut); }
  .gtyp { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--t-mut); background: var(--div3); padding: 3px 9px; border-radius: 6px; flex: none; }

  .matcher { display: flex; flex-direction: column; gap: 10px; }
  .match { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); overflow: hidden; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%; padding: 8px 12px; border: 0;
    background: transparent; text-align: left; cursor: pointer; }
  .rad:hover { background: var(--div3); }
  .datum { width: 36px; flex: none; text-align: center; }
  .datum .d { font-size: 17px; font-weight: 700; color: var(--acc); line-height: 1; }
  .datum .mon { font-size: 9px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--acc); margin-top: 1px; }
  .fixtur { flex: 1; min-width: 0; }
  .fx { font-size: 14.5px; font-weight: 700; color: var(--t-head); }
  .fmeta { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--t-mut); margin-top: 2px; }
  .grenlbl { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; flex: none; }
  .heldagstagg { font-size: 9.5px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--acc); background: var(--acc-soft); padding: 2px 7px; border-radius: 5px; flex: none; }
  .status { font-size: 13px; font-weight: 600; color: var(--t-mut); flex: none; }
  .status.klar { color: var(--ok); }
  .status.res { font-size: 20px; font-weight: 700; color: var(--t-head); }
  .synkpill { display: inline-flex; align-items: center; gap: 6px; flex: none; padding: 5px 11px;
    border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    font-size: 11.5px; font-weight: 600; color: var(--t-mut); }
  .synkpill .prick { width: 6px; height: 6px; border-radius: 50%; background: var(--t-help); flex: none; }
  .synkpill.pa { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 40%, var(--div)); }
  .synkpill.pa .prick { background: var(--ok); }
  .synkpill:hover { border-color: var(--acc); }
  .papperskorg { flex: none; width: 30px; height: 30px; display: inline-flex; align-items: center;
    justify-content: center; border: 1px solid var(--div); border-radius: 7px; background: var(--kort);
    color: var(--t-mut); }
  .papperskorg svg { width: 14px; height: 14px; }
  .papperskorg:hover { color: #C0453E; border-color: #C0453E; }
  .chev { width: 18px; text-align: center; color: var(--t-mut); font-size: 17px; transition: transform 0.15s; flex: none; }
  .chev.upp { transform: rotate(90deg); }

  .bekrafta { border-top: 1px solid var(--div3); padding: 12px 14px; display: flex; align-items: center;
    gap: 12px; background: rgba(192, 69, 62, 0.06); }
  .bekrafta svg { width: 17px; height: 17px; flex: none; }
  .btxt { flex: 1; font-size: 12.5px; color: var(--t-head); }
  .bavbryt { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 7px 13px; font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .bta { flex: none; background: #C0453E; border: 0; border-radius: 7px; padding: 7px 13px;
    font-size: 12.5px; font-weight: 600; color: #fff; }
  .fel { color: #C0453E; font-size: 12.5px; margin: 0 2px 10px; }

  .editor { border-top: 1px solid var(--div3); padding: 16px 14px; display: flex; flex-direction: column; gap: 12px; }
  .rad2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .rad3 { display: flex; gap: 10px; }
  .rad3 input:nth-of-type(1) { width: 150px; flex: none; }
  .rad3 input:nth-of-type(2) { width: 104px; flex: none; }
  .rad3 input:nth-of-type(3) { flex: 1; min-width: 0; }
  .slutkol { display: flex; flex-direction: column; justify-content: center; flex: none; }
  .slut { font-size: 12px; color: var(--t-mut); font-variant-numeric: tabular-nums; }
  .slutdur { font-size: 10px; color: var(--t-help); }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  label.full { width: 100%; }
  input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel);
    color: var(--t-head); font-size: 13px; font-weight: 400; text-transform: none; letter-spacing: 0; outline: none; }
  input:focus { border-color: var(--acc); }
  .caps2 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-top: 4px; }

  .lagbox2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .lbox { border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .lhuvud { display: flex; align-items: center; gap: 9px; }
  .lnamn-wrap { min-width: 0; }
  .lnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lsub { font-size: 10.5px; color: var(--t-mut); }
  .uttagrad { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
  .uttagnot { font-size: 10px; color: var(--t-help); }
  .grupplbl { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-help); margin-bottom: 4px; }
  .grupplbl-sub { font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--t-help); }
  .lbtn { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px;
    background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 7px 10px;
    font-size: 12px; color: var(--t-mut); }
  .lbtn.i { border-color: color-mix(in srgb, var(--acc) 45%, var(--div)); color: var(--t-head); }
  .lbtn-n { font-size: 10.5px; color: var(--t-mut); flex: none; }
  .lbtn:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .lbtn:disabled { opacity: 0.5; }
  .hint { font-size: 10.5px; color: var(--t-help); line-height: 1.45; }
  .lank { border: 0; background: none; color: var(--acc); font-size: 10.5px; font-weight: 600; padding: 0; }
  .lank:disabled { opacity: 0.5; }

  .gcalkort { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--div3);
    border-radius: 10px; background: var(--panel); }
  .gcalik { width: 36px; height: 36px; border-radius: 9px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .gcalik svg { width: 18px; height: 18px; }
  .gcaltxt { flex: 1; min-width: 0; }
  .gt { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .gs { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }
  .gcalbtn { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 14px; font-size: 13px; font-weight: 600; flex: none; }
  .gcalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .gcalbtn:disabled { opacity: 0.5; }

  .lankblock { display: flex; flex-direction: column; gap: 8px; }

  .knappar { display: flex; gap: 10px; }
  .prim { padding: 9px 16px; border: 0; border-radius: 7px; background: var(--acc); color: #fff; font-size: 13px; font-weight: 600; }
  .sek { padding: 9px 14px; border: 1px solid var(--div); border-radius: 7px; background: var(--kort); color: var(--t-head); font-size: 13px; }

  .ny { padding: 14px; width: 100%; border: 1.5px dashed var(--div); border-radius: var(--r);
    background: transparent; color: var(--t-mut); font-size: 13px; font-weight: 500; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }

  .proj { margin: 26px 2px 12px; }
  .projgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .projkort { border: 1px solid var(--div); border-radius: var(--r); overflow: hidden; background: var(--kort);
    box-shadow: var(--skugga); padding: 0; text-align: left; }
  .projkort:hover { border-color: var(--acc); }
  .projbild { aspect-ratio: 4 / 3; display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 9px, var(--panel) 9px, var(--panel) 18px); }
  .projbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--t-mut); }
  .projtxt { padding: 10px 12px; }
  .projnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .projsub { font-size: 11px; color: var(--t-mut); margin-top: 2px; }
  .projater { font-size: 12px; font-weight: 600; color: var(--acc); margin-top: 8px; }
</style>
