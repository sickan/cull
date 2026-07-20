"""Tester för datalager-CRUD (store) — körs mot in-memory SQLite (stdlib)."""

import threading
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

    def test_toppbilder_poang_fallande(self):
        uid = store.spara_urval(self.c, kalla="x", bilder=0)
        store.ersatt_urval_bilder(self.c, uid, [
            ("s1", 1, 0.50), ("s2", 1, 0.95), ("s3", 0, 0.99), ("s4", 1, 0.70)])
        self.assertEqual(store.urval_toppbilder(self.c, uid, 2), ["s2", "s4"])
        self.assertEqual(store.urval_toppbilder(self.c, uid),    # ratade (s3) utesluts
                         ["s2", "s4", "s1"])
        self.assertEqual(store.urval_toppbilder(self.c, "finns-ej"), [])

    def test_toppbilder_sokvagar_upploser_mot_kallmapp(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            for namn in ("s2.jpg", "s4.NEF"):
                open(os.path.join(d, namn), "w").close()
            uid = store.spara_urval(self.c, kalla=d, bilder=0)
            store.ersatt_urval_bilder(self.c, uid, [
                ("s2", 1, 0.95), ("s4", 1, 0.70), ("s1", 1, 0.50)])  # s1 saknar fil
            res = store.urval_toppbilder_sokvagar(self.c, uid, 3)
            self.assertEqual([r["stem"] for r in res], ["s2", "s4", "s1"])
            self.assertTrue(res[0]["sokvag"].endswith("s2.jpg"))
            self.assertTrue(res[1]["sokvag"].endswith("s4.NEF"))
            self.assertEqual(res[2]["sokvag"], "")   # ingen fil på disk → tom sökväg

    def test_toppbilder_sokvagar_saknad_mapp_ger_tomma(self):
        uid = store.spara_urval(self.c, kalla="/finns/inte/alls", bilder=0)
        store.ersatt_urval_bilder(self.c, uid, [("s1", 1, 0.9)])
        res = store.urval_toppbilder_sokvagar(self.c, uid, 3)
        self.assertEqual(res, [{"stem": "s1", "sokvag": ""}])

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

    def test_fran_gallring_persisterar_profil_och_sport(self):
        # CULL-02: profil/sport → cull_jobb.vikter så workern kan välja
        # signaluppsättning (hela rundresan testas i test_gallring_korning).
        import json
        cfg = Gallring(topp=10, profil="sport", sport="friidrott")
        store.cull_jobb_fran_gallring(self.c, self.uid, cfg)
        v = json.loads(store.jobb_for_urval(self.c, self.uid)[0]["vikter"])
        self.assertEqual(v, {"profil": "sport", "sport": "friidrott"})

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

    def test_p5_heldagsevent_utan_motstandare(self):
        # p.5: event = match utan motståndare. Ingen borta-referens sparas även
        # om ett namn följde med; event-flaggan round-trippar.
        mid = store.spara_match(self.c, {
            "lag_hemma": "Partille Cup", "lag_borta": "", "event": True,
            "datum": "2026-07-06", "arena": "Göteborg", "sport": "fotboll",
            "liga": "Heldagsevent"})
        m = store.hamta_match(self.c, mid)
        self.assertTrue(m["event"])
        self.assertEqual(m["lag_hemma"], "Partille Cup")
        self.assertEqual(m["lag_borta"], "")
        self.assertIsNone(m["lag_borta_id"])
        # syns i listan med event-flaggan
        rad = next(r for r in store.lista_matcher(self.c) if r["id"] == mid)
        self.assertTrue(rad["event"])

    def test_tennis_inline_skapar_individutovare(self):
        # En tennismatch där sidorna skrivs in på fri hand (ingen combobox-ref)
        # ska skapa lag som utövare (kind=individ) med matchens sport — inte som
        # lag utan sport. Så Lag-registret och Matcher-profilen stämmer direkt.
        mid = store.spara_match(self.c, {
            "lag_hemma": "Rebecca Peterson", "lag_borta": "Mirjam Björklund",
            "datum": "2026-07-15", "sport": "tennis", "liga": ""})
        m = store.hamta_match(self.c, mid)
        for namn in ("Rebecca Peterson", "Mirjam Björklund"):
            lag = next(l for l in store.lista_lag(self.c) if l["namn"] == namn)
            self.assertEqual(lag["kind"], "individ")
            self.assertEqual(lag["sport"], "tennis")

    def test_fotboll_inline_forblir_lag(self):
        # Regressionsskydd: inline-skapade sidor i en LAGSPORT förblir kind=team.
        mid = store.spara_match(self.c, {
            "lag_hemma": "Nytt Lag AIK", "lag_borta": "Nytt Lag BK",
            "datum": "2026-07-15", "sport": "fotboll", "liga": ""})
        store.hamta_match(self.c, mid)
        lag = next(l for l in store.lista_lag(self.c) if l["namn"] == "Nytt Lag AIK")
        self.assertEqual(lag["kind"], "team")

    def test_efter_match_lankar_round_trip(self):
        m = dict(self.match)
        m["galleri"] = "https://malmoff.pixieset.com/damallsvenskan-27jun/"
        m["sida_url"] = "https://dalecarliaphoto.se/sport/2026-06-27-malmo-ff-kristianstad"
        mid = store.spara_match(self.c, m)
        sparad = store.hamta_match(self.c, mid)
        self.assertEqual(sparad["galleri"], m["galleri"])
        self.assertEqual(sparad["sida_url"], m["sida_url"])

    def test_redigering_bevarar_cascade_lankade_rader(self):
        # spara_match måste vara en äkta UPPDATERING (ON CONFLICT DO UPDATE),
        # inte INSERT OR REPLACE — den senare raderar+återskapar raden, vilket
        # (med FK-tvång på) tyst raderar allt som pekar på matchen(id) med
        # ON DELETE CASCADE: fotojobb-länken och SoMe-publiceringshistoriken.
        mid = store.spara_match(self.c, self.match)
        store.lanka_fotojobb_match(self.c, "jobb1", mid)
        store.spara_some_material(self.c, kanal="instagram", format="Inlägg 4:5",
                                  match_id=mid, moment="Resultat", tema="Hav",
                                  fil="/tmp/a.jpg")
        self.assertEqual(len(store.lista_some_material(self.c, mid)), 1)

        m2 = dict(self.match); m2["id"] = mid; m2["arena"] = "Ny arena"
        store.spara_match(self.c, m2)

        self.assertEqual(store.hamta_match(self.c, mid)["arena"], "Ny arena")
        self.assertEqual(store.matchref_for_fotojobb(self.c, ["jobb1"]), {"jobb1": mid})
        self.assertEqual(len(store.lista_some_material(self.c, mid)), 1)

    def test_delad_slug_id(self):
        store.spara_match(self.c, self.match)
        self.assertIsNotNone(store.hamta_lag(self.c, "malmo-ff"))   # samma som migrera
        self.assertIsNotNone(store.hamta_lag(self.c, "kristianstads-dff"))

    def test_status_harleds(self):
        m = dict(self.match); m["resultat"] = ""; m["datum"] = "2027-01-01"
        mid = store.spara_match(self.c, m)
        self.assertEqual(store.hamta_match(self.c, mid)["status"], "kommande")

    def test_resultat_vid_uppdatering_ger_avslutad(self):
        # En kommande match som EFTERÅT får ett resultat (Slutsignalen) måste bli
        # 'avslutad' — även fast utkastet bär med sig det inlästa 'kommande'.
        m = dict(self.match); m["resultat"] = ""; m["datum"] = "2027-01-01"
        mid = store.spara_match(self.c, m)
        uppd = store.hamta_match(self.c, mid)          # bär status='kommande'
        uppd["resultat"] = "2-0"
        store.spara_match(self.c, uppd)
        self.assertEqual(store.hamta_match(self.c, mid)["status"], "avslutad")

    def test_satt_resultat_uppgraderar_status(self):
        # Resultatremsan (satt_resultat) ska följa samma regel: resultat →
        # avslutad, rensat resultat → återhärledd status.
        m = dict(self.match); m["resultat"] = ""; m["datum"] = "2027-01-01"
        mid = store.spara_match(self.c, m)
        store.satt_resultat(self.c, mid, resultat="2-0")
        self.assertEqual(store.hamta_match(self.c, mid)["status"], "avslutad")
        store.satt_resultat(self.c, mid, resultat="")
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


class TestFotojobbNotering(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_skrivs_och_lases_i_batch(self):
        store.satt_fotojobb_notering(self.c, "jobb1", "Kund: Anna")
        store.satt_fotojobb_notering(self.c, "jobb2", "Stativ, ND-filter")
        self.assertEqual(store.noteringar_for_fotojobb(self.c, ["jobb1", "jobb2"]),
                         {"jobb1": "Kund: Anna", "jobb2": "Stativ, ND-filter"})

    def test_uppdateras_och_raderas(self):
        store.satt_fotojobb_notering(self.c, "jobb1", "Kund: Anna")
        store.satt_fotojobb_notering(self.c, "jobb1", "Kund: Anna & Erik")
        self.assertEqual(store.noteringar_for_fotojobb(self.c, ["jobb1"]),
                         {"jobb1": "Kund: Anna & Erik"})
        # tom text raderar raden — inga tomma noteringar lagras
        store.satt_fotojobb_notering(self.c, "jobb1", "   ")
        self.assertEqual(store.noteringar_for_fotojobb(self.c, ["jobb1"]), {})

    def test_utan_ider(self):
        self.assertEqual(store.noteringar_for_fotojobb(self.c, []), {})
        self.assertEqual(store.noteringar_for_fotojobb(self.c, [None]), {})


class TestAckreditering(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_grundlage_utan_rad(self):
        a = store.hamta_ackreditering(self.c, "jobb1")
        self.assertEqual(a, {"status": "ejbegard", "note": "",
                             "paminnelse_jobb_id": None, "thread_id": None})
        self.assertEqual(store.ackreditering_for_fotojobb(self.c, ["jobb1"]), {})

    def test_satt_status_och_note(self):
        store.satt_ackreditering(self.c, "jobb1", status="begard")
        store.satt_ackreditering(self.c, "jobb1", note="Väst vid mittlinjen")
        a = store.hamta_ackreditering(self.c, "jobb1")
        self.assertEqual(a["status"], "begard")          # note-skrivning rör inte status
        self.assertEqual(a["note"], "Väst vid mittlinjen")
        batch = store.ackreditering_for_fotojobb(self.c, ["jobb1", "jobb2"])
        self.assertEqual(list(batch), ["jobb1"])

    def test_grundlage_raderar_raden(self):
        # Nollställd till Ej begärd + tom not = grundläget → raden ska bort,
        # tabellen bär bara avvikelser.
        store.satt_ackreditering(self.c, "jobb1", status="beviljad", note="x")
        store.satt_ackreditering(self.c, "jobb1", status="ejbegard", note="")
        self.assertEqual(store.ackreditering_for_fotojobb(self.c, ["jobb1"]), {})

    def test_okand_status_kastar(self):
        with self.assertRaises(ValueError):
            store.satt_ackreditering(self.c, "jobb1", status="kanske")

    def test_paminnelse_id_satts_och_rensas(self):
        store.satt_ackreditering(self.c, "jobb1", paminnelse_jobb_id="rem1")
        self.assertEqual(store.hamta_ackreditering(self.c, "jobb1")
                         ["paminnelse_jobb_id"], "rem1")
        store.satt_ackreditering(self.c, "jobb1", paminnelse_jobb_id=None)
        self.assertEqual(store.ackreditering_for_fotojobb(self.c, ["jobb1"]), {})

    def test_radera(self):
        store.satt_ackreditering(self.c, "jobb1", status="nekad")
        store.radera_ackreditering(self.c, "jobb1")
        self.assertEqual(store.hamta_ackreditering(self.c, "jobb1")["status"],
                         "ejbegard")


class TestLagTavling(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_upsert_lag_uppdaterar_utan_att_nolla(self):
        lid = store.upsert_lag(self.c, "Malmö FF", instagram="@malmoff")
        store.upsert_lag(self.c, "Malmö FF", logga="/x.png")   # bara logga
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["instagram"], "@malmoff")          # bevarat
        self.assertEqual(lag["logga"], "/x.png")                # tillagt

    def test_nytt_lag_ar_inte_arkiverat(self):
        lid = store.upsert_lag(self.c, "Malmö FF")
        self.assertEqual(store.hamta_lag(self.c, lid)["arkiverad"], 0)

    def test_arkivera_och_avarkivera_lag(self):
        lid = store.upsert_lag(self.c, "Malmö FF", instagram="@malmoff")
        store.upsert_lag(self.c, "Malmö FF", arkiverad=True)
        self.assertEqual(store.hamta_lag(self.c, lid)["arkiverad"], 1)
        # arkiverad=False måste kunna nolla flaggan — inte tolkas som "rör inte"
        store.upsert_lag(self.c, "Malmö FF", arkiverad=False)
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["arkiverad"], 0)
        self.assertEqual(lag["instagram"], "@malmoff")   # övriga fält orörda

    def test_arkiverad_utelamnad_ror_inte_flaggan(self):
        lid = store.upsert_lag(self.c, "Malmö FF", arkiverad=True)
        store.upsert_lag(self.c, "Malmö FF", logga="/x.png")
        self.assertEqual(store.hamta_lag(self.c, lid)["arkiverad"], 1)

    def test_upsert_tavling(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")
        self.assertEqual(tid, "obos-damallsvenskan")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)

    def test_upsert_tavling_uppdaterar(self):
        # Samma namn + SAMMA sport/gren = samma post (uppdateras).
        store.upsert_tavling(self.c, "EM Volley", sport="volleyboll", typ="liga")
        store.upsert_tavling(self.c, "EM Volley", sport="volleyboll", typ="masterskap")
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["typ"], "masterskap")       # uppdaterat
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)   # ingen dubblett

    def test_upsert_tavling_samma_namn_annan_gren_eller_sport(self):
        # BUG-01: samma namn med annan gren/sport är SKILDA poster — tidigare
        # skrevs originalet över (European League 2026 dam raderades av herr).
        dam = store.upsert_tavling(self.c, "European League 2026",
                                   sport="volleyboll", typ="masterskap",
                                   gren="dam", fran="2026-06-12")
        herr = store.upsert_tavling(self.c, "European League 2026",
                                    sport="volleyboll", typ="masterskap",
                                    gren="herr")
        self.assertNotEqual(dam, herr)
        d = store.hamta_tavling(self.c, dam)
        self.assertEqual(d["gren"], "dam")             # originalet orört
        self.assertEqual(d["fran"], "2026-06-12")
        self.assertEqual(store.hamta_tavling(self.c, herr)["gren"], "herr")
        # Annan sport likaså ("SM" handboll ≠ "SM" basket-analogt)
        a = store.upsert_tavling(self.c, "SM 2026", sport="handboll")
        b = store.upsert_tavling(self.c, "SM 2026", sport="volleyboll")
        self.assertNotEqual(a, b)
        # Samma kombination igen → träffar sin egen (suffixade) post
        self.assertEqual(store.upsert_tavling(
            self.c, "European League 2026", sport="volleyboll",
            gren="herr"), herr)

    def test_upsert_tavling_id_byter_namn(self):
        # Med id kan namnet bytas på rätt rad (referenser följer id:t).
        tid = store.upsert_tavling(self.c, "Nordea Open", sport="tennis",
                                   typ="turnering", gren="herr")
        tid2 = store.upsert_tavling(self.c, "Nordea Open ATP250", id=tid,
                                    sport="tennis", typ="turnering")
        self.assertEqual(tid2, tid)
        self.assertEqual(store.hamta_tavling(self.c, tid)["namn"],
                         "Nordea Open ATP250")
        self.assertEqual(len(store.lista_tavlingar(self.c)), 1)

    def test_spara_match_ror_inte_tavlingens_metadata(self):
        # BUG-01 (värsta delen): varje match-spar nollade tävlingens typ/datum/
        # kalender (spara_match körde full upsert med bara namn+sport).
        store.upsert_tavling(self.c, "Nordea Open - ATP", sport="tennis",
                             typ="turnering", gren="herr", fran="2026-07-13",
                             till="2026-07-19", ort="Båstad",
                             arena="Båstad Tennisstadion", kalender=True)
        store.spara_match(self.c, {"lag_hemma": "Leo Borg",
                                   "lag_borta": "Casper Ruud",
                                   "sport": "tennis",
                                   "liga": "Nordea Open - ATP"})
        t = store.hamta_tavling(self.c, "nordea-open-atp")
        self.assertEqual(t["typ"], "turnering")
        self.assertEqual(t["fran"], "2026-07-13")
        self.assertEqual(t["arena"], "Båstad Tennisstadion")
        self.assertEqual(t["kalender"], 1)

    def test_spara_match_tavling_id_vinner_over_namnet(self):
        # Två tävlingar med samma namn → Comboboxens id-ref pekar rätt.
        store.upsert_tavling(self.c, "European League 2026",
                             sport="volleyboll", gren="dam")
        herr = store.upsert_tavling(self.c, "European League 2026",
                                    sport="volleyboll", gren="herr")
        mid = store.spara_match(self.c, {
            "lag_hemma": "Sverige", "lag_borta": "Litauen",
            "sport": "volleyboll", "liga": "European League 2026",
            "tavling_id": herr})
        self.assertEqual(store.hamta_match(self.c, mid)["tavling_id"], herr)

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

    def test_discipliner_med_deltagare(self):
        # B-001: tävlingens grenar (discipliner) + deltagare per gren — en
        # deltagare kan stå i flera grenar (Längd + Tresteg).
        tid = store.upsert_tavling(self.c, "Friidrotts-SM 2026",
                                   sport="friidrott", typ="masterskap")
        a = store.upsert_lag(self.c, "Alva Hoppare", kind="individ",
                             sport="friidrott", klubb="Malmö AI")
        langd = store.upsert_disciplin(self.c, tid, "Längd", typ="hoppkast")
        tresteg = store.upsert_disciplin(self.c, tid, "Tresteg", typ="hoppkast")
        store.koppla_disciplin_deltagare(self.c, langd, a)
        store.koppla_disciplin_deltagare(self.c, tresteg, a)
        disc = store.lista_discipliner(self.c, tid)
        self.assertEqual([d["namn"] for d in disc], ["Längd", "Tresteg"])
        self.assertEqual(disc[0]["deltagare"][0]["namn"], "Alva Hoppare")
        self.assertEqual(disc[0]["deltagare"][0]["klubb"], "Malmö AI")
        self.assertEqual(disc[1]["deltagare"][0]["namn"], "Alva Hoppare")
        # Deltagaren kopplas automatiskt in i tävlingen (deltagarlistan)
        self.assertIn(a, [l["id"] for l in store.lista_lag_for_tavling(self.c, tid)])
        # Urkoppling + namn/typ-uppdatering + radering
        store.koppla_disciplin_deltagare(self.c, tresteg, a, pa=False)
        self.assertEqual(store.lista_discipliner(self.c, tid)[1]["deltagare"], [])
        store.upsert_disciplin(self.c, tid, "Längd — final", typ="hoppkast", id=langd)
        self.assertEqual(store.lista_discipliner(self.c, tid)[0]["namn"], "Längd — final")
        store.radera_disciplin(self.c, langd)
        self.assertEqual(len(store.lista_discipliner(self.c, tid)), 1)
        # Ogiltig typ faller tillbaka; tomt namn skapar inget
        d3 = store.upsert_disciplin(self.c, tid, "100 m", typ="ogiltig")
        self.assertEqual(store.lista_discipliner(self.c, tid)[-1]["typ"], "hoppkast")
        self.assertIsNone(store.upsert_disciplin(self.c, tid, "  "))
        # Tävlingsradering städar (CASCADE)
        store.radera_tavling(self.c, tid)
        self.assertEqual(store.lista_discipliner(self.c, tid), [])
        _ = d3

    def test_upsert_lag_ackrediteringsregler(self):
        # Klubben äger ackrediteringen för sina hemmamatcher (seriespel) —
        # samma fältkontrakt som på tävling: None rör inte, tom sträng rensar.
        lid = store.upsert_lag(self.c, "Malmö FF",
                               press_email="press@mff.se", ackr_dagar=7)
        store.upsert_lag(self.c, "Malmö FF", logga="/x.png")   # rör ej
        lag = store.hamta_lag(self.c, lid)
        self.assertEqual(lag["press_email"], "press@mff.se")
        self.assertEqual(lag["ackr_dagar"], 7)
        store.upsert_lag(self.c, "Malmö FF", press_email="", ackr_dagar="")
        lag = store.hamta_lag(self.c, lid)
        self.assertIsNone(lag["press_email"])
        self.assertIsNone(lag["ackr_dagar"])

    def test_upsert_lag_anteckning(self):
        # C12/M-1: anteckningen på utövaren följer samma fältkontrakt som
        # ackrediteringsfälten — None rör inte, tom sträng rensar.
        lid = store.upsert_lag(self.c, "Wilma Ek", kind="individ",
                               klubb="Turebergs FK", anteckning="Vill ha låg vinkel")
        self.assertEqual(store.hamta_lag(self.c, lid)["anteckning"],
                         "Vill ha låg vinkel")
        store.upsert_lag(self.c, "Wilma Ek", logga="/p.png")      # rör ej
        self.assertEqual(store.hamta_lag(self.c, lid)["anteckning"],
                         "Vill ha låg vinkel")
        store.upsert_lag(self.c, "Wilma Ek", anteckning="")       # rensar
        self.assertIsNone(store.hamta_lag(self.c, lid)["anteckning"])

    def test_registret_bar_bada_slagen(self):
        # M-1: ETT register — utövare och lag ligger i samma tabell och skiljs
        # bara av kind. Registerlistan måste returnera båda.
        store.upsert_lag(self.c, "Wilma Ek", kind="individ", gren="dam",
                         klubb="Turebergs FK")
        store.upsert_lag(self.c, "Malmö FF", kind="team", gren="herr",
                         stall_hemma="#87CEEB", stall_borta="#16181C")
        slag = {l["namn"]: l["kind"] for l in store.lista_lag(self.c)}
        self.assertEqual(slag, {"Wilma Ek": "individ", "Malmö FF": "team"})

    def test_upsert_tavling_ackrediteringsregler(self):
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                             press_email="press@obos.se", ackr_dagar=14)
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll")  # rör ej
        t = store.lista_tavlingar(self.c)[0]
        self.assertEqual(t["press_email"], "press@obos.se")   # bevarat
        self.assertEqual(t["ackr_dagar"], 14)
        # tom sträng rensar (None = "rör inte" — fältet skickas alltid av UI:t)
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                             press_email="", ackr_dagar="")
        t = store.lista_tavlingar(self.c)[0]
        self.assertIsNone(t["press_email"])
        self.assertIsNone(t["ackr_dagar"])
        # ogiltigt dagtal får inte fälla sparningen — tolkas som orimligt → NULL
        store.upsert_tavling(self.c, "OBOS Damallsvenskan", sport="fotboll",
                             ackr_dagar="tio")
        self.assertIsNone(store.lista_tavlingar(self.c)[0]["ackr_dagar"])

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

    def test_innehall_aterustar_matchpost_vid_ompublicering(self):
        # En match = ett match-innehåll. Ompublicering utan explicit id ska
        # UPPDATERA samma rad, inte skapa en dubblett (annars flera rader med
        # samma slug i content-sync → sajten kan visa en äldre hero-bild).
        self.c.execute("INSERT INTO matchen(id,skapad) VALUES('m1','2026-06-27')")
        a = store.spara_innehall(self.c, typ="match", match_id="m1",
                                 frontmatter={"titel": "A – B", "hero": "gammal.jpg"})
        b = store.spara_innehall(self.c, typ="match", match_id="m1",
                                 frontmatter={"titel": "A – B", "hero": "ny.jpg"})
        self.assertEqual(a, b)                                    # samma id återanvänt
        self.assertEqual(len(store.lista_innehall(self.c, typ="match")), 1)
        self.assertEqual(store.hamta_innehall(self.c, b)["frontmatter"]["hero"], "ny.jpg")
        # annan match → egen rad
        self.c.execute("INSERT INTO matchen(id,skapad) VALUES('m2','2026-06-28')")
        c = store.spara_innehall(self.c, typ="match", match_id="m2",
                                 frontmatter={"titel": "C – D"})
        self.assertNotEqual(a, c)
        self.assertEqual(len(store.lista_innehall(self.c, typ="match")), 2)

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
    def test_fresh_db_ar_v11_med_fotojobb_utkast(self):
        c = db.oppna(":memory:")
        self.assertEqual(db.schemaversion(c), db.SCHEMA_VERSION)
        self.assertIn("urval_bild", db.tabeller(c))
        self.assertIn("tavling_lag", db.tabeller(c))
        self.assertIn("fotojobb_utkast", db.tabeller(c))
        self.assertIn("fotojobb_match", db.tabeller(c))
        self.assertIn("publicera_material", db.tabeller(c))
        self.assertNotIn("aktivitet", db.tabeller(c))   # v17: kurerad lista borttagen
        self.assertIn("publicera_material_historik", db.tabeller(c))
        pubmatkol = [r[1] for r in c.execute("PRAGMA table_info(publicera_material)")]
        self.assertIn("dropbox", pubmatkol)
        self.assertIn("foto", pubmatkol)
        self.assertIn("banor", pubmatkol)
        self.assertIn("ch_results", pubmatkol)
        # v26 (tennis Fas 3): turnerings-SoMe-mål på material.
        self.assertIn("mal_typ", pubmatkol)
        self.assertIn("tavling_id", pubmatkol)
        self.assertIn("tavling_id",
                      [r[1] for r in c.execute("PRAGMA table_info(some_material)")])
        self.assertIn("trupp_kalla",
                      [r[1] for r in c.execute("PRAGMA table_info(lag)")])
        # v13: sportneutralt mellanresultat + innebandy i sport-enumen.
        matchkol = [r[1] for r in c.execute("PRAGMA table_info(matchen)")]
        self.assertIn("mellan", matchkol)
        self.assertNotIn("halvtid", matchkol)
        mid = store.spara_match(c, {"lag_hemma": "A", "lag_borta": "B",
                                    "sport": "innebandy"})
        self.assertEqual(store.hamta_match(c, mid)["sport"], "innebandy")
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

    def test_migrera_v25_till_v26(self):
        # v25-läge: material-tabeller utan turnerings-kolumnerna → additivt v26.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=25")
        c.execute("CREATE TABLE some_material(id TEXT PRIMARY KEY, match_id TEXT)")
        c.execute("CREATE TABLE publicera_material(id TEXT PRIMARY KEY, "
                  "kind TEXT, match_id TEXT, match_namn TEXT)")
        c.execute("INSERT INTO publicera_material VALUES('m1','some','x','A – B')")
        db._migrera(c, 25)
        pubkol = [r[1] for r in c.execute("PRAGMA table_info(publicera_material)")]
        self.assertIn("mal_typ", pubkol)
        self.assertIn("tavling_id", pubkol)
        self.assertIn("tavling_id",
                      [r[1] for r in c.execute("PRAGMA table_info(some_material)")])
        # befintlig rad orörd, mal_typ defaultar 'match'
        r = c.execute("SELECT * FROM publicera_material WHERE id='m1'").fetchone()
        self.assertEqual(r["match_namn"], "A – B")
        self.assertEqual(r["mal_typ"], "match")
        self.assertIsNone(r["tavling_id"])

    def test_migrera_v41_till_v42_favoritgren(self):
        # M-7: additiv favorit-kolumn på disciplin. Befintliga grenar blir
        # omarkerade, och migreringen ska tåla att köras om.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=41")
        c.execute("CREATE TABLE disciplin(id TEXT PRIMARY KEY, tavling_id TEXT, "
                  "namn TEXT, typ TEXT, gren TEXT, ordning INTEGER)")
        c.execute("INSERT INTO disciplin VALUES('d1','sm','Diskus','hoppkast',"
                  "'dam',0)")
        db._migrera(c, 41)
        self.assertIn("favorit",
                      [r[1] for r in c.execute("PRAGMA table_info(disciplin)")])
        r = c.execute("SELECT * FROM disciplin WHERE id='d1'").fetchone()
        self.assertEqual(r["namn"], "Diskus")
        self.assertEqual(r["favorit"], 0)
        db._migrera(c, 41)     # idempotent

    def test_turnering_material_round_trip(self):
        # Turnerings-SoMe: material utan match_id, med tavling_id + mal_typ.
        c = db.oppna(":memory:")
        store.upsert_tavling(c, "Nordea Open", sport="tennis", typ="turnering")
        mid = store.spara_publicera_material(
            c, kind="some", status="utkast", mal_typ="turnering",
            tavling_id="nordea-open", match_namn="Nordea Open",
            caption="Dag 3 i Båstad", channels=["ig", "fb"])
        rad = next(m for m in store.lista_publicera_material(c) if m["id"] == mid)
        self.assertEqual(rad["mal_typ"], "turnering")
        self.assertEqual(rad["tavling_id"], "nordea-open")
        self.assertIsNone(rad["match_id"])
        self.assertEqual(rad["match_namn"], "Nordea Open")
        self.assertEqual(rad["channels"], ["ig", "fb"])
        # publicerad post loggas mot tävlingen
        store.spara_some_material(c, kanal="instagram", format="9x16",
                                  tavling_id="nordea-open", moment="Dagens matcher")
        self.assertEqual(len(store.lista_some_material_for_tavling(c, "nordea-open")), 1)

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

    def test_migrera_v22_till_v23_sportevent_typ(self):
        # v22-läge: innehall med gamla typ-CHECK:en (utan sportevent) och en
        # befintlig rad. Efter v23 ska sportevent gå att spara och raden vara
        # orörd (tabellen skrivs om — CHECK kan inte ALTER:as).
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=22")
        c.execute("CREATE TABLE matchen(id TEXT PRIMARY KEY)")
        c.execute("""CREATE TABLE innehall (
          id TEXT PRIMARY KEY,
          typ TEXT NOT NULL CHECK (typ IN ('match','event','landskap','portratt','blogg')),
          match_id TEXT REFERENCES matchen(id) ON DELETE SET NULL,
          status TEXT, frontmatter TEXT, body TEXT, export_path TEXT,
          publicerad INTEGER NOT NULL DEFAULT 0, synkad_tid TEXT, skapad TEXT)""")
        c.execute("INSERT INTO matchen VALUES('m1')")
        c.execute("INSERT INTO innehall(id,typ,match_id,publicerad,skapad) "
                  "VALUES('i1','match','m1',1,'2026-07-01')")
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO innehall(id,typ,publicerad) VALUES('x','sportevent',0)")
        db._migrera(c, 22)
        # befintlig rad orörd (inkl. FK-koppling och publicerad-flaggan)
        r = c.execute("SELECT * FROM innehall WHERE id='i1'").fetchone()
        self.assertEqual(r["typ"], "match")
        self.assertEqual(r["match_id"], "m1")
        self.assertEqual(r["publicerad"], 1)
        # nya typen accepteras nu
        c.execute("INSERT INTO innehall(id,typ,publicerad,skapad) "
                  "VALUES('i2','sportevent',0,'2026-07-11')")
        self.assertEqual(c.execute(
            "SELECT typ FROM innehall WHERE id='i2'").fetchone()["typ"], "sportevent")

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

    def test_migrera_v8_till_v9(self):
        # v8-läge (utan publicera_material) → additivt v9.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=8")
        c.execute("CREATE TABLE matchen(id TEXT PRIMARY KEY)")
        db._migrera(c, 8)
        self.assertIn("publicera_material", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])

    def test_migrera_v9_till_v10(self):
        # v9-läge (publicera_material utan dropbox/foto/banor) → additivt v10.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=9")
        c.execute("CREATE TABLE matchen(id TEXT PRIMARY KEY)")
        c.execute("""CREATE TABLE publicera_material (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, match_id TEXT, match_namn TEXT,
            status TEXT NOT NULL, moment TEXT, tema TEXT, channels TEXT, caption TEXT,
            uppdaterad TEXT NOT NULL)""")
        c.execute("INSERT INTO publicera_material(id,kind,status,uppdaterad) "
                  "VALUES('m1','live','utkast','2026-07-03T00:00:00')")
        db._migrera(c, 9)
        kol = [r[1] for r in c.execute("PRAGMA table_info(publicera_material)")]
        self.assertIn("dropbox", kol)
        self.assertIn("foto", kol)
        self.assertIn("banor", kol)
        # befintlig rad orörd
        self.assertEqual(c.execute(
            "SELECT kind FROM publicera_material WHERE id='m1'").fetchone()[0], "live")

    def test_migrera_v10_till_v11(self):
        # v10-läge (publicera_material utan ch_results, status-CHECK saknar
        # 'delvis') → tabellen skrivs om + publicera_material_historik skapas.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA user_version=10")
        c.execute("CREATE TABLE matchen(id TEXT PRIMARY KEY)")
        c.execute("""CREATE TABLE publicera_material (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, match_id TEXT, match_namn TEXT,
            status TEXT NOT NULL CHECK (status IN ('utkast','publicerad')), moment TEXT,
            tema TEXT, dropbox TEXT, foto TEXT, channels TEXT, caption TEXT, banor TEXT,
            uppdaterad TEXT NOT NULL)""")
        c.execute("INSERT INTO publicera_material(id,kind,status,uppdaterad) "
                  "VALUES('m1','some','publicerad','2026-07-03T00:00:00')")
        db._migrera(c, 10)
        kol = [r[1] for r in c.execute("PRAGMA table_info(publicera_material)")]
        self.assertIn("ch_results", kol)
        self.assertIn("publicera_material_historik", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])
        # befintlig rad orörd, och det nya statuset accepteras nu
        self.assertEqual(c.execute(
            "SELECT kind FROM publicera_material WHERE id='m1'").fetchone()[0], "some")
        c.execute("UPDATE publicera_material SET status='delvis' WHERE id='m1'")
        self.assertEqual(c.execute(
            "SELECT status FROM publicera_material WHERE id='m1'").fetchone()[0], "delvis")

    def test_migrera_v12_till_v13(self):
        # v12-läge (halvtid-kolumn, sport-CHECK utan innebandy på tavling/lag/
        # matchen) → mellan-kolumn (lossless övertagen från halvtid) + CHECK
        # utökad. Bygg ett minimalt v12-schema för de tre tabellerna.
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA user_version=12")
        c.executescript("""
        CREATE TABLE tavling (
          id TEXT PRIMARY KEY, typ TEXT NOT NULL, namn TEXT NOT NULL,
          sport TEXT NOT NULL CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
          gren TEXT, hemsida TEXT, fran TEXT, till TEXT, ort TEXT, arena TEXT,
          logga TEXT, kalender INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE lag (
          id TEXT PRIMARY KEY, namn TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'team',
          sport TEXT CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
          gren TEXT, hemsida TEXT, instagram TEXT, logga TEXT,
          stall_hemma TEXT, stall_borta TEXT, stall_tredje TEXT,
          profilfarg TEXT, klubb TEXT, trupp_kalla TEXT
        );
        CREATE TABLE matchen (
          id TEXT PRIMARY KEY, tavling_id TEXT,
          sport TEXT CHECK (sport IN ('fotboll','handboll','volleyboll','beachvolley','tennis')),
          lag_hemma_id TEXT, lag_borta_id TEXT, datum TEXT, tid TEXT, arena TEXT,
          resultat TEXT, halvtid TEXT, malskyttar TEXT,
          status TEXT NOT NULL DEFAULT 'kommande', galleri TEXT, sida_url TEXT,
          omslag TEXT, skapad TEXT NOT NULL
        );
        """)
        c.execute("INSERT INTO lag(id,namn) VALUES('h','Hemma'),('b','Borta')")
        c.execute(
            "INSERT INTO matchen(id,sport,lag_hemma_id,lag_borta_id,resultat,"
            "halvtid,skapad) VALUES('m1','fotboll','h','b','6-0','3-0','2026-07-05')")
        db._migrera(c, 12)
        matchkol = [r[1] for r in c.execute("PRAGMA table_info(matchen)")]
        self.assertIn("mellan", matchkol)
        self.assertNotIn("halvtid", matchkol)
        rad = c.execute("SELECT resultat, mellan FROM matchen WHERE id='m1'").fetchone()
        self.assertEqual((rad["resultat"], rad["mellan"]), ("6-0", "3-0"))
        # sport-enumen tillåter nu innebandy på alla tre tabellerna.
        c.execute("INSERT INTO tavling(id,typ,namn,sport) VALUES('t1','liga','L','innebandy')")
        c.execute("INSERT INTO lag(id,namn,sport) VALUES('l1','Lag','innebandy')")
        c.execute("UPDATE matchen SET sport='innebandy' WHERE id='m1'")
        self.assertEqual(c.execute(
            "SELECT sport FROM matchen WHERE id='m1'").fetchone()[0], "innebandy")
        self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])


