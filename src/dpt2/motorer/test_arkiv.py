"""Tester för arkiv-genomgång + namnbaserad sport (stdlib, körs överallt)."""

import tempfile
import unittest
from pathlib import Path

from dpt2.motorer import arkiv


class TestSportAvNamn(unittest.TestCase):
    def test_lag_suffix_vager_tyngst(self):
        self.assertEqual(arkiv.sport_av_namn("(D) Malmö FF - Kristianstad DFF 6-0"),
                         "fotboll")
        self.assertEqual(arkiv.sport_av_namn("HK Malmö - Sävehof 31-29"), "handboll")

    def test_resultat_over_25_ger_handboll(self):
        self.assertEqual(arkiv.sport_av_namn("Lag A - Lag B 38-34"), "handboll")

    def test_okand(self):
        self.assertEqual(arkiv.sport_av_namn("Promenad i parken"), "okänd")


class TestFrameId(unittest.TestCase):
    def test_export_filnamn(self):
        self.assertEqual(arkiv._frame_id("20260627140000_Z816551_NIKON_Z_8.jpg"),
                         "Z816551")

    def test_redigera_strippas(self):
        self.assertEqual(arkiv._frame_id("_Z816551-Redigera.jpg"), "Z816551")


class TestHittaUppdrag(unittest.TestCase):
    def test_instagram_ger_positiva(self):
        root = Path(tempfile.mkdtemp())
        m = root / "(D) Malmö FF - KDFF 6-0"
        (m / "Instagram").mkdir(parents=True)
        (m / "Instagram" / "a.jpg").write_bytes(b"")        # publicerad → label 1
        for namn in "abcdefg":                               # 7 kandidater totalt
            (m / f"{namn}.jpg").write_bytes(b"")
        uppdrag = arkiv.hitta_uppdrag(root)
        self.assertEqual(len(uppdrag), 1)
        namn, sport, items = uppdrag[0]
        self.assertEqual(sport, "fotboll")
        labels = {Path(p).stem: lab for p, lab in items}
        self.assertEqual(labels["a"], 1)
        self.assertEqual(labels["b"], 0)
        self.assertEqual(sum(l for _, l in items), 1)

    def test_for_fa_kandidater_hoppas(self):
        root = Path(tempfile.mkdtemp())
        m = root / "match"
        (m / "Instagram").mkdir(parents=True)
        (m / "Instagram" / "a.jpg").write_bytes(b"")
        (m / "a.jpg").write_bytes(b"")                       # bara 1 kandidat
        self.assertEqual(arkiv.hitta_uppdrag(root), [])

    def test_test_loggor_exkluderas(self):
        root = Path(tempfile.mkdtemp())
        m = root / "match2"
        (m / "Instagram").mkdir(parents=True)
        (m / "Instagram" / "x.jpg").write_bytes(b"")
        (m / "Test").mkdir()
        (m / "Test" / "skräp.jpg").write_bytes(b"")          # ska EJ räknas
        for namn in "xpqrst":
            (m / f"{namn}.jpg").write_bytes(b"")
        _, _, items = arkiv.hitta_uppdrag(root)[0]
        self.assertNotIn("skräp", {Path(p).stem for p, _ in items})


if __name__ == "__main__":
    unittest.main()
