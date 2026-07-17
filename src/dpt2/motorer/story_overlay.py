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
    # P15: tennisens "Set klart" delar mellanställnings-läget (Halvtid-staten);
    # Tiebreak är ett eget läge — gamesiffrorna i pågående set är stora siffran.
    "set_klart": "Halvtid",
    "tiebreak": "Tiebreak",
    "resultat": "Slutresultat", "slutresultat": "Slutresultat",
    "startelva": "Startelva",
    "malgorare": "Målgörare", "målgörare": "Målgörare",
    "nasta_match": "Nästa match", "nästa_match": "Nästa match", "nästa match": "Nästa match",
}

# Filnamnsslug för ut-filen
_SLUG = {
    "Avspark": "avspark", "Halvtid": "halvtid", "Slutresultat": "resultat",
    "Startelva": "startelva", "Målgörare": "malgorare", "Nästa match": "nastamatch",
    "Tiebreak": "tiebreak",
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


def monogram_text(namn, fallback, individ=False):
    """Monogrammet i fallback-brickan (när logga saknas). Lagsport: lagnamnets
    3 första bokstäver ("Malmö FF" → "MAL"). Individ-sport (tennis, friidrott):
    "lagen" är personer — per-ord-initialer ("Rebecca Peterson" → "RP")."""
    if not namn:
        return fallback
    if individ:
        init = "".join(o[0] for o in namn.split() if o)[:3]
        return (init or namn[:3]).upper()
    return namn[:3].upper()


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
    """Skagen Hav-märket uppe till vänster.

    A2 (2026-07-13): indraget från gren-kanten — vänsterkant = 18px gren-kant +
    ~58px luft (x = 76px @ 1080), top = 44px, höjd = 132px. Ren logga (ingen
    hörnmask längre) med mjuk drop-shadow (0 3px 10px rgba(0,0,0,.55)) och
    85 % opacitet. Speglar prototypen `Matchgrafik Horisont.dc.html`."""
    import numpy as np
    from PIL import ImageFilter
    Image, *_ = _pil()
    p = _hitta_tema_logga(tema)
    if not p:
        return None
    try:
        # Skala mot canvas-bredden så 132px @ 1080 håller i alla format.
        skala  = canvas_w / CANVAS_W
        h_logo = max(1, round(132 * skala))
        x0     = round(76 * skala)
        y0     = round(44 * skala)
        logo = Image.open(p).convert("RGBA")
        w_logo = max(1, int(logo.width * h_logo / logo.height))
        logo   = logo.resize((w_logo, h_logo), Image.LANCZOS)
        # 85 % opacitet
        logo_a = (__import__("numpy").asarray(logo.getchannel("A"),
                  dtype=np.float32) * 0.85).astype("uint8")
        logo.putalpha(Image.fromarray(logo_a, "L"))

        lager = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        # Drop-shadow: 0 3px 10px rgba(0,0,0,.55)
        blur   = max(1, round(10 * skala))
        dy     = max(1, round(3 * skala))
        sh_src = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        sh_a   = Image.new("L", logo.size, 0)
        sh_a.paste(logo.getchannel("A"), (0, 0))
        black  = Image.new("RGBA", logo.size, (0, 0, 0, 140))
        black.putalpha(sh_a)
        sh_src.alpha_composite(black, (x0, y0 + dy))
        sh_src = sh_src.filter(ImageFilter.GaussianBlur(blur))
        lager.alpha_composite(sh_src)
        lager.alpha_composite(logo, (x0, y0))
        return lager
    except Exception:
        return None


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

    # Heldagsevent (p.5): ingen motståndare → eventnamnet är rubriken (big_word),
    # ingen tankstreck-vs-rad. Rubriken kan bli lång → auto-krymp så den ryms.
    is_event = not (lag_borta or "").strip()
    if is_event:
        langst = max(big_word.split("\n"), key=len) if big_word else ""
        big_size = 150
        while big_size > 60 and d0.textlength(langst, font=fnt_big) > BLOCK_W:
            big_size -= 6
            fnt_big = _saira_cond(700, big_size)

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

    total_h = h_comp + 14 + h_big + 18 + h_sub
    if not is_event:                     # + divider + lag-rad (bara riktiga matcher)
        total_h += 34 + 3 + 34 + BRICKA_S

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

    # 4+5. Divider + lag-rad ritas bara för RIKTIGA matcher. Heldagsevent (p.5)
    #      har ingen motståndare — eventnamnet står redan som rubrik (big_word),
    #      så vs-raden (bricka – bricka) hoppas över helt.
    if not is_event:
        # Divider
        y = _divider(d, L, y, BLOCK_W, alpha=56)
        y += 34
        # Lag-rad (flex, justify-content:center, gap:26)
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
# INDIVID-block (D1 tennis-handoffen) — spelare i stället för lag+brickor.
# Facit: design/HANDOFF-D1-SVAR + Horisont Tennis D1.dc.html. Inga klubbmärkes-
# cirklar i något individ-tillstånd; land är spärrad underrad per spelare.
# ---------------------------------------------------------------------------

def _spärrad_bredd(d0, text, font, tracking):
    """Bredden av _spärrad_text (glyfbredder + tracking mellan tecken)."""
    if not text:
        return 0
    w = sum(d0.textlength(ch, font=font) for ch in text)
    return int(w + tracking * max(0, len(text) - 1))


def _turnering_topphoger(canvas, text):
    """Turneringsnamnet som spärrad text uppe till höger (D1) — samma plats/
    stil som liga-namnet i fotbollens HTML-referens: 600 27px Saira, .24em,
    vitt 66 %, högerställt vid W-60, y=52. Tomt → raden utgår (anropas ej)."""
    Image, ImageDraw, *_ = _pil()
    W, _H = canvas.size
    lager = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)
    fnt = _saira(600, 27)
    track = 6   # .24em * 27 ≈ 6.5
    t = text.upper()
    w = _spärrad_bredd(d, t, fnt, track)
    x = W - _MARGIN - w
    # Enkel textskugga (facit: 0 1px 4px) — offsetkopia räcker i JPEG-skala.
    _spärrad_text(d, (x, 53), t, fnt, (0, 0, 0, 140), track)
    _spärrad_text(d, (x, 52), t, fnt, (255, 255, 255, 168), track)
    canvas.alpha_composite(lager)


