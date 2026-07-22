"""V5 §8 S2 — inläsning av tidsprogram och startlista."""

import unittest
from pathlib import Path

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



class TestPdfKolumnlayout(unittest.TestCase):
    """Skarp fil: SM 2026:s tidsprogram (Uppsala). Rutnät med tre dagar SIDA
    VID SIDA, var och en med tid | Män | Kvinnor, och varje glyf ritad två
    gånger. Läses texten utan koordinater flätas dagarna ihop."""

    PDF = str(Path(__file__).parent / "testdata" / "sm26-tidsprogram.pdf")

    @classmethod
    def setUpClass(cls):
        try:
            import pdfplumber       # noqa: F401
        except ImportError:
            raise unittest.SkipTest("pdfplumber saknas")
        cls.rader = PI.las_pdf(cls.PDF, ar=2026)

    def test_alla_tre_dagarna_lases(self):
        dagar = sorted({r["datum"] for r in self.rader})
        self.assertEqual(dagar, ["2026-07-24", "2026-07-25", "2026-07-26"])

    def test_hela_programmet_kommer_med(self):
        """108 schemaposter i filen. Sjunker siffran har layoutläsningen
        tappat en kolumn."""
        self.assertEqual(len(self.rader), 108)

    def test_klassen_kommer_ur_kolumnen(self):
        klasser = {r["klass"] for r in self.rader}
        self.assertEqual(klasser, {"dam", "herr"})

    def test_kolumnmitten_avgor_klassen_inte_vansterkanten(self):
        """De två 100 m-finalerna på fredagen ligger i var sin kolumn:
        damernas 20:25, herrarnas 20:35. Verifierat mot filens geometri."""
        finaler = {(r["tid"], r["klass"]) for r in self.rader
                   if r["datum"] == "2026-07-24" and r["gren"] == "100m"
                   and r["pass"] == "Final"}
        self.assertEqual(finaler, {("20:25", "dam"), ("20:35", "herr")})

    def test_ligaturer_overlever_avdubbleringen(self):
        """Varje glyf ritas två gånger; 'fi' är EN glyf. Klipper man varannan
        tecken blir 'final' till 'fnal' — därför positionell avdubblering."""
        self.assertIn("Final", {r["pass"] for r in self.rader})
        self.assertNotIn("Fnal", {r["pass"] for r in self.rader})

    def test_passnamn_delas_av_fran_grenen(self):
        rad = next(r for r in self.rader
                   if r["datum"] == "2026-07-24" and r["tid"] == "12:30")
        self.assertEqual((rad["gren"], rad["pass"], rad["klass"]),
                         ("Längd", "Kval", "herr"))

    def test_grenar_utan_fas_flaggas_i_stallet_for_att_gissas(self):
        """'Tiokamp 100m' har ingen kval/final-fas — parsern ska säga till,
        inte hitta på ett passnamn."""
        rad = next(r for r in self.rader if r["gren"] == "Tiokamp 100m")
        self.assertEqual(rad["pass"], "")
        self.assertIn("passnamn", rad["varning"])

    def test_samma_gren_bada_klasserna_pa_samma_tid(self):
        """15:05 fredag har I-20/R-stående 1500m i BÅDA kolumnerna."""
        rader = [r for r in self.rader
                 if r["datum"] == "2026-07-24" and r["tid"] == "15:05"]
        self.assertEqual(sorted(r["klass"] for r in rader), ["dam", "herr"])

    def test_saknad_fil_ger_tomt_inte_krasch(self):
        self.assertEqual(PI.las_pdf("/finns/inte.pdf", ar=2026), [])

