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


class TestMatchCRUD(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.match = {
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "datum": "2026-06-27", "tid": "14:00", "arena": "Eleda Stadion",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "resultat": "6-0",
            "spelare": [
                {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma",
                 "handle": "@zm", "info": "MV", "start": True},
                {"nr": "9", "namn": "Mia", "lag": "hemma", "start": False},
                {"nr": "7", "namn": "Borta-spelare", "lag": "borta"},
            ],
        }

    def test_round_trip(self):
        mid = store.spara_match(self.c, self.match)
        m = store.hamta_match(self.c, mid)
        self.assertEqual(m["lag_hemma"], "Malmö FF")
        self.assertEqual(m["liga"], "OBOS Damallsvenskan")
        self.assertEqual(m["status"], "avslutad")            # resultat satt
        self.assertEqual(len(m["spelare"]), 3)
        zm = next(p for p in m["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["lag"], "hemma")                 # sida härledd ur lag_id
        self.assertEqual(zm["handle"], "@zm")
        self.assertTrue(zm["start"])
        borta = next(p for p in m["spelare"] if p["nr"] == "7")
        self.assertEqual(borta["lag"], "borta")

    def test_delad_slug_id(self):
        store.spara_match(self.c, self.match)
        self.assertIsNotNone(store.hamta_lag(self.c, "malmo-ff"))   # samma som migrera
        self.assertIsNotNone(store.hamta_lag(self.c, "kristianstads-dff"))

    def test_status_harleds(self):
        m = dict(self.match); m["resultat"] = ""; m["datum"] = "2027-01-01"
        mid = store.spara_match(self.c, m)
        self.assertEqual(store.hamta_match(self.c, mid)["status"], "kommande")

    def test_redigera_tar_bort_spelare(self):
        mid = store.spara_match(self.c, self.match)
        m = store.hamta_match(self.c, mid)
        m["spelare"] = [p for p in m["spelare"] if p["nr"] != "9"]   # ta bort Mia
        store.spara_match(self.c, m)
        kvar = store.hamta_match(self.c, mid)["spelare"]
        self.assertEqual(len(kvar), 2)
        self.assertNotIn("9", {p["nr"] for p in kvar})

    def test_lista_matcher(self):
        store.spara_match(self.c, self.match)
        rad = store.lista_matcher(self.c)[0]
        self.assertEqual(rad["lag_hemma"], "Malmö FF")
        self.assertEqual(rad["liga"], "OBOS Damallsvenskan")

    def test_radera(self):
        mid = store.spara_match(self.c, self.match)
        store.radera_match(self.c, mid)
        self.assertIsNone(store.hamta_match(self.c, mid))

    def test_merge_in_trupp(self):
        mid = store.spara_match(self.c, self.match)        # 3 spelare
        # "hämtad" trupp: uppdaterar #1 (saknar handle→bevaras) + ny spelare #14
        nya = [
            {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma"},
            {"nr": "14", "namn": "Ny Spelare", "lag": "hemma", "handle": "@ny"},
        ]
        uppd = store.merge_in_trupp(self.c, mid, nya)
        nrs = {p["nr"] for p in uppd["spelare"]}
        self.assertIn("14", nrs)                            # ny tillagd
        zm = next(p for p in uppd["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["handle"], "@zm")              # bevarat över merge
        self.assertIn("9", nrs)                            # gammal kvar

    def test_merge_okand_match(self):
        self.assertIsNone(store.merge_in_trupp(self.c, "finns-ej", []))


class TestLagTavling(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_upsert_lag_uppdaterar_utan_att_nolla(self):
        lid = store.upsert_lag(self.c, "Malmö FF", instagram="@malmoff")
        store.upsert_lag(self.c, "Malmö FF", logga="/x.png")   # bara logga
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["instagram"], "@malmoff")          # bevarat
        self.assertEqual(lag["logga"], "/x.png")                # tillagt

    def test_upsert_tavling(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        self.assertEqual(tid, "obos-damallsvenskan")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)

    def test_upsert_tavling_uppdaterar(self):
        store.upsert_tavling(self.c, "EM Volley", sport="fotboll", typ="liga")
        store.upsert_tavling(self.c, "EM Volley", sport="volleyboll", typ="masterskap")
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["sport"], "volleyboll")     # uppdaterat
        self.assertEqual(t["typ"], "masterskap")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)   # ingen dubblett

    def test_radera_lag_och_tavling(self):
        store.upsert_lag(self.c, "HK Malmö")
        store.upsert_tavling(self.c, "Handbollsligan", sport="handboll")
        store.radera_lag(self.c, "hk-malmo")
        store.radera_tavling(self.c, "handbollsligan")
        self.assertEqual(store.lista_lag(self.c), [])
        self.assertEqual(store.lista_tavlingar(self.c), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
