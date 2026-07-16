"""Tester för molnrendern (render_service/render.py).

Kör mot den RIKTIGA `story_overlay` — poängen med servicen är att det finns
exakt en renderare, så en mock hade testat fel sak. Bilderna syntetiseras i
minnet; inga fixturer på disk.
"""

import hashlib
import io
import unittest

from PIL import Image, ImageDraw

from dpt2.render_service.render import MAX_BYTES, RenderFel, rendera


def _jpeg(bredd=1600, hojd=1000):
    """Ett MÖNSTRAT foto — en enfärgad yta ger identiska bytes efter beskärning,
    vilket tyst hade fått fokus/zoom-testet att jämföra ingenting."""
    im = Image.new("RGB", (bredd, hojd), (28, 60, 78))
    d = ImageDraw.Draw(im)
    for i in range(0, bredd + hojd, 40):
        d.line([(i, 0), (i - hojd, hojd)], fill=(36, 78, 100), width=14)
    d.ellipse([bredd * 0.6, hojd * 0.1, bredd * 0.9, hojd * 0.5], fill=(200, 90, 70))
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=80)
    return b.getvalue()


def _sig(data):
    """Kort signatur — assertNotEqual på råa JPEG-bytes spyr hundratals kB."""
    return hashlib.sha256(data).hexdigest()[:16]


def _png(storlek=200):
    b = io.BytesIO()
    Image.new("RGBA", (storlek, storlek), (255, 0, 0, 255)).save(b, format="PNG")
    return b.getvalue()


BAS = {"moment": "slutresultat", "lag_hemma": "Malmö FF",
       "lag_borta": "Kristianstads DFF", "tema": "Hav", "sport": "fotboll"}


