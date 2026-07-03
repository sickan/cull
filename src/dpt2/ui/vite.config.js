import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { execSync } from 'node:child_process'

// Byggnummer = antal commits på HEAD (git upptäcker repo-roten uppåt själv,
// funkar oavsett var vite körs ifrån inom trädet). '?' om git saknas (t.ex.
// ett exporterat källträd utan .git).
function buildNr() {
  try {
    return execSync('git rev-list --count HEAD').toString().trim()
  } catch {
    return '?'
  }
}

// Bygger till relativ dist/ så pywebview kan ladda index.html lokalt (file://).
export default defineConfig({
  plugins: [svelte()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  define: { __BUILD_NR__: JSON.stringify(buildNr()) },
})
