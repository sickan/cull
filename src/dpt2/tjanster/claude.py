"""En Anthropic-tjänst som ersätter det duplicerade mönstret i hamta_match /
las_lineup / bildsvep / bildtext_ai (OMSKRIVNING.md §3 fynd 4).

Allt går via `messages.create` + pause_turn-loop + kostnadstak. Klienten
INJICERAS (ny_klient() i drift, fejk i test) så orkestreringen är enhetstestbar
utan skarpa anrop. Web-sökning = samma loop med web_search-verktyget; vision =
samma loop med bild-block i meddelandet.
"""

import json
import os
import re

MODELL = "claude-opus-4-8"

# Ungefärliga priser för claude-opus-4-8 (USD/token, exkl. web search-avgifter).
PRIS_IN = 15.0 / 1_000_000
PRIS_UT = 75.0 / 1_000_000


def max_kostnad():
    """Kostnadstak/anrop i USD (env CULL_MAX_KOSTNAD_USD, default 2.00)."""
    return float(os.environ.get("CULL_MAX_KOSTNAD_USD", "2.00"))


def tillganglig():
    """True om API-nyckel + anthropic-SDK finns."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def ny_klient(max_retries=4):
    import anthropic
    return anthropic.Anthropic(max_retries=max_retries)


def parsa_json(text):
    """Plockar ut JSON-objektet ur svaret (tål kodstaket/omgivande text)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def web_search_verktyg(max_uses=6):
    return {"type": "web_search_20260209", "name": "web_search",
            "max_uses": max_uses}


class Kostnad:
    """Ackumulerar token → USD och vaktar mot taket."""

    def __init__(self, tak=None):
        self.tak = tak if tak is not None else max_kostnad()
        self.in_tok = 0
        self.ut_tok = 0

    def lagg_till(self, usage):
        if not usage:
            return
        self.in_tok += getattr(usage, "input_tokens", 0) or 0
        self.ut_tok += getattr(usage, "output_tokens", 0) or 0

    @property
    def usd(self):
        return self.in_tok * PRIS_IN + self.ut_tok * PRIS_UT

    def over_tak(self):
        return self.usd >= self.tak


def _text_ur(svar):
    return "".join(getattr(b, "text", "") for b in getattr(svar, "content", [])
                   if getattr(b, "type", "") == "text")


def bild_base64(path, max_kant=1024):
    """Läser en bild, skalar ned till max_kant och returnerar base64-JPEG-sträng
    (för vision). Kräver cv2. Returnerar None vid fel."""
    try:
        import base64
        import cv2
    except Exception:
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > max_kant:
        s = max_kant / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode()


def _bild_block(b64):
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}


def fraga_json(klient, system, fraga, *, modell=MODELL, max_tokens=4000,
               verktyg=None, max_varv=4, logg=print, kostnad=None):
    """Skickar en fråga och returnerar parsad JSON (eller None).

    Hanterar pause_turn-loopen (server-verktyg som web_search pausar turen) och
    kostnadstaket. `verktyg` = t.ex. web_search_verktyg() för web-sök; None för
    rena JSON-svar. `kostnad` kan delas mellan flera anrop.
    """
    messages = [{"role": "user", "content": fraga}]
    return _kor(klient, system, messages, modell, max_tokens, verktyg,
                max_varv, logg, kostnad)


def fraga_json_vision(klient, system, text, bild_paths, *, modell=MODELL,
                      max_tokens=4000, max_kant=1024, max_varv=4, logg=print,
                      kostnad=None):
    """Som fraga_json men med bilder (vision). bild_paths skalas + base64:as."""
    innehall = []
    for p in (bild_paths or []):
        b64 = bild_base64(p, max_kant)
        if b64:
            innehall.append(_bild_block(b64))
    innehall.append({"type": "text", "text": text})
    messages = [{"role": "user", "content": innehall}]
    return _kor(klient, system, messages, modell, max_tokens, None,
                max_varv, logg, kostnad)


def _kor(klient, system, messages, modell, max_tokens, verktyg, max_varv,
         logg, kostnad):
    kostnad = kostnad or Kostnad()
    extra = {"tools": [verktyg]} if verktyg else {}
    svar = None
    for _ in range(max_varv):
        try:
            svar = klient.messages.create(
                model=modell, max_tokens=max_tokens, system=system,
                messages=messages, **extra)
        except Exception as e:
            logg(f"⚠ {type(e).__name__}: {e}")
            return None
        kostnad.lagg_till(getattr(svar, "usage", None))
        if kostnad.over_tak():
            logg(f"⚠ Kostnadstak ${kostnad.tak:.2f} nått (~${kostnad.usd:.3f}).")
            break
        if getattr(svar, "stop_reason", "") == "pause_turn":
            messages.append({"role": "assistant", "content": svar.content})
            continue
        break
    if svar is None or getattr(svar, "stop_reason", "") == "refusal":
        logg("⚠ Inget svar (eller avböjt).")
        return None
    data = parsa_json(_text_ur(svar))
    if data is None:
        logg("⚠ Kunde inte tolka svaret som JSON.")
    return data
