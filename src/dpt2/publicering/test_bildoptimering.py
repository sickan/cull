"""Enhetstester för bildoptimering — resize/kvalitet/sRGB/skärpning.

  python -m unittest dpt2.publicering.test_bildoptimering -v
"""

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from dpt2.publicering import bildoptimering as BO


def _jpg(mapp, namn="bild.jpg", storlek=(400, 300), **extra):
    p = Path(mapp) / namn
    Image.new("RGB", storlek, (120, 80, 200)).save(p, "JPEG", **extra)
    return p


class TestOptimera(unittest.TestCase):
    def test_liten_bild_skalas_inte_upp(self):
        with tempfile.TemporaryDirectory() as d:
            p = _jpg(d, storlek=(400, 300))
            data, andelse = BO.optimera(p, max_bredd=2200, kvalitet=85)
            self.assertEqual(andelse, ".jpg")
            img = Image.open(io.BytesIO(data))
            self.assertEqual(img.width, 400)  # oförändrad, ingen uppskalning

    def test_stor_bild_skalas_ned_till_max_bredd(self):
        with tempfile.TemporaryDirectory() as d:
            p = _jpg(d, storlek=(4000, 3000))
            data, _ = BO.optimera(p, max_bredd=2200, kvalitet=85)
            img = Image.open(io.BytesIO(data))
            self.assertEqual(img.width, 2200)
            self.assertEqual(img.height, 1650)  # bevarad bildproportion (4:3)

    def test_utdata_ar_alltid_jpeg(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bild.png"
            Image.new("RGB", (200, 200), (10, 20, 30)).save(p, "PNG")
            data, andelse = BO.optimera(p)
            self.assertEqual(andelse, ".jpg")
            img = Image.open(io.BytesIO(data))
            self.assertEqual(img.format, "JPEG")

    def test_hogre_kvalitet_ger_storre_fil(self):
        with tempfile.TemporaryDirectory() as d:
            p = _jpg(d, storlek=(1200, 900))
            lag, _ = BO.optimera(p, max_bredd=2200, kvalitet=40)
            hog, _ = BO.optimera(p, max_bredd=2200, kvalitet=95)
            self.assertLess(len(lag), len(hog))

    def test_rgba_konverteras_utan_fel(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alpha.png"
            Image.new("RGBA", (300, 200), (10, 20, 30, 128)).save(p, "PNG")
            data, _ = BO.optimera(p)
            img = Image.open(io.BytesIO(data))
            self.assertEqual(img.mode, "RGB")  # JPEG stödjer ingen alfakanal


if __name__ == "__main__":
    unittest.main()
