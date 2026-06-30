"""Tester för pywebview-bryggan (Api) — mot in-memory DB, inget fönster."""

import unittest

from dpt2.app import Api, _gallring_av_config
from dpt2.data import store


class TestApi(unittest.TestCase):
    def setUp(self):
        # En delad in-memory-anslutning (Api håller self.conn).
        self.api = Api(db_path=":memory:")

    def test_info(self):
        info = self.api.info()
        self.assertEqual(info["schemaversion"], 1)

    def test_match_round_trip_genom_bryggan(self):
        res = self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "datum": "2026-06-27", "tid": "14:00", "arena": "Eleda Stadion",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "resultat": "6-0",
            "spelare": [
                {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma",
                 "handle": "@zm", "info": "MV", "start": True},
                {"nr": "9", "namn": "Borta-spelare", "lag": "borta"},
            ],
        })
        self.assertTrue(res["ok"])
        mid = res["id"]

        lista = self.api.lista_matcher()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["lag_hemma"], "Malmö FF")
        self.assertEqual(lista[0]["status"], "avslutad")     # resultat satt

        full = self.api.hamta_match(mid)
        self.assertEqual(len(full["spelare"]), 2)
        zm = next(p for p in full["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["lag"], "hemma")
        self.assertEqual(zm["handle"], "@zm")
        self.assertTrue(zm["start"])

    def test_lag_och_tavling_register(self):
        self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "datum": "2026-06-27",
        })
        lag = self.api.lista_lag()
        self.assertEqual({l["namn"] for l in lag},
                         {"Malmö FF", "Kristianstads DFF"})
        tav = self.api.lista_tavlingar()
        self.assertEqual(tav[0]["namn"], "OBOS Damallsvenskan")

    def test_spara_lag_direkt(self):
        res = self.api.spara_lag({"namn": "HK Malmö", "instagram": "@hkmhandboll"})
        self.assertEqual(res["id"], "hk-malmo")
        self.assertEqual(self.api.lista_lag()[0]["instagram"], "@hkmhandboll")

    def test_radera(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        self.api.radera_match(mid)
        self.assertEqual(self.api.lista_matcher(), [])

    def test_aktiv_match(self):
        self.assertIsNone(self.api.aktiv_match())
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        res = self.api.satt_aktiv_match(mid)
        self.assertTrue(res["ok"])
        self.assertEqual(self.api.aktiv_match()["id"], mid)

    def test_starta_cull_skapar_urval_och_jobb(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        res = self.api.starta_cull({
            "kalla": "/Volumes/NIKON/DCIM", "match_id": mid, "kamera": "NIKON Z 8",
            "behall_varde": 40, "behall_enhet": "bilder", "verktyg": "ai",
            "modell": "din_smak", "burst": 2.0})
        self.assertTrue(res["ok"])
        u = store.hamta_urval(self.api.conn, res["urval_id"])
        self.assertEqual(u["match_id"], mid)
        self.assertEqual(u["kamera"], "NIKON Z 8")
        jobb = store.jobb_for_urval(self.api.conn, res["urval_id"])
        self.assertEqual(jobb[0]["behall_varde"], 40.0)
        self.assertEqual(jobb[0]["behall_enhet"], "bilder")


    def test_leverera_urval_skriver_sidecars_och_satter_status(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        (d / "DSC_0001.nef").write_bytes(b"")
        (d / "DSC_0002.nef").write_bytes(b"")
        uid = store.spara_urval(self.api.conn, kalla=str(d), bilder=2)
        res = self.api.leverera_urval(uid, {"exp_bump": 0.3})
        self.assertTrue(res["ok"])
        self.assertEqual(res["skrivna"], 2)
        self.assertEqual(res["status"], "levererad")
        self.assertTrue((d / "DSC_0001.xmp").exists())
        self.assertEqual(store.hamta_urval(self.api.conn, uid)["status"],
                         "levererad")

    def test_leverera_urval_tom_mapp(self):
        import tempfile
        uid = store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(), bilder=0)
        res = self.api.leverera_urval(uid)
        self.assertFalse(res["ok"])
        # status oförändrad när inget levererades
        self.assertEqual(store.hamta_urval(self.api.conn, uid)["status"],
                         "gallrad")

    def test_leverera_okant_urval(self):
        self.assertFalse(self.api.leverera_urval("finns-inte")["ok"])

    def test_lista_urval_med_matchetikett_och_statusfilter(self):
        import tempfile
        mid = self.api.spara_match({"lag_hemma": "Malmö FF", "lag_borta": "KDFF",
                                    "datum": "2026-06-27"})["id"]
        u1 = store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(),
                               bilder=10, match_id=mid)
        store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(), bilder=5)
        alla = self.api.lista_urval()
        self.assertEqual(len(alla), 2)
        rad = next(u for u in alla if u["id"] == u1)
        self.assertEqual(rad["lag_hemma"], "Malmö FF")     # join mot matchen
        # statusfilter
        store.satt_urval_status(self.api.conn, u1, "levererad")
        lev = self.api.lista_urval("levererad")
        self.assertEqual([u["id"] for u in lev], [u1])


    def test_skapa_story_kraver_moment(self):
        self.assertFalse(self.api.skapa_story({})["ok"])
        res = self.api.skapa_story({"moment": "Avspark", "tema": "Sol", "format": "4x5"})
        self.assertTrue(res["ok"])
        self.assertIn("Avspark", res["meddelande"])

    def test_generera_bildsvep_utan_nyckel(self):
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.skipTest("API-nyckel satt — skarp väg testas ej här")
        res = self.api.generera_bildsvep("Malmö FF–Växjö DFF 3–0", "fotboll")
        self.assertFalse(res["ok"])           # ingen nyckel → snäll fallback


    def test_innehall_spara_forhandsgranska_lista(self):
        data = {"typ": "match", "titel": "Malmö FF – KDFF", "resultat": "6-0",
                "malskyttar": "Musovic 12', Persson 45'", "body": "Referat.",
                "figurer": [{"bild": "1.jpg", "alt": "jubel", "bildtext": "Segern"}]}
        pre = self.api.forhandsgranska_innehall(data)
        self.assertEqual(pre["slug"], "malmo-ff-kdff")
        self.assertIn("titel: Malmö FF – KDFF", pre["md"])
        self.assertIn("![jubel](1.jpg)", pre["md"])
        res = self.api.spara_innehall(data)
        self.assertTrue(res["ok"])
        lst = self.api.lista_innehall()
        self.assertEqual(lst[0]["frontmatter"]["malskyttar"], ["Musovic 12'", "Persson 45'"])

    def test_innehall_exportera_skriver_md(self):
        import tempfile
        d = tempfile.mkdtemp()
        data = {"typ": "event", "titel": "Sommarcup 2026", "body": "Text."}
        res = self.api.exportera_innehall(data, d)
        self.assertTrue(res["ok"])
        self.assertTrue(res["path"].endswith("sommarcup-2026.md"))
        from pathlib import Path
        self.assertIn("typ: event", Path(res["path"]).read_text(encoding="utf-8"))
        # markerat publicerat i datalagret
        self.assertTrue(self.api.lista_innehall()[0]["publicerad"])

    def test_innehall_export_utan_katalog(self):
        self.assertFalse(self.api.exportera_innehall({"titel": "X"}, "")["ok"])


    def test_modell_bibliotek_och_vaxling(self):
        a = store.spara_modell(self.api.conn, typ="din_smak",
                               pkl_path="/m/dinsmak.pkl", n_uppdrag=18, aktiv=True)
        b = store.spara_modell(self.api.conn, typ="arkiv", pkl_path="/m/arkiv.pkl")
        self.assertEqual(len(self.api.lista_modeller()), 2)
        self.assertEqual(self.api.aktiv_modell()["id"], a)
        res = self.api.satt_aktiv_modell(b)
        self.assertTrue(res["ok"])
        self.assertEqual(res["aktiv"]["id"], b)
        self.assertEqual(self.api.aktiv_modell()["id"], b)   # bara en aktiv
        self.assertFalse(self.api.satt_aktiv_modell("finns-inte")["ok"])

    def test_starta_omrakna_utan_root(self):
        self.assertFalse(self.api.starta_omrakna_arkiv("")["ok"])


    def test_logg_kor_demo_buffrar_och_rensar(self):
        res = self.api.kor_demo_jobb(3)
        self.assertTrue(res["ok"])
        typer = [e["typ"] for e in res["events"]]
        self.assertEqual(typer[0], "start")
        self.assertIn("klar", typer)
        # buffrat i appen → Logg-panelen kan hämta
        self.assertEqual(self.api.hamta_logg(), res["events"])
        self.api.rensa_logg()
        self.assertEqual(self.api.hamta_logg(), [])


class TestGallringConfig(unittest.TestCase):
    def test_bilder_ger_topp(self):
        g = _gallring_av_config({"behall_enhet": "bilder", "behall_varde": 40,
                                 "verktyg": "ai", "burst": 2.0})
        self.assertEqual(g.topp, 40)
        self.assertTrue(g.ai)

    def test_procent_ger_andel(self):
        g = _gallring_av_config({"behall_enhet": "procent", "behall_varde": 25,
                                 "verktyg": "rapport"})
        self.assertAlmostEqual(g.andel, 0.25)
        self.assertIsNone(g.topp)
        self.assertFalse(g.ai)          # rapport → ai=False


if __name__ == "__main__":
    unittest.main(verbosity=2)
