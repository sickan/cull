"""motorer — migrerade kärn-bibliotek (ren logik, inga andra dpt-beroenden).

Fas 0 steg 3: dessa åtta moduler är kopierade verbatim från `dpt` (utom
`story_overlay` som fått sina asset-/loggsökvägar omdirigerade till dpt2):

    bas            klassiska bildmått (skärpa, exponering, motljus, ögon)
    clip_lager     CLIP zero-shot semantiska features
    vision_lager   Apple Vision (horisont, saliens, estetik)
    matchfas       matchfas-bonus ur tidsstämplar
    vitbalans      vitbalans/färgstick-diagnostik
    xmp_writer     XMP-sidecars för Lightroom
    roster         roster-CSV → nummer→namn
    story_overlay  "Horisont"-grafik (story/inlägg)

Tunga importer (torch/clip i clip_lager; cv2/PIL/Vision i övriga) sker inuti
modulerna — importera bara den motor du behöver.
"""
