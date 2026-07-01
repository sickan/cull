<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import {
    listaMatcher, hamtaMatch, sparaMatch, hamtaTrupp, sattAktivMatch,
    lasLineup, valjFil, listaTavlingar, listaLag, listaLagForTavling,
  } from '../lib/api.js'
  import Combobox from '../lib/Combobox.svelte'

  const dispatch = createEventDispatcher()

  let matcher = []
  let tavlingar = []
  let lagAlla = []
  let lagForTavling = []     // lagen i utkastets tävling (annars tom → alla)
  let laddar = true
  let sportFilter = 'alla'
  let oppen = null
  let utkast = null

  const SPORTER = ['alla', 'fotboll', 'handboll', 'volleyboll', 'tennis']
  const MANADER = ['Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni',
    'Juli', 'Augusti', 'September', 'Oktober', 'November', 'December']
  const VECKODAG = ['sön', 'mån', 'tis', 'ons', 'tor', 'fre', 'lör']
  const SPORT_FARG = '#2F7CB0'   // kategori Sport (alla matcher), oberoende av gren
  const STATUS = {
    kommande: { txt: 'Kommande', f: '#2F7CB0' },
    pagaende: { txt: 'Pågående', f: '#4E8A3E' },
    avslutad: { txt: 'Avslutad', f: 'rgba(35,32,26,.5)' },
  }

  onMount(async () => {
    ;[matcher, tavlingar, lagAlla] = await Promise.all(
      [listaMatcher(), listaTavlingar(), listaLag()])
    laddar = false
  })

  $: filtrerade = matcher.filter((m) => sportFilter === 'alla' || m.sport === sportFilter)
  $: grupper = gruppera(filtrerade)
  // Lagväljarens optioner: tävlingens lag om känt, annars hela registret.
  $: lagVal = (lagForTavling.length ? lagForTavling : lagAlla).map(
    (l) => ({ id: l.id, namn: l.namn }))
  $: tavlingVal = tavlingar.map((t) => ({ id: t.id, namn: t.namn }))
  $: hemSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'hemma')
  $: bortaSpelare = (utkast?.spelare || []).filter((p) => p.lag === 'borta')

  function gruppera(lista) {
    const m = new Map()
    for (const x of lista) {
      const k = manadNyckel(x.datum)
      if (!m.has(k)) m.set(k, [])
      m.get(k).push(x)
    }
    return [...m.entries()].map(([nyckel, matcher]) => ({ nyckel, matcher }))
  }
  function manadNyckel(iso) {
    const d = (iso || '').split('-')
    return d.length >= 2 ? `${MANADER[+d[1] - 1]} ${d[0]}` : 'Utan datum'
  }
  function veckodag(iso) {
    const d = (iso || '').split('-').map(Number)
    if (d.length !== 3) return ''
    return VECKODAG[new Date(d[0], d[1] - 1, d[2]).getDay()] || ''
  }

  // ── Sport-radens brickor (variant 1a) ─────────────────────────────────────
  function initialer(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 3).toUpperCase()
  }
  function _lum(hex) {
    const h = (hex || '').replace('#', '')
    if (h.length < 3) return 1
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
    return (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  }
  function textPa(hex) { return _lum(hex) > 0.62 ? 'rgba(35,32,26,.85)' : '#fff' }
  function brickStil(farg) {
    const f = farg || '#c9bfa8'
    return `background:${f};color:${textPa(f)}`
  }
  function fargForLag(namn) {
    const l = lagAlla.find((x) => x.namn === namn)
    return l ? (l.stall_hemma || l.profilfarg) : ''
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
    const tmp = {
      id: 'ny-' + Date.now(), datum: '', tid: '', arena: '', status: 'kommande',
      resultat: '', sport: '', lag_hemma: '', lag_borta: '', liga: '',
    }
    matcher = [tmp, ...matcher]
    oppen = tmp.id
    utkast = { ...tmp, spelare: [] }
    lagForTavling = []
  }

  // ── Combobox-val (spara ref via namn; store slår upp/skapar + kopplar) ─────
  async function valjTavling(o) {
    utkast.liga = o.namn
    const t = tavlingar.find((x) => x.id === o.id)
    if (t?.sport) utkast.sport = t.sport
    await laddaLagForTavling(o.namn)
  }
  function skapaTavling(namn) { utkast.liga = namn; lagForTavling = [] }
  function valjHemma(o) { utkast.lag_hemma = o.namn }
  function valjBorta(o) { utkast.lag_borta = o.namn }

  let hamtar = false
  async function hamtaTruppen() {
    if (arMatch()) return
    hamtar = true
    const res = await hamtaTrupp(utkast.id)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }
  async function lasLineupAnk() {
    if (arMatch()) return
    const f = await valjFil('Välj laguppställnings-ark (bild/PDF)')
    if (!f.ok) return
    hamtar = true
    const res = await lasLineup(utkast.id, f.path)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }
  function arMatch() {
    return !utkast || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))
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
    dispatch('aktiverad', m)
    sattAktivMatch(m.id)
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Matcher</h1>
    <span class="sub">Planera kommande matcher och återuppta tidigare projekt</span>
  </header>

  <div class="chips">
    {#each SPORTER as s}
      <button class="chip" class:on={sportFilter === s} on:click={() => (sportFilter = s)}>{s}</button>
    {/each}
  </div>

  {#if laddar}
    <p class="tom">Laddar matcher…</p>
  {:else if grupper.length === 0}
    <p class="tom">Inga matcher för det här filtret.</p>
  {:else}
    {#each grupper as g}
      <div class="grupp">
        <div class="manad scd">{g.nyckel}</div>
        {#each g.matcher as m (m.id)}
          <div class="match">
            <button class="rad" on:click={() => toggla(m)}>
              <div class="brickor">
                <span class="bricka" style={brickStil(m.hemfarg)}>{initialer(m.lag_hemma)}</span>
                <span class="bricka away" style={brickStil(m.bortafarg)}>{initialer(m.lag_borta)}</span>
              </div>
              <div class="fixtur">
                <div class="kicker scd">{m.liga || 'Övrigt'}</div>
                <div class="lag">{m.lag_hemma} – {m.lag_borta}</div>
                <div class="radmeta">
                  <span class="pill" style="color:{STATUS[m.status]?.f};background:{STATUS[m.status]?.f}26">
                    {STATUS[m.status]?.txt || m.status}
                  </span>
                  <span class="submeta">{m.arena || ''}</span>
                </div>
              </div>
              <div class="hoger scd">
                {#if m.status === 'avslutad' && m.resultat}
                  <div class="res">{m.resultat}</div>
                  <div class="liten">slut</div>
                {:else}
                  <div class="tid">{m.tid || '–'}</div>
                  <div class="liten">{veckodag(m.datum)}</div>
                {/if}
              </div>
              <span class="chev" class:upp={oppen === m.id}>›</span>
            </button>

            {#if oppen === m.id && utkast}
              <div class="editor">
                <div class="rad2">
                  <label>Hemmalag
                    <Combobox options={lagVal} value={utkast.lag_hemma}
                      placeholder="Välj lag…" on:pick={(e) => valjHemma(e.detail)}
                      on:create={(e) => (utkast.lag_hemma = e.detail)} />
                  </label>
                  <label>Bortalag
                    <Combobox options={lagVal} value={utkast.lag_borta}
                      placeholder="Välj lag…" on:pick={(e) => valjBorta(e.detail)}
                      on:create={(e) => (utkast.lag_borta = e.detail)} />
                  </label>
                </div>
                <label class="full">Tävling
                  <Combobox options={tavlingVal} value={utkast.liga}
                    placeholder="Välj tävling…" on:pick={(e) => valjTavling(e.detail)}
                    on:create={(e) => skapaTavling(e.detail)} />
                </label>
                <div class="rad3">
                  <label>Datum<input bind:value={utkast.datum} placeholder="ÅÅÅÅ-MM-DD" /></label>
                  <label>Tid<input bind:value={utkast.tid} placeholder="HH:MM" /></label>
                  <label>Arena<input bind:value={utkast.arena} /></label>
                </div>

                {#if utkast.spelare?.length}
                  <div class="trupp2">
                    {#each [{ sida: 'hemma', namn: utkast.lag_hemma, lista: hemSpelare }, { sida: 'borta', namn: utkast.lag_borta, lista: bortaSpelare }] as kol}
                      <div class="kol">
                        <div class="kolhuvud">
                          <span class="bricka liten-b" style={brickStil(fargForLag(kol.namn))}>{initialer(kol.namn)}</span>
                          <span class="kolnamn scd">{kol.namn || (kol.sida === 'hemma' ? 'Hemmalag' : 'Bortalag')}</span>
                          <span class="kolantal">{kol.lista.length}</span>
                        </div>
                        <div class="spelare">
                          {#each kol.lista as p}
                            <span class="sp" class:start={p.start}>
                              {#if p.nr}<b>{p.nr}</b>{/if} {p.namn}
                              {#if p.handle}<i>{p.handle}</i>{/if}
                            </span>
                          {/each}
                          {#if kol.lista.length === 0}<span class="sptom">Ingen trupp inläst</span>{/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}

                <div class="knappar">
                  <div class="vanster">
                    <button class="sek" on:click={hamtaTruppen} disabled={hamtar || arMatch()}>
                      {hamtar ? 'Hämtar trupp…' : 'Hämta trupp'}
                    </button>
                    <button class="sek" on:click={lasLineupAnk} disabled={hamtar || arMatch()}>
                      Läs laguppställning…
                    </button>
                  </div>
                  <div class="hoger-k">
                    <button class="sek" on:click={spara}>Spara</button>
                    <button class="prim" on:click={() => aktivera(utkast)}>Aktivera match ›</button>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/each}
  {/if}

  <button class="ny" on:click={nyMatch}>+ Ny match</button>
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 920px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .chips { display: flex; gap: 7px; margin: 16px 0 22px; flex-wrap: wrap; }
  .chip {
    padding: 5px 13px; border: 1px solid var(--div); border-radius: 999px;
    background: var(--kort); color: var(--t-mut); font-size: 12.5px;
    text-transform: capitalize; transition: all 0.12s;
  }
  .chip.on { background: var(--acc); border-color: var(--acc); color: var(--kort); font-weight: 600; }
  .tom { color: var(--t-help); font-size: 13px; }

  .grupp { margin-bottom: 22px; }
  .manad { font-size: 12px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--t-mut); margin: 0 2px 10px; }

  .match { background: var(--kort); border: 1px solid var(--div);
    border-left: 3px solid var(--sport, #2F7CB0); border-radius: var(--r);
    margin-bottom: 10px; box-shadow: var(--skugga); overflow: hidden; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%;
    padding: 12px 15px; border: 0; background: transparent; text-align: left; }
  .rad:hover { background: var(--div3); }

  .brickor { display: flex; align-items: center; flex: none; }
  .bricka {
    display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; border-radius: 50%; flex: none;
    font-family: 'Saira Condensed', sans-serif; font-size: 12px; font-weight: 700;
    border: 2px solid var(--kort); box-shadow: 0 0 0 1px var(--div);
  }
  .bricka.away { margin-left: -10px; }

  .fixtur { flex: 1; min-width: 0; }
  .kicker { font-size: 10px; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--sport, #2F7CB0); }
  .lag { font-size: 14.5px; font-weight: 600; color: var(--t-head); margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .radmeta { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
  .pill { font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 999px; flex: none; white-space: nowrap; }
  .submeta { font-size: 11.5px; color: var(--t-mut); }

  .hoger { text-align: right; flex: none; }
  .res { font-size: 22px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .tid { font-size: 19px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .liten { font-size: 10px; color: var(--t-mut); margin-top: 3px; letter-spacing: 0.04em; }
  .chev { width: 16px; text-align: center; color: var(--t-mut); font-size: 18px;
    transition: transform 0.15s; flex: none; }
  .chev.upp { transform: rotate(90deg); }

  .editor { border-top: 1px solid var(--div3); padding: 16px 15px;
    display: flex; flex-direction: column; gap: 12px; }
  .rad2, .rad3 { display: grid; gap: 12px; }
  .rad2 { grid-template-columns: 1fr 1fr; }
  .rad3 { grid-template-columns: 1fr 1fr 2fr; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 11px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); }
  label.full { width: 100%; }
  input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; }
  input:focus { outline: none; border-color: var(--acc); }

  .trupp2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .kol { display: flex; flex-direction: column; gap: 8px; }
  .kolhuvud { display: flex; align-items: center; gap: 8px; }
  .liten-b { width: 26px; height: 26px; font-size: 10px; }
  .kolnamn { font-size: 13px; font-weight: 700; color: var(--t-head); flex: 1;
    min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kolantal { font-size: 11px; font-weight: 600; color: var(--t-mut); }
  .spelare { display: flex; flex-wrap: wrap; gap: 6px; }
  .sp { font-size: 12px; padding: 3px 9px; border-radius: 999px; background: var(--div3); color: var(--t-mut); }
  .sp.start { background: var(--acc-soft); color: var(--acc); }
  .sp b { color: var(--t-head); }
  .sp i { color: var(--rose); font-style: normal; margin-left: 3px; }
  .sptom { font-size: 11.5px; color: var(--t-help); }

  .knappar { display: flex; justify-content: space-between; align-items: center;
    gap: 8px; flex-wrap: wrap; }
  .vanster, .hoger-k { display: flex; gap: 8px; }
  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover:not(:disabled) { background: var(--div3); }
  .sek:disabled { opacity: 0.5; cursor: default; }
  .prim { padding: 8px 16px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .ny { margin-top: 6px; padding: 11px; width: 100%; border: 1.5px dashed var(--div);
    border-radius: var(--r); background: transparent; color: var(--t-mut);
    font-size: 13px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
</style>