class TestPassOchProgram(unittest.TestCase):
    """V5 §8 — pass på gren + det härledda dagsprogrammet."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(
            self.c, "Friidrotts-SM 2026", sport="friidrott", typ="masterskap",
            fran="2026-07-24", till="2026-07-26", ort="Uppsala")
        self.gren = store.upsert_disciplin(self.c, self.ev, "100 m dam",
                                           typ="sprint")

    def test_pass_sorteras_pa_tid_otidsatta_sist(self):
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        store.upsert_pass(self.c, self.gren, "Uppvärmning", "2026-07-24")
        store.upsert_pass(self.c, self.gren, "Försök", "2026-07-24", tid="09:00")
        namn = [p["namn"] for p in store.lista_pass(self.c, self.gren)]
        self.assertEqual(namn, ["Försök", "Uppvärmning", "Final"])

    def test_upsert_pass_kraver_namn_och_datum(self):
        self.assertIsNone(store.upsert_pass(self.c, self.gren, "", "2026-07-24"))
        self.assertIsNone(store.upsert_pass(self.c, self.gren, "Final", ""))

    def test_upsert_pass_uppdaterar_befintligt(self):
        pid = store.upsert_pass(self.c, self.gren, "Final", "2026-07-25",
                                tid="19:10")
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:40",
                          id=pid)
        pas = store.lista_pass(self.c, self.gren)
        self.assertEqual(len(pas), 1)
        self.assertEqual(pas[0]["tid"], "19:40")

    def test_program_grupperar_per_dag_i_tidsordning(self):
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        store.upsert_pass(self.c, self.gren, "Semi", "2026-07-24", tid="14:00")
        store.upsert_pass(self.c, self.gren, "Försök", "2026-07-24", tid="09:00")
        dagar = store.program(self.c, self.ev)
        self.assertEqual([d["datum"] for d in dagar],
                         ["2026-07-24", "2026-07-25"])
        self.assertEqual([r["namn"] for r in dagar[0]["rader"]],
                         ["Försök", "Semi"])

    def test_program_filtrerar_pa_dag(self):
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        store.upsert_pass(self.c, self.gren, "Försök", "2026-07-24", tid="09:00")
        dagar = store.program(self.c, self.ev, datum="2026-07-25")
        self.assertEqual(len(dagar), 1)
        self.assertEqual(dagar[0]["rader"][0]["namn"], "Final")

    def test_program_vaver_in_matcher_i_samma_tidslinje(self):
        """Cup/mästerskap med matcher ska ligga i SAMMA program som grenpassen
        — eventtypen är etikett, inte beteende."""
        store.upsert_pass(self.c, self.gren, "Försök", "2026-07-24", tid="09:00")
        store.spara_match(self.c, {
            "lag_hemma": "Sverige", "lag_borta": "Norge", "sport": "friidrott",
            "datum": "2026-07-24", "tid": "11:30", "tavling_id": self.ev})
        rader = store.program(self.c, self.ev)[0]["rader"]
        self.assertEqual([(r["slag"], r["namn"]) for r in rader],
                         [("pass", "Försök"), ("match", "Sverige – Norge")])

    def test_program_baraf_tidsatta_dagar_ingen_dubbellagring(self):
        """Ändrad passtid slår igenom i programmet utan att något skrivs om."""
        pid = store.upsert_pass(self.c, self.gren, "Final", "2026-07-25",
                                tid="19:10")
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-26", tid="17:00",
                          id=pid)
        dagar = store.program(self.c, self.ev)
        self.assertEqual([d["datum"] for d in dagar], ["2026-07-26"])

    def test_program_bar_deltagare_med_handle(self):
        """Vem + handle ska finnas där programmet läses — dagens taggning."""
        lid = store.upsert_lag(self.c, "Armand Duplantis", kind="individ",
                               sport="friidrott", instagram="mondo_duplantis")
        store.koppla_disciplin_deltagare(self.c, self.gren, lid)
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual([(d["namn"], d["handle"]) for d in rad["deltagare"]],
                         [("Armand Duplantis", "@mondo_duplantis")])

    def test_deltagare_ar_unionen_gren_och_eventkoppling(self):
        """v40: ETT register (lag kind='individ'). Unionen är nu gren-kopplade
        (disciplin_deltagare) ∪ event-kopplade (event_deltagare) — båda mot lag."""
        lid = store.upsert_lag(self.c, "Utövarlag", kind="individ",
                               sport="friidrott", instagram="@ur_lag")
        store.koppla_disciplin_deltagare(self.c, self.gren, lid)
        reg = store.upsert_individ(self.c, "Ur registret", sport="friidrott",
                                   instagram="@ur_reg")
        store.satt_event_deltagare(self.c, self.ev, reg, [self.gren])
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual(sorted(d["handle"] for d in rad["deltagare"]),
                         ["@ur_lag", "@ur_reg"])

    def test_individ_i_annan_gren_kommer_inte_med(self):
        annan = store.upsert_disciplin(self.c, self.ev, "Höjdhopp")
        fel = store.upsert_individ(self.c, "Fel gren", sport="friidrott")
        store.satt_event_deltagare(self.c, self.ev, fel, [annan])
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual(rad["deltagare"], [])

    def test_handle_normaliseras_utan_att_ata_osakerhetsmarkoren(self):
        self.assertEqual(store._handle("mondo"), "@mondo")
        self.assertEqual(store._handle("@mondo"), "@mondo")
        self.assertEqual(store._handle("?mondo"), "?mondo")
        self.assertIsNone(store._handle("  "))

    def test_pass_foljer_med_nar_grenen_raderas(self):
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        store.radera_disciplin(self.c, self.gren)
        self.assertEqual(store.program(self.c, self.ev), [])


class TestProgramImport(unittest.TestCase):
    """V5 §8 S2 — tolkade rader in i grenar/pass/deltagare."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(
            self.c, "Friidrotts-SM 2026", sport="friidrott", typ="masterskap",
            fran="2026-07-24", till="2026-07-26")

    def _rad(self, gren, pas, datum="2026-07-24", tid="09:00", plats=""):
        return {"gren": gren, "pass": pas, "datum": datum, "tid": tid,
                "plats": plats}

    def test_skapar_saknade_grenar_och_pass(self):
        sam = store.importera_program(self.c, self.ev, [
            self._rad("100 m dam", "Försök"),
            self._rad("100 m dam", "Final", datum="2026-07-25", tid="19:10"),
            self._rad("Höjd", "Kval"),
        ])
        self.assertEqual(sam["grenar_skapade"], ["100 m dam", "Höjd"])
        self.assertEqual(sam["pass_nya"], 3)
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 2)

    def test_ateranvander_befintlig_gren_oavsett_skiftlage(self):
        store.upsert_disciplin(self.c, self.ev, "100 m dam")
        sam = store.importera_program(self.c, self.ev,
                                      [self._rad("100 M DAM", "Försök")])
        self.assertEqual(sam["grenar_skapade"], [])
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 1)

    def test_omimport_uppdaterar_tid_i_stallet_for_att_dubblera(self):
        """Arrangörens version 4 klistras ovanpå version 3."""
        store.importera_program(self.c, self.ev,
                                [self._rad("100 m dam", "Final", tid="19:10")])
        sam = store.importera_program(self.c, self.ev,
                                      [self._rad("100 m dam", "Final", tid="19:40")])
        self.assertEqual((sam["pass_nya"], sam["pass_uppdaterade"]), (0, 1))
        gren = store.lista_discipliner(self.c, self.ev)[0]["id"]
        pas = store.lista_pass(self.c, gren)
        self.assertEqual(len(pas), 1)
        self.assertEqual(pas[0]["tid"], "19:40")

    def test_rad_utan_datum_hoppas_over(self):
        """Datum är det enda som inte går att härleda — utan det kan raden
        inte hamna i en dag. (Saknat passnamn duger däremot: se
        TestGrenklassOchFaslosa.)"""
        sam = store.importera_program(self.c, self.ev, [
            self._rad("Kula", "Final", datum=""),
        ])
        self.assertEqual(sam["pass_nya"], 0)
        self.assertEqual(store.program(self.c, self.ev), [])

    def test_manuellt_tillagt_pass_overlever_omimport(self):
        gid = store.upsert_disciplin(self.c, self.ev, "100 m dam")
        store.upsert_pass(self.c, gid, "Uppvärmning", "2026-07-24", tid="08:00")
        store.importera_program(self.c, self.ev,
                                [self._rad("100 m dam", "Final", tid="19:10")])
        namn = [p["namn"] for p in store.lista_pass(self.c, gid)]
        self.assertEqual(namn, ["Uppvärmning", "Final"])

    def test_startlista_kopplar_deltagare_till_gren(self):
        sam = store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m dam", "namn": "Anna Andersson", "klubb": "IF Göta",
             "handle": "@anna_a"},
            {"gren": "100 m dam", "namn": "Beata Berg", "klubb": "Malmö AI",
             "handle": ""},
        ], sport="friidrott")
        self.assertEqual(sam["deltagare_nya"], 2)
        gid = store.lista_discipliner(self.c, self.ev)[0]["id"]
        delt = store._pass_deltagare(self.c, gid)
        self.assertEqual([(d["namn"], d["handle"]) for d in delt],
                         [("Anna Andersson", "@anna_a"),
                          ("Beata Berg", None)])

    def test_startlista_skriver_inte_over_handle_du_redan_satt(self):
        lid = store.upsert_lag(self.c, "Anna Andersson", kind="individ",
                               sport="friidrott", instagram="@ratt_handle")
        store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m dam", "namn": "Anna Andersson", "klubb": "",
             "handle": ""}], sport="friidrott")
        self.assertEqual(store.hamta_lag(self.c, lid)["instagram"],
                         "@ratt_handle")

    def test_startlista_ateranvander_befintlig_utovare(self):
        store.upsert_lag(self.c, "Anna Andersson", kind="individ",
                         sport="friidrott")
        sam = store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m dam", "namn": "anna andersson", "klubb": "",
             "handle": ""}], sport="friidrott")
        self.assertEqual((sam["deltagare_nya"], sam["deltagare_befintliga"]),
                         (0, 1))

    def test_programmet_bar_deltagarna_efter_bada_importerna(self):
        """Tidsprogram och startlista kommer i två omgångar — programmet ska
        sy ihop dem."""
        store.importera_program(self.c, self.ev,
                                [self._rad("100 m dam", "Final", tid="19:10")])
        store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m dam", "namn": "Anna Andersson", "klubb": "IF Göta",
             "handle": "@anna_a"}], sport="friidrott")
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual(rad["namn"], "Final")
        self.assertEqual([d["handle"] for d in rad["deltagare"]], ["@anna_a"])


