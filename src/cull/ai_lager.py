"""AI-lager: YOLOv8, MediaPipe Pose, EasyOCR för tröjnummer."""

import contextlib
import os
import sys
import urllib.request
from pathlib import Path

# Tysta TensorFlow Lite / MediaPipe / PyTorch-loggar (Python-nivå)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["GRPC_VERBOSITY"] = "ERROR"

import warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*MPS.*")


@contextlib.contextmanager
def _tysta_stderr():
    """Stänger av C-nivå stderr (TF Lite / glog) under modellladdning."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old, 2)
        os.close(old)

import cv2
import numpy as np

FARG_HSV = {
    "röd":     ([0,   100, 100], [10,  255, 255]),
    "mörkröd": ([170, 100, 100], [180, 255, 255]),
    "blå":     ([100, 100,  80], [130, 255, 255]),
    "ljusblå": ([85,   80,  80], [105, 255, 255]),
    "gul":     ([20,  100, 100], [35,  255, 255]),
    "grön":    ([40,   80,  80], [80,  255, 255]),
    "vit":     ([0,     0, 180], [180,  30, 255]),
    "svart":   ([0,     0,   0], [180, 255,  60]),
    "orange":  ([10,  150, 150], [20,  255, 255]),
    "lila":    ([130,  80,  80], [160, 255, 255]),
}

FARG_NAMN = list(FARG_HSV)

_POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
_POSE_MODEL_PATH = Path.home() / ".cache" / "cull" / "pose_landmarker_lite.task"


def _hamta_pose_modell():
    if _POSE_MODEL_PATH.exists():
        return _POSE_MODEL_PATH
    _POSE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Laddar ned MediaPipe pose-modell (~3 MB)…")
    urllib.request.urlretrieve(_POSE_MODEL_URL, _POSE_MODEL_PATH)
    print("Pose-modell nedladdad.")
    return _POSE_MODEL_PATH


def _skapa_pose_detektor():
    """Skapar en ny PoseLandmarker-instans (en per tråd i poolen)."""
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    modell = _hamta_pose_modell()
    opts = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(modell)),
        num_poses=4,
        min_pose_detection_confidence=0.4,
    )
    with _tysta_stderr():
        return mp_vision.PoseLandmarker.create_from_options(opts)


def _valj_device():
    """Returnerar 'mps' på Apple Silicon, annars 'cpu'."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def ladda_modeller(med_ocr=False, n_pose=None, yolo_modell="yolo11s.pt",
                   med_estetik=False):
    """
    Returnerar dict med laddade modeller.
    n_pose:       antal parallella pose-detektorer (default = CPU-kärnor, max 8).
    yolo_modell:  vikt-fil för YOLO (yolov8n.pt = snabb, yolo11s/m.pt = bättre).
    med_estetik:  ladda NIMA-estetikmodell (kräver pyiqa).
    """
    import os
    if n_pose is None:
        n_pose = min(os.cpu_count() or 4, 8)

    modeller = {"yolo": None, "pose_pool": [], "ocr": None,
                "estetik": None, "device": _valj_device()}

    try:
        from ultralytics import YOLO
        with _tysta_stderr():
            modeller["yolo"] = YOLO(yolo_modell)
            if modeller["device"] == "mps":
                try:
                    modeller["yolo"].to("mps")
                except Exception:
                    modeller["device"] = "cpu"
        print(f"YOLO ({yolo_modell}): aktivt ({modeller['device'].upper()})")
    except ImportError:
        sys.exit("AI-läget kräver ultralytics: pipx inject cull ultralytics")

    try:
        pool = []
        for _ in range(n_pose):
            pool.append(_skapa_pose_detektor())
        modeller["pose_pool"] = pool
        print(f"MediaPipe Pose: aktivt ({n_pose} detektorer)")
    except Exception as e:
        print(f"MediaPipe Pose: ej tillgängligt ({e})")

    if med_ocr:
        try:
            import easyocr
            with _tysta_stderr():
                modeller["ocr"] = easyocr.Reader(["en"], gpu=False, verbose=False)
            print("EasyOCR: aktivt")
        except ImportError:
            print("EasyOCR saknas: pipx inject cull easyocr  (tröjnummer inaktiverat)")

    if med_estetik:
        try:
            import pyiqa
            with _tysta_stderr():
                modeller["estetik"] = pyiqa.create_metric(
                    "nima", device=modeller["device"])
            print(f"NIMA-estetik: aktivt ({modeller['device'].upper()})")
        except ImportError:
            print("NIMA saknas: pipx inject cull pyiqa  (estetik inaktiverat)")
        except Exception as e:
            print(f"NIMA: ej tillgängligt ({e})")

    return modeller


def nima_poang(img_bgr, metric, device):
    """Returnerar NIMA-estetikpoäng (~1–10, högre bättre) för en BGR-bild."""
    import torch
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0) / 255.0
    with torch.no_grad():
        return float(metric(t.to(device)).item())


# --- poängsättning -----------------------------------------------------------

def armar_uppe(pose_result):
    """True om någon person har händerna klart ovanför axlarna."""
    for lm in (pose_result.pose_landmarks or []):
        try:
            v_axel = (lm[11].y + lm[12].y) / 2
            v_hand = min(lm[15].y, lm[16].y)
            if v_hand < v_axel - 0.05:
                return True
        except (IndexError, AttributeError):
            continue
    return False


