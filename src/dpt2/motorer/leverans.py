"""Leverans-geometri (KÄRNA): upprätning, aspekt-komponering och nedskalning.

Migrerad verbatim ur gamla `dpt.leverans`. Detta är den dpt-fria geometrikärnan
— ren matematik + cv2, inga andra dpt-beroenden:

    _komponera_4x5 / _crop_aspekt   porträtt-komponerad aspekt-crop (4:5 m.fl.)
    _storsta_inskrivna              största inskrivna rektangel i roterad bild
    _ryms_i_inskriven / _vinkel_som_bevarar   innehållsmedveten upprätning
    rakta                           rotera för upprätning + kapa kilarna
    passa_i_box                     skala ned i en box (förstorar aldrig)
    spara_under_storlek             JPEG under en MB-gräns
    _fit_aspekt                     geometrisk "4:5-lämplighet" (0–1)
    crop_rect                       normaliserad cropruta → crs:Crop i XMP
    PROFILER                        DATA: mottagarprofiler (CEV/Instagram)

Orkestreringen (`exportera`, `valj_instagram`, `_claude_instagram_pick`) är GLUE
— den behöver YOLO/Apple Vision/Claude och flyttar till worker-/tjänstelagret i
ett senare steg. `crop_rect` är navet för den icke-destruktiva LR-vägen (skriver
crs:Crop i XMP via xmp_writer); `rakta`/`passa_i_box`/`spara_under_storlek` driver
den destruktiva JPEG-vägen (CEV/Instagram).
"""

import math
from pathlib import Path

import cv2

# Namngivna mottagarprofiler. max_w/max_h = box bilden ska få plats i (behåller
# bildförhållande, förstorar aldrig). stil: "naturlig" = kamerans bild orörd.
PROFILER = {
    "CEV": {"antal": 30, "max_w": 2500, "max_h": 1500, "max_mb": 7.0,
            "stil": "naturlig"},
    # Instagram porträtt 4:5 (1080×1350). aspekt = (bredd, höjd) → innehålls-
    # medveten beskärning centrerad på motivet (saliens) innan nedskalning.
    "INSTAGRAM": {"antal": 20, "aspekt": (4, 5), "max_w": 1080, "max_h": 1350,
                  "max_mb": 8.0, "stil": "naturlig", "urval": True},
}


def _komponera_4x5(bbox_norm, w, h, aspekt=(4, 5), komp=None,
                   luft_topp=0.08, undertill=0.66, sidmarginal=0.06):
    """Pixelruta (x0,y0,x1,y1) för en mål-aspekt-crop som porträtt. Med en pose-
    innehållsruta (komp = top,left,bottom,right normaliserad, omsluter huvud→lår
    OCH båda händerna) passas det MINSTA 4:5-fönstret runt den så inget av motivet
    eller händerna kapas. Utan komp används en geometrisk approximation. Faller
    tillbaka på största centrerade fönstret om motivet saknas/fyller bilden.
    Ligger alltid inom bilden (förstorar aldrig)."""
    mål = aspekt[0] / aspekt[1]   # bredd/höjd

    def storsta():
        nw, nh = (mål * h, h) if (w / h) > mål else (w, w / mål)
        if bbox_norm is not None:
            cx = (bbox_norm[0] + bbox_norm[2]) / 2.0 * w
            cy = bbox_norm[1] * h - luft_topp * (bbox_norm[3] - bbox_norm[1]) * h
        else:
            cx, cy = w / 2.0, (h - nh) / 2.0
        x0 = min(max(cx - nw / 2.0, 0.0), w - nw)
        y0 = min(max(cy, 0.0), h - nh)
        return (x0, y0, x0 + nw, y0 + nh)

    if w <= 0 or h <= 0:
        return storsta()

    if komp is not None and len(komp) == 4:
        ct, cl, cb, cr = komp[0] * h, komp[1] * w, komp[2] * h, komp[3] * w
        cw, chh, ccx = (cr - cl), (cb - ct), (cl + cr) / 2.0
        # Garantera sidmarginal runt innehållet (= huvud→lår OCH båda händerna):
        # utan den blir crop_w == cw för breda poser (utbredda handskar) → croppen
        # ligger kant-i-kant med innehållsrutan och kapar de skrymmande handskarna,
        # vars verkliga utbredning ligger utanför pose-landmärkena.
        crop_h = max(chh, (cw * (1 + 2 * sidmarginal)) / mål)
        crop_w = crop_h * mål
        if crop_h > h or crop_w > w:             # innehållet större än bilden
            return storsta()
        y0 = min(max(ct, 0.0), h - crop_h)       # ankra topp vid innehållets topp
        x0 = min(max(ccx - crop_w / 2.0, 0.0), w - crop_w)
        return (x0, y0, x0 + crop_w, y0 + crop_h)

    if bbox_norm is None:
        return storsta()
    bx0, by0 = bbox_norm[0] * w, bbox_norm[1] * h
    bx1, by1 = bbox_norm[2] * w, bbox_norm[3] * h
    sh, sw, scx = max(1.0, by1 - by0), max(1.0, bx1 - bx0), (bx0 + bx1) / 2.0
    hr = luft_topp * sh
    crop_h = max(hr + undertill * sh, (sw * (1 + 2 * sidmarginal)) / mål)
    crop_w = crop_h * mål
    if crop_h >= h or crop_w >= w:
        return storsta()
    y0 = min(max(by0 - hr, 0.0), h - crop_h)
    x0 = min(max(scx - crop_w / 2.0, 0.0), w - crop_w)
    return (x0, y0, x0 + crop_w, y0 + crop_h)


