#!/usr/bin/env python3
"""
cull — teknisk culling av NEF-uppdrag (macOS)

Extraherar inbäddad JPEG-preview ur varje NEF, poängsätter på skärpa /
exponering / ögon och kopierar topp-urvalet till urval/.

Valfritt AI-lager (--ai) aktiverar YOLOv8 + MediaPipe för att ge bonus
till bilder med armar i luften (målgest), synlig boll och hemmalagsfärg.

Krav:
  exiftool (brew install exiftool)
  opencv-python, numpy (ingår)

AI-tillägg (valfritt):
  pip install 'cull[ai]'   eller   pipx inject cull ultralytics mediapipe
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("Saknar opencv/numpy. Kör: pip install opencv-python numpy")

# --- färgnamn → HSV-intervall (lower, upper) --------------------------------

FARG_HSV = {
    "röd":    ([0,   100, 100], [10,  255, 255]),
    "mörkröd":([170, 100, 100], [180, 255, 255]),
    "blå":    ([100, 100,  80], [130, 255, 255]),
    "ljusblå":([85,  80,  80], [105, 255, 255]),
    "gul":    ([20,  100, 100], [35,  255, 255]),
    "grön":   ([40,  80,  80],  [80,  255, 255]),
    "vit":    ([0,   0,   180], [180,  30, 255]),
    "svart":  ([0,   0,   0],   [180, 255,  60]),
    "orange": ([10,  150, 150], [20,  255, 255]),
    "lila":   ([130, 80,  80],  [160, 255, 255]),
}


def kontrollera_exiftool():
    if shutil.which("exiftool") is None:
        sys.exit("Saknar exiftool. Kör: brew install exiftool")


def extrahera_preview(nef_path, ut_dir):
    ut = Path(ut_dir) / (Path(nef_path).stem + ".jpg")
    for tag in ("-JpgFromRaw", "-PreviewImage"):
        subprocess.run(
            ["exiftool", "-b", tag, str(nef_path)],
            stdout=open(ut, "wb"), stderr=subprocess.DEVNULL
        )
        if ut.exists() and ut.stat().st_size > 10000:
            return ut
    return None


def skarpa(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def exponering(gray):
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    klippt_hog = hist[250:].sum() / total
    klippt_lag = hist[:5].sum() / total
    medel = gray.mean() / 255.0
    straff = klippt_hog * 2.0 + klippt_lag * 1.5 + abs(medel - 0.45)
    return max(0.0, 1.0 - straff)


def ogon_ansikten(gray):
    f_cas = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    e_cas = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_eye.xml")
    ansikten = f_cas.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
    ogon = sum(
        len(e_cas.detectMultiScale(gray[y:y+h, x:x+w], 1.1, 6))
        for (x, y, w, h) in ansikten
    )
    return len(ansikten), ogon


def bas_poangsatt(jpg_path):
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
        "_img":     img,
    }


# --- AI-lager ----------------------------------------------------------------

def ladda_ai_modeller():
    """Returnerar (yolo, pose) eller avslutar med felmeddelande."""
    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("AI-läget kräver ultralytics: pipx inject cull ultralytics mediapipe")
    try:
        import mediapipe.solutions.pose as mp_pose
    except ImportError:
        sys.exit("AI-läget kräver mediapipe: pipx inject cull ultralytics mediapipe")

    yolo = YOLO("yolov8n.pt")          # laddas ned automatiskt första gången (~6 MB)
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.4,
    )
    return yolo, pose


def armar_uppe(pose_results, img_h):
    """
    True om minst en person har båda handlederna ovanför axlarna.
    Används som indikator på målgest / firande.
    """
    if not pose_results.pose_landmarks:
        return False
    lm = pose_results.pose_landmarks.landmark

    import mediapipe.solutions.pose as mp_pose
    PL = mp_pose.PoseLandmark
    try:
        # y ökar nedåt i bild-koordinater
        v_axel = (lm[PL.LEFT_SHOULDER].y + lm[PL.RIGHT_SHOULDER].y) / 2
        v_hand  = min(lm[PL.LEFT_WRIST].y, lm[PL.RIGHT_WRIST].y)
        return v_hand < v_axel - 0.05   # händerna klart ovanför axellinje
    except Exception:
        return False


def hemma_farg_andel(img_bgr, farg_namn):
    """
    Andel pixlar i bilden som matchar hemmalagsfärgen (0..1).
    Söker i den nedre 2/3-delen (spelare, inte himmel/publik).
    """
    if farg_namn not in FARG_HSV:
        return 0.0
    lo, hi = [np.array(x, np.uint8) for x in FARG_HSV[farg_namn]]
    h = img_bgr.shape[0]
    roi = img_bgr[h // 3:, :]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    return mask.sum() / 255 / mask.size


def ai_bonus(img_bgr, yolo, pose, hemma_farg):
    """Returnerar en dict med AI-baserade bonusvärden."""
    bonus = {"armar": 0.0, "boll": 0.0, "hemma": 0.0}

    # YOLOv8 — leta efter boll (klass 32) och spelare (klass 0)
    results = yolo(img_bgr, verbose=False)[0]
    klasser = results.boxes.cls.tolist() if results.boxes else []
    bonus["boll"] = 0.08 if 32 in klasser else 0.0

    # MediaPipe Pose — armar uppe?
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pose_res = pose.process(rgb)
    if armar_uppe(pose_res, img_bgr.shape[0]):
        bonus["armar"] = 0.15

    # Hemmalagsfärg
    if hemma_farg:
        andel = hemma_farg_andel(img_bgr, hemma_farg)
        bonus["hemma"] = min(andel * 2, 0.08)   # max +0.08

    return bonus


# --- huvud -------------------------------------------------------------------

def parse_tid(s):
    try:
        from datetime import datetime
        s = s.replace(":", "-", 2)
        return datetime.fromisoformat(s.strip()).timestamp()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(
        prog="cull",
        description="Teknisk culling av NEF-filer.",
    )
    ap.add_argument("katalog")
    ap.add_argument("--topp",      type=int,   default=None)
    ap.add_argument("--andel",     type=float, default=0.20)
    ap.add_argument("--burst-sek", type=float, default=2.0)
    ap.add_argument("--rapport",   action="store_true")
    ap.add_argument("--ai",        action="store_true",
                    help="aktivera YOLOv8 + MediaPipe (kräver 'cull[ai]')")
    ap.add_argument("--hemma-farg", default=None, metavar="FÄRG",
                    help=f"hemmalagsfärg: {', '.join(FARG_HSV)}")
    args = ap.parse_args()

    if args.hemma_farg and not args.ai:
        print("Tips: --hemma-farg har effekt bara tillsammans med --ai.")

    kontrollera_exiftool()
    katalog = Path(args.katalog).expanduser()
    if not katalog.is_dir():
        sys.exit(f"Hittar inte katalogen: {katalog}")

    nef_filer = sorted(p for p in katalog.iterdir() if p.suffix.lower() == ".nef")
    if not nef_filer:
        sys.exit("Inga NEF-filer i katalogen.")

    print(f"{len(nef_filer)} NEF hittade. Extraherar previews och poängsätter…")
    if args.ai:
        print("Laddar AI-modeller (YOLOv8 + MediaPipe)…")
        yolo, pose = ladda_ai_modeller()
        print("AI-modeller redo.\n")

    r = subprocess.run(
        ["exiftool", "-T", "-FileName", "-SubSecDateTimeOriginal",
         *[str(p) for p in nef_filer]],
        capture_output=True, text=True
    )
    tider = {}
    for rad in r.stdout.strip().splitlines():
        delar = rad.split("\t")
        if len(delar) >= 2:
            tider[delar[0]] = delar[1]

    resultat = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, nef in enumerate(nef_filer, 1):
            preview = extrahera_preview(nef, tmp)
            if preview is None:
                print(f"  [{i}/{len(nef_filer)}] {nef.name}: ingen preview, hoppar")
                continue
            p = bas_poangsatt(preview)
            if p is None:
                continue

            if args.ai:
                img = p.pop("_img")
                bonusar = ai_bonus(img, yolo, pose, args.hemma_farg)
                p.update(bonusar)
            else:
                p.pop("_img", None)
                p.update({"armar": 0.0, "boll": 0.0, "hemma": 0.0})

            p["fil"] = nef
            p["tid"] = tider.get(nef.name, "")
            resultat.append(p)
            if i % 25 == 0:
                print(f"  …{i}/{len(nef_filer)}")

    if not resultat:
        sys.exit("Inget kunde poängsättas.")

    # normalisera skärpa globalt
    sk = np.array([r["skarpa"] for r in resultat])
    lo, hi = np.percentile(sk, 5), np.percentile(sk, 95)
    spann = max(hi - lo, 1e-6)
    for r in resultat:
        r["skarpa_n"] = float(np.clip((r["skarpa"] - lo) / spann, 0, 1))

    for r in resultat:
        ogon_bonus = 0.0
        if r["ansikten"] > 0:
            ogon_bonus = min(r["ogon"] / (r["ansikten"] * 2), 1.0) * 0.10
        r["poang"] = (
            0.55 * r["skarpa_n"]
            + 0.35 * r["exp"]
            + ogon_bonus
            + r["armar"]
            + r["boll"]
            + r["hemma"]
        )

    # burst-gruppering
    har_tid = all(parse_tid(r["tid"]) is not None for r in resultat)
    if har_tid:
        resultat.sort(key=lambda r: parse_tid(r["tid"]))
        grupp, forra = 0, None
        for r in resultat:
            t = parse_tid(r["tid"])
            if forra is not None and t - forra > args.burst_sek:
                grupp += 1
            r["grupp"] = grupp
            forra = t
    else:
        for i, r in enumerate(resultat):
            r["grupp"] = i

    n_total  = len(resultat)
    n_behall = args.topp if args.topp else max(1, round(n_total * args.andel))

    basta_per_grupp = {}
    for r in resultat:
        g = r["grupp"]
        if g not in basta_per_grupp or r["poang"] > basta_per_grupp[g]["poang"]:
            basta_per_grupp[g] = r

    valda = sorted(basta_per_grupp.values(), key=lambda r: r["poang"], reverse=True)
    if len(valda) < n_behall:
        rest = sorted(
            [r for r in resultat if r not in valda],
            key=lambda r: r["poang"], reverse=True
        )
        valda += rest[:n_behall - len(valda)]
    valda = valda[:n_behall]

    print(f"\nBehåller {len(valda)} av {n_total} ({len(basta_per_grupp)} burst-grupper).\n")
    print("Topp-urval:")
    for r in sorted(valda, key=lambda r: r["poang"], reverse=True)[:40]:
        ai_rad = (f"  armar={'ja' if r['armar'] else 'nej'}"
                  f"  boll={'ja' if r['boll'] else 'nej'}"
                  f"  hemma={r['hemma']:.2f}") if args.ai else ""
        print(f"  {r['poang']:.3f}  sk {r['skarpa_n']:.2f}  "
              f"exp {r['exp']:.2f}  ans {r['ansikten']}{ai_rad}  {r['fil'].name}")

    if args.rapport:
        print("\n(Rapportläge — inget kopierades.)")
        return

    ut_dir = katalog / "urval"
    ut_dir.mkdir(exist_ok=True)
    for r in valda:
        shutil.copy2(r["fil"], ut_dir / r["fil"].name)
        xmp = r["fil"].with_suffix(".xmp")
        if xmp.exists():
            shutil.copy2(xmp, ut_dir / xmp.name)

    print(f"\nKlart. {len(valda)} NEF kopierade till: {ut_dir}")


if __name__ == "__main__":
    main()
