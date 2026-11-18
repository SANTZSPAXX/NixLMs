import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core.huggingface import HuggingFaceError, HuggingFaceHub


class FakeResponse:
    def __init__(self, payload):
        self.raw = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.raw.close()

    def read(self, size=-1):
        return self.raw.read(size)


class HuggingFaceHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nixlms-hf-test-")
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        self.payload = {
            "id": "Qwen/Qwen2.5-0.5B-Instruct",
            "sha": "a" * 40,
            "private": False,
            "gated": False,
            "downloads": 100,
            "likes": 5,
            "pipeline_tag": "text-generation",
            "tags": ["license:apache-2.0", "safetensors"],
            "cardData": {"license": "apache-2.0"},
            "siblings": [
                {"rfilename": "config.json", "size": 100},
                {"rfilename": "model.safetensors", "size": 900},
                {"rfilename": "tokenizer.json", "size": 200},
                {"rfilename": "modeling_custom.py", "size": 50},
                {"rfilename": "pytorch_model.bin", "size": 800},
            ],
        }

        def opener(request, timeout=0):
            self.calls.append((request, timeout))
            return FakeResponse([self.payload] if "/api/models?" in request.full_url else self.payload)

        self.opener = opener
        self.hub = HuggingFaceHub(Path(self.temp.name) / "data", opener=opener)

    def test_public_search_is_anonymous_and_sanitized(self):
        results = self.hub.search("model", "qwen", limit=5)
        self.assertEqual(results[0]["id"], self.payload["id"])
        request, _ = self.calls[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.get_header("User-agent"), "NixLMs-HuggingFace/1.0")

    def test_invalid_repository_id_is_rejected(self):
        with self.assertRaises(HuggingFaceError):
            self.hub.details("model", "../private/model")

    def test_gated_and_private_repositories_are_rejected(self):
        self.payload["gated"] = "auto"
        with self.assertRaises(HuggingFaceError):
            self.hub.download("model", self.payload["id"])
        self.payload["gated"] = False
        self.payload["private"] = True
        with self.assertRaises(HuggingFaceError):
            self.hub.download("model", self.payload["id"])

    def test_download_is_size_limited_pinned_and_allowlisted(self):
        captured = {}

        def downloader(repo_id, **kwargs):
            captured.update({"repo_id": repo_id, **kwargs})
            root = Path(kwargs["local_dir"])
            (root / "config.json").write_text("{}", encoding="utf-8")
            (root / "model.safetensors").write_bytes(b"weights")
            (root / "tokenizer.json").write_text("{}", encoding="utf-8")
            return str(root)

        hub = HuggingFaceHub(
            Path(self.temp.name) / "data", opener=self.opener,
            downloader=downloader,
        )
        result = hub.download("model", self.payload["id"], max_bytes=2000)
        self.assertEqual(result["revision"], "a" * 40)
        self.assertEqual(captured["token"], False)
        self.assertEqual(captured["revision"], "a" * 40)
        self.assertIn("model.safetensors", captured["allow_patterns"])
        self.assertNotIn("modeling_custom.py", captured["allow_patterns"])
        self.assertNotIn("pytorch_model.bin", captured["allow_patterns"])
        self.assertTrue(Path(result["path"], "model.safetensors").is_file())

    def test_download_over_limit_is_rejected_before_downloader(self):
        downloader = unittest.mock.Mock()
        hub = HuggingFaceHub(
            Path(self.temp.name) / "data", opener=self.opener,
            downloader=downloader,
        )
        with self.assertRaises(HuggingFaceError):
            hub.download("model", self.payload["id"], max_bytes=100)
        downloader.assert_not_called()

    def test_active_model_requires_local_safetensors_and_config(self):
        root = Path(self.temp.name) / "data"
        hub = HuggingFaceHub(root, opener=self.opener, downloader=lambda *a, **k: None)
        model_path = hub.models_dir / "Qwen" / "Qwen2.5-0.5B-Instruct"
        model_path.mkdir(parents=True)
        (model_path / "config.json").write_text("{}", encoding="utf-8")
        (model_path / "model.safetensors").write_bytes(b"weights")
        hub._save_registry([{
            "repo_id": self.payload["id"], "repo_type": "model",
            "path": str(model_path), "revision": "a" * 40, "pipeline_tag": "text-generation",
        }])
        active = hub.activate_model(self.payload["id"])
        self.assertEqual(active["repo_id"], self.payload["id"])
        self.assertEqual(hub.active_model()["path"], str(model_path))

    def test_embedding_activation_requires_semantic_task_and_local_weights(self):
        root = Path(self.temp.name) / "data"
        hub = HuggingFaceHub(root, opener=self.opener, downloader=lambda *a, **k: None)
        model_path = hub.models_dir / "intfloat" / "multilingual-e5-small"
        model_path.mkdir(parents=True)
        (model_path / "config.json").write_text("{}", encoding="utf-8")
        (model_path / "model.safetensors").write_bytes(b"weights")
        hub._save_registry([{
            "repo_id": "intfloat/multilingual-e5-small", "repo_type": "model",
            "path": str(model_path), "revision": "a" * 40,
            "pipeline_tag": "sentence-similarity",
        }])
        active = hub.activate_encoder("intfloat/multilingual-e5-small")
        self.assertEqual(active["repo_id"], "intfloat/multilingual-e5-small")
        self.assertEqual(hub.active_encoder()["path"], str(model_path))
        with self.assertRaises(HuggingFaceError):
            hub.activate_model("intfloat/multilingual-e5-small")

    def test_vision_and_speech_activation_require_matching_pipeline(self):
        root = Path(self.temp.name) / "data"
        hub = HuggingFaceHub(root, opener=self.opener, downloader=lambda *a, **k: None)
        vision_path = hub.models_dir / "org" / "vision-model"
        vision_path.mkdir(parents=True)
        (vision_path / "config.json").write_text("{}", encoding="utf-8")
        (vision_path / "model.safetensors").write_bytes(b"weights")
        hub._save_registry([{
            "repo_id": "org/vision-model", "repo_type": "model",
            "path": str(vision_path), "revision": "a" * 40,
            "pipeline_tag": "image-to-text",
        }])
        active = hub.activate_perception("org/vision-model", "vision")
        self.assertEqual(active["task"], "image-to-text")
        self.assertEqual(hub.active_perception()["vision"]["repo_id"], "org/vision-model")
        self.assertTrue(hub.deactivate_perception("vision"))
        self.assertEqual(hub.active_perception(), {})
        with self.assertRaises(HuggingFaceError):
            hub.activate_perception("org/vision-model", "speech")

    def test_status_does_not_require_optional_huggingface_packages(self):
        with patch("nixlms_core.huggingface.importlib.util.find_spec", return_value=None):
            status = self.hub.status()
        self.assertFalse(status["download_support"])
        self.assertFalse(status["inference_support"])
        self.assertTrue(status["anonymous_public_access"])
        self.assertFalse(status["token_required"])


if __name__ == "__main__":
    unittest.main()