class TestForhandsgranskaImport(unittest.TestCase):
    """C10 — omimporten är idempotent men inte tyst: diffen visas först."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(
            self.c, "Friidrotts-SM 2026", sport="friidrott", typ="masterskap",
            fran="2026-07-24", till="2026-07-26")

    def _rad(self, gren, pas, datum="2026-07-24", tid="09:00"):
        return {"gren": gren, "pass": pas, "datum": datum, "tid": tid}

    def test_nytt_program_raknas_som_nya_pass_och_grenar(self):
        d = store.forhandsgranska_import(self.c, self.ev, [
            self._rad("100 m", "Försök"), self._rad("Höjd", "Kval")])
        self.assertEqual(d["pass_nya"], 2)
        self.assertEqual(d["grenar_nya"], ["100 m", "Höjd"])
        self.assertEqual(d["pass_uppdaterade"], 0)

    def test_flyttad_tid_visas_med_gammalt_och_nytt(self):
        store.importera_program(self.c, self.ev,
                                [self._rad("100 m", "Final", tid="19:10")])
        d = store.forhandsgranska_import(self.c, self.ev,
                                         [self._rad("100 m", "Final", tid="19:40")])
        self.assertEqual((d["pass_nya"], d["pass_uppdaterade"]), (0, 1))
        self.assertEqual(len(d["flyttningar"]), 1)
        self.assertIn("19:10", d["flyttningar"][0])
        self.assertIn("19:40", d["flyttningar"][0])

    def test_oforandrad_rad_raknas_som_oforandrad(self):
        store.importera_program(self.c, self.ev,
                                [self._rad("100 m", "Final", tid="19:10")])
        d = store.forhandsgranska_import(self.c, self.ev,
                                         [self._rad("100 m", "Final", tid="19:10")])
        self.assertEqual((d["pass_nya"], d["pass_uppdaterade"], d["pass_oforandrade"]),
                         (0, 0, 1))

    def test_forhandsgranskning_skriver_inte(self):
        """Read-only: inga grenar/pass får skapas av en torrkörning."""
        store.forhandsgranska_import(self.c, self.ev, [self._rad("100 m", "Final")])
        self.assertEqual(store.lista_discipliner(self.c, self.ev), [])

    def test_deltagardiff_ny_kontra_befintlig(self):
        store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m", "namn": "Anna Andersson", "klass": "dam"}],
            sport="friidrott")
        d = store.forhandsgranska_import(self.c, self.ev, [
            {"gren": "100 m", "namn": "Anna Andersson"},
            {"gren": "100 m", "namn": "Bea Berg"}], sort="startlista")
        self.assertEqual((d["deltagare_nya"], d["deltagare_befintliga"]), (1, 1))


class TestPubliceraMaterial(unittest.TestCase):
    def setUp(self):
        self.c = db.oppna(":memory:")
        self.mid = store.spara_match(self.c, {"lag_hemma": "A", "lag_borta": "B"})

    def test_skapa_uppdatera_via_id(self):
        mat_id = store.spara_publicera_material(
            self.c, kind="live", status="utkast", match_id=self.mid,
            match_namn="A – B", moment="Avspark", tema="Hav")
        rader = store.lista_publicera_material(self.c)
        self.assertEqual(len(rader), 1)
        self.assertEqual(rader[0]["status"], "utkast")

        store.spara_publicera_material(
            self.c, id=mat_id, kind="live", status="publicerad", match_id=self.mid,
            match_namn="A – B", moment="Avspark", tema="Hav")
        rader = store.lista_publicera_material(self.c)
        self.assertEqual(len(rader), 1)                     # samma rad, inte en ny
        self.assertEqual(rader[0]["status"], "publicerad")

    def test_channels_json_round_trip(self):
        store.spara_publicera_material(
            self.c, kind="some", status="utkast", channels=["story", "ig"],
            caption="Text med #tagg")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["channels"], ["story", "ig"])
        self.assertEqual(d["caption"], "Text med #tagg")

    def test_live_dropbox_foto_round_trip(self):
        # Reproducerar buggen: utan dropbox/foto kan "Fortsätt" inte återställa
        # förhandsvisningen (bara moment/tema), eftersom bildvalet gick förlorat.
        store.spara_publicera_material(
            self.c, kind="live", status="utkast", moment="Resultat", tema="Hav",
            dropbox="~/Dropbox/DPT/Live/test", foto="~/Dropbox/DPT/Live/test/bild_03.jpg")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["dropbox"], "~/Dropbox/DPT/Live/test")
        self.assertEqual(d["foto"], "~/Dropbox/DPT/Live/test/bild_03.jpg")

    def test_some_banor_json_round_trip(self):
        banor = {"story": {"mapp": "/bilder/a", "bilder": ["1.jpg", "2.jpg"]},
                 "ig": {"mapp": "/bilder/a", "bilder": ["1.jpg"]},
                 "fb": {"mapp": "", "bilder": []}}
        store.spara_publicera_material(
            self.c, kind="some", status="utkast", channels=["story", "ig"], banor=banor)
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["banor"], banor)

    def test_banor_null_utan_data(self):
        store.spara_publicera_material(self.c, kind="live", status="utkast")
        d = store.lista_publicera_material(self.c)[0]
        self.assertIsNone(d["banor"])
        self.assertIsNone(d["dropbox"])
        self.assertIsNone(d["foto"])

    def test_nyast_forst(self):
        store.spara_publicera_material(self.c, kind="live", status="utkast",
                                       uppdaterad="2026-06-30T10:00:00")
        store.spara_publicera_material(self.c, kind="some", status="utkast",
                                       uppdaterad="2026-06-30T11:00:00")
        rader = store.lista_publicera_material(self.c)
        self.assertEqual(rader[0]["kind"], "some")

    def test_ch_results_json_round_trip(self):
        store.spara_publicera_material(
            self.c, kind="some", status="delvis", channels=["story", "fb"],
            ch_results={"story": "ok", "fb": "fail"})
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["ch_results"], {"story": "ok", "fb": "fail"})

    def test_ch_results_tomt_utan_data(self):
        store.spara_publicera_material(self.c, kind="live", status="utkast")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["ch_results"], {})

    def test_delvis_status_tillaten(self):
        store.spara_publicera_material(self.c, kind="some", status="delvis")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["status"], "delvis")

    def test_utkast_loggar_ingen_historik(self):
        store.spara_publicera_material(self.c, kind="some", status="utkast")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(d["history"], [])

    def test_publicerad_och_delvis_loggar_historik(self):
        mid = store.spara_publicera_material(
            self.c, kind="some", status="delvis", historik_note="Facebook föll")
        store.spara_publicera_material(
            self.c, id=mid, kind="some", status="publicerad", historik_note="")
        d = store.lista_publicera_material(self.c)[0]
        self.assertEqual(len(d["history"]), 2)
        # nyast först
        self.assertEqual(d["history"][0]["status"], "publicerad")
        self.assertEqual(d["history"][1]["status"], "delvis")
        self.assertEqual(d["history"][1]["note"], "Facebook föll")

    def test_radera_material_tar_bort_historik(self):
        mid = store.spara_publicera_material(self.c, kind="some", status="publicerad")
        store.radera_publicera_material(self.c, mid)
        rader = self.c.execute(
            "SELECT * FROM publicera_material_historik WHERE material_id=?", (mid,)).fetchall()
        self.assertEqual(rader, [])

    def test_radera(self):
        mat_id = store.spara_publicera_material(self.c, kind="live", status="utkast")
        store.radera_publicera_material(self.c, mat_id)
        self.assertEqual(store.lista_publicera_material(self.c), [])


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


class TestTradsakerAnslutning(unittest.TestCase):
    """Regression: pywebviews brygga anropar Api-metoder från flera trådar
    samtidigt mot samma anslutning (check_same_thread=False). Utan
    SafeConnection-låset (se db.py) kraschar detta intermittent med
    sqlite3.InterfaceError/IndexError — bekräftat både i produktion (se
    projektminnet) och reproducerat rått i denna testfil innan låset
    lades till. Inga asserts på RESULTATET (racen är intermittent, ett
    lyckat enstaka test bevisar inget) — testet ska bara ALDRIG kasta."""

    def test_samtidiga_lasningar_kraschar_inte(self):
        c = db.oppna(":memory:", check_same_thread=False)
        for i in range(20):
            store.upsert_lag(c, f"Lag {i}")
        mids = [store.spara_match(c, {"lag_hemma": f"Lag {i}",
                                       "lag_borta": f"Lag {i + 1}", "sport": "fotboll"})
                for i in range(10)]

        errors = []

        def worker():
            try:
                for _ in range(50):
                    store.lista_lag(c)
                    for mid in mids[:5]:
                        store.hamta_match(c, mid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class TestV5Datamodell(unittest.TestCase):
    """V5-B (eventmodell-epiken): Liga + Event ersätter Tävling — speglingen
    från tavling (skrivytan under övergången), match-referenserna, individ-/
    kategori-registren och den härledda individhistoriken."""

    def setUp(self):
        self.c = db.oppna(":memory:")

    # ── schema + seed ────────────────────────────────────────────────────────
    def test_tabeller_och_kategoriseed(self):
        t = db.tabeller(self.c)
        for tabell in ("liga", "event", "individ", "event_deltagare", "kategori"):
            self.assertIn(tabell, t)
        manniskor = store.lista_kategorier(self.c, topp="manniskor")
        self.assertEqual([k["id"] for k in manniskor],
                         ["portratt", "brollop", "student", "foretag", "mode",
                          "ovrigt-manniskor"])
        self.assertEqual(manniskor[1]["gallringsprofil"], "brollop")
        self.assertEqual(manniskor[0]["some_moment"], ["tjuvkik", "leverans-klar"])

    # ── spegling tavling → liga/event ────────────────────────────────────────
    def test_liga_speglas_med_samma_id(self):
        tid = store.upsert_tavling(self.c, "OBOS Damallsvenskan",
                                   sport="fotboll", typ="liga", gren="dam")
        liga = store.hamta_liga(self.c, tid)
        self.assertEqual(liga["namn"], "OBOS Damallsvenskan")
        self.assertEqual(liga["gren"], "dam")
        self.assertIsNone(store.hamta_event(self.c, tid))

    def test_turnering_och_masterskap_blir_event(self):
        t1 = store.upsert_tavling(self.c, "Nordea Open", sport="tennis",
                                  typ="turnering")
        t2 = store.upsert_tavling(self.c, "Friidrotts-SM 2026",
                                  sport="friidrott", typ="masterskap",
                                  fran="2026-07-24", till="2026-07-26",
                                  ort="Uppsala")
        self.assertEqual(store.hamta_event(self.c, t1)["typ"], "turnering")
        e2 = store.hamta_event(self.c, t2)
        self.assertEqual(e2["typ"], "masterskap")
        self.assertEqual(e2["pagang_lage"], "auto")        # default (skiss 1h)
        self.assertIsNone(store.hamta_liga(self.c, t1))

    def test_typbyte_flyttar_mellan_registren(self):
        tid = store.upsert_tavling(self.c, "European League", sport="handboll",
                                   typ="liga")
        mid = store.spara_match(self.c, {"lag_hemma": "Sverige",
                                         "lag_borta": "Norge",
                                         "sport": "handboll",
                                         "tavling_id": tid})
        self.assertEqual(store.hamta_match(self.c, mid)["liga_id"], tid)
        store.upsert_tavling(self.c, "European League", id=tid,
                             sport="handboll", typ="turnering")
        self.assertIsNone(store.hamta_liga(self.c, tid))
        self.assertEqual(store.hamta_event(self.c, tid)["typ"], "turnering")
        m = store.hamta_match(self.c, mid)
        self.assertIsNone(m["liga_id"])
        self.assertEqual(m["event_id"], tid)

    def test_pagang_lage_overlever_spegling(self):
        tid = store.upsert_tavling(self.c, "EuroVolley", sport="volleyboll",
                                   typ="masterskap")
        self.assertTrue(store.satt_pagang_lage(self.c, tid, "heldag"))
        store.upsert_tavling(self.c, "EuroVolley", id=tid, sport="volleyboll",
                             typ="masterskap", ort="Göteborg")
        self.assertEqual(store.hamta_event(self.c, tid)["pagang_lage"], "heldag")
        self.assertEqual(store.hamta_event(self.c, tid)["ort"], "Göteborg")
        self.assertFalse(store.satt_pagang_lage(self.c, tid, "banzai"))

    def test_spara_match_satter_ratt_referens(self):
        liga = store.upsert_tavling(self.c, "Allsvenskan", sport="fotboll",
                                    typ="liga")
        ev = store.upsert_tavling(self.c, "Svenska Cupen", sport="fotboll",
                                  typ="turnering")
        m1 = store.spara_match(self.c, {"lag_hemma": "MFF", "lag_borta": "AIK",
                                        "sport": "fotboll", "tavling_id": liga})
        m2 = store.spara_match(self.c, {"lag_hemma": "MFF", "lag_borta": "BP",
                                        "sport": "fotboll", "tavling_id": ev})
        m3 = store.spara_match(self.c, {"lag_hemma": "MFF", "lag_borta": "HIF",
                                        "sport": "fotboll"})   # träningsmatch
        self.assertEqual(store.hamta_match(self.c, m1)["liga_id"], liga)
        self.assertIsNone(store.hamta_match(self.c, m1)["event_id"])
        self.assertEqual(store.hamta_match(self.c, m2)["event_id"], ev)
        self.assertIsNone(store.hamta_match(self.c, m3)["liga_id"])
        self.assertIsNone(store.hamta_match(self.c, m3)["event_id"])

    def test_radera_tavling_stadar_spegeln(self):
        tid = store.upsert_tavling(self.c, "Nordea Open", sport="tennis",
                                   typ="turnering")
        mid = store.spara_match(self.c, {"lag_hemma": "Borges",
                                         "lag_borta": "Darderi",
                                         "sport": "tennis", "tavling_id": tid})
        store.radera_tavling(self.c, tid)
        self.assertIsNone(store.hamta_event(self.c, tid))
        self.assertIsNone(store.hamta_match(self.c, mid)["event_id"])

    # ── individ + härledd historik ───────────────────────────────────────────
    def test_individ_crud_och_sportkrock(self):
        i1 = store.upsert_individ(self.c, "Armand Duplantis", sport="friidrott",
                                  klubb="Upsala IF", instagram="@mondo")
        self.assertEqual(store.hamta_individ(self.c, i1)["klubb"], "Upsala IF")
        # Uppdatering: None rör inte befintliga fält
        store.upsert_individ(self.c, "Armand Duplantis", id=i1,
                             instagram="@mondo_duplantis")
        i = store.hamta_individ(self.c, i1)
        self.assertEqual(i["instagram"], "@mondo_duplantis")
        self.assertEqual(i["klubb"], "Upsala IF")
        # Namnkrock med annan sport → suffixat id, originalet orört
        i2 = store.upsert_individ(self.c, "Armand Duplantis", sport="tennis")
        self.assertNotEqual(i1, i2)
        store.radera_individ(self.c, i2)
        self.assertIsNone(store.hamta_individ(self.c, i2))

    def test_event_deltagare_och_harledd_historik(self):
        sm = store.upsert_tavling(self.c, "Friidrotts-SM 2026",
                                  sport="friidrott", typ="masterskap",
                                  fran="2026-07-24")
        vc = store.upsert_tavling(self.c, "Skid-VC Falun 2026", sport="friidrott",
                                  typ="turnering", fran="2026-02-01")
        iid = store.upsert_individ(self.c, "E. Andersson", sport="friidrott")
        store.satt_event_deltagare(self.c, sm, iid, ["hojd", "langd"])
        store.satt_event_deltagare(self.c, vc, iid, ["sprint"])
        deltagare = store.lista_event_deltagare(self.c, sm)
        self.assertEqual(deltagare[0]["namn"], "E. Andersson")
        self.assertEqual(deltagare[0]["grenar"], ["hojd", "langd"])
        # Historiken härleds ur eventen — nyast först, aldrig lagrad på individen
        hist = store.individ_historik(self.c, iid)
        self.assertEqual([h["id"] for h in hist], [sm, vc])
        self.assertEqual(hist[0]["grenar"], ["hojd", "langd"])
        # Ny gren-lista ersätter (upsert), bortkoppling försvinner ur historiken
        store.satt_event_deltagare(self.c, sm, iid, ["hojd"])
        self.assertEqual(store.lista_event_deltagare(self.c, sm)[0]["grenar"],
                         ["hojd"])
        store.koppla_bort_event_deltagare(self.c, vc, iid)
        self.assertEqual([h["id"] for h in store.individ_historik(self.c, iid)],
                         [sm])

    def test_v32_alla_eventtyper_ryms_i_skrivytan(self):
        # v32: cup/varldscup/ovrigt ryms i tavling-CHECK:en och speglas med
        # bevarad typ till event-registret.
        for typ in ("cup", "varldscup", "ovrigt"):
            tid = store.upsert_tavling(self.c, f"Test {typ}", sport="fotboll",
                                       typ=typ)
            self.assertEqual(store.hamta_event(self.c, tid)["typ"], typ)

    def test_matchens_tva_dorrar(self):
        # V5-C §2: liga-dörren (tävlingsfältet) + event-dörren (event_id) —
        # båda kan vara satta samtidigt; tom sträng kopplar bort eventet.
        liga = store.upsert_tavling(self.c, "Allsvenskan", sport="fotboll",
                                    typ="liga")
        cup = store.upsert_tavling(self.c, "Svenska Cupen", sport="fotboll",
                                   typ="cup")
        mid = store.spara_match(self.c, {"lag_hemma": "MFF", "lag_borta": "AIK",
                                         "sport": "fotboll", "tavling_id": liga,
                                         "event_id": cup})
        m = store.hamta_match(self.c, mid)
        self.assertEqual(m["liga_id"], liga)      # ur tävlingsfältet
        self.assertEqual(m["event_id"], cup)      # ur event-dörren
        self.assertEqual(m["tavling_id"], liga)   # legacy-bäraren orörd
        # Spara om utan event_id-nyckel → dörren rörs inte
        store.spara_match(self.c, {"id": mid, "lag_hemma": "MFF",
                                   "lag_borta": "AIK", "sport": "fotboll",
                                   "tavling_id": liga})
        self.assertEqual(store.hamta_match(self.c, mid)["event_id"], cup)
        # Ligan sparas om (spegeln kör) → event-dörren överlever
        store.upsert_tavling(self.c, "Allsvenskan", id=liga, sport="fotboll",
                             typ="liga", ort="Sverige")
        self.assertEqual(store.hamta_match(self.c, mid)["event_id"], cup)
        # Tom sträng kopplar bort
        store.spara_match(self.c, {"id": mid, "lag_hemma": "MFF",
                                   "lag_borta": "AIK", "sport": "fotboll",
                                   "tavling_id": liga, "event_id": ""})
        m = store.hamta_match(self.c, mid)
        self.assertIsNone(m["event_id"])
        self.assertEqual(m["liga_id"], liga)

    # ── kategoriregistret ────────────────────────────────────────────────────
    def test_kategori_upsert_och_statisk_topp(self):
        kid = store.upsert_kategori(self.c, "Konsert", topp="manniskor",
                                    some_moment=["tjuvkik"])
        k = [x for x in store.lista_kategorier(self.c, "manniskor")
             if x["id"] == kid][0]
        self.assertEqual(k["some_moment"], ["tjuvkik"])
        self.assertIsNone(store.upsert_kategori(self.c, "X", topp="musik"))
        store.radera_kategori(self.c, kid)
        self.assertNotIn(kid, [x["id"] for x in
                               store.lista_kategorier(self.c)])

    # ── migrering v30 → v31 (backfill) ───────────────────────────────────────
    def test_migrering_backfillar_liga_event_och_matchrefs(self):
        import sqlite3
        raa = sqlite3.connect(":memory:")
        raa.row_factory = sqlite3.Row
        raa.executescript("""
        CREATE TABLE tavling (
          id TEXT PRIMARY KEY, typ TEXT NOT NULL, sport TEXT NOT NULL,
          gren TEXT, namn TEXT NOT NULL, hemsida TEXT, fran TEXT, till TEXT,
          ort TEXT, arena TEXT, logga TEXT, kalender INTEGER NOT NULL DEFAULT 0,
          press_email TEXT, ackr_dagar INTEGER,
          pagang_dold INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE matchen (
          id TEXT PRIMARY KEY, tavling_id TEXT, skapad TEXT NOT NULL);
        INSERT INTO tavling(id,typ,sport,namn) VALUES
          ('allsvenskan','liga','fotboll','Allsvenskan'),
          ('nordea-open','turnering','tennis','Nordea Open'),
          ('friidrotts-sm','masterskap','friidrott','Friidrotts-SM');
        INSERT INTO matchen(id,tavling_id,skapad) VALUES
          ('m1','allsvenskan','x'), ('m2','nordea-open','x'), ('m3',NULL,'x');
        PRAGMA user_version = 30;
        """)
        conn = db.SafeConnection(raa)
        db.init_db(conn)
        self.assertEqual(db.schemaversion(conn), db.SCHEMA_VERSION)
        self.assertEqual(store.hamta_liga(conn, "allsvenskan")["namn"],
                         "Allsvenskan")
        self.assertEqual(store.hamta_event(conn, "nordea-open")["typ"],
                         "turnering")
        self.assertEqual(store.hamta_event(conn, "friidrotts-sm")["typ"],
                         "masterskap")
        rader = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM matchen")}
        self.assertEqual(rader["m1"]["liga_id"], "allsvenskan")
        self.assertIsNone(rader["m1"]["event_id"])
        self.assertEqual(rader["m2"]["event_id"], "nordea-open")
        self.assertIsNone(rader["m3"]["liga_id"])
        # Kategori-seeden följer med migreringen
        self.assertEqual(len(store.lista_kategorier(conn, "manniskor")), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestGrenklassOchFaslosa(unittest.TestCase):
    """V5 §8 — klassen på grenen (v39) + poster utan fas-ord."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(
            self.c, "Friidrotts-SM 2026", sport="friidrott", typ="masterskap",
            fran="2026-07-24", till="2026-07-26")

    def test_samma_gren_i_bada_klasser_blir_skilda_grenar(self):
        """100 m dam och 100 m herr är två tävlingar, inte en."""
        store.importera_program(self.c, self.ev, [
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:25", "klass": "dam"},
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:35", "klass": "herr"},
        ])
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 2)
        rader = store.program(self.c, self.ev)[0]["rader"]
        self.assertEqual([(r["tid"], r["gren_kant"]) for r in rader],
                         [("20:25", "dam"), ("20:35", "herr")])

    def test_grenens_klass_vinner_over_deltagarnas(self):
        store.importera_program(self.c, self.ev, [
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:25", "klass": "dam"}])
        gid = store.lista_discipliner(self.c, self.ev)[0]["id"]
        lid = store.upsert_lag(self.c, "Fel klass", kind="individ",
                               sport="friidrott", gren="herr")
        store.koppla_disciplin_deltagare(self.c, gid, lid)
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual(rad["gren_kant"], "dam")

    def test_utan_klass_harleds_markoren_ur_deltagarna_som_forr(self):
        gid = store.upsert_disciplin(self.c, self.ev, "Höjd")
        store.upsert_pass(self.c, gid, "Final", "2026-07-25", tid="19:10")
        lid = store.upsert_lag(self.c, "Alva", kind="individ",
                               sport="friidrott", gren="dam")
        store.koppla_disciplin_deltagare(self.c, gid, lid)
        self.assertEqual(store.program(self.c, self.ev)[0]["rader"][0]["gren_kant"],
                         "dam")

    def test_befintlig_gren_utan_klass_tas_over_vid_import(self):
        """Grenar Stig lagt in för hand ska inte dubbleras av importen."""
        store.upsert_disciplin(self.c, self.ev, "Kula")
        sam = store.importera_program(self.c, self.ev, [
            {"gren": "Kula", "pass": "Final", "datum": "2026-07-24",
             "tid": "18:30", "klass": "herr"}])
        self.assertEqual(sam["grenar_skapade"], [])
        grenar = store.lista_discipliner(self.c, self.ev)
        self.assertEqual(len(grenar), 1)
        self.assertEqual(grenar[0]["gren"], "herr")

    def test_post_utan_fasord_blir_sitt_eget_pass(self):
        """'Invigning' och 'Tiokamp 100m' saknar kval/final men är
        deltillfällen — de ska in i programmet, inte tappas."""
        sam = store.importera_program(self.c, self.ev, [
            {"gren": "Invigning", "pass": "", "datum": "2026-07-24",
             "tid": "16:30", "klass": ""},
            {"gren": "Tiokamp 100m", "pass": "", "datum": "2026-07-24",
             "tid": "12:45", "klass": "herr"},
        ])
        self.assertEqual(sam["pass_nya"], 2)
        rader = store.program(self.c, self.ev)[0]["rader"]
        self.assertEqual([(r["tid"], r["gren"], r["namn"]) for r in rader],
                         [("12:45", "Tiokamp 100m", "Tiokamp 100m"),
                          ("16:30", "Invigning", "Invigning")])

    def test_tvetydig_gren_flaggas_i_stallet_for_att_dubbleras(self):
        """När '100m' finns som både dam och herr får en klasslös startlista
        inte skapa en tredje klasslös gren — och inte gissa klass åt en
        deltagare. Hittat vid S4-arbetet."""
        store.importera_program(self.c, self.ev, [
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:25", "klass": "dam"},
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:35", "klass": "herr"},
        ])
        sam = store.importera_startlista(self.c, self.ev, [
            {"gren": "100m", "namn": "Anna", "klubb": "", "handle": ""}],
            sport="friidrott")
        self.assertEqual(sam["deltagare_nya"], 0)
        self.assertEqual(len(sam["oklara"]), 1)
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 2)

    def test_entydig_gren_behover_ingen_klass(self):
        store.importera_program(self.c, self.ev, [
            {"gren": "Slägga", "pass": "Final", "datum": "2026-07-25",
             "tid": "17:00", "klass": "herr"}])
        sam = store.importera_startlista(self.c, self.ev, [
            {"gren": "Slägga", "namn": "Bo", "klubb": "", "handle": "@bo"}],
            sport="friidrott")
        self.assertEqual(sam["deltagare_nya"], 1)
        self.assertEqual(sam["oklara"], [])

    def test_handle_kan_sattas_i_efterhand(self):
        """Stigs krav 19/7: SoMe-konton ska gå att lägga till senare i flödet,
        på deltagare som saknade dem när startlistan lästes in."""
        store.importera_startlista(self.c, self.ev, [
            {"gren": "Kula", "namn": "Bo Berg", "klubb": "IF Göta",
             "handle": ""}], sport="friidrott")
        gid = store.lista_discipliner(self.c, self.ev)[0]["id"]
        lid = store._pass_deltagare(self.c, gid)[0]["id"]
        self.assertIsNone(store._pass_deltagare(self.c, gid)[0]["handle"])

        self.assertTrue(store.satt_deltagare_handle(self.c, lid, "bo_berg"))
        self.assertEqual(store._pass_deltagare(self.c, gid)[0]["handle"],
                         "@bo_berg")   # snabel-a läggs till

    def test_handle_skrivs_pa_utovaren(self):
        """v40: Utövare = ETT register (lag kind='individ'). Handle skrivs där —
        ingen spegling till ett separat individregister som kan driva isär."""
        lid = store.upsert_lag(self.c, "Bo Berg", kind="individ",
                               sport="friidrott")
        store.satt_deltagare_handle(self.c, lid, "@bo")
        self.assertEqual(
            self.c.execute("SELECT instagram FROM lag WHERE id=?", (lid,)).fetchone()[0],
            "@bo")

    def test_tom_handle_rensar(self):
        lid = store.upsert_lag(self.c, "Bo", kind="individ", sport="friidrott",
                               instagram="@fel")
        store.satt_deltagare_handle(self.c, lid, "")
        self.assertIsNone(
            self.c.execute("SELECT instagram FROM lag WHERE id=?", (lid,)).fetchone()[0])

    def test_okand_deltagare_ger_falskt(self):
        self.assertFalse(store.satt_deltagare_handle(self.c, "finns-inte", "@x"))

    def test_mellanslag_gor_inte_100m_till_tva_grenar(self):
        """Stigs fynd 19/7: PDF:en skriver '100m', startlistesidan '100 m' —
        samma final hamnade två gånger med var sin preliminära tid."""
        store.importera_program(self.c, self.ev, [
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:25", "klass": "dam"}])
        sam = store.importera_program(self.c, self.ev, [
            {"gren": "100 m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:35", "klass": "dam"}])
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 1)
        self.assertEqual((sam["pass_nya"], sam["pass_uppdaterade"]), (0, 1))
        rad = store.program(self.c, self.ev)[0]["rader"][0]
        self.assertEqual(rad["tid"], "20:35")      # färskare källan vinner

    def test_startlistan_satter_klass_pa_deltagaren(self):
        """Klassen ska hamna på INDIVIDEN också — overlayns kantfärg följer
        henne, och utan den blir hon klasslös i utövarregistret."""
        store.importera_startlista(self.c, self.ev, [
            {"gren": "100 m", "klass": "dam", "namn": "Esther Sahlqvist",
             "klubb": "Hammarby IF", "handle": ""}], sport="friidrott")
        lag = self.c.execute(
            "SELECT gren FROM lag WHERE namn='Esther Sahlqvist'").fetchone()
        self.assertEqual(lag["gren"], "dam")

    def test_stad_slar_ihop_befintliga_dubbletter(self):
        a = store.upsert_disciplin(self.c, self.ev, "100m", gren="dam")
        b = store.upsert_disciplin(self.c, self.ev, "100 m", gren="dam")
        store.upsert_pass(self.c, a, "Försök", "2026-07-24", tid="18:20")
        store.upsert_pass(self.c, a, "Final", "2026-07-24", tid="20:25")
        store.upsert_pass(self.c, b, "Final", "2026-07-24", tid="20:35")
        lid = store.upsert_lag(self.c, "Esther", kind="individ", sport="friidrott")
        store.koppla_disciplin_deltagare(self.c, b, lid)

        hop = store.stad_grendubbletter(self.c, self.ev)
        self.assertEqual(len(hop), 1)
        grenar = store.lista_discipliner(self.c, self.ev)
        self.assertEqual(len(grenar), 1)
        self.assertEqual(grenar[0]["namn"], "100 m")     # flest deltagare bevaras
        pas = {p["namn"]: p["tid"] for p in store.lista_pass(self.c, grenar[0]["id"])}
        self.assertEqual(pas, {"Försök": "18:20", "Final": "20:35"})
        self.assertEqual(len(grenar[0]["deltagare"]), 1)

    def test_stad_ror_inte_olika_klasser(self):
        store.upsert_disciplin(self.c, self.ev, "100 m", gren="dam")
        store.upsert_disciplin(self.c, self.ev, "100m", gren="herr")
        self.assertEqual(store.stad_grendubbletter(self.c, self.ev), [])
        self.assertEqual(len(store.lista_discipliner(self.c, self.ev)), 2)

    def test_backfill_satter_klass_ur_grenen(self):
        gid = store.upsert_disciplin(self.c, self.ev, "100 m", gren="dam")
        lid = store.upsert_lag(self.c, "Esther", kind="individ", sport="friidrott")
        store.koppla_disciplin_deltagare(self.c, gid, lid)
        self.assertEqual(store.backfilla_deltagarklass(self.c, self.ev), 1)
        self.assertEqual(store.hamta_lag(self.c, lid)["gren"], "dam")

    def test_backfill_gissar_inte_vid_tvetydighet(self):
        d = store.upsert_disciplin(self.c, self.ev, "Höjd", gren="dam")
        h = store.upsert_disciplin(self.c, self.ev, "Längd", gren="herr")
        lid = store.upsert_lag(self.c, "Oklar", kind="individ", sport="friidrott")
        store.koppla_disciplin_deltagare(self.c, d, lid)
        store.koppla_disciplin_deltagare(self.c, h, lid)
        self.assertEqual(store.backfilla_deltagarklass(self.c, self.ev), 0)
        self.assertIsNone(store.hamta_lag(self.c, lid)["gren"])

    def test_farskare_kallan_rattar_stavningen(self):
        """PDF:en gav '100m', startlistan ger '100 m' — samma gren, och namnet
        ska följa den nyare källan så dam och herr inte stavas olika."""
        store.importera_program(self.c, self.ev, [
            {"gren": "100m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:35", "klass": "herr"}])
        store.importera_program(self.c, self.ev, [
            {"gren": "100 m", "pass": "Final", "datum": "2026-07-24",
             "tid": "20:35", "klass": "herr"}])
        grenar = store.lista_discipliner(self.c, self.ev)
        self.assertEqual([g["namn"] for g in grenar], ["100 m"])

    def test_stavningsrattning_ar_inte_ett_namnbyte(self):
        """Bara när nyckeln redan är lika — 'Höjd' blir aldrig 'Längd'."""
        gid = store.upsert_disciplin(self.c, self.ev, "Höjd", gren="dam")
        store.importera_program(self.c, self.ev, [
            {"gren": "Längd", "pass": "Final", "datum": "2026-07-24",
             "tid": "19:00", "klass": "dam"}])
        namn = sorted(g["namn"] for g in store.lista_discipliner(self.c, self.ev))
        self.assertEqual(namn, ["Höjd", "Längd"])


class TestUtovareMigrering(unittest.TestCase):
    """v40 (D11b §2): individ + lag(kind='individ') → ETT register i lag."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(self.c, "SM 2026", sport="friidrott",
                                       typ="masterskap", fran="2026-07-24",
                                       till="2026-07-26")
        # Återskapa event_deltagare i sin v31-form (individ_id → individ) så
        # migreringen har något gammalt att bygga om.
        self.c.execute("DROP TABLE event_deltagare")
        self.c.execute("""CREATE TABLE event_deltagare (
          event_id   TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
          individ_id TEXT NOT NULL REFERENCES individ(id) ON DELETE CASCADE,
          grenar     TEXT, PRIMARY KEY (event_id, individ_id))""")

    def _koppla_gammal(self, individ_id):
        self.c.execute(
            "INSERT INTO event_deltagare(event_id,individ_id,grenar) "
            "VALUES(?,?, '[]')", (self.ev, individ_id))

    def test_individ_utan_lagtvilling_speglas_in_i_lag(self):
        self.c.execute("INSERT INTO individ(id,namn,sport,klubb) "
                       "VALUES('i1','Armand Duplantis','friidrott','Upsala IF')")
        self._koppla_gammal("i1")
        db._migrera_utovare(self.c)
        lag = self.c.execute("SELECT * FROM lag WHERE id='i1'").fetchone()
        self.assertEqual((lag["kind"], lag["namn"], lag["klubb"]),
                         ("individ", "Armand Duplantis", "Upsala IF"))
        self.assertTrue(db._har_kolumn(self.c, "event_deltagare", "lag_id"))
        self.assertEqual(store.individ_historik(self.c, "i1")[0]["id"], self.ev)

    def test_individ_med_lagtvilling_dedupas_pa_namn(self):
        lid = store.upsert_lag(self.c, "Bea Berg", kind="individ",
                               sport="friidrott")
        self.c.execute("INSERT INTO individ(id,namn,sport,instagram) "
                       "VALUES('i2','Bea Berg','friidrott','@bea')")
        self._koppla_gammal("i2")
        db._migrera_utovare(self.c)
        antal = self.c.execute(
            "SELECT COUNT(*) FROM lag WHERE lower(namn)='bea berg'").fetchone()[0]
        self.assertEqual(antal, 1)                    # ingen dubblett skapades
        rad = self.c.execute("SELECT lag_id FROM event_deltagare").fetchone()
        self.assertEqual(rad["lag_id"], lid)          # pekar på lag-tvillingen
        self.assertEqual(store.hamta_individ(self.c, lid)["instagram"], "@bea")

    def test_migrering_ar_idempotent(self):
        self.c.execute("INSERT INTO individ(id,namn,sport) "
                       "VALUES('i3','Cilla Cast','friidrott')")
        self._koppla_gammal("i3")
        db._migrera_utovare(self.c)
        db._migrera_utovare(self.c)                    # andra körningen = no-op
        self.assertTrue(db._har_kolumn(self.c, "event_deltagare", "lag_id"))
        self.assertEqual(
            self.c.execute("SELECT COUNT(*) FROM event_deltagare").fetchone()[0], 1)


class TestUtovareStarter(unittest.TestCase):
    """D11b §2 — utövarsidans härledda starter (pass, aldrig lagrade)."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(self.c, "SM 2026", sport="friidrott",
                                       typ="masterskap", fran="2026-07-24",
                                       till="2026-07-26")
        self.gren = store.upsert_disciplin(self.c, self.ev, "100 m", gren="dam")
        self.lid = store.upsert_lag(self.c, "Anna Andersson", kind="individ",
                                    sport="friidrott")
        store.koppla_disciplin_deltagare(self.c, self.gren, self.lid)

    def test_starter_harleds_ur_grenkopplingen_med_tavlingskontext(self):
        store.upsert_pass(self.c, self.gren, "Försök", "2026-07-24", tid="09:00")
        store.upsert_pass(self.c, self.gren, "Final", "2026-07-25", tid="19:10")
        s = store.utovare_starter(self.c, self.lid)
        self.assertEqual([(x["pass"], x["klass"], x["event_namn"]) for x in s],
                         [("Försök", "dam", "SM 2026"),
                          ("Final", "dam", "SM 2026")])

    def test_okopplad_utovare_har_inga_starter(self):
        ovrig = store.upsert_lag(self.c, "Bea Berg", kind="individ")
        self.assertEqual(store.utovare_starter(self.c, ovrig), [])


class TestUtovareGrenar(unittest.TestCase):
    """C12/M-2 — "Tävlar i": härledd ur disciplin_deltagare, aldrig lagrad."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(self.c, "SM 2026", sport="friidrott",
                                       typ="masterskap", fran="2026-07-24",
                                       till="2026-07-26")
        # Grenen bär sin EGEN klass — 100 m dam och 100 m herr är två grenar.
        self.dam = store.upsert_disciplin(self.c, self.ev, "100 m", gren="dam")
        self.herr = store.upsert_disciplin(self.c, self.ev, "200 m", gren="herr")
        self.lid = store.upsert_lag(self.c, "Anna Andersson", kind="individ",
                                    sport="friidrott")
        store.koppla_disciplin_deltagare(self.c, self.dam, self.lid)

    def test_raden_bar_grenens_egen_klass_och_tavlingen(self):
        store.upsert_pass(self.c, self.dam, "Final", "2026-07-25", tid="20:25")
        g = store.utovare_grenar(self.c, self.lid)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["gren"], "100 m")
        self.assertEqual(g[0]["klass"], "dam")           # GRENENS klass
        self.assertEqual(g[0]["tavling"], "SM 2026")     # "Del av {tävling}"
        self.assertEqual([(p["namn"], p["tid"]) for p in g[0]["pass"]],
                         [("Final", "20:25")])

    def test_personens_klass_smittar_aldrig_grenraden(self):
        # Utövaren är dam men kopplas (av misstag eller för att hen tävlar i
        # herrklass) till en herr-gren: raden ska bära GRENENS klass.
        store.upsert_lag(self.c, "Anna Andersson", id=self.lid, kind="individ",
                         gren="dam")
        store.koppla_disciplin_deltagare(self.c, self.herr, self.lid)
        klasser = {g["gren"]: g["klass"]
                   for g in store.utovare_grenar(self.c, self.lid)}
        self.assertEqual(klasser, {"100 m": "dam", "200 m": "herr"})

    def test_kopplingen_ar_enda_sanningen_och_gar_att_ta_bort(self):
        store.koppla_disciplin_deltagare(self.c, self.dam, self.lid, pa=False)
        self.assertEqual(store.utovare_grenar(self.c, self.lid), [])
        self.assertEqual(store.utovare_starter(self.c, self.lid), [])

    def test_tavlar_i_och_kommande_starter_delar_harledning(self):
        """Låst invariant: två vyer, en härledning — aldrig var sin."""
        store.upsert_pass(self.c, self.dam, "Försök", "2026-07-24", tid="09:00")
        store.koppla_disciplin_deltagare(self.c, self.herr, self.lid)
        store.upsert_pass(self.c, self.herr, "Final", "2026-07-26", tid="18:00")
        ur_grenar = {g["gren"] for g in store.utovare_grenar(self.c, self.lid)}
        ur_starter = {s["gren"] for s in store.utovare_starter(self.c, self.lid)}
        self.assertEqual(ur_grenar, ur_starter)

    def test_kandidater_utelamnar_redan_kopplade(self):
        k = store.gren_kandidater(self.c, self.lid)
        self.assertEqual([r["gren"] for r in k], ["200 m"])
        self.assertEqual(k[0]["tavling"], "SM 2026")
        # Utan utövare: alla grenar är kandidater.
        self.assertEqual(len(store.gren_kandidater(self.c)), 2)

    def test_kandidater_filtrerar_pa_sport(self):
        cup = store.upsert_tavling(self.c, "Vinter-cup", sport="tennis",
                                   typ="turnering")
        store.upsert_disciplin(self.c, cup, "Singel")
        grenar = {r["gren"] for r in
                  store.gren_kandidater(self.c, self.lid, sport="friidrott")}
        self.assertEqual(grenar, {"200 m"})


class TestSokGlobalt(unittest.TestCase):
    """D11b §4 — ⌘K-index över utövare · tävling · fotojobb · gren."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(self.c, "Friidrotts-SM 2026",
                                       sport="friidrott", typ="masterskap")
        store.upsert_disciplin(self.c, self.ev, "100 meter", gren="dam")
        store.upsert_lag(self.c, "Armand Duplantis", kind="individ",
                         sport="friidrott")
        store.skapa_fotojobb_utkast(self.c, tavling_id=self.ev,
                                    title="SM friidrott lördag",
                                    start_at="2026-07-25", end_at="2026-07-25")

    def test_hittar_over_flera_typer(self):
        typer = {t["typ"] for t in store.sok_globalt(self.c, "SM")}
        self.assertIn("tavling", typer)     # 'Friidrotts-SM 2026'
        self.assertIn("fotojobb", typer)    # 'SM friidrott lördag'

    def test_utovare_matchas(self):
        self.assertTrue(any(t["typ"] == "utovare"
                            for t in store.sok_globalt(self.c, "duplantis")))

    def test_gren_traff_oppnar_sin_tavling(self):
        g = [t for t in store.sok_globalt(self.c, "100 met") if t["typ"] == "gren"]
        self.assertEqual(g[0]["id"], self.ev)

    def test_for_kort_query_ger_inget(self):
        self.assertEqual(store.sok_globalt(self.c, "s"), [])


