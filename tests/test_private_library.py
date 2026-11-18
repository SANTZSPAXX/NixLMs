import tempfile
import unittest
from pathlib import Path

from nixlms_core.private_library import PrivateKnowledgeLibrary


class PrivateKnowledgeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.library = PrivateKnowledgeLibrary(self.root / "library.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_imports_local_markdown_and_searches_offline(self):
        source = self.root / "notes.md"
        source.write_text("# SQLite\nSQLite stores structured data locally without a server.", encoding="utf-8")
        result = self.library.import_path(source)
        self.assertEqual(len(result["imported"]), 1)
        found = self.library.search("SQLite structured data")
        self.assertTrue(found)
        self.assertIn("locally", found[0]["content"])
        self.assertEqual(self.library.stats()["documents"], 1)

    def test_duplicate_content_is_not_imported_twice(self):
        source = self.root / "notes.txt"
        source.write_text("same content", encoding="utf-8")
        self.library.import_path(source)
        result = self.library.import_path(source)
        self.assertEqual(result["imported"], [])
        self.assertEqual(result["skipped"][0]["reason"], "duplicate")

    def test_rejects_missing_source_and_ignores_unsupported_files(self):
        with self.assertRaises(FileNotFoundError):
            self.library.import_path(self.root / "missing.md")
        binary = self.root / "image.png"
        binary.write_bytes(b"not text")
        result = self.library.import_path(binary)
        self.assertEqual(result["imported"], [])

    def test_learning_candidates_require_explicit_approval(self):
        candidate = self.library.add_candidate("O que é SQLite?", "Um banco de dados embutido.", "notes.md")
        self.assertEqual(candidate["status"], "pending")
        empty_export = self.library.export_approved_qa(self.root / "train.jsonl")
        self.assertEqual(empty_export["reason"], "no_approved_candidates")
        self.library.review_candidate(candidate["id"], True)
        exported = self.library.export_approved_qa(self.root / "train.jsonl")
        self.assertEqual(exported["exported"], 1)
        self.assertIn('"split": "train"', (self.root / "train.jsonl").read_text(encoding="utf-8"))

    def test_export_refuses_to_overwrite_existing_dataset(self):
        candidate = self.library.add_candidate("Q", "A")
        self.library.review_candidate(candidate["id"], True)
        destination = self.root / "existing-train.jsonl"
        destination.write_text("keep existing data\n", encoding="utf-8")

        result = self.library.export_approved_qa(destination)

        self.assertEqual(result["reason"], "destination_exists")
        self.assertEqual(result["exported"], 0)
        self.assertEqual(destination.read_text(encoding="utf-8"), "keep existing data\n")

    def test_rejected_candidate_cannot_be_approved_again(self):
        candidate = self.library.add_candidate("Q", "A")
        self.library.review_candidate(candidate["id"], False)
        with self.assertRaises(ValueError):
            self.library.review_candidate(candidate["id"], True)

    def test_file_size_limit_is_enforced(self):
        source = self.root / "large.txt"
        source.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        result = self.library.import_path(source)
        self.assertEqual(result["skipped"][0]["reason"], "file_too_large")


if __name__ == "__main__":
    unittest.main()
