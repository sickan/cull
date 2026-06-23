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


_FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
_FACE_MODEL_PATH = Path.home() / ".cache" / "cull" / "face_landmarker.task"


def _hamta_face_modell():
    if _FACE_MODEL_PATH.exists():
        return _FACE_MODEL_PATH
    _FACE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Laddar ned MediaPipe face-modell (~3 MB)…")
    urllib.request.urlretrieve(_FACE_MODEL_URL, _FACE_MODEL_PATH)
    print("Face-modell nedladdad.")
    return _FACE_MODEL_PATH


def _skapa_face_detektor():
    """Skapar en ny FaceLandmarker-instans (en per tråd i poolen)."""
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    modell = _hamta_face_modell()
    opts = mp_vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(modell)),
        num_faces=4,
        min_face_detection_confidence=0.4,
    )
    with _tysta_stderr():
        return mp_vision.FaceLandmarker.create_from_options(opts)


def _valj_device():
    """Returnerar 'mps' på Apple Silicon, annars 'cpu'."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _yolo_sokvag(namn):
    """Absolut sökväg till YOLO-vikten i cull:s skrivbara modellcache
    (~/.cache/cull/models/). Oberoende av CWD — annars försöker ultralytics
    ladda ner till nuvarande mapp, som är skrivskyddad när appen startas från
    skrivbordet. Kopierar in en befintlig vikt om cachen saknar den."""
    import shutil
    if os.path.isabs(namn):
        return namn
    cache = Path.home() / ".cache" / "cull" / "models"
    cache.mkdir(parents=True, exist_ok=True)
    mål = cache / namn
    if mål.exists():
        return str(mål)
    for kand in (Path.home() / "Claude" / namn,
                 Path.home() / "Claude" / "cull" / namn,
                 Path.cwd() / namn):
        try:
            if kand.exists():
                shutil.copy2(kand, mål)
                return str(mål)
        except Exception:
            pass
    return str(mål)   # saknas → ultralytics laddar ner till skrivbar cache


def ladda_modeller(med_ocr=False, n_pose=None, yolo_modell="yolo11s.pt",
                   med_estetik=False, med_ogon=False, med_clip=False):
    """
    Returnerar dict med laddade modeller.
    n_pose:       antal parallella pose-detektorer (default = CPU-kärnor, max 8).
    yolo_modell:  vikt-fil för YOLO (yolov8n.pt = snabb, yolo11s/m.pt = bättre).
    med_estetik:  ladda NIMA-estetikmodell (kräver pyiqa).
    med_ogon:     ladda FaceLandmarker-pool för ögonkontakt (EAR + frontalitet).
    med_clip:     ladda CLIP för zero-shot semantiska features.
    """
    import os
    if n_pose is None:
        n_pose = min(os.cpu_count() or 4, 8)

    modeller = {"yolo": None, "pose_pool": [], "face_pool": [], "ocr": None,
                "estetik": None, "clip": None, "device": _valj_device()}

    try:
        from ultralytics import YOLO
        with _tysta_stderr():
            modeller["yolo"] = YOLO(_yolo_sokvag(yolo_modell))
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

    if med_ogon:
        try:
            fpool = []
            for _ in range(n_pose):
                fpool.append(_skapa_face_detektor())
            modeller["face_pool"] = fpool
            print(f"MediaPipe Face (ögonkontakt): aktivt ({n_pose} detektorer)")
        except Exception as e:
            print(f"MediaPipe Face: ej tillgängligt ({e})")

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

    if med_clip:
        from cull import clip_lager
        modeller["clip"] = clip_lager.ladda_clip(device=modeller["device"])

    return modeller


def nima_poang(img_bgr, metric, device):
    """Returnerar NIMA-estetikpoäng (~1–10, högre bättre) för en BGR-bild."""
    import torch
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0) / 255.0
    with torch.no_grad():
        return float(metric(t.to(device)).item())


def nima_poang_batch(imgs_bgr, metric, device):
    """NIMA för en hel batch i ett enda forward-pass (snabbare på MPS/GPU).
    Bilderna skalas till 224×224 så de kan staplas. Returnerar en lista floats."""
    import torch
    ts = []
    for img in imgs_bgr:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (224, 224))
        ts.append(torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0)
    batch = torch.stack(ts).to(device)
    with torch.no_grad():
        out = metric(batch)
    return [float(v) for v in out.detach().cpu().flatten().tolist()]


# --- poängsättning -----------------------------------------------------------

def antal_firande(pose_result):
    """
    Räknar personer som gör en firande-gest: arm uppe ELLER utbredd åt sidan.
    Fångar fler målfiranden än enbart 'arm ovanför axel' (utbredda armar,
    knytnäve i luften, en arm upp m.m.).
    """
    n = 0
    for lm in (pose_result.pose_landmarks or []):
        try:
            axel_y = (lm[11].y + lm[12].y) / 2
            hand_y = min(lm[15].y, lm[16].y)
            arm_upp = hand_y < axel_y - 0.05

            # Utbredda armar: handled tydligt utanför axelbredden i sidled.
            axelbredd = abs(lm[11].x - lm[12].x) + 1e-6
            vänster_kant = min(lm[11].x, lm[12].x)
            höger_kant = max(lm[11].x, lm[12].x)
            arm_ut = (lm[15].x < vänster_kant - 0.6 * axelbredd or
                      lm[16].x > höger_kant + 0.6 * axelbredd)

            if arm_upp or arm_ut:
                n += 1
        except (IndexError, AttributeError):
            continue
    return n


def klunga_bonus(yolo_results):
    """
    Bonus för en tät klunga av spelare (≥3) — typiskt målmobbning/kram efter
    mål, som fångas även när inga armar är uppe. Returnerar upp till 0.10.
    """
    if yolo_results is None or yolo_results.boxes is None:
        return 0.0
    personer = [box.tolist() for box, cls in
                zip(yolo_results.boxes.xyxy, yolo_results.boxes.cls)
                if int(cls) == 0]
    if len(personer) < 3:
        return 0.0

    # Kräv att lådorna FAKTISKT överlappar i 2D (kram/mobbning) — inte bara
    # ligger i samma höjdband, vilket är vanligt i normalt spel.
    def overlappar(a, b):
        ov_x = min(a[2], b[2]) - max(a[0], b[0])
        ov_y = min(a[3], b[3]) - max(a[1], b[1])
        if ov_x <= 0 or ov_y <= 0:
            return False
        minbredd = min(a[2] - a[0], b[2] - b[0]) + 1e-6
        # Tydlig sidoöverlappning, inte bara att kanterna nuddar.
        return ov_x > 0.25 * minbredd

    # Största gruppen av personer som hänger ihop via överlapp (graf-komponent).
    n = len(personer)
    grann = [[j for j in range(n) if j != i and overlappar(personer[i], personer[j])]
             for i in range(n)]
    besökt = [False] * n
    störst = 0
    for i in range(n):
        if besökt[i]:
            continue
        stack, storlek = [i], 0
        besökt[i] = True
        while stack:
            k = stack.pop()
            storlek += 1
            for m in grann[k]:
                if not besökt[m]:
                    besökt[m] = True
                    stack.append(m)
        störst = max(störst, storlek)

    if störst >= 4:
        return 0.10
    if störst >= 3:
        return 0.06
    return 0.0


_VAST_HSV_RANGES = [
    ([20, 150, 150], [35, 255, 255]),   # neon gul
    ([10, 150, 150], [20, 255, 255]),   # neon orange
    ([55, 150, 150], [75, 255, 255]),   # lime/neon grön
]


def _person_har_vast(img_bgr, box):
    """Returnerar True om person-crop troligtvis bär uppvärmningssättet (bib/väst)."""
    x1, y1, x2, y2 = (max(0, int(v)) for v in box)
    h, w = y2 - y1, x2 - x1
    if h < 20 or w < 10:
        return False
    # Torso-region: 20–70 % av höjden (undviker huvud och ben)
    ty1 = y1 + h // 5
    ty2 = y1 + h * 7 // 10
    torso = img_bgr[ty1:ty2, x1:x2]
    if torso.size == 0:
        return False
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    total = torso.shape[0] * torso.shape[1]
    for lo, hi in _VAST_HSV_RANGES:
        mask = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        if mask.sum() / 255 / total > 0.15:
            return True
    return False


def vast_straff(img_bgr, yolo_res):
    """Returnerar antal YOLO-personer som troligtvis bär uppvärmningsväst."""
    if yolo_res is None or yolo_res.boxes is None:
        return 0
    n = 0
    for box, cls in zip(yolo_res.boxes.xyxy, yolo_res.boxes.cls):
        if int(cls) == 0 and _person_har_vast(img_bgr, box.tolist()):
            n += 1
    return n


def _storsta_person(yolo_res):
    """Returnerar [x1,y1,x2,y2] för den största person-lådan, eller None."""
    if yolo_res is None or yolo_res.boxes is None:
        return None
    bast, area = None, 0
    for box, cls in zip(yolo_res.boxes.xyxy, yolo_res.boxes.cls):
        if int(cls) != 0:
            continue
        x1, y1, x2, y2 = box.tolist()
        a = (x2 - x1) * (y2 - y1)
        if a > area:
            area, bast = a, [x1, y1, x2, y2]
    return bast


def bakgrundskontrast(img_bgr, yolo_res):
    """
    Mäter hur väl huvudmotivet (största spelaren) sticker ut mot bakgrunden,
    i [0,1]. Hög = motivet har tydlig ljushets-/färgkontrast mot omgivningen.
    """
    box = _storsta_person(yolo_res)
    if box is None:
        return 0.0
    H, W = img_bgr.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(W, x2), min(H, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return 0.0
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    subj = gray[y1:y2, x1:x2]
    # Ring runt motivet (utvidgad låda minus motivet) = bakgrund
    mx = (x2 - x1) // 2
    my = (y2 - y1) // 2
    rx1, ry1 = max(0, x1 - mx), max(0, y1 - my)
    rx2, ry2 = min(W, x2 + mx), min(H, y2 + my)
    ring = gray[ry1:ry2, rx1:rx2].copy()
    inre = gray[y1:y2, x1:x2]
    # Ta bort motivet ur ringen genom att maskera
    ring_mask = np.ones((ry2 - ry1, rx2 - rx1), bool)
    ring_mask[y1 - ry1:y2 - ry1, x1 - rx1:x2 - rx1] = False
    bakgrund = gray[ry1:ry2, rx1:rx2][ring_mask]
    if bakgrund.size == 0 or subj.size == 0:
        return 0.0
    kontrast = abs(subj.mean() - bakgrund.mean()) / 255.0
    # Lägg till skillnad i textur (motiv skarpt mot suddig bakgrund)
    textur = abs(subj.std() - bakgrund.std()) / 128.0
    return float(np.clip(kontrast * 1.2 + textur * 0.4, 0.0, 1.0))


def keeper_finns(img_bgr, yolo_res, min_personer=4):
    """
    Heuristik: returnerar 1.0 om en spelare bär en tröjfärg som tydligt
    avviker från övriga (typiskt målvakten), annars 0.0. Kräver flera spelare.
    """
    if yolo_res is None or yolo_res.boxes is None:
        return 0.0
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H, W = img_bgr.shape[:2]
    huer = []
    for box, cls in zip(yolo_res.boxes.xyxy, yolo_res.boxes.cls):
        if int(cls) != 0:
            continue
        x1, y1, x2, y2 = (int(v) for v in box.tolist())
        h, w = y2 - y1, x2 - x1
        if h < 24 or w < 12:
            continue
        ty1, ty2 = y1 + h // 5, y1 + h * 11 // 20   # torso
        tx1, tx2 = max(0, x1), min(W, x2)
        torso = hsv[max(0, ty1):min(H, ty2), tx1:tx2]
        if torso.size == 0:
            continue
        # Dominerande mättad nyans i torson
        mattad = torso[(torso[:, :, 1] > 60) & (torso[:, :, 2] > 50)]
        if mattad.size < 30:
            continue
        huer.append(float(np.median(mattad[:, 0])))
    if len(huer) < min_personer:
        return 0.0
    huer = np.array(huer)
    median = np.median(huer)
    # En spelare vars nyans ligger >35° (av 180 i OpenCV) från medianen
    avvik = np.abs(((huer - median + 90) % 180) - 90)
    return 1.0 if (avvik > 35).sum() >= 1 and (avvik <= 35).sum() >= 3 else 0.0


def hemma_farg_andel(img_bgr, farg_namn):
    if farg_namn not in FARG_HSV:
        return 0.0
    lo, hi = [np.array(x, np.uint8) for x in FARG_HSV[farg_namn]]
    h = img_bgr.shape[0]
    roi = img_bgr[h // 3:, :]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    return mask.sum() / 255 / mask.size


def detektera_nummer(img_bgr, yolo_results, ocr, max_personer=5):
    """
    OCR:ar ENBART de största spelar-cropparna (närmast kameran → läsbara
    nummer; små/avlägsna spelare ger ändå inget). Returnerar mängden avlästa
    siffersträngar — parameter-oberoende, så den kan cachas och jämföras mot
    valfri bevakningslista i efterhand.

    (Apple Vision testades men läser tröjnummer för otillförlitligt — fel/del-
    siffror — så EasyOCR är kvar som enda motor.)
    """
    if ocr is None or yolo_results is None or yolo_results.boxes is None:
        return set()
    personer = []
    for box, cls in zip(yolo_results.boxes.xyxy, yolo_results.boxes.cls):
        if int(cls) != 0:   # klass 0 = person
            continue
        x1, y1, x2, y2 = map(int, box.tolist())
        personer.append(((x2 - x1) * (y2 - y1), x1, y1, x2, y2))
    personer.sort(reverse=True)   # störst (närmast) först

    nummer = set()
    for _, x1, y1, x2, y2 in personer[:max_personer]:
        if (x2 - x1) < 24 or (y2 - y1) < 48:   # för liten → oläsbart
            continue
        y_mid = y1 + (y2 - y1) * 2 // 3        # ryggnumret = övre 2/3
        crop = img_bgr[max(0, y1):y_mid, max(0, x1):x2]
        if crop.size == 0:
            continue
        for text in ocr.readtext(crop, allowlist="0123456789", detail=0):
            text = text.strip()
            if text:
                nummer.add(text)
    return nummer


# MediaPipe face-mesh-index för ögonkontakt (EAR + frontalitet)
_HÖGER_ÖGA = (33, 160, 158, 133, 153, 144)   # ytter, topp×2, inner, botten×2
_VÄNSTER_ÖGA = (362, 385, 387, 263, 373, 380)
_NÄSA = 1


def _ear(lm, idx):
    """Eye Aspect Ratio för ett öga givet sex landmärken."""
    def d(a, b):
        return ((lm[a].x - lm[b].x) ** 2 + (lm[a].y - lm[b].y) ** 2) ** 0.5
    p1, p2, p3, p4, p5, p6 = idx
    horis = d(p1, p4) + 1e-6
    return (d(p2, p6) + d(p3, p5)) / (2.0 * horis)


def ogonkontakt_score(face_result):
    """
    Andel ansikten med öppna ögon som tittar mot kameran, i [0,1].
    Öppet öga = EAR > 0.18; frontalt = näsan ungefär mittemellan ögonen.
    """
    ansikten = getattr(face_result, "face_landmarks", None) or []
    if not ansikten:
        return 0.0
    bra = 0
    for lm in ansikten:
        try:
            ear = (_ear(lm, _HÖGER_ÖGA) + _ear(lm, _VÄNSTER_ÖGA)) / 2.0
            oppna = ear > 0.18
            # Frontalitet: näsan mellan ögonens ytterkanter, symmetriskt.
            xh = lm[_HÖGER_ÖGA[0]].x
            xv = lm[_VÄNSTER_ÖGA[3]].x
            mitt = (xh + xv) / 2.0
            bredd = abs(xv - xh) + 1e-6
            frontal = abs(lm[_NÄSA].x - mitt) / bredd < 0.35
            if oppna and frontal:
                bra += 1
        except (IndexError, AttributeError):
            continue
    return bra / len(ansikten)


def _kör_face(args):
    """Kör face-landmark-detektion i en tråd med en dedikerad detektor."""
    img_bgr, face_detektor = args
    if face_detektor is None:
        return None
    import mediapipe as mp
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    return face_detektor.detect(mp_img)


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
         "klunga": 0.0, "personer": 0, "vast": 0, "bakgrund": 0.0,
         "keeper": 0.0, "_nummer": [], "_yolo": yolo_res}

    klasser = yolo_res.boxes.cls.tolist() if yolo_res.boxes else []
    b["boll"] = 0.08 if 32 in klasser else 0.0
    b["personer"] = sum(1 for c in klasser if int(c) == 0)

    # Firande: skalas med antal firande spelare (gruppfirande väger tyngst).
    n_fira = antal_firande(pose_res) if pose_res is not None else 0
    if n_fira >= 1:
        b["armar"] = min(0.15 + 0.05 * (n_fira - 1), 0.25)

    # Klunga förstärker ENDAST när det redan finns en firande-gest — annars
    # skulle vanlig spelarträngsel (hörnor, närkamper) också belönas.
    if n_fira >= 1:
        b["klunga"] = klunga_bonus(yolo_res)

    if hemma_farg:
        b["hemma"] = min(hemma_farg_andel(img_bgr, hemma_farg) * 2, 0.08)

    # OBS: tröjnummer-OCR görs INTE här utan i bonus_batch, begränsat till
    # topp-kandidaterna (OCR är dyrt och påverkar bara slututvalet).

    b["vast"] = vast_straff(img_bgr, yolo_res)
    b["bakgrund"] = bakgrundskontrast(img_bgr, yolo_res)
    b["keeper"] = keeper_finns(img_bgr, yolo_res)
    return b


def bonus_batch(imgs_bgr, resultat_refs, modeller, hemma_farg, bevaka,
                batch_storlek=16, progress_cb=None, clip_text=None, tider=None,
                ocr_max=60):
    """
    Kör YOLO i batch + parallell MediaPipe pose per bild.
    Skriver bonusar direkt in i resultat_refs-diktarna.
    clip_text: förberäknade CLIP-text-features (per sport) → semantiska features.
    tider:     valfri dict som fylls med sekunder per AI-delsteg (mätning).
    """
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from time import perf_counter

    t = {} if tider is None else tider

    def _tic(nyckel, t0):
        t[nyckel] = t.get(nyckel, 0.0) + (perf_counter() - t0)

    yolo = modeller["yolo"]
    if yolo is None:
        return
    device = modeller.get("device", "cpu")
    estetik = modeller.get("estetik")
    clip_pak = modeller.get("clip")
    ocr = modeller.get("ocr")
    ocr_klar = 0   # tröjnummer-OCR görs bara på de ocr_max första (bästa baspoäng)

    # Bygg en pool av pose-detektorer via en kö
    pose_pool = modeller.get("pose_pool", [])
    pose_kö = Queue()
    for d in pose_pool:
        pose_kö.put(d)

    # Pool av face-detektorer för ögonkontakt (om laddad)
    face_pool = modeller.get("face_pool", [])
    face_kö = Queue()
    for d in face_pool:
        face_kö.put(d)

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
            t0 = perf_counter()
            yolo_res_list = yolo(batch_imgs, verbose=False, device=device)
            _tic("AI:YOLO", t0)

            # Parallell pose (en tråd per bild, lånar detektor från kön)
            pose_results = [None] * len(batch_imgs)
            if pose_pool:
                t0 = perf_counter()
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
                _tic("AI:pose", t0)

            # Parallell face-mesh (ögonkontakt) om pool finns
            face_results = [None] * len(batch_imgs)
            if face_pool:
                t0 = perf_counter()
                def kör_en_face(idx_img):
                    idx, img = idx_img
                    det = face_kö.get()
                    try:
                        return idx, _kör_face((img, det))
                    finally:
                        face_kö.put(det)

                n_fw = min(len(face_pool), len(batch_imgs))
                with ThreadPoolExecutor(max_workers=n_fw) as ex:
                    for idx, res in ex.map(kör_en_face, enumerate(batch_imgs)):
                        face_results[idx] = res
                _tic("AI:face", t0)

            # NIMA för hela batchen i ett pass (faller tillbaka per bild vid fel).
            nima_vals = None
            if estetik is not None:
                t0 = perf_counter()
                try:
                    nima_vals = nima_poang_batch(batch_imgs, estetik, device)
                except Exception:
                    nima_vals = None
                _tic("AI:NIMA", t0)

            # CLIP zero-shot semantiska features för hela batchen.
            clip_vals = None
            if clip_pak is not None and clip_text is not None:
                t0 = perf_counter()
                try:
                    from cull.clip_lager import clip_features_batch
                    clip_vals = clip_features_batch(batch_imgs, clip_pak, clip_text)
                except Exception:
                    clip_vals = None
                _tic("AI:CLIP", t0)

            t0 = perf_counter()
            ocr_batch = 0.0   # OCR-tid i denna batch (dras av cv2/övrigt-bucketen)
            for i, (img, ref, yolo_res, pose_res, face_res) in enumerate(zip(
                    batch_imgs, batch_refs, yolo_res_list, pose_results,
                    face_results)):
                b = _bonus_fran_yolo(img, yolo_res, pose_res, modeller,
                                     hemma_farg, bevaka)
                b["ogonkontakt"] = (ogonkontakt_score(face_res)
                                    if face_res is not None else 0.0)
                ref.update(b)
                # Tröjnummer-OCR: bara på de bästa baspoängs-kandidaterna
                # (refs kommer i baspoängsordning). Dyrt → begränsat.
                if bevaka and ocr is not None and ocr_klar < ocr_max:
                    t_ocr = perf_counter()
                    nummer = detektera_nummer(img, yolo_res, ocr)
                    ref["_nummer"] = sorted(nummer)
                    ref["trojnummer"] = 0.12 if nummer & set(bevaka) else 0.0
                    ocr_klar += 1
                    ocr_batch += perf_counter() - t_ocr
                if estetik is not None:
                    if nima_vals is not None and i < len(nima_vals):
                        ref["nima"] = nima_vals[i]
                    else:
                        try:
                            ref["nima"] = nima_poang(img, estetik, device)
                        except Exception:
                            ref["nima"] = None
                if clip_vals is not None and i < len(clip_vals):
                    ref.update(clip_vals[i])
            # OCR har egen rad → exkludera den ur cv2/övrigt (ingen dubbelräkning).
            if ocr_batch:
                t["AI:OCR"] = t.get("AI:OCR", 0.0) + ocr_batch
            t["AI:cv2/övrigt"] = (t.get("AI:cv2/övrigt", 0.0)
                                  + (perf_counter() - t0) - ocr_batch)

            klar += len(batch_imgs)
            if progress_cb:
                progress_cb(klar, totalt)
