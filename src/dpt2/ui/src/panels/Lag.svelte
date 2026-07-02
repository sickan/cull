<script>
  import { onMount } from 'svelte'
  import {
    listaLag, listaTavlingar, sparaLag, sparaTavling, raderaLag, raderaTavling,
    valjFil, lasLagTrupp, hamtaLagTrupp, sparaSpelare, raderaSpelare,
    laggTavlingIKalender, taBortTavlingUrKalender, kopplaLagTavling,
  } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'

  let lag = []
  let tavlingar = []
  let laddar = true
  let sparad = null

  const SPORTER = ['fotboll', 'handboll', 'volleyboll', 'beachvolley', 'tennis']
  const SPORT_ETIKETT = {
    fotboll: 'Fotboll', handboll: 'Handboll', volleyboll: 'Volleyboll',
    beachvolley: 'Beachvolley', tennis: 'Tennis',
  }
  const TYPER = ['liga', 'turnering', 'masterskap']
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }
  const GRENAR = ['dam', 'herr', 'mixed']
  const GREN_ETIKETT = { dam: 'Dam', herr: 'Herr', mixed: 'Mixed' }

  onMount(async () => {
    ;[lag, tavlingar] = await Promise.all([listaLag(), listaTavlingar()])
    laddar = false
  })

  function initial(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }
  function flash(id) {
    sparad = id
    setTimeout(() => (sparad = sparad === id ? null : sparad), 1400)
  }

  async function gerLag(l) {
    // Skicka id för befintliga rader — annars kan ett namnbyte aldrig uttryckas
    // (namn-slugen pekar då ut en annan post). Nya rader ('nytt-…') saknar id.
    const arNy = String(l.id).startsWith('nytt-')
    const res = await sparaLag({ ...l, id: arNy ? null : l.id })
    if (!res?.ok) return
    if (res.id && res.id !== l.id) {
      const gammalt = l.id
      l.id = res.id
      if (oppen === gammalt) oppen = res.id
      if (rosterOppen === gammalt) rosterOppen = res.id
      if (truppOppen === gammalt) truppOppen = res.id
      lag = lag
    }
    flash(l.id)
  }
  async function gerTavling(t) {
    const res = await sparaTavling(t)
    if (res?.ok) flash(t.id)
  }

  function sattKind(l, kind) {
    if (l.kind === kind) return
    l.kind = kind
    if (kind === 'individ' && l.gren === 'mixed') l.gren = null  // mixed bara team
    lag = lag                     // trigga re-render av villkorsfälten
    gerLag(l)
  }
  function sattGren(l, gren) {
    if (l.gren === gren) return
    l.gren = gren
    lag = lag
    gerLag(l)
  }

  // ── Kompakt lista + utfälld editor ("Ändra" / "Stäng") ────────────────────
  let oppen = null               // lag-id vars editor är utfälld

  function metaRad(l) {
    return [
      SPORT_ETIKETT[l.sport], GREN_ETIKETT[l.gren],
      l.kind === 'individ' ? 'Individ' : 'Lag',
      l.trupp_n ? `${l.trupp_n} spelare` : null,
    ].filter(Boolean).join(' · ')
  }
  function tavlingNamn(tid) {
    return tavlingar.find((t) => t.id === tid)?.namn || tid
  }
  function kopplingsText(l) {
    const namn = (l.comps || []).map(tavlingNamn)
    return namn.length ? namn.join(' · ') : ''
  }

  // ── Tävlingskoppling (chips, many-to-many via tavling_lag) ────────────────
  async function kopplaTill(l, tavlingId) {
    if (!tavlingId || (l.comps || []).includes(tavlingId)) return
    l.comps = [...(l.comps || []), tavlingId]
    lag = lag
    await kopplaLagTavling(l.id, tavlingId, true)
  }
  async function kopplaBort(l, tavlingId) {
    l.comps = (l.comps || []).filter((x) => x !== tavlingId)
    lag = lag
    await kopplaLagTavling(l.id, tavlingId, false)
  }

  async function valjLoggaLag(l) {
    const f = await valjFil('Välj logga/porträtt (bild)', ['Bilder (*.png;*.jpg;*.jpeg;*.webp)'])
    if (f.ok) { l.logga = f.path; lag = lag; gerLag(l) }
  }
  async function valjLoggaTavling(t) {
    const f = await valjFil('Välj tävlingslogga (bild)', ['*.png', '*.jpg', '*.jpeg', '*.webp'])
    if (f.ok) { t.logga = f.path; tavlingar = tavlingar; gerTavling(t) }
  }
  const bildUrl = (p) => (p ? (/^https?:|^file:/.test(p) ? p : 'file://' + p) : '')

  function nyttLag() {
    const id = 'nytt-' + Date.now()
    lag = [...lag, { id, namn: '', kind: 'team', sport: 'fotboll', gren: 'dam',
      instagram: '', hemsida: '', logga: null, stall_hemma: '#2f7cb0',
      stall_borta: '#ffffff', stall_tredje: '#16181c', profilfarg: '#2f7cb0',
      klubb: '', comps: [] }]
    oppen = id
  }
  function nyTavling() {
    tavlingar = [...tavlingar, { id: 'ny-' + Date.now(), namn: '', typ: 'liga',
      sport: 'fotboll', gren: 'dam', fran: '', till: '', ort: '', arena: '',
      hemsida: '', logga: null, kalender: 0 }]
  }

  // Tävling → fotojobb-utkast (Okategoriserat, ej synkat). Aktiveras/kategoriseras
  // sedan i Fotojobb-panelen — knappen här bara SKAPAR utkastet lokalt.
  let kalFelId = null
  let kalFelMsg = ''
  async function vaxlaTavlingKalender(t) {
    kalFelId = null
    if (t.kalender) {
      t.kalender = 0
      tavlingar = tavlingar
      await taBortTavlingUrKalender(t.id)
      return
    }
    const r = await laggTavlingIKalender(t.id)
    if (r?.ok) { t.kalender = 1; tavlingar = tavlingar }
    else { kalFelId = t.id; kalFelMsg = r?.fel || 'Kunde inte lägga till i kalendern.' }
  }

  // ── Trupp-källväljare (URL / CSV / bild / PDF) ─────────────────────────────
  let truppOppen = null          // lag-id vars källväljare är utfälld
  let truppLaddar = null         // lag-id som just läses in (spinner-läge)
  let truppUrl = ''              // URL-fältet (förifylls med lagets hemsida)
  let truppFel = ''

  function togglaTrupp(l) {
    if (truppOppen === l.id) { truppOppen = null; return }
    truppOppen = l.id
    truppUrl = l.hemsida || ''
    truppFel = ''
  }

  async function lasTrupp(l, kalla) {
    let arg = ''
    if (kalla === 'url') {
      arg = (truppUrl || '').trim()
    } else {
      const filter = { csv: ['CSV (*.csv)'], bild: ['Bilder (*.jpg;*.jpeg;*.png;*.heic;*.heif)'],
        pdf: ['PDF (*.pdf)'] }[kalla]
      const f = await valjFil('Välj spelarlista', filter)
      if (!f.ok) { if (f?.fel) truppFel = f.fel; return }
      arg = f.path
    }
    truppLaddar = l.id; truppFel = ''
    const r = await lasLagTrupp(l.id, kalla, arg)
    truppLaddar = null
    if (r?.ok) {
      l.trupp_n = r.antal; l.trupp_kalla = r.trupp_kalla; l.roster = r.roster || []
      lag = lag; truppOppen = null
      rosterOppen = l.id           // öppna direkt för granskning/rättning
      flash(l.id)
    } else {
      truppFel = r?.fel || 'Kunde inte läsa in truppen.'
    }
  }

  function truppEtikett(l) {
    if (!l.trupp_n) return 'ingen trupp inläst'
    return `${l.trupp_n} spelare i trupp${l.trupp_kalla ? ' · ' + l.trupp_kalla : ''}`
  }

  // ── Visa & redigera trupp ────────────────────────────────────────────────
  let rosterOppen = null         // lag-id vars redigerbara trupplista är utfälld

  async function togglaRoster(l) {
    if (rosterOppen === l.id) { rosterOppen = null; return }
    if (!l.roster) { l.roster = await hamtaLagTrupp(l.id); lag = lag }
    rosterOppen = l.id
  }
  function laggTillSpelare(l) {
    l.roster = [...(l.roster || []), { id: null, nr: '', namn: '', position: '' }]
    l.trupp_n = l.roster.length
    lag = lag
  }
  async function sparaSpelareRad(l, p) {
    if (!(p.namn || '').trim()) return       // tomma rader sparas inte förrän namngivna
    const r = await sparaSpelare(l.id, { id: p.id, nr: p.nr, namn: p.namn, position: p.position })
    if (r?.ok) { p.id = r.id; l.trupp_n = l.roster.length; l.roster = l.roster; lag = lag }
  }
  async function taBortSpelareRad(l, p) {
    l.roster = l.roster.filter((x) => x !== p)
    l.trupp_n = l.roster.length
    lag = lag
    if (p.id) await raderaSpelare(p.id)
  }

  async function taBortLag(l) {
    lag = lag.filter((x) => x !== l)
    if (!String(l.id).startsWith('nytt-')) await raderaLag(l.id)
  }
  async function taBortTavling(t) {
    tavlingar = tavlingar.filter((x) => x !== t)
    if (!String(t.id).startsWith('ny-')) await raderaTavling(t.id)
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Lag &amp; tävlingar</h1>
    <span class="sub">Registret som matcherna delar — loggor, Instagram och ställ</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar register…</p>
  {:else}
    <section>
      <div class="caps">Tävlingar</div>
      <div class="lista">
        {#each tavlingar as t (t.id)}
          <div class="kort">
            <button class="logo scd" on:click={() => valjLoggaTavling(t)} title="Välj logga">
              {#if t.logga}<img src={bildUrl(t.logga)} alt="" />{:else}{initial(t.namn)}{/if}
            </button>
            <div class="falt">
              <input class="namn-in scd" bind:value={t.namn} on:change={() => gerTavling(t)} placeholder="Tävlingens namn" />
              <div class="trippel">
                <select bind:value={t.typ} on:change={() => gerTavling(t)}>
                  {#each TYPER as ty}<option value={ty}>{TYP_ETIKETT[ty]}</option>{/each}
                </select>
                <select bind:value={t.sport} on:change={() => gerTavling(t)}>
                  {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                </select>
                <select bind:value={t.gren} on:change={() => gerTavling(t)}>
                  <option value={null}>Gren…</option>
                  {#each GRENAR as g}<option value={g}>{GREN_ETIKETT[g]}</option>{/each}
                </select>
              </div>
              <div class="dubbel">
                <label class="datumf"><span class="lbl">Start</span><input type="date" bind:value={t.fran} on:change={() => gerTavling(t)} /></label>
                <label class="datumf"><span class="lbl">Slut</span><input type="date" bind:value={t.till} on:change={() => gerTavling(t)} /></label>
              </div>
              <div class="dubbel">
                <input bind:value={t.ort} on:change={() => gerTavling(t)} placeholder="Ort" />
                <input bind:value={t.arena} on:change={() => gerTavling(t)} placeholder="Arena" />
              </div>
              <input bind:value={t.hemsida} on:change={() => gerTavling(t)} placeholder="Hemsida" />
              <div class="kalfot">
                <span class="kalik">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                </span>
                <span class="kaltxt">Läggs som ett Okategoriserat utkast i Fotojobb — du kategoriserar och aktiverar synk dit</span>
                <button class="kalbtn" class:i={t.kalender} on:click={() => vaxlaTavlingKalender(t)}>
                  {t.kalender ? 'Utkast i Fotojobb ✓' : 'Lägg i Google Calendar ›'}
                </button>
              </div>
              {#if kalFelId === t.id}<div class="kalfel">⚠ {kalFelMsg}</div>{/if}
            </div>
            {#if sparad === t.id}<span class="flash">✓</span>{/if}
            <button class="x" class:armerad={$armerad === `tavling-${t.id}`}
              title={$armerad === `tavling-${t.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
              on:click={taBortKlick(`tavling-${t.id}`, () => taBortTavling(t))}>{$armerad === `tavling-${t.id}` ? 'Ta bort?' : '×'}</button>
          </div>
        {/each}
      </div>
      <button class="ny" on:click={nyTavling}>+ Ny tävling</button>
    </section>

    <section>
      <div class="caps">Lag &amp; utövare</div>
      <div class="lista">
        {#each lag as l (l.id)}
          <div class="kort" class:utfalld={oppen === l.id}>
            <button class="logo scd" class:rund={l.kind === 'individ'} on:click={() => valjLoggaLag(l)} title="Välj logga/porträtt">
              {#if l.logga}<img src={bildUrl(l.logga)} alt="" />{:else}{initial(l.namn)}{/if}
            </button>
            {#if oppen !== l.id}
              <div class="kompakt">
                <div class="knamn scd">
                  {#if l.stall_hemma || l.profilfarg}<span class="prick" style="background:{l.kind === 'individ' ? l.profilfarg : l.stall_hemma}"></span>{/if}
                  {l.namn || 'Namnlöst lag'}
                </div>
                <div class="kmeta">{metaRad(l) || 'Ofullständig post'}</div>
                {#if kopplingsText(l)}<div class="kmeta koppl">{kopplingsText(l)}</div>{/if}
              </div>
              <button class="andra" on:click={() => (oppen = l.id)}>Ändra</button>
            {:else}
            <div class="falt">
              <div class="rad1">
                <div class="seg">
                  <button class:on={l.kind !== 'individ'} on:click={() => sattKind(l, 'team')}>Lag</button>
                  <button class:on={l.kind === 'individ'} on:click={() => sattKind(l, 'individ')}>Individ</button>
                </div>
                <input class="namn-in scd" bind:value={l.namn} on:change={() => gerLag(l)}
                  placeholder={l.kind === 'individ' ? 'Namn' : 'Lagnamn'} />
                <div class="seg">
                  {#each GRENAR as g}
                    {#if g !== 'mixed' || l.kind !== 'individ'}
                      <button class:on={l.gren === g} on:click={() => sattGren(l, g)}>{GREN_ETIKETT[g]}</button>
                    {/if}
                  {/each}
                </div>
              </div>
              <label class="sportrad">
                <span class="lbl">Sport</span>
                <select bind:value={l.sport} on:change={() => gerLag(l)}>
                  <option value={null}>Välj sport…</option>
                  {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                </select>
              </label>
              <div class="dubbel">
                <input bind:value={l.hemsida} on:change={() => gerLag(l)} placeholder="Hemsida" />
                <input bind:value={l.instagram} on:change={() => gerLag(l)} placeholder="@instagram" />
              </div>

              {#if l.kind === 'individ'}
                <div class="stall">
                  <span class="lbl">Profil</span>
                  <input type="color" bind:value={l.profilfarg} on:change={() => gerLag(l)} title="Profilfärg" />
                  <input class="klubb" bind:value={l.klubb} on:change={() => gerLag(l)} placeholder="Klubb / land" />
                  {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                </div>
              {:else}
                <div class="stall">
                  <span class="lbl">Ställ</span>
                  <input type="color" bind:value={l.stall_hemma} on:change={() => gerLag(l)} title="Hemma" />
                  <input type="color" bind:value={l.stall_borta} on:change={() => gerLag(l)} title="Borta" />
                  <input type="color" bind:value={l.stall_tredje} on:change={() => gerLag(l)} title="Tredje" />
                  <span class="lbl mut">hemma · borta · tredje</span>
                  {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                </div>
                <div class="trupprad">
                  <button class="spelarbtn" on:click={() => togglaTrupp(l)} disabled={truppLaddar === l.id}>Läs in spelare…</button>
                  <span class="truppinfo">{truppEtikett(l)}</span>
                  {#if l.trupp_n}<button class="visaredigera" on:click={() => togglaRoster(l)}>Visa &amp; redigera ›</button>{/if}
                </div>

                {#if rosterOppen === l.id}
                  <div class="rosterbox">
                    <div class="rosterhuvud"><span class="rnr">Nr</span><span class="rnamn">Namn</span><span class="rpos">Pos</span><span class="rx"></span></div>
                    {#each l.roster || [] as p, pi (p)}
                      <div class="rosterrad">
                        <input class="rnr" bind:value={p.nr} on:change={() => sparaSpelareRad(l, p)} />
                        <input class="rnamn" bind:value={p.namn} on:change={() => sparaSpelareRad(l, p)} />
                        <input class="rpos" bind:value={p.position} on:change={() => sparaSpelareRad(l, p)} />
                        <button class="rx" class:armerad={$armerad === `sp-${l.id}-${pi}`}
                          title={$armerad === `sp-${l.id}-${pi}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
                          on:click={taBortKlick(`sp-${l.id}-${pi}`, () => taBortSpelareRad(l, p))}>{$armerad === `sp-${l.id}-${pi}` ? 'Ta bort?' : '×'}</button>
                      </div>
                    {/each}
                    <button class="rosteradd" on:click={() => laggTillSpelare(l)}>+ Lägg till spelare</button>
                  </div>
                {/if}

                {#if truppLaddar === l.id}
                  <div class="truppladdar">
                    <span class="spin"></span>
                    <div><div class="tlt">Läser in trupp…</div><div class="tls">Hämtar och tolkar laguppställningen.</div></div>
                  </div>
                {:else if truppOppen === l.id}
                  <div class="truppvaljare">
                    <div class="truppcaps">Läs in trupp från</div>
                    <div class="truppurl">
                      <input bind:value={truppUrl} placeholder="Hemsida eller URL till laguppställning…" />
                      <button class="hamta" on:click={() => lasTrupp(l, 'url')}>Hämta</button>
                    </div>
                    <div class="avdelare"><span class="linje"></span><span class="eller">eller ladda upp fil</span><span class="linje"></span></div>
                    <div class="filknappar">
                      <button on:click={() => lasTrupp(l, 'csv')}>CSV</button>
                      <button on:click={() => lasTrupp(l, 'bild')}>Bild · JPG / PNG / HEIF</button>
                      <button on:click={() => lasTrupp(l, 'pdf')}>PDF</button>
                    </div>
                    {#if truppFel}<div class="truppfel">⚠ {truppFel}</div>
                    {:else}<div class="trupphint">Sidan/filen tolkas och spelarna läggs i lagets trupp.</div>{/if}
                  </div>
                {/if}
              {/if}

              <div class="kopplbox">
                <div class="truppcaps">Kopplad till liga / tävling / mästerskap</div>
                <div class="chips">
                  {#each l.comps || [] as tid (tid)}
                    <span class="chip">{tavlingNamn(tid)}
                      <button class="chipx" title="Koppla bort" on:click={() => kopplaBort(l, tid)}>×</button>
                    </span>
                  {/each}
                  {#if (tavlingar.filter((t) => !(l.comps || []).includes(t.id))).length}
                    <select class="chipny" value="" on:change={(e) => { kopplaTill(l, e.target.value); e.target.value = '' }}>
                      <option value="" disabled>+ Koppla till…</option>
                      {#each tavlingar.filter((t) => !(l.comps || []).includes(t.id)) as t (t.id)}
                        <option value={t.id}>{t.namn}</option>
                      {/each}
                    </select>
                  {:else if !(l.comps || []).length}
                    <span class="kmeta">Inga tävlingar i registret ännu.</span>
                  {/if}
                </div>
              </div>
              <button class="stang" on:click={() => (oppen = null)}>Stäng</button>
            </div>
            {/if}
            <button class="x" class:armerad={$armerad === `lag-${l.id}`}
              title={$armerad === `lag-${l.id}` ? 'Klicka igen för att ta bort' : 'Ta bort'}
              on:click={taBortKlick(`lag-${l.id}`, () => taBortLag(l))}>{$armerad === `lag-${l.id}` ? 'Ta bort?' : '×'}</button>
          </div>
        {/each}
      </div>
      <button class="ny" on:click={nyttLag}>+ Lägg till lag / utövare</button>
    </section>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 900px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  section { margin-top: 24px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--t-caps); margin-bottom: 10px; }
  .lista { display: flex; flex-direction: column; gap: 10px; }

  .kort { display: flex; gap: 14px; align-items: flex-start; background: var(--kort);
    border: 1px solid var(--div); border-radius: var(--r); padding: 14px;
    box-shadow: var(--skugga); position: relative; }
  .logo { width: 42px; height: 42px; flex: none; border-radius: 10px; border: 0;
    background: var(--acc-soft); color: var(--acc); display: flex; overflow: hidden;
    align-items: center; justify-content: center; font-size: 15px; font-weight: 700;
    cursor: pointer; padding: 0; }
  .logo.rund { border-radius: 50%; }
  .logo:hover { outline: 2px solid var(--acc); outline-offset: 1px; }
  .logo img { width: 100%; height: 100%; object-fit: cover; }

  .falt { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .rad1 { display: flex; gap: 8px; align-items: center; }
  .rad1 .namn-in { flex: 1; min-width: 0; }
  .dubbel { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .trippel { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }

  /* Kompakt rad (ihopfälld post): namn + "sport · gren · typ · N spelare" + koppling */
  .kompakt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px;
    padding-top: 2px; }
  .knamn { font-size: 15px; font-weight: 700; color: var(--t-head); display: flex;
    align-items: center; gap: 7px; }
  .prick { width: 9px; height: 9px; border-radius: 50%; flex: none;
    border: 1px solid var(--div); }
  .kmeta { font-size: 12px; color: var(--t-mut); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .kmeta.koppl { color: var(--t-help); font-size: 11.5px; }
  .andra { flex: none; align-self: center; border: 1px solid var(--div); border-radius: 7px;
    background: var(--kort); color: var(--acc); font-size: 12.5px; font-weight: 600;
    padding: 7px 14px; }
  .andra:hover { border-color: var(--acc); }
  .stang { align-self: flex-start; border: 1px solid var(--div); border-radius: 7px;
    background: var(--kort); color: var(--t-mut); font-size: 12.5px; font-weight: 600;
    padding: 7px 14px; margin-top: 2px; }
  .stang:hover { border-color: var(--acc); color: var(--acc); }

  /* Tävlingskoppling: chips (many-to-many, borttagbara) */
  .kopplbox { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 8px; }
  .chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 5px; background: var(--acc-soft);
    color: var(--acc); border-radius: 999px; padding: 4px 6px 4px 11px; font-size: 12px;
    font-weight: 600; }
  .chipx { border: 0; background: transparent; color: inherit; font-size: 13px;
    line-height: 1; width: 17px; height: 17px; border-radius: 50%; padding: 0; }
  .chipx:hover { background: var(--acc); color: var(--kort); }
  .chipny { border: 1.5px dashed var(--div); border-radius: 999px; background: transparent;
    color: var(--t-mut); font-size: 12px; padding: 4px 9px; max-width: 150px; }
  .chipny:hover { border-color: var(--acc); color: var(--acc); }
  .sportrad { display: flex; align-items: center; gap: 10px; }
  .sportrad select { flex: 1; min-width: 0; }
  .datumf { display: flex; flex-direction: column; gap: 4px; }
  .datumf input { width: 100%; box-sizing: border-box; }
  .kalfot { display: flex; align-items: center; gap: 10px; margin-top: 4px; padding: 10px 12px;
    background: var(--panel); border: 1px solid var(--div3); border-radius: 9px; }
  .kalik { width: 30px; height: 30px; border-radius: 8px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .kalik svg { width: 16px; height: 16px; }
  .kaltxt { flex: 1; min-width: 0; font-size: 12px; color: var(--t-mut); }
  .kalbtn { flex: none; background: var(--acc); color: #fff; border: 0; border-radius: 7px;
    padding: 8px 13px; font-size: 12.5px; font-weight: 600; }
  .kalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .kalfel { font-size: 11px; color: var(--rose); margin-top: -2px; }
  .trupprad { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .spelarbtn { background: var(--kort); border: 1px solid var(--div); border-radius: 8px;
    padding: 8px 12px; font-size: 12.5px; color: var(--t-mut); font-weight: 500; flex: none; }
  .spelarbtn:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .spelarbtn:disabled { opacity: 0.5; }
  .truppinfo { font-size: 11px; color: var(--t-mut); }
  .visaredigera { border: 0; background: none; font-size: 11.5px; color: var(--acc);
    font-weight: 600; padding: 0; flex: none; }
  .truppladdar { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 14px; display: flex; align-items: center; gap: 12px; }
  .spin { width: 22px; height: 22px; border-radius: 50%; flex: none;
    border: 3px solid var(--acc-soft); border-top-color: var(--acc); animation: lagspin 0.8s linear infinite; }
  @keyframes lagspin { to { transform: rotate(360deg); } }
  .tlt { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .tls { font-size: 11px; color: var(--t-mut); }
  .rosterbox { margin-left: 0; border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 6px; }
  .rosterhuvud { display: flex; align-items: center; gap: 8px; padding: 0 2px 2px; font-size: 9.5px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  .rosterhuvud .rnr { width: 34px; flex: none; }
  .rosterhuvud .rnamn { flex: 1; }
  .rosterhuvud .rpos { width: 52px; flex: none; }
  .rosterhuvud .rx { width: 28px; flex: none; }
  .rosterrad { display: flex; align-items: center; gap: 8px; }
  .rosterrad input.rnr { width: 34px; flex: none; text-align: center; padding: 6px 4px; font-size: 12px; background: var(--kort); }
  .rosterrad input.rnamn { flex: 1; min-width: 0; padding: 6px 9px; font-size: 12.5px; background: var(--kort); }
  .rosterrad input.rpos { width: 52px; flex: none; text-align: center; padding: 6px 6px; font-size: 12px; background: var(--kort); }
  .rosterrad button.rx { width: 28px; height: 28px; flex: none; border-radius: 6px; border: 1px solid var(--div);
    background: var(--kort); color: var(--t-mut); font-size: 15px; line-height: 1; }
  .rosterrad button.rx:hover { background: var(--rose); border-color: var(--rose); color: #fff; }
  .rosterrad button.rx.armerad { width: auto; padding: 0 10px; background: #C0453E; border-color: #C0453E;
    color: #fff; font-size: 11.5px; font-weight: 600; }
  .rosteradd { display: flex; align-items: center; justify-content: center; gap: 7px; margin-top: 2px;
    border: 1.5px dashed var(--div); border-radius: 8px; padding: 8px; color: var(--t-mut);
    font-size: 12px; background: transparent; }
  .rosteradd:hover { border-color: var(--acc); color: var(--acc); }
  .truppvaljare { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 9px; }
  .truppcaps { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  .truppurl { display: flex; gap: 6px; }
  .truppurl input { flex: 1; min-width: 0; background: var(--kort); font-size: 12px; padding: 7px 9px; }
  .hamta { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 7px 13px;
    font-size: 12px; font-weight: 600; flex: none; }
  .hamta:disabled { opacity: 0.5; }
  .avdelare { display: flex; align-items: center; gap: 8px; }
  .linje { height: 1px; flex: 1; background: var(--div3); }
  .eller { font-size: 10px; color: var(--t-help); }
  .filknappar { display: flex; gap: 6px; flex-wrap: wrap; }
  .filknappar button { background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 6px 11px; font-size: 12px; color: var(--t-head); }
  .filknappar button:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .filknappar button:disabled { opacity: 0.5; }
  .trupphint { font-size: 10px; color: var(--t-help); line-height: 1.45; }
  .truppfel { font-size: 11px; color: var(--rose); }
  input, select { padding: 7px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .namn-in { font-size: 15px; font-weight: 700; }

  .seg { display: flex; flex: none; border: 1px solid var(--div); border-radius: 8px; overflow: hidden; }
  .seg button { padding: 6px 12px; border: 0; background: var(--panel); color: var(--t-mut);
    font-size: 12px; font-weight: 600; cursor: pointer; }
  .seg button.on { background: var(--acc); color: var(--kort); }

  .stall { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .klubb { flex: 1; min-width: 120px; }
  .lbl { font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--t-caps); }
  .lbl.mut { font-weight: 500; color: var(--t-help); text-transform: none; letter-spacing: 0; }
  input[type='color'] { width: 30px; height: 28px; padding: 2px; border-radius: 7px; cursor: pointer; }
  .flash { font-size: 11.5px; font-weight: 600; color: var(--ok); align-self: center; }

  .x { width: 26px; height: 26px; flex: none; border: 1px solid var(--div);
    border-radius: 7px; background: var(--kort); color: var(--t-mut); font-size: 16px;
    line-height: 1; align-self: flex-start; }
  .x:hover { background: var(--rose); border-color: var(--rose); color: #fff; }
  /* Beväpnad tvåstegsknapp: × expanderar till rött "Ta bort?", andra klicket raderar. */
  .x.armerad { width: auto; padding: 0 10px; height: 26px; background: #C0453E; border-color: #C0453E;
    color: #fff; font-size: 11.5px; font-weight: 600; }

  .ny { margin-top: 10px; padding: 11px; width: 100%; border: 1.5px dashed var(--div);
    border-radius: var(--r); background: transparent; color: var(--t-mut);
    font-size: 13px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
</style>
