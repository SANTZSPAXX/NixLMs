import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore


class PrivateLibraryOfflineResponseTests(unittest.TestCase):
    def test_private_document_can_answer_without_language_model(self):
        with tempfile.TemporaryDirectory(prefix="nixlms-library-test-") as temp:
            root = Path(temp)
            data_dir = root / "data"
            document = root / "offline-proof.txt"
            document.write_text(
                "Zorbitalum 731 identifica o protocolo de catalogacao "
                "astronomica usado neste documento privado.",
                encoding="utf-8",
            )
            core = NixLMsNeuralCore(data_dir=data_dir)
            imported = core.private_library.import_path(document)
            self.assertEqual(len(imported["imported"]), 1)

            answer = core.respond(
                "O que significa Zorbitalum 731?",
                use_language=False,
                record=False,
            )

            self.assertIn("biblioteca privada", answer)
            self.assertIn("Zorbitalum 731", answer)
            self.assertEqual(
                core.last_trace["response_source"], "private_offline_library"
            )
            core.scheduler.stop()


if __name__ == "__main__":
    unittest.main()
