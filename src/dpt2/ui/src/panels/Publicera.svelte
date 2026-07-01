<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import { aktivMatch, genereraBildsvep, skapaStory, valjFil, valjMapp, listaLag } from '../lib/api.js'

  const dispatch = createEventDispatcher()
  const bytMatch = () => dispatch('navigera', 'matcher')

  let flik = 'matchdag'         // matchdag | bildsvep
  let match = null
  let lagAlla = []
  let laddar = true

  // Läs in favoritmärkta
  let favKalla = ''
  let favStatus = ''

  // Story & inlägg
  const MOMENT = ['Avspark', 'Halvtid', 'Resultat', 'Startelva', 'Målgörare', 'Nästa match']
  const KANALER = ['Instagram', 'Facebook', 'TikTok']
  const FORMAT = {
    Instagram: ['Story 9:16', 'Inlägg 4:5', 'Inlägg 1:1'],
    Facebook: ['Inlägg 1:1', 'Inlägg 16:9', 'Story 9:16'],
    TikTok: ['Helskärm 9:16'],
  }
  const FORMATNOT = { Instagram: 'filtreras per Instagrams krav', Facebook: 'inlägg + story', TikTok: 'helskärm 9:16' }
  const TEMAN = ['Hav', 'Sol', 'Rosé']
  let story = { moment: 'Avspark', kanal: 'Instagram', format: 'Story 9:16', tema: 'Hav', foto: '' }
  let storyKor = false
  let storyFlash = false

  // Bildsvepet
  let bsKor = false
  let bs = null
  let kopierad = false
  let mal = { web: true, post: true, story: false }

  onMount(async () => {
    ;[match, lagAlla] = await Promise.all([aktivMatch(), listaLag()])
    laddar = false
  })

  $: if (story.kanal && !FORMAT[story.kanal].includes(story.format)) story.format = FORMAT[story.kanal][0]

  function initialer(namn) { return (namn || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 3).toUpperCase() }
  function _lum(hex) {
    const h = (hex || '').replace('#', ''); if (h.length < 3) return 1
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
    return (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  }
  const brickStil = (f) => `background:${f || '#c9bfa8'};color:${_lum(f || '#c9bfa8') > 0.62 ? 'rgba(35,32,26,.85)' : '#fff'}`
  function fargForLag(namn) { const l = lagAlla.find((x) => x.namn === namn); return l ? (l.stall_hemma || l.profilfarg) : '' }

  async function lasFavoriter() {
    if (!favKalla) { const r = await valjMapp('Välj källmapp'); if (r.ok) favKalla = r.path; else return }
    favStatus = 'Läser favoritmärkta…'
    setTimeout(() => (favStatus = 'Favoriter inlästa (kör i workern).'), 400)
  }
  async function valjFavKalla() { const r = await valjMapp('Välj källmapp'); if (r.ok) favKalla = r.path }

  async function korStory() {
    storyKor = true; storyFlash = false
    const r = await skapaStory({ ...story, match_id: match?.id })
    storyKor = false
    storyFlash = !!r?.ok
    if (r?.ok) setTimeout(() => (storyFlash = false), 2600)
  }

  async function korBildsvep() {
    bsKor = true; bs = null; kopierad = false
    const info = match ? `${match.lag_hemma}–${match.lag_borta}${match.resultat ? ' ' + match.resultat : ''}` : ''
    bs = await genereraBildsvep(info, match?.sport || '', fargForLag(match?.lag_hemma) || '')
    bsKor = false
  }
  async function kopiera() {
    try { await navigator.clipboard.writeText(bs.bildsvep); kopierad = true; setTimeout(() => (kopierad = false), 1800) } catch (_) {}
  }
</script>

<div class="panel">
  <header>
    <h1 class="scd">Publicera</h1>
    <span class="sub">Skapa och publicera material för sociala medier och hemsidan</span>
  </header>

  <div class="tabs">
    <button class:on={flik === 'matchdag'} on:click={() => (flik = 'matchdag')}>Matchdag</button>
    <button class:on={flik === 'bildsvep'} on:click={() => (flik = 'bildsvep')}>Bildsvepet</button>
  </div>

  {#if laddar}
    <p class="tom">Laddar…</p>
  {:else if flik === 'matchdag'}
    <div class="stack">
      <!-- Läs in favoritmärkta -->
      <div class="kort">
        <div class="khuvud">
          <span class="kic"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2 4 13.5h5.5L8.5 22 19 9.5h-5.5z"/></svg></span>
          <div class="ktxt"><span class="kt scd">Läs in favoritmärkta</span><span class="ks">Hämtar bilderna du favoritmärkt i kameran — kör medan kortet sitter i, för en snabb story</span></div>
          <span class="redo">Redo</span>
        </div>
        <div class="frad"><span class="fl">Källmapp</span><input class="mono" bind:value={favKalla} placeholder="/Volumes/NIKON Z 8/DCIM/…" /><button class="valj" on:click={valjFavKalla}>Välj…</button></div>
        <div class="hoger">{#if favStatus}<span class="ok">{favStatus}</span>{/if}<button class="prim" on:click={lasFavoriter}>Läs in favoriter</button></div>
      </div>

      <!-- Story & inlägg -->
      <div class="kort">
        <div class="khuvud">
          <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10 5.5h4"/></svg></span>
          <div class="ktxt"><span class="kt scd">Story &amp; inlägg</span><span class="ks">Färdigt material för Instagram — moment, format och Skagen-tema</span></div>
        </div>

        <div class="caps">Moment</div>
        <div class="rutnat3">{#each MOMENT as m}<button class="seg-b" class:on={story.moment === m} on:click={() => (story.moment = m)}>{m}</button>{/each}</div>

        <div class="caps">Kanal</div>
        <div class="seg">{#each KANALER as k}<button class:on={story.kanal === k} on:click={() => (story.kanal = k)}>{k}</button>{/each}</div>

        <div class="capsrad"><span class="caps">Format</span><span class="note">{FORMATNOT[story.kanal]}</span></div>
        <div class="rutnat3">{#each FORMAT[story.kanal] as f}<button class="seg-b" class:on={story.format === f} on:click={() => (story.format = f)}>{f}</button>{/each}</div>

        <div class="caps">Tema</div>
        <div class="rutnat3">{#each TEMAN as t}<button class="seg-b" class:on={story.tema === t} on:click={() => (story.tema = t)}>{t}</button>{/each}</div>

        <div class="amatch">
          <div class="amh"><span class="caps">Aktiv match</span><button class="lank" on:click={bytMatch}>Byt i Matcher ›</button></div>
          {#if match}
            <div class="amrad">
              <span class="brickor">
                <span class="bricka" style={brickStil(fargForLag(match.lag_hemma))}>{initialer(match.lag_hemma)}</span>
                <span class="bricka away" style={brickStil(fargForLag(match.lag_borta))}>{initialer(match.lag_borta)}</span>
              </span>
              <div class="aminfo"><div class="amfix">{match.lag_hemma} – {match.lag_borta}</div><div class="amsub">{[match.datum, match.arena].filter(Boolean).join(' · ')}</div></div>
            </div>
            <div class="amtav"><span><span class="mut">Tävling</span> &nbsp;{match.liga}</span><span class="ur">✓ ur registret</span></div>
          {:else}
            <div class="amtom"><span>Ingen aktiv match vald — materialet fylls i från matchen du aktiverar.</span><button class="sek" on:click={bytMatch}>Välj match ›</button></div>
          {/if}
        </div>

        <label class="foto">Källfoto<div class="frad"><input bind:value={story.foto} placeholder="/sökväg/bild.jpg" /><button class="valj" on:click={async () => { const r = await valjFil('Välj källfoto'); if (r.ok) story.foto = r.path }}>Välj…</button></div></label>

        <div class="hoger">{#if storyFlash}<span class="ok">✓ Skapad</span>{/if}<button class="prim" on:click={korStory} disabled={storyKor}>{storyKor ? 'Skapar…' : 'Skapa story ›'}</button></div>
      </div>
    </div>
  {:else}
    <div class="stack">
      <!-- Instagram-urval (4:5) -->
      <div class="kort rad-kort">
        <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="3" width="16" height="18" rx="3"/><circle cx="12" cy="12" r="4"/><circle cx="17" cy="7" r="1" fill="currentColor"/></svg></span>
        <div class="ktxt"><span class="kt scd">Instagram-urval (4:5)</span><span class="ks">Plocka 20 IG-bästa ur urvalet, pose-beskuret 4:5, redigerbart i Lightroom</span></div>
        <span class="redo">Redo</span>
      </div>

      <!-- Bildsvepet -->
      <div class="kort">
        <div class="khuvud">
          <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 20l1-4 11-11 3 3-11 11z"/><path d="M14 6l3 3"/></svg></span>
          <div class="ktxt"><span class="kt scd">Bildsvepet</span><span class="ks">Claude skriver hela bildtexten i din stil, med målskyttar och hashtags</span></div>
        </div>
        <div class="caps">Publiceringsmål</div>
        <div class="mal">
          <button class="chk" on:click={() => (mal.web = !mal.web)}><span class="box" class:pa={mal.web}>{mal.web ? '✓' : ''}</span> Hemsidan (bildsvepet)</button>
          <button class="chk" on:click={() => (mal.post = !mal.post)}><span class="box" class:pa={mal.post}>{mal.post ? '✓' : ''}</span> Instagram-inlägg</button>
          <button class="chk" on:click={() => (mal.story = !mal.story)}><span class="box" class:pa={mal.story}>{mal.story ? '✓' : ''}</span> Instagram stories</button>
        </div>
        <div class="hoger"><button class="prim" on:click={korBildsvep} disabled={bsKor}>{bsKor ? 'Skriver…' : 'Skapa bildsvep ›'}</button></div>

        {#if bs?.ok}
          <div class="utdata">
            <textarea readonly rows="12">{bs.bildsvep}</textarea>
            <div class="utfot"><span class="hint">Granska fakta och @-handles (markerade med ?) innan du postar.</span><button class="sek" on:click={kopiera}>{kopierad ? '✓ Kopierat' : 'Kopiera'}</button></div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { padding: 22px 24px 40px; max-width: 720px; }
  header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: 25px; font-weight: 700; color: var(--t-head); }
  .sub { font-size: 13px; color: var(--t-mut); }
  .tom { color: var(--t-help); font-size: 13px; }

  .tabs { display: inline-flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; margin: 14px 0 0; }
  .tabs button { padding: 8px 16px; border: 0; border-radius: 7px; background: transparent; color: var(--t-mut); font-size: 13px; font-weight: 600; }
  .tabs button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }

  .stack { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
  .kort { background: var(--kort); border: 1px solid var(--div); border-radius: var(--r); box-shadow: var(--skugga); padding: 16px; }
  .khuvud { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
  .rad-kort { display: flex; align-items: center; gap: 14px; padding: 14px 16px; }
  .kic { width: 42px; height: 42px; border-radius: 11px; background: var(--acc-soft); color: var(--acc); display: flex; align-items: center; justify-content: center; flex: none; }
  .kic svg { width: 20px; height: 20px; }
  .ktxt { flex: 1; min-width: 0; }
  .kt { font-size: 17px; font-weight: 700; color: var(--t-head); display: block; }
  .ks { display: block; font-size: 12.5px; color: var(--t-mut); margin-top: 2px; }
  .redo { font-size: 12px; font-weight: 600; color: var(--t-mut); flex: none; }

  .caps { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin: 16px 0 10px; }
  .capsrad { display: flex; align-items: baseline; gap: 8px; margin: 16px 0 10px; }
  .capsrad .caps { margin: 0; }
  .note { font-size: 11px; color: var(--t-help); }
  .rutnat3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .seg-b { padding: 8px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-mut); font-size: 12.5px; font-weight: 500; }
  .seg-b.on { background: var(--acc); border-color: var(--acc); color: #fff; font-weight: 600; }
  .seg { display: flex; background: var(--div3); border-radius: 9px; padding: 3px; gap: 3px; }
  .seg button { flex: 1; padding: 7px; border: 0; border-radius: 7px; background: transparent; color: var(--t-mut); font-size: 12.5px; font-weight: 600; }
  .seg button.on { background: var(--kort); color: var(--t-head); box-shadow: 0 1px 2px rgba(0,0,0,.08); }

  .amatch { margin-top: 16px; border: 1px solid var(--div3); border-radius: 10px; padding: 12px 14px; background: var(--panel); }
  .amh { display: flex; align-items: center; justify-content: space-between; }
  .amh .caps { margin: 0; }
  .lank { border: 0; background: none; color: var(--acc); font-size: 11.5px; font-weight: 600; padding: 0; }
  .amrad { display: flex; align-items: center; gap: 11px; margin: 9px 0 8px; }
  .brickor { display: flex; align-items: center; flex: none; }
  .bricka { width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-c); font-size: 11px; font-weight: 700; border: 2px solid var(--kort); }
  .bricka.away { margin-left: -8px; }
  .aminfo { min-width: 0; } .amfix { font-size: 14px; font-weight: 600; color: var(--t-head); } .amsub { font-size: 11.5px; color: var(--t-mut); margin-top: 1px; }
  .amtav { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--t-head); padding: 6px 0 0; border-top: 1px solid var(--div3); }
  .amtav .mut { color: var(--t-mut); } .ur { color: var(--ok); }
  .amtom { display: flex; align-items: center; gap: 10px; margin-top: 9px; font-size: 13px; color: var(--t-mut); }
  .amtom span { flex: 1; }

  .foto { display: flex; flex-direction: column; gap: 5px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--t-caps); margin-top: 14px; }
  .frad { display: flex; align-items: center; gap: 8px; }
  .fl { font-size: 12.5px; color: var(--t-mut); width: 78px; flex: none; }
  input { font-family: inherit; padding: 8px 10px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); font-size: 12.5px; font-weight: 400; text-transform: none; letter-spacing: 0; outline: none; flex: 1; min-width: 0; }
  input:focus { border-color: var(--acc); }
  .mono { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; }
  .valj { flex: none; background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 8px 12px; font-size: 12px; color: var(--t-mut); }

  .mal { display: flex; flex-direction: column; gap: 12px; }
  .chk { display: flex; align-items: center; gap: 11px; border: 0; background: none; padding: 0; font-size: 13.5px; color: var(--t-head); }
  .box { width: 19px; height: 19px; border-radius: 5px; border: 1px solid var(--div); background: var(--panel); color: var(--acc); font-size: 12px; display: inline-flex; align-items: center; justify-content: center; }
  .box.pa { background: var(--acc); color: #fff; border-color: var(--acc); }

  .hoger { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 16px; }
  .ok { font-size: 12px; color: var(--ok); font-weight: 600; }
  .prim { background: var(--acc); color: #fff; border: 0; border-radius: 7px; padding: 9px 18px; font-size: 13px; font-weight: 600; }
  .prim:disabled { opacity: 0.5; }
  .sek { background: var(--kort); border: 1px solid var(--div); border-radius: 7px; padding: 8px 13px; font-size: 12.5px; font-weight: 600; color: var(--t-head); flex: none; }

  .utdata { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
  textarea { font-family: var(--mono, ui-monospace, monospace); font-size: 12px; line-height: 1.5; white-space: pre-wrap; padding: 11px; border: 1px solid var(--div); border-radius: 8px; background: var(--panel); color: var(--t-head); resize: vertical; }
  .utfot { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .hint { font-size: 11.5px; color: var(--t-help); }
</style>
