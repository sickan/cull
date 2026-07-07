<script>
  // "På gång" — kurerad aktivitetslista som driver Sport-sidans På gång-
  // sektion på webben. Varje post → content/pagang/{datum}-{slug}.md.
  // Datamodell: DATAMODELL-PAGANG.md (datum = enda datumkällan; veckodag/
  // månad härleds; passerade filtreras bort på webben; nästa kommande =
  // stort kort, 2–3 därefter = kompakt lista). Autospar per post.
  import { onMount } from 'svelte'
  import { listaAktiviteter, sparaAktivitet, raderaAktivitet,
    forhandsgranskaAktivitet, exporteraAktiviteter, publiceraAktiviteterNatet,
    listaMatcher, valjMapp, slugga } from '../lib/api.js'
  import { armerad, taBortKlick } from '../lib/bekrafta.js'
  import { testMode } from '../lib/testlage.js'

  const KATEGORIER = ['Match', 'Uppdrag', 'Utställning', 'Övrigt']
  const PGCOL = '#A0653B'                        // På gång-brun (admin-eyebrow)
  const SPORT = '#2F7CB0'                        // Sport-blå (webbens tema)
  const MAN = ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli',
    'augusti', 'september', 'oktober', 'november', 'december']
  const WD = ['Söndag', 'Måndag', 'Tisdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lördag']

  let poster = []
  let selId = ''
  let matcher = []
  let sparadTid = ''
  let filOpen = false
  let sparar = false
  let synkFel = ''
  let klarText = ''

  // idag som YYYY-MM-DD (lokal) — enda referenspunkten för kommande/passerad.
  function idagISO() {
    const d = new Date()
    const p = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  }
  const IDAG = idagISO()

  onMount(async () => {
    try {
      ;[poster, matcher] = await Promise.all([listaAktiviteter(), listaMatcher()])
    } catch (e) {
      console.error('På gång: kunde inte läsa aktiviteter/matcher', e)
    }
    if (poster.length && !poster.some((p) => p.id === selId)) {
      // Förvälj nästa kommande, annars första i listan.
      selId = (kommande[0] || poster[0]).id
    }
  })

  $: kommande = poster.filter((p) => (p.datum || '') >= IDAG)
    .sort((a, b) => ((a.datum || '') < (b.datum || '') ? -1 : 1))
  $: passerade = poster.filter((p) => (p.datum || '') < IDAG)
    .sort((a, b) => ((a.datum || '') < (b.datum || '') ? 1 : -1))
  $: vald = poster.find((p) => p.id === selId) || null

  // ── Härledda visningsvärden för vald post ────────────────────────────────
  $: dArr = String(vald?.datum || '').split('-')
  $: dObj = dArr.length === 3 ? new Date(+dArr[0], +dArr[1] - 1, +dArr[2]) : null
  $: passerad = !!vald && (vald.datum || '') < IDAG
  $: arNasta = kommande.length > 0 && vald && kommande[0].id === vald.id
  $: plac = vald ? kommande.findIndex((p) => p.id === vald.id) : -1
  $: pvVisas = !!vald?.titel && !!vald?.publicerad && !passerad
  $: aktSlug = (vald?.datum ? vald.datum + '-' : '') + (slugga(vald?.titel || '') || 'ny-aktivitet')
  $: filnamn = `content/pagang/${aktSlug}.md`
  $: pvSkal = !vald ? '' : !vald.publicerad ? 'Publicerad är avstängd.'
    : passerad ? 'Datumet har passerat — passerade aktiviteter filtreras bort automatiskt.'
    : 'Titel saknas.'
  $: pvPosition = arNasta ? 'Visas som stort ”nästa”-kort — först i sektionen.'
    : plac >= 1 && plac <= 3 ? `Visas som rad ${plac} i den kompakta listan under nästa-kortet.`
    : plac < 0 ? '' : `Plats ${plac + 1} i kön — visas när tidigare aktiviteter passerat.`

  // Kommande matcher i spelschemat (för matchväljaren i Förifyll).
  $: kommandeMatcher = matcher.filter((m) => (m.datum || '') >= IDAG)
    .sort((a, b) => ((a.datum || '') < (b.datum || '') ? -1 : 1))
  $: nastaMatch = kommandeMatcher[0]
  // Vald match att förifylla från (specifik, inte bara nästa). Faller tillbaka
  // på nästa kommande när inget valts eller valet inte längre finns.
  let valForifyllId = ''
  $: forifyllMatch = kommandeMatcher.find((m) => m.id === valForifyllId) || nastaMatch
  $: forifyllMatchTxt = forifyllMatch
    ? `${forifyllMatch.lag_hemma} – ${forifyllMatch.lag_borta}${forifyllMatch.datum ? ' · ' + forifyllMatch.datum : ''}${forifyllMatch.tid ? ' ' + forifyllMatch.tid : ''}`
    : ''

  let mdText = ''
  $: (async () => { if (vald) { const r = await forhandsgranskaAktivitet(vald); mdText = r?.md || '' } else mdText = '' })()

  function korta(m) { return (m || '').slice(0, 3).toUpperCase() }
  function metaText(p) { return [p.heldag ? 'Heldag' : p.tid, p.plats].filter(Boolean).join(' · ') }

  // ── Autospar (debounce ~500 ms) ──────────────────────────────────────────
  let sparaTimer = null
  function planeraSpar() {
    if (!vald) return
    if (sparaTimer) clearTimeout(sparaTimer)
    const snapshot = { ...vald }
    sparaTimer = setTimeout(async () => {
      sparar = true
      const r = await sparaAktivitet(snapshot)
      sparar = false
      if (r?.ok) {
        if (r.id && snapshot.id !== r.id) { snapshot.id = r.id; oppdatera(snapshot.id, {}) }
        const d = new Date(); const p = (n) => String(n).padStart(2, '0')
        sparadTid = `${p(d.getHours())}:${p(d.getMinutes())}`
      }
    }, 500)
  }

  function oppdatera(id, patch) {
    poster = poster.map((p) => (p.id === id ? { ...p, ...patch } : p))
  }
  function satt(falt, varde) {
    if (!vald) return
    oppdatera(vald.id, { [falt]: varde })
    planeraSpar()
  }

  async function nyAktivitet() {
    // Skapa direkt i backend så posten får ett riktigt id att autospara mot.
    const utkast = { kategori: 'Match', etikett: '', titel: 'Ny aktivitet',
      datum: IDAG, tid: '', plats: '', beskrivning: '', publicerad: false, heldag: false }
    const r = await sparaAktivitet(utkast)
    const id = r?.id || `tmp${Date.now()}`
    poster = [...poster, { ...utkast, id }]
    selId = id
  }

  async function taBort() {
    if (!vald) return
    const id = vald.id
    await raderaAktivitet(id)
    poster = poster.filter((p) => p.id !== id)
    selId = (kommande[0] || poster[0])?.id || ''
  }

  function forifyll() {
    const m = forifyllMatch
    if (!m || !vald) return
    oppdatera(vald.id, {
      kategori: 'Match',
      titel: `${m.lag_hemma || ''} – ${m.lag_borta || ''}`.trim(),
      datum: m.datum || '',
      tid: vald.heldag ? '' : (m.tid ? `Avspark ${m.tid}` : ''),
      plats: m.arena || '',
      etikett: m.liga || '',
    })
    planeraSpar()
  }

  async function exportera() {
    synkFel = ''; klarText = ''
    let dir = ''
    if (!$testMode) {
      const r = await valjMapp('Välj content/pagang-katalog')
      if (!r.ok) return
      dir = r.path
    }
    const r = await exporteraAktiviteter(dir, $testMode)
    if (r?.ok) klarText = $testMode
      ? `✓ Test — ${r.antal} .md-filer: ${r.path}/ · rensas vid omstart`
      : `✓ ${r.antal} .md-filer skrivna till ${r.path}/`
    else synkFel = r?.fel || 'Kunde inte exportera.'
    if (klarText) setTimeout(() => (klarText = ''), 3600)
  }

  async function publicera() {
    synkFel = ''; klarText = ''
    sparar = true
    const r = await publiceraAktiviteterNatet($testMode)
    sparar = false
    if (r?.ok) klarText = $testMode
      ? `✓ Test — ${r.antal} .md-filer skrivna · rensas vid omstart`
      : `✓ ${r.antal} aktiviteter publicerade${r.borttagna ? ` · ${r.borttagna} borttagna` : ''} till hemsidan`
    else synkFel = r?.fel || 'Kunde inte publicera — kontrollera anslutningen.'
    if (klarText) setTimeout(() => (klarText = ''), 3600)
  }
