"""
Inlärning: tränar en personlig rankningsmodell på dina tidigare manuella val.

Två facit-källor stöds (auto-detekteras):

1. Export-layout (rekommenderas) — dina levererade/publicerade bilder, t.ex.
   ~/Dropbox/Export/Sport/2026/<match>/ med kameramappar (Z8, D5, …) som
   innehåller hela tagningen som JPG, och en "Instagram"-mapp med de publicerade
   bilderna. Filnamnen bär käll-frame-id (…__Z815976_NIKON…), så varje bild kan
   etiketteras publicerad (1) / ej (0).

2. FilterPix-layout — ".../<match>/FilterPix/Five Star/" med manuellt
   betygsatta NEF:er.

Features per bild = samma signaler som culling använder (skärpa, exponering,
ansikten, ögon, firande, klunga, boll, spelarantal, NIMA), normaliserade per
uppdrag (z-score). En klassbalanserad logistisk regression tränas.

  cull-lar "~/Dropbox/Export/Sport/2026"
  cull-lar "~/Dropbox/Export/Sport/2026" --rapport --max-neg 120

Modellen sparas i ~/.config/cull/modell.pkl och används automatiskt av cull.
"""

import argparse
import os
import pickle
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from cull import bas

MODELL_PATH = Path.home() / ".config" / "cull" / "modell.pkl"

# Kanonisk feature-ordning — måste vara identisk i träning och inferens.
FEATURES = ["skarpa", "exp", "ansikten", "ogon", "armar", "klunga",
            "boll", "personer", "nima"]

# Mappnamn som räknas som "publicerad/vald".
FACIT_MAPPAR = ("Instagram", "Five Star", "Four Star", "Selects",
                "Levererad", "Levererat")
# Mappnamn som inte är kandidatbilder.
EJ_KANDIDAT = ("Test", "Loggor")


def _frame_id(namn):
    """Käll-frame-id ur ett exportfilnamn, normaliserat (Z816551, D858711)."""
    m = re.match(r"^\d{12,14}_(.+?)_NIKON", namn)
    tok = m.group(1) if m else Path(namn).stem
    tok = re.split(r"-Redigera|-Edit", tok)[0]
    return tok.replace("_", "").upper()


def _ai(yolo_modell="yolo11s.pt"):
    from cull import ai_lager
    return ai_lager.ladda_modeller(yolo_modell=yolo_modell, med_estetik=True,
                                   n_pose=1)


# --- Facit-upptäckt -----------------------------------------------------------

def hitta_uppdrag_export(root):
    """
    Hittar export-uppdrag. Returnerar lista av
    (namn, [(jpg_path, label), …]) där label=1 för publicerade bilder.
    Kandidater = alla JPG i matchen (deduplicerade på frame-id).
    """
    root = Path(root)
    uppdrag = []
    for ig in root.rglob("Instagram"):
        if not ig.is_dir():
            continue
        match_dir = ig.parent
        vald_ids = {_frame_id(p.name) for p in ig.glob("*.jpg")
                    if not p.name.startswith(".")}
        if not vald_ids:
            continue
        kandidater = {}   # frame_id -> jpg path (en per id)
        for jpg in match_dir.rglob("*.jpg"):
            if jpg.name.startswith("."):
                continue
            if any(d in jpg.parts for d in EJ_KANDIDAT):
                continue
            kandidater.setdefault(_frame_id(jpg.name), jpg)
        if len(kandidater) < len(vald_ids) + 5:
            continue
        items = [(p, 1 if fid in vald_ids else 0)
                 for fid, p in kandidater.items()]
        uppdrag.append((match_dir.name, items))
    return uppdrag


def _nef_stems(mapp, rekursivt=False):
    it = mapp.rglob("*") if rekursivt else mapp.iterdir()
    return {p.stem for p in it
            if p.suffix.lower() == ".nef" and not p.name.startswith(".")}


def hitta_uppdrag_filterpix(root):
    """FilterPix-layout → samma format men med NEF-källor (kräver extraktion)."""
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
        for cam in sorted(match_dir.iterdir()):
            if not cam.is_dir() or cam.name == "FilterPix":
                continue
            if cam.name.startswith(".") or cam.name.lower().startswith("urval"):
                continue
            nefs = [p for p in cam.iterdir()
                    if p.suffix.lower() == ".nef" and not p.name.startswith(".")]
            if not ({p.stem for p in nefs} & vald):
                continue
            items = [(p, 1 if p.stem in vald else 0) for p in nefs]
            uppdrag.append((match_dir.name, items))
    return uppdrag


