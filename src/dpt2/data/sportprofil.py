"""Sportprofiler — en fältmodell per sport, delad av backend och UI.

Matchresultat/mellanresultat/målskyttar/uppställning var tidigare fotbolls-
låsta antaganden överallt (Slutsignal, Live-mallens moment, Innehåll-
webbformuläret, Matchdaguttaget i Matcher). En profil per sport styr nu
etiketter, vilka fält som visas, och `md_key` (vilken nyckel mellanresultatet
får i .md-frontmattern — halvtid/set/perioder beroende på sport).

Nycklarna är samma lowercase sport-koder som lagras i matchen.sport/
lag.sport/tavling.sport. Rör inte gren (dam/herr/mixed) här — det är en
separat axel (se ui/src/lib/gren.js), oberoende av sport.
"""

PROFILER = {
    "fotboll": {
        "namn": "Fotboll",
        "res_label": "Slutresultat", "res_ph": "6–0",
        "mid_label": "Halvtid", "mid_ph": "3–0", "mid_moment": "Halvtid", "mid_token": "halvtid",
        "start_moment": "Avspark",
        "has_scorers": True, "scorers_label": "Målskyttar",
        "lineup": "Startelva", "lineup_n": "(11)",
        "squad": True, "individ": False,
        "md_key": "halvtid", "farg": "#2F7CB0",
    },
    "handboll": {
        "namn": "Handboll",
        "res_label": "Slutresultat", "res_ph": "28–24",
        "mid_label": "Halvtid", "mid_ph": "14–11", "mid_moment": "Halvtid", "mid_token": "halvtid",
        "start_moment": "Avspark",
        "has_scorers": True, "scorers_label": "Målskyttar",
        "lineup": "Startsju", "lineup_n": "(7)",
        "squad": True, "individ": False,
        "md_key": "halvtid", "farg": "#C9871F",
    },
    "innebandy": {
        "namn": "Innebandy",
        "res_label": "Slutresultat", "res_ph": "4–1",
        "mid_label": "Periodsiffror", "mid_ph": "1–0, 2–1, 1–0", "mid_moment": "Periodpaus",
        "mid_token": "periodsiffror",
        "start_moment": "Nedsläpp",
        "has_scorers": True, "scorers_label": "Målskyttar",
        "lineup": "Femma", "lineup_n": "(5)",
        "squad": True, "individ": False,
        "md_key": "perioder", "farg": "#6E8B5E",
    },
    "volleyboll": {
        "namn": "Volleyboll",
        "res_label": "Resultat i set", "res_ph": "3–1",
        "mid_label": "Setsiffror", "mid_ph": "25–21, 23–25, 25–19, 25–17", "mid_moment": "Mellan set",
        "mid_token": "setsiffror",
        "start_moment": "Matchstart",
        "has_scorers": False, "scorers_label": "",
        "lineup": "Startsexa", "lineup_n": "(6)",
        "squad": True, "individ": False,
        "md_key": "set", "farg": "#C9657F",
    },
    "beachvolley": {
        "namn": "Beachvolley",
        "res_label": "Resultat i set", "res_ph": "2–0",
        "mid_label": "Setsiffror", "mid_ph": "21–18, 21–15", "mid_moment": "Mellan set",
        "mid_token": "setsiffror",
        "start_moment": "Matchstart",
        "has_scorers": False, "scorers_label": "",
        "lineup": "Par", "lineup_n": "(2)",
        "squad": False, "individ": False,
        "md_key": "set", "farg": "#E0A040",
    },
    "tennis": {
        "namn": "Tennis",
        "res_label": "Resultat i set", "res_ph": "2–1",
        "mid_label": "Gamesiffror", "mid_ph": "6–4, 3–6, 7–5", "mid_moment": "Mellan set",
        "mid_token": "gamesiffror",
        "start_moment": "Matchstart",
        "has_scorers": False, "scorers_label": "",
        "lineup": "", "lineup_n": "",
        "squad": False, "individ": True,
        "md_key": "set", "farg": "#7A8794",
    },
    "friidrott": {
        "namn": "Friidrott",
        "res_label": "Resultat", "res_ph": "10,12 s",
        "mid_label": "Placering", "mid_ph": "1", "mid_moment": "Delresultat",
        "mid_token": "placering",
        "start_moment": "Start",
        "has_scorers": False, "scorers_label": "",
        "lineup": "", "lineup_n": "",
        "squad": False, "individ": True,
        "md_key": "placering", "farg": "#B5643C",
    },
}

_FALLBACK = "fotboll"


def profil(sport):
    """Sportens profil, eller Fotbollsprofilen om sporten är okänd/tom
    (matchar dagens beteende för befintliga matcher utan sportfält)."""
    return PROFILER.get((sport or "").lower(), PROFILER[_FALLBACK])


def alla_profiler():
    """Hela profiltabellen, för engångshämtning till UI:t."""
    return PROFILER
