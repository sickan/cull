<script>
  // Veckovy: jobb som block i kategorifärg, privata poster som dämpade band med
  // streckad ram i källfärg. Titeln på en privat post visas ALDRIG här — bara
  // "Upptaget". Den nås via krock-utfällningen på jobbet.
  import { createEventDispatcher } from 'svelte'
  import Hornmarkor from './Hornmarkor.svelte'
  import KrockPop from './KrockPop.svelte'
  import { jobbSpann, privatSpann, kalenderFarg } from './privat.js'
  import { mandagen, addDagar, dygnSpann, overlappar, VECKODAG_KORT, MANAD_NAMN } from './vydatum.js'

  export let jobb = []          // redan kategorifiltrerade
  export let privata = []       // redan källfiltrerade (visning)
  export let kalendrar = []
  export let krockar = new Map() // jobb-id → privata poster (oberoende av filter)
  export let katFarg = () => '#888'
  export let ankare = new Date() // vilken vecka som visas (drill-down från Månad)

  const dispatch = createEventDispatcher()

  const PXTIM = 44

  let hoverJobb = null, pinnadJobb = null
  $: krockVisas = pinnadJobb ?? hoverJobb

  $: veckoStart = mandagen(ankare)
  $: dagar = Array.from({ length: 7 }, (_, i) => addDagar(veckoStart, i))

  // Rutnätet spänner normalt 06–22, men VÄXER för att rymma veckans ytterlägen.
  // Ett fast fönster tappade tysta poster utanför: en soluppgång 04:30 är precis
  // det ett landskapsjobb ser ut som, och den måste synas.
  $: veckoSpann = [veckoStart.getTime(), addDagar(veckoStart, 7).getTime()]
  $: tider = [
    ...jobb.filter((j) => !j.all_day).map(jobbSpann),
    ...privata.filter((p) => !p.heldag).map(privatSpann),
  ].filter(([s, e]) => overlappar(s, e, ...veckoSpann))
  $: startH = Math.min(6, ...tider.map(([s]) => new Date(s).getHours()))
  $: slutH = Math.max(22, ...tider.map(([, e]) => {
    const d = new Date(e)
    return d.getMinutes() ? d.getHours() + 1 : d.getHours()
  }))
  $: TIMMAR = Array.from({ length: slutH - startH + 1 }, (_, i) => startH + i)
  $: GRIDH = TIMMAR.length * PXTIM
  $: rubrik = `${veckoStart.getDate()} ${MANAD_NAMN[veckoStart.getMonth()].slice(0, 3)} – ${addDagar(veckoStart, 6).getDate()} ${MANAD_NAMN[addDagar(veckoStart, 6).getMonth()].slice(0, 3)}`

  const idagNyckel = new Date().toDateString()

  // Ett block per (post, dag) — en post som spänner över midnatt klipps mot dygnet
  // och dyker upp i båda kolumnerna i stället för att rita utanför sin kolumn.
  // startH/hojd skickas in i stället för att läsas ur closuren: Svelte spårar bara
  // variabler som NÄMNS i det reaktiva uttrycket, och `kolumner` skulle annars
  // inte räknas om när rutnätet växer.
  function block(spann, dag, startH, gridH) {
    const [dS, dE] = dygnSpann(dag)
    const [s, e] = spann
    if (!overlappar(s, e, dS, dE)) return null
    const minFran = (Math.max(s, dS) - dS) / 60000
    const minTill = (Math.min(e, dE) - dS) / 60000
    const top = Math.max(0, (minFran - startH * 60) / 60 * PXTIM)
    const bot = Math.min(gridH, (minTill - startH * 60) / 60 * PXTIM)
    if (bot <= 0 || top >= gridH) return null
    return { top, hojd: Math.max(16, bot - top) }
  }

  $: kolumner = dagar.map((dag) => ({
    dag,
    heldag: jobb.filter((j) => j.all_day && overlappar(...jobbSpann(j), ...dygnSpann(dag))),
    jobbBlock: jobb.filter((j) => !j.all_day)
      .map((j) => ({ j, b: block(jobbSpann(j), dag, startH, GRIDH) })).filter((x) => x.b),
    privatBlock: privata.filter((p) => !p.heldag)
      .map((p) => ({ p, b: block(privatSpann(p), dag, startH, GRIDH) })).filter((x) => x.b),
    privatHeldag: privata.filter((p) => p.heldag && overlappar(...privatSpann(p), ...dygnSpann(dag))),
  }))

  const klocka = (iso) => ((iso || '').split('T')[1] || '').slice(0, 5)
  function krockKlick(e, id) { e.stopPropagation(); pinnadJobb = pinnadJobb === id ? null : id }
