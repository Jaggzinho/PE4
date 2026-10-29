from __future__ import annotations

from pathlib import Path
import sys


def package_dir() -> Path:
    """
    Absolute path to the `pe3_qc_app/` directory for both source and PyInstaller builds.
    """
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return (Path(str(getattr(sys, "_MEIPASS"))).resolve() / "pe3_qc_app").resolve()
    return Path(__file__).resolve().parents[1]


def asset_path(*parts: str) -> Path:
    return (package_dir() / Path(*parts)).resolve()

