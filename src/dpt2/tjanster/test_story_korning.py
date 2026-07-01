"""Tester för story-orkestreringens rena delar (matchfält-härledning +
validering). Den skarpa renderingen körs via worker (PIL, riktigt foto)."""

import unittest

from dpt2.data import db, store
from dpt2.tjanster import story_korning as S


class TestMatchfalt(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_fyller_ur_match_inkl_startelva(self):
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "KDFF", "liga": "OBOS",
            "arena": "Eleda", "resultat": "6-0", "datum": "2026-06-27",
            "spelare": [
                {"nr": "1", "namn": "Musovic", "lag": "hemma", "start": True},
                {"nr": "9", "namn": "Reserv", "lag": "hemma", "start": False},
                {"nr": "5", "namn": "Borta", "lag": "borta", "start": True},
            ]})
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(f["lag_hemma"], "Malmö FF")
        self.assertEqual(f["liga"], "OBOS")
        self.assertEqual(f["stallning"], "6-0")
        self.assertIn("Musovic", f["startelva"])
        self.assertNotIn("Borta", f["startelva"])       # bara hemma-start
        self.assertNotIn("Reserv", f["startelva"])       # bara start=True

    def test_config_fallback_utan_match(self):
        f = S._matchfalt(self.c, {"lag_hemma": "A", "lag_borta": "B"})
        self.assertEqual(f["lag_hemma"], "A")
        self.assertIsNone(f["startelva"])

    def test_kor_story_validering(self):
        self.assertFalse(S.kor_story(self.c, {})["ok"])                  # inget moment
        self.assertFalse(S.kor_story(self.c, {"moment": "Avspark"})["ok"])  # inget foto
        self.assertFalse(S.kor_story(
            self.c, {"moment": "Avspark", "foto": "/finns/inte.jpg"})["ok"])


if __name__ == "__main__":
    unittest.main()
