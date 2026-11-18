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

    def test_gguf_uses_llama_cpp_on_cpu_without_torch_or_network(self):
        import sys
        import types

        with tempfile.TemporaryDirectory(prefix="nixlms-hf-gguf-") as temp:
            root = Path(temp)
            (root / "model.gguf").write_bytes(b"gguf")
            calls = {}

            class FakeLlama:
                def __init__(self, **kwargs):
                    calls.update(kwargs)

                def create_completion(self, **kwargs):
                    return {"choices": [{"text": "Resposta GGUF local."}]}

            module = types.ModuleType("llama_cpp")
            module.Llama = FakeLlama
            generator = HuggingFaceLocalGenerator(root, "org/model", threads=2)
            with patch.dict(sys.modules, {"llama_cpp": module}):
                answer = generator.generate("Seja útil.", "Explique a NixLMs.")
            self.assertEqual(answer, "Resposta GGUF local.")
            self.assertEqual(generator.status()["backend"], "llama.cpp_cpu")
            self.assertEqual(calls["n_threads"], 2)
            self.assertEqual(calls["model_path"], str(root / "model.gguf"))

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
