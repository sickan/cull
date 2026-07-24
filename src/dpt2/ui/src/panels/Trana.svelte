<script>
  import { onMount } from 'svelte'
  // §9 (UX-lyftet): panelen bor numera som utfällbar rad i Inställningar —
  // inbäddad slipper den sin egen rubrik/panelram.
  export let inbaddad = false
  import { listaModeller, sattAktivModell, startaTraning, startaOmraknaArkiv,
    valjMapp, listaUrval, larAvMatch, larAvGallring, traningshistorik } from '../lib/api.js'

  const TYP_NAMN = { din_smak: 'Din smak', arkiv: 'Arkiv', hybrid: 'Hybrid' }

  let modeller = []
  let laddar = true
  let trana = { typ: 'arkiv' }
  let arkiv = { root: '' }
  let korOmrakna = false
  let korTrana = false
  let status = null

  // ── Lär av match ──────────────────────────────────────────────────────────
  let urvalval = []          // dropdown-poster {id, namn, kalla, bilder, kalltyp, etikett}
  let valtUrvalId = ''
  let larKor = false
  let larStatus = null       // {ok, meddelande} | {ok:false, fel} | null
  let historik = []

  $: valtUrval = urvalval.find((u) => u.id === valtUrvalId) || null

  $: aktiv = modeller.find((m) => m.aktiv) || null

  onMount(async () => {
    modeller = await listaModeller()
    await laddaLarData()
    laddar = false
  })

  function urvalEtikett(u) {
    if (u.lag_hemma) return `${u.lag_hemma} – ${u.lag_borta}`
    return (u.kalla || '').split('/').pop() || 'Urval'
  }

  async function laddaLarData() {
    const [urval, hist] = await Promise.all([listaUrval('gallrad'), traningshistorik()])
    urvalval = urval.map((u) => {
      const namn = urvalEtikett(u)
      return { id: u.id, namn, kalla: u.kalla, bilder: u.bilder, kalltyp: 'Gallra',
        etikett: `Gallra · ${namn} · ${u.bilder} bilder` }
    })
    historik = hist
  }

  async function valjPmMapp() {
    const r = await valjMapp('Välj Photo Mechanic-mapp')
    if (!r.ok) return
    const namn = (r.path || '').split('/').pop() || 'PM-urval'
    const id = 'pm:' + r.path
    urvalval = [{ id, namn, kalla: r.path, bilder: null, kalltyp: 'PM',
      etikett: `PM · ${namn}` }, ...urvalval.filter((u) => u.id !== id)]
    valtUrvalId = id
    larStatus = null
  }

  async function korLarAvMatch() {
    if (!valtUrval || larKor) return
    larKor = true; larStatus = null
    const r = await larAvMatch(valtUrval.kalla, valtUrval.namn, '')
    larKor = false
    larStatus = r
    if (r.ok) historik = await traningshistorik()
  }

  function aterstallLar() { larStatus = null }

  // ── Lär av gallring (genvägen 24/7): tagning + urval → fullt 1/0-facit ────
  let gallrTagning = ''
  let gallrUrval = ''
  let gallrNamn = ''
  let gallrKor = false
  let gallrStatus = null

  async function valjTagning() {
    const r = await valjMapp('Välj tagningens mapp (hela)')
    if (r.ok) { gallrTagning = r.path; gallrStatus = null
      if (!gallrNamn) gallrNamn = (r.path || '').split('/').pop() || '' }
  }
  async function valjGallrUrval() {
    const r = await valjMapp('Välj urvalets mapp (behållna)')
    if (r.ok) { gallrUrval = r.path; gallrStatus = null }
  }
  async function korLarAvGallring() {
    if (!gallrTagning || !gallrUrval || gallrKor) return
    gallrKor = true; gallrStatus = null
    const r = await larAvGallring(gallrTagning, gallrUrval, gallrNamn, '')
    gallrKor = false
    gallrStatus = r
    if (r.ok) historik = await traningshistorik()
  }

  const MANADER = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function kortDatum(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || '')
    if (!m) return s || ''
    return `${+m[3]} ${MANADER[+m[2] - 1] || ''}`
  }

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
    { id: 'osakra', namn: 'Granska osäkra', info: 'Bilder modellen är osäker på — döm in/ut' },
    { id: 'par', namn: 'Jämför par', info: 'A/B-jämför två bilder för att finslipa smaken' },
    { id: 'histogram', namn: 'Histogram', info: 'Poängfördelning för senaste gallringen' },
  ]

  // ── Granskningsmodal (mock-underlag; tiles = platshållare tills workern
  //    matar miniatyrer/poäng ur urvalet — Design-prototypen är också platshållare)
  const TROSKEL = 0.5
  let granska = null          // 'osakra' | 'par' | 'histogram' | null (stängd)

  let osakra = [
    { stem: '_D5A1042', poang: 0.52, orsak: 'burst · rörelse', beslut: null },
    { stem: '_D5A1058', poang: 0.47, orsak: 'blund', beslut: null },
    { stem: '_D5A1090', poang: 0.55, orsak: 'skärpa', beslut: null },
    { stem: '_D5A1113', poang: 0.44, orsak: 'motljus', beslut: null },
    { stem: '_D5A1147', poang: 0.61, orsak: 'burst', beslut: null },
    { stem: '_D5A1180', poang: 0.39, orsak: 'väst framför', beslut: null },
    { stem: '_D5A1201', poang: 0.5, orsak: 'komposition', beslut: null },
    { stem: '_D5A1233', poang: 0.48, orsak: 'rörelse', beslut: null },
  ]
  let par = [
    { a: { stem: '_D5A1042', poang: 0.52 }, b: { stem: '_D5A1043', poang: 0.5 }, val: null },
    { a: { stem: '_D5A1090', poang: 0.55 }, b: { stem: '_D5A1091', poang: 0.58 }, val: null },
    { a: { stem: '_D5A1147', poang: 0.61 }, b: { stem: '_D5A1148', poang: 0.6 }, val: null },
    { a: { stem: '_D5A1201', poang: 0.5 }, b: { stem: '_D5A1202', poang: 0.41 }, val: null },
  ]
  // Histogram-buckets (0.0–1.0 i 10 steg) från "senaste gallringen".
  const hist = [3, 7, 12, 21, 34, 41, 38, 47, 62, 55]
    .map((n, i) => ({ lo: i / 10, hi: (i + 1) / 10, n }))
  const histMax = Math.max(...hist.map((b) => b.n))

  $: osakraBedomda = osakra.filter((o) => o.beslut).length
  $: osakraBehall = osakra.filter((o) => o.beslut === 'behall').length
  $: histTotal = hist.reduce((s, b) => s + b.n, 0)
  $: histOver = hist.filter((b) => b.lo >= TROSKEL).reduce((s, b) => s + b.n, 0)

  function oppnaGranska(id) { granska = id }
  function stangGranska() { granska = null }
  function domOsakra(o, b) { o.beslut = b; osakra = osakra }
  function valjPar(p, sida) { p.val = sida; par = par }
  function barFarg(b) {
    if (b.hi <= TROSKEL) return 'var(--t-mut)'                 // helt under → gallras
    if (b.lo >= TROSKEL) return 'var(--ok)'                    // helt över → behålls
    return `linear-gradient(90deg, var(--t-mut) 50%, var(--ok) 50%)`   // korsar tröskeln
  }
