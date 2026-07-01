<script>
  import Rail from './lib/Rail.svelte'
  import Matcher from './panels/Matcher.svelte'
  import Lag from './panels/Lag.svelte'
  import Gallra from './panels/Gallra.svelte'
  import Leverera from './panels/Leverera.svelte'
  import Publicera from './panels/Publicera.svelte'
  import Innehall from './panels/Innehall.svelte'
  import Trana from './panels/Trana.svelte'
  import Logg from './panels/Logg.svelte'
  import { erMock } from './lib/api.js'

  // Beräknas vid komponent-init (efter att bryggan väntats in i main.js).
  const ARMOCK = erMock()

  let aktiv = 'matcher'
  let tema = 'light'
  let aktivMatchData = null   // matchen som "Aktivera match" skickar till Gallra

  const NAMN = {
    matcher: 'Matcher', lag: 'Lag & tävlingar', gallra: 'Gallra',
    leverera: 'Leverera', publicera: 'Publicera', innehall: 'Innehåll',
    trana: 'Träna', logg: 'Logg',
  }

  function vaxlaTema() {
    tema = tema === 'light' ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', tema)
  }
</script>

<div class="app">
  <Rail {aktiv} on:valj={(e) => (aktiv = e.detail)} />

  <main>
    <div class="topbar">
      {#if ARMOCK}<span class="mock">mockdata · ingen Python-brygga</span>{/if}
      <button class="tema" on:click={vaxlaTema} title="Växla tema">
        {tema === 'light' ? '☾' : '☀'}
      </button>
    </div>

    {#if aktiv === 'matcher'}
      <Matcher on:aktiverad={(e) => { aktivMatchData = e.detail; aktiv = 'gallra' }} />
    {:else if aktiv === 'lag'}
      <Lag />
    {:else if aktiv === 'gallra'}
      <Gallra {aktivMatchData} />
    {:else if aktiv === 'leverera'}
      <Leverera />
    {:else if aktiv === 'publicera'}
      <Publicera on:navigera={(e) => (aktiv = e.detail)} />
    {:else if aktiv === 'innehall'}
      <Innehall />
    {:else if aktiv === 'trana'}
      <Trana />
    {:else if aktiv === 'logg'}
      <Logg />
    {:else}
      <div class="platshallare">
        <h1 class="scd">{NAMN[aktiv]}</h1>
        <p>Den här panelen byggs i en kommande fas.</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .app { display: flex; height: 100vh; overflow: hidden; }
  main { flex: 1; min-width: 0; overflow-y: auto; position: relative; }
  .topbar {
    position: sticky; top: 0; z-index: 5; display: flex; align-items: center;
    justify-content: flex-end; gap: 12px; height: 46px; padding: 0 22px;
    background: color-mix(in srgb, var(--sand) 86%, transparent);
    backdrop-filter: blur(8px); border-bottom: 1px solid var(--div3);
  }
  .mock { font-size: 11px; color: var(--varn); font-weight: 600;
    background: color-mix(in srgb, var(--varn) 14%, transparent);
    padding: 3px 9px; border-radius: 999px; }
  .tema { width: 32px; height: 32px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 15px; }
  .tema:hover { background: var(--div3); }
  .platshallare { padding: 40px 26px; color: var(--t-mut); }
  .platshallare h1 { color: var(--t-head); font-size: 25px; margin: 0 0 6px; }
  .platshallare p { font-size: 13px; }
</style>
