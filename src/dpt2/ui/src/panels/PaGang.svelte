<script>
  // Webb → På gång (§C, handoff v2). Den kurerade Sport-startside-/På gång-listan
  // flyttad till en egen nav-post: kommande matcher & tävlingar, härledda ur
  // Matcher, med publicerad-toggle + .md-synk till sport-startsidan på webben.
  // Funktionellt oförändrad mot den tidigare inbäddade editorn i Innehåll — bara
  // flyttad hit och med egen rubrik (ingen bibliotek-länk).
  import { onMount } from 'svelte'
  import { pagangMatcher, sattPagangVisa, publiceraPagangMatcher } from '../lib/api.js'
  import { grenFarg } from '../lib/gren.js'
  import { testMode } from '../lib/testlage.js'

  const MK = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
  let pagang = []
  let pagangVisa = true
  let pagangKor = false
  let pagangFlash = ''

  onMount(laddaPagang)
  async function laddaPagang() {
    const r = await pagangMatcher()
    if (r?.ok) {
      // Matcher + tävlingsperioder (heldagsaktiviteter) i en kronologisk lista.
      const matcher = (r.matcher || []).map((m) => ({ ...m, art: 'match', sortNyckel: `${m.datum || '9999'}T${m.tid || ''}` }))
      const tavlingar = (r.tavlingar || []).map((t) => ({ ...t, art: 'tavling', sortNyckel: `${t.fran || '9999'}T` }))
      pagang = [...matcher, ...tavlingar].sort((a, b) => a.sortNyckel.localeCompare(b.sortNyckel))
      pagangVisa = r.visa
    }
  }
  // "24–26" + "JUL" inom samma månad, annars "30–2" + "JUL–AUG".
  function intervall(fran, till) {
    const [f, t] = [fran || '', till || '']
    const dag = (d) => String(Number(d.split('-')[2]) || '–')
    const mon = (d) => MK[(Number(d.split('-')[1]) || 1) - 1]?.toUpperCase()
    if (!t || t === f) return { dag: dag(f), mon: mon(f) }
    return f.slice(0, 7) === t.slice(0, 7)
      ? { dag: `${dag(f)}–${dag(t)}`, mon: mon(f) }
      : { dag: `${dag(f)}–${dag(t)}`, mon: `${mon(f)}–${mon(t)}` }
  }
  const versal = (s) => (s || '').charAt(0).toUpperCase() + (s || '').slice(1)
  async function togglePagangVisa() { pagangVisa = !pagangVisa; await sattPagangVisa(pagangVisa) }
  async function uppdateraSajten() {
    pagangKor = true; pagangFlash = ''
    const r = await publiceraPagangMatcher($testMode)
    pagangKor = false
    pagangFlash = r?.ok ? ($testMode ? '✓ Testfiler skrivna' : `✓ Uppdaterad · ${r.antal} poster`) : (r?.fel || 'Kunde inte uppdatera')
    setTimeout(() => (pagangFlash = ''), 2600)
  }
</script>

