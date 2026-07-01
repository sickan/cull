"""Tester för gallrings-orkestreringens rena delar (cfg-mappning). Den skarpa
end-to-end-cullen kräver bilder + modeller → körs via worker manuellt."""

import unittest

from dpt2.tjanster import gallring_korning as G


class TestCfgAvJobb(unittest.TestCase):
    def test_bilder_ger_topp(self):
        cfg = G._cfg_av_jobb({"behall_enhet": "bilder", "behall_varde": 40,
                              "verktyg": "ai", "burst_grans": 2.5})
        self.assertEqual(cfg.topp, 40)
        self.assertIsNone(cfg.andel and None)   # andel default men topp styr
        self.assertEqual(cfg.burst_sek, 2.5)
        self.assertTrue(cfg.ai)

    def test_procent_ger_andel(self):
        cfg = G._cfg_av_jobb({"behall_enhet": "procent", "behall_varde": 25,
                              "verktyg": "rapport"})
        self.assertAlmostEqual(cfg.andel, 0.25)
        self.assertIsNone(cfg.topp)
        self.assertFalse(cfg.ai)               # rapport → ai=False

    def test_tomt_jobb_ger_default(self):
        cfg = G._cfg_av_jobb(None)
        self.assertAlmostEqual(cfg.andel, 0.10)
        self.assertEqual(cfg.burst_sek, 2.0)


if __name__ == "__main__":
    unittest.main()
