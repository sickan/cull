"""Poäng- och urvalsmotorn — extraherad ur core.main() (Fas 1).

Ren logik, stdlib only (ingen cv2/numpy) → testbar var som helst. En TROGEN
spegling av core.py:s slutpoäng + urval; vikter/konstanter är FRYSTA (ändra
aldrig utan omträning — se OMSKRIVNING.md §8 beslut 3).

Arbetar på 'rader' (en dict per bild med feature-nycklar; samma kontrakt som
core:s `resultat`). Ingen I/O, ingen ML — feature-extraktionen sker FÖRE, och
poängsättning kan ske antingen via den personliga modellen (anroparen kör
inlarning.poangsatt_med_modell) eller via de handsatta vikterna här.

Identitet per bild: cfg.id_nyckel (default "fil"); `skyddade` är en mängd sådana
id, `bevaka` en mängd tröjnummer (matchas mot r["_nummer"]).
"""

from dataclasses import dataclass, field

from dpt2.motorer import matchfas

# ── Frysta vikter/konstanter (speglar core.py exakt) ─────────────────────────
W_SKARPA = 0.55
W_EXP = 0.35
W_OGON = 0.10
ESTETIK_SKALA = 0.15
FIRANDE_BOOST_PER_STEG = 0.05
VAST_STRAFF = 0.08
VAST_MAX = 3
PERC_LO, PERC_HI = 5, 95


@dataclass
class Gallring:
    """Cull-jobbets urvalsparametrar (motsvarar relevanta CLI-flaggor)."""
    ai: bool = True
    topp: int | None = None          # exakt antal; annars härleds ur andel
    andel: float = 0.10              # bevara-andel om topp saknas
    burst_sek: float = 2.0
    firande_boost: int = 0           # ±steg
    garanti_firande: int = 0
    garanti_bevaka: int = 0
    bevaka: set = field(default_factory=set)      # bevakade tröjnummer
    skyddade: set = field(default_factory=set)    # kamera-skyddade (id)
    id_nyckel: str = "fil"
    profil: str = "sport"            # §9-gallringsprofil (sport/brollop/landskap/portratt)
    sport: str = ""                  # matchens sport ("" = okänd → fotbollsformeln)


# ── små rena hjälpare (numpy-fri percentil = numpy 'linear') ─────────────────
def _percentil(varden, p):
    if not varden:
        return 0.0
    s = sorted(varden)
    if len(s) == 1:
        return float(s[0])
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return float(s[lo] + frac * (s[hi] - s[lo]))


def _clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _ogon_bonus(r):
    if r.get("ansikten", 0) > 0:
        return min(r.get("ogon", 0) / (r["ansikten"] * 2), 1.0) * W_OGON
    return 0.0


# ── normalisering ─────────────────────────────────────────────────────────────
def normalisera(resultat):
    """Sätter r['skarpa_n'] (percentil-normaliserad skärpa) och r['estetik']
    (NIMA-percentil × ESTETIK_SKALA). Speglar core 1410-1415 + 1590-1602."""
    sk = [r["skarpa"] for r in resultat if "skarpa" in r]
    if sk:
        lo, hi = _percentil(sk, PERC_LO), _percentil(sk, PERC_HI)
        spann = max(hi - lo, 1e-6)
        for r in resultat:
            r["skarpa_n"] = _clip((r.get("skarpa", lo) - lo) / spann, 0, 1)

    nima = [r["nima"] for r in resultat if r.get("nima") is not None]
    if nima:
        nl, nh = _percentil(nima, PERC_LO), _percentil(nima, PERC_HI)
        nspann = max(nh - nl, 1e-6)
    for r in resultat:
        if r.get("nima") is not None and nima:
            r["estetik"] = _clip((r["nima"] - nl) / nspann, 0, 1) * ESTETIK_SKALA
        else:
            r["estetik"] = 0.0
    return resultat