class TestStadDeltagareFelKlass(unittest.TestCase):
    """Stigs fynd 19/7 — dam-deltagare felkopplad till herr-gren flyttas rätt."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.ev = store.upsert_tavling(self.c, "SM 2026", sport="friidrott",
                                       typ="masterskap")

    def _delt(self, disc):
        return {r["lag_id"] for r in self.c.execute(
            "SELECT lag_id FROM disciplin_deltagare WHERE disciplin_id=?", (disc,))}

    def test_flyttar_till_ratt_klassgren(self):
        herr = store.upsert_disciplin(self.c, self.ev, "Diskus", gren="herr")
        dam = store.upsert_disciplin(self.c, self.ev, "Diskus", gren="dam")
        d = store.upsert_lag(self.c, "Daniel Ståhl", kind="individ",
                             sport="friidrott", gren="herr")
        v = store.upsert_lag(self.c, "Vanessa Kamga", kind="individ",
                             sport="friidrott", gren="dam")
        store.koppla_disciplin_deltagare(self.c, herr, d)
        store.koppla_disciplin_deltagare(self.c, herr, v)   # fel: dam på herr
        self.assertEqual(store.stad_deltagare_fel_klass(self.c, self.ev), 1)
        self.assertEqual(self._delt(herr), {d})             # Daniel kvar
        self.assertEqual(self._delt(dam), {v})              # Vanessa flyttad

    def test_ror_inte_utan_syskongren(self):
        herr = store.upsert_disciplin(self.c, self.ev, "Diskus", gren="herr")
        v = store.upsert_lag(self.c, "Vanessa", kind="individ", gren="dam")
        store.koppla_disciplin_deltagare(self.c, herr, v)
        self.assertEqual(store.stad_deltagare_fel_klass(self.c, self.ev), 0)
        self.assertEqual(self._delt(herr), {v})             # ingen dam-gren → lämnas

    def test_ror_inte_deltagare_utan_klass(self):
        herr = store.upsert_disciplin(self.c, self.ev, "Diskus", gren="herr")
        store.upsert_disciplin(self.c, self.ev, "Diskus", gren="dam")
        x = store.upsert_lag(self.c, "Okänd", kind="individ")   # ingen klass
        store.koppla_disciplin_deltagare(self.c, herr, x)
        self.assertEqual(store.stad_deltagare_fel_klass(self.c, self.ev), 0)


class TestFotojobbTavling(unittest.TestCase):
    """M-11: explicit, beständig koppling fotojobb→tävling + auto-matchningen."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.sm = store.upsert_tavling(
            self.c, "Friidrotts-SM 2026", sport="friidrott", typ="masterskap",
            fran="2026-07-24", till="2026-07-26")

    def test_lankning_rundresa_och_bortkoppling(self):
        store.lanka_fotojobb_tavling(self.c, "jobb1", self.sm)
        self.assertEqual(store.tavlingref_for_fotojobb(self.c, ["jobb1"]),
                         {"jobb1": self.sm})
        # Beständig — inte beroende av namnet. Koppla bort med falsy värde.
        store.lanka_fotojobb_tavling(self.c, "jobb1", "")
        self.assertEqual(store.tavlingref_for_fotojobb(self.c, ["jobb1"]), {})

    def test_tavlingref_batch_hoppar_over_okopplade(self):
        store.lanka_fotojobb_tavling(self.c, "a", self.sm)
        ref = store.tavlingref_for_fotojobb(self.c, ["a", "b", None])
        self.assertEqual(ref, {"a": self.sm})

    def test_matcha_namn_i_titel_och_datum_i_period(self):
        tv = store.lista_tavlingar(self.c)
        self.assertEqual(
            store.matcha_tavling("Friidrotts-SM 2026", "2026-07-24T08:00:00", tv),
            self.sm)

    def test_matcha_utanfor_perioden_ger_none(self):
        tv = store.lista_tavlingar(self.c)
        self.assertIsNone(
            store.matcha_tavling("Friidrotts-SM 2026", "2026-08-01T08:00:00", tv))

    def test_matcha_okant_namn_ger_none(self):
        tv = store.lista_tavlingar(self.c)
        self.assertIsNone(store.matcha_tavling("Bröllop i Lund", "2026-07-24", tv))
        self.assertIsNone(store.matcha_tavling("", "2026-07-24", tv))

    def test_matcha_utan_period_faller_tillbaka_pa_namnet(self):
        cup = store.upsert_tavling(self.c, "Skåne Cup", sport="fotboll", typ="cup")
        tv = store.lista_tavlingar(self.c)
        self.assertEqual(store.matcha_tavling("Skåne Cup", "2026-05-01", tv), cup)

    def test_bortkoppling_overlever_men_kaskaderar_med_tavlingen(self):
        store.lanka_fotojobb_tavling(self.c, "jobb1", self.sm)
        self.c.execute("DELETE FROM tavling WHERE id=?", (self.sm,))
        self.c.commit()
        # ON DELETE CASCADE: kopplingen städas när tävlingen försvinner.
        self.assertEqual(store.tavlingref_for_fotojobb(self.c, ["jobb1"]), {})


