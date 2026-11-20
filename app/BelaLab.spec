# Build with: app/.venv/Scripts/python.exe -m PyInstaller app/BelaLab.spec
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / "desktop.py")], pathex=[str(root / "src")],
    binaries=[], datas=[(str(root / "src/bela/interfaces/web"), "bela/interfaces/web"),
                        (str(root.parent / "docs"), "docs"),
                        (str(root.parent / "examples"), "examples")],
    hiddenimports=["webview.platforms.edgechromium", "webview.platforms.winforms"],
    hookspath=[], runtime_hooks=[], excludes=["tkinter", "PyQt5", "PySide6"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Bela Lab", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / "assets/bela-lab.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Bela Lab")
