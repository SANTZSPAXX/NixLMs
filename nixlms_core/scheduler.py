"""Agendador persistente local, com handlers allowlisted e SQLite.

Entrega at-least-once: em caso de queda durante um handler, a tarefa pode ser
reivindicada novamente após o lease expirar. Handlers devem ser idempotentes.
Nenhum callable, comando shell ou código é desserializado do banco.
"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class TaskScheduler:
    VALID_STATES = {"pending", "running", "completed", "failed", "cancelled"}

    def __init__(self, database_path, *, poll_interval=1.0, lease_seconds=300,
                 max_jobs=10000, max_payload_bytes=65536):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.poll_interval = max(0.1, float(poll_interval))
        self.lease_seconds = max(5, int(lease_seconds))
        self.max_jobs = max(1, int(max_jobs))
        self.max_payload_bytes = max(256, int(max_payload_bytes))
        self._handlers = {}
        self._stop_event = threading.Event()
        self._thread = None
        self._worker_id = "worker-" + uuid.uuid4().hex
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    id TEXT PRIMARY KEY,
                    handler TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_at REAL NOT NULL,
                    interval_seconds REAL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    lease_until REAL,
                    last_error TEXT,
                    last_result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_due
                ON scheduled_jobs(status, run_at, priority)
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details_json TEXT,
                    created_at REAL NOT NULL
                )
            """)

    def register_handler(self, name, callback):
        name = str(name).strip()
        if not name or not callable(callback):
            raise ValueError("Handler precisa de nome e callback válido.")
        if name in self._handlers:
            raise ValueError(f"Handler já registrado: {name}")
        self._handlers[name] = callback

    def _validate_payload(self, payload):
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload deve ser um objeto/dicionário JSON.")
        try:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("payload precisa ser serializável em JSON.") from exc
        if len(encoded.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("payload excede o limite permitido.")
        return encoded

    def _schedule(self, handler, payload, delay_seconds, interval_seconds,
                  priority, max_attempts, job_id=None):
        handler = str(handler).strip()
        if handler not in self._handlers:
            raise ValueError(f"Handler não permitido ou não registrado: {handler}")
        delay = float(delay_seconds)
        if delay < 0:
            raise ValueError("delay_seconds não pode ser negativo.")
        interval = None if interval_seconds is None else float(interval_seconds)
        if interval is not None and interval < 1:
            raise ValueError("interval_seconds deve ser pelo menos 1 segundo.")
        attempts = int(max_attempts)
        if not 1 <= attempts <= 20:
            raise ValueError("max_attempts deve estar entre 1 e 20.")
        priority = int(priority)
        encoded = self._validate_payload(payload)
        now = time.time()
        identifier = str(job_id or ("job-" + uuid.uuid4().hex[:16]))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "SELECT COUNT(*) FROM scheduled_jobs WHERE status IN ('pending','running')"
            ).fetchone()[0]
            if count >= self.max_jobs:
                raise ValueError("Limite de tarefas pendentes/ativas atingido.")
            db.execute("""
                INSERT INTO scheduled_jobs
                (id, handler, payload_json, status, run_at, interval_seconds,
                 priority, attempts, max_attempts, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, 0, ?, ?, ?)
            """, (identifier, handler, encoded, now + delay, interval,
                  priority, attempts, now, now))
            self._event(db, identifier, "scheduled", {"handler": handler})
        return identifier

    def schedule_once(self, handler, payload=None, *, delay_seconds=0,
                      priority=0, max_attempts=3, job_id=None):
        return self._schedule(handler, payload, delay_seconds, None,
                              priority, max_attempts, job_id)

    def schedule_interval(self, handler, interval_seconds, payload=None, *,
                          first_delay_seconds=None, priority=0,
                          max_attempts=3, job_id=None):
        delay = interval_seconds if first_delay_seconds is None else first_delay_seconds
        return self._schedule(handler, payload, delay, interval_seconds,
                              priority, max_attempts, job_id)

    @staticmethod
    def _event(db, job_id, event, details=None):
        db.execute(
            "INSERT INTO scheduler_events(job_id,event,details_json,created_at) VALUES(?,?,?,?)",
            (job_id, event, json.dumps(details or {}, ensure_ascii=False), time.time())
        )

    def cancel(self, job_id):
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("""
                UPDATE scheduled_jobs SET status='cancelled', updated_at=?
                WHERE id=? AND status='pending'
            """, (now, str(job_id)))
            if cursor.rowcount:
                self._event(db, str(job_id), "cancelled")
            return cursor.rowcount == 1

    def _claim(self):
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Jobs abandoned by a crashed process become eligible after lease expiry.
            expired = db.execute("""
                SELECT id FROM scheduled_jobs
                WHERE status='running' AND lease_until < ?
            """, (now,)).fetchall()
            for row in expired:
                db.execute("""
                    UPDATE scheduled_jobs SET status='pending', lease_until=NULL,
                    run_at=?, updated_at=? WHERE id=? AND status='running'
                """, (now, now, row["id"]))
                self._event(db, row["id"], "lease_expired")
            row = db.execute("""
                SELECT * FROM scheduled_jobs
                WHERE status='pending' AND run_at <= ?
                ORDER BY priority DESC, run_at ASC, created_at ASC
                LIMIT 1
            """, (now,)).fetchone()
            if row is None:
                return None
            cursor = db.execute("""
                UPDATE scheduled_jobs SET status='running', attempts=attempts+1,
                lease_until=?, updated_at=?
                WHERE id=? AND status='pending'
            """, (now + self.lease_seconds, now, row["id"]))
            if cursor.rowcount != 1:
                return None
            self._event(db, row["id"], "started", {"attempt": row["attempts"] + 1})
            claimed = dict(row)
            claimed["attempts"] += 1
            return claimed

    def _finish(self, job, *, result=None, error=None):
        now = time.time()
        job_id = job["id"]
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT status, attempts, max_attempts, interval_seconds FROM scheduled_jobs WHERE id=?",
                (job_id,)
            ).fetchone()
            if current is None or current["status"] != "running":
                return
            if error is None:
                encoded = json.dumps(result, ensure_ascii=False, default=str)
                if current["interval_seconds"] is not None:
                    next_run = now + float(current["interval_seconds"])
                    db.execute("""
                        UPDATE scheduled_jobs SET status='pending', run_at=?,
                        attempts=0, lease_until=NULL, last_error=NULL,
                        last_result_json=?, updated_at=? WHERE id=?
                    """, (next_run, encoded, now, job_id))
                    self._event(db, job_id, "completed", {"next_run_at": next_run, "result": result})
                else:
                    db.execute("""
                        UPDATE scheduled_jobs SET status='completed', lease_until=NULL,
                        last_error=NULL, last_result_json=?, updated_at=? WHERE id=?
                    """, (encoded, now, job_id))
                    self._event(db, job_id, "completed", {"result": result})
            else:
                message = str(error)[:2000]
                if current["attempts"] < current["max_attempts"]:
                    backoff = min(3600.0, 2.0 ** max(0, current["attempts"] - 1))
                    db.execute("""
                        UPDATE scheduled_jobs SET status='pending', run_at=?,
                        lease_until=NULL, last_error=?, updated_at=? WHERE id=?
                    """, (now + backoff, message, now, job_id))
                    self._event(db, job_id, "retry_scheduled", {"error": message, "delay_seconds": backoff})
                else:
                    db.execute("""
                        UPDATE scheduled_jobs SET status='failed', lease_until=NULL,
                        last_error=?, updated_at=? WHERE id=?
                    """, (message, now, job_id))
                    self._event(db, job_id, "failed", {"error": message})

    def run_once(self):
        job = self._claim()
        if job is None:
            return False
        handler = self._handlers.get(job["handler"])
        if handler is None:
            self._finish(job, error=f"Handler indisponível após reinício: {job['handler']}")
            return True
        try:
            payload = json.loads(job["payload_json"])
            result = handler(payload)
            self._finish(job, result=result)
        except Exception as exc:
            self._finish(job, error=f"{type(exc).__name__}: {exc}")
        return True

    def run_due(self, limit=100):
        limit = int(limit)
        if limit < 1:
            return 0
        completed = 0
        for _ in range(min(limit, 1000)):
            if not self.run_once():
                break
            completed += 1
        return completed

    def list_jobs(self, status=None, limit=100):
        limit = max(1, min(1000, int(limit)))
        query = "SELECT * FROM scheduled_jobs"
        params = []
        if status is not None:
            if status not in self.VALID_STATES:
                raise ValueError("status inválido.")
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY run_at ASC LIMIT ?"
        params.append(limit)
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            item["last_result"] = json.loads(item.pop("last_result_json")) if item.get("last_result_json") else None
            result.append(item)
        return result

    def events(self, job_id, limit=50):
        with self._connect() as db:
            rows = db.execute("""
                SELECT event, details_json, created_at FROM scheduler_events
                WHERE job_id=? ORDER BY id DESC LIMIT ?
            """, (str(job_id), max(1, min(500, int(limit))))).fetchall()
        return [{"event": row["event"], "details": json.loads(row["details_json"] or "{}"),
                 "created_at": row["created_at"]} for row in rows]

    def stats(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT status, COUNT(*) AS count FROM scheduled_jobs GROUP BY status"
            ).fetchall()
        counts = {state: 0 for state in self.VALID_STATES}
        counts.update({row["status"]: row["count"] for row in rows})
        return {"jobs": sum(counts.values()), "by_status": counts,
                "registered_handlers": sorted(self._handlers)}

    def start(self):
        if self._thread and self._thread.is_alive():
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="nixlms-scheduler", daemon=True
        )
        self._thread.start()
        return True

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                if not self.run_once():
                    self._stop_event.wait(self.poll_interval)
            except (sqlite3.Error, OSError):
                self._stop_event.wait(self.poll_interval)

    def stop(self, timeout=5.0):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(max(0.0, float(timeout)))
        stopped = not (self._thread and self._thread.is_alive())
        if stopped:
            self._thread = None
        return stopped

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())
