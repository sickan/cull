"""Webb-baserat gränssnitt (pywebview) — native fönster som hostar designens
HTML/CSS och kopplar fälten till cull-logiken. Återanvänder gui.bygg_kommando."""

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from cull import gui, version as ver
from cull.leverans import PROFILER as LEVPROF

# MediaPipe/TF Lite-skräp som loggas vid avstängning — filtreras bort.
SKRAP = ("clearcut", "Source Location Trace", "portable_clearcut",
         "playlog/cplusplus", "Not valid for uploading")


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

    # --- sekundära knappar (öppnar Finder / loggar tills vidare) -------------
    def visa_urval(self):
        self._logga("Visa urval öppnas via senaste körningens mapp "
                    "(historik kommer i nästa version).")

    def historik(self):
        try:
            subprocess.Popen(["open", str(gui.HISTORY_PATH.parent)])
        except Exception:
            pass

    def okanda_sporter(self):
        self._logga("Okända sporter: kör en träning så listas de i loggen.")

    def granska_osakra(self):
        self._logga("Granska osäkra — porteras till nya gränssnittet inom kort.")

    def jamfor_par(self):
        self._logga("Jämför par — porteras till nya gränssnittet inom kort.")

    def histogram(self):
        self._logga("Histogram — porteras till nya gränssnittet inom kort.")

    def jamfor_korningar(self):
        self._logga("Jämför körningar — porteras till nya gränssnittet inom kort.")


def main():
    import webview
    api = Api()
    html = Path(__file__).parent / "assets" / "gui.html"
    api.window = webview.create_window(
        "Dalecarlia Photo Cull", str(html),
        width=860, height=860, min_size=(700, 640),
        background_color="#F4F4F6", js_api=api)
    webview.start()


if __name__ == "__main__":
    main()
