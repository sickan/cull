"""Golden-verifiering (beslut 3): bevisar att dpt2:s förenade extraktion
reproducerar gamla FEATURES-vektorn på riktiga bilder.

Jämför `extraktion.features_for_bilder` mot facit_underlag (vektorer beräknade av
GAMLA pipelinen) på ett stickprov av överlappande bilder. Kräver:
  - ~/.config/dpt/facit_underlag/*.json (golden-vektorer)
  - den monterade källmappen med originalbilderna

Kör (i dpt-venv):
  python -m dpt2.motorer.verifiera_golden "<bildmapp>" [antal]

Inte ett auto-test (kräver extern volym + modell-laddning).
"""

import json
import sys
from pathlib import Path

from dpt2.motorer import ai_lager, extraktion


def ladda_facit(kamera_filter="NIKON_Z_8"):
    d = Path.home() / ".config" / "dpt" / "facit_underlag"
    f = next(p for p in d.glob("*.json") if kamera_filter in p.name)
    data = json.load(open(f))
    return {r["stem"]: r["v"] for r in data["rader"]}, data["features"]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mapp = Path(argv[0]) if argv else Path(
        "/Volumes/X10 Blue/Dalecarlia Photo Cull/"
        "(D) Malmö FF - Kristianstad DFF 6-0 (3-0) 20260627 14.00 Eleda Stadion/Z8")
    antal = int(argv[1]) if len(argv) > 1 else 6

    facit, feat_namn = ladda_facit()
    if feat_namn != extraktion.FEATURES:
        print("⚠ FEATURES-ordning skiljer!\n facit:", feat_namn,
              "\n dpt2: ", extraktion.FEATURES)
    nef = {p.stem: p for p in mapp.glob("*.NEF")}
    stems = sorted(set(facit) & set(nef))[:antal]
    if not stems:
        print(f"Inga överlappande bilder i {mapp}")
        return 1
    print(f"Stickprov: {len(stems)} bilder ur {mapp.name}")

    print("Laddar modeller (YOLO/pose/face/CLIP/NIMA)…")
    modeller = ai_lager.ladda_modeller(n_pose=1, med_estetik=True,
                                       med_ogon=True, med_clip=True)
    paths = [nef[s] for s in stems]
    X, ut_stems = extraktion.features_for_bilder(paths, modeller, sport="fotboll")

    # Jämför per bild, per feature.
    print(f"\n{'feature':14}{'max|Δ|':>12}{'medel|Δ|':>12}")
    n = len(extraktion.FEATURES)
    maxdiff = [0.0] * n
    sumdiff = [0.0] * n
    for stem, vekt in zip(ut_stems, X):
        g = facit[stem]
        for i in range(n):
            d = abs(vekt[i] - g[i])
            maxdiff[i] = max(maxdiff[i], d)
            sumdiff[i] += d
    for i, namn in enumerate(extraktion.FEATURES):
        print(f"{namn:14}{maxdiff[i]:>12.5f}{sumdiff[i]/len(ut_stems):>12.5f}")

    # Sammanfattning: relativ avvikelse mot facit-skalan per feature.
    värsta = max(range(n), key=lambda i: maxdiff[i])
    print(f"\nStörsta avvikelse: '{extraktion.FEATURES[värsta]}' "
          f"max|Δ|={maxdiff[värsta]:.5f}")
    # Klassiska bas-features ska matcha tajt; modell-outputs (nima/clip) kan ha
    # liten GPU-nondeterminism.
    bas_idx = [extraktion.FEATURES.index(k) for k in
               ("skarpa", "exp", "ansikten", "ogon", "motljus", "rorelse")]
    bas_ok = all(maxdiff[i] < 0.01 * max(1.0, abs_skala(facit, ut_stems, i))
                 for i in bas_idx)
    print("Bas-features reproduceras:", "JA" if bas_ok else "NEJ (se ovan)")
    return 0


def abs_skala(facit, stems, i):
    vals = [abs(facit[s][i]) for s in stems]
    return max(vals) if vals else 1.0


if __name__ == "__main__":
    sys.exit(main())
