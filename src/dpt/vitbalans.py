"""
Vitbalans-/färgstick-diagnostik med fokus på hudtoner.

Tar stickprov på bilderna under en cull-körning och rapporterar om uppdraget
lutar varmt/kallt eller mot grönt/magenta. Två referenser kombineras:

  • Hud — ansikten (Haar) → hudpixlar (YCrCb) → medel-Lab (a*/b*). Hud ligger
    i ett känt område, och ett systematiskt stick syns när det är samma
    riktning över MÅNGA olika personer (individuell variation medelvärdas bort).
  • Vitpunkt — ljusa, omättade pixlar (linjer, vita tröjor) som castfri
    WB-referens: en sann vit yta ska ha R=G=B, avvikelse = färgstick.

Rapporten är en pre-edit-indikation, inte en exakt Kelvin-mätning.
"""

import cv2
import numpy as np

# "Frisk" hud under korrekt vitbalans (sRGB/D65) hamnar grovt i dessa Lab-band.
HUD_A_BAND = (8, 24)    # a*: grön(−) ↔ magenta(+)
HUD_B_BAND = (12, 32)   # b*: blå(−) ↔ gul(+)

# Ansiktsexponering (medel-luminans på hud, 0–255).
EXP_UNDER = 85          # under detta = mörkt (kan dock vara mörk hudton)
EXP_OVER = 200          # över detta = ljust
EXP_KLIPP_ANDEL = 0.05  # >5 % hudpixlar nära vitt (>250) = utbränd hud


def _hud_mask(bgr):
    """Bool-mask för hudfärgade pixlar (YCrCb-intervall)."""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    return (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)


def _hud_per_ansikte(bgr, ansikte_cascade):
    """Lista med hudpixel-arrayer (BGR), en per ansikte med tillräckligt med hud."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if ansikte_cascade.empty():
        return []
    ansikten = ansikte_cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
    bitar = []
    for (x, y, w, h) in ansikten:
        # Centrala 60 % av ansiktet (undvik hår/kant)
        mx, my = int(w * 0.2), int(h * 0.2)
        roi = bgr[y + my:y + h - my, x + mx:x + w - mx]
        if roi.size == 0:
            continue
        m = _hud_mask(roi)
        if m.sum() >= 30:
            bitar.append(roi[m].reshape(-1, 3))
    return bitar


def _luma(bgr_pixlar):
    """Rec.601-luminans (0–255) för Nx3 BGR-pixlar."""
    b = bgr_pixlar[:, 0]; g = bgr_pixlar[:, 1]; r = bgr_pixlar[:, 2]
    return 0.114 * b + 0.587 * g + 0.299 * r


def _vitpunkt(bgr):
    """Medel-BGR för ljusa, omättade pixlar (vit referens), eller None."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = (hsv[:, :, 2] > 200) & (hsv[:, :, 1] < 25)
    if mask.sum() < 50:
        return None
    pix = bgr[mask].reshape(-1, 3).astype(float)
    return pix.mean(axis=0)   # [B, G, R]


def _lab_av_bgr_medel(bgr_medel):
    """a*/b* för en medel-BGR-färg (OpenCV Lab, neutral = 128)."""
    lab = cv2.cvtColor(np.uint8([[bgr_medel]]), cv2.COLOR_BGR2Lab)[0, 0]
    return float(lab[1]) - 128.0, float(lab[2]) - 128.0   # a*, b*


