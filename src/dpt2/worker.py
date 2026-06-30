"""Worker-process — kör ETT tungt jobb och skriver JSON-events till stdout.

Startas av tjanster.korning.kor_subprocess som `python -m dpt2.worker <jobb>
<args-json>`. Isoleringen (egen process) skyddar UI:t mot native-krascher/OOM
och process-globala trådfaror i de tunga biblioteken (torch/cv2/Vision).

Varje jobb är en funktion som tar en args-dict och anropar `_emit(event(...))`.
`demo` är beroendefri (bevisar IPC-röret utan ML). De tunga jobben (gallra/trana/
nummer/story) pluggas in i JOBB-registret och importerar sina motorer LAT inuti
funktionen — de kräver full ML-miljö (torch/sklearn/mediapipe) och din riktiga
data, så de körs på fotografens maskin, inte i CI.
"""

import json
import os
import sys

from dpt2.tjanster.korning import event, event_rad


def _emit(ev):
    print(event_rad(ev), flush=True)


def jobb_demo(args):
    """Beroendefritt demo-jobb: emitterar start → progress×N → klar. Bevisar att
    event-strömmen når UI:t utan att någon ML-motor laddas."""
    steg = int(args.get("steg", 5))
    _emit(event("start", jobb="demo"))
    for i in range(1, steg + 1):
        _emit(event("progress", andel=round(i / steg, 3), text=f"Steg {i}/{steg}"))
        _emit(event("logg", niva="info", text=f"bearbetar enhet {i}"))
    _emit(event("logg", niva="ok", text="demo färdig"))
    _emit(event("klar", resultat={"steg": steg}))


def _logg(niva="info"):
    """logg-callback som speglar tjänsternas print → JSON logg-event."""
    return lambda text: _emit(event("logg", niva=niva, text=str(text)))


def _db(args):
    from dpt2.data import db
    return db.oppna(os.path.expanduser(args["db_path"]) if args.get("db_path")
                    else db.DB_DEFAULT, check_same_thread=False)


def jobb_omrakna(args):
    """Bygger träningskorpusen ur ett arkiv-träd: walk → extrahera features ur de
    (nedladdade) JPG:erna → lagra som facit i dpt2. Online-only hoppas."""
    from dpt2.motorer import ai_lager
    from dpt2.tjanster import traning
    root = args.get("root")
    if not root:
        _emit(event("fel", text="Ingen arkiv-rot angiven (root).")); return
    _emit(event("start", jobb="omrakna"))
    _emit(event("progress", andel=0.05, text="Laddar modeller…"))
    modeller = ai_lager.ladda_modeller(n_pose=1, med_estetik=True,
                                       med_ogon=True, med_clip=True)
    r = traning.omrakna_arkiv(_db(args), os.path.expanduser(root), modeller,
                              logg=_logg())
    _emit(event("klar", resultat=r))


def jobb_trana(args):
    """Tränar modellen ur de LAGRADE facit-vektorerna (inga bilder). Sparar pkl +
    modell-bibliotekrad."""
    from dpt2.data import db
    from dpt2.tjanster import traning
    _emit(event("start", jobb="trana"))
    typ = args.get("typ", "arkiv")
    modell_path = os.path.expanduser(
        args.get("modell_path")
        or str(db.DB_DEFAULT.parent / "modeller" / f"{typ}.pkl"))
    r = traning.trana_modell(_db(args), typ=typ, modell_path=modell_path,
                             logg=_logg())
    if r.get("ok"):
        _emit(event("klar", resultat=r))
    else:
        _emit(event("fel", text=r.get("fel", "okänt fel")))


def _jobb_ej_implementerad(namn):
    def kor(_args):
        _emit(event("start", jobb=namn))
        _emit(event("logg", niva="info", text=
              f"Jobbet '{namn}' kräver full ML-miljö och riktig data; pluggas in här."))
        _emit(event("fel", text=f"'{namn}' ännu inte inkopplad i workern."))
    return kor


# Registret: tunga jobb. demo (beroendefritt) + omrakna/trana (väg B) körbara.
# gallra/nummer/story = nästa att plugga in (gallring/nummer-OCR/story_overlay).
JOBB = {
    "demo": jobb_demo,
    "omrakna": jobb_omrakna,
    "trana": jobb_trana,
    "gallra": _jobb_ej_implementerad("gallra"),
    "nummer": _jobb_ej_implementerad("nummer"),
    "story": _jobb_ej_implementerad("story"),
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    namn = argv[0] if argv else "demo"
    try:
        args = json.loads(argv[1]) if len(argv) > 1 else {}
    except Exception:
        args = {}
    fn = JOBB.get(namn)
    if not fn:
        _emit(event("fel", text=f"Okänt jobb: {namn}"))
        return 2
    try:
        fn(args)
        return 0
    except Exception as e:
        _emit(event("fel", text=f"{type(e).__name__}: {e}"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
