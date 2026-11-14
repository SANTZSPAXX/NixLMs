import os
from datetime import datetime
from pathlib import Path
from .config import CoreConfig
from .eeg import EEGInspiredEngine
from .neural import LIFNetwork
from .encoding import SemanticEncoder
from .pretrained_encoder import TransformersSentenceEncoder
from .memory import MemorySystem
from .episodic import EpisodicMemory
from .cognition import CognitiveEngine
from .learner import FeedbackLearner
from .mental_map import MentalMap
from .world_model import WorldModel
from .planning import GoalManager
from .scheduler import TaskScheduler
from .attention import AttentionSystem
from .language import LanguageEngine
from .learning import LearningEngine
from .utils import save_json, load_json, normalize


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
        self.episodic = EpisodicMemory(
            self.data_dir / "episodic_memory.json", self.config.max_memory_items
        )
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

    def _compress_neural_target(self, vector):
        """Projeta o embedding semântico para a dimensão da leitura de saída LIF."""
        size = self.network.output_size
        buckets = [[] for _ in range(size)]
        for index, value in enumerate(vector):
            buckets[index % size].append(float(value))
        compressed = [
            sum(bucket) / len(bucket) if bucket else 0.0
            for bucket in buckets
        ]
        magnitude = sum(value * value for value in compressed) ** .5
        return [value / magnitude for value in compressed] if magnitude else compressed

    @staticmethod
    def _cosine_similarity(left, right):
        if len(left) != len(right):
            return 0.0
        dot = sum(float(a) * float(b) for a, b in zip(left, right))
        left_norm = sum(float(a) ** 2 for a in left) ** .5
        right_norm = sum(float(b) ** 2 for b in right) ** .5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def _lif_recall(self, neural_output, limit=3):
        """Recupera respostas pela representação produzida pela rede LIF treinada."""
        if self.network.output_updates <= 0:
            return []
        ranked = []
        seen = set()
        for item in self.memory.knowledge:
            answer = str(item.get("answer", "")).strip()
            key = normalize(answer)
            if not answer or not key or key in seen:
                continue
            seen.add(key)
            target = self._compress_neural_target(self.encoder.encode(answer))
            score = self._cosine_similarity(neural_output, target)
            ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        threshold = float(self.config.lif_retrieval_threshold)
        return [
            {"question": item.get("question", ""), "answer": item.get("answer", ""),
             "score": float(score), "source": "lif_associative_readout"}
            for score, item in ranked[:max(0, int(limit))]
            if score >= threshold
        ]

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
        episodic_report = self.episodic.prune()
        cache_before = len(self.memory._embedding_cache)
        if cache_before > self.memory.max_items * 2:
            self.memory._embedding_cache.clear()
        return {"episodes_before": before, "episodes_after": len(self.memory.episodes),
                "embedding_cache_before": cache_before,
                "embedding_cache_after": len(self.memory._embedding_cache),
                "episodic_memory": episodic_report}

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

    @staticmethod
    def _is_greeting(message):
        query = normalize(message)
        return query in {
            'oi', 'ola', 'oi ola', 'bom dia', 'boa tarde', 'boa noite',
            'e ai', 'tudo bem', 'ola tudo bem',
        }

    @staticmethod
    def _is_person_question(message):
        query = normalize(message)
        return query.startswith('quem foi ') or query.startswith('quem era ')

    @staticmethod
    def _memory_is_relevant(query, item, score):
        query_tokens = set(normalize(query).split())
        item_tokens = set(normalize(item.get('question', '')).split())
        overlap = len(query_tokens & item_tokens) / max(1, len(query_tokens))
        return float(score) >= 0.55 and (overlap >= 0.20 or float(score) >= 0.82)

    @staticmethod
    def _validate_llm_answer(question, answer):
        if not answer or not str(answer).strip():
            return False, 'empty_answer'
        query = normalize(question)
        response = normalize(answer)
        if response == query:
            return False, 'question_echo'
        query_tokens = set(query.split())
        response_tokens = set(response.split())
        if len(query_tokens) >= 3 and len(query_tokens & response_tokens) / len(query_tokens) >= 0.85:
            return False, 'near_question_echo'
        greeting_starts = ('ola sou a nixlms', 'ola sou nixlms', 'como posso ajudar', 'oi sou a nixlms', 'sou a nixlms uma ia')
        if any(response.startswith(prefix) for prefix in greeting_starts) and not NixLMsNeuralCore._is_greeting(question):
            return False, 'irrelevant_greeting'
        if NixLMsNeuralCore._is_person_question(question):
            entity_tokens = [token for token in query_tokens if token not in {'quem', 'foi', 'era', 'o', 'a', 'um', 'uma', 'de', 'do', 'da'}]
            if entity_tokens and not any(token in response_tokens for token in entity_tokens):
                return False, 'requested_person_not_mentioned'
        return True, None

    @staticmethod
    def _user_name_response(message):
        query = normalize(message)
        if query in {'qual meu nome', 'qual e meu nome', 'voce sabe meu nome', 'como eu me chamo', 'lembra meu nome'}:
            return 'Ainda não sei seu nome. Você pode me dizer como prefere ser chamado?'
        return None
    @staticmethod
    def _temporal_response(message, now=None):
        """Responde consultas simples de data/hora com o relógio local do runtime."""
        query = normalize(message)
        words = set(query.split())
        asks_time = bool(words & {"hora", "horas", "horario"}) and bool(
            words & {"agora", "sao", "atual", "atualmente"}
        )
        asks_date = (
            "hoje" in words
            or ("data" in words and bool(words & {"qual", "hoje"}))
            or ("dia" in words and bool(words & {"hoje", "semana"}))
        )
        if not asks_date and not asks_time:
            return None
        current = now or datetime.now().astimezone()
        weekdays = (
            "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo",
        )
        date_text = f"{weekdays[current.weekday()]}, {current:%d/%m/%Y}"
        time_text = current.strftime("%H:%M")
        if asks_date and asks_time:
            return f"Hoje é {date_text}. Agora são {time_text}."
        if asks_date:
            return f"Hoje é {date_text}."
        return f"Agora são {time_text}."

    def respond(self, message, use_language=True, record=True):
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
        lif_ranked = self._lif_recall(output, limit=3)

        if record:
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
        attention_scores = {
            normalize(candidate.get("question", "")): float(score)
            for score, candidate in focused
            if normalize(candidate.get("question", ""))
        }
        attended_ranked = [
            (
                0.8 * retrieval_score
                + 0.2 * attention_scores.get(normalize(item.get("question", "")), 0.0),
                item,
            )
            for retrieval_score, item in ranked
        ]
        attended_ranked.sort(key=lambda pair: pair[0], reverse=True)
        relevant_ranked = [
            (score, item) for score, item in attended_ranked
            if self._memory_is_relevant(text, item, score)
        ]
        selected, confidence = self.cognition.decide(relevant_ranked, attention_state)
        memory_context = [
            {"question": item.get("question"), "answer": item.get("answer")}
            for _, item in relevant_ranked[:3]
        ]
        if lif_ranked:
            memory_context.insert(0, {
                "question": "Candidato de resposta recuperado pela leitura associativa LIF",
                "answer": lif_ranked[0]["answer"],
                "score": lif_ranked[0]["score"],
                "source": "lif_associative_readout",
            })
        episodic_encoder = self._active_retrieval_encoder()
        episodic_context = self.episodic.recall(text, episodic_encoder, limit=3)
        for _, episode in episodic_context:
            feedback = episode.get("feedback") or "sem feedback"
            memory_context.append({
                "question": f"Experiência anterior: {episode.get('user_input', '')}",
                "answer": (f"Resposta anterior: {episode.get('assistant_output', '')} "
                           f"(feedback: {feedback}; origem: {episode.get('source', 'unknown')})")
            })
        concepts = self.mental_map.associate(text, limit=8)
        world_facts = self.world_model.search(text, limit=5)
        goal_context = self.goals.active_context(limit=5)
        history = self.attention.working.context(limit=6)
        temporal_answer = self._temporal_response(text)
        user_name_answer = self._user_name_response(text)
        greeting_answer = 'Olá! Sou a NixLMs. Como posso ajudar?' if self._is_greeting(text) else None
        llm_attempted = (use_language and temporal_answer is None and user_name_answer is None and greeting_answer is None)
        llm_answer = self.language.generate(
            text, memory_context, concepts, history,
            world_facts=world_facts, goals=goal_context,
            neural_state={
                "retrieved_responses": lif_ranked,
                "output_updates": self.network.output_updates,
                "output_norm": sum(value * value for value in output) ** .5,
                "readout_trained": self.network.output_updates > 0,
            }
        ) if llm_attempted else None
        llm_rejection_reason = None
        if llm_answer:
            valid_answer, llm_rejection_reason = self._validate_llm_answer(text, llm_answer)
            if not valid_answer:
                llm_answer = None

        if temporal_answer:
            answer, source = temporal_answer, 'runtime_datetime'
            confidence = 1.0
        elif user_name_answer:
            answer, source = user_name_answer, 'unknown_user_profile'
            confidence = 1.0
        elif greeting_answer:
            answer, source = greeting_answer, 'greeting_rule'
            confidence = 1.0
        elif llm_answer:
            answer, source = llm_answer, 'lif_conditioned_llm' if lif_ranked else 'local_llm'
        elif lif_ranked:
            answer, source = lif_ranked[0]["answer"], "lif_associative_readout"
            confidence = max(confidence, lif_ranked[0]["score"])
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
        elif llm_rejection_reason == 'requested_person_not_mentioned':
            answer = ('Não consegui identificar essa pessoa com segurança. Você se refere a Pedro Álvares Cabral ou a outra pessoa?'
                      if 'pedro' in normalize(text) else 'Não consegui identificar essa pessoa com segurança. Pode informar o nome completo?')
            source = 'entity_abstention'
        else:
            answer = ("Ainda não encontrei uma resposta confiável. Você pode me ensinar "
                      "com /ensinar pergunta => resposta ou treinar pares semânticos.")
            source = 'fallback'

        if record:
            self.attention.attend_message("user", text, priority=attention_state["priority"])
            self.attention.attend_message("assistant", answer, priority=attention_state["priority"])
        self.last_question = text
        self.last_trace = {
            "eeg_bands": energies, "eeg_state": eeg_state,
            "attention": attention_state, "confidence": confidence,
            "attention_reranking_applied": bool(focused),
            "attention_reranking_weights": {"retrieval": 0.8, "attention": 0.2},
            "spike_activity": sum(self.network.last_spike_counts),
            "active_neurons": sum(1 for count in self.network.last_spike_counts if count > 0),
            "network_output_norm": sum(x * x for x in output) ** .5,
            "lif_output_updates": self.network.output_updates,
            "lif_retrieval_candidates": len(lif_ranked),
            "lif_retrieval_score": lif_ranked[0]["score"] if lif_ranked else None,
            "lif_candidate_conditioned_generation": bool(lif_ranked and llm_answer),
            "neural_generation_path": (
                "lif_conditioned_llm" if lif_ranked and llm_answer else
                "lif_associative_readout" if lif_ranked else
                "llm_without_trained_lif_readout" if llm_answer else "no_trained_lif_readout"
            ),
            "response_source": source, "concepts": concepts,
            "llm_error": self.language.last_error if llm_attempted else None,
            "llm_rejection_reason": llm_rejection_reason,
            "relevant_memories_used": len(relevant_ranked),
            "retrieval_encoder_error": self._retrieval_encoder_error,
            "world_facts_considered": len(world_facts),
            "world_fact_sources": sorted({str(fact.get("source", "unknown")) for fact in world_facts}),
            "active_goals_considered": len(goal_context),
            "episodic_experiences_recalled": len(episodic_context),
            "encoder": "trainable_word_bigram_contrastive"
        }
        if record:
            self.memory.add_episode("user", text)
            self.memory.add_episode("assistant", answer)
            self.episodic.record(
                text, answer,
                context={"response_source": source, "confidence": confidence,
                         "world_fact_sources": self.last_trace["world_fact_sources"]},
                outcome="response_generated", source=source,
                importance=max(0.0, min(1.0, float(confidence))),
            )
    
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
            target = self._compress_neural_target(self.encoder.encode(answer))
            self.network.train_output(
                hidden, target, learning_rate=self.config.lif_output_learning_rate
            )
            self.learner.reinforce(vector, hidden, reward)
            save_json(self.data_dir / "neural_weights.json", self.network.state_dict())
        self.mental_map.observe(question, weight=1.2)
        if add_to_dataset:
            self.learning.dataset.add(question, answer)
        self._save_encoder()

    def feedback(self, question, positive=True):
        """Avalia o episódio correspondente sem alterar pesos neurais sem treino validado."""
        if not str(question).strip():
            return False
        episode = self.episodic.set_feedback(question, positive)
        return episode is not None

    def status(self):
        retrieval_status = (
            self.retrieval_encoder.status()
            if hasattr(self.retrieval_encoder, "status")
            else {"type": "native_semantic_encoder",
                  "dimensions": self.encoder.dimensions, "loaded": True}
        )
        return {
            **self.memory.stats(), **self.episodic.stats(), **self.mental_map.stats(), **self.learner.stats(),
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