class TestStartlistaMedTider(unittest.TestCase):
    """Skarp källa: arrangörens startlistesida (easyrecord.se, SM 2026).
    Den bär BÅDE passtiderna och deltagarna — en inklistring ger båda."""

    RA = (Path(__file__).parent / "testdata"
          / "sm26-startlista-utdrag.txt").read_text(encoding="utf-8")

    def setUp(self):
        self.r = PI.tolka_startlista_med_tider(
            self.RA, fran="2026-07-24", till="2026-07-26")

    def test_veckodag_blir_datum_ur_perioden(self):
        """Sidan skriver 'Fredag', inte ett datum."""
        p = self.r["pass"][0]
        self.assertEqual((p["gren"], p["pass"], p["datum"], p["tid"]),
                         ("100 m", "Försök", "2026-07-24", "18:20"))

    def test_klassen_kommer_ur_rubriken(self):
        klasser = {(p["gren"], p["klass"]) for p in self.r["pass"]}
        self.assertIn(("100 m", "dam"), klasser)
        self.assertIn(("Tiokamp", "herr"), klasser)

    def test_pass_over_flera_dagar(self):
        hojd = [p for p in self.r["pass"] if p["gren"] == "Höjd"]
        self.assertEqual([(p["pass"], p["datum"]) for p in hojd],
                         [("Kval", "2026-07-24"), ("Final", "2026-07-25")])

    def test_mangkampens_delgrenar_blir_pass(self):
        """Tiokamp har en passrad per delgren — de ÄR grenens pass."""
        tio = [p for p in self.r["pass"] if p["gren"] == "Tiokamp"]
        self.assertEqual([p["pass"] for p in tio],
                         ["100 m", "Längd", "Kula", "110 m häck", "1500 m"])
        self.assertEqual(tio[3]["datum"], "2026-07-25")   # lördag

    def test_deltagare_knyts_till_sin_gren(self):
        d = self.r["deltagare"]
        self.assertEqual((d[0]["namn"], d[0]["klubb"], d[0]["gren"], d[0]["klass"]),
                         ("Esther Sahlqvist", "Hammarby IF", "100 m", "dam"))
        self.assertEqual({x["gren"] for x in d}, {"100 m", "Höjd", "Tiokamp"})

    def test_fodelsear_ar_inte_klubben(self):
        """Kolumnordningen är nr, namn, år, klubb — inte nr, namn, klubb."""
        self.assertNotIn("06", {d["klubb"] for d in self.r["deltagare"]})

    def test_deltagare_utan_resultat_kommer_med(self):
        namn = {d["namn"] for d in self.r["deltagare"]}
        self.assertIn("Erik Wallnäs", namn)      # tomma SB/PB-kolumner
        self.assertIn("Evelina Olsson", namn)    # tom SB

    def test_deltagare_utan_startnummer_tappas_inte(self):
        """SM 2026: Oscar Holmin står utan startnummer i två grenar. Ett krav
        på siffror i första fältet hade tappat båda tyst (hittat mot sidan)."""
        self.assertIn("Oscar Holmin", {d["namn"] for d in self.r["deltagare"]})

    def test_antal_deltagare_raden_ar_inte_en_deltagare(self):
        self.assertNotIn("Antal deltagare: 3",
                         {d["namn"] for d in self.r["deltagare"]})

    def test_utan_period_flaggas_passen_i_stallet_for_att_slangas(self):
        r = PI.tolka_startlista_med_tider(self.RA)
        self.assertTrue(all(not p["datum"] for p in r["pass"]))
        self.assertIn("period", r["pass"][0]["varning"])
        self.assertEqual(len(r["deltagare"]), 8)   # deltagarna påverkas inte

    def test_tom_text(self):
        r = PI.tolka_startlista_med_tider("", fran="2026-07-24")
        self.assertEqual((r["pass"], r["deltagare"]), ([], []))

    # Mixad gren (easyrecord): två klasser springer samma lopp. Rubriken säger
    # "Mixad med …" + en kombinerad "A & B"-rad, och varje deltagarrad bär en
    # Klass-kolumn. Passet ska gälla båda grenarna och deltagarna delas på klass.
    MIXAD = (
        "Kvinnor R-stående 100 m\n"
        "Mixad med Kvinnor I-20 100 m\n"
        "\n"
        "Kvinnor I-20 & Kvinnor R-stående 100 m\n"
        "Final Fredag, 13:15\n"
        "#\nKlass\nSB\nPB\n"
        "45\tNyakuan Kang Gai\t05\tEskilstuna FI\tKvinnor I-20\t15.27\t14.932025\t\n"
        "57\tEllen Westling\t07\tFalu IK\tKvinnor R-stående\t17.39\t16.942025\t\n"
        "292\tFilippa Ivarsson\t07\tKFUM Kristianstad\tKvinnor I-20\t14.20\t14.202026\t\n"
        "Antal deltagare: 3\n"
    )

    def test_mixad_gren_delas_pa_klasskolumnen(self):
        r = PI.tolka_startlista_med_tider(self.MIXAD, fran="2026-07-24", till="2026-07-26")
        # Passet (Final) gäller BÅDA grenarna — ej en hopklumpad "A & B"-gren.
        self.assertEqual({p["gren"] for p in r["pass"]},
                         {"R-stående 100 m", "I-20 100 m"})
        self.assertTrue(all(p["pass"] == "Final" for p in r["pass"]))
        # Deltagarna delas på sin Klass-kolumn, inte alla i en gren.
        per = {d["namn"]: d["gren"] for d in r["deltagare"]}
        self.assertEqual(per["Nyakuan Kang Gai"], "I-20 100 m")
        self.assertEqual(per["Ellen Westling"], "R-stående 100 m")
        self.assertEqual(per["Filippa Ivarsson"], "I-20 100 m")

    def test_sb_pb_fangas_med_arstrippat_pb(self):
        # #8: SB/PB ur kolumnerna. PB bär årtal i svansen ("14.932025") som ska
        # bort så bara värdet ("14.93") lagras. Tom SB ska bli tom, inte krascha.
        r = PI.tolka_startlista_med_tider(self.MIXAD, fran="2026-07-24", till="2026-07-26")
        per = {d["namn"]: (d.get("sb"), d.get("pb")) for d in r["deltagare"]}
        self.assertEqual(per["Nyakuan Kang Gai"], ("15.27", "14.93"))
        self.assertEqual(per["Ellen Westling"], ("17.39", "16.94"))


