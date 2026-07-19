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

# V2-01: ENDA sanningen för appens version. Läses av vite.config.js vid bygget
# (injiceras som __VERSION__ i UI:t) och av app.py:info() vid körning. Gamla
# `dpt`-paketet har en EGEN version i pyproject.toml — de är olika saker och
# ska inte synkas.
#
# Produktnamnet är DPT5 (uttalas "DPT fem punkt noll") — versionen följer
# eventmodell-epiken (V5), inte paketkatalogens namn `dpt2`.
__version__ = "5.0.0"
