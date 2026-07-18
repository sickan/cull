"""Tester för original-hemhämtningen (tjanster/original_synk.py, FEAT-15).

Tyngdpunkt: idempotensen (avbruten omgång ska kunna köras om utan att dra om
30 MB-filer) och att fel på EN fil aldrig äter resten av omgången.
"""

import tempfile
import unittest
from pathlib import Path

from dpt2.tjanster.original_synk import OriginalSynk


def fake_transport(svar):
    """{(metod, path): (status, data)} → transport som slår upp i tabellen."""
    anrop = []

    def _t(metod, url, *, headers=None, timeout=None):
        path = url.split("workers.dev")[-1]
        anrop.append((metod, path, headers))
        return svar.get((metod, path), (404, None))
    _t.anrop = anrop
    return _t


class TestListning(unittest.TestCase):
    def test_lista_mappar_och_filer(self):
        t = fake_transport({
            ("GET", "/api/original"): (200, {"mappar": ["osorterat", "mff"]}),
            ("GET", "/api/original/mff"): (200, {"filer": [
                {"filnamn": "Z81_1.NEF", "bytes": 31457280,
                 "uppladdad": "2026-07-17T23:01:16.474Z"}]}),
        })
        s = OriginalSynk(api_key="k", transport=t)
        self.assertEqual(s.lista_mappar(), ["osorterat", "mff"])
        self.assertEqual(s.lista_filer("mff")[0]["filnamn"], "Z81_1.NEF")

    def test_utan_nyckel_tomt_och_inga_anrop(self):
        t = fake_transport({})
        s = OriginalSynk(api_key="", transport=t)
        self.assertEqual(s.lista_mappar(), [])
        self.assertEqual(s.lista_filer("x"), [])
        self.assertEqual(t.anrop, [])

    def test_bearer_header_medfoljer(self):
        t = fake_transport({("GET", "/api/original"): (200, {"mappar": []})})
        OriginalSynk(api_key="hemlis", transport=t).lista_mappar()
        self.assertEqual(t.anrop[0][2]["Authorization"], "Bearer hemlis")


class TestHamtning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mal = Path(self.tmp.name) / "ut"

    def tearDown(self):
        self.tmp.cleanup()

    def test_hamtar_och_skriver(self):
        def nedladdare(url, headers, malfil):
            malfil.write_bytes(b"NEFDATA")
            return 7
        s = OriginalSynk(api_key="k", nedladdare=nedladdare)
        r = s.hamta_fil("mff", "Z81_1.NEF", self.mal)
        self.assertTrue(r["ok"])
        self.assertFalse(r["hoppad"])
        self.assertEqual((self.mal / "Z81_1.NEF").read_bytes(), b"NEFDATA")

    def test_idempotent_hoppar_ratt_storlek(self):
        self.mal.mkdir(parents=True)
        (self.mal / "Z81_1.NEF").write_bytes(b"1234567")
        kallad = []
        s = OriginalSynk(api_key="k",
                         nedladdare=lambda *a: kallad.append(a))
        r = s.hamta_fil("mff", "Z81_1.NEF", self.mal, bytes_vantat=7)
        self.assertTrue(r["ok"])
        self.assertTrue(r["hoppad"])
        self.assertEqual(kallad, [])   # ingen nedladdning gjordes

    def test_fel_storlek_dras_om(self):
        self.mal.mkdir(parents=True)
        (self.mal / "Z81_1.NEF").write_bytes(b"halv")   # trasig/halv fil

        def nedladdare(url, headers, malfil):
            malfil.write_bytes(b"HELFILEN")
            return 8
        s = OriginalSynk(api_key="k", nedladdare=nedladdare)
        r = s.hamta_fil("mff", "Z81_1.NEF", self.mal, bytes_vantat=8)
        self.assertTrue(r["ok"])
        self.assertFalse(r["hoppad"])
        self.assertEqual((self.mal / "Z81_1.NEF").read_bytes(), b"HELFILEN")

    def test_nedladdningsfel_ger_fel_inte_undantag(self):
        def nedladdare(url, headers, malfil):
            raise RuntimeError("HTTP 500")
        s = OriginalSynk(api_key="k", nedladdare=nedladdare)
        r = s.hamta_fil("mff", "Z81_1.NEF", self.mal)
        self.assertFalse(r["ok"])
        self.assertIn("Z81_1.NEF", r["fel"])

    def test_radera(self):
        t = fake_transport({
            ("DELETE", "/api/original/mff/Z81_1.NEF"): (200, {"ok": True})})
        s = OriginalSynk(api_key="k", transport=t)
        self.assertTrue(s.radera_fil("mff", "Z81_1.NEF"))
        self.assertFalse(s.radera_fil("mff", "finns_ej.NEF"))


if __name__ == "__main__":
    unittest.main()
