<script>
  // Utövare-sidan (D11b §2). ETT register (lag kind='individ'). Profil + @-handle
  // är det enda skrivbara; Kommande starter och Historik HÄRLEDS i backend ur
  // tävlingarnas grenar/pass — aldrig lagrade på utövaren.
  import { onMount } from 'svelte'
  import { listaUtovare, hamtaUtovare, sattUtovareHandle } from '../lib/api.js'

  // Låst gren-palett (invariant): färgkant, aldrig textetikett, ingen kant om okänd.
  const KLASSFARG = { dam: '#8E5A86', herr: '#3E7C87', mixed: '#6E8757' }
  const idag = new Date().toISOString().slice(0, 10)

  let lista = []
  let sok = ''
  let vald = null            // utövare-id
  let u = null               // detaljdata { ...profil, historik, starter }
  let handle = ''

  onMount(ladda)
  async function ladda() { lista = await listaUtovare() }

  $: filtrerade = lista.filter((x) =>
    !sok.trim() || (x.namn + ' ' + (x.klubb || '')).toLowerCase().includes(sok.toLowerCase()))

  async function oppna(id) {
    vald = id
    u = await hamtaUtovare(id)
    handle = u?.instagram || ''
  }
  function tillbaka() { vald = null; u = null; ladda() }

  async function sparaHandle() {
    if (!u) return
    await sattUtovareHandle(u.id, handle)
    u = { ...u, instagram: handle }
    // Spegla i listan så den syns direkt vid tillbaka.
    lista = lista.map((x) => (x.id === u.id ? { ...x, instagram: handle } : x))
  }

  const visHandle = (h) => !h ? '' : h.startsWith('@') || h.startsWith('?') ? h : '@' + h
  $: kommande = (u?.starter || []).filter((s) => (s.datum || '') >= idag)
  $: gjorda = (u?.historik || [])
</script>

