<script>
  import { onMount } from 'svelte'
  import { listaUrval, levereraUrval, startaNummer, valjFil } from '../lib/api.js'

  let urval = []
  let laddar = true
  let oppen = null          // expanderat urval-id
  let korId = null          // urval som levereras just nu
  let nummerId = null       // urval som läser tröjnummer just nu
  let resultat = {}         // urval-id → {skrivna, ratade} / {fel}
  let cfg = {}              // urval-id → { husstil, exp_bump, objektiv }

  onMount(async () => {
    urval = await listaUrval()
    cfg = Object.fromEntries(
      urval.map((u) => [u.id, { husstil: '', exp_bump: 0, objektiv: true }]))
    laddar = false
  })

  function toggla(u) {
    if (u.status === 'levererad') return
    oppen = oppen === u.id ? null : u.id
  }

  async function leverera(u) {
    korId = u.id
    const c = cfg[u.id] || {}
    const r = await levereraUrval(u.id, {
      husstil: c.husstil || '', exp_bump: Number(c.exp_bump) || 0,
      objektiv: c.objektiv !== false,
    })
    resultat = { ...resultat, [u.id]: r }
    if (r.ok) {
      urval = urval.map((x) => (x.id === u.id ? { ...x, status: 'levererad' } : x))
      oppen = null
    }
    korId = null
  }

  async function lasNummer(u) {
    nummerId = u.id
    const r = await startaNummer(u.id)
    resultat = { ...resultat, [u.id]: { ...r, nummer: true } }
    nummerId = null
  }

  const label = (u) =>
    u.lag_hemma ? `${u.lag_hemma} – ${u.lag_borta}` : 'Ingen match'
</script>

<div class="panel">
  <header>
    <h1 class="scd">Leverera</h1>
    <span class="sub">Skriver XMP-sidecars (husstil, exponering, upprätning) för Lightroom — icke-destruktivt</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar urval…</p>
  {:else if urval.length === 0}
    <div class="ingen">Inga urval ännu — gallra ett kort i <b>Gallra</b> först.</div>
  {:else}
    <div class="lista">
      {#each urval as u (u.id)}
        <div class="kort" class:on={oppen === u.id}>
          <button class="rad" on:click={() => toggla(u)} disabled={u.status === 'levererad'}>
            <div class="vänster">
              <div class="match scd">{label(u)}</div>
              <div class="kalla">{u.kalla}</div>
              <div class="meta">{u.kamera || '—'} · {u.bilder} bilder · {u.skapad}</div>
            </div>
            <span class="badge" class:lev={u.status === 'levererad'}>{u.status}</span>
          </button>

          {#if oppen === u.id}
            <div class="form">
              <label class="full">Husstil-preset (.xmp)
                <div class="filrad">
                  <input bind:value={cfg[u.id].husstil} placeholder="(valfritt) /sökväg/husstil.xmp" />
                  <button class="sek" on:click={async () => { const r = await valjFil('Välj husstil-preset', ['XMP-preset (*.xmp)']); if (r.ok) cfg[u.id].husstil = r.path }}>Välj…</button>
                </div>
              </label>
              <div class="grid2">
                <label>Exponeringsknuff (EV)
                  <input type="number" step="0.1" bind:value={cfg[u.id].exp_bump} />
                </label>
                <label class="chk">Objektivprofil på raw
                  <input type="checkbox" bind:checked={cfg[u.id].objektiv} />
                </label>
              </div>
              <div class="kor">
                {#if resultat[u.id] && !resultat[u.id].ok}
                  <span class="status fel">{resultat[u.id].fel}</span>
                {/if}
                <button class="sek" on:click={() => lasNummer(u)} disabled={nummerId === u.id}>
                  {nummerId === u.id ? 'Läser nummer…' : 'Läs tröjnummer'}
                </button>
                <button class="prim" on:click={() => leverera(u)} disabled={korId === u.id}>
                  {korId === u.id ? 'Skriver sidecars…' : 'Leverera ›'}
                </button>
              </div>
              <p class="not">Läs tröjnummer (YOLO + OCR, roster ur matchen) skriver nummer-keywords. Leverera skriver husstil/exponering-sidecars. Upprätning via Apple Vision kommer.</p>
            </div>
          {/if}

          {#if resultat[u.id] && resultat[u.id].ok && resultat[u.id].nummer}
            <div class="klar">✓ Tröjnummer skrivna på {resultat[u.id].resultat.skrivna} av {resultat[u.id].resultat.totalt} bilder ({resultat[u.id].resultat.luckor} luckor).</div>
          {:else if resultat[u.id] && resultat[u.id].ok}
            <div class="klar">✓ {resultat[u.id].skrivna} sidecars skrivna{resultat[u.id].ratade ? `, ${resultat[u.id].ratade} rätade` : ''}.</div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }
  .ingen { margin: 18px 0; padding: 12px 14px; background: var(--panel);
    border: 1px dashed var(--div); border-radius: var(--r); font-size: 13px; color: var(--t-mut); }

  .lista { display: flex; flex-direction: column; gap: 12px; margin-top: 18px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); overflow: hidden; }
  .kort.on { border-color: var(--acc); }
  .rad { width: 100%; display: flex; align-items: center; justify-content: space-between;
    gap: 14px; padding: 14px 16px; background: none; border: 0; text-align: left; cursor: pointer; }
  .rad:disabled { cursor: default; }
  .vänster { min-width: 0; }
  .match { font-size: 15px; font-weight: 700; color: var(--t-head); }
  .kalla { font-family: var(--mono, ui-monospace, monospace); font-size: 12px;
    color: var(--t-mut); margin: 2px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .meta { font-size: 12px; color: var(--t-help); }
  .badge { flex: none; padding: 4px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em;
    background: var(--div3); color: var(--t-mut); }
  .badge.lev { background: color-mix(in srgb, var(--ok) 18%, transparent); color: var(--ok); }

  .form { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 14px;
    border-top: 1px solid var(--div3); }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); padding-top: 14px; }
  .full { width: 100%; }
  .filrad { display: flex; gap: 8px; }
  .filrad input { flex: 1; }
  input { padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel);
    color: var(--t-head); font-size: 13px; font-weight: 400; text-transform: none; letter-spacing: 0; }
  input:focus { outline: none; border-color: var(--acc); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: end; }
  .chk { flex-direction: row; align-items: center; gap: 8px; }
  .chk input { width: 16px; height: 16px; accent-color: var(--acc); }
  .kor { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
  .status.fel { font-size: 12.5px; color: var(--varn); }
  .not { font-size: 11.5px; color: var(--t-help); margin: 0; }
  .klar { padding: 10px 16px; font-size: 12.5px; color: var(--ok);
    background: color-mix(in srgb, var(--ok) 9%, transparent); border-top: 1px solid var(--div3); }
  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }
</style>