</script>

<div class="veckovy">
  <div class="vhuvud">
    <button class="nav" on:click={() => (ankare = addDagar(veckoStart, -7))} aria-label="Föregående vecka">‹</button>
    <span class="vrubrik scd">{rubrik}</span>
    <button class="nav" on:click={() => (ankare = addDagar(veckoStart, 7))} aria-label="Nästa vecka">›</button>
    <button class="nav idag" on:click={() => (ankare = new Date())}>Denna vecka</button>
  </div>

  <div class="grid">
    <div class="tidspalt">
      <div class="hdspacer"></div>
      {#each TIMMAR as t}<div class="timme" style="height:{PXTIM}px"><span>{String(t).padStart(2, '0')}</span></div>{/each}
    </div>

    {#each kolumner as kol (kol.dag.toDateString())}
      <div class="kol" class:idag={kol.dag.toDateString() === idagNyckel}>
        <div class="dhuvud">
          <div class="dnamn scd">{VECKODAG_KORT[(kol.dag.getDay() + 6) % 7]}</div>
          <div class="dnr">{kol.dag.getDate()}</div>
        </div>

        <!-- Heldagsremsan: jobb och privata heldagsposter har ingen plats i
             timrutnätet och skulle annars fylla hela kolumnen. -->
        <div class="heldagsremsa">
          {#each kol.heldag as j (j.id)}
            <button class="hband" style="--f:{katFarg(j.category)}" title={j.title}
              on:click={() => dispatch('redigera', j)}>{j.title}</button>
          {/each}
          {#each kol.privatHeldag as p (p.id)}
            <div class="hband privat" style="--f:{kalenderFarg(kalendrar, p.kalender_id)}">Upptaget</div>
          {/each}
        </div>

        <div class="rutor" style="height:{GRIDH}px">
          {#each TIMMAR as t}<div class="ruta" style="height:{PXTIM}px"></div>{/each}

          {#each kol.privatBlock as { p, b } (p.id)}
            <div class="pband" style="top:{b.top}px;height:{b.hojd}px;--f:{kalenderFarg(kalendrar, p.kalender_id)}">
              <span>Upptaget</span>
            </div>
          {/each}

          {#each kol.jobbBlock as { j, b } (j.id)}
            {@const krock = krockar.get(j.id)}
            <div class="jwrap" style="top:{b.top}px;height:{b.hojd}px">
              {#if krock && krockVisas === j.id}<KrockPop krockar={krock} {kalendrar} heldag={false} />{/if}
              <div class="jblock" role="button" tabindex="0" style="--f:{katFarg(j.category)}"
                on:mouseenter={() => krock && (hoverJobb = j.id)} on:mouseleave={() => (hoverJobb = null)}
                on:click={() => dispatch('redigera', j)} on:keydown={(e) => e.key === 'Enter' && dispatch('redigera', j)}>
                {#if krock}
                  <Hornmarkor farg="var(--krock)" r={8} horn="nere-hoger" titel="Krockar med privat kalender" />
                  <button class="krocktapp" aria-label="Visa krock" on:click={(e) => krockKlick(e, j.id)}></button>
                {/if}
                <div class="jtid scd">{klocka(j.start_at)}</div>
                <div class="jtitel">{j.title}</div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .veckovy { display: flex; flex-direction: column; gap: 12px; }
  .vhuvud { display: flex; align-items: center; gap: 8px; }
  .vrubrik { font-size: 14px; font-weight: 700; color: var(--t-head); letter-spacing: 0.04em; min-width: 150px; }
  .nav { border: 1px solid var(--div); background: var(--kort); border-radius: 8px; padding: 5px 11px;
    font-size: 13px; color: var(--t-mut); }
  .nav:hover { border-color: var(--acc); color: var(--acc); }
  .nav.idag { margin-left: auto; font-size: 12.5px; font-weight: 600; }

  /* Varken overflow:hidden eller radie: krock-utfällningen växer ut ur sitt
     block och skulle klippas mot rutnätets kant. Ett fyrkantigt rutnät är
     dessutom vad en kalender ska se ut som. */
  .grid { display: grid; grid-template-columns: 46px repeat(7, 1fr); gap: 1px;
    background: var(--div3); border: 1px solid var(--div); }
  .tidspalt, .kol { background: var(--panel); }
  .hdspacer, .dhuvud { height: 52px; }
  .timme { position: relative; }
  .timme span { position: absolute; top: -7px; right: 8px; font-size: 10.5px; color: var(--t-caps);
    font-variant-numeric: tabular-nums; }
  .dhuvud { display: flex; flex-direction: column; align-items: center; justify-content: center;
    border-bottom: 1px solid var(--div); }
  .dnamn { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); }
  .dnr { font-size: 17px; font-weight: 700; color: var(--t-head); }
  .kol.idag .dnr { color: var(--acc); }

  .heldagsremsa { display: flex; flex-direction: column; gap: 2px; padding: 3px;
    min-height: 4px; border-bottom: 1px solid var(--div); }
  .hband { display: block; width: 100%; text-align: left; border: 0; border-left: 3px solid var(--f);
    background: color-mix(in srgb, var(--f) 18%, transparent); color: var(--t-head);
    font-size: 10.5px; font-weight: 600; padding: 3px 5px; border-radius: 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
  .hband.privat { border: 1px dashed var(--f); border-left: 3px solid var(--f);
    background: transparent; color: var(--t-mut); font-weight: 500; cursor: default; }

  .rutor { position: relative; }
  .ruta { border-bottom: 1px solid var(--div3); }

  /* Privat = tillgänglighet, inte innehåll: streckad, dämpad, aldrig klickbar.
     Bandet tar hela kolumnen och jobben dras in från vänster i stället för att
     läggas ovanpå — annars döljer ett jobb den upptagna tiden det krockar med,
     vilket är precis den information vyn finns för. */
  .pband { position: absolute; left: 3px; right: 3px; border: 1px dashed var(--f);
    border-left: 3px solid var(--f); border-radius: 5px; background: transparent;
    padding: 2px 5px; overflow: hidden; }
  .pband span { font-size: 10.5px; color: var(--t-mut); font-weight: 600; }

  /* jwrap bär popovern; jblock har overflow:hidden för hörnbågen. */
  .jwrap { position: absolute; left: 17px; right: 3px; z-index: 2; }
  .jblock { position: relative; overflow: hidden; height: 100%; border-radius: 6px;
    border-left: 3px solid var(--f); background: color-mix(in srgb, var(--f) 26%, var(--kort));
    padding: 3px 6px; cursor: pointer; }
  .jblock:hover { background: color-mix(in srgb, var(--f) 38%, var(--kort)); }
  .jtid { font-size: 10px; font-weight: 700; color: var(--t-head); font-variant-numeric: tabular-nums; }
  .jtitel { font-size: 10.5px; color: var(--t-head); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .krocktapp { position: absolute; right: 0; bottom: 0; width: 22px; height: 22px; z-index: 5;
    border: 0; background: transparent; padding: 0; cursor: pointer; }
</style>
