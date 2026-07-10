"""Tester för privat-kalender-klienten — fejk-transport, inget nät, ingen token
läcker till disk (config i tempdir). Speglar test_kalender.py:s upplägg."""

import json
import tempfile
import unittest
from pathlib import Path

from dpt2.tjanster.privat_kalender import PrivatKalender


class FejkTransport:
    """Spelar in anrop och svarar med förprogrammerade (status, data) per
    URL-suffix. `form`/`body`/`headers` sparas så testerna kan inspektera dem."""
    def __init__(self, svar):
        self.svar = svar
        self.anrop = []

    def __call__(self, metod, url, *, headers=None, body=None, form=None, timeout=20):
        self.anrop.append({"metod": metod, "url": url, "headers": headers,
                           "body": body, "form": form})
        for (m, suff), sv in self.svar.items():
            if m == metod and suff in url:
                return sv
        return 404, None


def _klient(svar, cfg=None, **kw):
    """Klient med tempdir-config så inget skrivs till ~/.config."""
    d = tempfile.mkdtemp()
    return PrivatKalender(config_path=Path(d) / "privat.json",
                          transport=FejkTransport(svar), config=dict(cfg or {}), **kw)


class TestAuth(unittest.TestCase):
    def test_har_uppgifter_kraver_klient_och_refresh(self):
        k = _klient({}, cfg={"client_id": "cid"})
        self.assertFalse(k.har_uppgifter())               # ingen refresh-token
        k = _klient({}, cfg={"client_id": "cid", "refresh_token": "r"})
        k.client_secret = "s"
        self.assertTrue(k.har_uppgifter())

    def test_auth_url_innehaller_offline_och_scope(self):
        k = _klient({}, cfg={"client_id": "cid"})
        url = k.auth_url("http://127.0.0.1:9999/cb", state="xyz")
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("calendar.readonly", url)
        self.assertIn("state=xyz", url)

    def test_vaxla_kod_sparar_refresh_token(self):
        t = FejkTransport({("POST", "/token"): (200, {
            "access_token": "atok", "refresh_token": "rtok", "expires_in": 3600})})
        d = tempfile.mkdtemp()
        p = Path(d) / "privat.json"
        k = PrivatKalender(config_path=p, transport=t,
                           config={"client_id": "cid", "client_secret": "sec"})
        r = k.vaxla_kod("auth-kod", "http://127.0.0.1:9999/cb")
        self.assertTrue(r["ok"])
        # refresh-token skrevs till config, access-token bara i RAM
        self.assertEqual(json.loads(p.read_text())["refresh_token"], "rtok")
        self.assertNotIn("access_token", p.read_text())

    def test_logga_ut_glommer_token_och_val(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "privat.json"
        k = PrivatKalender(config_path=p, transport=FejkTransport({}),
                           config={"client_id": "c", "client_secret": "s",
                                   "refresh_token": "r", "valda": ["a"]})
        k.logga_ut()
        self.assertFalse(k._refresh)
        self.assertEqual(json.loads(p.read_text()).get("valda", "BORTA"), "BORTA")


class TestLoopback(unittest.TestCase):
    """Kör hela consent-flödet mot den riktiga loopback-servern, men med en
    fejkad 'webbläsare' som träffar redirecten. Token-utbytet går via fejk-
    transport → inget riktigt Google-anrop."""
    def _fejk_webblasare(self, query):
        """Returnerar en oppna(url)-callback som i en tråd hämtar redirect-uri:n
        (utläst ur consent-url:en) med `query` påklistrad — som Google gör."""
        import threading
        import urllib.request
        from urllib.parse import urlparse, parse_qs

        def oppna(url):
            redirect = parse_qs(urlparse(url).query)["redirect_uri"][0]

            def traffa():
                for _ in range(50):
                    try:
                        urllib.request.urlopen(redirect + "?" + query, timeout=1).read()
                        return
                    except Exception:
                        import time
                        time.sleep(0.05)
            threading.Thread(target=traffa, daemon=True).start()
        return oppna

    def test_lyckad_inloggning_fangar_kod_och_vaxlar(self):
        t = FejkTransport({("POST", "/token"): (200, {
            "access_token": "a", "refresh_token": "r", "expires_in": 3600})})
        d = tempfile.mkdtemp()
        k = PrivatKalender(config_path=Path(d) / "p.json", transport=t,
                           config={"client_id": "cid", "client_secret": "sec"})
        r = k.logga_in_interaktivt(oppna=self._fejk_webblasare("code=testkod"), timeout=10)
        self.assertTrue(r["ok"])
        self.assertEqual(t.anrop[0]["form"]["code"], "testkod")   # koden växlades

    def test_avbruten_inloggning_ger_fel(self):
        k = PrivatKalender(config_path=Path(tempfile.mkdtemp()) / "p.json",
                           transport=FejkTransport({}),
                           config={"client_id": "cid", "client_secret": "sec"})
        r = k.logga_in_interaktivt(oppna=self._fejk_webblasare("error=access_denied"), timeout=10)
        self.assertFalse(r["ok"])
        self.assertEqual(r["fel"], "access_denied")

    def test_utan_klientuppgifter_vagrar(self):
        k = PrivatKalender(config_path=Path(tempfile.mkdtemp()) / "p.json",
                           transport=FejkTransport({}), config={})
        r = k.logga_in_interaktivt(oppna=lambda u: None, timeout=1)
        self.assertFalse(r["ok"])


class TestToken(unittest.TestCase):
    def _inloggad(self, svar, tid):
        return _klient(svar, cfg={"client_id": "c", "client_secret": "s",
                                  "refresh_token": "r"}, klocka=lambda: tid[0])

    def test_access_token_refreshas_vid_utgang(self):
        tid = [1000.0]
        t = FejkTransport({("POST", "/token"): (200, {"access_token": "ny", "expires_in": 3600})})
        k = PrivatKalender(config_path=Path(tempfile.mkdtemp()) / "p.json", transport=t,
                           config={"client_id": "c", "client_secret": "s", "refresh_token": "r"},
                           klocka=lambda: tid[0])
        self.assertEqual(k._access_token(), "ny")
        n = len(t.anrop)
        k._access_token()                     # inom giltighetstid → ingen ny refresh
        self.assertEqual(len(t.anrop), n)
        tid[0] += 4000                         # token utgången → refresh igen
        k._access_token()
        self.assertEqual(len(t.anrop), n + 1)
        # refresh-anropet är rätt grant + skickar aldrig kalenderdata
        self.assertEqual(t.anrop[0]["form"]["grant_type"], "refresh_token")

    def test_ingen_refresh_token_ger_none(self):
        k = _klient({}, cfg={"client_id": "c", "client_secret": "s"})
        self.assertIsNone(k._access_token())


class TestHandelser(unittest.TestCase):
    def _k(self, items):
        return _klient({
            ("POST", "/token"): (200, {"access_token": "a", "expires_in": 3600}),
            ("GET", "/events"): (200, {"items": items}),
        }, cfg={"client_id": "c", "client_secret": "s", "refresh_token": "r"})

    def test_heldag_slut_blir_inklusivt(self):
        # Google: exklusivt slut 2026-08-23 för en post 2026-08-22 → inklusivt 22.
        k = self._k([{"id": "e1", "summary": "Kräftskiva",
                      "start": {"date": "2026-08-22"}, "end": {"date": "2026-08-23"}}])
        p = k.hamta_handelser("cal", "2026-08-01", "2026-09-01")[0]
        self.assertTrue(p["heldag"])
        self.assertEqual(p["start"], "2026-08-22")
        self.assertEqual(p["slut"], "2026-08-22")

    def test_tidssatt_titel_bevaras(self):
        k = self._k([{"id": "e2", "summary": "Tandläkare",
                      "start": {"dateTime": "2026-07-19T14:00:00+02:00"},
                      "end": {"dateTime": "2026-07-19T15:00:00+02:00"}}])
        p = k.hamta_handelser("cal", "2026-07-01", "2026-08-01")[0]
        self.assertEqual(p["titel"], "Tandläkare")
        self.assertFalse(p["heldag"])
        self.assertTrue(p["start"].startswith("2026-07-19T"))

    def test_cancelled_och_transparent_hoppas(self):
        k = self._k([
            {"id": "x", "status": "cancelled", "start": {"date": "2026-07-01"}},
            {"id": "y", "transparency": "transparent", "summary": "Ledig",
             "start": {"dateTime": "2026-07-02T10:00:00+02:00"}, "end": {"dateTime": "2026-07-02T11:00:00+02:00"}},
            {"id": "z", "summary": "Upptagen möte",
             "start": {"dateTime": "2026-07-03T10:00:00+02:00"}, "end": {"dateTime": "2026-07-03T11:00:00+02:00"}},
        ])
        ut = k.hamta_handelser("cal", "2026-07-01", "2026-08-01")
        self.assertEqual([p["id"] for p in ut], ["z"])

    def test_titellos_post_blir_upptaget(self):
        k = self._k([{"id": "e", "start": {"dateTime": "2026-07-03T10:00:00+02:00"},
                      "end": {"dateTime": "2026-07-03T11:00:00+02:00"}}])
        self.assertEqual(k.hamta_handelser("cal", "2026-07-01", "2026-08-01")[0]["titel"], "Upptaget")

    def test_hamta_span_utan_uppgifter_ger_tom(self):
        k = _klient({}, cfg={})               # varken klient eller token
        self.assertEqual(k.hamta_span("2026-07-01", "2026-08-01"), [])


class TestKalendrar(unittest.TestCase):
    def test_calendarlist_etikett_och_farg(self):
        k = _klient({
            ("POST", "/token"): (200, {"access_token": "a", "expires_in": 3600}),
            ("GET", "/users/me/calendarList"): (200, {"items": [
                {"id": "me@x", "summary": "Jag", "primary": True, "backgroundColor": "#5C93C9"},
                {"id": "fru@x", "summaryOverride": "Frun", "colorId": "3"},
            ]}),
        }, cfg={"client_id": "c", "client_secret": "s", "refresh_token": "r"})
        kal = k.kalendrar()
        self.assertEqual(kal[0]["etikett"], "Jag")
        self.assertEqual(kal[0]["farg"], "#5C93C9")
        self.assertEqual(kal[1]["etikett"], "Frun")      # summaryOverride vinner
        self.assertTrue(kal[1]["farg"].startswith("#"))  # colorId → hex

    def test_satt_och_las_valda(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "p.json"
        k = PrivatKalender(config_path=p, transport=FejkTransport({}),
                           config={"client_id": "c"})
        k.satt_valda(["me@x", "fru@x"])
        self.assertEqual(json.loads(p.read_text())["valda"], ["me@x", "fru@x"])

    def test_egen_etikett_vinner_over_googles(self):
        svar = {
            ("POST", "/token"): (200, {"access_token": "a", "expires_in": 3600}),
            ("GET", "/users/me/calendarList"): (200, {"items": [
                {"id": "me@x", "summary": "me@x", "primary": True},
                {"id": "fru@x", "summaryOverride": "Frun"},
            ]}),
        }
        k = _klient(svar, cfg={"client_id": "c", "client_secret": "s", "refresh_token": "r"})
        k.satt_etikett("me@x", "Privat")
        k.satt_etikett("fru@x", "Anna")
        kal = k.kalendrar()
        self.assertEqual(kal[0]["etikett"], "Privat")    # egen etikett > Googles namn
        self.assertEqual(kal[1]["etikett"], "Anna")      # egen etikett > summaryOverride
        # Tom etikett = tillbaka till Googles namn; config-nyckeln städas bort.
        k.satt_etikett("me@x", "  ")
        self.assertEqual(k.kalendrar()[0]["etikett"], "me@x")
        self.assertNotIn("me@x", json.loads(k.config_path.read_text())["etiketter"])

    def test_etikett_sparas_i_config(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "p.json"
        k = PrivatKalender(config_path=p, transport=FejkTransport({}),
                           config={"client_id": "c"})
        k.satt_etikett("fru@x", "Anna")
        self.assertEqual(json.loads(p.read_text())["etiketter"], {"fru@x": "Anna"})


if __name__ == "__main__":
    unittest.main()
