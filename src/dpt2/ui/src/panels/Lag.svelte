<script>
  import { onMount } from 'svelte'
  import {
    listaLag, listaTavlingar, sparaLag, sparaTavling, raderaLag, raderaTavling,
  } from '../lib/api.js'

  let lag = []
  let tavlingar = []
  let laddar = true
  let sparad = null

  const SPORTER = ['fotboll', 'handboll', 'volleyboll', 'beachvolley', 'tennis']
  const SPORT_ETIKETT = {
    fotboll: 'Fotboll', handboll: 'Handboll', volleyboll: 'Volleyboll',
    beachvolley: 'Beachvolley', tennis: 'Tennis',
  }
  const TYPER = ['liga', 'turnering', 'masterskap']
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }

  onMount(async () => {
    ;[lag, tavlingar] = await Promise.all([listaLag(), listaTavlingar()])
    laddar = false
  })

  function initial(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }

  function flash(id) {
    sparad = id
    setTimeout(() => (sparad = sparad === id ? null : sparad), 1400)
  }

  async function gerLag(l) {
    const res = await sparaLag(l)
    if (res?.ok) flash(l.id)
  }
  async function gerTavling(t) {
    const res = await sparaTavling(t)
    if (res?.ok) flash(t.id)
  }

  function nyttLag() {
    lag = [...lag, { id: 'nytt-' + Date.now(), namn: '', instagram: '', hemsida: '',
      stall_hemma: '#2f7cb0', stall_borta: '#ffffff', stall_tredje: '#16181c' }]
  }
  function nyTavling() {
    tavlingar = [...tavlingar, { id: 'ny-' + Date.now(), namn: '', typ: 'liga', sport: 'fotboll' }]
  }

  async function taBortLag(l) {
    lag = lag.filter((x) => x !== l)
    if (!String(l.id).startsWith('nytt-')) await raderaLag(l.id)
  }
  async function taBortTavling(t) {
    tavlingar = tavlingar.filter((x) => x !== t)
    if (!String(t.id).startsWith('ny-')) await raderaTavling(t.id)
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Lag &amp; tävlingar</h1>
    <span class="sub">Registret som matcherna delar — loggor, Instagram och ställ</span>
  </header>

  {#if laddar}
    <p class="tom">Laddar register…</p>
  {:else}
    <section>
      <div class="caps">Tävlingar</div>
      <div class="lista">
        {#each tavlingar as t (t.id)}
          <div class="kort tav">
            <div class="logo scd">{initial(t.namn)}</div>
            <div class="falt">
              <input class="namn-in scd" bind:value={t.namn} on:change={() => gerTavling(t)} placeholder="Tävlingens namn" />
              <div class="dubbel">
                <select bind:value={t.typ} on:change={() => gerTavling(t)}>
                  {#each TYPER as ty}<option value={ty}>{TYP_ETIKETT[ty]}</option>{/each}
                </select>
                <select bind:value={t.sport} on:change={() => gerTavling(t)}>
                  {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                </select>
              </div>
            </div>
            {#if sparad === t.id}<span class="flash">✓</span>{/if}
            <button class="x" on:click={() => taBortTavling(t)} title="Ta bort">×</button>
          </div>
        {/each}
      </div>
      <button class="ny" on:click={nyTavling}>+ Ny tävling</button>
    </section>

    <section>
      <div class="caps">Lag</div>
      <div class="lista">
        {#each lag as l (l.id)}
          <div class="kort">
            <div class="logo scd">{initial(l.namn)}</div>
            <div class="falt">
              <input class="namn-in scd" bind:value={l.namn} on:change={() => gerLag(l)} placeholder="Lagnamn" />
              <div class="dubbel">
                <input bind:value={l.instagram} on:change={() => gerLag(l)} placeholder="@instagram" />
                <input bind:value={l.hemsida} on:change={() => gerLag(l)} placeholder="Hemsida" />
              </div>
              <div class="stall">
                <span class="lbl">Ställ</span>
                <input type="color" bind:value={l.stall_hemma} on:change={() => gerLag(l)} title="Hemma" />
                <input type="color" bind:value={l.stall_borta} on:change={() => gerLag(l)} title="Borta" />
                <input type="color" bind:value={l.stall_tredje} on:change={() => gerLag(l)} title="Tredje" />
                <span class="lbl mut">hemma · borta · tredje</span>
                {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
              </div>
            </div>
            <button class="x" on:click={() => taBortLag(l)} title="Ta bort">×</button>
          </div>
        {/each}
      </div>
      <button class="ny" on:click={nyttLag}>+ Lägg till lag</button>
    </section>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 48px; max-width: 900px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  section { margin-top: 24px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--t-caps); margin-bottom: 10px; }
  .lista { display: flex; flex-direction: column; gap: 10px; }

  .kort { display: flex; gap: 14px; align-items: flex-start; background: var(--kort);
    border: 1px solid var(--div); border-radius: var(--r); padding: 14px;
    box-shadow: var(--skugga); position: relative; }
  .logo { width: 42px; height: 42px; flex: none; border-radius: 10px;
    background: var(--acc-soft); color: var(--acc); display: flex;
    align-items: center; justify-content: center; font-size: 15px; font-weight: 700; }

  .falt { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .dubbel { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  input, select { padding: 7px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .namn-in { font-size: 15px; font-weight: 700; }
  .stall { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .lbl { font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--t-caps); }
  .lbl.mut { font-weight: 500; color: var(--t-help); text-transform: none; letter-spacing: 0; }
  input[type='color'] { width: 30px; height: 28px; padding: 2px; border-radius: 7px; cursor: pointer; }
  .flash { font-size: 11.5px; font-weight: 600; color: var(--ok); align-self: center; }

  .x { width: 26px; height: 26px; flex: none; border: 1px solid var(--div);
    border-radius: 7px; background: var(--kort); color: var(--t-mut); font-size: 16px;
    line-height: 1; align-self: flex-start; }
  .x:hover { background: var(--rose); border-color: var(--rose); color: #fff; }

  .ny { margin-top: 10px; padding: 11px; width: 100%; border: 1.5px dashed var(--div);
    border-radius: var(--r); background: transparent; color: var(--t-mut);
    font-size: 13px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
</style>
