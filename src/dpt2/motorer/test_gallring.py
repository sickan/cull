"""Tester för poäng-/urvalsmotorn (gallring). Ren stdlib → körs överallt;
percentil-ekvivalenstestet kräver numpy och hoppas annars över."""

import unittest

from dpt2.motorer import gallring as G
from dpt2.motorer.gallring import Gallring


def _har(mod):
    try:
        __import__(mod); return True
    except Exception:
        return False


HAR_NP = _har("numpy")


def _rad(fil, **kw):
    r = {"fil": fil, "skarpa": 50.0, "exp": 0.5, "ansikten": 0, "ogon": 0,
         "armar": 0.0, "boll": 0.0, "hemma": 0.0, "trojnummer": 0.0,
         "klunga": 0.0, "fas": 0.0, "vast": 0, "nima": None, "_nummer": []}
    r.update(kw)
    return r


class TestPercentil(unittest.TestCase):
    @unittest.skipUnless(HAR_NP, "numpy saknas")
    def test_ekvivalent_med_numpy(self):
        import numpy as np
        data = [0, 5, 5, 12, 40, 41, 90, 91, 100, 250]
        for p in (5, 25, 50, 75, 95):
            self.assertAlmostEqual(G._percentil(data, p),
                                   float(np.percentile(data, p)), places=6)

    def test_kantfall(self):
        self.assertEqual(G._percentil([], 50), 0.0)
        self.assertEqual(G._percentil([7], 50), 7.0)


class TestPoang(unittest.TestCase):
    def test_normalisera_skarpa(self):
        rs = [_rad("a", skarpa=0.0), _rad("b", skarpa=50.0), _rad("c", skarpa=100.0)]
        G.normalisera(rs)
        # lo=perc5=5, hi=perc95=95, spann=90
        d = {r["fil"]: r["skarpa_n"] for r in rs}
        self.assertAlmostEqual(d["a"], 0.0, places=6)          # clip neg → 0
        self.assertAlmostEqual(d["b"], (50 - 5) / 90, places=6)
        self.assertAlmostEqual(d["c"], 1.0, places=6)          # clip >1 → 1

    def test_handsatt_formel(self):
        # En rad där skarpa_n blir exakt 0.5 (mittenvärdet ovan), exp=0.4,
        # ögon: 2 ansikten, 4 ögon → min(4/4,1)*0.10 = 0.10; + armar 0.2
        rs = [_rad("a", skarpa=0.0), _rad("b", skarpa=50.0, exp=0.4,
                   ansikten=2, ogon=4, armar=0.2), _rad("c", skarpa=100.0)]
        G.normalisera(rs)
        G.poangsatt_handsatt(rs)
        b = next(r for r in rs if r["fil"] == "b")
        vantat = 0.55 * 0.5 + 0.35 * 0.4 + 0.10 + 0.2
        self.assertAlmostEqual(b["poang"], vantat, places=6)

    def test_firande_boost(self):
        r = _rad("a", armar=0.3, klunga=0.1)
        r["poang"] = 1.0
        G.firande_boost([r], 2)         # +2*0.05*(0.4)=0.04
        self.assertAlmostEqual(r["poang"], 1.04, places=6)

    def test_vast_straff(self):
        r = _rad("a", vast=5); r["poang"] = 1.0
        G.vast_straff([r])              # -0.08*min(5,3)=-0.24
        self.assertAlmostEqual(r["poang"], 1.0 - 0.24, places=6)


class TestBurst(unittest.TestCase):
    def test_gruppering_pa_tid(self):
        # tre i samma skur, sen ett gap > burst_sek, sen två
        rs = [_rad("a", tid="2026:06:27 14:00:00"),
              _rad("b", tid="2026:06:27 14:00:01"),
              _rad("c", tid="2026:06:27 14:00:02"),
              _rad("d", tid="2026:06:27 14:00:10"),
              _rad("e", tid="2026:06:27 14:00:11")]
        G.burst_grupper(rs, burst_sek=2.0)
        g = {r["fil"]: r["grupp"] for r in rs}
        self.assertEqual(g["a"], g["b"], )
        self.assertEqual(g["b"], g["c"])
        self.assertNotEqual(g["c"], g["d"])   # gapet bryter gruppen
        self.assertEqual(g["d"], g["e"])

    def test_utan_tid_egen_grupp(self):
        rs = [_rad("a"), _rad("b"), _rad("c")]
        G.burst_grupper(rs, 2.0)
        self.assertEqual(len({r["grupp"] for r in rs}), 3)


