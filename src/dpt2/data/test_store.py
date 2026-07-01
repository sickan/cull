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

    def test_per_bild_urval_round_trip(self):
        uid = store.spara_urval(self.c, kalla="x", bilder=0)
        store.ersatt_urval_bilder(self.c, uid, [
            ("s1", 1, 0.91), ("s2", 0, 0.30), ("s3", 1, 0.77)])
        self.assertEqual(sorted(store.behall_stems(self.c, uid)), ["s1", "s3"])
        self.assertEqual(store.hamta_urval(self.c, uid)["bilder"], 2)  # behåll-antal
        # idempotent: omkörning ersätter
        store.ersatt_urval_bilder(self.c, uid, [("s1", 1, 0.91)])
        self.assertEqual(store.behall_stems(self.c, uid), ["s1"])

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

    def test_upsert_tavling_hemsida(self):
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                             hemsida="damallsvenskan.se")
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")  # rör ej
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["hemsida"], "damallsvenskan.se")   # bevarat

    def test_lag_individ(self):
        lid = store.upsert_lag(self.c, "Rebecca Peterson", kind="individ",
                               profilfarg="#2F7CB0", klubb="Sverige")
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["kind"], "individ")
        self.assertEqual(lag["profilfarg"], "#2F7CB0")
        self.assertEqual(lag["klubb"], "Sverige")
        # default kind = team
        tid = store.upsert_lag(self.c, "Malmö FF")
        self.assertEqual(store.hamta_lag(self.c, tid)["kind"], "team")

    def test_tavling_ager_sina_lag(self):
        # spara_match ska koppla hemma+borta till tävlingen (tavling_lag).
        store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "FC Rosengård",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll"})
        lag = store.lista_lag_for_tavling(self.c, "obos-damallsvenskan")
        namn = sorted(l["namn"] for l in lag)
        self.assertEqual(namn, ["FC Rosengård", "Malmö FF"])

    def test_koppla_lag_idempotent(self):
        store.upsert_lag(self.c, "HK Malmö")
        store.upsert_tavling(self.c, "Handbollsligan", sport="handboll")
        store.koppla_lag_till_tavling(self.c, "handbollsligan", "hk-malmo")
        store.koppla_lag_till_tavling(self.c, "handbollsligan", "hk-malmo")  # igen
        self.assertEqual(len(store.lista_lag_for_tavling(self.c, "handbollsligan")), 1)


    def test_innehall_round_trip(self):
        iid = store.spara_innehall(
            self.c, typ="match", status="avslutad",
            frontmatter={"titel": "A – B", "malskyttar": ["X 12'"]},
            body="Referat.")
        d = store.hamta_innehall(self.c, iid)
        self.assertEqual(d["typ"], "match")
        self.assertEqual(d["frontmatter"]["titel"], "A – B")    # json round-trip
        self.assertEqual(d["frontmatter"]["malskyttar"], ["X 12'"])
        self.assertFalse(d["publicerad"])
        self.assertEqual(len(store.lista_innehall(self.c)), 1)
        self.assertEqual(len(store.lista_innehall(self.c, typ="blogg")), 0)

    def test_innehall_export_path_och_radera(self):
        iid = store.spara_innehall(self.c, typ="event",
                                   frontmatter={"titel": "Cup"})
        store.satt_export_path(self.c, iid, "/sajt/content/event/cup.md")
        d = store.hamta_innehall(self.c, iid)
        self.assertTrue(d["publicerad"])
        self.assertEqual(d["export_path"], "/sajt/content/event/cup.md")
        store.radera_innehall(self.c, iid)
        self.assertIsNone(store.hamta_innehall(self.c, iid))


class TestMigrering(unittest.TestCase):
    def test_fresh_db_ar_v3_med_tavling_lag(self):
        c = db.oppna(":memory:")
        self.assertEqual(db.schemaversion(c), 3)
        self.assertIn("urval_bild", db.tabeller(c))
        self.assertIn("tavling_lag", db.tabeller(c))

    def test_migrera_v1_till_v3(self):
        # v1-läge: urval + register-tabellerna (som alltid funnits). Migreringen
        # kör hela kedjan v1→v3 (urval_bild + tavling_lag + nya kolumner).
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.execute("PRAGMA user_version=1")
        c.execute("CREATE TABLE urval(id TEXT PRIMARY KEY)")
        c.execute("CREATE TABLE tavling(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("CREATE TABLE lag(id TEXT PRIMARY KEY, namn TEXT)")
        db._migrera(c, 1)
        namn = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertIn("urval_bild", namn)
        self.assertIn("tavling_lag", namn)
        self.assertIn("kind", [r[1] for r in c.execute("PRAGMA table_info(lag)")])

    def test_migrera_v2_till_v3(self):
        # Bygg ett v2-läge (lag/tavling utan nya kolumner) och migrera additivt.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=2")
        c.execute("CREATE TABLE tavling(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("CREATE TABLE lag(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("INSERT INTO lag VALUES('x','X')")
        db._migrera(c, 2)
        tk = [r[1] for r in c.execute("PRAGMA table_info(lag)")]
        self.assertIn("kind", tk)
        self.assertIn("profilfarg", tk)
        self.assertIn("hemsida", [r[1] for r in c.execute("PRAGMA table_info(tavling)")])
        self.assertIn("tavling_lag", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])
        # befintliga rader får default-kind via COALESCE-läsning (kolumnen är NULL
        # för gamla rader men NOT NULL-defaulten gäller nya inserts)
        self.assertEqual(c.execute("SELECT namn FROM lag WHERE id='x'").fetchone()[0], "X")


class TestSomeMaterial(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.mid = store.spara_match(self.c, {"lag_hemma": "A", "lag_borta": "B"})

    def test_spara_och_lista_nyast_forst(self):
        store.spara_some_material(self.c, kanal="instagram", format="story",
                                  match_id=self.mid, moment="Avspark", tema="Hav",
                                  fil="/foto/b1.jpg", skapad="2026-06-30T10:00:00")
        store.spara_some_material(self.c, kanal="facebook", format="inlägg",
                                  match_id=self.mid, moment="Avspark",
                                  fil="/foto/b1.jpg", skapad="2026-06-30T11:00:00")
        rader = store.lista_some_material(self.c, self.mid)
        self.assertEqual(len(rader), 2)
        self.assertEqual(rader[0]["kanal"], "facebook")     # nyast först
        self.assertEqual(rader[1]["format"], "story")

    def test_lista_filtrerar_pa_match(self):
        store.spara_some_material(self.c, kanal="instagram", format="story",
                                  match_id=self.mid)
        self.assertEqual(store.lista_some_material(self.c, "okand-match"), [])

    def test_utan_match_id_ok(self):
        sid = store.spara_some_material(self.c, kanal="instagram", format="story")
        self.assertTrue(sid)                                # match_id=None → ingen FK


if __name__ == "__main__":
    unittest.main(verbosity=2)
