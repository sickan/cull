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
import hashlib
import json
import os
import pickle
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime
import urllib.parse
import urllib.request
import warnings
from pathlib import Path

import numpy as np

# scikit-learn 1.8+ varnar om kommande API-byten (penalty/C_ → l1_ratios).
# Vi använder det stabila, äldre API:t medvetet — tysta övergångsbruset så
# träningsloggen förblir läsbar.
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

from cull import bas

MODELL_PATH = Path.home() / ".config" / "cull" / "modell.pkl"
# Modell-bibliotek: namngivna kopior (din_smak / arkiv) för modell-växlaren.
MODELLER_DIR = Path.home() / ".config" / "cull" / "modeller"
TRAIN_CACHE_DIR = Path.home() / ".cache" / "cull" / "train_features"
OKAND_PATH = Path.home() / ".cache" / "cull" / "sport_okand.json"
# Raw-format som extraheras via exiftool-preview (samma som core.RAW_SUFFIX).
_RAW_SUFFIX = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}

# Aktiv inlärning: användarens manuella behåll/förkasta-etiketter (stem → 0/1).
MANUELLA_PATH = Path.home() / ".config" / "cull" / "manuella_etiketter.json"

# Facit från Photo Mechanic-urval: cullen sparar feature-underlag per match
# (FACIT_UNDERLAG_DIR), "Lär av match" märker det med urvalet → FACIT_MARKT_DIR.
FACIT_UNDERLAG_DIR = Path.home() / ".config" / "cull" / "facit_underlag"
FACIT_MARKT_DIR = Path.home() / ".config" / "cull" / "facit_markt"


