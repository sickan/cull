"""Generera XMP-sidecars med upprätning (rätning av lutande horisont)."""

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


def skriv_xmp(nef_path, crop=None, vinkel=0.0,
              exposure=None, temperatur=None, tint=None, profil=None):
    """Skriver en XMP-sidecar bredvid NEF-filen.

    exposure:    relativ EV-justering (crs:Exposure2012), eller None.
    temperatur:  absolut Kelvin (crs:Temperature, WhiteBalance=Custom), eller None.
    tint:        absolut tint (crs:Tint), används med temperatur.
    profil:      kameraprofil (crs:CameraProfile), t.ex. 'Camera Neutral'.
    """
    if crop:
        top, left, bottom, right = crop
        has_crop = "True"
    else:
        top, left, bottom, right = 0.0, 0.0, 1.0, 1.0
        has_crop = "False"

    rader = []
    if profil:
        rader.append(f"crs:CameraProfile='{profil}'")
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
