# Build with: app/.venv/Scripts/python.exe -m PyInstaller app/BelaLab.spec
from pathlib import Path
from runpy import run_path
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH)
project = root.parent
version = run_path(str(root / "src/bela/__init__.py"))["__version__"]
version_tuple = (*map(int, version.split(".")), 0)
versions = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, OS=0x40004, fileType=1),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", "Bela Lab"),
            StringStruct("ProductName", "Bela Lab"),
            StringStruct("FileVersion", version),
            StringStruct("ProductVersion", version),
            StringStruct("OriginalFilename", "Bela Lab.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

web = root / "src/bela/interfaces/web"
web_assets = [
    (str(path), str(Path("bela/interfaces/web") / path.relative_to(web).parent))
    for path in sorted(web.rglob("*"))
    if path.suffix in {".html", ".css", ".js", ".svg", ".json"} and path.is_file()
]
docs = [
    (str(project / "docs" / name), str(Path("docs") / Path(name).parent))
    for name in ("RULES.md", "translations/RULES.hr.md", "PROJECT_STATUS.md")
]
legal = [(str(project / name), ".") for name in ("TERMS.md", "PRIVACY.md", "NOTICE.md")]
a = Analysis([str(root / "desktop.py")], pathex=[str(root / "src")],
    binaries=[], datas=web_assets + docs + legal + [
        (str(project / "examples/player_match.json"), "examples")],
    hiddenimports=["webview.platforms.edgechromium", "webview.platforms.winforms"],
    hookspath=[], runtime_hooks=[], excludes=["tkinter", "PyQt5", "PySide6"], noarchive=False)
a.datas = [entry for entry in a.datas if not entry[0].endswith("pywebview-android.jar")]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Bela Lab", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / "assets/bela-lab.ico"), version=versions)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Bela Lab")
