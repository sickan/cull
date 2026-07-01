"""dpt2 — omskrivningen av Dalecarlia Photo Tools.

Nytt paket vid sidan av det gamla `dpt` (som lever vidare under migreringen).
Lagerindelning (se OMSKRIVNING.md):

    data/       SANNINGEN — SQLite-datalager + entiteter
    motorer/    migrerad kärn-logik (rena bibliotek)
    tjanster/   konsoliderad glue (claude, körning, kommando)
    publicering/ astro-export (.md till sajten)
    ui/         Svelte + pywebview

Fas 0 pågår: datalager (SQLite-schema) + paketskelett.
"""

__version__ = "0.0.0"
