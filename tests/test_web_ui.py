import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class WebInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_data = tempfile.TemporaryDirectory(prefix="nixlms-web-test-")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            cls.port = probe.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env["NIXLMS_DATA_DIR"] = cls.temp_data.name
        env["NIXLMS_PORT"] = str(cls.port)
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "nixlms_web.server"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        for _ in range(60):
            if cls.process.poll() is not None:
                raise RuntimeError("Servidor encerrou durante a inicialização.")
            try:
                urllib.request.urlopen(cls.base + "/api/status", timeout=1)
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            cls.process.terminate()
            raise RuntimeError("Servidor não abriu a porta de teste.")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)
        cls.temp_data.cleanup()

    def get_json(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            import json
            return json.loads(response.read().decode("utf-8"))

    def test_homepage_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("NixLMs", body)

    def test_status_endpoint_connected_to_neural_core(self):
        data = self.get_json("/api/status")
        self.assertEqual(data["engine"], "NixLMsNeuralCore")
        self.assertIn("knowledge", data)
        self.assertIn("library", data)
        self.assertIn("documents", data["library"])
        self.assertIn("core", data)
        self.assertIn("world_model", data["core"])
        self.assertIn("autonomy", data["core"])
        self.assertTrue(data["core"]["simulation"]["enabled"])
        self.assertFalse(data["core"]["perception"]["automatic_downloads"])
        self.assertIn("runtime", data)

    def test_framework_inventory_does_not_require_registry_module(self):
        data = self.get_json("/api/frameworks")
        self.assertTrue(isinstance(data, list))
        self.assertTrue(any(item["name"] == "PyTorch" for item in data))

    def test_huggingface_status_is_anonymous_and_never_paid(self):
        data = self.get_json("/api/huggingface/status")
        self.assertTrue(data["anonymous_public_access"])
        self.assertFalse(data["token_required"])
        self.assertFalse(data["paid_remote_inference"])
        self.assertIn("download_support", data)
        self.assertIn("inference_support", data)

    def test_chat_endpoint_uses_neural_core(self):
        import json
        request = urllib.request.Request(
            self.base + "/api/chat",
            data=json.dumps({"message": "oi"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertIn("reply", data)
        self.assertTrue(data["reply"])
        self.assertEqual(data["engine"], "NixLMsNeuralCore")
        self.assertEqual(data["response_source"], "greeting_rule")

    def test_diagnostics_include_real_core_checks(self):
        data = self.get_json("/api/diagnostics")
        self.assertIn("checks", data)
        self.assertIn("module_memory", data["checks"])
        self.assertIn("dataset_integrity", data["checks"])
        self.assertIn("scheduler_running", data)
        self.assertIn("idle_learning", data)
        self.assertIn("scheduler_running", data["checks"])
        self.assertIn("idle_learning_dataset", data["checks"])
        self.assertEqual(data["checks"]["scheduler_running"]["status"], "ok")
        self.assertIn(data["status"], {"ok", "degraded", "failed"})
        self.assertEqual(data["ok"], data["status"] == "ok")

    def test_static_assets_exist_and_css_is_valid_prefix(self):
        base = ROOT / "nixlms_web" / "static"
        for name in ("index.html", "style.css", "app.js"):
            self.assertTrue((base / name).is_file())
        html = (base / "index.html").read_text(encoding="utf-8")
        js = (base / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-view="huggingface"', html)
        self.assertIn("/api/huggingface/search", js)
        self.assertIn("/api/huggingface/download", js)
        css = (base / "style.css").read_text(encoding="utf-8")
        self.assertTrue(css.startswith(":root"))

    def test_voice_console_and_hands_free_controls_are_present(self):
        base = ROOT / "nixlms_web" / "static"
        html = (base / "index.html").read_text(encoding="utf-8")
        js = (base / "app.js").read_text(encoding="utf-8")
        css = (base / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="voice-toggle"', html)
        self.assertIn('id="voice-state"', html)
        self.assertIn("webkitSpeechRecognition", js)
        self.assertIn('recognition.lang="pt-BR"', js)
        self.assertIn("SpeechSynthesisUtterance", js)
        self.assertIn("pendingVoiceAction", js)
        self.assertIn("voice-orb.listening", css)

    def test_server_is_loopback_only_and_has_no_shell_endpoint(self):
        source = (ROOT / "nixlms_web" / "server.py").read_text(encoding="utf-8")
        self.assertIn('host, port = "127.0.0.1", int(os.getenv("NIXLMS_PORT", "8765"))', source)
        self.assertNotIn('host,port="0.0.0.0"', source)
        self.assertNotIn("subprocess", source)

if __name__ == "__main__":
    unittest.main()
