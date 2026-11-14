import tempfile
import unittest
from pathlib import Path

from nixlms_core.episodic import EpisodicMemory


class EpisodicMemoryTests(unittest.TestCase):
    def test_record_persists_complete_experience_and_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episodic.json"
            memory = EpisodicMemory(path)
            episode = memory.record(
                "Como configurar Python?", "Instale Python 3.12.",
                context={"response_source": "local_llm"},
                outcome="Resposta entregue", importance=0.8, tags=["python"],
            )
            restored = EpisodicMemory(path)
            self.assertEqual(len(restored.items), 1)
            self.assertEqual(restored.items[0]["id"], episode["id"])
            self.assertEqual(restored.items[0]["context"]["response_source"], "local_llm")
            self.assertIsNone(restored.items[0]["feedback"])

    def test_recall_uses_content_and_returns_ranked_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "episodic.json")
            memory.record("Como instalar Python no Windows", "Use o instalador oficial.")
            memory.record("Receita de pão caseiro", "Misture farinha e água.")
            results = memory.recall("instalar Python Windows")
            self.assertEqual(len(results), 1)
            self.assertIn("Python", results[0][1]["user_input"])

    def test_feedback_updates_latest_matching_experience(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "episodic.json")
            first = memory.record("Como usar Git?", "Comandos básicos.")
            second = memory.record("Como usar Git?", "Use git status e git commit.")
            updated = memory.set_feedback("Como usar Git?", True)
            self.assertEqual(updated["id"], second["id"])
            self.assertIsNone(memory.items[0]["feedback"])
            self.assertEqual(memory.items[1]["feedback"], "positive")
            self.assertEqual(memory.stats()["positive_feedback"], 1)

    def test_invalid_inputs_and_limits_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "episodic.json", max_items=1)
            with self.assertRaises(ValueError):
                memory.record("", "resposta")
            with self.assertRaises(ValueError):
                memory.record("pergunta", "resposta", importance=1.5)
            memory.record("primeira", "resposta")
            memory.record("segunda", "resposta")
            self.assertEqual(len(memory.items), 1)
            self.assertEqual(memory.items[0]["user_input"], "segunda")

    def test_agent_records_interaction_and_feedback(self):
        from nixlms_core import NixLMsNeuralCore
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.respond("Pergunta experimental sobre memória episódica", use_language=False)
            self.assertEqual(len(ai.episodic.items), 1)
            episode = ai.episodic.items[0]
            self.assertEqual(episode["user_input"], "Pergunta experimental sobre memória episódica")
            self.assertIn("response_source", episode["context"])
            self.assertTrue(ai.feedback("Pergunta experimental sobre memória episódica", True))
            self.assertEqual(ai.episodic.items[0]["feedback"], "positive")
            self.assertEqual(ai.status()["positive_feedback"], 1)

    def test_feedback_requires_matching_episode_and_never_changes_neural_weights(self):
        from nixlms_core import NixLMsNeuralCore
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            before = ai.network.state_dict()
            self.assertFalse(ai.feedback("pergunta sem episódio", True))
            self.assertEqual(ai.network.state_dict(), before)
            question = "Experiência para validar feedback sem plasticidade"
            ai.respond(question, use_language=False)
            before = ai.network.state_dict()
            self.assertTrue(ai.feedback(question, False))
            self.assertEqual(ai.network.state_dict(), before)
            self.assertEqual(ai.episodic.items[-1]["feedback"], "negative")

    def test_empty_query_and_nonpositive_limit_return_no_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "episodic.json")
            memory.record("pergunta", "resposta")
            self.assertEqual(memory.recall(""), [])
            self.assertEqual(memory.recall("pergunta", limit=0), [])


if __name__ == "__main__":
    unittest.main()
