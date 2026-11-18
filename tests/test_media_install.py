import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from nixlms_core import media_install


class MediaInstallTests(unittest.TestCase):
    def test_nested_requirements_plan_is_read_only_and_skips_present_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "requirements-hf-media.txt").write_text(
                "-r requirements-hf-image.txt\nimageio>=2.34\n",
                encoding="utf-8",
            )
            (root / "requirements-hf-image.txt").write_text(
                "-r requirements-hf-local.txt\ndiffusers>=0.30,<1\nPillow>=10\n",
                encoding="utf-8",
            )
            (root / "requirements-hf-local.txt").write_text(
                "transformers>=4.45,<6\nsafetensors>=0.4\n",
                encoding="utf-8",
            )
            installed_modules = {"torch", "PIL", "transformers"}
            plan = media_install.build_install_plan(
                root / "requirements-hf-media.txt",
                root=root,
                module_probe=lambda module: module in installed_modules,
                version_probe=lambda distribution: "1.0" if distribution else None,
                system_name="Linux",
                machine="x86_64",
            )
        self.assertFalse(plan["blocked"])
        self.assertTrue(plan["torch"]["installed"])
        self.assertEqual(
            plan["missing_requirements"],
            ["safetensors>=0.4", "diffusers>=0.30,<1", "imageio>=2.34"],
        )

    def test_linux_arm64_without_torch_is_blocked_for_manual_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements.txt"
            requirements.write_text("diffusers>=0.30\n", encoding="utf-8")
            plan = media_install.build_install_plan(
                requirements, root=root, module_probe=lambda module: False,
                version_probe=lambda distribution: None,
                system_name="Linux", machine="aarch64",
            )
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["torch"]["action"], "manual_platform_selection")

    def test_plan_mode_never_runs_pip(self):
        with patch.object(media_install, "build_install_plan", return_value={
            "automatic_install": False, "blocked": False,
            "torch": {"installed": True}, "missing_requirements": [],
        }), patch.object(media_install.subprocess, "run") as run:
            self.assertEqual(media_install.main(["--plan"]), 0)
        run.assert_not_called()

    def test_install_requires_virtual_environment(self):
        with patch.object(media_install, "is_virtual_environment", return_value=False), \
             patch.object(media_install.subprocess, "run") as run:
            self.assertEqual(media_install.main(["--install"]), 2)
        run.assert_not_called()

    def test_install_requires_exact_confirmation(self):
        plan = {
            "automatic_install": False, "blocked": False,
            "torch": {"installed": True}, "missing_requirements": ["diffusers>=0.30"],
        }
        with patch.object(media_install, "is_virtual_environment", return_value=True), \
             patch.object(media_install, "build_install_plan", return_value=plan), \
             patch("builtins.input", return_value="sim"), \
             patch.object(media_install.subprocess, "run") as run:
            self.assertEqual(media_install.main(["--install"]), 1)
        run.assert_not_called()

    def test_install_runs_only_after_confirmation_and_reports_changes(self):
        plan = {
            "automatic_install": False, "blocked": False,
            "torch": {"installed": False}, "missing_requirements": ["diffusers>=0.30"],
        }
        with patch.object(media_install, "is_virtual_environment", return_value=True), \
             patch.object(media_install, "build_install_plan", return_value=plan), \
             patch("builtins.input", return_value="INSTALAR"), \
             patch.object(media_install, "_pip_freeze", side_effect=[
                 {"existing": "1.0"},
                 {"existing": "1.0", "torch": "2.0", "diffusers": "0.30"},
             ]), \
             patch.object(media_install.subprocess, "run", return_value=CompletedProcess([], 0)) as run:
            self.assertEqual(media_install.main(["--install"]), 0)
        self.assertEqual(run.call_count, 2)
        torch_call = run.call_args_list[0].args[0]
        self.assertIn("torch", torch_call)
        self.assertIn("--index-url", torch_call)
        self.assertIn("--no-upgrade", torch_call)
        requirements_call = run.call_args_list[1].args[0]
        self.assertIn("diffusers>=0.30", requirements_call)
        self.assertIn("--no-upgrade", requirements_call)


    def test_python_below_3_10_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements.txt"
            requirements.write_text("diffusers>=0.30\n", encoding="utf-8")
            plan = media_install.build_install_plan(
                requirements, root=root, module_probe=lambda module: True,
                version_probe=lambda distribution: "1.0",
                system_name="Windows", machine="AMD64", python_version=(3, 9),
            )
        self.assertTrue(plan["blocked"])
        self.assertFalse(plan["python_supported"])
        self.assertIn("Python 3.10", plan["blocked_reason"])


    def test_blocked_plan_never_prompts_or_runs_pip(self):
        plan = {
            "automatic_install": False, "blocked": True,
            "blocked_reason": "Este perfil exige Python 3.10 ou superior.",
            "torch": {"installed": False}, "missing_requirements": ["diffusers>=0.30"],
        }
        with patch.object(media_install, "is_virtual_environment", return_value=True), \
             patch.object(media_install, "build_install_plan", return_value=plan), \
             patch("builtins.input") as prompt, \
             patch.object(media_install.subprocess, "run") as run:
            self.assertEqual(media_install.main(["--install"]), 2)
        prompt.assert_not_called()
        run.assert_not_called()


    def test_python_3_11_is_supported_for_cpu_x64_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements.txt"
            requirements.write_text("diffusers>=0.30\n", encoding="utf-8")
            plan = media_install.build_install_plan(
                requirements, root=root, module_probe=lambda module: True,
                version_probe=lambda distribution: "1.0",
                system_name="Windows", machine="AMD64", python_version=(3, 11),
            )
        self.assertFalse(plan["blocked"])
        self.assertTrue(plan["python_supported"])



if __name__ == "__main__":
    unittest.main()
