"""Story-orkestrering (Publicera → Matchdag) — renderar en Horisont-overlay
(story/inlägg) ur ett källfoto + matchdata.

Tunn GLUE ovanpå den migrerade rendermotorn motorer.story_overlay (ren PIL,
fonts + temaloggor i dpt2/assets). Matchfält (lag/liga/arena/ställning/målgörare/
startelva) härleds ur matchen när ett match_id anges; annars ur config. Kör i
worker-processen (batch/tunga bilder), men är torch-fri.
"""

import os
from pathlib import Path

from dpt2.data import store, sportprofil
from dpt2.motorer import story_overlay
from dpt2.motorer.nummer import _env


_MAN = ["jan", "feb", "mar", "apr", "maj", "jun", "jul",
        "aug", "sep", "okt", "nov", "dec"]


def _datum_kort(iso):
    """'2026-07-06' → '6 jul' (tom sträng vid ogiltigt datum)."""
    d = (iso or "").split("-")
    if len(d) == 3:
        try:
            return f"{int(d[2])} {_MAN[int(d[1]) - 1]}"
        except (ValueError, IndexError):
            return ""
    return ""


def _matchfalt(conn, config):
    """Fyller lag/liga/arena/ställning/mål/startelva ur matchen (match_id) med
    config som fallback — utom mallfälten (stallning/mal_rad/startelva/lag_borta):
    där vinner config, eftersom Live-flödet skickar explicit ifyllda fält
    (t.ex. halvtidsställning eller 'Nästa match'-motståndare) som ska slå
    matchens lagrade värden.

    Sportprofilen (data/sportprofil.py) avgör vad "mal_rad" faktiskt visar:
    målskyttar för scorer-sporter, annars mellanresultatet (set-/period-/
    gamesiffror) i samma underrad — renderaren i story_overlay rör sig inte,
    bara vilken sträng som skickas in i dess befintliga mal_rad-parameter."""
    m = store.hamta_match(conn, config.get("match_id")) if config.get("match_id") else None
    m = m or {}
    sport = m.get("sport") or config.get("sport", "")
    prof = sportprofil.profil(sport)
    mellan = config.get("mellan") or m.get("mellan", "")
    mal_rad = (config.get("mal_rad") or m.get("malskyttar", "")) if prof["has_scorers"] \
        else (config.get("mal_rad") or mellan)
    startelva = None
    if m.get("spelare"):
        namn = [sp.get("namn") for sp in m["spelare"]
                if sp.get("start") and sp.get("lag") == "hemma" and sp.get("namn")]
        startelva = "\n".join(namn) if namn else None

    def _logga(lag_id):
        lag = store.hamta_lag(conn, lag_id) if lag_id else None
        return (lag or {}).get("logga") or None

    # p.5: för heldagsevent (moment Nästa match, ingen motståndare) saknar
    # kanalens config next_when → härled eventdatumet så underraden inte tappar
    # datumet. Explicit config.next_when (Live-flödet) vinner alltid.
    next_when = config.get("next_when") or (
        _datum_kort(m.get("datum")) if m.get("event") else "")

    return {
        "lag_hemma": m.get("lag_hemma") or config.get("lag_hemma", ""),
        "lag_borta": config.get("lag_borta") or m.get("lag_borta", ""),
        "liga": m.get("liga") or config.get("liga", ""),
        "arena": m.get("arena") or config.get("arena", ""),
        "next_when": next_when,
        "sport": sport,
        "stallning": config.get("stallning") or m.get("resultat", ""),
        "mal_rad": mal_rad,
        "startelva": config.get("startelva") or startelva,
        "gren": m.get("hem_gren") or config.get("gren", ""),
        # Loggor som fotografen laddat upp under Lag & tävlingar (lag.logga i
        # databasen) — INTE samma sak som story_overlay.hitta_logga()s gamla
        # filsystemkonvention (~/.config/dpt/loggor/<namn>.png), som bara är
        # en fallback om databasen saknar en logga för laget.
        "hem_logga": _logga(m.get("lag_hemma_id")),
        "borta_logga": _logga(m.get("lag_borta_id")),
    }


def _rendera(conn, config, *, ut_path=None, ut_mapp=None, env=None):
    """Gemensam renderingskärna för kor_story/forhandsgranska. Validerar
    foto+moment, härleder matchfält, kör story_overlay.skapa_story.
    Returnerar {ok, path} eller {ok:False, fel}."""
    config = config or {}
    if not config.get("moment"):
        return {"ok": False, "fel": "Välj ett moment."}
    foto = os.path.expanduser(config.get("foto") or "")
    if not foto or not Path(foto).exists():
        return {"ok": False, "fel": "Ange ett källfoto som finns."}

    f = _matchfalt(conn, config)
    ut = story_overlay.skapa_story(
        foto, config["moment"], f["lag_hemma"], f["lag_borta"],
        liga=f["liga"], stallning=f["stallning"], mal_rad=f["mal_rad"],
        arena=f["arena"], startelva=f["startelva"], sport=f["sport"],
        avspark_tid=config.get("avspark_tid", ""),
        next_when=f.get("next_when", ""),
        tema=config.get("tema", "Hav"), gren=f["gren"],
        hem_logga=f["hem_logga"], borta_logga=f["borta_logga"],
        format=config.get("format", "9x16"),
        fokus=config.get("fokus"), zoom=config.get("zoom", 1.0),
        ut_path=ut_path, ut_mapp=ut_mapp, env=env or _env())
    return {"ok": True, "path": str(ut)}


def kor_story(conn, config, *, env=None, logg=print):
    """Renderar en story ur config {foto, moment, tema, format, match_id?} till
    Dropbox-mappen (`config['ut_mapp']`, annars `~/.config/dpt2/stories`).
    Returnerar {ok, path, moment} eller {ok:False, fel}."""
    config = config or {}
    ut_mapp = os.path.expanduser(config.get("ut_mapp") or "~/.config/dpt2/stories")
    logg(f"Renderar story '{config.get('moment')}' ({config.get('tema', 'Hav')}, "
         f"{config.get('format', '9x16')})…")
    r = _rendera(conn, config, ut_mapp=ut_mapp, env=env)
    if r["ok"]:
        logg(f"✓ Story renderad: {r['path']}")
        r["moment"] = config["moment"]
    return r


# Fast fil (skrivs över varje gång) — snabb förhandsvisning, ALDRIG i Dropbox-
# mappen, rör aldrig skarpt renderade stories.
FORHANDSVISNING_PATH = Path.home() / ".config" / "dpt2" / "forhandsvisning.jpg"


def forhandsgranska(conn, config, *, env=None):
    """Renderar SAMMA mall som kor_story men till en fast tempfil, för
    Publicera→Live-panelens 'riktiga' förhandsvisning. Returnerar {ok, path}
    eller {ok:False, fel}.

    config['preview_slot'] (valfritt) ger en EGEN tempfil per anropare — så
    t.ex. SoMe-overlay-omslaget (4:5) inte skriver över Live-förhandsvisningen
    (9:16) i den delade filen."""
    slot = (config or {}).get("preview_slot")
    path = (FORHANDSVISNING_PATH.parent / f"forhandsvisning-{slot}.jpg") if slot \
        else FORHANDSVISNING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return _rendera(conn, config, ut_path=path, env=env)
