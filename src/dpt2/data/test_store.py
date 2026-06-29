"""Tester för datalager-CRUD (store) — körs mot in-memory SQLite (stdlib)."""

import unittest

from dpt2.data import db, store
from dpt2.motorer.gallring import Gallring


class TestUrval(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_spara_och_hamta(self):
        uid = store.spara_urval(self.c, kalla="/Volumes/NIKON/DCIM", bilder=40,
                                kamera="NIKON Z 8")
        u = store.hamta_urval(self.c, uid)
        self.assertEqual(u["bilder"], 40)
        self.assertEqual(u["kamera"], "NIKON Z 8")
        self.assertEqual(u["status"], "gallrad")      # default

    def test_status_livscykel(self):
        uid = store.spara_urval(self.c, kalla="x", bilder=10)
        store.satt_urval_status(self.c, uid, "levererad")
        self.assertEqual(store.hamta_urval(self.c, uid)["status"], "levererad")
        store.satt_urval_status(self.c, uid, "publicerad")
        self.assertEqual(store.hamta_urval(self.c, uid)["status"], "publicerad")
        with self.assertRaises(ValueError):
            store.satt_urval_status(self.c, uid, "trams")

    def test_koppling_till_match(self):
        # match kräver en rad i matchen (FK). Lägg en minimal match.
        self.c.execute("INSERT INTO matchen(id,skapad) VALUES('m1','2026-06-29')")
        uid = store.spara_urval(self.c, match_id="m1", kalla="x", bilder=5)
        self.assertEqual(store.urval_for_match(self.c, "m1")[0]["id"], uid)

    def test_ogiltig_status_avvisas_av_check(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            store.spara_urval(self.c, kalla="x", bilder=1, status="fel")


class TestCullJobb(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.uid = store.spara_urval(self.c, kalla="x", bilder=40)

    def test_fran_gallring_topp(self):
        cfg = Gallring(topp=40, burst_sek=2.0, bevaka={"10"})
        jid = store.cull_jobb_fran_gallring(self.c, self.uid, cfg, verktyg="ai")
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(j["id"], jid)
        self.assertEqual(j["behall_varde"], 40.0)
        self.assertEqual(j["behall_enhet"], "bilder")
        self.assertEqual(j["trojnummer_ocr"], 1)       # bevaka satt
        self.assertEqual(j["burst_grans"], 2.0)

    def test_fran_gallring_andel(self):
        cfg = Gallring(topp=None, andel=0.25)
        store.cull_jobb_fran_gallring(self.c, self.uid, cfg)
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(j["behall_varde"], 25.0)
        self.assertEqual(j["behall_enhet"], "procent")

    def test_vikter_json(self):
        jid = store.spara_cull_jobb(self.c, urval_id=self.uid, verktyg="ai",
                                    vikter={"pose": 60, "skarpa": 70})
        import json
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(json.loads(j["vikter"])["skarpa"], 70)

    def test_cull_jobb_kraver_giltig_urval_fk(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            store.spara_cull_jobb(self.c, urval_id="finns-ej", verktyg="ai")


if __name__ == "__main__":
    unittest.main(verbosity=2)
