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
                 "yolo", "estetik", "modell", "sport", "matchinfo",
                 "firande_boost", "garanti_firande", "snabb",
                 "xmp_justering", "oppna", "export_rot", "trana_rot",
                 "iptc", "fotograf", "bevaka_på", "garanti_bevaka",
                 "export_overskriv"]

OPPNA_VAL = ["Auto", "Lightroom", "DxO PureRAW", "Finder", "Inget"]

MODELL_PATH = Path.home() / ".config" / "cull" / "modell.pkl"
AKTIV_PATH    = Path.home() / ".cache" / "cull" / "aktiv_inlarning.json"
KOR_HIST_PATH = Path.home() / ".config" / "cull" / "kor_historik.json"

YOLO_MODELLER = ["yolov8n.pt", "yolo11s.pt", "yolo11m.pt"]
SPORTER = ["Auto", "Handboll", "Fotboll", "Volleyboll", "Innebandy"]


def ladda_installningar():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def spara_installningar(vals):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = ladda_installningar()   # bevara extra nycklar (t.ex. trana_rot)
    for k in SETTINGS_KEYS:
        v = vals[k]
        data[k] = v.get() if hasattr(v, "get") else v
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ladda_trana_rot():
    """Senast använda träningsrot (facit-rot), kom ihåg mellan körningar."""
    return ladda_installningar().get("trana_rot", "")


def spara_trana_rot(p):
    data = ladda_installningar()
    data["trana_rot"] = p
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _trana_rot_default():
    """Vettig startpunkt för träningsdialogen: ihågkommen rot → Dropbox/Export → hem."""
    kom_ihag = ladda_trana_rot()
    if kom_ihag and Path(kom_ihag).is_dir():
        return kom_ihag
    gissning = Path.home() / "Dropbox" / "Export"
    return str(gissning) if gissning.is_dir() else str(Path.home())


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


def _lightroom_finns():
    """True om Lightroom Classic/CC är installerat (för att hoppa över
    miniatyr-popupen när urvalet ändå öppnas i Lightroom)."""
    for app in ("/Applications/Adobe Lightroom Classic/Adobe Lightroom Classic.app",
                "/Applications/Adobe Lightroom Classic.app",
                "/Applications/Adobe Lightroom/Adobe Lightroom.app",
                "/Applications/Adobe Lightroom.app"):
        if Path(app).exists():
            return True
    return False


def _omonterad_disk(path):
    """Diskens namn om sökvägen ligger på en omonterad /Volumes-disk, annars None."""
    delar = Path(path).parts
    if len(delar) >= 3 and delar[1] == "Volumes":
        if not (Path("/Volumes") / delar[2]).exists():
            return delar[2]
    return None


def _katalog_problem(p):
    """Returnerar ett vänligt felmeddelande om katalogen inte går att använda."""
    path = Path(p)
    if path.is_dir():
        return None
    disk = _omonterad_disk(path)
    if disk:
        return f"Disken '{disk}' är inte monterad — anslut den och försök igen."
    if not path.exists():
        return f"Mappen finns inte: {path}"
    return f"'{path}' är inte en mapp."


def bygg_kommando(vals):
    katalog = vals["katalog"].get().strip()
    if not katalog:
        return None, "Välj en katalog först."
    problem = _katalog_problem(katalog)
    if problem:
        return None, problem

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

    sport = vals["sport"].get()
    if sport and sport.lower() != "auto":
        cmd += ["--sport", sport.lower()]

    matchinfo = vals["matchinfo"].get().strip()
    if matchinfo:
        cmd += ["--ut-namn", matchinfo]

    if vals["export_overskriv"].get():
        cmd.append("--export-overskriv")

    export_rot = vals["export_rot"].get().strip()
    if export_rot:
        disk = _omonterad_disk(export_rot)
        if disk:
            return None, f"Export-disken '{disk}' är inte monterad."
        cmd += ["--export-rot", export_rot]

    if vals["iptc"].get():
        cmd.append("--iptc")
        fotograf = vals["fotograf"].get().strip()
        if fotograf:
            cmd += ["--fotograf", fotograf]

    boost = int(vals["firande_boost"].get())
    if boost != 0:
        cmd += ["--firande-boost", str(boost)]

    garanti = int(vals["garanti_firande"].get())
    if garanti > 0:
        cmd += ["--garanti-firande", str(garanti)]

    garanti_b = int(vals["garanti_bevaka"].get())
    if garanti_b > 0:
        cmd += ["--garanti-bevaka", str(garanti_b)]

    if vals["snabb"].get():
        cmd.append("--snabb")

    farg = vals["hemma_farg"].get()
    if farg:
        cmd += ["--hemma-farg", farg]

    bevaka = vals["bevaka"].get().strip()
    if vals["bevaka_på"].get() and bevaka:
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

    if vals["xmp_justering"].get():
        cmd.append("--xmp-justering")

    oppna = vals["oppna"].get().strip().lower()
    oppna = {"dxo pureraw": "dxo"}.get(oppna, oppna)
    if oppna and oppna != "auto":
        cmd += ["--oppna", oppna]

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


KOLUMNER = 5
THUMB_W, THUMB_H = 210, 155


