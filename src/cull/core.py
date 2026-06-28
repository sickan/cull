"""
cull — teknisk culling av NEF-uppdrag (macOS)

Användning:
  cull <katalog>
  cull <katalog> --topp 30 --ai --hemma-farg blå --bevaka 9,11
  cull <katalog> --avspark 19:00 --xmp --rapport

Krav: exiftool (brew install exiftool)
AI:   pipx inject cull ultralytics mediapipe
OCR:  pipx inject cull easyocr
"""

import argparse
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("Saknar opencv/numpy.")

from cull import bas, matchfas, xmp_writer
from cull.ai_lager import FARG_NAMN

# Stödda raw-format. Alla går genom samma exiftool-preview-väg (-JpgFromRaw/
# -PreviewImage), så stöd = att filtypen tas med i filfiltret.
# NEF (Nikon), DNG (Ricoh GR m.fl.), CR3/CR2 (Canon), ARW (Sony),
# RAF (Fujifilm), RW2 (Panasonic), ORF (Olympus/OM).
RAW_SUFFIX = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}
# JPG kan också cullas — då är filen själv sin egen "preview".
JPG_SUFFIX = {".jpg", ".jpeg"}
BILD_SUFFIX = RAW_SUFFIX | JPG_SUFFIX

# Bilder som skyddats (protect/lås) i kameran tas alltid med i urvalet och
# får denna LR-färgetikett (xmp:Label) som markör. Protect lagras som DOS
# read-only-attributet på exFAT-kortet → exponeras som UF_IMMUTABLE (uchg) av
# macOS. Flaggan följer INTE med vid kopiering, så den måste läsas på kortet.
SKYDD_LABEL = "Blue"


def _ar_skyddad(p):
    """True om filen är protect-flaggad i kameran (read-only/UF_IMMUTABLE)."""
    try:
        return bool(os.stat(p).st_flags & stat.UF_IMMUTABLE)
    except (OSError, AttributeError):
        return False


def _rmtree_kraft(path):
    """shutil.rmtree som rensar immutable-flagga (uchg/UF_IMMUTABLE) +
    skrivskydd och försöker igen. Behövs vid --export-overskriv: kopior av
    kameralåsta NEF ärver uchg via shutil.copy2 (bevarar st_flags på macOS),
    annars 'Operation not permitted' när den gamla exportmappen ska raderas."""
    def _losgor(func, p, exc):
        try:
            os.chflags(p, 0)               # rensa uchg/UF_IMMUTABLE m.fl.
        except (OSError, AttributeError):
            pass
        try:
            os.chmod(p, stat.S_IRWXU)
        except OSError:
            pass
        try:
            func(p)                        # försök unlink/rmdir igen
        except OSError:
            pass
    try:
        shutil.rmtree(path, onexc=_losgor)        # Python ≥ 3.12
    except TypeError:
        shutil.rmtree(path, onerror=_losgor)      # äldre signatur

# Mappnamn som aldrig scannas som källa (appens egna utdata, inte kortbilder).
_HOPPA_MAPP = {"story", "snabbplock", "urval", "instagram"}


def lista_bildfiler(rot, rekursiv=True):
    """Riktiga bildfiler (raw/jpg) under rot. rekursiv=True går ner i ALLA
    underkataloger (kort med flera DCIM-mappar) men hoppar dolda mappar och
    appens egna utdata (_leverans*, Story, Snabbplock, Instagram, urval).
    Exkluderar dolda filer (._namn-AppleDouble m.m. på exFAT/FAT)."""
    rot = Path(rot)

    def _ok(p):
        return p.suffix.lower() in BILD_SUFFIX and not p.name.startswith(".")

    if not rekursiv:
        return sorted(p for p in rot.iterdir() if p.is_file() and _ok(p))
    träffar = []
    for d, dirs, files in os.walk(rot):
        dirs[:] = [x for x in dirs
                   if not x.startswith(".")
                   and x.lower() not in _HOPPA_MAPP
                   and not x.lower().startswith("_leverans")]
        dp = Path(d)
        träffar += [dp / f for f in files if _ok(dp / f)]
    return sorted(träffar)


# Antal CPU-kärnor att använda för parallell baspoängsättning
N_WORKERS = min(os.cpu_count() or 4, 8)
# Andel av bilderna (sorterade på baspoäng) som AI körs på
AI_KANDIDAT_ANDEL = 0.5
# Snabbläge: dyr AI körs bara på denna andel även med personlig modell
# (medveten recall-mot-fart-avvägning för leverans när beställaren väntar).
SNABB_ANDEL = 0.4

# Cache för baspoäng — nyckel = sökväg|mtime|storlek (oföränderlig per NEF)
import json
# v2: baspoängen innehåller nu motljus + rörelse-riktning → ny cachefil.
BAS_CACHE_PATH = Path.home() / ".cache" / "cull" / "bas_cache_v2.json"

# Aktiv inlärning: osäkra bilder (modell-p nära 0.5) sparas för manuell etikett.
AKTIV_PATH = Path.home() / ".cache" / "cull" / "aktiv_inlarning.json"
AKTIV_THUMB_DIR = Path.home() / ".cache" / "cull" / "aktiv_thumbs"
# Körningshistorik med poängfördelning (för histogram + jämför körningar).
KOR_HIST_PATH = Path.home() / ".config" / "cull" / "kor_historik.json"
# Träningsunderlag per cull: feature-vektorer för HELA tagningen (ingen bild),
# som "Lär av match" senare märker med ditt Photo Mechanic-urval → facit.
FACIT_UNDERLAG_DIR = Path.home() / ".config" / "cull" / "facit_underlag"


def _spara_aktiv_inlarning(resultat, katalog, n=12):
    """Sparar de mest osäkra bilderna (modell-p närmast 0.5) + thumbnails,
    så GUI kan be användaren etikettera dem (aktiv inlärning)."""
    kand = [r for r in resultat if r.get("modell_p") is not None and r.get("_jpg")]
    if not kand:
        return
    kand.sort(key=lambda r: abs(r["modell_p"] - 0.5))
    osakra = kand[:n]
    AKTIV_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    poster = []
    for r in osakra:
        thumb = AKTIV_THUMB_DIR / (r["fil"].stem + ".jpg")
        try:
            shutil.copy2(r["_jpg"], thumb)
        except Exception:
            continue
        poster.append({"nef": str(r["fil"]), "thumb": str(thumb),
                       "stem": r["fil"].stem, "modell_p": round(r["modell_p"], 4)})
    if poster:
        AKTIV_PATH.parent.mkdir(parents=True, exist_ok=True)
        AKTIV_PATH.write_text(
            json.dumps({"katalog": str(katalog), "bilder": poster},
                       ensure_ascii=False, indent=2), encoding="utf-8")


