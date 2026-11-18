"""Supabase PostgreSQL persistence and pgvector retrieval for NixLMs.

Configure NIXLMS_DATABASE_URL with the Supabase Postgres connection string.
The module is optional: local execution remains available when unset.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
from pathlib import Path, PurePosixPath

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # optional dependency on local installations
    psycopg = None
    dict_row = None


MAX_SNAPSHOT_BYTES = 40 * 1024 * 1024
SNAPSHOT_SUFFIXES = {".json", ".jsonl", ".sqlite3", ".db", ".yaml", ".yml", ".toml", ".csv"}
EXCLUDED_PARTS = {"cache", "__pycache__", "models", "hub", "outputs", "tmp", ".git"}


class SupabaseStore:
    def __init__(self, database_url: str, data_dir: Path, *, connect_timeout=5):
        if psycopg is None:
            raise RuntimeError("Instale psycopg[binary] para habilitar Supabase.")
        if not database_url:
            raise ValueError("NIXLMS_DATABASE_URL não configurada.")
        self.database_url = database_url
        self.data_dir = Path(data_dir).resolve()
        self.connect_timeout = max(2, min(15, int(connect_timeout)))
        self._lock = threading.RLock()
        self._last_hashes = {}
        self._last_error = None
        self._restored = False

    @classmethod
    def from_env(cls, data_dir):
        url = os.getenv("NIXLMS_DATABASE_URL", "").strip()
        if not url:
            return None
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError("NIXLMS_DATABASE_URL precisa ser uma URL PostgreSQL.")
        return cls(url, data_dir)

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            connect_timeout=self.connect_timeout,
            sslmode="require",
            row_factory=dict_row,
        )

    def ping(self):
        with self._connect() as conn:
            row = conn.execute("SELECT current_database() AS database, now() AS server_time").fetchone()
        self._last_error = None
        return {"ok": True, "database": row["database"], "server_time": row["server_time"].isoformat()}

    @staticmethod
    def _safe_relative(path: str):
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or not parsed.parts or any(part in {"", ".", ".."} for part in parsed.parts):
            raise ValueError("Caminho de snapshot inválido.")
        return parsed

    def restore(self):
        """Restore the last committed snapshot before application modules open files."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT path, content, sha256 FROM public.nix_runtime_snapshots ORDER BY path"
            ).fetchall()
            restored = 0
            for row in rows:
                rel = self._safe_relative(row["path"])
                target = (self.data_dir / Path(*rel.parts)).resolve()
                if self.data_dir not in target.parents:
                    raise ValueError("Snapshot fora do diretório de dados.")
                content = bytes(row["content"])
                digest = hashlib.sha256(content).hexdigest()
                if digest != row["sha256"]:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.suffix.lower() in {".sqlite3", ".db"}:
                    for suffix in ("-wal", "-shm"):
                        try:
                            Path(str(target) + suffix).unlink()
                        except FileNotFoundError:
                            pass
                fd, temp_name = tempfile.mkstemp(prefix=".nix-restore-", dir=str(target.parent))
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp_name, target)
                    restored += 1
                    self._last_hashes[row["path"]] = digest
                finally:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
            self._restored = True
            self._last_error = None
            return {"restored_files": restored, "snapshot_files": len(rows)}

    def _iter_files(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in self.data_dir.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(self.data_dir)
            if any(part.lower() in EXCLUDED_PARTS for part in rel.parts):
                continue
            if path.suffix.lower() not in SNAPSHOT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_SNAPSHOT_BYTES:
                    continue
            except OSError:
                continue
            yield path, rel.as_posix()

    @staticmethod
    def _read_consistent(path: Path):
        if path.suffix.lower() in {".sqlite3", ".db"}:
            fd, temp_name = tempfile.mkstemp(prefix=".nix-sqlite-backup-")
            os.close(fd)
            try:
                source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
                target = sqlite3.connect(temp_name)
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()
                return Path(temp_name).read_bytes()
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
        return path.read_bytes()

    def sync(self):
        """Upload changed durable state files; SQLite files use SQLite's backup API."""
        with self._lock:
            if not self._restored:
                self.restore()
            rows = []
            for path, relative in self._iter_files():
                try:
                    content = self._read_consistent(path)
                except (OSError, sqlite3.Error):
                    continue
                digest = hashlib.sha256(content).hexdigest()
                if self._last_hashes.get(relative) == digest:
                    continue
                rows.append((relative, content, digest))
            if not rows:
                return {"uploaded_files": 0, "status": "ok"}
            with self._connect() as conn:
                conn.executemany(
                    """INSERT INTO public.nix_runtime_snapshots(path, content, sha256, updated_at)
                       VALUES (%s, %s, %s, now())
                       ON CONFLICT(path) DO UPDATE SET
                         content = EXCLUDED.content,
                         sha256 = EXCLUDED.sha256,
                         updated_at = now()""",
                    rows,
                )
            for relative, _, digest in rows:
                self._last_hashes[relative] = digest
            self._last_error = None
            return {"uploaded_files": len(rows), "status": "ok"}

    def upsert_vector(self, memory_id, memory_type, content, embedding, metadata=None):
        return self.upsert_vectors([(memory_id, memory_type, content, embedding, metadata)])

    def upsert_vectors(self, records):
        rows = []
        for memory_id, memory_type, content, embedding, metadata in records:
            vector = [float(value) for value in embedding]
            if len(vector) != 64:
                raise ValueError(f"Embedding precisa ter 64 dimensões; recebido: {len(vector)}.")
            if memory_type not in {"knowledge", "episode", "library"}:
                raise ValueError("Tipo de memória vetorial inválido.")
            vector_literal = "[" + ",".join(format(value, ".9g") for value in vector) + "]"
            rows.append((
                str(memory_id), str(memory_type), str(content)[:12000],
                vector_literal, json.dumps(metadata or {}, ensure_ascii=False),
            ))
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO public.nix_memory_vectors
                   (memory_id, memory_type, content, embedding, metadata, updated_at)
                   VALUES (%s, %s, %s, %s::extensions.vector(64), %s::jsonb, now())
                   ON CONFLICT(memory_id) DO UPDATE SET
                     memory_type=EXCLUDED.memory_type, content=EXCLUDED.content,
                     embedding=EXCLUDED.embedding, metadata=EXCLUDED.metadata,
                     updated_at=now()""",
                rows,
            )
        return len(rows)

    def vector_count(self):
        with self._connect() as conn:
            row = conn.execute("SELECT count(*) AS total FROM public.nix_memory_vectors").fetchone()
        return int(row["total"])

    def search_vectors(self, embedding, limit=5, memory_type=None):
        vector = [float(value) for value in embedding]
        if len(vector) != 64:
            return []
        vector_literal = "[" + ",".join(format(value, ".9g") for value in vector) + "]"
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT memory_id, memory_type, content, metadata,
                          1 - (embedding <=> %s::extensions.vector(64)) AS similarity
                   FROM public.nix_memory_vectors
                   WHERE (%s::text IS NULL OR memory_type = %s::text)
                   ORDER BY embedding <=> %s::extensions.vector(64)
                   LIMIT %s""",
                (vector_literal, memory_type, memory_type, vector_literal,
                 max(1, min(20, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def status(self):
        return {
            "configured": True,
            "restored": self._restored,
            "last_error": self._last_error,
        }


class SnapshotWorker:
    def __init__(self, store: SupabaseStore, interval=15):
        self.store = store
        self.interval = max(5, int(interval))
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="nixlms-supabase-sync", daemon=True)
        self._thread.start()
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                self.store.sync()
            except Exception as exc:
                self.store._last_error = type(exc).__name__ + ": " + str(exc)[:300]
            self._stop.wait(self.interval)

    def flush(self):
        return self.store.sync()

    def stop(self, timeout=5):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(0, timeout))
        try:
            return self.store.sync()
        except Exception as exc:
            self.store._last_error = type(exc).__name__ + ": " + str(exc)[:300]
            return {"status": "error", "error": self.store._last_error}
