import tempfile
import unittest
from pathlib import Path

from nixlms_core.autonomy import AutonomyEngine, AutonomyPolicy


class AutonomyEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = AutonomyEngine(Path(self.temp.name) / "autonomy.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_internal_low_risk_action_executes(self):
        called = []
        self.engine.register_action("memory.inspect", lambda payload: called.append(payload) or {"ok": True})
        result = self.engine.request_action("memory.inspect", {"limit": 2})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(called, [{"limit": 2}])
        self.assertEqual([event["event"] for event in self.engine.events(result["id"])],
                         ["requested", "completed"])

    def test_local_action_requires_approval_by_default(self):
        called = []
        self.engine.register_action("file.read", lambda payload: called.append(payload),
                                    scope="local", risk="low")
        result = self.engine.request_action("file.read", {"path": "notes.txt"})
        self.assertEqual(result["status"], "pending_approval")
        self.assertEqual(called, [])
        approved = self.engine.approve(result["id"], approved_by="operator")
        self.assertEqual(approved["status"], "completed")
        self.assertEqual(len(called), 1)

    def test_external_sensitive_action_requires_approval(self):
        self.engine.register_action("http.post", lambda payload: {"sent": True},
                                    scope="external", risk="sensitive")
        result = self.engine.request_action("http.post", {})
        self.assertEqual(result["status"], "pending_approval")

    def test_denied_action_never_runs(self):
        called = []
        self.engine.register_action("system.change", lambda payload: called.append(True),
                                    scope="local", risk="high")
        result = self.engine.request_action("system.change")
        denied = self.engine.deny(result["id"], denied_by="operator", reason="not now")
        self.assertEqual(denied["status"], "denied")
        self.assertEqual(called, [])

    def test_unregistered_action_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.request_action("shell.execute", {"command": "echo unsafe"})

    def test_empty_allowed_scopes_blocks_every_action(self):
        policy = AutonomyPolicy(allowed_scopes=set())
        engine = AutonomyEngine(Path(self.temp.name) / "none.sqlite3", policy)
        engine.register_action("internal.read", lambda payload: None)
        with self.assertRaises(PermissionError):
            engine.request_action("internal.read")

    def test_disallowed_scope_is_rejected(self):
        policy = AutonomyPolicy(allowed_scopes={"internal"})
        engine = AutonomyEngine(Path(self.temp.name) / "restricted.sqlite3", policy)
        engine.register_action("local.read", lambda payload: None, scope="local")
        with self.assertRaises(PermissionError):
            engine.request_action("local.read")

    def test_duplicate_registration_is_rejected(self):
        callback = lambda payload: None
        self.engine.register_action("noop", callback)
        with self.assertRaises(ValueError):
            self.engine.register_action("noop", callback)

    def test_payload_must_be_json_object(self):
        self.engine.register_action("noop", lambda payload: None)
        with self.assertRaises(ValueError):
            self.engine.request_action("noop", ["not", "an", "object"])

    def test_payload_size_is_bounded(self):
        policy = AutonomyPolicy(max_payload_bytes=256)
        engine = AutonomyEngine(Path(self.temp.name) / "bounded.sqlite3", policy)
        engine.register_action("noop", lambda payload: None)
        with self.assertRaises(ValueError):
            engine.request_action("noop", {"text": "x" * 300})

    def test_nan_payload_is_rejected(self):
        self.engine.register_action("noop", lambda payload: None)
        with self.assertRaises(ValueError):
            self.engine.request_action("noop", {"score": float("nan")})

    def test_callback_failure_is_audited(self):
        def fail(payload):
            raise RuntimeError("expected failure")
        self.engine.register_action("fail", fail)
        result = self.engine.request_action("fail")
        self.assertEqual(result["status"], "failed")
        self.assertIn("RuntimeError", result["error"])

    def test_cycle_is_bounded(self):
        policy = AutonomyPolicy(max_actions_per_cycle=2)
        engine = AutonomyEngine(Path(self.temp.name) / "cycle.sqlite3", policy)
        calls = []
        engine.register_action("tick", lambda payload: calls.append(payload) or True)
        results = engine.run_cycle([
            {"action": "tick", "payload": {"n": 1}},
            {"action": "tick", "payload": {"n": 2}},
            {"action": "tick", "payload": {"n": 3}},
        ])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(calls), 2)

    def test_approval_cannot_be_replayed(self):
        self.engine.register_action("local.action", lambda payload: True, scope="local")
        result = self.engine.request_action("local.action")
        self.engine.approve(result["id"], approved_by="operator")
        with self.assertRaises(ValueError):
            self.engine.approve(result["id"], approved_by="operator")

    def test_unknown_request_cannot_be_approved(self):
        with self.assertRaises(ValueError):
            self.engine.approve("missing", approved_by="operator")

    def test_registry_is_not_loaded_from_database(self):
        self.engine.register_action("internal.action", lambda payload: True)
        result = self.engine.request_action("internal.action")
        fresh = AutonomyEngine(Path(self.temp.name) / "autonomy.sqlite3")
        self.assertEqual(fresh.registered_actions(), [])
        self.assertEqual(fresh.get_request(result["id"])["status"], "completed")

    def test_cycle_rejects_malformed_proposal(self):
        with self.assertRaises(ValueError):
            self.engine.run_cycle([{"payload": {}}])


if __name__ == "__main__":
    unittest.main()