class TestRendera(unittest.TestCase):
    def _bild(self, data):
        return Image.open(io.BytesIO(data))

    def test_renderar_9x16(self):
        ut = rendera(BAS, foto=_jpeg())
        self.assertEqual(self._bild(ut).size, (1080, 1920))

    def test_friidrott(self):
        # B-002: spec.friidrott → skapa_friidrott_story-vägen (D2-mallarna).
        spec = {"friidrott": {"tillstand": "placering", "gren_namn": "Längd",
                              "grentyp": "hoppkast", "moment": "Final",
                              "namn": "Alva Hoppare", "klubb": "Malmö AI",
                              "placering": "1", "resultat": "6,42"},
                "tema": "Hav", "gren": "dam"}
        ut = rendera(spec, foto=_jpeg())
        self.assertEqual(self._bild(ut).size, (1080, 1920))
        # Annan deltagare/placering → annan bild (fälten når overlayen)
        spec2 = {**spec, "friidrott": {**spec["friidrott"], "placering": "DNF"}}
        self.assertNotEqual(_sig(ut), _sig(rendera(spec2, foto=_jpeg())))
        # Valideringar → RenderFel (400), inte 500
        with self.assertRaises(RenderFel):
            rendera({"friidrott": {"tillstand": "banzai", "gren_namn": "Längd"}},
                    foto=_jpeg())
        with self.assertRaises(RenderFel):
            rendera({"friidrott": {"tillstand": "start"}}, foto=_jpeg())

    def test_format_4x5(self):
        ut = rendera({**BAS, "format": "4x5"}, foto=_jpeg())
        self.assertEqual(self._bild(ut).size, (1080, 1350))

    def test_matchdata_slapps_igenom(self):
        # liga/stallning/mal_rad/arena hamnar i overlayen — vi kan inte OCR:a,
        # men en ändring får inte krascha och ska ge en annan bild än utan dem.
        utan = rendera(BAS, foto=_jpeg())
        med = rendera({**BAS, "liga": "OBOS Damallsvenskan", "stallning": "3-1",
                       "mal_rad": "Hansson 14', Ali 63'", "arena": "Eleda Stadion"},
                      foto=_jpeg())
        self.assertNotEqual(_sig(utan), _sig(med))

    def test_gren_ger_annan_bild(self):
        # gren = färgad kant längst till vänster
        a = rendera(BAS, foto=_jpeg())
        b = rendera({**BAS, "gren": "dam"}, foto=_jpeg())
        self.assertNotEqual(_sig(a), _sig(b))

    def test_loggor_anvands(self):
        # Utan explicita loggor faller renderaren tillbaka på monogram (eller
        # ~/.config/dpt/loggor). Med loggor ska bilden bli en annan.
        utan = rendera(BAS, foto=_jpeg())
        med = rendera(BAS, foto=_jpeg(), hem_logga=_png(), borta_logga=_png())
        self.assertNotEqual(_sig(utan), _sig(med))

    def test_sport_utan_malskyttar(self):
        ut = rendera({"moment": "avspark", "lag_hemma": "Sverige",
                      "lag_borta": "Italien", "sport": "volleyboll"}, foto=_jpeg())
        self.assertEqual(self._bild(ut).size, (1080, 1920))

    def test_overlay_av_ger_annan_bild(self):
        # overlay=False → ren beskuren bild utan grafik (iOS-klienten).
        med = rendera({**BAS, "gren": "dam"}, foto=_jpeg())
        utan = rendera({**BAS, "gren": "dam", "overlay": False}, foto=_jpeg())
        self.assertNotEqual(_sig(med), _sig(utan))
        self.assertEqual(self._bild(utan).size, (1080, 1920))

    def test_scorers_layout_slapps_igenom(self):
        # A4: layout-valet ska nå renderaren → rad vs chips ger olika bilder.
        many = {**BAS, "stallning": "6-0",
                "mal_rad": "A 10' · B 20' · C 30' · D 40' · E 50' · F 60'"}
        rad = rendera({**many, "scorers_layout": "rad"}, foto=_jpeg())
        chips = rendera({**many, "scorers_layout": "chips"}, foto=_jpeg())
        self.assertNotEqual(_sig(rad), _sig(chips))

    def test_fokus_och_zoom(self):
        a = rendera(BAS, foto=_jpeg())
        b = rendera({**BAS, "fokus": {"x": 20, "y": 80}, "zoom": 1.6}, foto=_jpeg())
        self.assertNotEqual(_sig(a), _sig(b))

    def test_fokus_utan_xy_ignoreras(self):
        ut = rendera({**BAS, "fokus": {"x": 20}}, foto=_jpeg())   # ofullständig
        self.assertEqual(self._bild(ut).size, (1080, 1920))

    # ── felfall: ska bli RenderFel (→ 400), aldrig ett ohanterat undantag ──
    def test_foto_kravs(self):
        with self.assertRaises(RenderFel):
            rendera(BAS, foto=b"")

    def test_moment_kravs(self):
        with self.assertRaises(RenderFel):
            rendera({**BAS, "moment": ""}, foto=_jpeg())

    def test_lag_kravs(self):
        with self.assertRaises(RenderFel):
            rendera({**BAS, "lag_borta": ""}, foto=_jpeg())

    def test_trasigt_foto_ger_renderfel(self):
        with self.assertRaises(RenderFel):
            rendera(BAS, foto=b"inte en jpeg")

    def test_for_stort_foto(self):
        with self.assertRaises(RenderFel):
            rendera(BAS, foto=b"x" * (MAX_BYTES + 1))

    def test_okant_moment_ger_renderfel(self):
        # story_overlay normaliserar moment; ett okänt ska inte välta servicen
        try:
            rendera({**BAS, "moment": "kaffepaus"}, foto=_jpeg())
        except RenderFel:
            pass          # acceptabelt
        # renderar den ändå (fallback) är det också OK — men den får inte krascha

    def test_tempfiler_stadas(self):
        import tempfile
        from pathlib import Path
        fore = set(Path(tempfile.gettempdir()).glob("dpt-render-*"))
        rendera(BAS, foto=_jpeg())
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("dpt-render-*")), fore)


if __name__ == "__main__":
    unittest.main()
