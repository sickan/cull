"""Publicera-orkestrering (Publicera → SoMe) — kör ETT publiceringspaket och
spårar utfallet i DB.

Tunn GLUE ovanpå den rena fan-out-logiken (tjanster.publicera_some) och store:
bygger paketet ur config, kör planen (dry-run som default — rör inga API:er) och
skriver en some_material-rad per post som FAKTISKT gick ut. Kör i worker-processen
(nätverkslatens, tunga uppladdningar), men är torch-fri.

Kanal-adaptern (Meta/TikTok) injiceras som `poster`-callable i steg 3; här bor
bara bygg-paket → kör → spåra.
"""

from dpt2.data import store
from dpt2.tjanster import publicera_some


def _paket(config):
    """config {bilder, caption, mal, ...} → paket för publicera_some."""
    return {
        "bilder": config.get("bilder") or [],
        "caption": config.get("caption") or "",
        "mal": config.get("mal") or {},
    }


def kor_publicering(conn, config, *, poster=None, dry_run=True,
                    logg=print, progress=None):
    """Kör en publicering ur config {bilder, caption, mal, match_id?, moment?,
    tema?}. dry_run=True (default) loggar bara planen. Vid skarp körning krävs en
    `poster`-callable; varje lyckad post spåras som en some_material-rad.

    Returnerar {ok, resultat, varningar, sparade} eller {ok:False, fel}."""
    config = config or {}
    r = publicera_some.publicera(
        _paket(config), poster=poster, dry_run=dry_run, logg=logg,
        progress=progress)
    if not r.get("ok"):
        # ok:False täcker både validering (fel) och en misslyckad post.
        r.setdefault("sparade", 0)
        return r

    sparade = 0
    if not dry_run:
        match_id = config.get("match_id")
        tavling_id = config.get("tavling_id")   # turnerings-SoMe (ej matchbunden)
        moment = config.get("moment")
        tema = config.get("tema")
        for post in r["resultat"]:
            if post.get("status") != "postad":
                continue
            store.spara_some_material(
                conn, kanal=post["kanal"], format=post["form"],
                match_id=match_id, tavling_id=tavling_id, moment=moment, tema=tema,
                fil=post["bilder"][0] if post.get("bilder") else None)
            sparade += 1
        if sparade:
            logg(f"✓ Spårade {sparade} post(er) i some_material.")
    r["sparade"] = sparade
    return r
