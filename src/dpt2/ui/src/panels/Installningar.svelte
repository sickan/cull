<script>
  import { onMount } from 'svelte'
  import { kalenderStatus, listaFotojobb,
    privatStatus, privatKalendrar, privatSattValda, privatSattEtikett, privatLoggaIn, privatLoggaUt, privatSparaKlient } from '../lib/api.js'

  let status = { har_nyckel: false, ansluten: false, bas_url: '' }
  let laddar = true
  let synkar = false
  let flash = ''

  // ── Privata kalendrar ──────────────────────────────────────────────────────
  let pstatus = { har_klient: false, inloggad: false, kalendrar_valda: 0 }
  let pKalendrar = []          // Googles calendarList (för val)
  let pValda = new Set()       // markerade som privata
  let clientId = '', clientSecret = ''
  let pArbetar = ''            // '' | 'sparar' | 'loggar-in' | 'hamtar'
  let pFlash = ''

  onMount(async () => {
    status = await kalenderStatus()
    pstatus = await privatStatus().catch(() => pstatus)
    if (pstatus.inloggad) await hamtaKalendrar()
    laddar = false
  })

  async function hamtaKalendrar() {
    pArbetar = 'hamtar'
    const r = await privatKalendrar().catch(() => null)
    pKalendrar = r?.kalendrar || []
    pValda = new Set(r?.valda || [])
    pArbetar = ''
  }
  async function sparaKlient() {
    if (!clientId || !clientSecret) return
    pArbetar = 'sparar'
    await privatSparaKlient(clientId, clientSecret)
    clientSecret = ''            // håll inte hemligheten kvar i fältet
    pstatus = await privatStatus()
    pArbetar = ''
    pBlink('Uppgifter sparade')
  }
  async function loggaIn() {
    pArbetar = 'loggar-in'
    const r = await privatLoggaIn().catch((e) => ({ ok: false, fel: String(e) }))
    pArbetar = ''
    if (r?.ok) { pstatus = await privatStatus(); await hamtaKalendrar(); pBlink('Inloggad') }
    else pBlink(r?.fel || 'Inloggningen misslyckades', true)
  }
  async function loggaUt() {
    await privatLoggaUt()
    pKalendrar = []; pValda = new Set()
    pstatus = await privatStatus()
    pBlink('Utloggad')
  }
  async function toggleValdKalender(id) {
    pValda = new Set(pValda.has(id) ? [...pValda].filter((x) => x !== id) : [...pValda, id])
    await privatSattValda([...pValda])
    pstatus = { ...pstatus, kalendrar_valda: pValda.size }
  }

  // ── egen etikett per kalender (lagras lokalt — Googles kalender rörs aldrig) ──
  let pRedigerar = null        // kalender-id vars namn redigeras just nu
  let pEtikettUtkast = ''
  const fokus = (el) => { el.focus(); el.select() }

  function oppnaEtikett(e, k) {
    e.stopPropagation()        // pennan får inte toggla radens val
    pRedigerar = k.id
    pEtikettUtkast = k.etikett
  }
  // Sparar på blur/Enter. Esc nollar pRedigerar FÖRE blur — vakten här gör att
  // den avbrutna redigeringen då aldrig sparas. Tomt namn = återställ Googles.
  async function sparaEtikett(k) {
    if (pRedigerar !== k.id) return
    pRedigerar = null
    const ny = pEtikettUtkast.trim()
    if (ny === k.etikett) return
    await privatSattEtikett(k.id, ny)
    await hamtaKalendrar()
    pBlink(ny ? 'Namn sparat' : 'Namn återställt')
  }
  let pFel = false
  function pBlink(msg, fel = false) { pFlash = msg; pFel = fel; setTimeout(() => (pFlash = ''), 2600) }

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

    <!-- Privata kalendrar: skrivskyddad tillgänglighet, läses DIREKT (aldrig via
         Workern). Visas som "Upptaget" i Fotojobb; DPT skriver aldrig hit. -->
    <div class="kort">
      <div class="krad">
        <span class="titel scd">Privata kalendrar</span>
        <span class="pill" style="color:{pstatus.inloggad ? 'var(--ok)' : 'var(--t-mut)'};background:color-mix(in srgb, {pstatus.inloggad ? 'var(--ok)' : 'var(--t-mut)'} 15%, transparent)">
          {pstatus.inloggad ? 'Inloggad' : pstatus.har_klient ? 'Ej inloggad' : 'Ej konfigurerad'}
        </span>
      </div>
      <p class="not top">Läses skrivskyddat från din Mac för krock-koll mot fotojobb — inget lagras, inget skrivs tillbaka. Fruns delade kalender dyker upp här automatiskt.</p>

      {#if !pstatus.har_klient}
        <div class="fakta">
          <p class="not" style="margin-top:0">Skapa en <strong>OAuth-klient av typen Desktop</strong> i Google Cloud Console (API:t Google Calendar, scope <code>calendar.readonly</code>) och klistra in uppgifterna:</p>
          <label class="flt">Client ID<input bind:value={clientId} placeholder="…apps.googleusercontent.com" /></label>
          <label class="flt">Client secret<input type="password" bind:value={clientSecret} placeholder="GOCSPX-…" /></label>
        </div>
        <div class="knappar">
          <button class="prim" on:click={sparaKlient} disabled={!clientId || !clientSecret || pArbetar === 'sparar'}>
            {pArbetar === 'sparar' ? 'Sparar…' : 'Spara uppgifter'}
          </button>
          {#if pFlash}<span class="ok" class:felmed={pFel}>{pFel ? '⚠' : '✓'} {pFlash}</span>{/if}
        </div>
      {:else if !pstatus.inloggad}
        <div class="knappar">
          <button class="prim" on:click={loggaIn} disabled={pArbetar === 'loggar-in'}>
            {pArbetar === 'loggar-in' ? 'Väntar på Google…' : 'Logga in med Google'}
          </button>
          <button class="sek" on:click={() => (pstatus = { ...pstatus, har_klient: false })}>Byt uppgifter</button>
          {#if pFlash}<span class="ok" class:felmed={pFel}>{pFel ? '⚠' : '✓'} {pFlash}</span>{/if}
        </div>
      {:else}
        <div class="kallista">
          {#if pArbetar === 'hamtar'}
            <p class="tom">Hämtar kalendrar…</p>
          {:else}
            {#each pKalendrar as k (k.id)}
              <!-- div, inte button: raden hyser pennan/namnfältet (nästlade
                   interaktiva element är ogiltiga i en <button>). -->
              <div class="kalrad" class:vald={pValda.has(k.id)} role="button" tabindex="0"
                on:click={() => pRedigerar !== k.id && toggleValdKalender(k.id)}
                on:keydown={(e) => e.key === 'Enter' && pRedigerar !== k.id && toggleValdKalender(k.id)}>
                <span class="chk" class:pa={pValda.has(k.id)}>{pValda.has(k.id) ? '✓' : ''}</span>
                <span class="prick" style="background:{k.farg}"></span>
                {#if pRedigerar === k.id}
                  <input class="knamninput" use:fokus bind:value={pEtikettUtkast}
                    on:click|stopPropagation
                    on:keydown={(e) => {
                      if (e.key === 'Enter') { e.stopPropagation(); e.target.blur() }
                      else if (e.key === 'Escape') { e.stopPropagation(); pRedigerar = null }
                    }}
                    on:blur={() => sparaEtikett(k)} />
                {:else}
                  <span class="knamn">{k.etikett}</span>
                  {#if k.primar}<span class="primartag">Din</span>{/if}
                  <button class="penna" title="Byt namn" aria-label="Byt namn på {k.etikett}"
                    on:click={(e) => oppnaEtikett(e, k)}>✎</button>
                {/if}
              </div>
            {/each}
            <p class="not">Markera vilka som ska räknas som privata. Bara markerade används för krock-koll mot fotojobben — de visas aldrig som egna poster, bara som röd krock-markering på jobb de krockar med. Byt namn med pennan (tomt namn återställer Googles) — namnet lagras bara i DPT, kalendern hos Google rörs inte.</p>
          {/if}
        </div>
        <div class="knappar">
          <button class="fara" on:click={loggaUt}>Logga ut</button>
          {#if pFlash}<span class="ok" class:felmed={pFel}>{pFel ? '⚠' : '✓'} {pFlash}</span>{/if}
        </div>
      {/if}
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

  /* Privata kalendrar */
  .flt { display: flex; flex-direction: column; gap: 5px; margin-top: 10px;
    font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--t-caps); }
  .flt input { padding: 9px 11px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel);
    color: var(--t-head); font-size: 13px; font-weight: 400; text-transform: none; letter-spacing: 0; font-family: inherit; }
  .flt input:focus { border-color: var(--acc); outline: none; }
  .not code { font-family: var(--mono, ui-monospace, monospace); font-size: 12px;
    background: var(--panel); padding: 1px 5px; border-radius: 4px; }
  .felmed { color: var(--krock); }
  .kallista { margin: 14px 0 4px; display: flex; flex-direction: column; gap: 6px; }
  .kalrad { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
    background: var(--panel); border: 1px solid var(--div); border-radius: 9px; padding: 9px 12px;
    font-size: 13.5px; color: var(--t-head); cursor: pointer; }
  .kalrad:hover { border-color: var(--acc); }
  .kalrad.vald { border-color: var(--acc); background: var(--acc-soft); }
  .chk { width: 18px; height: 18px; border-radius: 5px; border: 1px solid var(--div); background: var(--kort);
    display: inline-flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; flex: none; }
  .chk.pa { background: var(--acc); border-color: var(--acc); }
  .kalrad .prick { width: 10px; height: 10px; border-radius: 3px; flex: none; }
  .knamn { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* Pennan: tyst tills raden hovras — namnbyte är sekundärt mot valet. */
  .penna { border: 0; background: transparent; color: var(--t-mut); font-size: 13px;
    padding: 2px 6px; border-radius: 6px; cursor: pointer; opacity: 0; flex: none; }
  .kalrad:hover .penna, .penna:focus-visible { opacity: 1; }
  .penna:hover { color: var(--acc); background: var(--div3); }
  .knamninput { flex: 1; min-width: 0; padding: 4px 8px; border: 1px solid var(--acc);
    border-radius: 6px; background: var(--kort); color: var(--t-head); font-size: 13.5px;
    font-family: inherit; outline: none; }
  .primartag { font-size: 10px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--t-mut); background: var(--div3); padding: 2px 7px; border-radius: 999px; flex: none; }

  .flode { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .box { background: var(--panel); border: 1px solid var(--div); border-radius: 8px; padding: 8px 13px; font-weight: 600; font-size: 13px; color: var(--t-head); }
  .box.acc { background: var(--acc-soft); border-color: var(--acc-border); color: var(--acc); }
  .pil { color: var(--acc); font-weight: 700; }
</style>
