"""Tester för story-orkestreringens rena delar (matchfält-härledning +
validering). Den skarpa renderingen körs via worker (PIL, riktigt foto)."""

import unittest

from dpt2.data import db, store
from dpt2.tjanster import story_korning as S


class TestMatchfalt(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_fyller_ur_match_inkl_startelva(self):
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "KDFF", "liga": "OBOS",
            "arena": "Eleda", "resultat": "6-0", "datum": "2026-06-27",
            "spelare": [
                {"nr": "1", "namn": "Musovic", "lag": "hemma", "start": True},
                {"nr": "9", "namn": "Reserv", "lag": "hemma", "start": False},
                {"nr": "5", "namn": "Borta", "lag": "borta", "start": True},
            ]})
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(f["lag_hemma"], "Malmö FF")
        self.assertEqual(f["liga"], "OBOS")
        self.assertEqual(f["stallning"], "6-0")
        self.assertIn("Musovic", f["startelva"])
        self.assertNotIn("Borta", f["startelva"])       # bara hemma-start
        self.assertNotIn("Reserv", f["startelva"])       # bara start=True

    def test_gren_ur_matchen_med_config_fallback(self):
        # gren-kanten härleds ur hemmalagets gren (matchlogik._gren, samma
        # källa som gren-markören på matchkort/matchlista i appen).
        mid = store.spara_match(self.c, {"lag_hemma": "Malmö FF", "lag_borta": "KDFF"})
        store.upsert_lag(self.c, "Malmö FF", gren="dam")
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(f["gren"], "dam")
        # utan matchat match_id → config som fallback (Live-flödets fritext-läge)
        f2 = S._matchfalt(self.c, {"lag_hemma": "A", "gren": "herr"})
        self.assertEqual(f2["gren"], "herr")

    def test_config_fallback_utan_match(self):
        f = S._matchfalt(self.c, {"lag_hemma": "A", "lag_borta": "B"})
        self.assertEqual(f["lag_hemma"], "A")
        self.assertIsNone(f["startelva"])
        self.assertEqual(f["gren"], "")

    def test_p5_event_harleder_next_when_ur_datum(self):
        # Heldagsevent: kanalens config saknar next_when → underraden ska ändå
        # få datumet (härlett ur eventets datum).
        mid = store.spara_match(self.c, {
            "lag_hemma": "Partille Cup", "lag_borta": "", "event": True,
            "datum": "2026-07-06", "arena": "Göteborg"})
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(f["next_when"], "6 jul")
        self.assertEqual(f["lag_borta"], "")
        # explicit config.next_when (Live-flödet) vinner
        f2 = S._matchfalt(self.c, {"match_id": mid, "next_when": "Lör 12 jul"})
        self.assertEqual(f2["next_when"], "Lör 12 jul")
        # en riktig match (ej event) härleder inte next_when
        mid2 = store.spara_match(self.c, {"lag_hemma": "A", "lag_borta": "B",
                                          "datum": "2026-08-01"})
        self.assertEqual(S._matchfalt(self.c, {"match_id": mid2})["next_when"], "")

    def test_rond_och_land_for_individsport(self):
        # D1 (tennis): rond round-trippas via matchen; land = utövarens
        # lag.klubb ("Klubb/land"). Config vinner (Live-flödets fritext-läge).
        mid = store.spara_match(self.c, {
            "lag_hemma": "Leo Borg", "lag_borta": "Casper Ruud",
            "sport": "tennis", "rond": "Semifinal"})
        m = store.hamta_match(self.c, mid)
        store.upsert_lag(self.c, "Leo Borg", sport="tennis", klubb="Sverige")
        store.upsert_lag(self.c, "Casper Ruud", sport="tennis", klubb="Norge")
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(m["rond"], "Semifinal")
        self.assertEqual(f["rond"], "Semifinal")
        self.assertEqual(f["land_hemma"], "Sverige")
        self.assertEqual(f["land_borta"], "Norge")
        f2 = S._matchfalt(self.c, {"match_id": mid, "rond": "Final"})
        self.assertEqual(f2["rond"], "Final")

    def test_loggor_ur_lagens_databaspost(self):
        # lag.logga (uppladdad under Lag & tävlingar) ska följa med matchfälten
        # — INTE story_overlay.hitta_logga()s gamla filsystemkonvention.
        mid = store.spara_match(self.c, {"lag_hemma": "Malmö FF", "lag_borta": "KDFF"})
        store.upsert_lag(self.c, "Malmö FF", logga="/loggor/mff.png")
        f = S._matchfalt(self.c, {"match_id": mid})
        self.assertEqual(f["hem_logga"], "/loggor/mff.png")
        self.assertIsNone(f["borta_logga"])              # KDFF fick ingen logga

    def test_loggor_none_utan_match(self):
        f = S._matchfalt(self.c, {"lag_hemma": "A", "lag_borta": "B"})
        self.assertIsNone(f["hem_logga"])
        self.assertIsNone(f["borta_logga"])

    def test_live_mallfalt_vinner_over_matchen(self):
        # Live-flödet skickar explicit ifyllda fält (halvtidsställning,
        # 'Nästa match'-motståndare …) — de ska slå matchens lagrade värden.
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "KDFF",
            "resultat": "6-0", "malskyttar": "Hansson 2",
            "spelare": [{"nr": "1", "namn": "Musovic", "lag": "hemma",
                         "start": True}]})
        f = S._matchfalt(self.c, {
            "match_id": mid, "stallning": "3-0", "mal_rad": "Berg 12'",
            "startelva": "Egen elva", "lag_borta": "IFK Norrköping"})
        self.assertEqual(f["stallning"], "3-0")
        self.assertEqual(f["mal_rad"], "Berg 12'")
        self.assertEqual(f["startelva"], "Egen elva")
        self.assertEqual(f["lag_borta"], "IFK Norrköping")
        self.assertEqual(f["lag_hemma"], "Malmö FF")     # matchen fyller resten

    def test_kor_story_validering(self):
        self.assertFalse(S.kor_story(self.c, {})["ok"])                  # inget moment
        self.assertFalse(S.kor_story(self.c, {"moment": "Avspark"})["ok"])  # inget foto
        self.assertFalse(S.kor_story(
            self.c, {"moment": "Avspark", "foto": "/finns/inte.jpg"})["ok"])

    def test_p5_event_utan_motstandare_renderar(self):
        # p.5: heldagsevent (ingen lag_borta) ska rendera en ren story utan
        # tom borta-bricka / tankstreck — och aldrig krascha.
        import tempfile
        from pathlib import Path
        from PIL import Image
        from dpt2.motorer import story_overlay
        with tempfile.TemporaryDirectory() as d:
            foto = f"{d}/f.jpg"
            Image.new("RGB", (900, 1600), (40, 80, 110)).save(foto, "JPEG")
            ut = story_overlay.skapa_story(
                foto, "nasta_match", "Partille Cup", "",
                liga="Heldagsevent", arena="Göteborg", next_when="6–11 jul",
                gren="mixed", tema="Hav", ut_path=f"{d}/ut.jpg")
            self.assertTrue(Path(ut).exists())


