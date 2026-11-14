import json
import tempfile
import unittest
from pathlib import Path

from nixlms_core.learning import DatasetStore


class DatasetIntegrityTests(unittest.TestCase):
    def test_pair_sentences_cannot_cross_train_test_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DatasetStore(Path(tmp) / "dataset.json")
            store.add_pair("gato persegue rato", "felino caça roedor", 1, "train")
            with self.assertRaises(ValueError):
                store.add_pair("gato persegue rato", "animal caça presa", 1, "test")

    def test_qa_and_pair_text_cannot_leak_across_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DatasetStore(Path(tmp) / "dataset.json")
            store.add("como aprender Python", "Pratique programação.", "train")
            with self.assertRaises(ValueError):
                store.add_pair("como aprender Python", "qual linguagem estudar", 1, "test")

    def test_import_jsonl_is_atomic_when_late_row_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            store = DatasetStore(path)
            store.add("capital do Brasil", "Brasília", "train")
            before = store.load()
            source = Path(tmp) / "incoming.jsonl"
            source.write_text(
                json.dumps({"question": "nova pergunta", "answer": "nova resposta", "split": "train"}) + "\n" +
                json.dumps({"type": "pair", "text_a": "capital do Brasil", "text_b": "pergunta diferente", "label": 1, "split": "test"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                store.import_jsonl(source)
            self.assertEqual(store.load(), before)

    def test_audit_splits_reports_legacy_pair_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            path.write_text(json.dumps([
                {"type": "pair", "text_a": "frase repetida", "text_b": "outra frase", "label": 1, "split": "train"},
                {"type": "pair", "text_a": "frase repetida", "text_b": "mais uma frase", "label": 1, "split": "test"},
            ]), encoding="utf-8")
            report = DatasetStore(path).audit_splits()
            self.assertFalse(report["valid"])
            self.assertTrue(report["violations"])


class WorldModelTests(unittest.TestCase):
    def test_fact_persistence_and_normalized_query(self):
        from nixlms_core.world_model import WorldModel
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "world.json"
            world = WorldModel(path)
            fact = world.assert_fact(" São Paulo ", "capital de", "Brasil", .95, "user")
            restored = WorldModel(path)
            result = restored.query(subject="sao paulo", predicate="capital de")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["object"], "Brasil")
            self.assertEqual(result[0]["source"], "user")
            self.assertEqual(fact["confidence"], .95)

    def test_fact_validation_and_conflicts_are_non_destructive(self):
        from nixlms_core.world_model import WorldModel
        with tempfile.TemporaryDirectory() as tmp:
            world = WorldModel(Path(tmp) / "world.json")
            with self.assertRaises(ValueError):
                world.assert_fact("", "capital de", "Brasil")
            with self.assertRaises(ValueError):
                world.assert_fact("São Paulo", "capital de", "Brasil", 1.5)
            world.assert_fact("São Paulo", "capital de", "Brasil", .9, "fonte-a")
            world.assert_fact("São Paulo", "capital de", "Argentina", .4, "fonte-b")
            conflicts = world.possible_conflicts("sao paulo", "capital de")
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(len(conflicts[0]), 2)
            self.assertEqual(world.stats()["facts"], 2)

    def test_world_search_ranks_relevant_facts(self):
        from nixlms_core.world_model import WorldModel
        with tempfile.TemporaryDirectory() as tmp:
            world = WorldModel(Path(tmp) / "world.json")
            world.assert_fact("Terra", "orbita", "Sol", .99, "dataset")
            world.assert_fact("Lua", "orbita", "Terra", .99, "dataset")
            self.assertEqual(world.search("Terra Sol")[0]["subject"], "Terra")


class GoalManagerTests(unittest.TestCase):
    def test_goal_and_steps_persist(self):
        from nixlms_core.planning import GoalManager
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goals.json"
            manager = GoalManager(path)
            goal = manager.create_goal("Melhorar memória", "Aprimorar recuperação.")
            step = manager.add_step(goal["id"], "Criar benchmark")
            restored = GoalManager(path)
            self.assertEqual(restored.get_goal(goal["id"])["steps"][0]["id"], step["id"])

    def test_dependencies_gate_next_actions_and_completion(self):
        from nixlms_core.planning import GoalManager
        with tempfile.TemporaryDirectory() as tmp:
            manager = GoalManager(Path(tmp) / "goals.json")
            goal = manager.create_goal("Evoluir")
            first = manager.add_step(goal["id"], "Definir testes")
            second = manager.add_step(goal["id"], "Implementar", depends_on=[first["id"]])
            self.assertEqual([x["id"] for x in manager.next_actions(goal["id"])], [first["id"]])
            with self.assertRaises(ValueError):
                manager.set_step_status(goal["id"], second["id"], "completed")
            manager.set_step_status(goal["id"], first["id"], "completed")
            self.assertEqual([x["id"] for x in manager.next_actions(goal["id"])], [second["id"]])
            manager.set_step_status(goal["id"], second["id"], "completed")
            self.assertEqual(manager.get_goal(goal["id"])["status"], "completed")

    def test_goal_manager_rejects_unknown_dependencies_and_statuses(self):
        from nixlms_core.planning import GoalManager
        with tempfile.TemporaryDirectory() as tmp:
            manager = GoalManager(Path(tmp) / "goals.json")
            goal = manager.create_goal("Evoluir")
            with self.assertRaises(ValueError):
                manager.add_step(goal["id"], "Etapa inválida", depends_on=["missing"])
            step = manager.add_step(goal["id"], "Etapa")
            with self.assertRaises(ValueError):
                manager.set_step_status(goal["id"], step["id"], "unknown")


class PretrainedEncoderTests(unittest.TestCase):
    def test_backend_is_lazy_and_uses_e5_query_passage_prefixes(self):
        from nixlms_core.pretrained_encoder import TransformersSentenceEncoder

        class FakeModel:
            max_seq_length = None
            def __init__(self):
                self.inputs = []
            def get_sentence_embedding_dimension(self):
                return 2
            def encode(self, texts, **kwargs):
                self.inputs.extend(texts)
                return [[3.0, 4.0] for _ in texts]

        captured = {}
        model = FakeModel()
        def loader(model_path, device, local_files_only, max_seq_length):
            captured.update(locals())
            return model

        encoder = TransformersSentenceEncoder("local/e5", model_loader=loader)
        self.assertFalse(encoder.status()["loaded"])
        query = encoder.encode_query("pergunta")
        passage = encoder.encode_passage("documento")
        self.assertEqual(model.inputs, ["query: pergunta", "passage: documento"])
        self.assertAlmostEqual(query[0], .6, places=6)
        self.assertAlmostEqual(passage[1], .8, places=6)
        self.assertEqual(captured["device"], "cpu")
        self.assertTrue(captured["local_files_only"])
        self.assertTrue(encoder.status()["loaded"])

    def test_backend_surfaces_missing_optional_dependency_without_importing_at_module_load(self):
        from nixlms_core.pretrained_encoder import TransformersSentenceEncoder
        encoder = TransformersSentenceEncoder("local/e5", model_loader=lambda **kwargs: (_ for _ in ()).throw(ImportError("optional dependency missing")))
        with self.assertRaises(ImportError):
            encoder.encode("texto")



class IntegrationGuardTests(unittest.TestCase):
    def test_agent_falls_back_to_native_encoder_when_optional_backend_is_missing(self):
        from nixlms_core import NixLMsNeuralCore
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))

            class BrokenBackend:
                def encode_query(self, _text):
                    raise ImportError("optional backend unavailable")

            ai.retrieval_encoder = BrokenBackend()
            active = ai._active_retrieval_encoder()
            self.assertIs(active, ai.encoder)
            self.assertIn("ImportError", ai._retrieval_encoder_error)
            self.assertEqual(ai.memory._embedding_cache, {})

    def test_training_and_evaluation_refuse_legacy_split_leakage(self):
        from nixlms_core import NixLMsNeuralCore
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.path.write_text(json.dumps([
                {"type": "pair", "text_a": "frase compartilhada", "text_b": "outra frase", "label": 1, "split": "train"},
                {"type": "pair", "text_a": "frase compartilhada", "text_b": "terceira frase", "label": 1, "split": "test"},
            ]), encoding="utf-8")
            with self.assertRaises(ValueError):
                ai.learning.train()
            with self.assertRaises(ValueError):
                ai.learning.evaluate()

    def test_goal_context_zero_limit_returns_empty(self):
        from nixlms_core.planning import GoalManager
        with tempfile.TemporaryDirectory() as tmp:
            manager = GoalManager(Path(tmp) / "goals.json")
            manager.create_goal("Objetivo")
            self.assertEqual(manager.active_context(limit=0), [])

if __name__ == "__main__":
    unittest.main()
