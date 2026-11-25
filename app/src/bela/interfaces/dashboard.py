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
from bela import __version__
from bela.paths import DOCS_ROOT, EXAMPLES_ROOT, RESOURCE_ROOT, SAVES_ROOT
from bela.rules.play import card_points, trick_winner
from bela.gameplay.tracking import UserMatch, ValidationLimit
from bela.gameplay.bot_game import BotGame
from bela.storage.persistence import write_archive_text, read_archive_text
from bela.interfaces.player_cli import event_text
from bela.interfaces.trump_advice import trump_request
from bela.interfaces.review import review_view, save_feedback, historical_match, review_variations
from bela.storage.analysis_log import append_analysis
from bela.storage.user_storage import (_command, _setup, dumps_user_match, event_data,
                               load_user_match, loads_user_match, save_user_match,
                               setup_data)


WEB_ROOT = Path(__file__).with_name("web")
LEGAL_DOCUMENTS = {"terms": "TERMS.md", "privacy": "PRIVACY.md", "notices": "NOTICE.md"}
MAX_REQUEST_BYTES = 16 * 1024 * 1024
CARD_ASSETS = {f"/cards/{suit}.svg" for suit in ("hearts", "leaves", "bells", "acorns")} | {
    f"/cards/hungarian/{suit}_{rank}.svg" for suit in "HSDC"
    for rank in ("7", "8", "9", "10", "J", "Q", "K", "A")} | {
    f"/cards/hungarian-illustrated/{suit}_{rank}.webp" for suit in "HSDC"
    for rank in ("7", "8", "9", "10", "J", "Q", "K", "A")}



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
            "deal_scores": [{"number":i+1,"trump":deal.setup.trump.value,"caller":int(deal.setup.caller),
                "recorded":getattr(deal.state.result,"recorded",None),"score":deal.state.score}
                for i,deal in enumerate(match.deals) if deal.state.result is not None],
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
        self.trump_lock = threading.Lock()
        self.analysis = AnalysisJobs(self.storage / "analysis")
        self.review_analysis = AnalysisJobs(self.storage / "analysis")
        self.review_sources = {}
        self.mode = "manual"
        self.manual_match = None
        self.bot_game = None
        active = self.storage / "active.json"
        if active.exists():
            try:
                data = json.loads(read_archive_text(active))
                if data.get("manual_id"):
                    self.manual_match = load_user_match(self._path(data["manual_id"]))
                if data.get("bot_id"):
                    self.bot_game = BotGame.loads(read_archive_text(self._bot_path(data["bot_id"])))
                self.mode = "bots" if data.get("mode") == "bots" else "manual"
                self.match = self.bot_game.tracked if self.mode == "bots" and self.bot_game else self.manual_match
            except (ValueError, OSError, KeyError, TypeError):
                self.mode, self.match = "manual", None

    def _bot_path(self, identity):
        self._path(identity)  # UUID validation before constructing private paths.
        return self.storage / "bots" / f"{identity}.json"

    def _save_active(self):
        write_archive_text(self.storage / "active.json", json.dumps({"mode":self.mode,
            "manual_id":self.manual_match.id if self.manual_match else None,
            "bot_id":self.bot_game.id if self.bot_game else None}))

    def _commit_bot(self, game):
        target = self._path(game.id)
        private = self._bot_path(game.id)
        active = self.storage / "active.json"
        backups = {p:read_archive_text(p) if p.exists() else None for p in (target,private,active)}
        manual = self.match if self.mode == "manual" else self.manual_match
        try:
            if game.tracked is not None:
                save_user_match(game.tracked, target)
            write_archive_text(private, game.dumps())
            write_archive_text(active, json.dumps({"mode":"bots", "manual_id":manual.id if manual else None,
                "bot_id":game.id}))
        except OSError:
            for path,previous in backups.items():
                if previous is not None:
                    write_archive_text(path, previous)
                elif path.exists():
                    path.unlink()
            raise
        self.manual_match = manual
        self.bot_game, self.mode, self.match = game, "bots", game.tracked
        self.analysis.invalidate()
        self.review_analysis.invalidate()
        return self.snapshot()

    def bot_request(self, route, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError("Expected a request object.")
            game = self.bot_game
            if payload.get("expected_id") != (game.id if game else None) or type(payload.get("expected_revision")) is not int or payload["expected_revision"] != (game.revision if game else 0):
                raise StaleRevision("The bot game changed. Refresh and try again.")
            fields = {"expected_id", "expected_revision"}
            if route == "/api/bot/new":
                _object(payload, fields | {"name", "profile"}, "bot match")
                return self._commit_bot(BotGame.new(payload["name"], payload["profile"]))
            if self.mode != "bots" or game is None:
                raise ValueError("Open a bot match first.")
            if route == "/api/bot/call":
                _object(payload, fields | {"suit"}, "trump call")
                candidate = game.call(payload["suit"])
            elif route == "/api/bot/play":
                _object(payload, fields | {"card"}, "your card")
                candidate = game.play(payload["card"])
            elif route == "/api/bot/step":
                _object(payload, fields, "bot turn")
                candidate = game.step()
            elif route == "/api/bot/next":
                _object(payload, fields, "next deal")
                candidate = game.next_deal()
            else:
                raise ValueError("Unknown bot action.")
            return self._commit_bot(candidate)

    def change_mode(self, payload):
        with self.lock:
            _object(payload, {"expected_id", "expected_revision", "mode"}, "game mode")
            if payload["expected_id"] != (self.match.id if self.match else None) or type(payload["expected_revision"]) is not int or payload["expected_revision"] != (self.match.revision if self.match else 0):
                raise StaleRevision("The match changed. Refresh and try again.")
            if payload["mode"] not in ("manual", "bots"):
                raise ValueError("Unknown game mode.")
            if self.mode == "manual":
                self.manual_match = self.match
            self.mode = payload["mode"]
            self.match = self.manual_match if self.mode == "manual" else self.bot_game.tracked if self.bot_game else None
            self._save_active()
            self.analysis.invalidate()
            return self.snapshot()

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
                result.append({"id": data["id"], "name": data["name"], "mode":"bots" if self._bot_path(data["id"]).exists() else "manual",
                               "revision": len(data["commands"]),
                               "deals": 1 + sum(c.get("type") == "next_deal" for c in data["commands"] if isinstance(c, dict)),
                               "modified": path.stat().st_mtime})
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        known = {r["id"] for r in result}
        for path in (self.storage / "bots").glob("*.json"):
            try:
                data=json.loads(read_archive_text(path))
                if data["id"] not in known and self._bot_path(data["id"]) == path:
                    result.append({"id":data["id"],"name":data["name"],"mode":"bots",
                        "revision":data["revision"],"deals":1,"modified":path.stat().st_mtime})
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return sorted(result, key=lambda item: item["modified"], reverse=True)

    def snapshot(self):
        with self.lock:
            return {"match": match_view(self.match), "saved": self.saved(), "mode":self.mode,
                "version": __version__, "illustrated_deck": (WEB_ROOT / "cards/hungarian-illustrated").is_dir(),
                "bot":self.bot_game.public_view() if self.mode == "bots" and self.bot_game else None}

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
                if self._bot_path(payload["id"]).exists():
                    return self._commit_bot(BotGame.loads(read_archive_text(self._bot_path(payload["id"]))))
                candidate = load_user_match(self._path(payload["id"]))
                if candidate.id != payload["id"]:
                    raise ValueError("Archive identity does not match the file.")
            elif route == "/api/import":
                _object(payload, context | {"archive"}, "import")
                # Import as a separate copy so an older export cannot overwrite a newer save.
                candidate = replace(loads_user_match(payload["archive"]), id=str(uuid4()))
            elif route == "/api/command":
                if self.mode == "bots":
                    raise ValueError("Bot games are controlled by the table. Use Manual input to edit another match.")
                _object(payload, context | {"command"}, "event")
                if self.match is None:
                    raise ValueError("Open or create a match first.")
                candidate = self.match.perform(_command(payload["command"]))
            else:
                raise ValueError("Unknown action.")
            # Commit memory only after persistence succeeds.
            save_user_match(candidate, self._path(candidate.id))
            self.match = candidate
            self.mode, self.manual_match = "manual", candidate
            self._save_active()
            self.analysis.invalidate()
            self.review_analysis.invalidate()
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

    def _review_match(self, match_id=None):
        if match_id is None or (self.match is not None and self.match.id == match_id):
            match = self.match
        else:
            match = load_user_match(self._path(match_id))
            if match.id != match_id:
                raise ValueError("Archive identity does not match the file.")
        if match is None:
            raise ValueError("Open a match first.")
        return match

    def review(self, match_id=None):
        with self.lock:
            match = self._review_match(match_id)
        return review_view(match, self.storage, _trick_data)

    def review_variations(self, payload):
        _object(payload, {"expected_id", "expected_revision", "key", "seed"}, "move variations")
        with self.lock:
            match = self._review_match(payload["expected_id"])
            if match.id != payload["expected_id"] or match.revision != payload["expected_revision"]:
                raise StaleRevision("The match changed. Reload the analysis board.")
            snapshot = historical_match(match, payload["key"])
        return review_variations(snapshot, payload["seed"], _trick_data)

    def review_analysis_request(self, route, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError("Expected a request object.")
            match = self._review_match(payload.get("expected_id"))
            if (payload.get("expected_id") != match.id or type(payload.get("expected_revision")) is not int
                    or payload["expected_revision"] != match.revision):
                raise StaleRevision("The match changed. Reload the analysis board.")
            fields = {"expected_id", "expected_revision"}
            if route == "/api/review/analysis/start":
                _object(payload, fields | {"key", "config"}, "historical analysis")
                if not isinstance(payload["key"], str):
                    raise ValueError("Invalid position key.")
                snapshot = historical_match(match, payload["key"])
                source = (match.id, match.revision, len(match.deals), payload["key"])
                job_id = self.review_analysis.start(snapshot, interactive_config(payload["config"]), source=source,
                    journal_context={"source": "dashboard_review", "position_key": payload["key"],
                                     "parent_revision": match.revision})
                self.review_sources[job_id] = source
                while len(self.review_sources) > 8:
                    self.review_sources.pop(next(iter(self.review_sources)))
            elif route == "/api/review/analysis/cancel":
                _object(payload, fields | {"job_id"}, "historical analysis cancellation")
                job_id = payload["job_id"]
                self.review_analysis.cancel(job_id)
            else:
                raise ValueError("Unknown analysis action.")
            return self.review_analysis_view(job_id)

    def review_analysis_view(self, job_id):
        with self.lock:
            if not isinstance(job_id, str) or job_id not in self.review_sources:
                raise ValueError("Analysis not found.")
            saved_source = self.review_sources[job_id]
            try:
                match = self._review_match(saved_source[0])
            except (ValueError, OSError):
                match = None
            source = None if match is None else (match.id, match.revision, len(match.deals), saved_source[3])
            return {**self.review_analysis.view(job_id, source), "position_key": saved_source[3]}

    def feedback(self, payload):
        with self.lock:
            _object(payload, {"expected_id", "expected_revision", "key", "version",
                              "flagged", "alternative", "note"}, "review feedback")
            match = self._review_match(payload["expected_id"])
            if (payload["expected_id"] != match.id or type(payload["expected_revision"]) is not int
                    or payload["expected_revision"] != match.revision):
                raise StaleRevision("The match changed. Reload the review before saving.")
            return save_feedback(match, self.storage, payload)

    def trump_advice(self, payload):
        if not self.trump_lock.acquire(blocking=False):
            raise AnalysisBusy('Trump analysis is already running. Try again shortly.')
        try:
            result = trump_request(payload)
            record = {'format':'bela-trump-analysis-record', 'schema_version':1,
                'provenance':'original_analysis', 'record_id':str(uuid4()),
                'input':result['input'], 'advice':result, 'context':{'source':'dashboard'}}
            append_analysis(self.storage/'trump-analysis'/f"{record['record_id']}.jsonl", record)
            return result
        finally:
            self.trump_lock.release()


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
            if isinstance(data.get("error"), str):
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
            elif path == "/api/review":
                try:
                    self._json(200, dashboard.review(parse_qs(urlsplit(self.path).query).get("match_id", [None])[0]))
                except (ValueError, OSError) as error:
                    self._json(422, {"error": str(error)})
            elif path == "/api/review/analysis":
                try:
                    self._json(200, dashboard.review_analysis_view(parse_qs(urlsplit(self.path).query).get("id", [None])[0]))
                except ValueError as error:
                    self._json(404, {"error": str(error)})
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
            elif path == '/api/project-status':
                try:
                    self._json(200, {'text':(DOCS_ROOT/'PROJECT_STATUS.md').read_text(encoding='utf-8')})
                except OSError:
                    self._json(503, {'error':'The project status document is unavailable.'})
            elif path.startswith("/api/legal/"):
                document = LEGAL_DOCUMENTS.get(path.removeprefix("/api/legal/"))
                if document is None:
                    self._json(404, {"error": "Document not found."})
                else:
                    try:
                        self._json(200, {"text": (RESOURCE_ROOT / document).read_text(encoding="utf-8")})
                    except OSError:
                        self._json(503, {"error": "The release document is unavailable."})
            elif path == "/api/export":
                with dashboard.lock:
                    if dashboard.match is None:
                        self._json(404, {"error": "No open match."})
                        return
                    raw = dumps_user_match(dashboard.match).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(raw),
                                  extra={"Content-Disposition": f'attachment; filename="{dashboard.match.id}.player.json"'})
                    self.wfile.write(raw)
            elif path in CARD_ASSETS:
                try:
                    raw = (WEB_ROOT / path[1:]).read_bytes()
                except FileNotFoundError:
                    self._json(404, {"error": "Card artwork is unavailable in this build."})
                    return
                self._headers(200, "image/webp" if path.endswith(".webp") else "image/svg+xml", len(raw))
                self.wfile.write(raw)
            elif path == "/locale.js":
                raw = ("const CROATIAN = " + json.dumps(CROATIAN, ensure_ascii=False) + ";").encode("utf-8")
                self._headers(200, "text/javascript; charset=utf-8", len(raw))
                self.wfile.write(raw)
            elif path in ("/", "/app.js", "/deck.js", "/advice.js", "/trump.js", "/predeal.js", "/review.js", "/review_analysis.js", "/bot_play.js", "/bot_advice.js", "/live_scores.js", "/review_coach.js", "/review_coach_jobs.js", "/review_board.js", "/review_layout.js", "/knowledge.js", "/i18n.js", "/preferences.js", "/style.css", "/workspace.css", "/desktop.css", "/favicon.svg"):
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
                if route.startswith("/api/bot/"):
                    self._json(200, dashboard.bot_request(route, payload))
                    return
                if route == "/api/mode":
                    self._json(200, dashboard.change_mode(payload))
                    return
                if route in ("/api/review/analysis/start", "/api/review/analysis/cancel"):
                    self._json(200, dashboard.review_analysis_request(route, payload))
                    return
                if route == "/api/review/variations":
                    self._json(200, dashboard.review_variations(payload))
                    return
                if route == '/api/review/feedback':
                    self._json(200, dashboard.feedback(payload))
                    return
                if route == '/api/trump':
                    self._json(200, dashboard.trump_advice(payload))
                    return
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
    parser.add_argument("--port", type=int, default=8766)
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
        dashboard.review_analysis.invalidate()
        server.server_close()
