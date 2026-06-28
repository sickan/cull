"""Hämta laguppställning från nätet via Claude web search.

Två separata funktioner för olika tidpunkter i matchförberedelsen:
  hamta_spelare()      — dagar/veckor innan: trupp från officiella klubbsidor
  hamta_uppstallning() — ~1h innan: officiell startuppställning

Klubbregistret (KLUBBAR) pekar Claude direkt till rätt URL:er. Utan känd
URL faller koden tillbaka på fri web-sökning. Lägg till nya lag i KLUBBAR
— ingen annan kodändring behövs.

Kräver ANTHROPIC_API_KEY + anthropic-SDK.
"""

import json
import os
import re

MODELL = "claude-opus-4-8"

# Ungefärliga priser för claude-opus-4-8 (USD per token, exkl. web search-avgifter).
# Uppdatera vid prisändring: https://www.anthropic.com/pricing
_PRIS_IN = 15.0 / 1_000_000   # $15/MTok input
_PRIS_UT = 75.0 / 1_000_000   # $75/MTok output

# Kostnadsgräns per anrop (USD). Kontrolleras efter varje runda.
# Ändra värdet här eller sätt miljövariabeln CULL_MAX_KOSTNAD_USD.
import os as _os
_MAX_KOSTNAD_USD = float(_os.environ.get("CULL_MAX_KOSTNAD_USD", "2.00"))

# Timeout i sekunder per streaming-runda.
_TIMEOUT_SPELARE      = 180.0   # fas 1: upp till 10 sökningar
_TIMEOUT_UPPSTALLNING =  90.0   # fas 2: färre sökningar

# ---------------------------------------------------------------------------
# Klubbregister — utöka med fler lag, ingen annan kodändring behövs.
# Nycklar: lagnamn i lowercase, trimmat. Alla varianter av samma lag.
# squad_url  : officiell truppsida (primär källa — alltid prioriteras)
# matches_url: officiell matchsida (används av hamta_uppstallning)
# ig         : officiellt klubb-Instagram-konto (utan @)
# ---------------------------------------------------------------------------
KLUBBAR = {
    # --- Damallsvenskan ---
    "fc rosengård": {
        "squad_url":   "https://www.fcrosengard.se/sv/players",
        "matches_url": "https://www.fcrosengard.se/sv/matches",
        "ig": "fcrosengard",
    },
    "eskilstuna united": {
        "squad_url":   "https://eskilstunaunited.se/truppen/",
        "matches_url": "https://eskilstunaunited.se/allsvenskan-2026/",
        "ig": "eskilstunaunited",
    },
    "eskilstuna united dff": {
        "squad_url":   "https://eskilstunaunited.se/truppen/",
        "matches_url": "https://eskilstunaunited.se/allsvenskan-2026/",
        "ig": "eskilstunaunited",
    },
    # Lägg till fler lag här:
    # "djurgårdens if dam": {
    #     "squad_url": "https://www.difdam.se/spelare/",
    #     "matches_url": "https://www.difdam.se/matcher/",
    #     "ig": "difdam",
    # },
}


def _klub(namn: str) -> dict:
    """Returnerar KLUBBAR-post för lagnamnet (case-insensitive), eller {}."""
    return KLUBBAR.get((namn or "").strip().lower(), {})


# ---------------------------------------------------------------------------
# Fas 1 — system + schema
# ---------------------------------------------------------------------------
SYSTEM_SPELARE = (
    "Du är en sportresearcher. Din uppgift är att hämta hela spelartruppen "
    "från klubbens OFFICIELLA hemsida. "
    "Om en URL anges: besök den direkt utan att söka via Google. "
    "Om ingen URL anges: hitta klubbens officiella webbsida och gå till truppsidan. "
    "Officiell klubbsida är alltid facit — tredjepartssidor som Transfermarkt, "
    "Sofascore, Wikipedia och liknande har ofta föråldrade uppgifter och felaktiga "
    "klubbtillhörigheter (spelare som bytts ut listas fortfarande). Använd dem "
    "bara för komplement (position, nationalitet) om det saknas på klubbsidan. "
    "Täck HELA truppen — alla positioner och ledarstab om den är listad. "
    "Sätt start=false för alla spelare (startuppställning är inte känd ännu). "
    "Instagram-handles: om du stöter på en verifierad handle i klubbens egna "
    "kanaler, ta med den. Gissa ALDRIG — lämna tomt snarare än att gissa. "
    "Om du hittar en handle men är osäker, lägg till '?' sist (t.ex. '@spelaren?'). "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)

