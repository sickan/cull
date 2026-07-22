"""Läs in ett events tidsprogram och startlista (V5 §8, S2).

Arrangörens PDF klistras in som text — formaten varierar mellan förbund och
år, så parsern GISSAR och flaggar i stället för att kräva. Varje rad bär
`varning` när gissningen är osäker; granskningstabellen i UI:t är
skyddsnätet, inte den här modulen. Ingenting sparas härifrån.

Tidsprogram — dagrubriker plus tidsatta rader:

    Fredag 24 juli
    09:00  100 m dam, Försök, A-planen
    14:00  100 m dam - Semi
    Lördag 25 juli
    19:10  100 m dam Final

Startlista — grenrubrik plus deltagare:

    100 m dam
    1  Anna Andersson  IF Göta  @anna_a
    2  Beata Berg, Malmö AI
"""

import csv
import re

# Ord som avslutar en gren och inleder ett pass. Ordningen spelar roll:
# längre uttryck först så "semifinal" inte fastnar på "final".
PASSORD = [
    "kvalomgång", "kvalomgang", "semifinal", "kvartsfinal", "uppvärmning",
    "uppvarmning", "prisutdelning", "försök", "forsok", "final", "kval",
    "semi", "heat", "omgång", "omgang", "pool",
]

MANADER = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

VECKODAGAR = ("måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag",
              "söndag", "mandag", "lordag", "sondag")