</script>

<div class="pg">
  <!-- Lista -->
  <div class="kort lista">
    <div class="listhuvud">
      <span class="caps">Aktiviteter</span>
      <button class="ny" on:click={nyAktivitet}>+ Ny aktivitet</button>
    </div>

    {#if kommande.length}
      <div class="grpcaps">Kommande · {kommande.length}</div>
      <div class="rader">
        {#each kommande as p (p.id)}
          {@const d = String(p.datum || '').split('-')}
          <button class="rad" class:on={p.id === selId} on:click={() => (selId = p.id)}>
            <div class="dagbox">
              <div class="dag scd" style={p.id === selId ? `color:${SPORT}` : ''}>{+d[2] || ''}</div>
              <div class="man">{korta(MAN[+d[1] - 1])}</div>
            </div>
            <div class="radmitt">
              <div class="radkat" style="color:{PGCOL}">{p.kategori}</div>
              <div class="radtitel scd">{p.titel || 'Namnlös'}</div>
              <div class="radmeta">{metaText(p)}</div>
            </div>
            <span class="pub" class:av={!p.publicerad}>{p.publicerad ? 'Publik' : 'Dold'}</span>
          </button>
        {/each}
      </div>
    {:else}
      <div class="tomt">Inga kommande aktiviteter. Klicka <b>+ Ny aktivitet</b>.</div>
    {/if}

    {#if passerade.length}
      <div class="grpcaps mt">Passerade · visas inte på webben</div>
      <div class="rader">
        {#each passerade as p (p.id)}
          {@const d = String(p.datum || '').split('-')}
          <button class="rad passerad" class:on={p.id === selId} on:click={() => (selId = p.id)}>
            <div class="dagbox">
              <div class="dag sm scd">{+d[2] || ''}</div>
              <div class="man">{korta(MAN[+d[1] - 1])}</div>
            </div>
            <div class="radmitt">
              <div class="radtitel scd sm">{p.titel || 'Namnlös'}</div>
              <div class="radmeta">{metaText(p)}</div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
    <p class="listfot">Nästa kommande aktivitet visas stort på webben; de 2–3 därefter i kompakt lista. Passerade poster filtreras bort automatiskt.</p>
  </div>

  <!-- Formulär -->
  <div class="kort form">
    <div class="formhuvud">
      <span class="caps nomarg">Redigera aktivitet</span>
      <span class="filnamn">{filnamn}</span>
    </div>

    {#if vald}
      <label class="flabel">Kategori</label>
      <div class="katter">
        {#each KATEGORIER as k}
          <button class="kat" class:on={vald.kategori === k}
            style={vald.kategori === k ? `background:${PGCOL};border-color:${PGCOL};color:#fff` : ''}
            on:click={() => satt('kategori', k)}>{k}</button>
        {/each}
      </div>

      {#if vald.kategori === 'Match'}
        <div class="prefill">
          <div class="prefillhuvud"><b>Förifyll från Matcher</b>
            {#if kommandeMatcher.length}
              <select class="matchval" bind:value={valForifyllId}>
                {#each kommandeMatcher as m (m.id)}
                  <option value={m.id}>{m.lag_hemma} – {m.lag_borta}{m.datum ? ` · ${m.datum}` : ''}</option>
                {/each}
              </select>
            {/if}
          </div>
          <div class="prefilltxt">{forifyllMatch
            ? `Hämtar ${forifyllMatchTxt} (lag, serie, avspark, arena).`
            : 'Ingen kommande match i spelschemat.'}</div>
          <button class="hamta" on:click={forifyll} disabled={!forifyllMatch}>Hämta →</button>
        </div>
      {/if}

      <div class="f"><label>Titel</label>
        <input value={vald.titel || ''} on:input={(e) => satt('titel', e.target.value)} /></div>
      <div class="grid3 mt">
        <div class="f"><label>Datum</label>
          <input value={vald.datum || ''} placeholder="ÅÅÅÅ-MM-DD" on:input={(e) => satt('datum', e.target.value)} /></div>
        <div class="f"><label class="tidlabel">Tid
            <button class="heldagtgl" class:pa={vald.heldag} on:click={() => satt('heldag', !vald.heldag)}>
              <span class="htrack" class:pa={vald.heldag}><span class="hknob"></span></span>Heldag</button></label>
          {#if vald.heldag}
            <div class="heldagtxt">Heldag — ingen specifik tid</div>
          {:else}
            <input value={vald.tid || ''} placeholder="t.ex. Avspark 16:00" on:input={(e) => satt('tid', e.target.value)} />
          {/if}</div>
        <div class="f"><label>Plats</label>
          <input value={vald.plats || ''} on:input={(e) => satt('plats', e.target.value)} /></div>
      </div>
      <div class="f mt"><label>Etikett</label>
        <input value={vald.etikett || ''} on:input={(e) => satt('etikett', e.target.value)} />
        <div class="hint">Liten rad ovanför titeln på webben, t.ex. ”Damallsvenskan · omgång 12” eller ”Utställning”.</div></div>
      <div class="f mt"><label>Beskrivning</label>
        <textarea rows="4" value={vald.beskrivning || ''} on:input={(e) => satt('beskrivning', e.target.value)}></textarea>
        <div class="hint">Valfri — visas bara i det stora ”nästa”-kortet på webben, inte i den kompakta listan.</div></div>

      <div class="formfot">
        <button class="toggle" on:click={() => satt('publicerad', !vald.publicerad)}>
          <span class="track" class:pa={vald.publicerad}><span class="knob"></span></span>
          <span class="tlabel">Publicerad</span>
          <span class="thint">{vald.publicerad ? 'Syns i ”På gång” på webbplatsen' : 'Sparad men dold'}</span>
        </button>
        <button class="delbtn" class:armerad={$armerad === 'akt-del'}
          on:click={taBortKlick('akt-del', taBort)}>{$armerad === 'akt-del' ? 'Ta bort?' : 'Ta bort aktivitet'}</button>
      </div>
    {:else}
      <div class="tomt">Välj en aktivitet i listan, eller skapa en ny.</div>
    {/if}
  </div>

  <!-- Webbförhandsvisning -->
  <div class="kort preview">
    <div class="pvhuvud">
      <span class="caps nomarg">Så visas den på webben · Sport → På gång</span>
      {#if sparadTid}<span class="sparad">✓ Sparas löpande · {sparadTid}</span>{/if}
    </div>

    {#if pvVisas && vald}
      <div class="webbram">
        <div class="webbbar">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          <div class="urlbar">dalecarliaphoto.se/sport <span style="color:{SPORT}">#pa-gang</span></div>
        </div>
        <div class="webbkropp">
          <div class="pgrubrik scd">På gång</div>
          <div class="pgkort">
            <div class="pgdatum" style="border-color:color-mix(in srgb, {SPORT} 12%, transparent)">
              <div class="pgwd">{dObj ? WD[dObj.getDay()] : ''}</div>
              <div class="pgdag scd" style="color:{SPORT}">{dArr[2] ? +dArr[2] : ''}</div>
              <div class="pgman">{(MAN[+dArr[1] - 1] || '').toUpperCase()}</div>
            </div>
            <div class="pgtxt">
              <div class="pgeti" style="color:{SPORT}">{vald.etikett || ''}</div>
              <div class="pgtitel scd">{vald.titel}</div>
              <div class="pgmeta"><span class="pgtid">{vald.heldag ? 'Heldag' : (vald.tid || '')}</span><span class="pgplats">{vald.plats || ''}</span></div>
              {#if vald.beskrivning && arNasta}<p class="pgbesk">{vald.beskrivning}</p>{/if}
            </div>
          </div>
        </div>
      </div>
      <div class="pvpos" style="color:{SPORT}"><span class="posdot" style="background:{SPORT}"></span>{pvPosition}</div>
    {:else}
      <div class="doldruta">
        <div class="doldtitel scd">Visas inte på webben</div>
        <div class="doldskal">{pvSkal}</div>
      </div>
    {/if}

    <div class="pvinfo">Finns inga kommande publicerade aktiviteter döljs hela sektionen på webbplatsen.</div>
    <button class="fillank" on:click={() => (filOpen = !filOpen)} style="color:{SPORT}">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={SPORT} stroke-width="1.9"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
      {filOpen ? 'Dölj .md-filen' : 'Visa .md-fil som synkas'}
    </button>
    {#if filOpen}
      <div class="mdruta">
        <div class="mdfil">{filnamn}</div>
        <div class="mdinnehall">{mdText}</div>
      </div>
    {/if}

    <div class="synka">
      <button class="prim" on:click={publicera} disabled={sparar}>{sparar ? 'Publicerar…' : 'Publicera till hemsidan'}</button>
      <button class="sek" on:click={exportera}>Exportera .md-filer…</button>
      {#if klarText}<span class="ok" class:testhint={$testMode}>{klarText}</span>{/if}
      {#if synkFel}<span class="synkfel">{synkFel}</span>{/if}
    </div>
  </div>
</div>

<style>
  .pg { display: grid; grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
    grid-template-rows: auto auto; gap: 14px; margin-top: 14px; align-items: start; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: 12px;
    box-shadow: var(--skugga); padding: 16px; }
  .lista { grid-column: 1; grid-row: 1; }
  .form { grid-column: 2; grid-row: 1 / 3; }
  .preview { grid-column: 1; grid-row: 2; }
  @media (max-width: 720px) {
    .pg { grid-template-columns: 1fr; }
    .lista, .form, .preview { grid-column: 1; grid-row: auto; }
  }

  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--t-caps); margin-bottom: 12px; }
  .caps.nomarg { margin-bottom: 0; }

  /* Lista */
  .listhuvud { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .ny { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 6px 12px;
    font-size: 12px; font-weight: 600; }
  .grpcaps { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;
    color: var(--t-caps); padding: 2px 2px 6px; }
  .grpcaps.mt { padding-top: 14px; }
  .rader { display: flex; flex-direction: column; gap: 6px; }
  .rad { display: grid; grid-template-columns: 42px 1fr auto; gap: 10px; align-items: center;
    padding: 10px; border-radius: 9px; border: 1px solid var(--div3); background: transparent;
    text-align: left; width: 100%; }
  .rad.on { border-color: var(--acc); background: var(--kort); }
  .rad.passerad { grid-template-columns: 42px 1fr; opacity: 0.55; }
  .dagbox { text-align: center; }
  .dag { font-weight: 700; font-size: 21px; line-height: 1; color: var(--t-head); }
  .dag.sm { font-size: 18px; }
  .man { font-size: 9px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--t-mut); margin-top: 2px; }
  .radmitt { min-width: 0; }
  .radkat { font-size: 9.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
  .radtitel { font-weight: 700; font-size: 15px; line-height: 1.1; color: var(--t-head); margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .radtitel.sm { font-size: 14px; }
  .radmeta { font-size: 11px; color: var(--t-mut); margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pub { font-size: 9px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 999px; background: color-mix(in srgb, var(--acc) 14%, transparent);
    color: var(--acc); white-space: nowrap; }
  .pub.av { background: var(--div3); color: var(--t-mut); }
  .tomt { font-size: 12.5px; color: var(--t-mut); padding: 10px 2px; line-height: 1.5; }
  .listfot { margin: 14px 2px 0; font-size: 11px; line-height: 1.55; color: var(--t-help); }

  /* Formulär */
  .formhuvud { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .filnamn { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--t-mut);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; text-align: right; }
  .flabel { display: block; font-size: 11px; color: var(--t-mut); margin-bottom: 6px; }
  .katter { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 14px; }
  .kat { font-size: 11.5px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
    padding: 7px 15px; border-radius: 999px; border: 1px solid var(--div); color: var(--t-head);
    background: var(--panel); }
  .prefill { display: flex; align-items: center; justify-content: space-between; gap: 10px 14px; flex-wrap: wrap;
    border: 1px dashed var(--acc-border); background: var(--acc-soft); border-radius: 9px;
    padding: 10px 13px; margin-bottom: 14px; }
  .prefillhuvud { flex-basis: 100%; display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--t-head); }
  .prefillhuvud b { font-weight: 600; }
  .matchval { font-size: 12px; color: var(--t-head); background: var(--kort); border: 1px solid var(--div);
    border-radius: 7px; padding: 4px 8px; max-width: 260px; }
  .prefilltxt { flex: 1; min-width: 0; font-size: 12px; color: var(--t-mut); line-height: 1.45; }
  .prefilltxt b { font-weight: 600; }
  .hamta { flex: none; background: var(--kort); border: 1px solid var(--acc); color: var(--acc);
    border-radius: 7px; padding: 7px 13px; font-size: 12px; font-weight: 600; }
  .hamta:disabled { opacity: 0.5; }
  .tidlabel { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .heldagtgl { display: inline-flex; align-items: center; gap: 6px; background: none; border: 0; padding: 0;
    font-size: 11px; color: var(--t-mut); cursor: pointer; }
  .heldagtgl.pa { color: var(--acc); }
  .htrack { position: relative; display: inline-block; flex: none; width: 30px; height: 17px;
    background: var(--div); border-radius: 999px; transition: background 0.12s; }
  .htrack.pa { background: var(--acc); }
  .hknob { position: absolute; top: 2px; left: 2px; width: 13px; height: 13px; border-radius: 50%;
    background: #fff; transition: left 0.12s; box-shadow: 0 1px 2px rgba(0,0,0,.25); }
  .htrack.pa .hknob { left: 15px; }
  .heldagtxt { font-size: 12px; color: var(--t-mut); padding: 8px 2px; font-style: italic; }
  .f { display: flex; flex-direction: column; gap: 5px; }
  .grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }
  .mt { margin-top: 12px; }
  label { font-size: 11px; color: var(--t-mut); }
  input, textarea { font-family: inherit; width: 100%; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 9px 11px; font-size: 13px; color: var(--t-head); outline: none; }
  input:focus, textarea:focus { border-color: var(--acc); }
  textarea { line-height: 1.55; resize: vertical; }
  .hint { font-size: 10.5px; color: var(--t-help); margin-top: 4px; line-height: 1.45; }

  .formfot { display: flex; align-items: center; justify-content: space-between; gap: 10px;
    margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--div3); }
  .toggle { display: flex; align-items: center; gap: 10px; background: none; border: 0; padding: 0; }
  .track { position: relative; display: inline-block; flex: none; width: 40px; height: 22px;
    border-radius: 999px; background: var(--div); transition: background 0.2s; }
  .track.pa { background: var(--acc); }
  .knob { position: absolute; top: 2.5px; left: 2.5px; width: 17px; height: 17px; border-radius: 50%;
    background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.25); transition: left 0.2s; }
  .track.pa .knob { left: 20.5px; }
  .tlabel { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .thint { font-size: 11.5px; color: var(--t-mut); }
  .delbtn { background: none; border: 0; font-size: 12px; font-weight: 600; color: #B0452F; }
  .delbtn.armerad { background: #C0453E; color: #fff; border-radius: 7px; padding: 5px 10px; }

  /* Preview */
  .pvhuvud { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 11px; }
  .sparad { font-size: 10.5px; color: var(--ok); font-weight: 600; flex: none; }
  .webbram { width: 100%; border: 1px solid var(--div); border-radius: 10px; overflow: hidden;
    box-shadow: 0 6px 18px rgba(60,50,30,.1); }
  .webbbar { background: var(--panel); padding: 8px 12px; display: flex; align-items: center; gap: 7px;
    border-bottom: 1px solid var(--div); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: rgba(120,110,90,.28); }
  .urlbar { flex: 1; background: var(--kort); border-radius: 5px; padding: 3px 10px;
    font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: var(--t-mut); margin-left: 6px; }
  .webbkropp { background: #fff; padding: 16px 16px 18px; }
  .pgrubrik { font-size: 13px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
    color: rgba(35,32,26,.45); margin-bottom: 11px; }
  .pgkort { display: flex; gap: 14px; }
  .pgdatum { flex: none; text-align: center; padding-right: 14px; border-right: 2px solid rgba(47,124,176,.12); }
  .pgwd { font-size: 9px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: rgba(35,32,26,.5); }
  .pgdag { font-weight: 700; font-size: 44px; line-height: 0.85; }
  .pgman { font-size: 10px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: #23201a; }
  .pgtxt { flex: 1; min-width: 0; }
  .pgeti { font-size: 9.5px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; }
  .pgtitel { font-weight: 700; font-size: 22px; line-height: 1.05; color: #23201a; margin-top: 4px; }
  .pgmeta { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 7px; }
  .pgtid { font-size: 11px; font-weight: 600; color: #3a352c; }
  .pgplats { font-size: 11px; color: rgba(35,32,26,.55); }
  .pgbesk { font-size: 11.5px; line-height: 1.6; color: #3a352c; margin: 9px 0 0; }
  .pvpos { display: flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 600; margin-top: 12px; }
  .posdot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
  .doldruta { width: 100%; border: 1px dashed var(--div); border-radius: 10px; padding: 22px 18px; text-align: center; }
  .doldtitel { font-weight: 700; font-size: 16px; color: var(--t-head); }
  .doldskal { font-size: 11.5px; color: var(--t-mut); margin-top: 4px; }
  .pvinfo { font-size: 11px; line-height: 1.55; color: var(--t-help); margin-top: 12px; }
  .fillank { display: inline-flex; align-items: center; gap: 6px; background: none; border: 0; padding: 0;
    font-size: 11px; font-weight: 600; margin-top: 9px; }
  .mdruta { background: #23201a; border-radius: 9px; padding: 12px 14px; margin-top: 8px; }
  .mdfil { font-family: var(--mono, ui-monospace, monospace); font-size: 10px; color: #8FD0E8;
    margin-bottom: 8px; word-break: break-all; }
  .mdinnehall { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; line-height: 1.6;
    color: rgba(255,255,255,.85); white-space: pre-wrap; word-break: break-word; }
  .synka { display: flex; align-items: center; gap: 12px; margin-top: 16px; padding-top: 14px;
    border-top: 1px solid var(--div3); flex-wrap: wrap; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 16px;
    font-size: 13px; font-weight: 600; flex: none; }
  .prim:disabled { opacity: 0.5; }
  .sek { background: var(--panel); border: 1px solid var(--div); border-radius: 7px; padding: 9px 14px;
    font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .ok.testhint { color: var(--varn); }
  .synkfel { font-size: 12.5px; color: #C0453E; font-weight: 600; }
</style>
