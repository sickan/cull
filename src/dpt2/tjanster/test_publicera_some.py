"""Tester för publicera-fan-out (rena regler): FB-strip, karusell-split (10-tak),
story-per-bild, FB-kap (4), validering och dry-run/poster-körning."""

import unittest

from dpt2.tjanster import publicera_some as P


def _bilder(n):
    return [f"/foto/b{i}.jpg" for i in range(1, n + 1)]


class TestStrippaFb(unittest.TestCase):
    def test_tar_bort_hashtags_och_mentions(self):
        t = P.strippa_fb("Vilken match! #malmöff @kdff heja #obosdamallsvenskan")
        self.assertNotIn("#", t)
        self.assertNotIn("@", t)
        self.assertIn("Vilken match!", t)
        self.assertIn("heja", t)

    def test_stadar_dubbla_mellanslag_och_tomrader(self):
        t = P.strippa_fb("Text #tagg\n\n\n@handle\nSlut")
        self.assertNotIn("   ", t)
        self.assertNotIn("\n\n\n", t)

    def test_tom_text(self):
        self.assertEqual(P.strippa_fb(""), "")
        self.assertEqual(P.strippa_fb(None), "")


class TestDelaKarusell(unittest.TestCase):
    def test_under_taket_en_bit(self):
        self.assertEqual(len(P.dela_karusell(_bilder(7))), 1)

    def test_precis_tio_en_bit(self):
        self.assertEqual(len(P.dela_karusell(_bilder(10))), 1)

    def test_elva_delas_i_tva(self):
        bitar = P.dela_karusell(_bilder(11))
        self.assertEqual([len(b) for b in bitar], [10, 1])

    def test_tjugo_delas_i_tva_jamna(self):
        self.assertEqual([len(b) for b in P.dela_karusell(_bilder(20))], [10, 10])

    def test_tom(self):
        self.assertEqual(P.dela_karusell([]), [])


class TestPlanera(unittest.TestCase):
    def test_validering_inga_bilder(self):
        self.assertFalse(P.planera({"mal": {"story": True}})["ok"])

    def test_validering_inget_mal(self):
        self.assertFalse(P.planera({"bilder": _bilder(3)})["ok"])

    def test_story_en_post_per_bild(self):
        r = P.planera({"bilder": _bilder(3), "caption": "hej #x",
                       "mal": {"story": True}})
        stories = [p for p in r["poster"] if p["form"] == "story"]
        self.assertEqual(len(stories), 3)
        self.assertTrue(all(len(p["bilder"]) == 1 for p in stories))
        self.assertEqual([p["del"] for p in stories], [1, 2, 3])
        self.assertEqual(stories[0]["text"], "hej #x")     # story behåller #/@

    def test_ig_inlagg_single(self):
        r = P.planera({"bilder": _bilder(1), "mal": {"ig_inlagg": True}})
        inlagg = [p for p in r["poster"] if p["kanal"] == "instagram"]
        self.assertEqual(len(inlagg), 1)
        self.assertEqual(len(inlagg[0]["bilder"]), 1)

    def test_ig_inlagg_karusell_under_tak(self):
        r = P.planera({"bilder": _bilder(8), "mal": {"ig_inlagg": True}})
        inlagg = [p for p in r["poster"] if p["form"] == "inlägg"
                  and p["kanal"] == "instagram"]
        self.assertEqual(len(inlagg), 1)
        self.assertEqual(len(inlagg[0]["bilder"]), 8)
        self.assertEqual(r["varningar"], [])

    def test_ig_inlagg_over_tak_delas_och_varnar(self):
        r = P.planera({"bilder": _bilder(15), "mal": {"ig_inlagg": True}})
        inlagg = [p for p in r["poster"] if p["kanal"] == "instagram"]
        self.assertEqual(len(inlagg), 2)
        self.assertEqual([len(p["bilder"]) for p in inlagg], [10, 5])
        self.assertEqual([p["av"] for p in inlagg], [2, 2])
        self.assertTrue(any("max" in v for v in r["varningar"]))

    def test_fb_kapas_till_fyra_och_strippar(self):
        r = P.planera({"bilder": _bilder(6), "caption": "Grymt @lag #hej",
                       "mal": {"fb": True}})
        fb = [p for p in r["poster"] if p["kanal"] == "facebook"]
        self.assertEqual(len(fb), 1)
        self.assertEqual(len(fb[0]["bilder"]), 4)
        self.assertNotIn("#", fb[0]["text"])
        self.assertNotIn("@", fb[0]["text"])
        self.assertTrue(any("FB" in v for v in r["varningar"]))

    def test_alla_mal_samtidigt(self):
        r = P.planera({"bilder": _bilder(12), "caption": "c #t",
                       "mal": {"story": True, "ig_inlagg": True, "fb": True}})
        kanaler = {(p["kanal"], p["form"]) for p in r["poster"]}
        self.assertIn(("instagram", "story"), kanaler)
        self.assertIn(("instagram", "inlägg"), kanaler)
        self.assertIn(("facebook", "inlägg"), kanaler)
        # 12 stories + 2 ig-inlägg (10+2) + 1 fb = 15
        self.assertEqual(len(r["poster"]), 12 + 2 + 1)


class TestPublicera(unittest.TestCase):
    def test_dry_run_ror_inga_apier(self):
        anrop = []
        r = P.publicera(
            {"bilder": _bilder(2), "caption": "x", "mal": {"story": True}},
            poster=lambda p: anrop.append(p), dry_run=True, logg=lambda *_: None)
        self.assertTrue(r["ok"])
        self.assertEqual(anrop, [])                          # postern rördes aldrig
        self.assertTrue(all(x["status"] == "dry_run" for x in r["resultat"]))

    def test_skarp_utan_poster_ger_fel(self):
        r = P.publicera({"bilder": _bilder(1), "mal": {"story": True}},
                        dry_run=False, logg=lambda *_: None)
        self.assertFalse(r["ok"])

    def test_skarp_anropar_poster_och_speglar_url(self):
        r = P.publicera(
            {"bilder": _bilder(1), "mal": {"ig_inlagg": True}},
            poster=lambda p: {"ok": True, "url": "https://ig/p/1"},
            dry_run=False, logg=lambda *_: None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["resultat"][0]["status"], "postad")
        self.assertEqual(r["resultat"][0]["url"], "https://ig/p/1")

    def test_en_misslyckad_post_ger_ok_false(self):
        r = P.publicera(
            {"bilder": _bilder(2), "mal": {"story": True}},
            poster=lambda p: {"ok": False, "fel": "token utgången"},
            dry_run=False, logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertTrue(all(x["status"] == "fel" for x in r["resultat"]))


if __name__ == "__main__":
    unittest.main()
