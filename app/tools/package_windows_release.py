"""Create the Windows x64 release ZIP and its SHA-256 checksum."""

import argparse
from hashlib import file_digest
from importlib.metadata import distribution
from pathlib import Path
from runpy import run_path
from struct import unpack_from
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable


PROJECT = Path(__file__).resolve().parents[2]
VERSION = run_path(str(PROJECT / "app/src/bela/__init__.py"))["__version__"]
BUNDLE = PROJECT / "dist/Bela Lab"
RELEASE_DOCS = ("TERMS.md", "PRIVACY.md", "NOTICE.md", "LICENSE.md", "SECURITY.md", "CHANGELOG.md")
DEPENDENCIES = ("bottle", "cffi", "clr-loader", "packaging", "pycparser", "pythonnet",
                "pywebview", "setuptools", "typing_extensions")
NATIVE_NOTICES = (
    "proxy_tools-0.1.0-LICENSE.txt", "OpenSSL-3.5.8-LICENSE.txt", "libffi-3.4.4-LICENSE.txt",
    "Expat-2.8.3-COPYING.txt", "xz-5.2.5-COPYING.txt", "zlib-1.3.2-LICENSE.txt",
    "mpdecimal-2.5.1-COPYRIGHT.txt", "WebView2-1.0.3856.49-LICENSE.txt",
    "WebView2-1.0.3856.49-NOTICE.txt",
)


def bundled_files():
    executable = BUNDLE / "Bela Lab.exe"
    with executable.open("rb") as handle:
        header = handle.read(64)
        handle.seek(unpack_from("<I", header, 0x3C)[0])
        machine = handle.read(6)
    if machine != b"PE\x00\x00\x64\x86":
        raise ValueError("The release executable must be Windows x64.")
    resource = read_version_info_from_executable(str(executable))
    major, minor, patch = map(int, VERSION.split("."))
    if (resource is None or (resource.ffi.fileVersionMS, resource.ffi.fileVersionLS)
            != (major << 16 | minor, patch << 16)):
        raise ValueError("Rebuild the executable for the current app version.")

    internal = BUNDLE / "_internal"
    deck = internal / "bela/interfaces/web/cards"
    if len(list((deck / "hungarian").glob("*.svg"))) != 32:
        raise ValueError("The release bundle must contain only the project SVG card faces.")
    private_names = {"saves", "webview2.nupkg", "early_chat_handover.md", "early_chat_source_summary.md"}
    yield executable, executable.name
    for path in sorted(internal.rglob("*")):
        if path.is_file():
            relative = path.relative_to(BUNDLE)
            if private_names.intersection(part.lower() for part in relative.parts):
                raise ValueError(f"Private or development file in release bundle: {relative}")
            yield path, relative.as_posix()
    for name in RELEASE_DOCS:
        source = PROJECT / name
        if name in ("TERMS.md", "PRIVACY.md", "NOTICE.md") and source.read_bytes() != (internal / name).read_bytes():
            raise ValueError(f"The bundled {name} differs from the release copy.")
        yield source, name
    yield PROJECT / "docs/WINDOWS_QUICK_START.txt", "START_HERE.txt"


def notice_files():
    yield Path(sys.base_prefix) / "LICENSE.txt", f"licenses/CPython-{sys.version.split()[0]}.txt"
    for name in DEPENDENCIES:
        package = distribution(name)
        files = [file for file in package.files or ()
                 if ".dist-info" in file.parts[0] and file.name.startswith(("LICENSE", "COPYING", "NOTICE"))]
        if not files:
            raise ValueError(f"No licence files were found for {name}.")
        for file in sorted(files):
            yield package.locate_file(file), f"licenses/{name}-{package.version}/{file.name}"
    vendor = Path(distribution("setuptools").locate_file("setuptools/_vendor"))
    for folder in sorted(vendor.glob("*.dist-info")):
        for path in sorted(folder.rglob("LICENSE*")):
            if path.is_file():
                yield path, f"licenses/setuptools-vendored/{folder.stem}/{path.name}"
    for name in NATIVE_NOTICES:
        yield PROJECT / "app/tools/release-licenses" / name, f"licenses/{name}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "dist")
    args = parser.parse_args()
    target = args.output_dir / f"Bela-Lab-{VERSION}-Windows-x64.zip"
    checksum = target.with_suffix(".zip.sha256")
    try:
        if target.exists() or checksum.exists():
            raise ValueError("The release archive or checksum exists. Use a new output directory.")
        files = list(bundled_files()) + list(notice_files())
        for path, _ in files:
            if not path.is_file():
                raise ValueError(f"Missing release file: {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(target, "x", compression=ZIP_DEFLATED) as archive:
            for path, name in files:
                archive.write(path, name)
        with target.open("rb") as handle:
            digest = file_digest(handle, "sha256").hexdigest()
        with checksum.open("x", encoding="ascii") as handle:
            handle.write(f"{digest}  {target.name}\n")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(target)
    print(checksum)


if __name__ == "__main__":
    main()