{#if !vald}
  <div class="topp">
    <div>
      <span class="kicker">Planera</span>
      <h1 class="scd">Utövare <span class="sub">Ett register — historik och starter härleds ur tävlingarna, aldrig dubbellagrade</span></h1>
    </div>
  </div>

  <div class="sokrad">
    <input class="sok" bind:value={sok} placeholder="Sök utövare eller klubb…" />
    <span class="antal">{filtrerade.length} av {lista.length}</span>
  </div>

  {#if !lista.length}
    <p class="tom">Inga utövare än — de skapas när du läser in en startlista på en tävling.</p>
  {:else}
    <div class="lista">
      {#each filtrerade as x (x.id)}
        <button class="rad" on:click={() => oppna(x.id)}>
          <span class="kant" style="background:{KLASSFARG[x.gren] || 'transparent'}"></span>
          <span class="namn scd">{x.namn}</span>
          <span class="klubb">{x.klubb || ''}</span>
          {#if visHandle(x.instagram)}<span class="handle">{visHandle(x.instagram)}</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
{:else if u}
  <button class="tillbaka" on:click={tillbaka}>‹ Alla utövare</button>

  <div class="kort profil">
    <span class="kant stor" style="background:{KLASSFARG[u.gren] || 'transparent'}"></span>
    <div class="pinfo">
      <h1 class="scd">{u.namn}</h1>
      <span class="meta">{[u.klubb, u.sport].filter(Boolean).join(' · ') || '—'}</span>
    </div>
    <label class="handlefalt">@-konto
      <div class="hrad">
        <input bind:value={handle} placeholder="@konto" on:blur={sparaHandle}
          on:keydown={(e) => e.key === 'Enter' && e.currentTarget.blur()} />
      </div>
    </label>
  </div>

  <div class="kort">
    <span class="caps">Kommande starter <span class="khint">härledda ur tävlingarnas program</span></span>
    {#if !kommande.length}
      <p class="tomkort">Inga kommande starter.</p>
    {:else}
      {#each kommande as s}
        <div class="starad">
          <span class="sdat scd">{s.datum}{s.tid ? ' · ' + s.tid : ''}</span>
          <span class="skant" style="background:{KLASSFARG[s.klass] || 'transparent'}"></span>
          <span class="sgren">{s.gren}{s.pass && s.pass !== s.gren ? ' · ' + s.pass : ''}</span>
          {#if s.event_namn}<span class="sdel">Del av {s.event_namn}</span>{/if}
        </div>
      {/each}
    {/if}
  </div>

  <div class="kort">
    <span class="caps">Historik <span class="khint">härledd tidslinje, nyast först</span></span>
    {#if !gjorda.length}
      <p class="tomkort">Ingen historik än.</p>
    {:else}
      {#each gjorda as e}
        <div class="histrad">
          <span class="hdat">{e.fran || ''}</span>
          <span class="hnamn scd">{e.namn}</span>
          <span class="htyp">{e.typ || ''}</span>
        </div>
      {/each}
    {/if}
  </div>
{/if}

<style>
  .topp { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
  .kicker { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--t-help); }
  .scd { font-family: var(--scd, inherit); }
  h1.scd { font-size: 26px; margin: 2px 0 0; color: var(--t-head); }
  .sub { font-size: 12.5px; font-weight: 400; color: var(--t-help); margin-left: 8px; }
  .sokrad { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
  .sok { flex: 1; border: 1px solid var(--div); border-radius: 9px; padding: 8px 12px;
    background: var(--kort); color: var(--t-head); font-family: inherit; font-size: 13px; }
  .antal { font-size: 12px; color: var(--t-help); }
  .tom { color: var(--t-help); padding: 20px 0; }
  .lista { display: flex; flex-direction: column; gap: 4px; }
  .rad { display: flex; align-items: center; gap: 10px; border: 1px solid var(--div);
    border-radius: 9px; background: var(--kort); padding: 9px 12px; cursor: pointer;
    text-align: left; font-family: inherit; }
  .rad:hover { border-color: var(--acc); }
  .kant { flex: 0 0 4px; align-self: stretch; border-radius: 3px; min-height: 20px; }
  .kant.stor { min-height: 44px; }
  .namn { flex: 1; color: var(--t-head); font-size: 14px; }
  .klubb { color: var(--t-help); font-size: 12.5px; }
  .handle { color: var(--acc); font-size: 12px; font-weight: 600; }
  .tillbaka { border: 0; background: none; color: var(--t-help); cursor: pointer;
    font-family: inherit; font-size: 13px; padding: 0 0 10px; }
  .kort { border: 1px solid var(--div); border-radius: 12px; background: var(--kort);
    padding: 14px 16px; margin-bottom: 12px; }
  .profil { display: flex; align-items: center; gap: 14px; }
  .pinfo { flex: 1; }
  .pinfo h1 { font-size: 22px; margin: 0; color: var(--t-head); }
  .meta { font-size: 12.5px; color: var(--t-help); }
  .handlefalt { font-size: 11px; color: var(--t-help); display: flex; flex-direction: column; gap: 4px; }
  .handlefalt input { border: 1px solid var(--div); border-radius: 8px; padding: 6px 10px;
    background: var(--panel); color: var(--t-head); font-family: inherit; font-size: 13px; width: 160px; }
  .caps { display: block; font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
    color: var(--t-head); font-weight: 700; margin-bottom: 8px; }
  .khint { font-weight: 400; text-transform: none; letter-spacing: 0; color: var(--t-help); margin-left: 6px; }
  .tomkort { color: var(--t-help); font-size: 13px; margin: 4px 0; }
  .starad, .histrad { display: flex; align-items: center; gap: 10px; padding: 6px 0;
    border-top: 1px solid var(--div); font-size: 13px; }
  .starad:first-of-type, .histrad:first-of-type { border-top: 0; }
  .sdat { flex: 0 0 128px; color: var(--t-head); }
  .skant { flex: 0 0 4px; align-self: stretch; border-radius: 3px; min-height: 16px; }
  .sgren { flex: 1; color: var(--t-head); }
  .sdel { color: var(--t-help); font-size: 12px; }
  .hdat { flex: 0 0 96px; color: var(--t-help); }
  .hnamn { flex: 1; color: var(--t-head); }
  .htyp { color: var(--t-help); font-size: 12px; text-transform: capitalize; }
</style>
