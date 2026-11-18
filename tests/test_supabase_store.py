import hashlib
import tempfile
import unittest
from pathlib import Path

from nixlms_core.supabase_store import SupabaseStore


class SupabaseStoreTests(unittest.TestCase):
    def test_env_is_optional(self):
        import os
        old = os.environ.pop("NIXLMS_DATABASE_URL", None)
        try:
            self.assertIsNone(SupabaseStore.from_env(Path(tempfile.mkdtemp())))
        finally:
            if old is not None:
                os.environ["NIXLMS_DATABASE_URL"] = old

    def test_safe_relative_rejects_traversal(self):
        with self.assertRaises(ValueError):
            SupabaseStore._safe_relative("../secrets.txt")
        with self.assertRaises(ValueError):
            SupabaseStore._safe_relative("/etc/passwd")

    def test_sqlite_backup_reads_consistent_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            import sqlite3
            with sqlite3.connect(path) as db:
                db.execute("create table t (v text)")
                db.execute("insert into t values ('persisted')")
            content = SupabaseStore._read_consistent(path)
            fd_path = Path(tmp) / "restored.sqlite3"
            fd_path.write_bytes(content)
            with sqlite3.connect(fd_path) as db:
                self.assertEqual(db.execute("select v from t").fetchone()[0], "persisted")


if __name__ == "__main__":
    unittest.main()
