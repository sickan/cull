"""Tester för ren matchdomän-logik (stdlib → körs överallt)."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from dpt2.data import matchlogik as M


class TestRensaSpelare(unittest.TestCase):
    def test_filtrerar_och_tvingar_lag(self):
        ut = M.rensa_spelare([
            {"nr": "9", "namn": "A", "lag": "HEMMA", "start": 1},
            {"nr": "", "namn": "", "lag": "borta"},          # tom → bort
            {"nr": "7", "namn": "B", "lag": "skräp"},        # ogiltigt lag → hemma
            "inte en dict",                                   # ignoreras
        ])
        self.assertEqual(len(ut), 2)
        self.assertEqual(ut[0]["lag"], "hemma")
        self.assertTrue(ut[0]["start"])
        self.assertEqual(ut[1]["lag"], "hemma")              # tvingad


class TestSlaIhop(unittest.TestCase):
    def test_bevarar_handle_info_fran_gamla(self):
        gamla = [{"nr": "9", "namn": "A", "lag": "hemma",
                  "handle": "@a", "info": "anf", "start": True}]
        nya = [{"nr": "9", "namn": "A", "lag": "hemma"}]      # saknar handle/info
        ut = M.sla_ihop_spelare(gamla, nya)
        self.assertEqual(ut[0]["handle"], "@a")              # bevarat
        self.assertEqual(ut[0]["info"], "anf")
        self.assertFalse(ut[0]["start"])                     # nollat (bevara_start=False)

    def test_bevara_start(self):
        gamla = [{"nr": "9", "namn": "A", "lag": "hemma", "start": True}]
        nya = [{"nr": "9", "namn": "A", "lag": "hemma"}]
        ut = M.sla_ihop_spelare(gamla, nya, bevara_start=True)
        self.assertTrue(ut[0]["start"])

    def test_spelare_enbart_i_gamla_behalls(self):
        gamla = [{"nr": "9", "namn": "A", "lag": "hemma"},
                 {"nr": "5", "namn": "B", "lag": "hemma"}]
        nya = [{"nr": "9", "namn": "A", "lag": "hemma"}]
        ut = M.sla_ihop_spelare(gamla, nya)
        namn = {p["namn"] for p in ut}
        self.assertEqual(namn, {"A", "B"})

    def test_match_pa_namn_nar_nummer_saknas(self):
        # fas 1 utan nummer, fas 2 med nummer → matchas på namn
        gamla = [{"nr": "", "namn": "Ria Öling", "lag": "hemma",
                  "handle": "@riaoling", "info": "MF"}]
        nya = [{"nr": "6", "namn": "Ria Öling", "lag": "hemma"}]
        ut = M.sla_ihop_spelare(gamla, nya)
        self.assertEqual(len(ut), 1)
        self.assertEqual(ut[0]["nr"], "6")
        self.assertEqual(ut[0]["handle"], "@riaoling")       # bevarat över match


class TestRoster(unittest.TestCase):
    def test_roster_rader(self):
        sp = [{"nr": "9", "namn": "A", "lag": "hemma"},
              {"nr": "", "namn": "X", "lag": "hemma"},        # ofullständig → bort
              {"nr": "5", "namn": "B", "lag": "borta"}]
        self.assertEqual(len(M.roster_rader(sp)), 2)

    def test_skriv_csv_tre_kolumner(self):
        d = Path(tempfile.mkdtemp())
        p = M.skriv_roster_csv(
            [{"nr": "9", "namn": "A", "lag": "hemma"}], "Malmö-Kristianstad", d)
        self.assertTrue(p.endswith(".csv") and Path(p).exists())
        txt = Path(p).read_text(encoding="utf-8")
        self.assertIn("nummer,namn,lag", txt)
        self.assertIn("9,A,hemma", txt)


class TestMatchinfo(unittest.TestCase):
    def test_komponera_iso_datum(self):
        s = M.komponera_matchinfo({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstad DFF",
            "resultat": "6-0", "datum": "2026-06-27", "tid": "14:00",
            "arena": "Eleda Stadion"})
        self.assertIn("Malmö FF - Kristianstad DFF", s)
        self.assertIn("6-0", s)
        self.assertIn("20260627", s)                         # ISO → 8 siffror
        self.assertIn("Eleda Stadion", s)


class TestStatus(unittest.TestCase):
    def test_resultat_ger_avslutad(self):
        self.assertEqual(M.harled_status("2027-01-01", resultat="2-1"), "avslutad")

    def test_framtid_kommande(self):
        nu = datetime(2026, 6, 29, 12, 0)
        self.assertEqual(
            M.harled_status("2026-08-15", "15:00", nu=nu), "kommande")

    def test_forflutet_pagaende(self):
        nu = datetime(2026, 6, 27, 15, 0)
        self.assertEqual(
            M.harled_status("2026-06-27", "14:00", nu=nu), "pagaende")

    def test_override_vinner(self):
        self.assertEqual(
            M.harled_status("2026-06-27", "14:00", resultat="1-0",
                            override="kommande"), "kommande")

    def test_saknat_datum(self):
        self.assertEqual(M.harled_status("", ""), "kommande")


if __name__ == "__main__":
    unittest.main(verbosity=2)
