<script>
  import { onMount } from 'svelte'
  import Rail from './lib/Rail.svelte'
  import Fotojobb from './panels/Fotojobb.svelte'
  import Matcher from './panels/Matcher.svelte'
  import EventSektion from './panels/EventSektion.svelte'
  import Lag from './panels/Lag.svelte'
  import Utovare from './panels/Utovare.svelte'
  import Gallra from './panels/Gallra.svelte'
  import Leverera from './panels/Leverera.svelte'
  import Snabbplock from './panels/Snabbplock.svelte'
  import Upprattning from './panels/Upprattning.svelte'
  import Publicera from './panels/Publicera.svelte'
  import Innehall from './panels/Innehall.svelte'
  import PaGang from './panels/PaGang.svelte'
  import Trana from './panels/Trana.svelte'
  import Logg from './panels/Logg.svelte'
  import Installningar from './panels/Installningar.svelte'
  import SynkMarke from './lib/SynkMarke.svelte'
  import Kommandopalett from './lib/Kommandopalett.svelte'
  import { oppnaMal } from './lib/oppna.js'
  import { synka as livesynkaNu } from './lib/livesynk.js'
  import { erMock, aktivMatch, aktivtUrval, listaMaterial, stangAktivMatch, synkDelta } from './lib/api.js'
  import { testMode } from './lib/testlage.js'

  const ARMOCK = erMock()

  let aktiv = 'fotojobb'
  // Temat följer OS (prefers-color-scheme) tills användaren manuellt växlar.
  const osTema = () => (typeof window !== 'undefined' && window.matchMedia
    && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark'
  let tema = osTema()
  let temaManuellt = false   // sant efter manuell växling → sluta följa OS
  // Speglar temat till <html data-theme> — körs direkt vid init (ingen ljus
  // blink) och vid varje växling.
  $: if (typeof document !== 'undefined') document.documentElement.setAttribute('data-theme', tema)
  let aktivMatchData = null
  let aktivM = null            // global aktiv match (topp-widget)
  let aktivU = null            // globalt aktivt urval (topp-widget)
  let harDelvis = false        // minst ett material är "Delvis publicerad" (nav-punkt)

  // D11b §4: ⌘K global sökning — öppnas var som helst, djuplänkar via oppnaMal.
  let palettOppen = false
  function globalTangent(e) {
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault(); palettOppen = !palettOppen
    }
  }
  function valjSok(e) {
    aktiv = e.detail.mal
    oppnaMal.set(e.detail)
    palettOppen = false
  }

  onMount(async () => {
    // Följ OS-temat live (tills man växlat manuellt).
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mq = window.matchMedia('(prefers-color-scheme: light)')
      const foljOS = () => { if (!temaManuellt) tema = mq.matches ? 'light' : 'dark' }
      mq.addEventListener ? mq.addEventListener('change', foljOS) : mq.addListener(foljOS)
    }
    ;[aktivM, aktivU] = await Promise.all([aktivMatch(), aktivtUrval()])
    await uppdateraDelvis()
    // D11b §4: pusha vid start så synk-märket speglar verkligt läge direkt.
    livesynkaNu()
    // SYNK-DPT2 (tvåvägs-blixten): appglobal delta-poll — mobilens ändringar
    // (resultat, trupp, original) når skrivbordet utan öppen Publicera-panel.
    // Billig fråga (bara ändrade paket kommer tillbaka); paneler lyssnar på
    // window-eventet och laddar om sina berörda vyer.
    setInterval(async () => {
      const d = await synkDelta().catch(() => null)
      if (d?.ok && d.andrade?.length) {
        window.dispatchEvent(new CustomEvent('dpt-synk', { detail: d.andrade }))
      }
    }, 15000)
  })
  async function uppdateraDelvis() {
    const mat = await listaMaterial()
    harDelvis = mat.some((m) => m.status === 'delvis')
  }

  async function uppdateraUrval() { aktivU = await aktivtUrval() }
  const urvalEtikett = (u) => !u ? ''
    : (u.lag_hemma ? `${u.lag_hemma} – ${u.lag_borta}` : (u.kalla || '').split('/').pop())

  function vaxlaTema() {
    temaManuellt = true                          // sluta följa OS efter manuell växling
    tema = tema === 'light' ? 'dark' : 'light'   // data-theme sätts av det reaktiva blocket ovan
  }
  // FEAT-05: uttryckligen stäng aktiva matchen (klar för dagen) — ingen match
  // ska ligga kvar som aktiv av misstag.
  async function stangMatch() {
    await stangAktivMatch()
    aktivM = null; aktivMatchData = null
  }
  function aktiveraFranMatcher(m) { aktivMatchData = m; aktivM = m; aktiv = 'gallra' }
  // §2: matchradens statuschips — samma aktivera-mekanism, valfri destination.
  function aktiveraFranMatcherTill(m, dest) { aktivMatchData = m; aktivM = m; aktiv = dest }
