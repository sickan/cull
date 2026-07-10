"""Tester för kalender-klienten — fejk-transport, inget nät, ingen nyckel läcker."""

import unittest

from dpt2.tjanster.kalender import Kalender


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


class TestKalender(unittest.TestCase):
    def test_publikt_utan_nyckel(self):
        t = FejkTransport({("GET", "/api/public/events"): (200, {"events": [{"id": "1", "title": "A"}]})})
        k = Kalender(api_key="", transport=t)
        self.assertFalse(k.har_nyckel())
        jobb = k.lista_jobb()
        self.assertEqual(jobb[0]["title"], "A")
        # publikt anrop → ingen Authorization-header
        self.assertNotIn("Authorization", t.anrop[0]["headers"])

    def test_skyddat_med_nyckel(self):
        t = FejkTransport({("GET", "/api/events"): (200, {"events": [{"id": "9"}]})})
        k = Kalender(api_key="hemlig", transport=t)
        self.assertTrue(k.har_nyckel())
        k.lista_jobb()
        self.assertEqual(t.anrop[0]["headers"]["Authorization"], "Bearer hemlig")

    def test_skapa_uppdatera_radera(self):
        # Tjänsten svarar `{event: {...}}` på POST/PUT (routes/events.ts) —
        # klienten ska packa upp så anroparna får jobbet (och dess id) direkt.
        t = FejkTransport({
            ("POST", "/api/events"): (201, {"event": {"id": "ny", "google_event_id": None}}),
            ("PUT", "/api/events/ny"): (200, {"event": {"id": "ny"}}),
            ("DELETE", "/api/events/ny"): (204, None),
        })
        k = Kalender(api_key="x", transport=t)
        r = k.skapa_jobb({"title": "Bröllop"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["jobb"]["id"], "ny")     # uppackat ur {event: …}
        self.assertEqual(t.anrop[0]["body"]["title"], "Bröllop")
        r = k.uppdatera_jobb("ny", {"title": "B2"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["jobb"]["id"], "ny")
        self.assertTrue(k.radera_jobb("ny")["ok"])

    def test_hamta_jobb_packar_upp_event(self):
        # Behövs av match-synken: läs jobbet först så description (fotografens
        # anteckning) kan bevaras när PUT ersätter hela jobbet.
        t = FejkTransport({("GET", "/api/events/j1"):
                           (200, {"event": {"id": "j1", "description": "Kund: Anna"}})})
        k = Kalender(api_key="x", transport=t)
        r = k.hamta_jobb("j1")
        self.assertTrue(r["ok"])
        self.assertEqual(r["jobb"]["description"], "Kund: Anna")
        self.assertEqual(t.anrop[0]["headers"]["Authorization"], "Bearer x")

    def test_fel_status_ger_tom_lista(self):
        t = FejkTransport({("GET", "/api/events"): (401, {"error": "Ogiltig API-nyckel"})})
        k = Kalender(api_key="fel", transport=t)
        self.assertEqual(k.lista_jobb(forsok=1), [])   # forsok=1 → ingen backoff-sömn

    def test_retry_vid_kall_start(self):
        # Första anropet failar (kall Worker), andra ger data → retry räddar.
        class Flaky:
            def __init__(s): s.n = 0
            def __call__(s, m, url, *, headers=None, body=None, timeout=20):
                s.n += 1
                if s.n == 1:
                    raise RuntimeError("connection reset")
                return 200, {"events": [{"id": "1"}]}
        k = Kalender(api_key="x", transport=Flaky())
        self.assertEqual(len(k.lista_jobb()), 1)       # andra försöket lyckas


if __name__ == "__main__":
    unittest.main()
