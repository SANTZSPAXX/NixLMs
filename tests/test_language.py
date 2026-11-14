import json
import unittest
from unittest.mock import patch

from nixlms_core.language import LanguageEngine


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class OllamaDiagnosticsTests(unittest.TestCase):
    def test_discovers_installed_model_and_selects_it_without_pull(self):
        engine = LanguageEngine(model="missing:latest")
        with patch("nixlms_core.language.urlopen",
                   return_value=FakeResponse({"models": [{"name": "llama3.2:1b"}]})):
            self.assertTrue(engine.available())
        self.assertEqual(engine.model, "llama3.2:1b")
        self.assertEqual(engine.status()["installed_models"], ["llama3.2:1b"])
        self.assertIsNone(engine.last_error)

    def test_reports_service_unavailable_instead_of_silent_failure(self):
        from urllib.error import URLError
        engine = LanguageEngine()
        with patch("nixlms_core.language.urlopen", side_effect=URLError("connection refused")):
            self.assertFalse(engine.available())
        self.assertIn("connection refused", engine.status()["last_error"])
        self.assertFalse(engine.status()["reachable"])

    def test_empty_model_list_is_reported(self):
        engine = LanguageEngine()
        with patch("nixlms_core.language.urlopen", return_value=FakeResponse({"models": []})):
            self.assertFalse(engine.available())
        self.assertIn("não há modelos instalados", engine.status()["last_error"])

    def test_select_model_requires_exact_installed_name(self):
        engine = LanguageEngine()
        with patch("nixlms_core.language.urlopen",
                   return_value=FakeResponse({"models": [{"name": "qwen2.5:0.5b"}]})):
            self.assertEqual(engine.select_model("qwen2.5:0.5b"), "qwen2.5:0.5b")
            with self.assertRaises(ValueError):
                engine.select_model("unknown")

    def test_generate_sends_local_date_and_clears_error_on_success(self):
        engine = LanguageEngine()
        responses = [
            FakeResponse({"models": [{"name": "qwen2.5:0.5b"}]}),
            FakeResponse({"message": {"content": "Hoje é uma data de teste."}}),
        ]
        with patch("nixlms_core.language.urlopen", side_effect=responses) as mocked:
            answer = engine.generate("Que dia é hoje?")
        self.assertEqual(answer, "Hoje é uma data de teste.")
        self.assertIsNone(engine.last_error)
        request = mocked.call_args_list[1].args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("data_hora_local", payload["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
