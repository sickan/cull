<script>
  // Delad resultat-remsa (scoreboard) — Publicera (Live+SoMe) och Innehåll→
  // Sport. Skriver direkt på matchposten (resultat/mellan/malskyttar), en
  // källa som Live-mallen, SoMe-brickorna och Webb-fälten alla speglar.
  // Design: design_handoff_live_some_webb/Bildval & Resultat-remsa -
  // varianter.dc.html, variant 1e. Ingen egen "Byt match"-knapp — sitter
  // alltid direkt under AktivMatchRad/matchväljaren, som redan har den.
  import { createEventDispatcher } from 'svelte'
  import { sattResultat } from './api.js'
  import Lagbricka from './Lagbricka.svelte'
  import { grenFarg } from './gren.js'

  const dispatch = createEventDispatcher()

  export let match = null       // {id, lag_hemma, lag_borta, liga, resultat, mellan, malskyttar, ...}
  export let profil = { res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid',
    mid_ph: '3–0', has_scorers: true, scorers_label: 'Målskyttar' }
  // lagAlla (för lagfärg/logga) tas emot som prop, inte hämtas här — den
  // aktuella panelen har redan listaLag() i sitt eget onMount (Publicera/
  // Innehåll), och ett tredje samtidigt anrop ovanpå det ökar bara chansen
  // att träffa den kända listaLag-racen (store.lista_lag, delad self.conn
  // mellan bryggtrådar — spårat separat, inte löst här).
  export let lagAlla = []
  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }
  function loggaForLag(namn) { return lagAlla.find((x) => x.namn === namn)?.logga || '' }

  // Mobil Live: panelen pollar workern och skickar hit de fält som är FÄRSKARE
  // än våra egna (fältvis LWW, samma regel som workern). `externRev` bumpas för
  // varje ny omgång — värdet i sig betyder inget, det är bara en triggerpuls.
  export let extern = null       // {resultat?, mellan?, malskyttar?}
  export let externRev = 0
  export let forsFran = null     // {enhet:'mobil'|'desktop', tid:ISO} — närvaro (Del D)

  let resultat = ''
  let mellan = ''
  let malskyttar = ''
  let savedAt = ''
  // F18FM-1: per-fält-status — tom cirkel (ej ifyllt) · puls (osparat) ·
  // grön bock (sparat). Snapshot av senast sparade värden är facit.
  let sparatVals = { resultat: '', mellan: '', malskyttar: '' }
  const faltStatus = (v, sp) => !(v || '').trim() ? 'tom' : v === sp ? 'sparad' : 'osparad'
  $: st = { resultat: faltStatus(resultat, sparatVals.resultat),
            mellan: faltStatus(mellan, sparatVals.mellan),
            malskyttar: faltStatus(malskyttar, sparatVals.malskyttar) }
  let laddar = false     // sant medan lokala fält resyncas från en ny match — spärrar autospar
  let saveTimer = null

  $: _resync(match?.id)
  function _resync(id) {
    laddar = true
    resultat = match?.resultat || ''
    mellan = match?.mellan || ''
    malskyttar = match?.malskyttar || ''
    sparatVals = { resultat, mellan, malskyttar }   // matchens värden ÄR sparade
    savedAt = ''
    // setTimeout(0): Sveltes reaktivitet flushar efter denna funktion (inte
    // mellan raderna i den), så en synkron laddar=false här hinner INTE
    // spärra reaktionsblocket nedan innan det ser de nya värdena — resultatet
    // blir en oönskad "sparning" (och synlig "✓ Sparad") direkt vid matchbyte,
    // trots att användaren inte redigerat något. Släpp spärren en tick senare.
    setTimeout(() => (laddar = false), 0)
  }

  // Inkommande mobil-ändringar. `extern` läses som ARGUMENT (inte ur closure)
  // så Svelte spårar beroendet — samma fälla som dokumenterats flera gånger i
  // den här kodbasen. Spärren släpps en tick senare, exakt som i _resync, annars
  // hinner inte `laddar` blockera autospar-blocket och vi skriver tillbaka
  // mobilens värden som en "egen" sparning.
  let sisteRev = 0
  $: _applicera(externRev, extern)
  function _applicera(rev, e) {
    if (rev === sisteRev || !e) return
    sisteRev = rev
    laddar = true
    if (e.resultat !== undefined) resultat = e.resultat
    if (e.mellan !== undefined) mellan = e.mellan
    if (e.malskyttar !== undefined) malskyttar = e.malskyttar
    sparatVals = { resultat, mellan, malskyttar }   // mobilens värden är sparade
    setTimeout(() => (laddar = false), 0)
  }

  // Närvaro-pill: bara när MOBILEN skrev senast (vi vet redan om vi själva gjorde det).
  $: mobilFor = forsFran?.enhet === 'mobil'
  $: mobilTid = forsFran?.tid ? _klocka(forsFran.tid) : ''
  function _klocka(iso) {
    const d = new Date(iso)
    return isNaN(d) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  function schedule() {
    if (laddar || !match?.id) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      await sattResultat(match.id, resultat, mellan, malskyttar)
      sparatVals = { resultat, mellan, malskyttar }
      dispatch('sparat', { resultat, mellan, malskyttar })   // panelen kan rita om previews
      const d = new Date()
      savedAt = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    }, 500)
  }
  $: if (match?.id) { resultat; mellan; malskyttar; schedule() }

  // Målskyttar: rå kommaseparerad sträng med MINUT (appens etablerade format,
  // se tjanster/bildsvep.py STILEXEMPEL/SYSTEM och Live-mallens malskott-fält)
  // — "Ivanovic 10', Milivojevic 28', Kanutte Fornes 50', 58', 80'". En post
  // utan namn (bara "MM'") hör till samma spelare som föregående namngivna
  // post (flera mål) — grupperas till EN bricka: "Kanutte Fornes 50', 58', 80'".
  $: chips = _chipify(malskyttar)
  function _chipify(raw) {
    const delar = (raw || '').split(',').map((s) => s.trim()).filter(Boolean)
    const ut = []
    for (const d of delar) {
      const harNamn = /[a-zA-ZåäöÅÄÖ]/.test(d.replace(/\d+'?/g, ''))
      if (harNamn || !ut.length) ut.push(d)
      else ut[ut.length - 1] += ', ' + d
    }
    return ut
  }
  let scorersOpen = false
  let scorersRaw = ''
  function oppnaScorers() { scorersRaw = malskyttar; scorersOpen = true }
  function stangScorers() { malskyttar = scorersRaw; scorersOpen = false }

  // Ljus tavla med gren-behandling (låst: ingen kant om gren okänd).
  $: grenPa = !!match?.hem_gren
  $: grenC = grenFarg(match?.hem_gren)
  function _rgba(hex, a) { const n = parseInt((hex || '#8A8172').replace('#', ''), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})` }
  $: remsaStil = grenPa
    ? `border-left:5px solid ${grenC}; box-shadow: var(--skugga), 0 0 0 1px ${_rgba(grenC, 0.25)}, 0 0 14px ${_rgba(grenC, 0.18)};`
    : ''
</script>

{#if match}
  <div class="remsa" style={remsaStil}>
    <div class="vanster">
      <Lagbricka namn={match.lag_hemma} farg={fargForLag(match.lag_hemma)} logga={loggaForLag(match.lag_hemma)} storlek={32} />
      <input class="res scd" class:ifylld={st.resultat !== 'tom'} bind:value={resultat} placeholder="–:–" size="6" />
      <span class="fstat {st.resultat}" title={st.resultat === 'sparad' ? 'Sparat' : st.resultat === 'osparad' ? 'Sparar…' : 'Ej ifyllt'}>{st.resultat === 'sparad' ? '✓' : ''}</span>
      <Lagbricka namn={match.lag_borta} farg={fargForLag(match.lag_borta)} logga={loggaForLag(match.lag_borta)} storlek={32} />
    </div>
    <div class="mitt">
      <div class="fixtur">{match.lag_hemma} – {match.lag_borta}</div>
      <div class="undertext">
        {profil.mid_label}
        <input class="mid" class:ifylld={st.mellan !== 'tom'} bind:value={mellan} placeholder="–:–" size="12" />
        <span class="fstat {st.mellan}" title={st.mellan === 'sparad' ? 'Sparat' : st.mellan === 'osparad' ? 'Sparar…' : 'Ej ifyllt'}>{st.mellan === 'sparad' ? '✓' : ''}</span>
        {#if match.liga}· {match.liga}{/if}
      </div>
    </div>
    {#if profil.has_scorers}
      <div class="chips">
        {#if scorersOpen}
          <input class="scorersinput" bind:value={scorersRaw} placeholder="Efternamn 10', efternamn 25'…"
            on:keydown={(e) => e.key === 'Enter' && stangScorers()} />
          <button class="klar" on:click={stangScorers}>Klar</button>
        {:else}
          {#each chips as c}<span class="chip">{c}</span>{/each}
          <button class="laggmal" on:click={oppnaScorers}>+ mål</button>
          <span class="fstat {st.malskyttar}" title={st.malskyttar === 'sparad' ? 'Sparat' : st.malskyttar === 'osparad' ? 'Sparar…' : 'Ej ifyllt'}>{st.malskyttar === 'sparad' ? '✓' : ''}</span>
        {/if}
      </div>
    {:else}
      <div class="chips">
        <input class="mid bred" class:ifylld={st.mellan !== 'tom'} bind:value={mellan} placeholder="–:–" />
      </div>
    {/if}
    <div class="hoger">
      {#if mobilFor}
        <span class="mobilpill" title="Matchen förs just nu från mobilen (DPT2 Live)">
          <svg viewBox="0 0 24 24" width="11" height="11" aria-hidden="true">
            <rect x="7" y="2" width="10" height="20" rx="2.5" fill="none" stroke="currentColor" stroke-width="2" />
            <line x1="10.5" y1="18.5" x2="13.5" y2="18.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <span>Förs från mobilen{#if mobilTid}&nbsp;· {mobilTid}{/if}</span>
        </span>
      {/if}
      {#if savedAt}<span class="sparad">✓ Sparad {savedAt}</span>{/if}
    </div>
  </div>
{/if}

<style>
  .remsa { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    background: var(--kort); border: 1px solid var(--div); border-left: 5px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 10px 16px; margin-bottom: 16px; }
  .vanster { display: flex; align-items: center; gap: 9px; flex: none; }
  .res { width: auto; font-size: 26px; font-weight: 700; color: var(--ink); line-height: 1;
    background: transparent; border: none; border-bottom: 1px dashed var(--div);
    text-align: center; font-family: var(--font-c); }
  .mitt { flex: none; }
  .fixtur { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .undertext { font-size: 10.5px; color: var(--t-mut); display: flex; align-items: center; gap: 4px; }
  .mid { background: transparent; border: none; border-bottom: 1px dashed var(--div);
    font-family: 'SF Mono', Menlo, monospace; font-size: 11px; color: var(--t-mut); padding: 1px 2px; }
  .mid.bred { width: 100%; min-width: 200px; font-size: 12px; }
  .chips { display: flex; align-items: center; gap: 5px; flex: 1; min-width: 200px; flex-wrap: wrap; }
  .chip { font-size: 11px; font-weight: 600; background: var(--acc-soft); color: var(--t-head);
    border: 1px solid var(--div3); border-radius: 999px; padding: 3px 10px; }
  .laggmal { font-size: 11px; font-weight: 600; background: transparent; color: var(--t-mut);
    border: 1px dashed var(--div); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
  .scorersinput { flex: 1; min-width: 180px; background: var(--panel); border: 1px solid var(--div);
    border-radius: 999px; padding: 4px 12px; color: var(--ink); font-size: 12px; }
  .klar { font-size: 11px; font-weight: 600; color: var(--acc); background: transparent; border: none; cursor: pointer; }
  .hoger { display: flex; align-items: center; gap: 9px; flex: none; margin-left: auto; }
  .sparad { font-size: 10.5px; color: var(--ok); font-weight: 600; }
  /* F18FM-1: tomt = streckad ram + dämpad placeholder; ifyllt = solid ram +
     full kontrast. Indikatorn: tom cirkel → puls (sparar) → grön bock. */
  .res::placeholder, .mid::placeholder { color: var(--t-help); opacity: 0.5; }
  .res.ifylld, .mid.ifylld { border-bottom: 1px solid var(--t-mut); }
  .fstat { width: 15px; height: 15px; border-radius: 50%; flex: none;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 800; border: 1.5px solid var(--div);
    color: transparent; }
  .fstat.osparad { border-color: var(--acc); background: color-mix(in srgb, var(--acc) 25%, transparent);
    animation: fpuls 1.2s ease-in-out infinite; }
  .fstat.sparad { border-color: var(--ok); background: var(--ok); color: #fff; }
  @keyframes fpuls { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  /* Närvaro (Del D). Sea-färg #9CC6E0 enligt Designs handoff — ren hex, samma
     i ljust och mörkt tema, precis som gren-paletten. */
  .mobilpill { display: inline-flex; align-items: center; gap: 5px;
    font-size: 10.5px; font-weight: 600; color: #9CC6E0; white-space: nowrap;
    background: rgba(156, 198, 224, 0.12); border: 1px solid rgba(156, 198, 224, 0.32);
    border-radius: 999px; padding: 3px 9px; }
</style>
