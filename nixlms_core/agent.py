from pathlib import Path
from .config import CoreConfig
from .eeg import EEGInspiredEngine
from .neural import LIFNetwork
from .encoding import HashEncoder
from .memory import MemorySystem
from .cognition import CognitiveEngine
from .learner import FeedbackLearner
from .utils import save_json, load_json

DEFAULTS=[
 {"question":"oi olá bom dia boa tarde boa noite","answer":"Olá! Sou a NixLMs Neural Core. Como posso ajudar?"},
 {"question":"quem é você qual seu nome","answer":"Sou a NixLMs, uma IA experimental modular com núcleo neural LIF, memória e mecanismos cognitivos."},
 {"question":"como você funciona arquitetura","answer":"Integro codificação textual, rede pulsante LIF, sinais oscilatórios sintéticos inspirados em EEG, atenção, memória e feedback Hebbiano."},
 {"question":"o que é eeg","answer":"EEG é eletroencefalografia: registro da atividade elétrica cerebral por eletrodos. Aqui uso oscilações sintéticas para experimentação, não dados clínicos."},
 {"question":"obrigado valeu","answer":"Por nada! Vamos continuar evoluindo a NixLMs."},
]

class NixLMsNeuralCore:
    def __init__(self, data_dir=None, config=None):
        self.config=config or CoreConfig()
        self.data_dir=Path(data_dir or Path(__file__).resolve().parents[1]/"data")
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.encoder=HashEncoder(self.config.input_size)
        self.network=LIFNetwork(self.config.input_size,self.config.hidden_size,self.config.output_size,self.config.steps,self.config.threshold,self.config.leak,self.config.seed,self.config.learning_rate)
        weights=load_json(self.data_dir/"neural_weights.json",None)
        if weights: self.network.load_state_dict(weights)
        self.eeg=EEGInspiredEngine(self.config.seed)
        self.memory=MemorySystem(self.data_dir,self.config.max_memory_items)
        self.cognition=CognitiveEngine(self.config.confidence_threshold)
        self.learner=FeedbackLearner(self.network); self.last_trace={}
        if not self.memory.knowledge:
            self.memory.knowledge.extend(DEFAULTS); save_json(self.memory.knowledge_path,self.memory.knowledge)

    def respond(self, message):
        text=message.strip()
        if not text: return "Digite uma mensagem para começarmos."
        signal=self.eeg.synthesize(profile={"delta":.12,"theta":.24,"alpha":.32,"beta":.25,"gamma":.07})
        energies=self.eeg.band_energy(signal); eeg_state=self.eeg.cognitive_state(energies)
        vector=self.encoder.encode(text)
        output,hidden=self.network.forward(vector,modulation=.8+eeg_state["focus"]*.4)
        attention=self.cognition.attend(text,eeg_state)
        ranked=self.memory.recall(text,self.encoder,self.network,limit=5)
        selected,confidence=self.cognition.decide(ranked,attention)
        answer=selected.get("answer","") if selected else ("Ainda não encontrei uma resposta suficientemente confiável. Você pode me ensinar com /ensinar pergunta => resposta.")
        self.last_trace={"eeg_bands":energies,"eeg_state":eeg_state,"attention":attention,"confidence":confidence,"spike_activity":sum(1 for x in hidden if x>0),"network_output_norm":sum(x*x for x in output)**.5}
        self.memory.add_episode("user",text); self.memory.add_episode("assistant",answer)
        return answer

    def learn(self, question, answer, reward=1.0):
        if not question.strip() or not answer.strip(): raise ValueError("Pergunta e resposta não podem ficar vazias.")
        self.memory.remember(question,answer)
        vector=self.encoder.encode(question); _,hidden=self.network.forward(vector)
        self.learner.reinforce(vector,hidden,reward)
        save_json(self.data_dir/"neural_weights.json",self.network.state_dict())

    def feedback(self, question, positive=True):
        if not question.strip(): return
        vector=self.encoder.encode(question); _,hidden=self.network.forward(vector)
        self.learner.reinforce(vector,hidden,1.0 if positive else -0.5)
        save_json(self.data_dir/"neural_weights.json",self.network.state_dict())

    def status(self):
        return {**self.memory.stats(),**self.learner.stats(),"architecture":"hybrid_lif_eeg_cognitive","config":self.config.__dict__}