def analysera(imgs_bgr, ansikte_cascade, max_prov=20):
    """
    Kör vitbalans-/hud-stickprov på ett urval av imgs_bgr.
    Returnerar en rapport-dict (eller None om för lite underlag).
    """
    if not imgs_bgr:
        return None
    steg = max(1, len(imgs_bgr) // max_prov)
    prov = imgs_bgr[::steg][:max_prov]

    hud_bitar, vitpunkter, n_ansikts_bilder = [], [], 0
    ansikts_luma = []   # medel-luminans per ansikte
    for img in prov:
        ansikten = _hud_per_ansikte(img, ansikte_cascade)
        if ansikten:
            n_ansikts_bilder += 1
        for hp in ansikten:
            hud_bitar.append(hp)
            ansikts_luma.append(float(_luma(hp.astype(float)).mean()))
        vp = _vitpunkt(img)
        if vp is not None:
            vitpunkter.append(vp)

    rapport = {"n_prov": len(prov), "n_ansikts_bilder": n_ansikts_bilder,
               "hud": None, "vit": None, "exp": None}

    # Hud-Lab + ansiktsexponering
    if hud_bitar:
        alla = np.vstack(hud_bitar).astype(float)
        bgr_medel = alla.mean(axis=0)
        a, b = _lab_av_bgr_medel(bgr_medel)
        rapport["hud"] = {"a": a, "b": b,
                          "a_ok": HUD_A_BAND[0] <= a <= HUD_A_BAND[1],
                          "b_ok": HUD_B_BAND[0] <= b <= HUD_B_BAND[1],
                          "n_pixlar": len(alla)}

        lum = _luma(alla)
        luma_arr = np.array(ansikts_luma)
        n_face = len(luma_arr)
        rapport["exp"] = {
            "medel": float(luma_arr.mean()),
            "n_ansikten": n_face,
            "n_morka": int((luma_arr < EXP_UNDER).sum()),
            "n_ljusa": int((luma_arr > EXP_OVER).sum()),
            "klipp_andel": float((lum > 250).mean()),
        }

    # Vitpunkt
    if vitpunkter:
        b, g, r = np.mean(vitpunkter, axis=0)
        g = g or 1e-6
        temp = r / max(b, 1e-6)          # >1 varmt, <1 kallt
        tint = g / max((r + b) / 2, 1e-6)  # >1 grönt, <1 magenta
        rapport["vit"] = {"r": r, "g": g, "b": b, "temp": temp, "tint": tint,
                          "n": len(vitpunkter)}

    return rapport


def ansikts_exponering_ev(img_bgr, ansikte_cascade, mal=145):
    """
    EV-justering för EN bild så hudens medelluminans närmar sig 'mal'.
    Försiktig (gain 0.6, klamrad ±0.4 EV). Returnerar None om inget ansikte.
    """
    bitar = _hud_per_ansikte(img_bgr, ansikte_cascade)
    if not bitar:
        return None
    alla = np.vstack(bitar).astype(float)
    medel = float(_luma(alla).mean())
    if medel < 1:
        return None
    ev = np.log2(mal / medel) * 0.6
    return float(np.clip(ev, -0.4, 0.4))


def korrigering(rapport):
    """
    Härleder en uppdrags-gemensam WB-korrigering ur vitpunkten.
    Returnerar (delta_k, delta_tint) i Lightroom-enheter — 0/0 om neutralt
    eller om ingen vit referens finns (då rörs WB inte).
    """
    if not rapport or not rapport.get("vit"):
        return 0.0, 0.0
    vit = rapport["vit"]
    temp = vit["temp"]        # r/b: >1 varmt
    tint = vit["tint"]        # g/((r+b)/2): >1 grönt
    # Varmt → kyl ner (lägre Kelvin). Grönt → mot magenta (positiv tint).
    delta_k = 0.0
    if not (0.97 <= temp <= 1.03):
        delta_k = float(np.clip(-(temp - 1.0) * 5000, -800, 800))
    delta_tint = 0.0
    if not (0.98 <= tint <= 1.02):
        delta_tint = float(np.clip((tint - 1.0) * 150, -18, 18))
    return delta_k, delta_tint


def formattera(rapport):
    """Bygger en kort textrapport av analysera()-resultatet."""
    if not rapport:
        return None
    rader = [f"Vitbalans/färgstick (stickprov {rapport['n_prov']} bilder, "
             f"{rapport['n_ansikts_bilder']} med ansikten):"]

    hud = rapport.get("hud")
    if hud:
        a_ord = ("magenta-skift" if hud["a"] > HUD_A_BAND[1]
                 else "grönt skift" if hud["a"] < HUD_A_BAND[0] else "neutral")
        b_ord = ("varmt/gult" if hud["b"] > HUD_B_BAND[1]
                 else "kallt/blått" if hud["b"] < HUD_B_BAND[0] else "neutralt")
        flagga = "" if (hud["a_ok"] and hud["b_ok"]) else "  ⚠"
        rader.append(f"  Hud:      a*={hud['a']:+.0f} ({a_ord})  "
                     f"b*={hud['b']:+.0f} ({b_ord}){flagga}")
    else:
        rader.append("  Hud:      (inga säkra ansikten/hudpixlar i stickprovet)")

    exp = rapport.get("exp")
    if exp:
        n = exp["n_ansikten"]
        klipp = exp["klipp_andel"]
        nivå = ("ljust" if exp["medel"] > EXP_OVER
                else "mörkt" if exp["medel"] < EXP_UNDER else "bra")
        delar = []
        if exp["n_morka"]:
            delar.append(f"{exp['n_morka']}/{n} mörka")
        if exp["n_ljusa"]:
            delar.append(f"{exp['n_ljusa']}/{n} ljusa")
        if klipp > EXP_KLIPP_ANDEL:
            delar.append(f"utbränd hud {klipp:.0%}")
        flagga = "  ⚠" if (klipp > EXP_KLIPP_ANDEL or exp["n_ljusa"]) else ""
        extra = ("  (" + ", ".join(delar) + ")") if delar else ""
        rader.append(f"  Exp (hud): medel {exp['medel']:.0f}/255 ({nivå}){extra}"
                     f"{flagga}")

    vit = rapport.get("vit")
    if vit:
        temp_ord = ("varmt" if vit["temp"] > 1.05
                    else "kallt" if vit["temp"] < 0.95 else "neutralt")
        tint_ord = ("grönt" if vit["tint"] > 1.03
                    else "magenta" if vit["tint"] < 0.97 else "neutral tint")
        rader.append(f"  Vitpunkt: R/G/B {vit['r']:.0f}/{vit['g']:.0f}/{vit['b']:.0f}"
                     f"  → {temp_ord}, {tint_ord}")
    else:
        rader.append("  Vitpunkt: (inga vita referensytor hittade)")

    # Sammanvägd bedömning
    delar = []
    if vit:
        if vit["temp"] > 1.05:
            delar.append("varmt stick")
        elif vit["temp"] < 0.95:
            delar.append("kallt stick")
        if vit["tint"] > 1.03:
            delar.append("grönskiftning")
        elif vit["tint"] < 0.97:
            delar.append("magentaskiftning")
    if hud and not (hud["a_ok"] and hud["b_ok"]):
        delar.append("hudton utanför normalband")
    exp = rapport.get("exp")
    if exp and exp["klipp_andel"] > EXP_KLIPP_ANDEL:
        delar.append("utbränd hud")
    elif exp and exp["n_ljusa"]:
        delar.append("ljusa ansikten")
    bedoming = ("färg + exponering ser bra ut" if not delar
                else "se upp: " + ", ".join(delar))
    rader.append(f"  Bedömning: {bedoming}.")
    return "\n".join(rader)
