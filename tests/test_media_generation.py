import json
import tempfile
import unittest
from pathlib import Path

from nixlms_core.media_generation import MediaGenerationError, MediaGenerationManager


class FakeHub:
    def details(self, repo_type, repo_id):
        return {"id": repo_id, "sha": "a" * 40, "private": False,
                "gated": False, "license": "apache-2.0", "siblings": []}


class MediaGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = MediaGenerationManager(Path(self.temp.name), hub=FakeHub())

    def tearDown(self):
        self.temp.cleanup()

    def test_nsfw_is_disabled_by_default(self):
        self.assertFalse(self.manager.settings()["nsfw_enabled"])
        with self.assertRaisesRegex(MediaGenerationError, "desativado"):
            self.manager._validate_prompt("adult fictional nude portrait", nsfw=True)

    def test_nsfw_toggle_persists(self):
        self.manager.set_nsfw(True)
        self.assertTrue(self.manager.settings()["nsfw_enabled"])
        self.manager.set_nsfw(False)
        self.assertFalse(self.manager.settings()["nsfw_enabled"])

    def test_safe_mode_allows_nonsexual_child_prompt(self):
        self.assertEqual(self.manager._validate_prompt("a child reading a book"), "a child reading a book")

    def test_minor_prompt_is_rejected(self):
        self.manager.set_nsfw(True)
        with self.assertRaisesRegex(MediaGenerationError, "menores"):
            self.manager._validate_prompt("fictional adult with a child", nsfw=True)

    def test_portuguese_minor_prompt_is_rejected(self):
        self.manager.set_nsfw(True)
        with self.assertRaisesRegex(MediaGenerationError, "menores"):
            self.manager._validate_prompt("personagem fictício adolescente", nsfw=True)

    def test_portuguese_real_person_prompt_is_rejected(self):
        self.manager.set_nsfw(True)
        with self.assertRaisesRegex(MediaGenerationError, "pessoas reais"):
            self.manager._validate_prompt("pessoa real em retrato adulto", nsfw=True)

    def test_real_person_prompt_is_rejected_in_nsfw_mode(self):
        self.manager.set_nsfw(True)
        with self.assertRaisesRegex(MediaGenerationError, "pessoas reais"):
            self.manager._validate_prompt("real person nude portrait", nsfw=True)

    def test_download_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(MediaGenerationError, "confirmação explícita"):
            self.manager.download_model("owner/model", "text-to-image")

    def test_download_rejects_unknown_mode(self):
        with self.assertRaisesRegex(MediaGenerationError, "Modo inválido"):
            self.manager.download_model("owner/model", "audio", confirm=True)

    def test_input_path_cannot_escape_input_directory(self):
        outside = Path(self.temp.name) / "outside.png"
        outside.write_bytes(b"not really an image")
        with self.assertRaisesRegex(MediaGenerationError, "dentro de data/media/input"):
            self.manager._safe_input(outside)

    def test_relative_input_path_is_confined(self):
        image = self.manager.input_dir / "source.png"
        image.write_bytes(b"x")
        self.assertEqual(self.manager._safe_input("source.png"), image.resolve())

    def test_bootstrap_can_be_disabled(self):
        self.assertEqual(self.manager.bootstrap_async(enabled=False),
                         {"started": False, "reason": "disabled"})

    def test_registry_and_settings_are_local_json(self):
        self.manager.set_nsfw(True)
        self.assertTrue(self.manager.settings_path.is_file())
        self.assertEqual(json.loads(self.manager.settings_path.read_text())["nsfw_enabled"], True)


if __name__ == "__main__":
    unittest.main()
