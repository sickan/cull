<script>
  // Galleripublicering som GUI (skiva 1): peka ut katalog → metadata →
  // publicera med progressbar. DPT2 är BARA gränssnitt + orkestrering —
  // publicera-galleri.mjs äger affärsreglerna (vattenstämpel på/av, kameranamn,
  // 0-byte-koll, orörda original). Se handover-dpt-galleri-gui-2026-07-23.
  import { valjMapp, galleriForhandsgranska,
    publiceraGalleriBakgrund, galleriStatus } from '../lib/api.js'

  const KATEGORIER = [
    { id: 'sport', namn: 'Sport' },
    { id: 'landskap', namn: 'Landskap' },
    { id: 'manniskor', namn: 'Människor' },
    { id: 'film', namn: 'Film' },
  ]

  let mapp = ''
  let forhands = null            // {antal, tomma, exempel, tom_exempel} eller {fel}
  let granskar = false

  let slug = ''
  let slugRord = false           // användaren har redigerat slug manuellt
  let titel = ''
  let kategori = 'sport'
  let datum = ''
  let plats = ''
  let ingress = ''
  let matchId = ''
  let last = false               // låst kundleverans → INGEN vattenstämpel
  let hogupplost = false         // laddar även upp orörda originalen (bröllop)

  let kor = false
  let prog = null                // {fas, klara, totalt} under körning
  let resultat = null            // {ok, url, antal} eller {ok:false, fel}
  let fel = ''

  // slug härleds ur titeln tills användaren rört fältet själv (kronologiskt
  // stabil, URL-säker). Speglar AX.slugga: gemener, diakriter bort, - som skiljetecken.
  function slugga(s) {
    return (s || '').toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[åäæ]/g, 'a').replace(/[öø]/g, 'o').replace(/é/g, 'e')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  }
  $: if (!slugRord) slug = slugga(titel)

  // Vattenstämpel styrs av LÅST kontra ÖPPET, inte kategorin (affärsregel).
  $: vattenstampel = !last

  $: kanPublicera = mapp && slug && titel && forhands?.antal > 0 &&
    !(forhands?.tomma > 0) && !kor

  async function valjKatalog() {
    const r = await valjMapp('Välj galleri-mapp')
    if (r?.ok && r.path) {
      mapp = r.path
      await granska()
    }
  }

  async function granska() {
    if (!mapp) { forhands = null; return }
    granskar = true
    forhands = await galleriForhandsgranska(mapp).catch(() => ({ fel: 'Kunde inte läsa mappen.' }))
    granskar = false
  }

  async function publicera(torrkor = false) {
    fel = ''; resultat = null; prog = null
    const config = { mapp, slug, titel, kategori,
      datum: datum || null, plats: plats || null, ingress: ingress || null,
      match_id: matchId || null, hogupplost, last, torrkor }
    const start = await publiceraGalleriBakgrund(config)
    if (!start?.ok) { fel = start?.fel || 'Kunde inte starta publiceringen.'; return }
    kor = true
    const poll = setInterval(async () => {
      const st = await galleriStatus().catch(() => null)
      if (!st) return
      prog = { fas: st.fas, klara: st.klara, totalt: st.totalt, url: st.url }
      if (!st.pagar) {
        clearInterval(poll)
        kor = false; prog = null
        const r = st.resultat || {}
        if (r.ok) resultat = { ...r, torrkor }
        else fel = r.fel || 'Publiceringen misslyckades.'
      }
    }, 500)
  }
</script>

