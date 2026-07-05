// Testläge — global switch i topbaren (App.svelte). PÅ: Live-story/SoMe/
// Webb-flödena kör sina riktiga pipelines men skriver resultatet som
// exempelfiler i en testkatalog i stället för att posta/spara på riktigt
// (se dpt2/tjanster/testlage.py för sökvägslogiken). ALDRIG persisterad —
// precis som temat (App.svelte) startar den om från AV vid varje appstart.
import { writable } from 'svelte/store'

export const testMode = writable(false)

// Material skapat i testläge hålls HÄR (modul-state) i stället för i
// publicera_material-tabellen — så det överlever både panel-remount
// (navigera bort/tillbaka i Rail:en förstör/återskapar Publicera.svelte)
// och att switchen stängs av mitt i sessionen. Försvinner bara vid
// appomstart (sidan laddas om, modulen återinitieras).
export const testMaterial = writable([])

let _seq = 0
export function nyttTestMaterial(data) {
  const rad = { ...data, id: `test${++_seq}`, test: true,
    uppdaterad: new Date().toISOString(), history: [] }
  testMaterial.update((xs) => [rad, ...xs])
  return rad
}
export function uppdateraTestMaterial(id, data) {
  testMaterial.update((xs) => xs.map((m) =>
    m.id === id ? { ...m, ...data, uppdaterad: new Date().toISOString() } : m))
}
export function raderaTestMaterial(id) {
  testMaterial.update((xs) => xs.filter((m) => m.id !== id))
}
