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


class TestModellPaket(unittest.TestCase):
    """BUG-CULL-01: UI-etiketten ("Din smak") missade typnyckel-uppslaget →
    varje cull föll tyst till den handsatta formeln trots tränade modeller."""

    def test_normaliserar_ui_etiketter(self):
        for varde, vantad in [("Din smak", "din_smak"), ("din_smak", "din_smak"),
                              ("Arkiv (facit)", "arkiv"), ("arkiv", "arkiv"),
                              ("ARKIV", "arkiv"), ("Hybrid", "hybrid"),
                              (" Din Smak ", "din_smak")]:
            self.assertEqual(G._modell_typ(varde), vantad, varde)
        self.assertIsNone(G._modell_typ(None))
        self.assertIsNone(G._modell_typ(""))
        self.assertIsNone(G._modell_typ("okänd"))

    def test_paket_hittas_via_ui_etikett(self):
        # Etiketten "Din smak" ska nå samma modellrad som typnyckeln.
        from unittest import mock
        from dpt2.data import store as st
        from dpt2.motorer import inlarning as inl
        rader = [{"typ": "arkiv", "pkl_path": "/m/arkiv.pkl"},
                 {"typ": "din_smak", "pkl_path": "/m/din_smak.pkl"}]
        laddade = []
        with mock.patch.object(st, "lista_modeller", lambda conn: rader), \
             mock.patch.object(inl, "ladda_modell",
                               lambda p: laddade.append(p) or {"pkl": p}):
            self.assertEqual(G._modell_paket(None, "Din smak"),
                             {"pkl": "/m/din_smak.pkl"})
            self.assertEqual(G._modell_paket(None, "Arkiv (facit)"),
                             {"pkl": "/m/arkiv.pkl"})
            self.assertIsNone(G._modell_paket(None, "Hybrid"))   # ej tränad än
            self.assertIsNone(G._modell_paket(None, None))
        self.assertEqual(laddade, ["/m/din_smak.pkl", "/m/arkiv.pkl"])


if __name__ == "__main__":
    unittest.main()
