"""
Inlärning: tränar en personlig rankningsmodell på dina tidigare manuella val.

Facit hämtas från FilterPix-betygsmappar (t.ex. ".../FilterPix/Five Star/")
där varje NEF är en manuellt utvald bild. Käll-NEF:erna i samma uppdrag
etiketteras vald (1) / ej vald (0) via filnamn.

Features per bild = samma signaler som culling använder (skärpa, exponering,
ansikten, ögon, firande, klunga, boll, spelarantal, NIMA). De normaliseras
per uppdrag (z-score) så att olika matcher blir jämförbara, och en logistisk
regression tränas med klassbalansering.

  cull-lar "/Volumes/X10 Blue"            # träna på alla uppdrag under roten
  cull-lar "/Volumes/X10 Blue" --rapport  # visa bara analys, spara ingen modell

Modellen sparas i ~/.config/cull/modell.pkl och används automatiskt av cull
när den finns (om inte --ingen-modell anges).
"""

import argparse
import os
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from cull import bas

MODELL_PATH = Path.home() / ".config" / "cull" / "modell.pkl"

# Ordningen är kanonisk — måste vara identisk i träning och inferens.
FEATURES = ["skarpa", "exp", "ansikten", "ogon", "armar", "klunga",
            "boll", "personer", "nima"]

# Betygsmappar som räknas som "manuellt vald".
FACIT_MAPPAR = ("Five Star", "Four Star", "Selects", "Levererad", "Levererat")


def _exiftool_env():
    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def _nef_stems(mapp, rekursivt=False):
    it = mapp.rglob("*") if rekursivt else mapp.iterdir()
    return {p.stem for p in it
            if p.suffix.lower() == ".nef" and not p.name.startswith(".")}


def hitta_uppdrag(root):
    """
    Hittar uppdrag med facit. Returnerar lista av (källkatalog, vald_stems).
    Ett uppdrag = en mapp med en FilterPix-betygsmapp; källan är den
    kameramapp i uppdraget vars NEF:er matchar de valda filnamnen.
    """
    root = Path(root)
    uppdrag = []
    for fp in root.rglob("FilterPix"):
        if not fp.is_dir():
            continue
        match_dir = fp.parent
        vald = set()
        for niva in fp.iterdir():
            if niva.is_dir() and niva.name in FACIT_MAPPAR:
                vald |= _nef_stems(niva, rekursivt=True)
        if not vald:
            continue
        # Hitta kameramappen vars NEF-stammar överlappar de valda.
        for cam in sorted(match_dir.iterdir()):
            if not cam.is_dir() or cam.name == "FilterPix":
                continue
            if cam.name.startswith(".") or cam.name.lower().startswith("urval"):
                continue
            stems = _nef_stems(cam)
            if stems & vald:
                uppdrag.append((cam, vald))
    return uppdrag


def _ladda_ai(yolo_modell="yolo11s.pt"):
    from cull import ai_lager
    m = ai_lager.ladda_modeller(yolo_modell=yolo_modell, med_estetik=True,
                                n_pose=1)
    return m


def features_for_katalog(src_dir, vald_stems, modeller, progress=True):
    """
    Returnerar (X, y, stems): råa (onormaliserade) features, etiketter, namn.
    """
    from cull.ai_lager import _bonus_fran_yolo, _kör_pose, nima_poang
    yolo = modeller["yolo"]
    dev = modeller["device"]
    pose = modeller["pose_pool"][0] if modeller.get("pose_pool") else None
    nima = modeller.get("estetik")

    env = _exiftool_env()
    nefs = sorted(p for p in src_dir.iterdir()
                  if p.suffix.lower() == ".nef" and not p.name.startswith("."))

    X, y, stems = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i, nef in enumerate(nefs):
            jpg = Path(tmp) / (nef.stem + ".jpg")
            ok = False
            for tag in ("-JpgFromRaw", "-PreviewImage"):
                with open(jpg, "wb") as f:
                    subprocess.run(["exiftool", "-b", tag, str(nef)],
                                   stdout=f, stderr=subprocess.DEVNULL, env=env)
                if jpg.exists() and jpg.stat().st_size > 10_000:
                    ok = True
                    break
            if not ok:
                continue
            import cv2
            img = cv2.imread(str(jpg))
            if img is None:
                continue
            h, w = img.shape[:2]
            if max(h, w) > 1600:
                s = 1600 / max(h, w)
                img = cv2.resize(img, (int(w * s), int(h * s)))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            p = bas.poangsatt(jpg)
            if p is None:
                continue
            yres = yolo(img, verbose=False, device=dev)[0]
            pres = _kör_pose((img, pose)) if pose is not None else None
            b = _bonus_fran_yolo(img, yres, pres, modeller, None, set())
            nv = nima_poang(img, nima, dev) if nima is not None else 0.0
            rad = {
                "skarpa": p["skarpa"], "exp": p["exp"],
                "ansikten": p["ansikten"], "ogon": p["ogon"],
                "armar": b["armar"], "klunga": b["klunga"], "boll": b["boll"],
                "personer": b["personer"], "nima": nv,
            }
            X.append([rad[k] for k in FEATURES])
            y.append(1 if nef.stem in vald_stems else 0)
            stems.append(nef.stem)
            if progress and (i + 1) % 25 == 0:
                print(f"    …{i + 1}/{len(nefs)}", flush=True)
    return np.array(X, float), np.array(y, int), stems


