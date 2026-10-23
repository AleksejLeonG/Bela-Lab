"""Shared project paths, independent of the shell's working directory."""

from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = APPLICATION_ROOT.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
EXAMPLES_ROOT = PROJECT_ROOT / "examples"
SAVES_ROOT = PROJECT_ROOT / "saves"