SCHEMA_SPELARE = (
    '{"lag": {"hemma": "lagnamn", "borta": "lagnamn eller tom sträng"}, '
    '"spelare": [{"nr": "10", "namn": "Remy Siemsen", "lag": "hemma", '
    '"start": false, "handle": "@remyysiemsen", "info": "Forward"}], '
    '"kallor": ["https://www.fcrosengard.se/sv/players"]}'
)

# ---------------------------------------------------------------------------
# Fas 2 — system + schema
# ---------------------------------------------------------------------------
SYSTEM_UPPSTALLNING = (
    "Du är en sportresearcher. Din uppgift är att hitta den officiella "
    "startuppställningen för en specifik kommande match. "
    "Om en URL anges: besök den direkt utan att söka via Google. "
    "Sök annars på klubbarnas officiella kanaler (webbsida, X/Twitter, Instagram) "
    "och sportdatabaser (Fogis, Profixio). "
    "Hitta: tröjnummer, spelarnamn och VILKA SOM STARTAR (start=true). "
    "Ta med avbytare om de listas (start=false). "
    "Hitta ALDRIG på nummer eller namn — ta bara med det som finns i källorna. "
    "Lämna handle och info som tomma strängar — de hämtas separat. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)

SCHEMA_UPPSTALLNING = (
    '{"lag": {"hemma": "lagnamn", "borta": "lagnamn"}, '
    '"spelare": [{"nr": "10", "namn": "Remy Siemsen", "lag": "hemma", '
    '"start": true, "handle": "", "info": ""}], '
    '"kallor": ["https://..."]}'
)


# ---------------------------------------------------------------------------
# Hjälpfunktioner
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Kärn-streaming-funktion
# ---------------------------------------------------------------------------

def _kör_sökning(klient, fraga, system, max_uses, logg, timeout=120.0):
    """Kör ett web-search-anrop och returnerar parsad JSON eller None.

    Feedback:
      • Ticker-tråd loggar "⏳ Xs…" var 10:e sekund oberoende av events.
      • Stream-events: fångar web_search tool_use i realtid om de levereras.
      • Fallback post-runda: sökfrågor ur final.content om events missades.
    Timeout: ticker avbryter efter 'timeout' sekunder totalt.
    Inaktivitetstimeout: 60 s (stream-parametern — fångar hängande anrop).
    """
    import time
    import threading
    import anthropic as _ant

    webb = {"type": "web_search_20260209", "name": "web_search",
            "max_uses": max_uses}
    messages = [{"role": "user", "content": fraga}]

    # Logga exakt prompt — i GUI-overlay och i terminalen (kopierbar)
    logg(f"Modell: {MODELL} · cap ${_MAX_KOSTNAD_USD:.2f}")
    logg("── SYSTEM ──")
    for rad in system.split(". "):
        if rad.strip():
            logg(rad.strip() + ".")
    logg("── FRÅGA ──")
    for rad in fraga.split("\n"):
        if rad.strip():
            logg(rad.strip())
    logg("────────────")
    print("\n=== HAMTA_MATCH PROMPT ===")
    print(f"[SYSTEM]\n{system}\n")
    print(f"[USER]\n{fraga}\n")
    print("=========================\n", flush=True)

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

            ticker_stop = threading.Event()
            ticker_timed_out = threading.Event()

            def _ticker(stop=ticker_stop, to=ticker_timed_out,
                        start=t0, lim=timeout):
                while not stop.wait(10.0):
                    elapsed = time.monotonic() - start
                    if elapsed > lim:
                        to.set()
                        logg(f"⚠ Timeout ({lim:.0f} s) — sökningen avbröts.")
                        break
                    logg(f"⏳ {int(elapsed)} s…")

            threading.Thread(target=_ticker, daemon=True).start()

            try:
                with klient.messages.stream(
                        model=MODELL, max_tokens=4000, system=system,
                        tools=[webb], messages=messages,
                        timeout=60.0) as stream:
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
                ticker_stop.set()

            if timed_out:
                return None

            if not stream_queries:
                for block in getattr(final, "content", []):
                    bt = getattr(block, "type", "")
                    if bt in ("tool_use", "server_tool_use") \
                            and getattr(block, "name", "") == "web_search":
                        q = (getattr(block, "input", {}) or {}).get("query", "")
                        if q:
                            logg(f"🔍 {q}")

            usage = getattr(final, "usage", None)
            if usage:
                in_tok  = getattr(usage, "input_tokens",  0) or 0
                out_tok = getattr(usage, "output_tokens", 0) or 0
                tot_in += in_tok
                tot_ut += out_tok
                kostnad = tot_in * _PRIS_IN + tot_ut * _PRIS_UT
                logg(f"📊 {tot_in + tot_ut:,} tok · ~${kostnad:.3f}"
                     f" / gräns ${_MAX_KOSTNAD_USD:.2f}")
                if kostnad >= _MAX_KOSTNAD_USD:
                    logg(f"⚠ Kostnadsgräns ${_MAX_KOSTNAD_USD:.2f} nådd.")
                    break

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


# ---------------------------------------------------------------------------
# Publika funktioner
# ---------------------------------------------------------------------------

def hamta_spelare(lag_hemma, lag_borta, sport="", logg=print):
    """Fas 1 — hämta spelartruppen från officiella klubbsidor.

    Kända lag (i KLUBBAR-registret) pekas ut med direkta URL:er.
    Okända lag faller tillbaka på fri web-sökning.
    Returnerar {lag, spelare:[{nr,namn,lag,start=false,handle,info}], kallor}
    eller None.
    """
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    import anthropic
    klient = anthropic.Anthropic(max_retries=4)

    # Bygg riktad fråga med URL:er där vi känner till dem
    lag_rader = []
    for namn in [lag_hemma, lag_borta]:
        if not namn:
            continue
        k = _klub(namn)
        url = k.get("squad_url")
        if url:
            lag_rader.append(f"- {namn}: besök {url}")
        else:
            lag_rader.append(f"- {namn}: hitta officiell truppsida")

    fraga = "Hämta spelartruppen för:\n" + "\n".join(lag_rader)
    if sport and sport.lower() not in ("", "auto"):
        fraga += f"\nSport: {sport}"
    fraga += f"\n\nReturnera JSON:\n{SCHEMA_SPELARE}"

    data = _kör_sökning(klient, fraga, SYSTEM_SPELARE, max_uses=10, logg=logg,
                        timeout=_TIMEOUT_SPELARE)
    if data:
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare. "
             "Granska och spara i matchen.")
    return data


