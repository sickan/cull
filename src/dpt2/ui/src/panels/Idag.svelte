<script>
  import { createEventDispatcher, onMount } from 'svelte'
  import { hamtaIdag, aktivMatch } from '../lib/api.js'
  const dispatch = createEventDispatcher()

  // Kanoniska kategorifärger (D16 §C: prick/kant, aldrig fylld bakgrund) —
  // speglar Fotojobb.svelte:s KAT_FARG så Idag och listan aldrig glider isär.
  const KAT_FARG = { Sport: '#2f7cb0', Landskap: '#c9871f', Människor: '#c9657f', Film: '#8a6fb0' }

  let data = null
  let aktiv = null
  let laddar = true

  onMount(async () => {
    ;[data, aktiv] = await Promise.all([
      hamtaIdag().catch(() => null),
      aktivMatch().catch(() => null),
    ])
    laddar = false
  })

  const nu = new Date()
  function halsning() {
    const h = nu.getHours()
    if (h < 5) return 'Godnatt'
    if (h < 10) return 'God morgon'
    if (h < 12) return 'God förmiddag'
    if (h < 17) return 'God dag'
    if (h < 22) return 'God kväll'
    return 'Godnatt'
  }
  const datumrad = nu.toLocaleDateString('sv-SE',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  // Relativ tid till ett jobb (kort-etikett i Närmast på tur).
  function narText(j) {
    const s = j.start_at
    if (!s) return ''
    const d = new Date(s.length <= 10 ? s + 'T00:00' : s)
    if (isNaN(d)) return ''
    const mid = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate())
    const dagar = Math.round((mid(d) - mid(nu)) / 86400000)
    const tid = (!j.all_day && s.includes('T')) ? s.split('T')[1].slice(0, 5) : ''
    if (dagar <= 0) return tid ? `Idag ${tid}` : 'Idag'
    if (dagar === 1) return tid ? `Imorgon ${tid}` : 'Imorgon'
    if (dagar < 7) return `Om ${dagar} dgr${tid ? ' · ' + tid : ''}`
    return d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' }) + (tid ? ` · ${tid}` : '')
  }

  const aktivEtikett = (m) =>
    m && m.lag_hemma ? `${m.lag_hemma} – ${m.lag_borta}` : (m && m.title) || ''
</script>

