"""Tester för datalager-CRUD (store) — körs mot in-memory SQLite (stdlib)."""

import unittest

from dpt2.data import db, store
from dpt2.motorer.gallring import Gallring


class TestUrval(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_spara_och_hamta(self):
        uid = store.spara_urval(self.c, kalla="/Volumes/NIKON/DCIM", bilder=40,
                                kamera="NIKON Z 8")
        u = store.hamta_urval(self.c, uid)
        self.assertEqual(u["bilder"], 40)
        self.assertEqual(u["kamera"], "NIKON Z 8")
        self.assertEqual(u["status"], "gallrad")      # default

    def test_per_bild_urval_round_trip(self):
        uid = store.spara_urval(self.c, kalla="x", bilder=0)
        store.ersatt_urval_bilder(self.c, uid, [
            ("s1", 1, 0.91), ("s2", 0, 0.30), ("s3", 1, 0.77)])
        self.assertEqual(sorted(store.behall_stems(self.c, uid)), ["s1", "s3"])
        self.assertEqual(store.hamta_urval(self.c, uid)["bilder"], 2)  # behåll-antal
        # idempotent: omkörning ersätter
        store.ersatt_urval_bilder(self.c, uid, [("s1", 1, 0.91)])
        self.assertEqual(store.behall_stems(self.c, uid), ["s1"])

    def test_status_livscykel(self):
        uid = store.spara_urval(self.c, kalla="x", bilder=10)
        store.satt_urval_status(self.c, uid, "levererad")
        self.assertEqual(store.hamta_urval(self.c, uid)["status"], "levererad")
        store.satt_urval_status(self.c, uid, "publicerad")
        self.assertEqual(store.hamta_urval(self.c, uid)["status"], "publicerad")
        with self.assertRaises(ValueError):
            store.satt_urval_status(self.c, uid, "trams")

    def test_koppling_till_match(self):
        # match kräver en rad i matchen (FK). Lägg en minimal match.
        self.c.execute("INSERT INTO matchen(id,skapad) VALUES('m1','2026-06-29')")
        uid = store.spara_urval(self.c, match_id="m1", kalla="x", bilder=5)
        self.assertEqual(store.urval_for_match(self.c, "m1")[0]["id"], uid)

    def test_ogiltig_status_avvisas_av_check(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            store.spara_urval(self.c, kalla="x", bilder=1, status="fel")


class TestCullJobb(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.uid = store.spara_urval(self.c, kalla="x", bilder=40)

    def test_fran_gallring_topp(self):
        cfg = Gallring(topp=40, burst_sek=2.0, bevaka={"10"})
        jid = store.cull_jobb_fran_gallring(self.c, self.uid, cfg, verktyg="ai")
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(j["id"], jid)
        self.assertEqual(j["behall_varde"], 40.0)
        self.assertEqual(j["behall_enhet"], "bilder")
        self.assertEqual(j["trojnummer_ocr"], 1)       # bevaka satt
        self.assertEqual(j["burst_grans"], 2.0)

    def test_fran_gallring_andel(self):
        cfg = Gallring(topp=None, andel=0.25)
        store.cull_jobb_fran_gallring(self.c, self.uid, cfg)
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(j["behall_varde"], 25.0)
        self.assertEqual(j["behall_enhet"], "procent")

    def test_vikter_json(self):
        jid = store.spara_cull_jobb(self.c, urval_id=self.uid, verktyg="ai",
                                    vikter={"pose": 60, "skarpa": 70})
        import json
        j = store.jobb_for_urval(self.c, self.uid)[0]
        self.assertEqual(json.loads(j["vikter"])["skarpa"], 70)

    def test_cull_jobb_kraver_giltig_urval_fk(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            store.spara_cull_jobb(self.c, urval_id="finns-ej", verktyg="ai")


class TestMatchCRUD(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.match = {
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "datum": "2026-06-27", "tid": "14:00", "arena": "Eleda Stadion",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "resultat": "6-0",
            "spelare": [
                {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma",
                 "handle": "@zm", "info": "MV", "start": True},
                {"nr": "9", "namn": "Mia", "lag": "hemma", "start": False},
                {"nr": "7", "namn": "Borta-spelare", "lag": "borta"},
            ],
        }

    def test_round_trip(self):
        mid = store.spara_match(self.c, self.match)
        m = store.hamta_match(self.c, mid)
        self.assertEqual(m["lag_hemma"], "Malmö FF")
        self.assertEqual(m["liga"], "OBOS Damallsvenskan")
        self.assertEqual(m["status"], "avslutad")            # resultat satt
        self.assertEqual(len(m["spelare"]), 3)
        zm = next(p for p in m["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["lag"], "hemma")                 # sida härledd ur lag_id
        self.assertEqual(zm["handle"], "@zm")
        self.assertTrue(zm["start"])
        borta = next(p for p in m["spelare"] if p["nr"] == "7")
        self.assertEqual(borta["lag"], "borta")

    def test_efter_match_lankar_round_trip(self):
        m = dict(self.match)
        m["galleri"] = "https://malmoff.pixieset.com/damallsvenskan-27jun/"
        m["sida_url"] = "https://dalecarliaphoto.se/sport/2026-06-27-malmo-ff-kristianstad"
        mid = store.spara_match(self.c, m)
        sparad = store.hamta_match(self.c, mid)
        self.assertEqual(sparad["galleri"], m["galleri"])
        self.assertEqual(sparad["sida_url"], m["sida_url"])

    def test_delad_slug_id(self):
        store.spara_match(self.c, self.match)
        self.assertIsNotNone(store.hamta_lag(self.c, "malmo-ff"))   # samma som migrera
        self.assertIsNotNone(store.hamta_lag(self.c, "kristianstads-dff"))

    def test_status_harleds(self):
        m = dict(self.match); m["resultat"] = ""; m["datum"] = "2027-01-01"
        mid = store.spara_match(self.c, m)
        self.assertEqual(store.hamta_match(self.c, mid)["status"], "kommande")

    def test_redigera_tar_bort_spelare(self):
        mid = store.spara_match(self.c, self.match)
        m = store.hamta_match(self.c, mid)
        m["spelare"] = [p for p in m["spelare"] if p["nr"] != "9"]   # ta bort Mia
        store.spara_match(self.c, m)
        kvar = store.hamta_match(self.c, mid)["spelare"]
        self.assertEqual(len(kvar), 2)
        self.assertNotIn("9", {p["nr"] for p in kvar})

    def test_lista_matcher(self):
        store.spara_match(self.c, self.match)
        rad = store.lista_matcher(self.c)[0]
        self.assertEqual(rad["lag_hemma"], "Malmö FF")
        self.assertEqual(rad["liga"], "OBOS Damallsvenskan")

    def test_hem_gren_harleds_ur_hemmalaget(self):
        # Gren-markören: matchens gren = hemmalagets; utan gren = "ej satt".
        mid = store.spara_match(self.c, self.match)
        self.assertFalse(store.lista_matcher(self.c)[0]["hem_gren"])
        store.upsert_lag(self.c, "Malmö FF", gren="dam")
        self.assertEqual(store.lista_matcher(self.c)[0]["hem_gren"], "dam")
        self.assertEqual(store.hamta_match(self.c, mid)["hem_gren"], "dam")

    def test_radera(self):
        mid = store.spara_match(self.c, self.match)
        store.radera_match(self.c, mid)
        self.assertIsNone(store.hamta_match(self.c, mid))

    def test_merge_in_trupp(self):
        mid = store.spara_match(self.c, self.match)        # 3 spelare
        # "hämtad" trupp: uppdaterar #1 (saknar handle→bevaras) + ny spelare #14
        nya = [
            {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma"},
            {"nr": "14", "namn": "Ny Spelare", "lag": "hemma", "handle": "@ny"},
        ]
        uppd = store.merge_in_trupp(self.c, mid, nya)
        nrs = {p["nr"] for p in uppd["spelare"]}
        self.assertIn("14", nrs)                            # ny tillagd
        zm = next(p for p in uppd["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["handle"], "@zm")              # bevarat över merge
        self.assertIn("9", nrs)                            # gammal kvar

    def test_merge_okand_match(self):
        self.assertIsNone(store.merge_in_trupp(self.c, "finns-ej", []))


class TestLagTavling(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_upsert_lag_uppdaterar_utan_att_nolla(self):
        lid = store.upsert_lag(self.c, "Malmö FF", instagram="@malmoff")
        store.upsert_lag(self.c, "Malmö FF", logga="/x.png")   # bara logga
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["instagram"], "@malmoff")          # bevarat
        self.assertEqual(lag["logga"], "/x.png")                # tillagt

    def test_upsert_tavling(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        self.assertEqual(tid, "obos-damallsvenskan")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)

    def test_upsert_tavling_uppdaterar(self):
        store.upsert_tavling(self.c, "EM Volley", sport="fotboll", typ="liga")
        store.upsert_tavling(self.c, "EM Volley", sport="volleyboll", typ="masterskap")
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["sport"], "volleyboll")     # uppdaterat
        self.assertEqual(t["typ"], "masterskap")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)   # ingen dubblett

    def test_radera_lag_och_tavling(self):
        store.upsert_lag(self.c, "HK Malmö")
        store.upsert_tavling(self.c, "Handbollsligan", sport="handboll")
        store.radera_lag(self.c, "hk-malmo")
        store.radera_tavling(self.c, "handbollsligan")
        self.assertEqual(store.lista_lag(self.c), [])
        self.assertEqual(store.lista_tavlingar(self.c), [])

    def test_upsert_tavling_hemsida(self):
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                             hemsida="damallsvenskan.se")
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")  # rör ej
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["hemsida"], "damallsvenskan.se")   # bevarat

    def test_hamta_tavling(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                                   fran="2026-04-01", till="2026-10-31")
        t = store.hamta_tavling(self.c, tid)
        self.assertEqual(t["namn"], "OBOS Damallsvenskan")
        self.assertEqual(t["fran"], "2026-04-01")
        self.assertIsNone(store.hamta_tavling(self.c, "finns-ej"))

    def test_lag_individ(self):
        lid = store.upsert_lag(self.c, "Rebecca Peterson", kind="individ",
                               profilfarg="#2F7CB0", klubb="Sverige")
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["kind"], "individ")
        self.assertEqual(lag["profilfarg"], "#2F7CB0")
        self.assertEqual(lag["klubb"], "Sverige")
        # default kind = team
        tid = store.upsert_lag(self.c, "Malmö FF")
        self.assertEqual(store.hamta_lag(self.c, tid)["kind"], "team")

    def test_lag_sport_och_gren(self):
        lid = store.upsert_lag(self.c, "Malmö FF", sport="Fotboll", gren="Dam")
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["sport"], "fotboll")   # normaliserat till gemener
        self.assertEqual(lag["gren"], "dam")
        # okänt värde ignoreras, befintligt bevaras
        store.upsert_lag(self.c, "Malmö FF", sport="quidditch", gren="öppen")
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["sport"], "fotboll")
        self.assertEqual(lag["gren"], "dam")

    def test_gren_mixed_bara_for_team(self):
        lid = store.upsert_lag(self.c, "Beachduon", kind="team", gren="mixed")
        self.assertEqual(store.hamta_lag(self.c, lid)["gren"], "mixed")
        iid = store.upsert_lag(self.c, "Rebecca Peterson", kind="individ",
                               gren="mixed")
        self.assertIsNone(store.hamta_lag(self.c, iid)["gren"])

    def test_upsert_lag_med_id_byter_namn_pa_ratt_rad(self):
        # Stigs bugg: "Malmö FF Herr" → "Malmö FF" via editorn träffade
        # dam-lagets slug i stället för att byta namn på herr-raden.
        dam = store.upsert_lag(self.c, "Malmö FF", gren="dam",
                               instagram="@malmoff_dam")
        herr = store.upsert_lag(self.c, "Malmö FF Herr", gren="herr")
        lid = store.upsert_lag(self.c, "Malmö FF", id=herr, gren="herr")
        self.assertEqual(lid, herr)                             # samma rad
        self.assertEqual(store.hamta_lag(self.c, herr)["namn"], "Malmö FF")
        self.assertEqual(store.hamta_lag(self.c, herr)["gren"], "herr")
        # dam-raden orörd
        d = store.hamta_lag(self.c, dam)
        self.assertEqual(d["gren"], "dam")
        self.assertEqual(d["instagram"], "@malmoff_dam")
        self.assertEqual(len(store.lista_lag(self.c)), 2)       # ingen dubblett

    def test_upsert_lag_okant_id_faller_tillbaka_till_slug(self):
        lid = store.upsert_lag(self.c, "Malmö FF", id="finns-ej")
        self.assertEqual(lid, "malmo-ff")

    def test_spara_match_foredrar_lag_id_fore_namn(self):
        # Två lag med samma namn — comboboxens ref (id) måste vinna.
        dam = store.upsert_lag(self.c, "Malmö FF", gren="dam")
        herr = store.upsert_lag(self.c, "Malmö FF Herr", gren="herr")
        store.upsert_lag(self.c, "Malmö FF", id=herr, gren="herr")  # namnbyte
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_hemma_id": herr,
            "lag_borta": "AIK", "datum": "2026-08-01",
            "liga": "Allsvenskan", "sport": "fotboll"})
        m = store.hamta_match(self.c, mid)
        self.assertEqual(m["lag_hemma_id"], herr)               # inte dam
        # utan id: namn-slugen som förr
        mid2 = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "AIK",
            "datum": "2026-08-02", "liga": "X", "sport": "fotboll"})
        self.assertEqual(store.hamta_match(self.c, mid2)["lag_hemma_id"], dam)

    def test_landslag_per_sport_far_egna_poster(self):
        # Sverige Volleyboll ≠ Sverige Handboll — samma namn, olika sport.
        v = store.upsert_lag(self.c, "Sverige", sport="volleyboll")
        h = store.upsert_lag(self.c, "Sverige", sport="handboll")
        self.assertNotEqual(v, h)
        self.assertEqual(store.hamta_lag(self.c, v)["sport"], "volleyboll")
        self.assertEqual(store.hamta_lag(self.c, h)["sport"], "handboll")
        # upprepad upsert med samma sport träffar samma post (ingen tredje)
        self.assertEqual(store.upsert_lag(self.c, "Sverige", sport="handboll"), h)
        self.assertEqual(
            len([l for l in store.lista_lag(self.c) if l["namn"] == "Sverige"]), 2)
        # utan sport-krock ändras inte beteendet: sportlöst namn träffar basposten
        self.assertEqual(store.upsert_lag(self.c, "Sverige"), v)

    def test_tavling_gren(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan",
                                   sport="fotboll", gren="Dam")
        self.assertEqual(store.hamta_tavling(self.c, tid)["gren"], "dam")
        # utan gren i anropet bevaras den
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        self.assertEqual(store.hamta_tavling(self.c, tid)["gren"], "dam")

    def test_tavling_ager_sina_lag(self):
        # spara_match ska koppla hemma+borta till tävlingen (tavling_lag).
        store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "FC Rosengård",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll"})
        lag = store.lista_lag_for_tavling(self.c, "obos-damallsvenskan")
        namn = sorted(l["namn"] for l in lag)
        self.assertEqual(namn, ["FC Rosengård", "Malmö FF"])

    def test_merge_lag_trupp(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        n = store.merge_lag_trupp(self.c, lid, [
            {"nr": "1", "namn": "Zecira Musovic", "position": "Målvakt"},
            {"nr": "9", "namn": "Anna Anvegård"},
            {"namn": ""},                                   # tom → hoppas
        ], kalla="från hemsida")
        self.assertEqual(n, 2)
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["trupp_kalla"], "från hemsida")
        trupp = store.lag_trupp(self.c, lid)
        self.assertEqual(trupp[0]["position"], "Målvakt")
        # lista_lag exponerar trupp_n
        rad = next(l for l in store.lista_lag(self.c) if l["id"] == lid)
        self.assertEqual(rad["trupp_n"], 2)

    def test_merge_lag_trupp_upsert_bevarar_falt(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        store.merge_lag_trupp(self.c, lid, [
            {"nr": "1", "namn": "Zecira Musovic", "position": "Målvakt"}])
        # Ny inläsning utan position → befintlig position bevaras, ingen dubblett.
        n = store.merge_lag_trupp(self.c, lid, [
            {"nr": "1", "namn": "Zecira Musovic"}], kalla="CSV")
        self.assertEqual(n, 1)
        trupp = store.lag_trupp(self.c, lid)
        self.assertEqual(trupp[0]["position"], "Målvakt")
        self.assertEqual(store.hamta_lag(self.c, lid)["trupp_kalla"], "CSV")

    def test_merge_lag_trupp_overlever_match_lankar(self):
        # Spelare inlagd via match — trupp-merge på laget får inte bryta
        # match_trupp-länken (samma id-regel → upsert, inte delete+insert).
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "X",
            "spelare": [{"nr": "1", "namn": "Zecira Musovic", "lag": "hemma",
                         "start": True}]})
        store.merge_lag_trupp(self.c, "malmo-ff", [
            {"nr": "1", "namn": "Zecira Musovic", "position": "Målvakt"}])
        m = store.hamta_match(self.c, mid)
        self.assertEqual(len(m["spelare"]), 1)
        self.assertTrue(m["spelare"][0]["start"])

    def test_merge_lag_trupp_okant_lag(self):
        self.assertIsNone(store.merge_lag_trupp(self.c, "finns-ej", []))

    def test_spara_spelare_skapar_och_uppdaterar(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        sid = store.spara_spelare(self.c, lid, {"nr": "1", "namn": "Ida Ohlsson",
                                                "position": "MV"})
        self.assertIsNotNone(sid)
        trupp = store.lag_trupp(self.c, lid)
        self.assertEqual(len(trupp), 1)
        self.assertEqual(trupp[0]["namn"], "Ida Ohlsson")
        # Uppdatering (id angivet) — samma rad, inte en ny.
        store.spara_spelare(self.c, lid, {"id": sid, "nr": "7", "namn": "Ida Ohlsson",
                                          "position": "MV"})
        trupp = store.lag_trupp(self.c, lid)
        self.assertEqual(len(trupp), 1)
        self.assertEqual(trupp[0]["nr"], "7")

    def test_spara_spelare_redigering_rör_inte_matchlank(self):
        # En spelare tillagd manuellt (id-baserad) och sedan omdöpt ska INTE
        # tappa sin match_trupp-länk (till skillnad från merge_lag_trupp:s
        # nr/namn-slug-id, som skulle byta id vid namnändring).
        mid = store.spara_match(self.c, {
            "lag_hemma": "Malmö FF", "lag_borta": "X",
            "spelare": [{"nr": "1", "namn": "Ida Ohlsson", "lag": "hemma", "start": True}]})
        sid = store.spelare_id("malmo-ff", {"nr": "1", "namn": "Ida Ohlsson"})
        store.spara_spelare(self.c, "malmo-ff", {"id": sid, "nr": "1",
                                                  "namn": "Ida Andersson", "position": "MV"})
        m = store.hamta_match(self.c, mid)
        self.assertEqual(len(m["spelare"]), 1)
        self.assertTrue(m["spelare"][0]["start"])

    def test_spara_spelare_tom_namn_sparas_ej(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        self.assertIsNone(store.spara_spelare(self.c, lid, {"nr": "1", "namn": ""}))
        self.assertEqual(store.lag_trupp(self.c, lid), [])

    def test_spara_spelare_okant_lag(self):
        self.assertIsNone(store.spara_spelare(self.c, "finns-ej", {"namn": "X"}))

    def test_radera_spelare(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        sid = store.spara_spelare(self.c, lid, {"nr": "1", "namn": "Ida Ohlsson"})
        store.radera_spelare(self.c, sid)
        self.assertEqual(store.lag_trupp(self.c, lid), [])

    def test_tavlingar_for_lag_och_koppla_bort(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        t1 = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        t2 = store.upsert_tavling(self.c, "Svenska Cupen", sport="fotboll",
                                  typ="turnering")
        store.koppla_lag_till_tavling(self.c, t1, lid)
        store.koppla_lag_till_tavling(self.c, t2, lid)
        namn = [t["namn"] for t in store.tavlingar_for_lag(self.c, lid)]
        self.assertEqual(namn, ["OBOS Damallsvenskan", "Svenska Cupen"])
        store.koppla_bort_lag_fran_tavling(self.c, t1, lid)
        namn = [t["namn"] for t in store.tavlingar_for_lag(self.c, lid)]
        self.assertEqual(namn, ["Svenska Cupen"])
        # idempotent bortkoppling
        store.koppla_bort_lag_fran_tavling(self.c, t1, lid)
        self.assertEqual(len(store.tavlingar_for_lag(self.c, lid)), 1)

    def test_lista_lag_har_comps(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        store.koppla_lag_till_tavling(self.c, tid, lid)
        l = next(x for x in store.lista_lag(self.c) if x["id"] == lid)
        self.assertEqual(l["comps"], [tid])

    def test_koppla_lag_idempotent(self):
        store.upsert_lag(self.c, "HK Malmö")
        store.upsert_tavling(self.c, "Handbollsligan", sport="handboll")
        store.koppla_lag_till_tavling(self.c, "handbollsligan", "hk-malmo")
        store.koppla_lag_till_tavling(self.c, "handbollsligan", "hk-malmo")  # igen
        self.assertEqual(len(store.lista_lag_for_tavling(self.c, "handbollsligan")), 1)


    def test_innehall_round_trip(self):
        iid = store.spara_innehall(
            self.c, typ="match", status="avslutad",
            frontmatter={"titel": "A – B", "malskyttar": ["X 12'"]},
            body="Referat.")
        d = store.hamta_innehall(self.c, iid)
        self.assertEqual(d["typ"], "match")
        self.assertEqual(d["frontmatter"]["titel"], "A – B")    # json round-trip
        self.assertEqual(d["frontmatter"]["malskyttar"], ["X 12'"])
        self.assertFalse(d["publicerad"])
        self.assertEqual(len(store.lista_innehall(self.c)), 1)
        self.assertEqual(len(store.lista_innehall(self.c, typ="blogg")), 0)

    def test_innehall_export_path_och_radera(self):
        iid = store.spara_innehall(self.c, typ="event",
                                   frontmatter={"titel": "Cup"})
        store.satt_export_path(self.c, iid, "/sajt/content/event/cup.md")
        d = store.hamta_innehall(self.c, iid)
        self.assertTrue(d["publicerad"])
        self.assertEqual(d["export_path"], "/sajt/content/event/cup.md")
        store.radera_innehall(self.c, iid)
        self.assertIsNone(store.hamta_innehall(self.c, iid))


class TestFotojobbUtkast(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                                        fran="2026-04-01", till="2026-10-31")

    def test_skapa_och_lista(self):
        uid = store.skapa_fotojobb_utkast(
            self.c, tavling_id=self.tid, title="OBOS Damallsvenskan",
            start_at="2026-04-01", end_at="2026-10-31", location="Sverige")
        self.assertIsNotNone(uid)
        utkast = store.lista_fotojobb_utkast(self.c)
        self.assertEqual(len(utkast), 1)
        self.assertEqual(utkast[0]["title"], "OBOS Damallsvenskan")
        self.assertIsNone(utkast[0]["category"])       # Okategoriserat

    def test_idempotent_per_tavling(self):
        # Re-klick på "Lägg i Google Calendar" ska INTE skapa en dubblett.
        u1 = store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                         title="A", start_at="2026-04-01", end_at="2026-10-31")
        u2 = store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                         title="A", start_at="2026-04-01", end_at="2026-10-31")
        self.assertEqual(u1, u2)
        self.assertEqual(len(store.lista_fotojobb_utkast(self.c)), 1)

    def test_spara_falt(self):
        uid = store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                          title="A", start_at="2026-04-01", end_at="2026-10-31")
        store.spara_fotojobb_utkast_falt(self.c, uid, {"category": "Sport", "okand": "hoppas"})
        u = store.hamta_fotojobb_utkast(self.c, uid)
        self.assertEqual(u["category"], "Sport")

    def test_radera(self):
        uid = store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                          title="A", start_at="2026-04-01", end_at="2026-10-31")
        store.radera_fotojobb_utkast(self.c, uid)
        self.assertIsNone(store.hamta_fotojobb_utkast(self.c, uid))

    def test_radera_for_tavling(self):
        store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                    title="A", start_at="2026-04-01", end_at="2026-10-31")
        store.radera_fotojobb_utkast_for_tavling(self.c, self.tid)
        self.assertEqual(store.lista_fotojobb_utkast(self.c), [])

    def test_tas_bort_med_tavlingen(self):
        # ON DELETE CASCADE — utkastet ska försvinna om tävlingen raderas.
        store.skapa_fotojobb_utkast(self.c, tavling_id=self.tid,
                                    title="A", start_at="2026-04-01", end_at="2026-10-31")
        store.radera_tavling(self.c, self.tid)
        self.assertEqual(store.lista_fotojobb_utkast(self.c), [])


