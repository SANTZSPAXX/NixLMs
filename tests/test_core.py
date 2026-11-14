import tempfile
import unittest
from unittest import mock
from pathlib import Path

from nixlms_core import NixLMsNeuralCore
from nixlms_core.eeg import EEGInspiredEngine
from nixlms_core.mental_map import MentalMap
from nixlms_core.neural import LIFNetwork
from nixlms_core.encoding import SemanticEncoder
from nixlms_core.memory import MemorySystem
from nixlms_core.utils import cosine


class CoreTests(unittest.TestCase):
    def test_eeg_bands(self):
        engine = EEGInspiredEngine()
        bands = engine.band_energy(engine.synthesize(1.0))
        self.assertEqual(set(bands), {"delta", "theta", "alpha", "beta", "gamma"})
        self.assertAlmostEqual(sum(bands.values()), 1.0, places=5)

    def test_learn_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learn("qual é a capital do Brasil", "Brasília")
            self.assertEqual(ai.respond("qual é a capital do Brasil", use_language=False), "Brasília")
            self.assertGreater(ai.status()["semantic_items"], 0)

    def test_typo_temporal_question_uses_runtime_date(self):
        from datetime import datetime
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            answer = ai.respond('Quem dia e hoje')
            self.assertIn(datetime.now().astimezone().strftime('%d/%m/%Y'), answer)
            self.assertEqual(ai.last_trace['response_source'], 'runtime_datetime')

    def test_unknown_user_name_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with mock.patch.object(ai.language, 'generate', side_effect=AssertionError('não deve inventar nome')):
                answer = ai.respond('Qual meu nome?')
            self.assertIn('Ainda não sei seu nome', answer)
            self.assertEqual(ai.last_trace['response_source'], 'unknown_user_profile')

    def test_irrelevant_semantic_greeting_is_not_used_as_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            answer = ai.respond('O que é uma sombra na piscina?', use_language=False)
            self.assertNotIn('Olá!', answer)
            self.assertEqual(ai.last_trace['response_source'], 'fallback')

    def test_llm_greeting_and_question_echo_are_rejected(self):
        self.assertEqual(NixLMsNeuralCore._validate_llm_answer('O que é uma sombra na piscina?', 'Olá! Sou a NixLMs. Como posso ajudar hoje?'), (False, 'irrelevant_greeting'))
        self.assertEqual(NixLMsNeuralCore._validate_llm_answer('Quem dia e hoje', 'Quem dia e hoje?'), (False, 'question_echo'))

    def test_person_answer_must_mention_requested_entity(self):
        self.assertEqual(NixLMsNeuralCore._validate_llm_answer('Quem foi Pedro Alvares', 'O nome de NixLMs é uma abreviação para Nix Language Models.'), (False, 'requested_person_not_mentioned'))
        self.assertTrue(NixLMsNeuralCore._validate_llm_answer('Quem foi Pedro Alvares', 'Pedro Álvares Cabral foi um navegador português.')[0])
    def test_runtime_rejects_generic_llm_greeting_for_information_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with mock.patch.object(ai.language, 'generate', return_value='Olá! Sou a NixLMs. Como posso ajudar hoje?'):
                answer = ai.respond('O que é uma sombra na piscina?')
            self.assertNotIn('Olá!', answer)
            self.assertEqual(ai.last_trace['response_source'], 'fallback')
            self.assertEqual(ai.last_trace['llm_rejection_reason'], 'irrelevant_greeting')

    def test_runtime_rejects_answer_about_wrong_person(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with mock.patch.object(ai.language, 'generate', return_value='O nome de NixLMs é uma abreviação para Nix Language Models.'):
                answer = ai.respond('Quem foi Pedro Alvares')
            self.assertIn('Pedro Álvares Cabral', answer)
            self.assertEqual(ai.last_trace['response_source'], 'entity_abstention')
            self.assertEqual(ai.last_trace['llm_rejection_reason'], 'requested_person_not_mentioned')
    def test_temporal_queries_use_runtime_clock_without_ollama(self):
        from datetime import datetime
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with mock.patch.object(
                ai.language, "generate",
                side_effect=AssertionError("consulta temporal não deve chamar o LLM")
            ):
                answer = ai.respond("Que dia é hoje?")
            now = datetime.now().astimezone()
            self.assertIn(now.strftime("%d/%m/%Y"), answer)
            self.assertEqual(ai.last_trace["response_source"], "runtime_datetime")
            self.assertEqual(ai.last_trace["confidence"], 1.0)

    def test_attention_reranking_changes_final_memory_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            candidates = [
                (0.90, {"question": "consulta alfa", "answer": "Resposta A"}),
                (0.80, {"question": "consulta beta", "answer": "Resposta B"}),
            ]
            def prioritize(_query, items, _eeg, _map, limit=5):
                return [(0.0, items[0]), (1.0, items[1])][:limit]
            with mock.patch.object(ai, "_recall", return_value=candidates), \
                 mock.patch.object(ai.attention, "allocate", side_effect=prioritize):
                answer = ai.respond("consulta de teste", use_language=False)
            self.assertEqual(answer, "Resposta B")
            self.assertTrue(ai.last_trace["attention_reranking_applied"])
            self.assertEqual(
                ai.last_trace["attention_reranking_weights"],
                {"retrieval": 0.8, "attention": 0.2},
            )

    def test_episodic_recall_uses_the_configured_retrieval_encoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            encoder = object()
            with mock.patch.object(ai, "_recall", return_value=[]), \
                 mock.patch.object(ai, "_active_retrieval_encoder", return_value=encoder), \
                 mock.patch.object(ai.episodic, "recall", return_value=[]) as recall:
                ai.respond("Pergunta para validar encoder episódico", use_language=False)
            self.assertIs(recall.call_args.args[1], encoder)

    def test_temporal_time_query_is_deterministic(self):
        from datetime import datetime
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            answer = ai.respond("Que horas são agora?", use_language=False)
            self.assertIn(datetime.now().astimezone().strftime("%H:%M"), answer)
            self.assertEqual(ai.last_trace["response_source"], "runtime_datetime")

    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Digite", NixLMsNeuralCore(Path(tmp)).respond("  "))

    def test_recurrent_weights_persist(self):
        net = LIFNetwork()
        clone = LIFNetwork()
        self.assertTrue(clone.load_state_dict(net.state_dict()))
        self.assertEqual(len(clone.w_rec), clone.hidden_size)

    def test_recurrent_matrix_has_zero_diagonal(self):
        net = LIFNetwork(hidden_size=12)
        self.assertEqual(len(net.w_rec), 12)
        self.assertTrue(all(len(row) == 12 for row in net.w_rec))
        self.assertTrue(all(net.w_rec[i][i] == 0.0 for i in range(12)))

    def test_lif_spike_telemetry_and_inference_is_not_plastic(self):
        net = LIFNetwork(threshold=.08)
        vector = [1.0 / (net.input_size ** .5)] * net.input_size
        before = [row[:] for row in net.eligibility_in]
        net.forward(vector)
        self.assertEqual(len(net.last_spike_counts), net.hidden_size)
        self.assertEqual(sum(net.last_spike_counts),
                         sum(sum(step) for step in net.last_spike_history))
        self.assertEqual(before, net.eligibility_in)

    def test_mental_map_association(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = MentalMap(Path(tmp) / "map.json")
            graph.observe("python programa linguagem")
            self.assertTrue(graph.associate("python"))

    def test_semantic_encoder_learns_positive_pair(self):
        encoder = SemanticEncoder(dimensions=32, seed=7)
        a, b = "estou feliz", "estou contente"
        encoder.fit_vocabulary([a, b])
        before = cosine(encoder.encode(a), encoder.encode(b))
        for _ in range(80):
            encoder.fit_pair(a, b, 1)
        after = cosine(encoder.encode(a), encoder.encode(b))
        self.assertGreater(after, before)
        self.assertGreater(encoder.updates, 0)

    def test_semantic_encoder_learns_negative_pair(self):
        encoder = SemanticEncoder(dimensions=32, seed=11)
        a, b = "o cachorro persegue o gato", "o gato persegue o cachorro"
        encoder.fit_vocabulary([a, b])
        before = cosine(encoder.encode(a), encoder.encode(b))
        for _ in range(80):
            encoder.fit_pair(a, b, 0)
        after = cosine(encoder.encode(a), encoder.encode(b))
        self.assertLess(after, before)

    def test_encoder_inference_does_not_mutate_vocabulary(self):
        encoder = SemanticEncoder(dimensions=16)
        before = len(encoder.vocab)
        encoder.encode("termo totalmente novo")
        self.assertEqual(len(encoder.vocab), before)

    def test_semantic_encoder_state_roundtrip(self):
        encoder = SemanticEncoder(dimensions=16)
        encoder.fit_pair("bom dia", "olá bom dia", 1)
        clone = SemanticEncoder(dimensions=16)
        self.assertTrue(clone.load_state_dict(encoder.state_dict()))
        self.assertEqual(encoder.encode("bom dia"), clone.encode("bom dia"))

    def test_memory_upsert_prevents_duplicates_and_recall_skips_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemorySystem(Path(tmp))
            memory.remember("capital do Brasil", "Brasília")
            memory.remember("capital do Brasil", "Brasília é a capital.")
            class ForbiddenNetwork:
                def forward(self, *_args, **_kwargs):
                    raise AssertionError("recall não deve executar a rede neural")
            encoder = SemanticEncoder()
            encoder.fit_vocabulary(["capital do Brasil"])
            self.assertEqual(len(memory.knowledge), 1)
            self.assertEqual(memory.recall("capital do Brasil", encoder, ForbiddenNetwork())[0][1]["answer"],
                             "Brasília é a capital.")
            self.assertNotIn("_embedding", memory.knowledge[0])

    def test_training_is_idempotent_for_qa_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("o que é Python", "Python é uma linguagem.", "train")
            ai.learning.dataset.add_pair("estou feliz", "estou contente", 1, "train")
            result = ai.learning.train(epochs=3)
            matches = [x for x in ai.memory.knowledge if x.get("question") == "o que é Python"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(result["contrastive_pairs"], 1)
            self.assertGreater(ai.encoder.updates, 0)

    def test_contrastive_dataset_deduplicates_and_prevents_split_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            store = ai.learning.dataset
            store.add_pair("estou feliz", "estou contente", 1, "train")
            store.add_pair("estou contente", "estou feliz", 1, "train")
            self.assertEqual(len([r for r in store.load() if r.get("type") == "pair"]), 1)
            with self.assertRaises(ValueError):
                store.add_pair("estou feliz", "estou contente", 1, "test")
            store.add("capital brasileira", "Brasília", "train")
            with self.assertRaises(ValueError):
                store.add("capital brasileira", "Brasília", "test")

    def test_dataset_metrics_separate_retrieval_and_contrastive(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("capital do Brasil", "Brasília", "test")
            ai.learning.dataset.add_pair("estou alegre", "estou contente", 1, "test")
            metrics = ai.learning.evaluate()
            self.assertEqual(metrics["retrieval"]["samples"], 1)
            self.assertEqual(metrics["contrastive"]["samples"], 1)

    def test_semantic_benchmark_reports_comparable_retrieval_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("capital do Brasil", "Brasília", "test")
            ai.learning.dataset.add_pair("estou feliz", "estou contente", 1, "test")
            ai.learning.dataset.add_pair("gato caça rato", "rato caça gato", 0, "test")
            report = ai.learning.evaluate(ks=(1, 3))
            self.assertEqual(report["protocol"]["test_qa_samples"], 1)
            self.assertEqual(report["protocol"]["test_pair_samples"], 2)
            self.assertEqual(set(report["retrieval"]["metrics"]),
                             {"lexical", "semantic", "hybrid"})
            for channel in ("lexical", "semantic", "hybrid"):
                self.assertIn("mrr", report["retrieval"]["metrics"][channel])
                self.assertEqual(
                    set(report["retrieval"]["metrics"][channel]["recall_at_k"]),
                    {"1", "3"}
                )
            self.assertIn("f1", report["contrastive"])
            self.assertEqual(
                sum(report["contrastive"]["confusion_matrix"].values()), 2
            )

    def test_semantic_benchmark_rejects_invalid_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with self.assertRaises(ValueError):
                ai.learning.evaluate(threshold=1.5)

    def test_cosine_rejects_dimension_mismatch(self):
        with self.assertRaises(ValueError):
            cosine([1.0, 0.0], [1.0])

    def test_dataset_import_rejects_invalid_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bad.jsonl"
            source.write_text('{"question":"x","answer":"y","split":"validation"}', encoding="utf-8")
            ai = NixLMsNeuralCore(Path(tmp) / "data")
            with self.assertRaises(ValueError):
                ai.learning.dataset.import_jsonl(source)


if __name__ == "__main__":
    unittest.main()
