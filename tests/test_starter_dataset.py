import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore


class StarterDatasetTests(unittest.TestCase):
    def test_clean_install_gets_curated_train_and_validation_samples(self):
        with tempfile.TemporaryDirectory(prefix="nixlms-starter-test-") as temp:
            core = NixLMsNeuralCore(data_dir=Path(temp) / "data")
            audit = core.learning.dataset.audit_splits()
            self.assertTrue(audit["valid"], audit["violations"])
            self.assertTrue(core.starter_dataset_seeded)
            self.assertGreater(audit["counts"]["qa_train"], 0)
            self.assertGreaterEqual(audit["counts"]["qa_validation"], 4)
            self.assertGreater(audit["counts"]["qa_test"], 0)
            core.scheduler.stop()

    def test_existing_user_dataset_is_not_overwritten_or_seeded(self):
        with tempfile.TemporaryDirectory(prefix="nixlms-existing-test-") as temp:
            data_dir = Path(temp) / "data"
            data_dir.mkdir()
            dataset = data_dir / "dataset.json"
            dataset.write_text(
                '[{"type":"qa","question":"pergunta privada","answer":"resposta privada","split":"train"}]',
                encoding="utf-8",
            )
            core = NixLMsNeuralCore(data_dir=data_dir)
            rows = core.learning.dataset.load()
            self.assertFalse(core.starter_dataset_seeded)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["question"], "pergunta privada")
            core.scheduler.stop()


if __name__ == "__main__":
    unittest.main()
