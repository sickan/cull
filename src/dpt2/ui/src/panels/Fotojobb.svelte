<script>
  import { onMount, onDestroy, tick, createEventDispatcher } from 'svelte'
  import { listaFotojobb, sparaFotojobb, raderaFotojobb, kalenderStatus, aktiveraSynkFotojobb, listaMatcher, listaLag } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { grenFarg } from '../lib/gren.js'
  import Hornmarkor from '../lib/Hornmarkor.svelte'
  import { synkFarg, jobbSynkStatus } from '../lib/synk.js'

  const dispatch = createEventDispatcher()

  let jobb = []
  let matcher = []
  let lagAlla = []
  let status = null            // null = okänd (visa ej offline-banner förrän känd)
  let laddar = true
  let layout = 'lista'          // lista | tidslinje
  let katFilter = 'Alla'
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
  $: grupper = gruppera(filtrerade)

  function gruppera(lista) {
    // Fallande: senaste aktiviteterna överst (framtid → historik), scroll-till-idag hittar dagens.
    const sorted = [...lista].sort((a, b) => (b.start_at || '').localeCompare(a.start_at || ''))
    const m = new Map()
    for (const j of sorted) {
      const k = manadNyckel(j.start_at)
      if (!m.has(k)) m.set(k, [])
      m.get(k).push(j)
    }
    return [...m.entries()].map(([label, jobb]) => ({ label, jobb }))
  }

  async function laddaOm() { jobb = await listaFotojobb(); if (!Array.isArray(jobb)) jobb = [] }

  async function bytKategori(j, val) {
    await sparaFotojobb({ ...j, category: val || null })
    await laddaOm()
  }
  function nyttJobb() {
    modal = { title: '', start_at: '', end_at: '', location: '', description: '', category: '', all_day: false, match_id: '' }
  }
  // datetime-local kräver 'YYYY-MM-DDTHH:mm' — heldagsjobb lagras som rent datum
  // ('2026-10-24') och skulle annars lämna fältet tomt (placeholder).
  const tillLokal = (v) => {
    const s = (v || '').slice(0, 16)
    return !s ? '' : s.includes('T') ? s : s + 'T00:00'
  }
  // Redigering flyttad in i listan (utfällt kort) — modalen är kvar bara för "＋ Nytt fotojobb".
  function oppnaRedigering(j) {
    if (jobEditId === j.id) { stangRedigering(); return }     // klick igen stänger, nytt "Ändra" flyttar kortet
    redigerar = { ...j, category: j.category || '', match_id: j.match_id || '',
      start_at: tillLokal(j.start_at), end_at: tillLokal(j.end_at) }
    jobEditId = j.id
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
    if (jobEditId != null) stangRedigering()
    else if (modal) modal = null
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
          <button class:on={layout === 'lista'} on:click={() => (layout = 'lista')}>Lista</button>
          <button class:on={layout === 'tidslinje'} on:click={() => (layout = 'tidslinje')}>Tidslinje</button>
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
      </div>
      <div class="hopp">
        <button class="tillidag" on:click={scrollTopp}>↑ Till toppen</button>
        <button class="tillidag" on:click={scrollTillIdag}>↓ Till idag</button>
      </div>
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

      {#if grupper.length === 0}
        <div class="empty">
          <div class="etxt">Inga fotojobb i den här vyn.</div>
          <div class="ehelp">Lägg till ett så speglas det till din kalender.</div>
        </div>
      {:else}
        {#each grupper as g}
          <div class="manad scd">{g.label}</div>
          {#if layout === 'tidslinje'}
            <div class="tidslinje">
              {#each g.jobb as j (j.id)}
                {@const gren = grenForJobb(j)}
                <div class="tlrad" data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)}>
                  <div class="tltid scd">
                    <div class="tlt">{j.all_day ? '–' : klocka(j.start_at)}</div>
                    <div class="tld">{veckodag(j.start_at)} {del(j.start_at)[2] || ''}</div>
                  </div>
                  <div class="tlspar" style="border-left-color:{katFarg(j.category)}">
                    <span class="tldot" style="background:{katFarg(j.category)}"></span>
                    <div class="tlkort" role="button" tabindex="0" class:forfluten={arForfluten(j)}
                      on:click={() => oppnaRedigering(j)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j)}>
                      <div class="tlinfo">
                        <div class="rtitel stor">{#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}{j.title}</div>
                        <div class="when">{j.all_day ? 'Heldag · ' + heldagText(j) : ''}{j.location ? (j.all_day ? ' · ' : '') + j.location : ''}</div>
                        {#if synkFelId === j.id}<div class="synkfel">⚠ {synkFelMsg}</div>{/if}
                      </div>
                      <select class="katsel" value={j.category || ''} on:click|stopPropagation on:change={(e) => bytKategori(j, e.target.value)}>
                        <option value="">Okategoriserat</option>
                        {#each KATEGORIER as k}<option value={k}>{k}</option>{/each}
                      </select>
                      <span class="synk" class:vantar={!synkad(j) && !j.utkast} class:utkast={j.utkast}>{synkText(j)}</span>
                      {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                      <button class="mini" on:click|stopPropagation={() => oppnaRedigering(j)}>Ändra</button>
                      <button class="mini kryss" class:armerad={$armerad === `fj-${j.id}`}
                        title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                        on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>{$armerad === `fj-${j.id}` ? 'Ta bort?' : '×'}</button>
                    </div>
                    {#if jobEditId === j.id && redigerar}
                      <div class="redigerakort">
                        <label class="full">Titel<input bind:value={redigerar.title} placeholder="Titel" /></label>
                        <div class="tva">
                          <label>Start<input type="datetime-local" bind:value={redigerar.start_at} /></label>
                          <label>Slut<input type="datetime-local" bind:value={redigerar.end_at} /></label>
                        </div>
                        <label class="full">Plats<input bind:value={redigerar.location} placeholder="t.ex. Rättvik" /></label>
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
              {#each g.jobb as j (j.id)}
                {@const gren = grenForJobb(j)}
                {#if j.all_day}
                  <div class="rad heldag" role="button" tabindex="0" class:idag={arIdag(j)} class:forfluten={arForfluten(j)} data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)} style="border-left-color:{katFarg(j.category)}"
                    on:click={() => oppnaRedigering(j)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j)}>
                    <Hornmarkor farg={synkFarg(jobbSynkStatus(j))} r={12} titel={synkText(j)} />
                    <span class="hrange scd" style="color:{katFarg(j.category)}">{heldagText(j)}</span>
                    {#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}
                    <span class="rtitel">{j.title}</span>
                    <span class="hlbl">Heldag</span>
                    {#if arIdag(j)}<span class="idagbricka">Idag</span>{/if}
                    <select class="katsel" value={j.category || ''} on:click|stopPropagation on:change={(e) => bytKategori(j, e.target.value)}>
                      <option value="">Okategoriserat</option>
                      {#each KATEGORIER as k}<option value={k}>{k}</option>{/each}
                    </select>
                    <span class="spacer"></span>
                    {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                    <button class="mini" on:click|stopPropagation={() => oppnaRedigering(j)}>Ändra</button>
                    <button class="mini" class:armerad={$armerad === `fj-${j.id}`}
                      title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                      on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>{$armerad === `fj-${j.id}` ? 'Säker?' : 'Ta bort'}</button>
                    {#if synkFelId === j.id}<div class="synkfel">⚠ {synkFelMsg}</div>{/if}
                  </div>
                {:else}
                  <div class="rad" role="button" tabindex="0" class:idag={arIdag(j)} class:forfluten={arForfluten(j)} data-jobdate={dateKey(j.start_at)} data-idag={arIdag(j)} style="border-left-color:{katFarg(j.category)}"
                    on:click={() => oppnaRedigering(j)} on:keydown={(e) => e.key === 'Enter' && oppnaRedigering(j)}>
                    <Hornmarkor farg={synkFarg(jobbSynkStatus(j))} r={12} titel={synkText(j)} />
                    <div class="datum scd">
                      <div class="d" style="color:{katFarg(j.category)}">{del(j.start_at)[2] || '–'}</div>
                      <div class="wd">{veckodag(j.start_at)}</div>
                    </div>
                    <div class="mitt">
                      <div class="rtitel stor">{#if gren}<span class="grenlbl3 scd" style="color:{grenFarg(gren)}">{GREN_ETIKETT[gren]}</span>{/if}{j.title}{#if arIdag(j)}<span class="idagbricka">Idag</span>{/if}</div>
                      <div class="when">{klocka(j.start_at)}{j.end_at ? '–' + klocka(j.end_at) : ''}{j.location ? ' · ' + j.location : ''}</div>
                      <div class="undermeta">
                        <select class="katsel" value={j.category || ''} on:click|stopPropagation on:change={(e) => bytKategori(j, e.target.value)}>
                          <option value="">Okategoriserat</option>
                          {#each KATEGORIER as k}<option value={k}>{k}</option>{/each}
                        </select>
                        {#if synkFelId === j.id}<span class="synkfel">⚠ {synkFelMsg}</span>{/if}
                      </div>
                    </div>
                    <div class="rknapp">
                      {#if j.utkast}<button class="mini synkbtn" on:click|stopPropagation={() => aktiveraSynk(j)}>Aktivera synk ›</button>{/if}
                      <button class="mini" on:click|stopPropagation={() => oppnaRedigering(j)}>Ändra</button>
                      <button class="mini" class:armerad={$armerad === `fj-${j.id}`}
                        title={$armerad === `fj-${j.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                        on:click|stopPropagation={taBortKlick(`fj-${j.id}`, () => taBort(j))}>{$armerad === `fj-${j.id}` ? 'Säker?' : 'Ta bort'}</button>
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
        <label class="full">Anteckning<textarea bind:value={modal.description} rows="2" placeholder="Kund, paket, övrigt…"></textarea></label>
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
  .rad.idag { border-color: var(--acc); box-shadow: 0 0 0 2px var(--acc-soft), var(--skugga); }
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
  .undermeta { display: flex; gap: 8px; margin-top: 8px; align-items: center; flex-wrap: wrap; }
  .rknapp { display: flex; gap: 6px; flex: none; }
  .mini { border: 1px solid var(--div); background: var(--kort); border-radius: 7px; padding: 6px 12px;
    font-size: 12.5px; color: var(--t-mut); }
  .mini:hover { border-color: var(--acc); color: var(--acc); }
  /* Beväpnad tvåstegsknapp: rött varningsläge, andra klicket raderar. */
  .mini.armerad, .mini.armerad:hover { background: #C0453E; border-color: #C0453E; color: #fff; font-weight: 600; }
  .mini.kryss.armerad { width: auto; padding: 6px 10px; font-size: 11.5px; }

  .rad.heldag { padding: 11px 16px; flex-wrap: wrap; }
  .hrange { font-size: 12px; font-weight: 700; letter-spacing: 0.03em; white-space: nowrap; flex: none; }
  .hlbl { font-size: 10px; font-weight: 600; color: var(--t-mut); text-transform: uppercase; letter-spacing: 0.07em; flex: none; }
  .spacer { flex: 1; }
  .rad.heldag .rtitel { flex: none; }
  .rad.heldag .synkfel { flex-basis: 100%; }

  /* A2: den stora synk-etiketten ersatt av <Hornmarkor> (hörnbåge, färgen bär signalen). */
  .katsel { padding: 4px 8px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 11.5px; font-family: inherit; }
  .synkbtn { border-color: var(--acc); color: var(--acc); font-weight: 600; }
  .synkfel { font-size: 11px; color: var(--rose); }

  /* Tidslinje */
  .tidslinje { display: flex; flex-direction: column; }
  .tlrad { display: grid; grid-template-columns: 56px 1fr; gap: 14px; }
  .tltid { text-align: right; padding-top: 14px; }
  .tlt { font-size: 13px; font-weight: 700; color: var(--t-head); font-variant-numeric: tabular-nums; }
  .tld { font-size: 10px; color: var(--t-mut); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
  .tlspar { position: relative; border-left: 2px solid var(--div); padding: 0 0 12px 22px; }
  .tldot { position: absolute; left: -6px; top: 20px; width: 10px; height: 10px; border-radius: 50%;
    border: 2px solid var(--kort); }
  .tlkort { background: var(--kort); border: 1px solid var(--div); border-radius: 10px; box-shadow: var(--skugga);
    padding: 11px 13px; display: flex; align-items: center; gap: 11px; cursor: pointer; }
  .tlkort:hover { background: var(--div3); }
  .tlinfo { flex: 1; min-width: 0; }
  .mini.kryss { width: 28px; padding: 6px 0; text-align: center; font-size: 15px; line-height: 1; }

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
  input, textarea, .katsel { font-family: inherit; }
  .dbody input, .dbody textarea, .dbody select { padding: 9px 11px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; outline: none; }
  .dbody input:focus, .dbody textarea:focus, .dbody select:focus { border-color: var(--acc); }

  /* Redigeringskort — utfällt direkt under raden (Fotojobb: Lista + Tidslinje) */
  .redigerakort { display: flex; flex-direction: column; gap: 10px; margin-top: 10px;
    border: 1.5px solid var(--acc-border); border-radius: 10px; padding: 12px; background: var(--kort); }
  .redigerakort input { padding: 9px 11px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; outline: none; }
  .redigerakort input:focus { border-color: var(--acc); }
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
