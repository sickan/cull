"""Astro-export (KÄRNA): match-/innehållsobjekt → Markdown (.md med YAML-
frontmatter) för sajtens content-collections.

Ren sträng-generering, stdlib only (ingen PyYAML) — fullt enhetstestbar. Fälten
speglar OMSKRIVNING §5: hero/heroPosition (omslagsväljare), pixieset (galleri-
länk), malskyttar, samt figur-block (bild+alt+bildtext) i brödtexten.

Skrivvägen (`skriv_md`) är enda I/O:t; allt annat är rena funktioner.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# Plain (ociterad) YAML-skalär: bokstav/siffra först, sen ofarliga tecken. Allt
# annat (kolon+blanksteg, #, citattecken, ledande indikatortecken, tom sträng,
# sådant som kan misstas för tal/bool) dubbelciteras.
_SAFE_PLAIN = re.compile(r"^[A-Za-z0-9åäöÅÄÖ][\wåäöÅÄÖ .\-/–·']*$")
_SER_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_RESERVERAT = {"true", "false", "null", "yes", "no", "on", "off", "~"}


def _yaml_skalar(v):
    """Serialiserar en skalär till YAML (plain när säkert, annars dubbelciterad)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = "" if v is None else str(v)
    if (s and _SAFE_PLAIN.match(s) and s.lower() not in _RESERVERAT
            and not _SER_NUM.match(s) and ": " not in s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def frontmatter_yaml(d):
    """dict → YAML-block (utan ---). Hoppar över None/tomma. Listor blir block-
    sekvenser; nycklar i insättningsordning (Python 3.7+ dict ordnar)."""
    rader = []
    for nyckel, varde in d.items():
        if varde is None or varde == "" or varde == []:
            continue
        if isinstance(varde, (list, tuple)):
            rader.append(f"{nyckel}:")
            rader += [f"  - {_yaml_skalar(x)}" for x in varde if x not in (None, "")]
        else:
            rader.append(f"{nyckel}: {_yaml_skalar(varde)}")
    return "\n".join(rader)


@dataclass
class Figur:
    """Ett figur-block i brödtexten: bild + alt-text + bildtext (valfri)."""
    bild: str
    alt: str = ""
    bildtext: str = ""

    def markdown(self):
        rader = [f"![{self.alt}]({self.bild})"]
        if self.bildtext:
            rader.append(f"*{self.bildtext}*")
        return "\n".join(rader)


def figurer_markdown(figurer):
    """Lista av Figur (eller dict) → markdown-block separerade med blankrad."""
    block = []
    for f in figurer or []:
        if isinstance(f, dict):
            f = Figur(bild=f.get("bild", ""), alt=f.get("alt", ""),
                      bildtext=f.get("bildtext", ""))
        if f.bild:
            block.append(f.markdown())
    return "\n\n".join(block)


def render_md(frontmatter, body=""):
    """Komplett .md: '---\\n<yaml>\\n---\\n\\n<body>\\n'. frontmatter = dict."""
    yaml = frontmatter_yaml(frontmatter)
    text = f"---\n{yaml}\n---\n"
    if body and body.strip():
        text += f"\n{body.rstrip()}\n"
    return text


def match_innehall(match, *, hero=None, hero_position=None, pixieset=None,
                   malskyttar=None, figurer=None, body="", status=None,
                   typ="match"):
    """Bygger {frontmatter, body, slug} för ett match-innehåll ur ett match-
    objekt (store.hamta_match-form). malskyttar kan vara lista eller
    kommaseparerad sträng. figurer läggs sist i brödtexten."""
    hemma = match.get("lag_hemma", "")
    borta = match.get("lag_borta", "")
    titel = f"{hemma} – {borta}".strip(" –")
    if isinstance(malskyttar, str):
        malskyttar = [m.strip() for m in malskyttar.split(",") if m.strip()]
    fm = {
        "typ": typ,
        "titel": titel,
        "datum": match.get("datum"),
        "lag_hemma": hemma,
        "lag_borta": borta,
        "liga": match.get("liga"),
        "arena": match.get("arena"),
        "resultat": match.get("resultat"),
        "status": status or match.get("status"),
        "hero": hero,
        "heroPosition": hero_position,
        "pixieset": pixieset,
        "malskyttar": malskyttar,
    }
    figur_md = figurer_markdown(figurer)
    hel_body = "\n\n".join(p for p in (body.rstrip() if body else "", figur_md) if p)
    return {"frontmatter": fm, "body": hel_body, "slug": slugga(titel)}


def slugga(text):
    """Svensk-vänlig slug: gemener, å/ä/ö→a/a/o, mellanslag→bindestreck."""
    s = (text or "").lower()
    for a, b in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("&", "och")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "innehall"


def skriv_md(text, export_dir, slug):
    """Skriver <export_dir>/<slug>.md (skapar mappen). Returnerar Path."""
    d = Path(export_dir)
    d.mkdir(parents=True, exist_ok=True)
    ut = d / f"{slug}.md"
    ut.write_text(text, encoding="utf-8")
    return ut
