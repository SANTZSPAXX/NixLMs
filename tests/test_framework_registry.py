import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core.framework_registry import (
    FRAMEWORKS, FRAMEWORK_METADATA, inspect_frameworks, main,
)
from nixlms_core.framework_status import classify_installation


class FakeDistribution:
    def __init__(self, root=None, files=None, version="1.2"):
        self.version = version
        self.files = files
        self.root = Path(root or ".")

    def locate_file(self, entry):
        return self.root / str(entry)


class FrameworkRegistryTests(unittest.TestCase):
    def test_registry_has_separate_optional_groups(self):
        groups = {item.install_group for item in FRAMEWORKS}
        self.assertTrue({"pytorch-cpu", "ml-cpu", "tensorflow", "llama-cpp"} <= groups)

    def test_inspection_does_not_import_frameworks(self):
        report = inspect_frameworks()
        self.assertEqual(len(report), len(FRAMEWORKS))
        self.assertTrue(all("installed" in item and "version" in item for item in report))

    def test_json_cli_is_valid(self):
        # The function's output is exercised by the CLI integration in CI;
        # this checks the report remains JSON-serializable without ML packages.
        payload = json.dumps(inspect_frameworks(), ensure_ascii=False)
        self.assertIsInstance(json.loads(payload), list)

    def test_huggingface_capability_groups_are_optional(self):
        by_name = {item.name: item for item in FRAMEWORKS}
        self.assertIn("Hugging Face Hub", by_name)
        self.assertIn("Hugging Face Datasets", by_name)
        self.assertIn("PEFT", by_name)
        self.assertIn("Diffusers", by_name)
        self.assertFalse(by_name["Hugging Face Hub"].default_recommendation)
        self.assertEqual(by_name["Hugging Face Hub"].install_group, "hf-hub")

    def test_default_recommendations_are_cpu_focused(self):
        recommended = {item.name for item in FRAMEWORKS if item.default_recommendation}
        self.assertIn("PyTorch", recommended)
        self.assertIn("ONNX Runtime CPU", recommended)
        self.assertNotIn("TensorFlow CPU", recommended)

    def test_installation_state_requires_metadata_and_module(self):
        self.assertEqual(classify_installation("1.2", True)["installation_state"], "installed")
        self.assertTrue(classify_installation("1.2", True)["installed"])
        self.assertEqual(classify_installation(None, False)["installation_state"], "absent")

    def test_metadata_without_module_is_ambiguous_not_installed(self):
        distribution = FakeDistribution(files=[])
        with patch("nixlms_core.framework_registry._installed_distribution", return_value=distribution), \
             patch("nixlms_core.framework_registry.importlib.util.find_spec", return_value=None):
            item = inspect_frameworks((FRAMEWORKS[0],))[0]
        self.assertFalse(item["installed"])
        self.assertTrue(item["ambiguous_install"])
        self.assertEqual(item["installation_state"], "metadata_only")

    def test_module_without_distribution_metadata_is_ambiguous(self):
        with patch("nixlms_core.framework_registry._installed_distribution", return_value=None), \
             patch("nixlms_core.framework_registry.importlib.util.find_spec", return_value=object()):
            item = inspect_frameworks((FRAMEWORKS[0],))[0]
        self.assertFalse(item["installed"])
        self.assertTrue(item["ambiguous_install"])
        self.assertEqual(item["installation_state"], "module_only")


    def test_manifest_covers_every_framework_and_marks_unverified_licenses(self):
        self.assertEqual(
            {item.package for item in FRAMEWORKS},
            set(FRAMEWORK_METADATA),
        )
        for package, metadata in FRAMEWORK_METADATA.items():
            with self.subTest(package=package):
                self.assertTrue(metadata["project_url"])
                self.assertTrue(metadata["source_url"])
                self.assertTrue(metadata["distribution_source_url"])
                self.assertTrue(metadata["compatibility_url"])
                if metadata["license_spdx"] is None:
                    self.assertNotEqual(metadata["license_status"], "verified_upstream")
                else:
                    self.assertEqual(metadata["license_status"], "verified_upstream")

    def test_inventory_reports_environment_and_separates_model_and_dataset_state(self):
        item = inspect_frameworks((FRAMEWORKS[0],))[0]
        self.assertEqual(
            set(item["current_environment"]),
            {"python", "implementation", "os", "architecture"},
        )
        self.assertEqual(item["compatibility_status"], "not_resolved_by_inventory")
        self.assertEqual(item["model_library_status"], "not_inspected")
        self.assertEqual(item["training_dataset_library_status"], "not_inspected")
        self.assertEqual(item["runtime_integration_status"], "not_verified")
        self.assertEqual(item["runtime_resources"]["cpu_time"], "not_measured")
        self.assertIsNone(item["runtime_resources"]["peak_ram_bytes"])

    def test_default_inventory_does_not_walk_installed_files(self):
        distribution = FakeDistribution(files=["package.py"])
        with patch("nixlms_core.framework_registry._installed_distribution", return_value=distribution), \
             patch("nixlms_core.framework_registry.importlib.util.find_spec", return_value=object()), \
             patch("nixlms_core.framework_registry._measure_distribution_size",
                   side_effect=AssertionError("não deve percorrer arquivos por padrão")):
            item = inspect_frameworks((FRAMEWORKS[0],))[0]
        self.assertEqual(item["installed_size_status"], "not_measured")
        self.assertIsNone(item["installed_size_bytes"])

    def test_optional_size_measurement_counts_only_files_inside_site_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "site-packages"
            root.mkdir()
            (root / "pkg").mkdir()
            (root / "pkg" / "module.py").write_bytes(b"12345")
            (Path(temp) / "outside.txt").write_bytes(b"x" * 100)
            distribution = FakeDistribution(
                root=root, files=["pkg/module.py", "../outside.txt"]
            )
            with patch("nixlms_core.framework_registry._installed_distribution",
                       return_value=distribution), \
                 patch("nixlms_core.framework_registry.importlib.util.find_spec",
                       return_value=object()), \
                 patch("nixlms_core.framework_registry.sysconfig.get_paths",
                       return_value={"purelib": str(root), "platlib": str(root)}):
                item = inspect_frameworks((FRAMEWORKS[0],), include_sizes=True)[0]
        self.assertEqual(item["installed_size_bytes"], 5)
        self.assertEqual(item["installed_size_file_count"], 1)
        self.assertEqual(item["installed_size_status"], "measured")

    def test_uninstalled_and_inconsistent_packages_do_not_claim_installed_size(self):
        with patch("nixlms_core.framework_registry._installed_distribution", return_value=None), \
             patch("nixlms_core.framework_registry.importlib.util.find_spec", return_value=None):
            absent = inspect_frameworks((FRAMEWORKS[0],), include_sizes=True)[0]
        self.assertEqual(absent["installed_size_status"], "not_installed")
        self.assertIsNone(absent["installed_size_bytes"])

        distribution = FakeDistribution(files=["package.py"])
        with patch("nixlms_core.framework_registry._installed_distribution", return_value=distribution), \
             patch("nixlms_core.framework_registry.importlib.util.find_spec", return_value=None):
            inconsistent = inspect_frameworks((FRAMEWORKS[0],), include_sizes=True)[0]
        self.assertEqual(inconsistent["installation_state"], "metadata_only")
        self.assertEqual(inconsistent["installed_size_status"], "inconsistent_installation")
        self.assertIsNone(inconsistent["installed_size_bytes"])

    def test_sizes_cli_enables_optional_measurement(self):
        with patch("nixlms_core.framework_registry.inspect_frameworks", return_value=[]) as inspect, \
             patch("builtins.print"):
            self.assertEqual(main(["--sizes"]), 0)
        inspect.assert_called_once_with(include_sizes=True)


if __name__ == "__main__":
    unittest.main()
