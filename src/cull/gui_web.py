"""Webb-baserat gränssnitt (pywebview) — native fönster som hostar designens
HTML/CSS och kopplar fälten till cull-logiken. Återanvänder gui.bygg_kommando."""

import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from cull import gui, version as ver
from cull.leverans import PROFILER as LEVPROF

# MediaPipe/TF Lite-skräp som loggas vid avstängning — filtreras bort.
SKRAP = ("clearcut", "Source Location Trace", "portable_clearcut",
         "playlog/cplusplus", "Not valid for uploading")

# Filtyper som "Visa urval" kan rendera (raw → extraherad preview, jpg direkt).
RAW_SUFFIX = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf"}
VISA_SUFFIX = RAW_SUFFIX | {".jpg", ".jpeg"}

# Okänd-sport (samma sökvägar som gui._klassificera_okanda).
OKAND_PATH = Path.home() / ".cache" / "cull" / "sport_okand.json"
SPORT_WEBB_CACHE = Path.home() / ".cache" / "cull" / "sport_cache.json"
SPORTER_VAL = ["handboll", "fotboll", "volleyboll", "innebandy"]


def _b64_thumb(path, maxsize):
    """Öppnar en bildfil, skalar ned och returnerar en data-URI (JPEG)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path)
        img.thumbnail(maxsize)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _thumb_for(path, env, maxsize=(300, 220)):
    """Miniatyr för raw (extrahera inbäddad preview) eller jpg (direkt)."""
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return _b64_thumb(path, maxsize)
    with tempfile.TemporaryDirectory() as td:
        jpg = Path(td) / (path.stem + ".jpg")
        if not gui._extrahera_preview(path, jpg, env):
            return None
        return _b64_thumb(jpg, maxsize)


class _V:
    """Shim så att gui.bygg_kommando (som väntar tk-vars) kan ta en dict."""
    __slots__ = ("_v",)

    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v


def _shim(d):
    return {k: _V(d.get(k, "")) for k in gui.SETTINGS_KEYS}


def _env():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    extra = ["/opt/homebrew/bin", "/usr/local/bin"]
    bef = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join([p for p in extra if p not in bef] + bef)
    return env


def _versionsrad():
    return f"v{ver.version()} · build {ver.build()}"


def _modellinfo():
    try:
        import pickle
        with open(gui.MODELL_PATH, "rb") as f:
            d = pickle.load(f)
        sporter = [k for k in d.get("sportmodeller", {})] if isinstance(d, dict) else []
        n_upp = d.get("n_uppdrag") if isinstance(d, dict) else None
        n_val = d.get("n_val") if isinstance(d, dict) else None
        bitar = []
        if n_upp:
            bitar.append(f"{n_upp} uppdrag")
        if n_val:
            bitar.append(f"{n_val} val")
        if sporter:
            bitar.append("[" + ", ".join(sporter) + "]")
        return " · ".join(bitar) or "modell finns"
    except Exception:
        return "ingen modell tränad än"


class Api:
    def __init__(self):
        self.window = None

    # --- init: skicka allt frontend behöver ---------------------------------
    def init(self):
        return {
            "version": _versionsrad(),
            "settings": gui.ladda_installningar(),
            "oppna": gui.OPPNA_VAL,
            "husstil": ["(ingen)"] + gui._lista_presets(),
            "leverans": ["(ingen)"] + list(LEVPROF),
            "bildtext_modell": list(gui.BILDTEXT_MODELLER),
            "farger": gui.FARGER,
            "yolo": gui.YOLO_MODELLER,
            "sport": gui.SPORTER,
            "estetik_motor": ["NIMA", "Vision"],
            "modellinfo": _modellinfo(),
        }

    # --- matchdatabas (förberedda matcher) -----------------------------------
    def matcher_lista(self, _d=None):
        return {"matcher": gui.ladda_matcher(), "sporter": gui.SPORTER}

    @staticmethod
    def _rensa_spelare(lista):
        """Saniterar en inline-spelarlista → [{nr,namn,lag,handle,info,start}].
        Behåller bara rader med nummer ELLER namn; lag tvingas hemma/borta."""
        ut = []
        for r in (lista or []):
            if not isinstance(r, dict):
                continue
            nr = str(r.get("nr", "")).strip()
            namn = str(r.get("namn", "")).strip()
            if not (nr or namn):
                continue
            lag = str(r.get("lag", "")).strip().lower()
            if lag not in ("hemma", "borta"):
                lag = "hemma"
            ut.append({
                "nr": nr, "namn": namn, "lag": lag,
                "handle": str(r.get("handle", "")).strip(),
                "info": str(r.get("info", "")).strip(),
                "start": bool(r.get("start")),
            })
        return ut

    @staticmethod
    def _skriv_roster_csv(rader, namn):
        """rader=[{nr,namn,lag?}] → roster-CSV i CONFIG_DIR, returnerar sökväg.
        3-kolumns (nummer,namn,lag) om någon rad har lag, annars 2-kolumns."""
        import csv
        import re as _re
        slug = _re.sub(r"[^\w-]+", "_", (namn or "match")).strip("_")[:60] or "match"
        gui.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = gui.CONFIG_DIR / f"roster_{slug}.csv"
        med_lag = any((r.get("lag") or "").strip() for r in (rader or []))
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["nummer", "namn", "lag"] if med_lag
                           else ["nummer", "namn"])
                for r in rader or []:
                    nr = str(r.get("nr", "")).strip()
                    nm = str(r.get("namn", "")).strip()
                    if not (nr and nm):
                        continue
                    if med_lag:
                        w.writerow([nr, nm, (r.get("lag") or "").strip().lower()])
                    else:
                        w.writerow([nr, nm])
            return str(path)
        except Exception:
            return ""

    def match_spara(self, d):
        """Skapar/uppdaterar en match. d = matchfälten (+ valfritt id).
        Inline-spelarlistan (spelare) bevaras om den inte skickas med."""
        import uuid
        m = d.get("match") if isinstance(d.get("match"), dict) else d
        falt = ("lag_hemma", "lag_borta", "datum", "tid", "arena", "liga",
                "sport", "resultat", "roster")
        post = {k: (m.get(k) or "").strip() for k in falt}
        if not post["lag_hemma"] and not post["lag_borta"]:
            return {"ok": False, "fel": "Ange minst ett lag."}
        lista = gui.ladda_matcher()
        mid = (m.get("id") or "").strip()
        gammal = None
        if mid:
            for i, x in enumerate(lista):
                if x.get("id") == mid:
                    gammal = x
                    post["id"] = mid
                    post["skapad"] = x.get("skapad", "")
                    lista[i] = post
                    break
            else:
                mid = ""
        # inline-spelarlista: använd skickad, annars bevara den befintliga
        if "spelare" in m:
            post["spelare"] = self._rensa_spelare(m.get("spelare"))
        elif gammal is not None:
            post["spelare"] = gammal.get("spelare", [])
        else:
            post["spelare"] = []
        if not mid:
            post["id"] = uuid.uuid4().hex[:12]
            post["skapad"] = datetime.now().isoformat(timespec="seconds")
            lista.insert(0, post)
        gui.spara_matcher(lista)
        return {"ok": True, "id": post["id"], "matcher": lista}

    def match_radera(self, d):
        mid = (d.get("id") or "").strip()
        lista = [x for x in gui.ladda_matcher() if x.get("id") != mid]
        gui.spara_matcher(lista)
        return {"ok": True, "matcher": lista}

    def match_aktivera(self, d):
        """Sätter en match som aktiv: komponerar matchinfo + fyller de fält som
        verktygen (stories, cull, bildsvep) redan läser. Returnerar fält att
        applicera i UI:t."""
        mid = (d.get("id") or "").strip()
        m = next((x for x in gui.ladda_matcher() if x.get("id") == mid), None)
        if not m:
            return {"ok": False, "fel": "Okänd match."}
        bitar = [b for b in [m.get("lag_hemma", ""), "-", m.get("lag_borta", "")]
                 if b]
        rad = " ".join(bitar)
        if m.get("resultat"):
            rad += " " + m["resultat"]
        if m.get("datum"):
            rad += " " + m["datum"]
        if m.get("tid"):
            rad += " " + m["tid"]
        if m.get("arena"):
            rad += " " + m["arena"]
        falt = {
            "matchinfo": rad.strip(),
            "avspark": m.get("tid", "") or "auto",
            "story_liga": m.get("liga", ""),
            "aktiv_match_id": mid,
        }
        if (m.get("sport") or "").strip():
            falt["sport"] = m["sport"].strip().capitalize()
        # roster: härled CSV ur matchens inline-spelare (källan), så nummer-/
        # bildtext-verktygen får en fil att läsa. Fallback: en befintlig sökväg.
        spelare = m.get("spelare") or []
        rader = [{"nr": p.get("nr", ""), "namn": p.get("namn", ""),
                  "lag": p.get("lag", "hemma")}
                 for p in spelare if (p.get("nr") and p.get("namn"))]
        if rader:
            namn = f"{m.get('lag_hemma', '')}-{m.get('lag_borta', '')}".strip("-") \
                or "match"
            path = self._skriv_roster_csv(rader, namn)
            if path:
                falt["roster"] = path
        elif (m.get("roster") or "").strip():
            falt["roster"] = m["roster"].strip()
        return {"ok": True, "falt": falt}

    @staticmethod
    def _slå_ihop_spelare(gamla, nya, *, bevara_start=False):
        """Mergar ny spelarlista mot befintlig.
        Matchar på (nr, lag) i första hand; faller tillbaka på (namn, lag) —
        täcker fallet att fas 1 saknar nummer men fas 2 har det.
        Nya vinner på: nr, namn, lag, start (om inte bevara_start).
        Gamla bevaras för: handle, info — om de saknas i nya.
        Spelare enbart i gamla behålls; start sätts False om inte bevara_start."""
        gl = list(gamla or [])
        anvanda = set()   # index i gl som redan matchats

        def _nr(p):   return str(p.get("nr", "")).strip()
        def _lag(p):  return str(p.get("lag", "hemma")).strip().lower()
        def _namn(p): return str(p.get("namn", "")).strip().lower()

        # Bygg snabbindex: (nr, lag) → index och (namn, lag) → index
        by_nr   = {(_nr(p), _lag(p)): i for i, p in enumerate(gl) if _nr(p)}
        by_namn = {(_namn(p), _lag(p)): i for i, p in enumerate(gl)}

        ut = []
        for ny in (nya or []):
            nr = _nr(ny); lag = _lag(ny); namn = _namn(ny)
            gi = by_nr.get((nr, lag)) if nr else None
            if gi is None or gi in anvanda:
                gi = by_namn.get((namn, lag))
            gammal = gl[gi] if (gi is not None and gi not in anvanda) else None
            if gi is not None and gi not in anvanda and gammal is not None:
                anvanda.add(gi)
            merged = {
                "nr":     nr,
                "namn":   str(ny.get("namn", "")).strip(),
                "lag":    lag,
                "handle": str(ny.get("handle", "")).strip(),
                "info":   str(ny.get("info", "")).strip(),
                "start":  bool(ny.get("start", False)),
            }
            if gammal:
                if not merged["handle"] and gammal.get("handle"):
                    merged["handle"] = gammal["handle"]
                if not merged["info"] and gammal.get("info"):
                    merged["info"] = gammal["info"]
                if bevara_start:
                    merged["start"] = bool(gammal.get("start", False))
            ut.append(merged)
        # Spelare enbart i gamla — behåll, reset start vid fas 2
        for i, g in enumerate(gl):
            if i in anvanda:
                continue
            ut.append({
                "nr":     _nr(g),
                "namn":   str(g.get("namn", "")).strip(),
                "lag":    _lag(g),
                "handle": str(g.get("handle", "")).strip(),
                "info":   str(g.get("info", "")).strip(),
                "start":  bool(g.get("start", False)) if bevara_start else False,
            })
        return ut

    def match_satt_spelare(self, d):
        """Skriver inline-spelarlistan till en match utan att röra övriga fält.
        d = {id, spelare:[{nr,namn,lag,handle,info,start}]}. Används av spelar-
        editorn (Hämta match / Redigera spelare) → matchposten = källan."""
        mid = (d.get("id") or "").strip()
        lista = gui.ladda_matcher()
        for x in lista:
            if x.get("id") == mid:
                x["spelare"] = self._rensa_spelare(d.get("spelare"))
                gui.spara_matcher(lista)
                antal = len(x["spelare"])
                med_h = sum(1 for p in x["spelare"] if p.get("handle"))
                return {"ok": True, "matcher": lista, "antal": antal,
                        "med_handle": med_h}
        return {"ok": False, "fel": "Okänd match."}

    # --- mapp-väljare --------------------------------------------------------
    def valj_mapp(self, start):
        import webview
        try:
            res = self.window.create_file_dialog(
                webview.FOLDER_DIALOG, directory=start or str(Path.home()))
        except Exception:
            res = None
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def valj_fil(self, start):
        import webview
        try:
            res = self.window.create_file_dialog(
                webview.OPEN_DIALOG, directory=start or str(Path.home()),
                file_types=("CSV (*.csv)", "Alla filer (*.*)"))
        except Exception:
            res = None
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def valj_bildfil(self, start):
        """Filväljare för bilder (JPEG + råformat)."""
        import webview
        start_dir = str(Path(start).parent) if start and Path(start).exists() else str(Path.home())
        try:
            res = self.window.create_file_dialog(
                webview.OPEN_DIALOG, directory=start_dir,
                file_types=("Bilder (*.jpg;*.jpeg;*.nef;*.dng;*.cr3;*.cr2;*.arw;*.raf;*.rw2;*.orf)",
                            "Alla filer (*.*)"))
        except Exception:
            res = None
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def bild_antal(self, d):
        """Räknar riktiga bildfiler rekursivt i källmappen (för antals-/%-
        visning). Returnerar {antal, mappar, mapp}."""
        from cull import core
        mapp = gui.stadad_sokvag(d.get("katalog"))
        p = Path(mapp)
        if not mapp or not p.is_dir():
            return {"antal": 0, "mappar": 0, "mapp": mapp}
        try:
            filer = core.lista_bildfiler(p, rekursiv=True)
        except Exception:
            return {"antal": 0, "mappar": 0, "mapp": mapp}
        mappar = len({f.parent for f in filer})
        return {"antal": len(filer), "mappar": mappar, "mapp": mapp}

    # --- spara inställningar --------------------------------------------------
    def spara(self, d):
        try:
            gui.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = gui.ladda_installningar()
            data.update(d)
            with open(gui.SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # --- JS-utskrift ----------------------------------------------------------
    def _js(self, code):
        try:
            self.window.evaluate_js(code)
        except Exception:
            pass

    def _logga(self, text, cls=None):
        arg = json.dumps(text)
        self._js(f"window.dpcLog({arg}, {json.dumps(cls) if cls else 'null'})")

    def _work(self, text, cls=None):
        """Som _logga men uppdaterar även arbets-vyn i sheeten (senaste steg),
        så långsamma Claude-anrop syns leva i stället för en frusen rad."""
        self._logga(text, cls)
        self._js(f"window.dpcWork({json.dumps(text)})")

    def _stream(self, cmd):
        self._logga("$ " + " ".join(cmd) + "\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    bufsize=1, env=_env())
        except Exception as e:
            self._logga(f"Kunde inte starta: {e}", "err")
            self._js("window.dpcDone(false)")
            return
        for rad in proc.stdout:
            if any(s in rad for s in SKRAP):
                continue
            self._logga(rad.rstrip("\n"))
        proc.wait()
        rc = proc.returncode
        if rc == 0:
            self._logga("\n✓ Klar.", "ok")
        elif rc < 0:
            import signal as _sig
            try:
                namn = _sig.Signals(-rc).name
            except ValueError:
                namn = f"signal {-rc}"
            tips = {9: " — slut på minne (OOM-dödad av macOS)",
                    11: " — krasch i en C-modul (segfault)",
                    6: " — avbrott i en C-modul (abort)"}.get(-rc, "")
            self._logga(f"\n✗ Processen dödades av {namn} (kod {rc}){tips}.", "err")
        else:
            self._logga(f"\n✗ Avslutades med fel (kod {rc}). "
                        "Se raderna ovan för orsak.", "err")
        self._js(f"window.dpcDone({'true' if rc == 0 else 'false'})")

    # --- kör cull ------------------------------------------------------------
    def kor(self, d):
        # Behåll-enhet: "%" → andel (fraktion 0–1), annars topp (antal).
        if (d.get("behall_enhet") or "").strip() == "%":
            try:
                pct = float(str(d.get("topp", "")).replace(",", "."))
                d["andel"] = f"{max(0.0, min(pct, 100.0)) / 100:.4f}"
            except (ValueError, TypeError):
                d["andel"] = ""
            d["topp"] = ""
        else:
            d["andel"] = ""
        cmd, fel = gui.bygg_kommando(_shim(d))
        if fel:
            self._logga("⚠ " + fel, "err")
            self._js("window.dpcDone(false)")
            return
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- träna modell --------------------------------------------------------
    def trana(self, d):
        rot = (d.get("trana_rot") or "").strip()
        if not rot:
            # Avbryt mapp-dialogen = träna bara på PM-underlag (Lär av match).
            rot = self.valj_mapp("") or str(gui.CONFIG_DIR)
            if rot != str(gui.CONFIG_DIR):
                self._js(f"document.getElementById('trana_rot').value={json.dumps(rot)}")
        cmd = [sys.executable, "-m", "cull.inlarning", rot, "--max-neg", "100"]
        yolo = (d.get("yolo") or "").strip()
        if yolo:
            cmd += ["--yolo", yolo]
        if d.get("estetik"):
            cmd += ["--estetik-motor", (d.get("estetik_motor") or "nima").lower()]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    def trana_dinsmak(self, d):
        """'Din smak'-modell: tränar enbart på dina märkta matcher (Lär av
        match), oblandat med arkivets Instagram-facit."""
        cmd = [sys.executable, "-m", "cull.inlarning",
               "--bara-markt", "--max-neg", "100"]
        if d.get("estetik"):
            cmd += ["--estetik-motor", (d.get("estetik_motor") or "nima").lower()]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- Modell-växlare: din smak ↔ arkiv ------------------------------------
    def modeller_lista(self, _d=None):
        """Listar modell-biblioteket (din_smak/arkiv) + vilken som är aktiv."""
        import pickle
        from cull import inlarning as inl

        def _meta(p):
            try:
                with open(p, "rb") as f:
                    d = pickle.load(f)
                return {"typ": d.get("modell_typ", ""),
                        "n_uppdrag": d.get("n_uppdrag"),
                        "n_valda": d.get("n_valda"),
                        "sport": list(d.get("sport_modeller", {}).keys()),
                        "sparad": d.get("sparad", "")}
            except Exception:
                return None

        aktiv = _meta(inl.MODELL_PATH) or {}
        poster = []
        if inl.MODELLER_DIR.is_dir():
            for p in sorted(inl.MODELLER_DIR.glob("*.pkl")):
                m = _meta(p)
                if not m:
                    continue
                m["fil"] = p.name
                m["aktiv"] = (bool(aktiv) and m.get("typ") == aktiv.get("typ")
                              and m.get("sparad") == aktiv.get("sparad"))
                poster.append(m)
        return {"modeller": poster, "aktiv": aktiv}

    def aktivera_modell(self, d):
        """Kopierar vald modell ur biblioteket till aktiva modell.pkl."""
        import shutil
        from cull import inlarning as inl
        fil = (d.get("modell_fil") or "").strip()
        src = inl.MODELLER_DIR / fil
        if not fil or not src.exists():
            return {"ok": False, "fel": "Okänd modell."}
        try:
            shutil.copy2(src, inl.MODELL_PATH)
        except Exception as e:
            return {"ok": False, "fel": str(e)}
        return {"ok": True}

    # --- Lär av match: märk cull-underlag med Photo Mechanic-urval -----------
    def facit_underlag_lista(self, _d=None):
        """Sparade tränings-underlag (ett per cull) + om de redan märkts."""
        from cull import inlarning as inl
        poster = []
        if inl.FACIT_UNDERLAG_DIR.is_dir():
            markta = ({p.name for p in inl.FACIT_MARKT_DIR.glob("*.json")}
                      if inl.FACIT_MARKT_DIR.is_dir() else set())
            for f in sorted(inl.FACIT_UNDERLAG_DIR.glob("*.json"), reverse=True):
                try:
                    j = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                poster.append({"fil": f.name,
                               "match": j.get("match", f.stem),
                               "kalla": j.get("kalla", ""),
                               "n": j.get("n", len(j.get("rader", []))),
                               "skapad": j.get("skapad", ""),
                               "markt": f.name in markta})
        return {"underlag": poster}

    def lar_av_match(self, d):
        """Märker ett underlag i två nivåer: behåll-mappen (ditt NEF-urval) →
        y=1, levererat (JPG-galleriet, valfritt) → samma men extra vikt. Resten
        y=0. Matchar på filstam → facit för träning."""
        from cull import inlarning as inl
        LEV_VIKT = 2.0
        EXIF = {".nef", ".dng", ".cr3", ".cr2", ".arw", ".raf", ".rw2", ".orf",
                ".jpg", ".jpeg"}

        def _stems(p):
            return {x.stem.lower() for x in Path(p).rglob("*")
                    if x.is_file() and x.suffix.lower() in EXIF
                    and not x.name.startswith(".")}

        fil = (d.get("underlag_fil") or "").strip()
        src = inl.FACIT_UNDERLAG_DIR / fil
        if not fil or not src.exists():
            return {"ok": False, "fel": "Välj ett underlag först."}
        keep_mapp = (d.get("lar_keep_mapp") or "").strip()
        if not keep_mapp or not Path(keep_mapp).is_dir():
            return {"ok": False, "fel": "Välj din behåll-mapp (NEF-urvalet)."}
        behall = _stems(keep_mapp)
        if not behall:
            return {"ok": False, "fel": "Inga bildfiler i behåll-mappen."}
        lev_mapp = (d.get("lar_lev_mapp") or "").strip()
        levererat = (_stems(lev_mapp)
                     if lev_mapp and Path(lev_mapp).is_dir() else set())
        try:
            j = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            return {"ok": False, "fel": f"Kunde inte läsa underlaget: {e}"}
        rader = j.get("rader", [])
        n_keep = n_lev = 0
        for r in rader:
            s = (r.get("stem", "") or "").lower()
            if s in behall:
                r["y"] = 1
                r["w"] = LEV_VIKT if s in levererat else 1.0
                n_keep += 1
                if s in levererat:
                    n_lev += 1
            else:
                r["y"] = 0
                r["w"] = 1.0
        j["behall_mapp"] = keep_mapp
        j["lev_mapp"] = lev_mapp
        try:
            inl.FACIT_MARKT_DIR.mkdir(parents=True, exist_ok=True)
            (inl.FACIT_MARKT_DIR / fil).write_text(
                json.dumps(j, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            return {"ok": False, "fel": f"Kunde inte spara: {e}"}
        return {"ok": True, "match": j.get("match", ""),
                "n_total": len(rader), "n_keep": n_keep, "n_lev": n_lev,
                "ej_matchade": max(0, len(behall) - n_keep)}

    # --- efterbehandla en exporterad mapp ------------------------------------
    def efterbehandla(self, d):
        mapp = self._aktiv_mapp(d, "export_rot")
        if not mapp:
            self._js("window.dpcDone(false)")
            return
        cmd = [sys.executable, "-m", "cull.core", mapp, "--efterbehandla"]
        if d.get("iptc"):
            cmd.append("--iptc")
        if (d.get("roster") or "").strip():
            cmd += ["--roster", d["roster"].strip()]
        if d.get("bildtext_ai"):
            cmd.append("--bildtext-ai")
            mdl = gui.BILDTEXT_MODELLER.get((d.get("bildtext_modell") or "").strip())
            if mdl:
                cmd += ["--bildtext-modell", mdl]
        lev = (d.get("leverans") or "").strip()
        if lev and lev != "(ingen)":
            cmd += ["--leverans", lev]
        hus = (d.get("husstil") or "").strip()
        if hus and hus != "(ingen)":
            cmd += ["--husstil", str(gui.PRESET_DIR / f"{hus}.xmp")]
        if d.get("xmp_brus"):
            cmd.append("--xmp-brus")
        try:
            bump = float(str(d.get("exp_bump", "0")).replace(",", "."))
        except (ValueError, TypeError):
            bump = 0.0
        if abs(bump) > 0.005:
            cmd += ["--exp-bump", f"{bump:.2f}"]
        if (d.get("fotograf") or "").strip():
            cmd += ["--fotograf", d["fotograf"].strip()]
        if (d.get("matchinfo") or "").strip():
            cmd += ["--ut-namn", d["matchinfo"].strip()]
        sp = (d.get("sport") or "").strip()
        if sp and sp.lower() != "auto":
            cmd += ["--sport", sp.lower()]
        if (d.get("hemma_farg") or "").strip():
            cmd += ["--hemma-farg", d["hemma_farg"].strip()]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    def _aktiv_mapp(self, d, *falt):
        """Återanvänd det aktiva urvalet (väljaren) om det pekar på en mapp,
        annars öppna mapp-dialogen med ett vettigt startläge."""
        akt = (d.get("aktivt_urval") or "").strip()
        if akt and Path(akt).is_dir():
            return akt
        start = next((d.get(f) for f in falt if (d.get(f) or "").strip()), "")
        return self.valj_mapp(start or "")

    # --- läs tröjnummer på en vald mapp → XMP-keywords -----------------------
    def nummer_pass(self, d):
        mapp = self._aktiv_mapp(d, "katalog", "export_rot")
        if not mapp:
            self._js("window.dpcDone(false)")
            return
        cmd = [sys.executable, "-m", "cull.nummer_pass", mapp]
        yolo = (d.get("yolo") or "").strip()
        if yolo:
            cmd += ["--yolo", yolo]
        if (d.get("roster") or "").strip():
            cmd += ["--roster", d["roster"].strip()]
        if (d.get("hemma_farg") or "").strip():
            cmd += ["--hemma-farg", d["hemma_farg"].strip()]
        if d.get("nummer_claude"):
            cmd.append("--claude")
            mdl = gui.BILDTEXT_MODELLER.get((d.get("bildtext_modell") or "").strip())
            if mdl:
                cmd += ["--claude-modell", mdl]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- Instagram-urval: plocka 20 IG-bästa ur ett urval (4:5 i XMP → LR) ---
    def instagram_urval(self, d):
        mapp = self._aktiv_mapp(d, "export_rot", "katalog")
        if not mapp:
            self._js("window.dpcDone(false)")
            return
        cmd = [sys.executable, "-m", "cull.core", mapp, "--instagram-urval"]
        if d.get("instagram_ai"):
            cmd.append("--instagram-ai")
        if (d.get("matchinfo") or "").strip():
            cmd += ["--ut-namn", d["matchinfo"].strip()]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- Snabbplock: bara de kameralåsta (protect) bilderna, ingen AI --------
    def snabbplock(self, d):
        # Källan = kortet som sitter i (uchg läses på källan). Återanvänd
        # Källmapp-fältet om det är ifyllt, annars öppna mappdialogen.
        mapp = gui.stadad_sokvag(d.get("snabb_kalla") or d.get("katalog"))
        if not mapp or not Path(mapp).is_dir():
            mapp = self.valj_mapp(mapp or "")
        if not mapp:
            self._js("window.dpcDone(false)")
            return
        self._js("document.getElementById('snabb_kalla').value="
                 + json.dumps(mapp))
        cmd = [sys.executable, "-m", "cull.core", mapp, "--snabbplock"]
        snabb_ut = (d.get("snabb_ut") or "").strip()
        if snabb_ut:
            cmd += ["--snabb-ut", snabb_ut]
        # Normalisera visningsvärdet ("Lightroom", "DxO PureRAW" …) till
        # CLI-koderna (lightroom/dxo/finder/inget); auto = default → utelämna.
        oppna = (d.get("oppna") or "").strip().lower()
        oppna = {"dxo pureraw": "dxo"}.get(oppna, oppna)
        if oppna and oppna != "auto":
            cmd += ["--oppna", oppna]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- Räta upp för Lightroom (fristående XMP-sidecars) --------------------
    def rata_upp(self, d):
        mapp = gui.stadad_sokvag(d.get("rata_mapp"))
        if not mapp or not Path(mapp).is_dir():
            mapp = self.valj_mapp(mapp or "")
        if not mapp:
            self._js("window.dpcDone(false)")
            return
        self._js("document.getElementById('rata_mapp').value="
                 + json.dumps(mapp))
        cmd = [sys.executable, "-m", "cull.core", mapp, "--rata-upp"]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- Story overlay (inbränd 9:16-JPEG) -----------------------------------
    def story_overlay(self, d):
        """Skapar en inbränd 9:16 story-JPEG och öppnar den i Finder."""
        bild = (d.get("story_bild") or "").strip()
        if not bild or not Path(bild).exists():
            self._js("window.dpcStory(null)")
            return

        from cull import story_overlay as so
        mi      = so.tolka_matchinfo((d.get("matchinfo") or "").strip())
        moment  = (d.get("story_moment") or "avspark").strip()
        liga    = (d.get("story_liga") or "").strip()
        avspark_tid = (d.get("avspark") or "").strip()
        if avspark_tid.lower() == "auto":
            avspark_tid = ""
        if not avspark_tid:
            avspark_tid = mi.get("tid", "")   # klockslag inbäddat i matchinfo

        def jobb():
            try:
                ut = so.skapa_story(
                    bild, moment,
                    mi["lag_hemma"], mi["lag_borta"],
                    liga=liga,
                    stallning=(d.get("story_stallning") or "").strip(),
                    mal_rad=(d.get("story_mal") or "").strip(),
                    avspark_tid=avspark_tid,
                    arena=mi["arena"],
                    ut_mapp=(d.get("story_utmapp") or "").strip() or None,
                    format=(d.get("story_format") or "9x16").strip(),
                    env=_env(),
                )
                self._logga(f"✓ Story skapad: {ut}")
                import subprocess as _sp
                _sp.Popen(["open", "-R", str(ut)])
                self._js(f"window.dpcStory({json.dumps(str(ut), ensure_ascii=False)})")
            except Exception as exc:
                self._logga(f"Story-fel: {exc}")
                self._js("window.dpcStory(null)")

        threading.Thread(target=jobb, daemon=True).start()

    def story_info(self, d):
        """Returnerar parsad matchdata + logga-status för Story-kortets live-visning."""
        from cull import story_overlay as so
        mi   = so.tolka_matchinfo((d.get("matchinfo") or "").strip())
        liga = (d.get("story_liga") or "").strip()
        avspark_val = (d.get("avspark") or "").strip()
        if avspark_val.lower() == "auto":
            avspark_val = ""

        def _logga_info(namn):
            p = so.hitta_logga(namn)
            return {"finns": p is not None, "fil": p.name if p else None}

        return {
            "lag_hemma":   mi["lag_hemma"],
            "lag_borta":   mi["lag_borta"],
            "datum":       mi["datum"],
            "arena":       mi["arena"],
            "avspark":     avspark_val,
            "liga":        liga,
            "logga_hemma": _logga_info(mi["lag_hemma"]),
            "logga_borta": _logga_info(mi["lag_borta"]),
            "logga_liga":  _logga_info(liga),
        }

    def ladda_upp_logga(self, d):
        """Filväljare → kopierar PNG till ~/.config/cull/loggor/<normnamn>.png."""
        import webview, shutil
        from cull import story_overlay as so
        lag_namn = (d.get("logga_lag") or "").strip()
        if not lag_namn:
            return {"ok": False, "fel": "Inget lagnamn angivet"}
        norm = so.normera_lag(lag_namn)
        try:
            res = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=str(Path.home()),
                file_types=("Bildfiler (*.png;*.jpg;*.jpeg)", "Alla filer (*.*)"))
        except Exception as e:
            import traceback
            self._logga(f"[logga] create_file_dialog fel: {e}\n", "fel")
            return {"ok": False, "fel": f"Dialogfel: {e}"}
        if not res:
            return {"ok": False, "fel": "Avbruten"}
        src = Path(res[0] if isinstance(res, (list, tuple)) else res)
        try:
            so.LOGG_DIR.mkdir(parents=True, exist_ok=True)
            dst = so.LOGG_DIR / (norm + src.suffix.lower())
            # Om befintlig logga hade annan suffix, ta bort den
            for sfx in (".png", ".jpg", ".jpeg"):
                old = so.LOGG_DIR / (norm + sfx)
                if old.exists() and old != dst:
                    old.unlink()
            shutil.copy2(src, dst)
        except Exception as e:
            self._logga(f"[logga] kunde inte spara: {e}\n", "fel")
            return {"ok": False, "fel": f"Kunde inte spara: {e}"}
        self._logga(f"[logga] sparad: {dst.name} ({lag_namn})\n")
        return {"ok": True, "fil": dst.name, "lag": lag_namn}

    def loggor_lista(self, _d=None):
        """Returnerar alla loggor i biblioteket med miniatyr (base64)."""
        from cull import story_overlay as so
        so.LOGG_DIR.mkdir(parents=True, exist_ok=True)
        poster = []
        for p in sorted(so.LOGG_DIR.iterdir()):
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                continue
            thumb = _b64_thumb(p, (80, 80))
            poster.append({"fil": p.name, "stem": p.stem, "thumb": thumb})
        return {"loggor": poster, "mapp": str(so.LOGG_DIR)}

    def logga_slet(self, d):
        """Tar bort en logga ur biblioteket."""
        from cull import story_overlay as so
        fil = (d.get("logga_fil") or "").strip()
        if not fil:
            return {"ok": False}
        p = so.LOGG_DIR / fil
        if p.exists() and p.parent == so.LOGG_DIR:
            p.unlink()
            return {"ok": True}
        return {"ok": False}

    # --- Bildsvepet (Claude web search) → Instagram-bildtext -----------------
    def bildsvep(self, d):
        import re as _re
        matchinfo = (d.get("matchinfo") or "").strip()
        sport = (d.get("sport") or "").strip()
        farg = (d.get("hemma_farg") or "").strip()

        def jobb():
            from cull import bildsvep as bs
            data = bs.generera(matchinfo, sport, farg, logg=self._work)
            if not data:
                self._js("window.dpcBildsvep(null)")
                return
            try:
                slug = (_re.sub(r"[^\w-]+", "_", matchinfo).strip("_")[:60] or "match")
                mapp = gui.CONFIG_DIR / "bildsvep"
                mapp.mkdir(parents=True, exist_ok=True)
                (mapp / f"{slug}_referat.txt").write_text(
                    data.get("referat", ""), encoding="utf-8")
                (mapp / f"{slug}_bildsvep.txt").write_text(
                    data.get("bildsvep", ""), encoding="utf-8")
            except Exception:
                pass
            self._js(f"window.dpcBildsvep({json.dumps(data, ensure_ascii=False)})")

        threading.Thread(target=jobb, daemon=True).start()

    def bildsvep_hamta(self, d):
        """Returnerar sparad {bildsvep, referat} för matchinfo, annars None."""
        import re as _re
        matchinfo = (d.get("matchinfo") or "").strip()
        slug = (_re.sub(r"[^\w-]+", "_", matchinfo).strip("_")[:60] or "match")
        mapp = gui.CONFIG_DIR / "bildsvep"
        f = mapp / f"{slug}_bildsvep.txt"
        if not f.exists():
            return None
        try:
            fr = mapp / f"{slug}_referat.txt"
            return {"bildsvep": f.read_text(encoding="utf-8"),
                    "referat": fr.read_text(encoding="utf-8") if fr.exists() else "",
                    "sparad": True}
        except Exception:
            return None

    # --- Läs laguppställnings-ark (Claude vision) → roster + matchinfo --------
    def las_lineup(self, d):
        import webview
        try:
            res = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=str(Path.home() / "Downloads"),
                file_types=("Ark (*.heic;*.heif;*.jpg;*.jpeg;*.png;*.pdf)",
                            "Alla filer (*.*)"))
        except Exception:
            res = None
        if not res:
            self._js("closeSheet()")
            return
        path = res[0] if isinstance(res, (list, tuple)) else res
        sport = (d.get("sport") or "").strip()

        def jobb():
            from cull import las_lineup as ll
            self._js('window.dpcMatchLoading("Läser arket med Claude vision…")')
            data = ll.las(path, sport, logg=self._work)
            if not data:
                self._js("window.dpcMatch(null)")
                return
            self._js(f"window.dpcMatch({json.dumps(data, ensure_ascii=False)})")

        threading.Thread(target=jobb, daemon=True).start()

    # --- Hämta spelare (fas 1, Claude web search) → trupp + handles ----------
    def hamta_spelare(self, d):
        """Fas 1: sök spelartruppens profiler och handles på klubbsidor.
        Mergar med befintliga spelare i matchposten (bevarar start-flaggor)."""
        mid    = (d.get("id") or "").strip()
        lag_h  = (d.get("lag_hemma") or "").strip()
        lag_b  = (d.get("lag_borta") or "").strip()
        sport  = (d.get("sport") or "").strip()

        def jobb():
            from cull import hamta_match as hm
            data = hm.hamta_spelare(lag_h, lag_b, sport, logg=self._work)
            if not data:
                self._js("window.dpcMatch(null)")
                return
            if mid:
                lista = gui.ladda_matcher()
                m = next((x for x in lista if x.get("id") == mid), None)
                if m:
                    data["spelare"] = self._slå_ihop_spelare(
                        m.get("spelare", []), data.get("spelare", []),
                        bevara_start=True)
            data["_mid"] = mid
            self._js(f"window.dpcMatch({json.dumps(data, ensure_ascii=False)})")

        threading.Thread(target=jobb, daemon=True).start()

    # --- Hämta uppställning (fas 2, Claude web search) → startande elva -----
    def hamta_uppstallning(self, d):
        """Fas 2: sök officiell startuppställning ~1h innan match.
        Mergar med befintliga spelare — bevarar handles/info från fas 1."""
        mid    = (d.get("id") or "").strip()
        lag_h  = (d.get("lag_hemma") or "").strip()
        lag_b  = (d.get("lag_borta") or "").strip()
        datum  = (d.get("datum") or "").strip()
        sport  = (d.get("sport") or "").strip()

        def jobb():
            from cull import hamta_match as hm
            data = hm.hamta_uppstallning(lag_h, lag_b, datum, sport,
                                         logg=self._work)
            if not data:
                self._js("window.dpcMatch(null)")
                return
            if mid:
                lista = gui.ladda_matcher()
                m = next((x for x in lista if x.get("id") == mid), None)
                if m:
                    data["spelare"] = self._slå_ihop_spelare(
                        m.get("spelare", []), data.get("spelare", []),
                        bevara_start=False)
            data["_mid"] = mid
            self._js(f"window.dpcMatch({json.dumps(data, ensure_ascii=False)})")

        threading.Thread(target=jobb, daemon=True).start()

    def spara_roster(self, rader, namn):
        """rader = [{nr, namn, lag?}] → roster-CSV. Har någon rad 'lag' (hemma/
        borta) skrivs en 3-kolumns 'nummer,namn,lag' så båda lagen kan namnsättas
        (samma nummer i olika lag). Returnerar sökvägen."""
        return self._skriv_roster_csv(rader, namn)

    # --- Steg 2: manuell nummer-genomgång (luckorna) -------------------------
    def osakra_data(self):
        from cull import nummer_pass, roster as roster_mod
        try:
            data = json.loads(nummer_pass.OSAKRA_PATH.read_text(encoding="utf-8"))
            bilder = data.get("bilder", [])
        except Exception:
            bilder = []
        ut = []
        for b in bilder:
            prev = b.get("preview") or b.get("fil")
            thumb = _b64_thumb(Path(prev), (260, 195)) if prev else None
            if not thumb:
                continue
            ut.append({"stam": b["stam"], "thumb": thumb})
        rost = roster_mod.las_roster(gui.ladda_installningar().get("roster", ""))
        roster = [{"nr": nr, "namn": rost[nr]}
                  for nr in sorted(rost, key=lambda n: int(n))]
        return {"bilder": ut, "roster": roster}

    def osakra_satt(self, stam, nummer):
        from cull import nummer_pass, roster as roster_mod
        nummer = [str(n).strip() for n in (nummer or []) if str(n).strip().isdigit()]
        try:
            data = json.loads(nummer_pass.OSAKRA_PATH.read_text(encoding="utf-8"))
        except Exception:
            return False
        katalog = Path(data.get("katalog", ""))
        filer = ([p for p in katalog.iterdir()
                  if p.stem == stam and p.suffix.lower() in nummer_pass.BILD_SUFFIX]
                 if katalog.is_dir() else [])
        lag_rost = roster_mod.las_roster_lag(gui.ladda_installningar().get("roster", ""))
        if nummer and filer:
            traffar = [(nr, nummer_pass._namn_unikt(nr, lag_rost)) for nr in nummer]
            nummer_pass._skriv_keywords(filer, traffar, nummer_pass._env())
        # Grundsanning (facit) för framtida träning.
        try:
            facit = (json.loads(nummer_pass.FACIT_PATH.read_text(encoding="utf-8"))
                     if nummer_pass.FACIT_PATH.exists() else {})
        except Exception:
            facit = {}
        facit[stam] = nummer
        try:
            nummer_pass.FACIT_PATH.write_text(
                json.dumps(facit, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        # Uppdatera nummer-cachen (kalla=manuell) och ta bort stammen ur luckorna.
        cache = nummer_pass._ladda_cache()
        for f in filer:
            cache[nummer_pass._nyckel(f)] = {"nummer": nummer, "n_personer": 1,
                                             "kalla": "manuell"}
        nummer_pass._spara_cache(cache)
        data["bilder"] = [x for x in data.get("bilder", []) if x.get("stam") != stam]
        try:
            nummer_pass.OSAKRA_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return True

    # --- Granska osäkra (aktiv inlärning) ------------------------------------
    def granska_data(self):
        try:
            data = json.loads(gui.AKTIV_PATH.read_text(encoding="utf-8"))
            bilder = data.get("bilder", [])
        except Exception:
            bilder = []
        from cull import inlarning
        sparade = inlarning.ladda_manuella_etiketter()
        ut = []
        for b in bilder:
            t = Path(b.get("thumb", ""))
            if not t.exists():
                continue
            thumb = _b64_thumb(t, (260, 195))
            if not thumb:
                continue
            ut.append({"stem": b["stem"], "p": round(b.get("modell_p", 0), 2),
                       "thumb": thumb, "etikett": sparade.get(b["stem"])})
        return {"bilder": ut}

    def satt_etikett(self, stem, behall):
        from cull import inlarning
        inlarning.spara_manuell_etikett(stem, bool(behall))
        return True

    # --- Jämför par (parvis preferens) ---------------------------------------
    def par_data(self):
        try:
            data = json.loads(gui.AKTIV_PATH.read_text(encoding="utf-8"))
            bilder = [b for b in data.get("bilder", [])
                      if Path(b.get("thumb", "")).exists()]
        except Exception:
            bilder = []
        par = []
        for i in range(0, len(bilder) - 1, 2):
            kort = []
            for b in (bilder[i], bilder[i + 1]):
                thumb = _b64_thumb(Path(b["thumb"]), (440, 330))
                kort.append({"stem": b["stem"],
                             "p": round(b.get("modell_p", 0), 2), "thumb": thumb})
            if all(k["thumb"] for k in kort):
                par.append(kort)
        return {"par": par}

    def valj_par(self, vinst, forl):
        from cull import inlarning
        inlarning.spara_par(vinst, forl)
        inlarning.spara_manuell_etikett(vinst, True)
        inlarning.spara_manuell_etikett(forl, False)
        return True

    # --- Histogram (poängfördelning senaste körningen) -----------------------
    def histogram_data(self):
        try:
            hist = json.loads(gui.KOR_HIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            hist = []
        if not hist:
            return {"tom": True}
        kor = hist[-1]
        poang = kor.get("poang", [])
        if not poang:
            return {"tom": True}
        n_valda = kor.get("n_valda", 0)
        trosk = (sorted(poang, reverse=True)[min(n_valda, len(poang)) - 1]
                 if n_valda else max(poang))
        return {"katalog": Path(kor.get("katalog", "")).name, "n_valda": n_valda,
                "n_total": kor.get("n_total", len(poang)),
                "tid": kor.get("tid", ""), "poang": poang, "trosk": trosk}

    # --- Jämför körningar ----------------------------------------------------
    def korningar_data(self):
        try:
            hist = json.loads(gui.KOR_HIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            hist = []
        ut = [{"label": (f"{k.get('tid', '?')}  {Path(k.get('katalog', '')).name}"
                         f"  ({k.get('n_valda', 0)} val)"),
               "valda": k.get("valda", [])} for k in reversed(hist)]
        return {"korningar": ut}

    def jamfor_levererat(self, _d=None):
        """Jämför en levererad mapp (t.ex. Pixieset-JPG:erna) mot cull-historiken:
        hittar vilken körning den motsvarar och visar hur många av cullens picks
        som levererades vs föll bort i din manuella gallring. Matchar på filstam
        (JPG-export behåller NEF-namnet)."""
        import webview
        try:
            res = self.window.create_file_dialog(
                webview.FOLDER_DIALOG, directory=str(Path.home()))
        except Exception as e:
            return {"ok": False, "fel": f"Dialogfel: {e}"}
        if not res:
            return {"ok": False, "fel": "Avbruten"}
        mapp = Path(res[0] if isinstance(res, (list, tuple)) else res)
        EXIF = {".jpg", ".jpeg", ".nef", ".dng", ".cr3", ".cr2", ".arw",
                ".raf", ".rw2", ".orf"}
        lev = {p.stem.lower() for p in mapp.rglob("*")
               if p.is_file() and p.suffix.lower() in EXIF
               and not p.name.startswith(".")}
        if not lev:
            return {"ok": False, "fel": "Inga bildfiler i den valda mappen."}
        try:
            hist = json.loads(gui.KOR_HIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            hist = []
        rader = []
        tackta = set()
        for k in hist:
            vs = {Path(n).stem.lower() for n in k.get("valda", [])}
            if not vs:
                continue
            ov = vs & lev
            if not ov:
                continue
            tackta |= ov
            ud = Path(k.get("ut_dir", ""))
            rader.append({
                "tid": (k.get("tid", "") or "")[:16],
                "namn": f"{ud.parent.name} / {ud.name}" if ud.name else ud.name,
                "n_culled": len(vs),
                "n_levererade": len(ov),
                "n_bortfall": len(vs - lev),
                "bortfall": sorted(s for s in (vs - lev))[:60],
            })
        rader.sort(key=lambda r: -r["n_levererade"])
        return {"ok": True, "mapp": str(mapp), "n_levererat": len(lev),
                "ej_tackt": len(lev - tackta), "rader": rader[:8]}

    # --- Historik (tidigare urval) -------------------------------------------
    def historik_data(self):
        ut = []
        for p in gui.ladda_historik():
            path = p.get("path", "")
            mp = Path(path)
            try:
                datum = datetime.fromtimestamp(p["tid"]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                datum = ""
            ut.append({"path": path, "rubrik": f"{mp.parent.name}  ›  {mp.name}",
                       "antal": p.get("antal", "?"), "datum": datum,
                       "finns": mp.exists()})
        return {"poster": ut}

    def historik_ta_bort(self, path):
        gui.spara_historik([p for p in gui.ladda_historik()
                            if p.get("path") != path])
        return self.historik_data()

    def oppna_finder(self, path):
        if path and Path(path).exists():
            try:
                subprocess.Popen(["open", str(path)])
            except Exception:
                pass
        return True

    # --- En miniatyr per urval-mapp (väljaren / Instagram-galleriet) ---------
    def urval_thumb(self, path):
        mapp = Path((path or "").strip())
        if not mapp.is_dir():
            return None
        try:
            filer = sorted((p for p in mapp.iterdir()
                            if p.suffix.lower() in VISA_SUFFIX
                            and not p.name.startswith(".")), key=lambda p: p.name)
        except Exception:
            filer = []
        for p in filer:
            thumb = _thumb_for(p, _env(), maxsize=(360, 270))
            if thumb:
                return {"thumb": thumb}
        return None

    # --- Visa urval (miniatyr-rutnät, strömmas) ------------------------------
    def valj_urval_mapp(self, start):
        return self.valj_mapp(start or "")

    def urval_ladda(self, mapp):
        mapp = Path((mapp or "").strip())

        def jobb():
            try:
                alla = [p for p in mapp.iterdir()
                        if p.suffix.lower() in VISA_SUFFIX
                        and not p.name.startswith(".")]
            except Exception:
                alla = []
            # En miniatyr per bild: föredra raw (NEF) framför jpg-export med samma stam.
            per_stem = {}
            for p in alla:
                vald = per_stem.get(p.stem)
                if vald is None or (p.suffix.lower() in RAW_SUFFIX
                                    and vald.suffix.lower() not in RAW_SUFFIX):
                    per_stem[p.stem] = p
            filer = sorted(per_stem.values(), key=lambda p: p.name)
            self._js(f"window.dpcUrvalMeta({json.dumps(mapp.name)},{len(filer)})")
            env = _env()
            n = 0
            for p in filer:
                thumb = _thumb_for(p, env)
                if not thumb:
                    continue
                nyttolast = json.dumps({"namn": p.name, "thumb": thumb})
                self._js(f"window.dpcUrvalThumb({nyttolast})")
                n += 1
            self._js(f"window.dpcUrvalDone({n})")

        threading.Thread(target=jobb, daemon=True).start()
        return True

    # --- Okända sporter ------------------------------------------------------
    def okanda_data(self):
        try:
            rå = json.loads(OKAND_PATH.read_text(encoding="utf-8"))
        except Exception:
            rå = []
        okanda = [({"namn": p, "path": ""} if isinstance(p, str) else p) for p in rå]
        try:
            cache = json.loads(SPORT_WEBB_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
        ut = [{"namn": u.get("namn", ""), "path": u.get("path", ""),
               "sport": cache.get(u.get("namn", ""), "")} for u in okanda]
        return {"okanda": ut, "sporter": SPORTER_VAL}

    def okanda_spara(self, val):
        """val = {namn: sport}. Sparar i sport-cachen, tömmer okänd-listan,
        tränar om om någon sport sattes."""
        try:
            cache = json.loads(SPORT_WEBB_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
        nagot = False
        for namn, sport in (val or {}).items():
            if (sport or "").strip():
                cache[namn] = sport.strip()
                nagot = True
        SPORT_WEBB_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SPORT_WEBB_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        OKAND_PATH.unlink(missing_ok=True)
        return {"tranar": nagot}


def _satt_dock_ikon():
    """Sätter Dock-/app-ikonen till loggan i runtime (annars visas Python-raketen
    eftersom appen körs som 'python -m', inte som en paketerad .app)."""
    try:
        from AppKit import NSApplication, NSImage
        ikon = Path(__file__).parent / "assets" / "icon.png"
        img = NSImage.alloc().initWithContentsOfFile_(str(ikon))
        if img is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(img)
    except Exception:
        pass


def main():
    import webview
    api = Api()
    html = Path(__file__).parent / "assets" / "gui.html"
    api.window = webview.create_window(
        "Dalecarlia Photo Tools", str(html),
        width=860, height=860, min_size=(700, 640),
        background_color="#F4F4F6", js_api=api)
    try:
        api.window.events.shown += lambda *a: _satt_dock_ikon()
    except Exception:
        pass
    _satt_dock_ikon()
    webview.start()


if __name__ == "__main__":
    main()
