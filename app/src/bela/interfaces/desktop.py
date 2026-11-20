"""Native desktop host. The engine stays local; closing the app stops its server."""
import argparse
import ctypes
import json
import logging
import os
from pathlib import Path
import sys
import threading


def data_directory():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "Bela Lab"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bela Lab desktop")
    parser.add_argument("--data-dir", type=Path, default=data_directory())
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=root / "desktop.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    mutex = None
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        kernel.CreateMutexW.restype = ctypes.c_void_p
        mutex = kernel.CreateMutexW(None, False, "Local\\BelaLabDesktop")
        if kernel.GetLastError() == 183:
            window = ctypes.windll.user32.FindWindowW(None, "Bela Lab")
            if window:
                ctypes.windll.user32.ShowWindow(window, 9)
                ctypes.windll.user32.SetForegroundWindow(window)
            kernel.CloseHandle(ctypes.c_void_p(mutex))
            return 0
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BelaLab.Desktop")
    os.environ["BELA_SAVES_ROOT"] = str(root / "saves")
    server = dashboard = None
    thread = None
    try:
        import webview
        from bela.interfaces.dashboard import Dashboard, make_server
        from bela.paths import EXAMPLES_ROOT
        dashboard = Dashboard(root / "saves" / "dashboard", EXAMPLES_ROOT / "player_match.json")
        server = make_server(dashboard, args.port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/?desktop=1"
        (root / "runtime.json").write_text(json.dumps({"pid": os.getpid(), "url": url}), encoding="utf-8")
        window = webview.create_window("Bela Lab", url, width=1440, height=940,
                                       min_size=(780, 640), background_color="#181b20",
                                       maximized=True, text_select=False)
        if args.smoke_test:
            def check():
                # Exercise the actual Windows renderer, not a browser stand-in.
                result = window.evaluate_js("JSON.stringify({title:document.title,cards:document.querySelectorAll('.hungarian-face').length,shell:document.documentElement.dataset.shell})")
                (root / "smoke.json").write_text(str(result), encoding="utf-8")
                window.destroy()
            window.events.loaded += check
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.start(gui="edgechromium", private_mode=False, storage_path=str(root / "webview"))
        return 0
    except Exception as error:
        logging.exception("Desktop startup failed")
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None,
                f"Bela Lab could not start: {error}\n\nDetails: {root / 'desktop.log'}",
                "Bela Lab", 16)
        return 1
    finally:
        if dashboard:
            dashboard.analysis.invalidate()
            dashboard.review_analysis.invalidate()
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(timeout=3)
        (root / "runtime.json").unlink(missing_ok=True)
        if mutex:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
