"""Filtyps-mängder (DATA) — EN sanning för vilka suffix som räknas som bild.

Bröts ut ur gamla `dpt.core` vid Fas 3-migreringen så motorerna (nummer,
gallring, leverans) slipper importera CLI-glue:t bara för att veta vad som är
en raw- respektive jpg-fil.
"""

RAW_SUFFIX = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}
JPG_SUFFIX = {".jpg", ".jpeg"}
BILD_SUFFIX = RAW_SUFFIX | JPG_SUFFIX
