"""Loopback-only development dashboard backed by the existing player engine."""

import argparse
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit, parse_qs
from uuid import UUID, uuid4
import webbrowser

from bela.interfaces.localization import CROATIAN, translate
from bela.interfaces.analysis_jobs import AnalysisBusy, AnalysisJobs, interactive_config
from bela.analysis.knowledge import knowledge_view
from bela.domain.cards import Card
from bela.domain.melds import BelotResult
from bela.storage.persistence import _invalid_constant, _object, _unique_object
from bela.paths import DOCS_ROOT, EXAMPLES_ROOT, SAVES_ROOT
from bela.rules.play import card_points, trick_winner
from bela.gameplay.tracking import UserMatch, ValidationLimit
from bela.interfaces.player_cli import event_text
from bela.storage.user_storage import (_command, _setup, dumps_user_match, event_data,
                               load_user_match, loads_user_match, save_user_match,
                               setup_data)


WEB_ROOT = Path(__file__).with_name("web")
MAX_REQUEST_BYTES = 16 * 1024 * 1024


class StaleRevision(ValueError):
    pass


def _trick_data(trick, trump, *, complete=False):
    data = {"leader": int(trick.leader),
            "plays": [{"player": int(trick.seat_at(i)), "card": str(card)}
                      for i, card in enumerate(trick.cards)]}
    if complete:
        data.update(winner=int(trick_winner(trick, trump)),
                    points=sum(card_points(card, trump) for card in trick.cards))
    return data


def match_view(match):
    if match is None:
        return None
    state = match.state
    result = None
    if isinstance(state.result, BelotResult):
        result = {"type": "belot", "winning_team": state.result.winning_team}
    elif state.result is not None:
        result = {"type": "deal", "earned": state.result.earned,
                  "recorded": state.result.recorded, "caller_passed": state.result.caller_passed,
                  "total": state.result.total}
    completed = [_trick_data(t, state.setup.trump, complete=True) for t in state.completed_tricks]
    return {"id": match.id, "name": match.name, "revision": match.revision,
            "deal_number": len(match.deals), "setup": setup_data(state.setup),
            "hand": [str(c) for c in sorted(state.hand, key=lambda c: c.id)],
            "phase": state.phase.value, "score": state.score, "winner": state.winner,
            "next_player": None if state.next_player is None else int(state.next_player),
            "legal_cards": list(map(str, state.legal_actions)),
            "trick": _trick_data(state.current_trick, state.setup.trump),
            "completed_tricks": completed, "trick_points": state.trick_points,
            "trick_counts": state.trick_counts, "remaining_counts": state.remaining_counts,
            "awarded_melds": state.awarded_melds,
            "revealed": [[str(c) for c in sorted(cs, key=lambda c: c.id)] for cs in state.revealed],
            "bela_players": [int(call.player) for call in state.bela_announcements],
            "result": result,
            "events": [{"index": i, "text": event_text(event), "event": event_data(event)}
                       for i, event in enumerate(match.deals[-1].events)],
            "deals": [{"number": i + 1, "score": d.state.score, "phase": d.state.phase.value,
                       "tricks": len(d.state.completed_tricks)} for i, d in enumerate(match.deals)]}


