"""Tester för match-hämtning — injicerad fejk-klient, inga skarpa anrop."""

import json
import tempfile
import unittest
from pathlib import Path

from dpt2.tjanster import matchhamtning as MH


class _Block:
    def __init__(self, text):
        self.type = "text"; self.text = text


class _Svar:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]; self.stop_reason = stop_reason
        self.usage = None


class _Messages:
    def __init__(self, svar):
        self.svar = list(svar); self.anrop = 0; self.sista_kw = None

    def create(self, **kw):
        self.sista_kw = kw
        s = self.svar[self.anrop]; self.anrop += 1; return s


class _Klient:
    def __init__(self, svar):
        self.messages = _Messages(svar)

    def _content_text(self):
        c = self.messages.sista_kw["messages"][0]["content"]
        return c if isinstance(c, str) else json.dumps(c)


class TestKlubb(unittest.TestCase):
    def test_kand_och_okand(self):
        self.assertEqual(MH.klubb("FC Rosengård")["ig"], "fcrosengard")
        self.assertEqual(MH.klubb("Okänt Lag"), {})


class TestHamtaSpelare(unittest.TestCase):
    def test_returnerar_data_och_url_i_prompt(self):
        kl = _Klient([_Svar('{"spelare": [{"nr":"9","namn":"A","lag":"hemma"}]}')])
        d = MH.hamta_spelare("FC Rosengård", "Okänt Lag",
                             logg=lambda *_: None, klient=kl)
        self.assertEqual(len(d["spelare"]), 1)
        prompt = kl._content_text()
        self.assertIn("fcrosengard.se", prompt)              # känd → URL
        self.assertIn("hitta officiell truppsida", prompt)   # okänd → fallback
        self.assertIn("tools", kl.messages.sista_kw)         # web_search

    def test_inget_lag(self):
        self.assertIsNone(MH.hamta_spelare("", "", logg=lambda *_: None,
                                           klient=_Klient([])))


class TestHamtaUppstallning(unittest.TestCase):
    def test_matches_url_i_prompt(self):
        kl = _Klient([_Svar('{"spelare": [{"nr":"9","namn":"A","lag":"hemma",'
                            '"start":true}]}')])
        d = MH.hamta_uppstallning("FC Rosengård", "Eskilstuna United",
                                  datum="2026-08-15", logg=lambda *_: None, klient=kl)
        self.assertEqual(len(d["spelare"]), 1)
        self.assertIn("fcrosengard.se/sv/matches", kl._content_text())


class TestLasLineup(unittest.TestCase):
    def test_pdf_block(self):
        p = Path(tempfile.mkdtemp()) / "ark.pdf"
        p.write_bytes(b"%PDF-1.4 fejk")
        block = MH._innehall_block(p)
        self.assertEqual(block["type"], "document")
        self.assertEqual(block["source"]["media_type"], "application/pdf")

    def test_okant_format(self):
        p = Path(tempfile.mkdtemp()) / "ark.txt"
        p.write_text("x")
        self.assertIsNone(MH._innehall_block(p))

    def test_las_flode_med_pdf(self):
        p = Path(tempfile.mkdtemp()) / "ark.pdf"
        p.write_bytes(b"%PDF-1.4 fejk")
        kl = _Klient([_Svar('{"matchinfo":"(D) A - B 20260609 Arena",'
                            '"spelare":[{"nr":"12","namn":"X","lag":"hemma"}]}')])
        d = MH.las_lineup(p, logg=lambda *_: None, klient=kl)
        self.assertEqual(d["matchinfo"], "(D) A - B 20260609 Arena")
        # första content-blocket ska vara PDF-dokumentet
        innehall = kl.messages.sista_kw["messages"][0]["content"]
        self.assertEqual(innehall[0]["type"], "document")

    def test_okant_format_ger_none_utan_anrop(self):
        p = Path(tempfile.mkdtemp()) / "ark.txt"; p.write_text("x")
        kl = _Klient([])
        self.assertIsNone(MH.las_lineup(p, logg=lambda *_: None, klient=kl))
        self.assertEqual(kl.messages.anrop, 0)               # inget anrop


