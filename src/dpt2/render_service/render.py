"""Ren renderfunktion för Mobil Live Etapp 2 — molnrender av Horisont-storyn.

VIKTIGT: den här modulen implementerar INGEN grafik. Den importerar
`dpt2.motorer.story_overlay` OFÖRÄNDRAT och matar den med filer. Det finns
exakt EN Horisont-renderare i systemet, och den ligger kvar där den alltid
legat — annars hade varje designändring behövt göras två gånger och de två
implementationerna hade glidit isär.

Skillnaden mot desktop-anropet är bara VAR bitarna kommer ifrån:
- desktop: foto på disk, laglogotyper i `~/.config/dpt/loggor`
- molnet:  foto och loggor kommer som bytes (workern hämtar dem ur R2) och
           skrivs till temp-filer innan `skapa_story` får dem

`skapa_story` tar redan `hem_logga`/`borta_logga` som explicita sökvägar, så
inget behöver röras i renderaren. Utan explicita loggor faller den tillbaka på
`~/.config/dpt/loggor` — en katalog som INTE finns i en container, vilket tyst
hade gett monogram-fallback (fel branding). Därför skickar vi alltid in dem.
"""

import tempfile
from pathlib import Path

from dpt2.motorer import story_overlay

# Fält som skickas rakt igenom till skapa_story (namn = samma på båda sidor).
_GENOMSLAPP = (
    "liga", "stallning", "mal_rad", "avspark_tid", "arena", "next_when",
    "sport", "tema", "gren", "format", "zoom",
    "overlay", "scorers_layout",
)

MAX_BYTES = 25 * 1024 * 1024   # skydd mot orimliga uppladdningar


class RenderFel(ValueError):
    """Ogiltig renderförfrågan — ska bli 400, inte 500."""


def _skriv_temp(katalog, namn, data):
    """Skriver bytes till en temp-fil och returnerar sökvägen (eller None)."""
    if not data:
        return None
    if len(data) > MAX_BYTES:
        raise RenderFel(f"{namn} är för stor ({len(data)} byte)")
    p = Path(katalog) / namn
    p.write_bytes(data)
    return str(p)


def rendera(spec, *, foto, hem_logga=None, borta_logga=None):
    """Renderar en Horisont-story och returnerar bildens bytes.

    `spec` är matchdata (se _GENOMSLAPP + moment/lag_hemma/lag_borta/fokus).
    `foto`, `hem_logga`, `borta_logga` är RÅA BYTES (workern har hämtat dem ur
    R2). Loggor är valfria — utan dem ritar renderaren monogram-badge.
    """
    if not foto:
        raise RenderFel("foto krävs")
    moment = (spec.get("moment") or "").strip()
    if not moment:
        raise RenderFel("moment krävs")
    hemma = (spec.get("lag_hemma") or "").strip()
    borta = (spec.get("lag_borta") or "").strip()
    if not hemma or not borta:
        raise RenderFel("lag_hemma och lag_borta krävs")

    with tempfile.TemporaryDirectory(prefix="dpt-render-") as tmp:
        foto_p = _skriv_temp(tmp, "foto.jpg", foto)
        hem_p = _skriv_temp(tmp, "hem.png", hem_logga)
        borta_p = _skriv_temp(tmp, "borta.png", borta_logga)
        ut_p = Path(tmp) / "story.jpg"

        kwargs = {k: spec[k] for k in _GENOMSLAPP if spec.get(k) not in (None, "")}
        fokus = spec.get("fokus")
        if isinstance(fokus, dict) and "x" in fokus and "y" in fokus:
            kwargs["fokus"] = fokus

        try:
            story_overlay.skapa_story(
                foto_p, moment, hemma, borta,
                hem_logga=hem_p, borta_logga=borta_p,
                ut_path=str(ut_p), **kwargs)
        except RenderFel:
            raise
        except Exception as e:                     # trasig JPEG, okänt moment…
            raise RenderFel(f"kunde inte rendera: {e}") from e

        if not ut_p.exists():
            raise RenderFel("renderaren skrev ingen fil")
        return ut_p.read_bytes()
