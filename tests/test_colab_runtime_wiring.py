import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ColabRuntimeWiringTests(unittest.TestCase):

    def test_notebook_stops_previous_runtime_before_module_reload(self):
        notebook = json.loads((ROOT / "NixLMs_Colab.ipynb").read_text(encoding="utf-8"))
        bootstrap = "".join(notebook["cells"][1]["source"])
        self.assertIn("previous_ia.scheduler.stop()", bootstrap)
        self.assertLess(bootstrap.index("previous_ia.scheduler.stop()"),
                        bootstrap.index("globals().pop('ia', None)"))

    def test_notebook_starts_runtime_after_core_initialization(self):
        notebook = json.loads((ROOT / "NixLMs_Colab.ipynb").read_text(encoding="utf-8"))
        setup = "".join(notebook["cells"][3]["source"])
        self.assertIn("ia = NixLMsNeuralCore(data_dir=DATA_DIR)", setup)
        self.assertIn("RUNTIME = ia.start_runtime()", setup)
        self.assertLess(setup.index("NixLMsNeuralCore"), setup.index("ia.start_runtime()"))
        compile(setup, "<colab-runtime-setup>", "exec")

    def test_notebook_exposes_anonymous_huggingface_commands(self):
        notebook = json.loads((ROOT / "NixLMs_Colab.ipynb").read_text(encoding="utf-8"))
        session = "".join(notebook["cells"][7]["source"])
        self.assertIn("elif low == '/hf' or low.startswith('/hf '):", session)
        self.assertIn("ia.huggingface.search", session)
        self.assertIn("ia.huggingface.download", session)
        compile(session, "<colab-huggingface-session>", "exec")

    def test_notebook_stops_scheduler_after_chat_session(self):
        notebook = json.loads((ROOT / "NixLMs_Colab.ipynb").read_text(encoding="utf-8"))
        session = "".join(notebook["cells"][7]["source"])
        self.assertIn("nix_chat()", session)
        self.assertIn("ia.scheduler.stop()", session)
        self.assertLess(session.index("nix_chat()"), session.index("ia.scheduler.stop()"))
        compile(session, "<colab-chat-session>", "exec")


if __name__ == "__main__":
    unittest.main()
