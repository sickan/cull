"""Tester för bildhosting-uppladdningen — fejk-transport, inget nät."""

import os
import tempfile
import unittest

from dpt2.tjanster import bildhosting


class FejkTransport:
    def __init__(self, svar=None):
        self.svar = svar or (lambda url: (200, {"ok": True, "url": url}))
        self.anrop = []

    def __call__(self, metod, url, *, headers=None, body=None, timeout=60):
        self.anrop.append({"metod": metod, "url": url, "headers": headers,
                           "bytes": len(body or b"")})
        return self.svar(url)


class TestLaddaUpp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.filer = []
        for namn in ("story_1.jpg", "story_2.jpg"):
            p = os.path.join(self.tmp.name, namn)
            with open(p, "wb") as f:
                f.write(b"\xff\xd8\xff\xd9")
            self.filer.append(p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_laddar_upp_med_basename_och_nyckel(self):
        t = FejkTransport()
        r = bildhosting.ladda_upp(self.filer, bas_url="https://x.dev",
                                  api_key="hemlig", transport=t, logg=lambda *_: None)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["urls"]), 2)
        # basename som nyckel (meta_api.bild_url-kontraktet) + Bearer-header
        self.assertEqual(t.anrop[0]["url"], "https://x.dev/story_1.jpg")
        self.assertEqual(t.anrop[0]["headers"]["Authorization"], "Bearer hemlig")
        self.assertGreater(t.anrop[0]["bytes"], 0)

    def test_utan_nyckel_stoppar(self):
        r = bildhosting.ladda_upp(self.filer, bas_url="https://x.dev",
                                  api_key=None, transport=FejkTransport(),
                                  logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertIn("DPT_BILD_API_KEY", r["fel"])

    def test_serverfel_avbryter(self):
        t = FejkTransport(svar=lambda url: (401, {"error": "Ej behörig"}))
        r = bildhosting.ladda_upp(self.filer, bas_url="https://x.dev",
                                  api_key="fel", transport=t, logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertIn("Ej behörig", r["fel"])
        self.assertEqual(len(t.anrop), 1)          # stoppade direkt

    def test_saknad_fil_stoppar(self):
        r = bildhosting.ladda_upp(["/finns/inte.jpg"], bas_url="https://x.dev",
                                  api_key="x", transport=FejkTransport(),
                                  logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertIn("inte.jpg", r["fel"])


if __name__ == "__main__":
    unittest.main()