# ── poängsättning ────────────────────────────────────────────────────────────
# CULL-02: matchsignalerna gäller bara lagsporter med trupp (tröjnummer,
# hemmafärg, målklunga finns inte i friidrott/tennis/bröllop). Basen
# skärpa/exponering/estetik gäller alla profiler; ögon gäller där människor
# är motivet. Vikterna i sig är oförändrade (frysta) — profilen väljer bara
# vilka termer som ingår.
MATCHSIGNALER = ("armar", "boll", "hemma", "trojnummer", "klunga", "fas")


def aktiva_signaler(profil="sport", sport=""):
    """Vilka signaler utöver basen som ingår för en §9-profil.
    Returnerar (ogon: bool, matchsignaler: tuple)."""
    p = (profil or "sport").strip().lower()
    if p == "landskap":
        return False, ()
    if p in ("brollop", "portratt", "manniskor"):
        return True, ()
    # Sportprofilen: lagsporter (squad) får hela matchformeln; individ-/
    # parsporter (friidrott, tennis, beachvolley) får ögon + armar (jubel/
    # ansträngning läses ur samma pose-signal). Okänd sport → fotboll (arvet).
    if sport:
        from dpt2.data import sportprofil
        pr = sportprofil.profil(sport) or {}
        if not pr.get("squad", True):
            return True, ("armar",)
    return True, MATCHSIGNALER


def poangsatt_handsatt(resultat, profil="sport", sport=""):
    """Sätter r['poang'] med de handsatta vikterna (när ingen modell finns).
    Förutsätter normalisera() körd. Speglar core 1611-1626; med default-
    argumenten (sport-profil, okänd sport) är formeln bit-identisk med arvet."""
    ogon, signaler = aktiva_signaler(profil, sport)
    for r in resultat:
        p = (
            W_SKARPA * r.get("skarpa_n", 0.0)
            + W_EXP * r.get("exp", 0.0)
            + r.get("estetik", 0.0)
        )
        if ogon:
            p += _ogon_bonus(r)
        for s in signaler:
            p += r.get(s, 0.0)
        r["poang"] = p
    return resultat


def firande_boost(resultat, steg):
    """±steg × 0.05 × (armar+klunga). Speglar core 1629-1633."""
    if not steg:
        return resultat
    for r in resultat:
        signal = r.get("armar", 0.0) + r.get("klunga", 0.0)
        r["poang"] += steg * FIRANDE_BOOST_PER_STEG * signal
    return resultat


def vast_straff(resultat):
    """Drar ned uppvärmningsväst-bilder. Speglar core 1636-1640."""
    for r in resultat:
        n = r.get("vast", 0)
        if n > 0:
            r["poang"] -= VAST_STRAFF * min(n, VAST_MAX)
    return resultat


# ── burst-gruppering ─────────────────────────────────────────────────────────
def burst_grupper(resultat, burst_sek):
    """Sätter r['grupp'] via tidsstämpel-gap. Speglar core 1642-1656."""
    har_tid = bool(resultat) and all(
        matchfas.parse_tid(r.get("tid")) is not None for r in resultat)
    if har_tid:
        resultat.sort(key=lambda r: matchfas.parse_tid(r["tid"]))
        grupp, forra = 0, None
        for r in resultat:
            t = matchfas.parse_tid(r["tid"])
            if forra is not None and t - forra > burst_sek:
                grupp += 1
            r["grupp"] = grupp
            forra = t
    else:
        for i, r in enumerate(resultat):
            r["grupp"] = i
    return resultat


