"""Tröjnummer-orkestrering (Leverera-väg) — läser tröjnummer på ett urvals bilder
och skriver in dem som keywords (syns i Lightroom).

Kor-glue kring den migrerade nummer-kärnan (motorer.nummer): per stam laddas en
preview, YOLO hittar spelare, EasyOCR läser ryggnumret, roster (härledd ur
matchen) namnger, och `_skriv_keywords` skriver 'nr namn' idempotent. Tung GLUE →
körs i worker-processen.

Claude-vision-fallback på luckor + osakra_nummer-listan (Steg 2) är EJ med i
denna v1 — de blir konsumenter av tjanster.claude i ett senare steg.
"""

from pathlib import Path

from dpt2.data import store
from dpt2.motorer import nummer as N
from dpt2.motorer.extraktion import _las_bild


def roster_av_match(conn, match_id):
    """Bygger lag_roster {'hemma':{nr:namn}, 'borta':{nr:namn}} ur matchens
    trupp. Tom dict om match/trupp saknas."""
    if not match_id:
        return {}
    m = store.hamta_match(conn, match_id)
    if not m:
        return {}
    r = {"hemma": {}, "borta": {}}
    for sp in m.get("spelare", []):
        lag = sp.get("lag")
        nr = str(sp.get("nr") or "").strip()
        if lag in r and nr:
            r[lag][nr] = sp.get("namn") or ""
    return {k: v for k, v in r.items() if v}


def kor_nummer(conn, urval_id, modeller, *, env=None, min_konf=0.45,
               logg=print, progress=None):
    """Läser tröjnummer på urvalets bilder → keywords. Roster + hemmafärg härleds
    ur matchen/cull_jobbet. Returnerar {totalt, skrivna, luckor}."""
    urval = store.hamta_urval(conn, urval_id)
    if not urval:
        return {"ok": False, "fel": "Okänt urval."}
    jobb = (store.jobb_for_urval(conn, urval_id) or [None])[-1]
    hemma_farg = (jobb or {}).get("hemmafarg") or ""
    lag_roster = roster_av_match(conn, urval.get("match_id"))
    kalla = urval.get("kalla") or ""
    grupper = N._bilder_per_stam(Path(kalla))
    if not grupper:
        return {"ok": False, "fel": f"Inga bildfiler i källmappen ({kalla})."}
    ocr = modeller.get("ocr")
    if ocr is None:
        return {"ok": False, "fel": "EasyOCR saknas (pipx inject dpt easyocr)."}

    env = env or N._env()
    yolo, dev = modeller["yolo"], modeller["device"]
    flera = len([k for k in lag_roster if k]) >= 2
    logg(f"Läser tröjnummer på {len(grupper)} bilder i {Path(kalla).name}"
         + (f" (roster: {sum(len(v) for v in lag_roster.values())} spelare)"
            if lag_roster else "") + "…")
    skrivna = luckor = 0
    for i, (stem, filer) in enumerate(grupper.items(), 1):
        img = _las_bild(N._preview_kalla(filer), env)
        if img is None:
            continue
        yres = yolo(img, verbose=False, device=dev)[0]
        traffar, n_pers = N._las_nummer(img, yres, ocr, lag_roster,
                                        hemma_farg, min_konf)
        if traffar:
            if N._skriv_keywords(filer, traffar, env):
                skrivna += 1
        elif n_pers >= 1:
            luckor += 1
        if progress:
            progress(i, len(grupper))
    logg(f"✓ Tröjnummer-keywords på {skrivna} bilder, {luckor} luckor "
         "(spelare men inget säkert nummer).")
    return {"ok": True, "totalt": len(grupper), "skrivna": skrivna,
            "luckor": luckor}
