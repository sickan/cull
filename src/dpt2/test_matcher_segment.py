"""Fas 4b / D17 (approach A): Matcher är inte längre en egen navpost — den nås
som segment "Alla jobb / Matcher" inifrån Fotojobb. Matchflödets kopplingar
(aktiverad/gaTill/navigera/urval) MÅSTE vara orörda.
"""

import unittest
from pathlib import Path

SRC = Path(__file__).parent / "ui" / "src"
RAIL = (SRC / "lib" / "Rail.svelte").read_text(encoding="utf-8")
FOTOJOBB = (SRC / "panels" / "Fotojobb.svelte").read_text(encoding="utf-8")
MATCHER = (SRC / "panels" / "Matcher.svelte").read_text(encoding="utf-8")
APP = (SRC / "App.svelte").read_text(encoding="utf-8")


class TestNavpostBorttagen(unittest.TestCase):
    def test_rail_har_ingen_matcher_navpost(self):
        self.assertNotIn("{ id: 'matcher', namn: 'Matcher' }", RAIL)

    def test_app_ruttar_fortfarande_matcher(self):
        # Panelen finns kvar — den nås bara via segmentet, inte naven.
        self.assertIn("aktiv === 'matcher'", APP)


class TestSegmentVaxling(unittest.TestCase):
    def test_fotojobb_har_matcher_segment(self):
        self.assertIn("dispatch('navigera', 'matcher')", FOTOJOBB)
        self.assertIn("Alla jobb", FOTOJOBB)

    def test_matcher_har_tillbaka_segment(self):
        self.assertIn("dispatch('navigera', 'fotojobb')", MATCHER)


class TestMatchflodetOrort(unittest.TestCase):
    def test_matcher_behaller_alla_flodeshandelser(self):
        # Aktivera match → Gallra, gaTill → destination, urval → topbar, navigera.
        for h in ("dispatch('aktiverad'", "dispatch('gaTill'",
                  "dispatch('urval'", "dispatch('navigera'"):
            self.assertIn(h, MATCHER, h)

    def test_app_lyssnar_pa_matcher_handelserna(self):
        for lyssnare in ("on:aktiverad", "on:gaTill", "on:urval"):
            self.assertIn(lyssnare, APP, lyssnare)


if __name__ == "__main__":
    unittest.main()
