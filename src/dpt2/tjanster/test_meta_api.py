"""Tester för Meta-adaptern: rätt Graph-anropssekvens per posttyp (story/enkel/
karusell/FB-multi), felhantering, och att stub-postern driver hela skarpa flödet."""

import unittest

from dpt2.tjanster import meta_api as M


class Spelin:
    """Inspelnings-transport: sekventiella id:n + bevarad anropslista (path, params)."""
    def __init__(self, fel_pa=None):
        self.anrop = []
        self._n = 0
        self.fel_pa = fel_pa            # delsträng i path → höj MetaFel

    def __call__(self, path, params):
        self.anrop.append((path, params))
        if self.fel_pa and self.fel_pa in path:
            raise M.MetaFel("nekad")
        self._n += 1
        return {"id": f"id{self._n}"}

    def paths(self):
        return [p for p, _ in self.anrop]


def _poster(t):
    return M.MetaPoster(transport=t, bild_url=lambda p: f"https://h/{p}",
                        ig_user_id="IG", fb_page_id="FB", logg=lambda *_: None)


class TestIgStory(unittest.TestCase):
    def test_container_utan_caption_sen_publish(self):
        t = Spelin()
        r = _poster(t)({"kanal": "instagram", "form": "story",
                        "bilder": ["/a.jpg"], "text": "hej #x"})
        self.assertTrue(r["ok"])
        self.assertEqual(t.paths(), ["IG/media", "IG/media_publish"])
        self.assertEqual(t.anrop[0][1]["media_type"], "STORIES")
        self.assertNotIn("caption", t.anrop[0][1])          # story tar ingen caption


class TestIgInlagg(unittest.TestCase):
    def test_enkel_bild(self):
        t = Spelin()
        r = _poster(t)({"kanal": "instagram", "form": "inlägg",
                        "bilder": ["/a.jpg"], "text": "cap"})
        self.assertTrue(r["ok"])
        self.assertEqual(t.paths(), ["IG/media", "IG/media_publish"])
        self.assertEqual(t.anrop[0][1]["caption"], "cap")
        self.assertNotIn("media_type", t.anrop[0][1])        # ej karusell

    def test_karusell_barn_foralder_publish(self):
        t = Spelin()
        r = _poster(t)({"kanal": "instagram", "form": "inlägg",
                        "bilder": ["/a.jpg", "/b.jpg", "/c.jpg"], "text": "cap"})
        self.assertTrue(r["ok"])
        # 3 barn + 1 förälder + publicera
        self.assertEqual(t.paths(),
                         ["IG/media", "IG/media", "IG/media", "IG/media",
                          "IG/media_publish"])
        self.assertEqual(t.anrop[0][1]["is_carousel_item"], "true")
        foralder = t.anrop[3][1]
        self.assertEqual(foralder["media_type"], "CAROUSEL")
        self.assertEqual(foralder["children"], "id1,id2,id3")
        self.assertEqual(foralder["caption"], "cap")


class TestFb(unittest.TestCase):
    def test_enkel_foto(self):
        t = Spelin()
        r = _poster(t)({"kanal": "facebook", "form": "inlägg",
                        "bilder": ["/a.jpg"], "text": "cap"})
        self.assertTrue(r["ok"])
        self.assertEqual(t.paths(), ["FB/photos"])
        self.assertEqual(t.anrop[0][1]["message"], "cap")

    def test_multi_foto_opublicerat_sen_feed(self):
        t = Spelin()
        r = _poster(t)({"kanal": "facebook", "form": "inlägg",
                        "bilder": ["/a.jpg", "/b.jpg"], "text": "cap"})
        self.assertTrue(r["ok"])
        self.assertEqual(t.paths(), ["FB/photos", "FB/photos", "FB/feed"])
        self.assertEqual(t.anrop[0][1]["published"], "false")
        import json
        media = json.loads(t.anrop[2][1]["attached_media"])
        self.assertEqual([m["media_fbid"] for m in media], ["id1", "id2"])


class TestFel(unittest.TestCase):
    def test_graph_fel_blir_ok_false(self):
        r = _poster(Spelin(fel_pa="media"))({
            "kanal": "instagram", "form": "story", "bilder": ["/a.jpg"], "text": ""})
        self.assertFalse(r["ok"])
        self.assertIn("nekad", r["fel"])

    def test_okand_kanal(self):
        r = _poster(Spelin())({"kanal": "tiktok", "form": "video",
                               "bilder": ["/a.mp4"], "text": ""})
        self.assertFalse(r["ok"])


class TestFabriker(unittest.TestCase):
    def test_stub_poster_kor_hela_flodet(self):
        p = M.stub_poster(logg=lambda *_: None)
        r = p({"kanal": "instagram", "form": "inlägg",
               "bilder": ["/a.jpg", "/b.jpg"], "text": "cap"})
        self.assertTrue(r["ok"])
        self.assertTrue(r["url"].startswith("https://www.instagram.com/"))

    def test_fran_env_utan_token_ger_none(self):
        self.assertIsNone(M.fran_env(env={}))

    def test_fran_env_med_token_bygger_poster(self):
        p = M.fran_env(env={"META_ACCESS_TOKEN": "t", "IG_USER_ID": "ig",
                            "DPT_BILD_BAS_URL": "https://cdn.x/bilder/"})
        self.assertIsNotNone(p)
        self.assertEqual(p.bild_url("/lokalt/foo.jpg"), "https://cdn.x/bilder/foo.jpg")

    def test_fran_env_utan_bas_url_hojer_vid_bildhamtning(self):
        p = M.fran_env(env={"META_ACCESS_TOKEN": "t", "IG_USER_ID": "ig"})
        with self.assertRaises(M.MetaFel):
            p.bild_url("/lokalt/foo.jpg")


if __name__ == "__main__":
    unittest.main()