class TestPlatsRegister(unittest.TestCase):
    """v44: platsregister (arenanamn → koordinat) — DPT2 äger koordinaterna."""

    def setUp(self):
        self.c = db.oppna(":memory:")

    def test_upsert_och_uppslag(self):
        store.upsert_plats(self.c, "Eleda Stadion", 55.6031, 12.9993)
        self.assertEqual(store.koordinat_for_plats(self.c, "Eleda Stadion"),
                         (55.6031, 12.9993))

    def test_delstrangs_och_diakritmatch_som_ios(self):
        store.upsert_plats(self.c, "Eleda Stadion", 55.6031, 12.9993)
        # Paketets arena kan vara "Eleda Stadion, Malmö" → delsträng.
        self.assertIsNotNone(store.koordinat_for_plats(self.c, "Eleda Stadion, Malmö"))
        store.upsert_plats(self.c, "Båstad", 56.426, 12.852)
        # Diakriter viks (bastad ↔ Båstad), som iOS ArenaKoordinat.
        self.assertEqual(store.koordinat_for_plats(self.c, "Bastad Arena")[0], 56.426)

    def test_upsert_uppdaterar_och_radering(self):
        store.upsert_plats(self.c, "Arena X", 1.0, 2.0)
        store.upsert_plats(self.c, "Arena X", 3.0, 4.0)   # samma namn → uppdatera
        self.assertEqual(store.koordinat_for_plats(self.c, "Arena X"), (3.0, 4.0))
        self.assertEqual(len(store.lista_platser(self.c)), 1)
        store.radera_plats(self.c, "Arena X")
        self.assertEqual(store.lista_platser(self.c), [])

    def test_okant_eller_tomt_ger_none(self):
        self.assertIsNone(store.koordinat_for_plats(self.c, "Finns ej"))
        self.assertIsNone(store.koordinat_for_plats(self.c, ""))
        self.assertIsNone(store.koordinat_for_plats(self.c, None))