class Dashboard:
    """One active session for this local workbench, with optimistic concurrency."""

    def __init__(self, storage: Path, example: Path):
        self.storage, self.example = Path(storage), Path(example)
        self.match = None
        self.lock = threading.RLock()
        self.analysis = AnalysisJobs()

    def _path(self, match_id):
        if not isinstance(match_id, str) or str(UUID(match_id)) != match_id:
            raise ValueError("Invalid match identity.")
        return self.storage / f"{match_id}.player.json"

    def saved(self):
        result = []
        for path in self.storage.glob("*.player.json"):
            try:
                if path.stat().st_size > 8 * 1024 * 1024:
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                if (data.get("format") != "bela-player-session" or not isinstance(data.get("name"), str)
                        or not isinstance(data.get("commands"), list)
                        or self._path(data.get("id")).name != path.name):
                    continue
                result.append({"id": data["id"], "name": data["name"],
                               "revision": len(data["commands"]),
                               "deals": 1 + sum(c.get("type") == "next_deal" for c in data["commands"] if isinstance(c, dict)),
                               "modified": path.stat().st_mtime})
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        return sorted(result, key=lambda item: item["modified"], reverse=True)

    def snapshot(self):
        with self.lock:
            return {"match": match_view(self.match), "saved": self.saved()}

    def mutate(self, route, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError("Expected a request object.")
            expected_id = None if self.match is None else self.match.id
            revision = 0 if self.match is None else self.match.revision
            if (payload.get("expected_id") != expected_id
                    or type(payload.get("expected_revision")) is not int
                    or payload["expected_revision"] != revision):
                raise StaleRevision("The match changed in another window. Refresh and try again.")
            context = {"expected_id", "expected_revision"}
            if route == "/api/new":
                _object(payload, context | {"name", "setup"}, "new match")
                candidate = UserMatch.start(_setup(payload["setup"]), payload["name"])
            elif route == "/api/demo":
                _object(payload, context, "demo")
                candidate = replace(load_user_match(self.example), id=str(uuid4()), name="Demo match")
            elif route == "/api/load":
                _object(payload, context | {"id"}, "load")
                candidate = load_user_match(self._path(payload["id"]))
                if candidate.id != payload["id"]:
                    raise ValueError("Archive identity does not match the file.")
            elif route == "/api/import":
                _object(payload, context | {"archive"}, "import")
                # Import as a separate copy so an older export cannot overwrite a newer save.
                candidate = replace(loads_user_match(payload["archive"]), id=str(uuid4()))
            elif route == "/api/command":
                _object(payload, context | {"command"}, "event")
                if self.match is None:
                    raise ValueError("Open or create a match first.")
                candidate = self.match.perform(_command(payload["command"]))
            else:
                raise ValueError("Unknown action.")
            # Commit memory only after persistence succeeds.
            save_user_match(candidate, self._path(candidate.id))
            self.match = candidate
            self.analysis.invalidate()
            return self.snapshot()

    def analysis_request(self, route, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError("Expected a request object.")
            match = self.match
            if match is None:
                raise ValueError("Open or create a match first.")
            if (payload.get("expected_id") != match.id
                    or type(payload.get("expected_revision")) is not int
                    or payload["expected_revision"] != match.revision):
                raise StaleRevision("The match changed in another window. Refresh and try again.")
            context = {"expected_id", "expected_revision"}
            if route == "/api/analysis/start":
                _object(payload, context | {"config"}, "analysis")
                job_id = self.analysis.start(match, interactive_config(payload["config"]))
            elif route == "/api/analysis/cancel":
                _object(payload, context | {"job_id"}, "analysis cancellation")
                job_id = payload["job_id"]
                self.analysis.cancel(job_id)
            else:
                raise ValueError("Unknown analysis action.")
            return self.analysis.view(job_id, (match.id, match.revision, len(match.deals)))

    def analysis_view(self, job_id):
        with self.lock:
            match = self.match
            source = None if match is None else (match.id, match.revision, len(match.deals))
        return self.analysis.view(job_id, source)


def make_server(dashboard: Dashboard, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _headers(self, status, content_type, size, *, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()

        def _json(self, status, data):
            if "error" in data:
                data = {**data, "error": translate(data["error"], self.headers.get("Accept-Language", "en"))}
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(raw))
            self.wfile.write(raw)

        def _local(self):
            port = self.server.server_address[1]
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                self._json(403, {"error": "This dashboard only runs on a local address."})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed}:
                self._json(403, {"error": "Requests must originate from the local dashboard."})
                return False
            return True

        def do_GET(self):
            if not self._local():
                return
            path = urlsplit(self.path).path
            if path == "/api/state":
                self._json(200, dashboard.snapshot())
            elif path == "/api/analysis":
                try:
                    self._json(200, dashboard.analysis_view(parse_qs(urlsplit(self.path).query).get("id", [None])[0]))
                except ValueError as error:
                    self._json(404, {"error": str(error)})
            elif path == "/api/knowledge":
                with dashboard.lock:
                    match = dashboard.match
                if match is None:
                    self._json(404, {"error": "No open match."})
                    return
                # Analyze an immutable snapshot without blocking game input.
                try:
                    self._json(200, knowledge_view(match))
                except ValueError as error:
                    self._json(422, {"error": str(error)})
            elif path == "/api/rules":
                try:
                    self._json(200, {"text": (DOCS_ROOT / ("translations/RULES.hr.md" if parse_qs(urlsplit(self.path).query).get("lang") == ["hr"] else "RULES.md")).read_text(encoding="utf-8")})
                except OSError:
                    self._json(503, {"error": "The rules file is unavailable in this project."})
            elif path == "/api/export":
                with dashboard.lock:
                    if dashboard.match is None:
                        self._json(404, {"error": "No open match."})
                        return
                    raw = dumps_user_match(dashboard.match).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(raw),
                                  extra={"Content-Disposition": f'attachment; filename="{dashboard.match.id}.player.json"'})
                    self.wfile.write(raw)
            elif path == "/locale.js":
                raw = ("const CROATIAN = " + json.dumps(CROATIAN, ensure_ascii=False) + ";").encode("utf-8")
                self._headers(200, "text/javascript; charset=utf-8", len(raw))
                self.wfile.write(raw)
            elif path in ("/", "/app.js", "/advice.js", "/knowledge.js", "/i18n.js", "/preferences.js", "/style.css", "/favicon.svg"):
                file = WEB_ROOT / ("index.html" if path == "/" else path[1:])
                raw = file.read_bytes()
                content_type = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}[file.suffix]
                self._headers(200, content_type + "; charset=utf-8", len(raw))
                self.wfile.write(raw)
            else:
                self._json(404, {"error": "Page not found."})

        def do_POST(self):
            if not self._local():
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REQUEST_BYTES:
                    self._json(413, {"error": "The request is empty or too large."})
                    return
                # Consume a bounded body before rejecting its type. Closing a
                # socket with unread bytes can reset it on Windows and discard
                # the error response before the browser receives it.
                raw = self.rfile.read(length)
                if self.headers.get_content_type() != "application/json":
                    self._json(415, {"error": "Expected a JSON request."})
                    return
                payload = json.loads(raw.decode("utf-8"),
                                     object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
                route = urlsplit(self.path).path
                result = dashboard.analysis_request(route, payload) if route in (
                    "/api/analysis/start", "/api/analysis/cancel") else dashboard.mutate(route, payload)
                self._json(200, result)
            except AnalysisBusy as error:
                self._json(409, {"error": str(error), "code": "analysis_busy"})
            except StaleRevision as error:
                self._json(409, {"error": str(error), "code": "stale_revision"})
            except ValidationLimit as error:
                self._json(422, {"error": str(error), "code": "validation_limit"})
            except (ValueError, TypeError, KeyError, RecursionError) as error:
                self._json(422, {"error": str(error), "code": "invalid_input"})
            except OSError:
                self._json(503, {"error": "Saving or loading failed. The previous state is preserved."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Bela dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    dashboard = Dashboard(SAVES_ROOT / "dashboard", EXAMPLES_ROOT / "player_match.json")
    try:
        server = make_server(dashboard, args.port)
    except OSError as error:
        parser.error(f"Cannot start the dashboard: {error}. Try another --port.")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Bela dashboard: {url}\nPress Ctrl+C to stop the server.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.analysis.invalidate()
        server.server_close()
