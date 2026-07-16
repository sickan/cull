"""Tester för pywebview-bryggan (Api) — mot in-memory DB, inget fönster."""

import unittest

from dpt2.app import Api, _gallring_av_config, _hitta_site_rot, _spara_export_bild
from dpt2.data import db, store


class TestApi(unittest.TestCase):
    def setUp(self):
        # En delad in-memory-anslutning (Api håller self.conn).
        self.api = Api(db_path=":memory:")

    def test_info(self):
        info = self.api.info()
        self.assertEqual(info["schemaversion"], db.SCHEMA_VERSION)

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

    def test_leverera_egen_mapp_skapar_urval_och_levererar(self):
        # §6: bildkälla "Egen mapp" — inget Gallra-urval behöver finnas i
        # förväg, ett skapas i farten och alla bilder i mappen levereras
        # (ingen behall_stems-filtrering eftersom ingen cull-körning finns).
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        (d / "DSC_0010.nef").write_bytes(b"")
        (d / "DSC_0011.nef").write_bytes(b"")
        (d / "DSC_0012.nef").write_bytes(b"")
        res = self.api.leverera_egen_mapp(str(d))
        self.assertTrue(res["ok"])
        self.assertEqual(res["skrivna"], 3)
        self.assertEqual(res["status"], "levererad")
        urval = store.lista_urval(self.api.conn)
        self.assertEqual(len(urval), 1)
        self.assertEqual(urval[0]["kalla"], str(d))
        self.assertIsNone(urval[0]["match_id"])

    def test_leverera_egen_mapp_tom(self):
        import tempfile
        res = self.api.leverera_egen_mapp(tempfile.mkdtemp())
        self.assertFalse(res["ok"])
        self.assertEqual(store.lista_urval(self.api.conn), [])

    def test_hitta_site_rot_hittar_astro_projekt(self):
        import tempfile
        from pathlib import Path
        rot = Path(tempfile.mkdtemp()).resolve()   # macOS: /tmp är en symlink
        (rot / "public").mkdir()
        (rot / "astro.config.mjs").write_text("")
        djup = rot / "src" / "content" / "matcher"
        djup.mkdir(parents=True)
        self.assertEqual(_hitta_site_rot(djup), rot)

    def test_hitta_site_rot_ingen_traff(self):
        import tempfile
        self.assertIsNone(_hitta_site_rot(tempfile.mkdtemp()))
        self.assertIsNone(_hitta_site_rot(""))

    def test_spara_export_bild_jpeg_skalas_ned(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        d = Path(tempfile.mkdtemp())
        kalla = d / "in.jpg"
        Image.new("RGB", (3000, 2000), "red").save(kalla, "JPEG")
        mal = d / "ut" / "1.jpg"
        self.assertTrue(_spara_export_bild(kalla, mal, maxsize=800))
        with Image.open(mal) as im:
            self.assertLessEqual(max(im.size), 800)

    def test_spara_export_bild_saknad_kalla(self):
        self.assertFalse(_spara_export_bild("/finns/ej.jpg", "/tmp/ut.jpg"))

    def test_exportera_innehall_kopierar_galleribilder_till_sport_mapp(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        site = Path(tempfile.mkdtemp())
        (site / "public").mkdir()
        (site / "astro.config.mjs").write_text("")
        export_dir = site / "src" / "content" / "matcher"
        export_dir.mkdir(parents=True)

        kalla_dir = Path(tempfile.mkdtemp())
        bild1 = kalla_dir / "DSC_0001.jpg"
        Image.new("RGB", (400, 300), "blue").save(bild1, "JPEG")
        hero = kalla_dir / "HERO.jpg"
        Image.new("RGB", (400, 300), "green").save(hero, "JPEG")

        r = self.api.exportera_innehall({
            "typ": "match", "titel": "A – B", "hem": "A", "borta": "B", "resultat": "1-0",
            "hero": "hero.jpg", "heroKalla": str(hero),
            "figurer": [{"bild": str(bild1), "alt": "", "bildtext": ""}],
        }, str(export_dir))
        self.assertTrue(r["ok"])
        self.assertTrue((export_dir / "a-b.md").exists())
        self.assertTrue((site / "public" / "sport" / "a-b" / "1.jpg").exists())
        self.assertTrue((site / "public" / "sport" / "a-b" / "hero.jpg").exists())

    def test_exportera_innehall_utan_kalla_kraschar_inte(self):
        import tempfile
        from pathlib import Path
        export_dir = Path(tempfile.mkdtemp()) / "matcher"
        r = self.api.exportera_innehall({
            "typ": "match", "hem": "A", "borta": "B",
            "figurer": [{"bild": "", "alt": "", "bildtext": ""}],
        }, str(export_dir))
        self.assertTrue(r["ok"])

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

    def test_forhandsgranska_bildsvep_fraga_inget_natverksanrop(self):
        # Ren strängbyggnad — ska funka oavsett API-nyckel/nätverk, för
        # "godkänn prompten"-steget i UI:t.
        res = self.api.forhandsgranska_bildsvep_fraga(
            "Malmö FF–Kristianstads DFF 6-0",
            {"resultat": "6-0", "arena": "Eleda Stadion", "liga": "OBOS Damallsvenskan"})
        self.assertTrue(res["ok"])
        self.assertIn("Resultat: 6-0", res["fraga"])
        self.assertIn("Arena: Eleda Stadion", res["fraga"])


    def test_forhandsgranska_story_genom_bryggan(self):
        # VIKTIGT: forhandsgranska_story skriver till story_korning sin FASTA
        # sökväg — samma fil som appens riktiga Publicera→Live-förhandsvisning
        # använder. Patcha den till en tempfil så testet aldrig klobbar Stigs
        # faktiska förhandsvisning (hände 2026-07-03 — detta test var boven).
        import tempfile
        from pathlib import Path
        from PIL import Image
        from dpt2.tjanster import story_korning
        verklig_path = story_korning.FORHANDSVISNING_PATH
        self.addCleanup(setattr, story_korning, "FORHANDSVISNING_PATH", verklig_path)
        with tempfile.TemporaryDirectory() as d:
            story_korning.FORHANDSVISNING_PATH = Path(d) / "forhandsvisning-test.jpg"
            foto = f"{d}/kalla.jpg"
            Image.new("RGB", (400, 300), (80, 120, 160)).save(foto, "JPEG")
            res = self.api.forhandsgranska_story({
                "moment": "Avspark", "foto": foto, "tema": "Sol",
                "ut_mapp": f"{d}/aldrig-anvand"})
            self.assertTrue(res["ok"])
            self.assertNotEqual(Path(res["path"]), verklig_path)   # aldrig skarpa filen
            self.assertTrue(Path(res["path"]).exists())
            self.assertFalse(Path(f"{d}/aldrig-anvand").exists())

    def test_kanal_tak_speglar_vagen(self):
        # p.3/p.4: IG-taket beror på vägen; live/fb har fasta tak.
        self.assertEqual(self.api._kanal_tak("ig", "direkt"), 10)
        self.assertEqual(self.api._kanal_tak("ig", "disk"), 20)
        self.assertEqual(self.api._kanal_tak("live"), 10)
        self.assertEqual(self.api._kanal_tak("fb"), 20)

    def test_ig_export_mapp_ligger_under_pictures(self):
        # match_id=None → slug "ig"; ingen mapp SKAPAS (bara sökväg byggs).
        p = self.api._ig_export_mapp(None)
        self.assertIn("DPT2 IG-export", str(p))
        self.assertTrue(p.name.endswith("-ig"))
        self.assertFalse(p.exists())

    def test_publicera_kanal_ig_disk_exporterar_utan_meta(self):
        # p.3: "Exportera till disk" postar ALDRIG mot Meta — den renderar och
        # returnerar exporterad=True. Kör i testläge → aldrig skarpt.
        import tempfile
        from pathlib import Path
        from PIL import Image
        from dpt2.tjanster import story_korning
        verklig = story_korning.FORHANDSVISNING_PATH
        self.addCleanup(setattr, story_korning, "FORHANDSVISNING_PATH", verklig)
        with tempfile.TemporaryDirectory() as d:
            story_korning.FORHANDSVISNING_PATH = Path(d) / "fv.jpg"
            foton = []
            for i in range(3):
                f = f"{d}/bild{i}.jpg"
                Image.new("RGB", (400, 500), (80, 120, 160)).save(f, "JPEG")
                foton.append({"path": f})
            r = self.api.publicera_kanal({
                "kanal": "ig", "vag": "disk", "format": "4x5", "moment": "resultat",
                "bilder": foton, "test": True, "test_mapp": f"{d}/ut"})
            self.assertTrue(r["ok"])
            self.assertTrue(r.get("exporterad"))
            self.assertEqual(r["antal"], 3)

    def test_publicera_kanal_live_ar_multiframe(self):
        # p.4: live-storyn tar nu fler än omslaget (var hårt kapad till 1).
        import tempfile
        from pathlib import Path
        from PIL import Image
        from dpt2.tjanster import story_korning
        verklig = story_korning.FORHANDSVISNING_PATH
        self.addCleanup(setattr, story_korning, "FORHANDSVISNING_PATH", verklig)
        with tempfile.TemporaryDirectory() as d:
            story_korning.FORHANDSVISNING_PATH = Path(d) / "fv.jpg"
            foton = []
            for i in range(4):
                f = f"{d}/bild{i}.jpg"
                Image.new("RGB", (400, 700), (60, 90, 130)).save(f, "JPEG")
                foton.append({"path": f})
            r = self.api.publicera_kanal({
                "kanal": "live", "format": "9x16", "moment": "avspark",
                "bilder": foton, "test": True, "test_mapp": f"{d}/ut"})
            self.assertTrue(r["ok"])
            self.assertEqual(r["antal"], 4)   # inte längre kapad till 1

    def test_publicera_kanal_turnering_fyller_storyfalt_ur_tavlingen(self):
        # Fas 3 turnerings-SoMe: match_id=None → story-fälten ska komma ur
        # TÄVLINGEN (namn som rubrik, period+ort som underrad, sport/gren),
        # inte renderas som "EVENT" utan sport (buggen före fixen).
        import tempfile
        from pathlib import Path
        from PIL import Image
        from dpt2.tjanster import story_korning
        self.api.spara_tavling({
            "namn": "Nordea Open - ATP", "sport": "tennis", "gren": "herr",
            "typ": "turnering", "fran": "2026-07-13", "till": "2026-07-19",
            "ort": "Båstad", "arena": "Båstad Tennisstadion"})
        tid = self.api.lista_tavlingar()[0]["id"]
        # Fånga cfg:n som når renderaren i stället för att OCR:a en JPEG.
        fangad = {}
        verklig = story_korning._rendera
        def _spion(conn, cfg, **kw):
            fangad.update(cfg)
            return verklig(conn, cfg, **kw)
        self.addCleanup(setattr, story_korning, "_rendera", verklig)
        story_korning._rendera = _spion
        with tempfile.TemporaryDirectory() as d:
            f = f"{d}/bild.jpg"
            Image.new("RGB", (400, 700), (60, 90, 130)).save(f, "JPEG")
            r = self.api.publicera_kanal({
                "kanal": "ig", "format": "9x16", "moment": "nasta_match",
                "tavling_id": tid, "bilder": [{"path": f}],
                "test": True, "test_mapp": f"{d}/ut"})
            self.assertTrue(r["ok"])
            self.assertEqual(r["antal"], 1)
        self.assertEqual(fangad["lag_hemma"], "Nordea Open - ATP")
        self.assertEqual(fangad["lag_borta"], "")
        self.assertEqual(fangad["sport"], "tennis")
        self.assertEqual(fangad["gren"], "herr")
        self.assertEqual(fangad["arena"], "Båstad Tennisstadion")
        self.assertEqual(fangad["next_when"], "13 jul – 19 jul")
        self.assertEqual(fangad["liga"], "")   # namnet är redan rubriken

    def test_material_spara_lista_radera_genom_bryggan(self):
        res = self.api.spara_material({
            "kind": "live", "status": "utkast", "moment": "Avspark", "tema": "Hav",
            "dropbox": "~/Dropbox/DPT/Live/test", "foto": "~/Dropbox/DPT/Live/test/bild_03.jpg"})
        self.assertTrue(res["ok"])
        mid = res["id"]

        lst = self.api.lista_material()
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["status"], "utkast")
        self.assertEqual(lst[0]["foto"], "~/Dropbox/DPT/Live/test/bild_03.jpg")

        # samma id → uppdaterar i stället för att skapa en ny rad
        self.api.spara_material({"id": mid, "kind": "live", "status": "publicerad",
                                 "moment": "Avspark", "tema": "Hav"})
        lst = self.api.lista_material()
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["status"], "publicerad")

        self.api.radera_material(mid)
        self.assertEqual(self.api.lista_material(), [])

    def test_innehall_spara_forhandsgranska_lista(self):
        # titel skickas fortfarande med (används bara för slug-generering,
        # skrivs inte längre till frontmatter) — hem/borta/serie är sajtens
        # verkliga matcher-schema.
        data = {"typ": "match", "titel": "Malmö FF – KDFF",
                "hem": "Malmö FF", "borta": "KDFF", "serie": "Damallsvenskan",
                "resultat": "6-0", "malskyttar": "Musovic 12', Persson 45'",
                "body": "Referat.",
                "figurer": [{"bild": "1.jpg", "alt": "jubel", "bildtext": "Segern"}]}
        pre = self.api.forhandsgranska_innehall(data)
        self.assertEqual(pre["slug"], "malmo-ff-kdff")
        self.assertIn("hem: Malmö FF", pre["md"])
        self.assertIn("borta: KDFF", pre["md"])
        self.assertNotIn("titel:", pre["md"])
        # Bildreferensen i markdown är alltid den publika sport-sökvägen, inte
        # den lokala källfilen (den är bara till för _kopiera_match_bilder).
        self.assertIn("![jubel](/sport/malmo-ff-kdff/1.jpg)", pre["md"])
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
        # Match härleder /sport/{slug}/{n}.jpg (dit _kopiera_match_bilder
        # kopierar filerna vid export); Sport har alt+bildtext.
        r = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "body": "Referat.",
            "figurer": [{"bild": "", "alt": "jubel", "bildtext": "Segern"},
                        {"bild": "", "alt": "nick", "bildtext": ""}]})
        self.assertIn("![jubel](/sport/a-b/1.jpg)", r["md"])
        self.assertIn("*Segern*", r["md"])
        self.assertIn("![nick](/sport/a-b/2.jpg)", r["md"])

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
            "mellan": "3-0"})
        self.assertIn("halvtid: 3-0", r["md"])

    def test_innehall_md_match_sportprofil_byter_mellan_nyckel(self):
        r = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "sport": "volleyboll",
            "resultat": "3-1", "mellan": "25-21"})
        self.assertIn("set: 25-21", r["md"])
        self.assertNotIn("halvtid:", r["md"])
        self.assertIn("sport: volleyboll", r["md"])

    def test_innehall_md_match_figurer_anvander_sport_sokvag(self):
        # Bildgalleriet: referensen i markdownen ska ALLTID vara den
        # kanoniska webbsökvägen (/sport/<slug>/<n>.jpg) — ALDRIG den lokala
        # källfilen (figurer[i].bild), även om en sådan är satt.
        r = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "resultat": "6-0",
            "figurer": [{"bild": "/Users/stig/Desktop/DSC_0001.NEF",
                        "alt": "Jubel", "bildtext": "Mål!"}]})
        self.assertIn("/sport/a-b/1.jpg", r["md"])
        self.assertNotIn("DSC_0001.NEF", r["md"])
        self.assertIn('bilder:\n  - "/sport/a-b/1.jpg"', r["md"])

    def test_innehall_md_landskap_event_skriver_bilder_array(self):
        # Landskap & Event skriver nu (precis som match) en `bilder:`-
        # frontmatter-array — det är den ENDA bildkällan sajtens landskap/
        # event-sidor renderar (hero = bilder[0], galleri = resten). Utan den
        # blev korten/detaljsidorna bildlösa. Referensen är den kanoniska
        # /bilder/{slug}/{n}.jpg (eller R2-URL vid nätpublicering), ALDRIG den
        # lokala källfilen.
        for typ in ("landskap", "event"):
            r = self.api.forhandsgranska_innehall({
                "typ": typ, "titel": "Grönt",
                "figurer": [{"bild": "/Users/stig/Desktop/DSC_0001.NEF"}]})
            self.assertIn("/bilder/gront/1.jpg", r["md"])
            self.assertNotIn("DSC_0001.NEF", r["md"])
            self.assertIn('bilder:\n  - "/bilder/gront/1.jpg"', r["md"])

    def test_innehall_md_sportevent(self):
        # Sportevent (skiss 1e): egen hero, bild-only-galleri (bilder:-array)
        # och underartiklar (slug-referenser) i frontmattern.
        r = self.api.forhandsgranska_innehall({
            "typ": "sportevent", "titel": "SM-veckan Borlänge",
            "period": "29 jun – 5 jul", "plats": "Borlänge",
            "ingress": "En vecka av allt.",
            "figurer": [{"bild": "/Users/stig/DSC_1.NEF", "alt": "x", "bildtext": "y"}],
            "underartiklar": [{"titel": "MFF – Kristianstad",
                               "slug": "mff-kristianstad", "match_id": "m1"}]})
        self.assertEqual(r["slug"], "sm-veckan-borlange")
        self.assertIn("typ: sportevent", r["md"])
        self.assertIn("period: 29 jun – 5 jul", r["md"])
        self.assertIn("underartiklar:", r["md"])
        self.assertIn("mff-kristianstad", r["md"])
        # bild-only: härledd referens, aldrig källfilen, ingen bildtext
        self.assertIn("/bilder/sm-veckan-borlange/1.jpg", r["md"])
        self.assertNotIn("DSC_1.NEF", r["md"])
        self.assertNotIn("*y*", r["md"])
        # spara accepteras av schemat (v23)
        res = self.api.spara_innehall({"typ": "sportevent", "titel": "SM-veckan"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.api.lista_innehall("sportevent")[0]["typ"], "sportevent")

    def test_publicera_natet_sportevent_laddar_upp_och_publicerar(self):
        # Sportevent nätpubliceras nu (worker + Astro fick typen): hero +
        # galleribilder laddas upp till R2 och frontmatterns bilder[] pekar dit.
        import os, tempfile
        from unittest import mock
        d = tempfile.mkdtemp()
        b1 = os.path.join(d, "a.jpg")
        with open(b1, "wb") as fh:
            fh.write(b"x")
        fejk = mock.MagicMock()
        fejk.ladda_upp_bild.side_effect = \
            lambda typ, slug, kalla, namn, **kw: f"https://r2.example/{typ}/{slug}/{namn}"
        fejk.publicera.return_value = {"ok": True}
        self.api.innehall_synk = fejk
        r = self.api.publicera_innehall_natet({
            "typ": "sportevent", "titel": "SM-veckan Borlänge",
            "period": "29 jun – 5 jul", "figurer": [{"bild": b1}],
            "underartiklar": [{"titel": "A – B", "slug": "a-b", "match_id": "m1"}]})
        self.assertTrue(r["ok"])
        _, kwargs = fejk.publicera.call_args
        self.assertEqual(kwargs["typ"] if "typ" in kwargs else fejk.publicera.call_args[0][0],
                         "sportevent")
        self.assertEqual(kwargs["frontmatter"]["bilder"],
                         ["https://r2.example/sportevent/sm-veckan-borlange/1.jpg"])
        self.assertEqual(kwargs["frontmatter"]["underartiklar"][0]["slug"], "a-b")

    def test_sportevent_bunden_tavling_fyller_underartiklar(self):
        # Sportevent bundet till en tävling (tavling_id): tävlingens matcher
        # hamnar automatiskt som underartiklar — utan att UI:t skickar dem.
        self.api.spara_match({"lag_hemma": "Litauen", "lag_borta": "Sverige",
                              "liga": "European League 2026", "sport": "volleyboll",
                              "datum": "2026-06-12"})
        self.api.spara_match({"lag_hemma": "Sverige", "lag_borta": "Bosnien",
                              "liga": "European League 2026", "sport": "volleyboll",
                              "datum": "2026-06-14"})
        tid = self.api.lista_matcher()[0]["tavling_id"]
        r = self.api.forhandsgranska_innehall({
            "typ": "sportevent", "titel": "(D) Volleyboll - European League",
            "tavling_id": tid, "underartiklar": []})
        self.assertIn("underartiklar:", r["md"])
        self.assertIn("Litauen – Sverige", r["md"])
        self.assertIn("litauen-sverige", r["md"])
        self.assertIn("Sverige – Bosnien", r["md"])
        # tavling_id sparas i frontmattern så bindningen överlever ompublicering
        self.assertIn("tavling_id:", r["md"])

    def test_sportevent_bunden_tavling_ror_ej_manuellt_valda(self):
        # Manuellt tillagd match dupliceras inte, och tavling_id=None gör inget.
        self.api.spara_match({"lag_hemma": "Litauen", "lag_borta": "Sverige",
                              "liga": "European League 2026", "sport": "volleyboll",
                              "datum": "2026-06-12"})
        rad = self.api.lista_matcher()[0]
        tid, mid = rad["tavling_id"], rad["id"]
        r = self.api.forhandsgranska_innehall({
            "typ": "sportevent", "titel": "EL", "tavling_id": tid,
            "underartiklar": [{"titel": "Litauen – Sverige",
                               "slug": "litauen-sverige", "match_id": mid}]})
        self.assertEqual(r["md"].count(mid), 1)   # inte duplicerad
        # Utan bindning: inga automatiska pålägg.
        utan = self.api.forhandsgranska_innehall({
            "typ": "sportevent", "titel": "EL", "underartiklar": []})
        self.assertNotIn("Litauen – Sverige", utan["md"])

    def test_innehall_md_match_topp_flagga(self):
        # Startside-kureringen: topp följer med frontmattern (och utelämnas
        # när den inte är satt — sajtens zod-schema defaultar till false).
        med = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "hem": "A", "borta": "B", "topp": True})
        self.assertIn("topp: true", med["md"])
        utan = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "hem": "A", "borta": "B"})
        self.assertNotIn("topp", utan["md"])

    def test_innehall_md_match_event_flagga(self):
        # p.5: heldagsevent (match utan motståndare) → event: true i frontmatter
        # så sajten kan rendera utan "– borta"/resultat.
        ev = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "Partille Cup", "hem": "Partille Cup", "borta": ""})
        self.assertIn("event: true", ev["md"])
        # riktig match (borta ifyllt) → ingen event-flagga
        match = self.api.forhandsgranska_innehall({
            "typ": "match", "titel": "A – B", "hem": "A", "borta": "B", "resultat": "1-0"})
        self.assertNotIn("event:", match["md"])

    def test_sport_topp_sparas_och_speglas(self):
        # Valet persisteras i installning; skarpt läge speglar till workern via
        # innehall_synk.satt_topp (fejkad här), testläge rör den aldrig.
        class FejkSynk:
            def __init__(self):
                self.anrop = []
            def satt_topp(self, typ, vald_id):
                self.anrop.append((typ, vald_id))
                return {"ok": True, "andrade": 1, "fel": None}
        fejk = FejkSynk()
        self.api.innehall_synk = fejk
        r = self.api.satt_sport_topp("valj", "i9")
        self.assertTrue(r["ok"])
        self.assertEqual(fejk.anrop, [("match", "i9")])
        t = self.api.sport_topp()
        self.assertEqual(t["lage"], "valj")
        self.assertEqual(t["innehall_id"], "i9")
        # 'senaste' → rensa flaggan på workern (vald=None)
        self.api.satt_sport_topp("senaste")
        self.assertEqual(fejk.anrop[-1], ("match", None))
        # testläge: bara lokal persist, inget synk-anrop
        innan = len(fejk.anrop)
        self.api.satt_sport_topp("valj", "i2", True)
        self.assertEqual(len(fejk.anrop), innan)
        self.assertEqual(self.api.sport_topp()["innehall_id"], "i2")

    def test_publicera_natet_event_laddar_upp_bilder_till_r2(self):
        # Regression: event-publicering laddade aldrig upp galleribilderna till
        # R2 och skrev ingen bilder:-array → sajtens kort/detaljsida blev
        # bildlösa (den lokala källsökvägen hamnade i brödtexten i stället).
        # Nu laddas varje figur upp och frontmatterns bilder[] pekar på R2.
        import os, tempfile
        from unittest import mock
        d = tempfile.mkdtemp()
        b1, b2 = os.path.join(d, "a.jpg"), os.path.join(d, "b.jpg")
        for p in (b1, b2):
            with open(p, "wb") as fh:
                fh.write(b"x")
        fejk = mock.MagicMock()
        fejk.ladda_upp_bild.side_effect = \
            lambda typ, slug, kalla, namn, **kw: f"https://r2.example/{typ}/{slug}/{namn}"
        fejk.publicera.return_value = {"ok": True}
        self.api.innehall_synk = fejk
        r = self.api.publicera_innehall_natet({
            "typ": "event", "titel": "Maya i Lund", "kategori": "Porträtt",
            "kund": "Maya", "figurer": [{"bild": b1}, {"bild": b2}]})
        self.assertTrue(r["ok"])
        self.assertEqual(fejk.ladda_upp_bild.call_count, 2)      # båda uppladdade
        _, kwargs = fejk.publicera.call_args
        self.assertEqual(kwargs["frontmatter"]["bilder"],
                         ["https://r2.example/event/maya-i-lund/1.jpg",
                          "https://r2.example/event/maya-i-lund/2.jpg"])
        self.assertNotIn(b1, kwargs["body"])                    # ingen lokal läcka


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
        self.uppdaterade = []
        self.beskrivningar = {}      # jobb-id → description hos "tjänsten"
        self.jobb = []               # svar för lista_jobb
        self.mail = []               # skickade (till, amne, kropp)
        self.mail_svar = {"ok": True, "status": 200, "fel": None}

    def har_nyckel(self):
        return True

    def halsa(self):
        return True

    def lista_jobb(self):
        return self.jobb

    def hamta_jobb(self, jid):
        return {"ok": True, "jobb": {"id": jid,
                                     "description": self.beskrivningar.get(jid, "")}}

    def skapa_jobb(self, jobb):
        self.skapade.append(jobb)
        return {"ok": True, "jobb": {**jobb, "id": f"remote{len(self.skapade)}",
                                     "google_event_id": "g1"}}

    def uppdatera_jobb(self, jid, jobb):
        self.uppdaterade.append((jid, jobb))
        return {"ok": True}

    def radera_jobb(self, jid):
        self.raderade.append(jid)
        return {"ok": True}

    def skicka_mail(self, till, amne, kropp):
        self.mail.append((till, amne, kropp))
        return dict(self.mail_svar)


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

    def test_notering_pa_utkast_sparas_lokalt(self):
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        self.api.kalender = _FakeKalender()
        self.api.spara_fotojobb({"id": uid, "utkast": True, "notering": "Kund: Anna"})
        self.assertEqual(self.api.lista_fotojobb()[0]["notering"], "Kund: Anna")
        self.assertEqual(self.api.kalender.skapade, [])   # rörde aldrig tjänsten

    def test_notering_synkas_som_description(self):
        """Ägarens beslut 2026-07-11: anteckningen synkas till Google igen —
        som event-description via kalendertjänsten. Den lokala fallback-raden
        städas när noten väl bor hos tjänsten."""
        self.api.kalender = _FakeKalender()
        r = self.api.spara_fotojobb({"title": "Bröllop – Anna & Erik",
                                     "start_at": "2026-08-08T12:00",
                                     "notering": "Kund: Anna"})
        self.assertTrue(r["ok"])
        pushat = self.api.kalender.skapade[0]
        self.assertNotIn("notering", pushat)          # rått fält läcker inte
        self.assertEqual(pushat["description"], "Kund: Anna")
        self.assertEqual(
            store.noteringar_for_fotojobb(self.api.conn, ["remote1"]), {})

    def test_notering_lases_ur_description(self):
        """Tvåvägs: en not skriven i Google Calendar (description) visas som
        jobbets notering — och DPT:s resultatblock räknas INTE som not."""
        fake = _FakeKalender()
        fake.jobb = [{"id": "remote1", "title": "Match", "start_at": "2026-08-15",
                      "end_at": "2026-08-15", "all_day": True, "status": "confirmed",
                      "google_event_id": "g1",
                      "description": "Ta med 400/2.8\n\nSlutresultat 6–0 (3–0)\nMål: Hansson 2"}]
        self.api.kalender = fake
        jobb = self.api.lista_fotojobb()
        self.assertEqual(jobb[0]["notering"], "Ta med 400/2.8")

    def test_gammal_lokal_notering_visas_som_fallback(self):
        """Noter skrivna före description-synken (bara i lokala tabellen)
        ska inte försvinna ur listan innan jobbet sparats om."""
        fake = _FakeKalender()
        fake.jobb = [{"id": "remote1", "title": "Bröllop", "start_at": "2026-08-08",
                      "end_at": "2026-08-08", "all_day": True, "status": "confirmed",
                      "google_event_id": "g1", "description": ""}]
        self.api.kalender = fake
        store.satt_fotojobb_notering(self.api.conn, "remote1", "Kund: Anna")
        self.assertEqual(self.api.lista_fotojobb()[0]["notering"], "Kund: Anna")

    def test_radera_jobb_stadar_noteringen(self):
        self.api.kalender = _FakeKalender()
        store.satt_fotojobb_notering(self.api.conn, "remote1", "Kund: Anna")
        self.api.radera_fotojobb("remote1")
        self.assertEqual(store.noteringar_for_fotojobb(self.api.conn, ["remote1"]), {})

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

    def test_aktivera_synk_tar_med_notering_och_flyttar_matchlank(self):
        """Noteringen följer med som description och match-kopplingen flyttas
        till det nya jobbets id — tidigare orphanades båda på utkast-id:t."""
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        mid = store.spara_match(self.api.conn, {"lag_hemma": "A", "lag_borta": "B"})
        self.api.kalender = _FakeKalender()
        self.api.spara_fotojobb({"id": uid, "utkast": True,
                                 "notering": "Ackreditering klar", "match_id": mid})
        r = self.api.aktivera_synk_fotojobb(uid)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.kalender.skapade[0]["description"],
                         "Ackreditering klar")
        self.assertEqual(store.matchref_for_fotojobb(self.api.conn, ["remote1"]),
                         {"remote1": mid})
        self.assertEqual(store.matchref_for_fotojobb(self.api.conn, [uid]), {})
        self.assertEqual(store.noteringar_for_fotojobb(self.api.conn, [uid]), {})

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
        # skapade rymmer även ackrediteringspåminnelsen — räkna bara jobben
        jobb = [j for j in self.fake.skapade
                if "Begär ackreditering" not in j["title"]]
        self.assertEqual(len(jobb), 1)
        self.assertEqual(r1["synk_jobb_id"], r2["synk_jobb_id"])

    def test_synk_av_tar_bort_jobb_och_lank(self):
        self.api.satt_match_synk(self.mid, True)
        r = self.api.satt_match_synk(self.mid, False)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["synk_jobb_id"])
        # jobbet + dess ackrediteringspåminnelse städas (ordningen kvittar)
        self.assertEqual(sorted(self.fake.raderade), ["remote1", "remote2"])
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
        jobb = [j for j in self.fake.skapade
                if "Begär ackreditering" not in j["title"]]
        self.assertEqual(len(jobb), 1)

    def test_radera_match_tar_bort_kalenderjobb_och_lankar(self):
        self.api.satt_match_synk(self.mid, True)
        r = self.api.radera_match(self.mid)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.lista_matcher(), [])
        # både jobbet OCH dess ackrediteringspåminnelse städas hos tjänsten
        self.assertIn("remote1", self.fake.raderade)
        self.assertIn("remote2", self.fake.raderade)   # påminnelsen
        self.assertEqual(
            store.matchref_for_fotojobb(self.api.conn, ["remote1"]), {})

    def test_radera_match_rensar_aktiv_match(self):
        self.api.satt_aktiv_match(self.mid)
        self.api.radera_match(self.mid)
        self.assertIsNone(self.api.aktiv_match())

    def test_redigering_uppdaterar_lankat_jobb_med_resultatblock(self):
        # Ägarens beslut 2026-07-11 (upphäver §9-låset): redigering pushar
        # uppdaterat jobb, och finns ett slutresultat skrivs det som
        # resultatblock i description — titel/plats hålls fortsatt rena.
        self.api.satt_match_synk(self.mid, True)
        self.assertEqual(self.fake.uppdaterade, [])
        m = store.hamta_match(self.api.conn, self.mid)
        m["arena"] = "Ny arena"
        m["resultat"] = "6-0"
        m["mellan"] = "3-0"
        self.api.spara_match(m)
        # uppdaterade kan även rymma ackrediteringspåminnelsen — plocka jobbet
        upp = [(i, j) for (i, j) in self.fake.uppdaterade if i == "remote1"]
        self.assertEqual(len(upp), 1)
        jid, jobb = upp[0]
        self.assertEqual(jobb["location"], "Ny arena")
        self.assertEqual(jobb["title"], "Malmö FF – FC Rosengård")
        self.assertEqual(jobb["description"], "Slutresultat 6-0 (3-0)")

    def test_matchsynk_bevarar_notering_i_description(self):
        # PUT hos tjänsten ersätter hela jobbet — fotografens anteckning i
        # description måste läsas upp och skrivas tillbaka framför blocket.
        self.api.satt_match_synk(self.mid, True)
        self.fake.beskrivningar["remote1"] = "Ta med 400/2.8"
        r = self.api.satt_resultat(self.mid, "2-1", "1-1", "Berg 55', Ali 78'")
        self.assertTrue(r["ok"])
        jid, jobb = self.fake.uppdaterade[-1]
        self.assertEqual(jid, "remote1")
        self.assertEqual(jobb["description"],
                         "Ta med 400/2.8\n\nSlutresultat 2-1 (1-1)\nMål: Berg 55', Ali 78'")

    def test_gammalt_resultatblock_skrivs_om_inte_dubblas(self):
        # Körs synken två gånger ska blocket ersättas, inte staplas.
        self.api.satt_match_synk(self.mid, True)
        self.fake.beskrivningar["remote1"] = ("Ta med 400/2.8\n\n"
                                              "Slutresultat 1-0")
        self.api.satt_resultat(self.mid, "2-1", "", "")
        jid, jobb = self.fake.uppdaterade[-1]
        self.assertEqual(jobb["description"], "Ta med 400/2.8\n\nSlutresultat 2-1")

    def test_spara_utan_lankat_jobb_pushar_inget(self):
        mid = self.api.spara_match({"lag_hemma": "A", "lag_borta": "B",
                                    "datum": "2026-08-20", "sport": "fotboll"})["id"]
        self.assertEqual(self.fake.uppdaterade, [])


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


