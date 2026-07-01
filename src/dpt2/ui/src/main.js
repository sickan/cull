import './lib/tokens.css'
import App from './App.svelte'
import { vantaPaBrygga } from './lib/api.js'

// Montera först när pywebview-bryggan är klar (eller timeout i webbläsaren) så
// panelernas onMount-anrop går mot Python-datalagret, inte mockdata.
vantaPaBrygga().then(() => {
  new App({ target: document.getElementById('app') })
})
