"""Hämta laguppställning från nätet via Claude web search.

Två separata funktioner för olika tidpunkter i matchförberedelsen:
  hamta_spelare()      — dagar/veckor innan: trupp + handles från klubbsidor
  hamta_uppstallning() — ~1h innan: officiell startuppställning

Inget skrivs på bilder här. Kräver ANTHROPIC_API_KEY + anthropic-SDK.
"""

import json
import os
import re

MODELL = "claude-opus-4-8"

# --- Fas 1: spelartruppens profiler + handles --------------------------------

SYSTEM_SPELARE = (
    "Du är en sportresearcher. Din uppgift är att hitta spelartruppens "
    "profiler för de angivna lagen. "
    "Sök på lagets officiella webbsida (t.ex. lagnamn.se/spelare eller "
    "/trupp), på sportförbundets sida (Fogis, Profixio, innebandy.se, "
    "volleyboll.se) och på sociala medier. "
    "Hitta för varje spelare: tröjnummer, namn, position/roll och "
    "eventuell Instagram-handle. "
    "Täck HELA den registrerade truppen — inte bara startande. "
    "Sätt start=false för alla (startuppställning är inte känd ännu). "
    "Gissa ALDRIG ett personligt Instagram-konto: hittar du ingen handle, "
    "lämna fältet tomt; hittar du en men är osäker, lägg till '?' sist "
    "(t.ex. \"@spelaren?\"). Officiella lag-/förbundskonton är ok om du är säker. "
    "Ange vilka källor du använde. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)

SCHEMA_SPELARE = (
    '{"lag": {"hemma": "lagnamn", "borta": "lagnamn eller tom sträng"}, '
    '"spelare": [{"nr": "10", "namn": "Anna Svensson", "lag": "hemma", '
    '"start": false, "handle": "@annasvensson", "info": "spiker, lagkapten"}], '
    '"kallor": ["https://..."]}'
)

# --- Fas 2: officiell startuppställning ~1h innan ----------------------------

SYSTEM_UPPSTALLNING = (
    "Du är en sportresearcher. Din uppgift är att hitta den officiella "
    "startuppställningen för en specifik kommande match. "
    "Sök på lagets officiella kanaler (webbsida, X/Twitter, Instagram), "
    "sportdatabaser (Fogis, Profixio, innebandy.se, volleyboll.se), "
    "matchförhandsvisningar och sportjournalistik. "
    "Hitta: tröjnummer, spelarnamn och VILKA SOM STARTAR (start=true). "
    "Ta med avbytare om de listas (start=false). "
    "Lämna handle och info som tomma strängar — de hämtas separat. "
    "Hitta ALDRIG på nummer eller namn — ta bara med det du hittar i källorna. "
    "Ange vilka källor du använde. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)

SCHEMA_UPPSTALLNING = (
    '{"lag": {"hemma": "lagnamn", "borta": "lagnamn"}, '
    '"spelare": [{"nr": "10", "namn": "Anna Svensson", "lag": "hemma", '
    '"start": true, "handle": "", "info": ""}], '
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


def _kör_sökning(klient, fraga, system, max_uses, logg):
    """Kör ett web-search-anrop och returnerar parsad JSON eller None."""
    webb = {"type": "web_search_20260209", "name": "web_search",
            "max_uses": max_uses}
    messages = [{"role": "user", "content": fraga}]
    logg("Söker på nätet via Claude (web search)…")
    svar = None
    try:
        for _ in range(4):   # server-tool-loop: pause_turn → fortsätt (taktat)
            svar = klient.messages.create(
                model=MODELL, max_tokens=4000, system=system,
                tools=[webb], messages=messages)
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
    return data


def hamta_spelare(lag_hemma, lag_borta, sport="", logg=print):
    """Fas 1 — hämta spelartruppens profiler + handles från klubbsidor.
    Returnerar {lag, spelare:[{nr,namn,lag,start=false,handle,info}], kallor}
    eller None. Körs dagar/veckor innan match."""
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    import anthropic
    klient = anthropic.Anthropic(max_retries=4)
    delar = [d for d in [lag_hemma, lag_borta] if d]
    fraga = "Lag: " + " och ".join(delar) + "."
    if sport and sport.lower() not in ("", "auto"):
        fraga += f" Sport: {sport}."
    fraga += (f"\nHitta spelartruppens profiler (tröjnummer, namn, positioner, "
              f"Instagram-handles) och returnera JSON enligt detta schema:\n"
              f"{SCHEMA_SPELARE}")
    data = _kör_sökning(klient, fraga, SYSTEM_SPELARE, max_uses=10, logg=logg)
    if data:
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare. "
             "Granska och spara i matchen.")
    return data


def hamta_uppstallning(lag_hemma, lag_borta, datum, sport="", logg=print):
    """Fas 2 — hämta officiell startuppställning ~1h innan match.
    Returnerar {lag, spelare:[{nr,namn,lag,start,handle='',info=''}], kallor}
    eller None. handle/info är alltid tomma — bevaras från fas 1 vid merge."""
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    import anthropic
    klient = anthropic.Anthropic(max_retries=4)
    fraga = f"Match: {lag_hemma} vs {lag_borta}"
    if datum:
        fraga += f", {datum}"
    if sport and sport.lower() not in ("", "auto"):
        fraga += f". Sport: {sport}"
    fraga += (f".\nHitta den officiella startuppställningen och returnera JSON "
              f"enligt detta schema:\n{SCHEMA_UPPSTALLNING}")
    data = _kör_sökning(klient, fraga, SYSTEM_UPPSTALLNING, max_uses=8, logg=logg)
    if data:
        n_start = sum(1 for p in data.get("spelare", []) if p.get("start"))
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare "
             f"({n_start} startande). Granska och spara i matchen.")
    return data
