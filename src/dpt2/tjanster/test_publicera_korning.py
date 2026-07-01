"""Tester för publicera-orkestreringen (glue): dry-run spårar inget, skarp körning
skriver some_material-rader per lyckad post, misslyckad post → ok:False."""

import unittest

from dpt2.data import db, store
from dpt2.tjanster import publicera_korning as K


def _config(n=3, **extra):
    c = {"bilder": [f"/foto/b{i}.jpg" for i in range(1, n + 1)],
         "caption": "Matchdag! #malmöff @kdff", "mal": {"story": True, "fb": True}}
    c.update(extra)
    return c


class TestKorPublicering(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.mid = store.spara_match(self.c, {"lag_hemma": "A", "lag_borta": "B"})

    def test_validering_bubblar_upp(self):
        r = K.kor_publicering(self.c, {"bilder": [], "mal": {"story": True}},
                              logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["sparade"], 0)

    def test_dry_run_sparar_inget(self):
        r = K.kor_publicering(self.c, _config(match_id=self.mid, moment="Avspark"),
                              dry_run=True, logg=lambda *_: None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["sparade"], 0)
        self.assertEqual(store.lista_some_material(self.c, self.mid), [])

    def test_skarp_sparar_en_rad_per_post(self):
        # 3 bilder, mål story+fb → 3 stories + 1 fb = 4 poster
        r = K.kor_publicering(
            self.c, _config(match_id=self.mid, moment="Avspark", tema="Hav"),
            poster=lambda p: {"ok": True, "url": "https://x/1"},
            dry_run=False, logg=lambda *_: None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["sparade"], 4)
        rader = store.lista_some_material(self.c, self.mid)
        self.assertEqual(len(rader), 4)
        self.assertEqual({row["kanal"] for row in rader}, {"instagram", "facebook"})
        self.assertTrue(all(row["moment"] == "Avspark" for row in rader))
        self.assertTrue(all(row["tema"] == "Hav" for row in rader))

    def test_misslyckad_post_ger_ok_false_och_sparar_bara_lyckade(self):
        # postern nekar allt → inga rader, ok:False
        r = K.kor_publicering(
            self.c, _config(n=2, match_id=self.mid, moment="Halvtid"),
            poster=lambda p: {"ok": False, "fel": "token utgången"},
            dry_run=False, logg=lambda *_: None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["sparade"], 0)
        self.assertEqual(store.lista_some_material(self.c, self.mid), [])


if __name__ == "__main__":
    unittest.main()