</script>

<svelte:window on:keydown={globalTangent} />
{#if palettOppen}
  <Kommandopalett on:valj={valjSok} on:stang={() => (palettOppen = false)} />
{/if}

<div class="app">
  <Rail {aktiv} delvis={harDelvis} on:valj={(e) => (aktiv = e.detail)} />

  <main>
    <div class="topbar">
      <div class="matchgrupp">
        <!-- §8: jobbet som nav — chippet heter "Aktivt jobb". Sportjobb visar
             matchdata som förut; tomläget bjuder in alla jobbtyper. -->
        <button class="widget match" on:click={() => (aktiv = 'matcher')} title="Aktivt jobb">
          <span class="dot" class:pa={aktivM}></span>
          <span class="wtext">
            <span class="wlbl">Aktivt jobb</span>
            <span class="wval scd">{aktivM ? `${aktivM.lag_hemma} – ${aktivM.lag_borta}` : 'Inget valt'}</span>
          </span>
        </button>
        {#if aktivM}
          <button class="stangmatch" on:click={stangMatch} title="Stäng matchen — klar för dagen">×</button>
        {/if}
      </div>
      <button class="widget urval" on:click={() => (aktiv = aktivU ? 'leverera' : 'gallra')}
        title={aktivU ? 'Aktivt urval — gå till Leverera' : 'Inget urval — gå till Gallra'}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" class="ic"><path d="M3 7.5A2 2 0 015 5.5h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
        <span class="wtext">
          {#if aktivU}
            <span class="wlbl">Aktivt urval · {aktivU.status}</span>
            <span class="wval scd">{urvalEtikett(aktivU)} · {aktivU.bilder} bilder</span>
          {:else}
            <span class="wval scd">Inget urval valt</span>
            <span class="wlbl">Klicka för att välja</span>
          {/if}
        </span>
      </button>
      <SynkMarke />
      {#if ARMOCK}<span class="mock">mock</span>{/if}
      <button class="testswitch" class:on={$testMode} on:click={() => ($testMode = !$testMode)}
        title="Testläge — inget sparas eller postas på riktigt">
        <span class="tsw-track"><span class="tsw-knob"></span></span>
        <span class="tsw-label">Testläge</span>
      </button>
      <button class="tema" on:click={vaxlaTema} title="Växla tema">{tema === 'light' ? '☾' : '☀'}</button>
    </div>

    {#if $testMode}
      <div class="testbanner">
        <span class="testtag">TESTLÄGE</span>
        <span>Allt skapas i minnet · exempelfiler skrivs till</span>
        <span class="testpath mono">~/DPT/test-output/</span>
        <span>· inget sparas — rensas vid omstart</span>
      </div>
    {/if}

    {#if aktiv === 'fotojobb'}
      <Fotojobb on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'matcher'}
      <Matcher on:aktiverad={(e) => aktiveraFranMatcher(e.detail)}
        on:gaTill={(e) => aktiveraFranMatcherTill(e.detail.match, e.detail.dest)}
        on:navigera={(e) => (aktiv = e.detail)} on:urval={uppdateraUrval} />
    {:else if aktiv === 'eventsektion'}
      <EventSektion on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'lag'}
      <Lag />
    {:else if aktiv === 'utovare'}
      <Utovare />
    {:else if aktiv === 'gallra'}
      <Gallra {aktivMatchData} on:navigera={(e) => (aktiv = e.detail)} on:urval={uppdateraUrval} />
    {:else if aktiv === 'leverera'}
      <Leverera on:navigera={(e) => (aktiv = e.detail)} on:urval={uppdateraUrval} />
    {:else if aktiv === 'snabbplock'}
      <Snabbplock on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'upprattning'}
      <Upprattning on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'publicera'}
      <Publicera on:navigera={(e) => (aktiv = e.detail)} on:materialAndrat={uppdateraDelvis} />
    {:else if aktiv === 'innehall'}
      <Innehall on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'pagang'}
      <PaGang />
    {:else if aktiv === 'trana'}
      <Trana />
    {:else if aktiv === 'logg'}
      <Logg />
    {:else if aktiv === 'installningar'}
      <Installningar />
    {/if}
  </main>
</div>

<style>
  .app { display: flex; height: 100vh; overflow: hidden; }
  main { flex: 1; min-width: 0; overflow-y: auto; position: relative; display: flex; flex-direction: column; }
  /* 6a: global topp = TUNN statusrad — prick + text / ikon + text, inga pills. */
  .topbar {
    position: sticky; top: 0; z-index: 5; display: flex; align-items: center;
    justify-content: flex-end; gap: 18px; min-height: 42px; padding: 6px 22px;
    background: color-mix(in srgb, var(--sand) 86%, transparent);
    backdrop-filter: blur(8px); border-bottom: 1px solid var(--div3); flex: none;
  }
  .widget { display: flex; align-items: center; gap: 8px; padding: 4px 2px;
    background: transparent; border: 0; color: var(--t-head); }
  .widget:hover .wval { color: var(--acc); }
  .matchgrupp { display: flex; align-items: center; gap: 4px; margin-right: auto; }
  .stangmatch { width: 22px; height: 22px; border: 0; border-radius: 50%; flex: none;
    background: transparent; color: var(--t-mut); font-size: 14px; line-height: 1; }
  .stangmatch:hover { background: var(--div3); color: var(--t-head); }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--t-help); flex: none; }
  .dot.pa { background: var(--acc); box-shadow: 0 0 0 3px var(--acc-soft); }
  .ic { width: 15px; height: 15px; color: var(--t-mut); flex: none; }
  .wtext { display: flex; flex-direction: column; line-height: 1.1; text-align: left; }
  .wlbl { font-size: 8.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--t-mut); font-weight: 600; }
  .wval { font-size: 12.5px; font-weight: 700; color: var(--t-head); }
  .mock { font-size: 10px; color: var(--varn); font-weight: 700;
    background: color-mix(in srgb, var(--varn) 14%, transparent); padding: 3px 8px; border-radius: 999px; }
  .tema { width: 30px; height: 30px; border: 0; border-radius: 50%;
    background: transparent; color: var(--t-head); font-size: 14px; flex: none; }
  .tema:hover { background: var(--div3); }

  .testswitch { display: flex; align-items: center; gap: 8px; padding: 4px 2px;
    background: transparent; border: 0;
    font-size: 12px; font-weight: 600; color: var(--t-mut); flex: none; }
  .testswitch.on { color: var(--varn); }
  .tsw-track { width: 30px; height: 17px; border-radius: 999px; background: var(--div3);
    border: 1px solid var(--div); position: relative; flex: none; transition: background .15s, border-color .15s; }
  .testswitch.on .tsw-track { background: var(--varn); border-color: var(--varn); }
  .tsw-knob { position: absolute; top: 1px; left: 1px; width: 13px; height: 13px; border-radius: 50%;
    background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.3); transition: left .15s; }
  .testswitch.on .tsw-knob { left: 14px; }

  .testbanner { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; flex: none;
    padding: 7px 22px; font-size: 11.5px; font-weight: 600; color: var(--varn);
    background: color-mix(in srgb, var(--varn) 10%, transparent);
    border-bottom: 1px solid color-mix(in srgb, var(--varn) 30%, transparent); }
  .testbanner .testtag { font-size: 9.5px; font-weight: 700; letter-spacing: .06em;
    border: 1px solid color-mix(in srgb, var(--varn) 55%, transparent); padding: 1px 7px; border-radius: 5px; }
  .testbanner .testpath { font-family: var(--mono, ui-monospace, monospace); font-size: 11px;
    background: color-mix(in srgb, var(--varn) 14%, transparent); padding: 1px 7px; border-radius: 5px; }
  .testbanner .mono { font-family: var(--mono, ui-monospace, monospace); }
</style>
