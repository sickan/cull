"""Testläge — sökvägslogik för topbar-switchen (App.svelte `testMode`).

När switchen är på ska Live-story/SoMe/Webb-flödena köra sina RIKTIGA
pipelines (samma renderare/exportkod som skarpt) men skriva resultatet som
exempelfiler under en daterad testkatalog i stället för att posta till Meta,
skriva till Dropbox eller publicera till hemsidan. Katalogen är bara
engångsmaterial — får rensas fritt, rörs aldrig av skarpa flöden.

Se design_handoff_testlage/README.md (handoff-specen) för hela kontraktet.
"""

import shutil
from datetime import datetime
from pathlib import Path

TEST_ROT = Path.home() / "DPT" / "test-output"


def dagskatalog():
    return TEST_ROT / datetime.now().strftime("%Y-%m-%d")


def live_mapp():
    """Story-renderaren (story_overlay.skapa_story) skriver hit i stället för
    Dropbox-mappen — samma filnamnskonvention, bara katalogen skiljer."""
    p = dagskatalog() / "live"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ny_some_mapp():
    """En ny mapp per SoMe-paket-körning (HHMMSS). UI:t hämtar EN sådan innan
    fan-out:en (ett brygganrop per aktiv kanal) och återanvänder den för alla
    anropen, så hela paketets exempelfiler hamnar tillsammans."""
    p = dagskatalog() / ("some_paket_" + datetime.now().strftime("%H%M%S"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def kopiera_exempel(kalla, mal_mapp, namn):
    """Kopierar EN redan vald bild in i test-mappen som exempelfil för en
    kanal/post — SoMe-paketets bilder är redan färdiga filer (inget renderas
    om), testläge återanvänder bara den första som representant. Tyst
    best-effort: en trasig/saknad källfil ska aldrig stoppa testkörningen."""
    try:
        kalla = Path(kalla).expanduser()
        if not kalla.exists():
            return None
        mal = Path(mal_mapp) / f"{namn}{kalla.suffix or '.jpg'}"
        shutil.copyfile(kalla, mal)
        return mal
    except Exception:
        return None


def innehall_mapp(rel_dir):
    """test-output/content/<samma undermapp som skarpt, t.ex. 'matcher'>."""
    p = TEST_ROT / "content" / rel_dir
    p.mkdir(parents=True, exist_ok=True)
    return p
