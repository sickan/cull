"""Tester för Bildsvepet-konsumenten — injicerad fejk-klient, inga skarpa anrop."""

import json
import unittest

from dpt2.tjanster import bildsvep as BS


class _Block:
    def __init__(self, text):
        self.type = "text"; self.text = text


class _Svar:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]; self.stop_reason = stop_reason
        self.usage = None


class _Messages:
    def __init__(self, svar):
        self.svar = list(svar); self.anrop = 0; self.sista_kw = None

    def create(self, **kw):
        self.sista_kw = kw
        s = self.svar[self.anrop]; self.anrop += 1; return s


class _Klient:
    def __init__(self, svar):
        self.messages = _Messages(svar)

    def _content_text(self):
        c = self.messages.sista_kw["messages"][0]["content"]
        return c if isinstance(c, str) else json.dumps(c)


GILTIGT = json.dumps({"referat": "A sköt in 1–0.",
                      "bildsvep": "⚽ BILDSVEPET\n\n…\n@a @b @liga @forbund @nikonsverige"})


class TestGenerera(unittest.TestCase):
    def test_returnerar_referat_och_bildsvep(self):
        kl = _Klient([_Svar(GILTIGT)])
        d = BS.generera("Malmö FF–Växjö DFF 3–0", sport="fotboll",
                        hemma_farg="blå", logg=lambda *_: None, klient=kl)
        self.assertIn("bildsvep", d)
        self.assertTrue(d["referat"])

    def test_skickar_web_search_och_matchinfo_i_prompt(self):
        kl = _Klient([_Svar(GILTIGT)])
        BS.generera("Malmö FF–Växjö DFF 3–0", sport="fotboll",
                    hemma_farg="blå", logg=lambda *_: None, klient=kl)
        self.assertIn("tools", kl.messages.sista_kw)            # web_search skickat
        prompt = kl._content_text()
        self.assertIn("Malmö FF–Växjö DFF 3–0", prompt)
        self.assertIn("blå", prompt)                            # hemmafärg vävs in
        self.assertIn("Sport: fotboll", prompt)

    def test_auto_sport_utelamnas(self):
        kl = _Klient([_Svar(GILTIGT)])
        BS.generera("X–Y 1–0", sport="auto", logg=lambda *_: None, klient=kl)
        self.assertNotIn("Sport:", kl._content_text())

    def test_tom_matchinfo(self):
        self.assertIsNone(BS.generera("", logg=lambda *_: None, klient=_Klient([])))

    def test_svar_utan_bildsvep_ger_none(self):
        kl = _Klient([_Svar(json.dumps({"referat": "bara referat"}))])
        self.assertIsNone(BS.generera("X–Y 1–0", logg=lambda *_: None, klient=kl))

    def test_oparsbart_svar_ger_none(self):
        kl = _Klient([_Svar("ingen json här")])
        self.assertIsNone(BS.generera("X–Y 1–0", logg=lambda *_: None, klient=kl))


if __name__ == "__main__":
    unittest.main()
