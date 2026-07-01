"""Tester för leverera-tjänsten (Fas 3 — icke-destruktiv LR-väg).

`leverera` importerar `xmp_writer` som importerar cv2/numpy på modulnivå, så hela
sviten guardas på dem (finns i dpt-venv). Inga tunga modeller laddas — vinkel/ISO
injiceras som callables.

  ~/.local/pipx/venvs/dpt/bin/python -m unittest dpt2.tjanster.test_leverera -v
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

PRESET_XMP = """<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:crs='http://ns.adobe.com/camera-raw-settings/1.0/'
      crs:Contrast2012='+20'
      crs:Clarity2012='+8'/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""


@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestSkrivSidecars(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def _nef(self, namn):
        p = self.d / namn
        p.write_bytes(b"")          # tom raw — skriv_xmp läser inte pixlarna
        return p

    def test_skriver_en_sidecar_per_fil(self):
        from dpt2.tjanster import leverera
        filer = [self._nef("a.nef"), self._nef("b.nef")]
        res = leverera.skriv_sidecars(filer, logg=lambda *_: None)
        self.assertEqual(res["skrivna"], 2)
        self.assertTrue((self.d / "a.xmp").exists())
        self.assertTrue((self.d / "b.xmp").exists())

    def test_raw_utan_preset_far_camera_neutral(self):
        from dpt2.tjanster import leverera
        leverera.skriv_sidecars([self._nef("a.nef")], logg=lambda *_: None)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertIn("Camera Neutral", txt)

    def test_exp_bump_skrivs(self):
        from dpt2.tjanster import leverera
        leverera.skriv_sidecars([self._nef("a.nef")], exp_bump=0.5,
                                logg=lambda *_: None)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertIn("crs:Exposure2012='+0.50'", txt)

    def test_vinkel_for_ger_croppvinkel_och_raknas(self):
        from dpt2.tjanster import leverera
        res = leverera.skriv_sidecars(
            [self._nef("a.nef")], vinkel_for=lambda f: 3.0,
            logg=lambda *_: None)
        self.assertEqual(res["ratade"], 1)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertIn("crs:CropAngle='3.00'", txt)
        self.assertIn("crs:HasCrop='True'", txt)

    def test_husstil_preset_bakas_in(self):
        from dpt2.tjanster import leverera
        preset = self.d / "husstil.xmp"
        preset.write_text(PRESET_XMP, encoding="utf-8")
        leverera.skriv_sidecars([self._nef("a.nef")], husstil_path=str(preset),
                                logg=lambda *_: None)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertIn("Contrast2012", txt)
        self.assertIn("+20", txt)
        self.assertNotIn("Camera Neutral", txt)   # presetet styr profilen

    def test_iso_brus_kraver_flagga(self):
        from dpt2.tjanster import leverera
        # xmp_brus=False → ingen brusreducering trots iso_for
        leverera.skriv_sidecars([self._nef("a.nef")], iso_for=lambda f: 6400,
                                xmp_brus=False, logg=lambda *_: None)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertNotIn("LuminanceSmoothing", txt)
        # xmp_brus=True → brusreducering enligt ISO
        leverera.skriv_sidecars([self._nef("a.nef")], iso_for=lambda f: 6400,
                                xmp_brus=True, logg=lambda *_: None)
        txt = (self.d / "a.xmp").read_text(encoding="utf-8")
        self.assertIn("LuminanceSmoothing", txt)


@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestListaOchHough(unittest.TestCase):
    def test_lista_bilder_filtrerar_och_sorterar(self):
        from dpt2.tjanster import leverera
        d = Path(tempfile.mkdtemp())
        for namn in ("b.nef", "a.jpg", "._a.jpg", "anteckning.txt"):
            (d / namn).write_bytes(b"")
        namn = [p.name for p in leverera.lista_bilder(d)]
        self.assertEqual(namn, ["a.jpg", "b.nef"])     # sorterat, ._/txt bort

    def test_lista_bilder_saknad_mapp(self):
        from dpt2.tjanster import leverera
        self.assertEqual(leverera.lista_bilder("/finns/verkligen/inte"), [])

    def test_hough_vinkel_pa_lutande_linje(self):
        import cv2
        import numpy as np
        from dpt2.tjanster import leverera
        # vit bakgrund, en mörk linje lutande ~4° i nedre halvan
        img = np.full((400, 600, 3), 255, np.uint8)
        cv2.line(img, (50, 320), (550, 285), (0, 0, 0), 3)
        p = Path(tempfile.mkdtemp()) / "lutar.jpg"
        cv2.imwrite(str(p), img)
        v = leverera.hough_vinkel(p)
        self.assertGreater(abs(v), 1.0)                # hittar lutningen
        self.assertLessEqual(abs(v), 5.0)              # klippt till ±5

    def test_hough_vinkel_oläsbar_fil(self):
        from dpt2.tjanster import leverera
        self.assertEqual(leverera.hough_vinkel("/x/finns/inte.jpg"), 0.0)


if __name__ == "__main__":
    unittest.main()
