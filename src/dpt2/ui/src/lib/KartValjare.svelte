<script>
  // Kartväljare för en jobb-koordinat: sök namn (Nominatim/OSM, POI-vänligt) +
  // DRAG pinnen exakt rätt. Sparar direkt till molnets `jobbplats` (samma
  // sanning som iOS). Löser att DPT tidigare bara hade ett fritext-platsfält.
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import { geokoda, sattJobbplats } from './api.js'

  export let jobbId
  export let namn = ''
  export let lat = null
  export let lon = null

  const dispatch = createEventDispatcher()
  let el, map, marker
  let letar = false, sparar = false, status = ''

  // Egen pin (divIcon) — undviker Leaflets trasiga bild-sökväg i bundlern.
  const pin = L.divIcon({ className: 'kv-pin', html: '<span></span>',
    iconSize: [22, 22], iconAnchor: [11, 20] })

  function placera(la, lo, spara = true) {
    lat = la; lon = lo
    if (marker) marker.setLatLng([la, lo])
    else {
      marker = L.marker([la, lo], { draggable: true, icon: pin }).addTo(map)
      marker.on('dragend', (e) => { const p = e.target.getLatLng(); placera(p.lat, p.lng) })
    }
    map.setView([la, lo], Math.max(map.getZoom(), 15))
    if (spara) sparaKoord()
  }

  async function sparaKoord() {
    if (lat == null || lon == null || !jobbId) return
    sparar = true
    const r = await sattJobbplats(jobbId, namn, lat, lon).catch(() => ({ ok: false }))
    sparar = false
    status = r?.ok ? 'Sparat ✓' : 'Kunde inte spara till molnet'
    if (r?.ok) dispatch('sparad', { lat, lon })
  }

  async function slaUpp() {
    if (!namn.trim()) return
    letar = true; status = ''
    const r = await geokoda(namn).catch(() => ({ fel: 'uppslag misslyckades' }))
    letar = false
    if (r?.lat != null) { placera(r.lat, r.lon); status = `OSM: ${r.typ || 'träff'}` }
    else status = r?.fel || 'Hittade inget — dra pinnen manuellt'
  }

  onMount(() => {
    map = L.map(el, { center: [lat ?? 62.0, lon ?? 15.0], zoom: lat != null ? 15 : 5 })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      { attribution: '© OpenStreetMap-bidragsgivare', maxZoom: 19 }).addTo(map)
    if (lat != null && lon != null) placera(lat, lon, false)
    map.on('click', (e) => placera(e.latlng.lat, e.latlng.lng))
    setTimeout(() => map && map.invalidateSize(), 120)
  })
  onDestroy(() => { if (map) map.remove() })
</script>

<div class="kv">
  <div class="kvtopp">
    <button class="kvbtn" on:click={slaUpp} disabled={letar || !namn.trim()}>
      {letar ? 'Slår upp…' : '🔍 Slå upp namnet'}</button>
    <span class="kvstat" class:ok={status.includes('✓')}>{sparar ? 'Sparar…' : status}</span>
  </div>
  <div class="kvkarta" bind:this={el}></div>
  <p class="kvhint">Sök namnet, dra sen pinnen (eller klicka på kartan) tills den sitter exakt på platsen. Sparas direkt till molnet — iOS ser samma punkt.</p>
</div>

<style>
  .kv { display: flex; flex-direction: column; gap: 6px; }
  .kvtopp { display: flex; align-items: center; gap: 10px; }
  .kvbtn { border: 1px solid var(--div); background: var(--panel); border-radius: 8px;
    padding: 5px 11px; font: inherit; font-size: 12px; cursor: pointer; color: var(--t-body); }
  .kvbtn:disabled { opacity: 0.5; cursor: default; }
  .kvstat { font-size: 11.5px; color: var(--t-mut); }
  .kvstat.ok { color: var(--ok, #4a8a4a); }
  .kvkarta { height: 220px; border-radius: 10px; overflow: hidden; border: 1px solid var(--div); }
  .kvhint { margin: 0; font-size: 11px; line-height: 1.4; color: var(--t-help); }
  :global(.leaflet-container) { font-family: inherit; background: var(--div3); }
  /* Mässings-pin (spetsen pekar nedåt mot punkten). */
  :global(.kv-pin span) { display: block; width: 16px; height: 16px; margin: 0 auto;
    background: var(--acc); border: 2px solid #fff; border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg); box-shadow: 0 1px 3px rgba(0,0,0,.4); }
</style>
