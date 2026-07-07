<script>
  // Sammanhållet match-huvud — slår ihop forna AktivMatchRad-remsan och den
  // svarta ResultatRemsan till ETT ljust huvud (Design: design_handoff_
  // matchhuvud_webb, skärmbild 01–03). Ljus tavla (temavariabler, följer mörkt
  // läge), gren-färg = 5px vänsterkant + mjuk glow (ingen textetikett, ingen
  // kant om gren okänd — låst yta). Resultat/mellan/målskyttar skrivs direkt på
  // matchposten (samma källa som Live-mallen och Webb-fälten speglar).
  import { createEventDispatcher } from 'svelte'
  import { sattResultat } from './api.js'
  import Lagbricka from './Lagbricka.svelte'
  import { grenFarg } from './gren.js'

  export let match = null
  export let profil = { res_label: 'Slutresultat', res_ph: '6–0', mid_label: 'Halvtid',
    mid_ph: '3–0', has_scorers: true, scorers_label: 'Målskyttar' }
  export let lagAlla = []
  export let materials = []      // Publiceras allMaterial (DB + test) — härleder kopplat material
  export let matcher = []        // matchlista för Byt-väljaren (allaMatcher)

  const dispatch = createEventDispatcher()

  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }
  function loggaForLag(namn) { return lagAlla.find((x) => x.namn === namn)?.logga || '' }

  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  function datumTxt(iso) {
    const d = (iso || '').split('-').map(Number)
    return d.length === 3 ? `${d[2]} ${MK[d[1] - 1]}` : ''
  }

  // ── Gren-färg ur hemmalagets gren (låst: ingen kant om gren okänd) ──────────
  $: grenPa = !!match?.hem_gren
  $: grenC = grenFarg(match?.hem_gren)
  function _rgba(hex, a) { const n = parseInt((hex || '#8A8172').replace('#', ''), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})` }
  $: huvudStil = grenPa
    ? `border-left:5px solid ${grenC}; box-shadow: var(--skugga), 0 0 0 1px ${_rgba(grenC, 0.25)}, 0 0 14px ${_rgba(grenC, 0.18)};`
    : ''

  // ── Resultat/mellan/målskyttar (autospar, identisk logik som ResultatRemsa) ─
  let resultat = ''
  let mellan = ''
  let malskyttar = ''
  let savedAt = ''
  let laddar = false
  let saveTimer = null

  $: _resync(match?.id)
  function _resync() {
    laddar = true
    resultat = match?.resultat || ''
    mellan = match?.mellan || ''
    malskyttar = match?.malskyttar || ''
    savedAt = ''
    bytOpen = false; pending = null
    setTimeout(() => (laddar = false), 0)
  }
  function schedule() {
    if (laddar || !match?.id) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      await sattResultat(match.id, resultat, mellan, malskyttar)
      const d = new Date()
      savedAt = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    }, 500)
  }
  $: if (match?.id) { resultat; mellan; malskyttar; schedule() }

  $: chips = _chipify(malskyttar)
  function _chipify(raw) {
    const delar = (raw || '').split(',').map((s) => s.trim()).filter(Boolean)
    const ut = []
    for (const d of delar) {
      const harNamn = /[a-zA-ZåäöÅÄÖ]/.test(d.replace(/\d+'?/g, ''))
      if (harNamn || !ut.length) ut.push(d)
      else ut[ut.length - 1] += ', ' + d
    }
    return ut
  }
  let scorersOpen = false
  let scorersRaw = ''
  function oppnaScorers() { scorersRaw = malskyttar; scorersOpen = true }
  function stangScorers() { malskyttar = scorersRaw; scorersOpen = false }

  // ── Kopplat material (härlett, inget nytt lagras) ──────────────────────────
  // (materials/matcher kan vara undefined en tick under förälderns init — i
  // Svelte gäller prop-defaulten inte när undefined skickas in; guarda därför.)
  $: mForMatch = (materials || []).filter((m) => m.match_id === match?.id)
  $: utkastN = mForMatch.filter((m) => m.status === 'utkast').length
  $: publiceratN = mForMatch.filter((m) => m.status === 'publicerad').length
  function pillState(kind) {
    // mForMatch läses inuti funktionen → Svelte ser inte beroendet, så denna
    // reaktiva sats kan köras innan mForMatch beräknats; guarda mot undefined.
    const rows = (mForMatch || []).filter((m) => m.kind === kind)
    if (rows.some((m) => m.status === 'publicerad')) return 'pub'
    if (rows.length) return 'utk'
    return 'ingen'
  }
  $: livePill = pillState('live')
  $: somePill = pillState('some')
  $: webbPill = match?.sida_url ? 'pub' : 'ingen'
  const pillMark = { pub: '✓', utk: '·', ingen: '–' }

  // ── Byt aktiv match (inline väljare + bekräftelse) ─────────────────────────
  let bytOpen = false
  let pending = null
  $: bytLista = (matcher || []).filter((m) => m.id !== match?.id)
    .sort((a, b) => (a.datum || '9999').localeCompare(b.datum || '9999'))
  function valjRad(m) { pending = m; bytOpen = false }
  function bekraftaByt() { const id = pending?.id; pending = null; if (id) dispatch('byt', id) }
  function avbrytByt() { pending = null }
  const bildUrl = (p) => (/^(https?|file):/.test(p) ? p : 'file://' + p)
</script>

{#if match}
  <div class="mh" style={huvudStil}>
    <!-- Rad 1: resultat + fixtur + målskyttar -->
    <div class="mh-top">
      <div class="mh-score">
        <Lagbricka namn={match.lag_hemma} farg={fargForLag(match.lag_hemma)} logga={loggaForLag(match.lag_hemma)} storlek={34} />
        <input class="res scd" bind:value={resultat} placeholder={profil.res_ph} size="5" />
        <Lagbricka namn={match.lag_borta} farg={fargForLag(match.lag_borta)} logga={loggaForLag(match.lag_borta)} storlek={34} />
      </div>
      <div class="mh-mitt">
        <div class="fixtur scd">{match.lag_hemma} – {match.lag_borta}</div>
        <div class="undertext">
          {profil.mid_label}
          <input class="mid" bind:value={mellan} placeholder={profil.mid_ph} size="10" />
          {#if match.liga}· {match.liga}{/if}
        </div>
      </div>
      {#if profil.has_scorers}
        <div class="chips">
          {#if scorersOpen}
            <input class="scorersinput" bind:value={scorersRaw} placeholder="Efternamn 10', efternamn 25'…"
              on:keydown={(e) => e.key === 'Enter' && stangScorers()} />
            <button class="klar" on:click={stangScorers}>Klar</button>
          {:else}
            {#each chips as c}<span class="chip">{c}</span>{/each}
            <button class="laggmal" on:click={oppnaScorers}>+ mål</button>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Rad 2: status + byt + inaktivera -->
    <div class="mh-actions">
      <span class="aktiv"><span class="prick"></span>AKTIV</span>
      <button class="mhbtn" class:on={bytOpen} on:click={() => { bytOpen = !bytOpen; pending = null }}>Byt ▾</button>
      <button class="mhbtn" on:click={() => dispatch('inaktivera')}>Inaktivera</button>
    </div>

    {#if bytOpen}
      <div class="bytlista">
        <div class="byttopp">
          <span class="caps">Välj match</span>
          <button class="allalank" on:click={() => dispatch('navigera', 'matcher')}>Alla matcher ›</button>
        </div>
        {#each bytLista as m (m.id)}
          <button class="bytrad" on:click={() => valjRad(m)}>
            <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
            <span class="bytnamn">{m.lag_hemma} – {m.lag_borta}</span>
            <span class="bytmeta">{[datumTxt(m.datum), m.resultat].filter(Boolean).join(' · ')}</span>
          </button>
        {/each}
        {#if !bytLista.length}<div class="bytingen">Inga andra matcher.</div>{/if}
      </div>
    {/if}

    {#if pending}
      <div class="bekrafta">
        <div class="bektxt">Byt aktiv match till <b>{pending.lag_hemma} – {pending.lag_borta}</b>? Pågående arbete sparas kvar på nuvarande match.</div>
        <div class="bekknappar">
          <button class="sek" on:click={avbrytByt}>Avbryt</button>
          <button class="prim" on:click={bekraftaByt}>Byt match</button>
        </div>
      </div>
    {/if}

    <div class="mh-delare"></div>

    <!-- Rad 3: länkar + kopplat material -->
    <div class="mh-bottom">
      <div class="mh-lankar">
        {#if match.galleri}<a class="lank" href={match.galleri} target="_blank" rel="noreferrer">Pixieset</a>{/if}
        {#if match.sida_url}<a class="lank" href={match.sida_url} target="_blank" rel="noreferrer">På hemsidan</a>{/if}
        {#if match.arena}<span class="arena">{match.arena}</span>{/if}
      </div>
      <div class="mh-material">
        <span class="mtxt">{utkastN} utkast · {publiceratN} publicerat</span>
        <span class="kpill" class:pub={livePill === 'pub'} class:utk={livePill === 'utk'}>LIVE {pillMark[livePill]}</span>
        <span class="kpill" class:pub={somePill === 'pub'} class:utk={somePill === 'utk'}>SOME {pillMark[somePill]}</span>
        <span class="kpill" class:pub={webbPill === 'pub'}>WEBB {pillMark[webbPill]}</span>
      </div>
    </div>
  </div>
{:else}
  <div class="mhtom">
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--t-mut)" stroke-width="1.7"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
    <div class="mhtomtxt">Ingen aktiv match — stegen fungerar ändå, men koppla en match för genvägar och auto-ifyllnad.</div>
    <button class="mhtombtn" on:click={() => dispatch('navigera', 'matcher')}>Välj match i Matcher ›</button>
  </div>
{/if}

<style>
  .mh { background: var(--kort); border: 1px solid var(--div); border-left: 5px solid var(--div);
    border-radius: var(--r); box-shadow: var(--skugga); padding: 12px 16px 11px; margin-bottom: 16px; }

  .mh-top { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
  .mh-score { display: flex; align-items: center; gap: 10px; flex: none; }
  .res { width: auto; font-size: 26px; font-weight: 700; color: var(--ink); line-height: 1;
    background: transparent; border: none; border-bottom: 1px dashed var(--div); text-align: center; font-family: var(--font-c); }
  .mh-mitt { flex: none; }
  .fixtur { font-size: 14px; font-weight: 600; color: var(--t-head); }
  .undertext { font-size: 11px; color: var(--t-mut); display: flex; align-items: center; gap: 4px; }
  .mid { background: transparent; border: none; border-bottom: 1px dashed var(--div);
    font-family: 'SF Mono', Menlo, monospace; font-size: 11px; color: var(--t-mut); padding: 1px 2px; }
  .chips { display: flex; align-items: center; gap: 5px; flex: 1; min-width: 160px; flex-wrap: wrap; justify-content: flex-end; }
  .chip { font-size: 11px; font-weight: 600; background: var(--acc-soft); color: var(--t-head);
    border: 1px solid var(--div3); border-radius: 999px; padding: 3px 10px; }
  .laggmal { font-size: 11px; font-weight: 600; background: transparent; color: var(--t-mut);
    border: 1px dashed var(--div); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
  .scorersinput { flex: 1; min-width: 180px; background: var(--panel); border: 1px solid var(--div);
    border-radius: 999px; padding: 4px 12px; color: var(--ink); font-size: 12px; }
  .klar { font-size: 11px; font-weight: 600; color: var(--acc); background: transparent; border: none; cursor: pointer; }

  .mh-actions { display: flex; align-items: center; gap: 8px; margin-top: 11px; }
  .aktiv { display: inline-flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--ok); background: rgba(47, 158, 110, 0.12);
    border-radius: 999px; padding: 4px 10px; }
  .prick { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); }
  .mhbtn { font-size: 12px; font-weight: 600; color: var(--t-mut); background: var(--panel);
    border: 1px solid var(--div); border-radius: 999px; padding: 4px 12px; }
  .mhbtn:hover, .mhbtn.on { border-color: var(--acc-border); color: var(--acc); }

  .bytlista { margin-top: 10px; border: 1px solid var(--div); border-radius: 10px; background: var(--panel); overflow: hidden; }
  .byttopp { display: flex; align-items: center; justify-content: space-between; padding: 7px 12px 5px; }
  .caps { font-size: 9.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t-caps); }
  .allalank { font-size: 11px; font-weight: 600; color: var(--acc); background: none; border: none; }
  .bytrad { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
    padding: 8px 12px; background: none; border: none; border-top: 1px solid var(--div3); }
  .bytrad:hover { background: var(--acc-soft); }
  .grendot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
  .bytnamn { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: var(--t-head); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bytmeta { font-size: 11px; color: var(--t-mut); flex: none; }
  .bytingen { padding: 10px 12px; font-size: 12px; color: var(--t-mut); }

  .bekrafta { margin-top: 10px; border: 1px solid var(--acc-border); background: var(--acc-soft);
    border-radius: 10px; padding: 12px 14px; }
  .bektxt { font-size: 12.5px; color: var(--t-head); line-height: 1.45; }
  .bekknappar { display: flex; gap: 8px; margin-top: 10px; }
  .bekknappar .sek { font-size: 12px; font-weight: 600; color: var(--t-mut); background: var(--panel);
    border: 1px solid var(--div); border-radius: 7px; padding: 6px 14px; }
  .bekknappar .prim { font-size: 12px; font-weight: 600; color: var(--ink); background: var(--acc);
    border: none; border-radius: 7px; padding: 6px 14px; }

  .mh-delare { height: 1px; background: var(--div3); margin: 11px 0 9px; }

  .mh-bottom { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .mh-lankar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .lank { display: inline-flex; align-items: center; padding: 3px 10px; border: 1px solid var(--div);
    border-radius: 999px; background: var(--panel); color: var(--t-mut); font-size: 11px; font-weight: 600; text-decoration: none; }
  .lank:hover { border-color: var(--acc); color: var(--acc); }
  .arena { font-size: 11.5px; color: var(--t-help); }
  .mh-material { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
  .mtxt { font-size: 11.5px; color: var(--t-mut); }
  .kpill { font-size: 10px; font-weight: 700; letter-spacing: 0.05em; color: var(--t-caps);
    background: var(--panel); border: 1px solid var(--div); border-radius: 999px; padding: 2px 9px; }
  .kpill.pub { color: var(--ok); border-color: rgba(47, 158, 110, 0.4); background: rgba(47, 158, 110, 0.1); }
  .kpill.utk { color: var(--varn); border-color: rgba(201, 138, 47, 0.4); background: rgba(201, 138, 47, 0.1); }

  .mhtom { display: flex; align-items: center; gap: 12px; background: var(--panel); border: 1px dashed var(--div);
    border-radius: 11px; padding: 10px 14px; margin-bottom: 16px; }
  .mhtom svg { flex: none; }
  .mhtomtxt { flex: 1; min-width: 0; font-size: 12.5px; color: var(--t-mut); }
  .mhtombtn { flex: none; background: var(--acc); color: var(--ink); border: none; border-radius: 7px;
    padding: 6px 12px; font-size: 12px; font-weight: 600; }
</style>