_TID = re.compile(r"^(\d{1,2})[:.](\d{2})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAG_MAN = re.compile(r"\b(\d{1,2})\s+([a-zåäö]+)\b", re.I)
_DAG_SNED = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def _dela(text):
    """Delar en rad på tabb, semikolon, pipe, komma eller ' - '. Två eller
    fler mellanslag räknas också — kolumner ur en PDF blir ofta så."""
    for avgr in ("\t", ";", "|"):
        if avgr in text:
            return [d.strip() for d in text.split(avgr) if d.strip()]
    if "," in text:
        return [d.strip() for d in text.split(",") if d.strip()]
    for streck in (" - ", " – ", " — "):
        if streck in text:
            return [d.strip() for d in text.split(streck) if d.strip()]
    delar = re.split(r"\s{2,}", text)
    return [d.strip() for d in delar if d.strip()]


def _dela_passord(text):
    """Sista utvägen när raden saknar avgränsare: hittar ett känt passord och
    delar där. '100 m dam Final' → ('100 m dam', 'Final')."""
    lag = text.lower()
    for ord_ in PASSORD:
        i = lag.rfind(ord_)
        if i <= 0:
            continue
        gren, pas = text[:i].strip(" -–—"), text[i:].strip()
        if gren:
            return gren, pas[:1].upper() + pas[1:]
    return text, ""


def tolka_datum(rad, ar=None):
    """Tolkar en dagrubrik → 'YYYY-MM-DD', annars None.

    Klarar '2026-07-24', 'Fredag 24 juli', '24/7'. Utan årtal i texten
    används `ar` (eventets period) — därför bör anroparen skicka det."""
    text = (rad or "").strip()
    if not text:
        return None
    m = _ISO.search(text)
    if m:
        return m.group(0)
    m = _DAG_MAN.search(text)
    if m and m.group(2).lower() in MANADER:
        if not ar:
            return None
        return f"{ar:04d}-{MANADER[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = _DAG_SNED.search(text)
    if m:
        if not ar:
            return None
        return f"{ar:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _ar_dagrubrik(text):
    lag = text.lower()
    return (any(d in lag for d in VECKODAGAR)
            or bool(_ISO.search(text))
            or bool(re.fullmatch(r"[^\d]*\d{1,2}[/ ][a-zåäö\d]+[^\d]*", lag)))


def tolka_tidsprogram(text, ar=None, standarddatum=None):
    """Klistrat tidsprogram → rader {datum, tid, gren, pass, plats, varning}.

    Rader utan klockslag hoppas över om de inte är dagrubriker. Saknas datum
    helt används `standarddatum` (eventets första dag) och raden flaggas."""
    ut = []
    datum = standarddatum
    dagrubrik_sedd = False
    for rå in (text or "").splitlines():
        rad = rå.strip()
        if not rad:
            continue
        nytt = tolka_datum(rad, ar=ar) if _ar_dagrubrik(rad) else None
        if nytt:
            datum, dagrubrik_sedd = nytt, True
            continue
        m = _TID.match(rad)
        if not m:
            continue
        tid = f"{int(m.group(1)):02d}:{m.group(2)}"
        rest = rad[m.end():].strip(" -–—\t")
        if not rest:
            continue
        delar = _dela(rest)
        varning = ""
        if len(delar) >= 2:
            gren, pas = delar[0], delar[1]
            plats = delar[2] if len(delar) > 2 else ""
        else:
            gren, pas = _dela_passord(delar[0] if delar else rest)
            plats = ""
            if not pas:
                varning = "Hittade inget passnamn — sätt det själv"
        if not dagrubrik_sedd:
            varning = (varning + " · " if varning else "") + \
                "Ingen dagrubrik hittad — kontrollera datumet"
        # Versal oavsett vilken väg passnamnet kom — 'kval' och 'Kval' ska
        # inte bli två olika pass i programmet.
        pas = pas[:1].upper() + pas[1:] if pas else ""
        ut.append({"datum": datum, "tid": tid, "gren": gren, "pass": pas,
                   "plats": plats, "varning": varning, "radtext": rad})
    return ut


def tolka_startlista(text, kanda_grenar=()):
    """Klistrad startlista → rader {gren, namn, klubb, handle, varning}.

    Grenrubriker känns igen mot `kanda_grenar` (eventets befintliga grenar);
    saknas träff gissar vi på rader utan avgränsare. Handle plockas där den
    står — startlistor bär den sällan, men klistrar man in ur ett kalkylark
    finns den ofta med."""
    kanda = {g.strip().lower(): g.strip() for g in kanda_grenar if g}
    ut = []
    gren = ""
    for rå in (text or "").splitlines():
        rad = rå.strip()
        if not rad:
            continue
        if rad.lower() in kanda:
            gren = kanda[rad.lower()]
            continue
        delar = _dela(rad)
        # Grenrubrik: en ensam kortare rad utan siffror i början.
        if len(delar) == 1 and not re.match(r"^\d", rad) and len(rad) < 40:
            if not kanda or rad.lower() in kanda:
                gren = kanda.get(rad.lower(), rad)
                continue
        # Startnummer först i raden är vanligt — det är inte namnet.
        if delar and re.fullmatch(r"\d{1,4}", delar[0]):
            delar = delar[1:]
        if not delar:
            continue
        handle = ""
        for i, d in enumerate(delar):
            if d.startswith("@"):
                handle = d
                delar = delar[:i] + delar[i + 1:]
                break
        namn = delar[0] if delar else ""
        klubb = delar[1] if len(delar) > 1 else ""
        if not namn:
            continue
        ut.append({"gren": gren, "namn": namn, "klubb": klubb,
                   "handle": handle,
                   "varning": "" if gren else "Ingen gren — välj i listan"})
    return ut


# ── PDF med kolumnlayout ─────────────────────────────────────────────────────
# Arrangörens tidsprogram är sällan en lista. SM 2026 är ett rutnät: tre dagar
# SIDA VID SIDA, var och en med (tid | Män | Kvinnor). Läser man texten utan
# koordinater flätas dagarna ihop rad för rad och allt blir fel — därför
# positionsläsning. Kolumnerna är CENTRERADE, så en post hör till den kolumn
# vars mitt ligger närmast postens mitt (inte dess vänsterkant).
#
# Filen ritar dessutom varje glyf två gånger på identiska koordinater (en
# skugg-/fetstilseffekt). pdfplumbers dedupe_chars() städar det; att i stället
# klippa varannan TECKEN går sönder på ligaturer ("final" blir "fnal").

KLASSKOLUMNER = {"män": "herr", "man": "herr", "herrar": "herr", "herr": "herr",
                 "kvinnor": "dam", "damer": "dam", "dam": "dam"}

_DAGRUBRIK = re.compile(
    r"(måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)\s+(\d{1,2})\s+([a-zåäö]+)",
    re.I)


def _klustra(ord_, lucka=14):
    """Slår ihop ord på samma rad till poster. En lucka bredare än `lucka`
    punkter betyder ny kolumn — inom en post står orden tätt."""
    ut = []
    for w in sorted(ord_, key=lambda w: w["x0"]):
        if ut and w["x0"] - ut[-1][-1]["x1"] <= lucka:
            ut[-1].append(w)
        else:
            ut.append([w])
    return ut


def _mitt(kluster):
    return (kluster[0]["x0"] + kluster[-1]["x1"]) / 2


def pdf_stod():
    """Går PDF-läsning att göra i den här installationen?

    Egen fråga eftersom svaret annars döljs: ett saknat pdfplumber gav förut
    samma tomma lista som en fil utan tidsprogram, och felmeddelandet skyllde
    på filen. DPT2 körs dessutom med pipx-venvets python, inte repots — en
    `pip install` i fel interpreter syns bara här."""
    try:
        import pdfplumber       # noqa: F401
        return True
    except ImportError:
        return False


def las_pdf(path, ar=None):
    """Läser ett tidsprogram ur en PDF med kolumnlayout.

    Returnerar samma radform som tolka_tidsprogram, plus `klass` ('dam'/'herr')
    när posten stod i en köns-kolumn — den blir grenmarkörens färg utan att
    någon behöver skriva den. Kräver pdfplumber; utan den returneras [].

    Layouten läses ur filen (dagrubriker och köns-rubriker med sina x-lägen),
    inte ur hårdkodade mått — en annan arrangör med samma grundform fungerar
    därför också. Allt är förslag: granskningstabellen är skyddsnätet.
    """
    try:
        import pdfplumber
    except ImportError:
        return []
    rader = []
    try:
        with pdfplumber.open(path) as pdf:
            for sida in pdf.pages:
                rader.extend(_las_sida(sida.dedupe_chars(), ar))
    except Exception:
        return []            # oläsbar/saknad fil — anroparen erbjuder inklistring
    rader.sort(key=lambda r: (r["datum"] or "", r["tid"] or "99:99"))
    return rader


def _las_sida(sida, ar):
    from collections import defaultdict
    linjer = defaultdict(list)
    for w in sida.extract_words():
        linjer[round(w["top"], 1)].append(w)

    # 1) Dagrubriker → varje dags x-mitt och datum.
    dagar = []                       # [{mitt, datum}]
    for top in sorted(linjer):
        text = " ".join(w["text"] for w in sorted(linjer[top], key=lambda w: w["x0"]))
        if not _DAGRUBRIK.search(text):
            continue
        for kl in _klustra(linjer[top], lucka=20):
            bit = " ".join(w["text"] for w in kl)
            m = _DAGRUBRIK.search(bit)
            if m and m.group(3).lower() in MANADER and ar:
                dagar.append({"mitt": _mitt(kl),
                              "datum": f"{ar:04d}-{MANADER[m.group(3).lower()]:02d}"
                                       f"-{int(m.group(2)):02d}"})
        if dagar:
            break
    if not dagar:
        return []
    dagar.sort(key=lambda d: d["mitt"])

    # 2) Köns-rubriker → kolumnmitter, knutna till närmaste dag.
    kolumner = []                    # [{mitt, klass, datum}]
    for top in sorted(linjer):
        kl = [w for w in linjer[top]
              if w["text"].strip().lower() in KLASSKOLUMNER]
        if len(kl) < 2:
            continue
        for w in kl:
            mitt = (w["x0"] + w["x1"]) / 2
            dag = min(dagar, key=lambda d: abs(d["mitt"] - mitt))
            kolumner.append({"mitt": mitt,
                             "klass": KLASSKOLUMNER[w["text"].strip().lower()],
                             "datum": dag["datum"]})
        break
    if not kolumner:
        return []

    # 3) Varje rad: tidsposten hör till en dag, övriga poster till en kolumn.
    ut = []
    for top in sorted(linjer):
        poster = _klustra(linjer[top])
        tider = {}                   # datum → tid, för denna rad
        ovriga = []
        for kl in poster:
            text = " ".join(w["text"] for w in kl)
            m = _TID.match(text.strip())
            if m and len(kl) == 1:
                dag = min(dagar, key=lambda d: abs(d["mitt"] - _mitt(kl)))
                tider[dag["datum"]] = f"{int(m.group(1)):02d}:{m.group(2)}"
            else:
                ovriga.append(kl)
        for kl in ovriga:
            kol = min(kolumner, key=lambda k: abs(k["mitt"] - _mitt(kl)))
            tid = tider.get(kol["datum"])
            if not tid:
                continue             # post utan tid på sin dag — hoppa
            text = " ".join(w["text"] for w in kl).strip()
            if not text or text.lower() in KLASSKOLUMNER:
                continue
            gren, pas = _dela_passord(text)
            ut.append({
                "datum": kol["datum"], "tid": tid, "gren": gren, "pass": pas,
                "plats": "", "klass": kol["klass"], "radtext": text,
                "varning": "" if pas else "Hittade inget passnamn — sätt det själv",
            })
    return ut


# ── Startlista med tider (EasyRecord m.fl.) ─────────────────────────────────
# Arrangörens startlistesida bär BÅDE programmet och deltagarna: varje gren har
# sina passrader ("Försök Fredag, 18:20") direkt ovanför sin deltagartabell.
# En inklistring ger därför båda delarna — bättre källa än PDF:en, som bara har
# tiderna.
#
# Formen (SM 2026, easyrecord.se) efter kopiering ur webbläsaren:
#
#     Kvinnor 100 m                 ← klass + gren
#     Försök Fredag, 18:20          ← pass med veckodag
#     Final Fredag, 20:25
#     ...tabellhuvud...
#     80⇥Esther Sahlqvist⇥06⇥Hammarby IF⇥11.85⇥11.682023
#     Antal deltagare: 22
#
# Mångkamp har en passrad per DELGREN ("100 m Fredag, 12:45") — de blir pass på
# grenen Tiokamp, vilket är precis vad de är.

KLASSORD = {"kvinnor": "dam", "damer": "dam", "flickor": "dam",
            "män": "herr", "man": "herr", "herrar": "herr", "pojkar": "herr"}

_VECKODAG = {"måndag": 0, "tisdag": 1, "onsdag": 2, "torsdag": 3,
             "fredag": 4, "lördag": 5, "söndag": 6,
             "mandag": 0, "lordag": 5, "sondag": 6}

_PASSRAD = re.compile(
    r"^(?P<namn>.+?)\s+(?P<dag>" + "|".join(_VECKODAG) + r")\s*,\s*"
    r"(?P<tid>\d{1,2}[:.]\d{2})\s*$", re.I)
_GRENRUBRIK = re.compile(
    r"^(?P<klass>kvinnor|damer|flickor|män|man|herrar|pojkar)\s+(?P<rest>\S.*)$",
    re.I)
_ANTAL = re.compile(r"^antal\s+(deltagare|starter)\s*:", re.I)


def _dagar_i_perioden(fran, till):
    """Veckodagsnamn → ISO-datum inom eventets period. Startlistan skriver
    'Fredag', inte ett datum — perioden gör om det till rätt dag."""
    from datetime import date, timedelta
    ut = {}
    try:
        d0 = date.fromisoformat(fran)
        d1 = date.fromisoformat(till or fran)
    except (TypeError, ValueError):
        return ut
    d, varv = d0, 0
    while d <= d1 and varv < 60:
        for namn, nr in _VECKODAG.items():
            if nr == d.weekday():
                ut.setdefault(namn, d.isoformat())
        d += timedelta(days=1)
        varv += 1
    return ut


def tolka_startlista_med_tider(text, fran=None, till=None):
    """Klistrad startlistesida → {"pass": [...], "deltagare": [...]}.

    Passraderna får samma form som tolka_tidsprogram, deltagarraderna samma som
    tolka_startlista — så bägge kan gå genom befintlig granskning och import.
    Utan `fran` går passen inte att datera; de flaggas då i stället för att
    slängas."""
    dagar = _dagar_i_perioden(fran, till)
    pas, delt = [], []
    grenar = []          # grenar det aktuella blocket gäller (>1 = mixad gren)
    klass = ""
    klasskolumn = False  # sätts när en "Klass"-kolumnrubrik setts (mixad startlista)

    def _norm(s):
        return "".join((s or "").lower().split())

    def _gren_for_klass(rad_klass):
        # "(Kvinnor) I-20" → grenen i den mixade uppsättningen vars namn bär
        # klassdelen ("I-20 100 m"). Faller till första grenen utan träff.
        k = (rad_klass or "").lower()
        for ko in KLASSORD:
            if k.startswith(ko):
                k = k[len(ko):]
                break
        kn = _norm(k)
        for g in grenar:
            if kn and kn in _norm(g):
                return g
        return grenar[0] if grenar else ""

    for rå in (text or "").splitlines():
        rad = rå.strip()
        if not rad or _ANTAL.match(rad):
            continue
        # "Klass"-kolumnrubrik: deltagarraderna bär då en klass per rad (mixad
        # gren där t.ex. Kvinnor I-20 och Kvinnor R-stående springer samma lopp).
        if rad.lower() == "klass":
            klasskolumn = True
            continue
        # Deltagarrad: tabbar och startnummer först. Testas FÖRE grenrubriken —
        # en klubb kan heta "Män..." och ska inte tolkas som ny gren.
        if "\t" in rå:
            d = [x.strip() for x in rå.split("\t")]
            # Startnumret får SAKNAS: på SM 2026 står Oscar Holmin utan nummer
            # i två grenar, och ett krav på siffror hade tappat båda tyst.
            # Namnet i andra fältet är det som gör raden till en deltagare.
            if (len(d) >= 3 and d[1] and not d[1].isdigit()
                    and (not d[0] or re.fullmatch(r"\d{1,5}", d[0]))):
                g = grenar[0] if grenar else ""
                # Mixad startlista: Klass-kolumnen (efter klubben) styr vilken av
                # de mixade grenarna raden hör till.
                if (klasskolumn and len(d) > 4 and d[4]
                        and not d[4].replace(".", "").isdigit()):
                    g = _gren_for_klass(d[4])
                # SB/PB (#8): kolumnerna efter klubb (+ ev. Klass). PB bär ofta
                # årtal i svansen ("54012026" = 5401 år 2026, "14.932025" = 14.93
                # år 2025) — strippa det så bara värdet visas.
                sb_idx = 5 if klasskolumn else 4
                sb = d[sb_idx] if len(d) > sb_idx else ""
                pb_rå = d[sb_idx + 1] if len(d) > sb_idx + 1 else ""
                pb = re.sub(r"\s*(20\d\d)\s*$", "", pb_rå).strip() if pb_rå else ""
                delt.append({
                    "gren": g, "klass": klass, "namn": d[1],
                    "klubb": d[3] if len(d) > 3 else "", "handle": "",
                    "sb": sb, "pb": pb,
                    "varning": "" if g else "Ingen gren — välj i listan",
                })
                continue
        # "Mixad med {gren}": grenen körs ihop med en till klass i samma lopp —
        # lägg till den som en gren till i blocket (delar pass + startlista).
        if rad.lower().startswith("mixad med "):
            m2 = _GRENRUBRIK.match(rad[len("mixad med "):].strip())
            if m2:
                g2 = m2.group("rest").strip()
                if g2 and g2 not in grenar:
                    grenar.append(g2)
            continue
        m = _GRENRUBRIK.match(rad)
        if m and not m.group("rest").lower().startswith(("startlista", "gren")):
            rest = m.group("rest").strip()
            # Kombinerad mixad-rubrik "A & B …" — grenarna är redan satta via
            # primärraden + "Mixad med"; låt den inte skriva över dem.
            if "&" in rest and len(grenar) > 1:
                continue
            klass = KLASSORD.get(m.group("klass").lower(), "")
            grenar = [rest]
            klasskolumn = False
            continue
        m = _PASSRAD.match(rad)
        if m and grenar:
            datum = dagar.get(m.group("dag").lower(), "")
            t = m.group("tid").replace(".", ":")
            tim, mi = t.split(":")
            for g in grenar:      # mixad gren → passet gäller båda grenarna
                pas.append({
                    "datum": datum, "tid": f"{int(tim):02d}:{mi}",
                    "gren": g, "pass": m.group("namn").strip(),
                    "plats": "", "klass": klass,
                    "varning": "" if datum else
                               f"Kunde inte datera {m.group('dag')} — sätt eventets period",
                })
    return {"pass": pas, "deltagare": delt}


def las_csv(text):
    """CSV/TSV med rubrikrad → lista med dictar, nycklarna gemener.

    Erkända kolumner för tidsprogram: datum, tid, gren, pass, plats.
    För startlista: gren, namn, klubb, handle. Returnerar [] utan rubrikrad."""
    rader = [r for r in (text or "").splitlines() if r.strip()]
    if not rader:
        return []
    avgr = "\t" if "\t" in rader[0] else (
        ";" if rader[0].count(";") > rader[0].count(",") else ",")
    las = csv.DictReader(rader, delimiter=avgr)
    if not las.fieldnames:
        return []
    kanda = {"datum", "tid", "gren", "pass", "plats", "namn", "klubb", "handle"}
    rubriker = {(f or "").strip().lower() for f in las.fieldnames}
    if not (rubriker & kanda):
        return []
    ut = []
    for r in las:
        d = {(k or "").strip().lower(): (v or "").strip()
             for k, v in r.items() if k}
        if any(d.values()):
            ut.append(d)
    return ut


# ── C8–C10: en väg in — igenkänning, sammanfattning, avvikelser ──────────────
# Arrangörens fil kan vara tidsprogram, startlista med tider (EasyRecord) eller
# bara en deltagarlista. Förr valde Stig sort själv i tre flikar; nu GISSAR vi
# och frågar bara vid osäkerhet (C8). Granskningen visar sedan bara det som
# sticker ut (C9) i stället för att kräva ögon på 845 rena rader.

def _nyckel(namn):
    """Grennyckel för jämförelse — gemener utan mellanslag. Samma tanke som
    store._grennyckel: '100 m' och '100m' ur olika källor ska vara samma gren."""
    return "".join((namn or "").lower().split())


def kanna_igen(text):
    """Gissar dokumenttyp (C8) → (sort, sakerhet, skal).

    sort ∈ {tidsprogram, startlista_tider, startlista, csv_program, csv_startlista}.
    sakerhet ∈ {saker, osaker} — UI:t frågar bara vid 'osaker'. `skal` är en
    kort klartext för varför, som kan visas bredvid valet."""
    rader = [r.strip() for r in (text or "").splitlines() if r.strip()]
    if not rader:
        return ("tidsprogram", "osaker", "Tom text")
    # CSV först: en rubrikrad med kända kolumner avgör utan att gissa.
    csv_rader = las_csv(text)
    if csv_rader:
        nycklar = set().union(*(set(r) for r in csv_rader))
        if {"namn"} & nycklar and not ({"tid", "datum", "pass"} & nycklar):
            return ("csv_startlista", "saker", "CSV med deltagarkolumner")
        return ("csv_program", "saker", "CSV med programkolumner")
    passrader = sum(1 for r in rader if _PASSRAD.match(r))
    grenrubriker = sum(1 for r in rader if _GRENRUBRIK.match(r))
    tidsrader = sum(1 for r in rader if _TID.match(r))
    tabbrader = sum(1 for r in (text or "").splitlines() if "\t" in r)
    handles = sum(1 for r in rader if "@" in r)
    # Startlista med tider: passrader med veckodag ("Final Fredag, 20:25") är
    # den signatur bara EasyRecord-sidan bär.
    if passrader >= 1 and (grenrubriker >= 1 or tabbrader >= 1):
        return ("startlista_tider", "saker",
                f"{passrader} passrader med veckodag · {tabbrader} deltagarrader")
    # Tidsprogram: rader som inleds med klockslag.
    if tidsrader >= 2 and tidsrader >= passrader:
        return ("tidsprogram", "saker", f"{tidsrader} tidsatta rader")
    # Inga tider men deltagartecken (tabbar, @handle, grenrubriker) → deltagare.
    if tabbrader >= 1 or handles >= 1 or grenrubriker >= 1:
        return ("startlista", "saker", "Grenrubriker och deltagarrader utan tider")
    # Osäkert: en tidsrad, eller bara löptext. Låt Stig välja.
    if tidsrader >= 1:
        return ("tidsprogram", "osaker", "Enstaka tidsrad — kontrollera typen")
    return ("startlista", "osaker", "Kunde inte avgöra typen säkert")


def _grunddata(sort):
    """Är detta ett program (pass) eller en deltagarlista i grunden?"""
    return "program" if sort in ("tidsprogram", "startlista_tider",
                                 "csv_program") else "startlista"


def sammanfatta(sort, rader, deltagare=None):
    """C8-sammanfattning i klartext: 'N dagar · N grenar · N starter · N pass'
    plus hur många rader som bär en varning ('behöver din blick')."""
    rader = rader or []
    deltagare = deltagare or []
    prog = rader if _grunddata(sort) == "program" else []
    delt = deltagare if deltagare else (rader if _grunddata(sort) == "startlista" else [])
    dagar = {(r.get("datum") or "").strip() for r in prog if (r.get("datum") or "").strip()}
    grenar = {_nyckel(r.get("gren")) for r in list(prog) + list(delt)
              if (r.get("gren") or "").strip()}
    behover = sum(1 for r in list(rader) + list(deltagare) if (r.get("varning") or "").strip())
    return {
        "dagar": len(dagar), "grenar": len(grenar),
        "pass": len(prog), "starter": len(delt),
        "behover_blick": behover, "totalt": len(rader) + len(deltagare),
    }


def _avvikelser_i(sort, rader, deltagare):
    """Sätter `avvik`-etikett på varje rad (C9): '' | flaggad | dubblett |
    okand_klass | tidskrock. En rad bär högst en etikett — strukturfel före
    parserns egen varning, så det tydligaste syns."""
    prog = rader if _grunddata(sort) == "program" else []
    alla = list(rader) + list(deltagare)

    # Dubbletter: samma grennyckel stavad på flera sätt (ur olika källor).
    stavning = {}
    for r in alla:
        namn = (r.get("gren") or "").strip()
        if namn:
            stavning.setdefault(_nyckel(namn), set()).add(namn)
    dubbelnycklar = {k for k, v in stavning.items() if len(v) > 1}

    # Okänd klass: grennyckel finns MED klass någonstans men den här raden
    # saknar den → tvetydig (100 m finns som dam+herr, raden säger inte vilken).
    med_klass = {_nyckel(r.get("gren")) for r in alla
                 if (r.get("gren") or "").strip()
                 and (r.get("klass") or "").strip() in ("dam", "herr", "mixed")}

    # Tidskrock: två programrader på samma datum+tid med olika gren/pass.
    tidskrock = set()
    per_tid = {}
    for i, r in enumerate(prog):
        d, t = (r.get("datum") or "").strip(), (r.get("tid") or "").strip()
        if d and t:
            per_tid.setdefault((d, t), []).append(i)
    for (d, t), idxs in per_tid.items():
        signaturer = {(_nyckel(prog[i].get("gren")), (prog[i].get("pass") or "").strip().lower())
                      for i in idxs}
        if len(signaturer) > 1:
            tidskrock.update(id(prog[i]) for i in idxs)

    for r in alla:
        namn = (r.get("gren") or "").strip()
        nyckel = _nyckel(namn)
        if id(r) in tidskrock:
            r["avvik"] = "tidskrock"
        elif nyckel and nyckel in dubbelnycklar:
            r["avvik"] = "dubblett"
        elif (namn and nyckel in med_klass
                and (r.get("klass") or "").strip() not in ("dam", "herr", "mixed")):
            r["avvik"] = "okand_klass"
        elif (r.get("varning") or "").strip():
            r["avvik"] = "flaggad"
        else:
            r["avvik"] = ""
    return rader, deltagare


AVVIK_ETIKETT = {
    "tidskrock": "Tidskrockar",
    "dubblett": "Dubbletter (samma gren, olika stavning)",
    "okand_klass": "Okänd klass",
    "flaggad": "Behöver din blick",
}


def analysera(sort, rader, deltagare=None):
    """Slår ihop sammanfattning (C8) + avvikelsemärkning (C9). Muterar raderna
    med ett `avvik`-fält och returnerar allt UI:t behöver för granskningsvyn."""
    deltagare = deltagare or []
    _avvikelser_i(sort, rader or [], deltagare)
    sam = sammanfatta(sort, rader or [], deltagare)
    avvikande = sum(1 for r in list(rader or []) + list(deltagare) if r.get("avvik"))
    sam["avvikande"] = avvikande
    sam["rena"] = sam["totalt"] - avvikande
    return {"sammanfattning": sam, "rader": rader or [], "deltagare": deltagare}
