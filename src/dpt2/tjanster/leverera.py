"""Leverera-tjänst — icke-destruktiva Lightroom-vägen: skriver XMP-sidecars för
ett urval (husstil-preset, exponering, upprätning, brus, betyg/etikett).

Speglar husstil/upprätnings-blocket i gamla `dpt.core.kor_efterbehandling`, men
med de TUNGA detektorerna injicerade i stället för inbyggda: Apple Vision-
horisont, gyro-roll och ISO laddas/körs i workern (beslut 4: hybrid — tunga jobb
i separat process). Tjänsten själv är ren (filurval + `xmp_writer.skriv_xmp`) och
fullt enhetstestbar utan torch/Vision.

`hough_vinkel` är en körbar default-rätning (OpenCV Hough på bilden, inget
torch) som workern — eller en lätt körning — kan koppla in som `vinkel_for`.
"""

import os
from pathlib import Path

from dpt2.motorer import xmp_writer
from dpt2.motorer.filtyper import BILD_SUFFIX, RAW_SUFFIX

# Mappnamn som aldrig scannas som källa (appens/v1:s egna utdata) — samma
# lista som dpt.core._HOPPA_MAPP så mappar som gått genom v1 funkar.
_HOPPA_MAPP = {"story", "snabbplock", "urval", "instagram"}


def lista_bilder(katalog):
    """Bildfiler (raw + jpg) under en mapp, rekursivt — så ett minneskorts rot
    (bilderna ligger i DCIM/171D5_01/…) fungerar som källa, inte bara den
    innersta mappen. Hoppar dolda mappar/filer (._AppleDouble på exFAT) och
    kända utdatamappar. Speglar dpt.core.lista_bildfiler."""
    def _ok(p):
        return p.suffix.lower() in BILD_SUFFIX and not p.name.startswith(".")

    traffar = []
    for d, dirs, files in os.walk(katalog):
        dirs[:] = [x for x in dirs
                   if not x.startswith(".")
                   and x.lower() not in _HOPPA_MAPP
                   and not x.lower().startswith("_leverans")]
        dp = Path(d)
        traffar += [dp / f for f in files if _ok(dp / f)]
    return sorted(traffar)


def hough_vinkel(jpg_path):
    """Upprätningsvinkel (grader) ur en bild via Hough-horisont — körbar default
    för `vinkel_for`. Returnerar 0.0 om bilden inte kan läsas eller ingen
    horisont hittas. Kräver cv2 (men inte torch/Vision)."""
    import cv2
    img = cv2.imread(str(jpg_path))
    if img is None:
        return 0.0
    return xmp_writer.berakna_uppratning(img)


def skriv_sidecars(filer, *, husstil_path=None, exp_bump=0.0, xmp_brus=False,
                   objektiv_pa_raw=True, vinkel_for=None, iso_for=None,
                   logg=print):
    """Skriver en XMP-sidecar per fil i `filer`.

    husstil_path:   sökväg till husstil-preset (.xmp) som bakas in, eller None.
    exp_bump:       generell EV-knuff (crs:Exposure2012).
    xmp_brus:       True → ISO-baserad brusreducering (kräver iso_for).
    objektiv_pa_raw:True → objektivprofil-korrigering på raw när husstil finns.
    vinkel_for:     callable fil→grader|None (Vision/gyro/Hough; None = ingen).
    iso_for:        callable fil→int|None (EXIF-ISO; None = ingen).

    Returnerar {'skrivna': n, 'ratade': m, 'sidecars': [Path, ...]}.
    Raw får crs:CameraProfile='Camera Neutral' när inget preset väljs (annars
    styr presetet profilen). Spegling av core.kor_efterbehandling."""
    preset = xmp_writer.las_preset(husstil_path) if husstil_path else None
    vinkel_for = vinkel_for or (lambda f: None)
    iso_for = iso_for or (lambda f: None)
    skrivna = ratade = 0
    sidecars = []
    for f in filer:
        är_raw = f.suffix.lower() in RAW_SUFFIX
        vinkel = vinkel_for(f) or 0.0
        sc = xmp_writer.skriv_xmp(
            f, vinkel=vinkel,
            profil=("Camera Neutral" if är_raw and not preset else None),
            iso=(iso_for(f) if är_raw and xmp_brus else None),
            objektiv=(är_raw and objektiv_pa_raw and bool(husstil_path)),
            preset=preset, exp_bump=exp_bump)
        sidecars.append(sc)
        skrivna += 1
        if abs(vinkel) > 0.005:
            ratade += 1
    etikett = (Path(husstil_path).stem if husstil_path else f"{exp_bump:+.2f} EV")
    logg(f"  Sidecars: {skrivna} skrivna ({etikett})"
         + (f", {ratade} rätade." if ratade else "."))
    return {"skrivna": skrivna, "ratade": ratade, "sidecars": sidecars}
