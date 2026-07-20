<script>
  // Delad resultat-remsa (scoreboard) — Publicera (Live+SoMe) och Innehåll→
  // Sport. Skriver direkt på matchposten (resultat/mellan/malskyttar), en
  // källa som Live-mallen, SoMe-brickorna och Webb-fälten alla speglar.
  // Design: design_handoff_live_some_webb/Bildval & Resultat-remsa -
  // varianter.dc.html, variant 1e. Ingen egen "Byt match"-knapp — sitter
  // alltid direkt under AktivMatchRad/matchväljaren, som redan har den.
  import { sattResultat } from './api.js'
  import Lagbricka from './Lagbricka.svelte'

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

  let resultat = ''
  let mellan = ''
  let malskyttar = ''
  let savedAt = ''
  let laddar = false     // sant medan lokala fält resyncas från en ny match — spärrar autospar
  let saveTimer = null

  $: _resync(match?.id)
  function _resync(id) {
    laddar = true
    resultat = match?.resultat || ''
    mellan = match?.mellan || ''
    malskyttar = match?.malskyttar || ''
    savedAt = ''
    // setTimeout(0): Sveltes reaktivitet flushar efter denna funktion (inte
    // mellan raderna i den), så en synkron laddar=false här hinner INTE
    // spärra reaktionsblocket nedan innan det ser de nya värdena — resultatet
    // blir en oönskad "sparning" (och synlig "✓ Sparad") direkt vid matchbyte,
    // trots att användaren inte redigerat något. Släpp spärren en tick senare.
    setTimeout(() => (laddar = false), 0)
  }

  function schedule() {
    if (laddar || !match?.id) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      await sattResultat(match.id, resultat, mellan, malskyttar)
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
</script>

{#if match}
  <div class="remsa">
    <div class="vanster">
      <Lagbricka namn={match.lag_hemma} farg={fargForLag(match.lag_hemma)} logga={loggaForLag(match.lag_hemma)} storlek={32} />
      <input class="res scd" bind:value={resultat} placeholder={profil.res_ph} size="6" />
      <Lagbricka namn={match.lag_borta} farg={fargForLag(match.lag_borta)} logga={loggaForLag(match.lag_borta)} storlek={32} />
    </div>
    <div class="mitt">
      <div class="fixtur">{match.lag_hemma} – {match.lag_borta}</div>
      <div class="undertext">
        {profil.mid_label}
        <input class="mid" bind:value={mellan} placeholder={profil.mid_ph} size="12" />
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
        {/if}
      </div>
    {:else}
      <div class="chips">
        <input class="mid bred" bind:value={mellan} placeholder={profil.mid_ph} />
      </div>
    {/if}
    <div class="hoger">
      {#if savedAt}<span class="sparad">✓ Sparad {savedAt}</span>{/if}
    </div>
  </div>
{/if}

<style>
  .remsa { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    background: #23201a; border: 1px solid rgba(0, 0, 0, 0.3); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 10px 16px; margin-bottom: 16px; }
  .vanster { display: flex; align-items: center; gap: 9px; flex: none; }
  .res { width: auto; font-size: 26px; font-weight: 700; color: #fff; line-height: 1;
    background: transparent; border: none; border-bottom: 1px dashed rgba(255, 255, 255, 0.25);
    text-align: center; font-family: var(--font-c); }
  .mitt { flex: none; }
  .fixtur { font-size: 12.5px; font-weight: 600; color: #fff; }
  .undertext { font-size: 10.5px; color: rgba(255, 255, 255, 0.5); display: flex; align-items: center; gap: 4px; }
  .mid { background: transparent; border: none; border-bottom: 1px dashed rgba(255, 255, 255, 0.25);
    font-family: 'SF Mono', Menlo, monospace; font-size: 11px; color: rgba(255, 255, 255, 0.85); padding: 1px 2px; }
  .mid.bred { width: 100%; min-width: 200px; font-size: 12px; }
  .chips { display: flex; align-items: center; gap: 5px; flex: 1; min-width: 200px; flex-wrap: wrap; }
  .chip { font-size: 11px; font-weight: 600; background: rgba(255, 255, 255, 0.12); color: #fff;
    border-radius: 999px; padding: 3px 10px; }
  .laggmal { font-size: 11px; font-weight: 600; background: transparent; color: rgba(255, 255, 255, 0.55);
    border: 1px dashed rgba(255, 255, 255, 0.3); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
  .scorersinput { flex: 1; min-width: 180px; background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 999px; padding: 4px 12px; color: #fff; font-size: 12px; }
  .klar { font-size: 11px; font-weight: 600; color: var(--acc); background: transparent; border: none; cursor: pointer; }
  .hoger { display: flex; align-items: center; gap: 9px; flex: none; margin-left: auto; }
  .sparad { font-size: 10.5px; color: #7fb56b; font-weight: 600; }
</style>
