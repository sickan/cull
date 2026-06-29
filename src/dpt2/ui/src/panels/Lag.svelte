<script>
  import { onMount } from 'svelte'
  import { listaLag, listaTavlingar, sparaLag } from '../lib/api.js'

  let lag = []
  let tavlingar = []
  let laddar = true
  let sparad = null   // lag-id som nyss sparades (flash)

  const SPORT_ETIKETT = {
    fotboll: 'Fotboll', handboll: 'Handboll', volleyboll: 'Volleyboll',
    beachvolley: 'Beachvolley', tennis: 'Tennis',
  }
  const TYP_ETIKETT = { liga: 'Liga', turnering: 'Turnering', masterskap: 'Mästerskap' }

  onMount(async () => {
    ;[lag, tavlingar] = await Promise.all([listaLag(), listaTavlingar()])
    laddar = false
  })

  function initial(namn) {
    return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  }

  async function spara(l) {
    const res = await sparaLag(l)
    if (res?.ok) {
      sparad = l.id
      setTimeout(() => (sparad = sparad === l.id ? null : sparad), 1400)
    }
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
            <div class="info">
              <div class="namn scd">{t.namn}</div>
              <div class="meta">{TYP_ETIKETT[t.typ] || t.typ} · {SPORT_ETIKETT[t.sport] || t.sport}</div>
            </div>
          </div>
        {/each}
        {#if tavlingar.length === 0}<p class="tom">Inga tävlingar än.</p>{/if}
      </div>
    </section>

    <section>
      <div class="caps">Lag</div>
      <div class="lista">
        {#each lag as l (l.id)}
          <div class="kort">
            <div class="logo scd">{initial(l.namn)}</div>
            <div class="falt">
              <input class="namn-in scd" bind:value={l.namn} on:change={() => spara(l)} placeholder="Lagnamn" />
              <div class="dubbel">
                <input bind:value={l.instagram} on:change={() => spara(l)} placeholder="@instagram" />
                <input bind:value={l.hemsida} on:change={() => spara(l)} placeholder="Hemsida" />
              </div>
              <div class="stall">
                <span class="lbl">Ställ</span>
                <input type="color" bind:value={l.stall_hemma} on:change={() => spara(l)} title="Hemma" />
                <input type="color" bind:value={l.stall_borta} on:change={() => spara(l)} title="Borta" />
                <input type="color" bind:value={l.stall_tredje} on:change={() => spara(l)} title="Tredje" />
                <span class="lbl mut">hemma · borta · tredje</span>
                {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
      <button class="ny">+ Lägg till lag</button>
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
    box-shadow: var(--skugga); }
  .kort.tav { align-items: center; }
  .logo { width: 42px; height: 42px; flex: none; border-radius: 10px;
    background: var(--acc-soft); color: var(--acc); display: flex;
    align-items: center; justify-content: center; font-size: 15px; font-weight: 700; }
  .info { flex: 1; }
  .namn { font-size: 16px; font-weight: 700; color: var(--t-head); }
  .meta { font-size: 12px; color: var(--t-mut); margin-top: 2px; }

  .falt { flex: 1; display: flex; flex-direction: column; gap: 8px; }
  .dubbel { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  input { padding: 7px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; }
  input:focus { outline: none; border-color: var(--acc); }
  .namn-in { font-size: 15px; font-weight: 700; }
  .stall { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .lbl { font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--t-caps); }
  .lbl.mut { font-weight: 500; color: var(--t-help); text-transform: none; letter-spacing: 0; }
  input[type='color'] { width: 30px; height: 28px; padding: 2px; border-radius: 7px; cursor: pointer; }
  .flash { font-size: 11.5px; font-weight: 600; color: var(--ok); margin-left: auto; }

  .ny { margin-top: 10px; padding: 11px; width: 100%; border: 1.5px dashed var(--div);
    border-radius: var(--r); background: transparent; color: var(--t-mut);
    font-size: 13px; font-weight: 600; }
  .ny:hover { border-color: var(--acc); color: var(--acc); }
</style>
