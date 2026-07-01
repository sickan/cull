"""Publicera-tjänsten — fan-out av ETT publiceringspaket till SoMe-kanalerna.

Ren GLUE ovanpå kanal-adaptrarna: tar ett paket med FÄRDIGA bilder + caption och
räknar ut EXAKT vilka poster som ska ut, per kanal, enligt fotografens regler:

  * IG Story  — 1 bild/post → N bilder blir N story-poster i följd. Full caption.
  * IG-inlägg — 1 bild = enkel post, 2–10 = karusell. API-taket är 10, så 11–20
                delas i flera inlägg (Graph API släpper inte förbi 10, till
                skillnad från appen). Full caption.
  * FB-sida   — max 4 bilder (kapas + varnas). Caption STRIPPAD på #hashtags och
                @mentions (fotografens FB-stil).

`planera()` är helt ren (inga API-anrop, ingen DB) — den räknar ut planen och är
det som testerna verifierar. `publicera()` kör planen mot en `poster`-callable;
med dry_run=True (default) rörs inga API:er utan planen loggas bara.
"""

import math
import re

# Graph API tar max 10 media per karusell (appen tar 20, men API:et gör inte det).
IG_KARUSELL_MAX = 10
# Facebook-sidans multi-photo-post i fotografens flöde: max 4 bilder.
FB_MAX = 4


def strippa_fb(text):
    """Tar bort #hashtags och @mentions ur en caption (fotografens FB-stil).
    Städar dubbla mellanslag/tomrader som blir kvar. Tom sträng → ''."""
    t = re.sub(r"[#@][\wåäöÅÄÖ]+", "", text or "")
    t = re.sub(r"[ \t]{2,}", " ", t)                    # dubbla mellanslag → ett
    t = re.sub(r" *\n", "\n", t)                         # blanksteg före radbryt
    t = re.sub(r"\n{3,}", "\n\n", t)                     # max en tomrad
    return t.strip()


def dela_karusell(bilder, max_per=IG_KARUSELL_MAX):
    """Delar en bildlista i karusell-lagom bitar (≤ max_per). [] → []."""
    return [bilder[i:i + max_per] for i in range(0, len(bilder), max_per)]


def planera(paket):
    """Räknar ut de planerade posterna ur ett paket. REN (inga sidoeffekter).

    paket = {
        bilder:  [path, ...]   # ordnad lista färdiga kompositioner
        caption: str           # BILDSVEP-texten (med #/@)
        mal:     {story?: bool, ig_inlagg?: bool, fb?: bool}
    }

    Returnerar {ok, poster, varningar} eller {ok:False, fel}. Varje post:
        {kanal, form, bilder, text, del, av}
    där kanal ∈ instagram|facebook, form ∈ story|inlägg, del/av numrerar
    uppdelade inlägg (11–20 bilder → del 1/2, 2/2).
    """
    bilder = list(paket.get("bilder") or [])
    caption = paket.get("caption") or ""
    mal = paket.get("mal") or {}

    if not bilder:
        return {"ok": False, "fel": "Paketet saknar bilder."}
    if not any(mal.get(k) for k in ("story", "ig_inlagg", "fb")):
        return {"ok": False, "fel": "Välj minst ett mål (story/ig_inlagg/fb)."}

    poster, varningar = [], []

    # IG Story — en post per bild, full caption.
    if mal.get("story"):
        n = len(bilder)
        for i, bild in enumerate(bilder, 1):
            poster.append({"kanal": "instagram", "form": "story",
                           "bilder": [bild], "text": caption, "del": i, "av": n})

    # IG-inlägg — karusell(er), max 10/post. 11–20 → flera inlägg.
    if mal.get("ig_inlagg"):
        bitar = dela_karusell(bilder)
        if len(bitar) > 1:
            varningar.append(
                f"{len(bilder)} bilder till IG-inlägg → {len(bitar)} poster "
                f"(Graph API tar max {IG_KARUSELL_MAX}/karusell).")
        for i, bit in enumerate(bitar, 1):
            poster.append({"kanal": "instagram", "form": "inlägg",
                           "bilder": bit, "text": caption,
                           "del": i, "av": len(bitar)})

    # FB-sida — max 4 bilder, strippad caption.
    if mal.get("fb"):
        fb_bilder = bilder[:FB_MAX]
        if len(bilder) > FB_MAX:
            varningar.append(
                f"{len(bilder)} bilder till FB → kapat till {FB_MAX} "
                f"(FB-sidans multi-photo-gräns).")
        poster.append({"kanal": "facebook", "form": "inlägg",
                       "bilder": fb_bilder, "text": strippa_fb(caption),
                       "del": 1, "av": 1})

    return {"ok": True, "poster": poster, "varningar": varningar}


def _etikett(p):
    """Kort människoläsbar etikett för en planerad post (logg/dry-run)."""
    delinfo = f" {p['del']}/{p['av']}" if p["av"] > 1 else ""
    return f"{p['kanal']}/{p['form']}{delinfo} ({len(p['bilder'])} bild)"


def publicera(paket, *, poster=None, dry_run=True, logg=print, progress=None):
    """Kör planen. Med dry_run=True (default) anropas INGA API:er — planen loggas
    bara, vilket gör hela reglerna testbara utan tokens.

    poster:   callable(planerad_post) -> {ok, url?|fel?}. Krävs när dry_run=False.
    progress: callable(n, tot) för UI-framsteg, eller None.

    Returnerar {ok, resultat:[{...post, status, url?|fel?}], varningar} eller
    {ok:False, fel}."""
    plan = planera(paket)
    if not plan.get("ok"):
        return plan
    poster_lista, varningar = plan["poster"], plan["varningar"]
    for v in varningar:
        logg(f"⚠ {v}")

    if not dry_run and poster is None:
        return {"ok": False, "fel": "Ingen poster angiven (dry_run=False)."}

    resultat, tot = [], len(poster_lista)
    for n, p in enumerate(poster_lista, 1):
        if progress:
            progress(n, tot)
        if dry_run:
            logg(f"[dry-run] skulle posta → {_etikett(p)}")
            resultat.append({**p, "status": "dry_run"})
            continue
        logg(f"Postar → {_etikett(p)}…")
        r = poster(p) or {}
        if r.get("ok"):
            logg(f"✓ {_etikett(p)} → {r.get('url', '')}")
            resultat.append({**p, "status": "postad", "url": r.get("url")})
        else:
            logg(f"✗ {_etikett(p)}: {r.get('fel', 'okänt fel')}")
            resultat.append({**p, "status": "fel", "fel": r.get("fel", "okänt fel")})

    ok = all(r["status"] != "fel" for r in resultat)
    return {"ok": ok, "resultat": resultat, "varningar": varningar}