class FejkInnehallSynkLogga:
    """Bara det logga_url_for_lag rör."""
    def __init__(self, nyckel=True, url="https://x.dev/bilder/lag/malmo-ff/l.png"):
        self._nyckel, self._url = nyckel, url
        self.uppladdningar = []          # [(slug, sokvag)]

    def har_nyckel(self):
        return self._nyckel

    def ladda_upp_logga(self, slug, sokvag, **kw):
        self.uppladdningar.append((slug, str(sokvag)))
        return self._url


class TestLagLoggaTillR2(unittest.TestCase):
    """Molnrendern läser laglogotyper ur R2 — utan URL faller den TYST tillbaka
    på monogram-badge i stället för klubbmärket."""

    def setUp(self):
        self.api = Api(db_path=":memory:")
        self.synk = FejkInnehallSynkLogga()
        self.api.innehall_synk = self.synk

    def _lag(self, namn="Malmö FF", **extra):
        lid = store.upsert_lag(self.api.conn, namn, **extra)
        return next(l for l in store.lista_lag(self.api.conn) if l["id"] == lid)

    def test_laddar_upp_och_sparar_url(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            logga = P(tmp) / "l.png"
            logga.write_bytes(b"x")
            lag = self._lag(logga=str(logga))
            url = self.api.logga_url_for_lag(lag)
            self.assertEqual(url, self.synk._url)
            # persisterad → nästa gång görs inget nätanrop
            farsk = next(l for l in store.lista_lag(self.api.conn) if l["id"] == lag["id"])
            self.assertEqual(farsk["logga_url"], self.synk._url)

    def test_idempotent_ingen_ny_uppladdning(self):
        lag = self._lag()
        lag["logga_url"] = "https://x.dev/redan.png"
        self.assertEqual(self.api.logga_url_for_lag(lag), "https://x.dev/redan.png")
        self.assertEqual(self.synk.uppladdningar, [])

    def test_lag_utan_logga_ger_tom_strang(self):
        # Inget att ladda upp → monogram är RÄTT, inte ett fel.
        lag = self._lag(namn="Klubb Utan Logga XYZ")
        self.assertEqual(self.api.logga_url_for_lag(lag), "")
        self.assertEqual(self.synk.uppladdningar, [])

    def test_utan_nyckel_ingen_uppladdning(self):
        self.api.innehall_synk = FejkInnehallSynkLogga(nyckel=False)
        self.assertEqual(self.api.logga_url_for_lag(self._lag()), "")

    def test_misslyckad_uppladdning_faller_inte_synken(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            logga = P(tmp) / "l.png"; logga.write_bytes(b"x")
            self.synk._url = None                      # uppladdning misslyckas
            self.assertEqual(self.api.logga_url_for_lag(self._lag(logga=str(logga))), "")

    def test_paket_bar_med_logga_urlarna(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            logga = P(tmp) / "l.png"; logga.write_bytes(b"x")
            self._lag("Malmö FF", logga=str(logga))
            self._lag("Testlag Utan Logga ZZZ")        # saknar logga → tom sträng
            mid = self.api.spara_match({"lag_hemma": "Malmö FF",
                                        "lag_borta": "Testlag Utan Logga ZZZ",
                                        "datum": "2099-08-01", "sport": "fotboll"})["id"]
            m = store.hamta_match(self.api.conn, mid)
            p = self.api._match_till_paket(m)
            self.assertEqual(p["lag_hemma_logga_url"], self.synk._url)
            self.assertEqual(p["lag_borta_logga_url"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ── Mobil Live (steg 3: desktop-krokarna) ───────────────────────────────────

class FejkLiveSynk:
    """Står in för LiveSynk i Api — inget nät, allt observerbart."""

    def __init__(self, nyckel=True, live=None, fjarrlista=None):
        self._nyckel = nyckel
        self.live = live                 # svaret från hamta()
        self.fjarrlista = fjarrlista or []
        self.pushade_falt = []           # [(match_id, falt)]
        self.pushade_paket = []          # [(match_id, paket)]
        self.pushade_jobb = []           # [lista] per push_jobb-anrop
        self.raderade = []

    def har_nyckel(self):
        return self._nyckel

    def hamta(self, match_id):
        return self.live

    def lista(self):
        return self.fjarrlista

    def push_falt(self, match_id, falt, *, tid=None):
        self.pushade_falt.append((match_id, falt))
        return {"ok": True}

    def push_paket(self, match_id, paket):
        self.pushade_paket.append((match_id, paket))
        return {"ok": True}

    def radera_paket(self, match_id):
        self.raderade.append(match_id)
        return {"ok": True, "borttagen": True}

    def push_jobb(self, jobb):
        self.pushade_jobb.append(jobb)
        return {"ok": True, "antal": len(jobb)}


class TestFotojobbSynk(unittest.TestCase):
    """synka_fotojobb trimmar lista_fotojobb till app-fält + härleder status."""

    def setUp(self):
        self.api = Api(db_path=":memory:")
        self.fake = FejkLiveSynk()
        self.api.live_synk = self.fake

    def test_synka_pushar_trimmade_jobb_med_status(self):
        # Ett riktigt jobb + ett utkast → bokad resp. offert.
        self.api.lista_fotojobb = lambda: [
            {"id": "g1", "title": "Bröllop – Anna", "start_at": "2026-08-15T14:00:00",
             "end_at": None, "all_day": False, "location": "Sofiero",
             "category": "Bröllop", "notering": "Kund: Anna", "match_id": None,
             "utkast": False},
            {"id": "u1", "title": "Offert lagfoto", "start_at": None, "end_at": None,
             "all_day": True, "location": "", "category": "Sport",
             "notering": "", "match_id": "m1", "utkast": True},
        ]
        r = self.api.synka_fotojobb()
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.fake.pushade_jobb), 1)
        pushat = self.fake.pushade_jobb[0]
        self.assertEqual(pushat[0]["status"], "bokad")
        self.assertEqual(pushat[0]["titel"], "Bröllop – Anna")
        self.assertEqual(pushat[0]["plats"], "Sofiero")
        self.assertEqual(pushat[1]["status"], "offert")
        self.assertEqual(pushat[1]["match_id"], "m1")
        # Bara app-fält — inga råa Google-fält läcker igenom.
        self.assertNotIn("google_event_id", pushat[0])
        self.assertNotIn("description", pushat[0])

    def test_synka_utan_nyckel(self):
        self.api.live_synk = FejkLiveSynk(nyckel=False)
        self.assertFalse(self.api.synka_fotojobb()["ok"])

    def _skapa_utkast(self, category="Sport"):
        """Skapar ett riktigt fotojobb-utkast (tävling → kalender-utkast) och
        stubbar bort Google-kalendern så lista_fotojobb inte når nätet. Sätter en
        kategori så jobbet passerar app-filtret (_ar_appjobb)."""
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan", "sport": "fotboll",
                                "fran": "2026-04-01", "till": "2026-10-31"})
        uid = self.api.lagg_tavling_i_kalender("obos-damallsvenskan")["utkast_id"]
        self.api.kalender = _FakeKalender()
        if category:
            self.api.spara_fotojobb({"id": uid, "utkast": True, "category": category,
                                     "start_at": "2026-12-01T14:00:00"})
        return uid

    def test_lista_fotojobb_auto_synkar(self):
        # Panelen laddar om via lista_fotojobb → jobben ska pushas automatiskt,
        # utan att synka_fotojobb anropas explicit.
        uid = self._skapa_utkast()
        self.assertEqual(self.fake.pushade_jobb, [])   # inget pushat än
        jobb = self.api.lista_fotojobb()
        self.assertTrue(any(j.get("id") == uid for j in jobb))
        self.assertEqual(len(self.fake.pushade_jobb), 1)   # auto-synk
        self.assertTrue(any(j["id"] == uid for j in self.fake.pushade_jobb[0]))

    def test_auto_synk_ingen_dubbelpush_via_synka(self):
        # synka_fotojobb anropar lista_fotojobb internt — reentrancy-guarden ska
        # se till att det blir EN push, inte två.
        self._skapa_utkast()
        self.fake.pushade_jobb.clear()
        self.api.synka_fotojobb()
        self.assertEqual(len(self.fake.pushade_jobb), 1)

    def test_lista_utan_nyckel_ingen_synk(self):
        self._skapa_utkast()
        self.api.live_synk = FejkLiveSynk(nyckel=False)
        self.api.lista_fotojobb()
        self.assertEqual(self.api.live_synk.pushade_jobb, [])

    def test_okategoriserade_jobb_filtreras_bort(self):
        # Kalenderns matchfixturer/privat (utan kategori) ska INTE nå appen;
        # bara triageade uppdrag (med kategori). _ar_appjobb är regeln.
        from dpt2.app import _ar_appjobb
        self.assertTrue(_ar_appjobb({"category": "Event", "start_at": "2026-08-15"}))
        self.assertTrue(_ar_appjobb({"category": "Sport"}))                 # utan datum
        self.assertFalse(_ar_appjobb({"category": "", "start_at": "2026-08-15"}))
        self.assertFalse(_ar_appjobb({"start_at": "2026-08-15"}))          # ingen kategori
        self.assertFalse(_ar_appjobb({"category": "Sport", "start_at": "2019-01-01"}))  # gammalt


class TestMobilLive(unittest.TestCase):
    def setUp(self):
        self.api = Api(db_path=":memory:")
        self.fake = FejkLiveSynk()
        self.api.live_synk = self.fake

    def _match(self, **extra):
        m = {"lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
             "datum": "2099-08-01", "tid": "18:00", "arena": "Eleda Stadion",
             "sport": "fotboll"}
        m.update(extra)
        return self.api.spara_match(m)["id"]

    # ── paket ────────────────────────────────────────────────────────────────
    def test_paket_har_sportprofil_och_avspark(self):
        mid = self._match()
        m = store.hamta_match(self.api.conn, mid)
        p = self.api._match_till_paket(m)
        self.assertEqual(p["lag_hemma"], "Malmö FF")
        self.assertEqual(p["avspark"], "2099-08-01T18:00:00")
        self.assertEqual(p["sportprofil"]["start_moment"], "Avspark")
        self.assertTrue(p["sportprofil"]["has_scorers"])

    def test_paket_for_sport_utan_malskyttar(self):
        mid = self._match(sport="volleyboll", lag_hemma="Sverige", lag_borta="Italien")
        m = store.hamta_match(self.api.conn, mid)
        p = self.api._match_till_paket(m)
        self.assertFalse(p["sportprofil"]["has_scorers"])
        self.assertEqual(p["sportprofil"]["mid_label"], "Setsiffror")

    def test_paket_roster_ratt_gren_vid_namnkrock(self):
        # Malmö FF finns som DAM och HERR — namn-nycklat lag-index kollapsade
        # dubbletterna och herrtruppen kunde hamna i dammatchens paket.
        dam = self.api.spara_lag({"namn": "Malmö FF", "sport": "fotboll",
                                  "gren": "dam"})["id"]
        herr = self.api.spara_lag({"namn": "Malmö FF", "sport": "fotboll",
                                   "gren": "herr"})["id"]
        store.upsert_lag(self.api.conn, "Malmö FF", id=dam, stall_hemma="#8fb7de")
        store.merge_lag_trupp(self.api.conn, dam,
                              [{"nr": "1", "namn": "Damspelare"}])
        store.merge_lag_trupp(self.api.conn, herr,
                              [{"nr": "1", "namn": "Herrspelare"}])
        mid = self._match(lag_hemma="Malmö FF", lag_hemma_id=dam,
                          lag_borta="Bröndby IF")
        m = store.hamta_match(self.api.conn, mid)
        p = self.api._match_till_paket(m)
        namn = [s["namn"] for s in p["roster"] if s["lag"] == "hemma"]
        self.assertEqual(namn, ["Damspelare"])          # inte herrtruppen
        self.assertEqual(p["lag_hemma_farg"], "#8fb7de")  # dam-lagets färg

    def test_paket_roster_fallback_per_sida(self):
        # Matchtrupp för BARA hemma får inte lämna bortalaget tomt — borta ska
        # falla tillbaka till lagets egen trupp (Bröndby-buggen).
        borta_id = self.api.spara_lag({"namn": "Bröndby IF", "sport": "fotboll",
                                       "gren": "dam"})["id"]
        store.merge_lag_trupp(self.api.conn, borta_id,
                              [{"nr": "9", "namn": "Bortaspelare"}])
        mid = self._match(lag_borta="Bröndby IF", lag_borta_id=borta_id,
                          spelare=[{"nr": "1", "namn": "Hemmaspelare",
                                    "lag": "hemma", "start": True}])
        m = store.hamta_match(self.api.conn, mid)
        roster = self.api._match_till_paket(m)["roster"]
        self.assertEqual([s["namn"] for s in roster if s["lag"] == "hemma"],
                         ["Hemmaspelare"])
        self.assertEqual([s["namn"] for s in roster if s["lag"] == "borta"],
                         ["Bortaspelare"])

    def test_paket_utan_tid_faller_tillbaka_pa_midnatt(self):
        mid = self._match(tid="")
        m = store.hamta_match(self.api.conn, mid)
        self.assertEqual(self.api._match_till_paket(m)["avspark"], "2099-08-01T00:00:00")

    def test_paket_utan_datum_ger_ingen_avspark(self):
        mid = self._match(datum="", tid="")
        m = store.hamta_match(self.api.conn, mid)
        self.assertIsNone(self.api._match_till_paket(m)["avspark"])

    def test_paket_roster_faller_tillbaka_pa_lagens_trupper(self):
        """Utan matchtrupp (skapas först vid "Hämta match") ska paketet bära
        LAGENS egna trupper — målskytt-väljaren i mobilen ska ha spelarna
        även för matcher som inte förberetts vid datorn."""
        hemma = self.api.spara_lag({"namn": "Malmö FF", "kind": "team", "sport": "fotboll"})["id"]
        self.api.spara_spelare(hemma, {"nr": "7", "namn": "Hansson", "position": ""})
        self.api.spara_spelare(hemma, {"nr": "9", "namn": "Berg", "position": ""})
        borta = self.api.spara_lag({"namn": "Kristianstads DFF", "kind": "team", "sport": "fotboll"})["id"]
        self.api.spara_spelare(borta, {"nr": "11", "namn": "Ali", "position": ""})
        mid = self._match()
        m = store.hamta_match(self.api.conn, mid)
        self.assertFalse(m.get("spelare"))          # premiss: ingen matchtrupp
        roster = self.api._match_till_paket(m)["roster"]
        self.assertEqual({(r["namn"], r["lag"]) for r in roster},
                         {("Hansson", "hemma"), ("Berg", "hemma"), ("Ali", "borta")})

    def test_paket_roster_foredrar_matchtruppen(self):
        hemma = self.api.spara_lag({"namn": "Malmö FF", "kind": "team", "sport": "fotboll"})["id"]
        self.api.spara_spelare(hemma, {"nr": "7", "namn": "Hansson", "position": ""})
        mid = self._match()
        store.merge_in_trupp(self.api.conn, mid,
                             [{"nr": "10", "namn": "Ivanovic", "lag": "hemma"}])
        m = store.hamta_match(self.api.conn, mid)
        roster = self.api._match_till_paket(m)["roster"]
        self.assertEqual([r["namn"] for r in roster], ["Ivanovic"])   # inte lagtruppen

    def test_synka_paket_pushar_kommande_och_stadar_bort_ovriga(self):
        mid = self._match()
        self.fake.fjarrlista = [{"match_id": mid}, {"match_id": "gammal-match"}]
        r = self.api.synka_live_paket()
        self.assertTrue(r["ok"])
        self.assertEqual(r["antal"], 1)
        self.assertEqual([m for m, _ in self.fake.pushade_paket], [mid])
        self.assertEqual(self.fake.raderade, ["gammal-match"])   # reconciliation
        self.assertEqual(r["borttagna"], 1)

    def test_synka_paket_stadar_inte_nar_push_failade(self):
        # Fjärrlistan är opålitlig om vår egen push inte gick igenom.
        self._match()
        self.fake.push_paket = lambda mid, p: {"ok": False, "fel": "nät nere"}
        self.fake.fjarrlista = [{"match_id": "gammal-match"}]
        r = self.api.synka_live_paket()
        self.assertFalse(r["ok"])
        self.assertEqual(self.fake.raderade, [])

    def test_synka_paket_utan_nyckel(self):
        self.api.live_synk = FejkLiveSynk(nyckel=False)
        self.assertFalse(self.api.synka_live_paket()["ok"])

    # ── hämta (poll) ─────────────────────────────────────────────────────────
    def test_hamta_live_serialiserar_malskyttar_till_appens_strang(self):
        self.fake.live = {"resultat": "2-0", "mellan": "1-0", "moment": "Målgörare",
                          "malskyttar": [{"namn": "Hansson", "minut": 14},
                                         {"namn": "Berg", "minut": None}],
                          "fors_fran": {"enhet": "mobil", "tid": "2026-07-10T19:42:00.000Z"},
                          "falt_uppdaterad": {"resultat": "2026-07-10T19:42:00.000Z"}}
        r = self.api.hamta_live("m1")
        self.assertEqual(r["live"]["malskyttar"], "Hansson 14', Berg")
        self.assertEqual(r["live"]["fors_fran"]["enhet"], "mobil")
        self.assertIn("resultat", r["live"]["falt_uppdaterad"])

    def test_hamta_live_tomt_state(self):
        self.fake.live = None
        self.assertIsNone(self.api.hamta_live("m1")["live"])

    # ── push vid satt_resultat ───────────────────────────────────────────────
    def _vanta_pa_push(self, n=1, timeout=2.0):
        import time
        slut = time.time() + timeout
        while time.time() < slut and len(self.fake.pushade_falt) < n:
            time.sleep(0.01)

    def test_satt_resultat_speglar_ut_till_mobil_live(self):
        mid = self._match()
        self.api.satt_resultat(mid, "3-1", "1-1", "Hansson 14', Berg")
        self._vanta_pa_push()
        self.assertEqual(len(self.fake.pushade_falt), 1)
        pushad_id, falt = self.fake.pushade_falt[0]
        self.assertEqual(pushad_id, mid)
        self.assertEqual(falt["resultat"], "3-1")
        # strängen översätts till strukturerade poster för molnet
        self.assertEqual([(p["namn"], p["minut"]) for p in falt["malskyttar"]],
                         [("Hansson", 14), ("Berg", None)])
        self.assertEqual(falt["fors_fran"]["enhet"], "desktop")

    def test_satt_resultat_bevarar_lag_och_nr_mobilen_satt(self):
        mid = self._match()
        self.fake.live = {"malskyttar": [{"namn": "Hansson", "minut": 14,
                                          "lag": "hemma", "nr": 7}]}
        self.api.satt_resultat(mid, "1-0", "", "Hansson 14'")
        self._vanta_pa_push()
        _mid, falt = self.fake.pushade_falt[0]
        self.assertEqual(falt["malskyttar"][0]["nr"], 7)
        self.assertEqual(falt["malskyttar"][0]["lag"], "hemma")

    def test_satt_resultat_sparar_lokalt_aven_utan_nyckel(self):
        self.api.live_synk = FejkLiveSynk(nyckel=False)
        mid = self._match()
        self.assertTrue(self.api.satt_resultat(mid, "1-0", "", "")["ok"])
        self.assertEqual(store.hamta_match(self.api.conn, mid)["resultat"], "1-0")

    def test_satt_resultat_svaljer_synkfel(self):
        # Nätet nere får ALDRIG välta resultat-remsans autospar.
        class Trasig(FejkLiveSynk):
            def push_falt(self, *a, **k):
                raise OSError("nät nere")
        self.api.live_synk = Trasig()
        mid = self._match()
        self.assertTrue(self.api.satt_resultat(mid, "2-0", "", "")["ok"])
        self.assertEqual(store.hamta_match(self.api.conn, mid)["resultat"], "2-0")


class TestAckreditering(unittest.TestCase):
    """Fotoackreditering (handoff "Ackreditering"): status per matchjobb,
    "begär senast" ur arrangörens regel, mailväg B och kalenderpåminnelsen."""

    def setUp(self):
        self.api = Api(db_path=":memory:")
        self.fake = _FakeKalender()
        self.api.kalender = self.fake

    def _matchjobb(self, *, ackr_dagar=14, press="press@obos.se",
                   datum="2026-07-19"):
        """Tävling med regler + match + synkat kalenderjobb → jobbets id."""
        self.api.spara_tavling({"namn": "OBOS Damallsvenskan",
                                "sport": "fotboll", "press_email": press,
                                "ackr_dagar": ackr_dagar})
        mid = self.api.spara_match({
            "lag_hemma": "Malmö FF", "lag_borta": "Kristianstads DFF",
            "datum": datum, "tid": "14:00", "sport": "fotboll",
            "liga": "OBOS Damallsvenskan"})["id"]
        r = self.api.satt_match_synk(mid, True)
        self.assertTrue(r["ok"])
        jid = r["synk_jobb_id"]
        # Speglar tjänsten: matchjobbet finns i lista_jobb-svaret.
        self.fake.jobb = [{**self.fake.skapade[0], "id": jid,
                           "status": "confirmed"}]
        return jid

    def test_paminnelse_skapas_vid_synk(self):
        # Ej begärd + regel ger datum → heldagspåminnelse hos tjänsten
        # (matchdatum − ackr_dagar), markerad som intern.
        self._matchjobb(ackr_dagar=14, datum="2026-07-19")
        pam = [j for j in self.fake.skapade
               if "Begär ackreditering" in j["title"]]
        self.assertEqual(len(pam), 1)
        self.assertEqual(pam[0]["start_at"], "2026-07-05")
        self.assertTrue(pam[0]["all_day"])
        self.assertIn("[dpt-ackr-paminnelse]", pam[0]["description"])

    def test_lista_blandar_in_ackreditering_bara_for_sport(self):
        jid = self._matchjobb()
        self.fake.jobb.append({"id": "j-land", "title": "Landskap",
                               "category": "Landskap", "status": "confirmed",
                               "start_at": "2026-07-12T04:30:00",
                               "end_at": "2026-07-12T06:00:00"})
        jobb = {j["id"]: j for j in self.api.lista_fotojobb()}
        self.assertEqual(jobb[jid]["ackreditering"],
                         {"status": "ejbegard", "note": ""})
        self.assertEqual(jobb[jid]["begar_senast"], "2026-07-05")
        self.assertEqual(jobb[jid]["press_email"], "press@obos.se")
        self.assertNotIn("ackreditering", jobb["j-land"])   # bara Sport

    def test_paminnelse_event_doljs_i_listan(self):
        jid = self._matchjobb()
        pam = next(j for j in self.fake.skapade
                   if "Begär ackreditering" in j["title"])
        self.fake.jobb.append({**pam, "id": "rem1", "status": "confirmed"})
        ider = [j["id"] for j in self.api.lista_fotojobb()]
        self.assertIn(jid, ider)
        self.assertNotIn("rem1", ider)

    def test_status_styr_paminnelsen(self):
        jid = self._matchjobb()
        pam_id = store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"]
        self.assertTrue(pam_id)
        # Beviljad → påminnelsen raderas hos tjänsten och id:t släpps.
        r = self.api.satt_ackreditering(jid, status="beviljad")
        self.assertEqual(r["ackreditering"]["status"], "beviljad")
        self.assertIn(pam_id, self.fake.raderade)
        self.assertIsNone(store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"])
        # Tillbaka till Ej begärd → ny påminnelse skapas.
        self.api.satt_ackreditering(jid, status="ejbegard")
        self.assertTrue(store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"])

    def test_note_ror_inte_status(self):
        jid = self._matchjobb()
        self.api.satt_ackreditering(jid, status="begard")
        r = self.api.satt_ackreditering(jid, note="Väst vid mittlinjen")
        self.assertEqual(r["ackreditering"],
                         {"status": "begard", "note": "Väst vid mittlinjen"})

    def test_skicka_mail_satter_begard(self):
        jid = self._matchjobb()
        r = self.api.skicka_ackr_mail(jid, "press@obos.se",
                                      "Ackreditering – Malmö FF", "Hej")
        self.assertTrue(r["ok"])
        self.assertEqual(r["ackreditering"]["status"], "begard")
        self.assertEqual(self.fake.mail, [("press@obos.se",
                                           "Ackreditering – Malmö FF", "Hej")])
        # Begärd → påminnelsen är borttagen.
        self.assertIsNone(store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"])

    def test_skicka_mail_validerar_och_ror_inget_vid_fel(self):
        jid = self._matchjobb()
        self.assertFalse(self.api.skicka_ackr_mail(jid, "", "Ämne", "x")["ok"])
        self.assertFalse(self.api.skicka_ackr_mail(jid, "a@b.se", " ", "x")["ok"])
        self.fake.mail_svar = {"ok": False, "status": 502,
                               "fel": "Gmail-behörighet saknas"}
        r = self.api.skicka_ackr_mail(jid, "a@b.se", "Ämne", "x")
        self.assertFalse(r["ok"])
        self.assertIn("Gmail", r["fel"])
        # misslyckat utskick → status orörd (fortfarande Ej begärd)
        self.assertEqual(store.hamta_ackreditering(self.api.conn, jid)["status"],
                         "ejbegard")

    def test_utan_regel_faller_tillbaka_pa_default(self):
        # Arrangör utan ackr_dagar → 10 dagar (handoff §5 default-fallback).
        jid = self._matchjobb(ackr_dagar=None, datum="2026-07-19")
        j = next(x for x in self.api.lista_fotojobb() if x["id"] == jid)
        self.assertEqual(j["begar_senast"], "2026-07-09")

    def test_hemmaklubben_vinner_over_tavlingens_regel(self):
        # Seriespel: hemmaklubben hanterar ackrediteringen för sina
        # hemmamatcher — klubbens fält vinner över tävlingens.
        self.api.spara_lag({"namn": "Malmö FF", "sport": "fotboll",
                            "press_email": "press@mff.se", "ackr_dagar": 7})
        jid = self._matchjobb(ackr_dagar=14, press="press@obos.se",
                              datum="2026-07-19")
        j = next(x for x in self.api.lista_fotojobb() if x["id"] == jid)
        self.assertEqual(j["press_email"], "press@mff.se")
        self.assertEqual(j["begar_senast"], "2026-07-12")   # 7 dagar, inte 14

    def test_faltvis_fallback_klubb_utan_dagregel(self):
        # Klubben har adress men ingen dagregel → adressen från klubben,
        # dagarna från tävlingen (fälten faller tillbaka var för sig).
        self.api.spara_lag({"namn": "Malmö FF", "sport": "fotboll",
                            "press_email": "press@mff.se"})
        jid = self._matchjobb(ackr_dagar=14, press="press@obos.se",
                              datum="2026-07-19")
        j = next(x for x in self.api.lista_fotojobb() if x["id"] == jid)
        self.assertEqual(j["press_email"], "press@mff.se")
        self.assertEqual(j["begar_senast"], "2026-07-05")   # tävlingens 14

    def test_radera_fotojobb_stadar_ackreditering(self):
        jid = self._matchjobb()
        pam_id = store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"]
        self.api.satt_ackreditering(jid, note="kontakt: Eva")
        self.api.radera_fotojobb(jid)
        self.assertIn(pam_id, self.fake.raderade)
        self.assertEqual(store.hamta_ackreditering(self.api.conn, jid),
                         {"status": "ejbegard", "note": "",
                          "paminnelse_jobb_id": None})

    def test_nytt_matchdatum_flyttar_paminnelsen(self):
        jid = self._matchjobb(datum="2026-07-19")
        m = store.hamta_match(
            self.api.conn,
            store.matchref_for_fotojobb(self.api.conn, [jid])[jid])
        self.api.spara_match({**m, "datum": "2026-08-01"})
        pam_id = store.hamta_ackreditering(
            self.api.conn, jid)["paminnelse_jobb_id"]
        upp = [d for (i, d) in self.fake.uppdaterade if i == pam_id]
        self.assertTrue(upp and upp[-1]["start_at"] == "2026-07-18")


class TestListaKortBilder(unittest.TestCase):
    """lista_kort_bilder — nyast först + RAW/JPEG-par ihopslagna (RAW föredras)."""

    def setUp(self):
        self.api = Api(db_path=":memory:")

    def _kort(self, filer):
        """Bygger en temp-kortmapp; `filer` = [(namn, mtime), ...]."""
        import os
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        dcim = os.path.join(d, "DCIM", "100NZ_8")
        os.makedirs(dcim)
        for namn, mt in filer:
            p = os.path.join(dcim, namn)
            open(p, "wb").write(b"x")
            os.utime(p, (mt, mt))
        return d

    def test_nyast_forst_och_raw_jpeg_par_slas_ihop(self):
        d = self._kort([
            ("DSC_0001.NEF", 100), ("DSC_0001.JPG", 100),  # par → en post, RAW vald
            ("DSC_0002.NEF", 300),                          # nyast
            ("DSC_0003.JPG", 200),                          # ren jpeg
        ])
        r = self.api.lista_kort_bilder(d, bara_skyddade=False)
        self.assertTrue(r["ok"])
        self.assertEqual(r["totalt"], 3)
        self.assertEqual([b["filnamn"] for b in r["bilder"]],
                         ["DSC_0002.NEF", "DSC_0003.JPG", "DSC_0001.NEF"])

    def test_antal_begransar(self):
        d = self._kort([(f"DSC_{i:04d}.NEF", i) for i in range(5)])
        r = self.api.lista_kort_bilder(d, antal=2, bara_skyddade=False)
        self.assertEqual(len(r["bilder"]), 2)
        self.assertEqual(r["totalt"], 5)

    def test_bara_skyddade_som_standard(self):
        # Standard = bara kameralåsta. Lås DSC_0002 (rensa skrivbiten) och
        # verifiera att bara den kommer med.
        import os
        import stat as _stat
        d = self._kort([("DSC_0001.NEF", 100), ("DSC_0002.NEF", 200),
                        ("DSC_0003.NEF", 300)])
        las = os.path.join(d, "DCIM", "100NZ_8", "DSC_0002.NEF")
        os.chmod(las, _stat.S_IREAD)  # skrivbiten bort → _ar_skyddad = True
        r = self.api.lista_kort_bilder(d)  # default bara_skyddade=True
        self.assertTrue(r["ok"])
        self.assertEqual([b["filnamn"] for b in r["bilder"]], ["DSC_0002.NEF"])
        self.assertEqual(r["totalt"], 1)
        # Utan filtret kommer alla tre med.
        alla = self.api.lista_kort_bilder(d, bara_skyddade=False)
        self.assertEqual(alla["totalt"], 3)

    def test_saknad_mapp(self):
        self.assertFalse(self.api.lista_kort_bilder("/finns/inte")["ok"])
        self.assertFalse(self.api.lista_kort_bilder("")["ok"])


class TestSnabbplockExport(unittest.TestCase):
    """snabbplock_export — kopierar explicit plockade filer + öppnar LR."""

    def setUp(self):
        self.api = Api(db_path=":memory:")
        # Stubba LR-öppningen så testet inte startar Lightroom.
        self._oppnad = []
        self.api.oppna_i_lightroom = lambda s="": self._oppnad.append(s)

    def _filer(self, namn):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        paths = []
        for n in namn:
            p = os.path.join(d, n)
            open(p, "wb").write(b"raw")
            paths.append(p)
        return d, paths

    def test_kopierar_valda_till_malmapp_och_oppnar_lr(self):
        import os
        d, paths = self._filer(["DSC_0001.NEF", "DSC_0002.NEF"])
        mal = os.path.join(d, "ut")
        r = self.api.snabbplock_export(paths, ut_mapp=mal)
        self.assertTrue(r["ok"], r.get("fel"))
        self.assertEqual(r["antal"], 2)
        self.assertTrue(os.path.exists(os.path.join(mal, "DSC_0001.NEF")))
        self.assertEqual(self._oppnad, [r["path"]])

    def test_hoppar_over_saknade_filer(self):
        import os
        d, paths = self._filer(["DSC_0001.NEF"])
        mal = os.path.join(d, "ut")
        r = self.api.snabbplock_export(paths + ["/finns/inte.NEF"], ut_mapp=mal)
        self.assertTrue(r["ok"])
        self.assertEqual(r["antal"], 1)

    def test_tom_lista_ger_fel(self):
        self.assertFalse(self.api.snabbplock_export([])["ok"])

    def test_inga_riktiga_filer_ger_fel(self):
        r = self.api.snabbplock_export(["/finns/inte.NEF"])
        self.assertFalse(r["ok"])
        self.assertEqual(self._oppnad, [])

    def test_export_rapporterar_saknade(self):
        import os
        d, paths = self._filer(["DSC_0001.NEF"])
        mal = os.path.join(d, "ut")
        r = self.api.snabbplock_export(paths + ["/finns/inte.NEF"], ut_mapp=mal)
        self.assertTrue(r["ok"])
        self.assertEqual(r["antal"], 1)
        self.assertEqual(r["saknade"], 1)


class TestSnabbplockStage(unittest.TestCase):
    """snabbplock_stage — säkrar korts bilder MEDAN kortet sitter i, så plocket
    kan spänna över flera kort utan att tappa de tidigare (regression: bara
    kortet som satt kvar följde med till Lightroom)."""

    def setUp(self):
        self.api = Api(db_path=":memory:")

    def _kort(self, namn):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        paths = []
        for n in namn:
            p = os.path.join(d, n)
            open(p, "wb").write(b"raw-" + n.encode())
            paths.append(p)
        return d, paths

    def test_stagar_till_gemensam_mapp_och_returnerar_mappning(self):
        import os
        _, paths = self._kort(["DSC_0001.NEF", "DSC_0002.NEF"])
        r = self.api.snabbplock_stage(paths)
        self.assertTrue(r["ok"], r.get("fel"))
        self.assertEqual(len(r["stegade"]), 2)
        self.assertEqual(r["saknade"], [])
        for par in r["stegade"]:
            self.assertTrue(os.path.isfile(par["dst"]))
            self.assertEqual(os.path.dirname(par["dst"]), r["mapp"])

    def test_atervanvander_mapp_over_flera_kort(self):
        import os
        _, k1 = self._kort(["A_0001.NEF"])
        _, k2 = self._kort(["B_0001.NEF"])
        r1 = self.api.snabbplock_stage(k1)
        r2 = self.api.snabbplock_stage(k2, mapp=r1["mapp"])
        self.assertEqual(r1["mapp"], r2["mapp"])
        self.assertEqual(len(os.listdir(r1["mapp"])), 2)

    def test_overlever_att_kortet_forsvinner(self):
        # Kärnan i buggen: staga kort 1, radera sedan källan (kortet dras ut),
        # och verifiera att exporten ändå får med kort 1 via arbetskopian.
        import os
        import shutil
        d1, k1 = self._kort(["DSC_0001.NEF"])
        r1 = self.api.snabbplock_stage(k1)
        staged1 = r1["stegade"][0]["dst"]
        shutil.rmtree(d1)  # kort 1 avmonteras
        self.assertFalse(os.path.exists(k1[0]))
        self.assertTrue(os.path.isfile(staged1))  # men arbetskopian finns kvar
        d2, k2 = self._kort(["DSC_0002.NEF"])
        r2 = self.api.snabbplock_stage(k2, mapp=r1["mapp"])
        mal = os.path.join(d2, "ut")
        self.api.oppna_i_lightroom = lambda s="": None
        exp = self.api.snabbplock_export([staged1, r2["stegade"][0]["dst"]], ut_mapp=mal)
        self.assertTrue(exp["ok"])
        self.assertEqual(exp["antal"], 2)  # BÅDA korten med, inte bara kort 2

    def test_filnamnskrock_far_suffix(self):
        import os
        _, k1 = self._kort(["DSC_0001.NEF"])
        _, k2 = self._kort(["DSC_0001.NEF"])  # samma namn, annat kort
        r1 = self.api.snabbplock_stage(k1)
        r2 = self.api.snabbplock_stage(k2, mapp=r1["mapp"])
        namn = sorted(os.listdir(r1["mapp"]))
        self.assertEqual(len(namn), 2)
        self.assertNotEqual(r1["stegade"][0]["dst"], r2["stegade"][0]["dst"])

    def test_tom_lista_ar_ok(self):
        r = self.api.snabbplock_stage([])
        self.assertTrue(r["ok"])
        self.assertEqual(r["stegade"], [])

    def test_saknad_kalla_hamnar_i_saknade(self):
        r = self.api.snabbplock_stage(["/finns/inte.NEF"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["saknade"], ["/finns/inte.NEF"])
        self.assertEqual(r["stegade"], [])
