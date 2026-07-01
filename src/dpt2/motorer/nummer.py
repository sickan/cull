"""Tröjnummer-kärna (KÄRNA): läs nummer ur ett YOLO/OCR-resultat och skriv dem
som keywords (XMP/IPTC) → syns i Lightroom.

Migrerad ur gamla `dpt.nummer_pass`. Detta är den rena kärnan — den tar redan
laddade modell-objekt (YOLO-resultat, OCR-läsare) som argument och rör inga
globala state-filer:

    _hemma_andel_crop   andel hemma-färgade pixlar i ett utsnitt (lag-bestämning)
    _las_nummer         (nr, namn)-träffar ur ett YOLO+OCR-resultat
    _namn_unikt         namn för ett nummer ENBART om unikt över lagen
    _skriv_keywords     skriv 'nr namn' som keywords via exiftool (idempotent)
    + filhjälpare (_bilder_per_stam, _preview_kalla, _nyckel, _env)

Orkestreringen (`kor`: previews→YOLO→OCR→cache→Claude-fallback→osakra_nummer) är
GLUE — den laddar tunga modeller (ai_lager), extraherar previews och äger
cache-/state-filerna. Den flyttar till worker-/tjänstelagret i ett senare steg.
`_claude_nummer` (vision-fallback) blir en konsument av `tjanster.claude`.
"""

import os
import subprocess
from pathlib import Path

from dpt2.motorer.filtyper import RAW_SUFFIX, JPG_SUFFIX, BILD_SUFFIX

COLOR_TROSKEL = 0.10   # andel hemma-färg i utsnittet för att räknas som hemmalag


def _env():
    """PATH-utökad miljö så exiftool/homebrew-verktyg hittas oavsett skal."""
    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def _nyckel(p):
    """Cache-nyckel path|size (omkörning gratis när filen är oförändrad)."""
    return f"{p}|{p.stat().st_size}"


def _bilder_per_stam(mapp):
    """{stam: [filer]} för alla bildfiler i mappen (raw + jpg)."""
    grupper = {}
    try:
        for p in sorted(mapp.iterdir()):
            if p.suffix.lower() in BILD_SUFFIX and not p.name.startswith("."):
                grupper.setdefault(p.stem, []).append(p)
    except Exception:
        pass
    return grupper


def _preview_kalla(filer):
    """Bästa fil att OCR:a per stam: jpg direkt om den finns, annars raw."""
    for f in filer:
        if f.suffix.lower() in JPG_SUFFIX:
            return f
    return filer[0]


def _hemma_andel_crop(crop_bgr, farg_namn):
    """Andel hemma-färgade pixlar i ett spelar-utsnitt (för lag-bestämning)."""
    from dpt2.motorer.farger import FARG_HSV
    import numpy as np
    import cv2
    if not farg_namn or farg_namn not in FARG_HSV or crop_bgr.size == 0:
        return 0.0
    lo, hi = [np.array(x, np.uint8) for x in FARG_HSV[farg_namn]]
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    return mask.sum() / 255 / mask.size


