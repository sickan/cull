"""Match-hämtning ovanpå Claude-tjänsten — trupp, startuppställning, ark.

Tunna konsumenter som bygger prompt + schema och delegerar till
dpt2.tjanster.claude. Prompter/scheman/KLUBBAR är migrerade verbatim ur
gamla hamta_match.py + las_lineup.py (DATA). Klienten kan injiceras (test);
utelämnad → tjänsten skapar en skarp klient.

Alla tre returnerar inline-spelarformatet {nr,namn,lag,start,handle,info} som
matchlogik/store förstår, eller None.
"""

import base64
import io
import subprocess
import tempfile
from pathlib import Path

from dpt2.tjanster import claude

# ── Klubbregister (migrerat ur hamta_match.KLUBBAR) ──────────────────────────
KLUBBAR = {
    "fc rosengård": {
        "squad_url": "https://www.fcrosengard.se/sv/players",
        "matches_url": "https://www.fcrosengard.se/sv/matches",
        "ig": "fcrosengard",
    },
    "eskilstuna united": {
        "squad_url": "https://eskilstunaunited.se/truppen/",
        "matches_url": "https://eskilstunaunited.se/allsvenskan-2026/",
        "ig": "eskilstunaunited",
    },
    "eskilstuna united dff": {
        "squad_url": "https://eskilstunaunited.se/truppen/",
        "matches_url": "https://eskilstunaunited.se/allsvenskan-2026/",
        "ig": "eskilstunaunited",
    },
}


def klubb(namn):
    """KLUBBAR-post för lagnamn (case-insensitive), eller {}."""
    return KLUBBAR.get((namn or "").strip().lower(), {})


# ── Prompter/scheman (migrerade verbatim) ────────────────────────────────────
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
    "Lämna handle-fältet TOMT för alla — sök INTE efter Instagram-handles, "
    "det görs i ett separat steg. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)
SCHEMA_SPELARE = (
    '{"lag": {"hemma": "lagnamn", "borta": "lagnamn eller tom sträng"}, '
    '"spelare": [{"nr": "10", "namn": "Remy Siemsen", "lag": "hemma", '
    '"start": false, "handle": "@remyysiemsen", "info": "Forward"}], '
    '"kallor": ["https://www.fcrosengard.se/sv/players"]}'
)

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

SYSTEM_LINEUP = (
    "Du läser ett officiellt laguppställnings-ark (line-up/team sheet) för en "
    "sportmatch och returnerar ENBART ett JSON-objekt enligt schemat — ingen "
    "annan text.\n"
    "- Extrahera varje spelares tröjnummer och namn för BÅDA lagen.\n"
    "- Markera målvakt (mv=true) och kapten (kapten=true) om det framgår "
    "(GK/MV, C/©).\n"
    "- Om arket visar en startuppställning (t.ex. 11 i fotboll, 6 i volleyboll, "
    "ofta även en formationsruta) sätt start=true för de spelarna.\n"
    "- Bestäm hemmalag: oftast arenans/värdlandets lag eller laget som listas "
    "först (lag='hemma'), motståndaren 'borta'.\n"
    "- Använd svenska namnformer för länder (Sweden→Sverige, Italy→Italien).\n"
    "- Bygg 'matchinfo' i formatet: '(D) eller (H) Hemma - Borta ÅÅÅÅMMDD Arena' "
    "— (D)=dam om det är Women's, (H)=herr om Men's. Lämna PLATS för resultatet "
    "men gissa det INTE (arket är oftast skrivet före match): skriv ingen "
    "resultatsiffra om den inte tydligt står på arket.\n"
    "- Hitta ALDRIG på nummer eller namn; utelämna det du inte kan läsa säkert."
)
SCHEMA_LINEUP = (
    '{"matchinfo": "(D) Sverige - Italien 20260609 Gamla Ullevi", '
    '"lag": {"hemma": "Sverige", "borta": "Italien"}, '
    '"datum": "20260609", "arena": "Gamla Ullevi", '
    '"spelare": [{"nr": "12", "namn": "Jennifer Falk", "lag": "hemma", '
    '"start": true, "mv": true, "kapten": false}]}'
)

SYSTEM_LAGTRUPP = (
    "Du är en sportresearcher. Din uppgift är att hämta hela spelartruppen "
    "för ETT lag från lagets OFFICIELLA hemsida. "
    "Om en URL anges: besök den direkt utan att söka via Google. "
    "Om ingen URL anges: hitta klubbens officiella webbsida och gå till truppsidan. "
    "Officiell klubbsida är alltid facit — tredjepartssidor (Transfermarkt, "
    "Sofascore, Wikipedia) har ofta föråldrade uppgifter; använd dem bara som "
    "komplement (position, nationalitet). Täck HELA truppen. "
    "Hitta ALDRIG på nummer eller namn — ta bara med det som finns i källan. "
    "Svara ENBART med ett JSON-objekt enligt schemat, ingen annan text."
)
SCHEMA_LAGTRUPP = (
    '{"lag": "lagnamn", '
    '"spelare": [{"nr": "10", "namn": "Remy Siemsen", "position": "Forward"}], '
    '"kallor": ["https://www.fcrosengard.se/sv/players"]}'
)