class TestUtovareResultat(unittest.TestCase):
    """M-6: resultat/placering/medalj per deltagare + härledd historik/persrekord."""

    def setUp(self):
        self.c = db.oppna(":memory:")
        self.sm = store.upsert_tavling(self.c, "Friidrotts-SM 2026", sport="friidrott",
                                       typ="masterskap", fran="2026-07-24",
                                       till="2026-07-26", ort="Uppsala")
        self.gm = store.upsert_tavling(self.c, "GM 2025", sport="friidrott",
                                       typ="masterskap", fran="2025-08-01",
                                       till="2025-08-02", ort="Malmö")
        self.langd_sm = store.upsert_disciplin(self.c, self.sm, "Längd", typ="hoppkast")
        self.langd_gm = store.upsert_disciplin(self.c, self.gm, "Längd", typ="hoppkast")
        self.a = store.upsert_lag(self.c, "Khaddi Sagnia", kind="individ", gren="dam")
        self.b = store.upsert_lag(self.c, "Tilde X", kind="individ", gren="dam")

    def test_satt_och_las_resultat(self):
        store.satt_disciplin_resultat(self.c, self.langd_sm, self.a,
                                      resultat="6.72", placering=1, medalj="guld")
        d = store.disciplin_deltagare(self.c, self.langd_sm)
        self.assertEqual((d[0]["namn"], d[0]["resultat"], d[0]["placering"],
                          d[0]["medalj"]), ("Khaddi Sagnia", "6.72", 1, "guld"))

    def test_listan_rankas_pa_placering_nulls_sist(self):
        store.koppla_disciplin_deltagare(self.c, self.langd_sm, self.a)   # oplacerad
        store.satt_disciplin_resultat(self.c, self.langd_sm, self.b,
                                      resultat="6.90", placering=1)
        namn = [p["namn"] for p in store.disciplin_deltagare(self.c, self.langd_sm)]
        self.assertEqual(namn, ["Tilde X", "Khaddi Sagnia"])   # placering 1 först

    def test_historik_bar_tavlingskontext_nyast_forst(self):
        store.satt_disciplin_resultat(self.c, self.langd_sm, self.a,
                                      resultat="6.72", placering=1, medalj="guld")
        store.satt_disciplin_resultat(self.c, self.langd_gm, self.a,
                                      resultat="6.55", placering=3, medalj="brons")
        h = store.utovare_historik(self.c, self.a)
        self.assertEqual([x["tavling"] for x in h], ["Friidrotts-SM 2026", "GM 2025"])
        self.assertEqual((h[0]["ort"], h[0]["medalj"]), ("Uppsala", "guld"))

    def test_persrekord_valjer_basta_placering_per_gren(self):
        store.satt_disciplin_resultat(self.c, self.langd_sm, self.a,
                                      resultat="6.72", placering=1)
        store.satt_disciplin_resultat(self.c, self.langd_gm, self.a,
                                      resultat="6.55", placering=3)
        pr = store.utovare_persrekord(self.c, self.a)
        self.assertEqual(len(pr), 1)                 # en rad per grennamn
        self.assertEqual((pr[0]["placering"], pr[0]["resultat"]), (1, "6.72"))

    def test_medalj_check_avvisar_ogiltig(self):
        with self.assertRaises(Exception):
            store.satt_disciplin_resultat(self.c, self.langd_sm, self.a, medalj="trä")


