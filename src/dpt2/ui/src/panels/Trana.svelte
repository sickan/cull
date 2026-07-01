<script>
  import { onMount } from 'svelte'
  import { listaModeller, sattAktivModell, startaTraning, startaOmraknaArkiv, valjMapp } from '../lib/api.js'

  const TYP_NAMN = { din_smak: 'Din smak', arkiv: 'Arkiv', hybrid: 'Hybrid' }

  let modeller = []
  let laddar = true
  let trana = { typ: 'arkiv' }
  let arkiv = { root: '' }
  let korOmrakna = false
  let korTrana = false
  let status = null

  $: aktiv = modeller.find((m) => m.aktiv) || null

  onMount(async () => {
    modeller = await listaModeller()
    laddar = false
  })

  async function aktivera(m) {
    const r = await sattAktivModell(m.id)
    if (r.ok) modeller = modeller.map((x) => ({ ...x, aktiv: x.id === m.id }))
  }

  async function korOmraknaArkiv() {
    korOmrakna = true; status = null
    const r = await startaOmraknaArkiv(arkiv.root)
    const res = r.resultat
    status = r.ok && res
      ? `Omräknat: ${res.uppdrag} uppdrag, ${res.bilder} bilder (${res.valda} valda) → korpus.`
      : (r.fel || 'Fel vid omräkning.')
    korOmrakna = false
  }

  async function korTraning() {
    korTrana = true; status = null
    const r = await startaTraning(trana)
    const res = r.resultat
    status = r.ok && res
      ? `Modell tränad: ${res.n_uppdrag} uppdrag, ${res.n_valda} valda. Se Logg.`
      : (r.fel || 'Inga omräknade facit än — omräkna arkiv först.')
    if (r.ok) modeller = await listaModeller()
    korTrana = false
  }

  const GRANSKNING = [
    { namn: 'Granska osäkra', info: 'Bilder modellen är osäker på — döm in/ut' },
    { namn: 'Jämför par', info: 'A/B-jämför två bilder för att finslipa smaken' },
    { namn: 'Histogram', info: 'Poängfördelning för senaste gallringen' },
  ]
</script>

<div class="panel">
  <header>
    <h1 class="scd">Träna</h1>
    <span class="sub">Lär modellen din smak — biblioteket lever här, träningen körs i ML-workern</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar modeller…</p>
  {:else}
    {#if aktiv}
      <div class="aktiv">
        <span class="prick"></span>
        <div>
          <div class="caps">Aktiv modell</div>
          <div class="namn scd">{TYP_NAMN[aktiv.typ] || aktiv.typ}</div>
          <div class="meta">{aktiv.n_uppdrag ?? '–'} uppdrag · {aktiv.n_valda ?? '–'} valda · {aktiv.sparad || ''}</div>
        </div>
      </div>
    {/if}

    <div class="kort">
      <div class="cardH">Modell-bibliotek</div>
      {#each modeller as m (m.id)}
        <div class="mrad" class:on={m.aktiv}>
          <div class="minfo">
            <span class="mtyp">{TYP_NAMN[m.typ] || m.typ}</span>
            <span class="mstat">{m.n_uppdrag ?? '–'} uppdrag · {m.n_valda ?? '–'} valda</span>
            <span class="mpath">{m.pkl_path}</span>
          </div>
          {#if m.aktiv}
            <span class="badge lev">aktiv</span>
          {:else}
            <button class="sek" on:click={() => aktivera(m)}>Aktivera</button>
          {/if}
        </div>
      {/each}
    </div>

    <div class="kort">
      <div class="cardH">Omräkna arkiv (bygg korpus)</div>
      <p class="not">Går igenom en arkiv-katalog (match-mapp + Instagram/ = dina val) och extraherar features ur de nedladdade bilderna → träningskorpus. Online-only-filer hoppas; kör om när fler kataloger laddats ned.</p>
      <label class="full">Arkiv-katalog
        <div class="filrad">
          <input bind:value={arkiv.root} placeholder="~/Dropbox/Export/Sport/2026" />
          <button class="sek" on:click={async () => { const r = await valjMapp('Välj arkiv-katalog'); if (r.ok) arkiv.root = r.path }}>Välj…</button>
        </div>
      </label>
      <div class="kor">
        <button class="sek" on:click={korOmraknaArkiv} disabled={korOmrakna || !arkiv.root}>
          {korOmrakna ? 'Omräknar…' : 'Omräkna arkiv ›'}
        </button>
      </div>
    </div>

    <div class="kort">
      <div class="cardH">Träna modell</div>
      <p class="not">Tränar ur de lagrade facit-vektorerna i korpusen — inga bilder behövs. Live-progress i Logg.</p>
      <div class="grid2">
        <label>Typ
          <select bind:value={trana.typ}>
            <option value="arkiv">Arkiv</option>
            <option value="din_smak">Din smak</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>
        <div></div>
      </div>
      <div class="kor">
        <button class="prim" on:click={korTraning} disabled={korTrana}>
          {korTrana ? 'Tränar…' : 'Träna ›'}
        </button>
      </div>
    </div>

    {#if status}<div class="kvitto">{status}</div>{/if}

    <div class="kort">
      <div class="cardH">Granskning</div>
      <div class="verktyg">
        {#each GRANSKNING as g}
          <div class="vrad">
            <div>
              <div class="vnamn">{g.namn}</div>
              <div class="vinfo">{g.info}</div>
            </div>
            <span class="snart">i workern</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .aktiv { display: flex; gap: 12px; align-items: center; margin: 18px 0;
    padding: 12px 14px; background: var(--acc-soft); border-radius: var(--r); }
  .prick { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); flex: none; }
  .namn { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .meta { font-size: 12px; color: var(--t-mut); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 18px; display: flex; flex-direction: column; gap: 14px;
    margin-bottom: 16px; }
  .cardH { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-caps); }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-caps); margin-bottom: 6px; }
  .not { font-size: 12px; color: var(--t-mut); margin: 0; }

  .mrad { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 12px 14px; border: 1px solid var(--div); border-radius: 10px; }
  .mrad.on { border-color: var(--acc); background: var(--acc-soft); }
  .minfo { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .mtyp { font-size: 14px; font-weight: 700; color: var(--t-head); }
  .mstat { font-size: 12px; color: var(--t-mut); }
  .mpath { font-family: var(--mono, ui-monospace, monospace); font-size: 11px; color: var(--t-help);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .badge { padding: 4px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em; background: var(--div3); color: var(--t-mut); }
  .badge.lev { background: color-mix(in srgb, var(--ok) 18%, transparent); color: var(--ok); }

  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); }
  .full { width: 100%; }
  .filrad { display: flex; gap: 8px; }
  .filrad input { flex: 1; }
  input, select { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; font-weight: 400;
    text-transform: none; letter-spacing: 0; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .grid2 { display: grid; grid-template-columns: 1fr 2fr; gap: 14px; }
  .kor { display: flex; justify-content: flex-end; }
  .kvitto { margin: -4px 0 16px; padding: 10px 14px; font-size: 12.5px; color: var(--ok);
    background: color-mix(in srgb, var(--ok) 9%, transparent); border-radius: var(--r); }

  .verktyg { display: flex; flex-direction: column; gap: 8px; }
  .vrad { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 14px; border: 1px solid var(--div3); border-radius: 10px; }
  .vnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .vinfo { font-size: 12px; color: var(--t-mut); }
  .snart { font-size: 11px; color: var(--t-help); font-style: italic; }

  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .sek:disabled { opacity: 0.5; cursor: default; }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