def _crop_aspekt(img, aspekt_w, aspekt_h, bbox_norm=None, komp=None):
    """Beskär till mål-bildförhållandet, porträtt-komponerat (_komponera_4x5, ev.
    med pose-innehållsruta som rymmer båda händerna). Förstorar aldrig."""
    h, w = img.shape[:2]
    if w <= 0 or h <= 0:
        return img
    x0, y0, x1, y1 = (int(round(v)) for v in
                      _komponera_4x5(bbox_norm, w, h, (aspekt_w, aspekt_h), komp))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return img
    return img[y0:y1, x0:x1]


def _storsta_inskrivna(w, h, vinkel_grader):
    """Största axelriktade rektangel inuti en bild roterad vinkel_grader."""
    a = math.radians(abs(vinkel_grader))
    if w <= 0 or h <= 0:
        return w, h
    lang_bredast = w >= h
    lang, kort = (w, h) if lang_bredast else (h, w)
    sin_a, cos_a = abs(math.sin(a)), abs(math.cos(a))
    if kort <= 2.0 * sin_a * cos_a * lang or abs(sin_a - cos_a) < 1e-10:
        x = 0.5 * kort
        wr, hr = (x / sin_a, x / cos_a) if lang_bredast else (x / cos_a, x / sin_a)
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr = (w * cos_a - h * sin_a) / cos_2a
        hr = (h * cos_a - w * sin_a) / cos_2a
    return wr, hr


def _ryms_i_inskriven(w, h, vinkel, bbox_px):
    """True om motivets ruta (pixlar) ryms i den centrerade max-inskrivna
    rektangeln för given vinkel."""
    wr, hr = _storsta_inskrivna(w, h, vinkel)
    cx0, cy0 = (w - wr) / 2.0, (h - hr) / 2.0
    cx1, cy1 = cx0 + wr, cy0 + hr
    return (bbox_px[0] >= cx0 and bbox_px[1] >= cy0
            and bbox_px[2] <= cx1 and bbox_px[3] <= cy1)


def _vinkel_som_bevarar(w, h, vinkel, bbox_px, tolerans=0.01):
    """Största |vinkel| (samma tecken) vars kil-beskärning INTE klipper motivet.
    bbox_px får krympas med tolerans (liten kantklipp tillåten). 0 om inget går."""
    # Krymp motivrutan något — en hand precis vid kanten ska inte blockera helt.
    mx, my = tolerans * w, tolerans * h
    bb = (bbox_px[0] + mx, bbox_px[1] + my, bbox_px[2] - mx, bbox_px[3] - my)
    steg = abs(vinkel)
    while steg > 0.05:
        if _ryms_i_inskriven(w, h, steg, bb):
            return math.copysign(steg, vinkel)
        steg -= 0.2
    return 0.0