def visa_miniatyrer(fönster, urval_mapp):
    """Öppnar ett fönster med alla miniatyrer i ett rutnät (5 per rad)."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return

    mapp = Path(urval_mapp)
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
    topp.title(f"Urval — {mapp.name}  ({len(nef_filer)} bilder)")
    win_w = KOLUMNER * (THUMB_W + 12) + 24
    topp.geometry(f"{win_w}x700")
    topp.minsize(win_w, 400)
    topp._bild_refs = []

    canvas = tk.Canvas(topp, bg="#1a1a1a", highlightthickness=0)
    scroll_y = ttk.Scrollbar(topp, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll_y.set)
    scroll_y.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)

    # Scrolla med mushjulet
    canvas.bind("<MouseWheel>",
                lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    inner = tk.Frame(canvas, bg="#1a1a1a")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    status = tk.Label(inner, text="Laddar miniatyrer…", fg="#888888",
                      bg="#1a1a1a", font=("Menlo", 11))
    status.grid(row=0, column=0, columnspan=KOLUMNER, padx=20, pady=20)

    placerad = [0]

    def _placera(photo, idx, name):
        if placerad[0] == 0:
            status.destroy()
        placerad[0] += 1
        rad, kol = divmod(idx, KOLUMNER)
        f = tk.Frame(inner, bg="#1a1a1a", padx=4, pady=4)
        f.grid(row=rad, column=kol, sticky="nw")
        tk.Label(f, image=photo, bg="#1a1a1a").pack()
        tk.Label(f, text=name[:28], fg="#aaaaaa", bg="#1a1a1a",
                 font=("Menlo", 8)).pack()
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def ladda_i_bakgrunden():
        idx = 0
        for nef in nef_filer:
            jpg = mapp / (nef.stem + ".jpg")
            if not (jpg.exists() and jpg.stat().st_size > 10_000):
                if not _extrahera_preview(nef, jpg, env):
                    continue
            try:
                img = Image.open(jpg)
                img.thumbnail((THUMB_W, THUMB_H))
                photo = ImageTk.PhotoImage(img)
            except Exception:
                continue
            topp._bild_refs.append(photo)
            i = idx
            topp.after(0, lambda ph=photo, ii=i, n=nef.name: _placera(ph, ii, n))
            idx += 1
        if idx == 0:
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


# --- Poäng-histogram ---------------------------------------------------------

def visa_histogram(fönster):
    """Ritar poängfördelningen från senaste körningen med urvalströskeln."""
    try:
        hist = json.loads(KOR_HIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    if not hist:
        _info_dialog(fönster, "Inget att visa",
                     "Ingen körning loggad ännu. Kör en cull först.")
        return
    kor = hist[-1]
    poäng = kor.get("poang", [])
    if not poäng:
        _info_dialog(fönster, "Inget att visa", "Körningen saknar poängdata.")
        return

    topp = tk.Toplevel(fönster)
    topp.title(f"Poänghistogram — {Path(kor['katalog']).name}")
    W, H = 640, 380
    topp.geometry(f"{W}x{H + 90}")

    info = (f"{kor['n_valda']} valda av {kor['n_total']}   ·   "
            f"{kor.get('tid','')}")
    ttk.Label(topp, text=info, foreground="gray").pack(pady=(8, 2))

    cv = tk.Canvas(topp, width=W, height=H, bg="#1a1a1a", highlightthickness=0)
    cv.pack(padx=10, pady=6)

    lo, hi = min(poäng), max(poäng)
    spann = (hi - lo) or 1e-6
    n_bins = 30
    bins = [0] * n_bins
    for p in poäng:
        b = min(int((p - lo) / spann * n_bins), n_bins - 1)
        bins[b] += 1
    max_b = max(bins) or 1

    mx, my = 40, 20
    bw = (W - 2 * mx) / n_bins
    bottom = H - my - 18

    # Tröskel: poängen för den n_valda:te bästa bilden
    n_valda = kor.get("n_valda", 0)
    trosk = sorted(poäng, reverse=True)[min(n_valda, len(poäng)) - 1] \
        if n_valda else hi

    for i, c in enumerate(bins):
        x0 = mx + i * bw
        bin_mitt = lo + (i + 0.5) / n_bins * spann
        h = (c / max_b) * (bottom - my)
        färg = "#3a7d3a" if bin_mitt >= trosk else "#5a5a8a"
        cv.create_rectangle(x0 + 1, bottom - h, x0 + bw - 1, bottom,
                            fill=färg, outline="")
    # Tröskellinje
    tx = mx + (trosk - lo) / spann * (W - 2 * mx)
    cv.create_line(tx, my, tx, bottom, fill="#cc5555", width=2, dash=(4, 3))
    cv.create_text(tx, my - 8, text=f"tröskel {trosk:.2f}",
                   fill="#cc7777", font=("Menlo", 9))
    # Axlar
    cv.create_line(mx, bottom, W - mx, bottom, fill="#666")
    cv.create_text(mx, bottom + 10, text=f"{lo:.2f}", fill="#888",
                   font=("Menlo", 8))
    cv.create_text(W - mx, bottom + 10, text=f"{hi:.2f}", fill="#888",
                   font=("Menlo", 8))
    cv.create_text(W // 2, bottom + 10, text="poäng →", fill="#888",
                   font=("Menlo", 8))
    ttk.Label(topp, text="Grönt = valt, blått = bortvalt. "
              "En tydlig dal vid tröskeln betyder ett rent snitt.",
              foreground="gray").pack(pady=(0, 8))


# --- Jämför körningar --------------------------------------------------------

def visa_jamfor_korningar(fönster):
    """Jämför urvalet mellan två tidigare körningar (overlap + statistik)."""
    try:
        hist = json.loads(KOR_HIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    if len(hist) < 2:
        _info_dialog(fönster, "För få körningar",
                     "Minst två loggade körningar krävs för jämförelse.")
        return

    topp = tk.Toplevel(fönster)
    topp.title("Jämför körningar")
    topp.geometry("720x520")

    val = list(reversed(hist))   # nyaste först

    def etikett(k):
        return f"{k.get('tid','?')}  {Path(k['katalog']).name}  ({k['n_valda']} val)"

    rad = ttk.Frame(topp); rad.pack(fill="x", padx=10, pady=8)
    a_var = tk.StringVar(value=etikett(val[0]))
    b_var = tk.StringVar(value=etikett(val[1]))
    ttk.Label(rad, text="A:").grid(row=0, column=0, sticky="w")
    ttk.Combobox(rad, textvariable=a_var, values=[etikett(k) for k in val],
                 state="readonly", width=70).grid(row=0, column=1, pady=2)
    ttk.Label(rad, text="B:").grid(row=1, column=0, sticky="w")
    ttk.Combobox(rad, textvariable=b_var, values=[etikett(k) for k in val],
                 state="readonly", width=70).grid(row=1, column=1, pady=2)

    ut = tk.Text(topp, font=("Menlo", 11), wrap="word", height=22)
    ut.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def jamfor():
        ka = val[[etikett(k) for k in val].index(a_var.get())]
        kb = val[[etikett(k) for k in val].index(b_var.get())]
        sa, sb = set(ka.get("valda", [])), set(kb.get("valda", []))
        bada = sa & sb
        bara_a = sa - sb
        bara_b = sb - sa
        ut.delete("1.0", "end")
        ut.insert("end", f"A: {etikett(ka)}\nB: {etikett(kb)}\n\n")
        jac = len(bada) / (len(sa | sb) or 1)
        ut.insert("end", f"Gemensamma val: {len(bada)}\n")
        ut.insert("end", f"Bara i A: {len(bara_a)}\n")
        ut.insert("end", f"Bara i B: {len(bara_b)}\n")
        ut.insert("end", f"Överlapp (Jaccard): {jac:.0%}\n\n")
        if bara_a:
            ut.insert("end", "Endast i A:\n  " + "\n  ".join(sorted(bara_a)) + "\n\n")
        if bara_b:
            ut.insert("end", "Endast i B:\n  " + "\n  ".join(sorted(bara_b)) + "\n")

    ttk.Button(rad, text="Jämför", command=jamfor).grid(row=0, column=2,
                                                        rowspan=2, padx=8)
    jamfor()


# --- Aktiv inlärning: granska osäkra bilder ----------------------------------

def visa_aktiv_inlarning(fönster):
    """Visar de mest osäkra bilderna från senaste körningen för etikettering."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        _info_dialog(fönster, "Pillow saknas",
                     "Miniatyrer kräver Pillow (pip install pillow).")
        return
    try:
        data = json.loads(AKTIV_PATH.read_text(encoding="utf-8"))
        bilder = data.get("bilder", [])
    except Exception:
        bilder = []
    if not bilder:
        _info_dialog(fönster, "Inga osäkra bilder",
                     "Kör en cull med personlig modell aktiv först.")
        return

    from cull import inlarning
    sparade = inlarning.ladda_manuella_etiketter()

    topp = tk.Toplevel(fönster)
    topp.title("Aktiv inlärning — granska osäkra bilder")
    win_w = KOLUMNER * (THUMB_W + 16) + 24
    topp.geometry(f"{win_w}x720")
    topp._bild_refs = []

    ttk.Label(topp, text="Modellen var osäker på dessa. Markera Behåll/Förkasta "
              "— dina val används vid nästa träning.",
              foreground="gray").pack(pady=(8, 4))

    canvas = tk.Canvas(topp, bg="#1a1a1a", highlightthickness=0)
    sb = ttk.Scrollbar(topp, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    canvas.bind("<MouseWheel>",
                lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
    inner = tk.Frame(canvas, bg="#1a1a1a")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    def satt(stem, behall, var):
        inlarning.spara_manuell_etikett(stem, behall)
        var.set("behåll" if behall else "förkasta")

    for idx, b in enumerate(bilder):
        thumb = Path(b["thumb"])
        if not thumb.exists():
            continue
        try:
            img = Image.open(thumb)
            img.thumbnail((THUMB_W, THUMB_H))
            photo = ImageTk.PhotoImage(img)
        except Exception:
            continue
        topp._bild_refs.append(photo)
        r, c = divmod(idx, KOLUMNER)
        cell = tk.Frame(inner, bg="#1a1a1a", padx=6, pady=6)
        cell.grid(row=r, column=c, sticky="nw")
        tk.Label(cell, image=photo, bg="#1a1a1a").pack()
        tk.Label(cell, text=f"p={b['modell_p']:.2f}", fg="#aaaaaa",
                 bg="#1a1a1a", font=("Menlo", 8)).pack()
        nuv = sparade.get(b["stem"])
        sv = tk.StringVar(value=("behåll" if nuv == 1 else
                                 "förkasta" if nuv == 0 else "—"))
        knappar = tk.Frame(cell, bg="#1a1a1a"); knappar.pack()
        ttk.Button(knappar, text="Behåll", width=7,
                   command=lambda s=b["stem"], v=sv: satt(s, True, v)).pack(side="left")
        ttk.Button(knappar, text="Förkasta", width=8,
                   command=lambda s=b["stem"], v=sv: satt(s, False, v)).pack(side="left")
        tk.Label(cell, textvariable=sv, fg="#88aa88", bg="#1a1a1a",
                 font=("Menlo", 8)).pack()
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))


