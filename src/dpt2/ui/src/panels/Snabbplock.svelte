<script>
  // Snabbplock — dedikerat plock-läge (B1–B3 ur MFF-backloggen).
  // Flöde: Kort in → Plocka → Mata ut → (nästa kort …) → Granska → Lightroom.
  // Medvetet mörk "fältläge"-panel oavsett app-tema (se design-handoffen) —
  // därför egen hårdkodad palett, inte tokens.css.
  //
  // UI-först: rutnätet visar platshållar-tumnaglar och Lightroom-steget är en
  // simulerad statuslista. Riktig RAW-preview + urval persistat per jobb +
  // stegvis kopiera/import görs i en backend-uppföljning (markerat nedan).
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { aktivMatch, listaMinnesKort, listaKortBilder, thumbForBild, snabbplockExport } from '../lib/api.js'

  const dispatch = createEventDispatcher()
  const N_THUMBS = 10 // tumnaglar som visas per kort (de senaste; resten rullar in)

  let step = 'insert' // insert | pick | review | lr
  let cardIdx = 0 // nästa kort att läsa
  let cards = [] // upptäckta monterade kort (växer när nya sätts i)
  let cardFiles = {} // { [cardIdx]: [{ path, filnamn, skyddad }] } — riktiga kortbilder
  let thumbs = {} // { [path]: data_uri } — lazy preview-cache
  let picks = {} // { [cardIdx]: { [thumbIdx]: true } }
  let removed = {} // granska: { 'c-i': true }
  let lrPhase = 'idle' // idle | running | done | fel
  let lrStep = 0
  let lrFel = '' // felmeddelande om exporten misslyckas
  let lrPath = '' // arbetsmappen exporten skrevs till
  let timer = null
  let pollTimer = null // detekterar isatta kort medan man står på Kort in
  let letat = false // har vi kört minst en kort-detektering?
  let headerMatch = null

  onMount(async () => {
    headerMatch = await aktivMatch()
  })
  onDestroy(() => {
    timer && clearInterval(timer)
    stopPoll()
  })

  // Detektera monterade kamerakort (volym m. DCIM). Nya kort läggs till sist
  // med stabil numrering så cardIdx/picks inte förskjuts. Redan tillagda kort
  // (samma path) hoppas över.
  async function detektera() {
    const r = await listaMinnesKort()
    letat = true
    if (r && r.ok && r.kort && r.kort.length) {
      const kanda = new Set(cards.map((c) => c.path))
      const bas = cards.length
      const nya = r.kort
        .filter((k) => k.path && !kanda.has(k.path))
        .map((k, j) => ({ name: `Kort ${bas + j + 1} · ${k.namn}`, total: k.skyddade || 0, path: k.path }))
      if (nya.length) cards = [...cards, ...nya]
    }
  }
  function startPoll() {
    if (pollTimer) return
    detektera()
    pollTimer = setInterval(detektera, 2500)
  }
  function stopPoll() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }
  // Poll:a bara medan man står på Kort in-steget (ett isatt kort dyker upp
  // automatiskt); sluta så fort man läser/plockar.
  $: if (step === 'insert') startPoll(); else stopPoll()

  // ── Härledda värden ────────────────────────────────────────────────────────
  $: cur = step === 'pick' ? cardIdx - 1 : -1
  const range = (n) => Array.from({ length: n }, (_, i) => i)
  $: doneIdx = range(cardIdx).filter((c) => c !== cur)
  // Reaktiv (inte const) så statements som anropar den spårar `picks` som
  // beroende och räknas om när urvalet ändras.
  $: pickedList = (c) => Object.keys(picks[c] || {}).map(Number).sort((a, b) => a - b)
  $: totalPicked = Object.keys(picks).reduce((a, c) => a + Object.keys(picks[c]).length, 0)
  $: removedN = Object.keys(removed).length
  $: finalN = totalPicked - removedN
  // De faktiska filsökvägarna som ska exporteras: plockade minus bortkryssade,
  // och bara de som har en riktig fil bakom sig (cardFiles laddat).
  $: finalPaths = Object.keys(picks)
    .map(Number)
    .flatMap((c) =>
      pickedList(c)
        .filter((i) => !removed[`${c}-${i}`])
        .map((i) => (cardFiles[c] || [])[i]?.path)
        .filter(Boolean)
    )
  $: hasNextCard = cardIdx < cards.length
  $: canReview = step === 'insert' && totalPicked > 0
  $: noneDone = doneIdx.length === 0 && cur < 0
  $: curCard = cur >= 0 ? cards[cur] : null
  $: curPickedN = cur >= 0 ? pickedList(cur).length : 0

  $: headerFixture = headerMatch
    ? `${headerMatch.lag_hemma} – ${headerMatch.lag_borta} · aktiv match`
    : 'Inget aktivt jobb — plocka ändå'

  // Chips i urvals-raden: en grön per genomgånget kort + amber för det som läses.
  $: cardChips = [
    ...doneIdx.map((c) => ({
      label: `${cards[c].name.split(' · ')[0]} · ${pickedList(c).length} plockade`,
      cur: false,
    })),
    ...(cur >= 0 ? [{ label: `${cards[cur].name.split(' · ')[0]} · läses nu`, cur: true }] : []),
  ]

  // Flödes-stepper (B3): Lightroom lyser sist.
  const FLOW = ['Kort in', 'Plocka', 'Kort ut', 'Granska', 'Lightroom']
  $: flowActive =
    step === 'insert' ? (doneIdx.length ? 2 : 0) : step === 'pick' ? 1 : step === 'review' ? 3 : 4

  const dscNum = (c, i) => 'DSC_0' + (400 + c * 100 + i)
  // Platshållar-ton per ruta (tills riktiga RAW-previews kopplas in).
  const tint = (c, i) => {
    const h = (c * 47 + i * 23) % 360
    return `linear-gradient(135deg, hsl(${h} 24% 26%), hsl(${(h + 40) % 360} 22% 17%))`
  }

  $: curThumbs =
    cur < 0
      ? []
      : cardFiles[cur]
        ? cardFiles[cur].map((b, i) => ({
            i, num: b.filnamn, path: b.path,
            uri: thumbs[b.path] || null, on: !!(picks[cur] || {})[i],
          }))
        : range(N_THUMBS).map((i) => ({
            i, num: dscNum(cur, i), path: null, uri: null, on: !!(picks[cur] || {})[i],
          }))

  $: reviewGroups = Object.keys(picks)
    .map(Number)
    .sort((a, b) => a - b)
    .filter((c) => pickedList(c).length)
    .map((c) => ({
      label: `${cards[c].name} — ${pickedList(c).length} plockade`,
      thumbs: pickedList(c).map((i) => {
        const k = `${c}-${i}`
        const f = (cardFiles[c] || [])[i]
        return {
          c, i, key: k, off: !!removed[k],
          num: f ? f.filnamn : dscNum(c, i),
          uri: f ? thumbs[f.path] || null : null,
        }
      }),
    }))
  $: doneCardsN = reviewGroups.length

  const LR_STEG = [
    ['Kopierar N bilder till arbetsdisken', 'Urvalet kopierat — korten orörda'],
    ['Bygger import med husstil + metadata', 'Import byggd'],
    ['Öppnar Lightroom med urvalet', 'Lightroom öppnat med urvalet'],
  ]
  $: lrSteps = LR_STEG.map((d, i) => {
    const done = lrPhase === 'done' || lrStep > i
    const active = lrPhase === 'running' && lrStep === i
    return { label: done ? d[1] : d[0].replace('N', finalN), done, active }
  })

  // ── Handlingar ──────────────────────────────────────────────────────────────
  async function insertCard() {
    if (cardIdx >= cards.length) return
    const idx = cardIdx
    cardIdx += 1
    step = 'pick'
    const card = cards[idx]
    if (!card.path) return // demo-kort utan riktig sökväg → platshållar-rutnät
    const r = await listaKortBilder(card.path, N_THUMBS)
    if (r && r.ok && r.bilder) {
      cardFiles = { ...cardFiles, [idx]: r.bilder }
      if (r.totalt != null) cards = cards.map((c, i) => (i === idx ? { ...c, total: r.totalt } : c))
      laddaThumbs(r.bilder)
    }
  }
  // Hämtar de inbäddade previewerna en och en (exiftool per fil) och fyller på
  // cachen — rutorna byter från platshållar-ton till bild allteftersom.
  async function laddaThumbs(bilder) {
    for (const b of bilder) {
      if (thumbs[b.path]) continue
      const t = await thumbForBild(b.path)
      if (t && t.ok && t.data_uri) thumbs = { ...thumbs, [b.path]: t.data_uri }
    }
  }
  function togglePick(c, i) {
    const per = { ...(picks[c] || {}) }
    if (per[i]) delete per[i]
    else per[i] = true
    picks = { ...picks, [c]: per }
  }
  function ejectCard() {
    step = 'insert'
  }
  function goReview() {
    step = 'review'
  }
  function toggleRemoved(k) {
    const r = { ...removed }
    if (r[k]) delete r[k]
    else r[k] = true
    removed = r
  }
  function backToInsert() {
    step = 'insert'
  }
  async function openLightroom() {
    // Skarp export: kopierar de plockade filerna till en arbetsmapp, skriver
    // Blue-etikett och öppnar mappen i Lightroom (api.snabbplock_export).
    step = 'lr'
    lrPhase = 'running'
    lrStep = 0
    lrFel = ''
    lrPath = ''
    const paths = finalPaths
    if (!paths.length) {
      lrPhase = 'fel'
      lrFel = 'Inga plockade filer att exportera.'
      return
    }
    const r = await snabbplockExport(paths)
    if (r && r.ok) {
      lrStep = 3
      lrPath = r.path || ''
      lrPhase = 'done'
    } else {
      lrPhase = 'fel'
      lrFel = (r && r.fel) || 'Kunde inte kopiera bilderna / öppna Lightroom.'
    }
  }
  function restart() {
    timer && clearInterval(timer)
    timer = null
    step = 'insert'
    cardIdx = 0
    cards = []
    letat = false
    picks = {}
    removed = {}
    cardFiles = {}
    thumbs = {}
    lrPhase = 'idle'
    lrStep = 0
    lrFel = ''
    lrPath = ''
  }
