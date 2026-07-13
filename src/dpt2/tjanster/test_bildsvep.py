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

    def test_kanda_matchfakta_vavs_in_i_prompten(self):
        # Regression: appen har redan resultat/mellan/malskyttar/arena/datum/
        # liga lokalt (resultat-remsan/matchposten) — Claude ska INTE behöva
        # websöka efter dem, de ska stå rakt i frågan.
        kl = _Klient([_Svar(GILTIGT)])
        BS.generera("Malmö FF–Kristianstads DFF 6–0", sport="fotboll",
                    resultat="6-0", mellan="3-0",
                    malskyttar="Ivanovic 10', Kanutte Fornes 50', 58'",
                    arena="Eleda Stadion", datum="2026-06-27",
                    liga="OBOS Damallsvenskan", logg=lambda *_: None, klient=kl)
        prompt = kl._content_text()
        self.assertIn("KÄNDA MATCHFAKTA", prompt)
        self.assertIn("Resultat: 6-0", prompt)
        self.assertIn("Halvtid/set: 3-0", prompt)
        self.assertIn("Kanutte Fornes 50', 58'", prompt)
        self.assertIn("Arena: Eleda Stadion", prompt)
        self.assertIn("Liga: OBOS Damallsvenskan", prompt)

    def test_utan_kanda_fakta_ingen_rubrik(self):
        kl = _Klient([_Svar(GILTIGT)])
        BS.generera("X–Y 1–0", logg=lambda *_: None, klient=kl)
        self.assertNotIn("KÄNDA MATCHFAKTA", kl._content_text())


class TestByggFraga(unittest.TestCase):
    """bygg_fraga är en ren strängoperation (inget nätverksanrop) — UI:t
    använder den för att visa exakt vad som SKULLE skickas, för godkännande
    innan det skarpa Claude-anropet (som tar ~2 minuter)."""

    def test_ingen_natverksanrop_kravs(self):
        fraga = BS.bygg_fraga("Malmö FF–Kristianstads DFF 6-0", resultat="6-0",
                              arena="Eleda Stadion")
        self.assertIn("Resultat: 6-0", fraga)
        self.assertIn("Arena: Eleda Stadion", fraga)

    def test_tom_matchinfo_bygger_anda_en_fraga(self):
        # bygg_fraga kastar aldrig — bara generera() vägrar tom matchinfo.
        fraga = BS.bygg_fraga("")
        self.assertIn("Skriv Bildsvepet", fraga)

    def test_p6_vinklar_och_inspel_vavs_in(self):
        # p.6 (handoff v2): fotografens vinkel-chips + fritext ska styra prompten.
        fraga = BS.bygg_fraga("Malmö FF–Kristianstad 6-0",
                              vinklar=["Stämning", "Publiken"],
                              inspel="avgörande i 90:e, publikrekord")
        self.assertIn("SÄRSKILD VIKT", fraga)
        self.assertIn("Stämning, Publiken", fraga)
        self.assertIn("FOTOGRAFENS EGNA INSPEL", fraga)
        self.assertIn("avgörande i 90:e, publikrekord", fraga)

    def test_p6_tomma_inspel_ger_inga_rubriker(self):
        fraga = BS.bygg_fraga("X–Y 1-0", vinklar=[], inspel="")
        self.assertNotIn("SÄRSKILD VIKT", fraga)
        self.assertNotIn("FOTOGRAFENS EGNA INSPEL", fraga)

    def test_p6_vinklar_nar_hela_vagen_genom_generera(self):
        kl = _Klient([_Svar(GILTIGT)])
        BS.generera("Malmö FF–Kristianstad 6-0", vinklar=["Vinkel"],
                    inspel="lyft målvakten", logg=lambda *_: None, klient=kl)
        prompt = kl._content_text()
        self.assertIn("SÄRSKILD VIKT", prompt)
        self.assertIn("lyft målvakten", prompt)


if __name__ == "__main__":
    unittest.main()
