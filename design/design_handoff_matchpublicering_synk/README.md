# design_handoff_matchpublicering_synk

Code→Design-synk (2026-07-08) efter att din `handoff-matchpublicering` byggts skarpt i DPT2.

- **`HANDOFF.md`** — statusrapport + de avvikelser mot prototypen som ska uppdateras i Claude Design.
- **`kallkod/`** — snapshot av de faktiska källfilerna (gren `dpt2-fas0`):
  - `ui/src/panels/Publicera.svelte` — hela den nya Matchpublicering-panelen (Steg 1/Steg 2, fan-out,
    På gång, Live nu- + Hämta bilder-slide-overs).
  - `ui/src/panels/Innehall.svelte` — omskriven, nu bara Blog/Landskap/Event.
  - `ui/src/App.svelte` — mörk-först + reaktivt `data-theme`.
  - `ui/src/lib/` — `ResultatRemsa`, `Lagbricka`, `loggacache.js` (data-URI-loggor), `Rail`, `api.js`.
  - `motorer/story_overlay.py` — fokus/zoom cover-crop + nya format (1x1/1.91x1/2x1/16x9).
  - `app.py` — backend: kanal-fan-out, minneskort-ingest, På gång match-synk.

Se `HANDOFF.md` för avvikelserna (mörk-först/full bredd · crop i Steg 1 · På gång = match-synk ·
Live nu eget rutnät · Hämta bilder).
