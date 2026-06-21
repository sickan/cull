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


def build():
    """Build-datum = den installerade kodens tidsstämpel. Uppdateras därför
    automatiskt vid varje 'pipx install' utan att behöva hårdkodas."""
    try:
        ts = Path(__file__).stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def etikett():
    return f"{APPNAMN}  v{version()}  (build {build()})"


def ikon_path():
    p = Path(__file__).parent / "assets" / "icon.png"
    return p if p.exists() else None


def header_logo_path():
    p = Path(__file__).parent / "assets" / "logo_header.png"
    return p if p.exists() else None
