"""
Skapar inbränd 9:16 story-JPEG för sport.

Loggor hämtas ur ~/.config/cull/loggor/<normaliserat>.(png|jpg).
Saknas logga → vitt monogram-badge med lagförkortningen.
"""
from pathlib import Path
import re
import subprocess
import tempfile

LOGG_DIR = Path("~/.config/cull/loggor").expanduser()
UT_STORLEK = (1080, 1920)

BLÅ_DJUP  = (12,  68, 124, 215)
BLÅ_LJUS  = (133, 183, 235, 255)
BLÅ_SUB   = (181, 212, 244, 220)
VIT       = (255, 255, 255, 255)
ORANGE    = (232, 130, 12,  255)

MOMENT_ETIKETT = {
    "avspark":  "AVSPARK",
    "paus":     "HALVTID",
    "resultat": "SLUTRESULTAT",
}


def _pil():
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    return Image, ImageDraw, ImageFont, ImageOps


def normera_lag(namn):
    return re.sub(r"[^\w]+", "_", namn.lower()).strip("_")


def tolka_matchinfo(s):
    """
    Parsar matchinfo-strängen till dict med lag_hemma, lag_borta, datum, arena.
    Format: "Hemmalag - Bortalag [ÅÅÅÅMMDD] [Arena]"
    Stödjer även " – " (långt tankstreck) och resultat inbakat (ignoreras).
    """
    out = {"lag_hemma": "", "lag_borta": "", "datum": "", "arena": ""}
    if not s:
        return out
    s = s.strip()

    # Hitta datum (8 siffror = YYYYMMDD)
    datum_m = re.search(r'\b(\d{8})\b', s)
    if datum_m:
        pre              = s[:datum_m.start()].strip()
        out["datum"]     = datum_m.group(1)
        out["arena"]     = s[datum_m.end():].strip()
    else:
        pre = s

    # Dela på " - " eller " – " (första förekomst)
    sep = re.search(r'\s+[–\-]\s+', pre)
    if sep:
        out["lag_hemma"] = pre[:sep.start()].strip()
        borta = pre[sep.end():]
        # Kapa eventuellt resultat (t.ex. "2-1 (0-1)") från bortalagsdelen
        borta = re.sub(r'\s+\d+\s*[-–]\s*\d+.*$', '', borta).strip()
        out["lag_borta"] = borta
    else:
        out["lag_hemma"] = pre.strip()

    return out


def hitta_logga(lag_namn):
    """Slår upp ~/.config/cull/loggor/<normaliserat>.(png|jpg)."""
    if not lag_namn:
        return None
    norm = normera_lag(lag_namn)
    for sfx in (".png", ".jpg", ".jpeg"):
        p = LOGG_DIR / (norm + sfx)
        if p.exists():
            return p
    return None


def saknar_loggor():
    """Returnerar vilka loggor som finns och saknas i biblioteket."""
    LOGG_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in LOGG_DIR.iterdir()
                  if p.suffix.lower() in (".png", ".jpg", ".jpeg"))


