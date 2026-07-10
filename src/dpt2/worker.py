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
    """Öppnar jobbets databas. `db_path` är OBLIGATORISK.

    Tidigare föll den tillbaka på `db.DB_DEFAULT` — användarens riktiga
    ~/.config/dpt2/dpt.db. `app.py:_kor_jobb` injicerar alltid db_path, så
    fallbacken var död i drift men förödande i test: `worker.main(["story", …])`
    utan db_path öppnade den SKARPA databasen och lät `init_db` MIGRERA den.
    Det syntes inte förrän en gren hade högre SCHEMA_VERSION än koden appen kör
    — då vägrade DPT2 starta ("schemaversion nyare än kodens").

    Saknad db_path är alltså ett anropsfel. main() fångar undantaget och skickar
    ett 'fel'-event, precis som för andra ogiltiga jobbargument."""
    from dpt2.data import db
    p = args.get("db_path")
    if not p:
        raise ValueError("db_path saknas i jobbargumenten")
    return db.oppna(os.path.expanduser(p), check_same_thread=False)


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


def jobb_gallra(args):
    """Kör cull på ett urval (läser kalla + cull_jobb ur db): extrahera features
    → poängsätt (modell/handsatt) → urvalsmotor → uppdatera urval.bilder."""
    from dpt2.motorer import ai_lager
    from dpt2.tjanster import gallring_korning
    urval_id = args.get("urval_id")
    if not urval_id:
        _emit(event("fel", text="Inget urval_id angivet.")); return
    _emit(event("start", jobb="gallra"))
    _emit(event("progress", andel=0.05, text="Laddar modeller…"))
    modeller = ai_lager.ladda_modeller(n_pose=1, med_estetik=True,
                                       med_ogon=True, med_clip=True)
    def progress(n, tot):
        _emit(event("progress", andel=round(0.1 + 0.85 * n / max(1, tot), 3),
                    text=f"Extraherar {n}/{tot}"))
    r = gallring_korning.kor_gallring(_db(args), urval_id, modeller,
                                      logg=_logg(), progress=progress)
    if r.get("ok"):
        _emit(event("klar", resultat=r))
    else:
        _emit(event("fel", text=r.get("fel", "okänt fel")))


def jobb_nummer(args):
    """Läser tröjnummer på ett urvals bilder → keywords (YOLO + EasyOCR)."""
    from dpt2.motorer import ai_lager
    from dpt2.tjanster import nummer_korning
    urval_id = args.get("urval_id")
    if not urval_id:
        _emit(event("fel", text="Inget urval_id angivet.")); return
    _emit(event("start", jobb="nummer"))
    _emit(event("progress", andel=0.05, text="Laddar YOLO + EasyOCR…"))
    modeller = ai_lager.ladda_modeller(med_ocr=True, n_pose=1)
    def progress(n, tot):
        _emit(event("progress", andel=round(0.1 + 0.85 * n / max(1, tot), 3),
                    text=f"OCR {n}/{tot}"))
    r = nummer_korning.kor_nummer(_db(args), urval_id, modeller,
                                  logg=_logg(), progress=progress)
    if r.get("ok"):
        _emit(event("klar", resultat=r))
    else:
        _emit(event("fel", text=r.get("fel", "okänt fel")))


def jobb_story(args):
    """Renderar en Matchdag-story (story_overlay, PIL) ur config + matchdata."""
    from dpt2.tjanster import story_korning
    _emit(event("start", jobb="story"))
    _emit(event("progress", andel=0.2, text="Renderar…"))
    r = story_korning.kor_story(_db(args), args.get("config") or {}, logg=_logg())
    if r.get("ok"):
        _emit(event("klar", resultat=r))
    else:
        _emit(event("fel", text=r.get("fel", "okänt fel")))


def jobb_publicera(args):
    """Publicerar ett paket (färdiga bilder + caption) till SoMe-kanalerna.
    dry_run som default — utan skarp=True rörs inga API:er, bara planen loggas."""
    from dpt2.tjanster import meta_api, publicera_korning
    config = args.get("config") or {}
    dry_run = not args.get("skarp")
    _emit(event("start", jobb="publicera"))
    def progress(n, tot):
        _emit(event("progress", andel=round(n / max(1, tot), 3),
                    text=f"Post {n}/{tot}"))
    # Kanal-adapter för skarp körning: stub (test av flödet) eller riktig ur env.
    poster = None
    if not dry_run:
        poster = (meta_api.stub_poster(_logg()) if args.get("stub")
                  else meta_api.fran_env(logg=_logg()))
        if poster is None:
            _emit(event("fel", text="Skarp publicering saknar Meta-token "
                        "(META_ACCESS_TOKEN). Kör med stub=True eller dry-run."))
            return
        if not args.get("stub"):
            # Graph hämtar bilder via publik URL → ladda upp till bild-hosten först.
            from dpt2.tjanster import bildhosting
            upp = bildhosting.ladda_upp(config.get("bilder") or [], logg=_logg())
            if not upp.get("ok"):
                _emit(event("fel", text=f"Bilduppladdning: {upp.get('fel')}"))
                return
    r = publicera_korning.kor_publicering(
        _db(args), config, poster=poster, dry_run=dry_run,
        logg=_logg(), progress=progress)
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
    "gallra": jobb_gallra,
    "nummer": jobb_nummer,
    "story": jobb_story,
    "publicera": jobb_publicera,
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