</script>

<svelte:window on:keydown={(e) => { if (e.key === 'Escape') stangGranska() }} />

<div class="panel" class:inbaddad>
  {#if !inbaddad}
    <header>
      <h1 class="scd">Träna</h1>
      <span class="sub">Lär modellen din smak — biblioteket lever här, träningen körs i ML-workern</span>
    </header>
  {/if}

  {#if laddar}
    <p class="tom">Laddar modeller…</p>
  {:else}
    <!-- Lär av match — den vardagliga feedback-loopen efter en gallring -->
    <div class="kort larkort">
      <div class="larhuvud">
        <span class="larikon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M12 3l1.9 4.9L19 9.8l-4 3.4 1.2 5.3L12 15.9 7.8 18.5 9 13.2 5 9.8l5.1-1.9z"/>
          </svg>
        </span>
        <div>
          <div class="lartitel scd">Lär av match</div>
          <p class="larbesk">Märk ett gallrat urval som träningsdata — modellen lär sig
            din stil inför nästa AI-gallring. Fungerar med urval från Gallra eller egna
            gallringar i Photo Mechanic.</p>
        </div>
      </div>

      <label class="full">Urval
        <select bind:value={valtUrvalId} on:change={aterstallLar}>
          <option value="" disabled>Välj gallrat urval…</option>
          {#each urvalval as u (u.id)}
            <option value={u.id}>{u.etikett}</option>
          {/each}
        </select>
      </label>

      {#if valtUrval}
        <div class="statusrad">
          <span class="sprick"></span>
          {#if valtUrval.bilder != null}{valtUrval.bilder} bilder i urvalet · {/if}läses från urvalets mapp
        </div>
      {/if}

      <div class="larslot">
        {#if larKor}
          <div class="larbar korbar"><span class="spinner"></span> Märker bilder…</div>
        {:else if larStatus && larStatus.ok}
          <div class="larbar okbar">
            <span class="bock">✓</span>
            <span class="larmed">{larStatus.meddelande}</span>
            <button class="sek" on:click={aterstallLar}>Kör igen</button>
          </div>
        {:else if larStatus && !larStatus.ok}
          <div class="larbar felbar">
            <span class="larmed">{larStatus.fel}</span>
            <button class="sek" on:click={aterstallLar}>Försök igen</button>
          </div>
        {:else}
          <button class="sek pmknapp" on:click={valjPmMapp}>Välj PM-mapp…</button>
          <button class="prim" on:click={korLarAvMatch} disabled={!valtUrval}>Märk och lär</button>
        {/if}
      </div>
    </div>

    <!-- Lär av gallring (genvägen 24/7): tagning + urval → fullt 1/0-facit i
         ett steg. Till skillnad från Lär av match (bara positiva) märks HELA
         tagningen: behållna = 1, bortgallrade = 0. -->
    <div class="kort larkort">
      <div class="larhuvud">
        <span class="larikon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M4 7h7M4 12h7M4 17h7"/><path d="M15 7l2 2 4-4"/>
            <path d="M15.5 15.5l4 4M19.5 15.5l-4 4"/>
          </svg>
        </span>
        <div>
          <div class="lartitel scd">Lär av gallring</div>
          <p class="larbesk">Gallrade du manuellt? Peka på HELA tagningen och din
            urvalsmapp — behållna märks 1, bortgallrade 0. Fullt facit i ett steg,
            ingen maskingallring krävs (matchning på filstam/frame-id, NEF funkar).</p>
        </div>
      </div>

      <div class="mapprad">
        <button class="sek" on:click={valjTagning}>Tagningen…</button>
        <span class="mappvag" class:tom={!gallrTagning}>{gallrTagning || 'hela tagningens mapp (NEF/JPG)'}</span>
      </div>
      <div class="mapprad">
        <button class="sek" on:click={valjGallrUrval}>Urvalet…</button>
        <span class="mappvag" class:tom={!gallrUrval}>{gallrUrval || 'mappen med de behållna bilderna'}</span>
      </div>
      <label class="full">Namn (t.ex. gren/pass)
        <input bind:value={gallrNamn} placeholder="Friidrotts-SM · Höjd final" />
      </label>

      <div class="larslot">
        {#if gallrKor}
          <div class="larbar korbar"><span class="spinner"></span> Extraherar features ur tagningen — kan ta flera minuter…</div>
        {:else if gallrStatus && gallrStatus.ok}
          <div class="larbar okbar">
            <span class="bock">✓</span>
            <span class="larmed">{gallrStatus.meddelande}</span>
            <button class="sek" on:click={() => (gallrStatus = null)}>Kör igen</button>
          </div>
        {:else if gallrStatus && !gallrStatus.ok}
          <div class="larbar felbar">
            <span class="larmed">{gallrStatus.fel}</span>
            <button class="sek" on:click={() => (gallrStatus = null)}>Försök igen</button>
          </div>
        {:else}
          <button class="prim" on:click={korLarAvGallring} disabled={!gallrTagning || !gallrUrval}>Märk och lär</button>
        {/if}
      </div>
    </div>

    <div class="kort">
      <div class="cardH">Träningshistorik</div>
      {#if historik.length === 0}
        <p class="not">Ingen träningsdata märkt än. Välj ett gallrat urval ovan och klicka "Märk och lär".</p>
      {:else}
        <div class="histlista">
          {#each historik as h (h.id)}
            <div class="histrad">
              <span class="hnamn">{h.match_namn}</span>
              <span class="hmeta">{h.n} bilder · {kortDatum(h.skapad)}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    {#if aktiv}
      <div class="aktiv">
        <span class="prick"></span>
        <div>
          <div class="caps">Aktiv modell</div>
          <div class="namn scd">{TYP_NAMN[aktiv.typ] || aktiv.typ}<span class="inne">{aktiv.n_uppdrag ?? 0} matcher inne</span></div>
          <div class="meta">{aktiv.n_valda ?? '–'} valda · {aktiv.sparad || ''}</div>
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
          <button class="vrad" on:click={() => oppnaGranska(g.id)}>
            <div>
              <div class="vnamn">{g.namn}</div>
              <div class="vinfo">{g.info}</div>
            </div>
            <span class="oppna">Öppna ›</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

{#if granska}
  <div class="overlay" on:click|self={stangGranska}>
    <div class="modal">
      <div class="modalH">
        <div class="seg">
          {#each GRANSKNING as g}
            <button class:on={granska === g.id} on:click={() => (granska = g.id)}>{g.namn}</button>
          {/each}
        </div>
        <button class="stang" on:click={stangGranska} title="Stäng (Esc)">×</button>
      </div>

      <div class="modalB">
        {#if granska === 'osakra'}
          <div class="rakn">{osakra.length} gränsfall · {osakraBedomda} bedömda · {osakraBehall} behålls</div>
          <div class="rutnat">
            {#each osakra as o (o.stem)}
              <div class="tile" class:bedomd={o.beslut}>
                <div class="bild" class:bort={o.beslut === 'kasta'}>
                  <span class="pbadge" style="background:{o.poang >= TROSKEL ? 'var(--ok)' : 'var(--sol)'}">{o.poang.toFixed(2)}</span>
                </div>
                <div class="tinfo">
                  <span class="fnamn">{o.stem}</span>
                  <span class="orsak">{o.orsak}</span>
                </div>
                <div class="tknapp">
                  <button class:vald={o.beslut === 'behall'} on:click={() => domOsakra(o, 'behall')}>Behåll</button>
                  <button class:kasta={o.beslut === 'kasta'} on:click={() => domOsakra(o, 'kasta')}>Kasta</button>
                </div>
              </div>
            {/each}
          </div>
          <p class="modalNot">Besluten blir facit som tränar modellen (matas till workern).</p>

        {:else if granska === 'par'}
          <div class="rakn">{par.length} par · välj den bästa bilden i varje</div>
          <div class="parlista">
            {#each par as p (p.a.stem)}
              <div class="parrad">
                {#each [['a', p.a], ['b', p.b]] as [sida, bild]}
                  <button class="parbild" class:vald={p.val === sida} on:click={() => valjPar(p, sida)}>
                    <div class="bild">
                      <span class="pbadge" style="background:{bild.poang >= TROSKEL ? 'var(--ok)' : 'var(--sol)'}">{bild.poang.toFixed(2)}</span>
                      {#if p.val === sida}<span class="valdbock">✓</span>{/if}
                    </div>
                    <span class="fnamn">{bild.stem}</span>
                  </button>
                {/each}
              </div>
            {/each}
          </div>

        {:else if granska === 'histogram'}
          <div class="rakn">{histTotal} bilder poängsatta · tröskel {TROSKEL.toFixed(2)} · {histOver} över tröskeln</div>
          <div class="hist">
            {#each hist as b}
              <div class="stapel">
                <div class="bar" style="height:{Math.round((b.n / histMax) * 130) + 4}px;background:{barFarg(b)}" title="{b.n} bilder"></div>
                <span class="xlbl">{b.lo.toFixed(1)}</span>
              </div>
            {/each}
          </div>
          <div class="legend">
            <span><i style="background:var(--ok)"></i> Behålls (≥ tröskel)</span>
            <span><i style="background:var(--t-mut)"></i> Gallras (&lt; tröskel)</span>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .panel { padding: 22px 26px 48px; max-width: 820px; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .aktiv { display: flex; gap: 12px; align-items: center; margin: 18px 0;
    padding: 12px 14px; background: var(--acc-soft); border-radius: var(--r); }
  .prick { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); flex: none; }
  .namn { font-size: 16px; font-weight: 700; color: var(--t-head); display: flex; align-items: center; gap: 9px; }
  .inne { font-size: 11px; font-weight: 600; color: var(--acc); background: var(--acc-soft); padding: 2px 8px; border-radius: 5px; }
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
    width: 100%; padding: 10px 14px; border: 1px solid var(--div3); border-radius: 10px;
    background: var(--panel); text-align: left; cursor: pointer; }
  .vrad:hover { border-color: var(--acc); }
  .vnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .vinfo { font-size: 12px; color: var(--t-mut); }
  .oppna { font-size: 12.5px; font-weight: 600; color: var(--acc); flex: none; }

  /* Granskningsmodal */
  .overlay { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center;
    justify-content: center; padding: 24px; background: rgba(20, 16, 8, 0.44); }
  .modal { width: min(880px, 100%); max-height: 88vh; display: flex; flex-direction: column;
    background: var(--kort); border: 1px solid var(--div); border-radius: 14px;
    box-shadow: 0 20px 60px rgba(30, 22, 8, 0.35); overflow: hidden; }
  .modalH { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 16px; border-bottom: 1px solid var(--div3); }
  .seg { display: flex; border: 1px solid var(--div); border-radius: 9px; overflow: hidden; }
  .seg button { padding: 7px 14px; border: 0; background: var(--panel); color: var(--t-mut);
    font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; }
  .seg button.on { background: var(--acc); color: var(--kort); }
  .stang { width: 30px; height: 30px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-mut); font-size: 17px; line-height: 1; cursor: pointer; }
  .stang:hover { background: var(--div3); }
  .modalB { padding: 16px; overflow-y: auto; }
  .rakn { font-size: 12px; font-weight: 600; color: var(--t-caps); text-transform: uppercase;
    letter-spacing: 0.04em; margin-bottom: 12px; }
  .modalNot { font-size: 11.5px; color: var(--t-help); margin: 12px 0 0; }

  .rutnat { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .tile { border: 1px solid var(--div); border-radius: 10px; overflow: hidden; background: var(--panel); }
  .tile.bedomd { border-color: var(--acc); }
  .bild { position: relative; aspect-ratio: 3 / 2;
    background: repeating-linear-gradient(45deg, var(--div3) 0 8px, transparent 8px 16px), var(--sand); }
  .bild.bort { opacity: 0.4; }
  .pbadge { position: absolute; top: 6px; left: 6px; padding: 2px 7px; border-radius: 999px;
    font-size: 11px; font-weight: 700; color: #fff; font-family: 'Saira Condensed', sans-serif; }
  .valdbock { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    font-size: 30px; font-weight: 700; color: var(--acc); background: var(--acc-soft); }
  .tinfo { display: flex; flex-direction: column; gap: 1px; padding: 7px 9px 4px; }
  .fnamn { font-family: var(--mono, ui-monospace, monospace); font-size: 11px; color: var(--t-head); }
  .orsak { font-size: 11px; color: var(--t-mut); }
  .tknapp { display: flex; gap: 6px; padding: 4px 9px 9px; }
  .tknapp button { flex: 1; padding: 5px; border: 1px solid var(--div); border-radius: 7px;
    background: var(--kort); color: var(--t-mut); font: inherit; font-size: 11.5px; font-weight: 600; cursor: pointer; }
  .tknapp button.vald { background: color-mix(in srgb, var(--ok) 16%, transparent); border-color: var(--ok); color: var(--ok); }
  .tknapp button.kasta { background: color-mix(in srgb, var(--rose) 16%, transparent); border-color: var(--rose); color: var(--rose); }

  .parlista { display: flex; flex-direction: column; gap: 12px; }
  .parrad { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .parbild { border: 1.5px solid var(--div); border-radius: 10px; overflow: hidden; background: var(--panel);
    padding: 0 0 7px; cursor: pointer; }
  .parbild.vald { border-color: var(--acc); }
  .parbild .fnamn { display: block; padding: 6px 9px 0; }

  .hist { display: flex; align-items: flex-end; gap: 6px; height: 160px; padding: 8px 4px 0; }
  .stapel { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; justify-content: flex-end; }
  .bar { width: 100%; border-radius: 4px 4px 0 0; }
  .xlbl { font-size: 10px; color: var(--t-mut); }
  .legend { display: flex; gap: 18px; margin-top: 12px; font-size: 12px; color: var(--t-mut); }
  .legend span { display: flex; align-items: center; gap: 6px; }
  .legend i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }

  .sek { padding: 8px 14px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--kort); color: var(--t-head); font-size: 13px; font-weight: 500; }
  .sek:hover { background: var(--div3); }
  .sek:disabled { opacity: 0.5; cursor: default; }
  .prim { padding: 9px 18px; border: 0; border-radius: 8px; background: var(--acc);
    color: var(--kort); font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; cursor: default; }

  /* Lär av match */
  .larkort { margin-top: 18px; }
  .larhuvud { display: flex; gap: 14px; align-items: flex-start; }
  .larikon { flex: none; width: 40px; height: 40px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    background: var(--acc-soft); color: var(--acc); }
  .larikon svg { width: 22px; height: 22px; }
  .lartitel { font-size: 17px; font-weight: 700; color: var(--t-head); }
  .larbesk { margin: 4px 0 0; font-size: 12.5px; line-height: 1.5; color: var(--t-mut); }

  .statusrad { display: flex; align-items: center; gap: 8px; margin: -4px 0 0;
    font-size: 12px; color: var(--t-mut); }
  .sprick { width: 7px; height: 7px; border-radius: 50%; background: var(--sol); flex: none; }

  .larslot { display: flex; align-items: center; gap: 10px; }
  .pmknapp { margin-right: auto; }
  .larbar { display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 11px 14px; border-radius: var(--r); font-size: 12.5px; font-weight: 500; }
  .larbar .larmed { flex: 1; }
  .larbar .sek { flex: none; }
  .korbar { color: var(--t-mut); background: var(--panel); border: 1px solid var(--div3); }
  .okbar { color: var(--ok); background: color-mix(in srgb, var(--ok) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--ok) 32%, transparent); }
  .okbar .bock { font-weight: 700; flex: none; }
  .felbar { color: var(--rose); background: color-mix(in srgb, var(--rose) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--rose) 32%, transparent); }
  .spinner { width: 14px; height: 14px; flex: none; border-radius: 50%;
    border: 2px solid var(--div); border-top-color: var(--acc); animation: snurr 0.7s linear infinite; }
  @keyframes snurr { to { transform: rotate(360deg); } }

  /* Träningshistorik */
  .histlista { display: flex; flex-direction: column; gap: 2px; }
  .histrad { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 9px 4px; border-bottom: 1px solid var(--div3); }
  .histrad:last-child { border-bottom: 0; }
  .hnamn { font-size: 13.5px; font-weight: 600; color: var(--t-head); min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hmeta { font-size: 12px; color: var(--t-mut); flex: none; }
  .panel.inbaddad { padding: 4px 0 8px; max-width: none; }
  /* Lär av gallring */
  .mapprad { display: flex; align-items: center; gap: 9px; margin-top: 9px; }
  .mappvag { font-size: 12px; color: var(--t-head); overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; direction: rtl; text-align: left; }
  .mappvag.tom { color: var(--t-help); direction: ltr; }
</style>
