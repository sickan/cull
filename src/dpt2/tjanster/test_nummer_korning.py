"""Tester för tröjnummer-orkestreringens rena del (roster ur match). Den skarpa
OCR-körningen kräver bilder + YOLO/EasyOCR → körs via worker manuellt."""

import unittest

from dpt2.data import db, store
from dpt2.tjanster import nummer_korning as NK


class TestRosterAvMatch(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_bygger_lag_roster(self):
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "KDFF", "datum": "2026-06-27",
            "spelare": [
                {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma"},
                {"nr": "10", "namn": "Mia Persson", "lag": "borta"},
            ]})
        r = NK.roster_av_match(self.c, mid)
        self.assertEqual(r["hemma"]["1"], "Zecira Musovic")
        self.assertEqual(r["borta"]["10"], "Mia Persson")

    def test_ingen_match_ger_tomt(self):
        self.assertEqual(NK.roster_av_match(self.c, None), {})
        self.assertEqual(NK.roster_av_match(self.c, "finns-inte"), {})


if __name__ == "__main__":
    unittest.main()
