"""Meta-adapter (Instagram + Facebook) — en `poster`-callable för publicera_some.

Översätter en planerad post {kanal, form, bilder, text} till Graph API-anropen och
returnerar {ok, url|fel}. Injiceras som `poster` i publicera_korning.

Seam: all HTTP går genom en `transport(path, params) -> dict`. Riktig transport
(`bygg_transport`) pratar med graph.facebook.com; `Stub` fejkar svar så hela det
SKARPA flödet (dry_run=False) kan köras end-to-end utan token. Byt bara transport.

Graph-verkligheter som styr designen:
  * Publicering är TVÅ steg: skapa media-container → media_publish.
  * Karusell = N barn-containrar (is_carousel_item) + en CAROUSEL-förälder.
  * IG Story tar INGEN caption via API — story-texten ligger i den komponerade
    bilden (story_overlay), så `text` skickas inte för stories.
  * Bilder måste vara PUBLIKT nåbara URL:er (Graph hämtar image_url) — lokala
    sökvägar funkar inte. Därför krävs en `bild_url`-mappare (lokal path → https).
  * FB multi-photo: ladda upp foton opublicerade (published=false) → skapa ett
    feed-inlägg med attached_media.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v21.0"
GRAPH_BAS = "https://graph.facebook.com"


class MetaFel(Exception):
    """Ett Graph-anrop misslyckades (HTTP-fel eller error i svaret)."""


# ── Transport (HTTP-seam) ─────────────────────────────────────────────────────
def bygg_transport(access_token, *, api_version=API_VERSION, bas=GRAPH_BAS):
    """Riktig transport mot Graph API. Returnerar callable(path, params)->dict."""
    def transport(path, params):
        url = f"{bas}/{api_version}/{path}"
        data = urllib.parse.urlencode(
            {**params, "access_token": access_token}).encode()
        req = urllib.request.Request(url, data=data)     # data ⇒ POST
        try:
            with urllib.request.urlopen(req) as r:
                svar = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            kropp = e.read().decode("utf-8", "replace")
            raise MetaFel(f"HTTP {e.code}: {kropp}") from e
        except urllib.error.URLError as e:
            raise MetaFel(f"nätverksfel: {e.reason}") from e
        if isinstance(svar, dict) and svar.get("error"):
            raise MetaFel(svar["error"].get("message", "okänt Graph-fel"))
        return svar
    return transport


class Stub:
    """Fejk-transport: inga nätanrop, deterministiska id:n. Loggar varje anrop så
    hela det skarpa flödet syns. `anrop` bevarar sekvensen (för tester)."""

    def __init__(self, logg=print):
        self.logg = logg
        self.anrop = []
        self._n = 0

    def __call__(self, path, params):
        self._n += 1
        self.anrop.append((path, params))
        self.logg(f"[stub] {path}  {params}")
        if path.endswith("/media_publish"):
            return {"id": f"media_{self._n}"}
        if path.endswith("/feed"):
            return {"id": f"post_{self._n}"}
        return {"id": f"c{self._n}"}


# ── Poster ────────────────────────────────────────────────────────────────────
class MetaPoster:
    """Callable(planerad_post) -> {ok, url|fel}. Dispatchar på kanal/form."""

    def __init__(self, *, transport, bild_url, ig_user_id=None, fb_page_id=None,
                 logg=print):
        self.transport = transport
        self.bild_url = bild_url
        self.ig = ig_user_id
        self.fb = fb_page_id
        self.logg = logg

    def __call__(self, post):
        kanal, form = post.get("kanal"), post.get("form")
        try:
            if kanal == "instagram" and form == "story":
                return self._ig_story(post)
            if kanal == "instagram" and form == "inlägg":
                return self._ig_inlagg(post)
            if kanal == "facebook":
                return self._fb_inlagg(post)
            return {"ok": False, "fel": f"okänd kanal/form: {kanal}/{form}"}
        except MetaFel as e:
            return {"ok": False, "fel": str(e)}

    def _call(self, path, params):
        return self.transport(path, params)

    def _ig_publicera(self, creation_id):
        mid = self._call(f"{self.ig}/media_publish",
                         {"creation_id": creation_id})["id"]
        return {"ok": True, "url": f"https://www.instagram.com/media/{mid}"}

    def _ig_story(self, post):
        if not self.ig:
            raise MetaFel("saknar ig_user_id")
        cid = self._call(f"{self.ig}/media", {
            "image_url": self.bild_url(post["bilder"][0]),
            "media_type": "STORIES"})["id"]           # story tar ingen caption
        return self._ig_publicera(cid)

    def _ig_inlagg(self, post):
        if not self.ig:
            raise MetaFel("saknar ig_user_id")
        bilder, text = post["bilder"], post.get("text", "")
        if len(bilder) == 1:
            cid = self._call(f"{self.ig}/media", {
                "image_url": self.bild_url(bilder[0]), "caption": text})["id"]
            return self._ig_publicera(cid)
        # Karusell: barn-containrar → CAROUSEL-förälder → publicera.
        barn = [self._call(f"{self.ig}/media", {
            "image_url": self.bild_url(b), "is_carousel_item": "true"})["id"]
            for b in bilder]
        cid = self._call(f"{self.ig}/media", {
            "media_type": "CAROUSEL", "children": ",".join(barn),
            "caption": text})["id"]
        return self._ig_publicera(cid)

    def _fb_inlagg(self, post):
        if not self.fb:
            raise MetaFel("saknar fb_page_id")
        bilder, text = post["bilder"], post.get("text", "")
        if len(bilder) == 1:
            r = self._call(f"{self.fb}/photos", {
                "url": self.bild_url(bilder[0]), "message": text})
            return {"ok": True, "url": f"https://www.facebook.com/{r['id']}"}
        # Multi-photo: ladda upp opublicerat → feed-inlägg med attached_media.
        media = [{"media_fbid": self._call(f"{self.fb}/photos", {
            "url": self.bild_url(b), "published": "false"})["id"]}
            for b in bilder]
        r = self._call(f"{self.fb}/feed", {
            "message": text, "attached_media": json.dumps(media)})
        return {"ok": True, "url": f"https://www.facebook.com/{r['id']}"}


# ── Fabriker (worker/UI använder dessa) ───────────────────────────────────────
def stub_poster(logg=print):
    """MetaPoster mot Stub-transport — kör hela skarpa flödet utan token/nät.
    bild_url mappar en lokal path → en fejk-https-URL (basename)."""
    import os
    return MetaPoster(
        transport=Stub(logg), bild_url=lambda p: f"https://stub.dpt/{os.path.basename(p)}",
        ig_user_id="stub_ig", fb_page_id="stub_fb", logg=logg)


def fran_env(env=None, *, logg=print):
    """Bygger en RIKTIG MetaPoster ur miljövariabler, eller None om token saknas.
        META_ACCESS_TOKEN  — long-lived Graph-token
        IG_USER_ID         — Instagram professional-konto-id
        FB_PAGE_ID         — Facebook-sidans id
        DPT_BILD_BAS_URL   — publik bas-URL där bilderna hostas (Graph hämtar dem)
    bild_url = DPT_BILD_BAS_URL + basename. Utan bas-URL kan Graph inte nå bilderna.
    """
    import os
    env = env or os.environ
    token = env.get("META_ACCESS_TOKEN")
    if not token:
        return None
    bas = (env.get("DPT_BILD_BAS_URL") or "").rstrip("/")

    def bild_url(p):
        if not bas:
            raise MetaFel("DPT_BILD_BAS_URL saknas — bilderna måste hostas publikt.")
        return f"{bas}/{os.path.basename(p)}"

    return MetaPoster(
        transport=bygg_transport(token), bild_url=bild_url,
        ig_user_id=env.get("IG_USER_ID"), fb_page_id=env.get("FB_PAGE_ID"),
        logg=logg)
