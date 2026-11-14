import unittest
from unittest.mock import patch

from nixlms_core.ollama_manager import OllamaManager


class FakeLanguage:
    def __init__(self, reachable=True, models=None, local_host=True):
        self.host = "http://127.0.0.1:11434"
        self.local_host = local_host
        self.reachable = reachable
        self.model = "qwen2.5:0.5b"
        self.installed_models = list(models or [])
        self.last_error = None

    def refresh_models(self):
        return list(self.installed_models)


class OllamaManagerTests(unittest.TestCase):
    def test_status_reports_binary_and_exact_model(self):
        language = FakeLanguage(models=["qwen2.5:0.5b"])
        manager = OllamaManager(language)
        with patch.object(manager, "executable", return_value="/usr/bin/ollama"):
            status = manager.status()
        self.assertTrue(status["installed"])
        self.assertTrue(status["model_installed"])
        self.assertEqual(status["executable"], "/usr/bin/ollama")

    def test_start_does_not_spawn_duplicate_service(self):
        language = FakeLanguage(reachable=True)
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.Popen") as popen:
            result = manager.start_service()
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        executable.assert_not_called()
        popen.assert_not_called()

    def test_start_refuses_non_loopback_endpoint(self):
        language = FakeLanguage(reachable=False, local_host=False)
        manager = OllamaManager(language)
        result = manager.start_service()
        self.assertFalse(result["ok"])
        self.assertIn("loopback", result["error"])

    def test_pull_does_not_download_model_already_installed(self):
        language = FakeLanguage(models=["qwen2.5:0.5b"])
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.run") as run:
            result = manager.pull_model()
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_installed"])
        executable.assert_not_called()
        run.assert_not_called()

    def test_pull_requires_reachable_local_service(self):
        language = FakeLanguage(reachable=False)
        language.last_error = "connection refused"
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.run") as run:
            result = manager.pull_model()
        self.assertFalse(result["ok"])
        self.assertIn("não está acessível", result["error"])
        executable.assert_not_called()
        run.assert_not_called()

    def test_pull_rejects_invalid_model_name(self):
        language = FakeLanguage()
        manager = OllamaManager(language)
        result = manager.pull_model("nome de modelo")
        self.assertFalse(result["ok"])
        self.assertIn("inválido", result["error"])


if __name__ == "__main__":
    unittest.main()