def _las_nummer(img_bgr, yolo_res, ocr, lag_roster, hemma_farg="",
                min_konf=0.45, max_personer=25):
    """Lista (nr, namn) för avlästa spelarnummer + antal personer. Brus-filter:
    konfidens + bara 1–2 siffror (0–99) + roster-filter. Namnsättning av BÅDA
    lagen: nummerunikhet först (nr som bara finns i ett lag → det lagets namn,
    ingen färg behövs), annars tröjfärg mot hemma-färg för krockande nummer. Två
    spelare med samma nummer i samma bild (hemma+borta) ger två poster. namn=''
    när roster saknas eller numret inte finns (då skrivs bara numret)."""
    if ocr is None or yolo_res is None or yolo_res.boxes is None:
        return [], 0
    teams = lag_roster or {}
    har_roster = any(teams.values())
    flera_lag = len([k for k in teams if k]) >= 2   # minst två namngivna lag

    def _resolve(nr, home_frac):
        if not har_roster:
            return "", True
        if flera_lag:
            inh = teams.get("hemma", {}).get(nr)
            ina = teams.get("borta", {}).get(nr)
            if inh and not ina:
                return inh, True
            if ina and not inh:
                return ina, True
            if inh and ina:                     # krock → tröjfärg avgör
                return (inh if home_frac >= COLOR_TROSKEL else ina), True
            return "", False
        for v in teams.values():                # enlagsroster
            if nr in v:
                return v[nr], True
        return "", False

    personer, n_pers = [], 0
    for box, cls in zip(yolo_res.boxes.xyxy, yolo_res.boxes.cls):
        if int(cls) != 0:           # klass 0 = person
            continue
        n_pers += 1
        x1, y1, x2, y2 = map(int, box.tolist())
        personer.append(((x2 - x1) * (y2 - y1), x1, y1, x2, y2))
    personer.sort(reverse=True)     # störst (närmast) först

    traffar = set()
    for _, x1, y1, x2, y2 in personer[:max_personer]:
        if (x2 - x1) < 24 or (y2 - y1) < 48:   # för liten → oläsbart
            continue
        y_mid = y1 + (y2 - y1) * 2 // 3        # ryggnumret = övre 2/3
        crop = img_bgr[max(0, y1):y_mid, max(0, x1):x2]
        if crop.size == 0:
            continue
        home_frac = _hemma_andel_crop(crop, hemma_farg) if flera_lag else 0.0
        for _b, text, konf in ocr.readtext(crop, allowlist="0123456789", detail=1):
            if konf < min_konf:
                continue
            t = (text.strip().lstrip("0") or "0")
            if not t.isdigit() or not (1 <= len(t) <= 2):   # tröjnummer 0–99
                continue
            namn, giltigt = _resolve(t, home_frac)
            if har_roster and not giltigt:                  # bara riktiga squad-nr
                continue
            traffar.add((t, namn))
    return list(traffar), n_pers


def _namn_unikt(nr, lag_roster):
    """Namn för ett nummer ENBART om det är unikt över lagen (annars '')."""
    teams = lag_roster or {}
    hits = [v[nr] for v in teams.values() if nr in v]
    return hits[0] if len(hits) == 1 else ""


def _skriv_keywords(filer, traffar, env):
    """traffar: lista av (nr, namn) (namn kan vara ''). Skriver 'nr namn' (eller
    bara 'nr') som keywords till alla filer för stammen + ev. .xmp-sidecar
    (Lightroom läser metadata ur sidecaren för raw-filer, inte inbäddat).
    Idempotent: tar bort (-=) varje värde före += så omkörning inte ger dubbletter
    och match-keywords m.m. bevaras. Hanterar samma nummer i två lag (två poster)."""
    if not traffar:
        return False
    par = sorted({(str(n), m or "") for n, m in traffar},
                 key=lambda p: (int(p[0]) if p[0].isdigit() else 0, p[1]))
    full_args = []   # bildfiler: XMP + IPTC
    xmp_args = []    # .xmp-sidecar: bara XMP (IPTC-IIM finns inte i sidecar)
    for nr, namn in par:
        flat = f"{nr} {namn}" if namn else str(nr)
        for v in {str(nr), flat}:   # täcker omkörning med/utan roster
            full_args += [f"-XMP-dc:Subject-={v}", f"-IPTC:Keywords-={v}",
                          f"-XMP-lr:HierarchicalSubject-=Spelare|{v}"]
            xmp_args += [f"-XMP-dc:Subject-={v}",
                         f"-XMP-lr:HierarchicalSubject-=Spelare|{v}"]
        full_args += [f"-XMP-dc:Subject+={flat}", f"-IPTC:Keywords+={flat}",
                      f"-XMP-lr:HierarchicalSubject+=Spelare|{flat}"]
        xmp_args += [f"-XMP-dc:Subject+={flat}",
                     f"-XMP-lr:HierarchicalSubject+=Spelare|{flat}"]

    # Mål: varje bildfil (full) + ev. sidecar för raw-filer (bara XMP).
    mål = [(f, full_args) for f in filer]
    for f in filer:
        if f.suffix.lower() in RAW_SUFFIX:
            sidecar = f.with_suffix(".xmp")
            if sidecar.exists():
                mål.append((sidecar, xmp_args))
    ok = False
    for path, args in mål:
        # Bildfiler: markera IPTC som UTF-8 (annars visas å/ä/ö i namn som skräp).
        # Sidecar (.xmp) har ingen IPTC-IIM → ingen markör behövs.
        charset = ([] if path.suffix.lower() == ".xmp"
                   else ["-charset", "UTF8", "-codedcharacterset=utf8"])
        cmd = (["exiftool", "-overwrite_original", "-sep", ", "]
               + charset + args + [str(path)])
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        ok = ok or r.returncode == 0
    return ok
