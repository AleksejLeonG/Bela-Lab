"""Desktop entry point, kept beside the development dashboard launcher."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    from bela.interfaces.desktop import main
    raise SystemExit(main())
