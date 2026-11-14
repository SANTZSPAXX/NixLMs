import os
from pathlib import Path
from .config import CoreConfig
from .eeg import EEGInspiredEngine
from .neural import LIFNetwork
from .encoding import SemanticEncoder
from .pretrained_encoder import TransformersSentenceEncoder
from .memory import MemorySystem
from .cognition import CognitiveEngine
from .learner import FeedbackLearner
from .mental_map import MentalMap
from .world_model import WorldModel
from .planning import GoalManager
from .scheduler import TaskScheduler
from .attention import AttentionSystem
from .language import LanguageEngine
from .learning import LearningEngine
from .utils import save_json, load_json


DEFAULTS = [
    {"question": "oi olá bom dia boa tarde boa noite", "answer": "Olá! Sou a NixLMs. Como posso ajudar?"},
    {"question": "quem é você qual seu nome", "answer": "Sou a NixLMs, uma IA experimental modular com rede recorrente LIF, mapa mental, atenção e memória."},
    {"question": "como você funciona arquitetura", "answer": "Integro uma rede recorrente pulsante, osciladores sintéticos inspirados em EEG, grafo de conceitos, atenção dinâmica, memória e um LLM local opcional."},
    {"question": "o que é eeg", "answer": "EEG é eletroencefalografia: registro da atividade elétrica cerebral por eletrodos. Aqui uso oscilações sintéticas para experimentação, não dados clínicos."},
    {"question": "obrigado valeu", "answer": "Por nada! Vamos continuar evoluindo a NixLMs."},
]


