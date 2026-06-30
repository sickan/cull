"""Tester för worker-IPC: event-parsning + skarp demo-subprocess (stdlib, körs
överallt — ingen ML).

  python -m unittest dpt2.tjanster.test_korning -v
"""

import unittest

from dpt2.tjanster import korning
from dpt2 import worker


class TestParsaEvent(unittest.TestCase):
    def test_giltigt_event(self):
        ev = korning.parsa_event('{"typ": "progress", "andel": 0.5}')
        self.assertEqual(ev["typ"], "progress")
        self.assertEqual(ev["andel"], 0.5)

    def test_icke_json_blir_logg(self):
        ev = korning.parsa_event("UserWarning: nåt från ett bibliotek")
        self.assertEqual(ev["typ"], "logg")
        self.assertIn("UserWarning", ev["text"])

    def test_json_utan_giltig_typ_blir_logg(self):
        ev = korning.parsa_event('{"typ": "skräp", "x": 1}')
        self.assertEqual(ev["typ"], "logg")

    def test_tom_rad(self):
        self.assertIsNone(korning.parsa_event("  \n"))

    def test_event_rad_round_trip(self):
        rad = korning.event_rad(korning.event("logg", niva="ok", text="åäö"))
        self.assertEqual(korning.parsa_event(rad)["text"], "åäö")


class TestWorkerMain(unittest.TestCase):
    def setUp(self):
        self.rader = []
        self._orig = worker._emit
        worker._emit = lambda ev: self.rader.append(ev)

    def tearDown(self):
        worker._emit = self._orig

    def test_demo_event_sekvens(self):
        kod = worker.main(["demo", '{"steg": 3}'])
        self.assertEqual(kod, 0)
        typer = [e["typ"] for e in self.rader]
        self.assertEqual(typer[0], "start")
        self.assertEqual(typer[-1], "klar")
        self.assertEqual(sum(1 for t in typer if t == "progress"), 3)
        self.assertEqual(self.rader[-1]["resultat"]["steg"], 3)

    def test_okant_jobb(self):
        self.assertEqual(worker.main(["finns-inte"]), 2)
        self.assertEqual(self.rader[-1]["typ"], "fel")

    def test_ej_implementerat_jobb_ger_fel_event(self):
        worker.main(["gallra", "{}"])
        self.assertEqual(self.rader[-1]["typ"], "fel")


class TestSubprocess(unittest.TestCase):
    def test_kor_demo_skarpt(self):
        """Skarp subprocess — bevisar hela röret (spawn → JSON-rader → events)."""
        sedda = []
        r = korning.kor_subprocess(["demo", '{"steg": 4}'], lyssnare=sedda.append)
        self.assertEqual(r["returkod"], 0)
        typer = [e["typ"] for e in r["events"]]
        self.assertEqual(typer[0], "start")
        self.assertIn("klar", typer)
        self.assertEqual(sum(1 for t in typer if t == "progress"), 4)
        self.assertEqual(len(sedda), len(r["events"]))     # lyssnaren fick allt


if __name__ == "__main__":
    unittest.main()
