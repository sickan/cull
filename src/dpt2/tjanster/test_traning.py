"""Tester för recompute+retrain-tjänsten — store-facit-väg + träning ur lagrade
vektorer (ingen bild/modell-laddning; kräver sklearn för trana_modell)."""

import tempfile
import unittest
from pathlib import Path

from dpt2.data import db, store


def _har_sklearn():
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


def _vekt(hog, i):
    """Syntetisk feature-vektor (FEATURES-längd 19); feature 0 hög → positiv."""
    v = [0.0] * 19
    v[0] = 5.0 + (i % 3) if hog else (i % 3) * 0.1
    v[8] = 7.0 if hog else 3.0
    return v


class TestFacitStore(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_spara_och_lasa_for_traning(self):
        fid = store.spara_facit(self.c, match_namn="Lag A - Lag B 2-0",
                                sport="fotboll", n=4)
        store.ersatt_facit_rader(self.c, fid, [
            ("s1", 1, 1.0, _vekt(True, 0)),
            ("s2", 0, 1.0, _vekt(False, 1)),
        ])
        # idempotent: omkörning ersätter (ingen dubblett)
        store.ersatt_facit_rader(self.c, fid, [
            ("s1", 1, 1.0, _vekt(True, 0)),
            ("s2", 0, 1.0, _vekt(False, 1)),
            ("s3", 1, 1.0, _vekt(True, 2)),
        ])
        upp = store.facit_for_traning(self.c)
        self.assertEqual(len(upp), 1)
        X, y, sport = upp[0]
        self.assertEqual(len(X), 3)
        self.assertEqual(sport, "fotboll")
        self.assertEqual(sum(y), 2)
        self.assertEqual(len(store.lista_facit(self.c)), 1)


@unittest.skipUnless(_har_sklearn(), "sklearn saknas")
class TestTranaModell(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        for u in range(2):
            fid = store.spara_facit(self.c, match_namn=f"Match {u} 2-0",
                                    sport="fotboll", n=40)
            rader = []
            for i in range(40):
                hog = i % 2 == 0
                rader.append((f"m{u}s{i}", 1 if hog else 0, 1.0, _vekt(hog, i)))
            store.ersatt_facit_rader(self.c, fid, rader)

    def test_trana_modell_sparar_pkl_och_modellrad(self):
        from dpt2.tjanster import traning
        p = Path(tempfile.mkdtemp()) / "modell.pkl"
        res = traning.trana_modell(self.c, typ="arkiv", modell_path=p,
                                   logg=lambda *_: None)
        self.assertTrue(res["ok"])
        self.assertTrue(p.exists())
        # modell-bibliotekrad skapad + aktiv
        mod = store.aktiv_modell(self.c)
        self.assertEqual(mod["typ"], "arkiv")

    def test_inga_facit_ger_fel(self):
        from dpt2.tjanster import traning
        tom = db.oppna(":memory:")
        res = traning.trana_modell(tom, typ="arkiv",
                                   modell_path="/x.pkl", logg=lambda *_: None)
        self.assertFalse(res["ok"])


class TestLarAvMatch(unittest.TestCase):
    """Lär av match: en gallrad mapp → ett facit-uppdrag med features, alla
    valda (label=1). Extraktionen mockas (ingen bild/modell-laddning)."""

    def setUp(self):
        self.c = db.oppna(":memory:")

    def _kor(self, stems):
        from dpt2.motorer import extraktion
        from dpt2.tjanster import leverera, traning
        paths = [f"/urval/{s}.NEF" for s in stems]
        X = [_vekt(True, i) for i in range(len(stems))]
        orig_lista, orig_feat = leverera.lista_bilder, extraktion.features_for_bilder
        leverera.lista_bilder = lambda mapp: paths
        extraktion.features_for_bilder = lambda p, m, **kw: (X, list(stems))
        try:
            return traning.lar_av_match(self.c, "/urval", modeller=None,
                                        match_namn="MFF – KDFF", sport="fotboll",
                                        logg=lambda *_: None)
        finally:
            leverera.lista_bilder = orig_lista
            extraktion.features_for_bilder = orig_feat

    def test_markning_lagras_som_valt_facit(self):
        r = self._kor(["a", "b", "c"])
        self.assertEqual(r["n_bilder"], 3)
        self.assertEqual(r["valda"], 3)
        self.assertEqual(r["namn"], "MFF – KDFF")
        # Facit-rader lagrade MED vektorer → syns i träningsdatan (alla valda)
        upp = store.facit_for_traning(self.c)
        self.assertEqual(len(upp), 1)
        X, y, sport = upp[0]
        self.assertEqual(len(X), 3)
        self.assertEqual(sum(y), 3)
        self.assertEqual(sport, "fotboll")
        # Syns i historiken
        hist = store.lista_facit(self.c)
        self.assertEqual(hist[0]["match_namn"], "MFF – KDFF")
        self.assertEqual(hist[0]["n"], 3)

    def test_idempotent_omkorning_ersatter(self):
        self._kor(["a", "b", "c"])
        self._kor(["a", "b"])
        self.assertEqual(len(store.lista_facit(self.c)), 1)  # ingen dubblett
        self.assertEqual(store.lista_facit(self.c)[0]["n"], 2)

    def test_tom_mapp_ger_fel(self):
        from dpt2.tjanster import leverera, traning
        orig = leverera.lista_bilder
        leverera.lista_bilder = lambda mapp: []
        try:
            r = traning.lar_av_match(self.c, "/tom", modeller=None,
                                     logg=lambda *_: None)
        finally:
            leverera.lista_bilder = orig
        self.assertIn("fel", r)
        self.assertEqual(r["n_bilder"], 0)


if __name__ == "__main__":
    unittest.main()
