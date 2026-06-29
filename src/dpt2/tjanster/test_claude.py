"""Tester för Claude-tjänsten — injicerad fejk-klient, inga skarpa anrop."""

import unittest

from dpt2.tjanster import claude


# ── fejk-klient som speglar anthropic.messages.create ────────────────────────
class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


class _Svar:
    def __init__(self, text="", stop_reason="end_turn", usage=None):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason
        self.usage = usage


class _Messages:
    def __init__(self, svar):
        self.svar = list(svar)
        self.anrop = 0
        self.sista_kw = None

    def create(self, **kw):
        self.sista_kw = kw
        s = self.svar[self.anrop]
        self.anrop += 1
        return s


class _Klient:
    def __init__(self, svar):
        self.messages = _Messages(svar)


class TestParsaJson(unittest.TestCase):
    def test_ren(self):
        self.assertEqual(claude.parsa_json('{"a": 1}'), {"a": 1})

    def test_kodstaket_och_text(self):
        self.assertEqual(
            claude.parsa_json('Här:\n```json\n{"a": 1, "b": [2,3]}\n```\nklart'),
            {"a": 1, "b": [2, 3]})

    def test_ogiltig(self):
        self.assertIsNone(claude.parsa_json("inget json här"))
        self.assertIsNone(claude.parsa_json(""))


class TestKostnad(unittest.TestCase):
    def test_ackumulering(self):
        k = claude.Kostnad(tak=1.0)
        k.lagg_till(_Usage(1000, 500))
        self.assertAlmostEqual(
            k.usd, 1000 * claude.PRIS_IN + 500 * claude.PRIS_UT, places=9)
        self.assertFalse(k.over_tak())

    def test_over_tak(self):
        k = claude.Kostnad(tak=0.001)
        k.lagg_till(_Usage(1_000_000, 0))      # $15 → över taket
        self.assertTrue(k.over_tak())


class TestFragaJson(unittest.TestCase):
    def test_enkelt_svar(self):
        kl = _Klient([_Svar('{"lag": "ok"}', usage=_Usage(10, 10))])
        d = claude.fraga_json(kl, "sys", "fråga", logg=lambda *_: None)
        self.assertEqual(d, {"lag": "ok"})
        self.assertEqual(kl.messages.anrop, 1)

    def test_pause_turn_loop(self):
        # första svaret pausar turen (web_search) → andra ger JSON
        kl = _Klient([
            _Svar("", stop_reason="pause_turn", usage=_Usage(10, 5)),
            _Svar('{"klart": true}', usage=_Usage(10, 5)),
        ])
        d = claude.fraga_json(kl, "sys", "fråga",
                              verktyg=claude.web_search_verktyg(), logg=lambda *_: None)
        self.assertEqual(d, {"klart": True})
        self.assertEqual(kl.messages.anrop, 2)
        self.assertIn("tools", kl.messages.sista_kw)     # verktyg skickades

    def test_refusal(self):
        kl = _Klient([_Svar("nej", stop_reason="refusal", usage=_Usage(5, 5))])
        self.assertIsNone(claude.fraga_json(kl, "s", "f", logg=lambda *_: None))

    def test_kostnadstak_bryter(self):
        # dyrt pause_turn-svar (inget JSON) → taket bryter, inget andra varv
        kl = _Klient([
            _Svar("", stop_reason="pause_turn", usage=_Usage(1_000_000, 0)),
            _Svar('{"skulle": "ej nås"}'),
        ])
        d = claude.fraga_json(kl, "s", "f", kostnad=claude.Kostnad(tak=0.01),
                              logg=lambda *_: None)
        self.assertIsNone(d)
        self.assertEqual(kl.messages.anrop, 1)           # stannade efter taket

    def test_api_fel_ger_none(self):
        class _Trasig:
            class messages:
                @staticmethod
                def create(**kw):
                    raise RuntimeError("nätverk")
        self.assertIsNone(
            claude.fraga_json(_Trasig(), "s", "f", logg=lambda *_: None))


class TestVision(unittest.TestCase):
    def test_text_utan_bilder(self):
        kl = _Klient([_Svar('{"nr": "10"}', usage=_Usage(5, 5))])
        d = claude.fraga_json_vision(kl, "sys", "läs", [], logg=lambda *_: None)
        self.assertEqual(d, {"nr": "10"})
        # innehållet ska vara en lista med text-block
        innehall = kl.messages.sista_kw["messages"][0]["content"]
        self.assertEqual(innehall[-1]["type"], "text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
