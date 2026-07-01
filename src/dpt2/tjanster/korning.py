"""Körning — strukturerad IPC mot worker-processen (beslut 4: hybrid).

Tunga/kraschbenägna jobb (gallring, träning, nummer-pass, story-batch) körs i en
SEPARAT process (`python -m dpt2.worker`) för att isolera native-krascher/OOM och
hålla process-globala trådfaror borta från UI:t. Kommunikationen är STRUKTURERAD:
workern skriver ETT JSON-event per rad till stdout, här parsas och strömmas de
till en lyssnare — INTE regex på loggrader (som i gamla gui:s _stream).

Event-typer:
    start     {jobb}                       jobbet börjar
    progress  {andel 0–1, text}            framsteg
    logg      {niva: info|ok|fel, text}    loggrad
    klar      {resultat}                   klart, med resultat-dict
    fel       {text}                       fel (jobbet avbröts)
"""

import json
import subprocess
import sys

EVENTTYPER = ("start", "progress", "logg", "klar", "fel")


def event(typ, **data):
    """Bygger ett event-dict."""
    return {"typ": typ, **data}


def event_rad(ev):
    """Serialiserar ett event till en JSON-rad (workern skriver dessa)."""
    return json.dumps(ev, ensure_ascii=False)


def parsa_event(rad):
    """JSON-rad → event-dict. Icke-JSON eller okänd typ (t.ex. en bibliotek-
    varning på stdout) blir ett info-logg-event så inget tappas. Tom rad → None."""
    rad = (rad or "").rstrip("\n")
    if not rad.strip():
        return None
    try:
        ev = json.loads(rad)
    except Exception:
        return event("logg", niva="info", text=rad)
    if isinstance(ev, dict) and ev.get("typ") in EVENTTYPER:
        return ev
    return event("logg", niva="info", text=rad)


def kor_subprocess(args, lyssnare=None, *, python=None):
    """Kör `python -m dpt2.worker <args...>` och strömmar JSON-events.

    args:     argv till workern, t.ex. ["demo", '{"steg": 5}'].
    lyssnare: callable(event) som anropas för varje event (UI-progress), eller None.
    python:   python-binär (default sys.executable — kör i samma venv).

    Returnerar {returkod, events}. Blockerar tills processen är klar.
    """
    cmd = [python or sys.executable, "-m", "dpt2.worker", *args]
    events = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
        for rad in proc.stdout:
            ev = parsa_event(rad)
            if ev is None:
                continue
            events.append(ev)
            if lyssnare:
                lyssnare(ev)
    return {"returkod": proc.returncode, "events": events}
