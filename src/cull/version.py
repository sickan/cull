"""Varumärke, version och build för Dalecarlia Photo Cull."""

from pathlib import Path

APPNAMN = "Dalecarlia Photo Cull"
BUILD = "2026-06-20"


def version():
    try:
        from importlib.metadata import version as _v
        return _v("cull")
    except Exception:
        return "0.0.0"


def etikett():
    return f"{APPNAMN}  v{version()}  (build {BUILD})"


def ikon_path():
    p = Path(__file__).parent / "assets" / "icon.png"
    return p if p.exists() else None


def header_logo_path():
    p = Path(__file__).parent / "assets" / "logo_header.png"
    return p if p.exists() else None
