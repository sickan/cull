<script>
  import { onMount } from 'svelte'
  import { listaMatcher, hamtaMatch, sparaMatch, hamtaTrupp } from '../lib/api.js'

  let matcher = []
  let laddar = true
  let sportFilter = 'alla'
  let oppen = null          // match-id som är expanderad
  let utkast = null         // redigeringsutkast för öppen match

  const SPORTER = ['alla', 'fotboll', 'handboll', 'volleyboll', 'tennis']
  const MAN = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  const STATUS = {
    kommande: { txt: 'Kommande', f: 'var(--acc)' },
    pagaende: { txt: 'Pågående', f: 'var(--ok)' },
    avslutad: { txt: 'Avslutad', f: 'var(--t-mut)' },
  }

  onMount(async () => { matcher = await listaMatcher(); laddar = false })

  $: filtrerade = matcher.filter((m) => sportFilter === 'alla' || m.sport === sportFilter)
  $: grupper = gruppera(filtrerade)

  function gruppera(lista) {
    const m = new Map()
    for (const x of lista) {
      const k = x.liga || 'Övriga'
      if (!m.has(k)) m.set(k, [])
      m.get(k).push(x)
    }
    return [...m.entries()].map(([liga, matcher]) => ({ liga, matcher }))
  }

  function dagDel(iso) {
    const d = (iso || '').split('-')
    return d.length === 3 ? { dag: d[2], man: MAN[+d[1] - 1] || '' } : { dag: '–', man: '' }
  }

  async function toggla(m) {
    if (oppen === m.id) { oppen = null; utkast = null; return }
    oppen = m.id
    utkast = await hamtaMatch(m.id)
  }

  function nyMatch() {
    const tmp = {
      id: 'ny-' + Date.now(), datum: '', tid: '', arena: '', status: 'kommande',
      resultat: '', sport: '', lag_hemma: '', lag_borta: '', liga: '',
    }
    matcher = [tmp, ...matcher]
    oppen = tmp.id
    utkast = { ...tmp, spelare: [] }
  }

  let hamtar = false
  async function hamtaTruppen() {
    if (!utkast || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))) return
    hamtar = true
    const res = await hamtaTrupp(utkast.id)
    hamtar = false
    if (res?.ok && res.match) utkast = res.match
  }

  async function spara() {
    const m = { ...utkast }
    if (typeof m.id === 'string' && m.id.startsWith('ny-')) delete m.id
    await sparaMatch(m)
    matcher = await listaMatcher()
    oppen = null; utkast = null
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
        <div class="grupphuvud">
          <span class="liga">{g.liga}</span>
          <span class="antal">{g.matcher.length} matcher</span>
        </div>
        {#each g.matcher as m (m.id)}
          <div class="match">
            <button class="rad" on:click={() => toggla(m)}>
              <div class="datum scd">
                <div class="dag">{dagDel(m.datum).dag}</div>
                <div class="man">{dagDel(m.datum).man}</div>
              </div>
              <div class="fixtur">
                <div class="lag scd">{m.lag_hemma} – {m.lag_borta}</div>
                <div class="meta">
                  {m.tid ? m.tid + ' · ' : ''}{m.arena}
                  {m.resultat ? ' · ' + m.resultat : ''}
                </div>
              </div>
              <span class="pill" style="color:{STATUS[m.status]?.f}">{STATUS[m.status]?.txt || m.status}</span>
              <span class="chev" class:upp={oppen === m.id}>›</span>
            </button>

            {#if oppen === m.id && utkast}
              <div class="editor">
                <div class="rad2">
                  <label>Hemmalag<input bind:value={utkast.lag_hemma} /></label>
                  <label>Bortalag<input bind:value={utkast.lag_borta} /></label>
                </div>
                <div class="rad3">
                  <label>Datum<input bind:value={utkast.datum} placeholder="ÅÅÅÅ-MM-DD" /></label>
                  <label>Tid<input bind:value={utkast.tid} placeholder="HH:MM" /></label>
                  <label>Arena<input bind:value={utkast.arena} /></label>
                </div>
                <label class="full">Tävling<input bind:value={utkast.liga} /></label>

                {#if utkast.spelare?.length}
                  <div class="trupp">
                    <span class="caps">Trupp · {utkast.spelare.length} spelare</span>
                    <div class="spelare">
                      {#each utkast.spelare as p}
                        <span class="sp" class:start={p.start}>
                          {#if p.nr}<b>{p.nr}</b>{/if} {p.namn}
                          {#if p.handle}<i>{p.handle}</i>{/if}
                        </span>
                      {/each}
                    </div>
                  </div>
                {/if}

                <div class="knappar">
                  <div class="vanster">
                    <button class="sek" on:click={hamtaTruppen}
                      disabled={hamtar || (typeof utkast.id === 'string' && utkast.id.startsWith('ny-'))}>
                      {hamtar ? 'Hämtar trupp…' : 'Hämta trupp'}
                    </button>
                    <button class="sek">Läs laguppställning…</button>
                  </div>
                  <div class="hoger">
                    <button class="sek" on:click={spara}>Spara</button>
                    <button class="prim">Aktivera match ›</button>
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
  .grupphuvud { display: flex; align-items: baseline; gap: 10px; margin: 0 2px 8px; }
  .liga { font-size: 12px; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase; color: var(--t-caps); }
  .antal { font-size: 11.5px; color: var(--t-help); }

  .match { background: var(--kort); border: 1px solid var(--div);
    border-radius: var(--r); margin-bottom: 9px; box-shadow: var(--skugga); overflow: hidden; }
  .rad { display: flex; align-items: center; gap: 14px; width: 100%;
    padding: 12px 14px; border: 0; background: transparent; text-align: left; }
  .rad:hover { background: var(--div3); }
  .datum { width: 44px; flex: none; text-align: center; }
  .dag { font-size: 20px; font-weight: 700; color: var(--t-head); line-height: 1; }
  .man { font-size: 10.5px; text-transform: uppercase; color: var(--t-mut); letter-spacing: 0.05em; }
  .fixtur { flex: 1; min-width: 0; }
  .lag { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .meta { font-size: 12px; color: var(--t-mut); margin-top: 2px; }
  .pill { font-size: 12px; font-weight: 600; flex: none; }
  .chev { width: 16px; text-align: center; color: var(--t-mut); font-size: 18px;
    transition: transform 0.15s; }
  .chev.upp { transform: rotate(90deg); }

  .editor { border-top: 1px solid var(--div3); padding: 16px 14px;
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

  .trupp { display: flex; flex-direction: column; gap: 7px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--t-caps); }
  .spelare { display: flex; flex-wrap: wrap; gap: 6px; }
  .sp { font-size: 12px; padding: 3px 9px; border-radius: 999px; background: var(--div3);
    color: var(--t-mut); }
  .sp.start { background: var(--acc-soft); color: var(--acc); }
  .sp b { color: var(--t-head); }
  .sp i { color: var(--rose); font-style: normal; margin-left: 3px; }

  .knappar { display: flex; justify-content: space-between; align-items: center;
    gap: 8px; flex-wrap: wrap; }
  .vanster, .hoger { display: flex; gap: 8px; }
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
