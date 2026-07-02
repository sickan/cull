<script>
  import { onMount } from 'svelte'
  import { startaCull, startaGallring, valjMapp, aktivMatch, listaLag } from '../lib/api.js'
  import AktivMatchRad from '../lib/AktivMatchRad.svelte'

  export let aktivMatchData = null

  let aktiv = aktivMatchData
  let lagAlla = []
  let oppet = 'ai'            // ai | snabb | rapport | null
  let adv = false

  let ai = { kalla: '', keep: 40, unit: 'bilder', burst: 2.0, ocr: true, nums: '',
    overwrite: false, kit: 'Hemmaställ', kick: 'auto', model: 'Din smak', pose: 60, sharp: 70 }
  let snabb = { kalla: '', keep: 40, burst: 2.0 }

  let kor = { ai: false, snabb: false, rapport: false }
  let prog = { ai: 0, snabb: 0, rapport: 0 }
  let res = { ai: '', snabb: '', rapport: '' }

  const KIT = ['Hemmaställ', 'Bortaställ', 'Tredjeställ', 'Egen färg']

  onMount(async () => {
    lagAlla = await listaLag()
    if (!aktiv) aktiv = await aktivMatch()
    if (aktiv?.tid && ai.kick === 'auto') ai.kick = aktiv.tid
  })

  $: hemlag = aktiv ? lagAlla.find((l) => l.namn === aktiv.lag_hemma) : null
  $: hemFarg = !hemlag ? '#c9bfa8'
    : ai.kit === 'Bortaställ' ? (hemlag.stall_borta || '#ffffff')
    : ai.kit === 'Tredjeställ' ? (hemlag.stall_tredje || '#333333')
    : (hemlag.stall_hemma || hemlag.profilfarg || '#c9bfa8')
  $: hemNote = aktiv?.lag_hemma ? `Hämtas från ${aktiv.lag_hemma} · ${ai.kit.toLowerCase()}` : 'Ingen aktiv match — välj hemmafärg manuellt'
  $: keepPreview = ai.unit === 'procent' ? `≈ ${ai.keep} % av tagningen` : `≈ ${ai.keep} bilder av tagningen`

  async function valjKalla(which) {
    const r = await valjMapp('Välj källmapp (RAW)')
    if (!r.ok) return
    if (which === 'snabb') { snabb.kalla = r.path; snabb = snabb } else { ai.kalla = r.path; ai = ai }
  }

  async function kora(vilket) {
    const cfg = vilket === 'snabb'
      ? { kalla: snabb.kalla, verktyg: 'snabb', behall: snabb.keep, enhet: 'bilder', burst: snabb.burst }
      : { kalla: ai.kalla, verktyg: vilket === 'rapport' ? 'rapport' : 'ai',
          behall: ai.keep, enhet: ai.unit, burst: ai.burst, trojnummer: ai.ocr,
          nummer: ai.nums, hemmafarg: hemFarg, avspark: ai.kick, modell: ai.model,
          match_id: aktiv?.id || null }
    kor[vilket] = true; prog[vilket] = 25; res[vilket] = ''
    const c = await startaCull(cfg)
    prog[vilket] = 60
    if (c?.urval_id) {
      const g = await startaGallring(c.urval_id)
      res[vilket] = g?.meddelande || (g?.resultat ? `behåller ${g.resultat.behall} av ${g.resultat.totalt}` : 'Klar')
    } else {
      res[vilket] = c?.meddelande || 'Urval skapat'
    }
    prog[vilket] = 100; kor[vilket] = false
  }
  const toggla = (k) => (oppet = oppet === k ? null : k)
</script>

