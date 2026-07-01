"""Kontrakt-test för den förenade extraktionen — FEATURES-ordningen är FRYST
(beslut 3) och får inte ändras utan medveten omträning. Den skarpa golden-
verifieringen mot facit ligger i verifiera_golden.py (kräver volym + modeller).
"""

import unittest


class TestFeaturesKontrakt(unittest.TestCase):
    def test_ordning_och_langd(self):
        from dpt2.motorer.extraktion import FEATURES
        self.assertEqual(FEATURES, [
            "skarpa", "exp", "ansikten", "ogon", "armar", "klunga",
            "boll", "personer", "nima", "motljus", "rorelse", "bakgrund",
            "keeper", "ogonkontakt",
            "clip_firande", "clip_narkamp", "clip_portratt",
            "clip_uppvarmning", "clip_publik"])
        self.assertEqual(len(FEATURES), 19)

    def test_clip_features_sist(self):
        from dpt2.motorer.extraktion import FEATURES
        from dpt2.motorer.clip_lager import CLIP_FEATURES
        self.assertEqual(FEATURES[-len(CLIP_FEATURES):], CLIP_FEATURES)


if __name__ == "__main__":
    unittest.main()
