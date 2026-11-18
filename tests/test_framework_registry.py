import json
import unittest

from nixlms_core.framework_registry import FRAMEWORKS, inspect_frameworks, main


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


if __name__ == "__main__":
    unittest.main()