class TestForhandsgranska(unittest.TestCase):
    """VIKTIGT: forhandsgranska() skriver till en FAST sökväg
    (story_korning.FORHANDSVISNING_PATH) — samma fil som appens riktiga
    Publicera→Live-förhandsvisning använder. Om testerna kör mot den skarpa
    sökvägen klobbar de Stigs faktiska förhandsvisning varje testkörning
    (hände 2026-07-03: appens preview byttes tyst ut mot testdata). Patcha
    DÄRFÖR alltid modulattributet till en tempfil i setUp/tearDown — aldrig
    den riktiga."""
    def setUp(self):
        self.c = db.oppna(":memory:")
        import tempfile
        from pathlib import Path
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._verklig_path = S.FORHANDSVISNING_PATH
        S.FORHANDSVISNING_PATH = Path(self._tmpdir.name) / "forhandsvisning-test.jpg"
        self.addCleanup(setattr, S, "FORHANDSVISNING_PATH", self._verklig_path)

    def test_validering_speglar_kor_story(self):
        self.assertFalse(S.forhandsgranska(self.c, {})["ok"])
        self.assertFalse(S.forhandsgranska(self.c, {"moment": "Avspark"})["ok"])

    def test_renderar_till_fast_fil_ej_dropbox(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            foto = f"{d}/kalla.jpg"
            Image.new("RGB", (400, 300), (80, 120, 160)).save(foto, "JPEG")
            otillatet = Path(d) / "ska-aldrig-anvandas"
            r = S.forhandsgranska(self.c, {
                "moment": "Avspark", "foto": foto, "tema": "Sol",
                "ut_mapp": str(otillatet)})
            self.assertTrue(r["ok"])
            self.assertEqual(r["path"], str(S.FORHANDSVISNING_PATH))
            self.assertNotEqual(S.FORHANDSVISNING_PATH, self._verklig_path)  # aldrig skarpa filen
            self.assertTrue(S.FORHANDSVISNING_PATH.exists())
            self.assertFalse(otillatet.exists())          # ut_mapp ignoreras helt

    def test_lagets_uppladdade_logga_anvands_i_renderingen(self):
        # Reproducerar buggen: en logga sparad på laget (Lag & tävlingar) ska
        # synas i den riktiga renderingen, inte bara det vita monogram-badget.
        import tempfile
        from pathlib import Path
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            foto = f"{d}/kalla.jpg"
            Image.new("RGB", (400, 300), (80, 120, 160)).save(foto, "JPEG")
            logga = f"{d}/mff.png"
            Image.new("RGBA", (200, 200), (255, 0, 0, 255)).save(logga, "PNG")

            mid = store.spara_match(self.c, {"lag_hemma": "Malmö FF", "lag_borta": "KDFF",
                                             "resultat": "6-0"})
            store.upsert_lag(self.c, "Malmö FF", logga=logga)

            # Utan logga (monogram-badge) som referens.
            r_utan = S.forhandsgranska(self.c, {
                "moment": "Resultat", "foto": foto, "lag_hemma": "X", "lag_borta": "Y"})
            utan_bytes = Path(r_utan["path"]).read_bytes()

            # Med matchens riktiga lag (Malmö FF har en logga i databasen).
            r_med = S.forhandsgranska(self.c, {
                "moment": "Resultat", "foto": foto, "match_id": mid})
            self.assertTrue(r_med["ok"])
            med_bytes = Path(r_med["path"]).read_bytes()

            self.assertNotEqual(utan_bytes, med_bytes)   # loggan syns → annan pixeldata


if __name__ == "__main__":
    unittest.main()
