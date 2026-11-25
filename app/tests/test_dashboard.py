import http.client
import json
from pathlib import Path
import tempfile
import threading
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from bela.interfaces.dashboard import Dashboard, StaleRevision, make_server
from bela.paths import EXAMPLES_ROOT
from bela.storage.persistence import InvalidSaveError
from bela.storage.user_storage import load_user_match


EXAMPLE = EXAMPLES_ROOT / "player_match.json"
SETUP = {"player": 0, "hand": "H_Q H_K S_9 S_10 S_A D_K C_8 C_9".split(),
         "dealer": 3, "caller": 0, "trump": "H", "match_score": [0, 0]}


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dashboard = Dashboard(Path(self.tmp.name), EXAMPLE)

    def mutate(self, route, **data):
        match = self.dashboard.match
        return self.dashboard.mutate(route, {"expected_id": match.id if match else None,
                                              "expected_revision": match.revision if match else 0, **data})

    def new(self):
        return self.mutate("/api/new", name="Moja partija", setup=SETUP)

    def test_create_and_view_have_only_user_knowledge(self):
        self.assertIsNone(self.dashboard.snapshot()["match"])
        data = self.new()
        self.assertEqual(data["match"]["hand"], SETUP["hand"])
        self.assertNotIn("hands", data["match"])
        self.assertEqual(data["match"]["remaining_counts"], (8, 8, 8, 8))
        self.assertEqual(len(data["saved"]), 1)
        self.assertEqual(load_user_match(self.dashboard._path(data["match"]["id"])), self.dashboard.match)

    def test_invalid_input_and_failed_save_leave_previous_state(self):
        self.new()
        before = self.dashboard.match
        with self.assertRaises(ValueError):
            self.mutate("/api/command", command={"type": "add", "event": {
                "type": "play", "player": 0, "card": "H_Q", "bela": False}})
        self.assertEqual(self.dashboard.match, before)
        path = self.dashboard._path(before.id)
        raw = path.read_bytes()
        with patch("bela.interfaces.dashboard.save_user_match", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.mutate("/api/command", command={"type": "add", "event": {
                    "type": "finish_declarations", "winning_team": None}})
        self.assertEqual(self.dashboard.match, before)
        self.assertEqual(path.read_bytes(), raw)

    def test_play_edit_and_reload(self):
        self.new()
        for command in [
            {"type": "add", "event": {"type": "finish_declarations", "winning_team": None}},
            {"type": "add", "event": {"type": "play", "player": 0, "card": "H_Q", "bela": True}},
            {"type": "replace", "index": 1, "event": {"type": "play", "player": 0, "card": "H_K", "bela": True}},
        ]:
            data = self.mutate("/api/command", command=command)
        self.assertEqual(data["match"]["trick"]["plays"], [{"player": 0, "card": "H_K"}])
        self.assertEqual(data["match"]["bela_players"], [0])
        other = Dashboard(Path(self.tmp.name), EXAMPLE)
        self.assertEqual(other.snapshot()["match"], data["match"])
        loaded = other.mutate("/api/load", {"expected_id": other.match.id, "expected_revision": other.match.revision, "id": data["match"]["id"]})
        self.assertEqual(loaded["match"], data["match"])

    def test_stale_tab_is_rejected(self):
        data = self.new()
        self.mutate("/api/command", command={"type": "add", "event": {
            "type": "finish_declarations", "winning_team": None}})
        with self.assertRaises(StaleRevision):
            self.dashboard.mutate("/api/demo", {"expected_id": data["match"]["id"], "expected_revision": 0})

    def test_demo_and_import_are_separate_copies(self):
        original = EXAMPLE.read_bytes()
        demo = self.mutate("/api/demo")["match"]
        self.assertEqual(demo["legal_cards"], ["H_K"])
        imported = self.mutate("/api/import", archive=original.decode("utf-8"))["match"]
        self.assertNotEqual(demo["id"], imported["id"])
        self.assertEqual(EXAMPLE.read_bytes(), original)
        self.assertEqual(len(self.dashboard.saved()), 2)

    def test_ids_and_unknown_commands_are_rejected(self):
        for match_id in ("../outside", "", None, 123):
            with self.subTest(match_id=match_id), self.assertRaises(ValueError):
                self.dashboard._path(match_id)
        self.new()
        with self.assertRaises(InvalidSaveError):
            self.mutate("/api/command", command={"type": "delete_all"})


class HttpDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dashboard = Dashboard(Path(self.tmp.name), EXAMPLE)
        self.server = make_server(self.dashboard, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        self.dashboard.analysis.invalidate()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, path, payload):
        return self.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})

    def test_static_assets_rules_and_no_directory_traversal(self):
        for path in ("/", "/app.js", "/deck.js", "/cards/hungarian/H_J.svg", "/cards/hungarian/S_Q.svg", "/cards/hungarian/D_A.svg", "/cards/hungarian/C_10.svg", "/cards/hearts.svg", "/cards/leaves.svg", "/cards/bells.svg", "/cards/acorns.svg", "/advice.js", "/predeal.js", "/review.js", "/review_board.js", "/review_analysis.js", "/knowledge.js", "/i18n.js", "/preferences.js", "/locale.js", "/style.css", "/workspace.css", "/favicon.svg", "/api/rules", "/api/project-status"):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "/../RULES.md")[0], 404)
        for name in ("terms", "privacy", "notices"):
            status, _, body = self.request("GET", f"/api/legal/{name}")
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["text"].startswith("# Bela Lab"))
        self.assertEqual(self.request("GET", "/api/legal/other")[0], 404)
        self.assertEqual(json.loads(self.request("GET", "/api/state")[2])["version"], "1.0.0")
        for path in ("/review_coach.js", "/review_coach_jobs.js"):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith("text/javascript"))
            self.assertTrue(body)
        for suit in "HSDC":
            for rank in ("7", "8", "9", "10", "J", "Q", "K", "A"):
                status, headers, body = self.request("GET", f"/cards/hungarian/{suit}_{rank}.svg")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "image/svg+xml")
                self.assertIn(b"<svg", body)
                status, headers, body = self.request("GET", f"/cards/hungarian-illustrated/{suit}_{rank}.webp")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "image/webp")
                self.assertEqual(body[8:12], b"WEBP")
        self.assertEqual(self.request("GET", "/cards/hungarian/H_2.svg")[0], 404)

    def test_knowledge_is_revisioned_read_only_and_contains_no_witness(self):
        self.assertEqual(self.request("GET", "/api/knowledge")[0], 404)
        _, _, body = self.post("/api/demo", {"expected_id": None, "expected_revision": 0})
        match = json.loads(body)["match"]
        before = self.dashboard._path(match["id"]).read_bytes()
        status, _, body = self.request("GET", "/api/knowledge")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["match_id"], match["id"])
        self.assertEqual(data["revision"], match["revision"])
        self.assertTrue(data["complete"])
        self.assertNotIn("hands", data)
        self.assertNotIn(b'"witness"', body)
        self.assertEqual(self.dashboard._path(match["id"]).read_bytes(), before)

    def test_language_changes_errors_and_rules_without_changing_match(self):
        status, _, body = self.request("GET", "/api/export")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "No open match.")
        status, _, body = self.request("GET", "/api/export", headers={"Accept-Language": "hr-HR"})
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "Nema otvorene partije.")
        _, _, english = self.request("GET", "/api/rules")
        _, _, croatian = self.request("GET", "/api/rules?lang=hr")
        self.assertIn("Croatian four-player Bela", json.loads(english)["text"])
        self.assertIn("Pravila hrvatske bele", json.loads(croatian)["text"])
        self.assertIsNone(self.dashboard.match)

    def test_http_demo_command_export_and_conflict(self):
        payload = {"expected_id": None, "expected_revision": 0}
        status, _, body = self.post("/api/demo", payload)
        self.assertEqual(status, 200)
        data = json.loads(body)["match"]
        self.assertEqual(self.post("/api/demo", payload)[0], 409)
        status, headers, body = self.request("GET", "/api/export")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(body)["format"], "bela-player-session")
        status, _, body = self.post("/api/command", {"expected_id": data["id"],
            "expected_revision": data["revision"], "command": {"type": "add", "event": {
                "type": "play", "player": 0, "card": "H_K", "bela": False}}})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["match"]["next_player"], 1)

    def test_rejects_other_origins_hosts_and_bad_payloads(self):
        for headers in ({"Host": "external.example"}, {"Origin": "https://external.example"}):
            self.assertEqual(self.request("GET", "/api/state", headers=headers)[0], 403)
        self.assertEqual(self.request("POST", "/api/new", "{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/new", "not JSON", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/new", "not JSON", {"Content-Type": "application/json"})[0], 422)
        self.assertEqual(self.request("GET", "/api/export")[0], 404)

    def test_analysis_http_job_is_read_only_and_rejects_stale_context(self):
        _, _, body = self.post("/api/demo", {"expected_id": None, "expected_revision": 0})
        match = json.loads(body)["match"]
        before = self.dashboard._path(match["id"]).read_bytes()
        payload = {"expected_id": match["id"], "expected_revision": match["revision"],
                   "config": {"samples": 4, "seconds": 1, "seed": 9,
                              "policy": "random_v1", "objective": "contract_success"}}
        status, _, body = self.post("/api/analysis/start", payload)
        self.assertEqual(status, 200)
        job_id = json.loads(body)["id"]
        deadline = monotonic() + 3
        while monotonic() < deadline:
            status, _, body = self.request("GET", "/api/analysis?id=" + job_id,
                                           headers={"Accept-Language": "hr-HR"})
            self.assertEqual(status, 200)
            job = json.loads(body)
            if job["state"] == "finished":
                break
            sleep(.01)
        self.assertEqual(job["state"], "finished")
        self.assertIsNone(job["error"])
        self.assertEqual(job["result"]["status"], "forced_move")
        self.assertEqual(self.dashboard._path(match["id"]).read_bytes(), before)
        self.assertEqual(self.request("GET", "/api/analysis?id=missing")[0], 404)
        self.assertEqual(self.post("/api/analysis/start", {**payload, "expected_revision": 0})[0], 409)
        self.assertEqual(self.post("/api/command", {"expected_id": match["id"],
            "expected_revision": match["revision"], "command": {"type": "add", "event": {
                "type": "play", "player": 0, "card": "H_K", "bela": False}}})[0], 200)
        _, _, body = self.request("GET", "/api/analysis?id=" + job_id)
        stale = json.loads(body)
        self.assertEqual(stale["state"], "stale")
        self.assertIsNone(stale["result"])