def _rund_bricka(logga_path, storlek, monogram):
    Image, ImageDraw, ImageFont, ImageOps = _pil()
    S = storlek
    bricka = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    if logga_path:
        try:
            logo = Image.open(logga_path).convert("RGBA")
            inre = int(S * 0.80)
            logo.thumbnail((inre, inre), Image.LANCZOS)
            ox = (S - logo.width) // 2
            oy = (S - logo.height) // 2
            bricka.paste(logo, (ox, oy), logo)
        except Exception:
            logga_path = None
    if not logga_path:
        d = ImageDraw.Draw(bricka)
        txt = monogram[:4].upper()
        fs = max(10, S // (3 if len(txt) <= 2 else 4))
        fnt = _hitta_typsnitt(fs)
        bbox = d.textbbox((0, 0), txt, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((S - tw) // 2, (S - th) // 2 - bbox[1]),
               txt, font=fnt, fill=(12, 68, 124, 255))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    bricka.putalpha(mask)
    return bricka


def _ladda_foto(bild_path, env=None):
    Image, *_ = _pil()
    p = Path(bild_path)
    if p.suffix.lower() in (".jpg", ".jpeg"):
        return Image.open(p).convert("RGB")
    with tempfile.TemporaryDirectory() as td:
        jpg = Path(td) / (p.stem + ".jpg")
        for tag in ("-JpgFromRaw", "-PreviewImage"):
            try:
                with open(jpg, "wb") as f:
                    subprocess.run(
                        ["exiftool", "-b", tag, str(p)],
                        stdout=f, stderr=subprocess.DEVNULL,
                        timeout=20, env=env,
                    )
            except Exception:
                pass
            if jpg.exists() and jpg.stat().st_size > 10_000:
                return Image.open(jpg).convert("RGB")
    raise RuntimeError(f"Kan inte extrahera preview ur {p.name}")


def _crop_9x16(img):
    W, H = img.size
    mal_h = W * 16 // 9
    if mal_h <= H:
        y0 = (H - mal_h) // 2
        return img.crop((0, y0, W, y0 + mal_h))
    mal_w = H * 9 // 16
    x0 = (W - mal_w) // 2
    return img.crop((x0, 0, x0 + mal_w, H))


def _hitta_typsnitt(storlek):
    from PIL import ImageFont
    for sokv in (
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(sokv, storlek)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_med_skugga(draw, xy, text, font, fill):
    x, y = xy
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=fill)


def _spärrad_bredd(draw, text, font, tracking=0):
    """Total bredd för text ritad med extra teckenmellanrum."""
    if not text:
        return 0
    return sum(draw.textlength(ch, font=font) + tracking for ch in text) - tracking


def _spärrad_text(draw, xy, text, font, fill, tracking=0, skugga=False):
    """Ritar text tecken-för-tecken med tracking (px mellan glyfer)."""
    x, y = xy
    for ch in text:
        if skugga:
            draw.text((x + 1, y + 1), ch, font=font, fill=(0, 0, 0, 150))
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def skapa_story(bild_path, moment, lag_hemma, lag_borta,
                liga="", stallning="", mal_rad="",
                avspark_tid="", arena="", ut_path=None, env=None):
    """
    Renderar en 1080×1920 story-JPEG med inbränd overlay.

    moment:    "avspark" | "paus" | "resultat"
    stallning: "1-0"  (paus/resultat)
    mal_rad:   "Larsson 23', Berg 67'"  (resultat)
    ut_path:   None → <bild-mapp>/Story/story_<moment>.jpg
    Returnerar Path till output-filen.
    """
    Image, ImageDraw, ImageFont, ImageOps = _pil()

    foto = _ladda_foto(bild_path, env)
    foto = _crop_9x16(foto).resize(UT_STORLEK, Image.LANCZOS)
    W, H = foto.size  # 1080 × 1920

    # Diskret liga-logga uppe i högra hörnet (20 % opacitet)
    if liga:
        liga_logga = hitta_logga(liga)
        if liga_logga:
            try:
                ll = Image.open(liga_logga).convert("RGBA")
                mål = int(W * 0.18)
                ll.thumbnail((mål, mål), Image.LANCZOS)
                alfa = ll.split()[3].point(lambda a: int(a * 0.20))
                ll.putalpha(alfa)
                lx = W - ll.width - 34
                ly = 34
                foto_rgba = foto.convert("RGBA")
                foto_rgba.alpha_composite(ll, (max(0, lx), ly))
                foto = foto_rgba.convert("RGB")
            except Exception:
                pass

    canvas = foto.convert("RGBA")
    d = ImageDraw.Draw(canvas)

    # Dalahäst-signatur uppe till vänster (enbart loggan)
    hast_p = Path(__file__).parent / "assets" / "icon_256.png"
    if hast_p.exists():
        try:
            hast = Image.open(hast_p).convert("RGBA")
            hast.thumbnail((62, 62), Image.LANCZOS)
            canvas.paste(hast, (30, 30), hast)
        except Exception:
            pass

    # Flytande blått kort med rundade hörn (lower third)
    BAND_H = 210
    SAFE_BOTTOM = 130       # IG:s svar-fält
    KORT_MARG = 26          # sidmarginal för det flytande kortet
    RADIE = 30
    band_y = H - SAFE_BOTTOM - BAND_H
    kort_x0 = KORT_MARG
    kort_x1 = W - KORT_MARG
    d.rounded_rectangle([(kort_x0, band_y), (kort_x1, band_y + BAND_H)],
                        radius=RADIE, fill=BLÅ_DJUP)

    # Rundade team-loggor – indragna från kortets kanter, närmare mitten
    BRICKA_S = 94
    BRICKA_INDRAG = 40
    by = band_y + (BAND_H - BRICKA_S) // 2
    bricka_h_x = kort_x0 + BRICKA_INDRAG
    bricka_b_x = kort_x1 - BRICKA_INDRAG - BRICKA_S

    mono_h = (lag_hemma[:3] if lag_hemma else "HEM").upper()
    mono_b = (lag_borta[:3] if lag_borta else "BORT").upper()
    bricka_h = _rund_bricka(hitta_logga(lag_hemma), BRICKA_S, mono_h)
    bricka_b = _rund_bricka(hitta_logga(lag_borta), BRICKA_S, mono_b)
    canvas.paste(bricka_h, (bricka_h_x, by), bricka_h)
    canvas.paste(bricka_b, (bricka_b_x, by), bricka_b)

    # Text centrerad mellan brickorna (= bildens mitt, symmetriskt)
    text_x = bricka_h_x + BRICKA_S + 18
    text_w = (bricka_b_x - 18) - text_x
    text_cx = text_x + text_w // 2

    # Etikettrad – spärrad, med klockslag bredvid vid avspark
    etikett = MOMENT_ETIKETT.get(moment, moment.upper())
    if moment == "avspark" and avspark_tid:
        etikett_full = f"{etikett}   {avspark_tid}"
    else:
        etikett_full = etikett
    etik_fnt = _hitta_typsnitt(22)
    TRACK = 5
    ew = _spärrad_bredd(d, etikett_full, etik_fnt, TRACK)
    _spärrad_text(d, (text_cx - ew // 2, band_y + 20),
                  etikett_full, etik_fnt, BLÅ_LJUS, TRACK)

    if moment == "avspark":
        huvud_fnt = _hitta_typsnitt(36)
        huvud_txt = f"{lag_hemma}  –  {lag_borta}"
        bbox = d.textbbox((0, 0), huvud_txt, font=huvud_fnt)
        if bbox[2] - bbox[0] > text_w:
            huvud_txt = f"{mono_h} – {mono_b}"
            bbox = d.textbbox((0, 0), huvud_txt, font=huvud_fnt)
        _text_med_skugga(d, (text_cx - (bbox[2] - bbox[0]) // 2, band_y + 56),
                         huvud_txt, huvud_fnt, VIT)
        # Underrad: liga · arena (klockslaget står nu uppe vid etiketten)
        sub_delar = []
        if liga:
            sub_delar.append(liga)
        if arena:
            sub_delar.append(arena)
        if sub_delar:
            sub_txt = "  ·  ".join(sub_delar)
            sub_fnt = _hitta_typsnitt(21)
            bbox = d.textbbox((0, 0), sub_txt, font=sub_fnt)
            d.text((text_cx - (bbox[2] - bbox[0]) // 2, band_y + 108),
                   sub_txt, font=sub_fnt, fill=BLÅ_SUB)
    else:
        stall_fnt = _hitta_typsnitt(78)
        stall_txt = stallning or "?"
        bbox = d.textbbox((0, 0), stall_txt, font=stall_fnt)
        _text_med_skugga(d, (text_cx - (bbox[2] - bbox[0]) // 2, band_y + 46),
                         stall_txt, stall_fnt, VIT)
        if moment == "resultat" and mal_rad:
            sub_fnt = _hitta_typsnitt(22)
            bbox = d.textbbox((0, 0), mal_rad, font=sub_fnt)
            if bbox[2] - bbox[0] > text_w:
                mal_rad = mal_rad[:40].rsplit(",", 1)[0] + "…"
                bbox = d.textbbox((0, 0), mal_rad, font=sub_fnt)
            d.text((text_cx - (bbox[2] - bbox[0]) // 2, band_y + 158),
                   mal_rad, font=sub_fnt, fill=BLÅ_SUB)

    result = canvas.convert("RGB")

    if ut_path is None:
        ut_dir = Path(bild_path).parent / "Story"
        ut_dir.mkdir(exist_ok=True)
        slug = {"avspark": "avspark", "paus": "halvtid",
                "resultat": "resultat"}.get(moment, moment)
        ut_path = ut_dir / f"story_{slug}.jpg"

    result.save(ut_path, "JPEG", quality=92, optimize=True)
    return Path(ut_path)