<div class="idag">
  <header>
    <div class="datum scd">{datumrad}</div>
    <h1 class="scd">{halsning()}</h1>
    {#if data}
      <div class="sum">
        {data.kraver.length} {data.kraver.length === 1 ? 'sak väntar' : 'saker väntar'} på dig
        · {data.antal_kommande_matcher} kommande matcher
      </div>
    {/if}
  </header>

  {#if aktiv}
    <button class="resume" on:click={() => dispatch('navigera', 'matcher')}>
      <span class="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></span>
      <span class="rtext">
        <span class="rlbl">Fortsätt där du var</span>
        <span class="rval scd">{aktivEtikett(aktiv)}</span>
      </span>
    </button>
  {/if}

  <div class="grid">
    <section class="kort">
      <div class="korthd">
        <h2 class="scd">Kräver åtgärd</h2>
        {#if data}<span class="badge">{data.kraver.length}</span>{/if}
      </div>
      {#if laddar}
        <div class="tom">Laddar…</div>
      {:else if data && data.kraver.length}
        {#each data.kraver as k}
          <div class="rad">
            <span class="prick" style="background: var(--{k.niva})"></span>
            <span class="radtext">
              <span class="radtitel">{k.titel}</span>
              <span class="radsub">{k.sub}</span>
            </span>
            <button class="cta" on:click={() => dispatch('navigera', k.dest)}>{k.cta}</button>
          </div>
        {/each}
      {:else}
        <div class="tom">Allt i ordning — inget väntar.</div>
      {/if}
    </section>

    <section class="hoger">
      <div class="kort">
        <div class="korthd"><h2 class="scd">Närmast på tur</h2></div>
        {#if data && data.narmast.length}
          {#each data.narmast as j}
            <div class="jobb" style="border-left-color: {KAT_FARG[j.kategori] || 'var(--div)'}">
              <span class="jtitel">{j.titel}</span>
              <span class="jsub">
                {narText(j)}{#if j.plats} · {j.plats}{/if}{#if j.tavling_namn} · <span class="delav">Del av {j.tavling_namn}</span>{/if}
              </span>
            </div>
          {/each}
        {:else}
          <div class="tom">Inga kommande jobb.</div>
        {/if}
      </div>

      <div class="kort">
        <div class="korthd"><h2 class="scd">Snabbvägar</h2></div>
        <div class="snabbrad">
          <button on:click={() => dispatch('navigera', 'fotojobb')}>Fotojobb</button>
          <button on:click={() => dispatch('navigera', 'gallra')}>Gallra</button>
          <button on:click={() => dispatch('navigera', 'leverera')}>Leverera</button>
          <button on:click={() => dispatch('navigera', 'publicera')}>Publicera</button>
        </div>
      </div>
    </section>
  </div>
</div>

<style>
  .idag { padding: 26px 30px 40px; max-width: 1100px; }
  header { margin-bottom: 20px; }
  .datum { font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--t-caps); }
  h1 { font-size: 32px; font-weight: 700; color: var(--t-head); margin: 4px 0 6px; }
  .sum { font-size: 13.5px; color: var(--t-mut); }

  .resume { display: flex; align-items: center; gap: 14px; width: 100%; text-align: left;
    padding: 14px 16px; border: 1px solid var(--div); border-left: 3px solid var(--info);
    border-radius: var(--r); background: var(--kort); margin-bottom: 22px; }
  .resume:hover { background: var(--div3); }
  .play { width: 40px; height: 40px; flex: none; border-radius: 10px;
    background: var(--info-soft); color: var(--info);
    display: inline-flex; align-items: center; justify-content: center; }
  .play svg { width: 18px; height: 18px; }
  .rtext { display: flex; flex-direction: column; gap: 2px; }
  .rlbl { font-size: 9.5px; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--t-mut); }
  .rval { font-size: 17px; font-weight: 700; color: var(--t-head); }

  .grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 18px; align-items: start; }
  .hoger { display: flex; flex-direction: column; gap: 18px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    padding: 16px 18px; box-shadow: var(--skugga); }
  .korthd { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
  .korthd h2 { font-size: 15px; font-weight: 700; color: var(--t-head); margin: 0; }
  .badge { min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px;
    background: var(--acc-soft); color: var(--acc); font-size: 12px; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center; }

  .rad { display: flex; align-items: center; gap: 12px; padding: 11px 2px;
    border-top: 1px solid var(--div); }
  .rad:first-of-type { border-top: 0; }
  .prick { width: 11px; height: 11px; border-radius: 50%; flex: none; }
  .radtext { display: flex; flex-direction: column; gap: 2px; margin-right: auto; }
  .radtitel { font-size: 14px; font-weight: 600; color: var(--t-head); }
  .radsub { font-size: 12px; color: var(--t-mut); }
  .cta { flex: none; padding: 6px 14px; border: 1px solid var(--acc-border);
    border-radius: 8px; background: transparent; color: var(--acc);
    font-size: 12.5px; font-weight: 600; }
  .cta:hover { background: var(--acc-soft); }

  .jobb { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px;
    border-left: 3px solid var(--div); border-radius: 8px; background: var(--panel);
    margin-bottom: 8px; }
  .jobb:last-child { margin-bottom: 0; }
  .jtitel { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .jsub { font-size: 11.5px; color: var(--t-mut); }
  .delav { color: var(--t-help); }

  .snabbrad { display: flex; flex-wrap: wrap; gap: 8px; }
  .snabbrad button { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-body); font-size: 13px; font-weight: 600; }
  .snabbrad button:hover { border-color: var(--acc-border); color: var(--acc); }

  .tom { font-size: 13px; color: var(--t-mut); padding: 8px 2px; }
</style>