# ── urval (topp-N per burst + garantiplatser) ────────────────────────────────
def valj(resultat, cfg):
    """Väljer urvalet. Förutsätter poang + grupp satta. Returnerar (valda, info).
    Trogen spegling av core 1658-1712."""
    idk = cfg.id_nyckel
    n_total = len(resultat)
    n_behall = cfg.topp if cfg.topp else max(1, round(n_total * cfg.andel))

    basta_per_grupp = {}
    for r in resultat:
        g = r["grupp"]
        if g not in basta_per_grupp or r["poang"] > basta_per_grupp[g]["poang"]:
            basta_per_grupp[g] = r

    valda = sorted(basta_per_grupp.values(), key=lambda r: r["poang"], reverse=True)
    if len(valda) < n_behall:
        valda_ids = {r[idk] for r in valda}
        rest = sorted([r for r in resultat if r[idk] not in valda_ids],
                      key=lambda r: r["poang"], reverse=True)
        valda += rest[:n_behall - len(valda)]
    valda = valda[:n_behall]

    firande_g, bevaka_g = [], []
    if cfg.ai:
        valda_ids = {r[idk] for r in valda}
        if cfg.garanti_firande > 0:
            firande_g = sorted(
                [r for r in resultat if r[idk] not in valda_ids
                 and r.get("armar", 0.0) + r.get("klunga", 0.0) > 0.0],
                key=lambda r: r.get("armar", 0.0) + r.get("klunga", 0.0),
                reverse=True)[:cfg.garanti_firande]
        if cfg.garanti_bevaka > 0 and cfg.bevaka:
            redan = valda_ids | {r[idk] for r in firande_g}
            bevaka_g = sorted(
                [r for r in resultat if r[idk] not in redan
                 and set(r.get("_nummer", [])) & cfg.bevaka],
                key=lambda r: r["poang"], reverse=True)[:cfg.garanti_bevaka]

    skydd_g = []
    if cfg.skyddade:
        redan = ({r[idk] for r in valda}
                 | {r[idk] for r in firande_g + bevaka_g})
        skydd_g = [r for r in resultat
                   if r[idk] in cfg.skyddade and r[idk] not in redan]

    garanterade = firande_g + bevaka_g + skydd_g
    if garanterade:
        g_ids = {r[idk] for r in garanterade}
        behalls = sorted([r for r in valda if r[idk] not in g_ids],
                         key=lambda r: r["poang"], reverse=True)
        valda = behalls[:max(0, n_behall - len(garanterade))] + garanterade

    info = {
        "n_total": n_total,
        "n_behall": n_behall,
        "n_grupper": len(basta_per_grupp),
        "firande": len(firande_g),
        "bevaka": len(bevaka_g),
        "skyddade": len(skydd_g),
    }
    return valda, info


def stjarnor_av_poang(valda, id_nyckel="fil"):
    """Stjärnbetyg 2-5 per bild ur poängens percentil i urvalet. Speglar
    core._stjarnor_av_poang. Returnerar {id: stjärnor}."""
    import bisect
    if not valda:
        return {}
    poäng = sorted(r["poang"] for r in valda)
    n = len(poäng)
    ut = {}
    for r in valda:
        p = bisect.bisect_right(poäng, r["poang"]) / n
        ut[r[id_nyckel]] = 5 if p >= 0.80 else 4 if p >= 0.55 else 3 if p >= 0.30 else 2
    return ut


# ── full handsatt pipeline (bekvämlighet) ────────────────────────────────────
def gallra(resultat, cfg, modellpoang_satt=False):
    """Kör hela kedjan: normalisera → poäng → firande/väst → burst → välj.

    modellpoang_satt=True: r['poang'] är redan satt (av den personliga modellen
    + fas), så den handsatta formeln hoppas över. Returnerar (valda, info)."""
    normalisera(resultat)
    if not modellpoang_satt:
        poangsatt_handsatt(resultat, cfg.profil, cfg.sport)
    # Firande/väst är lagsportsbegrepp — bara när matchsignalerna är aktiva.
    if cfg.ai and MATCHSIGNALER == aktiva_signaler(cfg.profil, cfg.sport)[1]:
        firande_boost(resultat, cfg.firande_boost)
        vast_straff(resultat)
    burst_grupper(resultat, cfg.burst_sek)
    return valj(resultat, cfg)
