<script>
  import { onMount } from 'svelte'
  import {
    listaLag, listaTavlingar, sparaLag, sparaTavling, raderaLag, raderaTavling,
    valjFil, lasLagTrupp,
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

  function sattKind(l, kind) {
    if (l.kind === kind) return
    l.kind = kind
    lag = lag                     // trigga re-render av villkorsfälten
    gerLag(l)
  }

  async function valjLoggaLag(l) {
    const f = await valjFil('Välj logga/porträtt (bild)', ['*.png', '*.jpg', '*.jpeg', '*.webp'])
    if (f.ok) { l.logga = f.path; lag = lag; gerLag(l) }
  }
  async function valjLoggaTavling(t) {
    const f = await valjFil('Välj tävlingslogga (bild)', ['*.png', '*.jpg', '*.jpeg', '*.webp'])
    if (f.ok) { t.logga = f.path; tavlingar = tavlingar; gerTavling(t) }
  }
  const bildUrl = (p) => (p ? (/^https?:|^file:/.test(p) ? p : 'file://' + p) : '')

  function nyttLag() {
    lag = [...lag, { id: 'nytt-' + Date.now(), namn: '', kind: 'team', instagram: '',
      hemsida: '', logga: null, stall_hemma: '#2f7cb0', stall_borta: '#ffffff',
      stall_tredje: '#16181c', profilfarg: '#2f7cb0', klubb: '' }]
  }
  function nyTavling() {
    tavlingar = [...tavlingar, { id: 'ny-' + Date.now(), namn: '', typ: 'liga',
      sport: 'fotboll', fran: '', ort: '', arena: '', hemsida: '', logga: null, kalender: 0 }]
  }

  function laggTavlingIKalender(t) {
    t.kalender = t.kalender ? 0 : 1
    tavlingar = tavlingar
    gerTavling(t)
  }

  // ── Trupp-källväljare (URL / CSV / bild / PDF) ─────────────────────────────
  let truppOppen = null          // lag-id vars källväljare är utfälld
  let truppUrl = ''              // URL-fältet (förifylls med lagets hemsida)
  let truppKor = false
  let truppFel = ''

  function togglaTrupp(l) {
    if (truppOppen === l.id) { truppOppen = null; return }
    truppOppen = l.id
    truppUrl = l.hemsida || ''
    truppFel = ''
  }

  async function lasTrupp(l, kalla) {
    let arg = ''
    if (kalla === 'url') {
      arg = (truppUrl || '').trim()
    } else {
      const filter = { csv: ['*.csv'], bild: ['*.jpg', '*.jpeg', '*.png', '*.heic', '*.heif'],
        pdf: ['*.pdf'] }[kalla]
      const f = await valjFil('Välj spelarlista', filter)
      if (!f.ok) return
      arg = f.path
    }
    truppKor = true; truppFel = ''
    const r = await lasLagTrupp(l.id, kalla, arg)
    truppKor = false
    if (r?.ok) {
      l.trupp_n = r.antal; l.trupp_kalla = r.trupp_kalla
      lag = lag; truppOppen = null
      flash(l.id)
    } else {
      truppFel = r?.fel || 'Kunde inte läsa in truppen.'
    }
  }

  function truppEtikett(l) {
    if (!l.trupp_n) return 'ingen trupp inläst'
    return `${l.trupp_n} spelare i trupp${l.trupp_kalla ? ' · ' + l.trupp_kalla : ''}`
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
          <div class="kort">
            <button class="logo scd" on:click={() => valjLoggaTavling(t)} title="Välj logga">
              {#if t.logga}<img src={bildUrl(t.logga)} alt="" />{:else}{initial(t.namn)}{/if}
            </button>
            <div class="falt">
              <input class="namn-in scd" bind:value={t.namn} on:change={() => gerTavling(t)} placeholder="Tävlingens namn" />
              <div class="trippel">
                <select bind:value={t.typ} on:change={() => gerTavling(t)}>
                  {#each TYPER as ty}<option value={ty}>{TYP_ETIKETT[ty]}</option>{/each}
                </select>
                <select bind:value={t.sport} on:change={() => gerTavling(t)}>
                  {#each SPORTER as s}<option value={s}>{SPORT_ETIKETT[s]}</option>{/each}
                </select>
                <input bind:value={t.fran} on:change={() => gerTavling(t)} placeholder="Period (t.ex. apr–okt 2026)" />
              </div>
              <div class="dubbel">
                <input bind:value={t.ort} on:change={() => gerTavling(t)} placeholder="Ort" />
                <input bind:value={t.arena} on:change={() => gerTavling(t)} placeholder="Arena" />
              </div>
              <input bind:value={t.hemsida} on:change={() => gerTavling(t)} placeholder="Hemsida" />
              <div class="kalfot">
                <span class="kalik">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="5" width="17" height="15.5" rx="2.4"/><path d="M3.5 9.5h17M8 3.5v3M16 3.5v3"/></svg>
                </span>
                <span class="kaltxt">Lägg hela tävlingen i kalendern som flerdagarsuppdrag</span>
                <button class="kalbtn" class:i={t.kalender} on:click={() => laggTavlingIKalender(t)}>
                  {t.kalender ? 'I kalendern ✓' : 'Lägg i Google Calendar ›'}
                </button>
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
      <div class="caps">Lag &amp; utövare</div>
      <div class="lista">
        {#each lag as l (l.id)}
          <div class="kort">
            <button class="logo scd" class:rund={l.kind === 'individ'} on:click={() => valjLoggaLag(l)} title="Välj logga/porträtt">
              {#if l.logga}<img src={bildUrl(l.logga)} alt="" />{:else}{initial(l.namn)}{/if}
            </button>
            <div class="falt">
              <div class="rad1">
                <input class="namn-in scd" bind:value={l.namn} on:change={() => gerLag(l)}
                  placeholder={l.kind === 'individ' ? 'Namn' : 'Lagnamn'} />
                <div class="seg">
                  <button class:on={l.kind !== 'individ'} on:click={() => sattKind(l, 'team')}>Lag</button>
                  <button class:on={l.kind === 'individ'} on:click={() => sattKind(l, 'individ')}>Individ</button>
                </div>
              </div>
              <div class="dubbel">
                <input bind:value={l.instagram} on:change={() => gerLag(l)} placeholder="@instagram" />
                <input bind:value={l.hemsida} on:change={() => gerLag(l)} placeholder="Hemsida" />
              </div>

              {#if l.kind === 'individ'}
                <div class="stall">
                  <span class="lbl">Profil</span>
                  <input type="color" bind:value={l.profilfarg} on:change={() => gerLag(l)} title="Profilfärg" />
                  <input class="klubb" bind:value={l.klubb} on:change={() => gerLag(l)} placeholder="Klubb / land" />
                  {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                </div>
              {:else}
                <div class="stall">
                  <span class="lbl">Ställ</span>
                  <input type="color" bind:value={l.stall_hemma} on:change={() => gerLag(l)} title="Hemma" />
                  <input type="color" bind:value={l.stall_borta} on:change={() => gerLag(l)} title="Borta" />
                  <input type="color" bind:value={l.stall_tredje} on:change={() => gerLag(l)} title="Tredje" />
                  <span class="lbl mut">hemma · borta · tredje</span>
                  {#if sparad === l.id}<span class="flash">✓ sparat</span>{/if}
                </div>
                <div class="trupprad">
                  <button class="spelarbtn" on:click={() => togglaTrupp(l)}>Läs in spelare…</button>
                  <span class="truppinfo">{truppEtikett(l)}</span>
                </div>
                {#if truppOppen === l.id}
                  <div class="truppvaljare">
                    <div class="truppcaps">Läs in trupp från</div>
                    <div class="truppurl">
                      <input bind:value={truppUrl} placeholder="Hemsida eller URL till laguppställning…" />
                      <button class="hamta" on:click={() => lasTrupp(l, 'url')} disabled={truppKor}>{truppKor ? 'Hämtar…' : 'Hämta'}</button>
                    </div>
                    <div class="avdelare"><span class="linje"></span><span class="eller">eller ladda upp fil</span><span class="linje"></span></div>
                    <div class="filknappar">
                      <button on:click={() => lasTrupp(l, 'csv')} disabled={truppKor}>CSV</button>
                      <button on:click={() => lasTrupp(l, 'bild')} disabled={truppKor}>Bild · JPG / PNG / HEIF</button>
                      <button on:click={() => lasTrupp(l, 'pdf')} disabled={truppKor}>PDF</button>
                    </div>
                    {#if truppFel}<div class="truppfel">⚠ {truppFel}</div>
                    {:else}<div class="trupphint">Sidan/filen tolkas och spelarna läggs i lagets trupp.</div>{/if}
                  </div>
                {/if}
              {/if}
            </div>
            <button class="x" on:click={() => taBortLag(l)} title="Ta bort">×</button>
          </div>
        {/each}
      </div>
      <button class="ny" on:click={nyttLag}>+ Lägg till lag / utövare</button>
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
  .logo { width: 42px; height: 42px; flex: none; border-radius: 10px; border: 0;
    background: var(--acc-soft); color: var(--acc); display: flex; overflow: hidden;
    align-items: center; justify-content: center; font-size: 15px; font-weight: 700;
    cursor: pointer; padding: 0; }
  .logo.rund { border-radius: 50%; }
  .logo:hover { outline: 2px solid var(--acc); outline-offset: 1px; }
  .logo img { width: 100%; height: 100%; object-fit: cover; }

  .falt { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .rad1 { display: flex; gap: 8px; align-items: center; }
  .rad1 .namn-in { flex: 1; min-width: 0; }
  .dubbel { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .trippel { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  .kalfot { display: flex; align-items: center; gap: 10px; margin-top: 4px; padding: 10px 12px;
    background: var(--panel); border: 1px solid var(--div3); border-radius: 9px; }
  .kalik { width: 30px; height: 30px; border-radius: 8px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .kalik svg { width: 16px; height: 16px; }
  .kaltxt { flex: 1; min-width: 0; font-size: 12px; color: var(--t-mut); }
  .kalbtn { flex: none; background: var(--acc); color: #fff; border: 0; border-radius: 7px;
    padding: 8px 13px; font-size: 12.5px; font-weight: 600; }
  .kalbtn.i { background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }
  .trupprad { display: flex; align-items: center; gap: 10px; }
  .spelarbtn { background: var(--kort); border: 1px solid var(--div); border-radius: 8px;
    padding: 8px 12px; font-size: 12.5px; color: var(--t-mut); font-weight: 500; flex: none; }
  .spelarbtn:hover { border-color: var(--acc); color: var(--acc); }
  .truppinfo { font-size: 11px; color: var(--t-mut); }
  .truppvaljare { border: 1px solid var(--div3); border-radius: 9px; background: var(--panel);
    padding: 11px; display: flex; flex-direction: column; gap: 9px; }
  .truppcaps { font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); }
  .truppurl { display: flex; gap: 6px; }
  .truppurl input { flex: 1; min-width: 0; background: var(--kort); font-size: 12px; padding: 7px 9px; }
  .hamta { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 7px 13px;
    font-size: 12px; font-weight: 600; flex: none; }
  .hamta:disabled { opacity: 0.5; }
  .avdelare { display: flex; align-items: center; gap: 8px; }
  .linje { height: 1px; flex: 1; background: var(--div3); }
  .eller { font-size: 10px; color: var(--t-help); }
  .filknappar { display: flex; gap: 6px; flex-wrap: wrap; }
  .filknappar button { background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 6px 11px; font-size: 12px; color: var(--t-head); }
  .filknappar button:hover:not(:disabled) { border-color: var(--acc); color: var(--acc); }
  .filknappar button:disabled { opacity: 0.5; }
  .trupphint { font-size: 10px; color: var(--t-help); line-height: 1.45; }
  .truppfel { font-size: 11px; color: var(--rose); }
  input, select { padding: 7px 10px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 13px; }
  input:focus, select:focus { outline: none; border-color: var(--acc); }
  .namn-in { font-size: 15px; font-weight: 700; }

  .seg { display: flex; flex: none; border: 1px solid var(--div); border-radius: 8px; overflow: hidden; }
  .seg button { padding: 6px 12px; border: 0; background: var(--panel); color: var(--t-mut);
    font-size: 12px; font-weight: 600; cursor: pointer; }
  .seg button.on { background: var(--acc); color: var(--kort); }

  .stall { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .klubb { flex: 1; min-width: 120px; }
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
