"""Varumärke, version och build för Dalecarlia Photo Cull."""

from datetime import datetime
from pathlib import Path

APPNAMN = "Dalecarlia Photo Cull"


def version():
    try:
        from importlib.metadata import version as _v
        return _v("cull")
    except Exception:
        return "0.0.0"


def _stampel():
    """(commit, dirty, tidpunkt) för det körande bygget, eller None.

    1) Installerat bygge: läs den auto-genererade _buildstamp.py (skapad av
       hatch_build.py vid paketering — .git finns inte i venv:en).
    2) Dev/källträd: läs git direkt + filens mtime som tidpunkt."""
    try:
        from . import _buildstamp as bs
        return bs.COMMIT, bs.DIRTY, bs.TIDPUNKT
    except Exception:
        pass
    try:
        import subprocess
        root = Path(__file__).resolve().parents[2]
        def g(*a):
            return subprocess.check_output(
                ["git", *a], cwd=root, text=True,
                stderr=subprocess.DEVNULL).strip()
        commit = g("rev-parse", "--short", "HEAD")
        dirty = bool(g("status", "--porcelain"))
        tid = datetime.fromtimestamp(
            Path(__file__).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        return commit, dirty, tid
    except Exception:
        return None


def build():
    """Exakt bygg-id: tidpunkt + git-commit (+ '*' om bygget hade osparade
    ändringar). Faller tillbaka till filens tidsstämpel om git saknas helt."""
    s = _stampel()
    if s:
        commit, dirty, tid = s
        return f"{tid} · {commit}{'*' if dirty else ''}"
    try:
        ts = Path(__file__).stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M")


def etikett():
    return f"{APPNAMN}  v{version()}  (build {build()})"


def ikon_path():
    p = Path(__file__).parent / "assets" / "icon.png"
    return p if p.exists() else None


def header_logo_path():
    p = Path(__file__).parent / "assets" / "logo_header.png"
    return p if p.exists() else None
