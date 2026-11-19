import unittest
from unittest.mock import patch

from nixlms_core import framework_install, media_install


class MediaInstallTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "automatic_install": False,
            "blocked": False,
            "virtual_environment": True,
            "python_supported": True,
            "platform_supported": True,
            "install_allowed": True,
            "torch": {"installed": True, "version": "2.5.0"},
            "packages": [],
            "missing_direct_requirements": ["diffusers>=0.30,<1"],
        }

    def test_media_profile_uses_shared_wheel_resolver(self):
        with patch.object(
            framework_install,
            "build_install_plan",
            return_value=self.plan,
        ) as build:
            result = media_install.build_install_plan()

        self.assertIs(result, self.plan)
        self.assertEqual(build.call_args.kwargs["requirements_file"], media_install.MEDIA_REQUIREMENTS)
        self.assertEqual(framework_install.MODULE_MAP["pillow"], "PIL")

    def test_plan_mode_resolves_without_install_confirmation(self):
        with patch.object(media_install, "build_install_plan", return_value=self.plan), \
             patch.object(
                 framework_install,
                 "run_install",
                 return_value={"status": "planned", "binary_only": True, "packages": []},
             ) as run_install:
            result = media_install.main(["--plan"])

        self.assertEqual(result, 0)
        args, kwargs = run_install.call_args
        self.assertEqual(args[0], "frameworks")
        self.assertEqual(kwargs["requirements_file"], media_install.MEDIA_REQUIREMENTS)
        self.assertFalse(kwargs["confirm"])
        self.assertFalse(kwargs["require_venv"])

    def test_install_mode_requires_shared_installer_consent_and_venv(self):
        with patch.object(media_install, "build_install_plan", return_value=self.plan), \
             patch.object(
                 framework_install,
                 "run_install",
                 return_value={"status": "cancelled"},
             ) as run_install:
            result = media_install.main(["--install"])

        self.assertEqual(result, 1)
        args, kwargs = run_install.call_args
        self.assertEqual(args[0], "frameworks")
        self.assertTrue(kwargs["confirm"])
        self.assertTrue(kwargs["require_venv"])

    def test_media_profile_never_installs_torch_as_a_side_effect(self):
        plan_without_torch = dict(self.plan)
        plan_without_torch["torch"] = {"installed": False}
        with patch.object(media_install, "build_install_plan", return_value=plan_without_torch), \
             patch.object(
                 framework_install,
                 "run_install",
                 return_value={"status": "blocked", "reason": "PyTorch precisa estar presente."},
             ) as run_install:
            result = media_install.main(["--install"])

        self.assertEqual(result, 2)
        self.assertEqual(run_install.call_args.args[0], "frameworks")
        self.assertNotEqual(run_install.call_args.args[0], "torch_cpu")

    def test_plan_is_not_an_install_command(self):
        with patch.object(media_install, "build_install_plan", return_value=self.plan), \
             patch.object(
                 framework_install,
                 "run_install",
                 return_value={"status": "planned"},
             ) as run_install:
            self.assertEqual(media_install.main([]), 0)

        self.assertFalse(run_install.call_args.kwargs["confirm"])

    def test_installer_errors_fail_closed(self):
        with patch.object(media_install, "build_install_plan", side_effect=ValueError("relatório inválido")), \
             patch.object(framework_install, "run_install") as run_install:
            self.assertEqual(media_install.main(["--plan"]), 2)
        run_install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