</script>

<div class="sp">
  <!-- Topp: titel + jobb + flödes-stepper -->
  <div class="topp">
    <div class="titel">
      <span class="ikon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2L4.5 13.5H11L10 22l8.5-11.5H12z"/></svg>
      </span>
      <div>
        <div class="h1 scd">Snabbplock</div>
        <div class="fixtur">{headerFixture}</div>
      </div>
    </div>
    <span class="vaxt"></span>
    <div class="stepper">
      {#each FLOW as f, i}
        <span class="fs" class:aktiv={i === flowActive} class:gjord={i < flowActive}>{f}</span>
        {#if i < FLOW.length - 1}<span class="pil">→</span>{/if}
      {/each}
    </div>
  </div>

  <div class="kropp">
    <!-- Urvals-rad: alltid synlig — B1 -->
    <div class="urval">
      <span class="urval-lbl">Urval</span>
      {#each cardChips as cc}
        <span class="chip" class:cur={cc.cur}><span class="chip-dot"></span>{cc.label}</span>
      {/each}
      {#if noneDone}<span class="tom">Inga kort genomgångna ännu</span>{/if}
      <span class="vaxt"></span>
      <span class="total scd">{totalPicked} plockade</span>
    </div>

    <!-- ============ STEG: SÄTT I KORT ============ -->
    {#if step === 'insert'}
      <div class="dropyta">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="rgba(243,245,247,.4)" stroke-width="1.4" class="drop-ic"><rect x="6" y="3" width="12" height="18" rx="2"/><path d="M9 3v4M12 3v4M15 3v4"/></svg>
        {#if hasNextCard}
          <div class="drop-h scd">Kort upptäckt</div>
          <div class="drop-p">{cards[cardIdx].name}<br>Läs kortet och plocka medan bilderna rullar in.</div>
          <button class="btn-amber" on:click={insertCard}>Läs kortet ›</button>
        {:else if cardIdx > 0}
          <div class="drop-h scd">Kort genomgånget</div>
          <div class="drop-p">Sätt i nästa kort — det upptäcks automatiskt.<br>Urvalet ligger kvar ({totalPicked} plockade).</div>
          <button class="btn-mork liten" on:click={detektera}>Leta efter kort igen</button>
        {:else}
          <div class="drop-h scd">Sätt i ett minneskort</div>
          <div class="drop-p">{letat ? 'Inget kort hittat än — det upptäcks automatiskt när det sitter i.' : 'Letar efter kort …'}<br>Kortet läses direkt — plocka medan bilderna rullar in.</div>
          <button class="btn-mork liten" on:click={detektera}>Leta efter kort igen</button>
        {/if}
      </div>
      {#if canReview}
        <div class="mitt">
          <button class="btn-linje" on:click={goReview}>Klar — granska urvalet ({totalPicked}) ›</button>
        </div>
      {/if}
    {/if}

    <!-- ============ STEG: PLOCKA ============ -->
    {#if step === 'pick'}
      <div class="rad-rubrik">
        <span class="grondot"></span>
        <span class="rr-namn scd">{curCard.name}</span>
        <span class="rr-meta">{curCard.total} bilder på kortet · nyast först</span>
        <span class="vaxt"></span>
        <span class="rr-plock"><b>{curPickedN}</b> plockade på det här kortet</span>
      </div>
      <div class="rutnat plock">
        {#each curThumbs as t}
          <button class="ruta" class:on={t.on} class:laddar={!t.uri && t.path} style="background-image:{t.uri ? `url(${t.uri})` : tint(cur, t.i)}" on:click={() => togglePick(cur, t.i)}>
            {#if t.on}<span class="stjarna">★</span>{/if}
            <span class="dsc">{t.num}</span>
          </button>
        {/each}
      </div>
      <div class="hjalp">Klicka en bild för att plocka den · klicka igen för att ångra. Visar de senaste — resten av kortet rullar in under genomgången.</div>
      <div class="fot-rad">
        <button class="btn-mork" on:click={ejectCard}>⏏ Mata ut kortet</button>
        <span class="fot-hjalp">Urvalet ligger kvar — sätt i nästa kort,<br>eller granska när alla kort är genomgångna.</span>
        <span class="vaxt"></span>
        <button class="btn-linje" on:click={goReview}>Klar — granska ({totalPicked}) ›</button>
      </div>
    {/if}

    <!-- ============ STEG: GRANSKA (B2) ============ -->
    {#if step === 'review'}
      <div class="granska-rubrik">
        <span class="gr-h scd">Granska urvalet</span>
        <span class="gr-p">Kryssa bort det som inte ska med — sedan öppnas Lightroom med resten.</span>
      </div>
      {#each reviewGroups as g}
        <div class="grupp">
          <div class="grupp-lbl">{g.label}</div>
          <div class="rutnat granska">
            {#each g.thumbs as t}
              <button class="ruta gruta" class:av={t.off} style="background-image:{t.uri ? `url(${t.uri})` : tint(t.c, t.i)}" on:click={() => toggleRemoved(t.key)}>
                {#if t.off}<span class="kryss">✕</span>{:else}<span class="stjarna liten">★</span>{/if}
                <span class="dsc">{t.num}</span>
              </button>
            {/each}
          </div>
        </div>
      {/each}
      <div class="fot-rad">
        <button class="btn-mork" on:click={backToInsert}>‹ Fler kort</button>
        <span class="vaxt"></span>
        {#if removedN}<span class="bortkryss">{removedN} bortkryssade</span>{/if}
        <button class="btn-amber stor" on:click={openLightroom}>Öppna i Lightroom · {finalN} bilder</button>
      </div>
    {/if}

    <!-- ============ STEG: LIGHTROOM (B3) ============ -->
    {#if step === 'lr'}
      <div class="lr-kort">
        {#if lrPhase === 'fel'}
          <div class="lr-klar">
            <span class="lr-badge fel">!</span>
            <div class="lr-h scd">Exporten stannade</div>
          </div>
          <div class="lr-slut">{lrFel}</div>
          <div class="mitt"><button class="btn-amber liten" on:click={() => (step = 'review')}>‹ Tillbaka till granska</button></div>
        {:else}
          {#if lrPhase === 'running'}
            <div class="lr-h scd">Öppnar Lightroom …</div>
          {:else}
            <div class="lr-klar">
              <span class="lr-badge">✓</span>
              <div class="lr-h scd">Lightroom öppnat</div>
            </div>
          {/if}
          <div class="lr-steg">
            {#each lrSteps as st}
              <div class="lr-rad">
                <span class="lr-dot" class:done={st.done} class:active={st.active}>✓</span>
                <span class="lr-lbl" class:done={st.done} class:active={st.active}>{st.label}</span>
              </div>
            {/each}
          </div>
          {#if lrPhase === 'done'}
            <div class="lr-slut">{finalN} bilder kopierade från {doneCardsN} kort och öppnade i Lightroom.<br>{#if lrPath}<span class="lr-path">{lrPath}</span><br>{/if}Korten kan formateras när säkerhetskopian är verifierad.</div>
            <div class="mitt"><button class="btn-mork liten" on:click={restart}>Börja om</button></div>
          {/if}
        {/if}
      </div>
    {/if}
  </div>

  <!-- Footer: snabbväg, inte ett steg -->
  <div class="footer">
    <span class="footer-txt">Plocka direkt från minneskorten — Lightroom öppnas när urvalet är klart.</span>
    <span class="vaxt"></span>
    <button class="btn-mork" on:click={() => dispatch('navigera', 'gallra')}>Fortsätt till Gallra ›</button>
  </div>
</div>

<style>
  /* Medvetet mörk fältläges-panel — egen palett, oberoende av app-temat. */
  .sp {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    background: #0a0d11;
    color: #f3f5f7;
    font-family: Saira, sans-serif;
    box-sizing: border-box;
  }
  .scd { font-family: 'Saira Condensed', sans-serif; }
  .vaxt { flex: 1; }
  button { font-family: inherit; cursor: pointer; }

  /* Topp */
  .topp {
    flex: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: #0d1015;
    padding: 16px 26px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .titel { display: flex; align-items: center; gap: 12px; }
  .ikon {
    width: 38px; height: 38px; border-radius: 10px;
    background: rgba(240, 180, 90, 0.14); color: #f0b45a;
    display: flex; align-items: center; justify-content: center; flex: none;
  }
  .h1 { font-size: 20px; font-weight: 700; letter-spacing: 0.01em; }
  .fixtur { font-size: 11.5px; color: rgba(243, 245, 247, 0.5); }
  .stepper { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
  .fs {
    font-size: 10.5px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
    padding: 3px 10px; border-radius: 999px; border: 1px solid transparent;
    color: rgba(243, 245, 247, 0.3);
  }
  .fs.gjord { color: rgba(243, 245, 247, 0.6); }
  .fs.aktiv {
    font-weight: 700; color: #f0b45a;
    background: rgba(240, 180, 90, 0.14); border-color: rgba(240, 180, 90, 0.4);
  }
  .pil { color: rgba(243, 245, 247, 0.28); font-size: 11px; }

  .kropp { flex: 1; max-width: 1060px; width: 100%; margin: 0 auto; padding: 22px 26px 40px; box-sizing: border-box; }

  /* Urvals-rad */
  .urval {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    background: #12151b; border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px; padding: 12px 16px; margin-bottom: 18px;
  }
  .urval-lbl { font-size: 10.5px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: rgba(243, 245, 247, 0.45); }
  .chip {
    display: inline-flex; align-items: center; gap: 7px;
    background: #1b2028; border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 999px; padding: 4px 12px; font-size: 11.5px; font-weight: 600; color: rgba(243, 245, 247, 0.8);
  }
  .chip-dot { width: 7px; height: 7px; border-radius: 50%; background: #6fb35a; flex: none; }
  .chip.cur { background: rgba(240, 180, 90, 0.1); border-color: rgba(240, 180, 90, 0.4); color: #f0b45a; }
  .chip.cur .chip-dot { background: #f0b45a; }
  .tom { font-size: 12px; color: rgba(243, 245, 247, 0.4); }
  .total { font-size: 17px; font-weight: 700; color: #f0b45a; }

  /* Sätt i kort */
  .dropyta {
    border: 1.5px dashed rgba(255, 255, 255, 0.18); border-radius: 16px;
    padding: 46px 30px; text-align: center; background: rgba(255, 255, 255, 0.015);
  }
  .drop-ic { margin-bottom: 14px; }
  .drop-h { font-size: 22px; font-weight: 700; }
  .drop-p { font-size: 12.5px; color: rgba(243, 245, 247, 0.5); margin-top: 6px; line-height: 1.5; }
  .mitt { display: flex; justify-content: center; margin-top: 18px; }

  /* Knappar */
  .btn-amber { background: #f0b45a; color: #100c05; border: none; border-radius: 10px; padding: 12px 22px; font-size: 13.5px; font-weight: 700; margin-top: 20px; }
  .btn-amber.stor { padding: 13px 24px; font-size: 14px; margin-top: 0; }
  .btn-amber.liten { padding: 10px 18px; font-size: 12.5px; margin-top: 0; }
  .btn-linje { background: transparent; border: 1.5px solid #f0b45a; color: #f0b45a; border-radius: 10px; padding: 12px 24px; font-size: 13.5px; font-weight: 700; }
  .btn-mork { background: #12151b; border: 1px solid rgba(255, 255, 255, 0.16); color: #f3f5f7; border-radius: 10px; padding: 12px 20px; font-size: 13.5px; font-weight: 700; }
  .btn-mork.liten { padding: 10px 18px; font-size: 12.5px; font-weight: 600; border-radius: 9px; }

  /* Plocka */
  .rad-rubrik { display: flex; align-items: center; gap: 12px; margin-bottom: 13px; flex-wrap: wrap; }
  .grondot { width: 9px; height: 9px; border-radius: 50%; background: #6fb35a; box-shadow: 0 0 9px #6fb35a; flex: none; }
  .rr-namn { font-size: 18px; font-weight: 700; }
  .rr-meta { font-size: 12px; color: rgba(243, 245, 247, 0.5); }
  .rr-plock { font-size: 12.5px; color: rgba(243, 245, 247, 0.7); }
  .rr-plock b { color: #f0b45a; }

  .rutnat { display: grid; gap: 10px; }
  .rutnat.plock { grid-template-columns: repeat(5, 1fr); }
  .rutnat.granska { grid-template-columns: repeat(6, 1fr); gap: 9px; }
  .ruta {
    position: relative; aspect-ratio: 3 / 2; border-radius: 9px; overflow: hidden; padding: 0;
    background-size: cover; background-position: center;
    outline: 1px solid rgba(255, 255, 255, 0.09); outline-offset: -2px; border: none;
  }
  .ruta.on { outline: 2.5px solid #f0b45a; box-shadow: 0 0 14px rgba(240, 180, 90, 0.35); }
  .ruta.laddar { animation: puls 1.3s ease-in-out infinite; }
  @keyframes puls { 0%, 100% { opacity: 1; } 50% { opacity: 0.62; } }
  .ruta.gruta { border-radius: 8px; outline: 1px solid rgba(255, 255, 255, 0.12); outline-offset: -1px; }
  .ruta.gruta.av { outline: 1px solid rgba(224, 96, 127, 0.5); }
  .stjarna {
    position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border-radius: 50%;
    background: #f0b45a; color: #100c05; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
  }
  .stjarna.liten { top: 5px; right: 5px; width: 19px; height: 19px; font-size: 11px; background: rgba(10, 13, 17, 0.6); color: #f0b45a; }
  .kryss { position: absolute; inset: 0; background: rgba(10, 13, 17, 0.66); display: flex; align-items: center; justify-content: center; font-size: 19px; color: #e0607f; }
  .dsc { position: absolute; left: 7px; bottom: 6px; font-family: 'Saira Condensed', sans-serif; font-size: 10px; color: rgba(255, 255, 255, 0.55); text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7); }
  .hjalp { font-size: 11px; color: rgba(243, 245, 247, 0.4); margin-top: 10px; }

  .fot-rad { display: flex; align-items: center; gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08); flex-wrap: wrap; }
  .fot-hjalp { font-size: 11.5px; color: rgba(243, 245, 247, 0.45); line-height: 1.45; }
  .bortkryss { font-size: 12px; color: rgba(243, 245, 247, 0.5); }

  /* Granska */
  .granska-rubrik { display: flex; align-items: baseline; gap: 12px; margin-bottom: 5px; flex-wrap: wrap; }
  .gr-h { font-size: 20px; font-weight: 700; }
  .gr-p { font-size: 12px; color: rgba(243, 245, 247, 0.5); }
  .grupp { margin-top: 16px; }
  .grupp-lbl { font-size: 10.5px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: rgba(243, 245, 247, 0.45); margin-bottom: 9px; }

  /* Lightroom */
  .lr-kort { max-width: 520px; margin: 40px auto 0; background: #12151b; border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 16px; padding: 28px 30px; }
  .lr-h { font-size: 19px; font-weight: 700; text-align: center; margin-bottom: 20px; }
  .lr-klar { text-align: center; margin-bottom: 20px; }
  .lr-badge { display: inline-flex; width: 44px; height: 44px; border-radius: 50%; background: #6fb35a; color: #0a0d11; align-items: center; justify-content: center; font-size: 21px; font-weight: 700; margin-bottom: 10px; }
  .lr-badge.fel { background: #e0607f; }
  .lr-path { font-family: 'Saira Condensed', sans-serif; color: rgba(243, 245, 247, 0.7); font-size: 11px; word-break: break-all; }
  .lr-klar .lr-h { margin-bottom: 0; }
  .lr-steg { display: flex; flex-direction: column; gap: 15px; }
  .lr-rad { display: flex; align-items: center; gap: 12px; }
  .lr-dot { width: 18px; height: 18px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; background: transparent; color: transparent; border: 1.5px solid rgba(255, 255, 255, 0.2); }
  .lr-dot.active { background: #f0b45a; color: #0a0d11; border: none; }
  .lr-dot.done { background: #6fb35a; color: #0a0d11; border: none; }
  .lr-lbl { font-size: 12.5px; color: rgba(243, 245, 247, 0.4); }
  .lr-lbl.active { color: #f3f5f7; }
  .lr-lbl.done { color: rgba(243, 245, 247, 0.85); }
  .lr-slut { font-size: 11.5px; color: rgba(243, 245, 247, 0.5); text-align: center; margin-top: 18px; line-height: 1.5; }

  /* Footer */
  .footer { flex: none; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 14px 26px; border-top: 1px solid rgba(255, 255, 255, 0.08); background: #0d1015; }
  .footer-txt { font-size: 12px; color: rgba(243, 245, 247, 0.55); }
</style>
