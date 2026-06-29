"""Tester för pywebview-bryggan (Api) — mot in-memory DB, inget fönster."""

import unittest

from dpt2.app import Api


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
