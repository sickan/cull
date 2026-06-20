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


# Ladda Haar-cascaderna en gång vid import (inte per anrop).
_ANSIKTE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_OGA = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml")


def ogon_ansikten(gray):
    # Skydd om cascade-filerna saknas/inte kunde läsas.
    if _ANSIKTE.empty() or _OGA.empty():
        return 0, 0
    ansikten = _ANSIKTE.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
    ogon = sum(
        len(_OGA.detectMultiScale(gray[y:y+h, x:x+w], 1.1, 6))
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
    }
