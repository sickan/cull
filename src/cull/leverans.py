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


def rakta(img, vinkel):
    """Roterar för upprätning och beskär bort kilarna (gyro-vinkeln bakas in)."""
    if vinkel is None or abs(vinkel) < 0.05:
        return img
    h, w = img.shape[:2]
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
    ut_dir = Path(ut_dir)
    ut_dir.mkdir(parents=True, exist_ok=True)
    skapade = []
    for j in jobb:
        img = cv2.imread(str(j["jpg"])) if j.get("jpg") else None
        if img is None:
            continue
        img = rakta(img, j.get("vinkel"))
        img = passa_i_box(img, profil["max_w"], profil["max_h"])
        ut = ut_dir / f"{j['namn']}.jpg"
        spara_under_storlek(img, ut, profil["max_mb"])
        skapade.append(ut)
    logg(f"  Leverans ({profil.get('_namn', '?')}): {len(skapade)} JPEG "
         f"≤{profil['max_w']}×{profil['max_h']}, ≤{profil['max_mb']:.0f} MB.")
    return skapade
