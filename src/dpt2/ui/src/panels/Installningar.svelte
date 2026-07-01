<script>
  import { onMount } from 'svelte'
  import { kalenderStatus, listaFotojobb } from '../lib/api.js'

  let status = { har_nyckel: false, ansluten: false, bas_url: '' }
  let laddar = true
  let synkar = false
  let flash = ''

  onMount(async () => { status = await kalenderStatus(); laddar = false })

  $: ansluten = status.har_nyckel && status.ansluten
  $: pill = ansluten ? { txt: 'Ansluten', f: 'var(--ok)' }
    : status.har_nyckel ? { txt: 'Tjänst ej nåbar', f: 'var(--varn)' }
    : { txt: 'Ej ansluten', f: 'var(--t-mut)' }

  async function synkaNu() {
    synkar = true; flash = ''
    await listaFotojobb()
    status = await kalenderStatus()
    synkar = false
    flash = 'Synkad'; setTimeout(() => (flash = ''), 2400)
  }
  const oppnaAdmin = () => { if (status.bas_url) window.open(status.bas_url + '/installningar', '_blank') }
</script>

<div class="panel">
  <span class="kicker">Inställningar</span>
  <h1 class="scd">Anslutning &amp; synk</h1>

  {#if laddar}
    <p class="tom">Laddar status…</p>
  {:else}
    <div class="kort">
      <div class="krad">
        <span class="titel scd">Google Calendar</span>
        <span class="pill" style="color:{pill.f};background:color-mix(in srgb, {pill.f} 15%, transparent)">{pill.txt}</span>
      </div>

      <div class="fakta">
        <div class="frad"><span class="fk">Konto</span><span class="fv">stig.johansson@dalecarliaphoto.se</span></div>
        <div class="frad"><span class="fk">Kalender</span><span class="fv">primary</span></div>
        <div class="frad"><span class="fk">Behörighet</span><span class="fv">Läs &amp; skriv händelser</span></div>
        <div class="frad slut"><span class="fk">API-nyckel</span><span class="fv">{status.har_nyckel ? 'satt (server-side)' : 'saknas — sätt CALENDAR_SYNC_API_KEY'}</span></div>
      </div>

      <div class="knappar">
        <button class="sek" on:click={oppnaAdmin}>Återanslut</button>
        <button class="fara" on:click={oppnaAdmin}>Koppla från</button>
      </div>
      <p class="not">Google-anslutningen (OAuth) sköts i tjänstens egen admin — den är låst till ägarens konto. Knapparna öppnar den.</p>
    </div>

    <div class="kort">
      <div class="krad">
        <span class="titel scd">Realtidsnotiser</span>
        <span class="pill" style="color:var(--ok);background:color-mix(in srgb, var(--ok) 15%, transparent)"><span class="led"></span>Aktiv</span>
      </div>
      <p class="not top">Google meddelar tjänsten direkt när kalendern ändras (webhook), med ett avstämmande bakgrundsjobb var 30:e minut som skyddsnät.</p>
      <div class="flode">
        <span class="box">Google Calendar</span><span class="pil">→</span>
        <span class="box acc">Webhook</span><span class="pil">→</span>
        <span class="box">DPT</span>
      </div>
      <div class="knappar mt">
        <button class="prim" on:click={synkaNu} disabled={synkar}>{synkar ? 'Synkar…' : 'Synka nu'}</button>
        <button class="sek" on:click={oppnaAdmin}>Förnya push-kanal</button>
        {#if flash}<span class="ok">✓ {flash}</span>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 40px; max-width: 640px; }
  .kicker { font-size: 11px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--acc); font-weight: 600; }
  h1 { margin: 2px 0 20px; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .tom { color: var(--t-help); font-size: 13px; }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 20px 22px; margin-bottom: 16px; }
  .krad { display: flex; align-items: center; gap: 11px; margin-bottom: 4px; }
  .titel { font-size: 19px; font-weight: 700; color: var(--t-head); }
  .pill { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 999px; }
  .led { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent); }

  .fakta { margin-top: 12px; }
  .frad { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--div3); font-size: 13.5px; }
  .frad.slut { border-bottom: 0; }
  .fk { color: var(--t-mut); width: 150px; flex: none; }
  .fv { font-weight: 500; color: var(--t-head); min-width: 0; overflow: hidden; text-overflow: ellipsis; }

  .knappar { display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
  .knappar.mt { margin-top: 16px; }
  .sek { background: var(--kort); border: 1px solid var(--div); border-radius: 8px; padding: 9px 15px; font-size: 13px; font-weight: 600; color: var(--t-head); }
  .fara { background: none; border: 1px solid var(--div); border-radius: 8px; padding: 9px 15px; font-size: 13px; font-weight: 600; color: var(--err, #b03838); }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 8px; padding: 9px 16px; font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }
  .not { margin: 12px 0 0; font-size: 12px; color: var(--t-help); line-height: 1.55; }
  .not.top { margin: 6px 0 14px; font-size: 13px; color: var(--t-mut); }

  .flode { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .box { background: var(--panel); border: 1px solid var(--div); border-radius: 8px; padding: 8px 13px; font-weight: 600; font-size: 13px; color: var(--t-head); }
  .box.acc { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .pil { color: var(--acc); font-weight: 700; }
</style>
