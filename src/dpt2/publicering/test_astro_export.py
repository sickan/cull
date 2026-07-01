"""Enhetstester för astro_export — ren sträng-generering (stdlib, körs överallt).

  python -m unittest dpt2.publicering.test_astro_export -v
"""

import tempfile
import unittest
from pathlib import Path

from dpt2.publicering import astro_export as AX


class TestYaml(unittest.TestCase):
    def test_skalar_plain_och_citerad(self):
        self.assertEqual(AX._yaml_skalar("Malmö FF"), "Malmö FF")     # plain
        self.assertEqual(AX._yaml_skalar("2026-06-27"), "2026-06-27")  # datum plain
        self.assertEqual(AX._yaml_skalar("a: b"), '"a: b"')            # kolon+space
        self.assertEqual(AX._yaml_skalar("12:00"), '"12:00"')          # kolon
        self.assertEqual(AX._yaml_skalar("true"), '"true"')            # reserverat
        self.assertEqual(AX._yaml_skalar("42"), '"42"')               # tal-sträng

    def test_skalar_bool_och_tal(self):
        self.assertEqual(AX._yaml_skalar(True), "true")
        self.assertEqual(AX._yaml_skalar(3), "3")

    def test_skalar_escapar_citat(self):
        self.assertEqual(AX._yaml_skalar('han sa "hej"'), '"han sa \\"hej\\""')

    def test_frontmatter_hoppar_tomma_och_listor(self):
        y = AX.frontmatter_yaml({"a": "x", "b": None, "c": "", "d": [],
                                 "mal": ["Persson 12'", "Lilja 45'"]})
        self.assertIn("a: x", y)
        self.assertNotIn("b:", y)
        self.assertNotIn("c:", y)
        self.assertNotIn("d:", y)
        self.assertIn("mal:", y)
        self.assertIn("  - Persson 12'", y)


class TestFigur(unittest.TestCase):
    def test_med_och_utan_bildtext(self):
        self.assertEqual(AX.Figur("b.jpg", "alt").markdown(), "![alt](b.jpg)")
        f = AX.Figur("b.jpg", "alt", "Jubel i 90:e")
        self.assertEqual(f.markdown(), "![alt](b.jpg)\n*Jubel i 90:e*")

    def test_figurer_markdown_dicts(self):
        md = AX.figurer_markdown([{"bild": "1.jpg", "alt": "a"},
                                  {"bild": "", "alt": "tom"},   # hoppas (ingen bild)
                                  {"bild": "2.jpg", "bildtext": "x"}])
        self.assertIn("![a](1.jpg)", md)
        self.assertIn("![](2.jpg)", md)
        self.assertNotIn("tom", md)


class TestMatchInnehall(unittest.TestCase):
    MATCH = {"lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
             "datum": "2026-06-27", "liga": "OBOS Damallsvenskan",
             "arena": "Eleda Stadion", "resultat": "6-0", "status": "avslutad"}

    def test_bygger_frontmatter_och_slug(self):
        d = AX.match_innehall(self.MATCH, hero="bilder/hero.jpg",
                              hero_position="center", pixieset="https://x.pixieset.com",
                              malskyttar="Musovic 12', Persson 45'")
        fm = d["frontmatter"]
        self.assertEqual(fm["titel"], "Malmö FF – Kristianstads DFF")
        self.assertEqual(fm["heroPosition"], "center")
        self.assertEqual(fm["malskyttar"], ["Musovic 12'", "Persson 45'"])
        self.assertEqual(d["slug"], "malmo-ff-kristianstads-dff")

    def test_figurer_hamnar_i_body(self):
        d = AX.match_innehall(self.MATCH, body="Inledning.",
                              figurer=[AX.Figur("1.jpg", "jubel", "Segern")])
        self.assertIn("Inledning.", d["body"])
        self.assertIn("![jubel](1.jpg)", d["body"])
        self.assertIn("*Segern*", d["body"])

    def test_full_md_struktur(self):
        d = AX.match_innehall(self.MATCH, body="Text.")
        md = AX.render_md(d["frontmatter"], d["body"])
        self.assertTrue(md.startswith("---\n"))
        self.assertIn("\n---\n", md)
        self.assertIn("titel: Malmö FF – Kristianstads DFF", md)
        self.assertIn("resultat: 6-0", md)
        self.assertTrue(md.rstrip().endswith("Text."))


class TestSlugOchSkriv(unittest.TestCase):
    def test_slugga(self):
        self.assertEqual(AX.slugga("Åre & Östersund vön"), "are-och-ostersund-von")
        self.assertEqual(AX.slugga("!!!"), "innehall")

    def test_skriv_md(self):
        d = Path(tempfile.mkdtemp())
        ut = AX.skriv_md("---\ntyp: match\n---\n", d, "min-match")
        self.assertEqual(ut, d / "min-match.md")
        self.assertTrue(ut.exists())
        self.assertIn("typ: match", ut.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