def _logga_korning(katalog, ut_dir, resultat, valda):
    """Loggar poängfördelning + urval för histogram och körningsjämförelse."""
    poäng = sorted(float(r["poang"]) for r in resultat)
    valda_namn = [r["fil"].name for r in
                  sorted(valda, key=lambda r: r["poang"], reverse=True)]
    post = {
        "tid": datetime.now().isoformat(timespec="seconds"),
        "katalog": str(katalog),
        "ut_dir": str(ut_dir),
        "n_total": len(resultat),
        "n_valda": len(valda),
        "poang": [round(p, 4) for p in poäng],
        "valda": valda_namn,
    }
    try:
        hist = json.loads(KOR_HIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    hist.append(post)
    hist = hist[-50:]
    KOR_HIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    KOR_HIST_PATH.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")


def _spara_facit_underlag(resultat, args, sport):
    """Sparar feature-vektorer för HELA tagningen (inga bilder) som senare kan
    märkas med användarens Photo Mechanic-urval → facit för träning. Kräver att
    modellen/AI körts (annars saknas riktiga features). Liten JSON per cull."""
    if not resultat:
        return
    from cull import inlarning
    namn = (args.ut_namn or Path(args.katalog).name or "match").strip()
    # Källkatalogens namn i filnamnet → flera kort/kameror (t.ex. 277Z8_01 vs
    # 170D5_01) för SAMMA match blir separata underlag i stället för att skriva
    # över varandra.
    kalla = Path(args.katalog).name
    slug = re.sub(r"[^\w-]+", "_", f"{namn}__{kalla}").strip("_")[:96] or "match"
    rader = [{"stem": r["fil"].stem,
              "v": [round(float(r.get(k, 0.0)), 5) for k in inlarning.FEATURES]}
             for r in resultat]
    post = {
        "match": namn,
        "kalla": kalla,
        "sport": sport or "",
        "skapad": datetime.now().isoformat(timespec="seconds"),
        "features": list(inlarning.FEATURES),
        "n": len(rader),
        "rader": rader,
    }
    try:
        FACIT_UNDERLAG_DIR.mkdir(parents=True, exist_ok=True)
        (FACIT_UNDERLAG_DIR / f"{slug}.json").write_text(
            json.dumps(post, ensure_ascii=False), encoding="utf-8")
        print(f"  Träningsunderlag sparat ({len(rader)} bilder) — märk med ditt "
              "PM-urval via 'Lär av match'.", flush=True)
    except Exception as e:
        print(f"  (kunde inte spara träningsunderlag: {e})", flush=True)


def _cache_nyckel(nef):
    # Nyckel på storlek (inte mtime) — Dropbox m.fl. ändrar mtime vid omsynk
    # men inte storleken, och raw redigeras aldrig på plats. Stabil cache.
    return f"{nef}|{nef.stat().st_size}"


def ladda_bas_cache():
    try:
        with open(BAS_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def spara_bas_cache(cache):
    try:
        BAS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BAS_CACHE_PATH, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


# AI-feature-cache per bild: sparar de dyra, parameter-oberoende AI-signalerna
# så att omkörning av samma shoot (t.ex. justera reglage) slipper YOLO/pose/
# face/NIMA på nytt. Används bara när personlig modell är aktiv — då påverkar
# inte --hemma-farg/--bevaka poängen, så cachen kan inte ge fel resultat.
import hashlib as _hashlib
from cull.clip_lager import CLIP_FEATURES as _CLIP_FEATURES
AI_CACHE_PATH = Path.home() / ".cache" / "cull" / "ai_cache.json"
AI_FEAT_KEYS = ["armar", "klunga", "boll", "personer", "vast",
                "bakgrund", "keeper", "ogonkontakt", "nima"] + _CLIP_FEATURES


def _ai_feat_version():
    from cull import inlarning
    return _hashlib.sha1("|".join(inlarning.FEATURES).encode()).hexdigest()[:8]


def _ai_cache_nyckel(nef, ver, sport="", estetik_motor=""):
    # CLIP-features beror på sporten (promptmallar) → ingår i nyckeln.
    # Vision-estetik separeras från NIMA så deras nima-värden inte blandas.
    bas = f"{_cache_nyckel(nef)}|v{ver}|{sport or ''}"
    return bas + ("|vis" if estetik_motor == "vision" else "")


def ladda_ai_cache():
    try:
        with open(AI_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def spara_ai_cache(cache):
    # Atomisk skrivning: skriv till temp + os.replace. Dödas processen (OOM/
    # signal) mitt i skrivningen blir den gamla cachen kvar intakt i stället
    # för att lämnas trasig (vilket skulle tvinga omkörning av all AI).
    try:
        AI_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AI_CACHE_PATH.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, AI_CACHE_PATH)
    except Exception:
        pass


def _as_shot_kelvin_batch(nef_paths, env):
    """Läser kamerans as-shot-vitbalans (Kelvin) för flera NEF i ett anrop.
    Returnerar {Path: kelvin}. Saknas värdet utelämnas filen."""
    if not nef_paths:
        return {}
    cmd = ["exiftool", "-j", "-WhiteBalance"] + [str(p) for p in nef_paths]
    ut = {}
    try:
        rå = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
        for post in json.loads(rå):
            wb = str(post.get("WhiteBalance", ""))
            m = re.search(r"(\d{4,5})\s*K", wb)
            if m:
                ut[Path(post["SourceFile"])] = int(m.group(1))
    except Exception:
        pass
    return ut


# Tecken på kamerans RollAngle → crs:CropAngle. Verifierat i Lightroom:
# +1.0 ger rätt riktning (-1.0 rätade åt fel håll).
ROLL_TECKEN = 1.0


def _roll_batch(nef_paths, env):
    """Läser kamerans RollAngle (gyro-lutning, grader) för flera filer i ett
    anrop. Returnerar {Path: grader}. Moderna Nikon (Z8/D5…) har den; äldre
    kroppar (D3S/Df) saknar den → utelämnas (fallback till Vision/Hough)."""
    if not nef_paths:
        return {}
    cmd = ["exiftool", "-j", "-RollAngle"] + [str(p) for p in nef_paths]
    ut = {}
    try:
        rå = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
        for post in json.loads(rå):
            try:
                grader = float(post.get("RollAngle"))
            except (TypeError, ValueError):
                continue
            if abs(grader) <= 10.0:
                ut[Path(post["SourceFile"])] = ROLL_TECKEN * grader
    except Exception:
        pass
    return ut


def _iso_batch(nef_paths, env):
    """Läser EXIF-ISO för flera filer i ett anrop. Returnerar {Path: iso}."""
    if not nef_paths:
        return {}
    cmd = ["exiftool", "-j", "-ISO"] + [str(p) for p in nef_paths]
    ut = {}
    try:
        rå = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
        for post in json.loads(rå):
            iso = post.get("ISO")
            if isinstance(iso, list):
                iso = iso[0] if iso else None
            try:
                ut[Path(post["SourceFile"])] = int(iso)
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    return ut


_VISION_OK = None


def _uppratningsvinkel(jpg_path, img, roll=None):
    """Upprätningsvinkel: kamerans gyro-RollAngle först (exakt, ur NEF), sedan
    Apple Vision-horisont, Hough-linjer sist. Returnerar (grader, motor)."""
    if roll is not None:
        return roll, "gyro"
    global _VISION_OK
    if _VISION_OK is None:
        try:
            from cull import vision_lager
            _VISION_OK = vision_lager.tillganglig()
        except Exception:
            _VISION_OK = False
    if jpg_path and _VISION_OK:
        from cull import vision_lager
        v = vision_lager.horisont_vinkel(jpg_path)
        if v is not None:
            return v, "vision"
    if img is not None:
        return xmp_writer.berakna_uppratning(img), "hough"
    return 0.0, None


def _skriv_rating_exiftool(rating_karta, ut_dir, env):
    """Skriver xmp:Rating inbäddat i de exporterade filerna (exiftool) — så
    Lightroom läser betyget pålitligt (sidecaren används bara för framkallning)."""
    n = 0
    for fil, stjärnor in rating_karta.items():
        mål = ut_dir / fil.name
        if not mål.exists():
            continue
        try:
            r = subprocess.run(
                ["exiftool", "-overwrite_original", "-P",
                 f"-XMP-xmp:Rating={stjärnor}", f"-Rating={stjärnor}", str(mål)],
                capture_output=True, text=True, env=env)
            n += 1 if r.returncode == 0 else 0
        except Exception:
            pass
    return n


def _skriv_label_exiftool(filer, label, ut_dir, env):
    """Bäddar in xmp:Label (färgetikett) i de exporterade filerna — LR läser
    etiketten ur filens inbäddade metadata för raw, precis som betyg."""
    n = 0
    for fil in filer:
        mål = ut_dir / fil.name
        if not mål.exists():
            continue
        try:
            r = subprocess.run(
                ["exiftool", "-overwrite_original", "-P",
                 f"-XMP-xmp:Label={label}", str(mål)],
                capture_output=True, text=True, env=env)
            n += 1 if r.returncode == 0 else 0
        except Exception:
            pass
    return n


def _stjarnor_av_poang(valda):
    """Stjärnbetyg (2-5) per bild utifrån helhetspoängens percentil i urvalet —
    starkast = 5★, garanti/svagast = 2★. Lightroom läser xmp:Rating."""
    if not valda:
        return {}
    poäng = sorted(r["poang"] for r in valda)
    n = len(poäng)
    ut = {}
    for r in valda:
        import bisect
        p = bisect.bisect_right(poäng, r["poang"]) / n
        ut[r["fil"]] = 5 if p >= 0.80 else 4 if p >= 0.55 else 3 if p >= 0.30 else 2
    return ut


def _rakt_bevarande(jpg_path, vinkel):
    """Dämpar upprätningsvinkeln så motivet inte beskärs för hårt — estetik
    före perfekt vinkel. Använder Vision-saliens; oförändrad om inget motiv
    hittas. Returnerar (vinkel, dämpad?)."""
    if not jpg_path or abs(vinkel) < 0.05:
        return vinkel, False
    try:
        from cull import vision_lager, leverans
        bb = vision_lager.saliens_bbox(jpg_path)
        if bb is None:
            return vinkel, False
        from PIL import Image
        w, h = Image.open(jpg_path).size
        ny = leverans._vinkel_som_bevarar(
            w, h, vinkel, (bb[0]*w, bb[1]*h, bb[2]*w, bb[3]*h))
        return ny, (abs(ny) + 0.05 < abs(vinkel))
    except Exception:
        return vinkel, False


def _exif_env():
    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def _kameratyp(nef_filer, env):
    """Kort kameranamn (Z8, D5, D850…) ur EXIF Model, annars None."""
    if not nef_filer:
        return None
    try:
        rå = subprocess.run(["exiftool", "-j", "-Model", str(nef_filer[0])],
                            capture_output=True, text=True, env=env).stdout
        model = str(json.loads(rå)[0].get("Model", ""))
    except Exception:
        return None
    for märke in ("NIKON", "CANON", "SONY", "FUJIFILM", "PANASONIC",
                  "RICOH", "OLYMPUS", "OM DIGITAL SOLUTIONS", "OM SYSTEM"):
        model = model.upper().replace(märke, "")
    kort = model.replace(" ", "").strip()
    return kort or None


def _iptc_metadata(matchinfo, sport):
    """Bygger {caption, keywords, datum, arena} ur matchinfo-strängen."""
    caption = (matchinfo or "").strip()
    home = away = arena = datum = ""
    m = re.match(r"^(.*?)\s+-\s+(.*?)(?:\s+\d+-\d+|\s*$)", caption)
    if m:
        home, away = m.group(1).strip(), m.group(2).strip()
    md = re.search(r"\b(20\d{2})(\d{2})(\d{2})\b", caption)
    if md:
        datum = f"{md.group(1)}:{md.group(2)}:{md.group(3)}"
        arena = caption[md.end():].strip(" -")
    keywords = [k for k in (home, away, sport if sport and sport != "okänd"
                            else "", arena) if k]
    return {"caption": caption, "keywords": keywords,
            "datum": datum, "arena": arena}


def _skriv_iptc(nef_paths, matchinfo, sport, fotograf, env, namn_per_fil=None,
                bildtext_per_fil=None):
    """Skriver IPTC/XMP-metadata till de exporterade filerna.

    namn_per_fil:     {Path: 'Emma Andersson (10), …'} → spelarnamn läggs till i
                      bildtexten per bild (roster).
    bildtext_per_fil: {Path: 'färdig bildtext'} → ersätter HELA bildtexten per
                      bild (Claude vision-bildtext); vinner över namn_per_fil.
    Utan per-fil-data skrivs match-gemensam metadata i ett enda anrop."""
    if not nef_paths or not (matchinfo or "").strip():
        return 0
    md = _iptc_metadata(matchinfo, sport)
    # -codedcharacterset=utf8 markerar IPTC-IIM som UTF-8 (annars visas å/ä/ö som
    # skräp i läsare som annars antar Latin-1/MacRoman).
    gem = ["-charset", "UTF8", "-codedcharacterset=utf8", "-sep", ", "]
    if md["keywords"]:
        kw = ", ".join(md["keywords"])
        gem += [f"-XMP-dc:Subject={kw}", f"-IPTC:Keywords={kw}"]
    if md["arena"]:
        gem += [f"-XMP-Iptc4xmpCore:Location={md['arena']}",
                f"-IPTC:Sub-location={md['arena']}"]
    if md["datum"]:
        gem += [f"-XMP-photoshop:DateCreated={md['datum']}",
                f"-IPTC:DateCreated={md['datum'].replace(':', '')}"]
    if fotograf:
        gem += [f"-XMP-dc:Creator={fotograf}", f"-IPTC:By-line={fotograf}"]

    def _bildtext(p):
        ai = (bildtext_per_fil or {}).get(p, "")
        if ai:
            return ai
        namn = (namn_per_fil or {}).get(p, "")
        return f"{md['caption']} — {namn}" if namn else md["caption"]

    try:
        if namn_per_fil or bildtext_per_fil:
            # Per-fil-bildtext (roster) → ett anrop per fil.
            n = 0
            for p in nef_paths:
                cap = _bildtext(p)
                cmd = (["exiftool", "-overwrite_original"] + gem +
                       [f"-XMP-dc:Description={cap}",
                        f"-IPTC:Caption-Abstract={cap}",
                        f"-XMP-photoshop:Headline={cap}", str(p)])
                r = subprocess.run(cmd, capture_output=True, text=True, env=env)
                n += 1 if r.returncode == 0 else 0
            _mirror_xmp_sidecar(nef_paths, env)
            return n
        cmd = (["exiftool", "-overwrite_original"] + gem +
               [f"-XMP-dc:Description={md['caption']}",
                f"-IPTC:Caption-Abstract={md['caption']}",
                f"-XMP-photoshop:Headline={md['caption']}"] +
               [str(p) for p in nef_paths])
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        _mirror_xmp_sidecar(nef_paths, env)
        return len(nef_paths) if r.returncode == 0 else 0
    except Exception:
        return 0


def _mirror_xmp_sidecar(paths, env):
    """Speglar metadatafälten Lightroom läser för raw (caption, keywords, skapare,
    plats, datum) från bildfilens inbäddade XMP till dess .xmp-sidecar, om en finns.
    LR läser metadata ur sidecaren för raw-filer, inte ur den inbäddade datan."""
    fält = ["-XMP-dc:Description", "-XMP-dc:Subject", "-XMP-photoshop:Headline",
            "-XMP-dc:Creator", "-XMP-photoshop:DateCreated",
            "-XMP-Iptc4xmpCore:Location"]
    for p in paths:
        if p.suffix.lower() not in RAW_SUFFIX:
            continue
        sc = p.with_suffix(".xmp")
        if not sc.exists():
            continue
        cmd = (["exiftool", "-charset", "UTF8", "-overwrite_original",
                "-tagsFromFile", str(p)] + fält + [str(sc)])
        try:
            subprocess.run(cmd, capture_output=True, text=True, env=env)
        except Exception:
            pass


def _hitta_lightroom():
    """Returnerar appnamnet för installerad Lightroom Classic/CC, eller None."""
    for app in ("/Applications/Adobe Lightroom Classic/Adobe Lightroom Classic.app",
                "/Applications/Adobe Lightroom Classic.app",
                "/Applications/Adobe Lightroom/Adobe Lightroom.app",
                "/Applications/Adobe Lightroom.app"):
        if Path(app).exists():
            return app
    return None


def _hitta_dxo():
    """Returnerar appsökväg för installerat DxO PureRAW (nyaste först), eller None."""
    import glob
    träffar = sorted(glob.glob("/Applications/DxO PureRAW*.app"), reverse=True)
    return träffar[0] if träffar else None


def oppna_resultat(ut_dir, lr_mapp, kopierade, lage="auto"):
    """Öppnar resultatet:
      lightroom/auto → matchroten (lr_mapp) för import av hela matchen
      dxo            → de valda filerna i DxO PureRAW (avbrusa behållarna)
      finder         → urvalsmappen (ut_dir)
      inget          → gör inget."""
    if lage == "inget":
        return
    if lage == "dxo":
        dxo = _hitta_dxo()
        if dxo:
            subprocess.Popen(["open", "-a", dxo] + [str(p) for p in kopierade])
            return
        print("  (DxO PureRAW hittades inte — öppnar i Finder istället.)", flush=True)
        subprocess.Popen(["open", str(ut_dir)])
        return
    lr = _hitta_lightroom()
    if lage in ("auto", "lightroom") and lr:
        subprocess.Popen(["open", "-a", lr, str(lr_mapp)])
        return
    if lage == "lightroom" and not lr:
        print("  (Lightroom hittades inte — öppnar i Finder istället.)", flush=True)
    subprocess.Popen(["open", str(ut_dir)])


def kontrollera_exiftool():
    if shutil.which("exiftool") is None:
        sys.exit("Saknar exiftool. Kör: brew install exiftool")


def extrahera_previews_batch(nef_filer, ut_dir, n_workers=N_WORKERS):
    """
    Extraherar previews parallellt. Returnerar dict: nef -> jpg_path | None.
    """
    ut_dir = Path(ut_dir)
    totalt  = len(nef_filer)
    klar    = 0
    lock    = __import__("threading").Lock()

    # JPG-filer är redan sin egen "preview" — ingen extraktion behövs.
    raw_filer = [n for n in nef_filer if n.suffix.lower() not in JPG_SUFFIX]
    totalt = len(raw_filer)

    def extrahera_en(nef):
        nonlocal klar
        ut = ut_dir / (nef.stem + ".jpg")
        for tag in ("-JpgFromRaw", "-PreviewImage"):
            try:
                with open(ut, "wb") as f:
                    subprocess.run(
                        ["exiftool", "-b", tag, str(nef)],
                        stdout=f,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                    )
            except Exception:
                pass
            if ut.exists() and ut.stat().st_size > 10_000:
                break
        else:
            if ut.exists():
                ut.unlink()

        with lock:
            klar += 1
            if klar % 25 == 0 or klar == totalt:
                print(f"  extraherar …{klar}/{totalt}", flush=True)

    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        list(ex.map(extrahera_en, raw_filer))

    def _preview(nef):
        if nef.suffix.lower() in JPG_SUFFIX:
            return nef               # JPG = sin egen preview
        jpg = ut_dir / (nef.stem + ".jpg")
        return jpg if jpg.exists() and jpg.stat().st_size > 10_000 else None

    return {nef: _preview(nef) for nef in nef_filer}


def hamta_metadata(nef_filer):
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
    return tider


def _score_en(args):
    nef, jpg_path = args
    p = bas.poangsatt(jpg_path)
    return nef, jpg_path, p


def _skriv_tidrapport(tider_fas):
    """Skriver 'Tid per fas'. AI:-delsteg är en nedbrytning av AI-bucketen och
    indenteras + räknas INTE in i Totalt (annars dubbelräknas de)."""
    if not tider_fas:
        return
    print("\nTid per fas:")
    for fas, sek in tider_fas.items():
        prefix = "    " if fas.startswith("AI:") else "  "
        print(f"{prefix}{fas:<16} {sek:5.1f} s")
    total = sum(s for f, s in tider_fas.items() if not f.startswith("AI:"))
    print(f"  {'Totalt':<16} {total:5.1f} s")


def _nummer_index():
    """Indexerar AI-cachens avlästa tröjnummer på (filnamn, storlek), så att
    redan exporterade (kopierade) filer kan matchas utan ny OCR."""
    idx = {}
    for nyckel, post in ladda_ai_cache().items():
        delar = nyckel.split("|")
        if len(delar) < 2:
            continue
        namn, storlek = Path(delar[0]).name, delar[1]
        nummer = post.get("_nummer")
        if nummer:
            idx[(namn, storlek)] = nummer
    return idx


def kor_efterbehandling(args, katalog):
    """Kör om leveranssteg på en redan exporterad mapp — ingen culling, ingen
    modell-laddning. Opt-in: --iptc/--roster, --husstil/--exp-bump."""
    from cull import xmp_writer
    filer = sorted(p for p in katalog.iterdir()
                   if p.suffix.lower() in BILD_SUFFIX
                   and not p.name.startswith("._"))
    if not filer:
        sys.exit(f"Inga bildfiler i {katalog}")
    print(f"Efterbehandlar {len(filer)} filer i {katalog.name} "
          "(ingen omculling).", flush=True)
    sport = (args.sport or "okänd").lower()
    matchinfo = args.ut_namn or katalog.name
    namn_per_fil = bildtext_per_fil = None   # delas med leveranssteget nedan

    # IPTC + roster (spelarnamn per bild ur cachade tröjnummer).
    if args.iptc:
        rost = {}
        from cull import roster as _roster
        if args.roster:
            rost = _roster.las_roster(args.roster)
            idx = _nummer_index()
            if rost:
                namn_per_fil = {}
                träff = 0
                for f in filer:
                    nummer = idx.get((f.name, str(f.stat().st_size)), [])
                    namn_per_fil[f] = _roster.namnge(rost, nummer)
                    träff += 1 if namn_per_fil[f] else 0
                print(f"  Roster: {len(rost)} spelare, namn på {träff} bilder "
                      "(tröjnummer ur cachen).", flush=True)
        bildtext_per_fil = None
        if args.bildtext_ai:
            from cull import bildtext_ai
            idx = _nummer_index()
            with tempfile.TemporaryDirectory() as tmp:
                raw = [f for f in filer if f.suffix.lower() in RAW_SUFFIX]
                pm = extrahera_previews_batch(raw, Path(tmp)) if raw else {}
                jobb = [{"id": f,
                         "jpg": (f if f.suffix.lower() in JPG_SUFFIX
                                 else pm.get(f)),
                         "nummer": idx.get((f.name, str(f.stat().st_size)), []),
                         "namn": (namn_per_fil or {}).get(f, "")}
                        for f in filer]
                lag = matchinfo.split(" - ")[0].strip()
                bildtext_per_fil = bildtext_ai.generera_bildtexter(
                    jobb, matchinfo, sport, args.hemma_farg,
                    args.bildtext_modell, print,
                    roster_text=_roster.lista_text(rost), roster_lag=lag)
        n = _skriv_iptc(filer, matchinfo, sport, args.fotograf,
                        _exif_env(), namn_per_fil, bildtext_per_fil)
        print(f"  IPTC skrivet på {n} filer." if n
              else "  IPTC hoppades över (matchinfo saknas?).", flush=True)

    # Husstil-preset / exponeringsknuff → nya sidecars. Upprätning via Apple
    # Vision-horisont (kräver bara filen) när den hittar en horisont.
    if args.husstil or args.exp_bump:
        preset = xmp_writer.las_preset(args.husstil) if args.husstil else None
        raw = [f for f in filer if f.suffix.lower() in RAW_SUFFIX]
        iso_karta = _iso_batch(raw, _exif_env()) if args.xmp_brus else {}
        roll_karta = _roll_batch(raw, _exif_env())
        with tempfile.TemporaryDirectory() as tmp:
            pm = extrahera_previews_batch(raw, Path(tmp)) if raw else {}
            n = vis = gyr = 0
            for f in filer:
                är_raw = f.suffix.lower() in RAW_SUFFIX
                jpg = f if f.suffix.lower() in JPG_SUFFIX else pm.get(f)
                vinkel, motor = _uppratningsvinkel(jpg, None, roll_karta.get(f))
                vinkel, _ = _rakt_bevarande(jpg, vinkel)
                vis += 1 if motor == "vision" else 0
                gyr += 1 if motor == "gyro" else 0
                xmp_writer.skriv_xmp(
                    f, vinkel=vinkel,
                    profil=("Camera Neutral" if är_raw and not preset else None),
                    iso=(iso_karta.get(f) if är_raw and args.xmp_brus else None),
                    objektiv=(är_raw and bool(args.husstil)),
                    preset=preset, exp_bump=args.exp_bump)
                n += 1
        etikett = (Path(args.husstil).stem if args.husstil else "exp-knuff")
        ratning = ", ".join(t for t in (
            f"{gyr} gyro" if gyr else "", f"{vis} Vision" if vis else "") if t)
        print(f"  Sidecars skrivna ({etikett}, {args.exp_bump:+.2f} EV) på "
              f"{n} filer." + (f" Upprätning: {ratning}." if ratning else ""),
              flush=True)

    # Leveransfärdiga JPEG (snabbflöde) enligt profil — gyro-rätat, skalat,
    # komprimerat. IPTC + ev. AI-bildtext bakas in på leverans-JPEG:erna.
    if args.leverans:
        from cull import leverans as _lev
        prof = _lev.PROFILER.get(args.leverans.upper())
        if not prof:
            print(f"  Okänd leveransprofil: {args.leverans} "
                  f"(finns: {', '.join(_lev.PROFILER)}).", flush=True)
        else:
            prof = dict(prof, _namn=args.leverans.upper())
            raw = [f for f in filer if f.suffix.lower() in RAW_SUFFIX]
            roll_karta = _roll_batch(raw, _exif_env())
            lev_dir = katalog / f"_leverans_{args.leverans.upper()}"
            with tempfile.TemporaryDirectory() as tmp:
                pm = extrahera_previews_batch(raw, Path(tmp)) if raw else {}
                jobb = [{"namn": f.stem,
                         "jpg": (f if f.suffix.lower() in JPG_SUFFIX else pm.get(f)),
                         "vinkel": roll_karta.get(f)} for f in filer]
                skapade = _lev.exportera(
                    jobb, lev_dir, prof, print,
                    claude=getattr(args, "instagram_ai", False),
                    matchinfo=(getattr(args, "ut_namn", "") or ""))
            # IPTC/bildtext på leverans-JPEG (samma texter, omnyckladе per stem).
            if args.iptc and skapade:
                npf = {lev_dir / f"{f.stem}.jpg": v
                       for f, v in (namn_per_fil or {}).items()} or None
                bpf = {lev_dir / f"{f.stem}.jpg": v
                       for f, v in (bildtext_per_fil or {}).items()} or None
                _skriv_iptc(skapade, matchinfo, sport, args.fotograf,
                            _exif_env(), npf, bpf)
            print(f"  Leverans klar: {lev_dir}", flush=True)

    print("Klart.", flush=True)


def _injicera_crop_xmp(xmp_path, rect, env):
    """Lägger till/ersätter en crs:Crop-ruta i en befintlig sidecar (bevarar
    övrig framkallning). rect = (top, left, bottom, right) normaliserade."""
    top, left, bottom, right = rect
    # Skriv en KOMPLETT crop-block: utan crs:CropAngle (+ CropConstrainToWarp) kan
    # Lightroom/Camera Raw tolka crop-rutan inkonsekvent. Vinkel 0 = ren aspekt-crop
    # utan rätning (rätningen, om någon, ligger redan i den bevarade framkallningen).
    cmd = ["exiftool", "-overwrite_original", "-XMP-crs:HasCrop=True",
           f"-XMP-crs:CropTop={top:.6f}", f"-XMP-crs:CropLeft={left:.6f}",
           f"-XMP-crs:CropBottom={bottom:.6f}", f"-XMP-crs:CropRight={right:.6f}",
           "-XMP-crs:CropAngle=0", "-XMP-crs:CropConstrainToWarp=0",
           str(xmp_path)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, env=env)
    except Exception:
        pass


def kor_instagram_urval(args, katalog):
    """Plockar de N IG-bästa ur ett BEFINTLIGT urval (saliens-4:5-passform + ev.
    Claude-redaktör), kopierar raw + sidecar till <katalog>/Instagram och
    injicerar en 4:5-crop i sidecaren. LR öppnar dem 4:5 men redigerbart, med
    all annan framkallning som redan ligger i sidecarsen bevarad."""
    import shutil
    from cull import leverans as _lev, xmp_writer
    kat = Path(katalog)
    if not kat.is_dir():
        print(f"Hittar inte mappen: {kat}", flush=True)
        return
    raw = sorted(p for p in kat.iterdir()
                 if p.suffix.lower() in RAW_SUFFIX and not p.name.startswith("."))
    if not raw:
        print("Inga raw-filer i mappen.", flush=True)
        return
    antal = args.topp if args.topp else _lev.PROFILER["INSTAGRAM"]["antal"]
    prof = dict(_lev.PROFILER["INSTAGRAM"], antal=antal, _namn="INSTAGRAM")
    print(f"Instagram-urval ur {len(raw)} bilder → {antal} bästa (4:5)…", flush=True)
    env = _exif_env()
    with tempfile.TemporaryDirectory() as tmp:
        pm = extrahera_previews_batch(raw, Path(tmp))
        jobb = [{"namn": r.stem, "jpg": pm.get(r), "raw": r, "vinkel": None}
                for r in raw if pm.get(r)]
        valda = _lev.valj_instagram(
            jobb, prof, claude=getattr(args, "instagram_ai", False),
            matchinfo=(getattr(args, "ut_namn", "") or ""), logg=print)
        ig_dir = kat / "Instagram"
        ig_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for j in valda:
            r = j["raw"]
            img = cv2.imread(str(j["jpg"]))
            if img is None:
                continue
            h, w = img.shape[:2]
            rect = _lev.crop_rect(j.get("_bbox"), w, h, prof["aspekt"],
                                  j.get("_komp"))
            shutil.copy2(r, ig_dir / r.name)
            try:
                os.chflags(ig_dir / r.name, 0)   # ärv inte kamerans uchg-lås
            except (OSError, AttributeError):
                pass
            src_xmp = r.with_suffix(".xmp")
            dst_xmp = ig_dir / f"{r.stem}.xmp"
            if src_xmp.exists():
                shutil.copy2(src_xmp, dst_xmp)
                _injicera_crop_xmp(dst_xmp, rect, env)   # behåll framkallning + lägg crop
            else:
                xmp_writer.skriv_xmp(ig_dir / r.name, crop=rect)
            n += 1
            if n % 5 == 0 or n == len(valda):
                print(f"  kopierar …{n}/{len(valda)}", flush=True)
    print(f"✓ Instagram-urval klart: {ig_dir} ({n} bilder, 4:5 i XMP).", flush=True)
    lr = _hitta_lightroom()
    if lr:
        subprocess.Popen(["open", "-a", lr, str(ig_dir)])
        print(f"  Öppnar i Lightroom: {ig_dir}", flush=True)
    print("Klart.", flush=True)


def kor_snabbplock(args, katalog):
    """Snabbplock: kopierar ENBART de kameralåsta (protect/UF_IMMUTABLE) NEF-
    filerna ur kortet till en egen mapp + XMP-sidecar med Blue-etikett. Ingen
    AI, ingen scoring, ingen burst-dedup, ingen crop — fristående snabbväg för
    att i en paus (t.ex. efter uppvärmningen) få ut just de bilder du redan
    låst i kameran och ta in dem direkt i Lightroom. Läs MEDAN kortet sitter i:
    uchg-flaggan följer inte med en kopia, så den måste läsas på källan."""
    import shutil
    from cull import xmp_writer
    kat = Path(katalog)
    nef_filer = sorted(p for p in kat.iterdir()
                       if p.suffix.lower() in BILD_SUFFIX
                       and not p.name.startswith("."))
    if not nef_filer:
        print("Inga bildfiler i katalogen.", flush=True)
        return
    skyddade = [p for p in nef_filer if _ar_skyddad(p)]
    if not skyddade:
        print(f"Inga kameralåsta (protect) bilder bland {len(nef_filer)} "
              "filer. Lås/skydda bilderna i kameran först, och kör medan "
              "kortet sitter i.", flush=True)
        return
    print(f"Snabbplock: {len(skyddade)} av {len(nef_filer)} bilder är "
          f"kameralåsta → kopierar + {SKYDD_LABEL}-etikett (ingen AI).",
          flush=True)

    def _sanera(s):
        return s.replace("/", "-").replace(":", ".").strip()

    if getattr(args, "snabb_ut", None):
        ut_dir = Path(args.snabb_ut).expanduser() / "Snabbplock"
    elif args.export_rot:
        rot = Path(args.export_rot).expanduser()
        namn = _sanera(args.ut_namn) if args.ut_namn else \
            (kat.parent.name or kat.name)
        ut_dir = rot / namn / "Snabbplock"
    else:
        ut_dir = kat / "Snabbplock"
    if ut_dir.exists():
        i = 2
        bas = ut_dir
        while ut_dir.with_name(f"{bas.name} {i}").exists():
            i += 1
        ut_dir = ut_dir.with_name(f"{bas.name} {i}")
    try:
        ut_dir.mkdir(parents=True)
    except OSError as e:
        sys.exit(f"Kan inte skapa mappen {ut_dir}: {e}. "
                 "Är disken ansluten och skrivbar?")
    print(f"Plockar till: {ut_dir}", flush=True)

    env = _exif_env()
    kopierade = []
    for i, src in enumerate(skyddade, 1):
        mål = ut_dir / src.name
        shutil.copy2(src, mål)
        # Rensa ärvd uchg (copy2 bevarar st_flags) så Snabbplock-mappen går
        # att radera/skriva över efteråt.
        try:
            os.chflags(mål, 0)
        except (OSError, AttributeError):
            pass
        kopierade.append(mål)
        # Sidecar med Blue-etikett. Finns redan en sidecar på kortet (egen
        # framkallning) → behåll den; den inbäddade etiketten nedan markerar
        # ändå bilden. Annars skriv en ren sidecar med bara etiketten.
        src_xmp = src.with_suffix(".xmp")
        if src_xmp.exists():
            shutil.copy2(src_xmp, ut_dir / src_xmp.name)
        else:
            xmp_writer.skriv_xmp(mål, label=SKYDD_LABEL)
        print(f"  kopierar …{i}/{len(skyddade)}", flush=True)
    # Bädda in etiketten i raw-filerna (LR läser xmp:Label ur inbäddad
    # metadata för raw — samma dubbla väg som vanliga cullen).
    nl = _skriv_label_exiftool(skyddade, SKYDD_LABEL, ut_dir, env)
    print(f"✓ Snabbplock klart: {ut_dir} ({len(kopierade)} bilder, "
          f"{SKYDD_LABEL}-etikett i {nl}).", flush=True)
    oppna_resultat(ut_dir, ut_dir, kopierade, args.oppna)
    print("Klart.", flush=True)


def _las_rating_label(xmp_path):
    """Plockar xmp:Rating + xmp:Label ur en befintlig sidecar (för att bevara
    dem när vi bara lägger på rätning)."""
    try:
        txt = Path(xmp_path).read_text(encoding="utf-8")
    except Exception:
        return None, None
    r = re.search(r"xmp:Rating=['\"](\d+)['\"]", txt)
    l = re.search(r"xmp:Label=['\"]([^'\"]+)['\"]", txt)
    return (int(r.group(1)) if r else None), (l.group(1) if l else None)


def kor_rata_upp(args, katalog):
    """Fristående upprätning: skriver crop-only XMP-sidecars (kamerans gyro-
    RollAngle → Apple Vision-horisont → Hough) bredvid NEF:erna, så Lightroom
    plockar upp rätningen vid import. Icke-förstörande: en befintlig sidecar
    bevaras (develop + betyg/etikett) och bara beskärningsvinkeln läggs på."""
    import tempfile
    raw = [p for p in lista_bildfiler(katalog, rekursiv=True)
           if p.suffix.lower() in RAW_SUFFIX]
    if not raw:
        print("Inga raw-filer att räta upp i mappen.", flush=True)
        return
    env = _exif_env()
    roll_karta = _roll_batch(raw, env)
    n_gyro = sum(1 for f in raw if roll_karta.get(f) is not None)
    print(f"Rätar upp {len(raw)} bilder ({n_gyro} med kamerans gyro)…",
          flush=True)
    n_skriv = n_raka = 0
    with tempfile.TemporaryDirectory() as tmp:
        pm = extrahera_previews_batch(raw, Path(tmp))
        for i, f in enumerate(raw, 1):
            jpg = pm.get(f)
            vinkel, _motor = _uppratningsvinkel(jpg, None, roll_karta.get(f))
            vinkel, _ = _rakt_bevarande(jpg, vinkel)
            if abs(vinkel) < 0.05:
                n_raka += 1
            sc = f.with_suffix(".xmp")
            preset = rating = label = None
            if sc.exists():
                preset = xmp_writer.las_preset(sc)
                rating, label = _las_rating_label(sc)
            try:
                xmp_writer.skriv_xmp(f, vinkel=vinkel, preset=preset,
                                     rating=rating, label=label)
                n_skriv += 1
            except Exception as e:
                print(f"  (kunde inte skriva {sc.name}: {e})", flush=True)
            if i % 25 == 0 or i == len(raw):
                print(f"  rätar …{i}/{len(raw)}", flush=True)
    print(f"✓ Rätning klar: {n_skriv} XMP-sidecars skrivna "
          f"({n_raka} var redan raka). Importera mappen i Lightroom — "
          "rätningen följer med automatiskt.", flush=True)


def main():
    ap = argparse.ArgumentParser(prog="cull",
                                 description="Teknisk culling av NEF-filer.")
    ap.add_argument("katalog", nargs="?")   # valfri vid --limpa-ai-cache
    ap.add_argument("--topp",       type=int,   default=None)
    ap.add_argument("--andel",      type=float, default=0.20)
    ap.add_argument("--burst-sek",  type=float, default=2.0)
    ap.add_argument("--rapport",    action="store_true")
    ap.add_argument("--ai",         action="store_true")
    ap.add_argument("--hemma-farg", default=None, metavar="FÄRG",
                    help=f"hemmalagsfärg: {', '.join(FARG_NAMN)}")
    ap.add_argument("--bevaka",     default=None, metavar="9,11")
    ap.add_argument("--avspark",    default=None, metavar="HH:MM")
    ap.add_argument("--xmp",        action="store_true")
    ap.add_argument("--yolo",       default="yolo11s.pt", metavar="MODELL",
                    help="YOLO-vikt: yolov8n.pt (snabb), yolo11s.pt (balans), "
                         "yolo11m.pt (bäst)")
    ap.add_argument("--estetik",    action="store_true",
                    help="lägg till estetikbetyg")
    ap.add_argument("--estetik-motor", default="nima", choices=["nima", "vision"],
                    help="estetikmotor: nima (pyiqa/MPS, std) eller vision "
                         "(Apple Vision, snabbt på Neural Engine, inget pyiqa)")
    ap.add_argument("--ingen-modell", action="store_true",
                    help="använd inte den tränade personliga modellen")
    ap.add_argument("--sport", default=None,
                    metavar="SPORT",
                    help="sport: handboll, fotboll, volleyboll, innebandy "
                         "(auto-detekteras om ej angiven)")
    ap.add_argument("--ut-namn", default=None, metavar="NAMN",
                    help="namn på urvalsmappen, t.ex. 'LUGI Sävehof 28-25 (13-12) 20260410'")
    ap.add_argument("--firande-boost", type=int, default=0, metavar="N",
                    help="justera firande-vikten: +1..+3 mer firande, -1..-3 mindre")
    ap.add_argument("--garanti-firande", type=int, default=0, metavar="N",
                    help="reservera N platser för bilder med högst firande-score")
    ap.add_argument("--garanti-bevaka", type=int, default=0, metavar="N",
                    help="reservera N platser för de bästa bilderna på bevakat "
                         "tröjnummer (kräver --bevaka)")
    ap.add_argument("--snabb", action="store_true",
                    help="snabbläge: dyr AI bara på topp 40 %% (snabb leverans, "
                         "lägre recall — för när beställaren väntar)")
    ap.add_argument("--oppna", default="auto",
                    choices=["auto", "lightroom", "dxo", "finder", "inget"],
                    help="öppna urvalet efteråt (auto=Lightroom om installerat, "
                         "dxo=DxO PureRAW på de valda filerna)")
    ap.add_argument("--export-rot", default=None, metavar="MAPP",
                    help="exportera till MAPP/<matchinfo>/<kameratyp>/ istället "
                         "för en undermapp i källkatalogen")
    ap.add_argument("--snabb-ut", default=None, metavar="MAPP",
                    help="snabbplock: lägg Snabbplock-mappen i MAPP (t.ex. en "
                         "Dropbox-mapp) istället för på minneskortet")
    ap.add_argument("--export-overskriv", action="store_true",
                    help="skriv över befintlig urvalsmapp istället för att räkna "
                         "upp (Z8 2, Z8 3 …) — undviker dubblettmappar vid omkörning")
    ap.add_argument("--iptc", action="store_true",
                    help="skriv IPTC-bildtexter (match/datum/lag/arena) i filerna")
    ap.add_argument("--fotograf", default=None, metavar="NAMN",
                    help="fotografens namn → IPTC By-line/Creator (med --iptc)")
    ap.add_argument("--xmp-justering", action="store_true",
                    help="skriv exponering + WB/tint + objektivkorr i XMP (från "
                         "ansikts-exponering och uppmätt färgstick)")
    ap.add_argument("--xmp-brus", action="store_true",
                    help="skriv ISO-baserad brusreducering i XMP (separat opt-in "
                         "— stäng av i flöden som går till DxO, som avbrusar)")
    ap.add_argument("--husstil", default=None, metavar="PRESET.xmp",
                    help="baka in ett Camera Raw/Lightroom-preset (.xmp) i varje "
                         "sidecar — din egen look på alla bilder direkt")
    ap.add_argument("--exp-bump", type=float, default=0.0, metavar="EV",
                    help="generell exponeringsknuff (EV) ovanpå allt annat, "
                         "t.ex. 0.5")
    ap.add_argument("--roster", default=None, metavar="ROSTER.csv",
                    help="trupplista (nummer,namn) → spelarnamn i IPTC-bildtext "
                         "per bild (kräver --iptc och avlästa tröjnummer)")
    ap.add_argument("--efterbehandla", action="store_true",
                    help="kör om leveranssteg (--iptc/--roster/--husstil/"
                         "--exp-bump/--bildtext-ai) på en REDAN exporterad mapp "
                         "utan att culla om")
    ap.add_argument("--bildtext-ai", action="store_true",
                    help="skriv publiceringsfärdig svensk bildtext per bild via "
                         "Claude (kräver --iptc, ANTHROPIC_API_KEY; kostar/bild)")
    ap.add_argument("--bildtext-modell", default="claude-opus-4-8",
                    metavar="MODELL",
                    help="modell för bildtext-AI (claude-opus-4-8 (std), "
                         "claude-haiku-4-5 = billigast, claude-sonnet-4-6)")
    ap.add_argument("--leverans", default=None, metavar="PROFIL",
                    help="producera leveransfärdiga JPEG enligt en profil "
                         "(t.ex. CEV, INSTAGRAM) — gyro-rätat, skalat, komprimerat")
    ap.add_argument("--instagram-ai", action="store_true",
                    help="låt en Claude-redaktör välja Instagram-bilderna ur "
                         "kortlistan (komposition/variation) — kostar några ören")
    ap.add_argument("--instagram-urval", action="store_true",
                    help="plocka N IG-bästa ur ett befintligt urval, kopiera raw"
                         " + sidecar med 4:5-crop i XMP (öppnas i Lightroom)")
    ap.add_argument("--snabbplock", action="store_true",
                    help="snabbväg: kopiera ENBART de kameralåsta (protect) "
                         "bilderna + Blue-etikett, ingen AI — för stories i pausen")
    ap.add_argument("--stjarnor", action="store_true",
                    help="sätt stjärnbetyg (xmp:Rating 2-5) i sidecaren utifrån "
                         "helhetspoängen → Lightroom visar dem")
    ap.add_argument("--rata-upp", action="store_true",
                    help="fristående: skriv crop-only XMP-sidecars med upprätning "
                         "(gyro/Vision/Hough) bredvid NEF:erna → Lightroom plockar "
                         "upp rätningen vid import (icke-förstörande)")
    ap.add_argument("--ingen-ai-cache", action="store_true",
                    help="hoppa över AI-feature-cachen (tvinga omräkning)")
    ap.add_argument("--limpa-ai-cache", action="store_true",
                    help="töm AI-feature-cachen och avsluta")
    args = ap.parse_args()

    from cull import version as ver
    print(ver.etikett(), flush=True)

    if args.limpa_ai_cache:
        try:
            AI_CACHE_PATH.unlink()
            print(f"AI-cache tömd: {AI_CACHE_PATH}", flush=True)
        except FileNotFoundError:
            print("Ingen AI-cache att tömma.", flush=True)
        return

    if not args.katalog:
        ap.error("katalog krävs (utom vid --limpa-ai-cache)")

    kontrollera_exiftool()
    katalog = Path(args.katalog).expanduser()
    if not katalog.is_dir():
        delar = katalog.parts
        if (len(delar) >= 3 and delar[1] == "Volumes"
                and not (Path("/Volumes") / delar[2]).exists()):
            sys.exit(f"Disken '{delar[2]}' är inte monterad. "
                     f"Anslut den och försök igen.")
        sys.exit(f"Hittar inte katalogen: {katalog}")

    if args.efterbehandla:
        kor_efterbehandling(args, katalog)
        return

    if args.instagram_urval:
        kor_instagram_urval(args, katalog)
        return

    if args.snabbplock:
        kor_snabbplock(args, katalog)
        return

    if args.rata_upp:
        kor_rata_upp(args, katalog)
        return

    # Läs rekursivt: alla underkataloger med riktiga NEF tas med (kort med
    # flera DCIM-mappar). Dolda AppleDouble-sidecars (._namn) + egna utdata
    # hoppas av lista_bildfiler.
    nef_filer = lista_bildfiler(katalog, rekursiv=True)
    if not nef_filer:
        sys.exit("Inga bildfiler i katalogen (raw: NEF/DNG/CR3/ARW/RAF/RW2/ORF "
                 "eller JPG).")

    # Exporten skiljer filer på basnamn (ut_dir/fil.name). Finns samma namn i
    # flera kortmappar (Nikon-räknaren börjar om per mapp) skulle de skriva
    # över varandra. I rapportläge kopieras INGET → då räcker en varning;
    # annars avbryt tydligt i stället för att tappa bilder.
    from collections import Counter as _Counter
    _dubbl = [n for n, c in _Counter(p.name for p in nef_filer).items() if c > 1]
    if _dubbl:
        if args.rapport:
            print(f"⚠ {len(_dubbl)} filnamn finns i flera mappar (t.ex. "
                  f"{sorted(_dubbl)[0]}). I rapportläge spelar det ingen roll "
                  "(inget kopieras), men för en riktig export: kör en mapp i "
                  "taget eller 'File number sequence' = ON i kameran.", flush=True)
        else:
            sys.exit(f"Samma filnamn finns i flera mappar ({len(_dubbl)} st, "
                     f"t.ex. {sorted(_dubbl)[0]}). Exporten skiljer filer på "
                     "namn, så det skulle skriva över. Kör en mapp i taget, "
                     "eller sätt 'File number sequence' = ON i kameran för "
                     "unika namn.")

    # Kamera-skyddade bilder (protect/lås) — läses NU medan filerna ligger på
    # kortet (flaggan följer inte med en kopia). Tas alltid med i urvalet +
    # får färgetikett. Läs på källan eftersom shutil.copy2 inte bevarar uchg.
    skyddade = {p for p in nef_filer if _ar_skyddad(p)}
    if skyddade:
        print(f"Skyddade i kameran (protect): {len(skyddade)} bild(er) — "
              f"tas alltid med + {SKYDD_LABEL}-etikett i LR.", flush=True)

    bevaka = set(args.bevaka.split(",")) if args.bevaka else set()

    # Personlig modell (om tränad) — kräver AI-features för alla bilder.
    from cull import inlarning
    modell_paket = None if args.ingen_modell else inlarning.ladda_modell()

    if args.sport:
        sport = args.sport.lower()
    else:
        # Röstning: nyckelord + resultatmönster + bildanalys (NEF-stickprov)
        # + webb-sökning. Allt cachas — andra körningen på samma match är snabb.
        prov_items = [(p, 0) for p in random.sample(nef_filer, min(6, len(nef_filer)))]
        cull_env = os.environ.copy()
        for _p in ("/opt/homebrew/bin", "/usr/local/bin"):
            if _p not in cull_env.get("PATH", "").split(os.pathsep):
                cull_env["PATH"] = _p + os.pathsep + cull_env.get("PATH", "")
        sport = inlarning.detektera_sport(
            katalog.parent.name or katalog.name,
            items=prov_items, webb=True, env=cull_env)

    if modell_paket:
        args.ai = True
        args.estetik = True
        sport_modeller = modell_paket.get("sport_modeller", {})
        sport_info = (f", {sport}-modell" if sport in sport_modeller
                      else f", {sport} (kombinerad)")
        print(f"Personlig modell aktiv "
              f"({modell_paket['n_valda']} val, "
              f"{modell_paket['n_uppdrag']} uppdrag{sport_info}).", flush=True)

    print(f"{len(nef_filer)} bildfiler hittade.", flush=True)

    tider_fas = {}   # tidmätning per fas (init före modell-laddningen)

    # --- Ladda AI-modeller ---
    modeller = None
    if args.ai:
        from cull import ai_lager
        print("Laddar AI-modeller…", flush=True)
        _t = time.perf_counter()
        # Vision-motorn behöver ingen pyiqa-modell (estetik räknas ur filerna).
        med_nima = args.estetik and args.estetik_motor != "vision"
        modeller = ai_lager.ladda_modeller(med_ocr=bool(bevaka),
                                           yolo_modell=args.yolo,
                                           med_estetik=med_nima,
                                           med_ogon=bool(modell_paket),
                                           med_clip=bool(modell_paket))
        if args.estetik and args.estetik_motor == "vision":
            from cull import vision_lager as _vis
            print(f"Vision-estetik: {'aktivt (Neural Engine)' if _vis.tillganglig() else 'EJ tillgängligt'}",
                  flush=True)
        tider_fas["Modell-laddning"] = time.perf_counter() - _t
        print("AI-modeller redo.", flush=True)

    # --- Sammanfattning av aktiva kriterier ---
    print("\nAktiva kriterier:", flush=True)
    if args.ai:
        print("  ✓ Skärpa + exponering + ögon (alltid)", flush=True)
        print("  ✓ AI: målfirande — armar + klunga (MediaPipe + YOLO)", flush=True)
        print(f"  ✓ AI: boll/spelare ({args.yolo})", flush=True)
        if args.hemma_farg:
            print(f"  ✓ AI: hemmalagsfärg — {args.hemma_farg}", flush=True)
        if bevaka:
            print(f"  ✓ AI: tröjnummer — {', '.join(sorted(bevaka))} (EasyOCR)", flush=True)
        if args.estetik:
            print("  ✓ AI: NIMA-estetikbetyg", flush=True)
    else:
        print("  ✓ Skärpa + exponering + ögon", flush=True)
    if args.avspark:
        print(f"  ✓ Matchfas — avspark {args.avspark}", flush=True)
    if args.xmp:
        print("  ✓ XMP-sidecars (upprätning)", flush=True)
    n_behall_est = args.topp if args.topp else f"~{int(len(nef_filer) * args.andel)}"
    print(f"  Urval: {n_behall_est} bilder av {len(nef_filer)}\n", flush=True)

    # --- Metadata (tidsstämplar) ---
    print("Hämtar metadata…", flush=True)
    _t = time.perf_counter()
    tider = hamta_metadata(nef_filer)

    avspark_ts = None
    if args.avspark and args.avspark.lower() == "auto":
        alla_ts = [matchfas.parse_tid(t) for t in tider.values()]
        avspark_ts = matchfas.uppskatta_avspark([t for t in alla_ts if t])
        if avspark_ts:
            print(f"  Avspark (auto) uppskattad till "
                  f"{datetime.fromtimestamp(avspark_ts):%H:%M} — matchfas-bonus aktiv.",
                  flush=True)
        else:
            print("  Avspark (auto): kunde inte uppskattas ur tidsstämplar "
                  "— matchfas avstängd.", flush=True)
    elif args.avspark:
        forsta_tid = next(
            (matchfas.parse_tid(t) for t in tider.values()
             if matchfas.parse_tid(t)), None)
        if forsta_tid:
            ref_dt = datetime.fromtimestamp(forsta_tid)
            avspark_ts = matchfas.parse_avspark(args.avspark, ref_dt)
            if avspark_ts:
                print(f"  Avspark {args.avspark} — matchfas-bonus aktiv.", flush=True)
    tider_fas["Metadata"] = time.perf_counter() - _t

    def _bygg_resultat(nef, p, jpg):
        tid_str = tider.get(nef.name, "")
        fas_b = 0.0
        if avspark_ts and tid_str:
            ts = matchfas.parse_tid(tid_str)
            if ts:
                fas_b = matchfas.fas_bonus(matchfas.matchminut(ts, avspark_ts))
        # Defaults för basfeatures som äldre cache-poster kan sakna.
        d = {"motljus": 0.0, "rorelse": 0.0}
        d.update(p)
        d.update({
            "armar": 0.0, "boll": 0.0, "hemma": 0.0,
            "trojnummer": 0.0, "klunga": 0.0, "personer": 0, "vast": 0,
            "bakgrund": 0.0, "keeper": 0.0, "ogonkontakt": 0.0,
            "_nummer": [], "_yolo": None,
            "fas": fas_b, "fil": nef, "tid": tid_str, "_jpg": jpg,
        })
        return d

    # --- Fas 1: Baspoäng (med cache) ---
    bas_cache = ladda_bas_cache()
    resultat = []
    att_poangsatta = []   # NEF utan cacheträff → måste extraheras + poängsättas
    for nef in nef_filer:
        c = bas_cache.get(_cache_nyckel(nef))
        if c:
            resultat.append(_bygg_resultat(nef, c, None))
        else:
            att_poangsatta.append(nef)

    if resultat:
        print(f"\n{len(resultat)} baspoäng från cache.", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        if att_poangsatta:
            print(f"\nExtraherar previews ({len(att_poangsatta)} nya)…",
                  flush=True)
            _t = time.perf_counter()
            preview_map = extrahera_previews_batch(att_poangsatta, tmp)
            giltiga = [(nef, jpg) for nef, jpg in preview_map.items() if jpg]
            tider_fas["Extrahering"] = time.perf_counter() - _t
            print(f"{len(giltiga)} previews extraherade "
                  f"({len(att_poangsatta) - len(giltiga)} saknade).\n",
                  flush=True)

            print(f"Baspoängsätter med {N_WORKERS} trådar…", flush=True)
            _t = time.perf_counter()
            klar = 0
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                futures = {ex.submit(_score_en, (nef, jpg)): nef
                           for nef, jpg in giltiga}
                for future in as_completed(futures):
                    klar += 1
                    print(f"  …{klar}/{len(giltiga)}", flush=True)
                    try:
                        nef, jpg, p = future.result()
                    except Exception as e:
                        print(f"  Fel vid poängsättning: {e}", flush=True)
                        continue
                    if p is None:
                        continue
                    bas_cache[_cache_nyckel(nef)] = p
                    resultat.append(_bygg_resultat(nef, p, jpg))
            tider_fas["Baspoäng"] = time.perf_counter() - _t
            spara_bas_cache(bas_cache)

        if not resultat:
            sys.exit("Inget kunde poängsättas.")

        # Normalisera skärpa
        sk = np.array([r["skarpa"] for r in resultat])
        lo, hi = np.percentile(sk, 5), np.percentile(sk, 95)
        spann = max(hi - lo, 1e-6)
        for r in resultat:
            r["skarpa_n"] = float(np.clip((r["skarpa"] - lo) / spann, 0, 1))

        def bas_poang(r):
            ogon_b = 0.0
            if r["ansikten"] > 0:
                ogon_b = min(r["ogon"] / (r["ansikten"] * 2), 1.0) * 0.10
            return 0.55 * r["skarpa_n"] + 0.35 * r["exp"] + ogon_b

        for r in resultat:
            r["bas"] = bas_poang(r)

        # --- Fas 3: AI på topp-kandidater ---
        vb_rapport = None   # vitbalans-/färgstick-rapport (sätts om AI körs)
        if args.ai and modeller:
            _t = time.perf_counter()
            # Med personlig modell behövs AI-features för ALLA bilder — utom i
            # snabbläge, då dyr AI medvetet begränsas till topp SNABB_ANDEL.
            if args.snabb:
                andel = SNABB_ANDEL
            elif modell_paket:
                andel = 1.0
            else:
                andel = AI_KANDIDAT_ANDEL
            n_kandidater = max(1, int(len(resultat) * andel))
            if args.snabb:
                print(f"  ⚡ Snabbläge: dyr AI körs på topp {n_kandidater} "
                      f"({SNABB_ANDEL:.0%}) — resten rankas på baspoäng.",
                      flush=True)
            kandidater = sorted(resultat, key=lambda r: r["bas"],
                                reverse=True)[:n_kandidater]
            n_pose = len(modeller.get("pose_pool", []))
            print(f"\nAI-analys på topp {n_kandidater} kandidater "
                  f"(YOLO-batch + {n_pose} pose-trådar)…", flush=True)

            # AI-feature-cache (bara med personlig modell — se helpers ovan).
            anv_ai_cache = bool(modell_paket) and not args.ingen_ai_cache
            ai_ver = _ai_feat_version()
            _est_motor = args.estetik_motor if args.estetik else ""
            ai_cache = ladda_ai_cache() if anv_ai_cache else {}
            n_cache = 0

            kvar = []
            for r in kandidater:
                if anv_ai_cache:
                    try:
                        post = ai_cache.get(_ai_cache_nyckel(
                            r["fil"], ai_ver, sport, _est_motor))
                    except OSError:
                        post = None
                    # Cachad UTAN OCR men vi bevakar nummer nu → analysera om
                    # (annars skulle tröjnummer-detekteringen tyst hoppas över).
                    if post is not None and bevaka and not post.get("_ocr"):
                        post = None
                    if post is not None:
                        for k in AI_FEAT_KEYS:
                            r[k] = post.get(k, 0.0)
                        # Tröjnummer från cachade avlästa nummer (slipper OCR).
                        r["_nummer"] = post.get("_nummer", [])
                        r["trojnummer"] = (0.12 if bevaka
                                           and set(r["_nummer"]) & bevaka else 0.0)
                        n_cache += 1
                        continue
                kvar.append(r)

            if n_cache:
                print(f"  {n_cache} kandidater från AI-cache, "
                      f"{len(kvar)} analyseras.", flush=True)

            # Kandidater som behöver AI och saknar preview — extrahera nu.
            saknar = [r for r in kvar if not r["_jpg"]]
            if saknar:
                _t = time.perf_counter()
                pm = extrahera_previews_batch([r["fil"] for r in saknar], tmp)
                for r in saknar:
                    r["_jpg"] = pm.get(r["fil"])
                tider_fas["AI:extrahering"] = time.perf_counter() - _t

            _t = time.perf_counter()
            imgs, ref_lista = [], []
            for r in kvar:
                if not r["_jpg"]:
                    continue
                img = cv2.imread(str(r["_jpg"]))
                if img is None:
                    continue
                h, w = img.shape[:2]
                if max(h, w) > 1600:
                    s = 1600 / max(h, w)
                    img = cv2.resize(img, (int(w * s), int(h * s)))
                imgs.append(img)
                ref_lista.append(r)
            if kvar:
                tider_fas["AI:avkodning"] = time.perf_counter() - _t

            # CLIP-text-features (sport-specifika prompter) byggs en gång.
            clip_text = None
            if modeller.get("clip") is not None:
                from cull import clip_lager
                try:
                    clip_text = clip_lager.bygg_text_features(
                        modeller["clip"], sport)
                except Exception:
                    clip_text = None

            if imgs:
                from cull.ai_lager import bonus_batch
                ai_tider = {}
                # OCR (tröjnummer) bara på topp-kandidaterna efter baspoäng —
                # täcker slututvalet med marginal utan att OCR:a hela uppdraget.
                n_behall_ung = args.topp or max(1, round(len(resultat) * args.andel))
                ocr_max = max(60, 3 * n_behall_ung)
                bonus_batch(imgs, ref_lista, modeller,
                            args.hemma_farg, bevaka, batch_storlek=16,
                            progress_cb=lambda klar, tot:
                                print(f"  AI …{klar}/{tot}", flush=True),
                            clip_text=clip_text, tider=ai_tider, ocr_max=ocr_max)
                for k, v in sorted(ai_tider.items(), key=lambda kv: -kv[1]):
                    tider_fas[k] = v
                    print(f"  · {k:<14} {v:5.1f} s", flush=True)

                # Vision-estetik → nima-slot, skalad −1..1 → 1..10 (jämförbar
                # med NIMA för percentil-bonusen och modellen).
                if args.estetik and args.estetik_motor == "vision":
                    from cull import vision_lager as _vis
                    _tv = time.perf_counter()
                    _vtot = len(ref_lista)
                    for _vi, r in enumerate(ref_lista, 1):
                        jpg = r.get("_jpg")
                        try:
                            sc = _vis.estetik_poang(jpg) if jpg else None
                        except Exception:
                            sc = None
                        if sc is not None:
                            r["nima"] = (sc[0] + 1.0) * 4.5 + 1.0
                        if _vi % 200 == 0 or _vi == _vtot:
                            print(f"  Vision-estetik …{_vi}/{_vtot}", flush=True)
                    tider_fas["AI:Vision-estetik"] = time.perf_counter() - _tv

            # Spara nyberäknade AI-features till cachen (+ avlästa tröjnummer).
            if anv_ai_cache and ref_lista:
                for r in ref_lista:
                    try:
                        post = {k: r.get(k) for k in AI_FEAT_KEYS}
                        post["_nummer"] = r.get("_nummer", [])
                        post["_ocr"] = bool(bevaka)   # OCR övervägdes denna körning
                        ai_cache[_ai_cache_nyckel(
                            r["fil"], ai_ver, sport, _est_motor)] = post
                    except OSError:
                        continue
                spara_ai_cache(ai_cache)

            tider_fas["AI"] = time.perf_counter() - _t
            print(f"AI klar.", flush=True)

            # Vitbalans-/färgstick-stickprov (hud + vitpunkt) på redan
            # avkodade bilder — gratis på kalla körningar; vid cache-träff
            # avkodas ett litet stickprov ur kandidaterna.
            try:
                from cull import vitbalans
                from cull.bas import _cascades
                prov_imgs = list(imgs)
                if not prov_imgs:
                    for r in kandidater[:20]:
                        if r.get("_jpg"):
                            im = cv2.imread(str(r["_jpg"]))
                            if im is not None:
                                prov_imgs.append(im)
                ansikte_c, _ = _cascades()
                vb_rapport = vitbalans.analysera(prov_imgs, ansikte_c)
                txt = vitbalans.formattera(vb_rapport)
                if txt:
                    print("\n" + txt, flush=True)
            except Exception as e:
                print(f"  (vitbalans-analys hoppades över: {e})", flush=True)

        # Normalisera NIMA-estetik (om beräknad) över kandidaterna → bonus.
        nima_varden = [r["nima"] for r in resultat
                       if r.get("nima") is not None]
        if nima_varden:
            nl = np.percentile(nima_varden, 5)
            nh = np.percentile(nima_varden, 95)
            nspann = max(nh - nl, 1e-6)
        for r in resultat:
            if r.get("nima") is not None and nima_varden:
                r["estetik"] = float(
                    np.clip((r["nima"] - nl) / nspann, 0, 1)) * 0.15
            else:
                r["estetik"] = 0.0

        # Slutpoäng — personlig modell om tränad, annars handsatta vikter.
        if modell_paket:
            inlarning.poangsatt_med_modell(resultat, modell_paket, sport=sport)
            # Behåll matchfas som liten additiv knuff ovanpå modellpoängen.
            for r in resultat:
                r["poang"] += r["fas"]
        else:
            for r in resultat:
                ogon_b = 0.0
                if r["ansikten"] > 0:
                    ogon_b = min(r["ogon"] / (r["ansikten"] * 2), 1.0) * 0.10
                r["poang"] = (
                    0.55 * r["skarpa_n"]
                    + 0.35 * r["exp"]
                    + ogon_b
                    + r["armar"]
                    + r["boll"]
                    + r["hemma"]
                    + r["trojnummer"]
                    + r["klunga"]
                    + r["fas"]
                    + r["estetik"]
                )

        # Firande-boost: varje steg (±1) lägger till/drar av 0.05 × firandesignal.
        if args.firande_boost != 0 and args.ai:
            boost_per_steg = 0.05
            for r in resultat:
                firande_signal = r.get("armar", 0.0) + r.get("klunga", 0.0)
                r["poang"] += args.firande_boost * boost_per_steg * firande_signal

        # Väst-straff: bilder med uppvärmningsvästar trycks ned visuellt.
        if args.ai:
            for r in resultat:
                n_vast = r.get("vast", 0)
                if n_vast > 0:
                    r["poang"] -= 0.08 * min(n_vast, 3)

        # Burst-gruppering
        har_tid = all(matchfas.parse_tid(r["tid"]) is not None
                      for r in resultat)
        if har_tid:
            resultat.sort(key=lambda r: matchfas.parse_tid(r["tid"]))
            grupp, forra = 0, None
            for r in resultat:
                t = matchfas.parse_tid(r["tid"])
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

        valda = sorted(basta_per_grupp.values(),
                       key=lambda r: r["poang"], reverse=True)
        if len(valda) < n_behall:
            rest = sorted(
                [r for r in resultat if r not in valda],
                key=lambda r: r["poang"], reverse=True
            )
            valda += rest[:n_behall - len(valda)]
        valda = valda[:n_behall]

        # Garantiplatser: reservera platser för firande och/eller bevakade
        # tröjnummer — de bästa sådana bilderna tas in även om de inte rankar
        # in på egen hand. Slås samman så de inte tränger ut varandra.
        firande_g, bevaka_g = [], []
        if args.ai:
            valda_filer = {r["fil"] for r in valda}
            if args.garanti_firande > 0:
                firande_g = sorted(
                    [r for r in resultat if r["fil"] not in valda_filer
                     and r.get("armar", 0.0) + r.get("klunga", 0.0) > 0.0],
                    key=lambda r: r.get("armar", 0.0) + r.get("klunga", 0.0),
                    reverse=True)[:args.garanti_firande]
            if args.garanti_bevaka > 0 and bevaka:
                redan = valda_filer | {r["fil"] for r in firande_g}
                bevaka_g = sorted(
                    [r for r in resultat if r["fil"] not in redan
                     and set(r.get("_nummer", [])) & bevaka],
                    key=lambda r: r["poang"], reverse=True)[:args.garanti_bevaka]
        # Kamera-skyddade bilder tas ALLTID med, oavsett poäng/burst/topp-N.
        # Ovillkorlig garanti (ej beroende av args.ai) — kan aldrig trängas ut.
        skydd_g = []
        if skyddade:
            redan = ({r["fil"] for r in valda}
                     | {r["fil"] for r in firande_g + bevaka_g})
            skydd_g = [r for r in resultat
                       if r["fil"] in skyddade and r["fil"] not in redan]
        garanterade = firande_g + bevaka_g + skydd_g
        if garanterade:
            g_filer = {r["fil"] for r in garanterade}
            behalls = sorted([r for r in valda if r["fil"] not in g_filer],
                             key=lambda r: r["poang"], reverse=True)
            valda = behalls[:max(0, n_behall - len(garanterade))] + garanterade
            delar = ([f"{len(firande_g)} firande"] if firande_g else []) + \
                    ([f"{len(bevaka_g)} på bevakat nummer"] if bevaka_g else []) + \
                    ([f"{len(skydd_g)} skyddade"] if skydd_g else [])
            print(f"Garantiplatser: {', '.join(delar)} tillagd(a).")

        print(f"\nBehåller {len(valda)} av {n_total} "
              f"({len(basta_per_grupp)} burst-grupper).\n")
        print("Topp-urval:")
        for r in sorted(valda, key=lambda r: r["poang"], reverse=True)[:40]:
            ai_rad = ""
            if args.ai:
                ai_rad = (f"  fira={r['armar']:.2f}"
                          f"  klunga={r['klunga']:.2f}"
                          f"  boll={'ja' if r['boll'] else 'nej'}"
                          f"  nr={'ja' if r['trojnummer'] else 'nej'}"
                          f"  fas={r['fas']:.2f}")
                if args.estetik and r.get("nima") is not None:
                    ai_rad += f"  nima={r['nima']:.1f}"
            print(f"  {r['poang']:.3f}  sk {r['skarpa_n']:.2f}  "
                  f"exp {r['exp']:.2f}  ans {r['ansikten']}{ai_rad}  "
                  f"{r['fil'].name}")

        if args.rapport:
            # Spara facit-underlag även i rapportläge: poängsätt hela tagningen
            # (snabbt vid cache-träff) och dumpa features utan att kopiera/
            # exportera — perfekt "lär tagning" inför Lär av match.
            if args.ai or modell_paket:
                _spara_facit_underlag(resultat, args, sport)
            _skriv_tidrapport(tider_fas)
            print("\n(Rapportläge — inget kopierades.)")
            return

        def _sanera(s):
            return s.replace("/", "-").replace(":", ".").strip()

        if args.export_rot:
            # Struktur: <rot>/<matchinfo>/<kameratyp>/
            rot = Path(args.export_rot).expanduser()
            match_namn = _sanera(args.ut_namn) if args.ut_namn else \
                (katalog.parent.name or katalog.name)
            kam = _kameratyp(nef_filer, _exif_env()) or katalog.name
            bas_dir = rot / match_namn
            ut_dir = bas_dir / kam
            if ut_dir.exists():
                if args.export_overskriv:
                    _rmtree_kraft(ut_dir)
                    print(f"  (skriver över befintlig mapp {ut_dir})", flush=True)
                else:
                    i = 2   # finns redan → Z8, Z8 2, Z8 3, …
                    while (bas_dir / f"{kam} {i}").exists():
                        i += 1
                    ut_dir = bas_dir / f"{kam} {i}"
            try:
                ut_dir.mkdir(parents=True)
            except OSError as e:
                sys.exit(f"Kan inte skapa exportmappen {ut_dir}: {e}. "
                         f"Är export-disken ansluten och skrivbar?")
            print(f"Exporterar till: {ut_dir}", flush=True)
        else:
            if args.ut_namn:
                ut_dir = katalog / _sanera(args.ut_namn)
            else:
                ut_dir = katalog / "urval"
            if ut_dir.exists():
                if args.export_overskriv:
                    _rmtree_kraft(ut_dir)
                    print(f"  (skriver över befintlig mapp {ut_dir})", flush=True)
                else:
                    i = 2   # finns redan → urval, urval 2, urval 3, …
                    bas = ut_dir.name
                    while (katalog / f"{bas} {i}").exists():
                        i += 1
                    ut_dir = katalog / f"{bas} {i}"
            ut_dir.mkdir()

        husstil = xmp_writer.las_preset(args.husstil) if args.husstil else None
        if args.husstil and husstil is None:
            print(f"  Varning: kunde inte läsa husstil-preset {args.husstil} "
                  "— hoppar över.", flush=True)
        elif husstil:
            print(f"  Husstil: bakar in {Path(args.husstil).stem} i sidecars."
                  + (f" Exp-knuff {args.exp_bump:+.2f} EV." if args.exp_bump else ""),
                  flush=True)
        gör_xmp = args.xmp or args.xmp_justering or husstil or args.exp_bump

        # XMP, bildtext-AI och leverans behöver previews — extrahera de som saknar.
        if gör_xmp or args.bildtext_ai or args.leverans:
            saknar = [r for r in valda if not r["_jpg"]]
            if saknar:
                pm = extrahera_previews_batch([r["fil"] for r in saknar], tmp)
                for r in saknar:
                    r["_jpg"] = pm.get(r["fil"])

        # Justeringsdata (exponering per bild + uppdrags-gemensam WB-korr).
        _vb = ansikte_c = None
        as_shot = {}
        iso_karta = {}
        delta_k = delta_tint = 0.0
        if args.xmp_justering:
            from cull import vitbalans as _vb
            from cull.bas import _cascades as _csc
            ansikte_c, _ = _csc()
            delta_k, delta_tint = _vb.korrigering(vb_rapport)
            env_wb = os.environ.copy()
            for _p in ("/opt/homebrew/bin", "/usr/local/bin"):
                if _p not in env_wb.get("PATH", "").split(os.pathsep):
                    env_wb["PATH"] = _p + os.pathsep + env_wb.get("PATH", "")
            as_shot = _as_shot_kelvin_batch([r["fil"] for r in valda], env_wb)
            if delta_k or delta_tint:
                print(f"  XMP-WB: as-shot {delta_k:+.0f}K, tint {delta_tint:+.0f} "
                      f"(uppmätt färgstick).", flush=True)

        # ISO-brus = egen opt-in (av i DXO-flöden där DXO avbrusar).
        if args.xmp_brus:
            iso_karta = _iso_batch([r["fil"] for r in valda
                                    if r["fil"].suffix.lower() in RAW_SUFFIX],
                                   _exif_env())

        print(f"\nExporterar {len(valda)} filer (kopierar + XMP)…", flush=True)
        _t = time.perf_counter()
        vision_n = [0]
        gyro_n = [0]
        dampad_n = [0]
        roll_karta = (_roll_batch([r["fil"] for r in valda
                                   if r["fil"].suffix.lower() in RAW_SUFFIX],
                                  _exif_env()) if (args.xmp or args.leverans) else {})
        rating_karta = _stjarnor_av_poang(valda) if args.stjarnor else {}
        # Färgetikett på de kamera-skyddade bilderna i urvalet (skyddade läses
        # på källkortet före kopiering eftersom uchg-flaggan inte följer med).
        label_karta = {r["fil"]: SKYDD_LABEL for r in valda
                       if r["fil"] in skyddade}
        for i, r in enumerate(valda, 1):
            _mål = ut_dir / r["fil"].name
            shutil.copy2(r["fil"], _mål)
            # shutil.copy2 bevarar st_flags på macOS → kamerans uchg-lås skulle
            # annars ärvas till exporten och göra den oraderbar. Rensa det.
            try:
                os.chflags(_mål, 0)
            except (OSError, AttributeError):
                pass
            rating = rating_karta.get(r["fil"])
            label = label_karta.get(r["fil"])
            if gör_xmp or rating is not None or label is not None:
                img = cv2.imread(str(r["_jpg"])) if r["_jpg"] else None
                crop = None
                vinkel = 0.0
                exposure = temperatur = tint = None
                if args.xmp:
                    # Upprätning (gyro/Vision/Hough), dämpad om motivet annars
                    # beskärs för hårt (estetik > perfekt vinkel).
                    vinkel, motor = _uppratningsvinkel(
                        r.get("_jpg"), img, roll_karta.get(r["fil"]))
                    vinkel, dämpad = _rakt_bevarande(r.get("_jpg"), vinkel)
                    if motor == "vision":
                        vision_n[0] += 1
                    elif motor == "gyro":
                        gyro_n[0] += 1
                    if dämpad:
                        dampad_n[0] += 1
                if img is not None:
                    if args.xmp_justering:
                        exposure = _vb.ansikts_exponering_ev(img, ansikte_c)
                        # Absolut WB (Kelvin) gäller bara raw — för JPG använder
                        # Lightroom relativa reglage, så hoppa över WB där.
                        if r["fil"].suffix.lower() in RAW_SUFFIX:
                            bas_k = as_shot.get(r["fil"])
                            if (delta_k or delta_tint) and bas_k:
                                temperatur = bas_k + delta_k
                                tint = delta_tint
                # Kameraprofil (Nikon Neutral), ISO-brus och objektivkorr
                # gäller raw, inte JPG (JPG är redan kamera-processad).
                # Med husstil styr presetets Look profilen → sätt inte Neutral.
                är_raw = r["fil"].suffix.lower() in RAW_SUFFIX
                profil = ("Camera Neutral"
                          if är_raw and not husstil else None)
                iso = objektiv = None
                if är_raw:
                    if args.xmp_brus:          # ISO-brus = egen opt-in (DXO-flöden)
                        iso = iso_karta.get(r["fil"])
                    if args.xmp_justering:     # objektivkorr ingår i leveransklar
                        objektiv = True
                if (args.xmp or husstil or args.exp_bump
                        or exposure is not None or temperatur is not None
                        or iso is not None or rating is not None
                        or label is not None):
                    xmp_writer.skriv_xmp(ut_dir / r["fil"].name,
                                         crop=crop, vinkel=vinkel,
                                         exposure=exposure,
                                         temperatur=temperatur, tint=tint,
                                         profil=profil,
                                         iso=iso, objektiv=bool(objektiv),
                                         preset=husstil, exp_bump=args.exp_bump,
                                         rating=rating, label=label)
            else:
                xmp = r["fil"].with_suffix(".xmp")
                if xmp.exists():
                    shutil.copy2(xmp, ut_dir / xmp.name)
            if i % 3 == 0 or i == len(valda):
                print(f"  kopierar …{i}/{len(valda)}", flush=True)
        tider_fas["Export"] = time.perf_counter() - _t
        if rating_karta:
            from collections import Counter
            f = Counter(rating_karta.values())
            print("  Stjärnor: " + "  ".join(f"{s}★×{f[s]}"
                  for s in (5, 4, 3, 2) if f.get(s)), flush=True)
        if args.xmp and (gyro_n[0] or vision_n[0]):
            hough_n = len(valda) - gyro_n[0] - vision_n[0]
            print(f"  Upprätning: {gyro_n[0]} via kamerans gyro (RollAngle), "
                  f"{vision_n[0]} via Vision-horisont, {hough_n} via Hough."
                  + (f" Dämpad på {dampad_n[0]} (bevarar motivet)."
                     if dampad_n[0] else ""), flush=True)

        # IPTC-bildtexter på de exporterade filerna (match-gemensam metadata,
        # + spelarnamn per bild om en roster är angiven).
        namn_per_fil = bildtext_per_fil = None   # delas med leverans nedan
        if args.iptc:
            print("Skriver IPTC-bildtexter…", flush=True)
            _t = time.perf_counter()
            kopierade = [ut_dir / r["fil"].name for r in valda]
            rost = {}
            if args.roster:
                from cull import roster as _roster
                rost = _roster.las_roster(args.roster)
                if rost:
                    namn_per_fil = {ut_dir / r["fil"].name:
                                    _roster.namnge(rost, r.get("_nummer", []))
                                    for r in valda}
                    n_namn = sum(1 for v in namn_per_fil.values() if v)
                    print(f"  Roster: {len(rost)} spelare, namn på {n_namn} bilder "
                          "(via OCR) + AI matchar resten.", flush=True)
            bildtext_per_fil = None
            if args.bildtext_ai:
                from cull import roster as _roster
                from cull import bildtext_ai
                lag = (args.ut_namn or "").split(" - ")[0].strip()
                jobb = [{"id": ut_dir / r["fil"].name,
                         "jpg": r.get("_jpg"),
                         "nummer": r.get("_nummer", []),
                         "namn": (namn_per_fil or {}).get(ut_dir / r["fil"].name, "")}
                        for r in valda]
                bildtext_per_fil = bildtext_ai.generera_bildtexter(
                    jobb, args.ut_namn, sport, args.hemma_farg,
                    args.bildtext_modell, print,
                    roster_text=_roster.lista_text(rost), roster_lag=lag)
            n_iptc = _skriv_iptc(kopierade, args.ut_namn, sport,
                                 args.fotograf, _exif_env(), namn_per_fil,
                                 bildtext_per_fil)
            tider_fas["IPTC"] = time.perf_counter() - _t
            print(f"IPTC-bildtexter skrivna på {n_iptc} filer."
                  if n_iptc else
                  "IPTC hoppades över (matchinfo saknas?).", flush=True)

        # Stjärnbetyg inbäddat i filerna (Lightroom läser xmp:Rating därifrån).
        if rating_karta:
            nr = _skriv_rating_exiftool(rating_karta, ut_dir, _exif_env())
            print(f"  Stjärnbetyg inbäddat i {nr} filer.", flush=True)

        # Färgetikett inbäddad på de skyddade bilderna (LR läser xmp:Label
        # ur inbäddad metadata för raw, precis som betyget).
        if label_karta:
            nl = _skriv_label_exiftool(label_karta, SKYDD_LABEL, ut_dir,
                                       _exif_env())
            print(f"  {SKYDD_LABEL}-etikett (protect) inbäddad i {nl} filer.",
                  flush=True)

        # Leveransfärdiga JPEG (snabbflöde) enligt profil — gyro-rätat, skalat,
        # komprimerat, med IPTC/bildtext på leverans-JPEG:erna.
        if args.leverans:
            from cull import leverans as _lev
            prof = _lev.PROFILER.get(args.leverans.upper())
            if not prof:
                print(f"  Okänd leveransprofil: {args.leverans} "
                      f"(finns: {', '.join(_lev.PROFILER)}).", flush=True)
            else:
                prof = dict(prof, _namn=args.leverans.upper())
                lev_dir = ut_dir / f"_leverans_{args.leverans.upper()}"
                jobb = [{"namn": r["fil"].stem, "jpg": r.get("_jpg"),
                         "vinkel": roll_karta.get(r["fil"]),
                         "poang": r.get("poang", 0.5)} for r in valda]
                skapade = _lev.exportera(
                    jobb, lev_dir, prof, print,
                    claude=getattr(args, "instagram_ai", False),
                    matchinfo=(args.ut_namn or ""))
                if args.iptc and skapade:
                    npf = {lev_dir / f"{r['fil'].stem}.jpg":
                           (namn_per_fil or {}).get(ut_dir / r["fil"].name, "")
                           for r in valda}
                    bpf = {lev_dir / f"{r['fil'].stem}.jpg":
                           (bildtext_per_fil or {}).get(ut_dir / r["fil"].name, "")
                           for r in valda}
                    _skriv_iptc(skapade, args.ut_namn, sport, args.fotograf,
                                _exif_env(),
                                {k: v for k, v in npf.items() if v} or None,
                                {k: v for k, v in bpf.items() if v} or None)
                print(f"  Leverans klar: {lev_dir}", flush=True)

        # Aktiv inlärning + körningslogg (kräver previews i tmp → inom with-blocket)
        if modell_paket:
            _spara_aktiv_inlarning(resultat, katalog)
        _logga_korning(katalog, ut_dir, resultat, valda)
        # Träningsunderlag: spara features för hela tagningen när AI/modell körts
        # (annars är features tomma). Märks senare med PM-urvalet via "Lär av match".
        if args.ai or modell_paket:
            _spara_facit_underlag(resultat, args, sport)

    # Tidrapport
    _skriv_tidrapport(tider_fas)

    print(f"\nKlart. {len(valda)} NEF kopierade till: {ut_dir}")
    if args.xmp:
        print("XMP-sidecars skrivna med upprätning.")
    if args.xmp_justering:
        print("XMP-sidecars med exponering/WB skrivna.")

    # Lightroom öppnas mot matchroten (matchinfo-mappen) — med export-rot är
    # det ut_dir.parent (ovanför kameramappen), annars urvalsmappen själv.
    lr_mapp = ut_dir.parent if args.export_rot else ut_dir
    kopierade = [ut_dir / r["fil"].name for r in valda]
    oppna_resultat(ut_dir, lr_mapp, kopierade, args.oppna)
    if args.oppna == "dxo" and _hitta_dxo():
        print(f"Öppnar {len(kopierade)} filer i DxO PureRAW.")
    elif _hitta_lightroom() and args.oppna in ("auto", "lightroom"):
        print(f"Öppnar matchen i Lightroom: {lr_mapp}")
    else:
        print("Öppnar urvalsmappen.")


def _main_safe():
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print("\n--- FELINFORMATION ---", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    _main_safe()
