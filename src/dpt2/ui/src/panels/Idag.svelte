<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte'
  import { hamtaIdag, aktivMatch } from '../lib/api.js'
  import { oppna, tillbaka, idagOppet } from '../lib/oppna.js'
  const dispatch = createEventDispatcher()

  // En berörd post → dit direkt; flera → fäll ut listan; ingen → panelen.
  // Utfällningen persistas (idagOppet) så listan finns kvar när man kommer
  // tillbaka och plockar nästa post.
  function oppnaKrav(k) {
    const n = (k.poster || []).length
    if (n === 1) return oppnaPost(k.poster[0])
    if (n > 1) { $idagOppet = $idagOppet === k.typ ? null : k.typ; return }
    dispatch('navigera', k.dest)
  }
  function oppnaPost(p) {
    tillbaka.set('idag')        // toppradens "← Tillbaka" hittar hem
    oppna(p.mal, p.id)          // målpanelen läser storen och öppnar posten
    dispatch('navigera', p.mal)
  }

  // Kanoniska kategorifärger (D16 §C: prick/kant, aldrig fylld bakgrund) —
  // speglar Fotojobb.svelte:s KAT_FARG så Idag och listan aldrig glider isär.
  const KAT_FARG = { Sport: '#2f7cb0', Landskap: '#c9871f', Människor: '#c9657f', Film: '#8a6fb0' }
  // Inkorg-prickens färg per nivå (delar tokens med resten av appen).
  const NIVAFARG = { info: 'var(--info)', ok: 'var(--ok)', danger: 'var(--danger)',
                     warn: 'var(--warn)', rose: 'var(--rose)' }

  let data = null
  let aktiv = null
  let laddar = true

  async function ladda() {
    ;[data, aktiv] = await Promise.all([
      hamtaIdag().catch(() => null),
      aktivMatch().catch(() => null),
    ])
    laddar = false
  }
  // Realtid: räkna om åtgärdskön när jobb/plats/idag ändrats i molnet (t.ex. en
  // plats iOS satte får "plats saknas" att försvinna) — auto, ingen omladdning.
  function paAndring(e) {
    const d = e.detail || []
    if (d.includes('jobb') || d.includes('jobbplats') || d.includes('idag')) ladda()
  }
  onMount(async () => {
    await ladda()
    window.addEventListener('dpt-andring', paAndring)
  })
  onDestroy(() => window.removeEventListener('dpt-andring', paAndring))

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
    // Change 4: bara Idag/Imorgon som relativ text — allt längre bort som datum
    // (inga "Om 3 dgr"). Change 5: heldag bär veckodag, aldrig klockslag.
    if (dagar <= 0) return tid ? `Idag ${tid}` : 'Idag'
    if (dagar === 1) return tid ? `Imorgon ${tid}` : 'Imorgon'
    if (j.all_day) {
      const v = d.toLocaleDateString('sv-SE', { weekday: 'long' })
      const dat = d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' })
      return `${v[0].toUpperCase()}${v.slice(1)} ${dat}`   // "Fredag 24 okt"
    }
    return d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' }) + (tid ? ` · ${tid}` : '')
  }

  const aktivEtikett = (m) =>
    m && m.lag_hemma ? `${m.lag_hemma} – ${m.lag_borta}` : (m && m.title) || ''
</script>

