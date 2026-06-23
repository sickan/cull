"""Bakgrundspass: läser tröjnummer på de VALDA bilderna och skriver in dem som
keywords i bildernas metadata (XMP/IPTC, inbäddat → syns i Lightroom).

Skiljer sig från cullens första flöde:
- körs på exakt de bilder som finns i den valda mappen (t.ex. urvalet på 20),
- EasyOCR på ALLA spelar-utsnitt per bild (inte bara de 5 största),
- skriver ALLA avlästa nummer (inte bara de bevakade) → roster ger namn.

EasyOCR är gratis och körs alltid. Claude vision är en opt-in-fallback (--claude)
som bara körs på bilder där OCR inte fick ut något trots att en spelare syns;
den har en hård tak-gräns (--max-claude) så kostnaden är förutsägbar. Bilder som
ingen motor klarar listas i osakra_nummer.json för manuell genomgång (Steg 2).

Allt cachas på path|size i nummer_cache.json (omkörning gratis)."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cull import ai_lager, roster as roster_mod
from cull.core import (BILD_SUFFIX, RAW_SUFFIX, JPG_SUFFIX,
                       extrahera_previews_batch)

NUMMER_CACHE_PATH = Path.home() / ".cache" / "cull" / "nummer_cache.json"
OSAKRA_PATH = Path.home() / ".cache" / "cull" / "osakra_nummer.json"
# Manuellt bekräftade nummer (Steg 2) — grundsanning för framtida träning.
FACIT_PATH = Path.home() / ".cache" / "cull" / "nummer_facit.json"
# Beständiga previews för luckorna (överlever /tmp-städning → Steg 2 hittar dem).
OSAKRA_THUMBS = Path.home() / ".cache" / "cull" / "osakra_thumbs"

# Grov kostnadsuppskattning per Claude-anrop (nedskalad bild + kort svar).
KR_PER_CLAUDE = 0.10        # ~1 cent → ~0,10 kr, medvetet i överkant
MAX_CLAUDE_STANDARD = 40    # tak: värsta fall ~4 kr


def _env():
    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def _nyckel(p):
    return f"{p}|{p.stat().st_size}"


def _ladda_cache():
    try:
        with open(NUMMER_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _spara_cache(c):
    try:
        NUMMER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(NUMMER_CACHE_PATH, "w") as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _bilder_per_stam(mapp):
    """{stam: [filer]} för alla bildfiler i mappen (raw + jpg)."""
    grupper = {}
    try:
        for p in sorted(mapp.iterdir()):
            if p.suffix.lower() in BILD_SUFFIX and not p.name.startswith("."):
                grupper.setdefault(p.stem, []).append(p)
    except Exception:
        pass
    return grupper


def _preview_kalla(filer):
    """Bästa fil att OCR:a per stam: jpg direkt om den finns, annars raw."""
    for f in filer:
        if f.suffix.lower() in JPG_SUFFIX:
            return f
    return filer[0]


def _las_nummer(img_bgr, yolo_res, ocr, roster, min_konf=0.45, max_personer=25):
    """(mängd tröjnummer, antal personer) — OCR på alla spelar-utsnitt med
    brus-filter: konfidens-tröskel + bara 1–2 siffror (0–99) + roster-filter
    när en trupplista finns. Tar bort reklamtext, poäng-overlays och
    hopslagna siffror som annars förorenar keywords."""
    if ocr is None or yolo_res is None or yolo_res.boxes is None:
        return set(), 0
    personer, n_pers = [], 0
    for box, cls in zip(yolo_res.boxes.xyxy, yolo_res.boxes.cls):
        if int(cls) != 0:           # klass 0 = person
            continue
        n_pers += 1
        x1, y1, x2, y2 = map(int, box.tolist())
        personer.append(((x2 - x1) * (y2 - y1), x1, y1, x2, y2))
    personer.sort(reverse=True)     # störst (närmast) först

    nummer = set()
    for _, x1, y1, x2, y2 in personer[:max_personer]:
        if (x2 - x1) < 24 or (y2 - y1) < 48:   # för liten → oläsbart
            continue
        y_mid = y1 + (y2 - y1) * 2 // 3        # ryggnumret = övre 2/3
        crop = img_bgr[max(0, y1):y_mid, max(0, x1):x2]
        if crop.size == 0:
            continue
        for _b, text, konf in ocr.readtext(crop, allowlist="0123456789", detail=1):
            if konf < min_konf:
                continue
            t = (text.strip().lstrip("0") or "0")
            if not t.isdigit() or not (1 <= len(t) <= 2):   # tröjnummer 0–99
                continue
            if roster and t not in roster:                  # bara riktiga squad-nr
                continue
            nummer.add(t)
    return nummer, n_pers


def _claude_nummer(jpg_path, roster_text, hemma_farg, modell):
    """Frågar Claude vilka tröjnummer som tydligt syns. Returnerar lista siffror."""
    from cull import bildtext_ai
    b64 = bildtext_ai._bild_base64(jpg_path)
    if not b64:
        return []
    import anthropic
    klient = anthropic.Anthropic(max_retries=6)
    system = (
        "Du läser tröjnummer på sportbilder. Svara ENDAST med de tröjnummer du "
        "TYDLIGT ser, som kommaseparerade siffror (t.ex. '10, 7'). Gissa aldrig "
        "ett otydligt nummer. Ser du inga tydliga nummer, svara exakt 'inga'."
    )
    kontext = "Läs av tröjnumren i bilden."
    if hemma_farg:
        kontext += f" Hemmalaget spelar i {hemma_farg}."
    if roster_text:
        kontext += f" Trupplista (nummer = namn): {roster_text}"
    innehall = [
        {"type": "image", "source": {"type": "base64",
                                     "media_type": "image/jpeg", "data": b64}},
        {"type": "text", "text": kontext},
    ]
    svar = klient.messages.create(model=modell, max_tokens=60, system=system,
                                  messages=[{"role": "user", "content": innehall}])
    text = "".join(b.text for b in svar.content if b.type == "text").strip()
    if not text or text.lower().startswith("inga"):
        return []
    return [d for d in (t.strip() for t in text.replace(";", ",").split(","))
            if d.isdigit()]


def _skriv_keywords(filer, nummer, roster, env):
    """Skriver tröjnummer/-namn som keywords till alla filer för stammen + till
    ev. .xmp-sidecar (Lightroom läser metadata ur sidecaren för raw-filer, inte ur
    den inbäddade datan). Idempotent: tar bort (-=) varje värde före += så omkörning
    inte ger dubbletter och match-keywords m.m. bevaras."""
    if not nummer:
        return False
    full_args = []   # bildfiler: XMP + IPTC
    xmp_args = []    # .xmp-sidecar: bara XMP (IPTC-IIM finns inte i sidecar)
    for nr in sorted(nummer, key=lambda n: int(n) if str(n).isdigit() else 0):
        namn = roster.get(str(nr))
        flat = f"{nr} {namn}" if namn else str(nr)
        for v in {str(nr), flat}:   # täcker omkörning med/utan roster
            full_args += [f"-XMP-dc:Subject-={v}", f"-IPTC:Keywords-={v}",
                          f"-XMP-lr:HierarchicalSubject-=Spelare|{v}"]
            xmp_args += [f"-XMP-dc:Subject-={v}",
                         f"-XMP-lr:HierarchicalSubject-=Spelare|{v}"]
        full_args += [f"-XMP-dc:Subject+={flat}", f"-IPTC:Keywords+={flat}",
                      f"-XMP-lr:HierarchicalSubject+=Spelare|{flat}"]
        xmp_args += [f"-XMP-dc:Subject+={flat}",
                     f"-XMP-lr:HierarchicalSubject+=Spelare|{flat}"]

    # Mål: varje bildfil (full) + ev. sidecar för raw-filer (bara XMP).
    mål = [(f, full_args) for f in filer]
    for f in filer:
        if f.suffix.lower() in RAW_SUFFIX:
            sidecar = f.with_suffix(".xmp")
            if sidecar.exists():
                mål.append((sidecar, xmp_args))
    ok = False
    for path, args in mål:
        # Bildfiler: markera IPTC som UTF-8 (annars visas å/ä/ö i namn som skräp).
        # Sidecar (.xmp) har ingen IPTC-IIM → ingen markör behövs.
        charset = ([] if path.suffix.lower() == ".xmp"
                   else ["-charset", "UTF8", "-codedcharacterset=utf8"])
        cmd = (["exiftool", "-overwrite_original", "-sep", ", "]
               + charset + args + [str(path)])
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        ok = ok or r.returncode == 0
    return ok


def kor(katalog, yolo_modell="yolo11m.pt", roster_path="", hemma_farg="",
        claude=False, max_claude=MAX_CLAUDE_STANDARD, min_konf=0.45,
        claude_modell="claude-opus-4-8", logg=print):
    mapp = Path(katalog)
    if not mapp.is_dir():
        logg(f"⚠ Hittar inte mappen: {mapp}")
        return
    grupper = _bilder_per_stam(mapp)
    if not grupper:
        logg("Inga bildfiler i mappen.")
        return
    roster = roster_mod.las_roster(roster_path) if roster_path else {}
    env = _env()
    cache = _ladda_cache()
    logg(f"Läser tröjnummer på {len(grupper)} bilder i {mapp.name}…")

    # 1) Extrahera previews (en per stam) för OCR.
    repr_filer = {stam: _preview_kalla(filer) for stam, filer in grupper.items()}
    previews = extrahera_previews_batch(list(repr_filer.values()), tempfile.mkdtemp())

    # 2) Ladda YOLO + EasyOCR (ingen pose/clip behövs här).
    modeller = ai_lager.ladda_modeller(med_ocr=True, n_pose=1, yolo_modell=yolo_modell)
    if modeller.get("ocr") is None:
        logg("⚠ EasyOCR saknas — kan inte läsa nummer. (pipx inject cull easyocr)")
        return
    import cv2
    yolo = modeller["yolo"]
    device = modeller["device"]

    resultat = {}     # stam -> {"nummer": [...], "n_personer": N, "kalla": ...}
    luckor = []       # stammar: spelare syns men inget nummer (Claude-kandidat)
    n = 0
    for stam, filer in grupper.items():
        n += 1
        jpg = previews.get(repr_filer[stam])
        if jpg is None:
            resultat[stam] = {"nummer": [], "n_personer": 0, "kalla": "—"}
            continue
        img = cv2.imread(str(jpg))
        if img is None:
            resultat[stam] = {"nummer": [], "n_personer": 0, "kalla": "—"}
            continue
        yres = yolo(img, verbose=False, device=device)[0]
        nummer, n_pers = _las_nummer(img, yres, modeller["ocr"], roster, min_konf)
        resultat[stam] = {"nummer": sorted(nummer, key=int),
                          "n_personer": n_pers,
                          "kalla": "ocr" if nummer else "—"}
        cache[_nyckel(filer[0])] = resultat[stam]
        if not nummer and n_pers >= 1:
            luckor.append(stam)
        if n % 5 == 0 or n == len(grupper):
            logg(f"  OCR …{n}/{len(grupper)}")
    _spara_cache(cache)
    träffar = sum(1 for r in resultat.values() if r["nummer"])
    logg(f"  EasyOCR: nummer på {träffar}/{len(grupper)} bilder, "
         f"{len(luckor)} luckor (spelare men inget nummer).")

    # 3) Claude-fallback (opt-in, takbegränsad) på luckorna.
    if claude and luckor:
        from cull import bildtext_ai
        if not bildtext_ai.tillganglig():
            logg("  Claude-fallback: ANTHROPIC_API_KEY/anthropic saknas — hoppar.")
        else:
            kandidater = luckor[:max_claude]
            kostnad = len(kandidater) * KR_PER_CLAUDE
            logg(f"  Claude-fallback på {len(kandidater)} bilder "
                 f"(tak {max_claude}) ≈ {kostnad:.1f} kr…")
            roster_text = roster_mod.lista_text(roster)
            lösta = 0
            for stam in kandidater:
                jpg = previews.get(repr_filer[stam])
                try:
                    nummer = _claude_nummer(jpg, roster_text, hemma_farg, claude_modell)
                except Exception as e:
                    logg(f"  Claude-fel: {type(e).__name__}: {e}")
                    nummer = []
                if nummer:
                    resultat[stam] = {"nummer": sorted(set(nummer), key=int),
                                      "n_personer": resultat[stam]["n_personer"],
                                      "kalla": "claude"}
                    cache[_nyckel(grupper[stam][0])] = resultat[stam]
                    lösta += 1
            _spara_cache(cache)
            logg(f"  Claude löste {lösta}/{len(kandidater)} luckor.")
    elif luckor and not claude:
        logg(f"  Tips: kör med --claude för AI-fallback på {len(luckor)} luckor "
             f"(tak {max_claude} bilder ≈ {max_claude * KR_PER_CLAUDE:.0f} kr).")

    # 4) Skriv keywords + lista kvarvarande osäkra för manuell genomgång.
    skrivna = 0
    osakra = []
    for stam, filer in grupper.items():
        r = resultat[stam]
        if r["nummer"]:
            if _skriv_keywords(filer, r["nummer"], roster, env):
                skrivna += 1
        elif r["n_personer"] >= 1:
            # Spelare syns men inget nummer → manuell genomgång (Steg 2).
            # Kopiera previewn till en beständig mapp (mkdtemp-pathen kan städas bort).
            prev = previews.get(repr_filer[stam])
            kvar = ""
            if prev and Path(prev).exists():
                try:
                    OSAKRA_THUMBS.mkdir(parents=True, exist_ok=True)
                    dst = OSAKRA_THUMBS / f"{stam}.jpg"
                    shutil.copy2(prev, dst)
                    kvar = str(dst)
                except Exception:
                    kvar = str(prev)
            osakra.append({"stam": stam, "fil": str(filer[0]), "preview": kvar})
    try:
        OSAKRA_PATH.parent.mkdir(parents=True, exist_ok=True)
        OSAKRA_PATH.write_text(
            json.dumps({"katalog": str(mapp), "bilder": osakra},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    logg(f"✓ Klart. Keywords skrivna till {skrivna} bilder. "
         f"{len(osakra)} kvar för manuell genomgång.")


def main():
    ap = argparse.ArgumentParser(description="Läs tröjnummer på valda bilder → XMP-keywords.")
    ap.add_argument("katalog", help="mapp med de valda bilderna (urvalet)")
    ap.add_argument("--yolo", default="yolo11m.pt")
    ap.add_argument("--roster", default="", help="roster-CSV (nummer→namn)")
    ap.add_argument("--hemma-farg", default="")
    ap.add_argument("--claude", action="store_true",
                    help="AI-fallback på bilder där OCR inte fick ut nummer (kostar)")
    ap.add_argument("--max-claude", type=int, default=MAX_CLAUDE_STANDARD,
                    help="tak för antal Claude-anrop (kostnadsspärr)")
    ap.add_argument("--min-konf", type=float, default=0.45,
                    help="lägsta OCR-konfidens (0–1) för att lita på ett nummer")
    ap.add_argument("--claude-modell", default="claude-opus-4-8")
    a = ap.parse_args()
    kor(a.katalog, yolo_modell=a.yolo, roster_path=a.roster,
        hemma_farg=a.hemma_farg, claude=a.claude, max_claude=a.max_claude,
        min_konf=a.min_konf, claude_modell=a.claude_modell)


if __name__ == "__main__":
    main()
