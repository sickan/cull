"""Lär av gallring (genvägen 24/7): manuell gallring → fullt 1/0-facit i ett
steg. Testar märkningen isolerat — extraktionen stubbas (tunga modeller körs
ALDRIG i tester), filerna är tomma attrapper i tmp-kataloger.

Kärnan som vaktas: behållna (urvalets frame-id/stam) = 1, resten = 0;
LR-exporter med tidsstämplade namn matchar tagningens NEF-stammar; tomt
urval/ingen träff lagrar INGET (allt-negativt förgiftar modellen)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dpt2.data import db
from dpt2.data import store
from dpt2.tjanster import traning


def _fejk_features(paths, modeller, env=None, sport=None):
    """Stub: en vektor per fil, stems ur filnamnen — ingen bildläsning."""
    stems = [Path(p).stem for p in paths]
    return [[0.5] * 3 for _ in stems], stems


class TestLarAvGallring(unittest.TestCase):
    def setUp(self):
        self.conn = db.oppna(":memory:")
        self.tmp = tempfile.TemporaryDirectory()
        rot = Path(self.tmp.name)
        self.tagning = rot / "tagning"
        self.urval = rot / "urval"
        self.tagning.mkdir()
        self.urval.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _fil(self, mapp, namn):
        (mapp / namn).write_bytes(b"x")

    def _kor(self, **kw):
        with mock.patch.object(traning.extraktion, "features_for_bilder",
                               _fejk_features), \
             mock.patch.object(traning.extraktion, "FEATURES", ["a", "b", "c"]):
            return traning.lar_av_gallring(self.conn, self.tagning, self.urval,
                                           modeller=None, logg=lambda *a: None,
                                           **kw)

    def test_behallna_far_1_resten_0(self):
        for n in ("DSC_0001.NEF", "DSC_0002.NEF", "DSC_0003.NEF"):
            self._fil(self.tagning, n)
        self._fil(self.urval, "DSC_0002.jpg")   # behållen, annan ändelse
        r = self._kor(namn="Höjd final", sport="friidrott")
        self.assertNotIn("fel", r)
        self.assertEqual((r["n_bilder"], r["valda"]), (3, 1))
        facit = store.lista_facit(self.conn)
        self.assertEqual(facit[0]["match_namn"], "Höjd final")
        self.assertEqual(facit[0]["n"], 3)

    def test_tidsstamplad_export_matchar_nef(self):
        # Urvalet är LR-exporter med leveransnamn — frame-id:t (Z81_1234)
        # ska matcha tagningens NEF-stam.
        self._fil(self.tagning, "Z81_1234.NEF")
        self._fil(self.tagning, "Z81_9999.NEF")
        self._fil(self.urval, "20260724135501_Z81_1234_NIKON Z 8_560 mm.jpg")
        r = self._kor(namn="Sprint")
        self.assertNotIn("fel", r)
        self.assertEqual((r["n_bilder"], r["valda"]), (2, 1))
        self.assertEqual(r.get("omatchade", 0), 0)

    def test_ingen_traff_lagrar_inget(self):
        self._fil(self.tagning, "DSC_0001.NEF")
        self._fil(self.urval, "HELT_ANNAN.jpg")
        r = self._kor()
        self.assertIn("fel", r)
        self.assertEqual(store.lista_facit(self.conn), [],
                         "allt-negativt facit får aldrig lagras")

    def test_tom_urvalsmapp_ger_fel(self):
        self._fil(self.tagning, "DSC_0001.NEF")
        r = self._kor()
        self.assertIn("fel", r)

    def test_omatchade_urvalsbilder_rapporteras(self):
        self._fil(self.tagning, "DSC_0001.NEF")
        self._fil(self.urval, "DSC_0001.jpg")
        self._fil(self.urval, "DSC_0777.jpg")   # från ett annat kort
        r = self._kor()
        self.assertEqual(r["valda"], 1)
        self.assertEqual(r["omatchade"], 1)

    def test_gallrings_id(self):
        gid = traning.gallrings_id
        self.assertEqual(gid("DSC_0001.NEF"), gid("DSC_0001.jpg"))
        self.assertEqual(gid("20260724135501_Z81_1234_NIKON Z 8_560 mm.jpg"),
                         gid("Z81_1234.NEF"))
        self.assertEqual(gid("DSC_0001-Edit.jpg"), gid("DSC_0001.NEF"))


if __name__ == "__main__":
    unittest.main()