<div class="idag">
  <header>
    <div class="hleft">
      <div class="datum scd">{datumrad}</div>
      <h1 class="scd">{halsning()}</h1>
      {#if data}
        <div class="sum">
          {data.kraver.length} {data.kraver.length === 1 ? 'sak väntar' : 'saker väntar'} på dig
          · {data.antal_kommande_matcher} kommande matcher
        </div>
      {/if}
    </div>
    <button class="nyprim" on:click={() => dispatch('navigera', 'fotojobb')}>+ Nytt fotojobb</button>
  </header>

  {#if aktiv}
    <button class="resume" on:click={() => dispatch('navigera', 'matcher')}>
      <span class="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></span>
      <span class="rtext">
        <span class="rlbl">Fortsätt där du var</span>
        <span class="rval scd">{aktivEtikett(aktiv)}</span>
      </span>
      <span class="rsenast">senast öppnad</span>
      <span class="ropen">Öppna</span>
    </button>
  {/if}

  <div class="grid">
    <!-- Vänster: åtgärdskö + närmast på tur -->
    <section class="vanster">
      <div class="kort">
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
              <button class="cta" on:click={() => oppnaKrav(k)}>
                {(k.poster && k.poster.length > 1) ? ($idagOppet === k.typ ? 'Dölj' : 'Visa') : k.cta}
              </button>
            </div>
            {#if $idagOppet === k.typ && k.poster}
              <div class="undlist">
                {#each k.poster as p}
                  <button class="undrad" on:click={() => oppnaPost(p)}>
                    <span class="undtitel">{p.titel}</span>
                    <span class="undpil">›</span>
                  </button>
                {/each}
              </div>
            {/if}
          {/each}
        {:else}
          <div class="tom">Allt i ordning — inget väntar.</div>
        {/if}
      </div>

      <div class="kort">
        <div class="korthd">
          <h2 class="scd">Närmast på tur</h2>
          <button class="lank" on:click={() => { tillbaka.set('idag'); dispatch('navigera', 'fotojobb') }}>Till fotojobb →</button>
        </div>
        {#if data && data.narmast.length}
          {#each data.narmast as j}
            <button class="jobb" style="border-left-color: {KAT_FARG[j.kategori] || 'var(--div)'}"
              on:click={() => oppnaPost(j)}>
              <span class="jtitel">{j.titel}</span>
              <span class="jsub">
                {narText(j)}{#if j.plats} · {j.plats}{/if}{#if j.tavling_namn} · <span class="delav">Del av {j.tavling_namn}</span>{/if}
              </span>
            </button>
          {/each}
        {:else}
          <div class="tom">Inga kommande jobb.</div>
        {/if}
      </div>
    </section>

    <!-- Höger: statistik + inkorg & svar -->
    <section class="hoger">
      <div class="kort">
        <div class="korthd"><h2 class="scd">Statistik · denna månad</h2></div>
        {#if data && data.statistik}
          <div class="statgrid">
            {#each data.statistik as s}
              <button class="stat" on:click={() => dispatch('navigera', s.dest)}>
                <span class="stal scd">{s.tal}</span>
                <span class="setikett">{s.etikett}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="kort">
        <div class="korthd"><h2 class="scd">Inkorg & svar</h2></div>
        {#if data && data.inkorg && data.inkorg.length}
          {#each data.inkorg as i}
            <button class="inrad" on:click={() => i.id && i.mal ? oppnaPost(i) : dispatch('navigera', i.dest || 'fotojobb')}>
              <span class="prick" style="background: {NIVAFARG[i.niva] || 'var(--t-help)'}"></span>
              <span class="intext">
                <span class="intitel">{i.titel}</span>
                <span class="insub">{i.sub}</span>
              </span>
              {#if i.nar}<span class="inar">{i.nar}</span>{/if}
            </button>
          {/each}
        {:else}
          <div class="tom">Inga svar just nu.</div>
        {/if}
      </div>
    </section>
  </div>
</div>

<style>
  .idag { padding: 26px 30px 40px; max-width: 1180px; }
  header { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
  .hleft { margin-right: auto; }
  .datum { font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--t-caps); }
  h1 { font-size: 32px; font-weight: 700; color: var(--t-head); margin: 4px 0 6px; }
  .sum { font-size: 13.5px; color: var(--t-mut); }
  .nyprim { flex: none; margin-top: 20px; padding: 10px 16px; border: 0; border-radius: 10px;
    background: var(--acc); color: var(--kort); font-size: 13.5px; font-weight: 700; }
  .nyprim:hover { filter: brightness(1.05); }

  .resume { display: flex; align-items: center; gap: 14px; width: 100%; text-align: left;
    padding: 14px 16px; border: 1px solid var(--div); border-left: 3px solid var(--info);
    border-radius: var(--r); background: var(--kort); margin-bottom: 22px; }
  .resume:hover { background: var(--div3); }
  .play { width: 40px; height: 40px; flex: none; border-radius: 10px;
    background: var(--info-soft); color: var(--info);
    display: inline-flex; align-items: center; justify-content: center; }
  .play svg { width: 18px; height: 18px; }
  .rtext { display: flex; flex-direction: column; gap: 2px; margin-right: auto; }
  .rlbl { font-size: 9.5px; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--t-mut); }
  .rval { font-size: 17px; font-weight: 700; color: var(--t-head); }
  .rsenast { font-size: 11.5px; color: var(--t-help); }
  .ropen { flex: none; padding: 6px 16px; border-radius: 8px; background: var(--acc-soft);
    color: var(--acc); font-size: 12.5px; font-weight: 700; }

  .grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 18px; align-items: start; }
  .vanster, .hoger { display: flex; flex-direction: column; gap: 18px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    padding: 16px 18px; box-shadow: var(--skugga); }
  .korthd { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
  .korthd h2 { font-size: 15px; font-weight: 700; color: var(--t-head); margin: 0; }
  .badge { min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px;
    background: var(--acc-soft); color: var(--acc); font-size: 12px; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center; }
  .lank { margin-left: auto; border: 0; background: transparent; color: var(--acc);
    font-size: 12.5px; font-weight: 600; }
  .lank:hover { text-decoration: underline; }

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

  /* Utfälld lista när flera poster berörs — var och en öppnar sin post. */
  .undlist { display: flex; flex-direction: column; gap: 4px; padding: 2px 0 8px 23px; }
  .undrad { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
    padding: 8px 12px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-body); font-size: 13px; font-weight: 500; }
  .undrad:hover { border-color: var(--acc-border); color: var(--acc); }
  .undtitel { margin-right: auto; }
  .undpil { color: var(--t-help); font-weight: 700; }

  .jobb { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px;
    border-left: 3px solid var(--div); border-radius: 8px; background: var(--panel);
    margin-bottom: 8px; width: 100%; text-align: left; border-top: 0; border-right: 0;
    border-bottom: 0; font: inherit; cursor: pointer; }
  .jobb:hover { background: color-mix(in srgb, var(--acc) 8%, var(--panel)); }
  .jobb:last-child { margin-bottom: 0; }
  .jtitel { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .jsub { font-size: 11.5px; color: var(--t-mut); }
  .delav { color: var(--t-help); }

  /* Statistik — 2×2 rutnät med stora tal. */
  .statgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .stat { display: flex; flex-direction: column; gap: 2px; align-items: flex-start;
    padding: 12px 14px; border: 1px solid var(--div); border-radius: 10px;
    background: var(--panel); text-align: left; }
  .stat:hover { border-color: var(--acc-border); }
  .stal { font-size: 26px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .setikett { font-size: 11.5px; color: var(--t-mut); }

  /* Inkorg & svar — prick + titel/sub + tid. */
  .inrad { display: flex; align-items: center; gap: 11px; width: 100%; text-align: left;
    padding: 10px 2px; border: 0; border-top: 1px solid var(--div); background: transparent; }
  .inrad:first-of-type { border-top: 0; }
  .inrad:hover .intitel { color: var(--acc); }
  .intext { display: flex; flex-direction: column; gap: 1px; margin-right: auto; }
  .intitel { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .insub { font-size: 11.5px; color: var(--t-mut); }
  .inar { font-size: 10.5px; color: var(--t-help); flex: none; }

  .tom { font-size: 13px; color: var(--t-mut); padding: 8px 2px; }
</style>
