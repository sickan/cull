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


def uppskatta_avspark(timestamps, min_gap_sek=120):
    """
    Uppskattar avsparkstid ur bildernas tidsstämplar.
    Uppvärmning ger glesa bilder; avspark inleds typiskt med ett uppehåll
    (lag in i omklädningsrum / uppställning) följt av en tät skur. Letar i
    första 45 % av tidslinjen efter den starkaste 'paus → skur'-punkten.
    Returnerar ett Unix-timestamp, eller None om mönstret är otydligt.
    """
    import bisect
    ts = sorted(t for t in timestamps if t)
    if len(ts) < 12:
        return None
    start, slut = ts[0], ts[-1]
    span = slut - start
    if span < 1200:          # under 20 min totalt — för kort för att gissa
        return None
    gräns = start + 0.6 * span   # avspark sker i god tid före matchens slut
    kand = []   # (tid, poäng)
    for i in range(1, len(ts)):
        if ts[i] > gräns:
            break
        gap = ts[i] - ts[i - 1]
        if gap < min_gap_sek:
            continue
        # antal bilder de följande 20 minuterna (skurens styrka)
        efter = bisect.bisect_right(ts, ts[i] + 1200) - i
        # gapet kapas så att en lång halvtidspaus inte överröstar avsparken
        poäng = min(gap, 600) * efter
        if poäng > 0:
            kand.append((ts[i], poäng))
    if not kand:
        return None
    # Välj den TIDIGASTE tillräckligt starka punkten (avspark före halvtid).
    tröskel = 0.5 * max(p for _, p in kand)
    for tid, p in kand:
        if p >= tröskel:
            return tid
    return kand[0][0]


def fas_bonus(minut):
    """
    Ger bonus för dramatiska skeden och straff för uppvärmning.
    Uppvärmningsbilder (västar/bibs) trycks ned ur urvalet.
    """
    if minut < -20:
        return -0.20  # tidig uppvärmning — västar, löpning, drillövningar
    if minut < -5:
        return -0.10  # sen uppvärmning
    if 38 <= minut <= 47:   # slutminut HL1 inkl. tilläggstid
        return 0.08
    if 78 <= minut <= 97:   # slutminut HL2 inkl. tilläggstid
        return 0.08
    if 105 <= minut <= 125: # förlängning
        return 0.10
    return 0.0
