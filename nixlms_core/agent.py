from pathlib import Path
from .config import CoreConfig
from .eeg import EEGInspiredEngine
from .neural import LIFNetwork
from .encoding import HashEncoder
from .memory import MemorySystem
from .cognition import CognitiveEngine
from .learner import FeedbackLearner
from .mental_map import MentalMap
from .attention import AttentionSystem
from .language import LanguageEngine
from .learning import LearningEngine
from .utils import save_json,load_json

DEFAULTS=[
 {"question":"oi olá bom dia boa tarde boa noite","answer":"Olá! Sou a NixLMs. Como posso ajudar?"},
 {"question":"quem é você qual seu nome","answer":"Sou a NixLMs, uma IA experimental modular com rede recorrente LIF, mapa mental, atenção e memória."},
 {"question":"como você funciona arquitetura","answer":"Integro uma rede recorrente pulsante, osciladores sintéticos inspirados em EEG, grafo de conceitos, atenção dinâmica, memória e um LLM local opcional."},
 {"question":"o que é eeg","answer":"EEG é eletroencefalografia: registro da atividade elétrica cerebral por eletrodos. Aqui uso oscilações sintéticas para experimentação, não dados clínicos."},
 {"question":"obrigado valeu","answer":"Por nada! Vamos continuar evoluindo a NixLMs."},
]

class NixLMsNeuralCore:
    def __init__(self,data_dir=None,config=None,llm_model=None):
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
        self.learner=FeedbackLearner(self.network)
        self.mental_map=MentalMap(self.data_dir/"mental_map.json")
        self.attention=AttentionSystem()
        self.language=LanguageEngine(model=llm_model)
        self.learning=LearningEngine(self,self.data_dir/"dataset.json")
        self.last_trace={}; self.last_question=""
        if not self.memory.knowledge:
            self.memory.knowledge.extend(DEFAULTS); save_json(self.memory.knowledge_path,self.memory.knowledge)

    def respond(self,message,use_language=True):
        text=message.strip()
        if not text: return "Digite uma mensagem para começarmos."
        signal=self.eeg.synthesize(profile={"delta":.12,"theta":.24,"alpha":.32,"beta":.25,"gamma":.07})
        energies=self.eeg.band_energy(signal); eeg_state=self.eeg.cognitive_state(energies)
        vector=self.encoder.encode(text)
        output,hidden=self.network.forward(vector,modulation=.8+eeg_state["focus"]*.4)
        self.mental_map.observe(text)
        ranked=self.memory.recall(text,self.encoder,self.network,limit=8)
        candidates=[{"question":item.get("question",""),"answer":item.get("answer",""),"priority":1.0/(i+1)} for i,(_,item) in enumerate(ranked)]
        focused=self.attention.allocate(text,candidates,eeg_state,self.mental_map,limit=5)
        attention_state={"focus":eeg_state.get("focus",0.0),"priority":focused[0][0] if focused else 0.0}
        selected,confidence=self.cognition.decide(ranked,attention_state)
        memory_context=[{"question":item.get("question"),"answer":item.get("answer")} for _,item in ranked[:3]]
        concepts=self.mental_map.associate(text,limit=8)
        history=self.attention.working.context(limit=6)
        llm_answer=self.language.generate(text,memory_context,concepts,history) if use_language else None
        if llm_answer: answer=llm_answer; source="local_llm"
        elif selected: answer=selected.get("answer",""); source="retrieval"
        else:
            answer="Ainda não encontrei uma resposta confiável. Você pode me ensinar com /ensinar pergunta => resposta ou ativar um LLM local."
            source="fallback"
        self.attention.attend_message("user",text,priority=attention_state["priority"])
        self.attention.attend_message("assistant",answer,priority=attention_state["priority"])
        self.last_question=text
        self.last_trace={"eeg_bands":energies,"eeg_state":eeg_state,"attention":attention_state,"confidence":confidence,
                         "spike_activity":sum(1 for x in hidden if x>0),"network_output_norm":sum(x*x for x in output)**.5,
                         "response_source":source,"concepts":concepts}
        self.memory.add_episode("user",text); self.memory.add_episode("assistant",answer)
        return answer

    def learn(self,question,answer,reward=1.0,add_to_dataset=False):
        if not question.strip() or not answer.strip(): raise ValueError("Pergunta e resposta não podem ficar vazias.")
        self.memory.remember(question,answer)
        vector=self.encoder.encode(question); _,hidden=self.network.forward(vector)
        self.learner.reinforce(vector,hidden,reward)
        self.mental_map.observe(question,weight=1.2)
        if add_to_dataset: self.learning.dataset.add(question,answer)
        save_json(self.data_dir/"neural_weights.json",self.network.state_dict())

    def feedback(self,question,positive=True):
        if not question.strip(): return
        vector=self.encoder.encode(question); _,hidden=self.network.forward(vector)
        self.learner.reinforce(vector,hidden,1.0 if positive else -.5)
        save_json(self.data_dir/"neural_weights.json",self.network.state_dict())

    def status(self):
        return {**self.memory.stats(),**self.mental_map.stats(),**self.learner.stats(),
                "architecture":"hybrid_recurrent_lif_mental_map_attention_learning_local_llm",
                "llm":self.language.status(),"last_trace":self.last_trace,"config":self.config.__dict__}
