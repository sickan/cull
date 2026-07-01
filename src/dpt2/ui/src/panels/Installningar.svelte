<script>
  import { onMount } from 'svelte'
  import { kalenderStatus, listaFotojobb } from '../lib/api.js'

  let status = { har_nyckel: false, ansluten: false, bas_url: '' }
  let laddar = true
  let synkar = false
  let flash = ''

  onMount(async () => { status = await kalenderStatus(); laddar = false })

  $: pill = status.har_nyckel && status.ansluten
    ? { txt: 'Ansluten', f: 'var(--ok)' }
    : status.har_nyckel
      ? { txt: 'Nyckel satt · tjänst ej nåbar', f: 'var(--varn)' }
      : { txt: 'Ej ansluten', f: 'var(--t-mut)' }

  async function synkaNu() {
    synkar = true; flash = ''
    await listaFotojobb()                 // hämtar om ur tjänsten
    status = await kalenderStatus()
    synkar = false
    flash = 'Synkad'
    setTimeout(() => (flash = ''), 2400)
  }
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
        <div class="frad"><span class="fk">Tjänst</span><span class="fv mono">{status.bas_url}</span></div>
        <div class="frad"><span class="fk">API-nyckel</span><span class="fv">{status.har_nyckel ? 'satt (server-side)' : 'saknas — sätt CALENDAR_SYNC_API_KEY'}</span></div>
        <div class="frad slut"><span class="fk">Konto</span><span class="fv">stig.johansson@dalecarliaphoto.se</span></div>
      </div>

      {#if status.har_nyckel}
        <div class="knappar">
          <button class="prim" on:click={synkaNu} disabled={synkar}>{synkar ? 'Synkar…' : 'Synka nu'}</button>
          <a class="sek" href={status.bas_url + '/installningar'} target="_blank" rel="noreferrer">Öppna tjänstens inställningar ›</a>
          {#if flash}<span class="ok">✓ {flash}</span>{/if}
        </div>
      {:else}
        <p class="not">Sätt <code>CALENDAR_SYNC_API_KEY</code> i miljön (som ANTHROPIC_API_KEY) och starta om appen. Själva Google-anslutningen (OAuth) sköts i tjänstens egen admin — den är låst till ägarens konto.</p>
        <a class="prim" href={status.bas_url} target="_blank" rel="noreferrer">Öppna tjänsten ›</a>
      {/if}
    </div>

    <div class="kort">
      <div class="krad">
        <span class="titel scd">Realtidsnotiser</span>
        <span class="pill" style="color:var(--ok);background:color-mix(in srgb, var(--ok) 15%, transparent)">
          <span class="led"></span>Sköts av tjänsten
        </span>
      </div>
      <p class="not">Tjänsten håller tvåvägssynken: Google → webhook (push-notis) → tjänst, med ett avstämmande bakgrundsjobb var 30:e minut som skyddsnät. DPT2 läser och skriver bara jobb via tjänstens API.</p>
      <div class="flode">
        <span class="box">Google Calendar</span><span class="pil">→</span>
        <span class="box acc">Webhook</span><span class="pil">→</span>
        <span class="box">DPT</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 26px 40px; max-width: 640px; }
  .kicker { font-size: 11px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--acc); font-weight: 600; }
  h1 { margin: 2px 0 20px; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .tom { color: var(--t-help); font-size: 13px; }

  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r);
    box-shadow: var(--skugga); padding: 20px 22px; margin-bottom: 16px; }
  .krad { display: flex; align-items: center; gap: 11px; margin-bottom: 4px; }
  .titel { font-size: 19px; font-weight: 700; color: var(--t-head); }
  .pill { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
    padding: 3px 10px; border-radius: 999px; }
  .led { width: 7px; height: 7px; border-radius: 50%; background: var(--ok);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent); }

  .fakta { margin-top: 12px; }
  .frad { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--div3); font-size: 13.5px; }
  .frad.slut { border-bottom: 0; }
  .fk { color: var(--t-mut); width: 150px; flex: none; }
  .fv { font-weight: 500; color: var(--t-head); min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }

  .knappar { display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
  .not { margin: 12px 0 14px; font-size: 13px; color: var(--t-mut); line-height: 1.55; }
  .not code { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .prim { display: inline-flex; align-items: center; background: var(--acc); color: #fff; border: 0;
    border-radius: 8px; padding: 10px 16px; font-size: 13px; font-weight: 600; text-decoration: none; }
  .prim:disabled { opacity: 0.5; }
  .sek { display: inline-flex; align-items: center; background: var(--kort); border: 1px solid var(--div);
    border-radius: 8px; padding: 9px 15px; font-size: 13px; font-weight: 600; color: var(--t-head); text-decoration: none; }
  .ok { font-size: 12.5px; color: var(--ok); font-weight: 600; }

  .flode { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 6px; }
  .box { background: var(--panel); border: 1px solid var(--div); border-radius: 8px; padding: 8px 13px;
    font-weight: 600; font-size: 13px; color: var(--t-head); }
  .box.acc { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .pil { color: var(--acc); font-weight: 700; }
</style>
