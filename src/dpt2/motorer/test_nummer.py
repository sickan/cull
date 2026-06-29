"""Enhetstester för tröjnummer-kärnan (Fas 3).

_namn_unikt + brus-/roster-filtreringen i _las_nummer testas med fejkade YOLO/
OCR-objekt (ingen modell laddas). _las_nummer behöver numpy (bild-utsnitt);
_hemma_andel_crop behöver cv2; _skriv_keywords behöver exiftool på PATH. Saknas
beroendet hoppas testet snyggt.

  ~/.local/pipx/venvs/dpt/bin/python -m unittest dpt2.motorer.test_nummer -v
"""

import shutil
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
HAR_EXIFTOOL = shutil.which("exiftool") is not None


# ── fejk-modeller ─────────────────────────────────────────────────────────────
class _Box:
    def __init__(self, xyxy):
        self._x = xyxy

    def tolist(self):
        return self._x


class _Boxes:
    def __init__(self, boxar, klasser):
        self.xyxy = [_Box(b) for b in boxar]
        self.cls = list(klasser)


class _Yolo:
    def __init__(self, boxar, klasser):
        self.boxes = _Boxes(boxar, klasser)


class _OCR:
    """Returnerar en fast lista (bbox, text, konf) för varje crop."""
    def __init__(self, lasningar):
        self._las = lasningar

    def readtext(self, crop, allowlist=None, detail=1):
        return self._las


# ── ren logik (stdlib) ────────────────────────────────────────────────────────
class TestNamnUnikt(unittest.TestCase):
    def test_unikt_over_lagen(self):
        from dpt2.motorer import nummer
        roster = {"hemma": {"7": "Anna"}, "borta": {"10": "Mia"}}
        self.assertEqual(nummer._namn_unikt("7", roster), "Anna")

    def test_krock_ger_tomt(self):
        from dpt2.motorer import nummer
        roster = {"hemma": {"7": "Anna"}, "borta": {"7": "Bea"}}
        self.assertEqual(nummer._namn_unikt("7", roster), "")

    def test_okant_nummer(self):
        from dpt2.motorer import nummer
        self.assertEqual(nummer._namn_unikt("99", {"hemma": {"7": "Anna"}}), "")

    def test_env_har_homebrew_i_path(self):
        from dpt2.motorer import nummer
        env = nummer._env()
        self.assertIn("/opt/homebrew/bin", env["PATH"])


# ── _las_nummer (behöver numpy för bild-utsnitt) ──────────────────────────────
@unittest.skipUnless(HAR_NP, "numpy saknas")
class TestLasNummer(unittest.TestCase):
    def _img(self):
        import numpy as np
        return np.full((300, 300, 3), 127, np.uint8)

    def test_utan_roster_ger_bart_nummer(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[10, 10, 130, 250]], [0])          # en person, klass 0
        ocr = _OCR([("b", "10", 0.9)])
        traffar, n = nummer._las_nummer(self._img(), yolo, ocr, {})
        self.assertEqual(n, 1)
        self.assertEqual(traffar, [("10", "")])

    def test_brusfilter_konf_och_siffror(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[10, 10, 130, 250]], [0])
        ocr = _OCR([("b", "100", 0.9),   # 3 siffror → bort
                    ("b", "7", 0.20),    # låg konfidens → bort
                    ("b", "9", 0.95)])   # ok
        traffar, _ = nummer._las_nummer(self._img(), yolo, ocr, {}, min_konf=0.45)
        self.assertEqual(traffar, [("9", "")])

    def test_for_liten_person_hoppas(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[0, 0, 10, 20]], [0])              # < 24×48 → oläsbart
        ocr = _OCR([("b", "10", 0.99)])
        traffar, n = nummer._las_nummer(self._img(), yolo, ocr, {})
        self.assertEqual(n, 1)
        self.assertEqual(traffar, [])

    def test_icke_person_klass_ignoreras(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[10, 10, 130, 250]], [32])         # boll → ej person
        ocr = _OCR([("b", "10", 0.99)])
        traffar, n = nummer._las_nummer(self._img(), yolo, ocr, {})
        self.assertEqual(n, 0)
        self.assertEqual(traffar, [])

    def test_enlagsroster_namnsatter(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[10, 10, 130, 250]], [0])
        ocr = _OCR([("b", "10", 0.9)])
        roster = {"hemma": {"10": "Mia Persson"}}
        traffar, _ = nummer._las_nummer(self._img(), yolo, ocr, roster)
        self.assertEqual(traffar, [("10", "Mia Persson")])

    def test_okant_squadnummer_filtreras_med_roster(self):
        from dpt2.motorer import nummer
        yolo = _Yolo([[10, 10, 130, 250]], [0])
        ocr = _OCR([("b", "44", 0.9)])                   # ej i roster
        roster = {"hemma": {"10": "Mia"}}
        traffar, _ = nummer._las_nummer(self._img(), yolo, ocr, roster)
        self.assertEqual(traffar, [])


@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestHemmaAndel(unittest.TestCase):
    def test_helrod_crop_hog_andel(self):
        import numpy as np
        from dpt2.motorer import nummer
        # ren röd BGR-bild → hög andel "röd"
        crop = np.zeros((40, 40, 3), np.uint8)
        crop[:, :, 2] = 255
        self.assertGreater(nummer._hemma_andel_crop(crop, "röd"), 0.5)

    def test_okand_farg_ger_noll(self):
        import numpy as np
        from dpt2.motorer import nummer
        crop = np.zeros((40, 40, 3), np.uint8)
        self.assertEqual(nummer._hemma_andel_crop(crop, "finnsej"), 0.0)


@unittest.skipUnless(HAR_EXIFTOOL and (HAR_CV2 or _har("PIL")), "exiftool/bild saknas")
class TestSkrivKeywords(unittest.TestCase):
    def _jpg(self, path):
        try:
            import cv2
            import numpy as np
            cv2.imwrite(str(path), np.full((20, 20, 3), 127, np.uint8))
        except Exception:
            from PIL import Image
            Image.new("RGB", (20, 20), (127, 127, 127)).save(path)

    def test_skriver_och_ar_idempotent(self):
        import subprocess
        from dpt2.motorer import nummer
        d = Path(tempfile.mkdtemp())
        f = d / "bild.jpg"
        self._jpg(f)
        env = nummer._env()
        traffar = [("10", "Mia Persson"), ("7", "")]
        self.assertTrue(nummer._skriv_keywords([f], traffar, env))
        # läs tillbaka XMP-dc:Subject
        out = subprocess.run(
            ["exiftool", "-XMP-dc:Subject", "-s", "-s", "-s", str(f)],
            capture_output=True, text=True, env=env).stdout
        self.assertIn("10 Mia Persson", out)
        self.assertIn("7", out)
        # omkörning → inga dubbletter
        nummer._skriv_keywords([f], traffar, env)
        out2 = subprocess.run(
            ["exiftool", "-XMP-dc:Subject", "-s", "-s", "-s", str(f)],
            capture_output=True, text=True, env=env).stdout
        self.assertEqual(out2.count("10 Mia Persson"), 1)

    def test_tomma_traffar_skriver_inget(self):
        from dpt2.motorer import nummer
        self.assertFalse(nummer._skriv_keywords([Path("/x.jpg")], [], nummer._env()))


if __name__ == "__main__":
    unittest.main()