class NixLMsNeuralCore:
    def __init__(self, data_dir=None, config=None, llm_model=None):
        self.config = config or CoreConfig()
        self.data_dir = Path(data_dir or Path(__file__).resolve().parents[1] / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.encoder = SemanticEncoder(self.config.input_size, seed=self.config.seed)
        encoder_state = load_json(self.data_dir / "semantic_encoder.json", None)
        if encoder_state:
            self.encoder.load_state_dict(encoder_state)

        # O encoder nativo continua responsável pelo vetor de entrada LIF e pelo
        # aprendizado contrastivo. O backend pré-treinado é apenas para recuperação.
        model_path = os.getenv("NIXLMS_EMBEDDING_MODEL_PATH", "").strip()
        self.retrieval_encoder = (
            TransformersSentenceEncoder(model_path, device="cpu", local_files_only=True)
            if model_path else self.encoder
        )
        self._retrieval_encoder_error = None

        self.network = LIFNetwork(
            self.config.input_size, self.config.hidden_size, self.config.output_size,
            self.config.steps, self.config.threshold, self.config.leak,
            self.config.seed, self.config.learning_rate
        )
        weights = load_json(self.data_dir / "neural_weights.json", None)
        if weights:
            self.network.load_state_dict(weights)

        self.eeg = EEGInspiredEngine(self.config.seed)
        self.memory = MemorySystem(self.data_dir, self.config.max_memory_items)
        self.cognition = CognitiveEngine(self.config.confidence_threshold)
        self.learner = FeedbackLearner(self.network)
        self.mental_map = MentalMap(self.data_dir / "mental_map.json")
        self.world_model = WorldModel(self.data_dir / "world_model.json")
        self.goals = GoalManager(self.data_dir / "goals.json")
        self.scheduler = TaskScheduler(self.data_dir / "scheduler.sqlite3")
        self.scheduler.register_handler("memory_housekeeping", self._scheduled_memory_housekeeping)
        self.scheduler.register_handler("dataset_audit", self._scheduled_dataset_audit)
        self.scheduler.register_handler("goal_review", self._scheduled_goal_review)
        self.attention = AttentionSystem()
        self.language = LanguageEngine(model=llm_model)
        self.learning = LearningEngine(self, self.data_dir / "dataset.json")

        if not self.memory.knowledge:
            self.memory.knowledge.extend(DEFAULTS)
            save_json(self.memory.knowledge_path, self.memory.knowledge)

        corpus = []
        for item in self.memory.knowledge:
            corpus.extend([item.get("question", ""), item.get("answer", "")])
        for row in self.learning.dataset.load():
            corpus.extend([row.get("question", ""), row.get("answer", ""),
                           row.get("text_a", ""), row.get("text_b", "")])
        self.encoder.fit_vocabulary(corpus)
        self._save_encoder()

        self.last_trace = {}
        self.last_question = ""

    def _save_encoder(self):
        save_json(self.data_dir / "semantic_encoder.json", self.encoder.state_dict())

    def _active_retrieval_encoder(self):
        if self.retrieval_encoder is self.encoder:
            return self.encoder
        try:
            # Inicializa o backend uma única vez antes de usá-lo no benchmark
            # ou na memória; o encoder retorna vetor zero para texto vazio.
            self.retrieval_encoder.encode_query("")
        except (ImportError, OSError, RuntimeError) as exc:
            self._retrieval_encoder_error = f"{type(exc).__name__}: {exc}"
            self.retrieval_encoder = self.encoder
            self.memory._embedding_cache.clear()
        return self.retrieval_encoder

    def _recall(self, text, limit=8):
        encoder = self._active_retrieval_encoder()
        try:
            return self.memory.recall(text, encoder, limit=limit)
        except (ImportError, OSError, RuntimeError) as exc:
            if encoder is self.encoder:
                raise
            self._retrieval_encoder_error = f"{type(exc).__name__}: {exc}"
            self.retrieval_encoder = self.encoder
            self.memory._embedding_cache.clear()
            return self.memory.recall(text, self.encoder, limit=limit)

    def _scheduled_memory_housekeeping(self, payload):
        """Manutenção conservadora: poda apenas além do limite já configurado."""
        before = len(self.memory.episodes)
        if before > self.memory.max_items:
            self.memory.episodes = self.memory.episodes[-self.memory.max_items:]
            save_json(self.memory.episodes_path, self.memory.episodes)
        cache_before = len(self.memory._embedding_cache)
        if cache_before > self.memory.max_items * 2:
            self.memory._embedding_cache.clear()
        return {"episodes_before": before, "episodes_after": len(self.memory.episodes),
                "embedding_cache_before": cache_before,
                "embedding_cache_after": len(self.memory._embedding_cache)}

    def _scheduled_dataset_audit(self, payload):
        return self.learning.dataset.audit_splits()

    def _scheduled_goal_review(self, payload):
        goals = self.goals.list_goals()
        active = [goal for goal in goals if goal.get("status") == "active"]
        actions = []
        for goal in active:
            for step in self.goals.next_actions(goal["id"]):
                actions.append({"goal_id": goal["id"], "goal_title": goal["title"],
                                "step": step})
        return {"active_goals": len(active), "available_actions": actions[:100]}

    def respond(self, message, use_language=True):
        text = str(message).strip()
        if not text:
            return "Digite uma mensagem para começarmos."

        signal = self.eeg.synthesize(profile={
            "delta": .12, "theta": .24, "alpha": .32, "beta": .25, "gamma": .07
        })
        energies = self.eeg.band_energy(signal)
        eeg_state = self.eeg.cognitive_state(energies)
        vector = self.encoder.encode(text)
        output, hidden = self.network.forward(
            vector, modulation=.8 + eeg_state["focus"] * .4
        )

        self.mental_map.observe(text)
        ranked = self._recall(text, limit=8)
        candidates = [
            {"question": item.get("question", ""), "answer": item.get("answer", ""),
             "priority": score}
            for score, item in ranked
        ]
        focused = self.attention.allocate(
            text, candidates, eeg_state, self.mental_map, limit=5
        )
        attention_state = {
            "focus": eeg_state.get("focus", 0.0),
            "priority": focused[0][0] if focused else 0.0
        }
        selected, confidence = self.cognition.decide(ranked, attention_state)
        memory_context = [
            {"question": item.get("question"), "answer": item.get("answer")}
            for _, item in ranked[:3]
        ]
        concepts = self.mental_map.associate(text, limit=8)
        world_facts = self.world_model.search(text, limit=5)
        goal_context = self.goals.active_context(limit=5)
        history = self.attention.working.context(limit=6)
        llm_answer = self.language.generate(
            text, memory_context, concepts, history,
            world_facts=world_facts, goals=goal_context
        ) if use_language else None

        if llm_answer:
            answer, source = llm_answer, "local_llm"
        elif selected:
            answer, source = selected.get("answer", ""), "semantic_memory"
        elif world_facts:
            statements = [
                f"{fact.get('subject', '')} {fact.get('predicate', '')} "
                f"{fact.get('object', '')} (fonte: {fact.get('source', 'não informada')}; "
                f"confiança registrada: {float(fact.get('confidence', 0.0)):.2f})"
                for fact in world_facts
            ]
            answer, source = "Encontrei estes registros no modelo de mundo: " + "; ".join(statements), "world_model"
        else:
            answer = ("Ainda não encontrei uma resposta confiável. Você pode me ensinar "
                      "com /ensinar pergunta => resposta ou treinar pares semânticos.")
            source = "fallback"

        self.attention.attend_message("user", text, priority=attention_state["priority"])
        self.attention.attend_message("assistant", answer, priority=attention_state["priority"])
        self.last_question = text
        self.last_trace = {
            "eeg_bands": energies, "eeg_state": eeg_state,
            "attention": attention_state, "confidence": confidence,
            "spike_activity": sum(self.network.last_spike_counts),
            "active_neurons": sum(1 for count in self.network.last_spike_counts if count > 0),
            "network_output_norm": sum(x * x for x in output) ** .5,
            "response_source": source, "concepts": concepts,
            "world_facts_considered": len(world_facts),
            "world_fact_sources": sorted({str(fact.get("source", "unknown")) for fact in world_facts}),
            "active_goals_considered": len(goal_context),
            "encoder": "trainable_word_bigram_contrastive"
        }
        self.memory.add_episode("user", text)
        self.memory.add_episode("assistant", answer)
        return answer

    def learn(self, question, answer, reward=1.0, add_to_dataset=False,
              remember=True, reinforce=True):
        question, answer = str(question).strip(), str(answer).strip()
        if not question or not answer:
            raise ValueError("Pergunta e resposta não podem ficar vazias.")
        self.encoder.fit_vocabulary([question, answer])
        if remember:
            self.memory.remember(question, answer)
        if reinforce:
            vector = self.encoder.encode(question)
            _, hidden = self.network.forward(vector, track_plasticity=True)
            self.learner.reinforce(vector, hidden, reward)
            save_json(self.data_dir / "neural_weights.json", self.network.state_dict())
        self.mental_map.observe(question, weight=1.2)
        if add_to_dataset:
            self.learning.dataset.add(question, answer)
        self._save_encoder()

    def feedback(self, question, positive=True):
        if not str(question).strip():
            return
        vector = self.encoder.encode(question)
        _, hidden = self.network.forward(vector, track_plasticity=True)
        self.learner.reinforce(vector, hidden, 1.0 if positive else -.5)
        save_json(self.data_dir / "neural_weights.json", self.network.state_dict())

    def status(self):
        retrieval_status = (
            self.retrieval_encoder.status()
            if hasattr(self.retrieval_encoder, "status")
            else {"type": "native_semantic_encoder",
                  "dimensions": self.encoder.dimensions, "loaded": True}
        )
        return {
            **self.memory.stats(), **self.mental_map.stats(), **self.learner.stats(),
            "world_model": self.world_model.stats(),
            "planning": self.goals.stats(),
            "scheduler": self.scheduler.stats(),
            "dataset_audit": self.learning.dataset.audit_splits(),
            "architecture": "semantic_contrastive_recurrent_lif_memory_world_model_goal_manager",
            "encoder": {
                "type": "SemanticEncoder", "dimensions": self.encoder.dimensions,
                "vocabulary_size": len(self.encoder.vocab),
                "contrastive_updates": self.encoder.updates
            },
            "retrieval_encoder": retrieval_status,
            "retrieval_encoder_error": self._retrieval_encoder_error,
            "llm": self.language.status(), "last_trace": self.last_trace,
            "config": self.config.__dict__
        }