SYSTEM_TRUPP_ARK = (
    "Du läser en spelarlista/trupplista för ETT lag (blad, foto av papper, "
    "PDF eller skärmdump) och returnerar ENBART ett JSON-objekt enligt "
    "schemat — ingen annan text.\n"
    "- Extrahera varje spelares tröjnummer, namn och position om den framgår.\n"
    "- Hitta ALDRIG på nummer eller namn; utelämna det du inte kan läsa säkert."
)
SCHEMA_TRUPP_ARK = (
    '{"lag": "lagnamn eller tom sträng", '
    '"spelare": [{"nr": "12", "namn": "Jennifer Falk", "position": "Målvakt"}]}'
)

HEIC_SUFFIX = {".heic", ".heif"}
BILD_SUFFIX = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
LINEUP_MAX_KANT = 2000


def _klient_eller_skapa(klient, logg):
    if klient is not None:
        return klient
    if not claude.tillganglig():
        logg("⚠ ANTHROPIC_API_KEY eller anthropic saknas.")
        return None
    return claude.ny_klient()


# ── Fas 1: trupp via web-sök ─────────────────────────────────────────────────
def hamta_spelare(lag_hemma, lag_borta, sport="", logg=print, klient=None):
    """Hämtar truppen från officiella klubbsidor. Returnerar
    {lag, spelare:[...], kallor} eller None."""
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    rader = []
    for namn in (lag_hemma, lag_borta):
        if not namn:
            continue
        url = klubb(namn).get("squad_url")
        rader.append(f"- {namn}: besök {url}" if url
                     else f"- {namn}: hitta officiell truppsida")
    fraga = "Hämta spelartruppen för:\n" + "\n".join(rader)
    if sport and sport.lower() not in ("", "auto"):
        fraga += f"\nSport: {sport}"
    fraga += f"\n\nReturnera JSON:\n{SCHEMA_SPELARE}"

    data = claude.fraga_json(klient, SYSTEM_SPELARE, fraga,
                             verktyg=claude.web_search_verktyg(max_uses=4),
                             logg=logg)
    if data:
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare.")
    return data


# ── Fas 2: startuppställning via web-sök ──────────────────────────────────────
def hamta_uppstallning(lag_hemma, lag_borta, datum="", sport="", logg=print,
                       klient=None):
    """Hämtar officiell startuppställning. Returnerar {lag, spelare, kallor}
    eller None. handle/info tomma (bevaras från fas 1 vid merge)."""
    if not (lag_hemma or lag_borta):
        logg("⚠ Ange minst ett lag.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    rader = []
    for namn in (lag_hemma, lag_borta):
        if not namn:
            continue
        url = klubb(namn).get("matches_url")
        if url:
            rader.append(f"- {namn}: {url}")
    fraga = f"Match: {lag_hemma} vs {lag_borta}"
    if datum:
        fraga += f", {datum}"
    if sport and sport.lower() not in ("", "auto"):
        fraga += f". Sport: {sport}"
    if rader:
        fraga += "\nOfficiell matchinfo på:\n" + "\n".join(rader)
    fraga += f"\n\nReturnera JSON:\n{SCHEMA_UPPSTALLNING}"

    data = claude.fraga_json(klient, SYSTEM_UPPSTALLNING, fraga,
                             verktyg=claude.web_search_verktyg(max_uses=8),
                             logg=logg)
    if data:
        n_start = sum(1 for p in data.get("spelare", []) if p.get("start"))
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare "
             f"({n_start} startande).")
    return data


