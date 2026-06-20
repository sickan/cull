"""Grafiskt gränssnitt för cull — välj katalog och kriterier, se output live."""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk


FARGER = ["", "blå", "ljusblå", "röd", "mörkröd", "gul", "grön",
          "vit", "svart", "orange", "lila"]


def bygg_kommando(vals):
    katalog = vals["katalog"].get().strip()
    if not katalog:
        return None, "Välj en katalog först."

    cmd = [sys.executable, "-m", "cull.core", katalog]

    if vals["ai"].get():
        cmd.append("--ai")

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


def main():
    root = tk.Tk()
    root.title("cull")
    root.resizable(False, False)

    pad = {"padx": 10, "pady": 4}
    vals = {}

    # --- Katalog ---
    f_katalog = ttk.LabelFrame(root, text="Katalog", padding=8)
    f_katalog.grid(row=0, column=0, sticky="ew", **pad)

    vals["katalog"] = tk.StringVar()
    ttk.Entry(f_katalog, textvariable=vals["katalog"], width=52).grid(
        row=0, column=0, padx=(0, 6))

    def valj_katalog():
        d = filedialog.askdirectory(title="Välj uppdragskatalog")
        if d:
            vals["katalog"].set(d)

    ttk.Button(f_katalog, text="Välj…", command=valj_katalog).grid(row=0, column=1)

    # --- Kriterier ---
    f_krit = ttk.LabelFrame(root, text="Kriterier", padding=8)
    f_krit.grid(row=1, column=0, sticky="ew", **pad)

    def rad(parent, etikett, row):
        ttk.Label(parent, text=etikett).grid(row=row, column=0, sticky="w", pady=2)

    # AI
    vals["ai"] = tk.BooleanVar(value=True)
    ttk.Checkbutton(f_krit, text="AI  (YOLOv8 + MediaPipe Pose)",
                    variable=vals["ai"]).grid(row=0, column=0, columnspan=2,
                                              sticky="w", pady=2)

    # XMP
    vals["xmp"] = tk.BooleanVar(value=False)
    ttk.Checkbutton(f_krit, text="Skriv XMP-sidecars  (beskärning + upprätnning)",
                    variable=vals["xmp"]).grid(row=1, column=0, columnspan=2,
                                               sticky="w", pady=2)

    # Rapport
    vals["rapport"] = tk.BooleanVar(value=False)
    ttk.Checkbutton(f_krit, text="Rapportläge  (poängsätt, kopiera inget)",
                    variable=vals["rapport"]).grid(row=2, column=0, columnspan=2,
                                                   sticky="w", pady=2)

    ttk.Separator(f_krit, orient="horizontal").grid(
        row=3, column=0, columnspan=2, sticky="ew", pady=6)

    # Hemmalagsfärg
    rad(f_krit, "Hemmalagsfärg", 4)
    vals["hemma_farg"] = tk.StringVar()
    ttk.Combobox(f_krit, textvariable=vals["hemma_farg"],
                 values=FARGER, width=14, state="readonly").grid(
        row=4, column=1, sticky="w")

    # Bevaka tröjnummer
    rad(f_krit, "Bevaka tröjnummer", 5)
    vals["bevaka"] = tk.StringVar()
    ttk.Entry(f_krit, textvariable=vals["bevaka"], width=16).grid(
        row=5, column=1, sticky="w")
    ttk.Label(f_krit, text="  t.ex. 9,11", foreground="gray").grid(
        row=5, column=2, sticky="w")

    # Avspark
    rad(f_krit, "Avspark", 6)
    vals["avspark"] = tk.StringVar()
    ttk.Entry(f_krit, textvariable=vals["avspark"], width=8).grid(
        row=6, column=1, sticky="w")
    ttk.Label(f_krit, text="  HH:MM", foreground="gray").grid(
        row=6, column=2, sticky="w")

    # Topp / Andel
    rad(f_krit, "Behåll", 7)
    f_behall = ttk.Frame(f_krit)
    f_behall.grid(row=7, column=1, columnspan=2, sticky="w")
    vals["topp"] = tk.StringVar()
    vals["andel"] = tk.StringVar(value="0.20")
    ttk.Entry(f_behall, textvariable=vals["topp"], width=6).pack(side="left")
    ttk.Label(f_behall, text=" bilder  eller  andel ").pack(side="left")
    ttk.Entry(f_behall, textvariable=vals["andel"], width=6).pack(side="left")

    # Burst-sek
    rad(f_krit, "Burst-gräns (sek)", 8)
    vals["burst_sek"] = tk.StringVar(value="2.0")
    ttk.Entry(f_krit, textvariable=vals["burst_sek"], width=8).grid(
        row=8, column=1, sticky="w")

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

    # --- Kör-knapp ---
    f_knapp = ttk.Frame(root)
    f_knapp.grid(row=3, column=0, sticky="e", padx=10, pady=4)

    status_var = tk.StringVar(value="")
    ttk.Label(f_knapp, textvariable=status_var, foreground="gray").pack(
        side="left", padx=8)

    knapp = ttk.Button(f_knapp, text="Kör cull")
    knapp.pack(side="right")

    # --- Logg ---
    f_logg = ttk.LabelFrame(root, text="Output", padding=8)
    f_logg.grid(row=4, column=0, sticky="nsew", **pad)

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

    def kor():
        cmd, fel = bygg_kommando(vals)
        if fel:
            status_var.set(fel)
            return

        knapp.configure(state="disabled")
        status_var.set("Kör…")
        progress_var.set(0)
        räknare_var.set("")
        logg.configure(state="normal")
        logg.delete("1.0", "end")
        logg.configure(state="disabled")
        skriv("$ " + " ".join(cmd) + "\n\n")

        totalt    = [0]
        pulsande  = [False]   # True när vi är i ett okänt-längd-steg
        puls_job  = [None]

        import re
        re_total    = re.compile(r"^(\d+) NEF hittade")
        re_framsteg = re.compile(r"…(\d+)/(\d+)")
        re_hoppar   = re.compile(r"\[(\d+)/(\d+)\]")

        # Rader som startar ett okänt-längd-steg (indeterminate)
        PULS_START = ("Laddar AI", "Hämtar metadata", "Extraherar previews",
                      "AI-analys på topp")
        # Rader som avslutar ett sådant steg
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

        def hantera_rad(rad):
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

        def kör_process():
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
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

        threading.Thread(target=kör_process, daemon=True).start()

    knapp.configure(command=kor)
    root.mainloop()


if __name__ == "__main__":
    main()
