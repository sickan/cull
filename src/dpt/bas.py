"""Baspoängsättning: skärpa, exponering, ögon."""

import cv2
import numpy as np


def skarpa(gray):
    """
    Mäter skärpa som max av nio överlappande patches (3×3 rutnät).
    Belönar bilder där motivet är skarpt oavsett var i bilden det befinner sig,
    utan att bokeh-bakgrund sänker poängen.
    """
    h, w = gray.shape
    ph, pw = h // 2, w // 2
    bast = 0.0
    for row in range(3):
        for col in range(3):
            y1 = row * h // 4
            x1 = col * w // 4
            patch = gray[y1:y1 + ph, x1:x1 + pw]
            v = cv2.Laplacian(patch, cv2.CV_64F).var()
            if v > bast:
                bast = v
    return bast


def exponering(gray):
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    klippt_hog = hist[250:].sum() / total
    klippt_lag = hist[:5].sum() / total
    medel = gray.mean() / 255.0
    straff = klippt_hog * 2.0 + klippt_lag * 1.5 + abs(medel - 0.45)
    return max(0.0, 1.0 - straff)


def motljus(gray):
    """
    Motljus-indikator i [0,1]: hög när kanterna (bakgrund/himmel) är klart
    ljusare än bildens mitt (motivet), vilket ger siluett/rim-ljus.
    Neutralt signalvärde — modellen lär sig om det är önskvärt eller inte.
    """
    h, w = gray.shape
    mh, mw = h // 4, w // 4
    mitt = gray[mh:h - mh, mw:w - mw]
    if mitt.size == 0:
        return 0.0
    mask = np.ones_like(gray, dtype=bool)
    mask[mh:h - mh, mw:w - mw] = False
    kant = gray[mask]
    diff = (kant.mean() - mitt.mean()) / 255.0
    # Förstärk även av andelen utbrända kantpixlar (bakgrundsljus).
    utbrant = (kant > 230).mean()
    return float(np.clip(diff * 1.5 + utbrant * 0.5, 0.0, 1.0))


def rorelse_riktning(gray):
    """
    Riktnings-anisotropi i [0,1] via struktur-tensorns koherens.
    Hög = starkt riktad gradient (panorering/svep), låg = isotropisk
    (skarp detalj eller ostrukturerad skakning). Tillsammans med 'skarpa'
    kan modellen skilja medveten panorering från kameraskak.
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    jxx = float(np.mean(gx * gx))
    jyy = float(np.mean(gy * gy))
    jxy = float(np.mean(gx * gy))
    spar = jxx + jyy
    if spar < 1e-6:
        return 0.0
    koherens = ((jxx - jyy) ** 2 + 4.0 * jxy * jxy) ** 0.5 / spar
    return float(np.clip(koherens, 0.0, 1.0))


# Haar-cascadernas sökvägar. CascadeClassifier.detectMultiScale är INTE
# trådsäker — flera trådar som delar samma objekt kraschar med
# "getScaleData"-assertion. Därför hålls en egen instans per tråd.
_ANSIKTE_XML = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_OGA_XML = cv2.data.haarcascades + "haarcascade_eye.xml"

import threading
_tls = threading.local()


def _cascades():
    """Returnerar (ansikte, öga)-cascade för den anropande tråden."""
    par = getattr(_tls, "casc", None)
    if par is None:
        par = (cv2.CascadeClassifier(_ANSIKTE_XML),
               cv2.CascadeClassifier(_OGA_XML))
        _tls.casc = par
    return par


def ogon_ansikten(gray):
    ansikte, oga = _cascades()
    # Skydd om cascade-filerna saknas/inte kunde läsas.
    if ansikte.empty() or oga.empty():
        return 0, 0
    ansikten = ansikte.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
    ogon = sum(
        len(oga.detectMultiScale(gray[y:y+h, x:x+w], 1.1, 6))
        for (x, y, w, h) in ansikten
    )
    return len(ansikten), ogon


def poangsatt(jpg_path):
    img = cv2.imread(str(jpg_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > 1600:
        s = 1600 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    n_ans, n_ogon = ogon_ansikten(gray)
    return {
        "skarpa":   skarpa(gray),
        "exp":      exponering(gray),
        "ansikten": n_ans,
        "ogon":     n_ogon,
        "motljus":  motljus(gray),
        "rorelse":  rorelse_riktning(gray),
    }