# ── Läs ark via vision (HEIC/JPG/PNG/PDF) ────────────────────────────────────
def _innehall_block(path):
    """Anthropic content-block för bild/PDF (HEIC→JPEG via sips, PDF som
    dokument, bilder nedskalade). None vid fel/okänt format."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".pdf":
        try:
            data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
        except Exception:
            return None
        return {"type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": data}}
    jpg = p
    if suf in HEIC_SUFFIX:
        tmp = Path(tempfile.mkdtemp()) / "ark.jpg"
        try:
            subprocess.run(["sips", "-s", "format", "jpeg", str(p),
                            "--out", str(tmp)], check=True, capture_output=True)
            jpg = tmp
        except Exception:
            return None
    elif suf not in BILD_SUFFIX:
        return None
    try:
        from PIL import Image
        img = Image.open(jpg)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((LINEUP_MAX_KANT, LINEUP_MAX_KANT))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}


def hamta_trupp_for_lag(namn, url="", sport="", logg=print, klient=None):
    """Hämtar ETT lags trupp från en hemsida (URL:en om angiven, annars via
    web-sök). Returnerar {lag, spelare:[{nr,namn,position}], kallor} eller None."""
    if not (namn or "").strip():
        logg("⚠ Ange ett lag.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    url = (url or "").strip() or klubb(namn).get("squad_url", "")
    fraga = (f"Hämta spelartruppen för {namn}: besök {url}" if url
             else f"Hämta spelartruppen för {namn}: hitta officiell truppsida")
    if sport and sport.lower() not in ("", "auto"):
        fraga += f"\nSport: {sport}"
    fraga += f"\n\nReturnera JSON:\n{SCHEMA_LAGTRUPP}"

    data = claude.fraga_json(klient, SYSTEM_LAGTRUPP, fraga,
                             verktyg=claude.web_search_verktyg(max_uses=4),
                             logg=logg)
    if data:
        logg(f"✓ Hittade {len(data.get('spelare', []))} spelare.")
    return data


def las_trupp_fil(filsokvag, logg=print, klient=None):
    """Läser ETT lags trupplista ur bild/PDF via vision. Returnerar
    {lag, spelare:[{nr,namn,position}]} eller None."""
    block = _innehall_block(filsokvag)
    if block is None:
        logg(f"⚠ Kunde inte läsa filen ({Path(filsokvag).suffix}). "
             "Stöder HEIC/JPG/PNG/PDF.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    fraga = "Läs trupplistan och returnera JSON enligt schemat:\n" \
        + SCHEMA_TRUPP_ARK
    data = claude.fraga_json_innehall(
        klient, SYSTEM_TRUPP_ARK, [block, {"type": "text", "text": fraga}],
        logg=logg)
    if data:
        logg(f"✓ Läste {len(data.get('spelare', []))} spelare.")
    return data


# ── CSV-trupp (ren Python — ingen modell) ────────────────────────────────────
_CSV_NR = {"nr", "nummer", "no", "number", "#", "tröjnummer", "trojnummer"}
_CSV_NAMN = {"namn", "name", "spelare", "player"}
_CSV_POS = {"position", "pos", "roll"}


def tolka_trupp_csv(filsokvag, logg=print):
    """Tolkar en trupp-CSV → {spelare:[{nr,namn,position}]} eller None.
    Kolumnmappning via rubrikrad (nr/namn/position, sv+en); utan rubrik antas
    kolumnordningen nr,namn[,position]."""
    import csv
    try:
        text = Path(filsokvag).read_text(encoding="utf-8-sig")
    except Exception as e:
        logg(f"⚠ Kunde inte läsa CSV: {e}")
        return None
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except Exception:
        dialect = csv.excel
    rader = [r for r in csv.reader(text.splitlines(), dialect) if any(
        c.strip() for c in r)]
    if not rader:
        logg("⚠ CSV-filen är tom.")
        return None

    huvud = [c.strip().lower() for c in rader[0]]
    ix = {"nr": None, "namn": None, "position": None}
    for i, kol in enumerate(huvud):
        if kol in _CSV_NR:
            ix["nr"] = i
        elif kol in _CSV_NAMN:
            ix["namn"] = i
        elif kol in _CSV_POS:
            ix["position"] = i
    har_rubrik = ix["namn"] is not None
    if not har_rubrik:
        ix = {"nr": 0, "namn": 1 if len(rader[0]) > 1 else 0,
              "position": 2 if len(rader[0]) > 2 else None}

    spelare = []
    for rad in (rader[1:] if har_rubrik else rader):
        def _c(i):
            return rad[i].strip() if i is not None and i < len(rad) else ""
        namn = _c(ix["namn"])
        if not namn:
            continue
        spelare.append({"nr": _c(ix["nr"]), "namn": namn,
                        "position": _c(ix["position"])})
    if not spelare:
        logg("⚠ Hittade inga spelare i CSV-filen.")
        return None
    logg(f"✓ Läste {len(spelare)} spelare ur CSV.")
    return {"spelare": spelare}


def las_lineup(filsokvag, sport="", logg=print, klient=None):
    """Läser ett laguppställnings-ark via vision. Returnerar
    {matchinfo, lag, datum, arena, spelare:[...]} eller None."""
    block = _innehall_block(filsokvag)
    if block is None:
        logg(f"⚠ Kunde inte läsa filen ({Path(filsokvag).suffix}). "
             "Stöder HEIC/JPG/PNG/PDF.")
        return None
    klient = _klient_eller_skapa(klient, logg)
    if klient is None:
        return None

    fraga = "Läs laguppställnings-arket och returnera JSON enligt schemat:\n" \
        + SCHEMA_LINEUP
    if sport and sport.lower() != "auto":
        fraga = f"Sport: {sport}.\n" + fraga
    data = claude.fraga_json_innehall(
        klient, SYSTEM_LINEUP, [block, {"type": "text", "text": fraga}], logg=logg)
    if data:
        logg(f"✓ Läste {len(data.get('spelare', []))} spelare.")
    return data
