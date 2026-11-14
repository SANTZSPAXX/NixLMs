"""Tests for trainable character subword representations and OOV generalization."""
import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore
from nixlms_core.encoding import SemanticEncoder
from nixlms_core.utils import cosine


class SubwordEncoderTests(unittest.TestCase):
    def test_oov_morphological_variants_share_character_ngram_features(self):
        encoder = SemanticEncoder(dimensions=64, seed=42)
        encoder.fit_vocabulary(["programação"])

        related = cosine(
            encoder.encode("programação"),
            encoder.encode("programacoes"),
        )
        unrelated = cosine(
            encoder.encode("programação"),
            encoder.encode("astronomia"),
        )

        self.assertGreater(related, unrelated + 0.25)

    def test_oov_inference_does_not_expand_vocabulary(self):
        encoder = SemanticEncoder(dimensions=32, seed=7)
        encoder.fit_vocabulary(["rede neural"])
        before = len(encoder.vocab)

        encoder.encode("neurocomputação desconhecida")
        coverage = encoder.feature_coverage("neurocomputação desconhecida")

        self.assertEqual(len(encoder.vocab), before)
        self.assertGreater(coverage["total_subword_features"], 0)
        self.assertGreater(coverage["subword_feature_coverage"], 0.0)

    def test_feature_expansion_is_bounded_for_long_inputs(self):
        encoder = SemanticEncoder(dimensions=16, seed=5)
        features = encoder._features(" ".join(["extraordinarytoken" * 5] * 300))

        self.assertLessEqual(len(features), 128 * 94 + 127)

    def test_contrastive_training_updates_character_subword_embeddings(self):
        encoder = SemanticEncoder(dimensions=32, seed=11)
        encoder.fit_vocabulary(["programação", "programacoes"])
        feature = "char:pro"
        self.assertIn(feature, encoder.vocab)
        index = encoder.vocab[feature]
        before = list(encoder.embeddings[index])

        result = encoder.fit_pair("programação", "programacoes", label=0)

        self.assertTrue(result["updated"])
        self.assertNotEqual(encoder.embeddings[index], before)

    def test_subword_features_survive_encoder_state_roundtrip(self):
        encoder = SemanticEncoder(dimensions=32, seed=13)
        encoder.fit_vocabulary(["aprendizado", "aprendizagem"])
        expected = encoder.encode("aprendizado")
        restored = SemanticEncoder(dimensions=32, seed=13)
        self.assertTrue(restored.load_state_dict(encoder.state_dict()))

        self.assertEqual(restored.encode("aprendizado"), expected)
        self.assertTrue(any(feature.startswith("char:") for feature in restored.vocab))

    def test_integrated_evaluation_reports_validation_representation_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            train = [
                ("gato é um felino", "felino"),
                ("cachorro é um canino", "canino"),
                ("águia é uma ave", "ave"),
            ]
            validation = [
                ("explique gato", "felino"),
                ("descreva cachorro", "canino"),
                ("defina águia", "ave"),
            ]
            for question, answer in train:
                ai.learning.dataset.add(question, answer, "train")
            for question, answer in validation:
                ai.learning.dataset.add(question, answer, "validation")
            ai.encoder.fit_vocabulary([text for row in train for text in row])

            vocab_before = len(ai.encoder.vocab)
            report = ai.learning.evaluate()
            metrics = report["representations"]["metrics"]

            self.assertEqual(len(ai.encoder.vocab), vocab_before)

            self.assertEqual(report["representations"]["samples"], 3)
            self.assertGreater(metrics["positive_similarity"], metrics["negative_similarity"])
            self.assertGreater(metrics["pairwise_accuracy"], 0.66)
            self.assertGreater(metrics["subword_feature_coverage"], 0.0)
            self.assertFalse(report["representations"]["protocol"]["test_split_used"])

    def test_representation_benchmark_reports_empty_validation_without_fake_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))

            report = ai.learning.evaluate()

            self.assertEqual(report["representations"]["samples"], 0)
            self.assertIsNone(report["representations"]["metrics"]["pairwise_accuracy"])


if __name__ == "__main__":
    unittest.main()