def hemma_farg_andel(img_bgr, farg_namn):
    if farg_namn not in FARG_HSV:
        return 0.0
    lo, hi = [np.array(x, np.uint8) for x in FARG_HSV[farg_namn]]
    h = img_bgr.shape[0]
    roi = img_bgr[h // 3:, :]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    return mask.sum() / 255 / mask.size


def las_trojnummer(img_bgr, yolo_results, ocr, bevaka):
    """
    Kör OCR på varje person-crop från YOLO.
    Returnerar True om ett bevakat tröjnummer hittas.
    """
    if ocr is None or not bevaka or yolo_results is None:
        return False

    h, w = img_bgr.shape[:2]
    for box, cls in zip(yolo_results.boxes.xyxy, yolo_results.boxes.cls):
        if int(cls) != 0:   # klass 0 = person
            continue
        x1, y1, x2, y2 = map(int, box.tolist())
        # Fokusera på ryggnumret — övre 2/3 av personcroppen
        y_mid = y1 + (y2 - y1) * 2 // 3
        crop = img_bgr[y1:y_mid, x1:x2]
        if crop.size == 0:
            continue
        resultat = ocr.readtext(crop, allowlist="0123456789", detail=0)
        for text in resultat:
            text = text.strip()
            if text in bevaka:
                return True
    return False


def _kör_pose(args):
    """Kör pose-detektion i en tråd med en dedikerad detektor från poolen.

    OBS: ingen fd-nivå-tystande här — `_tysta_stderr` manipulerar den
    process-globala fd 2 och är inte trådsäker (kapplöpning ger
    "Bad file descriptor" när flera pose-trådar kör samtidigt).
    """
    img_bgr, pose_detektor = args
    import mediapipe as mp
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    return pose_detektor.detect(mp_img)


def _bonus_fran_yolo(img_bgr, yolo_res, pose_res, modeller, hemma_farg, bevaka):
    """Beräknar AI-bonusar givet YOLO- och pose-resultat."""
    b = {"armar": 0.0, "boll": 0.0, "hemma": 0.0, "trojnummer": 0.0,
         "_yolo": yolo_res}

    klasser = yolo_res.boxes.cls.tolist() if yolo_res.boxes else []
    b["boll"] = 0.08 if 32 in klasser else 0.0

    if pose_res is not None and armar_uppe(pose_res):
        b["armar"] = 0.15

    if hemma_farg:
        b["hemma"] = min(hemma_farg_andel(img_bgr, hemma_farg) * 2, 0.08)

    if bevaka and modeller["ocr"]:
        if las_trojnummer(img_bgr, yolo_res, modeller["ocr"], bevaka):
            b["trojnummer"] = 0.12

    return b


def bonus_batch(imgs_bgr, resultat_refs, modeller, hemma_farg, bevaka,
                batch_storlek=16, progress_cb=None):
    """
    Kör YOLO i batch + parallell MediaPipe pose per bild.
    Skriver bonusar direkt in i resultat_refs-diktarna.
    """
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue

    yolo = modeller["yolo"]
    if yolo is None:
        return
    device = modeller.get("device", "cpu")
    estetik = modeller.get("estetik")

    # Bygg en pool av pose-detektorer via en kö
    pose_pool = modeller.get("pose_pool", [])
    pose_kö = Queue()
    for d in pose_pool:
        pose_kö.put(d)

    totalt = len(imgs_bgr)
    klar   = 0

    # En enda fd-nivå-redirect runt hela loopen (anropas bara från
    # huvudtråden) tystar C-nivå-varningar från MediaPipe/TF Lite utan den
    # trådosäkra per-bild-varianten som gav "Bad file descriptor".
    with _tysta_stderr():
        for start in range(0, totalt, batch_storlek):
            batch_imgs = imgs_bgr[start:start + batch_storlek]
            batch_refs = resultat_refs[start:start + batch_storlek]

            # YOLO-batch
            yolo_res_list = yolo(batch_imgs, verbose=False, device=device)

            # Parallell pose (en tråd per bild, lånar detektor från kön)
            pose_results = [None] * len(batch_imgs)
            if pose_pool:
                def kör_en_pose(idx_img):
                    idx, img = idx_img
                    det = pose_kö.get()
                    try:
                        return idx, _kör_pose((img, det))
                    finally:
                        pose_kö.put(det)

                n_workers = min(len(pose_pool), len(batch_imgs))
                with ThreadPoolExecutor(max_workers=n_workers) as ex:
                    for idx, res in ex.map(kör_en_pose, enumerate(batch_imgs)):
                        pose_results[idx] = res

            for img, ref, yolo_res, pose_res in zip(
                    batch_imgs, batch_refs, yolo_res_list, pose_results):
                b = _bonus_fran_yolo(img, yolo_res, pose_res, modeller,
                                     hemma_farg, bevaka)
                ref.update(b)
                if estetik is not None:
                    try:
                        ref["nima"] = nima_poang(img, estetik, device)
                    except Exception:
                        ref["nima"] = None

            klar += len(batch_imgs)
            if progress_cb:
                progress_cb(klar, totalt)
