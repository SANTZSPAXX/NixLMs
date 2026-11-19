import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nixlms_core import framework_install as installer


class FrameworkInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.requirements = self.root / "requirements-ml-cpu.txt"
        self.requirements.write_text(
            "numpy>=1.0\nscikit-learn>=1.0\nsentence-transformers>=3.0\n",
            encoding="utf-8",
        )
        self.size_patch = patch.object(installer, "_wheel_size", return_value=None)
        self.size_patch.start()

    def tearDown(self):
        self.size_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def report_item(name, version, requested=True, url=None, digest=None):
        digest = digest or ("a" * 64)
        url = url or (
            "https://files.pythonhosted.org/packages/test/"
            + name.lower().replace("_", "-") + "-" + version + "-py3-none-any.whl"
        )
        hashes = {"sha256": digest} if digest else {}
        return {
            "metadata": {"name": name, "version": version},
            "requested": requested,
            "is_direct": False,
            "is_yanked": False,
            "download_info": {"url": url, "archive_info": {"hashes": hashes}},
        }

    def plan(self, torch_version="2.5.0", modules=None, versions=None,
             system="Windows", machine="AMD64", python=(3, 12), venv=True):
        modules = {"torch"} if modules is None else modules
        versions = versions or {}
        return installer.build_install_plan(
            self.requirements, root=self.root,
            module_probe=lambda name: name in modules,
            version_probe=lambda name: versions.get(name, torch_version if name == "torch" else None),
            system=system, machine=machine, python=python, venv=venv,
        )

    def test_offline_plan_lists_missing_direct_packages(self):
        plan = self.plan()
        self.assertFalse(plan["automatic_install"])
        self.assertEqual(len(plan["missing_direct_requirements"]), 3)
        self.assertTrue(plan["torch"]["installed"])
        self.assertTrue(plan["install_allowed"])

    def test_stack_blocked_without_torch_to_prevent_implicit_install(self):
        plan = self.plan(torch_version=None, modules=set())
        self.assertTrue(plan["blocked"])
        self.assertFalse(plan["install_allowed"])

    def test_module_without_distribution_metadata_is_ambiguous(self):
        plan = self.plan(modules={"torch", "sklearn"}, versions={"torch": "2.5.0"})
        self.assertIn("scikit-learn", plan["ambiguous_packages"])
        self.assertTrue(plan["blocked"])

    def test_distribution_metadata_without_module_is_ambiguous(self):
        plan = self.plan(
            modules={"torch"},
            versions={"torch": "2.5.0", "numpy": "2.0.0"},
        )
        self.assertIn("numpy", plan["ambiguous_packages"])
        self.assertTrue(plan["blocked"])

    def test_torch_metadata_without_module_is_ambiguous(self):
        plan = installer.build_torch_plan(
            module_probe=lambda name: False,
            version_probe=lambda name: "2.5.0",
            system="Windows", machine="AMD64", python=(3, 12), venv=True,
        )
        self.assertTrue(plan["blocked"])
        self.assertTrue(plan["torch"]["ambiguous_install"])

    def test_arm64_torch_install_is_blocked(self):
        plan = installer.build_torch_plan(
            module_probe=lambda name: False, version_probe=lambda name: None,
            system="Linux", machine="aarch64", python=(3, 12), venv=True,
        )
        self.assertTrue(plan["blocked"])
        self.assertFalse(plan["install_allowed"])

    def test_existing_torch_is_preserved(self):
        plan = installer.build_torch_plan(
            module_probe=lambda name: True,
            version_probe=lambda name: "2.5.0" if name == "torch" else None,
            system="Windows", machine="AMD64", python=(3, 12), venv=True,
        )
        result = installer.run_install(
            "torch_cpu", plan,
            run=lambda *a, **k: self.fail("pip não deve ser chamado"),
        )
        self.assertEqual(result["status"], "nothing_to_do")

    def test_requirement_include_cannot_escape_root(self):
        outside = self.root.parent / "outside-requirements.txt"
        outside.write_text("numpy\n", encoding="utf-8")
        self.requirements.write_text("-r ../outside-requirements.txt\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            list(installer._iter_requirements(self.requirements, self.root))

    def test_non_venv_install_is_blocked_before_pip(self):
        plan = self.plan(venv=False)
        calls = []
        result = installer.run_install(
            "frameworks", plan, requirements_file=self.requirements,
            run=lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""),
            venv=False,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(calls, [])

    def test_report_is_pinned_and_existing_packages_are_not_upgraded(self):
        plan = self.plan()
        calls, freeze_count, displayed = [], {"value": 0}, []
        def fake_run(command, **kwargs):
            calls.append(command)
            if "--help" in command:
                return SimpleNamespace(returncode=0, stdout="--dry-run --report", stderr="")
            if "--dry-run" in command:
                report = Path(command[command.index("--report") + 1])
                report.write_text(json.dumps({"install": [
                    self.report_item("numpy", "2.0.0", requested=True),
                    self.report_item("scipy", "1.14.0", requested=False),
                ]}), encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if command[-1] == "freeze":
                freeze_count["value"] += 1
                out = "base-package==1.0\n"
                if freeze_count["value"] > 1:
                    out += "numpy==2.0.0\nscipy==1.14.0\n"
                return SimpleNamespace(returncode=0, stdout=out, stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = installer.run_install(
            "frameworks", plan, requirements_file=self.requirements,
            run=fake_run,
            input_fn=lambda prompt: (self.assertTrue(displayed), "INSTALAR")[1],
            version_probe=lambda name: "2.5.0" if name == "torch" else None,
            module_probe=lambda name: False,
            size_probe=lambda url: 12345,
            display_fn=displayed.append,
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(displayed), 1)
        self.assertIn('"sha256"', displayed[0])
        actual = [c for c in calls if "install" in c and "--dry-run" not in c and "--help" not in c]
        self.assertEqual(len(actual), 1)
        self.assertIn("--no-upgrade", actual[0])
        self.assertIn("--no-deps", actual[0])
        self.assertIn("--no-index", actual[0])
        self.assertIn("--only-binary=:all:", actual[0])
        self.assertTrue(any("#sha256=" in item for item in actual[0]))
        self.assertTrue(any("files.pythonhosted.org" in item for item in actual[0]))
        self.assertNotIn("--upgrade", actual[0])
        self.assertEqual(result["planned_packages"][0]["download_size_bytes"], 12345)
        self.assertIn("numpy", result["changed_packages"])

    def test_cancelled_install_never_runs_mutating_pip(self):
        plan, calls = self.plan(), []
        def fake_run(command, **kwargs):
            calls.append(command)
            if "--help" in command:
                return SimpleNamespace(returncode=0, stdout="--dry-run --report", stderr="")
            if "--dry-run" in command:
                report = Path(command[command.index("--report") + 1])
                report.write_text(json.dumps({"install": [
                    self.report_item("numpy", "2.0.0", requested=True)
                ]}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = installer.run_install(
            "frameworks", plan, requirements_file=self.requirements,
            run=fake_run, input_fn=lambda prompt: "não",
            version_probe=lambda name: "2.5.0" if name == "torch" else None,
            module_probe=lambda name: False,
            display_fn=lambda value: None,
        )
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(any("install" in c and "--dry-run" not in c and "--help" not in c for c in calls))

    def test_torch_uses_official_cpu_index(self):
        plan = installer.build_torch_plan(
            module_probe=lambda name: False, version_probe=lambda name: None,
            system="Windows", machine="AMD64", python=(3, 12), venv=True,
        )
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            if "--help" in command:
                return SimpleNamespace(returncode=0, stdout="--dry-run --report", stderr="")
            if "--dry-run" in command:
                report = Path(command[command.index("--report") + 1])
                report.write_text(json.dumps({"install": [
                    self.report_item(
                        "torch", "2.7.0", requested=True,
                        url="https://download.pytorch.org/whl/cpu/torch-2.7.0-cp312-cp312-win_amd64.whl",
                    )
                ]}), encoding="utf-8")
            if command[-1] == "freeze":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = installer.run_install(
            "torch_cpu", plan, run=fake_run, input_fn=lambda prompt: "INSTALAR",
            version_probe=lambda name: None,
            module_probe=lambda name: False,
        )
        self.assertEqual(result["status"], "success")
        actual = [c for c in calls if "install" in c and "--dry-run" not in c and "--help" not in c]
        dry_run = next(command for command in calls if "--dry-run" in command)
        self.assertIn(installer.TORCH_CPU_INDEX, dry_run)
        self.assertTrue(any(
            "download.pytorch.org" in item and "#sha256=" in item for item in actual[0]
        ))
        self.assertIn("--no-deps", actual[0])
        self.assertIn("--only-binary=:all:", dry_run)
        self.assertIn("--only-binary=:all:", actual[0])

    def test_direct_url_requirement_is_rejected(self):
        self.requirements.write_text(
            "custom-package @ https://example.invalid/custom.whl\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            self.plan()

    def test_resolver_cannot_overwrite_module_without_distribution_metadata(self):
        plan, calls = self.plan(), []
        def fake_run(command, **kwargs):
            calls.append(command)
            if "--help" in command:
                return SimpleNamespace(returncode=0, stdout="--dry-run --report", stderr="")
            if "--dry-run" in command:
                report = Path(command[command.index("--report") + 1])
                report.write_text(json.dumps({"install": [
                    self.report_item("numpy", "2.0.0", requested=True)
                ]}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = installer.run_install(
            "frameworks", plan, requirements_file=self.requirements,
            run=fake_run, input_fn=lambda prompt: self.fail("não deve pedir confirmação"),
            version_probe=lambda name: "2.5.0" if name == "torch" else None,
            module_probe=lambda name: name == "numpy",
            display_fn=lambda value: None,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["conflicts"][0]["module_without_metadata"])
        self.assertFalse(any(
            "install" in command and "--dry-run" not in command and "--help" not in command
            for command in calls
        ))

    def test_report_rejects_source_archive(self):
        report = {"install": [self.report_item(
            "numpy", "2.0.0",
            url="https://files.pythonhosted.org/packages/numpy-2.0.0.tar.gz",
        )]}
        with self.assertRaises(ValueError):
            installer._summarize_report(report, size_probe=lambda url: None)

    def test_report_rejects_untrusted_origin(self):
        report = {"install": [self.report_item(
            "numpy", "2.0.0",
            url="https://example.invalid/numpy-2.0.0-py3-none-any.whl",
        )]}
        with self.assertRaises(ValueError):
            installer._summarize_report(report, size_probe=lambda url: None)

    def test_report_requires_sha256(self):
        item = self.report_item("numpy", "2.0.0")
        item["download_info"]["archive_info"]["hashes"] = {}
        report = {"install": [item]}
        with self.assertRaises(ValueError):
            installer._summarize_report(report, size_probe=lambda url: None)

    def test_plan_resolves_transitives_without_mutating_environment(self):
        plan = self.plan(venv=False)
        calls, displayed = [], []
        def fake_run(command, **kwargs):
            calls.append(command)
            if "--help" in command:
                return SimpleNamespace(returncode=0, stdout="--dry-run --report", stderr="")
            if "--dry-run" in command:
                report_path = Path(command[command.index("--report") + 1])
                report_path.write_text(json.dumps({
                    "version": "1",
                    "install": [self.report_item("numpy", "2.0.0", requested=True)],
                }), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = installer.run_install(
            "frameworks", plan, requirements_file=self.requirements,
            run=fake_run, confirm=False, require_venv=False,
            version_probe=lambda name: "2.5.0" if name == "torch" else None,
            module_probe=lambda name: False,
            size_probe=lambda url: 4096,
            display_fn=displayed.append,
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(len(displayed), 1)
        self.assertIn('"sha256"', displayed[0])
        self.assertIn('"source"', displayed[0])
        self.assertEqual(result["packages"][0]["download_size_bytes"], 4096)
        self.assertFalse(any(
            "install" in command and "--dry-run" not in command and "--help" not in command
            for command in calls
        ))

    @unittest.skipUnless(os.name == "nt", "Validação de sintaxe PowerShell executada somente no Windows.")
    def test_powershell_wrapper_parses_on_windows(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell não disponível no runner.")
        script = (Path(__file__).resolve().parents[1] / "scripts" / "install-ml-cpu.ps1")
        quoted = str(script).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{quoted}', [ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
        )
        subprocess.run(
            [shell, "-NoProfile", "-Command", command],
            check=True, capture_output=True, text=True, timeout=20,
        )

    def test_powershell_wrapper_delegates_without_pip_upgrade(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "install-ml-cpu.ps1").read_text(encoding="utf-8")
        self.assertIn("nixlms_core.framework_install", source)
        self.assertNotIn("pip install --upgrade pip", source)


if __name__ == "__main__":
    unittest.main()
