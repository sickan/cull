"""Tester för Mobil Live-synken (tjanster/live_synk.py).

Tyngdpunkt: målskyttar-konverteringen (sträng ⇄ poster) och tidsstämpel-
formatet, som båda är tysta felkällor mot workerns fältvisa LWW.
"""

import unittest

from dpt2.tjanster.live_synk import (
    GREN_FARG, LiveSynk, iso_nu, malskyttar_till_poster, poster_till_malskyttar,
)


class TestIsoNu(unittest.TestCase):
    def test_slutar_med_z_inte_offset(self):
        # Workern jämför fältstämplar LEXIKOGRAFISKT. '+' (0x2B) < 'Z' (0x5A),
        # så ett '+00:00'-format skulle få desktop att alltid förlora mot
        # mobilens toISOString()-stämplar.
        t = iso_nu()
        self.assertTrue(t.endswith("Z"), t)
        self.assertNotIn("+00:00", t)

    def test_millisekunder_som_js_toisostring(self):
        t = iso_nu()  # 2026-07-10T05:00:15.706Z
        self.assertRegex(t, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_sorterar_lexikografiskt_mot_js_stampel(self):
        js_gammal = "2026-07-10T04:00:00.000Z"
        self.assertGreater(iso_nu(), js_gammal)


class TestMalskyttarTillPoster(unittest.TestCase):
    def test_namn_och_minut(self):
        p = malskyttar_till_poster("Ivanovic 10', Milivojevic 28'")
        self.assertEqual([(x["namn"], x["minut"]) for x in p],
                         [("Ivanovic", 10), ("Milivojevic", 28)])

    def test_foljdmal_utan_namn_hor_till_foregaende(self):
        # Appens konvention: "Kanutte Fornes 50', 58', 80'" = tre mål, en spelare
        p = malskyttar_till_poster("Kanutte Fornes 50', 58', 80'")
        self.assertEqual([(x["namn"], x["minut"]) for x in p],
                         [("Kanutte Fornes", 50), ("Kanutte Fornes", 58),
                          ("Kanutte Fornes", 80)])

    def test_mal_utan_minut(self):
        # Mobilen får spara mål utan minut (fylls i senare)
        p = malskyttar_till_poster("Berg")
        self.assertEqual(p, [{"namn": "Berg", "minut": None, "lag": None, "nr": None}])

    def test_blandat_med_och_utan_minut(self):
        p = malskyttar_till_poster("Hansson 14', Berg")
        self.assertEqual([(x["namn"], x["minut"]) for x in p],
                         [("Hansson", 14), ("Berg", None)])

    def test_tom_strang(self):
        self.assertEqual(malskyttar_till_poster(""), [])
        self.assertEqual(malskyttar_till_poster(None), [])

    def test_prime_tecken_bade_apostrof_och_u2032(self):
        p = malskyttar_till_poster("Hansson 14′, Berg 20'")
        self.assertEqual([(x["namn"], x["minut"]) for x in p],
                         [("Hansson", 14), ("Berg", 20)])

    def test_minut_utan_foregaende_namn_hoppas(self):
        self.assertEqual(malskyttar_till_poster("58'"), [])

    def test_bevarar_lag_och_nr_fran_tidigare_poster(self):
        # Desktop-strängen kan inte uttrycka lag/nr — de får inte tappas när
        # användaren redigerar strängen på datorn.
        tidigare = [{"namn": "Hansson", "minut": 14, "lag": "hemma", "nr": 7},
                    {"namn": "Berg", "minut": None, "lag": "hemma", "nr": 9}]
        p = malskyttar_till_poster("Hansson 14', Berg 20'", tidigare)
        self.assertEqual(p[0]["lag"], "hemma")
        self.assertEqual(p[0]["nr"], 7)
        self.assertEqual(p[1]["nr"], 9)
        self.assertEqual(p[1]["minut"], 20)   # ny minut vinner över gamla None

    def test_svenska_tecken_i_namn(self):
        p = malskyttar_till_poster("Öberg 5', Sjöström 12'")
        self.assertEqual([x["namn"] for x in p], ["Öberg", "Sjöström"])


class TestPosterTillMalskyttar(unittest.TestCase):
    def test_grupperar_foljdmal(self):
        poster = [{"namn": "Kanutte Fornes", "minut": 50},
                  {"namn": "Kanutte Fornes", "minut": 58},
                  {"namn": "Kanutte Fornes", "minut": 80}]
        self.assertEqual(poster_till_malskyttar(poster),
                         "Kanutte Fornes 50', 58', 80'")

    def test_mal_utan_minut_blir_bara_namn(self):
        self.assertEqual(poster_till_malskyttar([{"namn": "Berg", "minut": None}]), "Berg")

    def test_hoppar_namnlosa_poster(self):
        self.assertEqual(poster_till_malskyttar([{"namn": "", "minut": 5}]), "")

    def test_tom_lista(self):
        self.assertEqual(poster_till_malskyttar([]), "")
        self.assertEqual(poster_till_malskyttar(None), "")


class TestRundtur(unittest.TestCase):
    """Sträng → poster → sträng måste vara stabilt för appens kanoniska format."""

    def test_rundtur_kanoniska_former(self):
        for raw in ["Ivanovic 10', Milivojevic 28'",
                    "Kanutte Fornes 50', 58', 80'",
                    "Hansson 14', Berg",
                    "Berg",
                    ""]:
            self.assertEqual(poster_till_malskyttar(malskyttar_till_poster(raw)),
                             raw, f"rundtur bröts för {raw!r}")

    def test_rundtur_mobilens_poster(self):
        # Så som PWA:n skickar upp dem
        poster = [{"namn": "Hansson", "minut": 14, "lag": "hemma", "nr": 7},
                  {"namn": "Berg", "minut": None, "lag": "hemma", "nr": 9}]
        s = poster_till_malskyttar(poster)
        self.assertEqual(s, "Hansson 14', Berg")
        self.assertEqual([(p["namn"], p["minut"]) for p in malskyttar_till_poster(s, poster)],
                         [("Hansson", 14), ("Berg", None)])


class FejkTransport:
    def __init__(self, svar=None):
        self.anrop = []
        self.svar = svar or {}

    def __call__(self, metod, url, *, headers=None, body=None, timeout=15):
        self.anrop.append({"metod": metod, "url": url, "headers": headers, "body": body})
        return self.svar.get((metod, url.split(".dev")[-1] or url), (200, {}))


class TestLiveSynk(unittest.TestCase):
    def _synk(self, svar=None):
        t = FejkTransport(svar)
        return LiveSynk(bas_url="https://x.dev", api_key="k", transport=t), t

    def test_utan_nyckel_skriver_inte(self):
        s = LiveSynk(bas_url="https://x.dev", api_key="", transport=FejkTransport())
        self.assertFalse(s.har_nyckel())
        self.assertFalse(s.push_falt("m1", {"resultat": "1-0"})["ok"])
        self.assertEqual(s.lista(), [])
        self.assertIsNone(s.hamta("m1"))

    def test_push_falt_skickar_tid_per_falt(self):
        s, t = self._synk({("PUT", "/api/live/m1"): (200, {"live": {"resultat": "1-0"}})})
        r = s.push_falt("m1", {"resultat": "1-0", "moment": "Avspark"})
        self.assertTrue(r["ok"])
        body = t.anrop[0]["body"]
        self.assertEqual(body["falt"], {"resultat": "1-0", "moment": "Avspark"})
        self.assertEqual(set(body["tid"]), {"resultat", "moment"})
        for v in body["tid"].values():
            self.assertTrue(v.endswith("Z"))

    def test_push_falt_egen_tid_bevaras(self):
        s, t = self._synk({("PUT", "/api/live/m1"): (200, {"live": {}})})
        s.push_falt("m1", {"resultat": "2-0"}, tid={"resultat": "2026-01-01T00:00:00.000Z"})
        self.assertEqual(t.anrop[0]["body"]["tid"]["resultat"], "2026-01-01T00:00:00.000Z")

    def test_push_falt_svaljer_natverksfel(self):
        class Trasig:
            def __call__(self, *a, **k):
                raise OSError("nät nere")
        s = LiveSynk(bas_url="https://x.dev", api_key="k", transport=Trasig())
        r = s.push_falt("m1", {"resultat": "1-0"})
        self.assertFalse(r["ok"])          # aldrig ett undantag upp i UI:t
        self.assertIn("nät nere", r["fel"])

    def test_hamta_tomt_state_ger_none(self):
        s, _ = self._synk({("GET", "/api/live/m1"): (200, {"live": None, "match_id": "m1"})})
        self.assertIsNone(s.hamta("m1"))

    def test_push_paket_lyfter_avspark(self):
        s, t = self._synk({("PUT", "/api/live/m1/paket"): (200, {})})
        s.push_paket("m1", {"lag_hemma": "MFF", "avspark": "2026-07-31T18:00:00+02:00"})
        self.assertEqual(t.anrop[0]["body"]["avspark"], "2026-07-31T18:00:00+02:00")

    def test_radera_paket_idempotent(self):
        s, _ = self._synk({("DELETE", "/api/live/m1/paket"): (200, {"ok": True, "borttagen": False})})
        r = s.radera_paket("m1")
        self.assertTrue(r["ok"])
        self.assertFalse(r["borttagen"])

    def test_gren_palett_speglar_gren_js(self):
        self.assertEqual(GREN_FARG, {"herr": "#3E7C87", "dam": "#8E5A86", "mixed": "#6E8757"})


if __name__ == "__main__":
    unittest.main()
