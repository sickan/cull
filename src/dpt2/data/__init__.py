"""Datalagret — SQLite-store som äger sanningen (matcher, lag, tävlingar,
urval, modeller, SoMe-material, facit). Exporterar .md till Astro vid publicering.

Beslut (OMSKRIVNING.md §8): SQLite från start. Relationell/metadata-sanning i
tabeller; tunga binärer (feature-vektorer, modell-pickles) som filer refererade
från DB.
"""

from dpt2.data.db import DB_DEFAULT, SCHEMA_VERSION, oppna, init_db

__all__ = ["DB_DEFAULT", "SCHEMA_VERSION", "oppna", "init_db"]