class TestImporteraSpelschema(unittest.TestCase):
    """F18-3: importera spelschema-JSON → liga + lag + matcher via spara_match."""

    FIXTURES = [
        {"league": "Handbollsligan", "home_team": "HK Malmö", "away_team": "LUGI HF",
         "date": "2026-10-22", "kickoff": "19:00"},
        {"league": "Handbollsligan", "home_team": "HK Malmö", "away_team": "Amo HK",
         "date": "2027-02-07", "kickoff": None},              # null kickoff
        {"league": "Handbollsligan", "home_team": "LUGI HF", "away_team": "HK Malmö",
         "date": "2026-12-26", "kickoff": "15:00"},           # omvänd match
        {"league": "Handbollsligan", "home_team": "", "away_team": "X",
         "date": "2026-10-22", "kickoff": None},              # ofullständig → hoppas
    ]

    def setUp(self):
        self.c = db.oppna(":memory:")

    def _lag(self):
        return {r["namn"] for r in self.c.execute("SELECT namn FROM lag")}

    def test_import_skapar_liga_lag_matcher(self):
        r = store.importera_spelschema(self.c, self.FIXTURES, sport="handboll")
        self.assertEqual(r, {"skapade": 3, "uppdaterade": 0, "hoppade": 1})
        ligor = [t for t in store.lista_tavlingar(self.c) if t["namn"] == "Handbollsligan"]
        self.assertEqual(len(ligor), 1)                       # liga inte dubblerad
        self.assertEqual((ligor[0]["typ"], ligor[0]["sport"]), ("liga", "handboll"))
        self.assertTrue({"HK Malmö", "LUGI HF", "Amo HK"} <= self._lag())

    def test_null_kickoff_ger_tom_tid_och_handboll(self):
        store.importera_spelschema(self.c, self.FIXTURES, sport="handboll")
        m = self.c.execute(
            "SELECT tid, sport FROM matchen WHERE datum='2027-02-07'").fetchone()
        self.assertEqual((m["tid"], m["sport"]), (None, "handboll"))  # tom tid → NULL

    def test_omimport_ar_idempotent(self):
        store.importera_spelschema(self.c, self.FIXTURES, sport="handboll")
        r2 = store.importera_spelschema(self.c, self.FIXTURES, sport="handboll")
        self.assertEqual(r2, {"skapade": 0, "uppdaterade": 3, "hoppade": 1})
        n = self.c.execute("SELECT COUNT(*) FROM matchen").fetchone()[0]
        self.assertEqual(n, 3)                                # inga dubbletter

    def test_sport_ur_fixture_engelska_mappas(self):
        # Volleyboll-filerna bär "sport": "volleyball" per fixture → mappas till
        # schemats "volleyboll"; inget sport-argument behövs.
        vb = [{"league": "Elitserien Damer", "sport": "volleyball",
               "home_team": "Lunds VK", "away_team": "Göteborg VBK",
               "date": "2026-11-21", "kickoff": "16:00"}]
        r = store.importera_spelschema(self.c, vb)   # inget sport-arg
        self.assertEqual(r["skapade"], 1)
        m = self.c.execute("SELECT sport FROM matchen").fetchone()
        self.assertEqual(m["sport"], "volleyboll")

    def test_otolkbar_sport_hoppas(self):
        bad = [{"league": "X", "sport": "curling", "home_team": "A",
                "away_team": "B", "date": "2026-11-21"}]
        self.assertEqual(store.importera_spelschema(self.c, bad),
                         {"skapade": 0, "uppdaterade": 0, "hoppade": 1})

    def test_sport_ur_liganamnet_nar_falt_och_arg_saknas(self):
        # Handboll-filerna saknar sport-fält → härleds ur "Handbollsligan Dam".
        hb = [{"league": "Handbollsligan Dam", "home_team": "H65 Höör",
               "away_team": "Skövde HF", "date": "2026-10-10", "kickoff": "14:00"}]
        r = store.importera_spelschema(self.c, hb)   # varken sport-arg el. -fält
        self.assertEqual(r["skapade"], 1)
        self.assertEqual(
            self.c.execute("SELECT sport FROM matchen").fetchone()["sport"], "handboll")