<div class="panel">
  <div class="topp">
    <div class="topptitel">
      <h1 class="scd">På gång</h1>
      <span class="toppsub">Kurerad lista · kommande matcher &amp; tävlingar</span>
    </div>
    <button class="visatoggle" on:click={togglePagangVisa}>
      <span class="chk" class:pa={pagangVisa}>{pagangVisa ? '✓' : ''}</span>Visa på sajten</button>
  </div>

  <div class="kort">
    <div class="korthuvud">
      <span class="caps">Kommande · {pagang.length} st</span>
      {#if pagangFlash}<span class="ok">{pagangFlash}</span>{/if}
      <button class="statusbtn" on:click={uppdateraSajten} disabled={pagangKor}>{pagangKor ? 'Uppdaterar…' : 'Uppdatera sajten'}</button>
    </div>
    <div class="pglista">
      {#each pagang as m (m.art + m.id)}
        {#if m.art === 'tavling'}
          {@const iv = intervall(m.fran, m.till)}
          <div class="pgkort">
            <div class="pgdatum"><span class="pgdag scd">{iv.dag}</span>
              <span class="pgmon">{iv.mon}</span></div>
            <span class="grendot" style="background:{grenFarg(m.gren)}"></span>
            <div class="pgi"><div class="pgf">{m.namn}</div>
              <div class="pgl">Heldag · {versal(m.sport)}{m.ort ? ` · ${m.ort}` : ''}</div></div>
          </div>
        {:else}
          <div class="pgkort">
            <div class="pgdatum"><span class="pgdag scd">{(m.datum || '').split('-')[2] || '–'}</span>
              <span class="pgmon">{MK[(Number((m.datum || '').split('-')[1]) || 1) - 1]?.toUpperCase()}</span></div>
            <span class="grendot" style="background:{grenFarg(m.hem_gren)}"></span>
            <div class="pgi"><div class="pgf">{m.lag_hemma}{m.lag_borta ? ` – ${m.lag_borta}` : ''}</div><div class="pgl">{m.liga || ''}</div></div>
          </div>
        {/if}
      {/each}
      {#if !pagang.length}<div class="tom">Inget kommande — matcher läggs till i Matcher, tävlingsperioder får från/till-datum i Lag &amp; tävlingar.</div>{/if}
    </div>
    <div class="pgfot">
      Kurerad På gång-lista → sport-startsidan på webben. Matcherna följer Matcher; tävlingar med
      från/till-datum (Nordea Open, Friidrotts-SM …) visas som heldagsaktiviteter hela perioden.
      Publiceras som "På gång"-modul på sajten.
    </div>
  </div>
</div>

<style>
  .panel { padding: 26px 30px 40px; max-width: 900px; }
  .topp { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
  .topptitel { display: flex; flex-direction: column; gap: 3px; }
  h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--t-head); }
  .toppsub { font-size: 12.5px; color: var(--t-mut); }
  .visatoggle { display: inline-flex; align-items: center; gap: 8px; background: var(--kort);
    border: 1px solid var(--div); border-radius: 10px; padding: 8px 13px; font-size: 12px; font-weight: 600; color: var(--t-head); cursor: pointer; }
  .chk { width: 16px; height: 16px; border-radius: 5px; border: 1px solid var(--div); display: inline-flex;
    align-items: center; justify-content: center; font-size: 10px; color: var(--ink); }
  .chk.pa { background: var(--acc); border-color: var(--acc); }
  .kort { border: 1px solid var(--div); border-radius: 13px; background: var(--kort); padding: 16px 18px; }
  .korthuvud { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .caps { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--t-caps); }
  .ok { font-size: 11.5px; color: var(--gron, #6E8757); font-weight: 600; }
  .statusbtn { margin-left: auto; border: 1px solid var(--acc-border); background: var(--acc-soft); color: var(--acc);
    border-radius: 8px; padding: 7px 12px; font-size: 12px; font-weight: 600; cursor: pointer; }
  .statusbtn:disabled { opacity: 0.5; cursor: default; }
  .pglista { display: flex; flex-direction: column; gap: 8px; }
  .pgkort { display: flex; align-items: center; gap: 13px; padding: 9px 11px; border: 1px solid var(--div); border-radius: 10px; background: var(--panel); }
  .pgdatum { display: flex; flex-direction: column; align-items: center; min-width: 40px; }
  .pgdag { font-size: 17px; font-weight: 700; color: var(--t-head); font-family: var(--font-c); line-height: 1; }
  .pgmon { font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: var(--t-mut); }
  .grendot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .pgi { min-width: 0; }
  .pgf { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .pgl { font-size: 10.5px; color: var(--t-mut); }
  .tom { font-size: 12px; color: var(--t-mut); padding: 8px 2px; }
  .pgfot { font-size: 10.5px; color: var(--t-help); margin-top: 14px; line-height: 1.5; }
</style>