class TestKannaIgen(unittest.TestCase):
    """C8 — gissa dokumenttyp så Stig slipper välja flik."""

    def test_tidsprogram_pa_klockslag(self):
        sort, sak, _ = PI.kanna_igen(
            "09:00  100 m dam, Försök\n19:10  100 m dam Final")
        self.assertEqual((sort, sak), ("tidsprogram", "saker"))

    def test_startlista_med_tider_pa_passrad_med_veckodag(self):
        text = ("Kvinnor 100 m\nFörsök Fredag, 18:20\nFinal Fredag, 20:25\n"
                "80\tEsther Sahlqvist\t06\tHammarby IF")
        sort, sak, _ = PI.kanna_igen(text)
        self.assertEqual((sort, sak), ("startlista_tider", "saker"))

    def test_bara_deltagare_utan_tider(self):
        sort, sak, _ = PI.kanna_igen(
            "100 m dam\n1\tAnna Andersson\tIF Göta\t@anna_a")
        self.assertEqual((sort, sak), ("startlista", "saker"))

    def test_csv_program_pa_rubrikkolumner(self):
        sort, _, _ = PI.kanna_igen(
            "datum,tid,gren,pass\n2026-07-24,09:00,100 m,Försök")
        self.assertEqual(sort, "csv_program")

    def test_csv_startlista_pa_deltagarkolumner(self):
        sort, _, _ = PI.kanna_igen("namn,klubb,handle\nAnna,IF Göta,@anna")
        self.assertEqual(sort, "csv_startlista")

    def test_tom_text_ar_osaker(self):
        self.assertEqual(PI.kanna_igen("")[1], "osaker")


