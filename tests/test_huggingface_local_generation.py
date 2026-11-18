import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nixlms_core.huggingface import HuggingFaceLocalGenerator
from nixlms_core.language import LanguageEngine


class HuggingFaceLocalGenerationTests(unittest.TestCase):
    def test_generator_load_is_cpu_local_and_disables_remote_code(self):
        with tempfile.TemporaryDirectory(prefix="nixlms-hf-model-") as temp:
            root = Path(temp)
            (root / "config.json").write_text("{}", encoding="utf-8")
            (root / "model.safetensors").write_bytes(b"weights")
            loaded = {}

            def loader(**kwargs):
                loaded.update(kwargs)
                return object(), object()

            generator = HuggingFaceLocalGenerator(
                root, "org/model", model_loader=loader, threads=2
            )
            generator._load()
            self.assertEqual(loaded["device"], "cpu")
            self.assertTrue(loaded["local_files_only"])
            self.assertFalse(loaded["trust_remote_code"])
            self.assertTrue(loaded["use_safetensors"])
            self.assertEqual(loaded["threads"], 2)

    def test_generator_rejects_missing_or_pickle_only_weights(self):
        with tempfile.TemporaryDirectory(prefix="nixlms-hf-model-") as temp:
            root = Path(temp)
            (root / "config.json").write_text("{}", encoding="utf-8")
            (root / "pytorch_model.bin").write_bytes(b"unsafe")
            generator = HuggingFaceLocalGenerator(root)
            with self.assertRaises(Exception):
                generator._load()

    def test_language_engine_can_use_hf_local_when_ollama_is_disabled(self):
        engine = LanguageEngine()
        engine.enabled = False
        generator = Mock()
        generator.generate.return_value = "Resposta local de teste."
        generator.status.return_value = {"provider": "huggingface_local"}
        engine.hf_local_generator = generator

        answer = engine.generate("Explique a NixLMs.")

        self.assertEqual(answer, "Resposta local de teste.")
        self.assertEqual(engine.last_used_provider, "huggingface_local")
        generator.generate.assert_called_once()

    def test_language_engine_reports_local_provider_without_token(self):
        engine = LanguageEngine()
        engine.hf_local_generator = Mock()
        engine.hf_local_generator.status.return_value = {
            "provider": "huggingface_local", "loaded": False
        }
        status = engine.status()
        self.assertIn("huggingface_local", status)
        self.assertNotIn("token", status["huggingface_local"])


if __name__ == "__main__":
    unittest.main()