class TestMigrering(unittest.TestCase):
    def test_fresh_db_ar_v8_med_fotojobb_utkast(self):
        c = db.oppna(":memory:")
        self.assertEqual(db.schemaversion(c), 8)
        self.assertIn("urval_bild", db.tabeller(c))
        self.assertIn("tavling_lag", db.tabeller(c))
        self.assertIn("fotojobb_utkast", db.tabeller(c))
        self.assertIn("fotojobb_match", db.tabeller(c))
        self.assertIn("trupp_kalla",
                      [r[1] for r in c.execute("PRAGMA table_info(lag)")])
        self.assertIn("sida_url",
                      [r[1] for r in c.execute("PRAGMA table_info(matchen)")])
        lagkol = [r[1] for r in c.execute("PRAGMA table_info(lag)")]
        self.assertIn("sport", lagkol)
        self.assertIn("gren", lagkol)
        self.assertIn("gren",
                      [r[1] for r in c.execute("PRAGMA table_info(tavling)")])

    def test_migrera_v7_till_v8(self):
        # v7-läge (lag/tavling utan gren, lag utan sport) → additivt v8.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=7")
        c.execute("CREATE TABLE tavling(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("CREATE TABLE lag(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("INSERT INTO lag VALUES('malmo-ff','Malmö FF')")
        db._migrera(c, 7)
        lagkol = [r[1] for r in c.execute("PRAGMA table_info(lag)")]
        self.assertIn("sport", lagkol)
        self.assertIn("gren", lagkol)
        self.assertIn("gren",
                      [r[1] for r in c.execute("PRAGMA table_info(tavling)")])
        # befintlig rad orörd, nya kolumner NULL
        r = c.execute("SELECT * FROM lag WHERE id='malmo-ff'").fetchone()
        self.assertEqual(r["namn"], "Malmö FF")
        self.assertIsNone(r["sport"])

    def test_migrera_v1_till_v5(self):
        # v1-läge: urval + register-tabellerna (som alltid funnits). Migreringen
        # kör hela kedjan v1→v5 (urval_bild + tavling_lag + nya kolumner/tabell).
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.execute("PRAGMA user_version=1")
        c.execute("CREATE TABLE urval(id TEXT PRIMARY KEY)")
        c.execute("CREATE TABLE tavling(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("CREATE TABLE lag(id TEXT PRIMARY KEY, namn TEXT)")
        db._migrera(c, 1)
        namn = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertIn("urval_bild", namn)
        self.assertIn("tavling_lag", namn)
        self.assertIn("fotojobb_utkast", namn)
        kolumner = [r[1] for r in c.execute("PRAGMA table_info(lag)")]
        self.assertIn("kind", kolumner)
        self.assertIn("trupp_kalla", kolumner)

    def test_migrera_v2_till_v3(self):
        # Bygg ett v2-läge (lag/tavling utan nya kolumner) och migrera additivt.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=2")
        c.execute("CREATE TABLE tavling(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("CREATE TABLE lag(id TEXT PRIMARY KEY, namn TEXT)")
        c.execute("INSERT INTO lag VALUES('x','X')")
        db._migrera(c, 2)
        tk = [r[1] for r in c.execute("PRAGMA table_info(lag)")]
        self.assertIn("kind", tk)
        self.assertIn("profilfarg", tk)
        self.assertIn("hemsida", [r[1] for r in c.execute("PRAGMA table_info(tavling)")])
        self.assertIn("tavling_lag", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])
        # befintliga rader får default-kind via COALESCE-läsning (kolumnen är NULL
        # för gamla rader men NOT NULL-defaulten gäller nya inserts)
        self.assertEqual(c.execute("SELECT namn FROM lag WHERE id='x'").fetchone()[0], "X")


class TestSomeMaterial(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.mid = store.spara_match(self.c, {"lag_hemma": "A", "lag_borta": "B"})

    def test_spara_och_lista_nyast_forst(self):
        store.spara_some_material(self.c, kanal="instagram", format="story",
                                  match_id=self.mid, moment="Avspark", tema="Hav",
                                  fil="/foto/b1.jpg", skapad="2026-06-30T10:00:00")
        store.spara_some_material(self.c, kanal="facebook", format="inlägg",
                                  match_id=self.mid, moment="Avspark",
                                  fil="/foto/b1.jpg", skapad="2026-06-30T11:00:00")
        rader = store.lista_some_material(self.c, self.mid)
        self.assertEqual(len(rader), 2)
        self.assertEqual(rader[0]["kanal"], "facebook")     # nyast först
        self.assertEqual(rader[1]["format"], "story")

    def test_lista_filtrerar_pa_match(self):
        store.spara_some_material(self.c, kanal="instagram", format="story",
                                  match_id=self.mid)
        self.assertEqual(store.lista_some_material(self.c, "okand-match"), [])

    def test_utan_match_id_ok(self):
        sid = store.spara_some_material(self.c, kanal="instagram", format="story")
        self.assertTrue(sid)                                # match_id=None → ingen FK


if __name__ == "__main__":
    unittest.main(verbosity=2)
