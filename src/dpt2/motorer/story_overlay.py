"""
Skapar Instagram-grafik i Matchgrafik "Horisont"-mallen (v2).

Full-bleed matchfoto + gradient-scrims + Saira-typografi.
Sex tillståndstyper: Avspark, Halvtid, Slutresultat, Startelva, Målgörare, Nästa match.
Tre teman: Hav (#8FD0E8), Sol (#F4C77A), Rosé (#EBB3C4).

Loggor hämtas ur ~/.config/dpt/loggor/<normaliserat>.(png|jpg).
Temaloggor hämtas ur assets/temaloggor/.
Saknas laglogga → vitt monogram-badge med lagförkortningen.
"""
from pathlib import Path
import re
import subprocess
import tempfile

from dpt2.data import sportprofil

# Migrerad till dpt2: app-assets (typsnitt + temaloggor) ligger i dpt2/assets.
ASSETS_DIR  = Path(__file__).parent.parent / "assets"
FONTS_DIR   = ASSETS_DIR / "fonts"
TEMA_LOGG_DIR = ASSETS_DIR / "temaloggor"
# Användarens lagloggor. Överskrivbar modulattribut (datalagret pekar om hit
# när media-hanteringen flyttar in i dpt2). Default = gamla platsen så befintliga
# loggor + migrerade lag.logga-sökvägar fortsätter att lösas ut. TODO Fas 2+:
# flytta logo-lagringen till dpt2 data-dir.
LOGG_DIR    = Path("~/.config/dpt/loggor").expanduser()

CANVAS_W = 1080
# 1080 bred canvas; höjden ger bildförhållandet. story 9:16 · inlägg 4:5 · kvadrat
# 1:1 · FB-landskap 1.91:1 · webb-hero 2:1 / 16:9. Nya format är rena beskärnings-
# mål för Skicka till-kanalerna — overlay-blocken skalar efter höjden som förr.
FORMAT_H  = {"9x16": 1920, "4x5": 1350, "1x1": 1080, "1.91x1": 566,
             "2x1": 540, "16x9": 608}
FORMAT_PREFIX = {"9x16": "story", "4x5": "inlagg", "1x1": "kvadrat",
                 "1.91x1": "fb", "2x1": "hero", "16x9": "hero"}

# Tematabellen: accent + brand-färger (RGBA)
TEMAN = {
    "Hav":  {"accent": (143, 208, 232, 255), "brand": (60,  144, 196, 255)},
    "Sol":  {"accent": (244, 199, 122, 255), "brand": (240, 180,  90, 255)},
    "Rosé": {"accent": (235, 179, 196, 255), "brand": (229, 156, 176, 255)},
}

# Normalisering av moment-strängar → kanoniskt tillståndsnamn
_STATE_MAP = {
    "avspark": "Avspark",
    "paus": "Halvtid", "halvtid": "Halvtid",
    "resultat": "Slutresultat", "slutresultat": "Slutresultat",
    "startelva": "Startelva",
    "malgorare": "Målgörare", "målgörare": "Målgörare",
    "nasta_match": "Nästa match", "nästa_match": "Nästa match", "nästa match": "Nästa match",
}

# Filnamnsslug för ut-filen
_SLUG = {
    "Avspark": "avspark", "Halvtid": "halvtid", "Slutresultat": "resultat",
    "Startelva": "startelva", "Målgörare": "malgorare", "Nästa match": "nastamatch",
}

# Designkonstanter
_VIT       = (255, 255, 255, 255)
_VIT80     = (255, 255, 255, 204)   # rgba(255,255,255,.8)
_VIT70     = (255, 255, 255, 178)   # rgba(255,255,255,.7)
_VIT82     = (255, 255, 255, 209)   # rgba(255,255,255,.82)
_VIT74     = (255, 255, 255, 189)   # rgba(255,255,255,.74)
_SCRIM_TOP = (8,  10, 13)           # topp-scrim-färg
_SCRIM_BOT = (6,   8, 11)           # botten-scrim-färg
_MARGIN    = 60                     # innehållsmarginal (left/right/bottom)
_CONTENT_W = CANVAS_W - 2 * _MARGIN  # 960 px


# ---------------------------------------------------------------------------
# PIL-helpers
# ---------------------------------------------------------------------------

def _pil():
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    return Image, ImageDraw, ImageFont, ImageOps


def _saira(vikt, storlek):
    """Saira (normalbredd) vid given vikt (400/500/600/700) och px-storlek."""
    from PIL import ImageFont
    NAMN = {400: b"Regular", 500: b"Medium", 600: b"SemiBold", 700: b"Bold"}
    p = FONTS_DIR / "Saira-Variable.ttf"
    if p.exists():
        try:
            f = ImageFont.truetype(str(p), storlek)
            if vikt in NAMN:
                f.set_variation_by_name(NAMN[vikt])
            return f
        except Exception:
            pass
    return _hitta_typsnitt(storlek)


def _saira_cond(vikt, storlek):
    """Saira Condensed vid given vikt (500/600/700) och px-storlek."""
    from PIL import ImageFont
    NAMN = {500: "SairaCondensed-Medium.ttf", 600: "SairaCondensed-SemiBold.ttf",
            700: "SairaCondensed-Bold.ttf"}
    p = FONTS_DIR / NAMN.get(vikt, "SairaCondensed-Bold.ttf")
    if p.exists():
        try:
            return ImageFont.truetype(str(p), storlek)
        except Exception:
            pass
    return _hitta_typsnitt(storlek)


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