# --- Feature-extraktion -------------------------------------------------------

def ar_online_only(path):
    """
    True om filen bara finns i molnet (Dropbox/iCloud), inte lokalt.
    Online-only-filer har 0 allokerade block trots full logisk storlek —
    detekteras utan att trigga nedladdning.
    """
    try:
        st = path.stat()
        return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0
    except OSError:
        return True


def _las_bild(path, env):
    """Läser en JPG direkt, eller extraherar preview ur en NEF. BGR ≤1600px."""
    import cv2
    if path.suffix.lower() == ".nef":
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


def features_for_uppdrag(items, modeller, env, progress_namn=""):
    """items = [(path, label)]. Returnerar (X, y) med råa features."""
    import cv2
    from cull.ai_lager import _bonus_fran_yolo, _kör_pose, nima_poang
    yolo = modeller["yolo"]
    dev = modeller["device"]
    pose = modeller["pose_pool"][0] if modeller.get("pose_pool") else None
    nima = modeller.get("estetik")

    X, y = [], []
    n_online = [0]
    BATCH = 16
    for start in range(0, len(items), BATCH):
        del_items = items[start:start + BATCH]
        bilder, labels = [], []
        for path, lab in del_items:
            if ar_online_only(path):
                n_online[0] += 1
                continue
            img = _las_bild(path, env)
            if img is not None:
                bilder.append(img)
                labels.append(lab)
        if not bilder:
            continue
        yres_list = yolo(bilder, verbose=False, device=dev)
        for img, lab, yres in zip(bilder, labels, yres_list):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            n_ans, n_ogon = bas.ogon_ansikten(gray)
            pres = _kör_pose((img, pose)) if pose is not None else None
            b = _bonus_fran_yolo(img, yres, pres, modeller, None, set())
            nv = nima_poang(img, nima, dev) if nima is not None else 0.0
            rad = {"skarpa": bas.skarpa(gray), "exp": bas.exponering(gray),
                   "ansikten": n_ans, "ogon": n_ogon,
                   "armar": b["armar"], "klunga": b["klunga"], "boll": b["boll"],
                   "personer": b["personer"], "nima": nv}
            X.append([rad[k] for k in FEATURES])
            y.append(lab)
        print(f"    {progress_namn} …{min(start + BATCH, len(items))}/{len(items)}",
              flush=True)
    if n_online[0]:
        print(f"    ⚠ {n_online[0]}/{len(items)} bilder online-only (ej "
              f"nedladdade i Dropbox) — hoppade över.", flush=True)
    return np.array(X, float), np.array(y, int)


def _znorm(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-6] = 1.0
    return (X - mu) / sd


def _exiftool_env():
    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


# --- Träning ------------------------------------------------------------------

