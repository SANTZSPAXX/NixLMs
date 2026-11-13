# NixLMs Neural Core 0.2.0

Implementação experimental híbrida em Python puro: codificação lexical determinística, rede LIF pequena, plasticidade Hebbiana local, osciladores sintéticos inspirados em EEG, atenção heurística, memória semântica/episódica e feedback.

## Requisitos
- Python 3.10 ou superior.
- Sem dependências externas; CPU suficiente. O projeto não exige GPU.

## Windows
Extraia o repositório e execute `iniciar_neural.bat` ou `python neural_core.py`.

## Google Colab
Abra o notebook [NixLMs_Colab.ipynb](https://colab.research.google.com/github/SANTZSPAXX/NixLMs/blob/main/NixLMs_Colab.ipynb) ou execute:
```python
!git clone https://github.com/SANTZSPAXX/NixLMs.git
%cd NixLMs
from nixlms_core import NixLMsNeuralCore
ai = NixLMsNeuralCore()
print(ai.respond("Olá, NixLMs"))
```

## Comandos
- `/ensinar pergunta => resposta`: grava conhecimento e aplica atualização Hebbiana limitada.
- `/status`: mostra estado da memória e arquitetura.
- `/eeg`: mostra bandas da última inferência.
- `/positivo` e `/negativo`: feedback simples associado à última entrada.
- `/ajuda`, `/sair`.

## Módulos
`config.py`, `encoding.py`, `eeg.py`, `neural.py`, `memory.py`, `cognition.py`, `learner.py`, `agent.py`.

## Limitações
O EEG é sintético; não há aquisição de sensores, diagnóstico ou interpretação clínica. As bandas são modulação experimental, não equivalentes diretos de estados mentais. HashEncoder é lexical, não embedding semântico pré-treinado. A rede LIF é didática: não é um LLM, não gera linguagem livre e não possui consciência. O feedback Hebbiano não equivale a treinamento supervisionado ponta a ponta. Os dados ficam em `data/`; faça backup antes de experimentos.

## Testes
`python -m unittest discover -s tests -v`
