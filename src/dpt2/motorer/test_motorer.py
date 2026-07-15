"""Enhetstester för migrerade KÄRN-motorer (Fas 0 steg 3).

Körs med valfri Python via `python -m unittest dpt2.motorer.test_motorer`.
Ren-logik-tester körs överallt; dep-bundna tester hoppas över om biblioteket
saknas (markeras som skipped, inte fail). Kör i dpt-venv för full täckning:
  ~/.local/pipx/venvs/dpt/bin/python -m unittest dpt2.motorer.test_motorer -v
"""

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


def _har(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


HAR_CV2 = _har("cv2")
HAR_NP = _har("numpy")
HAR_PIL = _har("PIL")
HAR_VISION = _har("Vision")


# ── roster (stdlib — körs alltid) ─────────────────────────────────────────────
class TestRoster(unittest.TestCase):
    def setUp(self):
        self.csv = Path(tempfile.mkdtemp()) / "r.csv"
        with open(self.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nummer", "namn", "lag"])
            w.writerow(["1", "Zecira Musovic", "hemma"])
            w.writerow(["2", "Nathalie Hoff Persson", "hemma"])
            w.writerow(["10", "Mia Persson", "borta"])

    def test_las_roster(self):
        from dpt2.motorer import roster
        r = roster.las_roster(self.csv)
        self.assertIn("Zecira Musovic", r.values())
        self.assertEqual(len(r), 3)

    def test_las_roster_lag(self):
        from dpt2.motorer import roster
        r = roster.las_roster_lag(self.csv)
        self.assertIn("hemma", r)
        self.assertIn("borta", r)
        self.assertIn("Mia Persson", r["borta"].values())

    def test_lista_text_och_namnge(self):
        from dpt2.motorer import roster
        r = roster.las_roster(self.csv)
        txt = roster.lista_text(r)
        self.assertIsInstance(txt, str)
        self.assertIn("Zecira Musovic", txt)

    def test_saknad_fil_ger_tomt(self):
        from dpt2.motorer import roster
        self.assertEqual(roster.las_roster(Path("/finns/inte.csv")), {})


# ── matchfas (stdlib — körs alltid) ───────────────────────────────────────────
class TestMatchfas(unittest.TestCase):
    def test_parse_tid_exif(self):
        from dpt2.motorer import matchfas
        ts = matchfas.parse_tid("2026:06:27 14:30:05")
        self.assertIsInstance(ts, float)
        self.assertIsNone(matchfas.parse_tid("skräp"))

    def test_parse_avspark(self):
        from dpt2.motorer import matchfas
        ref = datetime(2026, 6, 27, 9, 0, 0)
        ts = matchfas.parse_avspark("14:00", ref)
        self.assertEqual(datetime.fromtimestamp(ts).hour, 14)

    def test_matchminut(self):
        from dpt2.motorer import matchfas
        avspark = datetime(2026, 6, 27, 14, 0).timestamp()
        bild = datetime(2026, 6, 27, 14, 45).timestamp()
        self.assertAlmostEqual(matchfas.matchminut(bild, avspark), 45.0, places=3)

    def test_fas_bonus_zoner(self):
        from dpt2.motorer import matchfas
        self.assertLess(matchfas.fas_bonus(-30), 0)      # tidig uppvärmning
        self.assertLess(matchfas.fas_bonus(-10), 0)      # sen uppvärmning
        self.assertGreater(matchfas.fas_bonus(42), 0)    # slutminut HL1
        self.assertGreater(matchfas.fas_bonus(90), 0)    # slutminut HL2
        self.assertGreater(matchfas.fas_bonus(110), 0)   # förlängning
        self.assertEqual(matchfas.fas_bonus(20), 0.0)    # mitt i halvlek

    def test_uppskatta_avspark(self):
        from dpt2.motorer import matchfas
        base = datetime(2026, 6, 27, 14, 0).timestamp()
        # Realistiskt: gles uppvärmning, paus, sen tät matchskur. Spann måste
        # vara > 20 min och avsparken ligga i första 60 % av tidslinjen.
        warm = [base - 900 + i * 180 for i in range(4)]      # gles (gap 180s)
        match = [base + i * 8 for i in range(120)]           # tät skur från avspark
        gissning = matchfas.uppskatta_avspark(warm + match)
        self.assertIsNotNone(gissning)
        self.assertAlmostEqual(gissning, base, delta=60)     # ~ avspark


# ── vitbalans (ren dict-logik — kräver bara numpy) ────────────────────────────
@unittest.skipUnless(HAR_NP, "numpy saknas")
class TestVitbalans(unittest.TestCase):
    def test_korrigering_neutral(self):
        from dpt2.motorer import vitbalans
        self.assertEqual(vitbalans.korrigering({}), (0.0, 0.0))
        self.assertEqual(
            vitbalans.korrigering({"vit": {"temp": 1.0, "tint": 1.0}}), (0.0, 0.0))

    def test_korrigering_varmt_kyler(self):
        from dpt2.motorer import vitbalans
        dk, dt = vitbalans.korrigering({"vit": {"temp": 1.10, "tint": 1.0}})
        self.assertLess(dk, 0)        # varmt → negativ Kelvin-delta

    def test_formattera_tal(self):
        from dpt2.motorer import vitbalans
        self.assertIsNone(vitbalans.formattera(None))


# ── xmp_writer (ren beräkning + sidecar-skrivning) ────────────────────────────
@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestXmpWriter(unittest.TestCase):
    def test_brus_av_iso(self):
        from dpt2.motorer import xmp_writer
        self.assertIsNone(xmp_writer.brus_av_iso(800))
        self.assertEqual(xmp_writer.brus_av_iso(2000), (10, 25, 50))
        self.assertEqual(xmp_writer.brus_av_iso(20000), (38, 55, 40))

    def test_skriv_xmp_sidecar(self):
        from dpt2.motorer import xmp_writer
        d = Path(tempfile.mkdtemp())
        nef = d / "_TEST0001.nef"
        nef.write_bytes(b"")           # innehållet läses inte
        ut = xmp_writer.skriv_xmp(nef, rating=5, label="Blue", iso=6400)
        self.assertTrue(Path(ut).exists())
        txt = Path(ut).read_text(encoding="utf-8")
        self.assertIn("xmp:Rating", txt)
        self.assertIn("Blue", txt)


# ── bas (klassiska bildmått på syntetiska arrayer) ────────────────────────────
@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestBas(unittest.TestCase):
    def _gray(self):
        import numpy as np
        g = np.tile(np.linspace(0, 255, 128, dtype="uint8"), (128, 1))
        return g

    def test_skarpa_returnerar_tal(self):
        from dpt2.motorer import bas
        v = bas.skarpa(self._gray())
        self.assertIsInstance(float(v), float)

    def test_exponering_och_motljus(self):
        from dpt2.motorer import bas
        g = self._gray()
        self.assertIsNotNone(bas.exponering(g))
        self.assertIsNotNone(bas.motljus(g))


# ── story_overlay (rena parsers — kräver att modulen importeras) ──────────────
@unittest.skipUnless(HAR_PIL and HAR_NP, "PIL/numpy saknas")
class TestStoryOverlay(unittest.TestCase):
    def test_normera_lag(self):
        from dpt2.motorer import story_overlay
        self.assertEqual(story_overlay.normera_lag("Malmö FF"), "malmö_ff")

    def test_assets_finns(self):
        # Asset-omdirigeringen ska peka på dpt2/assets med typsnitt + temaloggor.
        from dpt2.motorer import story_overlay
        self.assertTrue((story_overlay.FONTS_DIR / "Saira-Variable.ttf").exists())
        self.assertTrue((story_overlay.TEMA_LOGG_DIR / "logo-hav.png").exists())

    def test_tolka_matchinfo(self):
        from dpt2.motorer import story_overlay
        d = story_overlay.tolka_matchinfo(
            "Malmö FF - Kristianstad DFF 20260627 Eleda Stadion 14:00")
        self.assertEqual(d["lag_hemma"], "Malmö FF")
        self.assertEqual(d["lag_borta"], "Kristianstad DFF")
        self.assertEqual(d["datum"], "20260627")
        self.assertIn("Eleda", d["arena"])
        self.assertEqual(d["tid"], "14:00")

    def test_monogram_text(self):
        # Lagsport: förkortning. Individ-sport: personinitialer.
        from dpt2.motorer import story_overlay as so
        self.assertEqual(so.monogram_text("Malmö FF", "HEM"), "MAL")
        self.assertEqual(so.monogram_text("Rebecca Peterson", "HEM", individ=True), "RP")
        self.assertEqual(so.monogram_text("Mirjam Björklund", "BORT", individ=True), "MB")
        self.assertEqual(so.monogram_text("", "HEM", individ=True), "HEM")

    def test_startmoment_i_alla_profiler(self):
        # Stora ordet i preview-blocket hämtas ur profilen — varje sport ska ha
        # ett start_moment (fotboll "Avspark", tennis "Matchstart", friidrott
        # "Start") så tennis-storyn inte säger "AVSPARK".
        from dpt2.data import sportprofil
        for sport in ("fotboll", "handboll", "innebandy", "volleyboll",
                      "beachvolley", "tennis", "friidrott"):
            self.assertTrue(sportprofil.profil(sport).get("start_moment"),
                            f"{sport} saknar start_moment")
        self.assertEqual(sportprofil.profil("tennis")["start_moment"], "Matchstart")
        self.assertEqual(sportprofil.profil("fotboll")["start_moment"], "Avspark")


# ── vision_lager (PyObjC) ─────────────────────────────────────────────────────
@unittest.skipUnless(HAR_VISION, "Apple Vision saknas")
class TestVisionLager(unittest.TestCase):
    def test_tillganglig(self):
        from dpt2.motorer import vision_lager
        self.assertTrue(vision_lager.tillganglig())


# ── clip_lager (torch/clip lazy → modulen importerbar med cv2/numpy) ──────────
@unittest.skipUnless(HAR_CV2 and HAR_NP, "cv2/numpy saknas")
class TestClipLager(unittest.TestCase):
    def test_importerbar_och_features(self):
        from dpt2.motorer import clip_lager
        self.assertTrue(hasattr(clip_lager, "CLIP_FEATURES"))
        self.assertGreater(len(clip_lager.CLIP_FEATURES), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
