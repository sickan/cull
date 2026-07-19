"""V5 §8 S2 — inläsning av tidsprogram och startlista."""

import unittest

from dpt2.motorer import program_import as PI


class TestDatum(unittest.TestCase):
    def test_iso_behover_inget_ar(self):
        self.assertEqual(PI.tolka_datum("2026-07-24"), "2026-07-24")

    def test_veckodag_och_manad(self):
        self.assertEqual(PI.tolka_datum("Fredag 24 juli", ar=2026),
                         "2026-07-24")

    def test_snedstreck(self):
        self.assertEqual(PI.tolka_datum("Lördag 25/7", ar=2026), "2026-07-25")

    def test_utan_ar_gissar_vi_inte(self):
        self.assertIsNone(PI.tolka_datum("Fredag 24 juli"))

    def test_icke_datum(self):
        self.assertIsNone(PI.tolka_datum("100 m dam"))


class TestTidsprogram(unittest.TestCase):
    def test_dagrubriker_delar_upp_programmet(self):
        rader = PI.tolka_tidsprogram("""
            Fredag 24 juli
            09:00  100 m dam, Försök
            14:00  100 m dam, Semi
            Lördag 25 juli
            19:10  100 m dam, Final
        """, ar=2026)
        self.assertEqual([(r["datum"], r["tid"], r["pass"]) for r in rader], [
            ("2026-07-24", "09:00", "Försök"),
            ("2026-07-24", "14:00", "Semi"),
            ("2026-07-25", "19:10", "Final"),
        ])

    def test_passnamn_far_versal_oavsett_vag(self):
        """'kval' ur en kommarad och 'Final' ur passordsdelningen ska inte bli
        två sorters passnamn i programmet."""
        rader = PI.tolka_tidsprogram(
            "2026-07-24\n09:00 Kula damer, kval\n19:10 Kula damer Final",
            ar=2026)
        self.assertEqual([r["pass"] for r in rader], ["Kval", "Final"])

    def test_plats_som_tredje_kolumn(self):
        rad = PI.tolka_tidsprogram(
            "2026-07-24\n09:00  Höjd, Kval, A-planen", ar=2026)[0]
        self.assertEqual((rad["gren"], rad["pass"], rad["plats"]),
                         ("Höjd", "Kval", "A-planen"))

    def test_tabbseparerat_ur_kalkylark(self):
        rad = PI.tolka_tidsprogram(
            "2026-07-24\n09:00\t100 m dam\tFörsök", ar=2026)[0]
        self.assertEqual((rad["gren"], rad["pass"]), ("100 m dam", "Försök"))

    def test_tankstreck_som_avgransare(self):
        rad = PI.tolka_tidsprogram(
            "2026-07-24\n14:00 100 m dam - Semi", ar=2026)[0]
        self.assertEqual((rad["gren"], rad["pass"]), ("100 m dam", "Semi"))

    def test_passord_utan_avgransare(self):
        """PDF-rader saknar ofta skiljetecken helt."""
        rad = PI.tolka_tidsprogram(
            "2026-07-24\n19:10 100 m dam Final", ar=2026)[0]
        self.assertEqual((rad["gren"], rad["pass"]), ("100 m dam", "Final"))

    def test_okant_passnamn_flaggas_i_stallet_for_att_gissas(self):
        rad = PI.tolka_tidsprogram(
            "2026-07-24\n11:00 Stavhopp damer", ar=2026)[0]
        self.assertEqual(rad["gren"], "Stavhopp damer")
        self.assertEqual(rad["pass"], "")
        self.assertIn("passnamn", rad["varning"])

    def test_punkt_som_tidsavgransare(self):
        rad = PI.tolka_tidsprogram("2026-07-24\n09.30 Kula, Final", ar=2026)[0]
        self.assertEqual(rad["tid"], "09:30")

    def test_ensiffrig_timme_nollutfylls(self):
        rad = PI.tolka_tidsprogram("2026-07-24\n9:05 Kula, Final", ar=2026)[0]
        self.assertEqual(rad["tid"], "09:05")

    def test_rader_utan_klockslag_hoppas_over(self):
        rader = PI.tolka_tidsprogram(
            "2026-07-24\nOBS! Tider kan ändras\n09:00 Kula, Final", ar=2026)
        self.assertEqual(len(rader), 1)

    def test_utan_dagrubrik_flaggas_men_slangs_inte(self):
        rader = PI.tolka_tidsprogram("09:00 Kula, Final",
                                     standarddatum="2026-07-24")
        self.assertEqual(rader[0]["datum"], "2026-07-24")
        self.assertIn("dagrubrik", rader[0]["varning"])

    def test_tom_text(self):
        self.assertEqual(PI.tolka_tidsprogram(""), [])
        self.assertEqual(PI.tolka_tidsprogram(None), [])


class TestStartlista(unittest.TestCase):
    def test_grenrubrik_styr_efterfoljande_rader(self):
        rader = PI.tolka_startlista("""
            100 m dam
            1  Anna Andersson  IF Göta
            2  Beata Berg  Malmö AI
        """, kanda_grenar=["100 m dam"])
        self.assertEqual([(r["gren"], r["namn"], r["klubb"]) for r in rader], [
            ("100 m dam", "Anna Andersson", "IF Göta"),
            ("100 m dam", "Beata Berg", "Malmö AI"),
        ])

    def test_startnummer_ar_inte_namnet(self):
        rad = PI.tolka_startlista("101  Anna Andersson  IF Göta")[0]
        self.assertEqual(rad["namn"], "Anna Andersson")

    def test_handle_plockas_var_den_an_star(self):
        rad = PI.tolka_startlista("1, Anna Andersson, @anna_a, IF Göta")[0]
        self.assertEqual((rad["namn"], rad["klubb"], rad["handle"]),
                         ("Anna Andersson", "IF Göta", "@anna_a"))

    def test_deltagare_utan_gren_flaggas(self):
        rad = PI.tolka_startlista("Anna Andersson, IF Göta")[0]
        self.assertIn("gren", rad["varning"])

    def test_okand_grenrubrik_anvands_anda_nar_inga_grenar_ar_kanda(self):
        rader = PI.tolka_startlista("Stavhopp\nAnna Andersson, IF Göta")
        self.assertEqual(rader[0]["gren"], "Stavhopp")


class TestCSV(unittest.TestCase):
    def test_rubrikrad_ger_dictar(self):
        rader = PI.las_csv("datum,tid,gren,pass\n"
                           "2026-07-24,09:00,100 m dam,Försök")
        self.assertEqual(rader, [{"datum": "2026-07-24", "tid": "09:00",
                                  "gren": "100 m dam", "pass": "Försök"}])

    def test_semikolon_och_versaler_i_rubriken(self):
        rader = PI.las_csv("Gren;Namn;Klubb\n100 m dam;Anna;IF Göta")
        self.assertEqual(rader[0]["namn"], "Anna")

    def test_utan_kand_rubrik_ger_tomt(self):
        self.assertEqual(PI.las_csv("a,b,c\n1,2,3"), [])

    def test_tom_text(self):
        self.assertEqual(PI.las_csv(""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