def _text_h(draw, text, font):
    """Pixelhöjd för texten (bounding box)."""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _text_w(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _spärrad_bredd(draw, text, font, tracking=0):
    if not text:
        return 0
    return sum(draw.textlength(ch, font=font) + tracking for ch in text) - tracking


def _spärrad_text(draw, xy, text, font, fill, tracking=0):
    """Ritar text tecken-för-tecken med tracking (px mellan glyfer)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


# ---------------------------------------------------------------------------
# Lag-loggor & normalisering
# ---------------------------------------------------------------------------

def normera_lag(namn):
    return re.sub(r"[^\w]+", "_", namn.lower()).strip("_")


def hitta_logga(lag_namn):
    """Slår upp ~/.config/dpt/loggor/<normaliserat>.(png|jpg) — den GAMLA
    filsystemkonventionen, kvar som fallback när laget saknar en logga i
    databasen (lag.logga, satt via Lag & tävlingar)."""
    if not lag_namn:
        return None
    norm = normera_lag(lag_namn)
    for sfx in (".png", ".jpg", ".jpeg"):
        p = LOGG_DIR / (norm + sfx)
        if p.exists():
            return p
    return None


def _valj_logga(lag_namn, db_logga=None):
    """DB-loggan (lag.logga, laddas upp under Lag & tävlingar) vinner om den
    finns och pekar på en fil som faktiskt existerar — annars fallback till
    den gamla filsystemkonventionen (hitta_logga)."""
    if db_logga:
        p = Path(db_logga).expanduser()
        if p.exists():
            return p
    return hitta_logga(lag_namn)


def _hitta_tema_logga(tema):
    """Temaloggan (Skagen Hav-loggan) i assets/temaloggor/."""
    filer = {"Hav": "logo-hav.png", "Sol": "logo-sol.png", "Rosé": "logo-rose.png"}
    p = TEMA_LOGG_DIR / filer.get(tema, "logo-hav.png")
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# Mjuk cirkelmask (Horisont: inner 62 %, outer 92 %)
# ---------------------------------------------------------------------------

def _mjuk_cirkelmask(storlek, inner=0.62, outer=0.92):
    """L-mask: full opacitet inom inner·r, linjär utfasning till outer·r."""
    import numpy as np
    from PIL import Image as _Img
    y, x = np.ogrid[:storlek, :storlek]
    c = (storlek - 1) / 2.0
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    alpha = np.clip((outer - r) / (outer - inner), 0.0, 1.0)
    return _Img.fromarray((alpha * 255.0).astype("uint8"), "L")


def _rund_bricka(logga_path, storlek, monogram, fallback_color=(70, 130, 180)):
    """
    Returnerar RGBA-bild (storlek×storlek) med mjuk cirkelmask.
    Logga → cover-crop + mjuk mask.
    Saknas logga → monogram-cirkel med fallback_color.
    """
    import numpy as np
    Image, ImageDraw, ImageFont, ImageOps = _pil()
    S = storlek
    if logga_path:
        try:
            logo = Image.open(logga_path).convert("RGBA")
            # Contain (inte cover): skala ner så hela loggan ryms, centrera på transparent
            logo.thumbnail((S, S), Image.LANCZOS)
            bricka = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            ox = (S - logo.width) // 2
            oy = (S - logo.height) // 2
            bricka.alpha_composite(logo, (ox, oy))
            cirkel = np.asarray(_mjuk_cirkelmask(S), dtype=np.float32) / 255.0
            egen   = np.asarray(bricka.getchannel("A"), dtype=np.float32) / 255.0
            bricka.putalpha(Image.fromarray((cirkel * egen * 255).astype("uint8"), "L"))
            return bricka
        except Exception:
            pass
    # Monogram-fallback
    bricka = Image.new("RGBA", (S, S), fallback_color + (255,))
    d = ImageDraw.Draw(bricka)
    txt = monogram[:4].upper()
    fs  = max(10, S // (3 if len(txt) <= 2 else 4))
    fnt = _saira(700, fs)
    bb  = d.textbbox((0, 0), txt, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - tw) // 2 - bb[0], (S - th) // 2 - bb[1]), txt, font=fnt, fill=_VIT)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    bricka.putalpha(mask)
    return bricka


def _bricka_med_skugga(logga_path, storlek, monogram, fallback_color=(70, 130, 180)):
    """Bricka + drop-shadow (0 2px 6px rgba(0,0,0,.45))."""
    from PIL import ImageFilter
    Image, *_ = _pil()
    bricka = _rund_bricka(logga_path, storlek, monogram, fallback_color)
    pad = 20
    S   = storlek
    # Canvas med utrymme för skugga
    komp = Image.new("RGBA", (S + pad * 2, S + pad * 2 + 4), (0, 0, 0, 0))
    # Skugglager: solid svart i brickans form, förskjutet 2px nedåt
    skugga_lager = Image.new("RGBA", (S + pad * 2, S + pad * 2 + 4), (0, 0, 0, 0))
    svart = Image.new("RGBA", (S, S), (0, 0, 0, 115))
    skugga_lager.paste(svart, (pad, pad + 2), bricka.getchannel("A"))
    skugga_lager = skugga_lager.filter(ImageFilter.GaussianBlur(6))
    komp.alpha_composite(skugga_lager)
    komp.alpha_composite(bricka, (pad, pad))
    return komp, pad   # returnerar (bild, offset som pekar till brickans (0,0))


# ---------------------------------------------------------------------------
# Gradient-scrims (PIL har ingen gradient → numpy)
# ---------------------------------------------------------------------------

def _topp_scrim(canvas_w, h=300):
    """rgba(8,10,13,.62) uppe → 0 nere."""
    import numpy as np
    Image, *_ = _pil()
    alfas = np.linspace(158, 0, h, dtype=np.float32).astype("uint8")
    mask  = Image.fromarray(
        np.tile(alfas[:, np.newaxis], (1, canvas_w)), "L"
    )
    lager = Image.new("RGBA", (canvas_w, h), _SCRIM_TOP + (255,))
    lager.putalpha(mask)
    return lager


def _botten_scrim(canvas_w, frame_h):
    """rgba(6,8,11) gradient nedifrån: 0% 255, 24% 209, 52% 92, 100% 0."""
    import numpy as np
    Image, *_ = _pil()
    scrim_h = int(frame_h * 0.68)
    # stop_p = fraktioner från botten (0=botten, 1=topp); stop_a = alpha vid varje stopp
    stop_p = np.array([0.0, 0.24, 0.52, 1.0])
    stop_a = np.array([255, 209,  92,   0], dtype=np.float32)
    y_idx  = np.arange(scrim_h)
    frac   = (scrim_h - 1 - y_idx) / max(1, scrim_h - 1)   # 1.0 vid y=0, 0 vid botten
    row_a  = np.interp(frac, stop_p, stop_a).astype("uint8")  # interp kräver stigande xp
    mask   = Image.fromarray(
        np.tile(row_a[:, np.newaxis], (1, canvas_w)), "L"
    )
    lager  = Image.new("RGBA", (canvas_w, scrim_h), _SCRIM_BOT + (255,))
    lager.putalpha(mask)
    return lager


# ---------------------------------------------------------------------------
# Hörnmask (för Skagen Hav-logga och liga-logga)
# ---------------------------------------------------------------------------

def _hornmask(w, h, horn="vl", inre=0.18, yttre=0.72):
    """
    Radial gradient-mask från hörnet.
    CSS-referens: radial-gradient(150% 150% at <hörn>, transparent 18%, #000 72%)
    inre/yttre: var övergången från osynlig till fullt synlig sker (andel av
    1.5×w/1.5×h-radien). Lägre inre = synlig närmare själva hörnet.
    """
    import numpy as np
    Image, *_ = _pil()
    y, x = np.ogrid[:h, :w]
    cx, cy = (0, 0) if horn == "vl" else (w, 0)
    rx, ry = 1.5 * w, 1.5 * h
    d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    alpha = np.clip((d - inre) / (yttre - inre), 0.0, 1.0)
    return Image.fromarray((alpha * 255).astype("uint8"), "L")


def _tema_logga_lager(canvas_w, canvas_h, tema):
    """Skagen Hav-logga uppe till vänster, hörnmaskad.

    80 % max-opacitet (höjt från 50 % 2026-07-03 — för svag mot ljusa/röriga
    foton, i praktiken osynlig) + tightare hörnmask (närmare full synlighet,
    inte bara en tunn skymt långt ute i hörnet)."""
    import numpy as np
    Image, *_ = _pil()
    p = _hitta_tema_logga(tema)
    if not p:
        return None
    try:
        logo = Image.open(p).convert("RGBA")
        h_logo = 200
        w_logo = max(1, int(logo.width * h_logo / logo.height))
        logo   = logo.resize((w_logo, h_logo), Image.LANCZOS)
        mask   = _hornmask(w_logo, h_logo, "vl", inre=0.05, yttre=0.5)
        logo_a = __import__("numpy").asarray(logo.getchannel("A"), dtype=np.float32)
        mask_a = __import__("numpy").asarray(mask, dtype=np.float32)
        ny_a   = (logo_a * mask_a / 255.0 * 0.8).astype("uint8")
        logo.putalpha(Image.fromarray(ny_a, "L"))
        lager  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        lager.alpha_composite(logo, (0, 0))
        return lager
    except Exception:
        return None


def _competition_text_lager(canvas_w, canvas_h, competition):
    """Tävlings-/liga-/mästerskapsnamnet, spärrad text uppe till höger — ersätter
    den tidigare liga-loggan (watermark). CSS-referens: top:52px; right:60px;
    max-width:560px; text-align:right; font:600 27px Saira; letter-spacing:.24em;
    color:rgba(255,255,255,.66); text-shadow:0 1px 4px rgba(0,0,0,.55)."""
    if not competition:
        return None
    from PIL import ImageFilter
    Image, ImageDraw, *_ = _pil()
    text    = competition.upper()
    storlek = 27
    max_w   = 560
    right   = 60
    top     = 52

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    tracking = round(0.24 * storlek)
    bredd    = _spärrad_bredd(d0, text, _saira(600, storlek), tracking)
    while bredd > max_w and storlek > 14:
        storlek -= 1
        tracking = round(0.24 * storlek)
        bredd    = _spärrad_bredd(d0, text, _saira(600, storlek), tracking)
    fnt = _saira(600, storlek)
    h   = _text_h(d0, text, fnt)

    pad   = 6
    t_img = Image.new("RGBA", (int(bredd) + pad * 2, h + pad * 2 + 4), (0, 0, 0, 0))
    t_d   = ImageDraw.Draw(t_img)

    # Skugga: 0 1px 4px rgba(0,0,0,.55)
    sh_img = Image.new("RGBA", t_img.size, (0, 0, 0, 0))
    sh_d   = ImageDraw.Draw(sh_img)
    _spärrad_text(sh_d, (pad, pad + 1), text, fnt, (0, 0, 0, 140), tracking)
    sh_img = sh_img.filter(ImageFilter.GaussianBlur(4))
    t_img.alpha_composite(sh_img)

    # Text: vit, 66 % opacity → alpha 168
    _spärrad_text(t_d, (pad, pad), text, fnt, (255, 255, 255, 168), tracking)

    lager = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    x = canvas_w - right - pad - int(bredd)
    y = top - pad
    lager.alpha_composite(t_img, (x, y))
    return lager


# Gren-kant — samma färgspråk som gren-markören på matchkort/matchlista i appen.
_GREN_FARG = {
    "dam": (142, 90, 134, 255),
    "herr": (62, 124, 135, 255),
    "mixed": (110, 135, 87, 255),
}


def _gren_kant_lager(canvas_w, canvas_h, gren):
    """Solid färgremsa längst till vänster (18px @ 1080-bred canvas, full höjd)
    som kodar gren (dam/herr/mixed). Ingen etikett — färgen är hela signalen.
    Okänd/tom gren → ingen remsa."""
    farg = _GREN_FARG.get((gren or "").strip().lower())
    if not farg:
        return None
    Image, *_ = _pil()
    bredd = round(canvas_w * 18 / CANVAS_W)
    lager = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    strip = Image.new("RGBA", (bredd, canvas_h), farg)
    lager.alpha_composite(strip, (0, 0))
    return lager


# ---------------------------------------------------------------------------
# Vertikal URL-text (nere till vänster)
# ---------------------------------------------------------------------------

def _url_text_lager(canvas_w, canvas_h):
    """
    'www.dalecarliaphoto.se' vertikalt, läses nedifrån upp.
    CSS: left:24px; bottom:54px; writing-mode:vertical-rl; rotate(180deg).
    """
    from PIL import ImageFilter
    Image, ImageDraw, *_ = _pil()
    url      = "www.dalecarliaphoto.se"
    fnt      = _saira(500, 16)
    tracking = round(0.22 * 16)   # .22em @ 16px ≈ 4px

    # Mät textdimension
    tmp_img = Image.new("RGBA", (800, 60), (0, 0, 0, 0))
    tmp_d   = ImageDraw.Draw(tmp_img)
    t_w     = int(_spärrad_bredd(tmp_d, url, fnt, tracking))
    t_h     = _text_h(tmp_d, "Ag", fnt)

    # Rita text + skugga på horisontell yta
    pad   = 4
    h_img = Image.new("RGBA", (t_w + pad * 2, t_h + pad * 2 + 2), (0, 0, 0, 0))
    h_d   = ImageDraw.Draw(h_img)

    # Skugga: 0 1px 3px rgba(0,0,0,.55)
    sh_img = Image.new("RGBA", h_img.size, (0, 0, 0, 0))
    sh_d   = ImageDraw.Draw(sh_img)
    _spärrad_text(sh_d, (pad, pad + 1), url, fnt, (0, 0, 0, 140), tracking)
    sh_img = sh_img.filter(ImageFilter.GaussianBlur(3))
    h_img.alpha_composite(sh_img)

    # Text: vit, 70 % opacity → alpha 178
    _spärrad_text(h_d, (pad, pad), url, fnt, (255, 255, 255, 178), tracking)

    # Rotera CW → text läses nedifrån upp
    v_img = h_img.rotate(-90, expand=True)

    # Placera: left=24, bottom-edge=canvas_h-54
    lager = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    x = 24
    y = canvas_h - 54 - v_img.height
    lager.alpha_composite(v_img, (x, y))
    return lager


# ---------------------------------------------------------------------------
# Foto-bakgrund
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Divider-hjälp
# ---------------------------------------------------------------------------

def _divider(draw, x0, y, bredd, alpha=56, tjocklek=3):
    draw.rectangle([x0, y, x0 + bredd - 1, y + tjocklek - 1],
                   fill=(255, 255, 255, alpha))
    return y + tjocklek


# ---------------------------------------------------------------------------
# PREVIEW-block (Avspark / Nästa match)
# ---------------------------------------------------------------------------

def _render_preview(canvas, accent, lag_hemma, lag_borta,
                    bricka_h, bricka_b, competition, big_word, sub_line):
    """Renderar preview-blocket (bottom-anchored)."""
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN   # left = 60px
    BLOCK_W = _CONTENT_W   # 960px

    # — mätfas (dummy draw) —
    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_comp = _saira(600, 28)
    fnt_big  = _saira_cond(700, 150)
    fnt_sub  = _saira(600, 34)
    fnt_team = _saira_cond(600, 46)
    fnt_dash = _saira_cond(600, 38)

    track_comp = 8   # .3em * 28
    track_sub  = 5   # .16em * 34 ≈ 5.4

    # Använd bb[3] (draw_to_bottom) för layout — stora fonter har stor top-offset
    h_comp = d0.textbbox((0, 0), competition.upper(), fnt_comp)[3]
    h_big  = d0.textbbox((0, 0), big_word, fnt_big)[3]
    h_sub  = d0.textbbox((0, 0), sub_line.upper(), fnt_sub)[3]
    BRICKA_S = 84

    # Lag-rad: centrera glyfer med brickan
    bb_ht   = d0.textbbox((0, 0), lag_hemma, fnt_team)
    bb_bt   = d0.textbbox((0, 0), lag_borta, fnt_team)
    bb_dash = d0.textbbox((0, 0), "–", fnt_dash)
    team_ctr = (bb_ht[1] + bb_ht[3]) // 2   # visuell mitt för lagnamn
    bricka_ctr = BRICKA_S // 2               # = 42
    lagtext_dy = bricka_ctr - team_ctr       # offset: rita text vid y+lagtext_dy
    dash_ctr   = (bb_dash[1] + bb_dash[3]) // 2
    dash_dy    = bricka_ctr - dash_ctr

    total_h = (h_comp +
               14 + h_big +
               18 + h_sub +
               34 + 3 + 34 +   # margin + divider + margin
               BRICKA_S)

    y = H - _MARGIN - total_h

    # Skapa ritlager ovanpå canvas
    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Tävlings-etikett
    _spärrad_text(d, (L, y), competition.upper(), fnt_comp, accent, track_comp)
    y += h_comp + 14

    # 2. Stort ord (AVSPARK / NÄSTA MATCH)
    _spärrad_text(d, (L, y), big_word, fnt_big, _VIT, 0)
    y += h_big + 18

    # 3. Underrad
    _spärrad_text(d, (L, y), sub_line.upper(), fnt_sub, _VIT80, track_sub)
    y += h_sub + 34

    # 4. Divider
    y = _divider(d, L, y, BLOCK_W, alpha=56)
    y += 34

    # 5. Lag-rad (flex, justify-content:center, gap:26)
    w_ht   = int(d.textlength(lag_hemma, font=fnt_team))
    w_bt   = int(d.textlength(lag_borta, font=fnt_team))
    w_dash = int(d.textlength("–", font=fnt_dash))
    row_w  = BRICKA_S + 26 + w_ht + 26 + w_dash + 26 + w_bt + 26 + BRICKA_S
    rx     = L + (BLOCK_W - row_w) // 2

    lager.alpha_composite(bricka_h, (rx, y))
    rx += BRICKA_S + 26

    _spärrad_text(d, (rx, y + lagtext_dy), lag_hemma, fnt_team, _VIT, 0)
    rx += w_ht + 26

    ac_85 = accent[:3] + (int(accent[3] * 0.85),)
    d.text((rx, y + dash_dy), "–", font=fnt_dash, fill=ac_85)
    rx += w_dash + 26

    _spärrad_text(d, (rx, y + lagtext_dy), lag_borta, fnt_team, _VIT, 0)
    rx += w_bt + 26

    lager.alpha_composite(bricka_b, (rx, y))

    canvas.alpha_composite(lager)


# ---------------------------------------------------------------------------
# SCORE-block (Halvtid / Slutresultat)
# ---------------------------------------------------------------------------

def _render_score(canvas, accent, lag_hemma, lag_borta,
                  bricka_h, bricka_b, score_label, score_text, score_sub):
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_lbl   = _saira(600, 30)
    fnt_score = _saira_cond(700, 220)
    fnt_sub   = _saira(600, 30)
    BRICKA_S  = 128
    track_lbl = 9   # .3em * 30

    # bb[3] = draw_to_bottom (siffertoppens offset ingår i fonten)
    bb_lbl  = d0.textbbox((0, 0), score_label.upper(), fnt_lbl)
    bb_score = d0.textbbox((0, 0), score_text, fnt_score)
    bb_sub  = d0.textbbox((0, 0), score_sub, fnt_sub)

    # Centrera bricka med scoretextens visuella mitt
    score_glyph_ctr = (bb_score[1] + bb_score[3]) // 2
    by_crest = max(0, score_glyph_ctr - BRICKA_S // 2)
    h_row = max(bb_score[3], by_crest + BRICKA_S)

    total_h = bb_lbl[3] + 30 + h_row + 40 + 3 + 28 + bb_sub[3]

    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Etikett (centrerad)
    w_lbl = int(_spärrad_bredd(d, score_label.upper(), fnt_lbl, track_lbl))
    _spärrad_text(d, (L + (BLOCK_W - w_lbl) // 2, y),
                  score_label.upper(), fnt_lbl, accent, track_lbl)
    y += bb_lbl[3] + 30

    # 2. Resultat-rad: hemma-bricka + score + borta-bricka (centrerat)
    w_score = int(d.textlength(score_text, font=fnt_score))
    row_w   = BRICKA_S + 46 + w_score + 46 + BRICKA_S
    rx = L + (BLOCK_W - row_w) // 2
    lager.alpha_composite(bricka_h, (rx, y + by_crest))
    rx += BRICKA_S + 46

    d.text((rx, y), score_text, font=fnt_score, fill=_VIT)
    rx += w_score + 46

    lager.alpha_composite(bricka_b, (rx, y + by_crest))
    y += h_row + 40

    # 3. Divider 78 % bred, centrerad
    div_w = int(BLOCK_W * 0.78)
    y = _divider(d, L + (BLOCK_W - div_w) // 2, y, div_w, alpha=56)
    y += 28

    # 4. Underrad (centrerad)
    track_sub = 2   # .05em * 30 ≈ 1.5
    w_sub = int(_spärrad_bredd(d, score_sub, fnt_sub, track_sub))
    _spärrad_text(d, (L + (BLOCK_W - w_sub) // 2, y),
                  score_sub, fnt_sub, _VIT82, track_sub)
    # (y inte uppdaterad — sista elementet)

    canvas.alpha_composite(lager)


# ---------------------------------------------------------------------------
# STARTELVA-block
# ---------------------------------------------------------------------------

def _render_startelva(canvas, accent, lag_hemma,
                      competition, venue, startelva_rader):
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_lbl  = _saira(600, 30)
    fnt_lag  = _saira_cond(700, 96)
    fnt_sub  = _saira(600, 28)
    fnt_num  = _saira_cond(700, 30)
    fnt_namn = _saira_cond(600, 34)
    track_lbl = 9
    track_sub = 4   # .16em * 28 ≈ 4.5

    sub_line = f"{competition} · {venue}".upper()
    spelare  = [s.strip() for s in re.split(r'\n|,', startelva_rader) if s.strip()][:22]

    # draw_to_bottom (bb[3]) för korrekt layout med stora fonter
    h_lbl  = d0.textbbox((0, 0), "STARTELVA", fnt_lbl)[3]
    h_lag  = d0.textbbox((0, 0), lag_hemma or "Lag", fnt_lag)[3]
    h_sub  = d0.textbbox((0, 0), sub_line or "–", fnt_sub)[3]
    h_rad  = d0.textbbox((0, 0), "Ag", fnt_namn)[3] + 14  # rad + padding-bottom
    n_rows = (len(spelare) + 1) // 2
    h_grid = n_rows * h_rad + max(0, n_rows - 1) * 20

    total_h = h_lbl + 10 + h_lag + 8 + h_sub + 30 + 3 + 30 + h_grid

    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Etikett
    _spärrad_text(d, (L, y), "STARTELVA", fnt_lbl, accent, track_lbl)
    y += h_lbl + 10   # h_lbl = bb[3] = draw_to_bottom

    # 2. Lagnamn
    _spärrad_text(d, (L, y), lag_hemma, fnt_lag, _VIT, 0)
    y += h_lag + 8    # h_lag = bb[3]

    # 3. Underrad
    _spärrad_text(d, (L, y), sub_line, fnt_sub, _VIT70, track_sub)
    y += h_sub + 30   # h_sub = bb[3]

    # 4. Divider
    y = _divider(d, L, y, BLOCK_W, alpha=51)
    y += 30

    # 5. Spelargrid: 2 kolumner
    col_w = (BLOCK_W - 56) // 2   # 452 px
    for i, namn in enumerate(spelare):
        col = i % 2
        row = i // 2
        x = L + col * (col_w + 56)
        ry = y + row * (h_rad + 20)
        num_str = str(i + 1)
        # Nummer (accent, min-width 42px)
        d.text((x, ry), num_str, font=fnt_num, fill=accent)
        # Namn
        nx = x + 42 + 20
        d.text((nx, ry), namn, font=fnt_namn, fill=_VIT)
        # Separator-linje
        ly = ry + h_rad - 3
        if ly < H:
            d.rectangle([x, ly, x + col_w - 1, ly], fill=(255, 255, 255, 31))

    canvas.alpha_composite(lager)


# ---------------------------------------------------------------------------
# MÅLGÖRARE-block
# ---------------------------------------------------------------------------

def _render_malgorare(canvas, accent, lag_hemma, lag_borta,
                      score_text, malgorare_rader):
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_lbl    = _saira(600, 30)
    fnt_score  = _saira_cond(700, 130)
    fnt_lagrad = _saira_cond(600, 34)
    fnt_mal    = _saira_cond(600, 40)
    track_lbl  = 9

    rader = [r.strip() for r in re.split(r'\n|·', malgorare_rader) if r.strip()]

    bb_lbl   = d0.textbbox((0, 0), "MÅLGÖRARE", fnt_lbl)
    bb_score = d0.textbbox((0, 0), score_text, fnt_score)
    bb_lagrad= d0.textbbox((0, 0), f"{lag_hemma} – {lag_borta}", fnt_lagrad)
    h_mal    = d0.textbbox((0, 0), "Ag", fnt_mal)[3]
    h_lista  = len(rader) * h_mal + max(0, len(rader) - 1) * 18

    # Rubrikrad höjd = max av siffra och lagnamn (baseline-alignment)
    # Lagrad baseline-alignas med scorens botten: offset = bb_score[3] - bb_lagrad[3]
    lagrad_dy = bb_score[3] - bb_lagrad[3]
    h_rubrik  = max(bb_score[3], lagrad_dy + bb_lagrad[3])

    total_h = bb_lbl[3] + 14 + h_rubrik + 30 + 3 + 30 + h_lista

    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Etikett
    _spärrad_text(d, (L, y), "MÅLGÖRARE", fnt_lbl, accent, track_lbl)
    y += bb_lbl[3] + 14

    # 2. Rubrikrad: stor siffra + lag-namn (baseline-align)
    d.text((L, y), score_text, font=fnt_score, fill=_VIT)
    w_score = int(d.textlength(score_text, font=fnt_score))
    lagrad  = f"{lag_hemma} – {lag_borta}"
    d.text((L + w_score + 28, y + lagrad_dy), lagrad, font=fnt_lagrad, fill=_VIT74)
    y += h_rubrik + 30

    # 3. Divider
    y = _divider(d, L, y, BLOCK_W, alpha=51)
    y += 30

    # 4. Lista
    for rad in rader:
        # Prick (18×18, accent)
        pr = 9   # radie
        cx, cy = L + pr, y + h_mal // 2
        d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=accent)
        # Text
        d.text((L + 18 + 24, y), rad, font=fnt_mal, fill=_VIT)
        y += h_mal + 18

    canvas.alpha_composite(lager)


# ---------------------------------------------------------------------------
# Huvud-funktion
# ---------------------------------------------------------------------------

def skapa_story(bild_path, moment, lag_hemma, lag_borta,
                liga="", stallning="", mal_rad="",
                avspark_tid="", arena="", next_when="",
                startelva=None, sport="",
                tema="Hav", gren="", hem_logga=None, borta_logga=None,
                ut_path=None, ut_mapp=None,
                format="9x16", fokus=None, zoom=1.0, env=None):
    """
    Renderar en JPEG med Horisont-overlay.

    moment: "avspark"|"halvtid"|"paus"|"resultat"|"slutresultat"
            |"startelva"|"malgorare"|"nasta_match" (eller svenska varianter)
    tema:   "Hav"|"Sol"|"Rosé"
    gren:   "dam"|"herr"|"mixed" (eller tomt) — färgad kant längst till vänster,
            samma källa som gren-markören på matchkort/matchlista i appen.
    sport:  "fotboll"|"handboll"|"innebandy"|"volleyboll"|"beachvolley"|"tennis"
            (eller tomt → fotboll) — styr bara Halvtid/Slutresultat-etiketterna
            (data/sportprofil.py mid_label/res_label), aldrig blockens layout.
    hem_logga/borta_logga: sökväg till lagets uppladdade logga (lag.logga i
        databasen). Saknas den → fallback till hitta_logga()s gamla
        filsystemkonvention, sist ett vitt monogram-badge.
    format: "9x16" (1080×1920) | "4x5" (1080×1350)
    stallning: "1-0" (paus/resultat/malgorare)
    mal_rad: "Larsson 23', Berg 67'" (resultat/malgorare) — för set-sporter
        (sportprofil.has_scorers=False) är detta istället mellanresultatet
        (set-/period-/gamesiffror), ifyllt av story_korning._matchfalt.
    startelva: sträng med namn (\n- eller kommaseparerade) eller None
    next_when: "Lör 14 jun · 16:00" (för Nästa match)
    Returnerar Path till output-filen.
    """
    Image, ImageDraw, ImageFont, ImageOps = _pil()
    profil = sportprofil.profil(sport)

    # Normera tillståndsnamn
    state = _STATE_MAP.get(moment.lower().replace(" ", "_"), moment)

    # Tema-tokens
    tema_data = TEMAN.get(tema, TEMAN["Hav"])
    accent    = tema_data["accent"]

    # Canvas-storlek
    frame_h = FORMAT_H.get(format, FORMAT_H["9x16"])
    W, H    = CANVAS_W, frame_h

    # 1. Bakgrundsfoto (cover-crop med fokuspunkt + zoom)
    #    fokus={"x","y"} i procent (0–100) = var beskärningsrutan centreras;
    #    zoom≥1 krymper rutan (skalar upp motivet) med fokuspunkten som origo.
    #    Rutan behåller alltid målformatets bildförhållande (W/H) så resize
    #    aldrig förvränger. Default (fokus mitten, zoom 1) = gamla center-croppen.
    foto = _ladda_foto(bild_path, env)
    foto_w, foto_h = foto.size
    fx = min(1.0, max(0.0, (fokus or {}).get("x", 50) / 100.0)) if fokus else 0.5
    fy = min(1.0, max(0.0, (fokus or {}).get("y", 50) / 100.0)) if fokus else 0.5
    z  = max(1.0, float(zoom or 1.0))
    if foto_w * H >= foto_h * W:                 # foto bredare än målformatet
        ny_w = (foto_h * W / H) / z
        ny_h = foto_h / z
    else:                                        # foto smalare/högre
        ny_w = foto_w / z
        ny_h = (foto_w * H / W) / z
    ny_w = max(1, min(foto_w, int(round(ny_w))))
    ny_h = max(1, min(foto_h, int(round(ny_h))))
    x0 = max(0, min(foto_w - ny_w, int(round(fx * (foto_w - ny_w)))))
    y0 = max(0, min(foto_h - ny_h, int(round(fy * (foto_h - ny_h)))))
    foto = foto.crop((x0, y0, x0 + ny_w, y0 + ny_h))
    foto = foto.resize((W, H), Image.LANCZOS)

    canvas = foto.convert("RGBA")

    # 2. Topp-scrim
    canvas.alpha_composite(_topp_scrim(W))

    # 3. Skagen Hav-temalogga (uppe vänster)
    lager = _tema_logga_lager(W, H, tema)
    if lager:
        canvas.alpha_composite(lager)

    # 4. Tävlingsnamn, text uppe höger (ersätter tidigare liga-logga/watermark)
    competition = liga or "Damallsvenskan"
    lager = _competition_text_lager(W, H, competition)
    if lager:
        canvas.alpha_composite(lager)

    # 5. Botten-scrim
    scrim_h = int(H * 0.68)
    bot_scrim = _botten_scrim(W, H)
    canvas.alpha_composite(bot_scrim, (0, H - scrim_h))

    # 6. Innehållsblock
    isPreview  = state in ("Avspark", "Nästa match")
    isScore    = state in ("Halvtid", "Slutresultat")
    isLineup   = state == "Startelva"
    isScorers  = state == "Målgörare"

    # Härled visade texter (speglar renderVals() i HTML-referensen)
    venue_up    = arena.upper() if arena else ""
    big_word    = "AVSPARK" if state == "Avspark" else "NÄSTA\nMATCH"
    if state == "Nästa match":
        sub_line = f"{next_when} · {venue_up}" if next_when else venue_up
        big_word = "NÄSTA MATCH"
    else:
        sub_line = f"{avspark_tid} · {venue_up}" if avspark_tid else venue_up

    # Halvtid/Slutresultat — etikett styrs av sportprofilen (fotboll:
    # "Halvtid"/"Slutresultat" oförändrat, andra sporter: t.ex.
    # "Periodsiffror"/"Resultat i set").
    score_label = profil["mid_label"] if state == "Halvtid" else profil["res_label"]
    # SairaCondensed-Bold saknar space-glyf — rendera utan mellanslag
    if stallning and "-" in stallning:
        delar = stallning.split("-", 1)
        score_text = f"{delar[0].strip()}–{delar[1].strip()}"
    else:
        score_text = stallning or "?–?"
    score_sub = mal_rad if state == "Slutresultat" else competition

    # Lagbrickor
    mono_h = (lag_hemma[:3] if lag_hemma else "HEM").upper()
    mono_b = (lag_borta[:3] if lag_borta else "BORT").upper()

    if isPreview:
        bricka_h, pad_h = _bricka_med_skugga(_valj_logga(lag_hemma, hem_logga), 84, mono_h)
        bricka_b, pad_b = _bricka_med_skugga(_valj_logga(lag_borta, borta_logga), 84, mono_b)
        # Crop bort skugg-padding för att använda ren bricka vid placering
        bricka_h_ren = bricka_h.crop((pad_h, pad_h, pad_h + 84, pad_h + 84))
        bricka_b_ren = bricka_b.crop((pad_b, pad_b, pad_b + 84, pad_b + 84))
        _render_preview(canvas, accent,
                        lag_hemma or "", lag_borta or "",
                        bricka_h_ren, bricka_b_ren,
                        competition, big_word, sub_line)

    elif isScore:
        bricka_h, pad_h = _bricka_med_skugga(_valj_logga(lag_hemma, hem_logga), 128, mono_h)
        bricka_b, pad_b = _bricka_med_skugga(_valj_logga(lag_borta, borta_logga), 128, mono_b)
        bricka_h_ren = bricka_h.crop((pad_h, pad_h, pad_h + 128, pad_h + 128))
        bricka_b_ren = bricka_b.crop((pad_b, pad_b, pad_b + 128, pad_b + 128))
        _render_score(canvas, accent,
                      lag_hemma or "", lag_borta or "",
                      bricka_h_ren, bricka_b_ren,
                      score_label, score_text, score_sub)

    elif isLineup:
        sv_text = startelva or ""
        _render_startelva(canvas, accent, lag_hemma or "",
                          competition, arena or "", sv_text)

    elif isScorers:
        _render_malgorare(canvas, accent,
                          lag_hemma or "", lag_borta or "",
                          score_text, mal_rad or "")

    # 7. Vertikal URL-text
    canvas.alpha_composite(_url_text_lager(W, H))

    # 8. Gren-kant (vänster, full höjd) — sist/överst, ovanpå allt annat.
    lager = _gren_kant_lager(W, H, gren)
    if lager:
        canvas.alpha_composite(lager)

    # Exportera JPEG
    result = canvas.convert("RGB")
    slug = _SLUG.get(state, "story")

    if ut_path is None:
        if ut_mapp:
            ut_dir = Path(ut_mapp).expanduser()
        else:
            ut_dir = Path(bild_path).parent / "Story"
        ut_dir.mkdir(parents=True, exist_ok=True)
        prefix = FORMAT_PREFIX.get(format, "story")
        ut_path = ut_dir / f"{prefix}_{slug}.jpg"

    result.save(ut_path, "JPEG", quality=92, optimize=True)
    return Path(ut_path)


# ---------------------------------------------------------------------------
# Hjälp-funktion för GUI
# ---------------------------------------------------------------------------

def hitta_logga_namn():
    """Lista befintliga loggor i ~/.config/dpt/loggor/."""
    LOGG_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in LOGG_DIR.iterdir()
                  if p.suffix.lower() in (".png", ".jpg", ".jpeg"))


def tolka_matchinfo(s):
    """
    Parsar matchinfo-strängen → dict: lag_hemma, lag_borta, datum, arena, tid.
    Format: "Hemmalag - Bortalag [ÅÅÅÅMMDD] [Arena]"
    """
    out = {"lag_hemma": "", "lag_borta": "", "datum": "", "arena": "", "tid": ""}
    if not s:
        return out
    s = s.strip()
    datum_m = re.search(r'\b(\d{8})\b', s)
    if datum_m:
        pre          = s[:datum_m.start()].strip()
        out["datum"] = datum_m.group(1)
        out["arena"] = s[datum_m.end():].strip()
    else:
        pre = s

    tid_m = re.search(r'\b([012]?\d)[:.]([0-5]\d)\b', out["arena"])
    if tid_m:
        out["tid"]   = f"{int(tid_m.group(1)):02d}:{tid_m.group(2)}"
        out["arena"] = (out["arena"][:tid_m.start()]
                        + out["arena"][tid_m.end():]).strip(" ·-–").strip()

    sep = re.search(r'\s+[–\-]\s+', pre)
    if sep:
        out["lag_hemma"] = pre[:sep.start()].strip()
        borta = pre[sep.end():]
        borta = re.sub(r'\s+\d+\s*[-–]\s*\d+.*$', '', borta).strip()
        out["lag_borta"] = borta
    else:
        out["lag_hemma"] = pre.strip()

    prefix = re.compile(r'^\([A-Za-zÅÄÖåäö0-9]{1,4}\)\s*')
    out["lag_hemma"] = prefix.sub("", out["lag_hemma"]).strip()
    out["lag_borta"] = prefix.sub("", out["lag_borta"]).strip()
    return out