<div class="panel">
  <header>
    <h1 class="scd">Gallra</h1>
    <span class="sub">Verktyg som poängsätter och plockar de bästa bilderna</span>
  </header>
  <AktivMatchRad on:navigera />
  <p class="intro">Varje verktyg konfigureras och körs för sig — resultatet kopieras till ett nytt urval.</p>

  <div class="verktyg">
    <!-- AI-gallring -->
    <div class="kort" class:open={oppet === 'ai'}>
      <button class="khuvud" on:click={() => toggla('ai')}>
        <span class="kic"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/></svg></span>
        <span class="ktxt">
          <span class="ktitel scd">AI-gallring <span class="prim">Primär</span></span>
          <span class="ksub">Poängsätter hela tagningen och behåller dina bästa bilder</span>
        </span>
        <span class="kstatus">{res.ai ? 'Klar' : 'Redo'}</span>
        <span class="kchev" class:upp={oppet === 'ai'}>›</span>
      </button>
      {#if oppet === 'ai'}
        <div class="kkropp">
          <div class="kalla">
            <span class="lbl">Källmapp</span>
            <input bind:value={ai.kalla} placeholder="/Volumes/NIKON Z 8/DCIM/…" />
            <button class="valj" on:click={() => valjKalla('ai')}>Välj…</button>
          </div>
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
                <div class="frad"><button class="box" class:pa={ai.overwrite} on:click={() => (ai.overwrite = !ai.overwrite)}>{ai.overwrite ? '✓' : ''}</button><span class="fx">Skriv över befintligt urval</span></div>
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
              <div class="frad"><span class="fl3">Modell</span><select bind:value={ai.model} class="vaxa"><option>Din smak</option><option>Arkiv (facit)</option><option>Hybrid</option></select></div>
              <div></div>
              <div class="frad"><span class="fl3">Pose</span><input type="range" min="0" max="100" bind:value={ai.pose} /><span class="mono v">{ai.pose}</span></div>
              <div class="frad"><span class="fl3">Skärpa</span><input type="range" min="0" max="100" bind:value={ai.sharp} /><span class="mono v">{ai.sharp}</span></div>
            </div>
          {/if}
          <div class="korrad">
            <div class="progbar"><div class="progfyll" style="width:{prog.ai}%"></div></div>
            {#if res.ai}<span class="ok">✓ {res.ai}</span>{/if}
            <button class="prim-btn" on:click={() => kora('ai')} disabled={kor.ai || !ai.kalla}>{kor.ai ? 'Kör…' : 'Kör AI-gallring'}</button>
          </div>
        </div>
      {/if}
    </div>

    <!-- Snabbgallring -->
    <div class="kort" class:open={oppet === 'snabb'}>
      <button class="khuvud" on:click={() => toggla('snabb')}>
        <span class="kic"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2 4 13.5h5.5L8.5 22 19 9.5h-5.5z"/></svg></span>
        <span class="ktxt">
          <span class="ktitel scd">Snabbgallring</span>
          <span class="ksub">Regelbaserad — ingen AI, klar på sekunder för en deadline</span>
        </span>
        <span class="kstatus">{res.snabb ? 'Klar' : 'Redo'}</span>
        <span class="kchev" class:upp={oppet === 'snabb'}>›</span>
      </button>
      {#if oppet === 'snabb'}
        <div class="kkropp">
          <div class="kalla">
            <span class="lbl">Källmapp</span>
            <input bind:value={snabb.kalla} placeholder="/Volumes/NIKON/DCIM/…" />
            <button class="valj" on:click={() => valjKalla('snabb')}>Välj…</button>
          </div>
          <div class="rad-inline">
            <div class="frad"><span class="fl">Behåll</span><input class="liten" bind:value={snabb.keep} /><span class="enhet">bilder</span></div>
            <div class="frad"><span class="fl">Burst-gräns</span><input class="liten" bind:value={snabb.burst} /><span class="enhet">sek</span></div>
          </div>
          <div class="korrad">
            <div class="progbar"><div class="progfyll" style="width:{prog.snabb}%"></div></div>
            {#if res.snabb}<span class="ok">✓ {res.snabb}</span>{/if}
            <button class="prim-btn" on:click={() => kora('snabb')} disabled={kor.snabb || !snabb.kalla}>{kor.snabb ? 'Kör…' : 'Kör snabbgallring'}</button>
          </div>
        </div>
      {/if}
    </div>

    <!-- Rapportläge -->
    <div class="kort" class:open={oppet === 'rapport'}>
      <button class="khuvud" on:click={() => toggla('rapport')}>
        <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4.5" y="3" width="15" height="18" rx="2.2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg></span>
        <span class="ktxt">
          <span class="ktitel scd">Rapportläge</span>
          <span class="ksub">Torrkörning — poängsätter utan att röra disken</span>
        </span>
        <span class="kstatus">{res.rapport ? 'Klar' : 'Redo'}</span>
        <span class="kchev" class:upp={oppet === 'rapport'}>›</span>
      </button>
      {#if oppet === 'rapport'}
        <div class="kkropp">
          <p class="rapptext">Använder samma inställningar som AI-gallring ovan. Inga filer skrivs — resultatet listas i Loggen. Bra för att förhandsbedöma nytt material eller samla facit-underlag inför träning.</p>
          <div class="korrad">
            <div class="progbar"><div class="progfyll" style="width:{prog.rapport}%"></div></div>
            {#if res.rapport}<span class="ok">✓ {res.rapport}</span>{/if}
            <button class="prim-btn" on:click={() => kora('rapport')} disabled={kor.rapport || !ai.kalla}>{kor.rapport ? 'Kör…' : 'Kör rapport'}</button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 800px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .intro { margin: 7px 0 18px; font-size: 12px; color: var(--t-help); }

  .verktyg { display: flex; flex-direction: column; gap: 12px; }
  .kort { border: 1px solid var(--div); border-radius: var(--r); background: var(--kort); box-shadow: var(--skugga); overflow: hidden; }
  .kort.open { border-color: var(--acc-border); }
  .khuvud { display: flex; align-items: center; gap: 14px; width: 100%; padding: 14px 16px; border: 0; background: transparent; text-align: left; }
  .kic { width: 42px; height: 42px; border-radius: 11px; background: var(--acc-soft); color: var(--acc);
    display: flex; align-items: center; justify-content: center; flex: none; }
  .kic svg { width: 22px; height: 22px; }
  .ktxt { flex: 1; min-width: 0; }
  .ktitel { font-size: 17.5px; font-weight: 700; color: var(--t-head); display: flex; align-items: center; gap: 8px; }
  .prim { font-size: 9.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--acc); background: var(--acc-soft); padding: 2px 6px; border-radius: 5px; }
  .ksub { display: block; font-size: 12.5px; color: var(--t-mut); margin-top: 2px; }
  .kstatus { font-size: 12px; font-weight: 600; color: var(--ok); flex: none; }
  .kchev { width: 18px; text-align: center; color: var(--t-mut); font-size: 17px; transition: transform 0.15s; flex: none; }
  .kchev.upp { transform: rotate(90deg); }

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
</style>
