import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

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

function commit() {
  try {
    return execSync('git rev-parse --short HEAD').toString().trim()
  } catch {
    return '?'
  }
}

// V2-01: versionen bor i src/dpt2/__init__.py — läses här så UI:t aldrig kan
// hårdkoda en avvikande siffra (det var precis vad Rail gjorde: 'v4.0').
function version() {
  try {
    const p = fileURLToPath(new URL('../__init__.py', import.meta.url))
    const m = readFileSync(p, 'utf8').match(/^__version__\s*=\s*["']([^"']+)["']/m)
    return m ? m[1] : '?'
  } catch {
    return '?'
  }
}

// Bygger till relativ dist/ så pywebview kan ladda index.html lokalt (file://).
export default defineConfig({
  plugins: [svelte()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  define: {
    __BUILD_NR__: JSON.stringify(buildNr()),
    __VERSION__: JSON.stringify(version()),
    __COMMIT__: JSON.stringify(commit()),
  },
})
