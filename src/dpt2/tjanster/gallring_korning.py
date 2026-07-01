"""Gallrings-orkestrering (väg: Gallra) — kör cull end-to-end på ett urval.

Binder ihop den förenade extraktionen, poängsättningen (personlig modell ELLER
handsatt formel) och urvalsmotorn:

  urval+cull_jobb (db) → lista bilder → extraktion.features_for_bilder
  → resultat-dicts (+ EXIF-tid för burst) → poäng (modell/handsatt)
  → gallring.gallra → behåll-urval → uppdatera urval.bilder.

Tung GLUE → körs i worker-processen. Modell-vägen använder bara de 19 frysta
FEATURES (poangsatt_med_modell); handsatt-vägen använder de signaler som finns
(hemma/trojnummer/fas defaultar till 0 tills de wire:as in).
"""

import json
import subprocess
from pathlib import Path

from dpt2.data import store
from dpt2.motorer import extraktion, inlarning
from dpt2.motorer.gallring import Gallring, gallra
from dpt2.tjanster.leverera import lista_bilder


def _cfg_av_jobb(jobb):
    """cull_jobb-rad → Gallring. behall_enhet 'bilder'→topp, 'procent'→andel."""
    enhet = (jobb or {}).get("behall_enhet") or "procent"
    varde = (jobb or {}).get("behall_varde")
    topp = int(varde) if (enhet == "bilder" and varde) else None
    andel = (float(varde) / 100.0) if (enhet == "procent" and varde) else 0.10
    return Gallring(
        ai=(jobb or {}).get("verktyg", "ai") != "rapport",
        topp=topp, andel=andel,
        burst_sek=float((jobb or {}).get("burst_grans") or 2.0))


def _las_tider(paths, env):
    """{stem: 'YYYY:MM:DD HH:MM:SS'} ur EXIF (en exiftool-batch). Tom vid fel."""
    try:
        r = subprocess.run(
            ["exiftool", "-j", "-DateTimeOriginal", "-S", *map(str, paths)],
            capture_output=True, text=True, env=env)
        data = json.loads(r.stdout) if r.stdout.strip() else []
        return {Path(d["SourceFile"]).stem: d.get("DateTimeOriginal")
                for d in data if d.get("DateTimeOriginal")}
    except Exception:
        return {}


def _modell_paket(conn, typ):
    """Laddar modell-paketet för en typ (din_smak/arkiv/hybrid) ur biblioteket,
    eller None om den saknas/ej tränad."""
    if not typ:
        return None
    for m in store.lista_modeller(conn):
        if m["typ"] == typ and m.get("pkl_path"):
            return inlarning.ladda_modell(m["pkl_path"])
    return None


def kor_gallring(conn, urval_id, modeller, *, env=None, logg=print, progress=None):
    """Kör cull på ett urval (läser kalla + cull_jobb ur db). Uppdaterar
    urval.bilder till antalet behållna. Returnerar {totalt, behall, modell, valda}."""
    urval = store.hamta_urval(conn, urval_id)
    if not urval:
        return {"ok": False, "fel": "Okänt urval."}
    jobb = (store.jobb_for_urval(conn, urval_id) or [None])[-1]
    cfg = _cfg_av_jobb(jobb)
    kalla = urval.get("kalla") or ""
    filer = lista_bilder(kalla)
    if not filer:
        return {"ok": False, "fel": f"Inga bildfiler i källmappen ({kalla})."}
    logg(f"Gallrar {len(filer)} bilder i {Path(kalla).name}…")

    env = env or extraktion._env()
    X, stems = extraktion.features_for_bilder(filer, modeller, env=env,
                                              progress=progress)
    if not X:
        return {"ok": False, "fel": "Inga läsbara bilder (online-only?)."}
    tider = _las_tider(filer, env)
    fil_per_stem = {Path(f).stem: str(f) for f in filer}
    resultat = []
    for v, stem in zip(X, stems):
        r = dict(zip(extraktion.FEATURES, v))
        r["fil"] = fil_per_stem.get(stem, stem)
        r["tid"] = tider.get(stem)
        resultat.append(r)

    paket = _modell_paket(conn, (jobb or {}).get("modell"))
    if paket is not None:
        inlarning.poangsatt_med_modell(resultat, paket,
                                       sport=urval.get("sport"))
        logg(f"  Poängsatt med modell ({(jobb or {}).get('modell')}).")
    else:
        logg("  Ingen tränad modell — handsatt poängformel.")
    valda, info = gallra(resultat, cfg, modellpoang_satt=paket is not None)

    store.satt_urval_bilder(conn, urval_id, len(valda))
    logg(f"✓ Behåller {len(valda)} av {len(resultat)}.")
    return {"ok": True, "totalt": len(resultat), "behall": len(valda),
            "modell": (jobb or {}).get("modell") if paket is not None else "handsatt",
            "valda": [Path(r["fil"]).stem for r in valda]}
