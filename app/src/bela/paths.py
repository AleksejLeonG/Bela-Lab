"""Shared project paths, independent of the shell's working directory."""

from pathlib import Path
import os
import sys

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = APPLICATION_ROOT.parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
DOCS_ROOT = RESOURCE_ROOT / "docs"
EXAMPLES_ROOT = RESOURCE_ROOT / "examples"
SAVES_ROOT = Path(os.environ.get("BELA_SAVES_ROOT", PROJECT_ROOT / "saves"))
