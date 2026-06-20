"""Matchfas-bonus baserad på tidsstämpel och avspark."""

from datetime import datetime


def parse_tid(s):
    try:
        s = s.replace(":", "-", 2)
        return datetime.fromisoformat(s.strip()).timestamp()
    except Exception:
        return None


def parse_avspark(avspark_str, referensdatum):
    """
    Tolka '--avspark HH:MM' mot referensdatumet från första NEF-filens tidsstämpel.
    Returnerar ett Unix-timestamp.
    """
    try:
        h, m = map(int, avspark_str.split(":"))
        dt = referensdatum.replace(hour=h, minute=m, second=0, microsecond=0)
        return dt.timestamp()
    except Exception:
        return None


def matchminut(ts, avspark_ts):
    """Minuter sedan avspark (kan vara negativ = före avspark)."""
    return (ts - avspark_ts) / 60.0


def fas_bonus(minut):
    """
    Ger bonus för dramatiska skeden i matchen.
    Slutminuterna i varje halvlek värderas högst.
    """
    if minut < -5:
        return 0.0   # uppvärmning
    if 38 <= minut <= 47:   # slutminut HL1 inkl. tilläggstid
        return 0.08
    if 78 <= minut <= 97:   # slutminut HL2 inkl. tilläggstid
        return 0.08
    if 105 <= minut <= 125: # förlängning
        return 0.10
    return 0.0
