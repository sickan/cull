"""Vakter för importrutan i Matcher-panelen (spelschema-import).

Samma mönster som test_registerpanel: panelen är ren presentation och det
finns ingen körbar Svelte-runtime i sviten, så testerna läser källan och
kontrollerar de invarianter som faktiskt gick sönder skarpt:

  * grenvalet MÅSTE nå backend — utan det föll herrlagen ihop med damlagen
    (svenska herrserier är omärkta: "Elitserien" = herr)
  * krockalternativen MÅSTE vara klickbara — rubriken lovade "du väljer"
    medan markupen var rena <span> utan handler
"""

import unittest
from pathlib import Path

UI = Path(__file__).parent / "ui" / "src"
MATCHER = (UI / "panels" / "Matcher.svelte").read_text(encoding="utf-8")
API = (UI / "lib" / "api.js").read_text(encoding="utf-8")


class TestGrenval(unittest.TestCase):
    def test_grenvalet_finns_med_alla_tre_grenar(self):
        self.assertIn("let importGren = ''", MATCHER)
        for gren in ("'dam', 'Dam'", "'herr', 'Herr'", "'mixed', 'Mixed'"):
            self.assertIn(gren, MATCHER)

    def test_grenvalet_skickas_till_backend(self):
        # Kärnan: väljaren är verkningslös om den inte följer med anropet.
        self.assertIn("importeraSpelschema(fixtures, null, importGren || null)",
                      MATCHER)
        self.assertIn("api.importera_spelschema(fixtures, sport, gren)", API)


class TestKrockval(unittest.TestCase):
    def test_alternativen_ar_klickbara_knappar(self):
        self.assertIn('<button class="krockalt"', MATCHER)
        self.assertIn("on:click={() => valjKrock(k, ai)}", MATCHER)
        self.assertNotIn('<span class="krockalt"', MATCHER)   # regression

    def test_valet_styr_fotojobbet_och_plockar_bort_de_andra(self):
        # Stigs beslut: allt importeras, valet styr BARA fotojobbet. Att de
        # icke-valda får false är poängen — annars ligger gamla jobb kvar i
        # kalendern när han ändrar sig.
        self.assertIn("await sattMatchSynk(m.id, i === ai)", MATCHER)

    def test_rubriken_lovar_inte_att_valet_styr_importen(self):
        self.assertIn("allt är importerat, välj vad du bevakar", MATCHER)


if __name__ == "__main__":
    unittest.main()