class TestHamtaTruppForLag(unittest.TestCase):
    def test_explicit_url_i_prompt(self):
        kl = _Klient([_Svar('{"lag":"Malmö FF","spelare":'
                            '[{"nr":"1","namn":"Musovic","position":"Målvakt"}]}')])
        d = MH.hamta_trupp_for_lag("Malmö FF", url="https://malmoff.se/truppen",
                                   logg=lambda *_: None, klient=kl)
        self.assertEqual(len(d["spelare"]), 1)
        self.assertIn("malmoff.se/truppen", kl._content_text())
        self.assertIn("tools", kl.messages.sista_kw)         # web_search

    def test_klubbregister_url_som_fallback(self):
        kl = _Klient([_Svar('{"spelare":[{"nr":"9","namn":"A"}]}')])
        MH.hamta_trupp_for_lag("FC Rosengård", logg=lambda *_: None, klient=kl)
        self.assertIn("fcrosengard.se", kl._content_text())  # ur KLUBBAR

    def test_inget_lag(self):
        self.assertIsNone(MH.hamta_trupp_for_lag("", logg=lambda *_: None,
                                                 klient=_Klient([])))


class TestLasTruppFil(unittest.TestCase):
    def test_las_trupp_pdf(self):
        p = Path(tempfile.mkdtemp()) / "trupp.pdf"
        p.write_bytes(b"%PDF-1.4 fejk")
        kl = _Klient([_Svar('{"lag":"Malmö FF","spelare":'
                            '[{"nr":"1","namn":"Musovic","position":"Målvakt"}]}')])
        d = MH.las_trupp_fil(p, logg=lambda *_: None, klient=kl)
        self.assertEqual(d["spelare"][0]["position"], "Målvakt")
        innehall = kl.messages.sista_kw["messages"][0]["content"]
        self.assertEqual(innehall[0]["type"], "document")

    def test_okant_format(self):
        p = Path(tempfile.mkdtemp()) / "trupp.txt"; p.write_text("x")
        self.assertIsNone(MH.las_trupp_fil(p, logg=lambda *_: None,
                                           klient=_Klient([])))


class TestTolkaTruppCsv(unittest.TestCase):
    def _skriv(self, text):
        p = Path(tempfile.mkdtemp()) / "trupp.csv"
        p.write_text(text, encoding="utf-8")
        return p

    def test_rubrikrad_mappas(self):
        p = self._skriv("Nr,Namn,Position\n1,Zecira Musovic,Målvakt\n"
                        "9,Anna Anvegård,Forward\n")
        d = MH.tolka_trupp_csv(p, logg=lambda *_: None)
        self.assertEqual(len(d["spelare"]), 2)
        self.assertEqual(d["spelare"][0],
                         {"nr": "1", "namn": "Zecira Musovic",
                          "position": "Målvakt"})

    def test_semikolon_och_engelska_rubriker(self):
        p = self._skriv("number;name;pos\n7;Ria Öling;Mittfältare\n")
        d = MH.tolka_trupp_csv(p, logg=lambda *_: None)
        self.assertEqual(d["spelare"][0]["namn"], "Ria Öling")
        self.assertEqual(d["spelare"][0]["position"], "Mittfältare")

    def test_utan_rubrik_antas_kolumnordning(self):
        p = self._skriv("1,Zecira Musovic,Målvakt\n9,Anna Anvegård,Forward\n")
        d = MH.tolka_trupp_csv(p, logg=lambda *_: None)
        self.assertEqual(len(d["spelare"]), 2)
        self.assertEqual(d["spelare"][1]["nr"], "9")

    def test_tom_fil(self):
        self.assertIsNone(MH.tolka_trupp_csv(self._skriv(""),
                                             logg=lambda *_: None))

    def test_saknad_fil(self):
        self.assertIsNone(MH.tolka_trupp_csv("/finns/inte.csv",
                                             logg=lambda *_: None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
