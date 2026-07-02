"""Tester för pywebview-bryggan (Api) — mot in-memory DB, inget fönster."""

import unittest

from dpt2.app import Api, _gallring_av_config
from dpt2.data import store


class TestApi(unittest.TestCase):
    def setUp(self):
        # En delad in-memory-anslutning (Api håller self.conn).
        self.api = Api(db_path=":memory:")

    def test_info(self):
        info = self.api.info()
        self.assertEqual(info["schemaversion"], 8)

    def test_match_round_trip_genom_bryggan(self):
        res = self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "datum": "2026-06-27", "tid": "14:00", "arena": "Eleda Stadion",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "resultat": "6-0",
            "spelare": [
                {"nr": "1", "namn": "Zecira Musovic", "lag": "hemma",
                 "handle": "@zm", "info": "MV", "start": True},
                {"nr": "9", "namn": "Borta-spelare", "lag": "borta"},
            ],
        })
        self.assertTrue(res["ok"])
        mid = res["id"]

        lista = self.api.lista_matcher()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["lag_hemma"], "Malmö FF")
        self.assertEqual(lista[0]["status"], "avslutad")     # resultat satt

        full = self.api.hamta_match(mid)
        self.assertEqual(len(full["spelare"]), 2)
        zm = next(p for p in full["spelare"] if p["nr"] == "1")
        self.assertEqual(zm["lag"], "hemma")
        self.assertEqual(zm["handle"], "@zm")
        self.assertTrue(zm["start"])

    def test_lag_och_tavling_register(self):
        self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll", "datum": "2026-06-27",
        })
        lag = self.api.lista_lag()
        self.assertEqual({l["namn"] for l in lag},
                         {"Malmö FF", "Kristianstads DFF"})
        tav = self.api.lista_tavlingar()
        self.assertEqual(tav[0]["namn"], "OBOS Damallsvenskan")

    def test_spara_lag_direkt(self):
        res = self.api.spara_lag({"namn": "HK Malmö", "instagram": "@hkmhandboll"})
        self.assertEqual(res["id"], "hk-malmo")
        self.assertEqual(self.api.lista_lag()[0]["instagram"], "@hkmhandboll")

    def test_radera(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        self.api.radera_match(mid)
        self.assertEqual(self.api.lista_matcher(), [])

    def test_aktiv_match(self):
        self.assertIsNone(self.api.aktiv_match())
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        res = self.api.satt_aktiv_match(mid)
        self.assertTrue(res["ok"])
        self.assertEqual(self.api.aktiv_match()["id"], mid)

    def test_aktivt_urval(self):
        # Utan urval: None. Med urval men utan uttryckligt val: senaste gallrade.
        self.assertIsNone(self.api.aktivt_urval())
        u1 = store.spara_urval(self.api.conn, kalla="/a", bilder=10)
        u2 = store.spara_urval(self.api.conn, kalla="/b", bilder=20)
        # skapad har sekundupplösning — gör ordningen deterministisk i testet
        self.api.conn.execute(
            "UPDATE urval SET skapad='2099-01-01T00:00:00' WHERE id=?", (u2,))
        self.assertEqual(self.api.aktivt_urval()["id"], u2)   # nyast gallrad
        # Uttryckligt val vinner.
        res = self.api.satt_aktivt_urval(u1)
        self.assertTrue(res["ok"])
        self.assertEqual(res["urval"]["id"], u1)
        self.assertEqual(self.api.aktivt_urval()["id"], u1)
        # Aktivt urval följer med genom statusbyten (levererad ≠ bortglömd).
        store.satt_urval_status(self.api.conn, u1, "levererad")
        self.assertEqual(self.api.aktivt_urval()["id"], u1)
        # Pekar valet på ett raderat urval faller vi tillbaka till senaste gallrade.
        self.api.conn.execute("DELETE FROM urval WHERE id=?", (u1,))
        self.assertEqual(self.api.aktivt_urval()["id"], u2)

    def test_urval_hojdpunkter(self):
        # Utan aktivt urval → ok: False.
        self.assertFalse(self.api.urval_hojdpunkter()["ok"])
        uid = store.spara_urval(self.api.conn, kalla="/Volumes/NIKON/DCIM/277Z8",
                                bilder=0)
        store.ersatt_urval_bilder(self.api.conn, uid, [
            ("DSC_0417", 1, 0.91), ("DSC_0301", 0, 0.30), ("DSC_0502", 1, 0.95),
            ("DSC_0610", 1, 0.40)])
        self.api.satt_aktivt_urval(uid)
        r = self.api.urval_hojdpunkter(2)
        self.assertTrue(r["ok"])
        self.assertEqual(r["filer"], ["DSC_0502", "DSC_0417"])   # poäng fallande
        self.assertEqual(r["namn"], "277Z8")                     # kalla-fallback
        # Match-kopplat urval → "Hemma – Borta" som namn.
        mid = self.api.spara_match({"lag_hemma": "Malmö FF",
                                    "lag_borta": "KDFF", "datum": "2026-01-01"})["id"]
        uid2 = store.spara_urval(self.api.conn, kalla="/x", bilder=5, match_id=mid)
        self.api.satt_aktivt_urval(uid2)
        r2 = self.api.urval_hojdpunkter()
        self.assertEqual(r2["namn"], "Malmö FF – KDFF")
        self.assertEqual(r2["filer"], [])   # ingen per-bild-gallring ännu

    def test_starta_cull_skapar_urval_och_jobb(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-01-01"})["id"]
        res = self.api.starta_cull({
            "kalla": "/Volumes/NIKON/DCIM", "match_id": mid, "kamera": "NIKON Z 8",
            "behall_varde": 40, "behall_enhet": "bilder", "verktyg": "ai",
            "modell": "din_smak", "burst": 2.0})
        self.assertTrue(res["ok"])
        u = store.hamta_urval(self.api.conn, res["urval_id"])
        self.assertEqual(u["match_id"], mid)
        self.assertEqual(u["kamera"], "NIKON Z 8")
        jobb = store.jobb_for_urval(self.api.conn, res["urval_id"])
        self.assertEqual(jobb[0]["behall_varde"], 40.0)
        self.assertEqual(jobb[0]["behall_enhet"], "bilder")


    def test_leverera_urval_skriver_sidecars_och_satter_status(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        (d / "DSC_0001.nef").write_bytes(b"")
        (d / "DSC_0002.nef").write_bytes(b"")
        uid = store.spara_urval(self.api.conn, kalla=str(d), bilder=2)
        res = self.api.leverera_urval(uid, {"exp_bump": 0.3})
        self.assertTrue(res["ok"])
        self.assertEqual(res["skrivna"], 2)
        self.assertEqual(res["status"], "levererad")
        self.assertTrue((d / "DSC_0001.xmp").exists())
        self.assertEqual(store.hamta_urval(self.api.conn, uid)["status"],
                         "levererad")

    def test_leverera_urval_tom_mapp(self):
        import tempfile
        uid = store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(), bilder=0)
        res = self.api.leverera_urval(uid)
        self.assertFalse(res["ok"])
        # status oförändrad när inget levererades
        self.assertEqual(store.hamta_urval(self.api.conn, uid)["status"],
                         "gallrad")

    def test_leverera_okant_urval(self):
        self.assertFalse(self.api.leverera_urval("finns-inte")["ok"])

    def test_lista_urval_med_matchetikett_och_statusfilter(self):
        import tempfile
        mid = self.api.spara_match({"lag_hemma": "Malmö FF", "lag_borta": "KDFF",
                                    "datum": "2026-06-27"})["id"]
        u1 = store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(),
                               bilder=10, match_id=mid)
        store.spara_urval(self.api.conn, kalla=tempfile.mkdtemp(), bilder=5)
        alla = self.api.lista_urval()
        self.assertEqual(len(alla), 2)
        rad = next(u for u in alla if u["id"] == u1)
        self.assertEqual(rad["lag_hemma"], "Malmö FF")     # join mot matchen
        # statusfilter
        store.satt_urval_status(self.api.conn, u1, "levererad")
        lev = self.api.lista_urval("levererad")
        self.assertEqual([u["id"] for u in lev], [u1])



    def test_generera_bildsvep_utan_nyckel(self):
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.skipTest("API-nyckel satt — skarp väg testas ej här")
        res = self.api.generera_bildsvep("Malmö FF–Växjö DFF 3–0", "fotboll")
        self.assertFalse(res["ok"])           # ingen nyckel → snäll fallback


    def test_innehall_spara_forhandsgranska_lista(self):
        data = {"typ": "match", "titel": "Malmö FF – KDFF", "resultat": "6-0",
                "malskyttar": "Musovic 12', Persson 45'", "body": "Referat.",
                "figurer": [{"bild": "1.jpg", "alt": "jubel", "bildtext": "Segern"}]}
        pre = self.api.forhandsgranska_innehall(data)
        self.assertEqual(pre["slug"], "malmo-ff-kdff")
        self.assertIn("titel: Malmö FF – KDFF", pre["md"])
        self.assertIn("![jubel](1.jpg)", pre["md"])
        res = self.api.spara_innehall(data)
        self.assertTrue(res["ok"])
        lst = self.api.lista_innehall()
        self.assertEqual(lst[0]["frontmatter"]["malskyttar"], ["Musovic 12'", "Persson 45'"])

    def test_innehall_exportera_skriver_md(self):
        import tempfile
        d = tempfile.mkdtemp()
        data = {"typ": "event", "titel": "Sommarcup 2026", "body": "Text."}
        res = self.api.exportera_innehall(data, d)
        self.assertTrue(res["ok"])
        self.assertTrue(res["path"].endswith("sommarcup-2026.md"))
        from pathlib import Path
        self.assertIn("typ: event", Path(res["path"]).read_text(encoding="utf-8"))
        # markerat publicerat i datalagret
        self.assertTrue(self.api.lista_innehall()[0]["publicerad"])

    def test_innehall_export_utan_katalog(self):
        self.assertFalse(self.api.exportera_innehall({"titel": "X"}, "")["ok"])

    def test_innehall_md_event(self):
        r = self.api.forhandsgranska_innehall({
            "typ": "event", "titel": "Bröllop i Tällberg", "kategori": "Bröllop",
            "kund": "Anna & Erik", "datum": "2026-08-15", "plats": "Tällberg",
            "galleri": "https://galleri.dalecarliaphoto.se/x",
            "ingress": "En dag vid Siljan."})
        self.assertEqual(r["slug"], "brollop-i-tallberg")
        self.assertIn("typ: event", r["md"])
        self.assertIn("kategori: Bröllop", r["md"])
        self.assertIn('kund: "Anna & Erik"', r["md"])     # & citeras
        self.assertIn("plats: Tällberg", r["md"])
        self.assertIn("ingress:", r["md"])
        self.assertNotIn("liga", r["md"])                 # inga matchfält

    def test_innehall_md_landskap(self):
        # Temat härleds ur typen (Landskap = Sol) — `tema:` skrivs aldrig.
        r = self.api.forhandsgranska_innehall({
            "typ": "landskap", "titel": "Höst vid Siljan", "tema": "Sol",
            "plats": "Rättvik", "period": "sep–okt 2026",
            "ingress": "Bildserie."})
        self.assertEqual(r["slug"], "host-vid-siljan")
        self.assertNotIn("tema", r["md"])
        self.assertIn("period: sep–okt 2026", r["md"])

    def test_innehall_galleri_harledda_referenser(self):
        # Utan explicit bild härleds /bilder/{slug}/{n}.jpg; Sport har alt+bildtext.
        r = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "body": "Referat.",
            "figurer": [{"bild": "", "alt": "jubel", "bildtext": "Segern"},
                        {"bild": "", "alt": "nick", "bildtext": ""}]})
        self.assertIn("![jubel](/bilder/a-b/1.jpg)", r["md"])
        self.assertIn("*Segern*", r["md"])
        self.assertIn("![nick](/bilder/a-b/2.jpg)", r["md"])

    def test_innehall_galleri_bild_only_landskap_event(self):
        # Landskap & Event: endast bild — alt/bildtext strippas.
        for typ in ("landskap", "event"):
            r = self.api.forhandsgranska_innehall({
                "typ": typ, "titel": "Serie X",
                "figurer": [{"bild": "", "alt": "ignoreras", "bildtext": "bort"}]})
            self.assertIn("![](/bilder/serie-x/1.jpg)", r["md"])
            self.assertNotIn("ignoreras", r["md"])
            self.assertNotIn("bort", r["md"])

    def test_innehall_blogg_bildkatalog_utan_datumprefix(self):
        # Bloggens .md-fil är datum-prefixad men bildkatalogen är titelns slug.
        r = self.api.forhandsgranska_innehall({
            "typ": "blogg", "titel": "Vandring", "datum": "2026-09-01",
            "figurer": [{"bild": "", "alt": "fjäll", "bildtext": ""}]})
        self.assertEqual(r["slug"], "2026-09-01-vandring")
        self.assertIn("![fjäll](/bilder/vandring/1.jpg)", r["md"])

    def test_innehall_md_blogg_med_platser(self):
        r = self.api.forhandsgranska_innehall({
            "typ": "blogg", "titel": "Vandring i Grövelsjön",
            "kategori": "Resor", "datum": "2026-09-01",
            "ingress": "Tre dagar på fjället.", "body": "Dag ett…",
            "platser": [{"plats": "Grövelsjöns fjällstation", "tips": "boka tidigt"},
                        {"plats": "", "tips": "ignoreras"}]})
        self.assertEqual(r["slug"], "2026-09-01-vandring-i-grovelsjon")  # datum-prefix
        self.assertIn("## Platser & tips", r["md"])
        self.assertIn("- **Grövelsjöns fjällstation** — boka tidigt", r["md"])
        self.assertNotIn("ignoreras", r["md"])

    def test_innehall_md_match_har_halvtid(self):
        r = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "resultat": "6-0",
            "halvtid": "3-0"})
        self.assertIn("halvtid: 3-0", r["md"])


    def test_modell_bibliotek_och_vaxling(self):
        a = store.spara_modell(self.api.conn, typ="din_smak",
                               pkl_path="/m/dinsmak.pkl", n_uppdrag=18, aktiv=True)
        b = store.spara_modell(self.api.conn, typ="arkiv", pkl_path="/m/arkiv.pkl")
        self.assertEqual(len(self.api.lista_modeller()), 2)
        self.assertEqual(self.api.aktiv_modell()["id"], a)
        res = self.api.satt_aktiv_modell(b)
        self.assertTrue(res["ok"])
        self.assertEqual(res["aktiv"]["id"], b)
        self.assertEqual(self.api.aktiv_modell()["id"], b)   # bara en aktiv
        self.assertFalse(self.api.satt_aktiv_modell("finns-inte")["ok"])

    def test_starta_omrakna_utan_root(self):
        self.assertFalse(self.api.starta_omrakna_arkiv("")["ok"])

    def test_starta_gallring_utan_urval(self):
        self.assertFalse(self.api.starta_gallring("")["ok"])

    def test_starta_nummer_utan_urval(self):
        self.assertFalse(self.api.starta_nummer("")["ok"])

    def test_las_lag_trupp_via_csv(self):
        import tempfile
        from pathlib import Path
        self.api.spara_lag({"namn": "Malmö FF"})
        p = Path(tempfile.mkdtemp()) / "trupp.csv"
        p.write_text("Nr,Namn,Position\n1,Zecira Musovic,Målvakt\n"
                     "9,Anna Anvegård,Forward\n", encoding="utf-8")
        r = self.api.las_lag_trupp("malmo-ff", "csv", str(p))
        self.assertTrue(r["ok"])
        self.assertEqual(r["antal"], 2)
        self.assertEqual(r["trupp_kalla"], "CSV")
        self.assertEqual(len(r["roster"]), 2)                # roster i svaret
        rad = next(l for l in self.api.lista_lag() if l["id"] == "malmo-ff")
        self.assertEqual(rad["trupp_n"], 2)
        self.assertEqual(rad["trupp_kalla"], "CSV")

    def test_las_lag_trupp_validering(self):
        self.assertFalse(self.api.las_lag_trupp("finns-ej", "csv", "/x.csv")["ok"])
        self.api.spara_lag({"namn": "Malmö FF"})
        self.assertFalse(self.api.las_lag_trupp("malmo-ff", "voodoo", "")["ok"])
        # tom/oläsbar källa → informativt fel
        self.assertFalse(self.api.las_lag_trupp("malmo-ff", "csv",
                                                "/finns/inte.csv")["ok"])

    def test_hamta_lag_trupp(self):
        self.api.spara_lag({"namn": "Malmö FF"})
        self.api.spara_spelare("malmo-ff", {"nr": "1", "namn": "Ida Ohlsson"})
        trupp = self.api.hamta_lag_trupp("malmo-ff")
        self.assertEqual(len(trupp), 1)
        self.assertEqual(trupp[0]["namn"], "Ida Ohlsson")

    def test_spara_och_radera_spelare(self):
        self.api.spara_lag({"namn": "Malmö FF"})
        r = self.api.spara_spelare("malmo-ff", {"nr": "1", "namn": "Ida Ohlsson",
                                                 "position": "MV"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["id"])
        self.assertEqual(len(self.api.hamta_lag_trupp("malmo-ff")), 1)
        self.api.radera_spelare(r["id"])
        self.assertEqual(self.api.hamta_lag_trupp("malmo-ff"), [])

    def test_spara_spelare_validering(self):
        self.assertFalse(self.api.spara_spelare("finns-ej", {"namn": "X"})["ok"])
        self.api.spara_lag({"namn": "Malmö FF"})
        self.assertFalse(self.api.spara_spelare("malmo-ff", {"namn": ""})["ok"])

    def test_las_uttag_fil_startelva(self):
        import tempfile
        from pathlib import Path
        mid = self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "KDFF",
            "spelare": [{"nr": "99", "namn": "Gammal Start", "lag": "borta",
                         "start": True}]})["id"]
        d = Path(tempfile.mkdtemp())
        (d / "start.csv").write_text("Nr,Namn\n1,Musovic\n6,Öling\n",
                                     encoding="utf-8")
        r = self.api.las_uttag_fil(mid, str(d / "start.csv"), "hemma")
        self.assertTrue(r["ok"])
        hemma_start = [p for p in r["match"]["spelare"]
                       if p["lag"] == "hemma" and p["start"]]
        self.assertEqual(len(hemma_start), 2)
        # bortalagets startelva orörd
        self.assertTrue(any(p["lag"] == "borta" and p["start"]
                            for p in r["match"]["spelare"]))
        # ny startelva ERSÄTTER sidans tidigare uttag helt (ingen bänk kvar)
        (d / "start2.csv").write_text("Nr,Namn\n7,Ny Elva\n", encoding="utf-8")
        r2 = self.api.las_uttag_fil(mid, str(d / "start2.csv"), "hemma")
        hemma = [p for p in r2["match"]["spelare"] if p["lag"] == "hemma"]
        self.assertEqual([p["namn"] for p in hemma], ["Ny Elva"])
        self.assertTrue(hemma[0]["start"])

    def test_las_uttag_fil_okand_match(self):
        self.assertFalse(self.api.las_uttag_fil("finns-ej", "/x.csv",
                                                "hemma")["ok"])

    def test_publicera_live_story_validering(self):
        self.assertFalse(self.api.publicera_live_story({})["ok"])
        self.assertFalse(self.api.publicera_live_story(
            {"moment": "Avspark"})["ok"])                    # ingen bild vald

    def test_skapa_story_kraver_moment_och_foto(self):
        self.assertFalse(self.api.skapa_story({})["ok"])
        self.assertFalse(self.api.skapa_story({"moment": "Avspark"})["ok"])

    def test_filvaljare_graciost_utan_fonster(self):
        # inget pywebview-fönster i test → {ok:False}, ingen krasch
        self.assertFalse(self.api.valj_mapp()["ok"])
        self.assertFalse(self.api.valj_fil("Välj", ["XMP (*.xmp)"])["ok"])

    def test_ui_filter_ar_giltiga_pywebview_filetypes(self):
        # Regression: pywebview validerar file_types mot 'Beskrivning (*.ext)' —
        # råa mönster som '*.csv' kastar ValueError inuti create_file_dialog,
        # vilket _dialog sväljer tyst ({ok:False}) så knappen ser ut att inte
        # göra något. Utan fönster (som ovan) körs aldrig valideringen, så den
        # bugen missas där — testa parse_file_type direkt mot filtren UI:t
        # skickar (Lag.svelte: logga/trupp-källor).
        from webview.util import parse_file_type
        ui_filter = [
            "Bilder (*.png;*.jpg;*.jpeg;*.webp)",
            "CSV (*.csv)",
            "Bilder (*.jpg;*.jpeg;*.png;*.heic;*.heif)",
            "PDF (*.pdf)",
        ]
        for f in ui_filter:
            parse_file_type(f)


    def test_logg_kor_demo_buffrar_och_rensar(self):
        res = self.api.kor_demo_jobb(3)
        self.assertTrue(res["ok"])
        typer = [e["typ"] for e in res["events"]]
        self.assertEqual(typer[0], "start")
        self.assertIn("klar", typer)
        # buffrat i appen → Logg-panelen kan hämta
        self.assertEqual(self.api.hamta_logg(), res["events"])
        self.api.rensa_logg()
        self.assertEqual(self.api.hamta_logg(), [])


