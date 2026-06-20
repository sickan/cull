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
      crs:StraightenAngle='{vinkel:.2f}'
    />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""


def berakna_uppratning(img_bgr):
    """
    Detekterar horisontella linjer (planets kant/mittlinje) med Hough-transform
    och returnerar korrektionsvinkeln i grader.
    """
    h, w = img_bgr.shape[:2]
    # Sök i nedre halvan — gräs och planmarkeringar
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
        vinkel = np.degrees(np.arctan2(dy, dx))
        if abs(vinkel) < 15:   # bara nära-horisontella linjer
            vinklar.append(vinkel)

    if not vinklar:
        return 0.0

    median = float(np.median(vinklar))
    # Begränsa till rimlig korrektionsvinkel
    return float(np.clip(-median, -5.0, 5.0))


def berakna_crop(yolo_results, img_shape, marginal=0.12):
    """
    Beräknar en beskärningsruta som omsluter alla detekterade
    spelare och boll, med lite luft runt om.
    Returnerar (top, left, bottom, right) normaliserat 0..1,
    eller None om inga detektioner.
    """
    if yolo_results is None or not yolo_results.boxes:
        return None

    h, w = img_shape[:2]
    boxes = yolo_results.boxes.xyxyn.tolist()   # normaliserade koordinater
    if not boxes:
        return None

    xs = [b[0] for b in boxes] + [b[2] for b in boxes]
    ys = [b[1] for b in boxes] + [b[3] for b in boxes]

    left   = max(0.0, min(xs) - marginal)
    top    = max(0.0, min(ys) - marginal)
    right  = min(1.0, max(xs) + marginal)
    bottom = min(1.0, max(ys) + marginal)

    # Ignorera crops som täcker nästan hela bilden — inte meningsfull
    if (right - left) > 0.92 and (bottom - top) > 0.92:
        return None

    return top, left, bottom, right


def skriv_xmp(nef_path, crop=None, vinkel=0.0):
    """Skriver en XMP-sidecar bredvid NEF-filen."""
    if crop:
        top, left, bottom, right = crop
        has_crop = "True"
    else:
        top, left, bottom, right = 0.0, 0.0, 1.0, 1.0
        has_crop = "False"

    innehall = XMP_MALL.format(
        has_crop=has_crop,
        top=top, left=left, bottom=bottom, right=right,
        vinkel=vinkel,
    )
    xmp_path = Path(nef_path).with_suffix(".xmp")
    xmp_path.write_text(innehall, encoding="utf-8")
    return xmp_path