class TestValj(unittest.TestCase):
    def _set(self, poang_lista):
        rs = []
        for i, p in enumerate(poang_lista):
            r = _rad(f"f{i}"); r["poang"] = p; r["grupp"] = i
            rs.append(r)
        return rs

    def test_topp_n(self):
        rs = self._set([0.1, 0.9, 0.5, 0.7, 0.2])
        valda, info = G.valj(rs, Gallring(ai=False, topp=2))
        self.assertEqual({r["fil"] for r in valda}, {"f1", "f3"})  # 0.9, 0.7
        self.assertEqual(info["n_behall"], 2)

    def test_burst_representant(self):
        # två i samma grupp → bästa är gruppens representant. topp=1 så ingen
        # backfill sker (med topp>1 fyller core på med resten, rad 1669-1674).
        rs = self._set([0.3, 0.8])
        for r in rs:
            r["grupp"] = 0
        valda, info = G.valj(rs, Gallring(ai=False, topp=1))
        self.assertEqual(info["n_grupper"], 1)
        self.assertEqual([r["fil"] for r in valda], ["f1"])      # 0.8

    def test_backfill_over_burstgrupper(self):
        # topp större än antal grupper → backfill med icke-representanter
        rs = self._set([0.3, 0.8])
        for r in rs:
            r["grupp"] = 0
        valda, _ = G.valj(rs, Gallring(ai=False, topp=5))
        self.assertEqual({r["fil"] for r in valda}, {"f0", "f1"})

    def test_skyddade_alltid_med(self):
        rs = self._set([0.9, 0.8, 0.1])      # f2 svagast
        cfg = Gallring(ai=True, topp=2, skyddade={"f2"})
        valda, info = G.valj(rs, cfg)
        ids = {r["fil"] for r in valda}
        self.assertIn("f2", ids)             # skyddad in trots låg poäng
        self.assertEqual(len(valda), 2)      # behåller n_behall
        self.assertEqual(info["skyddade"], 1)

    def test_garanti_firande(self):
        rs = self._set([0.9, 0.8, 0.05])
        rs[2]["armar"] = 0.5                 # firande men låg totalpoäng
        cfg = Gallring(ai=True, topp=2, garanti_firande=1)
        valda, info = G.valj(rs, cfg)
        self.assertIn("f2", {r["fil"] for r in valda})
        self.assertEqual(info["firande"], 1)

    def test_garanti_bevaka(self):
        rs = self._set([0.9, 0.8, 0.05])
        rs[2]["_nummer"] = ["10"]
        cfg = Gallring(ai=True, topp=2, garanti_bevaka=1, bevaka={"10"})
        valda, info = G.valj(rs, cfg)
        self.assertIn("f2", {r["fil"] for r in valda})
        self.assertEqual(info["bevaka"], 1)


class TestStjarnor(unittest.TestCase):
    def test_monotont(self):
        valda = [{"fil": f"f{i}", "poang": p}
                 for i, p in enumerate([0.1, 0.3, 0.5, 0.7, 0.9])]
        st = G.stjarnor_av_poang(valda)
        self.assertEqual(st["f4"], 5)        # högst
        self.assertEqual(st["f0"], 2)        # lägst
        self.assertGreaterEqual(st["f3"], st["f1"])


class TestGallraEndToEnd(unittest.TestCase):
    def test_handsatt_pipeline(self):
        rs = [_rad(f"f{i}", skarpa=float(i * 10), exp=0.5,
                   tid=f"2026:06:27 14:00:{i:02d}") for i in range(10)]
        valda, info = G.gallra(rs, Gallring(ai=True, topp=3, burst_sek=0.5))
        self.assertEqual(len(valda), 3)
        self.assertEqual(info["n_total"], 10)
        # alla valda har poäng satt
        self.assertTrue(all("poang" in r for r in valda))


if __name__ == "__main__":
    unittest.main(verbosity=2)
