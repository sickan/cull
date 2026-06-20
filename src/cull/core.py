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
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
except ImportError:
    sys.exit("Saknar numpy. Kör: pip install numpy")

from cull import bas, matchfas, xmp_writer
from cull.ai_lager import FARG_NAMN


def kontrollera_exiftool():
    if shutil.which("exiftool") is None:
        sys.exit("Saknar exiftool. Kör: brew install exiftool")


def extrahera_preview(nef_path, ut_dir):
    ut = Path(ut_dir) / (Path(nef_path).stem + ".jpg")
    for tag in ("-JpgFromRaw", "-PreviewImage"):
        subprocess.run(
            ["exiftool", "-b", tag, str(nef_path)],
            stdout=open(ut, "wb"), stderr=subprocess.DEVNULL
        )
        if ut.exists() and ut.stat().st_size > 10000:
            return ut
    return None


def hamta_metadata(nef_filer):
    """Hämtar filnamn och tidsstämpel för alla NEF i ett svep."""
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


def main():
    ap = argparse.ArgumentParser(
        prog="cull",
        description="Teknisk culling av NEF-filer.",
    )
    ap.add_argument("katalog")
    ap.add_argument("--topp",       type=int,   default=None,
                    help="behåll N bästa")
    ap.add_argument("--andel",      type=float, default=0.20,
                    help="behåll denna andel (default 0.20)")
    ap.add_argument("--burst-sek",  type=float, default=2.0,
                    help="burst-gräns i sekunder (default 2.0)")
    ap.add_argument("--rapport",    action="store_true",
                    help="poängsätt utan att kopiera")
    ap.add_argument("--ai",         action="store_true",
                    help="aktivera YOLOv8 + MediaPipe")
    ap.add_argument("--hemma-farg", default=None, metavar="FÄRG",
                    help=f"hemmalagsfärg: {', '.join(FARG_NAMN)}")
    ap.add_argument("--bevaka",     default=None, metavar="9,11",
                    help="tröjnummer att prioritera (kräver --ai, easyocr)")
    ap.add_argument("--avspark",    default=None, metavar="HH:MM",
                    help="avsparktid för matchfas-bonus")
    ap.add_argument("--xmp",        action="store_true",
                    help="skriv XMP-sidecars med crop och upprätnning")
    args = ap.parse_args()

    kontrollera_exiftool()
    katalog = Path(args.katalog).expanduser()
    if not katalog.is_dir():
        sys.exit(f"Hittar inte katalogen: {katalog}")

    nef_filer = sorted(p for p in katalog.iterdir() if p.suffix.lower() == ".nef")
    if not nef_filer:
        sys.exit("Inga NEF-filer i katalogen.")

    bevaka = set(args.bevaka.split(",")) if args.bevaka else set()
    med_ocr = bool(bevaka)

    print(f"{len(nef_filer)} NEF hittade. Extraherar previews och poängsätter…")

    if args.ai:
        from cull import ai_lager
        print("Laddar AI-modeller…")
        modeller = ai_lager.ladda_modeller(med_ocr=med_ocr)
        print()

    tider = hamta_metadata(nef_filer)

    # Referensdatum för avspark (från första bildens tidsstämpel)
    avspark_ts = None
    if args.avspark:
        forsta_tid = next(
            (matchfas.parse_tid(t) for t in tider.values() if matchfas.parse_tid(t)),
            None
        )
        if forsta_tid:
            ref_dt = datetime.fromtimestamp(forsta_tid)
            avspark_ts = matchfas.parse_avspark(args.avspark, ref_dt)
            if avspark_ts:
                print(f"Avspark satt till {args.avspark} — matchfas-bonus aktiv.\n")

    resultat = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, nef in enumerate(nef_filer, 1):
            preview = extrahera_preview(nef, tmp)
            if preview is None:
                print(f"  [{i}/{len(nef_filer)}] {nef.name}: ingen preview, hoppar",
                      flush=True)
                continue
            p = bas.poangsatt(preview)
            if p is None:
                continue

            img = p.pop("_img")

            # AI-bonusar
            ai_b = {"armar": 0.0, "boll": 0.0, "hemma": 0.0,
                    "trojnummer": 0.0, "_yolo": None}
            if args.ai:
                ai_b = ai_lager.bonus(img, modeller, args.hemma_farg, bevaka)

            # Matchfas-bonus
            fas_b = 0.0
            tid_str = tider.get(nef.name, "")
            if avspark_ts and tid_str:
                ts = matchfas.parse_tid(tid_str)
                if ts:
                    fas_b = matchfas.fas_bonus(matchfas.matchminut(ts, avspark_ts))

            p.update({
                "armar":      ai_b["armar"],
                "boll":       ai_b["boll"],
                "hemma":      ai_b["hemma"],
                "trojnummer": ai_b["trojnummer"],
                "fas":        fas_b,
                "_yolo":      ai_b.get("_yolo"),
                "_img_bgr":   img if args.xmp else None,
                "fil":        nef,
                "tid":        tid_str,
            })
            resultat.append(p)
            print(f"  …{i}/{len(nef_filer)}", flush=True)

    if not resultat:
        sys.exit("Inget kunde poängsättas.")

    # Normalisera skärpa globalt
    sk = np.array([r["skarpa"] for r in resultat])
    lo, hi = np.percentile(sk, 5), np.percentile(sk, 95)
    spann = max(hi - lo, 1e-6)
    for r in resultat:
        r["skarpa_n"] = float(np.clip((r["skarpa"] - lo) / spann, 0, 1))

    # Sammanvägd poäng
    for r in resultat:
        ogon_bonus = 0.0
        if r["ansikten"] > 0:
            ogon_bonus = min(r["ogon"] / (r["ansikten"] * 2), 1.0) * 0.10
        r["poang"] = (
            0.55 * r["skarpa_n"]
            + 0.35 * r["exp"]
            + ogon_bonus
            + r["armar"]
            + r["boll"]
            + r["hemma"]
            + r["trojnummer"]
            + r["fas"]
        )

    # Burst-gruppering
    har_tid = all(matchfas.parse_tid(r["tid"]) is not None for r in resultat)
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

    valda = sorted(basta_per_grupp.values(), key=lambda r: r["poang"], reverse=True)
    if len(valda) < n_behall:
        rest = sorted(
            [r for r in resultat if r not in valda],
            key=lambda r: r["poang"], reverse=True
        )
        valda += rest[:n_behall - len(valda)]
    valda = valda[:n_behall]

    print(f"\nBehåller {len(valda)} av {n_total} ({len(basta_per_grupp)} burst-grupper).\n")
    print("Topp-urval:")
    for r in sorted(valda, key=lambda r: r["poang"], reverse=True)[:40]:
        bonusar = ""
        if args.ai or avspark_ts:
            bonusar = (
                f"  armar={'ja' if r['armar'] else 'nej'}"
                f"  boll={'ja' if r['boll'] else 'nej'}"
                f"  nr={'ja' if r['trojnummer'] else 'nej'}"
                f"  fas={r['fas']:.2f}"
            )
        print(f"  {r['poang']:.3f}  sk {r['skarpa_n']:.2f}  "
              f"exp {r['exp']:.2f}  ans {r['ansikten']}{bonusar}  {r['fil'].name}")

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

        # XMP — skriv ny sidecar med crop + upprätnning
        if args.xmp and r["_img_bgr"] is not None:
            crop   = xmp_writer.berakna_crop(r["_yolo"], r["_img_bgr"].shape)
            vinkel = xmp_writer.berakna_uppratning(r["_img_bgr"])
            xmp_writer.skriv_xmp(ut_dir / r["fil"].name, crop=crop, vinkel=vinkel)
        else:
            # Kopiera befintlig XMP-sidecar om den finns
            xmp = r["fil"].with_suffix(".xmp")
            if xmp.exists():
                shutil.copy2(xmp, ut_dir / xmp.name)

    print(f"\nKlart. {len(valda)} NEF kopierade till: {ut_dir}")
    if args.xmp:
        print(f"XMP-sidecars skrivna med beskärning och upprätnning.")


if __name__ == "__main__":
    main()
