"""End-to-end cognitive benchmark tests (offline and deterministic)."""
import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore
from nixlms_core.learning import LearningEngine


class CognitiveBenchmarkTests(unittest.TestCase):
    def test_evaluate_reports_end_to_end_answer_quality_and_source_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add(
                "Qual o código do projeto secreto 83?",
                "O código de teste é AX-83.",
                split="test",
            )

            report = ai.learning.evaluate()

            cognition = report["cognition"]
            self.assertEqual(cognition["samples"], 1)
            self.assertIn("exact_match", cognition["metrics"])
            self.assertIn("token_f1", cognition["metrics"])
            self.assertIn("abstention_rate", cognition["metrics"])
            self.assertIn("question_echo_rate", cognition["metrics"])
            self.assertEqual(len(cognition["cases"]), 1)
            self.assertEqual(cognition["cases"][0]["response_source"], "fallback")
            self.assertTrue(cognition["cases"][0]["abstained"])
            self.assertFalse(cognition["protocol"]["llm_enabled"])

    def test_cognitive_benchmark_excludes_exact_test_questions_from_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            question = "Qual o código do projeto sigiloso ZX-917?"
            leaked_answer = "O código sigiloso é ZX-917."
            ai.memory.remember(question, leaked_answer)
            ai.learning.dataset.add(question, leaked_answer, split="test")

            report = ai.learning.evaluate()

            case = report["cognition"]["cases"][0]
            self.assertNotEqual(case["answer"], leaked_answer)
            self.assertEqual(case["response_source"], "fallback")
            self.assertTrue(report["cognition"]["protocol"]["exact_test_questions_excluded"])
            self.assertFalse(report["cognition"]["protocol"]["historical_weight_provenance_verified"])

    def test_evaluate_does_not_persist_benchmark_interactions_as_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("Pergunta de avaliação sem resposta", "Resposta esperada.", "test")
            episodic_before = len(ai.episodic.items)
            legacy_episodes_before = len(ai.memory.episodes)
            working_before = len(ai.attention.working)
            neural_weights_before = ai.network.state_dict()
            encoder_before = ai.encoder.state_dict()

            ai.learning.evaluate()

            self.assertEqual(len(ai.episodic.items), episodic_before)
            self.assertEqual(len(ai.memory.episodes), legacy_episodes_before)
            self.assertEqual(len(ai.attention.working), working_before)
            self.assertEqual(ai.network.state_dict(), neural_weights_before)
            self.assertEqual(ai.encoder.state_dict(), encoder_before)

    def test_empty_cognitive_test_set_is_reported_without_fake_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))

            report = ai.learning.evaluate()

            self.assertEqual(report["cognition"]["samples"], 0)
            self.assertIsNone(report["cognition"]["metrics"]["token_f1"])
            self.assertEqual(report["cognition"]["cases"], [])

    def test_cognitive_benchmark_restores_memory_when_response_raises(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            question = "Pergunta de restauração?"
            ai.learning.dataset.add(question, "Resposta.", "test")
            knowledge_ref = ai.memory.knowledge
            episodic_ref = ai.episodic.items
            with patch.object(ai, "respond", side_effect=RuntimeError("simulated failure")):
                with self.assertRaises(RuntimeError):
                    ai.learning.evaluate()

            self.assertIs(ai.memory.knowledge, knowledge_ref)
            self.assertIs(ai.episodic.items, episodic_ref)

    def test_token_f1_uses_multiset_overlap(self):
        self.assertAlmostEqual(
            LearningEngine._token_f1("gato gato caça rato", "gato caça rato"),
            6 / 7,
        )

    def test_live_language_generation_is_opt_in_for_cognitive_benchmark(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("O que é um neurônio artificial?", "É uma unidade computacional inspirada em neurônios.", "test")
            with patch.object(ai.language, "generate", return_value="É uma unidade computacional inspirada em neurônios.") as generate:
                report = ai.learning.evaluate(include_llm=True)

            generate.assert_called_once()
            self.assertTrue(report["cognition"]["protocol"]["llm_enabled"])
            self.assertEqual(report["cognition"]["cases"][0]["response_source"], "local_llm")


if __name__ == "__main__":
    unittest.main()