def _znorm(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-6] = 1.0
    return (X - mu) / sd


def traina(root, yolo_modell="yolo11s.pt", rapport=False):
    uppdrag = hitta_uppdrag(root)
    if not uppdrag:
        sys.exit(f"Hittade inga FilterPix-facitmappar under {root}.")
    print(f"Hittade {len(uppdrag)} uppdrag med facit:", flush=True)
    for cam, vald in uppdrag:
        print(f"  • {cam.parent.name} ({len(vald)} valda)", flush=True)

    print("\nLaddar AI-modeller…", flush=True)
    modeller = _ladda_ai(yolo_modell)

    X_list, y_list = [], []
    for cam, vald in uppdrag:
        print(f"\nExtraherar features: {cam.parent.name}…", flush=True)
        X, y, _ = features_for_katalog(cam, vald, modeller)
        if len(X) == 0:
            continue
        X_list.append(_znorm(X))   # normalisera per uppdrag
        y_list.append(y)

    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    n_pos = int(y.sum())
    print(f"\nTräningsdata: {len(y)} bilder, {n_pos} valda "
          f"({n_pos / len(y) * 100:.1f}%).", flush=True)

    from sklearn.linear_model import LogisticRegression
    modell = LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)
    modell.fit(X, y)

    # Vilka features driver dina val? (koefficienter på z-normaliserad skala)
    coef = modell.coef_[0]
    print("\nVad styr dina val (vikt, + = väljer oftare):", flush=True)
    for namn, w in sorted(zip(FEATURES, coef), key=lambda t: -abs(t[1])):
        print(f"  {namn:<10} {w:+.2f}", flush=True)

    # In-sample-träffsäkerhet (vägledande — ej generalisering med få uppdrag).
    from sklearn.metrics import roc_auc_score
    try:
        auc = roc_auc_score(y, modell.predict_proba(X)[:, 1])
        print(f"\nIn-sample AUC: {auc:.3f}  "
              f"(1.0 = perfekt, 0.5 = slump)", flush=True)
    except Exception:
        pass

    if rapport:
        print("\n(Rapportläge — ingen modell sparades.)")
        return

    MODELL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODELL_PATH, "wb") as f:
        pickle.dump({"modell": modell, "features": FEATURES,
                     "n_uppdrag": len(uppdrag), "n_valda": n_pos}, f)
    print(f"\nModell sparad: {MODELL_PATH}", flush=True)
    if len(uppdrag) < 3:
        print("OBS: tränad på få uppdrag — lägg till fler FilterPix-urval "
              "för bättre generalisering.", flush=True)


def ladda_modell():
    try:
        with open(MODELL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def poangsatt_med_modell(resultat, paket):
    """
    Skriver r["poang"] för alla i resultat utifrån tränad modell.
    Förutsätter att varje r har alla FEATURES-nycklar.
    Normaliserar per uppdrag (z-score) precis som vid träning.
    """
    feats = paket["features"]
    modell = paket["modell"]
    X = np.array([[float(r.get(k, 0.0)) for k in feats] for r in resultat])
    Xn = _znorm(X)
    proba = modell.predict_proba(Xn)[:, 1]
    for r, p in zip(resultat, proba):
        r["poang"] = float(p)


def main():
    ap = argparse.ArgumentParser(
        prog="cull-lar",
        description="Träna en personlig rankningsmodell på dina FilterPix-val.")
    ap.add_argument("root", help="rotkatalog att söka uppdrag i")
    ap.add_argument("--yolo", default="yolo11s.pt", metavar="MODELL")
    ap.add_argument("--rapport", action="store_true",
                    help="visa analys men spara ingen modell")
    args = ap.parse_args()
    traina(Path(args.root).expanduser(), yolo_modell=args.yolo,
           rapport=args.rapport)


if __name__ == "__main__":
    main()