def traina(root, yolo_modell="yolo11s.pt", rapport=False,
           max_neg=150, max_uppdrag=None, kontroll_bara=False):
    uppdrag = hitta_uppdrag_export(root)
    kalla = "export (Instagram)"
    if not uppdrag:
        uppdrag = hitta_uppdrag_filterpix(root)
        kalla = "FilterPix"
    if not uppdrag:
        sys.exit(f"Hittade inga facit-uppdrag under {root}.")

    if max_uppdrag:
        uppdrag = uppdrag[:max_uppdrag]
    print(f"Hittade {len(uppdrag)} uppdrag ({kalla}).", flush=True)

    # Förkontroll: online-only-tillgänglighet per uppdrag (ingen nedladdning).
    tillg, helt_online = [], []
    for namn, items in uppdrag:
        n = len(items)
        n_online = sum(1 for p, _ in items if ar_online_only(p))
        if n_online == n:
            helt_online.append(namn)
        elif n_online > 0:
            tillg.append((namn, n - n_online, n))
    if helt_online:
        print(f"\n⚠ {len(helt_online)} uppdrag är HELT online-only och hoppas "
              f"över — gör dem offline i Dropbox för att inkludera dem:",
              flush=True)
        for namn in helt_online[:20]:
            print(f"    · {namn}", flush=True)
        if len(helt_online) > 20:
            print(f"    … och {len(helt_online) - 20} till", flush=True)
    if tillg:
        print(f"\n⚠ {len(tillg)} uppdrag delvis online-only "
              f"(bara lokala bilder används).", flush=True)
    n_anv = len(uppdrag) - len(helt_online)
    print(f"\n{n_anv}/{len(uppdrag)} uppdrag har lokala bilder att träna på.",
          flush=True)
    if kontroll_bara:
        return
    if n_anv == 0:
        sys.exit("Inga lokala bilder att träna på — gör Dropbox-mappar offline.")

    # Balansera: behåll alla positiva + slumpsample negativa per uppdrag.
    random.seed(0)
    for i, (namn, items) in enumerate(uppdrag):
        pos = [it for it in items if it[1] == 1]
        neg = [it for it in items if it[1] == 0]
        if max_neg and len(neg) > max_neg:
            neg = random.sample(neg, max_neg)
        uppdrag[i] = (namn, pos + neg)

    print("\nLaddar AI-modeller…", flush=True)
    modeller = _ai(yolo_modell)
    env = _exiftool_env()

    X_list, y_list = [], []
    for k, (namn, items) in enumerate(uppdrag, 1):
        n_pos = sum(l for _, l in items)
        print(f"\n[{k}/{len(uppdrag)}] {namn}  ({len(items)} bilder, "
              f"{n_pos} valda)…", flush=True)
        X, y = features_for_uppdrag(items, modeller, env, progress_namn=namn[:18])
        if len(X) == 0 or y.sum() == 0:
            continue
        X_list.append(_znorm(X))
        y_list.append(y)

    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    n_pos = int(y.sum())
    print(f"\nTräningsdata: {len(y)} bilder, {n_pos} valda "
          f"({n_pos / len(y) * 100:.1f}%) från {len(X_list)} uppdrag.",
          flush=True)

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    modell = LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)

    # Korsvalidering (om ≥3 uppdrag finns blir detta en ärlig generaliseringssiffra)
    try:
        auc_cv = cross_val_score(modell, X, y, cv=min(5, len(X_list)),
                                 scoring="roc_auc")
        print(f"Korsvaliderad AUC: {auc_cv.mean():.3f} ± {auc_cv.std():.3f}",
              flush=True)
    except Exception as e:
        print(f"(korsvalidering hoppades över: {e})", flush=True)

    modell.fit(X, y)
    coef = modell.coef_[0]
    print("\nVad styr dina val (vikt, + = väljer oftare):", flush=True)
    for namn, w in sorted(zip(FEATURES, coef), key=lambda t: -abs(t[1])):
        print(f"  {namn:<10} {w:+.2f}", flush=True)

    if rapport:
        print("\n(Rapportläge — ingen modell sparades.)")
        return

    MODELL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODELL_PATH, "wb") as f:
        pickle.dump({"modell": modell, "features": FEATURES,
                     "n_uppdrag": len(X_list), "n_valda": n_pos}, f)
    print(f"\nModell sparad: {MODELL_PATH}", flush=True)


def ladda_modell():
    try:
        with open(MODELL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def poangsatt_med_modell(resultat, paket):
    """Skriver r['poang'] för alla i resultat (z-normaliserat per uppdrag)."""
    feats = paket["features"]
    X = np.array([[float(r.get(k, 0.0)) for k in feats] for r in resultat])
    Xn = _znorm(X)
    proba = paket["modell"].predict_proba(Xn)[:, 1]
    for r, p in zip(resultat, proba):
        r["poang"] = float(p)


def main():
    ap = argparse.ArgumentParser(
        prog="cull-lar",
        description="Träna personlig rankningsmodell på dina levererade val.")
    ap.add_argument("root", help="rotkatalog (export- eller FilterPix-träd)")
    ap.add_argument("--yolo", default="yolo11s.pt", metavar="MODELL")
    ap.add_argument("--max-neg", type=int, default=150,
                    help="max antal ej-valda per uppdrag (balans/fart)")
    ap.add_argument("--max-uppdrag", type=int, default=None,
                    help="begränsa antal uppdrag (för test)")
    ap.add_argument("--rapport", action="store_true",
                    help="visa analys men spara ingen modell")
    ap.add_argument("--kolla", action="store_true",
                    help="visa bara online-only-status, träna inte")
    args = ap.parse_args()
    traina(Path(args.root).expanduser(), yolo_modell=args.yolo,
           rapport=args.rapport, max_neg=args.max_neg,
           max_uppdrag=args.max_uppdrag, kontroll_bara=args.kolla)


if __name__ == "__main__":
    main()