<div class="panel">
  <header>
    <h1>Galleri</h1>
    <span class="sub">Publicera ett bildgalleri till bilder.dalecarliaphoto.se</span>
  </header>

  <!-- 1. Källmapp + förhandsgranskning -->
  <div class="kort">
    <div class="caps">Källmapp</div>
    <div class="frad">
      <button class="valj" on:click={valjKatalog}>Välj mapp…</button>
      <input class="mono" bind:value={mapp} on:change={granska} placeholder="/Users/…/Galleri" />
    </div>
    {#if granskar}
      <div class="fh">Läser mappen…</div>
    {:else if forhands?.fel}
      <div class="fh varn">⚠ {forhands.fel}</div>
    {:else if forhands}
      {#if forhands.tomma > 0}
        <div class="fh varn">⚠ {forhands.tomma} av {forhands.antal} filer är 0 byte — mappen
          ligger sannolikt "endast online" i Dropbox. Gör den tillgänglig offline och läs om.
          {#if forhands.tom_exempel?.length}<span class="ex">({forhands.tom_exempel.join(', ')}…)</span>{/if}
        </div>
      {:else if forhands.antal > 0}
        <div class="fh ok">✓ {forhands.antal} bilder redo
          {#if forhands.exempel?.length}<span class="ex">— {forhands.exempel.join(', ')}…</span>{/if}
        </div>
      {:else}
        <div class="fh varn">Inga JPEG-filer i mappen.</div>
      {/if}
    {/if}
  </div>

  <!-- 2. Metadata -->
  <div class="kort">
    <div class="caps">Metadata</div>
    <div class="frad"><span class="fl">Titel</span>
      <input bind:value={titel} placeholder="Malmö FF – Brøndby IF" /></div>
    <div class="frad"><span class="fl">Slug</span>
      <input class="mono" bind:value={slug} on:input={() => slugRord = true}
        placeholder="malmo-brondby-20260718" />
    </div>
    <div class="frad"><span class="fl">Kategori</span>
      <select bind:value={kategori}>
        {#each KATEGORIER as k}<option value={k.id}>{k.namn}</option>{/each}
      </select>
      <span class="ev">styr bara temat</span>
    </div>
    <div class="frad"><span class="fl">Datum</span>
      <input type="date" bind:value={datum} /></div>
    <div class="frad"><span class="fl">Plats</span>
      <input bind:value={plats} placeholder="Eleda Stadion" /></div>
    <div class="frad"><span class="fl">Ingress</span>
      <input bind:value={ingress} placeholder="(valfritt)" /></div>
    <div class="frad"><span class="fl">Match-id</span>
      <input class="mono" bind:value={matchId} placeholder="(valfritt, kopplar galleriet till en match)" /></div>
    <div class="slughint">bilder.dalecarliaphoto.se/galleri/<b>{slug || '…'}</b></div>
  </div>

  <!-- 3. Alternativ + vattenstämpel-indikator (affärskritisk) -->
  <div class="kort">
    <div class="caps">Alternativ</div>
    <button class="chk" on:click={() => last = !last}>
      <span class="box" class:pa={last}>{last ? '✓' : ''}</span>
      Låst kundleverans <span class="ev">(rena bilder, ingen vattenstämpel)</span>
    </button>
    <button class="chk" on:click={() => hogupplost = !hogupplost}>
      <span class="box" class:pa={hogupplost}>{hogupplost ? '✓' : ''}</span>
      Ladda även upp originalen i full upplösning <span class="ev">(bröllop — tungt)</span>
    </button>

    <div class="stampel" class:pa={vattenstampel} class:av={!vattenstampel}>
      {#if vattenstampel}
        <b>Vattenstämpel: JA</b> — vitt ordmärke, nedre mitten. Öppet galleri sprids fritt.
      {:else}
        <b>Vattenstämpel: NEJ</b> — låst kundleverans, rena bilder. Kontrollera att detta
        verkligen är en betald leverans (ett stämpel-fritt öppet galleri är en kundmiss).
      {/if}
    </div>
    {#if last}
      <div class="fh varn liten">Obs: lösenordsgrinden är inte byggd än — galleriet är
        fortfarande nåbart för den som har länken.</div>
    {/if}
  </div>

  <!-- 4. Publicera + progress -->
  <div class="korrad">
    {#if fel}<span class="felm">⚠ {fel}</span>{/if}
    {#if resultat?.ok}
      <span class="ok">✓ {resultat.torrkor ? 'Torrkörning klar' : `Publicerat — ${resultat.antal ?? ''} bilder`}
        {#if resultat.url && !resultat.torrkor}<a href={resultat.url} target="_blank" rel="noreferrer">Öppna →</a>{/if}
      </span>
    {/if}
    {#if kor && prog}
      <div class="prog">
        <div class="bar"><div class="fyll" style="width:{prog.totalt ? Math.round(prog.klara / prog.totalt * 100) : 6}%"></div></div>
        <span class="ptxt">{prog.fas}{prog.totalt ? ` ${prog.klara}/${prog.totalt}` : '…'}</span>
      </div>
    {/if}
    <button class="sek" on:click={() => publicera(true)} disabled={!kanPublicera}>Torrkör</button>
    <button class="prim" on:click={() => publicera(false)} disabled={!kanPublicera}>
      {kor ? 'Publicerar…' : 'Publicera galleri ›'}</button>
  </div>
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 720px; }
  header { display: flex; align-items: baseline; gap: 10px; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { margin: 7px 0 16px; font-size: 13px; color: var(--t-mut); }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 16px; margin-bottom: 14px; }
  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--t-caps); margin-bottom: 14px; }
  .frad { display: flex; align-items: center; gap: 8px; margin-bottom: 11px; }
  .frad:last-child { margin-bottom: 0; }
  .fl { font-size: 12.5px; color: var(--t-mut); width: 66px; flex: none; }
  input, select { font-family: inherit; padding: 7px 9px; border: 1px solid var(--div); border-radius: 8px;
    background: var(--panel); color: var(--t-head); font-size: 12.5px; outline: none; flex: 1; min-width: 0; }
  input:focus, select:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .valj { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px;
    padding: 7px 11px; font-size: 12px; color: var(--t-mut); }
  .ev { font-size: 11px; color: var(--t-mut); flex: none; }
  .slughint { font-size: 11.5px; color: var(--t-help); margin-top: 4px; }
  .slughint b { color: var(--acc); }

  .fh { font-size: 12px; margin-top: 4px; }
  .fh.ok { color: var(--ok); }
  .fh.varn { color: var(--acc); }
  .fh.liten { margin-top: 8px; font-size: 11.5px; }
  .ex { color: var(--t-help); }

  .chk { display: flex; align-items: center; gap: 10px; border: 0; background: none; padding: 0;
    font-size: 13px; color: var(--t-head); margin-bottom: 11px; }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel);
    color: var(--acc); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }

  .stampel { margin-top: 6px; padding: 11px 13px; border-radius: 9px; font-size: 12.5px;
    color: var(--t-head); border: 1px solid var(--div); background: var(--div3); }
  .stampel.av { border-color: #C9871F; background: color-mix(in srgb, #C9871F 12%, transparent); }
  .stampel b { color: var(--t-head); }

  .korrad { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 4px; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .ok a { color: var(--acc); margin-left: 8px; }
  .felm { font-size: 12.5px; color: #C0483A; font-weight: 600; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 10px 18px;
    font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; }
  .sek { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 8px;
    padding: 9px 14px; font-size: 13px; color: var(--t-head); }
  .sek:disabled { opacity: 0.5; }
  .prog { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 160px; }
  .bar { flex: 1; height: 6px; border-radius: 4px; background: var(--div3); overflow: hidden; }
  .fyll { height: 100%; background: var(--acc); border-radius: 4px; transition: width 0.3s; }
  .ptxt { font-size: 11px; color: var(--t-mut); white-space: nowrap; font-variant-numeric: tabular-nums; }
</style>