class TestAvvikelser(unittest.TestCase):
    """C9 — märk bara det som behöver ögon."""

    def test_dubblett_pa_stavning(self):
        rader = [{"datum": "2026-07-24", "tid": "09:00", "gren": "100 m", "pass": "Försök"},
                 {"datum": "2026-07-25", "tid": "19:10", "gren": "100m", "pass": "Final"}]
        PI.analysera("tidsprogram", rader)
        self.assertTrue(all(r["avvik"] == "dubblett" for r in rader))

    def test_okand_klass_nar_grenen_finns_med_klass(self):
        rader = [{"gren": "100 m", "namn": "Anna", "klass": "dam"},
                 {"gren": "100 m", "namn": "Bea", "klass": ""}]
        PI.analysera("startlista", rader)
        self.assertEqual(rader[1]["avvik"], "okand_klass")

    def test_tidskrock_pa_samma_datum_och_tid(self):
        rader = [{"datum": "2026-07-24", "tid": "09:00", "gren": "100 m", "pass": "Försök"},
                 {"datum": "2026-07-24", "tid": "09:00", "gren": "200 m", "pass": "Försök"}]
        PI.analysera("tidsprogram", rader)
        self.assertTrue(all(r["avvik"] == "tidskrock" for r in rader))

    def test_parserns_varning_blir_flaggad(self):
        rader = [{"datum": "2026-07-24", "tid": "09:00", "gren": "Höjd",
                  "pass": "", "varning": "Hittade inget passnamn"}]
        PI.analysera("tidsprogram", rader)
        self.assertEqual(rader[0]["avvik"], "flaggad")

    def test_ren_rad_far_ingen_etikett(self):
        rader = [{"datum": "2026-07-24", "tid": "09:00", "gren": "Höjd", "pass": "Final"}]
        PI.analysera("tidsprogram", rader)
        self.assertEqual(rader[0]["avvik"], "")

    def test_sammanfattning_raknar_dagar_grenar_pass(self):
        rader = [{"datum": "2026-07-24", "tid": "09:00", "gren": "100 m", "pass": "Försök"},
                 {"datum": "2026-07-25", "tid": "19:10", "gren": "100 m", "pass": "Final"}]
        s = PI.analysera("tidsprogram", rader)["sammanfattning"]
        self.assertEqual((s["dagar"], s["grenar"], s["pass"]), (2, 1, 2))
        self.assertEqual(s["rena"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMixadSeparerad(unittest.TestCase):
    """Full SM-lista: "Mixad med"-stubbarna ligger separerade från den
    kombinerade "A & B"-rubriken, och kön kan blandas. Regressionsvakt."""

    TXT = (
        "Kvinnor R-stående 100 m\n"
        "Mixad med Kvinnor I-20 100 m\n"
        "\n"
        "Kvinnor R-stående Längd\n"
        "Final Söndag, 12:40\n"
        "#\nSB\nPB\n"
        "57\tEllen Westling\t07\tFalu IK\t3.38\t3.402025\t\n"
        "Antal deltagare: 1\n"
        "\n"
        "Kvinnor I-20 & Kvinnor R-stående 100 m\n"
        "Final Fredag, 13:15\n"
        "#\nKlass\nSB\nPB\n"
        "45\tNyakuan Kang Gai\t05\tEskilstuna FI\tKvinnor I-20\t15.27\t14.932025\t\n"
        "57\tEllen Westling\t07\tFalu IK\tKvinnor R-stående\t17.39\t16.942025\t\n"
        "Antal deltagare: 2\n"
        "\n"
        "Män I-20 & Kvinnor R-stående & Kvinnor I-20 & Män R-stående 1500 m\n"
        "Final Fredag, 15:05\n"
        "#\nKlass\nSB\nPB\n"
        "278\tKarin Petersson\t64\tIK Ymer\tKvinnor R-stående\t\t6:59.732025\t\n"
        "465\tAdam Hellgren\t93\tTjalve FIF\tMän I-20\t4:22.51\t4:17.132025\t\n"
        "Antal deltagare: 2\n"
    )

    def test_kombinerad_rubrik_delas_aven_langt_fran_stubben(self):
        r = PI.tolka_startlista_med_tider(self.TXT, fran="2026-07-24", till="2026-07-26")
        per = {d["namn"]: (d["gren"], d["klass"]) for d in r["deltagare"]}
        # 100 m-loppet delas rätt trots att stubben låg tre grenar bort.
        self.assertEqual(per["Nyakuan Kang Gai"], ("I-20 100 m", "dam"))
        self.assertEqual(per["Ellen Westling"], ("R-stående 100 m", "dam"))
        # Blandat kön: klassen kommer ur radens kön, inte rubrikens första.
        self.assertEqual(per["Karin Petersson"], ("R-stående 1500 m", "dam"))
        self.assertEqual(per["Adam Hellgren"], ("I-20 1500 m", "herr"))
