<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import {
    listaMatcher, hamtaMatch, sparaMatch, hamtaTrupp, sattAktivMatch,
    lasLineup, valjFil, listaTavlingar, listaLag, listaLagForTavling,
    listaUrval, sparaFotojobb,
  } from '../lib/api.js'
  import Combobox from '../lib/Combobox.svelte'

  const dispatch = createEventDispatcher()

  let matcher = []
  let tavlingar = []
  let lagAlla = []
  let lagForTavling = []
  let projekt = []
  let laddar = true
  let sportFilter = 'alla'
  let oppen = null
  let utkast = null
  let iKalender = new Set()

  const SPORTER = ['alla', 'fotboll', 'handboll', 'volleyboll', 'beachvolley', 'tennis']
  const SPORT_ETIKETT = { fotboll: 'Fotboll', handboll: 'Handboll', volleyboll: 'Volleyboll', beachvolley: 'Beachvolley', tennis: 'Tennis' }
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }
  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const SPORT_FARG = '#2F7CB0'

  onMount(async () => {
    ;[matcher, tavlingar, lagAlla, projekt] = await Promise.all(
      [listaMatcher(), listaTavlingar(), listaLag(), listaUrval()])
    laddar = false
  })

  $: filtrerade = matcher.filter((m) => sportFilter === 'alla' || m.sport === sportFilter)
  $: grupper = gruppera(filtrerade)
  $: lagVal = (lagForTavling.length ? lagForTavling : lagAlla).map((l) => ({ id: l.id, namn: l.namn }))
  $: tavlingVal = tavlingar.map((t) => ({ id: t.id, namn: t.namn }))
  $: hemSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'hemma')
  $: bortaSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'borta')

  const del = (iso) => (iso || '').split('T')[0].split('-').map(Number)
  function periodText(t) {
    const f = (t.fran || '').split('-'), ti = (t.till || '').split('-')
    if (f.length < 2 || ti.length < 2) return ''
    const yr = ti[0] === f[0] ? f[0] : `${f[0]}–${ti[0]}`
    return `${MK[+f[1] - 1]}–${MK[+ti[1] - 1]} ${yr}`
  }
  function initialer(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }
  function _lum(hex) {
    const h = (hex || '').replace('#', '')
    if (h.length < 3) return 1
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
    return (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  }
  const brickStil = (f) => `background:${f || '#c9bfa8'};color:${_lum(f || '#c9bfa8') > 0.62 ? 'rgba(35,32,26,.85)' : '#fff'}`
  function fargForLag(namn) {
    const l = lagAlla.find((x) => x.namn === namn)
    return l ? (l.stall_hemma || l.profilfarg) : ''
  }

  function gruppera(lista) {
    const m = new Map()
    for (const x of lista) {
      const k = x.tavling_id || x.liga || 'ovrigt'
      if (!m.has(k)) m.set(k, { key: k, namn: x.liga || 'Övriga matcher', matcher: [] })
      m.get(k).matcher.push(x)
    }
    return [...m.values()].map((g) => {
      const t = tavlingar.find((tv) => tv.id === g.key || tv.namn === g.namn) || {}
      return { ...g, badge: initialer(g.namn), typ: TYP_ETIKETT[t.typ] || 'Liga',
        meta: [SPORT_ETIKETT[t.sport] || '', periodText(t), t.ort].filter(Boolean).join(' · ') }
    })
  }

  async function toggla(m) {
    if (oppen === m.id) { oppen = null; utkast = null; lagForTavling = []; return }
    oppen = m.id
    utkast = await hamtaMatch(m.id)
    await laddaLagForTavling(utkast.liga)
  }
  async function laddaLagForTavling(ligaNamn) {
    const t = tavlingar.find((x) => x.namn === ligaNamn)
    lagForTavling = t ? await listaLagForTavling(t.id) : []
  }

  function nyMatch() {
    const tmp = { id: 'ny-' + Date.now(), datum: '', tid: '', arena: '', status: 'kommande', resultat: '', sport: '', lag_hemma: '', lag_borta: '', liga: '' }
    matcher = [{ ...tmp, trupp_n: 0 }, ...matcher]
    oppen = tmp.id; utkast = { ...tmp, spelare: [] }; lagForTavling = []
  }

  async function valjTavling(o) {
    utkast.liga = o.namn
    const t = tavlingar.find((x) => x.id === o.id)
    if (t?.sport) utkast.sport = t.sport
    await laddaLagForTavling(o.namn)
  }
  const skapaTavling = (namn) => { utkast.liga = namn; lagForTavling = [] }
  const valjHemma = (o) => { utkast.lag_hemma = o.namn }
  const valjBorta = (o) => { utkast.lag_borta = o.namn }
  const arMatch = () => !utkast || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))

  let hamtar = false
  async function lasUttaget() {
    if (arMatch()) return
    const f = await valjFil('Välj laguppställnings-ark (bild/PDF)')
    if (!f.ok) return
    hamtar = true
    const res = await lasLineup(utkast.id, f.path)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }
  async function hamtaTruppen() {
    if (arMatch()) return
    hamtar = true
    const res = await hamtaTrupp(utkast.id)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }

  async function laggIKalender(u) {
    const start = u.datum ? `${u.datum}T${u.tid || '00:00'}:00` : ''
    if (!start) return
    await sparaFotojobb({ title: `${u.lag_hemma || ''} – ${u.lag_borta || ''}`.trim(),
      start_at: start, end_at: start, location: u.arena || '', category: 'Sport', all_day: false })
    iKalender = new Set(iKalender).add(u.id)
  }

  async function spara() {
    const m = { ...utkast }
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) delete m.id
    await sparaMatch(m)
    ;[matcher, lagAlla] = await Promise.all([listaMatcher(), listaLag()])
    oppen = null; utkast = null; lagForTavling = []
  }
  function aktivera(m) {
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) return
    dispatch('aktiverad', m); sattAktivMatch(m.id)
  }
  function aterUppta() { dispatch('navigera', 'gallra') }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Matcher</h1>
    <span class="sub">Planera kommande matcher och återuppta tidigare projekt</span>
  </header>

  <div class="filterrad">
    <div class="caps">Kommande</div>
    <div class="chips">
      {#each SPORTER as s}
        <button class="chip" class:on={sportFilter === s} on:click={() => (sportFilter = s)}>{s === 'alla' ? 'Alla' : SPORT_ETIKETT[s]}</button>
      {/each}
    </div>
  </div>

  {#if laddar}
    <p class="tom">Laddar matcher…</p>
  {:else}
    <div class="grupper">
      {#each grupper as g (g.key)}
        <div class="grupp">
          <div class="ghuvud">
            <span class="glogo scd" style="background:{SPORT_FARG}">{g.badge}</span>
            <div class="gtxt">
              <div class="gnamn">{g.namn}</div>
              <div class="gmeta">{g.meta}</div>
            </div>
            <span class="gtyp">{g.typ}</span>
          </div>

          <div class="matcher">
            {#each g.matcher as m (m.id)}
              <div class="match">
                <button class="rad" on:click={() => toggla(m)}>
                  <div class="datum scd">
                    <div class="d">{del(m.datum)[2] || '–'}</div>
                    <div class="mon">{del(m.datum).length === 3 ? MK[del(m.datum)[1] - 1] : ''}</div>
                  </div>
                  <div class="fixtur">
                    <div class="fx scd">{m.lag_hemma} – {m.lag_borta}</div>
                    <div class="fmeta">{[SPORT_ETIKETT[m.sport] || '', m.arena, m.tid].filter(Boolean).join(' · ')}</div>
                  </div>
                  {#if m.status === 'avslutad' && m.resultat}
                    <span class="status res scd">{m.resultat}</span>
                  {:else}
                    <span class="status" class:klar={m.trupp_n > 0}>{m.trupp_n > 0 ? 'Roster klar' : 'Planera'}</span>
                  {/if}
                  <span class="chev" class:upp={oppen === m.id}>›</span>
                </button>

                {#if oppen === m.id && utkast}
                  <div class="editor">
                    <div class="rad2">
                      <label>Hemmalag
                        <Combobox options={lagVal} value={utkast.lag_hemma} placeholder="Välj lag…"
                          on:pick={(e) => valjHemma(e.detail)} on:create={(e) => (utkast.lag_hemma = e.detail)} />
                      </label>
                      <label>Bortalag
                        <Combobox options={lagVal} value={utkast.lag_borta} placeholder="Välj lag…"
                          on:pick={(e) => valjBorta(e.detail)} on:create={(e) => (utkast.lag_borta = e.detail)} />
                      </label>
                    </div>
                    <label class="full">Tävling
                      <Combobox options={tavlingVal} value={utkast.liga} placeholder="Välj tävling…"
                        on:pick={(e) => valjTavling(e.detail)} on:create={(e) => skapaTavling(e.detail)} />
                    </label>
                    <div class="rad3">
                      <input bind:value={utkast.datum} placeholder="ÅÅÅÅ-MM-DD" />
                      <input bind:value={utkast.tid} placeholder="HH:MM" />
                      <input bind:value={utkast.arena} placeholder="Arena" />
                    </div>

                    <div class="caps2">Laguppställning per lag</div>
                    <div class="lagbox2">
                      {#each [{ sida: 'hemma', namn: utkast.lag_hemma, lista: hemSpelare }, { sida: 'borta', namn: utkast.lag_borta, lista: bortaSpelare }] as kol}
                        <div class="lbox">
                          <div class="lhuvud">
                            <span class="lbricka" style={brickStil(fargForLag(kol.namn))}>{initialer(kol.namn)}</span>
                            <div class="lnamn-wrap">
                              <div class="lnamn scd">{kol.namn || (kol.sida === 'hemma' ? 'Hemmalag' : 'Bortalag')}</div>
                              <div class="lsub">{kol.sida === 'hemma' ? 'Hemma' : 'Borta'} · {kol.lista.length} spelare</div>
                            </div>
                          </div>
                          {#if kol.lista.length}
                            <div class="spelare">
                              {#each kol.lista as p}<span class="sp" class:start={p.start}>{#if p.nr}<b>{p.nr}</b>{/if} {p.namn}</span>{/each}
                            </div>
                          {/if}
                          <button class="lbtn" on:click={lasUttaget} disabled={hamtar || arMatch()}>Läs in uttaget lag…</button>
                        </div>
                      {/each}
                    </div>
                    <div class="hint">Läs blad/CSV/foto — spelarna matchas mot respektive lags trupp. <button class="lank" on:click={hamtaTruppen} disabled={hamtar || arMatch()}>{hamtar ? 'Hämtar…' : 'Hämta trupp automatiskt'}</button></div>

                    <div class="gcalkort">
                      <span class="gcalik">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                      </span>
                      <div class="gcaltxt">
                        <div class="gt">Lägg i kalender</div>
                        <div class="gs">Lägg matchen i din Google Calendar så du har koll på uppdraget</div>
                      </div>
                      <button class="gcalbtn" class:i={iKalender.has(utkast.id)} on:click={() => laggIKalender(utkast)} disabled={arMatch()}>
                        {iKalender.has(utkast.id) ? 'I kalendern ✓' : 'Lägg i kalender ›'}
                      </button>
                    </div>

                    <div class="knappar">
                      <button class="prim" on:click={() => aktivera(utkast)}>Aktivera match ›</button>
                      <button class="sek" on:click={spara}>Spara</button>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}

      <button class="ny" on:click={nyMatch}>+ Ny match</button>
    </div>

    {#if projekt.length}
      <div class="caps proj">Tidigare projekt</div>
      <div class="projgrid">
        {#each projekt as pr (pr.id)}
          <button class="projkort" on:click={aterUppta}>
            <div class="projbild"><span>{(pr.skapad || '').split(' ')[0]}</span></div>
            <div class="projtxt">
              <div class="projnamn">{pr.lag_hemma ? `${pr.lag_hemma} – ${pr.lag_borta}` : (pr.kalla || 'Urval').split('/').pop()}</div>
              <div class="projsub">{[pr.kamera, pr.bilder ? pr.bilder + ' bilder' : '', pr.status].filter(Boolean).join(' · ')}</div>
              <div class="projater">Återuppta ›</div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 920px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .filterrad { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin: 20px 2px 12px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: var(--t-caps); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { padding: 5px 13px; border: 1px solid var(--div); border-radius: 999px; background: var(--kort);
    color: var(--t-mut); font-size: 12.5px; }
  .chip.on { background: var(--acc); border-color: var(--acc); color: #fff; font-weight: 600; }

  .grupper { display: flex; flex-direction: column; gap: 20px; }
  .ghuvud { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .glogo { width: 34px; height: 34px; border-radius: 8px; color: #fff; display: flex; align-items: center;
    justify-content: center; flex: none; font-size: 12px; font-weight: 700; }
  .gtxt { flex: 1; min-width: 0; }
  .gnamn { font-size: 14px; font-weight: 600; color: var(--t-head); }
  .gmeta { font-size: 11.5px; color: var(--t-mut); }
  .gtyp { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--t-mut); background: var(--div3); padding: 3px 9px; border-radius: 6px; flex: none; }

  .matcher { display: flex; flex-direction: column; gap: 10px; }
  .match { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); overflow: hidden; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%; padding: 12px 14px; border: 0;
    background: transparent; text-align: left; }
  .rad:hover { background: var(--div3); }
  .datum { width: 50px; flex: none; text-align: center; background: var(--acc-soft); border-radius: 9px; padding: 7px 0; }
  .datum .d { font-size: 23px; font-weight: 700; color: var(--acc); line-height: 1; }
  .datum .mon { font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--acc); margin-top: 2px; }
  .fixtur { flex: 1; min-width: 0; }
  .fx { font-size: 17px; font-weight: 700; color: var(--t-head); }
  .fmeta { font-size: 12px; color: var(--t-mut); margin-top: 2px; }
  .status { font-size: 13px; font-weight: 600; color: var(--t-mut); flex: none; }
  .status.klar { color: var(--ok); }
  .status.res { font-size: 20px; font-weight: 700; color: var(--t-head); }
  .chev { width: 18px; text-align: center; color: var(--t-mut); font-size: 17px; transition: transform 0.15s; flex: none; }
  .chev.upp { transform: rotate(90deg); }

  .editor { border-top: 1px solid var(--div3); padding: 16px 14px; display: flex; flex-direction: column; gap: 12px; }
  .rad2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .rad3 { display: flex; gap: 10px; }
  .rad3 input:nth-child(1) { width: 130px; flex: none; }
  .rad3 input:nth-child(2) { width: 90px; flex: none; }
  .rad3 input:nth-child(3) { flex: 1; min-width: 0; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  label.full { width: 100%; }
  input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel);
    color: var(--t-head); font-size: 13px; font-weight: 400; text-transform: none; letter-spacing: 0; outline: none; }
  input:focus { border-color: var(--acc); }
  .caps2 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-top: 4px; }

  .lagbox2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .lbox { border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .lhuvud { display: flex; align-items: center; gap: 9px; }
  .lbricka { width: 30px; height: 30px; border-radius: 50%; flex: none; display: inline-flex; align-items: center;
    justify-content: center; font-family: var(--font-c); font-size: 11px; font-weight: 700; }
  .lnamn-wrap { min-width: 0; }
  .lnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lsub { font-size: 10.5px; color: var(--t-mut); }
  .spelare { display: flex; flex-wrap: wrap; gap: 5px; }
  .sp { font-size: 11.5px; padding: 2px 8px; border-radius: 999px; background: var(--div3); color: var(--t-mut); }
  .sp.start { background: var(--acc-soft); color: var(--acc); }
  .sp b { color: var(--t-head); }
  .lbtn { width: 100%; background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 7px 10px;
    font-size: 12px; color: var(--t-mut); }
  .lbtn:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .lbtn:disabled { opacity: 0.5; }
  .hint { font-size: 10.5px; color: var(--t-help); line-height: 1.45; }
  .lank { border: 0; background: none; color: var(--acc); font-size: 10.5px; font-weight: 600; padding: 0; }
  .lank:disabled { opacity: 0.5; }

  .gcalkort { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--div3);
    border-radius: 10px; background: var(--panel); }
  .gcalik { width: 36px; height: 36px; border-radius: 9px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .gcalik svg { width: 18px; height: 18px; }
  .gcaltxt { flex: 1; min-width: 0; }
  .gt { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .gs { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }
  .gcalbtn { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 14px; font-size: 13px; font-weight: 600; flex: none; }
  .gcalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .gcalbtn:disabled { opacity: 0.5; }

  .knappar { display: flex; gap: 10px; }
  .prim { padding: 9px 16px; border: 0; border-radius: 7px; background: var(--acc); color: #fff; font-size: 13px; font-weight: 600; }
  .sek { padding: 9px 14px; border: 1px solid var(--div); border-radius: 7px; background: var(--kort); color: var(--t-head); font-size: 13px; }

  .ny { padding: 14px; width: 100%; border: 1.5px dashed var(--div); border-radius: var(--r);
    background: transparent; color: var(--t-mut); font-size: 13px; font-weight: 500; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }

  .proj { margin: 26px 2px 12px; }
  .projgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .projkort { border: 1px solid var(--div); border-radius: var(--r); overflow: hidden; background: var(--kort);
    box-shadow: var(--skugga); padding: 0; text-align: left; }
  .projkort:hover { border-color: var(--acc); }
  .projbild { aspect-ratio: 4 / 3; display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 9px, var(--panel) 9px, var(--panel) 18px); }
  .projbild span { font-family: var(--mono, ui-monospace, monospace); font-size: 10.5px; color: var(--t-mut); }
  .projtxt { padding: 10px 12px; }
  .projnamn { font-size: 12.5px; font-weight: 600; color: var(--t-head); }
  .projsub { font-size: 11px; color: var(--t-mut); margin-top: 2px; }
  .projater { font-size: 12px; font-weight: 600; color: var(--acc); margin-top: 8px; }
</style>
