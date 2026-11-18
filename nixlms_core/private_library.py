"""Biblioteca privada local de documentos e candidatos de aprendizagem.

Os ficheiros são copiados para SQLite local em blocos pesquisáveis. Nada é
baixado, executado ou promovido automaticamente para pesos neurais.
"""
import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml", ".toml"}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_IMPORT = 100
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 180


class PrivateKnowledgeLibrary:
    def __init__(self, database_path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    bytes INTEGER NOT NULL,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    UNIQUE(document_id, chunk_index)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS learning_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(question, answer)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
            try:
                db.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                    USING fts5(content, content='chunks', content_rowid='id')
                """)
                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                      INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
                    END
                """)
                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                      INSERT INTO chunks_fts(chunks_fts, rowid, content)
                      VALUES ('delete', old.id, old.content);
                    END
                """)
                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                      INSERT INTO chunks_fts(chunks_fts, rowid, content)
                      VALUES ('delete', old.id, old.content);
                      INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
                    END
                """)
            except sqlite3.OperationalError:
                # Builds without FTS5 retain a safe LIKE-based search fallback.
                pass

    @staticmethod
    def _chunks(text):
        text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
        if not text:
            return []
        result = []
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_SIZE)
            if end < len(text):
                boundary = text.rfind("\n", start + CHUNK_SIZE // 2, end)
                if boundary > start:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                result.append(piece)
            if end >= len(text):
                break
            start = max(start + 1, end - CHUNK_OVERLAP)
        return result

    def import_path(self, source_path):
        source = Path(source_path).expanduser()
        if not source.exists():
            raise FileNotFoundError(str(source))
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        imported, skipped, errors = [], [], []
        processed = 0
        for path in candidates:
            if processed >= MAX_FILES_PER_IMPORT:
                skipped.append({"path": str(path), "reason": "file_limit_reached"})
                break
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            processed += 1
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    skipped.append({"path": str(path), "reason": "file_too_large"})
                    continue
                raw = path.read_bytes()
                text = raw.decode("utf-8-sig")
                chunks = self._chunks(text)
                if not chunks:
                    skipped.append({"path": str(path), "reason": "empty_or_unsupported_text"})
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                with self._connect() as db:
                    existing = db.execute("SELECT id FROM documents WHERE sha256=?", (digest,)).fetchone()
                    if existing:
                        skipped.append({"path": str(path), "reason": "duplicate"})
                        continue
                    cursor = db.execute(
                        "INSERT INTO documents(path,title,sha256,bytes) VALUES(?,?,?,?)",
                        (str(path.resolve()), path.name, digest, len(raw)),
                    )
                    document_id = cursor.lastrowid
                    db.executemany(
                        "INSERT INTO chunks(document_id,chunk_index,content) VALUES(?,?,?)",
                        [(document_id, index, chunk) for index, chunk in enumerate(chunks)],
                    )
                imported.append({"id": document_id, "title": path.name, "chunks": len(chunks)})
            except (OSError, UnicodeError, sqlite3.Error) as exc:
                errors.append({"path": str(path), "error": type(exc).__name__, "detail": str(exc)[:300]})
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def search(self, query, limit=5):
        query = str(query).strip()
        if not query:
            return []
        limit = max(1, min(20, int(limit)))
        terms = [part for part in query.split() if part]
        if not terms:
            return []
        with self._connect() as db:
            try:
                expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms[:12])
                rows = db.execute("""
                    SELECT d.id AS document_id, d.title, d.path, c.content,
                           bm25(chunks_fts) AS rank
                    FROM chunks_fts
                    JOIN chunks c ON c.id=chunks_fts.rowid
                    JOIN documents d ON d.id=c.document_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank LIMIT ?
                """, (expression, limit)).fetchall()
            except sqlite3.OperationalError:
                pattern = "%" + "%".join(terms[:6]) + "%"
                rows = db.execute("""
                    SELECT d.id AS document_id, d.title, d.path, c.content, 0 AS rank
                    FROM chunks c JOIN documents d ON d.id=c.document_id
                    WHERE c.content LIKE ? ORDER BY c.id DESC LIMIT ?
                """, (pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def list_documents(self, limit=50):
        with self._connect() as db:
            rows = db.execute("""
                SELECT d.id,d.title,d.path,d.bytes,d.imported_at,COUNT(c.id) AS chunks
                FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
                GROUP BY d.id ORDER BY d.imported_at DESC LIMIT ?
            """, (max(1, min(200, int(limit))),)).fetchall()
        return [dict(row) for row in rows]

    def add_candidate(self, question, answer, source=""):
        question, answer = str(question).strip(), str(answer).strip()
        if not question or not answer:
            raise ValueError("Pergunta e resposta são obrigatórias.")
        if len(question) > 4000 or len(answer) > 12000:
            raise ValueError("Candidato excede o limite de tamanho.")
        with self._connect() as db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO learning_candidates(question,answer,source)
                VALUES(?,?,?)
            """, (question, answer, str(source)[:1000]))
            if cursor.rowcount:
                return {"id": cursor.lastrowid, "status": "pending"}
            row = db.execute(
                "SELECT id,status FROM learning_candidates WHERE question=? AND answer=?",
                (question, answer),
            ).fetchone()
            return {"id": row["id"], "status": row["status"], "duplicate": True}

    def review_candidate(self, candidate_id, approved):
        status = "approved" if approved else "rejected"
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE learning_candidates SET status=? WHERE id=? AND status='pending'",
                (status, int(candidate_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Candidato inexistente ou já revisado.")
        return {"id": int(candidate_id), "status": status}

    def export_approved_qa(self, destination):
        """Export approved QA rows as train-only JSONL; validation remains separate."""
        import json
        target = Path(destination).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            rows = db.execute("""
                SELECT question,answer FROM learning_candidates
                WHERE status='approved' ORDER BY id
            """).fetchall()
        if not rows:
            return {"exported": 0, "path": str(target), "reason": "no_approved_candidates"}
        try:
            # Exclusive creation prevents silently replacing an existing dataset,
            # including when another process races the export.
            with target.open("x", encoding="utf-8", newline="\\n") as handle:
                for row in rows:
                    handle.write(json.dumps({
                        "type": "qa", "question": row["question"],
                        "answer": row["answer"], "split": "train"
                    }, ensure_ascii=False) + "\\n")
        except FileExistsError:
            return {"exported": 0, "path": str(target), "reason": "destination_exists"}
        return {"exported": len(rows), "path": str(target), "split": "train"}

    def stats(self):
        with self._connect() as db:
            documents = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            candidates = db.execute(
                "SELECT status,COUNT(*) AS count FROM learning_candidates GROUP BY status"
            ).fetchall()
            size = self.path.stat().st_size if self.path.exists() else 0
        return {
            "documents": documents, "chunks": chunks,
            "learning_candidates": {row["status"]: row["count"] for row in candidates},
            "database_bytes": size, "offline": True,
            "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        }
