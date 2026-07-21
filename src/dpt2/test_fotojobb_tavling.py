"""Fas 3 / M-11: fotojobb ↔ tävling-kopplingen (D16 §A).

Backend-primitiverna (matcha + länka + baklänges) och de UI-ytor som MÅSTE
finnas för att kopplingen ska gå att se och sätta: väljaren + "Del av"-chippen
i Fotojobb, Fotojobb-kortet i Tävlingar.
"""

import unittest
from pathlib import Path

from dpt2.data import db, store

SRC = Path(__file__).parent / "ui" / "src"
FOTOJOBB = (SRC / "panels" / "Fotojobb.svelte").read_text(encoding="utf-8")
EVENT = (SRC / "panels" / "EventSektion.svelte").read_text(encoding="utf-8")
API = (SRC / "lib" / "api.js").read_text(encoding="utf-8")
APP = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")


class TestMatchaTavling(unittest.TestCase):
    def setUp(self):
        self.tavlingar = [{"id": "sm", "namn": "Friidrotts-SM",
                           "fran": "2026-07-24", "till": "2026-07-26"},
                          {"id": "nordea", "namn": "Nordea Open"}]  # utan period

    def test_namn_i_titel_och_datum_inom_period(self):
        self.assertEqual(store.matcha_tavling("Friidrotts-SM dag 1",
                         "2026-07-25T10:00", self.tavlingar), "sm")

    def test_datum_utanfor_perioden_matchar_inte(self):
        self.assertIsNone(store.matcha_tavling("Friidrotts-SM",
                          "2026-08-01T10:00", self.tavlingar))

    def test_utan_period_matchas_pa_namn_ensamt(self):
        self.assertEqual(store.matcha_tavling("Nordea Open final",
                         "2026-07-10T12:00", self.tavlingar), "nordea")

    def test_namn_saknas_i_titel_ger_none(self):
        self.assertIsNone(store.matcha_tavling("Bröllop Berg",
                          "2026-07-25T12:00", self.tavlingar))


class TestLankaOchBaklanges(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.c.execute("INSERT INTO tavling(id,typ,sport,namn) "
                       "VALUES('sm','masterskap','friidrott','Friidrotts-SM')")

    def test_lanka_och_las_tillbaka(self):
        store.lanka_fotojobb_tavling(self.c, "jobb1", "sm")
        self.assertEqual(store.tavlingref_for_fotojobb(self.c, ["jobb1"]),
                         {"jobb1": "sm"})

    def test_tom_tavling_kopplar_bort(self):
        store.lanka_fotojobb_tavling(self.c, "jobb1", "sm")
        store.lanka_fotojobb_tavling(self.c, "jobb1", "")   # "" = Fristående
        self.assertEqual(store.tavlingref_for_fotojobb(self.c, ["jobb1"]), {})


class TestUIYtor(unittest.TestCase):
    def test_fotojobb_har_valjare_och_chip(self):
        self.assertIn("Del av tävling", FOTOJOBB)
        self.assertIn("bind:value={modal.tavling_id}", FOTOJOBB)
        self.assertIn("Fristående", FOTOJOBB)                # tom = fristående
        self.assertIn("Del av ${j.tavling_namn}", FOTOJOBB)  # radchippen

    def test_tavlingar_listar_sina_jobb(self):
        self.assertIn("fotojobbForTavling", EVENT)
        self.assertIn("tavlingsjobb", EVENT)

    def test_api_och_backend_har_baklangesfragan(self):
        self.assertIn("export async function fotojobbForTavling", API)
        self.assertIn("def fotojobb_for_tavling", APP)


if __name__ == "__main__":
    unittest.main()
