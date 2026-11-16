import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nixlms_core.ollama_manager import OllamaManager


class FakeLanguage:
    def __init__(self, reachable=True, models=None, local_host=True):
        self.host = "http://127.0.0.1:11434"
        self.local_host = local_host
        self.reachable = reachable
        self.model = "qwen2.5:0.5b"
        self.installed_models = list(models or [])
        self.last_error = None
        self.last_used_model = None
        self.last_generation = None

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
        self.assertEqual(result["bind_scope"], "unverified_preexisting")
        executable.assert_not_called()
        popen.assert_not_called()

    def test_managed_service_overrides_inherited_wildcard_bind(self):
        language = FakeLanguage(reachable=False)
        manager = OllamaManager(language)
        process = Mock()
        process.poll.return_value = None

        def spawn(*args, **kwargs):
            language.reachable = True
            return process

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OLLAMA_HOST": "0.0.0.0:11434"}):
                with patch.object(Path, "home", return_value=Path(tmp)):
                    with patch.object(manager, "executable", return_value="/usr/bin/ollama"):
                        with patch(
                            "nixlms_core.ollama_manager.subprocess.Popen",
                            side_effect=spawn,
                        ) as popen:
                            result = manager.start_service()
                            child_env = popen.call_args.kwargs["env"]
                            self.assertEqual(os.environ["OLLAMA_HOST"], "0.0.0.0:11434")

        self.assertTrue(result["ok"])
        self.assertEqual(child_env["OLLAMA_HOST"], "127.0.0.1:11434")
        self.assertEqual(result["bind_scope"], "configured_loopback")
        self.assertEqual(result["bind_address"], "127.0.0.1:11434")

    def test_loopback_bind_preserves_port_and_formats_ipv6(self):
        language = FakeLanguage()
        manager = OllamaManager(language)

        language.host = "http://localhost:12345"
        self.assertEqual(manager._loopback_bind_address(), "127.0.0.1:12345")

        language.host = "http://[::1]:12346"
        self.assertEqual(manager._loopback_bind_address(), "[::1]:12346")

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
