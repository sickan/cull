"""Engångs-setup för Meta-integrationen (Instagram + Facebook).

Kör:  python -m dpt2.tjanster.meta_setup <APP_ID> <APP_SECRET> <KORT_TOKEN> [--skriv]

Gör hela kedjan som annars är pillrig i Metas portal:
  1. Byter den KORTLIVADE user-tokenen (från Graph API Explorer) mot en
     långlivad (~60 dagar).
  2. Hämtar dina Facebook-sidor (/me/accounts) — sidans access_token är
     långlivad och det är DEN som används för både FB- och IG-publicering.
  3. Läser sidans kopplade Instagram-proffskonto (instagram_business_account).
  4. Skriver META_ACCESS_TOKEN (= sidans token), FB_PAGE_ID och IG_USER_ID
     till ~/.zshrc med --skriv (annars visas raderna, token maskerad).

Kräver att Meta-appen har behörigheterna: pages_show_list, pages_manage_posts,
pages_read_engagement, instagram_basic, instagram_content_publish — och att
IG-proffskontot är kopplat till Facebook-sidan.
"""

import json
import sys
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"


def _get(path, **params):
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as r:
            svar = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Graph-fel HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")
    if isinstance(svar, dict) and svar.get("error"):
        raise SystemExit(f"Graph-fel: {svar['error'].get('message')}")
    return svar


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    skriv = "--skriv" in argv
    argv = [a for a in argv if a != "--skriv"]
    if len(argv) != 3:
        print(__doc__)
        return 1
    app_id, app_secret, kort_token = argv

    print("1/3 Byter till långlivad user-token …")
    lang = _get("oauth/access_token", grant_type="fb_exchange_token",
                client_id=app_id, client_secret=app_secret,
                fb_exchange_token=kort_token)["access_token"]

    print("2/3 Hämtar Facebook-sidor …")
    sidor = _get("me/accounts", access_token=lang).get("data", [])
    if not sidor:
        # Nya appar i dev-läge kan ge tom /me/accounts trots beviljad sida —
        # läs då sid-id:t ur tokenens granular scopes och hämta sidan direkt.
        dbg = _get("debug_token", input_token=lang,
                   access_token=f"{app_id}|{app_secret}")["data"]
        mal = [t for g in dbg.get("granular_scopes", [])
               if g.get("scope") == "pages_manage_posts"
               for t in g.get("target_ids", [])]
        sidor = [_get(pid, fields="name,access_token", access_token=lang)
                 for pid in mal]
    if not sidor:
        raise SystemExit("Inga sidor på kontot — koppla Facebook-sidan till appen "
                         "(Graph API Explorer → behörighet pages_show_list).")
    if len(sidor) > 1:
        print("   Flera sidor hittade:")
        for i, s in enumerate(sidor):
            print(f"   [{i}] {s['name']} (id {s['id']})")
        val = input("   Välj sida [0]: ").strip() or "0"
        sida = sidor[int(val)]
    else:
        sida = sidor[0]
        print(f"   Sida: {sida['name']} (id {sida['id']})")

    print("3/3 Läser kopplat Instagram-konto …")
    ig = _get(sida["id"], fields="instagram_business_account",
              access_token=lang).get("instagram_business_account")
    if not ig:
        raise SystemExit(f"Sidan '{sida['name']}' saknar kopplat IG-proffskonto — "
                         "koppla i Metas inställningar (Linked accounts) först.")

    rader = [
        "# DPT2 → Meta (SoMe-publicering) — sido-token, långlivad",
        f"export META_ACCESS_TOKEN={sida['access_token']}",
        f"export FB_PAGE_ID={sida['id']}",
        f"export IG_USER_ID={ig['id']}",
    ]
    if skriv:
        import os
        zshrc = os.path.expanduser("~/.zshrc")
        with open(zshrc, "a") as f:
            f.write("\n" + "\n".join(rader) + "\n")
        print(f"\n✓ Skrivet till {zshrc} (token ej visad).")
        print(f"  FB_PAGE_ID={sida['id']}  IG_USER_ID={ig['id']}")
    else:
        print("\nLägg i ~/.zshrc (eller kör om med --skriv):")
        for r in rader:
            print("  " + (r[:40] + "…" if r.startswith("export META_ACCESS_TOKEN") else r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
