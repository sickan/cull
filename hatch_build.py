"""Hatch-build-hook: stämplar in git-commit + tidpunkt vid varje paketering.

Körs av hatchling under 'pipx install' / 'pip wheel'. Skriver
src/cull/_buildstamp.py så att den installerade koden vet EXAKT vilket
bygge den är — även när .git inte följer med in i venv:en."""

import os
import subprocess
from datetime import datetime

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _git(root, *args):
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True,
        stderr=subprocess.DEVNULL).strip()


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = self.root
        try:
            commit = _git(root, "rev-parse", "--short", "HEAD")
        except Exception:
            commit = "okänd"
        try:
            dirty = bool(_git(root, "status", "--porcelain"))
        except Exception:
            dirty = False
        tid = datetime.now().strftime("%Y-%m-%d %H:%M")
        sokvag = os.path.join(root, "src", "cull", "_buildstamp.py")
        with open(sokvag, "w", encoding="utf-8") as f:
            f.write(
                '"""Auto-genererad av hatch_build.py vid paketering. Committa ej."""\n'
                f"COMMIT = {commit!r}\n"
                f"DIRTY = {dirty!r}\n"
                f"TIDPUNKT = {tid!r}\n"
            )
