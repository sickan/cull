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
    m = re.search(r"(v[\d.]+).*?build ([\d-]+)", ver.etikett())
    return f"{m.group(1)} · build {m.group(2)}" if m else ver.etikett()


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
        ok = proc.returncode == 0
        self._logga("\n✓ Klar." if ok else "\n✗ Avslutades med fel.",
                    "ok" if ok else "err")
        self._js(f"window.dpcDone({'true' if ok else 'false'})")

    # --- kör cull ------------------------------------------------------------
    def kor(self, d):
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
            rot = self.valj_mapp("")
            if not rot:
                self._js("window.dpcDone(false)")
                return
            self._js(f"document.getElementById('trana_rot').value={json.dumps(rot)}")
        cmd = [sys.executable, "-m", "cull.inlarning", rot, "--max-neg", "100"]
        yolo = (d.get("yolo") or "").strip()
        if yolo:
            cmd += ["--yolo", yolo]
        if d.get("estetik"):
            cmd += ["--estetik-motor", (d.get("estetik_motor") or "nima").lower()]
        threading.Thread(target=self._stream, args=(cmd,), daemon=True).start()

    # --- efterbehandla en exporterad mapp ------------------------------------
    def efterbehandla(self, d):
        mapp = self.valj_mapp(d.get("export_rot") or "")
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

    # --- läs tröjnummer på en vald mapp → XMP-keywords -----------------------
    def nummer_pass(self, d):
        mapp = self.valj_mapp(d.get("katalog") or d.get("export_rot") or "")
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
        rost = roster_mod.las_roster(gui.ladda_installningar().get("roster", ""))
        if nummer and filer:
            nummer_pass._skriv_keywords(filer, set(nummer), rost, nummer_pass._env())
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
        "Dalecarlia Photo Cull", str(html),
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