# --- Jämförelseläge: parvis val ----------------------------------------------

def visa_jamforelse(fönster, vals):
    """Visar osäkra bilder två och två — välj den bättre (parvis träningsdata)."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        _info_dialog(fönster, "Pillow saknas",
                     "Miniatyrer kräver Pillow (pip install pillow).")
        return
    try:
        data = json.loads(AKTIV_PATH.read_text(encoding="utf-8"))
        bilder = [b for b in data.get("bilder", []) if Path(b["thumb"]).exists()]
    except Exception:
        bilder = []
    if len(bilder) < 2:
        _info_dialog(fönster, "För få bilder",
                     "Minst två osäkra bilder krävs. Kör en cull med modell först.")
        return

    from cull import inlarning
    par = [(bilder[i], bilder[i + 1]) for i in range(0, len(bilder) - 1, 2)]

    topp = tk.Toplevel(fönster)
    topp.title("Jämför par — välj den bättre bilden")
    topp.geometry("760x560")
    topp._bild_refs = []
    idx = [0]

    ttk.Label(topp, text="Klicka på den bild du hellre levererar. "
              "Vinnaren märks Behåll, förloraren Förkasta.",
              foreground="gray").pack(pady=(8, 4))
    rad = tk.Frame(topp); rad.pack(fill="both", expand=True, padx=10, pady=10)
    status = ttk.Label(topp, text="", foreground="gray"); status.pack(pady=4)

    def ladda_par():
        for w in rad.winfo_children():
            w.destroy()
        if idx[0] >= len(par):
            status.configure(text="Klar — alla par bedömda.")
            return
        a, b = par[idx[0]]
        status.configure(text=f"Par {idx[0] + 1} av {len(par)}")
        for kol, bild in ((0, a), (1, b)):
            try:
                img = Image.open(bild["thumb"]); img.thumbnail((340, 260))
                photo = ImageTk.PhotoImage(img)
            except Exception:
                continue
            topp._bild_refs.append(photo)
            cell = tk.Frame(rad); cell.grid(row=0, column=kol, padx=12)
            lbl = tk.Label(cell, image=photo, cursor="hand2", bd=2, relief="solid")
            lbl.pack()
            lbl.bind("<Button-1>",
                     lambda e, vinst=bild, forl=(b if bild is a else a): valj(vinst, forl))
            ttk.Label(cell, text=f"p={bild['modell_p']:.2f}").pack()

    def valj(vinst, forl):
        # Parvis preferens (för learning-to-rank) + absoluta etiketter.
        inlarning.spara_par(vinst["stem"], forl["stem"])
        inlarning.spara_manuell_etikett(vinst["stem"], True)
        inlarning.spara_manuell_etikett(forl["stem"], False)
        idx[0] += 1
        ladda_par()

    ttk.Button(topp, text="Hoppa över par",
               command=lambda: (idx.__setitem__(0, idx[0] + 1), ladda_par())).pack(
        pady=(0, 8))
    ladda_par()


def _info_dialog(fönster, titel, text):
    d = tk.Toplevel(fönster)
    d.title(titel)
    d.geometry("420x140")
    ttk.Label(d, text=text, wraplength=380, justify="left").pack(
        padx=20, pady=20)
    ttk.Button(d, text="OK", command=d.destroy).pack(pady=(0, 12))


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

    pad = {"padx": 10, "pady": 2}
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
    ttk.Label(f_titel, text=f"v{ver.version()}  ·  build {ver.build()}",
              foreground="#cc8400").pack(anchor="w")

    # --- Flikar (Urval / Leverans / Modell) ---
    notebook = ttk.Notebook(root)
    notebook.grid(row=1, column=0, sticky="nsew", **pad)

    # --- Flik: Leverans (källkatalog, matchinfo, export, IPTC) ---
    f_katalog = ttk.Frame(notebook, padding=8)
    notebook.add(f_katalog, text="  Leverans  ")

    # 3-kolumners grid: col 0 = etikett, col 1 = entry (stretchar), col 2 = knapp
    f_katalog.columnconfigure(1, weight=1)

    vals["katalog"] = tk.StringVar(value=saved.get("katalog", ""))
    ttk.Entry(f_katalog, textvariable=vals["katalog"]).grid(
        row=0, column=0, columnspan=2, sticky="ew", padx=(0, 6))

    def valj_katalog():
        initial = vals["katalog"].get().strip() or "/"
        d = filedialog.askdirectory(title="Välj uppdragskatalog",
                                    initialdir=initial)
        if d:
            vals["katalog"].set(d)

    ttk.Button(f_katalog, text="Välj…", command=valj_katalog).grid(
        row=0, column=2, padx=(0, 0))

    ttk.Separator(f_katalog, orient="horizontal").grid(
        row=1, column=0, columnspan=3, sticky="ew", pady=(8, 4))

    ttk.Label(f_katalog, text="Matchinfo").grid(row=2, column=0, sticky="w", padx=(0, 8))
    vals["matchinfo"] = tk.StringVar(value=saved.get("matchinfo", ""))
    ttk.Entry(f_katalog, textvariable=vals["matchinfo"]).grid(
        row=2, column=1, sticky="ew")

    matchinfo_status = tk.StringVar(value="")

    def _formatera_matchinfo(text):
        """
        Tolkar fri text och returnerar ett snyggt formaterat mappnamn.
        Exempel: 'malmö ff växjö dff 3-0 2-0 20260531 eleda'
              →  'Malmö FF - Växjö DFF 3-0 (2-0) 20260531 Eleda'
        """
        s = text.strip()

        # Datum: YYYYMMDD eller YYYY-MM-DD → normalisera till YYYYMMDD
        datum = ""
        m = re.search(r"\b(20\d{2})[- ]?(\d{2})[- ]?(\d{2})\b", s)
        if m:
            datum = m.group(1) + m.group(2) + m.group(3)
            s = s[:m.start()].strip() + " " + s[m.end():].strip()

        # Resultat + ev. halvtid/periodresultat: N-N och (N-N) eller bara N-N N-N
        slutresultat = ""
        delresultat = ""
        # Parentesformat: (N-N)
        m = re.search(r"\((\d{1,3}-\d{1,3})\)", s)
        if m:
            delresultat = m.group(1)
            s = s[:m.start()].strip() + " " + s[m.end():].strip()
        # Slutresultat: det kvarvarande N-N-mönstret
        results = re.findall(r"\b(\d{1,3}-\d{1,3})\b", s)
        if results:
            slutresultat = results[0]
            s = re.sub(r"\b" + re.escape(results[0]) + r"\b", "", s, count=1)
            # Om ytterligare ett resultat finns och inget delresultat → halvtid
            if not delresultat and len(results) > 1:
                delresultat = results[1]
                s = re.sub(r"\b" + re.escape(results[1]) + r"\b", "", s, count=1)

        # Det som är kvar: lag och arena. Försök hitta bindestrecket som skiljer lag.
        s = re.sub(r"\s+", " ", s).strip()
        # Om användaren redan har " - " eller " vs " som separator
        for sep in [" - ", " vs ", " VS "]:
            if sep in s:
                delar = s.split(sep, 1)
                hemma = delar[0].strip().title()
                resten = delar[1].strip()
                # Sista "ordet/orden" efter laget = arena
                lag_arena = resten.rsplit(None, 1)
                borta = lag_arena[0].title() if len(lag_arena) > 1 else resten.title()
                arena = lag_arena[1].title() if len(lag_arena) > 1 else ""
                break
        else:
            # Ingen separator — anta att de två första "stora" orden = hemmalag,
            # mellersta = bortalag, sista = arena
            ord_lista = s.split()
            n = len(ord_lista)
            if n >= 4:
                hemma  = " ".join(ord_lista[:n//3 + 1]).title()
                borta  = " ".join(ord_lista[n//3 + 1:2*n//3 + 1]).title()
                arena  = " ".join(ord_lista[2*n//3 + 1:]).title()
            elif n >= 2:
                hemma, borta, arena = ord_lista[0].title(), ord_lista[1].title(), ""
            else:
                return text  # kan inte tolka

        delar = [f"{hemma} - {borta}"]
        if slutresultat:
            delar.append(slutresultat)
        if delresultat:
            delar.append(f"({delresultat})")
        if datum:
            delar.append(datum)
        if arena:
            delar.append(arena)
        return " ".join(delar)

    def sok_matchinfo():
        fraga = vals["matchinfo"].get().strip()
        if not fraga:
            return

        # Steg 1: formatera lokalt direkt (fungerar alltid, ingen nätverkslatens)
        formaterat = _formatera_matchinfo(fraga)

        # Steg 2: försök förbättra med webb i bakgrunden (valfritt)
        matchinfo_status.set("Formaterar…")
        sok_knapp.configure(state="disabled")

        def _sok():
            import urllib.parse, urllib.request, json as _json
            webb_forslag = None
            try:
                q = urllib.parse.quote(fraga + " fotbollsmatch OR handbollsmatch")
                url = (f"https://api.duckduckgo.com/?q={q}"
                       f"&format=json&no_html=1&skip_disambig=1")
                req = urllib.request.Request(url, headers={"User-Agent": "cull/1.0"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = _json.loads(r.read().decode("utf-8"))
                heading = data.get("Heading", "").strip()
                if heading and len(heading) > 5:
                    webb_forslag = heading
            except Exception:
                pass
            root.after(0, lambda: _klar(webb_forslag))

        def _klar(webb_forslag):
            sok_knapp.configure(state="normal")
            _visa_forslag(formaterat, webb_forslag)

        def _visa_forslag(lokalt, webb):
            dlg = tk.Toplevel(root)
            dlg.title("Formaterad matchinfo")
            dlg.grab_set()
            dlg.resizable(False, False)

            rad = 0
            ttk.Label(dlg, text="Formaterat förslag:",
                      foreground="gray").grid(row=rad, column=0, columnspan=2,
                                              padx=16, pady=(14, 2), sticky="w")
            rad += 1
            lokalt_var = tk.StringVar(value=lokalt)
            ttk.Entry(dlg, textvariable=lokalt_var, width=52).grid(
                row=rad, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
            rad += 1

            if webb and webb.lower() not in lokalt.lower():
                ttk.Label(dlg, text="Webb-träff:",
                          foreground="gray").grid(row=rad, column=0, columnspan=2,
                                                  padx=16, pady=(4, 2), sticky="w")
                rad += 1
                ttk.Label(dlg, text=webb,
                          font=("Helvetica", 11)).grid(
                    row=rad, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="w")
                rad += 1
                ttk.Button(dlg, text="Använd webb-träff",
                           command=lambda: [lokalt_var.set(webb)]).grid(
                    row=rad, column=0, padx=16, pady=(0, 4), sticky="w")
                rad += 1

            f_kn = ttk.Frame(dlg)
            f_kn.grid(row=rad, column=0, columnspan=2, padx=16, pady=(8, 14),
                      sticky="e")

            def acceptera():
                säkert = lokalt_var.get().replace("/", "-").replace(":", ".").strip()
                vals["matchinfo"].set(säkert)
                matchinfo_status.set("✓ Uppdaterad")
                dlg.destroy()

            ttk.Button(f_kn, text="Använd", command=acceptera).pack(
                side="left", padx=4)
            ttk.Button(f_kn, text="Avbryt",
                       command=dlg.destroy).pack(side="left")

        threading.Thread(target=_sok, daemon=True).start()

    sok_knapp = ttk.Button(f_katalog, text="Sök", command=sok_matchinfo)
    sok_knapp.grid(row=2, column=2, padx=(6, 0))

    ttk.Label(f_katalog, textvariable=matchinfo_status,
              foreground="gray").grid(row=3, column=0, sticky="w")
    ttk.Label(f_katalog,
              text="Hemmalag Bortalag Slutresultat (Halvtid) ÅÅÅÅMMDD Arena",
              foreground="gray").grid(row=3, column=1, columnspan=2, sticky="w")

    ttk.Separator(f_katalog, orient="horizontal").grid(
        row=4, column=0, columnspan=3, sticky="ew", pady=(8, 4))

    # Export-rot — exportera till <rot>/<matchinfo>/<kameratyp>/ på extern disk
    ttk.Label(f_katalog, text="Export-rot").grid(row=5, column=0, sticky="w", padx=(0, 8))
    vals["export_rot"] = tk.StringVar(value=saved.get("export_rot", ""))
    ttk.Entry(f_katalog, textvariable=vals["export_rot"]).grid(
        row=5, column=1, sticky="ew")

    def valj_export_rot():
        start = vals["export_rot"].get().strip() or "/Volumes"
        d = filedialog.askdirectory(title="Välj export-rot (basmapp på extern disk)",
                                    initialdir=start)
        if d:
            vals["export_rot"].set(d)

    ttk.Button(f_katalog, text="Välj…", command=valj_export_rot).grid(
        row=5, column=2, padx=(6, 0))
    ttk.Label(f_katalog,
              text="tom = urval i källkatalogen · annars <rot>/<matchinfo>/<kameratyp>/",
              foreground="gray").grid(row=6, column=1, columnspan=2, sticky="w")
    vals["export_overskriv"] = tk.BooleanVar(
        value=saved.get("export_overskriv", False))
    ttk.Checkbutton(f_katalog, text="Skriv över",
                    variable=vals["export_overskriv"]).grid(
        row=6, column=0, sticky="w")

    # IPTC-bildtexter (match/datum/lag/arena ur Matchinfo) + fotografnamn
    vals["iptc"] = tk.BooleanVar(value=saved.get("iptc", False))
    ttk.Checkbutton(f_katalog, text="IPTC-bildtexter",
                    variable=vals["iptc"]).grid(row=7, column=0, sticky="w",
                                                pady=(4, 0))
    f_fotograf = ttk.Frame(f_katalog)
    f_fotograf.grid(row=7, column=1, columnspan=2, sticky="w", pady=(4, 0))
    ttk.Label(f_fotograf, text="Fotograf:").pack(side="left")
    vals["fotograf"] = tk.StringVar(value=saved.get("fotograf", ""))
    ttk.Entry(f_fotograf, textvariable=vals["fotograf"], width=28).pack(
        side="left", padx=(4, 0))

    ttk.Separator(f_katalog, orient="horizontal").grid(
        row=8, column=0, columnspan=3, sticky="ew", pady=(8, 4))

    # Öppna efteråt + XMP-sidecars (leverans)
    vals["oppna"] = tk.StringVar(value=saved.get("oppna", "Auto"))
    f_oppna = ttk.Frame(f_katalog)
    f_oppna.grid(row=9, column=0, columnspan=2, sticky="w")
    ttk.Label(f_oppna, text="Öppna efteråt:").pack(side="left")
    ttk.Combobox(f_oppna, textvariable=vals["oppna"], values=OPPNA_VAL,
                 width=12, state="readonly").pack(side="left", padx=(4, 0))

    vals["xmp"] = tk.BooleanVar(value=saved.get("xmp", False))
    ttk.Checkbutton(f_katalog, text="XMP-sidecars (upprätning)",
                    variable=vals["xmp"]).grid(row=10, column=0, sticky="w", pady=2)
    vals["xmp_justering"] = tk.BooleanVar(value=saved.get("xmp_justering", False))
    ttk.Checkbutton(f_katalog, text="XMP: leveransklar",
                    variable=vals["xmp_justering"]).grid(
        row=10, column=1, columnspan=2, sticky="w", pady=2)

    # --- Flik: Urval (kriterier) ---
    f_krit = ttk.Frame(notebook, padding=8)
    notebook.add(f_krit, text="  Urval  ")

    def rad(parent, etikett, row):
        ttk.Label(parent, text=etikett).grid(row=row, column=0, sticky="w", pady=2)

    # AI + lägen (XMP/öppna ligger på Leverans-fliken)
    vals["ai"] = tk.BooleanVar(value=saved.get("ai", True))
    ttk.Checkbutton(f_krit, text="AI", variable=vals["ai"]).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=2)
    vals["snabb"] = tk.BooleanVar(value=saved.get("snabb", False))
    ttk.Checkbutton(f_krit, text="⚡ Snabbläge", variable=vals["snabb"]).grid(
        row=0, column=2, columnspan=2, sticky="w", pady=2)
    vals["rapport"] = tk.BooleanVar(value=saved.get("rapport", False))
    ttk.Checkbutton(f_krit, text="Rapportläge", variable=vals["rapport"]).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=2)

    ttk.Separator(f_krit, orient="horizontal").grid(
        row=3, column=0, columnspan=4, sticky="ew", pady=6)

    # Hemmalagsfärg
    rad(f_krit, "Hemmalagsfärg", 4)
    vals["hemma_farg"] = tk.StringVar(value=saved.get("hemma_farg", ""))
    ttk.Combobox(f_krit, textvariable=vals["hemma_farg"],
                 values=FARGER, width=14, state="readonly").grid(
        row=4, column=1, sticky="w")

    # Bevaka tröjnummer — opt-in via kryssruta (OCR är långsam på första körningen)
    vals["bevaka_på"] = tk.BooleanVar(value=saved.get("bevaka_på", False))
    ttk.Checkbutton(f_krit, text="Bevaka tröjnummer",
                    variable=vals["bevaka_på"]).grid(
        row=5, column=0, sticky="w", pady=2)
    vals["bevaka"] = tk.StringVar(value=saved.get("bevaka", ""))
    ttk.Entry(f_krit, textvariable=vals["bevaka"], width=16).grid(
        row=5, column=1, sticky="w")
    ttk.Label(f_krit, text="  t.ex. 9,11  ·  OCR (långsamt)",
              foreground="gray").grid(row=5, column=2, sticky="w")

    # Avspark
    rad(f_krit, "Avspark", 6)
    vals["avspark"] = tk.StringVar(value=saved.get("avspark", ""))
    f_avspark = ttk.Frame(f_krit)
    f_avspark.grid(row=6, column=1, columnspan=2, sticky="w")
    ttk.Entry(f_avspark, textvariable=vals["avspark"], width=8).pack(side="left")
    ttk.Label(f_avspark, text=" HH:MM", foreground="gray").pack(side="left")
    ttk.Button(f_avspark, text="Auto", width=6,
               command=lambda: vals["avspark"].set("auto")).pack(
        side="left", padx=(8, 0))
    ttk.Label(f_avspark, text="(auto)",
              foreground="gray").pack(side="left", padx=(4, 0))

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

    # Sport
    rad(f_krit, "Sport", 11)
    vals["sport"] = tk.StringVar(value=saved.get("sport", "Auto"))
    ttk.Combobox(f_krit, textvariable=vals["sport"], values=SPORTER,
                 width=14, state="readonly").grid(row=11, column=1, sticky="w")
    ttk.Label(f_krit, text="  välj rätt sportmodell",
              foreground="gray").grid(row=11, column=2, sticky="w")

    # NIMA-estetik
    vals["estetik"] = tk.BooleanVar(value=saved.get("estetik", False))
    ttk.Checkbutton(f_krit, text="NIMA-estetik",
                    variable=vals["estetik"]).grid(
        row=12, column=0, columnspan=3, sticky="w", pady=2)

    # Personlig modell
    finns_modell = MODELL_PATH.exists()
    vals["modell"] = tk.BooleanVar(value=saved.get("modell", True))
    if finns_modell:
        try:
            import pickle
            with open(MODELL_PATH, "rb") as _f:
                _pak = pickle.load(_f)
            _sport_mod = _pak.get("sport_modeller", {})
            _sport_del = (f"  [{', '.join(sorted(_sport_mod))}]"
                          if _sport_mod else "")
            etikett = (f"Personlig modell  "
                       f"({_pak.get('n_uppdrag', '?')} uppdrag, "
                       f"{_pak.get('n_valda', '?')} val{_sport_del})")
        except Exception:
            etikett = "Personlig modell  (tränad)"
    else:
        etikett = "Personlig modell  (ingen tränad ännu — kör Träna modell…)"
    ttk.Checkbutton(f_krit, text=etikett, variable=vals["modell"],
                    state="normal" if finns_modell else "disabled").grid(
        row=13, column=0, columnspan=3, sticky="w", pady=2)

    ttk.Separator(f_krit, orient="horizontal").grid(
        row=14, column=0, columnspan=3, sticky="ew", pady=6)

    # Firande-boost
    rad(f_krit, "Firande-boost", 15)
    vals["firande_boost"] = tk.IntVar(value=saved.get("firande_boost", 0))
    boost_label = tk.StringVar(value="0")
    def _upd_boost(v):
        boost_label.set(f"{int(float(v)):+d}" if int(float(v)) != 0 else "0")
    sl = ttk.Scale(f_krit, from_=-3, to=3, orient="horizontal",
                   variable=vals["firande_boost"], command=_upd_boost, length=120)
    sl.grid(row=15, column=1, sticky="w")
    ttk.Label(f_krit, textvariable=boost_label, width=4,
              anchor="w").grid(row=15, column=2, sticky="w")
    _upd_boost(saved.get("firande_boost", 0))

    # Garanterade firandeplatser
    rad(f_krit, "Garanti firande", 16)
    vals["garanti_firande"] = tk.IntVar(value=saved.get("garanti_firande", 0))
    garanti_label = tk.StringVar(value="0")
    def _upd_garanti(v):
        garanti_label.set(str(int(float(v))))
    sl2 = ttk.Scale(f_krit, from_=0, to=5, orient="horizontal",
                    variable=vals["garanti_firande"], command=_upd_garanti, length=120)
    sl2.grid(row=16, column=1, sticky="w")
    ttk.Label(f_krit, textvariable=garanti_label, width=4,
              anchor="w").grid(row=16, column=2, sticky="w")
    ttk.Label(f_krit, text="  platser",
              foreground="gray").grid(row=16, column=2, sticky="w", padx=(28, 0))
    _upd_garanti(saved.get("garanti_firande", 0))

    # Garanterade platser för bevakat tröjnummer
    rad(f_krit, "Garanti spelare", 17)
    vals["garanti_bevaka"] = tk.IntVar(value=saved.get("garanti_bevaka", 0))
    garanti_b_label = tk.StringVar(value="0")
    def _upd_garanti_b(v):
        garanti_b_label.set(str(int(float(v))))
    ttk.Scale(f_krit, from_=0, to=5, orient="horizontal",
              variable=vals["garanti_bevaka"], command=_upd_garanti_b,
              length=120).grid(row=17, column=1, sticky="w")
    ttk.Label(f_krit, textvariable=garanti_b_label, width=4,
              anchor="w").grid(row=17, column=2, sticky="w")
    ttk.Label(f_krit, text="  platser",
              foreground="gray").grid(row=17, column=2, sticky="w", padx=(28, 0))
    _upd_garanti_b(saved.get("garanti_bevaka", 0))

    # --- Träning ---
    OKAND_PATH = Path.home() / ".cache" / "cull" / "sport_okand.json"
    SPORT_WEBB_CACHE = Path.home() / ".cache" / "cull" / "sport_cache.json"
    SPORTER_VAL = ["handboll", "fotboll", "volleyboll", "innebandy"]

    # --- Flik: Modell (träning) ---
    f_trana = ttk.Frame(notebook, padding=8)
    notebook.add(f_trana, text="  Modell  ")
    f_trana.columnconfigure(1, weight=1)
    notebook.select(f_krit)   # öppna på Urval-fliken

    trana_status_var = tk.StringVar(value="")
    ttk.Label(f_trana, textvariable=trana_status_var,
              foreground="gray").grid(row=0, column=0, sticky="w")

    trana_progress_var = tk.DoubleVar(value=0)
    trana_progress = ttk.Progressbar(f_trana, variable=trana_progress_var,
                                     maximum=100)
    trana_progress.grid(row=0, column=1, sticky="ew", padx=8)

    trana_räknare_var = tk.StringVar(value="")
    ttk.Label(f_trana, textvariable=trana_räknare_var,
              width=10, anchor="e").grid(row=0, column=2)

    # Tränings-rot — synligt, sparat fält (separat från match-katalogen ovan)
    ttk.Label(f_trana, text="Tränings-rot").grid(
        row=1, column=0, sticky="w", pady=(6, 0))
    vals["trana_rot"] = tk.StringVar(value=saved.get("trana_rot", ""))
    ttk.Entry(f_trana, textvariable=vals["trana_rot"]).grid(
        row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=(6, 0))

    def valj_trana_rot():
        start = vals["trana_rot"].get().strip() or _trana_rot_default()
        d = filedialog.askdirectory(
            title="Välj facit-rot (mappen med alla matchmappar)",
            initialdir=start)
        if d:
            vals["trana_rot"].set(d)
            spara_trana_rot(d)

    ttk.Button(f_trana, text="Välj…", command=valj_trana_rot).grid(
        row=1, column=4, padx=(8, 0), pady=(6, 0))

    trana_proc = [None]   # referens till pågående subprocess

    def _klassificera_okanda():
        """Öppnar dialog för uppdrag med okänd sport och sparar svaren."""
        try:
            rå = json.loads(OKAND_PATH.read_text(encoding="utf-8"))
        except Exception:
            rå = []
        # Normalisera: stöd både gamla listan av namn och nya {namn, path}.
        okanda = [({"namn": p, "path": ""} if isinstance(p, str) else p)
                  for p in rå]
        if not okanda:
            from tkinter import messagebox
            messagebox.showinfo("Okända sporter",
                                "Inga oklassificerade uppdrag just nu.")
            return

        try:
            cache = json.loads(SPORT_WEBB_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

        dialog = tk.Toplevel(root)
        dialog.title(f"Oklassificerad sport — {len(okanda)} uppdrag")
        dialog.grab_set()

        ttk.Label(dialog,
                  text="Appen kunde inte avgöra sport för dessa uppdrag.\n"
                       "Öppna mappen för att kontrollera, välj sport, spara.",
                  justify="left").grid(row=0, column=0, columnspan=3,
                                       padx=16, pady=(14, 8), sticky="w")

        sport_vars = {}
        for i, u in enumerate(okanda):
            namn = u.get("namn", "")
            path = u.get("path", "")
            ttk.Label(dialog, text=namn, anchor="w").grid(
                row=i + 1, column=0, padx=(16, 8), pady=3, sticky="w")
            sv = tk.StringVar(value=cache.get(namn, ""))
            sport_vars[namn] = sv
            ttk.Combobox(dialog, textvariable=sv, values=SPORTER_VAL,
                         width=14, state="readonly").grid(
                row=i + 1, column=1, pady=3, sticky="w")
            ttk.Button(dialog, text="Öppna mapp", width=11,
                       command=lambda p=path: oppna_i_finder(p) if p else None,
                       state="normal" if path else "disabled").grid(
                row=i + 1, column=2, padx=(8, 16), pady=3)

        def spara_och_stäng():
            for namn, sv in sport_vars.items():
                val = sv.get().strip()
                if val:
                    cache[namn] = val
            SPORT_WEBB_CACHE.parent.mkdir(parents=True, exist_ok=True)
            SPORT_WEBB_CACHE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8")
            OKAND_PATH.unlink(missing_ok=True)
            dialog.destroy()
            # Starta om träningen direkt med de nya klassificeringarna
            if any(sv.get() for sv in sport_vars.values()):
                _starta_trana()

        ttk.Button(dialog, text="Spara och träna om",
                   command=spara_och_stäng).grid(
            row=len(okanda) + 1, column=0, columnspan=3,
            padx=16, pady=(10, 14))

    def _starta_trana():
        rot = vals["trana_rot"].get().strip()
        if not rot:
            rot = filedialog.askdirectory(
                title="Välj facit-rot (mappen med alla matchmappar)",
                initialdir=_trana_rot_default())
            if not rot:
                return
            vals["trana_rot"].set(rot)
        spara_trana_rot(rot)   # persistera tränings-roten (separat från match)

        cmd = [sys.executable, "-m", "cull.inlarning", rot, "--max-neg", "100"]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        for p in ("/opt/homebrew/bin", "/usr/local/bin"):
            if p not in env.get("PATH", "").split(os.pathsep):
                env["PATH"] = p + os.pathsep + env.get("PATH", "")

        trana_knapp.configure(text="Stoppa träning", command=_stoppa_trana)
        trana_status_var.set("Startar…")
        trana_progress["mode"] = "indeterminate"
        trana_progress.start(12)
        trana_räknare_var.set("")

        SKRAP = ("clearcut", "Source Location", "playlog",
                 "landmark_projection", "Loading pretrained")
        re_uppdrag = re.compile(r"^\[(\d+)/(\d+)\]")

        def kör():
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    bufsize=1, env=env)
            trana_proc[0] = proc
            totalt = [0]
            for rad in proc.stdout:
                if any(s in rad for s in SKRAP):
                    continue
                root.after(0, skriv, rad)
                m = re_uppdrag.match(rad.strip())
                if m:
                    aktuell, tot = int(m.group(1)), int(m.group(2))
                    totalt[0] = tot
                    def _upd(a=aktuell, t=tot):
                        trana_progress.stop()
                        trana_progress["mode"] = "determinate"
                        trana_progress_var.set(a / t * 100)
                        trana_räknare_var.set(f"{a} / {t}")
                        trana_status_var.set("Tränar…")
                    root.after(0, _upd)
                elif "Laddar AI" in rad:
                    root.after(0, lambda: trana_status_var.set("Laddar AI…"))
                elif "Modell sparad" in rad:
                    root.after(0, lambda: trana_status_var.set("Modell sparad ✓"))
            proc.wait()
            trana_proc[0] = None
            ok = proc.returncode == 0
            def _klar():
                trana_progress.stop()
                trana_progress["mode"] = "determinate"
                trana_progress_var.set(100 if ok else 0)
                trana_knapp.configure(text="Träna modell…", command=_starta_trana)
                if ok and OKAND_PATH.exists():
                    root.after(500, _klassificera_okanda)
            root.after(0, _klar)
            root.after(0, lambda: skriv(
                "\n✓ Klar.\n" if ok else "\n✗ Avslutades med fel.\n",
                "klar" if ok else "fel"))

        threading.Thread(target=kör, daemon=True).start()

    def _stoppa_trana():
        if trana_proc[0]:
            trana_proc[0].terminate()
        trana_knapp.configure(text="Träna modell…", command=_starta_trana)
        trana_status_var.set("Stoppad.")
        trana_progress.stop()
        trana_progress["mode"] = "determinate"
        trana_progress_var.set(0)

    ttk.Button(f_trana, text="Okända sporter…",
               command=_klassificera_okanda).grid(row=0, column=3, padx=(8, 0))

    trana_knapp = ttk.Button(f_trana, text="Träna modell…",
                              command=_starta_trana)
    trana_knapp.grid(row=0, column=4, padx=(8, 0))

    # --- Progress ---
    f_progress = ttk.Frame(root)
    f_progress.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 0))

    progress_var = tk.DoubleVar(value=0)
    progress = ttk.Progressbar(f_progress, variable=progress_var,
                               maximum=100, length=500)
    progress.pack(side="left", fill="x", expand=True)

    räknare_var = tk.StringVar(value="")
    ttk.Label(f_progress, textvariable=räknare_var, width=12,
              anchor="e").pack(side="right")

    # --- Knapprad: granskningsverktyg (vänster) + huvudåtgärder (höger) ---
    f_knapp = ttk.Frame(root)
    f_knapp.grid(row=3, column=0, sticky="ew", padx=10, pady=4)

    status_var = tk.StringVar(value="")

    def visa_befintligt_urval():
        start = vals["katalog"].get().strip() or "/"
        d = filedialog.askdirectory(title="Välj urval-mapp att visa",
                                    initialdir=start)
        if d:
            visa_miniatyrer(root, d)

    # Granskningsverktyg → Modell-fliken (relaterar till modell/aktiv inlärning)
    ttk.Separator(f_trana, orient="horizontal").grid(
        row=2, column=0, columnspan=5, sticky="ew", pady=(10, 4))
    ttk.Label(f_trana, text="Granskning", foreground="gray").grid(
        row=3, column=0, sticky="w")
    f_verktyg = ttk.Frame(f_trana)
    f_verktyg.grid(row=4, column=0, columnspan=5, sticky="w", pady=(2, 0))
    for txt, cmd in (
        ("Granska osäkra…", lambda: visa_aktiv_inlarning(root)),
        ("Jämför par…",     lambda: visa_jamforelse(root, vals)),
        ("Histogram…",      lambda: visa_histogram(root)),
        ("Jämför körningar…", lambda: visa_jamfor_korningar(root)),
    ):
        ttk.Button(f_verktyg, text=txt, command=cmd).pack(side="left",
                                                          padx=(0, 6))

    # Höger: huvudåtgärder
    knapp = ttk.Button(f_knapp, text="Kör cull")
    knapp.pack(side="right")
    ttk.Button(f_knapp, text="Visa urval…",
               command=visa_befintligt_urval).pack(side="right", padx=6)
    ttk.Button(f_knapp, text="Historik…",
               command=lambda: visa_historik(root)).pack(side="right")
    ttk.Label(f_knapp, textvariable=status_var, foreground="gray").pack(
        side="right", padx=10)

    # --- Logg ---
    f_logg = ttk.LabelFrame(root, text="Output", padding=4)
    f_logg.grid(row=4, column=0, sticky="nsew", **pad)

    logg = tk.Text(f_logg, width=80, height=8, font=("Menlo", 11),
                   state="disabled", wrap="word")
    scroll = ttk.Scrollbar(f_logg, command=logg.yview)
    logg.configure(yscrollcommand=scroll.set)
    logg.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    # Loggen fyller bredden, växer med fönstret och har en garanterad minhöjd
    # så den inte trycks ihop till oläslig av kontrollerna ovanför.
    f_logg.columnconfigure(0, weight=1)
    f_logg.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(4, weight=3, minsize=200)   # loggen (under flikarna)

    def skriv(text, tag=None):
        logg.configure(state="normal")
        logg.insert("end", text, tag or ())
        logg.configure(state="disabled")
        logg.see("end")
        logg.yview_moveto(1.0)   # tvinga autoscroll till botten

    logg.tag_configure("fel", foreground="#cc0000")
    logg.tag_configure("klar", foreground="#007700")

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

        re_total    = re.compile(r"^(\d+) (?:NEF|bildfiler) hittade")
        re_framsteg = re.compile(r"…(\d+)/(\d+)")
        re_hoppar   = re.compile(r"\[(\d+)/(\d+)\]")
        re_urval    = re.compile(r"(\d+) NEF kopierade till:\s*(.+)$")

        PULS_START = ("Laddar AI", "Hämtar metadata", "Extraherar previews",
                      "AI-analys på topp", "Skriver IPTC")
        PULS_STOPP = ("AI-modeller redo", "Avspark", "previews extraherade",
                      "AI klar", "Baspoängsätter", "IPTC-bildtexter skrivna")

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
                # Hoppa över miniatyr-popupen när urvalet ändå öppnas i en
                # extern app (LR/DxO) — annars dyker både den och popupen upp.
                läge = vals["oppna"].get().strip().lower()
                till_app = (läge in ("lightroom", "dxo pureraw")
                            or (läge == "auto" and _lightroom_finns()))
                if not till_app:
                    root.after(500, lambda: visa_miniatyrer(root, urval_mapp[0]))

        threading.Thread(target=kör_process, daemon=True).start()

    knapp.configure(command=kor)

    # Centrera och tvinga fram fönstret. OBS: sätt INTE resizable(False, False)
    # på ett tomt fönster — på Tk 9.0/macOS låser det storleken till ~21x52 och
    # innehåll som läggs till efteråt växer inte fönstret (osynlig app).
    root.update_idletasks()
    sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
    # Lämna plats för menyrad och Dock så fönstret inte hamnar bakom dem.
    topp_marg, dock_marg = 32, 96
    tillgänglig_h = sy - topp_marg - dock_marg
    w = min(max(root.winfo_reqwidth(), 600), sx - 40)
    h = min(max(root.winfo_reqheight(), 600), tillgänglig_h)
    x = max(0, (sx - w) // 2)
    y = topp_marg   # strax under menyraden, inte centrerat (annars under Dock)
    root.geometry(f"{w}x{h}+{x}+{y}")
    # Tillåt att krympa fönstret (lås det inte vid full höjd).
    root.minsize(min(w, 560), min(h, 480))
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
