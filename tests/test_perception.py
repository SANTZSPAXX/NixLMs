import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core.perception import PerceptionManager
from nixlms_core import NixLMsNeuralCore


class PerceptionManagerTests(unittest.TestCase):

    def test_neural_core_exposes_perception_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            status = ai.status()
            self.assertTrue(status["perception"]["enabled"])
            self.assertFalse(status["perception"]["automatic_downloads"])

    def test_status_is_cpu_only_and_never_downloads(self):
        manager = PerceptionManager(vision_model_path=None, speech_model_path=None)
        status = manager.status()
        self.assertEqual(status["device"], "cpu")
        self.assertFalse(status["automatic_downloads"])
        self.assertFalse(status["vision"]["configured"])
        self.assertFalse(status["speech"]["configured"])

    def test_rejects_missing_and_unsupported_image_files(self):
        manager = PerceptionManager(vision_model_path=None)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                manager.describe_image(Path(tmp) / "missing.png")
            unsupported = Path(tmp) / "image.gif"
            unsupported.write_bytes(b"GIF89a")
            with self.assertRaises(ValueError):
                manager.describe_image(unsupported)

    def test_rejects_oversized_or_empty_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.wav"
            empty.write_bytes(b"")
            manager = PerceptionManager(speech_model_path=None)
            with self.assertRaises(ValueError):
                manager.transcribe_audio(empty)
            large = Path(tmp) / "large.wav"
            large.write_bytes(b"0" * 16)
            manager = PerceptionManager(speech_model_path=None, max_audio_bytes=8)
            with self.assertRaises(ValueError):
                manager.transcribe_audio(large)

    def test_local_model_is_required_before_loading_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "image.png"
            image.write_bytes(b"not-a-real-image")
            manager = PerceptionManager(vision_model_path=None)
            with patch.object(manager, "_transformers_available", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "diretório de modelo local"):
                    manager.describe_image(image)

    def test_audio_requires_wav_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "voice.mp3"
            audio.write_bytes(b"audio")
            manager = PerceptionManager(speech_model_path=None)
            with self.assertRaises(ValueError):
                manager.transcribe_audio(audio)


if __name__ == "__main__":
    unittest.main()
