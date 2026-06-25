"""Hämta laguppställning + matchsammanfattning från nätet via Claude web search.

Ger ett FÖRSLAG (nummer→namn, vilka som startade, kort referat) som användaren
granskar/redigerar i GUI:t och kan spara som roster. Inget skrivs på bilder här —
detta producerar bara en roster-fil. Kräver ANTHROPIC_API_KEY + anthropic-SDK.
"""

import json
import os
import re

MODELL = "claude-opus-4-8"
# max_uses begränsar antalet sökningar → bundnar latens OCH kostnad (svåra/ej
# hittbara matcher gör annars att Claude söker i det oändliga).
WEBB_VERKTYG = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}

SYSTEM = (
    "Du är en sportresearcher. Använd web search för att hitta laguppställningen "
    "för den angivna matchen: spelarnas tröjnummer och namn, vilka som startade "
    "(startelva i fotboll, startande sex i volleyboll), samt ett kort sakligt "
    "referat på svenska (resultat och förlopp). "
    "Hitta ALDRIG på nummer eller namn — ta bara med det du hittar i källorna; "
    "utelämna spelare där du är osäker på numret. Ange vilka källor du använde. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)

SCHEMA = (
    '{"sammanfattning": "kort referat på svenska", '
    '"lag": {"hemma": "lagnamn", "borta": "lagnamn"}, '
    '"spelare": [{"nr": "10", "namn": "Isabelle Haak", "lag": "hemma", "start": true}], '
    '"kallor": ["https://..."]}'
)


def tillganglig():
    """True om SDK + API-nyckel finns."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _parsa(text):
    """Plockar ut JSON-objektet ur svaret (tål omgivande text/kodstaket)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def hamta(matchinfo, sport="", logg=print):
    """Returnerar dict {sammanfattning, lag, spelare:[{nr,namn,lag,start}], kallor}
    eller None. matchinfo = "Hemma - Borta R-R ÅÅÅÅMMDD Arena"."""
    matchinfo = (matchinfo or "").strip()
    if not matchinfo:
        logg("⚠ Ingen matchinfo angiven.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas — kan inte hämta.")
        return None

    import anthropic
    klient = anthropic.Anthropic(max_retries=4)
    fraga = f"Match: {matchinfo}."
    if sport and sport.lower() != "auto":
        fraga += f" Sport: {sport}."
    fraga += f"\nHitta laguppställningen och returnera JSON enligt detta schema:\n{SCHEMA}"

    messages = [{"role": "user", "content": fraga}]
    logg("Söker på nätet via Claude (web search)…")
    svar = None
    try:
        for _ in range(4):   # server-tool-loop: pause_turn → fortsätt (takat)
            svar = klient.messages.create(
                model=MODELL, max_tokens=4000, system=SYSTEM,
                tools=[WEBB_VERKTYG], messages=messages)
            if svar.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": svar.content})
                continue
            break
    except Exception as e:
        logg(f"⚠ Web search misslyckades: {type(e).__name__}: {e}")
        return None

    if svar is None or svar.stop_reason == "refusal":
        logg("⚠ Inget svar (eller avböjt).")
        return None
    text = "".join(b.text for b in svar.content if b.type == "text")
    data = _parsa(text)
    if not data:
        logg("⚠ Kunde inte tolka svaret som JSON.")
        return None
    spelare = data.get("spelare", [])
    logg(f"✓ Hittade {len(spelare)} spelare. Granska och spara som roster.")
    return data
