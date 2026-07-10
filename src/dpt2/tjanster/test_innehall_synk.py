"""Tester för content-sync-klienten — fejk-transport, inget nät, ingen nyckel läcker."""

import tempfile
import unittest
from pathlib import Path

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

    def _riktig_jpg(self, mapp, namn="01.jpg", storlek=(400, 300)):
        """Skapar en riktig (liten) JPEG — ladda_upp_bild optimerar via PIL,
        så en fejkad byte-sträng duger inte längre som testbild."""
        from PIL import Image
        p = Path(mapp) / namn
        Image.new("RGB", storlek, (120, 80, 200)).save(p, "JPEG")
        return p

    def test_ladda_upp_bild_ok(self):
        with tempfile.TemporaryDirectory() as d:
            fil = self._riktig_jpg(d)
            t = FejkTransport({("PUT", "/api/bilder/match/malmo-if/01.jpg"):
                                (200, {"ok": True, "url": "https://x/bilder/match/malmo-if/01.jpg"})})
            k = InnehallSynk(api_key="x", transport=t)
            url = k.ladda_upp_bild("match", "malmo-if", str(fil))
            self.assertEqual(url, "https://x/bilder/match/malmo-if/01.jpg")
            # Optimerad (omkodad) JPEG, inte källfilens rå bytes rakt av.
            self.assertTrue(t.anrop[0]["body"].startswith(b"\xff\xd8"))
            self.assertEqual(t.anrop[0]["headers"]["Content-Type"], "image/jpeg")

    def test_ladda_upp_bild_skalar_ned_stor_bild(self):
        with tempfile.TemporaryDirectory() as d:
            fil = self._riktig_jpg(d, storlek=(3000, 2000))
            t = FejkTransport({("PUT", "/api/bilder/match/malmo-if/01.jpg"):
                                (200, {"ok": True, "url": "https://x/01.jpg"})})
            k = InnehallSynk(api_key="x", transport=t)
            k.ladda_upp_bild("match", "malmo-if", str(fil), max_bredd=1600, kvalitet=75)
            from PIL import Image
            import io
            optimerad = Image.open(io.BytesIO(t.anrop[0]["body"]))
            self.assertEqual(optimerad.width, 1600)

    def test_ladda_upp_bild_saknad_fil(self):
        k = InnehallSynk(api_key="x", transport=FejkTransport({}))
        self.assertIsNone(k.ladda_upp_bild("match", "malmo-if", "/finns/inte.jpg"))

    def test_ladda_upp_bild_ingen_sokvag(self):
        k = InnehallSynk(api_key="x", transport=FejkTransport({}))
        self.assertIsNone(k.ladda_upp_bild("match", "malmo-if", None))

    def test_ladda_upp_bild_ogiltig_bild_ger_none(self):
        with tempfile.TemporaryDirectory() as d:
            fil = Path(d) / "01.jpg"
            fil.write_bytes(b"inte-en-riktig-bild")
            k = InnehallSynk(api_key="x", transport=FejkTransport({}))
            self.assertIsNone(k.ladda_upp_bild("match", "malmo-if", str(fil)))

    def test_ladda_upp_bild_fel_ger_none(self):
        with tempfile.TemporaryDirectory() as d:
            fil = self._riktig_jpg(d)
            t = FejkTransport({("PUT", "/api/bilder/match/malmo-if/01.jpg"): (500, {"error": "internt fel"})})
            k = InnehallSynk(api_key="x", transport=t)
            self.assertIsNone(k.ladda_upp_bild("match", "malmo-if", str(fil), forsok=1))


class TestListaOchRadera(unittest.TestCase):
    def test_lista_returnerar_rader(self):
        t = FejkTransport({("GET", "/api/innehall/pagang"):
                           (200, {"innehall": [{"id": "a1"}, {"id": "a2"}]})})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertEqual([r["id"] for r in k.lista("pagang")], ["a1", "a2"])

    def test_lista_tom_vid_fel(self):
        t = FejkTransport({("GET", "/api/innehall/pagang"): (500, None)})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertEqual(k.lista("pagang"), [])

    def test_radera_lyckas(self):
        t = FejkTransport({("DELETE", "/api/innehall/pagang/a1"):
                           (200, {"ok": True, "borttagen": True})})
        k = InnehallSynk(api_key="x", transport=t)
        r = k.radera("pagang", "a1")
        self.assertTrue(r["ok"])
        self.assertEqual(t.anrop[0]["metod"], "DELETE")
        self.assertEqual(t.anrop[0]["headers"]["Authorization"], "Bearer x")

    def test_radera_404_ar_ok(self):
        # Redan borta → målet (raden finns inte) är nått, räknas som lyckat.
        t = FejkTransport({("DELETE", "/api/innehall/pagang/borta"): (404, {"error": "hittas inte"})})
        k = InnehallSynk(api_key="x", transport=t)
        self.assertTrue(k.radera("pagang", "borta")["ok"])

    def test_radera_utan_nyckel_ger_fel_utan_natanrop(self):
        t = FejkTransport({("DELETE", "/api/innehall/pagang/a1"): (200, {"ok": True})})
        k = InnehallSynk(api_key="", transport=t)
        r = k.radera("pagang", "a1")
        self.assertFalse(r["ok"])
        self.assertIn("saknas", r["fel"])
        self.assertEqual(t.anrop, [])

    def test_radera_serverfel_retry_och_ger_upp(self):
        t = FejkTransport({("DELETE", "/api/innehall/pagang/a1"): (500, {"error": "internt"})})
        k = InnehallSynk(api_key="x", transport=t)
        r = k.radera("pagang", "a1", forsok=2)
        self.assertFalse(r["ok"])
        self.assertEqual(len(t.anrop), 2)


