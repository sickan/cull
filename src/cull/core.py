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


def _ai_cache_nyckel(nef, ver, sport=""):
    # CLIP-features beror på sporten (promptmallar) → ingår i nyckeln.
    return f"{_cache_nyckel(nef)}|v{ver}|{sport or ''}"


def ladda_ai_cache():
    try:
        with open(AI_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def spara_ai_cache(cache):
    try:
        AI_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AI_CACHE_PATH, "w") as f:
            json.dump(cache, f)
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


def _skriv_iptc(nef_paths, matchinfo, sport, fotograf, env):
    """Skriver match-gemensam IPTC/XMP-metadata till alla exporterade NEF:er."""
    if not nef_paths or not (matchinfo or "").strip():
        return 0
    md = _iptc_metadata(matchinfo, sport)
    cmd = ["exiftool", "-overwrite_original", "-sep", ", ",
           f"-XMP-dc:Description={md['caption']}",
           f"-IPTC:Caption-Abstract={md['caption']}",
           f"-XMP-photoshop:Headline={md['caption']}"]
    if md["keywords"]:
        kw = ", ".join(md["keywords"])
        cmd += [f"-XMP-dc:Subject={kw}", f"-IPTC:Keywords={kw}"]
    if md["arena"]:
        cmd += [f"-XMP-Iptc4xmpCore:Location={md['arena']}",
                f"-IPTC:Sub-location={md['arena']}"]
    if md["datum"]:
        cmd += [f"-XMP-photoshop:DateCreated={md['datum']}",
                f"-IPTC:DateCreated={md['datum'].replace(':', '')}"]
    if fotograf:
        cmd += [f"-XMP-dc:Creator={fotograf}", f"-IPTC:By-line={fotograf}"]
    cmd += [str(p) for p in nef_paths]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return len(nef_paths) if r.returncode == 0 else 0
    except Exception:
        return 0


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
                    help="lägg till NIMA-estetikbetyg (kräver pyiqa)")
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
    ap.add_argument("--export-overskriv", action="store_true",
                    help="skriv över befintlig urvalsmapp istället för att räkna "
                         "upp (Z8 2, Z8 3 …) — undviker dubblettmappar vid omkörning")
    ap.add_argument("--iptc", action="store_true",
                    help="skriv IPTC-bildtexter (match/datum/lag/arena) i filerna")
    ap.add_argument("--fotograf", default=None, metavar="NAMN",
                    help="fotografens namn → IPTC By-line/Creator (med --iptc)")
    ap.add_argument("--xmp-justering", action="store_true",
                    help="skriv exponering + WB/tint i XMP (från ansikts-"
                         "exponering och uppmätt färgstick)")
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

    # Exkludera macOS AppleDouble-sidecars (._namn.NEF) och andra dolda
    # filer som dyker upp på exFAT/FAT-diskar — de är inte riktiga bilder.
    nef_filer = sorted(p for p in katalog.iterdir()
                       if p.suffix.lower() in BILD_SUFFIX
                       and not p.name.startswith("."))
    if not nef_filer:
        sys.exit("Inga bildfiler i katalogen (raw: NEF/DNG/CR3/ARW/RAF/RW2/ORF "
                 "eller JPG).")

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
        modeller = ai_lager.ladda_modeller(med_ocr=bool(bevaka),
                                           yolo_modell=args.yolo,
                                           med_estetik=args.estetik,
                                           med_ogon=bool(modell_paket),
                                           med_clip=bool(modell_paket))
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
            ai_cache = ladda_ai_cache() if anv_ai_cache else {}
            n_cache = 0

            kvar = []
            for r in kandidater:
                if anv_ai_cache:
                    try:
                        post = ai_cache.get(_ai_cache_nyckel(r["fil"], ai_ver, sport))
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

            # Spara nyberäknade AI-features till cachen (+ avlästa tröjnummer).
            if anv_ai_cache and ref_lista:
                for r in ref_lista:
                    try:
                        post = {k: r.get(k) for k in AI_FEAT_KEYS}
                        post["_nummer"] = r.get("_nummer", [])
                        post["_ocr"] = bool(bevaka)   # OCR övervägdes denna körning
                        ai_cache[_ai_cache_nyckel(r["fil"], ai_ver, sport)] = post
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
        garanterade = firande_g + bevaka_g
        if garanterade:
            g_filer = {r["fil"] for r in garanterade}
            behalls = sorted([r for r in valda if r["fil"] not in g_filer],
                             key=lambda r: r["poang"], reverse=True)
            valda = behalls[:max(0, n_behall - len(garanterade))] + garanterade
            delar = ([f"{len(firande_g)} firande"] if firande_g else []) + \
                    ([f"{len(bevaka_g)} på bevakat nummer"] if bevaka_g else [])
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
                    shutil.rmtree(ut_dir)
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
                    shutil.rmtree(ut_dir)
                    print(f"  (skriver över befintlig mapp {ut_dir})", flush=True)
                else:
                    i = 2   # finns redan → urval, urval 2, urval 3, …
                    bas = ut_dir.name
                    while (katalog / f"{bas} {i}").exists():
                        i += 1
                    ut_dir = katalog / f"{bas} {i}"
            ut_dir.mkdir()

        gör_xmp = args.xmp or args.xmp_justering

        # XMP behöver previews — extrahera för valda som saknar (cacheträffar).
        if gör_xmp:
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
            iso_karta = _iso_batch([r["fil"] for r in valda
                                    if r["fil"].suffix.lower() in RAW_SUFFIX], env_wb)
            if delta_k or delta_tint:
                print(f"  XMP-WB: as-shot {delta_k:+.0f}K, tint {delta_tint:+.0f} "
                      f"(uppmätt färgstick).", flush=True)

        print(f"\nExporterar {len(valda)} filer (kopierar + XMP)…", flush=True)
        _t = time.perf_counter()
        for i, r in enumerate(valda, 1):
            shutil.copy2(r["fil"], ut_dir / r["fil"].name)
            if gör_xmp:
                img = cv2.imread(str(r["_jpg"])) if r["_jpg"] else None
                crop = None
                vinkel = 0.0
                exposure = temperatur = tint = None
                if img is not None:
                    if args.xmp:
                        # Beskärning struken (gav dåliga crops) — bara upprätning.
                        vinkel = xmp_writer.berakna_uppratning(img)
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
                är_raw = r["fil"].suffix.lower() in RAW_SUFFIX
                profil = "Camera Neutral" if är_raw else None
                iso = objektiv = None
                if args.xmp_justering and är_raw:
                    iso = iso_karta.get(r["fil"])
                    objektiv = True
                if (args.xmp or exposure is not None or temperatur is not None
                        or iso is not None):
                    xmp_writer.skriv_xmp(ut_dir / r["fil"].name,
                                         crop=crop, vinkel=vinkel,
                                         exposure=exposure,
                                         temperatur=temperatur, tint=tint,
                                         profil=profil,
                                         iso=iso, objektiv=bool(objektiv))
            else:
                xmp = r["fil"].with_suffix(".xmp")
                if xmp.exists():
                    shutil.copy2(xmp, ut_dir / xmp.name)
            if i % 3 == 0 or i == len(valda):
                print(f"  kopierar …{i}/{len(valda)}", flush=True)
        tider_fas["Export"] = time.perf_counter() - _t

        # IPTC-bildtexter på de exporterade filerna (match-gemensam metadata).
        if args.iptc:
            print("Skriver IPTC-bildtexter…", flush=True)
            _t = time.perf_counter()
            kopierade = [ut_dir / r["fil"].name for r in valda]
            n_iptc = _skriv_iptc(kopierade, args.ut_namn, sport,
                                 args.fotograf, _exif_env())
            tider_fas["IPTC"] = time.perf_counter() - _t
            print(f"IPTC-bildtexter skrivna på {n_iptc} filer."
                  if n_iptc else
                  "IPTC hoppades över (matchinfo saknas?).", flush=True)

        # Aktiv inlärning + körningslogg (kräver previews i tmp → inom with-blocket)
        if modell_paket:
            _spara_aktiv_inlarning(resultat, katalog)
        _logga_korning(katalog, ut_dir, resultat, valda)

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
