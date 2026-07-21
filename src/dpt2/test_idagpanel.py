"""Vakter för Startskärm "Idag" (D16 §C).

Två lager, samma mönster som test_importpanel/test_registerpanel:
  * käll-invarianter i Svelte (panelen kan inte köras i sviten) — de ytor och
    kopplingar som MÅSTE finnas för att skärmen ska funka;
  * riktiga frågor mot in-memory SQLite för de två härledda kö-signalerna som
    fick ny backend (startlista + leverans).
"""

import unittest
from pathlib import Path

from dpt2.data import db, store

SRC = Path(__file__).parent / "ui" / "src"
IDAG = (SRC / "panels" / "Idag.svelte").read_text(encoding="utf-8")
RAIL = (SRC / "lib" / "Rail.svelte").read_text(encoding="utf-8")
APP = (SRC / "App.svelte").read_text(encoding="utf-8")
API = (SRC / "lib" / "api.js").read_text(encoding="utf-8")
TOKENS = (SRC / "lib" / "tokens.css").read_text(encoding="utf-8")


class TestKallInvarianter(unittest.TestCase):
    def test_navpost_idag_finns_och_ar_topp(self):
        self.assertIn("dispatch('valj', 'idag')", RAIL)

    def test_app_startar_pa_idag_och_ruttar_panelen(self):
        self.assertIn("let aktiv = 'idag'", APP)
        self.assertIn("import Idag from './panels/Idag.svelte'", APP)
        self.assertIn("aktiv === 'idag'", APP)

    def test_panelen_har_atgardsko_och_navigerar(self):
        self.assertIn("Kräver åtgärd", IDAG)
        # Varje kö-rad och snabbväg måste kunna navigera vidare.
        self.assertIn("dispatch('navigera', k.dest)", IDAG)

    def test_kategorifarger_ar_kanon(self):
        for hex_ in ("#2f7cb0", "#c9871f", "#c9657f", "#8a6fb0"):
            self.assertIn(hex_, IDAG.lower())

    def test_api_exporterar_hamtaidag(self):
        self.assertIn("export async function hamtaIdag()", API)
        self.assertIn("api.hamta_idag()", API)

    def test_nya_tokens_i_bada_teman(self):
        # --danger/--warn/--info måste finnas ljust OCH mörkt (annars osynlig kö).
        for token in ("--danger:", "--warn:", "--info:"):
            self.assertGreaterEqual(TOKENS.count(token), 2, token)


class TestIdagFragor(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_matcher_utan_trupp_raknar_bara_lagsport_utan_trupp(self):
        # Lagsportmatch UTAN trupp → ska flaggas.
        store.spara_match(self.c, {"lag_hemma": "Malmö FF", "lag_borta": "AIK",
                                   "datum": "2099-05-01", "sport": "fotboll"})
        # Lagsportmatch MED trupp → ska INTE flaggas.
        store.spara_match(self.c, {"lag_hemma": "IFK", "lag_borta": "BK",
                                   "datum": "2099-05-02", "sport": "fotboll",
                                   "spelare": [{"nr": 1, "namn": "Kalle", "lag": "hemma"}]})
        # Friidrott UTAN trupp → individsport, ska INTE flaggas (SM-fällan).
        store.spara_match(self.c, {"lag_hemma": "Ospårad", "lag_borta": "Löpare",
                                   "datum": "2099-05-03", "sport": "friidrott"})
        utan = store.matcher_utan_trupp(self.c, "2026-07-21")
        self.assertEqual(len(utan), 1)

    def test_matcher_utan_trupp_utesluter_passerade(self):
        store.spara_match(self.c, {"lag_hemma": "Gammal", "lag_borta": "Match",
                                   "datum": "2000-01-01", "sport": "fotboll"})
        self.assertEqual(store.matcher_utan_trupp(self.c, "2026-07-21"), [])

    def test_urval_vantar_leverans_raknar_bara_gallrade(self):
        a = store.spara_urval(self.c, kalla="x", bilder=10)  # default: gallrad
        store.spara_urval(self.c, kalla="y", bilder=20)      # gallrad
        self.assertEqual(store.urval_vantar_leverans(self.c), 2)
        self.c.execute("UPDATE urval SET status='levererad' WHERE id=?", (a,))
        self.assertEqual(store.urval_vantar_leverans(self.c), 1)


if __name__ == "__main__":
    unittest.main()
