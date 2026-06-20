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

# Antal CPU-kärnor att använda för parallell baspoängsättning
N_WORKERS = min(os.cpu_count() or 4, 8)
# Andel av bilderna (sorterade på baspoäng) som AI körs på
AI_KANDIDAT_ANDEL = 0.5

# Cache för baspoäng — nyckel = sökväg|mtime|storlek (oföränderlig per NEF)
import json
BAS_CACHE_PATH = Path.home() / ".cache" / "cull" / "bas_cache.json"


def _cache_nyckel(nef):
    st = nef.stat()
    return f"{nef}|{int(st.st_mtime)}|{st.st_size}"


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
        list(ex.map(extrahera_en, nef_filer))

    return {
        nef: (ut_dir / (nef.stem + ".jpg"))
        if (ut_dir / (nef.stem + ".jpg")).exists()
           and (ut_dir / (nef.stem + ".jpg")).stat().st_size > 10_000
        else None
        for nef in nef_filer
    }


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


def main():
    ap = argparse.ArgumentParser(prog="cull",
                                 description="Teknisk culling av NEF-filer.")
    ap.add_argument("katalog")
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
    args = ap.parse_args()

    kontrollera_exiftool()
    katalog = Path(args.katalog).expanduser()
    if not katalog.is_dir():
        sys.exit(f"Hittar inte katalogen: {katalog}")

    # Exkludera macOS AppleDouble-sidecars (._namn.NEF) och andra dolda
    # filer som dyker upp på exFAT/FAT-diskar — de är inte riktiga bilder.
    nef_filer = sorted(p for p in katalog.iterdir()
                       if p.suffix.lower() == ".nef"
                       and not p.name.startswith("."))
    if not nef_filer:
        sys.exit("Inga NEF-filer i katalogen.")

    bevaka = set(args.bevaka.split(",")) if args.bevaka else set()

    print(f"{len(nef_filer)} NEF hittade.", flush=True)

    # --- Ladda AI-modeller ---
    modeller = None
    if args.ai:
        from cull import ai_lager
        print("Laddar AI-modeller…", flush=True)
        modeller = ai_lager.ladda_modeller(med_ocr=bool(bevaka),
                                           yolo_modell=args.yolo,
                                           med_estetik=args.estetik)
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
        print("  ✓ XMP-sidecars (crop + upprätnning)", flush=True)
    n_behall_est = args.topp if args.topp else f"~{int(len(nef_filer) * args.andel)}"
    print(f"  Urval: {n_behall_est} bilder av {len(nef_filer)}\n", flush=True)

    tider_fas = {}   # tidmätning per fas

    # --- Metadata (tidsstämplar) ---
    print("Hämtar metadata…", flush=True)
    _t = time.perf_counter()
    tider = hamta_metadata(nef_filer)

    avspark_ts = None
    if args.avspark:
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
        d = dict(p)
        d.update({
            "armar": 0.0, "boll": 0.0, "hemma": 0.0,
            "trojnummer": 0.0, "klunga": 0.0, "_yolo": None,
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

        # --- Fas 3: AI på topp 50 % ---
        if args.ai and modeller:
            _t = time.perf_counter()
            n_kandidater = max(1, int(len(resultat) * AI_KANDIDAT_ANDEL))
            kandidater = sorted(resultat, key=lambda r: r["bas"],
                                reverse=True)[:n_kandidater]
            n_pose = len(modeller.get("pose_pool", []))
            print(f"\nAI-analys på topp {n_kandidater} kandidater "
                  f"(YOLO-batch + {n_pose} pose-trådar)…", flush=True)

            # Kandidater från cachen saknar extraherad preview — fixa nu.
            saknar = [r for r in kandidater if not r["_jpg"]]
            if saknar:
                pm = extrahera_previews_batch([r["fil"] for r in saknar], tmp)
                for r in saknar:
                    r["_jpg"] = pm.get(r["fil"])

            imgs, ref_lista = [], []
            for r in kandidater:
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

            from cull.ai_lager import bonus_batch
            bonus_batch(imgs, ref_lista, modeller,
                        args.hemma_farg, bevaka, batch_storlek=16,
                        progress_cb=lambda klar, tot:
                            print(f"  AI …{klar}/{tot}", flush=True))
            tider_fas["AI"] = time.perf_counter() - _t
            print(f"AI klar.", flush=True)

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

        # Slutpoäng
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
            if tider_fas:
                print("\nTid per fas:")
                for fas, sek in tider_fas.items():
                    print(f"  {fas:<16} {sek:5.1f} s")
                print(f"  {'Totalt':<16} {sum(tider_fas.values()):5.1f} s")
            print("\n(Rapportläge — inget kopierades.)")
            return

        ut_dir = katalog / "urval"
        if ut_dir.exists():
            i = 1
            while (katalog / f"urval {i}").exists():
                i += 1
            ut_dir = katalog / f"urval {i}"
        ut_dir.mkdir()

        # XMP behöver previews — extrahera för valda som saknar (cacheträffar).
        if args.xmp:
            saknar = [r for r in valda if not r["_jpg"]]
            if saknar:
                pm = extrahera_previews_batch([r["fil"] for r in saknar], tmp)
                for r in saknar:
                    r["_jpg"] = pm.get(r["fil"])

        for r in valda:
            shutil.copy2(r["fil"], ut_dir / r["fil"].name)
            if args.xmp:
                img = cv2.imread(str(r["_jpg"]))
                if img is not None:
                    crop   = xmp_writer.berakna_crop(r["_yolo"], img.shape)
                    vinkel = xmp_writer.berakna_uppratning(img)
                    xmp_writer.skriv_xmp(ut_dir / r["fil"].name,
                                         crop=crop, vinkel=vinkel)
            else:
                xmp = r["fil"].with_suffix(".xmp")
                if xmp.exists():
                    shutil.copy2(xmp, ut_dir / xmp.name)

    # Tidrapport
    if tider_fas:
        print("\nTid per fas:")
        for fas, sek in tider_fas.items():
            print(f"  {fas:<16} {sek:5.1f} s")
        print(f"  {'Totalt':<16} {sum(tider_fas.values()):5.1f} s")

    print(f"\nKlart. {len(valda)} NEF kopierade till: {ut_dir}")
    if args.xmp:
        print("XMP-sidecars skrivna med beskärning och upprätnning.")

    subprocess.Popen(["open", str(ut_dir)])


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
