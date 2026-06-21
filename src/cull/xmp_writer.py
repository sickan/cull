"""Generera XMP-sidecars med beskärning och upprätnning."""

import cv2
import numpy as np
from pathlib import Path

XMP_MALL = """\
<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='cull'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:crs='http://ns.adobe.com/camera-raw-settings/1.0/'
      crs:HasCrop='{has_crop}'
      crs:CropTop='{top:.6f}'
      crs:CropLeft='{left:.6f}'
      crs:CropBottom='{bottom:.6f}'
      crs:CropRight='{right:.6f}'
      crs:CropAngle='0'
      crs:CropConstrainToWarp='0'
      crs:StraightenAngle='{vinkel:.2f}'{extra}
    />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""

# Aspektkvoter i prioritetsordning: original detekteras från bilden
_KVOTER = [
    ("original", None),   # fylls i dynamiskt
    ("4:5",      4 / 5),
    ("16:9",     16 / 9),
]

# Rule-of-thirds korsningar (normaliserade 0..1)
_ROT = [(1/3, 1/3), (2/3, 1/3), (1/3, 2/3), (2/3, 2/3)]


def berakna_uppratning(img_bgr):
    """
    Detekterar horisontella linjer (planets kant/mittlinje) med Hough-transform
    och returnerar korrektionsvinkeln i grader.
    """
    h, w = img_bgr.shape[:2]
    roi = img_bgr[h // 2:, :]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                             threshold=80, minLineLength=w // 5, maxLineGap=20)
    if lines is None:
        return 0.0
    vinklar = []
    for x1, y1, x2, y2 in lines[:, 0]:
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 10:
            continue
        v = np.degrees(np.arctan2(dy, dx))
        if abs(v) < 15:
            vinklar.append(v)
    if not vinklar:
        return 0.0
    return float(np.clip(-float(np.median(vinklar)), -5.0, 5.0))


def _subject_box(yolo_results):
    """
    Returnerar (cx, cy, w_subj, h_subj) normaliserat för spelare+boll,
    eller None om inga detektioner.
    Bollen (klass 32) ges dubbel vikt om den syns.
    """
    if yolo_results is None or not yolo_results.boxes:
        return None

    boxes  = yolo_results.boxes.xyxyn.cpu().numpy()
    klasser = yolo_results.boxes.cls.cpu().numpy().astype(int)

    # Filtrera: spelare (0) och boll (32)
    mask = np.isin(klasser, [0, 32])
    if not mask.any():
        return None
    boxes   = boxes[mask]
    klasser = klasser[mask]

    # Viktat centrum — bollen tyngre
    vikter = np.where(klasser == 32, 2.0, 1.0)
    cx_vals = (boxes[:, 0] + boxes[:, 2]) / 2
    cy_vals = (boxes[:, 1] + boxes[:, 3]) / 2
    cx = float(np.average(cx_vals, weights=vikter))
    cy = float(np.average(cy_vals, weights=vikter))

    # Omslutande ruta för alla subjekt
    x1, y1 = boxes[:, 0].min(), boxes[:, 1].min()
    x2, y2 = boxes[:, 2].max(), boxes[:, 3].max()

    return cx, cy, float(x1), float(y1), float(x2), float(y2)


def _kompositionspoang(subj_cx, subj_cy, crop_left, crop_top,
                       crop_right, crop_bottom, aktions_riktning):
    """
    Beräknar kompositionskvalitet för en given crop (0 = bäst).
    Lägre avstånd till närmaste rule-of-thirds punkt = bättre.
    Aktionsutrymme: om subjektet rör sig åt höger bör det sitta i vänstra tredjedelen.
    """
    crop_w = crop_right  - crop_left
    crop_h = crop_bottom - crop_top

    # Normalisera subjektets position inom croppen
    rel_x = (subj_cx - crop_left) / crop_w if crop_w > 0 else 0.5
    rel_y = (subj_cy - crop_top)  / crop_h if crop_h > 0 else 0.5

    # Avstånd till närmaste RoT-korsning
    avstand = min(
        (rel_x - rx)**2 + (rel_y - ry)**2
        for rx, ry in _ROT
    )

    # Aktionsutrymme: subjekt i höger halva men rör sig åt höger = dåligt
    aktion_straff = 0.0
    if aktions_riktning > 0 and rel_x > 0.55:   # rör sig höger, sitter höger
        aktion_straff = 0.05
    elif aktions_riktning < 0 and rel_x < 0.45:  # rör sig vänster, sitter vänster
        aktion_straff = 0.05

    return avstand + aktion_straff


def berakna_crop(yolo_results, img_shape, marginal=0.10):
    """
    Provar aspektkvoterna original → 4:5 → 16:9 och väljer den crop
    som ger bäst komposition med subjektet vid en rule-of-thirds korsning.

    Returnerar (top, left, bottom, right) normaliserat 0..1, eller None.
    """
    subj = _subject_box(yolo_results)
    if subj is None:
        return None

    cx, cy, sx1, sy1, sx2, sy2 = subj
    h_img, w_img = img_shape[:2]
    original_kvot = w_img / h_img

    # Uppskatta aktionsriktning: om subjektet är i vänstra halvan antas
    # det röra sig mot mitten/höger, och vice versa
    aktions_riktning = 1.0 if cx < 0.5 else -1.0

    # Minsta crop-storlek för att rymma subjektet + marginal
    subj_w = (sx2 - sx1) + marginal * 2
    subj_h = (sy2 - sy1) + marginal * 2

    basta_poang = float("inf")
    basta_crop  = None
    basta_kvot_namn = None

    kvoter = [("original", original_kvot), ("4:5", 4/5), ("16:9", 16/9)]

    for kvot_namn, kvot in kvoter:
        # Bestäm crop-dimensioner baserat på aspektkvot
        # Utgå från subjektets storlek och välj minsta crop som ryms i bilden
        if kvot >= 1.0:   # liggande
            crop_w = max(subj_w, subj_h * kvot)
            crop_h = crop_w / kvot
        else:             # stående
            crop_h = max(subj_h, subj_w / kvot)
            crop_w = crop_h * kvot

        # Om croppen inte ryms i bilden: skippa denna kvot
        if crop_w > 1.0 or crop_h > 1.0:
            continue

        # Prova placera subjektets centrum vid varje RoT-korsning
        for rot_x, rot_y in _ROT:
            left   = cx - rot_x * crop_w
            top    = cy - rot_y * crop_h
            right  = left + crop_w
            bottom = top  + crop_h

            # Skjut in i bilden om det sticker utanför
            if left < 0:
                right -= left; left = 0.0
            if top < 0:
                bottom -= top; top = 0.0
            if right > 1.0:
                left -= (right - 1.0); right = 1.0
            if bottom > 1.0:
                top  -= (bottom - 1.0); bottom = 1.0

            # Kontrollera att subjektet faktiskt är innanför med marginal
            if sx1 < left or sx2 > right or sy1 < top or sy2 > bottom:
                continue

            poang = _kompositionspoang(cx, cy, left, top, right, bottom,
                                       aktions_riktning)

            if poang < basta_poang:
                basta_poang     = poang
                basta_crop      = (top, left, bottom, right)
                basta_kvot_namn = kvot_namn

    if basta_crop is None:
        return None

    # Ignorera meningslösa crops som täcker nästan hela bilden
    top, left, bottom, right = basta_crop
    if (right - left) > 0.93 and (bottom - top) > 0.93:
        return None

    return basta_crop


def skriv_xmp(nef_path, crop=None, vinkel=0.0,
              exposure=None, temperatur=None, tint=None):
    """Skriver en XMP-sidecar bredvid NEF-filen.

    exposure:    relativ EV-justering (crs:Exposure2012), eller None.
    temperatur:  absolut Kelvin (crs:Temperature, WhiteBalance=Custom), eller None.
    tint:        absolut tint (crs:Tint), används med temperatur.
    """
    if crop:
        top, left, bottom, right = crop
        has_crop = "True"
    else:
        top, left, bottom, right = 0.0, 0.0, 1.0, 1.0
        has_crop = "False"

    rader = []
    if exposure is not None:
        rader.append(f"crs:Exposure2012='{exposure:+.2f}'")
    if temperatur is not None:
        rader.append("crs:WhiteBalance='Custom'")
        rader.append(f"crs:Temperature='{int(round(temperatur))}'")
        rader.append(f"crs:Tint='{int(round(tint or 0))}'")
    extra = ("\n      " + "\n      ".join(rader)) if rader else ""

    innehall = XMP_MALL.format(
        has_crop=has_crop,
        top=top, left=left, bottom=bottom, right=right,
        vinkel=vinkel, extra=extra,
    )
    xmp_path = Path(nef_path).with_suffix(".xmp")
    xmp_path.write_text(innehall, encoding="utf-8")
    return xmp_path
