"""Läs ett laguppställnings-ark (foto/PDF/skärmdump) med Claude vision.

Ger roster (nr→namn), startelva/startsexa, och en matchinfo-sträng (som också
blir katalognamnet). Primär roster-källa — du har oftast det officiella arket i
handen direkt efter match, mer pålitligt än webbsök. Hittar ALDRIG på nummer/namn.
"""

import base64
import io
import os
import subprocess
import tempfile
from pathlib import Path

MODELL = "claude-opus-4-8"
MAX_KANT = 2000          # lineup-text behöver upplösning → större än bildtext-AI
HEIC_SUFFIX = {".heic", ".heif"}
BILD_SUFFIX = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

SYSTEM = (
    "Du läser ett officiellt laguppställnings-ark (line-up/team sheet) för en "
    "sportmatch och returnerar ENBART ett JSON-objekt enligt schemat — ingen "
    "annan text.\n"
    "- Extrahera varje spelares tröjnummer och namn för BÅDA lagen.\n"
    "- Markera målvakt (mv=true) och kapten (kapten=true) om det framgår "
    "(GK/MV, C/©).\n"
    "- Om arket visar en startuppställning (t.ex. 11 i fotboll, 6 i volleyboll, "
    "ofta även en formationsruta) sätt start=true för de spelarna.\n"
    "- Bestäm hemmalag: oftast arenans/värdlandets lag eller laget som listas "
    "först (lag='hemma'), motståndaren 'borta'.\n"
    "- Använd svenska namnformer för länder (Sweden→Sverige, Italy→Italien).\n"
    "- Bygg 'matchinfo' i formatet: '(D) eller (H) Hemma - Borta ÅÅÅÅMMDD Arena' "
    "— (D)=dam om det är Women's, (H)=herr om Men's. Lämna PLATS för resultatet "
    "men gissa det INTE (arket är oftast skrivet före match): skriv ingen "
    "resultatsiffra om den inte tydligt står på arket.\n"
    "- Hitta ALDRIG på nummer eller namn; utelämna det du inte kan läsa säkert."
)

SCHEMA = (
    '{"matchinfo": "(D) Sverige - Italien 20260609 Gamla Ullevi", '
    '"lag": {"hemma": "Sverige", "borta": "Italien"}, '
    '"datum": "20260609", "arena": "Gamla Ullevi", '
    '"spelare": [{"nr": "12", "namn": "Jennifer Falk", "lag": "hemma", '
    '"start": true, "mv": true, "kapten": false}]}'
)


def tillganglig():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _innehall_block(path):
    """Returnerar ett Anthropic-content-block för bilden/PDF:en, eller None.
    HEIC→JPEG (sips), PDF skickas som dokument, övriga bilder nedskalas (PIL)."""
    p = Path(path)
    suf = p.suffix.lower()

    if suf == ".pdf":
        try:
            data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
        except Exception:
            return None
        return {"type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": data}}

    jpg = p
    tmp = None
    if suf in HEIC_SUFFIX:
        tmp = Path(tempfile.mkdtemp()) / "ark.jpg"
        try:
            subprocess.run(["sips", "-s", "format", "jpeg", str(p),
                            "--out", str(tmp)], check=True,
                           capture_output=True)
            jpg = tmp
        except Exception:
            return None
    elif suf not in BILD_SUFFIX:
        return None

    try:
        from PIL import Image
        img = Image.open(jpg)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((MAX_KANT, MAX_KANT))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}


def _parsa(text):
    import json
    import re
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def las(filsokvag, sport="", logg=print):
    """Returnerar dict {matchinfo, lag, datum, arena, spelare:[...]} eller None."""
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas — kan inte läsa arket.")
        return None
    block = _innehall_block(filsokvag)
    if block is None:
        logg(f"⚠ Kunde inte läsa filen ({Path(filsokvag).suffix}). "
             "Stöder HEIC/JPG/PNG/PDF.")
        return None

    import anthropic
    klient = anthropic.Anthropic(max_retries=4)
    fraga = "Läs laguppställnings-arket och returnera JSON enligt schemat:\n" + SCHEMA
    if sport and sport.lower() != "auto":
        fraga = f"Sport: {sport}.\n" + fraga
    logg("Läser laguppställnings-arket med Claude vision…")
    try:
        svar = klient.messages.create(
            model=MODELL, max_tokens=4000, system=SYSTEM,
            messages=[{"role": "user", "content": [block, {"type": "text", "text": fraga}]}])
    except Exception as e:
        logg(f"⚠ Vision-läsning misslyckades: {type(e).__name__}: {e}")
        return None

    text = "".join(b.text for b in svar.content if b.type == "text")
    data = _parsa(text)
    if not data:
        logg("⚠ Kunde inte tolka arket som JSON.")
        return None
    spelare = data.get("spelare", [])
    logg(f"✓ Läste {len(spelare)} spelare. Granska, använd matchinfo och spara roster.")
    return data
