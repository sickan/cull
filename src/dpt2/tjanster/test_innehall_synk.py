"""Tester för content-sync-klienten — fejk-transport, inget nät, ingen nyckel läcker."""

import unittest

from dpt2.tjanster.innehall_synk import InnehallSynk


class FejkTransport:
    """Spelar in anrop och svarar med förprogrammerade (status, data)."""
    def __init__(self, svar):
        self.svar = svar          # {(metod, path_suffix): (status, data)}
        self.anrop = []

    def __call__(self, metod, url, *, headers=None, body=None, timeout=20):
        self.anrop.append({"metod": metod, "url": url, "headers": headers, "body": body})
        for (m, suff), sv in self.svar.items():
            if m == metod and url.endswith(suff):
                return sv
        return 404, None


class TestInnehallSynk(unittest.TestCase):
    def test_publicera_lyckas(self):
        t = FejkTransport({
            ("PUT", "/api/innehall/match/i1"): (200, {"innehall": {"id": "i1", "publicerad": True}}),
        })
        k = InnehallSynk(api_key="hemlig", transport=t)
        r = k.publicera("match", "i1", slug="malmo-if", frontmatter={"hem": "Malmö FF"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["innehall"]["id"], "i1")     # uppackat ur {innehall: …}
        self.assertEqual(t.anrop[0]["headers"]["Authorization"], "Bearer hemlig")
        self.assertEqual(t.anrop[0]["body"]["slug"], "malmo-if")

    def test_publicera_fel_nyckel(self):
        t = FejkTransport({
            ("PUT", "/api/innehall/match/i1"): (401, {"error": "Ogiltig API-nyckel"}),
        })
        k = InnehallSynk(api_key="fel", transport=t)
        r = k.publicera("match", "i1", slug="x", frontmatter={}, forsok=1)
        self.assertFalse(r["ok"])
        self.assertEqual(r["fel"], "Ogiltig API-nyckel")

    def test_publicera_utan_nyckel_ger_tydligt_fel_utan_natanrop(self):
        # Tom nyckel ska aldrig nå transporten (httpx/h11 vägrar ett
        # "Bearer "-headervärde med LocalProtocolError innan anropet går ut —
        # utan den här spärren fastnar det i ett generiskt fel i UI:t).
        t = FejkTransport({("PUT", "/api/innehall/match/i1"): (200, {"innehall": {}})})
        k = InnehallSynk(api_key="", transport=t)
        r = k.publicera("match", "i1", slug="x", frontmatter={})
        self.assertFalse(r["ok"])
        self.assertIn("saknas", r["fel"])
        self.assertEqual(t.anrop, [])

    def test_retry_vid_kall_start(self):
        # Första anropet failar (kall Worker), andra ger 200 → retry räddar.
        class Flaky:
            def __init__(s): s.n = 0
            def __call__(s, m, url, *, headers=None, body=None, timeout=20):
                s.n += 1
                if s.n == 1:
                    raise RuntimeError("connection reset")
                return 200, {"innehall": {"id": "i1"}}
        k = InnehallSynk(api_key="x", transport=Flaky())
        r = k.publicera("match", "i1", slug="x", frontmatter={})
        self.assertTrue(r["ok"])

    def test_status_hittas_inte(self):
        t = FejkTransport({("GET", "/api/innehall/match/saknas"): (404, {"error": "hittas inte"})})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertIsNone(k.status("match", "saknas"))

    def test_status_ok(self):
        t = FejkTransport({("GET", "/api/innehall/match/i1"): (200, {"innehall": {"id": "i1"}})})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertEqual(k.status("match", "i1")["id"], "i1")

    def test_status_med_deploy(self):
        t = FejkTransport({("GET", "/api/innehall/match/i1"): (200, {
            "innehall": {"id": "i1"},
            "deploy": {"status": "success", "skapad": "2026-07-05T00:00:00Z", "url": None},
        })})
        k = InnehallSynk(api_key="x", transport=t)
        r = k.status("match", "i1")
        self.assertEqual(r["deploy"]["status"], "success")

    def test_status_utan_cf_secrets_ger_deploy_none(self):
        t = FejkTransport({("GET", "/api/innehall/match/i1"): (200, {
            "innehall": {"id": "i1"}, "deploy": None,
        })})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertIsNone(k.status("match", "i1")["deploy"])


if __name__ == "__main__":
    unittest.main()
