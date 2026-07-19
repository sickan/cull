<script>
  // Läs in (C8–C10): EN väg in till en tävlings program/startlista.
  // Bruten ur EventSektion när M-3:s arbetsyta tillkom — kort-stapeln och
  // arbetsytan öppnar nu samma implementation i stället för var sin kopia.
  //
  // Parsern GISSAR dokumenttyp (C8) — Stig väljer bara om vid osäkerhet.
  // Granskningen visar som standard BARA avvikelser (C9) — 800 rena rader ska
  // inte kräva ögon. En omimport visar sin diff innan något sparas (C10).
  import { createEventDispatcher } from 'svelte'
  import { tolkaProgramPdf, importeraProgram, lasIn as lasInApi,
    forhandsgranskaImport } from './api.js'

  export let oppen = false
  export let eventId = null

  const dispatch = createEventDispatcher()

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

  // Varje öppning börjar från noll — annars ligger förra granskningen kvar.
  let sistOppen = false
  $: if (oppen !== sistOppen) {
    sistOppen = oppen
    if (oppen) {
      inlasText = ''; granskning = null; forhands = null
      inlasKvitto = ''; inlasFel = ''
    }
  }

  async function lasIn(sort = 'auto') {
    if (!inlasText.trim()) return
    inlasFel = ''; forhands = null
    granskning = await lasInApi(eventId, inlasText, sort).catch(() => null)
    if (granskning) baraAvvik = (granskning.sammanfattning?.avvikande || 0) > 0
  }
  // PDF: arrangörens fil läses direkt, med kolumnlayouten. Klassen (dam/herr)
  // följer med ur kolumnen och blir grenmarkörens färg.
  async function lasPdf() {
    inlasFel = ''; forhands = null
    const r = await tolkaProgramPdf(eventId).catch(() => null)
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
    forhands = await forhandsgranskaImport(eventId, rader, sort, delt).catch(() => null)
  }
  async function sparaInlas() {
    const [rader, sort, delt] = importArgs()
    if (!rader.length && !(delt && delt.length)) return
    const sam = await importeraProgram(eventId, rader, sort, delt)
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
    dispatch('klar')
  }
</script>

{#if oppen}
  <div class="inlas">
    <div class="seg liten">
      <span class="caps">Läs in program eller startlista</span>
      <span class="spacer"></span>
      <button class="bort" title="Stäng" on:click={() => (oppen = false)}>✕</button>
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

<style>
  .inlas { border: 1px solid var(--div); border-radius: 10px; padding: 12px;
    margin-bottom: 12px; background: var(--panel); }
  .caps { font-size: 10.5px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--t-caps, var(--t-mut)); }
  .spacer { flex: 1; }
  .khint { font-size: 11.5px; color: var(--t-help); }
  .seg.liten { margin-bottom: 10px; display: flex; width: 100%; align-items: center; }
  .inlas textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--div);
    border-radius: 8px; padding: 9px 11px; background: var(--kort); color: var(--t-head);
    font-family: inherit; font-size: 12.5px; line-height: 1.6; resize: vertical; }
  .inlasfot { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px;
    padding: 7px 12px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
  .prim:disabled { opacity: 0.5; }
  .avbryt { border: 1px solid var(--div); background: var(--kort); border-radius: 8px;
    padding: 7px 12px; font-size: 12.5px; font-weight: 600; color: var(--t-mut); cursor: pointer; }
  .avbryt:disabled { opacity: 0.5; }
  .bort { border: 0; background: none; color: var(--t-mut); cursor: pointer;
    font-size: 12px; padding: 2px 5px; }
  .bort:hover { color: var(--krock, #b03838); }
  .bort.synlig { opacity: 0.65; }
  .bort.synlig:hover { opacity: 1; }
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
  .tomkort { font-size: 12.5px; color: var(--t-help); margin: 4px 0 2px; }
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
  .gransktabell select.gf { padding: 5px 4px; }
  .kvitto { font-size: 12px; color: var(--t-help); background: var(--panel);
    border: 1px solid var(--div); border-radius: 8px; padding: 7px 11px; margin-bottom: 10px; }
  .kvitto.fel { color: var(--krock, #b03838); border-color: var(--krock, #b03838); margin-top: 10px; }
</style>