def _render_preview_individ(canvas, accent, spelare_a, spelare_b, land_a, land_b,
                            etikett, big_word, sub_line):
    """PREVIEW för individ-sporter: accent-etikett (moment/turnering), stort ord
    (rond eller moment), underrad tid · plats, avdelare, namnrad utan brickor —
    spelarnamn med land som spärrad underrad, accentfärgat '–' emellan."""
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_et   = _saira(600, 28)
    fnt_big  = _saira_cond(700, 150)
    fnt_sub  = _saira(600, 34)
    fnt_name = _saira_cond(600, 52)
    fnt_land = _saira(600, 21)
    fnt_dash = _saira_cond(600, 40)
    track_et, track_sub, track_land = 8, 5, 5   # .3em·28 / .16em·34 / .24em·21

    # Lång rond/moment → auto-krymp (samma skydd som event-rubriken).
    big_size = 150
    while big_size > 60 and d0.textlength(big_word, font=fnt_big) > BLOCK_W:
        big_size -= 6
        fnt_big = _saira_cond(700, big_size)

    h_et  = d0.textbbox((0, 0), etikett.upper(), fnt_et)[3] if etikett else 0
    h_big = d0.textbbox((0, 0), big_word, fnt_big)[3]
    h_sub = d0.textbbox((0, 0), sub_line.upper(), fnt_sub)[3]
    bb_na = d0.textbbox((0, 0), spelare_a or "", fnt_name)
    bb_nb = d0.textbbox((0, 0), spelare_b or "", fnt_name)
    bb_da = d0.textbbox((0, 0), "–", fnt_dash)
    h_name = max(bb_na[3], bb_nb[3])
    h_land = d0.textbbox((0, 0), "X", fnt_land)[3] if (land_a or land_b) else 0
    rad_h  = h_name + (8 + h_land if h_land else 0)

    total_h = (h_et + 14 if etikett else 0) + h_big + 18 + h_sub + 34 + 3 + 34 + rad_h
    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Etikett (momentet när rond är stora ordet; annars turneringen)
    if etikett:
        _spärrad_text(d, (L, y), etikett.upper(), fnt_et, accent, track_et)
        y += h_et + 14
    # 2. Stort ord (rond eller moment)
    _spärrad_text(d, (L, y), big_word, fnt_big, _VIT, 0)
    y += h_big + 18
    # 3. Underrad (tid · plats)
    _spärrad_text(d, (L, y), sub_line.upper(), fnt_sub, _VIT80, track_sub)
    y += h_sub + 34
    # 4. Avdelare
    y = _divider(d, L, y, BLOCK_W, alpha=56)
    y += 34
    # 5. Namnrad — centrerad, namn baseline-linjerade med accentfärgat '–'.
    GAP = 34
    w_na = int(d.textlength(spelare_a or "", font=fnt_name))
    w_nb = int(d.textlength(spelare_b or "", font=fnt_name))
    la, lb = (land_a or "").upper(), (land_b or "").upper()
    w_la = _spärrad_bredd(d0, la, fnt_land, track_land)
    w_lb = _spärrad_bredd(d0, lb, fnt_land, track_land)
    kol_a = max(w_na, w_la)
    kol_b = max(w_nb, w_lb)
    w_dash = int(d.textlength("–", font=fnt_dash))
    row_w  = kol_a + GAP + w_dash + GAP + kol_b
    rx = L + (BLOCK_W - row_w) // 2

    # Kolumn A: namn centrerat över land
    d.text((rx + (kol_a - w_na) // 2, y), spelare_a or "", font=fnt_name, fill=_VIT)
    if la:
        _spärrad_text(d, (rx + (kol_a - w_la) // 2, y + h_name + 8),
                      la, fnt_land, (255, 255, 255, 148), track_land)
    rx += kol_a + GAP
    # '–' centrerad mot namnens visuella mitt (samma teknik som lagraden)
    ac_85 = accent[:3] + (int(accent[3] * 0.85),)
    namn_ctr = (bb_na[1] + bb_na[3]) // 2
    dash_ctr = (bb_da[1] + bb_da[3]) // 2
    d.text((rx, y + namn_ctr - dash_ctr), "–", font=fnt_dash, fill=ac_85)
    rx += w_dash + GAP
    # Kolumn B
    d.text((rx + (kol_b - w_nb) // 2, y), spelare_b or "", font=fnt_name, fill=_VIT)
    if lb:
        _spärrad_text(d, (rx + (kol_b - w_lb) // 2, y + h_name + 8),
                      lb, fnt_land, (255, 255, 255, 148), track_land)

    canvas.alpha_composite(lager)


def _render_score_individ(canvas, accent, spelare_a, spelare_b,
                          score_label, set_a, set_b, games, avgjord):
    """SCORE för individ-sporter (centrerad): etikett (t.ex. "RESULTAT I SET ·
    SEMIFINAL"), stor set-siffra med tunna mellanrum, namnrad (vinnare i accent
    när avgjord), avdelare 78 %, gamesiffror under. Inga brickor."""
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_lbl   = _saira(600, 30)
    fnt_score = _saira_cond(700, 220)
    fnt_name  = _saira_cond(600, 48)
    fnt_dash  = _saira_cond(600, 38)
    fnt_games = _saira_cond(600, 38)
    track_lbl, track_games = 9, 3   # .3em·30 / .08em·38

    # Set-siffran ritas i tre delar (SairaCondensed-Bold saknar space-glyf →
    # facit-mallens U+2009-mellanrum blir manuella 20px-gap i stället).
    THIN = 20
    w_sa = int(d0.textlength(str(set_a), font=fnt_score))
    w_sd = int(d0.textlength("–", font=fnt_score))
    w_sb = int(d0.textlength(str(set_b), font=fnt_score))
    w_score = w_sa + THIN + w_sd + THIN + w_sb
    h_score = d0.textbbox((0, 0), f"{set_a}–{set_b}", fnt_score)[3]

    h_lbl = d0.textbbox((0, 0), score_label.upper(), fnt_lbl)[3] if score_label else 0
    bb_na = d0.textbbox((0, 0), spelare_a or "", fnt_name)
    bb_nb = d0.textbbox((0, 0), spelare_b or "", fnt_name)
    h_name = max(bb_na[3], bb_nb[3])
    h_games = d0.textbbox((0, 0), games, fnt_games)[3] if games else 0

    total_h = ((h_lbl + 24 if score_label else 0) + h_score + 14 + h_name
               + (36 + 3 + 26 + h_games if games else 0))
    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    # 1. Etikett
    if score_label:
        t = score_label.upper()
        w = _spärrad_bredd(d0, t, fnt_lbl, track_lbl)
        _spärrad_text(d, (L + (BLOCK_W - w) // 2, y), t, fnt_lbl, accent, track_lbl)
        y += h_lbl + 24
    # 2. Set-siffran (tre delar med manuella tunna gap)
    sx = L + (BLOCK_W - w_score) // 2
    d.text((sx, y), str(set_a), font=fnt_score, fill=_VIT); sx += w_sa + THIN
    d.text((sx, y), "–", font=fnt_score, fill=_VIT);        sx += w_sd + THIN
    d.text((sx, y), str(set_b), font=fnt_score, fill=_VIT)
    y += h_score + 14
    # 3. Namnrad — vinnaren i accent, förloraren dämpad (bara när avgjord).
    vit_dim = (255, 255, 255, 153)   # rgba(255,255,255,.6)
    if avgjord == "a":
        farg_a, farg_b = accent, vit_dim
    elif avgjord == "b":
        farg_a, farg_b = vit_dim, accent
    else:
        farg_a = farg_b = _VIT
    GAP = 22
    w_na = int(d.textlength(spelare_a or "", font=fnt_name))
    w_nb = int(d.textlength(spelare_b or "", font=fnt_name))
    w_dash = int(d.textlength("–", font=fnt_dash))
    bb_da = d0.textbbox((0, 0), "–", fnt_dash)
    row_w = w_na + GAP + w_dash + GAP + w_nb
    rx = L + (BLOCK_W - row_w) // 2
    namn_ctr = (bb_na[1] + bb_na[3]) // 2
    dash_ctr = (bb_da[1] + bb_da[3]) // 2
    d.text((rx, y), spelare_a or "", font=fnt_name, fill=farg_a); rx += w_na + GAP
    d.text((rx, y + namn_ctr - dash_ctr), "–", font=fnt_dash,
           fill=(255, 255, 255, 128)); rx += w_dash + GAP
    d.text((rx, y), spelare_b or "", font=fnt_name, fill=farg_b)
    y += h_name
    # 4. Avdelare (78 % centrerad) + gamesiffror
    if games:
        y += 36
        div_w = int(BLOCK_W * 0.78)
        y = _divider(d, L + (BLOCK_W - div_w) // 2, y, div_w, alpha=56)
        y += 26
        w_g = _spärrad_bredd(d0, games, fnt_games, track_games)
        _spärrad_text(d, (L + (BLOCK_W - w_g) // 2, y), games, fnt_games,
                      (255, 255, 255, 217), track_games)

    canvas.alpha_composite(lager)


# ---------------------------------------------------------------------------
# FRIIDROTT (D2-handoffen) — Start / Resultat / Placering.
# Facit: design/HANDOFF-D2-SVAR + Horisont Friidrott D2.dc.html. En idrottare
# + ett resultat; eventnamnet uppe till höger; gren-kanten som alltid.
# ---------------------------------------------------------------------------

# Medaljfärger (D2): Guld #D9B24C · Silver #C7CDD4 · Brons #C08A5A. 4+ = vit.
MEDALJ_FARG = {1: (217, 178, 76, 255), 2: (199, 205, 212, 255),
               3: (192, 138, 90, 255)}
_DISCIPLIN_ENHET = {"hoppkast": "m", "mangkamp": "p"}


def friidrott_stort_ord_storlek(text):
    """Grennamnets fontstorlek — D2: ≤9 tecken 150px · 10–13 118px · >13 96px,
    alltid en rad."""
    n = len(text or "")
    return 150 if n <= 9 else (118 if n <= 13 else 96)


def ordinal_text(placering):
    """Svensk ordinal för placering: 1:a, 2:a, 3:e … 21:a (11/12 → :e)."""
    try:
        n = int(placering)
    except (TypeError, ValueError):
        return ""
    return ":a" if n % 10 in (1, 2) and n % 100 not in (11, 12) else ":e"


def formattera_serie(serie):
    """Hoppserien som D2-sträng: '6,21 · 6,42 · × · 6,38' — övertramp (x/X)
    blir tecknet ×. Tar rå inmatning separerad med mellanslag/·/;/komma —
    men komma direkt följt av siffra är DECIMALKOMMA (6,42), inte separator."""
    delar = [d.strip(", ") for d in
             re.split(r"[·;]+|\s+|,(?!\d)", serie or "") if d.strip(", ")]
    return " · ".join("×" if d.lower() == "x" else d for d in delar)


def resultat_enhet(grentyp):
    """Dämpad enhet efter stora siffran: hopp/kast 'm', mångkamp 'p' — tid
    (sprint/medel) och placering saknar enhet."""
    return _DISCIPLIN_ENHET.get(grentyp or "", "")


def _fri_namnrad(d, d0, lager_w, y, namn, klubb, fnt_namn, fnt_klubb,
                 x0, block_w):
    """Namn (centrerat) + klubb som spärrad underrad. Returnerar ny y."""
    track_klubb = 5   # .24em * 21
    w_n = int(d.textlength(namn or "", font=fnt_namn))
    h_n = d0.textbbox((0, 0), namn or "X", fnt_namn)[3]
    d.text((x0 + (block_w - w_n) // 2, y), namn or "", font=fnt_namn, fill=_VIT)
    y += h_n
    if klubb:
        k = klubb.upper()
        w_k = _spärrad_bredd(d0, k, fnt_klubb, track_klubb)
        _spärrad_text(d, (x0 + (block_w - w_k) // 2, y + 8), k, fnt_klubb,
                      (255, 255, 255, 148), track_klubb)
        y += 8 + d0.textbbox((0, 0), "X", fnt_klubb)[3]
    return y


def _render_friidrott_preview(canvas, accent, etikett, stort_ord, sub_line,
                              idrottare):
    """START: etikett ("START · KVAL") över grennamnet (stort ord ensamt),
    underrad tid · plats, avdelare, 1–3 idrottare som namnkolumner."""
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_et   = _saira(600, 28)
    fnt_big  = _saira_cond(700, friidrott_stort_ord_storlek(stort_ord))
    fnt_sub  = _saira(600, 34)
    fnt_namn = _saira_cond(600, 52)
    fnt_klubb = _saira(600, 21)
    track_et, track_sub, track_klubb = 8, 5, 5

    pers = [p for p in (idrottare or []) if (p.get("namn") or "").strip()][:3]

    h_et  = d0.textbbox((0, 0), etikett.upper(), fnt_et)[3] if etikett else 0
    h_big = d0.textbbox((0, 0), stort_ord.upper(), fnt_big)[3]
    h_sub = d0.textbbox((0, 0), sub_line.upper(), fnt_sub)[3] if sub_line else 0
    h_namn = d0.textbbox((0, 0), "X", fnt_namn)[3]
    h_klubb = d0.textbbox((0, 0), "X", fnt_klubb)[3]
    har_klubb = any(p.get("klubb") for p in pers)
    rad_h = h_namn + (8 + h_klubb if har_klubb else 0) if pers else 0

    total_h = ((h_et + 14 if etikett else 0) + h_big
               + (18 + h_sub if sub_line else 0)
               + (34 + 3 + 34 + rad_h if pers else 0))
    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    if etikett:
        _spärrad_text(d, (L, y), etikett.upper(), fnt_et, accent, track_et)
        y += h_et + 14
    _spärrad_text(d, (L, y), stort_ord.upper(), fnt_big, _VIT, 0)
    y += h_big
    if sub_line:
        y += 18
        _spärrad_text(d, (L, y), sub_line.upper(), fnt_sub, _VIT80, track_sub)
        y += h_sub
    if pers:
        y += 34
        y = _divider(d, L, y, BLOCK_W, alpha=56)
        y += 34
        # 1–3 namnkolumner, gap 26 — kolumnbredd = max(namn, klubb).
        GAP = 26
        kol = []
        for p in pers:
            w_n = int(d.textlength(p["namn"], font=fnt_namn))
            w_k = _spärrad_bredd(d0, (p.get("klubb") or "").upper(),
                                 fnt_klubb, track_klubb)
            kol.append(max(w_n, w_k))
        row_w = sum(kol) + GAP * (len(pers) - 1)
        rx = L + (BLOCK_W - row_w) // 2
        for p, kw in zip(pers, kol):
            _fri_namnrad(d, d0, W, y, p["namn"], p.get("klubb") or "",
                         fnt_namn, fnt_klubb, rx, kw)
            rx += kw + GAP

    canvas.alpha_composite(lager)


def _render_friidrott_score(canvas, accent, etikett, tal, tal_farg, suffix,
                            suffix_fnt, suffix_farg, namn, klubb, under_rad):
    """Gemensamt RESULTAT/PLACERING-block (centrerat): etikett, stor siffra
    med ev. baseline-linjerat suffix (enhet/ordinal), namn + klubb, ev.
    avdelare + underrad (serie eller resultat)."""
    Image, ImageDraw, *_ = _pil()
    W, H = canvas.size
    L = _MARGIN
    BLOCK_W = _CONTENT_W

    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0  = ImageDraw.Draw(tmp)
    fnt_lbl   = _saira(600, 30)
    fnt_tal   = _saira_cond(700, 220)
    fnt_namn  = _saira_cond(600, 48)
    fnt_klubb = _saira(600, 21)
    fnt_under = _saira_cond(600, 38)
    track_lbl, track_under = 9, 3
    SUF_GAP = 16 if suffix_fnt and suffix_fnt.size >= 80 else 6

    h_lbl = d0.textbbox((0, 0), etikett.upper(), fnt_lbl)[3] if etikett else 0
    bb_tal = d0.textbbox((0, 0), tal, fnt_tal)
    w_tal, h_tal = int(d0.textlength(tal, font=fnt_tal)), bb_tal[3]
    w_suf = int(d0.textlength(suffix, font=suffix_fnt)) if suffix else 0
    h_namn = d0.textbbox((0, 0), "X", fnt_namn)[3] if namn else 0
    h_klubb = d0.textbbox((0, 0), "X", fnt_klubb)[3]
    h_under = d0.textbbox((0, 0), under_rad, fnt_under)[3] if under_rad else 0

    namn_h = (h_namn + (8 + h_klubb if klubb else 0)) if namn else 0
    total_h = ((h_lbl + 24 if etikett else 0) + h_tal
               + (14 + namn_h if namn else 0)
               + (36 + 3 + 26 + h_under if under_rad else 0))
    y = H - _MARGIN - total_h

    lager = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    if etikett:
        t = etikett.upper()
        w = _spärrad_bredd(d0, t, fnt_lbl, track_lbl)
        _spärrad_text(d, (L + (BLOCK_W - w) // 2, y), t, fnt_lbl, accent, track_lbl)
        y += h_lbl + 24
    # Stor siffra + baseline-linjerat suffix (enhet 80px gap 16 / ordinal 90px gap 6)
    grupp_w = w_tal + (SUF_GAP + w_suf if suffix else 0)
    sx = L + (BLOCK_W - grupp_w) // 2
    d.text((sx, y), tal, font=fnt_tal, fill=tal_farg)
    if suffix:
        h_suf = d0.textbbox((0, 0), suffix, suffix_fnt)[3]
        d.text((sx + w_tal + SUF_GAP, y + h_tal - h_suf), suffix,
               font=suffix_fnt, fill=suffix_farg)
    y += h_tal
    if namn:
        y += 14
        _fri_namnrad(d, d0, W, y, namn, klubb, fnt_namn, fnt_klubb, L, BLOCK_W)
        y += namn_h
    if under_rad:
        y += 36
        div_w = int(BLOCK_W * 0.78)
        y = _divider(d, L + (BLOCK_W - div_w) // 2, y, div_w, alpha=56)
        y += 26
        w_u = _spärrad_bredd(d0, under_rad, fnt_under, track_under)
        _spärrad_text(d, (L + (BLOCK_W - w_u) // 2, y), under_rad, fnt_under,
                      (255, 255, 255, 217), track_under)

    canvas.alpha_composite(lager)


def skapa_friidrott_story(bild_path, tillstand, *, gren_namn, grentyp="hoppkast",
                          moment="", event="", idrottare=None,
                          namn="", klubb="", resultat="", serie="",
                          placering="", start_when="", venue="",
                          tema="Hav", gren="", format="9x16",
                          fokus=None, zoom=1.0, env=None,
                          ut_path=None, ut_mapp=None):
    """Friidrotts-story (D2): tillstand = "start" | "resultat" | "placering".

    gren_namn: "Längd", "100 m" — stort ord i start, del av etiketten annars.
    grentyp:   sprint|medel|hoppkast|mangkamp — styr enhet (m/p) + serie.
    event:     "Friidrotts-SM 2026" — spärrad text uppe till höger.
    idrottare: [{namn, klubb}] 1–3 st (start-tillståndet).
    namn/klubb: idrottaren i resultat/placering.
    placering: heltal (1 → "1:a" i guld) eller "DNF"/"DNS"/"DQ" (dämpat ord).
    serie:     hoppserie (bara hoppkast) — formatteras till '6,21 · × · 6,42'.
    """
    Image, ImageDraw, ImageFont, ImageOps = _pil()
    tema_data = TEMAN.get(tema, TEMAN["Hav"])
    accent = tema_data["accent"]
    frame_h = FORMAT_H.get(format, FORMAT_H["9x16"])
    W, H = CANVAS_W, frame_h

    foto = _cover_crop(_ladda_foto(bild_path, env), W, H, fokus, zoom, Image)
    canvas = foto.convert("RGBA")
    canvas.alpha_composite(_topp_scrim(W))
    lager = _tema_logga_lager(W, H, tema)
    if lager:
        canvas.alpha_composite(lager)
    if event:
        _turnering_topphoger(canvas, event)
    canvas.alpha_composite(_botten_scrim(W, H), (0, H - int(H * 0.68)))

    mom = (moment or "").strip()
    if tillstand == "start":
        etikett = f"Start · {mom}" if mom else "Start"
        sub = " · ".join(x for x in ((start_when or "").strip(),
                                     (venue or "").strip()) if x)
        _render_friidrott_preview(canvas, accent, etikett,
                                  (gren_namn or "").strip(), sub,
                                  idrottare or [])
    else:
        grendel = f"{gren_namn} — {mom}" if mom else (gren_namn or "")
        if tillstand == "placering":
            etikett = f"Placering · {grendel}" if grendel else "Placering"
            p = str(placering or "").strip()
            if p.upper() in ("DNF", "DNS", "DQ"):
                # Dämpat stort ord — ingen ordinal/medalj/resultatrad (D2 §5).
                _render_friidrott_score(canvas, accent, etikett, p.upper(),
                                        (255, 255, 255, 153), "", None, None,
                                        namn, klubb, "")
            else:
                farg = MEDALJ_FARG.get(int(p) if p.isdigit() else 0, _VIT)
                suf_farg = farg[:3] + (int(farg[3] * 0.75),)
                enh = resultat_enhet(grentyp)
                under = f"{resultat} {enh}".strip() if resultat else ""
                _render_friidrott_score(canvas, accent, etikett, p, farg,
                                        ordinal_text(p), _saira_cond(600, 90),
                                        suf_farg, namn, klubb, under)
        else:
            etikett = f"Resultat · {grendel}" if grendel else "Resultat"
            enh = resultat_enhet(grentyp)
            under = formattera_serie(serie) if grentyp == "hoppkast" else ""
            _render_friidrott_score(canvas, accent, etikett,
                                    (resultat or "").strip(), _VIT,
                                    enh, _saira_cond(600, 80) if enh else None,
                                    (255, 255, 255, 140), namn, klubb, under)

    kant = _gren_kant_lager(W, H, gren)
    if kant:
        canvas.alpha_composite(kant)

    result = canvas.convert("RGB")
    if ut_path is None:
        ut_dir = (Path(ut_mapp).expanduser() if ut_mapp
                  else Path(bild_path).parent / "Story")
        ut_dir.mkdir(parents=True, exist_ok=True)
        prefix = FORMAT_PREFIX.get(format, "story")
        ut_path = ut_dir / f"{prefix}_friidrott_{tillstand}.jpg"
    result.save(ut_path, "JPEG", quality=92, optimize=True)
    return Path(ut_path)


# ---------------------------------------------------------------------------
# A4 · Målskyttelistan under Slutresultatet — dynamisk layout
# ---------------------------------------------------------------------------
# Tre layouter (speglar Tweaks-proppen `scorersLayout` i prototypen):
#   'rad'     — en balanserad textrad (auto-krymp 30→26→23 efter antal), radbryts
#               på skytte-gränser om den inte ryms i _SCORERS_MAXW.
#   'chips'   — pill per skytt (accentprick), greedy radbrytning, centrerade rader.
#   'spalter' — två spalter (grid) när >3 skyttar.
# 'auto' (renderarens default): en rad så länge den ryms i ~940px, annars chips.
# Skyttar separeras på '·'/radbrytning (komma kan ingå i EN skytt, t.ex.
# "Fornes 50', 58', 80'") — därför splittas ALDRIG på komma.

_SCORERS_MAXW = 940


def _scorer_units(mal_rad):
    return [s.strip() for s in re.split(r'\n|·', mal_rad or "") if s.strip()]


def _wrap_units(d0, units, fnt, track, max_w):
    """Radbryter skyttar (join ' · ') så varje rad ryms i max_w."""
    sep, lines, cur = " · ", [], ""
    for u in units:
        cand = u if not cur else cur + sep + u
        if cur and _spärrad_bredd(d0, cand, fnt, track) > max_w:
            lines.append(cur)
            cur = u
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def _scorers_plan(d0, units, layout, max_w=_SCORERS_MAXW):
    """Väljer layout + mäter höjden. Returnerar en plan-dict med 'mode'+'h'."""
    n = len(units)
    row_size = 23 if n > 6 else 26 if n > 4 else 30
    fnt_row  = _saira(600, row_size)
    track    = 1
    one_line = " · ".join(units)
    line_w   = _spärrad_bredd(d0, one_line, fnt_row, track) if units else 0

    want = layout or "auto"
    if want == "auto":
        want = "rad" if (units and line_w <= max_w) else ("chips" if units else "rad")

    if want == "rad":
        lines = _wrap_units(d0, units, fnt_row, track, max_w) if units else [""]
        lh    = int(row_size * 1.4)
        return {"mode": "rad", "fnt": fnt_row, "track": track,
                "lines": lines, "lh": lh, "h": len(lines) * lh}

    if want == "spalter":
        col_size = 30 if n > 8 else 34 if n > 4 else 40
        fnt   = _saira_cond(600, col_size)
        cols  = 2 if n > 3 else 1
        rows  = (n + cols - 1) // cols
        h_rad = _text_h(d0, "Ag", fnt)
        gap_y = 16
        return {"mode": "spalter", "fnt": fnt, "cols": cols, "units": units,
                "h_rad": h_rad, "gap_y": gap_y,
                "h": rows * h_rad + max(0, rows - 1) * gap_y}

    # chips
    chip_size = 27 if n > 6 else 31
    fnt = _saira_cond(600, chip_size)
    dot, gap_dot, pad_x, pad_y, gap_x, gap_y = 11, 13, 26, 10, 14, 16
    chip_h = _text_h(d0, "Ag", fnt) + pad_y * 2
    chips  = [(u, pad_x * 2 + dot + gap_dot + int(d0.textlength(u, font=fnt)))
              for u in units]
    rows, cur, cur_w = [], [], 0
    for c in chips:
        add = c[1] + (gap_x if cur else 0)
        if cur and cur_w + add > max_w:
            rows.append(cur)
            cur, cur_w = [c], c[1]
        else:
            cur.append(c)
            cur_w += add
    if cur:
        rows.append(cur)
    return {"mode": "chips", "fnt": fnt, "rows": rows, "chip_h": chip_h,
            "dot": dot, "gap_dot": gap_dot, "pad_x": pad_x, "gap_x": gap_x,
            "gap_y": gap_y,
            "h": len(rows) * chip_h + max(0, len(rows) - 1) * gap_y}


def _draw_scorers(d, plan, accent, cx, y):
    """Ritar sub-blocket centrerat kring x=cx med toppen vid y."""
    mode = plan["mode"]
    if mode == "rad":
        fnt, track, lh = plan["fnt"], plan["track"], plan["lh"]
        for line in plan["lines"]:
            w = int(_spärrad_bredd(d, line, fnt, track))
            _spärrad_text(d, (cx - w // 2, y), line, fnt, _VIT82, track)
            y += lh
        return

    if mode == "chips":
        fnt, chip_h = plan["fnt"], plan["chip_h"]
        dot, gap_dot, pad_x = plan["dot"], plan["gap_dot"], plan["pad_x"]
        gap_x, gap_y = plan["gap_x"], plan["gap_y"]
        h_txt = _text_h(d, "Ag", fnt)
        for row in plan["rows"]:
            row_w = sum(cw for _, cw in row) + (len(row) - 1) * gap_x
            x = cx - row_w // 2
            for u, cw in row:
                d.rounded_rectangle([x, y, x + cw, y + chip_h],
                                    radius=chip_h // 2,
                                    outline=(255, 255, 255, 66), width=2)
                cyc = y + chip_h // 2
                dx  = x + pad_x
                d.ellipse([dx, cyc - dot // 2, dx + dot, cyc + dot // 2],
                          fill=accent)
                d.text((dx + dot + gap_dot, y + (chip_h - h_txt) // 2), u,
                       font=fnt, fill=_VIT)
                x += cw + gap_x
            y += chip_h + gap_y
        return

    # spalter
    fnt, cols, units = plan["fnt"], plan["cols"], plan["units"]
    h_rad, gap_y = plan["h_rad"], plan["gap_y"]
    dot, gap, gap_x = 13, 18, 60
    col_w = max((dot + gap + int(d.textlength(u, font=fnt)) for u in units),
                default=0)
    total_w = cols * col_w + (cols - 1) * gap_x
    x0 = cx - total_w // 2
    for i, u in enumerate(units):
        x  = x0 + (i % cols) * (col_w + gap_x)
        ry = y + (i // cols) * (h_rad + gap_y)
        cyc = ry + h_rad // 2
        d.ellipse([x, cyc - dot // 2, x + dot, cyc + dot // 2], fill=accent)
        d.text((x + dot + gap, ry), u, font=fnt, fill=_VIT)


# ---------------------------------------------------------------------------
# SCORE-block (Halvtid / Slutresultat)
# ---------------------------------------------------------------------------

def _render_score(canvas, accent, lag_hemma, lag_borta,
                  bricka_h, bricka_b, score_label, score_text, score_sub,
                  scorers=None, scorers_layout="auto"):
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

    # A4: Slutresultatet visar målskyttelistan i vald/auto-layout (rad/chips/
    # spalter). Halvtid (scorers=None) behåller den enkla centrerade underraden.
    units = scorers or []
    plan  = _scorers_plan(d0, units, scorers_layout) if units else None
    sub_h = plan["h"] if plan else bb_sub[3]

    # Centrera bricka med scoretextens visuella mitt
    score_glyph_ctr = (bb_score[1] + bb_score[3]) // 2
    by_crest = max(0, score_glyph_ctr - BRICKA_S // 2)
    h_row = max(bb_score[3], by_crest + BRICKA_S)

    total_h = bb_lbl[3] + 30 + h_row + 40 + 3 + 28 + sub_h

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

    # 4. Underrad — Slutresultat: målskyttelistan (A4-layout); Halvtid: en
    #    centrerad textrad (score_sub = tävlingsnamnet).
    if plan:
        _draw_scorers(d, plan, accent, L + BLOCK_W // 2, y)
    else:
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
# Cover-beskärning (delas av skapa_story + beskar_foto)
# ---------------------------------------------------------------------------

def _cover_crop(foto, W, H, fokus, zoom, Image=None):
    """Cover-beskär `foto` till W×H med fokuspunkt (rutans MITT, i procent) +
    zoom (≥1 krymper rutan / skalar upp motivet). Rutan behåller alltid W/H så
    resize aldrig förvränger; klampad mot kanterna. fokus None/mitten + zoom 1 =
    vanlig center-crop. Samma modell som ram-overlayen i UI:ts crop-editor."""
    if Image is None:
        Image, _d, _f, _o = _pil()
    foto_w, foto_h = foto.size
    fx = min(1.0, max(0.0, (fokus or {}).get("x", 50) / 100.0)) if fokus else 0.5
    fy = min(1.0, max(0.0, (fokus or {}).get("y", 50) / 100.0)) if fokus else 0.5
    z = max(1.0, float(zoom or 1.0))
    if foto_w * H >= foto_h * W:                 # foto bredare än målformatet
        ny_w = (foto_h * W / H) / z
        ny_h = foto_h / z
    else:                                        # foto smalare/högre
        ny_w = foto_w / z
        ny_h = (foto_w * H / W) / z
    ny_w = max(1, min(foto_w, int(round(ny_w))))
    ny_h = max(1, min(foto_h, int(round(ny_h))))
    x0 = max(0, min(foto_w - ny_w, int(round(fx * foto_w - ny_w / 2))))
    y0 = max(0, min(foto_h - ny_h, int(round(fy * foto_h - ny_h / 2))))
    return foto.crop((x0, y0, x0 + ny_w, y0 + ny_h)).resize((W, H), Image.LANCZOS)


def beskar_foto(bild_path, format="1x1", fokus=None, zoom=1.0,
                ut_path=None, ut_mapp=None, env=None):
    """Beskär ETT foto till FORMAT (fokus+zoom) UTAN overlay — för karusell-/
    extra-bilder i Matchpublicering (IG upp till 9, FB upp till 3 efter omslaget).
    Returnerar Path till den sparade JPEG:en."""
    Image, _d, _f, _o = _pil()
    frame_h = FORMAT_H.get(format, FORMAT_H["9x16"])
    foto = _cover_crop(_ladda_foto(bild_path, env), CANVAS_W, frame_h,
                       fokus, zoom, Image).convert("RGB")
    if ut_path:
        ut = Path(ut_path)
    else:
        ut = Path(ut_mapp or (Path.home() / ".config" / "dpt2" / "stories")) \
            / f"beskuren_{FORMAT_PREFIX.get(format, 'bild')}.jpg"
    ut.parent.mkdir(parents=True, exist_ok=True)
    foto.save(ut, "JPEG", quality=92)
    return ut


# ---------------------------------------------------------------------------
# Huvud-funktion
# ---------------------------------------------------------------------------

def skapa_story(bild_path, moment, lag_hemma, lag_borta,
                liga="", stallning="", mal_rad="",
                avspark_tid="", arena="", next_when="",
                startelva=None, sport="",
                tema="Hav", gren="", hem_logga=None, borta_logga=None,
                ut_path=None, ut_mapp=None,
                format="9x16", fokus=None, zoom=1.0, env=None,
                overlay=True, scorers_layout="auto",
                rond="", land_hemma="", land_borta=""):
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
    overlay: False → ren beskuren bild utan Horisont-grafik (iOS-klienten kan
        begära det via story-anropet). Default True.
    scorers_layout: "auto"|"rad"|"chips"|"spalter" — hur målskyttelistan ritas
        under Slutresultatet (A4). "auto" = en rad om den ryms i ~940px, annars
        chips.
    rond: turneringsrond ("Semifinal") — individ-sporter (D1): stora ordet i
        preview, del av score-etiketten. Tom = fallbacks, inget hål.
    land_hemma/land_borta: spelarens land (lag.klubb) — individ-sporter (D1):
        spärrad underrad per spelare i preview. Tom = raden utgår.
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

    # 1. Bakgrundsfoto (cover-crop med fokuspunkt + zoom, se _cover_crop)
    foto = _cover_crop(_ladda_foto(bild_path, env), W, H, fokus, zoom, Image)

    canvas = foto.convert("RGBA")

    # overlay=False (iOS-klienten kan begära det): ren beskuren bild utan
    # Horisont-grafik — hoppa över alla lager, exportera bara fotot.
    if overlay:
        # 2. Topp-scrim
        canvas.alpha_composite(_topp_scrim(W))

        # 3. Skagen Hav-temalogga (uppe vänster, indragen — A2)
        lager = _tema_logga_lager(W, H, tema)
        if lager:
            canvas.alpha_composite(lager)

        # 4. (A3) Liga-/tävlingstexten uppe till höger är BORTTAGEN ur
        #    renderaren (medvetet beslut från skarp användning). `competition`
        #    lever kvar för blockens egna underrader (Avspark/Startelva/
        #    Halvtid), inte som watermark.
        # Ingen liga → ingen tävlingsrad (tidigare hårdkodad "Damallsvenskan"-
        # default läckte in på turnerings-/eventposter utan liga).
        competition = liga or ""

        # 5. Botten-scrim
        scrim_h = int(H * 0.68)
        bot_scrim = _botten_scrim(W, H)
        canvas.alpha_composite(bot_scrim, (0, H - scrim_h))

        # 6. Innehållsblock
        isPreview  = state in ("Avspark", "Nästa match")
        isScore    = state in ("Halvtid", "Slutresultat", "Tiebreak")
        isLineup   = state == "Startelva"
        isScorers  = state == "Målgörare"

        # Härled visade texter (speglar renderVals() i HTML-referensen).
        # Startmomentets stora ord kommer ur sportprofilen: fotboll "Avspark"
        # (oförändrat), tennis/beachvolley "Matchstart", friidrott "Start".
        venue_up    = arena.upper() if arena else ""
        big_word    = (profil.get("start_moment") or "Avspark").upper() \
            if state == "Avspark" else "NÄSTA\nMATCH"
        if state == "Nästa match":
            sub_line = f"{next_when} · {venue_up}" if next_when else venue_up
            big_word = "NÄSTA MATCH"
        else:
            sub_line = f"{avspark_tid} · {venue_up}" if avspark_tid else venue_up
        # p.5: heldagsevent (ingen motståndare) → eventnamnet ÄR rubriken, inte
        # "NÄSTA MATCH"/"AVSPARK" (som antyder en kommande match).
        if isPreview and not (lag_borta or "").strip():
            big_word = (lag_hemma or "EVENT").upper()

        # Halvtid/Slutresultat — etikett styrs av sportprofilen (fotboll:
        # "Halvtid"/"Slutresultat" oförändrat, andra sporter: t.ex.
        # "Periodsiffror"/"Resultat i set"). P15: mellanställningens
        # overlay-etikett kan skilja sig från formulärfältets (tennis: stora
        # siffran är SETSTÄLLNINGEN → "Setsiffror", medan fältet man fyller i
        # heter "Gamesiffror") — mid_overlay_label vinner när den finns.
        if state == "Halvtid":
            score_label = profil.get("mid_overlay_label") or profil["mid_label"]
        elif state == "Tiebreak":
            score_label = "Tiebreak"
        else:
            score_label = profil["res_label"]
        # SairaCondensed-Bold saknar space-glyf — rendera utan mellanslag
        if stallning and "-" in stallning:
            delar = stallning.split("-", 1)
            score_text = f"{delar[0].strip()}–{delar[1].strip()}"
        else:
            score_text = stallning or "?–?"
        score_sub = mal_rad if state == "Slutresultat" else competition
        # A4: målskyttar bara i Slutresultat (Halvtid = enkel underrad).
        slut_scorers = _scorer_units(mal_rad) if state == "Slutresultat" else None

        # D1: individ-sporter (tennis) har egna preview/score-block — spelare i
        # stället för lag+brickor, rond som stort ord, turnering uppe höger.
        # Heldagsevent (turnerings-SoMe, ingen "motståndare") tar dock p.5-vägen
        # även för individ-sporter: eventnamnet är rubriken.
        individ = bool(profil.get("individ")) and (lag_borta or "").strip()
        rond_ren = (rond or "").strip()

        if individ and liga:
            _turnering_topphoger(canvas, liga)

        # Lagbrickor (monogram_text: individ-sport → personinitialer "RP",
        # lagsport → förkortning "MAL").
        mono_h = monogram_text(lag_hemma, "HEM", profil.get("individ", False))
        mono_b = monogram_text(lag_borta, "BORT", profil.get("individ", False))

        if isPreview and individ:
            # Ronden är det stora ordet, momentet blir etiketten. Saknas rond:
            # momentet stort och turneringen som etikett (design-svaret: topp-
            # högern står alltid; i fallbacken dubbleras turneringen medvetet).
            moment_ord = big_word   # "MATCHSTART"/"NÄSTA MATCH" (profildrivet)
            if rond_ren:
                etikett, stort = moment_ord, rond_ren.upper()
            else:
                etikett, stort = (liga or ""), moment_ord
            _render_preview_individ(canvas, accent,
                                    lag_hemma or "", lag_borta or "",
                                    land_hemma or "", land_borta or "",
                                    etikett, stort, sub_line)

        elif isPreview:
            bricka_h, pad_h = _bricka_med_skugga(_valj_logga(lag_hemma, hem_logga), 84, mono_h)
            bricka_b, pad_b = _bricka_med_skugga(_valj_logga(lag_borta, borta_logga), 84, mono_b)
            # Crop bort skugg-padding för att använda ren bricka vid placering
            bricka_h_ren = bricka_h.crop((pad_h, pad_h, pad_h + 84, pad_h + 84))
            bricka_b_ren = bricka_b.crop((pad_b, pad_b, pad_b + 84, pad_b + 84))
            _render_preview(canvas, accent,
                            lag_hemma or "", lag_borta or "",
                            bricka_h_ren, bricka_b_ren,
                            competition, big_word, sub_line)

        elif isScore and individ:
            # Etiketten: sportprofilens label + rond ("RESULTAT I SET ·
            # SEMIFINAL"). Vinnaren härleds ur set-siffrorna — markeras bara
            # vid Slutresultat (facit: aldrig vid mellanställning).
            etikett = f"{score_label} · {rond_ren}" if rond_ren else score_label
            if state == "Tiebreak":
                # P15: stora siffran är PÅGÅENDE setets gamesiffror (sista
                # segmentet av gamesiffror-strängen, "6–4, 6–6" → "6–6");
                # setställningen flyttar ner till komplementraden. Saknas
                # gamesiffror faller vi tillbaka på setställningen — hellre
                # rätt nivå-etikett med grova siffror än fel nivå.
                seg = [s.strip() for s in (mal_rad or "").replace(";", ",").split(",")
                       if s.strip()]
                stor = seg[-1] if seg else score_text
                games_rad = f"Set {score_text}" if score_text and score_text != "?–?" else ""
            else:
                stor = score_text
                games_rad = mal_rad or ""
            set_a, set_b = (stor.split("–", 1) + [""])[:2] \
                if "–" in stor else (stor, "")
            avgjord = ""
            if state == "Slutresultat":
                try:
                    a_i, b_i = int(set_a), int(set_b)
                    if a_i != b_i:
                        avgjord = "a" if a_i > b_i else "b"
                except ValueError:
                    pass
            _render_score_individ(canvas, accent,
                                  lag_hemma or "", lag_borta or "",
                                  etikett, set_a.strip(), set_b.strip(),
                                  games_rad, avgjord)

        elif isScore:
            bricka_h, pad_h = _bricka_med_skugga(_valj_logga(lag_hemma, hem_logga), 128, mono_h)
            bricka_b, pad_b = _bricka_med_skugga(_valj_logga(lag_borta, borta_logga), 128, mono_b)
            bricka_h_ren = bricka_h.crop((pad_h, pad_h, pad_h + 128, pad_h + 128))
            bricka_b_ren = bricka_b.crop((pad_b, pad_b, pad_b + 128, pad_b + 128))
            _render_score(canvas, accent,
                          lag_hemma or "", lag_borta or "",
                          bricka_h_ren, bricka_b_ren,
                          score_label, score_text, score_sub,
                          scorers=slut_scorers, scorers_layout=scorers_layout)

        elif isLineup:
            sv_text = startelva or ""
            _render_startelva(canvas, accent, lag_hemma or "",
                              competition, arena or "", sv_text)

        elif isScorers:
            _render_malgorare(canvas, accent,
                              lag_hemma or "", lag_borta or "",
                              score_text, mal_rad or "")

        # 7. (A5) Vertikal webbadress i vänsterkanten är BORTTAGEN — gren-kanten
        #    står ren.

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
