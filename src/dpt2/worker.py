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


def _jobb_ej_implementerad(namn):
    def kor(_args):
        _emit(event("start", jobb=namn))
        _emit(event("logg", niva="info", text=
              f"Jobbet '{namn}' kräver full ML-miljö (torch/sklearn/mediapipe) "
              "och körs på fotografens maskin. Motorn pluggas in här."))
        _emit(event("fel", text=f"'{namn}' ännu inte inkopplad i workern."))
    return kor


# Registret: nya tunga jobb läggs till här (gallra→gallring, trana→inlarning,
# nummer→motorer.nummer, story→story_overlay). Demo är den körbara referensen.
JOBB = {
    "demo": jobb_demo,
    "gallra": _jobb_ej_implementerad("gallra"),
    "trana": _jobb_ej_implementerad("trana"),
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
