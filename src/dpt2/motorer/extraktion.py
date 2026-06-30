"""Förenad feature-extraktion (KÄRNA) — EN väg som både gallring (cull) och
träning använder.

Gamla dpt hade TVÅ parallella extraktionsvägar som måste ge identiska värden:
träning (inlarning.features_for_uppdrag) och cull (ai_lager.bonus_batch). Här är
de förenade till `features_for_bilder` → producerar exakt `FEATURES`-vektorn.
Träning lägger bara på etiketter ovanpå; cull poängsätter X direkt.

FEATURES-ordningen är FRYST (beslut 3): den måste reproducera gamla vektorn
bit-för-bit så `modell.pkl` + facit + cacher förblir giltiga. Golden-test i
test_extraktion verifierar det mot facit_underlag på riktiga bilder.

Förbehandlingen (`_las_bild`: raw→exiftool-preview ≤1600px) är migrerad verbatim
ur inlarning — den är en del av kontraktet (annars skiljer pixlarna → vektorerna).
"""

import subprocess
import tempfile
from pathlib import Path

from dpt2.motorer import bas
from dpt2.motorer.clip_lager import CLIP_FEATURES
from dpt2.motorer.filtyper import RAW_SUFFIX
from dpt2.motorer.nummer import _env

# Det frysta FEATURES-kontraktet (14 klassiska/AI + CLIP). Ordningen är en
# del av cache-fingerprintet och modell.pkl — ändra ALDRIG utan omträning.
FEATURES = ["skarpa", "exp", "ansikten", "ogon", "armar", "klunga",
            "boll", "personer", "nima",
            "motljus", "rorelse", "bakgrund", "keeper", "ogonkontakt"
            ] + CLIP_FEATURES


def ar_online_only(path):
    """True om filen bara finns i molnet (Dropbox/iCloud), inte lokalt. Online-
    only-filer har 0 allokerade block trots full logisk storlek."""
    try:
        st = path.stat()
        return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0
    except OSError:
        return True


def _las_bild(path, env):
    """Läser en JPG direkt, eller extraherar preview ur en rawfil. BGR ≤1600px.
    Migrerad verbatim ur inlarning — del av extraktionskontraktet."""
    import cv2
    path = Path(path)
    if path.suffix.lower() in RAW_SUFFIX:
        with tempfile.TemporaryDirectory() as tmp:
            jpg = Path(tmp) / (path.stem + ".jpg")
            for tag in ("-JpgFromRaw", "-PreviewImage"):
                with open(jpg, "wb") as f:
                    subprocess.run(["exiftool", "-b", tag, str(path)],
                                   stdout=f, stderr=subprocess.DEVNULL, env=env)
                if jpg.exists() and jpg.stat().st_size > 10_000:
                    img = cv2.imread(str(jpg))
                    break
            else:
                return None
    else:
        img = cv2.imread(str(path))
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > 1600:
        s = 1600 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)))
    return img


def features_for_bilder(paths, modeller, *, env=None, sport=None,
                        estetik_motor="nima", progress=None):
    """paths = lista filsökvägar. Returnerar (X, stems): X = lista 19-feature-
    vektorer i FEATURES-ordning, stems = filstammar (online-only/oläsbara hoppas).

    modeller = ai_lager.ladda_modeller(...). EN extraktion: bas (skärpa/exp/ögon/
    motljus/rörelse) + ai_lager._bonus_fran_yolo (armar/klunga/boll/personer/
    bakgrund/keeper) + NIMA/Vision-estetik + ogonkontakt + CLIP. Spegel av gamla
    features_for_uppdrag (utan etiketter)."""
    import cv2
    from dpt2.motorer.ai_lager import (_bonus_fran_yolo, _kör_pose, _kör_face,
                                       ogonkontakt_score, nima_poang)
    from dpt2.motorer import clip_lager

    env = env or _env()
    yolo = modeller["yolo"]
    dev = modeller["device"]
    pose = modeller["pose_pool"][0] if modeller.get("pose_pool") else None
    face = modeller["face_pool"][0] if modeller.get("face_pool") else None
    nima = modeller.get("estetik")
    clip_pak = modeller.get("clip")
    clip_text = (clip_lager.bygg_text_features(clip_pak, sport)
                 if clip_pak is not None else None)

    X, stems = [], []
    BATCH = 16
    paths = list(paths)
    for start in range(0, len(paths), BATCH):
        del_paths = paths[start:start + BATCH]
        bilder, b_stems = [], []
        for path in del_paths:
            path = Path(path)
            if ar_online_only(path):
                continue
            img = _las_bild(path, env)
            if img is not None:
                bilder.append(img)
                b_stems.append(path.stem)
        if not bilder:
            continue
        yres_list = yolo(bilder, verbose=False, device=dev)
        clip_rows = None
        if clip_text is not None:
            try:
                clip_rows = clip_lager.clip_features_batch(bilder, clip_pak, clip_text)
            except Exception:
                clip_rows = None
        nima_vals = None
        if nima is not None:
            from dpt2.motorer.ai_lager import nima_poang_batch
            try:
                nima_vals = nima_poang_batch(bilder, nima, dev)
            except Exception:
                nima_vals = None
        for j, (img, stem, yres) in enumerate(zip(bilder, b_stems, yres_list)):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            n_ans, n_ogon = bas.ogon_ansikten(gray)
            pres = _kör_pose((img, pose)) if pose is not None else None
            fres = _kör_face((img, face)) if face is not None else None
            b = _bonus_fran_yolo(img, yres, pres, modeller, None, set())
            if estetik_motor == "vision":
                from dpt2.motorer import vision_lager
                sc = vision_lager.estetik_poang_bgr(img)
                nv = (sc[0] + 1.0) * 4.5 + 1.0 if sc is not None else 0.0
            elif nima_vals is not None and j < len(nima_vals):
                nv = nima_vals[j]
            else:
                nv = nima_poang(img, nima, dev) if nima is not None else 0.0
            rad = {k: 0.0 for k in FEATURES}
            rad.update({"skarpa": bas.skarpa(gray), "exp": bas.exponering(gray),
                        "ansikten": n_ans, "ogon": n_ogon,
                        "armar": b["armar"], "klunga": b["klunga"], "boll": b["boll"],
                        "personer": b["personer"], "nima": nv,
                        "motljus": bas.motljus(gray),
                        "rorelse": bas.rorelse_riktning(gray),
                        "bakgrund": b["bakgrund"], "keeper": b["keeper"],
                        "ogonkontakt": (ogonkontakt_score(fres)
                                        if fres is not None else 0.0)})
            if clip_rows is not None and j < len(clip_rows):
                rad.update(clip_rows[j])
            X.append([rad[k] for k in FEATURES])
            stems.append(stem)
        if progress:
            progress(min(start + BATCH, len(paths)), len(paths))
    return X, stems
