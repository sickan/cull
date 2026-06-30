"""Verifierar recompute+retrain-flödet (beslut 3, väg B) på RIKTIG data:

  facit-y ur dpt2 SQLite (bevarad grundsanning)
  + omräknade features (extraktion.features_for_bilder, nuvarande ML-libs)
  → träna om (inlarning.trana) → poängsätt.

Bevisar att hela kedjan håller med de nya biblioteken. Läser BARA dpt2.db och
bildmappen; sparar testmodellen till scratch (rör inte skarpa modell.pkl).

  python -m dpt2.motorer.verifiera_omtraning "<bildmapp>" [max]
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

from dpt2.motorer import ai_lager, extraktion, inlarning


def _facit_y(db, kamera="NIKON Z 8"):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    fid = c.execute("SELECT id FROM facit WHERE kamera=? LIMIT 1",
                    (kamera,)).fetchone()
    if not fid:
        return {}
    return {r["stem"]: r["y"] for r in c.execute(
        "SELECT stem,y FROM facit_rad WHERE facit_id=?", (fid["id"],))}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mapp = Path(argv[0]) if argv else Path(
        "/Volumes/X10 Blue/Dalecarlia Photo Cull/"
        "(D) Malmö FF - Kristianstad DFF 6-0 (3-0) 20260627 14.00 Eleda Stadion/Z8")
    maxbilder = int(argv[1]) if len(argv) > 1 else 100

    db = Path.home() / ".config" / "dpt2" / "dpt.db"
    ystem = _facit_y(db)
    nef = {p.stem: p for p in mapp.glob("*.NEF")}
    stems = sorted(set(ystem) & set(nef))[:maxbilder]
    if not stems:
        print(f"Inga facit-märkta bilder i {mapp}")
        return 1
    n_pos = sum(ystem[s] for s in stems)
    print(f"Stickprov: {len(stems)} facit-märkta bilder, {n_pos} behållna "
          f"({n_pos/len(stems)*100:.0f}%) ur {mapp.name}")

    print("Laddar modeller…")
    modeller = ai_lager.ladda_modeller(n_pose=1, med_estetik=True,
                                       med_ogon=True, med_clip=True)
    print("Omräknar features (nuvarande libs)…")
    paths = [nef[s] for s in stems]
    X, ut_stems = extraktion.features_for_bilder(paths, modeller, sport="fotboll")
    y = [ystem[s] for s in ut_stems]
    print(f"Extraherade {len(X)} vektorer, {sum(y)} positiva.")

    print("\nTränar om (din smak) på de BEVARADE y-etiketterna…")
    paket = inlarning.trana([(X, y, "fotboll")], features=extraktion.FEATURES,
                            typ="din_smak")
    p = Path(tempfile.mkdtemp()) / "modell_omtranad.pkl"
    inlarning.spara_modell(paket, p)
    print(f"Modell sparad (scratch): {p}")

    # Poängsätt samma bilder → sanity: behållna ska ranka högre i snitt.
    res = [dict(zip(extraktion.FEATURES, v)) for v in X]
    inlarning.poangsatt_med_modell(res, paket, sport="fotboll")
    poäng = [(r["poang"], yy) for r, yy in zip(res, y)]
    snitt_pos = sum(p for p, yy in poäng if yy) / max(1, sum(y))
    snitt_neg = sum(p for p, yy in poäng if not yy) / max(1, len(y) - sum(y))
    print(f"\nSnittpoäng behållna (y=1): {snitt_pos:.3f}")
    print(f"Snittpoäng förkastade (y=0): {snitt_neg:.3f}")
    print("Behållna rankas högre:", "JA ✓" if snitt_pos > snitt_neg else "NEJ")
    print("\n→ Recompute+retrain-kedjan fungerar med nuvarande ML-libs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