class _FakeKalender:
    """Ersätter Api.kalender i tester som rör synk — inga riktiga nätverksanrop
    (den skarpa Kalender() gör HTTP mot Calendar Sync-tjänsten även vid fel)."""

    def __init__(self):
        self.skapade = []
        self.raderade = []

    def har_nyckel(self):
        return True

    def halsa(self):
        return True

    def lista_jobb(self):
        return []

    def skapa_jobb(self, jobb):
        self.skapade.append(jobb)
        return {"ok": True, "jobb": {**jobb, "id": f"remote{len(self.skapade)}",
                                     "google_event_id": "g1"}}

    def uppdatera_jobb(self, jid, jobb):
        return {"ok": True}

    def radera_jobb(self, jid):
        self.raderade.append(jid)
        return {"ok": True}


class TestFotojobbUtkastBridge(unittest.TestCase):
    """Tävling → lokalt fotojobb-utkast → aktivera synk (skickas till tjänsten).
    Validerings-/lokala vägarna testas utan fake (rör aldrig self.kalender);
    de som faktiskt synkar använder _FakeKalender för att undvika nätverk."""

    def setUp(self):
        self.api = Api(db_path=":memory:")

    def test_lagg_tavling_i_kalender_kraver_datum(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll"})
        r = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")
        self.assertFalse(r["ok"])
        self.assertIn("datum", r["fel"])

    def test_lagg_tavling_i_kalender_okand_tavling(self):
        self.assertFalse(self.api.lagg_tavling_i_kalender("finns-ej")["ok"])

    def test_lagg_tavling_i_kalender_skapar_utkast(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31",
                                "ort": "Sverige"})
        r = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")
        self.assertTrue(r["ok"])
        self.assertTrue(r["utkast_id"])
        # kalender-flaggan persisteras på tävlingen
        t = next(x for x in self.api.lista_tavlingar() if x["id"] == "obos-damallsvenskan")
        self.assertTrue(t["kalender"])
        # utkastet dyker upp i Fotojobb-listan, taggat utkast=True, aldrig pushat
        self.api.kalender = _FakeKalender()
        jobb = self.api.lista_fotojobb()
        self.assertEqual(len(jobb), 1)
        self.assertTrue(jobb[0]["utkast"])
        self.assertIsNone(jobb[0]["google_event_id"])
        self.assertIsNone(jobb[0]["category"])          # Okategoriserat
        self.assertEqual(self.api.kalender.skapade, [])  # inget pushat än

    def test_lagg_tavling_i_kalender_idempotent(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        r1 = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")
        r2 = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")
        self.assertEqual(r1["utkast_id"], r2["utkast_id"])

    def test_ta_bort_tavling_ur_kalender(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        self.api.lagg_tavling_i_kalender("obos-damallsvenskan")
        r = self.api.ta_bort_tavling_ur_kalender("obos-damallsvenskan")
        self.assertTrue(r["ok"])
        t = next(x for x in self.api.lista_tavlingar() if x["id"] == "obos-damallsvenskan")
        self.assertFalse(t["kalender"])
        self.api.kalender = _FakeKalender()
        self.assertEqual(self.api.lista_fotojobb(), [])

    def test_kategorisera_utkast_sparas_bara_lokalt(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        self.api.kalender = _FakeKalender()
        r = self.api.spara_fotojobb({"id": uid, "utkast": True, "category": "Sport"})
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.kalender.skapade, [])   # rörde aldrig tjänsten
        jobb = self.api.lista_fotojobb()
        self.assertEqual(jobb[0]["category"], "Sport")

    def test_koppla_utkast_till_match(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        mid = store.spara_match(self.api.conn, {"lag_hemma": "A", "lag_borta": "B"})
        self.api.kalender = _FakeKalender()
        self.api.spara_fotojobb({"id": uid, "utkast": True, "category": "Sport",
                                 "match_id": mid})
        jobb = self.api.lista_fotojobb()
        self.assertEqual(jobb[0]["match_id"], mid)

    def test_koppla_bort_match_satter_none(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        mid = store.spara_match(self.api.conn, {"lag_hemma": "A", "lag_borta": "B"})
        self.api.kalender = _FakeKalender()
        self.api.spara_fotojobb({"id": uid, "utkast": True, "match_id": mid})
        self.api.spara_fotojobb({"id": uid, "utkast": True, "match_id": None})
        self.assertIsNone(self.api.lista_fotojobb()[0]["match_id"])

    def test_koppla_nytt_riktigt_jobb_till_match_ur_svarets_id(self):
        mid = store.spara_match(self.api.conn, {"lag_hemma": "A", "lag_borta": "B"})
        fake = _FakeKalender()
        self.api.kalender = fake
        r = self.api.spara_fotojobb({"title": "Match", "start_at": "2026-08-01T10:00",
                                     "end_at": "2026-08-01T12:00", "category": "Sport",
                                     "match_id": mid})
        self.assertTrue(r["ok"])
        self.assertEqual(store.matchref_for_fotojobb(self.api.conn, ["remote1"]),
                         {"remote1": mid})

    def test_radera_fotojobb_stadar_matchlank(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        mid = store.spara_match(self.api.conn, {"lag_hemma": "A", "lag_borta": "B"})
        self.api.kalender = _FakeKalender()
        self.api.spara_fotojobb({"id": uid, "utkast": True, "match_id": mid})
        self.api.radera_fotojobb(uid)
        self.assertEqual(store.matchref_for_fotojobb(self.api.conn, [uid]), {})

    def test_radera_utkast_via_radera_fotojobb(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        self.api.kalender = _FakeKalender()
        r = self.api.radera_fotojobb(uid)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.lista_fotojobb(), [])

    def test_aktivera_synk_pushar_och_tar_bort_utkastet(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31",
                                "arena": "Eleda Stadion"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        fake = _FakeKalender()
        self.api.kalender = fake
        r = self.api.aktivera_synk_fotojobb(uid)
        self.assertTrue(r["ok"])
        self.assertEqual(len(fake.skapade), 1)
        self.assertEqual(fake.skapade[0]["title"], "OBOS Damallsvenskan")
        self.assertEqual(fake.skapade[0]["location"], "Eleda Stadion")
        # utkastet är borta lokalt — det som nu finns kommer från tjänsten (lista_jobb)
        self.assertIsNone(store.hamta_fotojobb_utkast(self.api.conn, uid))

    def test_aktivera_synk_okant_utkast(self):
        r = self.api.aktivera_synk_fotojobb("finns-ej")
        self.assertFalse(r["ok"])


class TestMatchSynkOchRadering(unittest.TestCase):
    """Synk-pillen i matchlistan (satt_match_synk) + Ta bort match som städar
    kalenderjobb — handoff matcher_synk_heldag."""

    def setUp(self):
        self.api = Api(db_path=":memory:")
        self.fake = _FakeKalender()
        self.api.kalender = self.fake
        self.mid = self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "FC Rosengård",
            "datum": "2026-08-15", "tid": "14:00", "arena": "Eleda Stadion",
            "liga": "OBOS Damallsvenskan", "sport": "fotboll"})["id"]

    def test_synk_pa_skapar_jobb_med_sluttid_per_sport(self):
        r = self.api.satt_match_synk(self.mid, True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["synk_jobb_id"], "remote1")
        jobb = self.fake.skapade[0]
        self.assertEqual(jobb["title"], "Malmö FF – FC Rosengård")
        self.assertEqual(jobb["start_at"], "2026-08-15T14:00:00")
        self.assertEqual(jobb["end_at"], "2026-08-15T16:00:00")   # fotboll 2 tim
        self.assertFalse(jobb["all_day"])
        self.assertEqual(jobb["category"], "Sport")
        self.assertEqual(jobb["location"], "Eleda Stadion")
        self.assertEqual(self.api.lista_matcher()[0]["synk_jobb_id"], "remote1")

    def test_synk_sluttid_handboll(self):
        mid = self.api.spara_match({
            "lag_hemma": "HK Malmö", "lag_borta": "IK Sävehof",
            "datum": "2026-09-03", "tid": "19:00", "sport": "handboll"})["id"]
        self.api.satt_match_synk(mid, True)
        self.assertEqual(self.fake.skapade[0]["end_at"],
                         "2026-09-03T20:30:00")                   # 1,5 tim

    def test_synk_utan_tid_blir_heldag(self):
        mid = self.api.spara_match({
            "lag_hemma": "A", "lag_borta": "B",
            "datum": "2026-08-20", "tid": "", "sport": "fotboll"})["id"]
        r = self.api.satt_match_synk(mid, True)
        self.assertTrue(r["ok"])
        jobb = self.fake.skapade[0]
        self.assertTrue(jobb["all_day"])
        self.assertEqual(jobb["start_at"], "2026-08-20")
        self.assertEqual(jobb["end_at"], "2026-08-20")

    def test_synk_pa_ar_idempotent(self):
        r1 = self.api.satt_match_synk(self.mid, True)
        r2 = self.api.satt_match_synk(self.mid, True)
        self.assertEqual(len(self.fake.skapade), 1)
        self.assertEqual(r1["synk_jobb_id"], r2["synk_jobb_id"])

    def test_synk_av_tar_bort_jobb_och_lank(self):
        self.api.satt_match_synk(self.mid, True)
        r = self.api.satt_match_synk(self.mid, False)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["synk_jobb_id"])
        self.assertEqual(self.fake.raderade, ["remote1"])
        self.assertIsNone(self.api.lista_matcher()[0]["synk_jobb_id"])

    def test_synk_kraver_datum(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B"})["id"]
        r = self.api.satt_match_synk(mid, True)
        self.assertFalse(r["ok"])
        self.assertIn("datum", r["fel"])

    def test_synk_okand_match(self):
        self.assertFalse(self.api.satt_match_synk("finns-ej", True)["ok"])

    def test_lankat_utkast_raknas_inte_som_synkat(self):
        # Ett fotojobb-UTKAST kopplat till matchen ligger inte i Google —
        # pillen ska visa Ej synkad, och synk på ska skapa ett riktigt jobb.
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        store.lanka_fotojobb_match(self.api.conn, uid, self.mid)
        self.assertIsNone(self.api.lista_matcher()[0]["synk_jobb_id"])
        r = self.api.satt_match_synk(self.mid, True)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.fake.skapade), 1)

    def test_radera_match_tar_bort_kalenderjobb_och_lankar(self):
        self.api.satt_match_synk(self.mid, True)
        r = self.api.radera_match(self.mid)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.lista_matcher(), [])
        self.assertEqual(self.fake.raderade, ["remote1"])
        self.assertEqual(
            store.matchref_for_fotojobb(self.api.conn, ["remote1"]), {})

    def test_radera_match_rensar_aktiv_match(self):
        self.api.satt_aktiv_match(self.mid)
        self.api.radera_match(self.mid)
        self.assertIsNone(self.api.aktiv_match())


class TestGallringConfig(unittest.TestCase):
    def test_bilder_ger_topp(self):
        g = _gallring_av_config({"behall_enhet": "bilder", "behall_varde": 40,
                                 "verktyg": "ai", "burst": 2.0})
        self.assertEqual(g.topp, 40)
        self.assertTrue(g.ai)

    def test_procent_ger_andel(self):
        g = _gallring_av_config({"behall_enhet": "procent", "behall_varde": 25,
                                 "verktyg": "rapport"})
        self.assertAlmostEqual(g.andel, 0.25)
        self.assertIsNone(g.topp)
        self.assertFalse(g.ai)          # rapport → ai=False


if __name__ == "__main__":
    unittest.main(verbosity=2)
