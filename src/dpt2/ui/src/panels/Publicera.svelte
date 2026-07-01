<script>
  import { onMount, createEventDispatcher } from 'svelte'
  import { aktivMatch, genereraBildsvep, skapaStory, valjFil, valjMapp, listaLag,
    listaSomeBilder, publiceraTillSoMe } from '../lib/api.js'

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

  // Publicera till SoMe (fan-out IG story/inlägg + FB)
  let someCaption = ''
  let someMapp = ''
  let someBilder = []
  let someMal = { story: true, ig_inlagg: true, fb: false }
  let somePlan = { ok: false, poster: [], varningar: [] }
  let someLage = 'idle'         // idle | dry | progress | done | fel
  let someResultat = []
  let someFel = ''
  let someGen = false

  // Live-plan = synkron lokal beräkning (samma LÅSTA regler som backend). Bryggan
  // (publiceraTillSoMe) används för skarp körning; förhandsvisning behöver inte await.
  const _strippaFb = (t) => (t || '').replace(/[#@][\wåäöÅÄÖ]+/g, '').replace(/[ \t]{2,}/g, ' ')
    .replace(/ *\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
  function planLokalt(bilder, caption, mal) {
    if (!bilder.length) return { ok: false, fel: 'Paketet saknar bilder.', poster: [], varningar: [] }
    if (!(mal.story || mal.ig_inlagg || mal.fb)) return { ok: false, fel: 'Välj minst ett mål (story/inlägg/FB).', poster: [], varningar: [] }
    const poster = [], varningar = []
    if (mal.story) bilder.forEach((b, i) => poster.push({ kanal: 'instagram', form: 'story', bilder: [b], text: caption, del: i + 1, av: bilder.length }))
    if (mal.ig_inlagg) {
      const bitar = []; for (let i = 0; i < bilder.length; i += 10) bitar.push(bilder.slice(i, i + 10))
      if (bitar.length > 1) varningar.push(`${bilder.length} bilder till IG-inlägg → ${bitar.length} poster (Graph API tar max 10/karusell).`)
      bitar.forEach((bit, i) => poster.push({ kanal: 'instagram', form: 'inlägg', bilder: bit, text: caption, del: i + 1, av: bitar.length }))
    }
    if (mal.fb) {
      const fb = bilder.slice(0, 4)
      if (bilder.length > 4) varningar.push(`${bilder.length} bilder till FB → kapat till 4 (FB-sidans multi-photo-gräns).`)
      poster.push({ kanal: 'facebook', form: 'inlägg', bilder: fb, text: _strippaFb(caption), del: 1, av: 1 })
    }
    return { ok: true, poster, varningar }
  }
  $: somePlan = planLokalt(someBilder, someCaption, someMal)
  $: someStoryP = (somePlan.poster || []).filter((p) => p.form === 'story')
  $: someIgP = (somePlan.poster || []).filter((p) => p.kanal === 'instagram' && p.form === 'inlägg')
  $: someFbP = (somePlan.poster || []).find((p) => p.kanal === 'facebook')
  $: someRunCount = (somePlan.poster || []).length
  const postLabel = (p) => `${p.kanal === 'instagram' ? 'Instagram' : 'Facebook'} · ${p.form === 'story' ? 'Story' : 'Inlägg'}${p.av > 1 ? ' ' + p.del + '/' + p.av : ''}`

  async function valjSomeMapp() {
    const r = await valjMapp('Välj mapp med färdiga bilder')
    if (r.ok) { someMapp = r.path; someBilder = await listaSomeBilder(r.path) }
  }
  const fbTokens = (t) => (t || '').split(/(\s+)/).map((s) => ({ s, bort: /^[#@][\wåäöÅÄÖ]+$/.test(s) }))
  async function someGenerera() {
    someGen = true
    const info = match ? `${match.lag_hemma}–${match.lag_borta}${match.resultat ? ' ' + match.resultat : ''}` : ''
    const r = await genereraBildsvep(info, match?.sport || '', fargForLag(match?.lag_hemma) || '')
    someGen = false
    if (r?.ok) someCaption = r.bildsvep
  }
  function someTestkor() { if (somePlan.ok) someLage = 'dry' }
  async function somePublicera() {
    if (!someBilder.length) return
    someLage = 'progress'; someResultat = []; someFel = ''
    const r = await publiceraTillSoMe({ bilder: someBilder, caption: someCaption, mal: someMal,
      match_id: match?.id, moment: story.moment, tema: story.tema })
    if (r?.ok) { someLage = 'done'; someResultat = r.resultat || [] }
    else { someLage = 'fel'; someFel = r?.fel || 'Fel vid publicering.' }
  }
  const someReset = () => { someLage = 'idle'; someResultat = [] }

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
    <button class:on={flik === 'some'} on:click={() => (flik = 'some')}>SoMe</button>
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
  {:else if flik === 'bildsvep'}
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
  {:else if flik === 'some'}
    <div class="stack">
      <div class="kort">
        <div class="khuvud">
          <span class="kic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4M12 2v13"/></svg></span>
          <div class="ktxt"><span class="kt scd">Publicera till SoMe</span><span class="ks">Ett paket — välj bildset och text per kanal, se planen, publicera.</span></div>
        </div>

        {#if match}
          <div class="matchrad">
            <span class="brickor"><span class="bricka" style={brickStil(fargForLag(match.lag_hemma))}>{initialer(match.lag_hemma)}</span><span class="bricka away" style={brickStil(fargForLag(match.lag_borta))}>{initialer(match.lag_borta)}</span></span>
            <div class="mrinfo"><div class="mrfix">{match.lag_hemma} – {match.lag_borta}</div><div class="mrsub">knyter match, moment &amp; tema till paketet</div></div>
            <button class="lank" on:click={bytMatch}>Byt ›</button>
          </div>
        {/if}

        <div class="capsrad"><span class="caps">Bildtext (delas av alla kanaler)</span><button class="genlank" on:click={someGenerera} disabled={someGen}>{someGen ? 'Genererar…' : '✨ Generera'}</button></div>
        <textarea class="somecap" bind:value={someCaption} rows="3" placeholder="Bildsvep-text med #hashtags och @mentions…"></textarea>

        <div class="capsrad2"><span class="caps">Bilder</span><button class="valjbild" on:click={valjSomeMapp}>{someBilder.length ? someBilder.length + ' bilder · byt mapp' : 'Välj bildmapp…'}</button></div>

        <div class="caps mt">Kanaler &amp; bildset</div>
        <div class="kanaler">
          <div class="kanal">
            <button class="krad" on:click={() => (someMal.story = !someMal.story)}>
              <span class="box" class:pa={someMal.story}>{someMal.story ? '✓' : ''}</span>
              <span class="knamn">Instagram Story</span>
              {#if someMal.story && someBilder.length}<span class="antal">{someStoryP.length} stories</span>{/if}
            </button>
            {#if someMal.story && someBilder.length}<div class="strip">{#each someBilder as _b, i}<span class="thumb"><b>{i + 1}</b></span>{/each}</div>{/if}
          </div>

          <div class="kanal">
            <button class="krad" on:click={() => (someMal.ig_inlagg = !someMal.ig_inlagg)}>
              <span class="box" class:pa={someMal.ig_inlagg}>{someMal.ig_inlagg ? '✓' : ''}</span>
              <span class="knamn">Instagram-inlägg</span>
              {#if someMal.ig_inlagg && someBilder.length}<span class="antal">{someIgP.length > 1 ? someIgP.length + ' inlägg' : 'karusell'}</span>{/if}
            </button>
            {#if someMal.ig_inlagg && someBilder.length}
              <div class="strip">{#each someBilder.slice(0, 10) as _b, i}<span class="thumb">{#if i === 0}<em>omslag</em>{/if}</span>{/each}{#if someBilder.length > 10}<span class="thumb plus">+{someBilder.length - 10}</span>{/if}</div>
              {#each somePlan.varningar.filter((v) => v.includes('IG-inlägg')) as v}<div class="varn">⚠ {v}</div>{/each}
            {/if}
          </div>

          <div class="kanal">
            <button class="krad" on:click={() => (someMal.fb = !someMal.fb)}>
              <span class="box" class:pa={someMal.fb}>{someMal.fb ? '✓' : ''}</span>
              <span class="knamn">Facebook-sida</span>
              {#if someMal.fb && someBilder.length}<span class="antal">max 4 bilder</span>{/if}
            </button>
            {#if someMal.fb && someBilder.length}
              <div class="strip">{#each someBilder.slice(0, 6) as _b, i}<span class="thumb" class:dim={i >= 4}></span>{/each}</div>
              {#each somePlan.varningar.filter((v) => v.includes('FB')) as v}<div class="varn">⚠ {v}</div>{/each}
              <div class="fbdiff"><div class="fbdifflbl">Facebook-text (utan #/@)</div><div class="fbtokens">{#each fbTokens(someCaption) as tk}<span class:bort={tk.bort}>{tk.s}</span>{/each}</div></div>
            {/if}
          </div>
        </div>

        {#if someLage === 'dry'}
          <div class="drybanner">Testkörning — <b>inget postades</b>. Planen är vad som skulle skickas.</div>
          <div class="planlista">{#each somePlan.poster as p}<div class="planrad"><span class="pdot"></span><span class="pl">{postLabel(p)}</span><span class="pn">{p.bilder.length} bild</span></div>{/each}</div>
        {:else if someLage === 'progress'}
          <div class="progress"><span class="spin"></span><div><div class="pt">Postar… {someRunCount} poster</div><div class="ps">Avbryt inte — poster som gått igenom rullas inte tillbaka.</div></div></div>
        {:else if someLage === 'done'}
          <div class="donebox"><div class="donehuvud"><span class="okc">✓</span><span>Klart · {someResultat.length} poster publicerade</span><button class="lank rst" on:click={someReset}>Nytt paket</button></div>{#each someResultat as p}<div class="donerad"><span class="okc">✓</span><span class="dl">{postLabel(p)}</span>{#if p.url}<a class="oppna" href={p.url} target="_blank" rel="noreferrer">öppna ›</a>{/if}</div>{/each}</div>
        {:else if someLage === 'fel'}
          <div class="felbox">⚠ {someFel}</div>
        {/if}
        {#if somePlan.fel && someBilder.length === 0 && someLage === 'idle'}<div class="hint mt">{somePlan.fel}</div>{/if}

        <div class="korrad">
          <button class="prim" on:click={somePublicera} disabled={!someBilder.length || someLage === 'progress'}>Publicera skarpt · {someRunCount} poster</button>
          <button class="sek" on:click={someTestkor} disabled={!someBilder.length}>Testkör</button>
          <span class="summa">{someBilder.length ? someRunCount + ' poster' : 'Välj bilder och minst ett mål'}</span>
        </div>
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

  /* Publicera till SoMe */
  .mt { margin-top: 16px; }
  .matchrad { display: flex; align-items: center; gap: 11px; border: 1px solid var(--div3);
    border-radius: 10px; background: var(--panel); padding: 10px 13px; margin-bottom: 16px; }
  .mrinfo { flex: 1; min-width: 0; }
  .mrfix { font-size: 13px; font-weight: 600; color: var(--t-head); }
  .mrsub { font-size: 11px; color: var(--t-mut); }
  .capsrad2 { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0 8px; }
  .capsrad2 .caps { margin: 0; }
  .genlank { border: 0; background: none; color: var(--acc); font-size: 11px; font-weight: 600; }
  .somecap { width: 100%; background: var(--panel); border: 1px solid var(--div); border-radius: 8px;
    padding: 9px 11px; font-size: 12.5px; line-height: 1.55; color: var(--t-head); font-family: inherit; outline: none; resize: vertical; }
  .somecap:focus { border-color: var(--acc); }
  .valjbild { border: 1px solid var(--div); background: var(--kort); border-radius: 8px; padding: 7px 12px;
    font-size: 12.5px; font-weight: 600; color: var(--t-mut); }
  .valjbild:hover { border-color: var(--acc); color: var(--acc); }

  .kanaler { display: flex; flex-direction: column; gap: 10px; }
  .kanal { border: 1px solid var(--div3); border-radius: 11px; background: var(--panel); overflow: hidden; }
  .krad { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px 13px; border: 0; background: transparent; text-align: left; }
  .knamn { flex: 1; font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .antal { font-size: 11px; font-weight: 600; color: var(--acc); background: var(--acc-soft); padding: 3px 9px; border-radius: 999px; }
  .strip { display: flex; gap: 6px; padding: 0 13px 11px; overflow-x: auto; }
  .thumb { width: 44px; height: 55px; border-radius: 5px; flex: none; position: relative;
    border: 1px solid var(--div); display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(135deg, var(--div3), var(--div3) 8px, var(--kort) 8px, var(--kort) 16px); }
  .thumb b { font-family: var(--font-c); font-size: 11px; color: var(--t-mut); }
  .thumb em { position: absolute; top: 2px; left: 3px; font-size: 8px; font-style: normal;
    font-family: var(--mono, monospace); background: var(--kort); border-radius: 3px; padding: 0 3px; color: var(--t-mut); }
  .thumb.plus { background: var(--kort); font-size: 11px; color: var(--t-mut); }
  .thumb.dim { opacity: 0.4; }
  .varn { display: flex; align-items: center; gap: 7px; padding: 9px 13px; border-top: 1px solid var(--div3);
    background: color-mix(in srgb, var(--varn) 9%, transparent); font-size: 11.5px; color: var(--varn); }
  .fbdiff { padding: 11px 13px; border-top: 1px solid var(--div3); }
  .fbdifflbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--t-caps); margin-bottom: 6px; }
  .fbtokens { font-size: 12px; line-height: 1.5; color: var(--t-head); font-family: var(--mono, monospace); }
  .fbtokens .bort { color: var(--rose); text-decoration: line-through; opacity: 0.6; }

  .drybanner { margin-top: 14px; border: 1px solid var(--acc-border); border-radius: 10px; background: var(--acc-soft); padding: 11px 13px; font-size: 12px; color: var(--t-head); }
  .planlista { margin-top: 8px; display: flex; flex-direction: column; gap: 2px; }
  .planrad { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--t-head); padding: 3px 0; }
  .pdot { width: 7px; height: 7px; border-radius: 50%; background: var(--acc); flex: none; }
  .pl { flex: 1; } .pn { color: var(--t-mut); font-size: 11px; }
  .progress { margin-top: 14px; display: flex; align-items: center; gap: 11px; border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 13px; }
  .spin { width: 24px; height: 24px; border-radius: 50%; border: 3px solid var(--acc-soft); border-top-color: var(--acc); flex: none; animation: sospin 0.8s linear infinite; }
  @keyframes sospin { to { transform: rotate(360deg); } }
  .pt { font-size: 13.5px; font-weight: 600; color: var(--t-head); } .ps { font-size: 11.5px; color: var(--t-mut); }
  .donebox { margin-top: 14px; border: 1px solid var(--div3); border-radius: 10px; background: var(--panel); padding: 13px; }
  .donehuvud { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13.5px; font-weight: 600; color: var(--t-head); }
  .okc { color: var(--ok); font-weight: 700; }
  .rst { margin-left: auto; }
  .donerad { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--t-head); padding: 3px 0; }
  .dl { flex: 1; } .oppna { color: var(--acc); text-decoration: none; font-weight: 600; }
  .felbox { margin-top: 14px; border: 1px solid var(--div3); border-radius: 10px; padding: 11px 13px; font-size: 12.5px; color: var(--varn); background: color-mix(in srgb, var(--varn) 8%, transparent); }
  .korrad { display: flex; align-items: center; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--div3); }
  .summa { margin-left: auto; font-size: 11.5px; color: var(--t-help); }
</style>