class TestLaddaUppLogga(unittest.TestCase):
    """Laglogotyper → R2. Alfakanalen MÅSTE överleva: `ladda_upp_bild` kör
    optimera() som konverterar till RGB och sparar JPEG, vilket hade lagt
    klubbmärket på en opak ruta. Därför en egen väg."""

    def _png(self, storlek=800, alpha=0):
        import io
        from PIL import Image
        b = io.BytesIO()
        # genomskinlig bakgrund + en ogenomskinlig fyrkant = äkta alfakanal
        im = Image.new("RGBA", (storlek, storlek), (0, 0, 0, alpha))
        im.paste((200, 30, 40, 255), (storlek // 4, storlek // 4, storlek // 2, storlek // 2))
        im.save(b, format="PNG")
        return b.getvalue()

    def _skriv(self, tmp, data, namn="malmö_ff.png"):
        p = Path(tmp) / namn
        p.write_bytes(data)
        return p

    def _synk(self):
        t = FejkTransport({("PUT", "/api/bilder/lag/malmo-ff/malmö_ff.png"):
                           (200, {"ok": True, "url": "https://x.dev/bilder/lag/malmo-ff/malmö_ff.png"})})
        return InnehallSynk(bas_url="https://x.dev", api_key="hemlig", transport=t), t

    def test_laddar_upp_och_returnerar_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            k, t = self._synk()
            url = k.ladda_upp_logga("malmo-ff", self._skriv(tmp, self._png()))
            self.assertEqual(url, "https://x.dev/bilder/lag/malmo-ff/malmö_ff.png")
            self.assertEqual(t.anrop[0]["metod"], "PUT")
            self.assertIn("/api/bilder/lag/malmo-ff/", t.anrop[0]["url"])

    def test_behaller_png_och_alfakanal(self):
        import io
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            k, t = self._synk()
            k.ladda_upp_logga("malmo-ff", self._skriv(tmp, self._png()))
            skickad = t.anrop[0]["body"]
            self.assertEqual(t.anrop[0]["headers"]["Content-Type"], "image/png")
            bild = Image.open(io.BytesIO(skickad))
            self.assertEqual(bild.format, "PNG")
            self.assertEqual(bild.mode, "RGBA")
            # hörnet ska fortfarande vara genomskinligt
            self.assertEqual(bild.getpixel((0, 0))[3], 0)

    def test_skalas_ned_till_max_bredd(self):
        import io
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            k, t = self._synk()
            k.ladda_upp_logga("malmo-ff", self._skriv(tmp, self._png(800)), max_bredd=512)
            self.assertEqual(Image.open(io.BytesIO(t.anrop[0]["body"])).width, 512)

    def test_liten_logga_skalas_inte_upp(self):
        import io
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            k, t = self._synk()
            k.ladda_upp_logga("malmo-ff", self._skriv(tmp, self._png(120)), max_bredd=512)
            self.assertEqual(Image.open(io.BytesIO(t.anrop[0]["body"])).width, 120)

    def test_saknad_fil_ger_none_utan_anrop(self):
        k, t = self._synk()
        self.assertIsNone(k.ladda_upp_logga("malmo-ff", "/finns/inte.png"))
        self.assertEqual(t.anrop, [])

    def test_trasig_bild_ger_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            k, t = self._synk()
            p = Path(tmp) / "trasig.png"
            p.write_bytes(b"inte en png")
            self.assertIsNone(k.ladda_upp_logga("malmo-ff", p))
            self.assertEqual(t.anrop, [])

    def test_serverfel_ger_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = FejkTransport({})            # allt → 404
            k = InnehallSynk(bas_url="https://x.dev", api_key="hemlig", transport=t)
            self.assertIsNone(k.ladda_upp_logga("x", self._skriv(tmp, self._png()), forsok=1))


if __name__ == "__main__":
    unittest.main()