def rakta(img, vinkel, bbox_norm=None):
    """Roterar för upprätning och beskär bort kilarna. Innehållsmedvetet:
    om kil-beskärningen skulle klippa motivet (bbox_norm, normaliserad) kapas
    vinkeln tills motivet ryms — hellre lite kvarvarande lutning än bortklippt
    motiv."""
    if vinkel is None or abs(vinkel) < 0.05:
        return img
    h, w = img.shape[:2]
    if bbox_norm is not None:
        bbox_px = (bbox_norm[0] * w, bbox_norm[1] * h,
                   bbox_norm[2] * w, bbox_norm[3] * h)
        vinkel = _vinkel_som_bevarar(w, h, vinkel, bbox_px)
        if abs(vinkel) < 0.05:
            return img
    M = cv2.getRotationMatrix2D((w / 2, h / 2), vinkel, 1.0)
    rot = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_REPLICATE)
    wr, hr = _storsta_inskrivna(w, h, vinkel)
    wr, hr = int(wr), int(hr)
    x0, y0 = (w - wr) // 2, (h - hr) // 2
    return rot[y0:y0 + hr, x0:x0 + wr]


def passa_i_box(img, max_w, max_h):
    """Skalar ned så bilden får plats i max_w×max_h (behåller förhållande,
    förstorar aldrig)."""
    h, w = img.shape[:2]
    skala = min(max_w / w, max_h / h)
    if skala >= 1.0:
        return img
    return cv2.resize(img, (round(w * skala), round(h * skala)),
                      interpolation=cv2.INTER_AREA)


def spara_under_storlek(img, ut_path, max_mb, q_start=92):
    """Sparar JPEG och sänker kvaliteten tills filen är under max_mb."""
    gräns = max_mb * 1024 * 1024
    for q in range(q_start, 39, -6):
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok and len(buf) <= gräns:
            Path(ut_path).write_bytes(buf.tobytes())
            return q, len(buf)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 40])
    Path(ut_path).write_bytes(buf.tobytes())
    return 40, len(buf)


def _fit_aspekt(bbox_norm, w, h, aspekt):
    """Andel av motivrutan som överlever en aspekt-beskärning centrerad på
    motivet (1.0 = motivet ryms helt i 4:5, lägre = motivet klipps). Saknas
    motivruta antas 1.0. Detta är den geometriska '4:5-lämpligheten'."""
    if bbox_norm is None or w <= 0 or h <= 0:
        return 1.0
    mål = aspekt[0] / aspekt[1]
    cur = w / h
    nw, nh = (mål * h, h) if cur > mål else (w, w / mål)
    cx = (bbox_norm[0] + bbox_norm[2]) / 2.0 * w
    cy = (bbox_norm[1] + bbox_norm[3]) / 2.0 * h
    x0 = min(max(cx - nw / 2.0, 0.0), w - nw)
    y0 = min(max(cy - nh / 2.0, 0.0), h - nh)
    bx0, by0 = bbox_norm[0] * w, bbox_norm[1] * h
    bx1, by1 = bbox_norm[2] * w, bbox_norm[3] * h
    ix = max(0.0, min(bx1, x0 + nw) - max(bx0, x0))
    iy = max(0.0, min(by1, y0 + nh) - max(by0, y0))
    area = max(1e-6, (bx1 - bx0) * (by1 - by0))
    return (ix * iy) / area


def crop_rect(bbox_norm, w, h, aspekt, komp=None):
    """Normaliserad cropruta (top, left, bottom, right) för mål-bildförhållandet,
    porträtt-komponerad på motivet (ev. pose-innehållsruta) — för crs:Crop i XMP
    (LR öppnar bilden beskuren men redigerbar, ingen inbränd pixel)."""
    if w <= 0 or h <= 0:
        return (0.0, 0.1, 1.0, 0.9)
    x0, y0, x1, y1 = _komponera_4x5(bbox_norm, w, h, aspekt, komp)
    return (y0 / h, x0 / w, y1 / h, x1 / w)
