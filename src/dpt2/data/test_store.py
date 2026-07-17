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
                             "paminnelse_jobb_id": None})
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
