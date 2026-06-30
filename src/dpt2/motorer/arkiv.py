"""Arkiv-genomgång (KÄRNA) — hittar facit-uppdrag i ett export-träd.

Den BESTÄNDIGA träningskorpusen: levererade/publicerade JPG i Dropbox-arkivet.
Per match-mapp med en `Instagram/`-undermapp är de publicerade bilderna positiva
(label 1), övriga kandidat-JPG negativa (0), deduplicerat på käll-frame-id. JPG
består (till skillnad från kamerakort) → recompute-bart med nuvarande libs.

Migrerad ur gamla dpt.inlarning (hitta_uppdrag_export/_frame_id). Sport härleds
NAMNBASERAT (sport_av_namn) — deterministiskt och beroendefritt, utan den gamla
webb-/bildröstningen.
"""

import re
from pathlib import Path

EJ_KANDIDAT = ("Test", "Loggor")

_LAG_SUFFIX = [("dff", "fotboll"), (" fc", "fotboll"), ("fc ", "fotboll"),
               (" ff", "fotboll"),
               (" hk", "handboll"), ("hk ", "handboll"),
               (" hf", "handboll"), ("hf ", "handboll"),
               (" vk", "volleyboll"), ("ibk", "innebandy")]

_SPORT_NYCKELORD = {
    "handboll":  [" hk", "hk ", " hf", "hf ", "handboll", "handball",
                  " rk ", "nexe", "lugi", "kristianstad", "varberg hk",
                  "kungälv", "sävehof", "höör", "skövde hf", "redbergslid",
                  "ystads if", "alingsås", "boden handboll", "önnereds",
                  " ifk göteborg h", "rimbo", "spårvägen", "hammarby if hf",
                  "heim", "flensburg", "kiel", "barcelona hand", "paris hand"],
    "fotboll":   [" ff", "dff", " fc", "fotboll", "soccer", " mff", "allsvenskan",
                  "superettan", "damallsvenskan", " bk ", "fotbolls",
                  " aik", " djurgård", " hammarby if", " ifk göteborg ",
                  " ifk norrköping", " häcken", "brommapojkarna", " bp "],
    "beachvolley": ["beachvolley", "beach volley", "beachvolleyboll",
                    "beach volleyball"],
    "volleyboll": [" vk", "volleyboll", "volleyball"],
    "tennis":    ["tennis", " atp", " wta", "davis cup", "billie jean",
                  "grand slam", "us open", "roland garros", "wimbledon"],
    "innebandy": ["ibk", "innebandy", "floorball", " fbc", "fbk"],
}


def _frame_id(namn):
    """Käll-frame-id ur ett exportfilnamn, normaliserat (Z816551, D858711)."""
    m = re.match(r"^\d{12,14}_(.+?)_NIKON", namn)
    tok = m.group(1) if m else Path(namn).stem
    tok = re.split(r"-Redigera|-Edit", tok)[0]
    return tok.replace("_", "").upper()


def sport_av_namn(namn):
    """Härleder sport ur match-mappens namn via röstning (lag-suffix 4p,
    nyckelord 2p, resultat-heuristik). 'okänd' om inget träffar."""
    röster = {}

    def rösta(sport, poäng):
        if sport and sport != "inomhus":
            röster[sport] = röster.get(sport, 0) + poäng

    low = (namn or "").lower()
    for suf, sport in _LAG_SUFFIX:
        if suf in low:
            rösta(sport, 4)
    for sport, nyckelord in _SPORT_NYCKELORD.items():
        if any(k in low for k in nyckelord):
            rösta(sport, 2)
    for a, b in re.findall(r"\b(\d+)-(\d+)\b", namn or ""):
        if int(a) > 25 or int(b) > 25:
            rösta("handboll", 2)
            break
        if int(a) <= 6 and int(b) <= 6:
            rösta("fotboll", 1)
            break
    return max(röster, key=röster.get) if röster else "okänd"


def hitta_uppdrag(root):
    """Hittar export-uppdrag under root. Returnerar lista av
    (namn, sport, [(jpg_path, label), …]) där label=1 för publicerade bilder
    (de som ligger i match-mappens Instagram/). Kandidater = alla JPG i matchen,
    deduplicerade på frame-id. Hoppar matcher utan tydligt fler kandidater än
    valda (då saknas negativa exempel)."""
    root = Path(root)
    uppdrag = []
    for ig in root.rglob("Instagram"):
        if not ig.is_dir():
            continue
        match_dir = ig.parent
        vald_ids = {_frame_id(p.name) for p in ig.glob("*.jpg")
                    if not p.name.startswith(".")}
        if not vald_ids:
            continue
        kandidater = {}
        for jpg in match_dir.rglob("*.jpg"):
            if jpg.name.startswith(".") or any(d in jpg.parts for d in EJ_KANDIDAT):
                continue
            kandidater.setdefault(_frame_id(jpg.name), jpg)
        if len(kandidater) < len(vald_ids) + 5:
            continue
        items = [(p, 1 if fid in vald_ids else 0)
                 for fid, p in kandidater.items()]
        uppdrag.append((match_dir.name, sport_av_namn(match_dir.name), items))
    return uppdrag
