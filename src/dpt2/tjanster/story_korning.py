"""Story-orkestrering (Publicera → Matchdag) — renderar en Horisont-overlay
(story/inlägg) ur ett källfoto + matchdata.

Tunn GLUE ovanpå den migrerade rendermotorn motorer.story_overlay (ren PIL,
fonts + temaloggor i dpt2/assets). Matchfält (lag/liga/arena/ställning/målgörare/
startelva) härleds ur matchen när ett match_id anges; annars ur config. Kör i
worker-processen (batch/tunga bilder), men är torch-fri.
"""

import os
from pathlib import Path

from dpt2.data import store
from dpt2.motorer import story_overlay
from dpt2.motorer.nummer import _env


def _matchfalt(conn, config):
    """Fyller lag/liga/arena/ställning/mål/startelva ur matchen (match_id) med
    config som fallback."""
    m = store.hamta_match(conn, config.get("match_id")) if config.get("match_id") else None
    m = m or {}
    startelva = None
    if m.get("spelare"):
        namn = [sp.get("namn") for sp in m["spelare"]
                if sp.get("start") and sp.get("lag") == "hemma" and sp.get("namn")]
        startelva = "\n".join(namn) if namn else None
    return {
        "lag_hemma": m.get("lag_hemma") or config.get("lag_hemma", ""),
        "lag_borta": m.get("lag_borta") or config.get("lag_borta", ""),
        "liga": m.get("liga") or config.get("liga", ""),
        "arena": m.get("arena") or config.get("arena", ""),
        "stallning": m.get("resultat") or config.get("stallning", ""),
        "mal_rad": m.get("malskyttar") or config.get("mal_rad", ""),
        "startelva": startelva,
    }


def kor_story(conn, config, *, env=None, logg=print):
    """Renderar en story ur config {foto, moment, tema, format, match_id?}.
    Returnerar {ok, path, moment} eller {ok:False, fel}."""
    config = config or {}
    if not config.get("moment"):
        return {"ok": False, "fel": "Välj ett moment."}
    foto = os.path.expanduser(config.get("foto") or "")
    if not foto or not Path(foto).exists():
        return {"ok": False, "fel": "Ange ett källfoto som finns."}

    f = _matchfalt(conn, config)
    ut_mapp = os.path.expanduser(config.get("ut_mapp") or "~/.config/dpt2/stories")
    logg(f"Renderar story '{config['moment']}' ({config.get('tema', 'Hav')}, "
         f"{config.get('format', '9x16')})…")
    ut = story_overlay.skapa_story(
        foto, config["moment"], f["lag_hemma"], f["lag_borta"],
        liga=f["liga"], stallning=f["stallning"], mal_rad=f["mal_rad"],
        arena=f["arena"], startelva=f["startelva"],
        tema=config.get("tema", "Hav"), format=config.get("format", "9x16"),
        ut_mapp=ut_mapp, env=env or _env())
    logg(f"✓ Story renderad: {ut}")
    return {"ok": True, "path": str(ut), "moment": config["moment"]}
