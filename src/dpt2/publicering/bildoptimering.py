"""Automatisk bildoptimering inför uppladdning till content-sync/R2.

Sweet spot för fotosajter: JPEG-kvalitet 75-85 (under 70 syns artefakter i
mjuka övergångar som himmel/hud, över 85 växer filstorleken utan synlig
vinst), bredd viktigare än kvalitet (~2000-2400px för fullbredd/hero,
~1200-1600px för galleri/kolumn), sRGB (annars urblekta färger i vissa
webbläsare), lätt efterskärpning vid nedskalning (nedskalning äter skärpa).

RAW-filer (NEF/CR2/...) hanteras genom att först extrahera den inbäddade
JPEG-förhandsvisningen — samma väg som dpt v1:s "Visa urval"-miniatyrer
(gui_web._thumb_for/gui._extrahera_preview).
"""

import io
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageCms, ImageFilter

RAW_SUFFIX = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}

_srgb_profil = None


def _hamta_srgb_profil():
    global _srgb_profil
    if _srgb_profil is None:
        _srgb_profil = ImageCms.createProfile("sRGB")
    return _srgb_profil


def _sakerstall_srgb(img):
    """Konverterar till sRGB om bilden har ett annat inbäddat ICC-profil
    (t.ex. Adobe RGB) — annars kan färgerna se urblekta/förskjutna ut i
    webbläsare som inte färghanterar. Ingen inbäddad profil alls (vanligt
    för kamera-JPEG) → antas redan vara sRGB, ingen konvertering."""
    icc = img.info.get("icc_profile")
    if not icc:
        return img
    try:
        kalla = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        return ImageCms.profileToProfile(img, kalla, _hamta_srgb_profil(), outputMode="RGB")
    except Exception:
        return img.convert("RGB")


def _bild_env():
    env = os.environ.copy()
    for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
        if extra not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def _oppna(sokvag):
    """Öppnar en bildfil för PIL — extraherar inbäddad JPEG-förhandsvisning
    om källan är en RAW-fil."""
    if sokvag.suffix.lower() not in RAW_SUFFIX:
        return Image.open(sokvag)
    from dpt import gui
    with tempfile.TemporaryDirectory() as td:
        jpg = Path(td) / (sokvag.stem + ".jpg")
        if not gui._extrahera_preview(sokvag, jpg, _bild_env()):
            raise ValueError(f"Kunde inte extrahera förhandsvisning ur {sokvag.name}")
        img = Image.open(jpg)
        img.load()  # läs in pixeldata innan temp-mappen försvinner
        return img


def optimera(sokvag, *, max_bredd=2200, kvalitet=85):
    """Läser en lokal bildfil (jpg/png/RAW), säkerställer sRGB, skalar ned
    till max_bredd (aldrig upp), skärper lätt vid nedskalning, och kodar om
    som JPEG vid given kvalitet. Returnerar (bytes, filändelse) — filändelsen
    är alltid ".jpg" eftersom utdata alltid är omkodad JPEG, oavsett källformat."""
    img = _oppna(Path(sokvag))
    img = _sakerstall_srgb(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    if img.width > max_bredd:
        ny_hojd = round(img.height * max_bredd / img.width)
        img = img.resize((max_bredd, ny_hojd), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=2))

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=kvalitet, optimize=True, progressive=True)
    return buf.getvalue(), ".jpg"
