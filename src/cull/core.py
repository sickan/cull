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


def kontrollera_exiftool():
    if shutil.which("exiftool") is None:
        sys.exit("Saknar exiftool. Kör: brew install exiftool")


def extrahera_previews_batch(nef_filer, ut_dir):
    """
    Extraherar previews från alla NEF i ett fåtal exiftool-anrop.
    Returnerar dict: nef_path -> jpg_path (eller None om misslyckades).
    """
    ut_dir = Path(ut_dir)
    fmt = str(ut_dir / "%f.jpg")

    def kör(filer, tag):
        # Max ~500 filer per anrop för att undvika ARG_MAX
        for i in range(0, len(filer), 500):
            subprocess.run(
                ["exiftool", "-b", tag, "-w!", fmt,
                 *[str(f) for f in filer[i:i + 500]]],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Pass 1: JpgFromRaw (full preview på Nikon)
    kör(nef_filer, "-JpgFromRaw")

    # Pass 2: PreviewImage för de som saknas eller är för små
    saknas = [n for n in nef_filer
              if not (ut_dir / (n.stem + ".jpg")).exists()
              or (ut_dir / (n.stem + ".jpg")).stat().st_size < 10_000]
    if saknas:
        kör(saknas, "-PreviewImage")

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
    return nef, p


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
    args = ap.parse_args()

    kontrollera_exiftool()
    katalog = Path(args.katalog).expanduser()
    if not katalog.is_dir():
        sys.exit(f"Hittar inte katalogen: {katalog}")

    nef_filer = sorted(p for p in katalog.iterdir() if p.suffix.lower() == ".nef")
    if not nef_filer:
        sys.exit("Inga NEF-filer i katalogen.")

    bevaka = set(args.bevaka.split(",")) if args.bevaka else set()

    if args.ai:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)

    print(f"{len(nef_filer)} NEF hittade.", flush=True)

    # --- Ladda AI-modeller ---
    modeller = None
    if args.ai:
        from cull import ai_lager
        print("Laddar AI-modeller…", flush=True)
        modeller = ai_lager.ladda_modeller(med_ocr=bool(bevaka))
        print("AI-modeller redo.\n", flush=True)

    # --- Metadata (tidsstämplar) ---
    print("Hämtar metadata…", flush=True)
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
                print(f"Avspark {args.avspark} — matchfas-bonus aktiv.", flush=True)

    # --- Fas 1: Batch-extrahering av previews ---
    print(f"\nExtraherar previews (batch)…", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        preview_map = extrahera_previews_batch(nef_filer, tmp)
        giltiga = [(nef, jpg) for nef, jpg in preview_map.items() if jpg]
        print(f"{len(giltiga)} previews extraherade "
              f"({len(nef_filer) - len(giltiga)} saknade).\n", flush=True)

        # --- Fas 2: Parallell baspoängsättning ---
        print(f"Baspoängsätter med {N_WORKERS} trådar…", flush=True)
        resultat = []
        klar = 0

        with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
            futures = {ex.submit(_score_en, (nef, jpg)): nef
                       for nef, jpg in giltiga}
            for future in as_completed(futures):
                nef, p = future.result()
                klar += 1
                print(f"  …{klar}/{len(giltiga)}", flush=True)
                if p is None:
                    continue
                tid_str = tider.get(nef.name, "")
                fas_b = 0.0
                if avspark_ts and tid_str:
                    ts = matchfas.parse_tid(tid_str)
                    if ts:
                        fas_b = matchfas.fas_bonus(
                            matchfas.matchminut(ts, avspark_ts))
                p.update({
                    "armar": 0.0, "boll": 0.0, "hemma": 0.0,
                    "trojnummer": 0.0, "_yolo": None,
                    "fas": fas_b, "fil": nef, "tid": tid_str,
                    "_jpg": jpg,
                })
                resultat.append(p)

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
            n_kandidater = max(1, int(len(resultat) * AI_KANDIDAT_ANDEL))
            kandidater = sorted(resultat, key=lambda r: r["bas"],
                                reverse=True)[:n_kandidater]
            print(f"\nAI-analys på topp {n_kandidater} kandidater "
                  f"(batch-YOLO + MediaPipe)…", flush=True)

            imgs  = []
            for r in kandidater:
                img = cv2.imread(str(r["_jpg"]))
                if img is not None:
                    h, w = img.shape[:2]
                    if max(h, w) > 1600:
                        s = 1600 / max(h, w)
                        img = cv2.resize(img, (int(w * s), int(h * s)))
                imgs.append(img)

            from cull.ai_lager import bonus_batch
            bonus_batch(imgs, kandidater, modeller,
                        args.hemma_farg, bevaka, batch_storlek=16)
            print(f"AI klar.", flush=True)

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
                + r["fas"]
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
                ai_rad = (f"  armar={'ja' if r['armar'] else 'nej'}"
                          f"  boll={'ja' if r['boll'] else 'nej'}"
                          f"  nr={'ja' if r['trojnummer'] else 'nej'}"
                          f"  fas={r['fas']:.2f}")
            print(f"  {r['poang']:.3f}  sk {r['skarpa_n']:.2f}  "
                  f"exp {r['exp']:.2f}  ans {r['ansikten']}{ai_rad}  "
                  f"{r['fil'].name}")

        if args.rapport:
            print("\n(Rapportläge — inget kopierades.)")
            return

        ut_dir = katalog / "urval"
        if ut_dir.exists():
            i = 1
            while (katalog / f"urval {i}").exists():
                i += 1
            ut_dir = katalog / f"urval {i}"
        ut_dir.mkdir()

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

    print(f"\nKlart. {len(valda)} NEF kopierade till: {ut_dir}")
    if args.xmp:
        print("XMP-sidecars skrivna med beskärning och upprätnning.")


if __name__ == "__main__":
    main()
