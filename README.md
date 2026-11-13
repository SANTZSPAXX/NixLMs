# NixLMs

**NixLMs 0.2.0 — Neural Core Hybrid / All** é uma plataforma experimental em Python para Windows e Google Colab.

## Componentes
- Protótipo lexical legado: `nixlms.py`.
- Neural Core: rede LIF (*Leaky Integrate-and-Fire*), osciladores sintéticos inspirados em EEG, atenção heurística, memória semântica/episódica e feedback Hebbiano.
- Persistência JSON em `data/`.
- Execução offline com biblioteca padrão do Python.

## Requisitos
- Python 3.10 ou superior.
- Sem dependências externas; CPU suficiente, GPU opcional e desnecessária.

## Windows
Execute `iniciar_neural.bat` ou `python neural_core.py`. O protótipo antigo continua disponível por `python nixlms.py`.

## Google Colab
Abra [NixLMs_Colab.ipynb](https://colab.research.google.com/github/SANTZSPAXX/NixLMs/blob/main/NixLMs_Colab.ipynb) e execute em ordem. Ou:
```python
!git clone https://github.com/SANTZSPAXX/NixLMs.git
%cd NixLMs
from nixlms_core import NixLMsNeuralCore
ia = NixLMsNeuralCore()
print(ia.respond('Olá, NixLMs'))
```

## Comandos
- `/ensinar pergunta => resposta`: armazena conhecimento e aplica atualização Hebbiana limitada.
- `/status`: estado e contadores.
- `/eeg`: bandas sintéticas da última inferência.
- `/positivo` e `/negativo`: feedback simples à última entrada.
- `/ajuda` e `/sair`.

## Estrutura
```text
NixLMs/
├── nixlms.py
├── neural_core.py
├── nixlms_core/ (config, encoding, eeg, neural, memory, cognition, learner, agent, utils)
├── tests/
├── NixLMs_Colab.ipynb
├── iniciar_neural.bat
└── data/ (criado automaticamente)
```

## Testes
`python -m unittest discover -s tests -v`

## Limitações científicas e técnicas
O EEG é **sintético**: não acessa sensores nem fornece diagnóstico. As bandas são sinais experimentais de modulação, não equivalentes diretos de estados mentais. A codificação é lexical por hashing, não embedding semântico pré-treinado. A rede LIF é didática, não é um LLM generativo e não demonstra consciência ou senciência. O feedback Hebbiano é local e limitado, não treinamento supervisionado ponta a ponta. A memória é gravada em `data/`; faça backup antes de experimentos. Sensores e dados pessoais exigem autorização explícita.