def hitta_uppdrag_markt():
    """Läser märkta facit-underlag (features redan extraherade av cullen, märkta
    med PM-urvalet). Returnerar [(namn, X, y, stems, sport)] med X i nuvarande
    FEATURES-ordning (namn-justerat så gamla underlag funkar när features växt)."""
    ut = []
    if not FACIT_MARKT_DIR.is_dir():
        return ut
    for f in sorted(FACIT_MARKT_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        gamla = d.get("features") or FEATURES
        idx = {namn: i for i, namn in enumerate(gamla)}
        rader = d.get("rader") or []
        stems, X, y = [], [], []
        for r in rader:
            v = r.get("v") or []
            vec = [float(v[idx[fn]]) if fn in idx and idx[fn] < len(v)
                   else 0.0 for fn in FEATURES]
            y_val = int(r.get("y", 0))
            # Vikt (levererat-nivån) realiseras som radupprepning → ingen
            # ändring i fit-signaturen; vikt 2 = två kopior. Bara positiva.
            rep = max(1, int(round(float(r.get("w", 1.0))))) if y_val == 1 else 1
            for _ in range(rep):
                X.append(vec)
                y.append(y_val)
                stems.append(r.get("stem", ""))
        if not X or sum(y) == 0:
            continue
        ut.append((d.get("match") or f.stem, np.array(X, dtype=float),
                   np.array(y, dtype=int), stems, (d.get("sport") or "").lower()))
    return ut


def ladda_manuella_etiketter():
    try:
        return json.loads(MANUELLA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def spara_manuell_etikett(stem, behall):
    """Sparar en manuell etikett (behall=True/False) för en bilds stem."""
    et = ladda_manuella_etiketter()
    et[stem] = 1 if behall else 0
    MANUELLA_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUELLA_PATH.write_text(json.dumps(et, ensure_ascii=False, indent=2),
                             encoding="utf-8")


# Parvisa preferenser (vinnare slår förlorare) för learning-to-rank.
PAR_PATH = Path.home() / ".config" / "cull" / "par_etiketter.json"


def ladda_par():
    try:
        return json.loads(PAR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def spara_par(vinnare_stem, forlorare_stem):
    """Loggar att vinnare_stem föredrogs framför forlorare_stem."""
    if vinnare_stem == forlorare_stem:
        return
    par = ladda_par()
    par.append([vinnare_stem, forlorare_stem])
    par = par[-2000:]
    PAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAR_PATH.write_text(json.dumps(par, ensure_ascii=False), encoding="utf-8")


def _applicera_manuella(uppdrag):
    """Skriver över etiketter i uppdrag med användarens manuella val (stem-match)."""
    et = ladda_manuella_etiketter()
    if not et:
        return 0
    n = 0
    for i, (namn, items) in enumerate(uppdrag):
        nya = []
        for path, lab in items:
            ny_lab = et.get(Path(path).stem, lab)
            if ny_lab != lab:
                n += 1
            nya.append((path, ny_lab))
        uppdrag[i] = (namn, nya)
    return n

# Kanonisk feature-ordning — måste vara identisk i träning och inferens.
# Nya features läggs ALLTID sist (annars feltolkas sparade modeller).
from cull.clip_lager import CLIP_FEATURES
FEATURES = ["skarpa", "exp", "ansikten", "ogon", "armar", "klunga",
            "boll", "personer", "nima",
            "motljus", "rorelse", "bakgrund", "keeper", "ogonkontakt"
            ] + CLIP_FEATURES

# Mappnamn som räknas som "publicerad/vald".
FACIT_MAPPAR = ("Instagram", "Five Star", "Four Star", "Selects",
                "Levererad", "Levererat")
# Mappnamn som inte är kandidatbilder.
EJ_KANDIDAT = ("Test", "Loggor")


_SPORT_NYCKELORD = {
    "handboll":  [" hk", "hk ", " hf", "hf ", "handboll", "handball",
                  " rk ", "nexe", "lugi", "kristianstad", "varberg hk",
                  "kungälv", "sävehof", "höör", "skövde hf", "redbergslid",
                  "ystads if", "alingsås", "boden handboll", "önnereds",
                  " ifk göteborg h", "rimbo", "spårvägen", "hammarby if hf",
                  "heim", "flensburg", "kiel", "barcelona hand", "paris hand"],
    "fotboll":   [" ff", "dff", " fc", "fotboll", "soccer", " mff", "allsvenskan",
                  "superettan", "damallsvenskan", " bk ", "fotbolls",
                  " aik", " djurgård", " hammarby if", " ifk göteborg ",
                  " ifk norrköping", " häcken", "brommapojkarna", " bp "],
    "volleyboll": [" vk", "volleyboll", "volleyball"],
    "innebandy": ["ibk", "innebandy", "floorball", " fbc", "fbk"],
}

_SPORT_WEBB_CACHE_PATH = Path.home() / ".cache" / "cull" / "sport_cache.json"

# Webb-nyckelord per sport (engelska + svenska, söks i DuckDuckGo-svar)
_SPORT_WEBB_NYCKELORD = {
    "handboll":  ["handball", "handboll", "handbollsförbundet", "ehf", "shf"],
    "fotboll":   ["football", "fotboll", "soccer", "fifa", "uefa", "allsvenskan",
                  "superettan", "damallsvenskan", "svff"],
    "volleyboll": ["volleyball", "volleyboll", "cev", "svbf"],
    "innebandy": ["floorball", "innebandy", "ibf", "innebandyförbundet"],
}


def _ladda_sport_webb_cache():
    try:
        return json.loads(_SPORT_WEBB_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _spara_sport_webb_cache(cache):
    _SPORT_WEBB_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SPORT_WEBB_CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _läs_bild_för_sport(path, env):
    """Läser en bild för sportanalys — JPG direkt, NEF via ThumbnailImage (snabb)."""
    import cv2
    if path.suffix.lower() in (".jpg", ".jpeg"):
        img = cv2.imread(str(path))
        return img
    # NEF: extrahera liten thumbnail (ThumbnailImage ~160px, snabb)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        tmp = Path(f.name)
    try:
        for tag in ("-ThumbnailImage", "-PreviewImage"):
            with open(tmp, "wb") as f:
                subprocess.run(["exiftool", "-b", tag, str(path)],
                               stdout=f, stderr=subprocess.DEVNULL, env=env)
            if tmp.exists() and tmp.stat().st_size > 2_000:
                img = cv2.imread(str(tmp))
                if img is not None:
                    return img
    finally:
        tmp.unlink(missing_ok=True)
    return None


def _sport_via_bilder(items, n=6, env=None):
    """
    Stickprov på n bilder. Mäter grön-andel (fotboll/gräs) och
    trä/parkett-toner (inomhussport). Returnerar sport-sträng eller None.
    """
    import cv2
    if env is None:
        env = os.environ.copy()
        for p in ("/opt/homebrew/bin", "/usr/local/bin"):
            if p not in env.get("PATH", "").split(os.pathsep):
                env["PATH"] = p + os.pathsep + env.get("PATH", "")

    prov = random.sample(items, min(n, len(items)))
    grön, inomhus = [], []
    for path, _ in prov:
        if ar_online_only(path):
            continue
        img = _läs_bild_för_sport(Path(path), env)
        if img is None:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Grönt: H=36–86, S>40, V>40 → gräs/utomhus
        mask_grön = cv2.inRange(hsv, (36, 40, 40), (86, 255, 255))
        andel_g = float(mask_grön.sum()) / mask_grön.size
        grön.append(andel_g)
        # Inomhus-indikator: låg mättnad + värde i mitten (hallbelysning)
        s_kanal = hsv[:, :, 1].mean() / 255.0
        v_kanal = hsv[:, :, 2].mean() / 255.0
        inomhus.append(s_kanal < 0.25 and 0.3 < v_kanal < 0.85)

    if not grön:
        return None
    if sum(grön) / len(grön) > 0.15:
        return "fotboll"
    if sum(inomhus) / len(inomhus) > 0.5:
        return "inomhus"   # handboll/volleyboll/innebandy — kan ej skilja på färg
    return None


def _sport_via_webb(namn, timeout=6):
    """DuckDuckGo Instant Answer — returnerar sport eller None. Resultat cachas."""
    cache = _ladda_sport_webb_cache()
    if namn in cache:
        return cache[namn] or None

    # Rensa bort prefix (H)/(D), resultat och datum ur katalognamnet
    fraga = re.sub(r"^\([A-Z]+\)\s*", "", namn)
    fraga = re.sub(r"\s+\d+-\d+\s*", " ", fraga)
    fraga = re.sub(r"\s+\d{8}$", "", fraga).strip()
    # Lägg till "sport" för att styra sökmotorn mot idrottsresultat
    fraga = fraga + " sport match"
    url = ("https://api.duckduckgo.com/?q="
           + urllib.parse.quote(fraga)
           + "&format=json&no_html=1&skip_disambig=1")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cull/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = " ".join([
            data.get("AbstractText", ""),
            data.get("Answer", ""),
            " ".join(t.get("Text", "") for t in data.get("RelatedTopics", [])[:8]),
        ]).lower()
        for sport, nyckelord in _SPORT_WEBB_NYCKELORD.items():
            if any(k in text for k in nyckelord):
                cache[namn] = sport
                _spara_sport_webb_cache(cache)
                return sport
    except Exception:
        pass
    cache[namn] = ""   # misslyckades — spara tomt för att inte fråga igen
    _spara_sport_webb_cache(cache)
    return None


def detektera_sport(namn, items=None, webb=True, env=None):
    """
    Detekterar sport via röstning bland fyra metoder.
    Returnerar 'handboll', 'fotboll', 'volleyboll', 'innebandy' eller 'okänd'.
    """
    röster = {}   # sport -> poäng

    def rösta(sport, poäng):
        if sport and sport != "inomhus":
            röster[sport] = röster.get(sport, 0) + poäng

    low = namn.lower()

    # 1. Nyckelord i namn (stark signal, 3p)
    for sport, nyckelord in _SPORT_NYCKELORD.items():
        if any(k in low for k in nyckelord):
            rösta(sport, 3)
            break

    # 2. Resultat i matchnamnet: >25 → aldrig fotboll (2p); ≤6 → troligt fotboll (1p)
    for a, b in re.findall(r"\b(\d+)-(\d+)\b", namn):
        if int(a) > 25 or int(b) > 25:
            rösta("handboll", 2)
            break
        if int(a) <= 6 and int(b) <= 6:
            rösta("fotboll", 1)
            break

    # 3. Bildanalys på stickprov (1p för fotboll, 1p mot fotboll vid inomhus)
    if items:
        bild_sport = _sport_via_bilder(items, env=env)
        if bild_sport == "fotboll":
            rösta("fotboll", 1)
        elif bild_sport == "inomhus":
            # Inte fotboll — stärk vinnaren bland nyckelords-/resultatrösterna
            for s in list(röster):
                if s != "fotboll":
                    röster[s] = röster.get(s, 0) + 1

    # 4. Webbaserad sökning (cachas, 2p)
    if webb:
        webb_sport = _sport_via_webb(namn)
        rösta(webb_sport, 2)

    if not röster:
        return "okänd"
    bäst = max(röster, key=röster.get)
    # Kräv minst 2p för att inte gissa på en enda svag signal
    return bäst if röster[bäst] >= 2 else "okänd"


def _frame_id(namn):
    """Käll-frame-id ur ett exportfilnamn, normaliserat (Z816551, D858711)."""
    m = re.match(r"^\d{12,14}_(.+?)_NIKON", namn)
    tok = m.group(1) if m else Path(namn).stem
    tok = re.split(r"-Redigera|-Edit", tok)[0]
    return tok.replace("_", "").upper()


def _ai(yolo_modell="yolo11s.pt", estetik_motor="nima"):
    from cull import ai_lager
    # Vision-motorn behöver ingen pyiqa-modell (estetik räknas ur bilderna).
    return ai_lager.ladda_modeller(yolo_modell=yolo_modell,
                                   med_estetik=(estetik_motor != "vision"),
                                   med_ogon=True, med_clip=True, n_pose=1)


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
            if p.suffix.lower() in _RAW_SUFFIX and not p.name.startswith(".")}


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
                    if p.suffix.lower() in _RAW_SUFFIX and not p.name.startswith(".")]
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
    """Läser en JPG direkt, eller extraherar preview ur en rawfil. BGR ≤1600px."""
    import cv2
    if path.suffix.lower() in _RAW_SUFFIX:
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


def features_for_uppdrag(items, modeller, env, progress_namn="", sport=None,
                         estetik_motor="nima"):
    """items = [(path, label)]. Returnerar (X, y, stems) med råa features."""
    import cv2
    from cull.ai_lager import (_bonus_fran_yolo, _kör_pose, _kör_face,
                               ogonkontakt_score, nima_poang)
    yolo = modeller["yolo"]
    dev = modeller["device"]
    pose = modeller["pose_pool"][0] if modeller.get("pose_pool") else None
    face = modeller["face_pool"][0] if modeller.get("face_pool") else None
    nima = modeller.get("estetik")
    clip_pak = modeller.get("clip")
    clip_text = None
    if clip_pak is not None:
        from cull import clip_lager
        clip_text = clip_lager.bygg_text_features(clip_pak, sport)

    X, y = [], []
    n_online = [0]
    BATCH = 16
    stems = []
    for start in range(0, len(items), BATCH):
        del_items = items[start:start + BATCH]
        bilder, labels, b_stems = [], [], []
        for path, lab in del_items:
            if ar_online_only(path):
                n_online[0] += 1
                continue
            img = _las_bild(path, env)
            if img is not None:
                bilder.append(img)
                labels.append(lab)
                b_stems.append(Path(path).stem)
        if not bilder:
            continue
        yres_list = yolo(bilder, verbose=False, device=dev)
        clip_rows = None
        if clip_text is not None:
            from cull.clip_lager import clip_features_batch, CLIP_FEATURES
            try:
                clip_rows = clip_features_batch(bilder, clip_pak, clip_text)
            except Exception:
                clip_rows = None
        # NIMA batchat på MPS (ett pass per batch) istället för per bild.
        nima_vals = None
        if nima is not None:
            from cull.ai_lager import nima_poang_batch
            try:
                nima_vals = nima_poang_batch(bilder, nima, dev)
            except Exception:
                nima_vals = None
        for j, (img, lab, stem, yres) in enumerate(
                zip(bilder, labels, b_stems, yres_list)):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            n_ans, n_ogon = bas.ogon_ansikten(gray)
            pres = _kör_pose((img, pose)) if pose is not None else None
            fres = _kör_face((img, face)) if face is not None else None
            b = _bonus_fran_yolo(img, yres, pres, modeller, None, set())
            if estetik_motor == "vision":
                from cull import vision_lager
                sc = vision_lager.estetik_poang_bgr(img)
                nv = (sc[0] + 1.0) * 4.5 + 1.0 if sc is not None else 0.0
            elif nima_vals is not None and j < len(nima_vals):
                nv = nima_vals[j]
            else:
                nv = nima_poang(img, nima, dev) if nima is not None else 0.0
            rad = {k: 0.0 for k in FEATURES}   # defaults (CLIP m.fl.)
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
            y.append(lab)
            stems.append(stem)
        print(f"    {progress_namn} …{min(start + BATCH, len(items))}/{len(items)}",
              flush=True)
    if n_online[0]:
        print(f"    ⚠ {n_online[0]}/{len(items)} bilder online-only (ej "
              f"nedladdade i Dropbox) — hoppade över.", flush=True)
    return np.array(X, float), np.array(y, int), np.array(stems, dtype=object)


def _shoot_fingerprint(namn, items, estetik_motor="nima"):
    """SHA1-fingeravtryck av exakt de filer som ska extraheras.
    Inkluderar FEATURES-uppsättningen + estetikmotorn så att cachen
    ogiltigförklaras när features ändras eller motorn byts (nima vs vision)."""
    h = hashlib.sha1()
    h.update(("|".join(FEATURES)).encode())   # cache-version = feature-set
    h.update(f"est:{estetik_motor}".encode())
    h.update(namn.encode())
    for path, lab in sorted(items, key=lambda t: str(t[0])):
        # Storlek istället för mtime → cachen överlever Dropbox-omsynk
        # (mtime ändras vid av-/återhydrering, men storleken är stabil).
        try:
            storlek = path.stat().st_size
        except OSError:
            storlek = 0
        h.update(f"{path}|{storlek}|{lab}".encode())
    return h.hexdigest()[:16]


def _ladda_från_cache(fingerprint):
    f = TRAIN_CACHE_DIR / f"{fingerprint}.npz"
    if not f.exists():
        return None
    try:
        d = np.load(f, allow_pickle=True)
        stems = d["stems"] if "stems" in d.files else np.array([], dtype=object)
        return d["X"], d["y"], stems
    except Exception:
        return None


def _ladda_cache_via_stems(items):
    """Fallback när fingerprint missar fastän features finns cachade — t.ex. när
    källfilerna blivit online-only (Dropbox/iCloud): stat-storleken blir 0 →
    annan fingerprint, OCH bilderna går inte att läsa om. Hittar i stället en
    cachad npz vars stems matchar uppdraget (innehållsidentitet, överlever både
    mtime- och storleksändringar) och återanvänder dess features. Etiketterna
    sätts om från items (Instagram-facit är stabil)."""
    want = {Path(p).stem: int(lab) for p, lab in items}
    if not want:
        return None
    bäst_X = bäst_stems = None
    bäst_ov = 0
    for f in TRAIN_CACHE_DIR.glob("*.npz"):
        try:
            d = np.load(f, allow_pickle=True)
            stems = [str(s) for s in d["stems"]]
        except Exception:
            continue
        if len(stems) < 30:
            continue
        ov = sum(1 for s in stems if s in want)
        if ov > bäst_ov and ov >= 0.95 * len(stems):
            bäst_X, bäst_stems, bäst_ov = d["X"], stems, ov
    if bäst_X is None:
        return None
    y = np.array([want.get(s, 0) for s in bäst_stems], dtype=int)
    if y.sum() == 0:
        return None
    return bäst_X, y, np.array(bäst_stems, dtype=object)


def _spara_i_cache(fingerprint, X, y, stems=None):
    TRAIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if stems is None:
        stems = np.array([], dtype=object)
    np.savez_compressed(TRAIN_CACHE_DIR / f"{fingerprint}.npz",
                        X=X, y=y, stems=stems)


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
           max_neg=150, max_uppdrag=None, kontroll_bara=False,
           limpa_cache=False, estetik_motor="nima", bara_markt=False):
    if limpa_cache:
        import shutil
        if TRAIN_CACHE_DIR.exists():
            shutil.rmtree(TRAIN_CACHE_DIR)
            print(f"Cache rensad: {TRAIN_CACHE_DIR}", flush=True)
        else:
            print("Ingen cache att rensa.", flush=True)
        return

    # bara_markt = "din smak"-modell: enbart dina egna märkta matcher (Lär av
    # match), oblandat med arkivets Instagram/FilterPix-facit.
    if bara_markt:
        uppdrag, kalla = [], "din smak (märkta matcher)"
    else:
        uppdrag = hitta_uppdrag_export(root)
        kalla = "export (Instagram)"
        if not uppdrag:
            uppdrag = hitta_uppdrag_filterpix(root)
            kalla = "FilterPix"
    markta = hitta_uppdrag_markt()   # PM-urval (features redan extraherade)
    if markta:
        n_match = len({u[0] for u in markta})
        print(f"Lär av match: {len(markta)} märkta underlag "
              f"({n_match} matcher).", flush=True)
        if bara_markt and n_match < 3:
            print(f"⚠ Bara {n_match} match(er) i din-smak-läget — modellen blir "
                  "svag/överanpassad. Mata in fler matcher för en stabil modell.",
                  flush=True)
    if not uppdrag and not markta:
        sys.exit(f"Hittade inga facit-uppdrag under {root} och inga märkta "
                 "PM-underlag (kör en cull → 'Lär av match').")

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
    if n_anv == 0 and not markta:
        sys.exit("Inga lokala bilder att träna på — gör Dropbox-mappar offline.")

    # Aktiv inlärning: lägg på användarens manuella behåll/förkasta-etiketter.
    n_man = _applicera_manuella(uppdrag)
    if n_man:
        print(f"\nAktiv inlärning: {n_man} manuella etiketter tillämpade.",
              flush=True)

    # Balansera: behåll alla positiva + slumpsample negativa per uppdrag.
    random.seed(0)
    for i, (namn, items) in enumerate(uppdrag):
        pos = [it for it in items if it[1] == 1]
        neg = [it for it in items if it[1] == 0]
        if max_neg and len(neg) > max_neg:
            neg = random.sample(neg, max_neg)
        uppdrag[i] = (namn, pos + neg)

    # Kolla vilka uppdrag som behöver extraheras (cache-miss).
    fingerprints = {namn: _shoot_fingerprint(namn, items, estetik_motor)
                    for namn, items in uppdrag}
    n_miss = sum(1 for namn, _ in uppdrag
                 if namn not in helt_online
                 and _ladda_från_cache(fingerprints[namn]) is None)
    n_cache_hit = n_anv - n_miss

    if n_cache_hit > 0:
        print(f"\n{n_cache_hit} uppdrag laddas från cache, "
              f"{n_miss} extraheras.", flush=True)

    modeller = None
    env = _exiftool_env()

    # Samla features per uppdrag, märkt med sport.
    X_list, y_list, sport_list = [], [], []
    stem_feat = {}        # stem -> rå feature-vektor (för parvis rankning)
    okanda_uppdrag = []   # namn på uppdrag där sport inte kunde fastställas
    k = 0
    for namn, items in uppdrag:
        if namn in helt_online:
            continue
        k += 1
        fp = fingerprints[namn]
        cached = _ladda_från_cache(fp)
        via_stems = False
        if cached is None:
            cached = _ladda_cache_via_stems(items)   # online-only-fallback
            via_stems = cached is not None
        if cached is not None:
            X, y, stems = cached
            n_pos = int(y.sum())
            sport = detektera_sport(namn, items=items, env=env)
            print(f"[{k}/{n_anv}] {namn}  (cache{'/stems' if via_stems else ''}, "
                  f"{len(y)} bilder, {n_pos} valda, {sport})", flush=True)
        else:
            if modeller is None:
                print("\nLaddar AI-modeller…", flush=True)
                modeller = _ai(yolo_modell, estetik_motor)
            n_pos = sum(l for _, l in items)
            sport = detektera_sport(namn, items=items, env=env)
            print(f"\n[{k}/{n_anv}] {namn}  ({len(items)} bilder, "
                  f"{n_pos} valda, {sport})…", flush=True)
            X, y, stems = features_for_uppdrag(items, modeller, env,
                                               progress_namn=namn[:18],
                                               sport=sport,
                                               estetik_motor=estetik_motor)
            if len(X) > 0 and y.sum() > 0:
                _spara_i_cache(fp, X, y, stems)
        if len(X) == 0 or y.sum() == 0:
            continue
        if sport == "okänd":
            try:
                sökväg = os.path.commonpath([str(p) for p, _ in items])
                if Path(sökväg).is_file():
                    sökväg = str(Path(sökväg).parent)
            except Exception:
                sökväg = ""
            okanda_uppdrag.append({"namn": namn, "path": sökväg})
        for st, rad in zip(stems, X):
            stem_feat[str(st)] = rad
        X_list.append(_znorm(X))
        y_list.append(y)
        sport_list.append(sport)

    # Märkta PM-underlag: features redan extraherade av cullen → läggs på direkt
    # (samma per-uppdrag z-norm + sporthantering som de bild-extraherade).
    for namn, X, y, stems, sport in markta:
        if len(X) == 0 or y.sum() == 0:
            continue
        sport = sport or "okänd"
        for st, rad in zip(stems, X):
            stem_feat[str(st)] = rad
        X_list.append(_znorm(X))
        y_list.append(y)
        sport_list.append(sport)
        print(f"[PM] {namn}  ({len(y)} bilder, {int(y.sum())} valda, {sport})",
              flush=True)

    if not X_list:
        sys.exit("Inga användbara träningsuppdrag (tomma efter filtrering).")
    X_all = np.vstack(X_list)
    y_all = np.concatenate(y_list)
    n_pos = int(y_all.sum())
    print(f"\nTräningsdata: {len(y_all)} bilder, {n_pos} valda "
          f"({n_pos / len(y_all) * 100:.1f}%) från {len(X_list)} uppdrag.",
          flush=True)

    from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
    from sklearn.model_selection import cross_val_score

    # L1-straff (liblinear) korsvaliderar C och nollställer brusiga features
    # → automatisk feature-gallring. Faller tillbaka på enkel L2 om data är tunt.
    _Cs = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]

    def _ny_modell(n_folds, n_pos):
        if n_folds >= 3 and n_pos >= n_folds:
            return LogisticRegressionCV(
                Cs=_Cs, cv=n_folds, scoring="roc_auc", penalty="l1",
                solver="liblinear", class_weight="balanced", max_iter=2000)
        return LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0)

    def _träna_en(X, y, X_per_uppdrag, etikett=""):
        n_folds = min(5, len(X_per_uppdrag))
        n_pos = int(y.sum())
        try:
            # Nästlad CV: yttre veck skattar AUC, inre väljer C → ärlig siffra.
            auc_cv = cross_val_score(_ny_modell(n_folds, n_pos), X, y,
                                     cv=n_folds, scoring="roc_auc")
            print(f"  AUC: {auc_cv.mean():.3f} ± {auc_cv.std():.3f}", flush=True)
        except Exception as e:
            print(f"  (korsvalidering hoppades över: {e})", flush=True)
        lr = _ny_modell(n_folds, n_pos)
        lr.fit(X, y)
        valt_C = getattr(lr, "C_", None)
        if valt_C is not None:
            print(f"  Valt C: {float(valt_C[0]):.3g}", flush=True)
        coef = lr.coef_[0]
        n_noll = int((coef == 0).sum())
        print(f"  Vad styr {etikett or 'valen'} (+ = väljer oftare"
              f"{', ' + str(n_noll) + ' bortgallrade' if n_noll else ''}):",
              flush=True)
        for fn, w in sorted(zip(FEATURES, coef), key=lambda t: -abs(t[1])):
            märke = "  (gallrad)" if w == 0 else ""
            print(f"    {fn:<11} {w:+.2f}{märke}", flush=True)
        return lr

    # Kombinerad modell
    print("\n=== Kombinerad modell ===", flush=True)
    modell = _träna_en(X_all, y_all, X_list)

    # Per-sport-modeller (minst 5 uppdrag krävs, "okänd" exkluderas)
    sport_modeller = {}
    sporters = sorted(s for s in set(sport_list) if s != "okänd")
    for sport in sporters:
        idx = [i for i, s in enumerate(sport_list) if s == sport]
        if len(idx) < 5:
            print(f"\n(Hoppar {sport}: bara {len(idx)} uppdrag, ≥5 krävs)",
                  flush=True)
            continue
        Xs = np.vstack([X_list[i] for i in idx])
        ys = np.concatenate([y_list[i] for i in idx])
        Xs_per = [X_list[i] for i in idx]
        print(f"\n=== {sport.capitalize()} ({len(idx)} uppdrag) ===", flush=True)
        sport_modeller[sport] = _träna_en(Xs, ys, Xs_per, sport)

    # Parvis rankningsmodell (learning-to-rank) från "Jämför par"-data.
    # Tränas på feature-skillnader vinnare−förlorare (RankNet-logistik utan
    # intercept). Aktiveras först när tillräckligt många par finns.
    rank_modell = None
    par = ladda_par()
    giltiga_par = [(v, f) for v, f in par
                   if str(v) in stem_feat and str(f) in stem_feat]
    PAR_TRÖSKEL = 25
    if par:
        print(f"\n=== Parvis rankning ===", flush=True)
        print(f"  {len(par)} par loggade, {len(giltiga_par)} kopplade till "
              f"träningsbilder.", flush=True)
    if len(giltiga_par) >= PAR_TRÖSKEL:
        # Global z-norm så ranker och features är jämförbara.
        mu = X_all.mean(axis=0); sd = X_all.std(axis=0); sd[sd < 1e-6] = 1.0
        Xd, yd = [], []
        for v, f in giltiga_par:
            dv = (np.asarray(stem_feat[str(v)], float) - mu) / sd
            df = (np.asarray(stem_feat[str(f)], float) - mu) / sd
            diff = dv - df
            Xd.append(diff);  yd.append(1)        # vinnare > förlorare
            Xd.append(-diff); yd.append(0)        # symmetriskt motexempel
        Xd, yd = np.array(Xd), np.array(yd)
        rl = LogisticRegression(fit_intercept=False, max_iter=2000, C=1.0)
        try:
            acc = cross_val_score(rl, Xd, yd, cv=min(5, len(giltiga_par)),
                                  scoring="accuracy").mean()
            print(f"  Parvis träffsäkerhet (CV): {acc:.0%}", flush=True)
        except Exception as e:
            print(f"  (CV hoppades över: {e})", flush=True)
        rl.fit(Xd, yd)
        print(f"  Vad avgör vilken bild som föredras:", flush=True)
        for fn, w in sorted(zip(FEATURES, rl.coef_[0]), key=lambda t: -abs(t[1])):
            print(f"    {fn:<11} {w:+.2f}", flush=True)
        rank_modell = {"coef": rl.coef_[0], "mu": mu, "sd": sd,
                       "features": FEATURES, "n_par": len(giltiga_par)}
    elif giltiga_par:
        print(f"  (≥{PAR_TRÖSKEL} kopplade par krävs för rankningsmodell — "
              f"styr urvalet först då.)", flush=True)

    if rapport:
        print("\n(Rapportläge — ingen modell sparades.)")
        return

    # Skriv okända uppdrag till fil så GUI kan fråga användaren.
    if okanda_uppdrag:
        OKAND_PATH.parent.mkdir(parents=True, exist_ok=True)
        OKAND_PATH.write_text(
            json.dumps(okanda_uppdrag, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n⚠ {len(okanda_uppdrag)} uppdrag med okänd sport sparade "
              f"— GUI frågar om klassificering.", flush=True)
    elif OKAND_PATH.exists():
        OKAND_PATH.unlink()

    sport_stats = {s: {"n_uppdrag": sport_list.count(s)} for s in sporters}
    typ = "din_smak" if bara_markt else "arkiv"
    paket = {"modell": modell, "sport_modeller": sport_modeller,
             "features": FEATURES, "n_uppdrag": len(X_list),
             "n_valda": n_pos, "sport_stats": sport_stats,
             "rank_modell": rank_modell, "modell_typ": typ,
             "sparad": datetime.now().isoformat(timespec="seconds")}
    MODELL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODELL_PATH, "wb") as f:
        pickle.dump(paket, f)
    # Namngiven kopia i modell-biblioteket → modell-växlaren (din smak ↔ arkiv).
    MODELLER_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELLER_DIR / f"{typ}.pkl", "wb") as f:
        pickle.dump(paket, f)
    print(f"\nModell sparad: {MODELL_PATH}  "
          f"(typ: {typ}, kombinerad + {len(sport_modeller)} sportmodeller: "
          f"{', '.join(sport_modeller)})", flush=True)


