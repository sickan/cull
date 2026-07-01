"""Enhetstester för träningskärnan — syntetisk data, ingen bild/modell-laddning
(kräver bara sklearn).

  python -m unittest dpt2.motorer.test_inlarning -v
"""

import tempfile
import unittest


def _har_sklearn():
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


FEAT = ["a", "b", "c"]


def _uppdrag(n, seed):
    """Linjärt separerbart: y=1 när a stort. Deterministiskt utan slump-modul."""
    X, y = [], []
    for i in range(n):
        hog = (i + seed) % 2 == 0
        a = 5.0 + (i % 5) if hog else (i % 5) * 0.2
        X.append([a, (i % 3), (i * 0.1) % 1.0])
        y.append(1 if hog else 0)
    return X, y, "fotboll"


@unittest.skipUnless(_har_sklearn(), "sklearn saknas")
class TestTrana(unittest.TestCase):
    def test_trana_ger_paket_i_ratt_format(self):
        from dpt2.motorer import inlarning
        upp = [_uppdrag(30, 0), _uppdrag(30, 1)]
        paket = inlarning.trana(upp, features=FEAT, typ="din_smak",
                                logg=lambda *_: None)
        self.assertEqual(paket["features"], FEAT)
        self.assertEqual(paket["modell_typ"], "din_smak")
        self.assertEqual(paket["n_uppdrag"], 2)
        self.assertGreater(paket["n_valda"], 0)
        self.assertIn("modell", paket)
        self.assertIn("sparad", paket)

    def test_poangsatt_z_norm_per_uppdrag(self):
        from dpt2.motorer import inlarning
        paket = inlarning.trana([_uppdrag(40, 0), _uppdrag(40, 1)],
                                features=FEAT, logg=lambda *_: None)
        # hög-a-bild ska få högre poäng än låg-a-bild
        res = [{"a": 9.0, "b": 1, "c": 0.2}, {"a": 0.1, "b": 1, "c": 0.2}]
        inlarning.poangsatt_med_modell(res, paket)
        self.assertTrue(all(0.0 <= r["poang"] <= 1.0 for r in res))
        self.assertGreater(res[0]["poang"], res[1]["poang"])

    def test_spara_ladda_round_trip(self):
        from dpt2.motorer import inlarning
        paket = inlarning.trana([_uppdrag(20, 0), _uppdrag(20, 1)],
                                features=FEAT, logg=lambda *_: None)
        p = tempfile.mkdtemp() + "/modell.pkl"
        inlarning.spara_modell(paket, p)
        ut = inlarning.ladda_modell(p)
        self.assertEqual(ut["features"], FEAT)
        self.assertEqual(ut["modell_typ"], paket["modell_typ"])

    def test_tomt_uppdrag_ger_fel(self):
        from dpt2.motorer import inlarning
        with self.assertRaises(ValueError):
            inlarning.trana([([], [], "fotboll")], features=FEAT,
                            logg=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
