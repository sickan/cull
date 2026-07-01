"""Recompute+retrain-tjänst (väg B) — bygger träningskorpusen ur arkivet
INKREMENTELLT och tränar modellen ur de lagrade vektorerna.

- omrakna_arkiv(root): går igenom ett monterat arkiv-träd, extraherar features ur
  varje uppdrags (beständiga) JPG med NUVARANDE libs och lagrar dem som facit-
  uppdrag i dpt2 (idempotent per uppdrag). Online-only-filer (ej nedladdade
  Dropbox-filer) hoppas automatiskt → kör om när fler kataloger laddats ned.
- trana_modell(): läser ALLA lagrade facit-vektorer (inga bilder behövs) och
  tränar via inlarning.trana → sparar modell.pkl + en modell-rad i biblioteket.

Tung GLUE → körs i worker-processen (ai_lager + torch laddas inuti).
"""

from pathlib import Path

from dpt2.data import store
from dpt2.motorer import arkiv, extraktion, inlarning


def omrakna_arkiv(conn, root, modeller, *, env=None, logg=print):
    """Walk + extrahera + lagra. Returnerar {uppdrag, bilder, valda}."""
    uppdrag = arkiv.hitta_uppdrag(root)
    logg(f"Hittade {len(uppdrag)} uppdrag i {root}.")
    tot, tot_valda = 0, 0
    for namn, sport, items in uppdrag:
        labels = {Path(p).stem: lab for p, lab in items}
        paths = [p for p, _ in items]
        X, stems = extraktion.features_for_bilder(paths, modeller, env=env,
                                                  sport=sport)
        if not X:
            logg(f"  {namn}: 0 bilder lokalt (online-only?) — hoppar.")
            continue
        rader = [(s, labels.get(s, 0), 1.0, v) for s, v in zip(stems, X)]
        valda = sum(1 for r in rader if r[1])
        fid = store.spara_facit(conn, match_namn=namn, sport=sport,
                                n=len(rader), features=extraktion.FEATURES)
        store.ersatt_facit_rader(conn, fid, rader)
        tot += len(rader)
        tot_valda += valda
        logg(f"  {namn} [{sport}]: {len(rader)} bilder, {valda} valda → lagrat.")
    return {"uppdrag": len(uppdrag), "bilder": tot, "valda": tot_valda}


def trana_modell(conn, *, typ="arkiv", modell_path, logg=print):
    """Tränar ur ALLA lagrade facit-vektorer. Sparar pkl + modell-bibliotekrad
    (aktiv). Returnerar {ok, n_uppdrag, n_valda} eller {ok:False, fel}."""
    uppdrag = store.facit_for_traning(conn)
    if not uppdrag:
        return {"ok": False, "fel": "Inga omräknade facit-uppdrag att träna på."}
    paket = inlarning.trana(uppdrag, features=extraktion.FEATURES, typ=typ,
                            logg=logg)
    inlarning.spara_modell(paket, modell_path)
    store.spara_modell(conn, typ=typ, pkl_path=str(modell_path),
                       features=extraktion.FEATURES, n_uppdrag=paket["n_uppdrag"],
                       n_valda=paket["n_valda"], aktiv=True)
    logg(f"Modell sparad: {modell_path} "
         f"({paket['n_uppdrag']} uppdrag, {paket['n_valda']} valda).")
    return {"ok": True, "n_uppdrag": paket["n_uppdrag"],
            "n_valda": paket["n_valda"]}
