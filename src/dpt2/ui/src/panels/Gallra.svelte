<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { startaCull, startaGallring, valjMapp, aktivMatch, listaLag, sattAktivtUrval, hamtaLogg,
    listaOriginal, hamtaOriginal, originalStatus } from '../lib/api.js'
  import AktivMatchRad from '../lib/AktivMatchRad.svelte'

  const dispatch = createEventDispatcher()

  export let aktivMatchData = null

  let aktiv = aktivMatchData
  let lagAlla = []
  let lage = 'ai'             // F1: ett gallringssteg, tre lägen — ai | snabb | rapport
  let adv = false

  let kalla = ''              // F1: källmappen delas av alla lägen
  let ai = { keep: 40, unit: 'bilder', burst: 2.0, ocr: true, nums: '',
    overwrite: false, kit: 'Hemmaställ', kick: 'auto', model: 'din_smak', pose: 60, sharp: 70 }
  let snabb = { keep: 40, burst: 2.0 }

  let kor = { ai: false, snabb: false, rapport: false }
  let prog = { ai: 0, snabb: 0, rapport: 0 }
  let res = { ai: '', snabb: '', rapport: '' }

  const KIT = ['Hemmaställ', 'Bortaställ', 'Tredjeställ', 'Egen färg']

  // §9 (UX-lyftet): Gallra som ETT flöde — stegindikatorn är ramen (Mål→Kör→
  // Granska), profilen styr vilka signaler som väger (Din smak är gemensam).
  // Rätt profil förvals ur jobbets kategori (aktiv match → Sport).
  const PROFILER = [
    { id: 'sport', namn: 'Sport', signaler: ['Burst-gräns 2.0 s', 'Tröjnummer-OCR', 'Hemmafärg ur laget', 'Skärpa på bollhöjd'] },
    { id: 'brollop', namn: 'Bröllop', signaler: ['Blundningar bort', 'Dubbletter ihop', 'Ansikten skarpa', 'Mjukt ljus prioriteras'] },
    { id: 'landskap', namn: 'Landskap', signaler: ['Skärpa kant till kant', 'Rak horisont', 'Bracketing-serier ihop', 'Inga burst-straff'] },
    { id: 'portratt', namn: 'Porträtt/Student', signaler: ['Ögon skarpa', 'Blinkningar bort', 'Hudton', 'Pose-varianter ihop'] },
  ]
  let profil = 'sport'
  let profilManuell = false     // manuellt val vinner över jobb-förvalet
  $: if (!profilManuell) profil = aktiv ? 'sport' : profil
  $: aktivProfil = PROFILER.find((p) => p.id === profil)
  // Aktivt steg i ramen: ingen källa → 1 Mål; kör → 2; klar körning → 3 Granska.
  $: steg = kor[lage] ? 2 : res[lage] ? 3 : kalla ? 2 : 1
  // Rapport kör AI:s poängsättning utan att skriva till disk → delar AI:s inställningar.
  const LAGEN = [
    { id: 'ai', namn: 'AI', sub: 'Poängsätter hela tagningen och behåller dina bästa bilder', knapp: 'Kör AI-gallring' },
    { id: 'snabb', namn: 'Snabb', sub: 'Regelbaserad — ingen AI, klar på sekunder för en deadline', knapp: 'Kör snabbgallring' },
    { id: 'rapport', namn: 'Rapport', sub: 'Torrkörning — poängsätter utan att röra disken', knapp: 'Kör rapport' },
  ]
  $: aktivtLage = LAGEN.find((l) => l.id === lage)

  // FEAT-15: telefonens uppladdade original — kortet visas bara när molnet
  // faktiskt har något att hämta (tyst annars, ingen tom yta).
  let molnMappar = []
  let molnStadar = true
  let molnHamtar = null        // gruppnamn under pågående hämtning
  let molnStatus = null        // senaste status-pollen
  let molnPoll = null

  onMount(async () => {
    lagAlla = await listaLag()
    if (!aktiv) aktiv = await aktivMatch()
    if (aktiv?.tid && ai.kick === 'auto') ai.kick = aktiv.tid
    const o = await listaOriginal().catch(() => null)
    if (o?.ok) molnMappar = o.mappar || []
  })
  onDestroy(() => clearInterval(molnPoll))

  const mb = (b) => (b >= 1 << 30 ? `${(b / (1 << 30)).toFixed(1)} GB` : `${Math.round(b / (1 << 20))} MB`)

  async function hamtaHem(mapp) {
    const r = await hamtaOriginal(mapp.namn, molnStadar)
    if (!r?.ok) { molnStatus = { fel: [r?.fel || 'Kunde inte starta hämtningen'] }; return }
    molnHamtar = mapp.namn
    molnStatus = r.status
    molnPoll = setInterval(async () => {
      molnStatus = await originalStatus().catch(() => null)
      if (molnStatus && !molnStatus.pagar) {
        clearInterval(molnPoll)
        molnHamtar = null
        // Klart: hämtade mappen blir källa för gallringen — hela poängen
        // med bryggan ("bilderna väntar när du kommer hem").
        if (molnStatus.klara > 0 && molnStatus.mal) kalla = molnStatus.mal
        if (molnStatus.stadade > 0) {
          const o = await listaOriginal().catch(() => null)
          if (o?.ok) molnMappar = o.mappar || []
        }
      }
    }, 700)
  }

  $: hemlag = aktiv ? lagAlla.find((l) => l.namn === aktiv.lag_hemma) : null
  $: hemFarg = !hemlag ? '#c9bfa8'
    : ai.kit === 'Bortaställ' ? (hemlag.stall_borta || '#ffffff')
    : ai.kit === 'Tredjeställ' ? (hemlag.stall_tredje || '#333333')
    : (hemlag.stall_hemma || hemlag.profilfarg || '#c9bfa8')
  $: hemNote = aktiv?.lag_hemma ? `Hämtas från ${aktiv.lag_hemma} · ${ai.kit.toLowerCase()}` : 'Ingen aktiv match — välj hemmafärg manuellt'
  $: keepPreview = ai.unit === 'procent' ? `≈ ${ai.keep} % av tagningen` : `≈ ${ai.keep} bilder av tagningen`

  async function valjKalla() {
    const r = await valjMapp('Välj källmapp (RAW)')
    if (r.ok) kalla = r.path
  }

  async function kora(vilket) {
    // §9: profilen följer med körningen (framtida signalviktning — Din
    // smak-modellen är gemensam, se CULL-02).
    const cfg = vilket === 'snabb'
      ? { kalla, verktyg: 'snabb', behall: snabb.keep, enhet: 'bilder', burst: snabb.burst, profil }
      : { kalla, verktyg: vilket === 'rapport' ? 'rapport' : 'ai',
          behall: ai.keep, enhet: ai.unit, burst: ai.burst, trojnummer: ai.ocr,
          nummer: ai.nums, hemmafarg: hemFarg, avspark: ai.kick, modell: ai.model,
          match_id: aktiv?.id || null, profil }
    kor[vilket] = true; prog[vilket] = 5; res[vilket] = ''
    // Riktig progress: startaGallring blockar tills workern är klar, men
    // events (5% Laddar modeller… → 95% Extraherar) strömmar löpande in i
    // loggen — polla den och spegla senaste progress-eventet i baren.
    const poll = setInterval(async () => {
      const ev = await hamtaLogg().catch(() => null)
      if (!ev) return
      for (let i = ev.length - 1; i >= 0; i--) {
        const e = ev[i]
        if (e.typ === 'start' || e.typ === 'klar') break
        if (e.typ === 'progress') {
          prog[vilket] = Math.max(prog[vilket], Math.round((e.andel || 0) * 100))
          break
        }
      }
    }, 800)
    try {
      const c = await startaCull(cfg)
      if (c?.urval_id) {
        const g = await startaGallring(c.urval_id)
        res[vilket] = g?.meddelande || (g?.resultat ? `behåller ${g.resultat.behall} av ${g.resultat.totalt}` : 'Klar')
        if (g?.ok) {
          await sattAktivtUrval(c.urval_id)   // nya urvalet blir det aktiva
          dispatch('urval')                   // topbar-chippet uppdaterar sig
        }
      } else {
        res[vilket] = c?.meddelande || 'Urval skapat'
      }
    } finally {
      clearInterval(poll)
      prog[vilket] = 100; kor[vilket] = false
    }
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Gallra</h1>
    <span class="sub">Verktyg som poängsätter och plockar de bästa bilderna</span>
  </header>
  <AktivMatchRad on:navigera />
  <p class="intro">Ett gallringssteg — välj läge, peka ut källmappen och kör. Resultatet kopieras till ett nytt urval.</p>

  <!-- §9: stegindikatorn — ramen för hela flödet -->
  <div class="steg">
    <span class="stegpill" class:pa={steg === 1}><span class="stegnr">1</span>Mål</span>
    <span class="stegpil">→</span>
    <span class="stegpill" class:pa={steg === 2}><span class="stegnr">2</span>Kör <span class="stegsub">— profil per jobbtyp</span></span>
    <span class="stegpil">→</span>
    <span class="stegpill" class:pa={steg === 3}><span class="stegnr">3</span>Granska <span class="stegsub">— dina val tränar modellen tyst</span></span>
  </div>

  <!-- §9: gallringsprofilen — signalerna som väger, förvald ur jobbet -->
  <div class="profkort">
    <div class="profrad">
      <span class="profcaps">Profil</span>
      <div class="profseg">
        {#each PROFILER as p (p.id)}
          <button class:on={profil === p.id} on:click={() => { profil = p.id; profilManuell = true }}>{p.namn}</button>
        {/each}
      </div>
      <span class="profkalla">{profilManuell ? 'Vald manuellt' : aktiv ? 'Förvald ur jobbet (Sport)' : 'Standard'}</span>
    </div>
    <div class="profchips">
      {#each aktivProfil.signaler as s}<span class="profchip">{s}</span>{/each}
    </div>
    <div class="profnot">Din smak-modellen är gemensam — profilen styr bara vilka signaler som väger. Rätt profil förvald ur jobbets kategori.</div>
  </div>

  <div class="kort open">
    <div class="khuvud">
      <span class="kic">
        {#if lage === 'ai'}
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/></svg>
        {:else if lage === 'snabb'}
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2 4 13.5h5.5L8.5 22 19 9.5h-5.5z"/></svg>
        {:else}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4.5" y="3" width="15" height="18" rx="2.2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>
        {/if}
      </span>
      <span class="ktxt">
        <span class="ktitel scd">Gallring</span>
        <span class="ksub">{aktivtLage.sub}</span>
      </span>
      <span class="kstatus">{res[lage] ? 'Klar' : 'Redo'}</span>
    </div>

    <div class="kkropp">
      <div class="lagevaxel">
        {#each LAGEN as l (l.id)}
          <button class:on={lage === l.id} on:click={() => (lage = l.id)}>{l.namn}</button>
        {/each}
      </div>

      <div class="kalla">
        <span class="lbl">Källmapp</span>
        <input bind:value={kalla} placeholder="/Volumes/NIKON Z 8/DCIM/…" />
        <button class="valj" on:click={valjKalla}>Välj…</button>
      </div>

      {#if lage === 'snabb'}
        <div class="rad-inline">
          <div class="frad"><span class="fl">Behåll</span><input class="liten" bind:value={snabb.keep} /><span class="enhet">bilder</span></div>
          <div class="frad"><span class="fl">Burst-gräns</span><input class="liten" bind:value={snabb.burst} /><span class="enhet">sek</span></div>
        </div>
      {:else}
        {#if lage === 'rapport'}
          <p class="rapptext">Torrkörning: inga filer skrivs — resultatet listas i Loggen. Bra för att förhandsbedöma nytt material eller samla facit-underlag inför träning.</p>
        {/if}
        <div class="tvakol">
          <div class="kol">
            <div class="caps">Urval</div>
            <div class="fält">
              <div class="frad"><span class="fl">Behåll</span>
                <input class="liten" bind:value={ai.keep} />
                <select bind:value={ai.unit}><option>bilder</option><option>procent</option></select>
              </div>
              <div class="preview">{keepPreview}</div>
              <div class="frad"><span class="fl">Burst-gräns</span><input class="liten" bind:value={ai.burst} /><span class="enhet">sek</span></div>
              <div class="frad"><button class="box" class:pa={ai.ocr} on:click={() => (ai.ocr = !ai.ocr)}>{ai.ocr ? '✓' : ''}</button><span class="fx">Tröjnummer</span><input class="liten" bind:value={ai.nums} placeholder="11,23" /><span class="mono">OCR</span></div>
              {#if lage === 'ai'}
                <div class="frad"><button class="box" class:pa={ai.overwrite} on:click={() => (ai.overwrite = !ai.overwrite)}>{ai.overwrite ? '✓' : ''}</button><span class="fx">Skriv över befintligt urval</span></div>
              {/if}
            </div>
          </div>
          <div class="kol">
            <div class="caps">Match</div>
            <div class="fält">
              <div class="frad"><span class="fl2">Hemmafärg</span><span class="swatch" style="background:{hemFarg}"></span>
                <select class="vaxa" bind:value={ai.kit}>{#each KIT as k}<option>{k}</option>{/each}</select>
              </div>
              {#if ai.kit === 'Egen färg' && hemlag}
                <div class="frad"><span class="fl2"></span><input type="color" bind:value={hemlag.stall_hemma} class="cpick" /><span class="help">Välj egen färg</span></div>
              {:else}
                <div class="teamnote">{hemNote}</div>
              {/if}
              <div class="frad"><span class="fl2">Avspark</span><input class="liten" bind:value={ai.kick} /><span class="mono">HH:MM</span></div>
              <div class="help lång">Matchfärg och avspark hjälper modellen att vikta rätt lag och rätt skeden.</div>
            </div>
          </div>
        </div>
        <button class="avanc" on:click={() => (adv = !adv)}><span class="achev" class:upp={adv}>›</span> Avancerat: modeller &amp; viktning</button>
        {#if adv}
          <div class="avbox">
            <!-- BUG-CULL-01: value = typnyckeln biblioteket nycklas på (backend
                 normaliserar även gamla etikettvärden) -->
            <div class="frad"><span class="fl3">Modell</span><select bind:value={ai.model} class="vaxa"><option value="din_smak">Din smak</option><option value="arkiv">Arkiv (facit)</option><option value="hybrid">Hybrid</option></select></div>
            <div></div>
            <div class="frad"><span class="fl3">Pose</span><input type="range" min="0" max="100" bind:value={ai.pose} /><span class="mono v">{ai.pose}</span></div>
            <div class="frad"><span class="fl3">Skärpa</span><input type="range" min="0" max="100" bind:value={ai.sharp} /><span class="mono v">{ai.sharp}</span></div>
          </div>
        {/if}
      {/if}

      <div class="korrad">
        <div class="progbar"><div class="progfyll" style="width:{prog[lage]}%"></div></div>
        {#if res[lage]}<span class="ok">✓ {res[lage]}</span>{/if}
        <button class="prim-btn" on:click={() => kora(lage)} disabled={kor[lage] || !kalla}>{kor[lage] ? 'Kör…' : aktivtLage.knapp}</button>
      </div>
    </div>
  </div>

  {#if molnMappar.length}
    <!-- FEAT-15: Mac-sidan av kort→telefon→moln-bryggan -->
    <div class="kort moln">
      <div class="khuvud">
        <span class="kic">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 15a4 4 0 0 1 .6-7.96A5.5 5.5 0 0 1 18.2 8.6 3.5 3.5 0 0 1 17.5 15"/><path d="M12 12v7m0 0-2.5-2.5M12 19l2.5-2.5"/></svg>
        </span>
        <span class="ktxt">
          <span class="ktitel scd">Från telefonen</span>
          <span class="ksub">Original som appen laddat upp i fält — hämta hem och gallra</span>
        </span>
      </div>
      <div class="kkropp">
        {#each molnMappar as m (m.namn)}
          <div class="molnrad">
            <span class="mnamn">{m.namn}</span>
            <span class="minfo">{m.antal} {m.antal === 1 ? 'fil' : 'filer'} · {mb(m.bytes)}</span>
            <button class="prim-btn" on:click={() => hamtaHem(m)} disabled={!!molnHamtar}>
              {molnHamtar === m.namn ? `Hämtar ${molnStatus?.klara ?? 0} av ${molnStatus?.totalt ?? m.antal}…` : 'Hämta hem'}
            </button>
          </div>
        {/each}
        <div class="frad">
          <button class="box" class:pa={molnStadar} on:click={() => (molnStadar = !molnStadar)}>{molnStadar ? '✓' : ''}</button>
          <span class="fx">Städa molnet efter hämtning</span>
          <span class="help">— tas bara bort när filen är verifierat hemma</span>
        </div>
        {#if molnStatus && !molnStatus.pagar && (molnStatus.klara > 0 || molnStatus.fel?.length)}
          <div class="molnres">
            {#if molnStatus.klara > 0}
              <span class="ok">✓ {molnStatus.klara} {molnStatus.klara === 1 ? 'fil' : 'filer'} hemma i {molnStatus.mal}{molnStatus.stadade ? ` · ${molnStatus.stadade} städade ur molnet` : ''} — satt som källmapp</span>
            {/if}
            {#each molnStatus.fel || [] as f}<span class="molnfel">✕ {f}</span>{/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 800px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .intro { margin: 7px 0 18px; font-size: 12px; color: var(--t-help); }

  /* §9: stegindikator + profilkort */
  .steg { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 0 0 16px; }
  .stegpill { display: inline-flex; align-items: center; gap: 7px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 999px; padding: 4px 13px;
    font-size: 11.5px; font-weight: 600; color: var(--t-head); }
  .stegpill.pa { border-color: var(--acc-border); box-shadow: inset 0 0 0 1px var(--acc-border); }
  .stegnr { width: 16px; height: 16px; border-radius: 50%; background: var(--acc); color: var(--kort);
    display: inline-flex; align-items: center; justify-content: center; font-size: 9.5px; font-weight: 700; }
  .stegsub { font-weight: 400; color: var(--t-mut); }
  .stegpil { color: var(--t-help); font-size: 11px; }
  .profkort { background: var(--kort); border: 1px solid var(--div); border-radius: 11px;
    padding: 12px 16px; margin-bottom: 18px; }
  .profrad { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .profcaps { font-size: 9.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--t-caps); flex: none; }
  .profseg { display: inline-flex; background: var(--panel); border: 1px solid var(--div);
    border-radius: 8px; padding: 3px; flex: none; }
  .profseg button { border: 0; background: transparent; color: var(--t-mut); border-radius: 6px;
    padding: 5px 12px; font-size: 12px; font-weight: 600; cursor: pointer; }
  .profseg button.on { background: var(--acc); color: var(--kort); }
  .profkalla { font-size: 11px; color: var(--t-help); flex: none; }
  .profchips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
  .profchip { background: var(--panel); border: 1px solid var(--div); border-radius: 999px;
    padding: 3px 11px; font-size: 11px; color: var(--t-mut); }
  .profnot { font-size: 11px; color: var(--t-help); margin-top: 8px; }

  .kort { border: 1px solid var(--div); border-radius: var(--r); background: var(--kort); box-shadow: var(--skugga); overflow: hidden; }
  .kort.open { border-color: var(--acc-border); }
  .khuvud { display: flex; align-items: center; gap: 14px; width: 100%; padding: 14px 16px; text-align: left; }

  /* F1: lägesväxel — samma segmentkontroll som Lag/Matcher */
  .lagevaxel { display: flex; align-self: flex-start; border: 1px solid var(--div); border-radius: 8px; overflow: hidden; }
  .lagevaxel button { padding: 7px 16px; border: 0; background: var(--panel); color: var(--t-mut);
    font-size: 12.5px; font-weight: 600; cursor: pointer; }
  .lagevaxel button.on { background: var(--acc); color: var(--kort); }
  .kic { width: 42px; height: 42px; border-radius: 11px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .kic svg { width: 22px; height: 22px; }
  .ktxt { flex: 1; min-width: 0; }
  .ktitel { font-size: 17.5px; font-weight: 700; color: var(--t-head); display: flex; align-items: center; gap: 8px; }
  .ksub { display: block; font-size: 12.5px; color: var(--t-mut); margin-top: 2px; }
  .kstatus { font-size: 12px; font-weight: 600; color: var(--ok); flex: none; }

  .kkropp { border-top: 1px solid var(--div3); padding: 18px 16px 16px; display: flex; flex-direction: column; gap: 16px; }
  .kalla { display: flex; align-items: center; gap: 10px; }
  .kalla input { flex: 1; min-width: 0; padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); font-size: 12.5px; font-family: var(--mono, ui-monospace, monospace); outline: none; }
  .lbl { font-size: 13px; color: var(--t-mut); width: 70px; flex: none; }
  .valj { background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 8px 12px; font-size: 12.5px; color: var(--t-mut); flex: none; }

  .tvakol { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-bottom: 14px; }
  .fält { display: flex; flex-direction: column; gap: 13px; }
  .frad { display: flex; align-items: center; gap: 10px; }
  .rad-inline { display: flex; gap: 24px; flex-wrap: wrap; }
  .fl { font-size: 13px; color: var(--t-mut); width: 96px; flex: none; }
  .fl2 { font-size: 13px; color: var(--t-mut); width: 80px; flex: none; }
  .fl3 { font-size: 13px; color: var(--t-mut); width: 64px; flex: none; }
  .fx { font-size: 13px; color: var(--t-head); flex: none; }
  input, select { font-family: inherit; }
  .liten { width: 62px; text-align: center; padding: 7px 9px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); font-size: 13px; outline: none; }
  select { padding: 7px 9px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); font-size: 13px; outline: none; }
  .vaxa { flex: 1; min-width: 0; }
  .enhet, .help { font-size: 12px; color: var(--t-mut); }
  .mono { font-size: 11px; color: var(--t-help); font-family: var(--mono, ui-monospace, monospace); }
  .mono.v { width: 30px; text-align: right; color: var(--t-head); }
  .preview { font-size: 11px; color: var(--t-help); margin-left: 106px; margin-top: -6px; }
  .swatch { width: 20px; height: 20px; border-radius: 6px; border: 1px solid var(--div); flex: none; }
  .cpick { width: 48px; height: 32px; border: 1px solid var(--div); border-radius: 8px; padding: 2px; }
  .teamnote { font-size: 11px; color: var(--t-help); margin-left: 90px; }
  .help.lång { line-height: 1.5; margin-top: 2px; }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel); color: var(--acc); font-size: 12px; flex: none; display: inline-flex; align-items: center; justify-content: center; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }

  .avanc { display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 0; font-size: 13px; color: var(--t-head); font-weight: 500; }
  .achev { color: var(--t-mut); font-size: 15px; transition: transform 0.15s; }
  .achev.upp { transform: rotate(90deg); }
  .avbox { padding: 15px; border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  input[type='range'] { flex: 1; accent-color: var(--acc); }

  .rapptext { font-size: 12.5px; color: var(--t-mut); line-height: 1.55; margin: 0; }
  .korrad { display: flex; align-items: center; gap: 14px; }
  .progbar { flex: 1; height: 6px; border-radius: 4px; background: var(--div3); overflow: hidden; }
  .progfyll { height: 100%; background: var(--acc); transition: width 0.2s; border-radius: 4px; }
  .ok { font-size: 12px; color: var(--ok); font-weight: 600; white-space: nowrap; }
  .prim-btn { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 9px 16px; font-size: 13px; font-weight: 600; flex: none; }
  .prim-btn:disabled { opacity: 0.5; }

  /* FEAT-15: Från telefonen */
  .kort.moln { margin-top: 16px; }
  .molnrad { display: flex; align-items: center; gap: 12px; }
  .mnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head); font-family: var(--mono, ui-monospace, monospace); }
  .minfo { flex: 1; font-size: 12px; color: var(--t-mut); }
  .molnres { display: flex; flex-direction: column; gap: 4px; }
  .molnres .ok { white-space: normal; }
  .molnfel { font-size: 12px; color: var(--fel, #c0524f); }
</style>
