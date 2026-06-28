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

# Ungefärliga priser för claude-opus-4-8 (USD per token, exkl. web search-avgifter).
# Uppdatera vid prisändring: https://www.anthropic.com/pricing
_PRIS_IN = 15.0 / 1_000_000   # $15/MTok input
_PRIS_UT = 75.0 / 1_000_000   # $75/MTok output

# Timeout i sekunder per streaming-runda.
_TIMEOUT_SPELARE     = 120.0   # fas 1: fler sökningar, mer tid
_TIMEOUT_UPPSTALLNING =  90.0  # fas 2: färre sökningar

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


def _kör_sökning(klient, fraga, system, max_uses, logg, timeout=120.0):
    """Kör ett web-search-anrop och returnerar parsad JSON eller None.

    Feedback-strategi:
      • Ticker-tråd loggar "⏳ Xs…" var 10:e sekund — alltid, oberoende av events.
      • Stream-events: fångar web_search tool_use i realtid om de levereras.
      • Fallback post-runda: sökfrågor ur final.content om events missades.
    Timeout: ticker avbryter efter 'timeout' sekunder totalt (via ticker_timed_out-
    flagga + break i event-loopen). Inaktivitetstimeout = 60 s (stream-parameter).
    """
    import time
    import threading
    import anthropic as _ant
    webb = {"type": "web_search_20260209", "name": "web_search",
            "max_uses": max_uses}
    messages = [{"role": "user", "content": fraga}]
    logg("Söker på nätet via Claude (web search)…")
    final = None
    tot_in = tot_ut = 0

    try:
        for _ in range(4):   # server-tool-loop: pause_turn → fortsätt
            tool_namn = None
            tool_json = ""
            stream_queries = []
            timed_out = False
            t0 = time.monotonic()

            # Ticker: synlig aktivitet var 10:e sekund, startas innan stream
            ticker_stop = threading.Event()
            ticker_timed_out = threading.Event()

            def _ticker(stop=ticker_stop, to=ticker_timed_out,
                        start=t0, lim=timeout):
                while not stop.wait(10.0):
                    elapsed = time.monotonic() - start
                    if elapsed > lim:
                        to.set()   # signalera timeout till huvud-tråden
                        logg(f"⚠ Timeout ({lim:.0f} s) — sökningen avbröts.")
                        break
                    logg(f"⏳ {int(elapsed)} s…")

            threading.Thread(target=_ticker, daemon=True).start()

            try:
                with klient.messages.stream(
                        model=MODELL, max_tokens=4000, system=system,
                        tools=[webb], messages=messages,
                        timeout=60.0) as stream:   # 60 s inaktivitetstimeout
                    for ev in stream:
                        if ticker_timed_out.is_set():
                            timed_out = True
                            break
                        etype = getattr(ev, "type", "")
                        if etype == "content_block_start":
                            cb = ev.content_block
                            if getattr(cb, "type", "") in (
                                    "tool_use", "server_tool_use") \
                                    and getattr(cb, "name", "") == "web_search":
                                tool_namn = "web_search"
                                tool_json = ""
                            else:
                                tool_namn = None
                        elif etype == "content_block_delta":
                            d = ev.delta
                            if tool_namn == "web_search" \
                                    and getattr(d, "type", "") \
                                    == "input_json_delta":
                                tool_json += getattr(d, "partial_json", "") or ""
                        elif etype == "content_block_stop" \
                                and tool_namn == "web_search":
                            try:
                                q = json.loads(
                                    tool_json or "{}").get("query", "")
                                if q:
                                    logg(f"🔍 {q}")
                                    stream_queries.append(q)
                            except Exception:
                                pass
                            tool_namn = None
                    if not timed_out:
                        final = stream.get_final_message()

            except _ant.APITimeoutError:
                logg("⚠ Inaktivitet >60 s — servern svarar inte.")
                return None
            except _ant.APIStatusError as e:
                logg(f"⚠ API-fel {e.status_code}: {e.message}")
                return None
            except _ant.APIConnectionError as e:
                logg(f"⚠ Nätverksfel: {e}")
                return None
            finally:
                ticker_stop.set()   # stoppa ticker oavsett utfall

            if timed_out:
                return None

            # Fallback: sökfrågor ur final.content om streaming-events missades
            if not stream_queries:
                for block in getattr(final, "content", []):
                    bt = getattr(block, "type", "")
                    if bt in ("tool_use", "server_tool_use") \
                            and getattr(block, "name", "") == "web_search":
                        q = (getattr(block, "input", {}) or {}).get("query", "")
                        if q:
                            logg(f"🔍 {q}")

            # Token-förbrukning + uppskattad kostnad
            usage = getattr(final, "usage", None)
            if usage:
                in_tok  = getattr(usage, "input_tokens",  0) or 0
                out_tok = getattr(usage, "output_tokens", 0) or 0
                tot_in += in_tok
                tot_ut += out_tok
                kostnad = tot_in * _PRIS_IN + tot_ut * _PRIS_UT
                logg(f"📊 {tot_in + tot_ut:,} token · ~${kostnad:.3f}")

            if final.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": final.content})
                continue
            break

    except Exception as e:
        logg(f"⚠ Oväntat fel: {type(e).__name__}: {e}")
        return None

    if final is None or final.stop_reason == "refusal":
        logg("⚠ Inget svar (eller avböjt).")
        return None
    text = "".join(getattr(b, "text", "") for b in getattr(final, "content", [])
                   if getattr(b, "type", "") == "text")
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
    data = _kör_sökning(klient, fraga, SYSTEM_SPELARE, max_uses=10, logg=logg,
                       timeout=_TIMEOUT_SPELARE)
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
    data = _kör_sökning(klient, fraga, SYSTEM_UPPSTALLNING, max_uses=8, logg=logg,
                       timeout=_TIMEOUT_UPPSTALLNING)
    if data:
        n_start = sum(1 for p in data.get("spelare", []) if p.get("start"))
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare "
             f"({n_start} startande). Granska och spara i matchen.")
    return data
