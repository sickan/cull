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


def lar_av_match(conn, mapp, modeller, *, match_namn="", sport="", env=None,
                 logg=print):
    """Lär av match: märker ETT gallrat urval (mappen med de behållna bilderna)
    som träningsdata. Extraherar features ur bilderna med NUVARANDE libs och
    lagrar dem som ett facit-uppdrag där ALLA rader är valda (label=1) —
    fotografens positiva val blir modellens smakfacit. Idempotent per uppdrags-
    namn (omkörning ersätter). Returnerar {n_bilder, valda, namn} eller
    {..., fel} om inget lokalt gick att läsa."""
    from dpt2.tjanster import leverera
    paths = leverera.lista_bilder(str(mapp))
    namn = match_namn or Path(mapp).name or "Gallrat urval"
    if not paths:
        return {"n_bilder": 0, "valda": 0, "namn": namn,
                "fel": "Inga bildfiler i urvalets mapp."}
    logg(f"Lär av {namn}: {len(paths)} bilder i mappen.")
    X, stems = extraktion.features_for_bilder(paths, modeller, env=env,
                                              sport=sport or None)
    if not X:
        return {"n_bilder": 0, "valda": 0, "namn": namn,
                "fel": "Inga bilder gick att läsa lokalt (online-only?)."}
    rader = [(s, 1, 1.0, v) for s, v in zip(stems, X)]
    fid = store.spara_facit(conn, match_namn=namn, sport=sport or "okänd",
                            n=len(rader), features=extraktion.FEATURES)
    store.ersatt_facit_rader(conn, fid, rader)
    logg(f"  {namn}: {len(rader)} bilder märkta som träningsdata.")
    return {"n_bilder": len(rader), "valda": len(rader), "namn": namn}


def gallrings_id(namn):
    """Matchnyckel tagning↔urval: frame-id ur tidsstämplade exportnamn
    (20260724…_Z81_1234_NIKON… → Z811234), annars filstammen; -Edit/-Redigera
    strippas, skiftlägesokänsligt. Så matchar urvalets LR-exporter tagningens
    NEF:er även när namnen döpts om vid export."""
    from dpt2.motorer.arkiv import _frame_id
    return _frame_id(namn)


def lar_av_gallring(conn, tagning_mapp, urval_mapp, modeller, *,
                    namn="", sport="", env=None, logg=print):
    """Genvägen (Stig 24/7): manuell gallring → FULLT 1/0-facit i ETT steg,
    utan krav på att maskingallringen körts först. Extraherar features ur HELA
    tagningen (NEF läses via inbäddad preview) och märker varje bild mot
    urvalsmappen: frame-id/stam som finns i urvalet = 1 (behållen), annars 0
    (bortgallrad) — det är poängen mot lar_av_match, som bara ger positiva.
    Idempotent per uppdragsnamn (omkörning ersätter)."""
    from dpt2.tjanster import leverera
    tagning = leverera.lista_bilder(str(tagning_mapp))
    urval = leverera.lista_bilder(str(urval_mapp))
    uppdragsnamn = namn or Path(tagning_mapp).name or "Gallring"
    if not tagning:
        return {"n_bilder": 0, "valda": 0, "namn": uppdragsnamn,
                "fel": "Inga bildfiler i tagningens mapp."}
    if not urval:
        return {"n_bilder": 0, "valda": 0, "namn": uppdragsnamn,
                "fel": "Inga bildfiler i urvalets mapp."}
    valda_ids = {gallrings_id(Path(p).name) for p in urval}
    logg(f"Lär av gallring {uppdragsnamn}: {len(tagning)} i tagningen, "
         f"{len(urval)} i urvalet.")
    X, stems = extraktion.features_for_bilder(tagning, modeller, env=env,
                                              sport=sport or None)
    if not X:
        return {"n_bilder": 0, "valda": 0, "namn": uppdragsnamn,
                "fel": "Inga bilder gick att läsa lokalt (online-only?)."}
    rader = [(s, 1 if gallrings_id(s) in valda_ids else 0, 1.0, v)
             for s, v in zip(stems, X)]
    valda = sum(1 for r in rader if r[1])
    if valda == 0:
        # Urvalet matchade INTE tagningen — fel mapp-par eller omdöpta filer.
        # Lagra inget: ett facit där ALLT är negativt förgiftar modellen.
        return {"n_bilder": len(rader), "valda": 0, "namn": uppdragsnamn,
                "fel": "Ingen urvalsbild matchade tagningen — kolla att "
                       "mapparna hör ihop (matchning på filstam/frame-id)."}
    fid = store.spara_facit(conn, match_namn=uppdragsnamn,
                            sport=sport or "okänd",
                            n=len(rader), features=extraktion.FEATURES)
    store.ersatt_facit_rader(conn, fid, rader)
    # Omatchade urvalsbilder (id utan motsvarighet i tagningen — t.ex. annat
    # kort) rapporteras så glappet syns i stället för att försvinna tyst.
    tagning_ids = {gallrings_id(s) for s in stems}
    omatchade = sum(1 for i in valda_ids if i not in tagning_ids)
    logg(f"  {uppdragsnamn}: {len(rader)} bilder, {valda} behållna (1), "
         f"{len(rader) - valda} bortgallrade (0)"
         + (f", {omatchade} urvalsbilder utan motsvarighet." if omatchade else "."))
    return {"n_bilder": len(rader), "valda": valda, "namn": uppdragsnamn,
            "omatchade": omatchade}


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
