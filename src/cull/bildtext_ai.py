"""Claude vision-bildtexter: skriver publiceringsfärdiga svenska bildtexter
per bild via Anthropic-API:t.

Körs bara på de valda bilderna (opt-in, kostar per bild). Kräver att paketet
`anthropic` är injicerat och att ANTHROPIC_API_KEY finns i miljön. Bilderna
nedskalas innan de skickas (färre tokens, lägre kostnad).
"""

import base64
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2

MODELL_STANDARD = "claude-opus-4-8"
MAX_KANT = 1024          # nedskala långsidan innan upload (tokens/kostnad)
MAX_PARALLELLA = 5

SYSTEM = (
    "Du är bildredaktör för sportbilder och skriver bildtexter på svenska för "
    "pressbruk. Skriv EN kort, saklig bildtext i presens som beskriver vad som "
    "händer i bilden.\n"
    "Regler:\n"
    "- Använd ENDAST det du ser i bilden och det som ges i matchkontexten. "
    "Hitta ALDRIG på turnering, tävling, insats, omgång eller sammanhang "
    "(t.ex. 'VM-kval', 'final', 'seriematch') som inte uttryckligen ges.\n"
    "- Resultatet i matchkontexten är slutresultatet — tolka det INTE som att "
    "ett enskilt jubel i bilden är slutsegern. Skriv 'jublar' eller 'firar en "
    "poäng', inte 'firar segern', om det inte tydligt är slutsignalen.\n"
    "- Skriv ALDRIG ut något personnamn — inte ens om du tror dig känna igen "
    "spelaren. Använd bara tröjnummer och lag. Spelarnamn får bara förekomma om "
    "de uttryckligen ges i kontexten.\n"
    "- Ange tröjnummer och vilket lag (utifrån tröjfärg/kontext) när det syns. "
    "Gissa aldrig ett tröjnummer — utelämna det om siffran är otydlig.\n"
    "- En enda mening. Svara endast med själva bildtexten — inga citattecken, "
    "ingen inledning, ingen förklaring."
)


def tillganglig():
    """True om SDK + API-nyckel finns (annars kan bildtexter inte genereras)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _bild_base64(jpg_path):
    """Läser och nedskalar en bild → (base64-jpg, media_type) eller None."""
    img = cv2.imread(str(jpg_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    skala = MAX_KANT / max(h, w)
    if skala < 1.0:
        img = cv2.resize(img, (int(w * skala), int(h * skala)),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _kontext(matchinfo, sport, hemma_farg, nummer, namn):
    rader = []
    if matchinfo:
        rader.append(f"Match: {matchinfo}")
    if sport and sport != "okänd":
        rader.append(f"Sport: {sport}")
    if hemma_farg:
        rader.append(f"Hemmalaget spelar i {hemma_farg}.")
    if namn:
        rader.append(f"Spelare i bild (namn och tröjnummer): {namn}")
    elif nummer:
        rader.append(f"Avlästa tröjnummer i bild: {', '.join(str(n) for n in nummer)}")
    rader.append("Skriv bildtexten.")
    return "\n".join(rader)


def generera_bildtexter(jobb, matchinfo, sport, hemma_farg=None,
                        modell=MODELL_STANDARD, logg=print):
    """jobb: lista av {id, jpg, nummer, namn}. Returnerar {id: bildtext}.

    id som inte kunde genereras utelämnas. Tomt resultat vid saknad nyckel/SDK."""
    if not tillganglig():
        logg("  Bildtext-AI: ANTHROPIC_API_KEY saknas eller anthropic ej "
             "installerat — hoppar över.")
        return {}
    import anthropic
    # Fler återförsök än standard (2) — tål tillfällig 529-överbelastning.
    klient = anthropic.Anthropic(max_retries=6)

    def en(j):
        b64 = _bild_base64(j["jpg"]) if j.get("jpg") else None
        if not b64:
            return j["id"], None
        innehall = [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": _kontext(matchinfo, sport, hemma_farg,
                                              j.get("nummer"), j.get("namn"))},
        ]
        svar = klient.messages.create(
            model=modell, max_tokens=300, system=SYSTEM,
            messages=[{"role": "user", "content": innehall}])
        text = "".join(b.text for b in svar.content if b.type == "text").strip()
        return j["id"], text.strip('"').strip() or None

    resultat = {}
    fel = 0
    with ThreadPoolExecutor(max_workers=MAX_PARALLELLA) as pool:
        futs = {pool.submit(en, j): j for j in jobb}
        for fut in as_completed(futs):
            try:
                jid, text = fut.result()
                if text:
                    resultat[jid] = text
            except Exception as e:
                fel += 1
                if fel <= 2:
                    logg(f"  Bildtext-AI: fel ({type(e).__name__}: {e}).")
    logg(f"  Bildtext-AI: {len(resultat)}/{len(jobb)} bildtexter "
         f"({modell})." + (f" {fel} fel." if fel else ""))
    return resultat
