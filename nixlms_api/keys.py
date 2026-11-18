"""Armazenamento local de chaves da API; segredos são exibidos somente na criação."""
from __future__ import annotations
import hashlib, json, secrets, sqlite3, time
from contextlib import contextmanager
from pathlib import Path
VALID_SCOPES = {"chat:read", "chat:write", "models:read"}

class APIKeyStore:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY, prefix TEXT NOT NULL, label TEXT NOT NULL,
                scopes TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL,
                revoked_at REAL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix)")
    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
    def create(self, label, scopes=None, ttl_days=None):
        scopes = sorted(set(scopes or ["chat:read", "chat:write", "models:read"]))
        if not scopes or not set(scopes).issubset(VALID_SCOPES):
            raise ValueError("Escopos inválidos: " + ", ".join(sorted(VALID_SCOPES)))
        if ttl_days is not None and not 1 <= int(ttl_days) <= 3650:
            raise ValueError("Validade deve ser de 1 a 3650 dias.")
        token = "nix_" + secrets.token_urlsafe(36); now = time.time()
        expires = now + int(ttl_days) * 86400 if ttl_days is not None else None
        with self._connect() as db:
            db.execute("INSERT INTO api_keys VALUES (?, ?, ?, ?, ?, ?, NULL)",
                       (self._digest(token), token[:12], str(label)[:100], json.dumps(scopes), now, expires))
        return {"token": token, "prefix": token[:12], "label": str(label)[:100],
                "scopes": scopes, "created_at": now, "expires_at": expires}
    def authenticate(self, token):
        if not isinstance(token, str) or not token.startswith("nix_") or len(token) > 200: return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM api_keys WHERE key_hash=?", (self._digest(token),)).fetchone()
        if row is None or row["revoked_at"] is not None: return None
        if row["expires_at"] is not None and row["expires_at"] <= time.time(): return None
        return {"prefix": row["prefix"], "label": row["label"], "scopes": json.loads(row["scopes"])}
    def list(self):
        with self._connect() as db:
            rows = db.execute("SELECT prefix,label,scopes,created_at,expires_at,revoked_at FROM api_keys ORDER BY created_at DESC").fetchall()
        return [dict(row) | {"scopes": json.loads(row["scopes"]),
                "status": "revoked" if row["revoked_at"] else
                "expired" if row["expires_at"] and row["expires_at"] <= time.time() else "active"}
                for row in rows]
    def revoke(self, prefix):
        with self._connect() as db:
            cur = db.execute("UPDATE api_keys SET revoked_at=? WHERE prefix=? AND revoked_at IS NULL", (time.time(), prefix))
            return cur.rowcount == 1
