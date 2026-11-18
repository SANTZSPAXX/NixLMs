"""Policy-governed action execution for the NixLMs runtime.

Only callbacks registered by trusted application code can execute. This module
never deserializes callables, invokes a shell, or discovers tools implicitly.
"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class AutonomyPolicy:
    """Explicit scope/risk policy for registered actions."""

    VALID_SCOPES = {"internal", "local", "external"}
    VALID_RISKS = {"low", "medium", "high", "sensitive"}

    def __init__(
        self,
        *,
        allowed_scopes=None,
        approval_scopes=None,
        approval_risks=None,
        max_actions_per_cycle=5,
        max_payload_bytes=16384,
        max_result_bytes=65536,
    ):
        self.allowed_scopes = set(allowed_scopes or {"internal", "local", "external"})
        self.approval_scopes = set(
            approval_scopes if approval_scopes is not None else {"local", "external"}
        )
        self.approval_risks = set(
            approval_risks if approval_risks is not None else {"high", "sensitive"}
        )
        if not self.allowed_scopes.issubset(self.VALID_SCOPES):
            raise ValueError("Escopo de ação inválido.")
        if not self.approval_scopes.issubset(self.VALID_SCOPES):
            raise ValueError("Escopo de aprovação inválido.")
        if not self.approval_risks.issubset(self.VALID_RISKS):
            raise ValueError("Nível de risco inválido.")
        self.max_actions_per_cycle = max(1, min(100, int(max_actions_per_cycle)))
        self.max_payload_bytes = max(256, int(max_payload_bytes))
        self.max_result_bytes = max(256, int(max_result_bytes))

    def allows(self, scope, risk):
        if scope not in self.allowed_scopes:
            return False
        return scope not in self.approval_scopes and risk not in self.approval_risks


class AutonomyEngine:
    """Bounded action engine with explicit registration and SQLite audit.

    A cycle accepts proposals from a trusted planner. Local/external actions
    require approval by default. A process crash while an action is running
    leaves it in 'running' for manual reconciliation; it is never auto-replayed.
    """

    VALID_STATUSES = {
        "pending_approval", "running", "completed", "failed", "denied"
    }

    def __init__(self, database_path, policy=None):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = policy or AutonomyPolicy()
        self._actions = {}
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self):
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS autonomy_requests (
                    id TEXT PRIMARY KEY,
                    action_name TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    requested_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    approved_by TEXT
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS autonomy_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    def register_action(self, name, callback, *, scope="internal", risk="low",
                        description=""):
        """Register a trusted callback; registration is never loaded from SQLite."""
        name = str(name).strip()
        if not name or len(name) > 100 or not callable(callback):
            raise ValueError("Ação precisa de nome curto e callback válido.")
        if scope not in self.policy.VALID_SCOPES:
            raise ValueError("Escopo de ação inválido.")
        if risk not in self.policy.VALID_RISKS:
            raise ValueError("Nível de risco inválido.")
        with self._lock:
            if name in self._actions:
                raise ValueError("Ação já registrada: " + name)
            self._actions[name] = {
                "callback": callback, "scope": scope, "risk": risk,
                "description": str(description)[:500],
            }

    def registered_actions(self):
        with self._lock:
            return [
                {"name": name, "scope": item["scope"], "risk": item["risk"],
                 "description": item["description"]}
                for name, item in sorted(self._actions.items())
            ]

    def _encode_payload(self, payload):
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("Payload da ação deve ser um objeto JSON.")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False)
        if len(encoded.encode("utf-8")) > self.policy.max_payload_bytes:
            raise ValueError("Payload excede o limite configurado.")
        return encoded

    @staticmethod
    def _event(db, request_id, event, details=None):
        db.execute(
            "INSERT INTO autonomy_events(request_id,event,details_json,created_at) "
            "VALUES(?,?,?,?)",
            (request_id, event, json.dumps(details or {}, ensure_ascii=False,
                                           allow_nan=False), time.time()),
        )

    def request_action(self, action_name, payload=None):
        """Queue an action or execute it only when policy explicitly permits."""
        action_name = str(action_name).strip()
        with self._lock:
            action = self._actions.get(action_name)
        if action is None:
            raise ValueError("Ação não registrada/permitida: " + action_name)
        if action["scope"] not in self.policy.allowed_scopes:
            raise PermissionError("Escopo bloqueado pela política.")
        encoded = self._encode_payload(payload)
        request_id = "act-" + uuid.uuid4().hex
        auto_execute = self.policy.allows(action["scope"], action["risk"])
        status = "running" if auto_execute else "pending_approval"
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO autonomy_requests "
                "(id,action_name,scope,risk,payload_json,status,requested_at,started_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (request_id, action_name, action["scope"], action["risk"],
                 encoded, status, now, now if auto_execute else None),
            )
            self._event(db, request_id, "requested", {
                "scope": action["scope"], "risk": action["risk"],
                "approval_required": not auto_execute,
            })
        if auto_execute:
            self._execute_claimed(request_id, action, json.loads(encoded))
        return self.get_request(request_id)

    def _execute_claimed(self, request_id, action, payload):
        try:
            result = action["callback"](payload)
            encoded = json.dumps(result, ensure_ascii=False, default=str,
                                 allow_nan=False)
            if len(encoded.encode("utf-8")) > self.policy.max_result_bytes:
                raise ValueError("Resultado excede o limite configurado.")
        except Exception as exc:
            message = (type(exc).__name__ + ": " + str(exc))[:2000]
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE autonomy_requests SET status='failed',error=?,finished_at=? "
                    "WHERE id=? AND status='running'",
                    (message, time.time(), request_id),
                )
                self._event(db, request_id, "failed", {"error": message})
            return
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE autonomy_requests SET status='completed',result_json=?,"
                "finished_at=? WHERE id=? AND status='running'",
                (encoded, time.time(), request_id),
            )
            self._event(db, request_id, "completed", {"result_bytes": len(encoded)})

    def approve(self, request_id, *, approved_by):
        approved_by = str(approved_by).strip()
        if not approved_by:
            raise ValueError("Identificação de aprovação obrigatória.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM autonomy_requests WHERE id=?", (str(request_id),)
            ).fetchone()
            if row is None:
                raise ValueError("Solicitação não encontrada.")
            if row["status"] != "pending_approval":
                raise ValueError("Solicitação não está aguardando aprovação.")
            db.execute(
                "UPDATE autonomy_requests SET status='running',started_at=?,approved_by=? "
                "WHERE id=? AND status='pending_approval'",
                (time.time(), approved_by, str(request_id)),
            )
            self._event(db, str(request_id), "approved", {"approved_by": approved_by})
            action_name, payload_json = row["action_name"], row["payload_json"]
        with self._lock:
            action = self._actions.get(action_name)
        if action is None:
            self._finish_failure(request_id, "Ação não registrada neste runtime.")
        else:
            self._execute_claimed(request_id, action, json.loads(payload_json))
        return self.get_request(request_id)

    def deny(self, request_id, *, denied_by, reason=""):
        denied_by = str(denied_by).strip()
        if not denied_by:
            raise ValueError("Identificação de rejeição obrigatória.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "UPDATE autonomy_requests SET status='denied',error=?,finished_at=? "
                "WHERE id=? AND status='pending_approval'",
                (str(reason)[:1000], time.time(), str(request_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Solicitação inexistente ou não aguardando aprovação.")
            self._event(db, str(request_id), "denied", {
                "denied_by": denied_by, "reason": str(reason)[:1000],
            })
        return self.get_request(request_id)

    def _finish_failure(self, request_id, message):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE autonomy_requests SET status='failed',error=?,finished_at=? "
                "WHERE id=? AND status='running'",
                (str(message)[:2000], time.time(), str(request_id)),
            )
            self._event(db, str(request_id), "failed", {"error": str(message)[:2000]})

    def run_cycle(self, proposals):
        """Process a bounded batch of planner proposals; no background thread."""
        if proposals is None:
            proposals = []
        results = []
        for index, proposal in enumerate(proposals):
            if index >= self.policy.max_actions_per_cycle:
                break
            if not isinstance(proposal, dict) or "action" not in proposal:
                raise ValueError("Cada proposta precisa ser um objeto com 'action'.")
            results.append(self.request_action(
                proposal["action"], proposal.get("payload", {})
            ))
        return results

    def get_request(self, request_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM autonomy_requests WHERE id=?", (str(request_id),)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        raw = item.pop("result_json")
        item["result"] = json.loads(raw) if raw is not None else None
        return item

    def list_requests(self, status=None, limit=100):
        limit = max(1, min(500, int(limit)))
        if status is not None and status not in self.VALID_STATUSES:
            raise ValueError("Status inválido.")
        query = "SELECT id FROM autonomy_requests"
        params = []
        if status is not None:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY requested_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as db:
            ids = [row["id"] for row in db.execute(query, params).fetchall()]
        return [self.get_request(item) for item in ids]

    def events(self, request_id, limit=100):
        with self._connect() as db:
            rows = db.execute(
                "SELECT event,details_json,created_at FROM autonomy_events "
                "WHERE request_id=? ORDER BY id ASC LIMIT ?",
                (str(request_id), max(1, min(500, int(limit)))),
            ).fetchall()
        return [
            {"event": row["event"], "details": json.loads(row["details_json"]),
             "created_at": row["created_at"]}
            for row in rows
        ]
