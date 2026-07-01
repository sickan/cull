"""Enhetstester för leverans-geometrikärnan (Fas 3).

Pure-matematiktester (komponering, inskriven rektangel, crop_rect, fit) körs
överallt. cv2-bundna tester (rakta, passa_i_box, spara_under_storlek) hoppas
över om cv2/numpy saknas.

  ~/.local/pipx/venvs/dpt/bin/python -m unittest dpt2.motorer.test_leverans -v
"""

import tempfile
import unittest
from pathlib import Path


def _har(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


HAR_CV2 = _har("cv2")
HAR_NP = _har("numpy")


# ── ren geometri (stdlib — körs alltid) ───────────────────────────────────────
class TestGeometri(unittest.TestCase):
    def test_storsta_inskrivna_noll_vinkel(self):
        from dpt2.motorer import leverans
        self.assertEqual(leverans._storsta_inskrivna(800, 600, 0.0), (800, 600))

    def test_storsta_inskrivna_krymper(self):
        from dpt2.motorer import leverans
        wr, hr = leverans._storsta_inskrivna(800, 600, 5.0)
        self.assertLess(wr, 800)
        self.assertLess(hr, 600)
        self.assertGreater(wr, 0)
        self.assertGreater(hr, 0)

    def test_komponera_utan_bbox_ger_aspekt(self):
        from dpt2.motorer import leverans
        x0, y0, x1, y1 = leverans._komponera_4x5(None, 1000, 1000, (4, 5))
        self.assertAlmostEqual((x1 - x0) / (y1 - y0), 4 / 5, places=2)
        # ligger inom bilden
        self.assertGreaterEqual(x0, 0)
        self.assertLessEqual(x1, 1000)

    def test_komponera_bbox_centrerar(self):
        from dpt2.motorer import leverans
        # motiv i vänster halva → fönstret ska dras vänster
        bbox = (0.1, 0.1, 0.4, 0.8)
        x0, _y0, x1, _y1 = leverans._komponera_4x5(bbox, 1000, 1000, (4, 5))
        mitt = (x0 + x1) / 2
        self.assertLess(mitt, 500)

    def test_crop_rect_normaliserad(self):
        from dpt2.motorer import leverans
        top, left, bottom, right = leverans.crop_rect(None, 1000, 1000, (4, 5))
        for v in (top, left, bottom, right):
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)
        self.assertLess(top, bottom)
        self.assertLess(left, right)

    def test_crop_rect_degenererad(self):
        from dpt2.motorer import leverans
        self.assertEqual(leverans.crop_rect(None, 0, 0, (4, 5)), (0.0, 0.1, 1.0, 0.9))

    def test_fit_aspekt_utan_bbox_ar_ett(self):
        from dpt2.motorer import leverans
        self.assertEqual(leverans._fit_aspekt(None, 1000, 1000, (4, 5)), 1.0)

    def test_fit_aspekt_smal_bbox_ryms(self):
        from dpt2.motorer import leverans
        # smalt centrerat motiv ryms helt i 4:5 → nära 1.0
        f = leverans._fit_aspekt((0.4, 0.2, 0.6, 0.8), 1000, 1000, (4, 5))
        self.assertGreater(f, 0.9)

    def test_vinkel_som_bevarar_kapar(self):
        from dpt2.motorer import leverans
        # motiv som fyller nästan hela bilden → upprätning måste dämpas mot 0
        bbox_px = (20, 20, 980, 980)
        v = leverans._vinkel_som_bevarar(1000, 1000, 5.0, bbox_px)
        self.assertLess(abs(v), 5.0)


# ── cv2-bundna (bildoperationer) ──────────────────────────────────────────────
@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestBildops(unittest.TestCase):
    def _bild(self, w, h):
        import numpy as np
        return np.full((h, w, 3), 127, np.uint8)

    def test_rakta_noop_vid_liten_vinkel(self):
        from dpt2.motorer import leverans
        img = self._bild(400, 300)
        # None och försumbar vinkel → oförändrad (samma objekt)
        self.assertIs(leverans.rakta(img, None), img)
        self.assertIs(leverans.rakta(img, 0.01), img)

    def test_rakta_beskar_kilarna(self):
        from dpt2.motorer import leverans
        img = self._bild(800, 600)
        ut = leverans.rakta(img, 4.0)
        # roterad + kil-beskuren → mindre än originalet men ej tom
        self.assertLess(ut.shape[0], 600)
        self.assertLess(ut.shape[1], 800)
        self.assertGreater(ut.size, 0)

    def test_passa_i_box_skalar_ned(self):
        from dpt2.motorer import leverans
        ut = leverans.passa_i_box(self._bild(1000, 1000), 100, 100)
        h, w = ut.shape[:2]
        self.assertLessEqual(w, 100)
        self.assertLessEqual(h, 100)

    def test_passa_i_box_forstorar_aldrig(self):
        from dpt2.motorer import leverans
        img = self._bild(50, 50)
        self.assertIs(leverans.passa_i_box(img, 1000, 1000), img)

    def test_spara_under_storlek(self):
        from dpt2.motorer import leverans
        ut = Path(tempfile.mkdtemp()) / "ut.jpg"
        q, n = leverans.spara_under_storlek(self._bild(600, 400), ut, 1.0)
        self.assertTrue(ut.exists())
        self.assertLessEqual(n, 1.0 * 1024 * 1024)
        self.assertGreaterEqual(q, 40)


if __name__ == "__main__":
    unittest.main()
