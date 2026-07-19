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

    def test_las_roll_vinklar_parsar_och_filtrerar(self):
        import json
        import subprocess
        from unittest import mock
        from dpt2.motorer import xmp_writer
        svar = json.dumps([
            {"SourceFile": "/x/a.nef", "RollAngle": 1.1, "PitchAngle": 0.3},
            {"SourceFile": "/x/b.nef", "RollAngle": -2.0, "PitchAngle": -1.0},
            {"SourceFile": "/x/c.nef", "RollAngle": 11.8, "PitchAngle": 0.0},
            {"SourceFile": "/x/d.nef"},                       # ingen gyrotagg
            {"SourceFile": "/x/e.nef", "RollAngle": 1.8, "PitchAngle": 5.3},
            # rak, rimlig vinkel — men kropp med obrukbar givare
            {"SourceFile": "/x/f.nef", "RollAngle": -6.1, "PitchAngle": 1.3,
             "Model": "NIKON D5"},
        ])
        with mock.patch.object(subprocess, "run",
                               return_value=mock.Mock(stdout=svar)):
            ut = xmp_writer.las_roll_vinklar(
                [Path("/x/a.nef"), Path("/x/b.nef"), Path("/x/c.nef"),
                 Path("/x/d.nef"), Path("/x/e.nef"), Path("/x/f.nef")])
        # CropAngle = +RollAngle rakt av (LR-katalog-verifierat 18/7) —
        # ingen negering får smyga in här.
        self.assertEqual(ut[Path("/x/a.nef")], 1.1)
        self.assertEqual(ut[Path("/x/b.nef")], -2.0)
        self.assertNotIn(Path("/x/c.nef"), ut)   # >8° = medveten lutning
        self.assertNotIn(Path("/x/d.nef"), ut)   # ingen gyrotagg alls
        # Nickad kamera: taggen finns men värdet duger inte -> None, så
        # anroparen lämnar bilden orörd i stället för att gissa.
        self.assertIn(Path("/x/e.nef"), ut)
        self.assertIsNone(ut[Path("/x/e.nef")])
        # D5:ans givare är obrukbar även på raka bilder — aldrig ett tal här.
        self.assertIn(Path("/x/f.nef"), ut)
        self.assertIsNone(ut[Path("/x/f.nef")])

    def test_las_roll_vinklar_tom_och_trasig(self):
        import subprocess
        from unittest import mock
        from dpt2.motorer import xmp_writer
        self.assertEqual(xmp_writer.las_roll_vinklar([]), {})
        with mock.patch.object(subprocess, "run",
                               return_value=mock.Mock(stdout="inte json")):
            self.assertEqual(
                xmp_writer.las_roll_vinklar([Path("/x/a.nef")]), {})


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

    def test_friidrott_hjalpare(self):
        # D2-svarets regler: serie med decimalkomma + × för övertramp,
        # svenska ordinaler (11/12 → :e), stort ord-trösklar, enheter.
        from dpt2.motorer import story_overlay as so
        self.assertEqual(so.formattera_serie("6,21, 6,42, x, 6,38"),
                         "6,21 · 6,42 · × · 6,38")
        self.assertEqual(so.formattera_serie("6,21 6,42 X 6,38"),
                         "6,21 · 6,42 · × · 6,38")
        self.assertEqual([str(n) + so.ordinal_text(n)
                          for n in (1, 2, 3, 11, 12, 21)],
                         ["1:a", "2:a", "3:e", "11:e", "12:e", "21:a"])
        self.assertEqual(so.friidrott_stort_ord_storlek("LÄNGD"), 150)
        self.assertEqual(so.friidrott_stort_ord_storlek("KULSTÖTNING F"), 118)
        self.assertEqual(so.friidrott_stort_ord_storlek("MARATONLÖPNING"), 96)
        self.assertEqual(so.resultat_enhet("hoppkast"), "m")
        self.assertEqual(so.resultat_enhet("mangkamp"), "p")
        self.assertEqual(so.resultat_enhet("sprint"), "")
        self.assertEqual(so.MEDALJ_FARG[1][:3], (217, 178, 76))   # guld #D9B24C

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


# ── M18-8: lagbrickan ─────────────────────────────────────────────────────────
class TestLagbricka(unittest.TestCase):
    """Roten till M18-8: loggan fyllde brickan och cirkelmasken åt upp kanterna.
    Nu dras loggan in — och en logga utan transparens får ljus platta."""

    def _logga(self, storlek=400, transparent=True, form="hog"):
        """Bygger en syntetisk logga som når HELA vägen ut i rutan (det är den
        formen som blev kapad — MFF:s höga sköld)."""
        from PIL import Image, ImageDraw
        bg = (0, 0, 0, 0) if transparent else (255, 255, 255, 255)
        im = Image.new("RGBA", (storlek, storlek), bg)
        d = ImageDraw.Draw(im)
        if form == "hog":
            d.rectangle((storlek // 3, 0, 2 * storlek // 3, storlek - 1),
                        fill=(20, 60, 160, 255))
        else:
            d.ellipse((0, 0, storlek - 1, storlek - 1), fill=(20, 60, 160, 255))
        return im

    def _spara(self, im):
        import tempfile
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        im.save(f.name)
        return f.name

    def test_har_transparens_skiljer_akta_fran_inbakad(self):
        from dpt2.motorer import story_overlay as so
        self.assertTrue(so.har_transparens(self._logga(transparent=True)))
        self.assertFalse(so.har_transparens(self._logga(transparent=False)))

    def test_transparent_logga_kapas_inte(self):
        """Regressionsvakt för M18-8: märkets topp- och bottenpixlar ska
        överleva. Före fixen nollades de av cirkelmasken."""
        import numpy as np
        from dpt2.motorer import story_overlay as so
        S = 128
        b = so._rund_bricka(self._spara(self._logga(form="hog")), S, "XX")
        a = np.asarray(b.getchannel("A"))
        mitt = S // 2
        # Kolumnen genom märket ska ha synliga pixlar en bra bit upp och ner,
        # inte bara i den innersta cirkeln.
        kolumn = a[:, mitt]
        synliga = np.nonzero(kolumn > 40)[0]
        self.assertLess(synliga.min(), S * 0.25, "märkets topp kapades")
        self.assertGreater(synliga.max(), S * 0.75, "märkets botten kapades")

    def test_logga_utan_transparens_far_ljus_platta(self):
        """Skyddsnätet: en fil med inbakad bakgrund ska bli en snygg bricka,
        aldrig en vit fyrkant i en publicerad bild."""
        import numpy as np
        from dpt2.motorer import story_overlay as so
        S = 128
        b = so._rund_bricka(self._spara(self._logga(transparent=False)), S, "XX")
        a = np.asarray(b)
        # Hörnet ska vara helt genomskinligt (cirkeln klipper fyrkanten bort)
        self.assertEqual(int(a[2, 2, 3]), 0, "hörnet är inte bortklippt")
        # Kanten mitt på vänstersidan ska vara ogenomskinlig OCH ljus (plattan)
        self.assertGreater(int(a[S // 2, 3, 3]), 200)
        self.assertGreater(int(a[S // 2, 3, :3].mean()), 200)

    def test_utan_logga_ger_monogram_som_forut(self):
        from dpt2.motorer import story_overlay as so
        b = so._rund_bricka(None, 128, "MAL")
        self.assertEqual(b.size, (128, 128))
        self.assertEqual(int(__import__("numpy").asarray(b)[2, 2, 3]), 0)


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
