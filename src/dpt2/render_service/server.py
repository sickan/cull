"""HTTP-skal runt molnrendern. Stdlib bara — enda tredjepartsberoendet i hela
servicen är Pillow (via story_overlay), vilket håller containern liten och
gör "det finns exakt EN renderare"-löftet lätt att granska.

Kontrakt (server-till-server, aldrig exponerad mot telefonen direkt):

    GET  /health              → 200 {"ok": true}
    POST /rendera             → 200 image/jpeg  |  400 {"fel": ...}
         Authorization: Bearer <RENDER_API_KEY>
         Content-Type: application/json
         {
           "moment": "slutresultat", "lag_hemma": "...", "lag_borta": "...",
           "liga": "...", "stallning": "3-1", "mal_rad": "...", "arena": "...",
           "sport": "fotboll", "tema": "Hav", "gren": "dam",
           "format": "9x16", "fokus": {"x": 50, "y": 40}, "zoom": 1.2,
           "overlay": true,               # valfritt (default true); false =
                                          #   ren beskuren bild utan grafik
           "scorers_layout": "auto",      # valfritt: auto|rad|chips|spalter (A4)
           "foto": "<base64>",            # obligatoriskt
           "hem_logga": "<base64>",       # valfritt (annars monogram)
           "borta_logga": "<base64>"
         }

Workern (content-sync) hämtar foto + loggor ur R2 och postar dem hit som
base64. Servicen gör INGA utgående anrop — den är en ren funktion över HTTP,
vilket gör den trivial att köra var som helst (Cloudflare Containers, Fly,
Railway, en liten server) och trivial att testa.
"""

import base64
import binascii
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dpt2.render_service.render import RenderFel, rendera

MAX_KROPP = 40 * 1024 * 1024      # base64 sväller ~33 % → tak över MAX_BYTES


def _konstant_lika(a, b):
    if len(a) != len(b):
        return False
    d = 0
    for x, y in zip(a, b):
        d |= ord(x) ^ ord(y)
    return d == 0


class Handler(BaseHTTPRequestHandler):
    server_version = "dpt-render/1.0"

    # Tyst logg — annars spammar varje render stderr i containern.
    def log_message(self, *a):
        pass

    def _svara(self, kod, kropp, typ="application/json; charset=utf-8"):
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(kropp)))
        self.end_headers()
        self.wfile.write(kropp)

    def _fel(self, kod, text):
        self._svara(kod, json.dumps({"fel": text}).encode())

    def do_GET(self):
        if self.path == "/health":
            return self._svara(200, b'{"ok":true}')
        self._fel(404, "hittas inte")

    def do_POST(self):
        if self.path != "/rendera":
            return self._fel(404, "hittas inte")

        nyckel = os.environ.get("RENDER_API_KEY", "")
        if nyckel:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or not _konstant_lika(auth[7:], nyckel):
                return self._fel(401, "ogiltig nyckel")

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._fel(400, "ogiltig Content-Length")
        if n <= 0 or n > MAX_KROPP:
            return self._fel(400, "tom eller för stor kropp")

        try:
            spec = json.loads(self.rfile.read(n))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._fel(400, "ogiltig JSON")
        if not isinstance(spec, dict):
            return self._fel(400, "kroppen måste vara ett objekt")

        try:
            bilder = {n_: _avkoda(spec.pop(n_, None), n_)
                      for n_ in ("foto", "hem_logga", "borta_logga")}
        except RenderFel as e:
            return self._fel(400, str(e))

        try:
            jpeg = rendera(spec, foto=bilder["foto"],
                           hem_logga=bilder["hem_logga"],
                           borta_logga=bilder["borta_logga"])
        except RenderFel as e:
            return self._fel(400, str(e))
        except Exception as e:                       # aldrig en tyst 500-krasch
            print(f"renderfel: {e}", file=sys.stderr, flush=True)
            return self._fel(500, "internt renderfel")

        self._svara(200, jpeg, "image/jpeg")


def _avkoda(varde, namn):
    if varde in (None, ""):
        return None
    if not isinstance(varde, str):
        raise RenderFel(f"{namn} måste vara base64-sträng")
    try:
        return base64.b64decode(varde, validate=True)
    except (binascii.Error, ValueError):
        raise RenderFel(f"{namn} är inte giltig base64")


def kor(port=None):
    port = int(port or os.environ.get("PORT", 8080))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"dpt-render lyssnar på :{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    kor()