def hamta_uppstallning(lag_hemma, lag_borta, datum, sport="", logg=print):
    """Fas 2 — hämta officiell startuppställning ~1h innan match.

    Returnerar {lag, spelare:[{nr,namn,lag,start,handle='',info=''}], kallor}
    eller None. handle/info är alltid tomma — bevaras från fas 1 vid merge.
    """
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    if not tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    import anthropic
    klient = anthropic.Anthropic(max_retries=4)

    # Bygg riktad fråga med match-URL:er där vi känner till dem
    match_rader = []
    for namn in [lag_hemma, lag_borta]:
        if not namn:
            continue
        k = _klub(namn)
        url = k.get("matches_url")
        if url:
            match_rader.append(f"- {namn}: {url}")

    fraga = f"Match: {lag_hemma} vs {lag_borta}"
    if datum:
        fraga += f", {datum}"
    if sport and sport.lower() not in ("", "auto"):
        fraga += f". Sport: {sport}"
    if match_rader:
        fraga += "\nOfficiel matchinfo på:\n" + "\n".join(match_rader)
    fraga += f"\n\nReturnera JSON:\n{SCHEMA_UPPSTALLNING}"

    data = _kör_sökning(klient, fraga, SYSTEM_UPPSTALLNING, max_uses=8, logg=logg,
                        timeout=_TIMEOUT_UPPSTALLNING)
    if data:
        n_start = sum(1 for p in data.get("spelare", []) if p.get("start"))
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare "
             f"({n_start} startande). Granska och spara i matchen.")
    return data
