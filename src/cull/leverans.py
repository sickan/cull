"""Leveransprofiler: producerar leveransfärdiga JPEG ur urvalet (snabbflöde,
flöde 3 & 4 — ingen Lightroom). Per mottagare: aspekt/maxmått, max filstorlek,
stil. Upprätning (gyro) bakas in i pixlarna eftersom det är en färdig JPEG."""

import math
from pathlib import Path

import cv2

# Namngivna mottagarprofiler. max_w/max_h = box bilden ska få plats i (behåller
# bildförhållande, förstorar aldrig). stil: "naturlig" = kamerans bild orörd.
PROFILER = {
    "CEV": {"antal": 30, "max_w": 2500, "max_h": 1500, "max_mb": 7.0,
            "stil": "naturlig"},
}


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


def _vinkel_som_bevarar(w, h, vinkel, bbox_px, tolerans=0.03):
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


def exportera(jobb, ut_dir, profil, logg=print):
    """jobb: lista av {namn (utfil-stem), jpg (full preview-path), vinkel (gyro
    eller None)}. Skriver leverans-JPEG till ut_dir enligt profil. Returnerar
    listan med skapade filer."""
    from cull import vision_lager
    ut_dir = Path(ut_dir)
    ut_dir.mkdir(parents=True, exist_ok=True)
    skapade = []
    kapade = 0
    for j in jobb:
        img = cv2.imread(str(j["jpg"])) if j.get("jpg") else None
        if img is None:
            continue
        vinkel = j.get("vinkel")
        # Innehållsmedveten upprätning: hitta motivet, klipp aldrig bort det.
        bbox = vision_lager.saliens_bbox(j["jpg"]) if vinkel else None
        if vinkel and bbox is not None:
            h, w = img.shape[:2]
            sänkt = _vinkel_som_bevarar(
                w, h, vinkel, (bbox[0]*w, bbox[1]*h, bbox[2]*w, bbox[3]*h))
            if abs(sänkt) + 0.05 < abs(vinkel):
                kapade += 1
        img = rakta(img, vinkel, bbox)
        img = passa_i_box(img, profil["max_w"], profil["max_h"])
        ut = ut_dir / f"{j['namn']}.jpg"
        spara_under_storlek(img, ut, profil["max_mb"])
        skapade.append(ut)
    logg(f"  Leverans ({profil.get('_namn', '?')}): {len(skapade)} JPEG "
         f"≤{profil['max_w']}×{profil['max_h']}, ≤{profil['max_mb']:.0f} MB."
         + (f" Rätning dämpad på {kapade} för att bevara motivet." if kapade else ""))
    return skapade
