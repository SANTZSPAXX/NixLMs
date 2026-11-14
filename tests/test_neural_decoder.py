"""Tests for the LIF-conditioned autoregressive neural decoder."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core import CoreConfig, NixLMsNeuralCore
from nixlms_core.decoder import NeuralTextDecoder


class NeuralTextDecoderTests(unittest.TestCase):
    def test_teacher_forcing_training_reduces_sequence_loss(self):
        decoder = NeuralTextDecoder(
            context_size=4, hidden_size=12, embedding_size=12,
            learning_rate=0.08, seed=7,
        )
        answer = "A água reflete a luz."
        decoder.fit_vocabulary([answer])
        context = [0.2, -0.1, 0.3, 0.4]
        initial = decoder.score(context, answer)["loss"]

        for _ in range(160):
            decoder.train_pair(context, answer)

        final = decoder.score(context, answer)["loss"]
        generated = decoder.generate(context, max_tokens=12)

        self.assertLess(final, initial)
        self.assertGreater(decoder.trained_steps, 0)
        self.assertGreater(generated["token_count"], 0)
        self.assertTrue(generated["text"])

    def test_generation_obeys_token_limit_and_reports_confidence(self):
        decoder = NeuralTextDecoder(context_size=3, hidden_size=8, embedding_size=8, seed=3)
        decoder.fit_vocabulary(["Olá mundo."])
        context = [0.1, 0.2, 0.3]
        for _ in range(80):
            decoder.train_pair(context, "Olá mundo.")

        result = decoder.generate(context, max_tokens=2)

        self.assertLessEqual(result["token_count"], 2)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_decoder_state_roundtrip_preserves_generation(self):
        decoder = NeuralTextDecoder(context_size=4, hidden_size=10, embedding_size=8, seed=13)
        decoder.fit_vocabulary(["NixLMs gera linguagem."])
        context = [0.1, -0.2, 0.3, 0.4]
        for _ in range(20):
            decoder.train_pair(context, "NixLMs gera linguagem.")
        expected = decoder.generate(context, max_tokens=10)

        restored = NeuralTextDecoder(context_size=4, hidden_size=10, embedding_size=8, seed=13)
        self.assertTrue(restored.load_state_dict(decoder.state_dict()))
        self.assertEqual(restored.generate(context, max_tokens=10), expected)

    def test_invalid_context_and_non_finite_values_are_rejected(self):
        decoder = NeuralTextDecoder(context_size=2, hidden_size=8, embedding_size=8)
        with self.assertRaises(ValueError):
            decoder.generate([0.1], max_tokens=4)
        with self.assertRaises(ValueError):
            decoder.train_pair([float("nan"), 0.1], "texto")

    def test_oov_generation_does_not_expand_decoder_vocabulary(self):
        decoder = NeuralTextDecoder(context_size=2, hidden_size=8, embedding_size=8)
        decoder.fit_vocabulary(["palavra conhecida"])
        before = len(decoder.vocab)

        decoder.score([0.1, 0.2], "termo desconhecido")

        self.assertEqual(len(decoder.vocab), before)

    def test_training_uses_only_train_answers_for_decoder_vocabulary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("pergunta de treino", "resposta treino exclusiva", "train")
            ai.learning.dataset.add("pergunta validação", "resposta validation exclusiva", "validation")
            ai.learning.dataset.add("pergunta teste", "resposta test exclusiva", "test")

            report = ai.learning.train(epochs=1)

            self.assertGreater(report["decoder_trained_steps"], 0)
            self.assertIn("treino", ai.decoder.vocab)
            self.assertNotIn("validation", ai.decoder.vocab)
            self.assertNotIn("test", ai.decoder.vocab)

    def test_trained_decoder_is_primary_and_skips_external_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CoreConfig(decoder_min_confidence=0.0, decoder_max_tokens=12)
            ai = NixLMsNeuralCore(Path(tmp), config=config)
            question = "Explique a água"
            answer = "A água reflete a luz."
            ai.learning.dataset.add(question, answer, "train")
            ai.learning.train(epochs=100)

            with patch.object(ai.language, "generate", side_effect=AssertionError("LLM não deveria ser chamado")):
                ai.respond(question, use_language=True)

            self.assertEqual(ai.last_trace["response_source"], "lif_neural_decoder")
            self.assertTrue(ai.last_trace["decoder_accepted"])
            self.assertGreater(ai.last_trace["decoder_token_count"], 0)

    def test_agent_persists_and_reloads_trained_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            question = "Explique a água"
            ai.learning.dataset.add(question, "A água reflete a luz.", "train")
            ai.learning.train(epochs=5)
            context, _, _, _ = ai._lif_forward(question)
            expected = ai.decoder.generate(context, max_tokens=10)
            trained_steps = ai.decoder.trained_steps

            restored = NixLMsNeuralCore(data_dir)
            restored_context, _, _, _ = restored._lif_forward(question)

            self.assertEqual(restored.decoder.trained_steps, trained_steps)
            self.assertEqual(
                restored.decoder.generate(restored_context, max_tokens=10),
                expected,
            )

    def test_unreadable_decoder_checkpoint_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            checkpoint = data_dir / "neural_decoder.json"
            data_dir.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text("{not valid json", encoding="utf-8")
            ai = NixLMsNeuralCore(data_dir)
            self.assertEqual(ai.decoder_load_error, "decoder_state_unreadable")
            self.assertFalse(ai.decoder_persistence_enabled)

            ai.learning.dataset.add("pergunta treino", "resposta treino", "train")
            ai.learning.train(epochs=1)

            self.assertEqual(checkpoint.read_text(encoding="utf-8"), "{not valid json")

    def test_decoder_test_metrics_are_reported_without_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("pergunta treino", "resposta conhecida", "train")
            ai.learning.dataset.add("pergunta teste", "resposta conhecida", "test")
            ai.learning.train(epochs=2)

            before = ai.decoder.state_dict()
            report = ai.learning.evaluate()

            self.assertEqual(report["decoder"]["samples"], 1)
            self.assertIsNotNone(report["decoder"]["metrics"]["loss"])
            self.assertEqual(ai.decoder.state_dict(), before)


if __name__ == "__main__":
    unittest.main()