class TestBevakningKrockar(unittest.TestCase):
    """Krock-hantering: prio HK Malmö > Lunds VK Dam > H65 > Lunds VK herr > OV."""

    def test_match_prio_ordning_liga_och_borta(self):
        p = store.match_prio
        self.assertEqual(p("HK Malmö", "X", "Handbollsligan"), 0)
        self.assertEqual(p("Lunds VK", "RIG Falköping", "Elitserien Damer"), 1)
        self.assertEqual(p("H65 Höör", "Boden", "Handbollsligan Dam"), 2)
        self.assertEqual(p("Lunds VK", "Habo", "Elitserien"), 3)          # herr
        self.assertEqual(p("OV Helsingborg", "X", "Handbollsligan Dam"), 4)
        self.assertEqual(p("Kristianstad HK", "Sävehof", "Handbollsligan Dam"), 5)  # ej
        self.assertEqual(p("LUGI HF", "HK Malmö", "Handbollsligan"), 0)   # borta räknas

    def test_krock_11_07_lunds_dam_vinner_over_h65_och_herr(self):
        matcher = [
            {"lag_hemma": "H65 Höör", "lag_borta": "Boden Handboll",
             "datum": "2026-11-07", "liga": "Handbollsligan Dam", "tid": "14:00"},
            {"lag_hemma": "Lunds VK", "lag_borta": "Habo Wolley",
             "datum": "2026-11-07", "liga": "Elitserien", "tid": "16:00"},
            {"lag_hemma": "Lunds VK", "lag_borta": "RIG Falköping",
             "datum": "2026-11-07", "liga": "Elitserien Damer", "tid": "16:00"},
        ]
        k = store.hitta_krockar(matcher)
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]["vald"]["liga"], "Elitserien Damer")        # prio 1
        self.assertEqual([m["prio"] for m in k[0]["krockar"]], [2, 3])    # H65, herr

    def test_krock_hk_malmo_vinner_over_ov(self):
        matcher = [
            {"lag_hemma": "HK Malmö", "lag_borta": "HF Karlskrona",
             "datum": "2026-10-09", "liga": "Handbollsligan", "tid": "19:00"},
            {"lag_hemma": "OV Helsingborg", "lag_borta": "Kristianstad HK",
             "datum": "2026-10-09", "liga": "Handbollsligan Dam", "tid": "19:00"},
        ]
        k = store.hitta_krockar(matcher)
        self.assertEqual(k[0]["vald"]["hemma"], "HK Malmö")               # prio 0

    def test_obevakad_match_ar_ingen_krock(self):
        matcher = [
            {"lag_hemma": "HK Malmö", "lag_borta": "X", "datum": "2026-11-01",
             "liga": "Handbollsligan"},
            {"lag_hemma": "Kristianstad HK", "lag_borta": "Sävehof",
             "datum": "2026-11-01", "liga": "Handbollsligan Dam"},        # bevakas ej
        ]
        self.assertEqual(store.hitta_krockar(matcher), [])