def ladda_modell():
    try:
        with open(MODELL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def poangsatt_med_modell(resultat, paket, sport=None):
    """Skriver r['poang'] för alla i resultat (z-normaliserat per uppdrag).
    Använder sportspecifik modell om tillgänglig, annars kombinerad."""
    feats = paket["features"]
    sport_modeller = paket.get("sport_modeller", {})
    lr = sport_modeller.get(sport) if sport else None
    if lr is None:
        lr = paket["modell"]
    X = np.array([[float(r.get(k, 0.0)) for k in feats] for r in resultat])
    Xn = _znorm(X)
    proba = lr.predict_proba(Xn)[:, 1]
    for r, p in zip(resultat, proba):
        r["poang"] = float(p)
        r["modell_p"] = float(p)   # rå sannolikhet (för aktiv inlärning)


def main():
    ap = argparse.ArgumentParser(
        prog="cull-lar",
        description="Träna personlig rankningsmodell på dina levererade val.")
    ap.add_argument("root", nargs="?",
                    help="rotkatalog (export- eller FilterPix-träd)")
    ap.add_argument("--yolo", default="yolo11s.pt", metavar="MODELL")
    ap.add_argument("--estetik-motor", default="nima", choices=["nima", "vision"],
                    help="estetikmotor i träningen: nima (pyiqa, std) eller "
                         "vision (Apple Vision) — måste matcha cull-körningen")
    ap.add_argument("--max-neg", type=int, default=150,
                    help="max antal ej-valda per uppdrag (balans/fart)")
    ap.add_argument("--max-uppdrag", type=int, default=None,
                    help="begränsa antal uppdrag (för test)")
    ap.add_argument("--rapport", action="store_true",
                    help="visa analys men spara ingen modell")
    ap.add_argument("--kolla", action="store_true",
                    help="visa bara online-only-status, träna inte")
    ap.add_argument("--limpa-cache", action="store_true",
                    help="rensa feature-cache och avsluta")
    ap.add_argument("--bara-markt", action="store_true",
                    help="'din smak'-modell: träna enbart på dina märkta matcher "
                         "(Lär av match), oblandat med arkivets Instagram-facit")
    args = ap.parse_args()
    if not args.root and not args.limpa_cache and not args.bara_markt:
        ap.error("root krävs (ange rotkatalog, --bara-markt, eller --limpa-cache)")
    root = Path(args.root).expanduser() if args.root else Path(".")
    traina(root, yolo_modell=args.yolo,
           rapport=args.rapport, max_neg=args.max_neg,
           max_uppdrag=args.max_uppdrag, kontroll_bara=args.kolla,
           limpa_cache=args.limpa_cache, estetik_motor=args.estetik_motor,
           bara_markt=args.bara_markt)


if __name__ == "__main__":
    main()
