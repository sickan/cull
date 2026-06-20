"""Grafiskt gränssnitt för cull — välj katalog och kriterier, se output live."""

import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from cull import version as ver

FARGER = ["", "blå", "ljusblå", "röd", "mörkröd", "gul", "grön",
          "vit", "svart", "orange", "lila"]

CONFIG_DIR    = Path.home() / ".config" / "cull"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
HISTORY_PATH  = CONFIG_DIR / "history.json"
SETTINGS_KEYS = ["katalog", "ai", "xmp", "rapport", "hemma_farg",
                 "bevaka", "avspark", "topp", "andel", "burst_sek",
                 "yolo", "estetik", "modell"]

MODELL_PATH = Path.home() / ".config" / "cull" / "modell.pkl"

YOLO_MODELLER = ["yolov8n.pt", "yolo11s.pt", "yolo11m.pt"]


def ladda_installningar():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def spara_installningar(vals):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for k in SETTINGS_KEYS:
        v = vals[k]
        data[k] = v.get() if hasattr(v, "get") else v
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ladda_historik():
    try:
        with open(HISTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def spara_historik(poster):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(poster, f, indent=2, ensure_ascii=False)


def lagg_till_historik(urval_mapp, antal):
    """Lägger till en post överst; tar bort dubbletter och kapar till 50."""
    poster = ladda_historik()
    poster = [p for p in poster if p.get("path") != urval_mapp]
    poster.insert(0, {
        "path": urval_mapp,
        "antal": antal,
        "tid": time.time(),
    })
    spara_historik(poster[:50])


def bygg_kommando(vals):
    katalog = vals["katalog"].get().strip()
    if not katalog:
        return None, "Välj en katalog först."

    cmd = [sys.executable, "-m", "cull.core", katalog]

    if vals["ai"].get():
        cmd.append("--ai")
        yolo = vals["yolo"].get().strip()
        if yolo:
            cmd += ["--yolo", yolo]
        if vals["estetik"].get():
            cmd.append("--estetik")

    if not vals["modell"].get():
        cmd.append("--ingen-modell")

    farg = vals["hemma_farg"].get()
    if farg:
        cmd += ["--hemma-farg", farg]

    bevaka = vals["bevaka"].get().strip()
    if bevaka:
        cmd += ["--bevaka", bevaka]

    avspark = vals["avspark"].get().strip()
    if avspark:
        cmd += ["--avspark", avspark]

    topp = vals["topp"].get().strip()
    andel = vals["andel"].get().strip()
    if topp:
        cmd += ["--topp", topp]
    elif andel:
        cmd += ["--andel", andel]

    burst = vals["burst_sek"].get().strip()
    if burst and burst != "2.0":
        cmd += ["--burst-sek", burst]

    if vals["xmp"].get():
        cmd.append("--xmp")

    if vals["rapport"].get():
        cmd.append("--rapport")

    return cmd, None


def _extrahera_preview(nef, jpg, env):
    """Extraherar inbäddad JPEG ur en NEF till `jpg`. Returnerar True vid lyckat."""
    for tag in ("-JpgFromRaw", "-PreviewImage"):
        try:
            with open(jpg, "wb") as f:
                subprocess.run(["exiftool", "-b", tag, str(nef)],
                               stdout=f, stderr=subprocess.DEVNULL,
                               timeout=15, env=env)
        except Exception:
            pass
        if jpg.exists() and jpg.stat().st_size > 10_000:
            return True
    if jpg.exists():
        jpg.unlink()
    return False


def visa_miniatyrer(fönster, urval_mapp, max_bilder=10):
    """Öppnar ett fönster med miniatyrer från urval-mappen."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return  # Pillow saknas — hoppa över miniatyrer

    mapp = Path(urval_mapp)
    # Exkludera macOS AppleDouble-skuggfiler (._namn.NEF) som dyker upp på
    # exFAT/FAT-diskar och sorteras före de riktiga filerna.
    nef_filer = sorted(p for p in mapp.iterdir()
                       if p.suffix.lower() == ".nef"
                       and not p.name.startswith("."))
    if not nef_filer:
        return

    env = os.environ.copy()
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if p not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")

    topp = tk.Toplevel(fönster)
    topp.title(f"Urval — {mapp.name}")
    topp.geometry("840x270")
    # Håll referenser levande på fönstret — annars GC:as PhotoImage och
    # rutorna blir svarta.
    topp._bild_refs = []

    canvas = tk.Canvas(topp, bg="#1a1a1a", highlightthickness=0)
    scroll_x = ttk.Scrollbar(topp, orient="horizontal", command=canvas.xview)
    canvas.configure(xscrollcommand=scroll_x.set)
    scroll_x.pack(side="bottom", fill="x")
    canvas.pack(fill="both", expand=True)

    inner = tk.Frame(canvas, bg="#1a1a1a")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    status = tk.Label(inner, text="Laddar miniatyrer…", fg="#888888",
                      bg="#1a1a1a", font=("Menlo", 11))
    status.grid(row=0, column=0, padx=20, pady=20)

    def _placera(photo, col, name):
        if col == 0:
            status.destroy()
        f = tk.Frame(inner, bg="#1a1a1a", padx=4, pady=4)
        f.grid(row=0, column=col)
        tk.Label(f, image=photo, bg="#1a1a1a").pack()
        tk.Label(f, text=name, fg="#aaaaaa", bg="#1a1a1a",
                 font=("Menlo", 9)).pack()
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def ladda_i_bakgrunden():
        col = 0
        for nef in nef_filer[:max_bilder]:
            jpg = mapp / (nef.stem + ".jpg")
            if not (jpg.exists() and jpg.stat().st_size > 10_000):
                if not _extrahera_preview(nef, jpg, env):
                    continue
            try:
                img = Image.open(jpg)
                img.thumbnail((220, 160))
                photo = ImageTk.PhotoImage(img)
            except Exception:
                continue
            topp._bild_refs.append(photo)
            c = col
            topp.after(0, lambda ph=photo, cc=c, n=nef.name: _placera(ph, cc, n))
            col += 1
        if col == 0:
            topp.after(0, lambda: status.configure(
                text="Kunde inte läsa några miniatyrer."))

    threading.Thread(target=ladda_i_bakgrunden, daemon=True).start()


def oppna_i_finder(path):
    if Path(path).exists():
        subprocess.Popen(["open", str(path)])


def visa_historik(fönster):
    """Fönster med tidigare urval — visa miniatyrer eller öppna i Finder."""
    poster = ladda_historik()

    topp = tk.Toplevel(fönster)
    topp.title("Historik — tidigare urval")
    topp.geometry("620x420")

    if not poster:
        tk.Label(topp, text="Ingen historik ännu.",
                 foreground="gray").pack(padx=20, pady=20)
        return

    canvas = tk.Canvas(topp, highlightthickness=0)
    scroll = ttk.Scrollbar(topp, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    lista = ttk.Frame(canvas, padding=6)
    canvas.create_window((0, 0), window=lista, anchor="nw")

    def rita():
        for w in lista.winfo_children():
            w.destroy()
        aktuella = ladda_historik()
        for i, post in enumerate(aktuella):
            p = post.get("path", "")
            finns = Path(p).exists()
            antal = post.get("antal", "?")
            try:
                datum = datetime.fromtimestamp(post["tid"]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                datum = ""

            rad = ttk.Frame(lista, padding=(0, 4))
            rad.grid(row=2 * i, column=0, sticky="ew")

            mapp = Path(p)
            # Visa matchnamn (mappens förälder) + urval-mappens namn
            rubrik = f"{mapp.parent.name}  ›  {mapp.name}"
            fg = "black" if finns else "#aa0000"
            ttk.Label(rad, text=rubrik, font=("Helvetica", 12, "bold"),
                      foreground=fg).grid(row=0, column=0, columnspan=3, sticky="w")
            info = f"{antal} bilder   ·   {datum}"
            if not finns:
                info += "   ·   (saknas)"
            ttk.Label(rad, text=info, foreground="gray").grid(
                row=1, column=0, columnspan=3, sticky="w")

            knappar = ttk.Frame(rad)
            knappar.grid(row=2, column=0, sticky="w", pady=(2, 0))
            ttk.Button(knappar, text="Visa miniatyrer",
                       command=lambda pp=p: visa_miniatyrer(fönster, pp),
                       state="normal" if finns else "disabled").pack(side="left")
            ttk.Button(knappar, text="Öppna i Finder",
                       command=lambda pp=p: oppna_i_finder(pp),
                       state="normal" if finns else "disabled").pack(
                       side="left", padx=6)
            ttk.Button(knappar, text="Ta bort",
                       command=lambda pp=p: ta_bort(pp)).pack(side="left")

            ttk.Separator(lista, orient="horizontal").grid(
                row=2 * i + 1, column=0, sticky="ew", pady=2)

        lista.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def ta_bort(path):
        spara_historik([p for p in ladda_historik() if p.get("path") != path])
        rita()

    rita()


def main():
    root = tk.Tk()
    root.title(ver.etikett())

    # App-ikon (titelrad/aktivitetsfält)
    ikon = ver.ikon_path()
    if ikon:
        try:
            root._ikon = tk.PhotoImage(file=str(ikon))
            root.iconphoto(True, root._ikon)
        except Exception:
            pass

    pad = {"padx": 10, "pady": 4}
    vals = {}

    saved = ladda_installningar()

    # --- Rubrik med logga och version ---
    f_topp = ttk.Frame(root)
    f_topp.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
    logo_p = ver.header_logo_path()
    if logo_p:
        try:
            root._logo = tk.PhotoImage(file=str(logo_p))
            tk.Label(f_topp, image=root._logo).pack(side="left", padx=(0, 10))
        except Exception:
            pass
    f_titel = ttk.Frame(f_topp)
    f_titel.pack(side="left", anchor="w")
    ttk.Label(f_titel, text=ver.APPNAMN,
              font=("Helvetica", 18, "bold")).pack(anchor="w")
    ttk.Label(f_titel, text=f"v{ver.version()}  ·  build {ver.BUILD}",
              foreground="#cc8400").pack(anchor="w")

    # --- Katalog ---
    f_katalog = ttk.LabelFrame(root, text="Katalog", padding=8)
    f_katalog.grid(row=1, column=0, sticky="ew", **pad)

    vals["katalog"] = tk.StringVar(value=saved.get("katalog", ""))
    ttk.Entry(f_katalog, textvariable=vals["katalog"], width=52).grid(
        row=0, column=0, padx=(0, 6))

    def valj_katalog():
        initial = vals["katalog"].get().strip() or "/"
        d = filedialog.askdirectory(title="Välj uppdragskatalog",
                                    initialdir=initial)
        if d:
            vals["katalog"].set(d)

    ttk.Button(f_katalog, text="Välj…", command=valj_katalog).grid(row=0, column=1)

    # --- Kriterier ---
    f_krit = ttk.LabelFrame(root, text="Kriterier", padding=8)
    f_krit.grid(row=2, column=0, sticky="ew", **pad)

    def rad(parent, etikett, row):
        ttk.Label(parent, text=etikett).grid(row=row, column=0, sticky="w", pady=2)

    # AI
    vals["ai"] = tk.BooleanVar(value=saved.get("ai", True))
    ttk.Checkbutton(f_krit, text="AI  (YOLO + MediaPipe Pose)",
                    variable=vals["ai"]).grid(row=0, column=0, columnspan=2,
                                              sticky="w", pady=2)

    # XMP
    vals["xmp"] = tk.BooleanVar(value=saved.get("xmp", False))
    ttk.Checkbutton(f_krit, text="Skriv XMP-sidecars  (beskärning + upprätnning)",
                    variable=vals["xmp"]).grid(row=1, column=0, columnspan=2,
                                               sticky="w", pady=2)

    # Rapport
    vals["rapport"] = tk.BooleanVar(value=saved.get("rapport", False))
    ttk.Checkbutton(f_krit, text="Rapportläge  (poängsätt, kopiera inget)",
                    variable=vals["rapport"]).grid(row=2, column=0, columnspan=2,
                                                   sticky="w", pady=2)

    ttk.Separator(f_krit, orient="horizontal").grid(
        row=3, column=0, columnspan=2, sticky="ew", pady=6)

    # Hemmalagsfärg
    rad(f_krit, "Hemmalagsfärg", 4)
    vals["hemma_farg"] = tk.StringVar(value=saved.get("hemma_farg", ""))
    ttk.Combobox(f_krit, textvariable=vals["hemma_farg"],
                 values=FARGER, width=14, state="readonly").grid(
        row=4, column=1, sticky="w")

    # Bevaka tröjnummer
    rad(f_krit, "Bevaka tröjnummer", 5)
    vals["bevaka"] = tk.StringVar(value=saved.get("bevaka", ""))
    ttk.Entry(f_krit, textvariable=vals["bevaka"], width=16).grid(
        row=5, column=1, sticky="w")
    ttk.Label(f_krit, text="  t.ex. 9,11", foreground="gray").grid(
        row=5, column=2, sticky="w")

    # Avspark
    rad(f_krit, "Avspark", 6)
    vals["avspark"] = tk.StringVar(value=saved.get("avspark", ""))
    ttk.Entry(f_krit, textvariable=vals["avspark"], width=8).grid(
        row=6, column=1, sticky="w")
    ttk.Label(f_krit, text="  HH:MM", foreground="gray").grid(
        row=6, column=2, sticky="w")

    # Topp / Andel
    rad(f_krit, "Behåll", 7)
    f_behall = ttk.Frame(f_krit)
    f_behall.grid(row=7, column=1, columnspan=2, sticky="w")
    vals["topp"] = tk.StringVar(value=saved.get("topp", ""))
    vals["andel"] = tk.StringVar(value=saved.get("andel", "0.20"))
    ttk.Entry(f_behall, textvariable=vals["topp"], width=6).pack(side="left")
    ttk.Label(f_behall, text=" bilder  eller  andel ").pack(side="left")
    ttk.Entry(f_behall, textvariable=vals["andel"], width=6).pack(side="left")

    # Burst-sek
    rad(f_krit, "Burst-gräns (sek)", 8)
    vals["burst_sek"] = tk.StringVar(value=saved.get("burst_sek", "2.0"))
    ttk.Entry(f_krit, textvariable=vals["burst_sek"], width=8).grid(
        row=8, column=1, sticky="w")

    ttk.Separator(f_krit, orient="horizontal").grid(
        row=9, column=0, columnspan=3, sticky="ew", pady=6)

    # YOLO-modell
    rad(f_krit, "YOLO-modell", 10)
    vals["yolo"] = tk.StringVar(value=saved.get("yolo", "yolo11s.pt"))
    ttk.Combobox(f_krit, textvariable=vals["yolo"], values=YOLO_MODELLER,
                 width=14, state="readonly").grid(row=10, column=1, sticky="w")
    ttk.Label(f_krit, text="  n=snabb · s=balans · m=bäst",
              foreground="gray").grid(row=10, column=2, sticky="w")

    # NIMA-estetik
    vals["estetik"] = tk.BooleanVar(value=saved.get("estetik", False))
    ttk.Checkbutton(f_krit, text="NIMA-estetikbetyg  (lärt bildkvalitetsmått)",
                    variable=vals["estetik"]).grid(
        row=11, column=0, columnspan=3, sticky="w", pady=2)

    # Personlig modell
    finns_modell = MODELL_PATH.exists()
    vals["modell"] = tk.BooleanVar(value=saved.get("modell", True))
    etikett = ("Personlig modell  (tränad på dina FilterPix-val)"
               if finns_modell else
               "Personlig modell  (ingen tränad ännu — kör Träna modell…)")
    ttk.Checkbutton(f_krit, text=etikett, variable=vals["modell"],
                    state="normal" if finns_modell else "disabled").grid(
        row=12, column=0, columnspan=3, sticky="w", pady=2)

    # --- Progress ---
    f_progress = ttk.Frame(root)
    f_progress.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 0))

    progress_var = tk.DoubleVar(value=0)
    progress = ttk.Progressbar(f_progress, variable=progress_var,
                               maximum=100, length=500)
    progress.pack(side="left", fill="x", expand=True)

    räknare_var = tk.StringVar(value="")
    ttk.Label(f_progress, textvariable=räknare_var, width=12,
              anchor="e").pack(side="right")

    # --- Kör-knapp ---
    f_knapp = ttk.Frame(root)
    f_knapp.grid(row=4, column=0, sticky="e", padx=10, pady=4)

    status_var = tk.StringVar(value="")
    ttk.Label(f_knapp, textvariable=status_var, foreground="gray").pack(
        side="left", padx=8)

    knapp = ttk.Button(f_knapp, text="Kör cull")
    knapp.pack(side="right")

    def visa_befintligt_urval():
        start = vals["katalog"].get().strip() or "/"
        d = filedialog.askdirectory(title="Välj urval-mapp att visa",
                                    initialdir=start)
        if d:
            visa_miniatyrer(root, d)

    ttk.Button(f_knapp, text="Visa urval…",
               command=visa_befintligt_urval).pack(side="right", padx=6)

    ttk.Button(f_knapp, text="Historik…",
               command=lambda: visa_historik(root)).pack(side="right")

    # --- Logg ---
    f_logg = ttk.LabelFrame(root, text="Output", padding=8)
    f_logg.grid(row=5, column=0, sticky="nsew", **pad)

    logg = tk.Text(f_logg, width=80, height=20, font=("Menlo", 11),
                   state="disabled", wrap="word")
    scroll = ttk.Scrollbar(f_logg, command=logg.yview)
    logg.configure(yscrollcommand=scroll.set)
    logg.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    def skriv(text, tag=None):
        logg.configure(state="normal")
        logg.insert("end", text, tag or ())
        logg.see("end")
        logg.configure(state="disabled")

    logg.tag_configure("fel", foreground="#cc0000")
    logg.tag_configure("klar", foreground="#007700")

    def trana_modell():
        rot = filedialog.askdirectory(
            title="Välj rotkatalog med dina FilterPix-urval",
            initialdir=vals["katalog"].get().strip() or "/")
        if not rot:
            return
        cmd = [sys.executable, "-m", "cull.inlarning", rot]
        knapp.configure(state="disabled")
        trana_knapp.configure(state="disabled")
        status_var.set("Tränar modell…")
        logg.configure(state="normal")
        logg.delete("1.0", "end")
        logg.configure(state="disabled")
        skriv("$ " + " ".join(cmd) + "\n\n")
        progress["mode"] = "indeterminate"
        progress.start(12)

        SKRAP = ("clearcut", "Source Location", "playlog",
                 "landmark_projection", "Loading pretrained")

        def kör():
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            for p in ("/opt/homebrew/bin", "/usr/local/bin"):
                if p not in env.get("PATH", "").split(os.pathsep):
                    env["PATH"] = p + os.pathsep + env.get("PATH", "")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    bufsize=1, env=env)
            for rad in proc.stdout:
                if not any(s in rad for s in SKRAP):
                    root.after(0, skriv, rad)
            proc.wait()
            ok = proc.returncode == 0
            root.after(0, progress.stop)
            root.after(0, lambda: progress.configure(mode="determinate"))
            root.after(0, lambda: progress_var.set(0))
            root.after(0, lambda: status_var.set(
                "Modell tränad ✓" if ok else "Tränings­fel ✗"))
            root.after(0, lambda: skriv(
                "\n✓ Klar.\n" if ok else "\n✗ Avslutades med fel.\n",
                "klar" if ok else "fel"))
            root.after(0, lambda: knapp.configure(state="normal"))
            root.after(0, lambda: trana_knapp.configure(state="normal"))

        threading.Thread(target=kör, daemon=True).start()

    trana_knapp = ttk.Button(f_knapp, text="Träna modell…",
                             command=trana_modell)
    trana_knapp.pack(side="right", padx=6)

    def kor():
        cmd, fel = bygg_kommando(vals)
        if fel:
            status_var.set(fel)
            return

        spara_installningar(vals)

        knapp.configure(state="disabled")
        status_var.set("Kör…")
        progress_var.set(0)
        räknare_var.set("")
        logg.configure(state="normal")
        logg.delete("1.0", "end")
        logg.configure(state="disabled")
        skriv("$ " + " ".join(cmd) + "\n\n")

        totalt       = [0]
        pulsande     = [False]
        urval_mapp   = [None]   # fångar "kopierade till: <path>"
        urval_antal  = [0]

        re_total    = re.compile(r"^(\d+) NEF hittade")
        re_framsteg = re.compile(r"…(\d+)/(\d+)")
        re_hoppar   = re.compile(r"\[(\d+)/(\d+)\]")
        re_urval    = re.compile(r"(\d+) NEF kopierade till:\s*(.+)$")

        PULS_START = ("Laddar AI", "Hämtar metadata", "Extraherar previews",
                      "AI-analys på topp")
        PULS_STOPP = ("AI-modeller redo", "Avspark", "previews extraherade",
                      "AI klar", "Baspoängsätter")

        def starta_puls():
            pulsande[0] = True
            progress["mode"] = "indeterminate"
            progress.start(12)

        def stoppa_puls():
            if pulsande[0]:
                pulsande[0] = False
                progress.stop()
                progress["mode"] = "determinate"

        def uppdatera_progress(aktuell, total):
            stoppa_puls()
            if total > 0:
                progress_var.set(aktuell / total * 100)
                räknare_var.set(f"{aktuell} / {total}")

        # MediaPipe/TF Lite-telemetri (clearcut) loggar från en bakgrundstråd
        # vid avstängning, efter att stderr-redirecten stängts. Ofarligt —
        # filtreras bort så loggen hålls ren.
        SKRAP = ("clearcut", "Source Location Trace", "portable_clearcut",
                 "playlog/cplusplus", "Not valid for uploading")

        def hantera_rad(rad):
            if any(s in rad for s in SKRAP):
                return
            skriv(rad)
            rad_s = rad.strip()

            if any(rad_s.startswith(p) for p in PULS_START):
                starta_puls()
                return
            if any(p in rad_s for p in PULS_STOPP):
                stoppa_puls()

            m = re_total.match(rad_s)
            if m:
                totalt[0] = int(m.group(1))
                return
            m = re_framsteg.search(rad)
            if m:
                uppdatera_progress(int(m.group(1)), int(m.group(2)))
                return
            m = re_hoppar.search(rad)
            if m:
                uppdatera_progress(int(m.group(1)), int(m.group(2)))
                return
            m = re_urval.search(rad_s)
            if m:
                urval_antal[0] = int(m.group(1))
                urval_mapp[0] = m.group(2).strip()

        def kör_process():
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            # Säkerställ att Homebrew-binärer (exiftool) hittas även när
            # appen startats från Finder/Dock med en minimal PATH.
            extra = ["/opt/homebrew/bin", "/usr/local/bin"]
            befintlig = env.get("PATH", "").split(os.pathsep)
            env["PATH"] = os.pathsep.join(
                [p for p in extra if p not in befintlig] + befintlig)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            for rad in proc.stdout:
                root.after(0, hantera_rad, rad)
            proc.wait()
            ok = proc.returncode == 0
            root.after(0, stoppa_puls)
            root.after(0, lambda: progress_var.set(100))
            root.after(0, lambda: räknare_var.set(
                f"{totalt[0]} / {totalt[0]}" if totalt[0] else ""))
            root.after(0, lambda: status_var.set("Klart ✓" if ok else "Fel ✗"))
            root.after(0, lambda: skriv(
                "\n✓ Klar.\n" if ok else "\n✗ Avslutades med fel.\n",
                "klar" if ok else "fel"
            ))
            root.after(0, lambda: knapp.configure(state="normal"))
            if ok and urval_mapp[0]:
                lagg_till_historik(urval_mapp[0], urval_antal[0])
                root.after(500, lambda: visa_miniatyrer(root, urval_mapp[0]))

        threading.Thread(target=kör_process, daemon=True).start()

    knapp.configure(command=kor)

    # Centrera och tvinga fram fönstret. OBS: sätt INTE resizable(False, False)
    # på ett tomt fönster — på Tk 9.0/macOS låser det storleken till ~21x52 och
    # innehåll som läggs till efteråt växer inte fönstret (osynlig app).
    root.update_idletasks()
    w = max(root.winfo_reqwidth(), 600)
    h = max(root.winfo_reqheight(), 700)
    sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
    x = max(0, (sx - w) // 2)
    y = max(0, (sy - h) // 3)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(w, h)
    root.update()
    root.lift()
    root.attributes("-topmost", True)
    root.after(1200, lambda: root.attributes("-topmost", False))
    try:
        root.focus_force()
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
