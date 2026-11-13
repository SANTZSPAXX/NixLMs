# NixLMs

**NixLMs 0.3.0 — Cognitive Hybrid Architecture** é uma IA experimental modular em Python, compatível com Windows e Google Colab.

## Arquitetura 0.3
- **Neural Core:** rede recorrente LIF, sinapses recorrentes, traços de elegibilidade e plasticidade STDP aproximada modulada por recompensa.
- **EEG-inspired:** osciladores sintéticos Delta, Theta, Alpha, Beta e Gamma.
- **Mental Map:** grafo persistente de conceitos e associações.
- **Attention System:** seleção dinâmica de contexto e memória de trabalho limitada.
- **Learning Engine:** datasets locais, treino incremental e avaliação de recuperação (hit rate top-5 e MRR).
- **Language Engine:** integração opcional com LLM pequeno executado localmente via Ollama.
- **Memória:** armazenamento semântico e episódico em JSON.

## Requisitos
Python 3.10+. O núcleo usa apenas a biblioteca padrão e funciona em CPU. GPU não é necessária.

## Windows
Execute `iniciar_neural.bat` ou `python neural_core.py`. O protótipo original segue disponível em `python nixlms.py`.

## LLM local (opcional)
Para máquinas com 8 GB de RAM e CPU sem GPU dedicada, comece pelo modelo pequeno:
```powershell
# Instale Ollama: https://ollama.com/download
ollama pull qwen2.5:0.5b
ollama serve
python neural_core.py
```
O adaptador conecta apenas a `http://127.0.0.1:11434`. Sem Ollama, a NixLMs continua funcionando com memória e recuperação local. O modelo pode ser lento em CPU; feche aplicativos pesados. Para trocar o modelo use `NIXLMS_LLM_MODEL`; para desativar `NIXLMS_LLM_ENABLED=0`.

## Google Colab
Abra [NixLMs_Colab.ipynb](https://colab.research.google.com/github/SANTZSPAXX/NixLMs/blob/main/NixLMs_Colab.ipynb). O notebook executa o núcleo sem LLM remoto. Para persistência, salve `data/` no Google Drive; o filesystem temporário do Colab pode ser apagado ao encerrar a sessão.

## Dataset, treino e avaliação
O conjunto inicial em português está em `datasets/starter_ptbr.jsonl`, com partições `train` e `test`. No terminal:
```text
/importar datasets/starter_ptbr.jsonl
/treinar 2
/avaliar
```
As métricas avaliam recuperação de exemplos conhecidos, não qualidade geral de linguagem. Para novos dados, use JSONL com campos `question`, `answer` e `split` (`train` ou `test`). Não inclua dados pessoais ou confidenciais sem base legal e autorização.

## Comandos
- `/ensinar pergunta => resposta`: grava conhecimento, atualiza o grafo e adiciona ao dataset.
- `/importar arquivo.jsonl`: importa dataset JSONL.
- `/treinar [epocas]`: aprendizagem incremental no dataset.
- `/avaliar`: métricas top-5 e MRR.
- `/mapa`: conceitos e associações.
- `/eeg`, `/llm`, `/status`, `/positivo`, `/negativo`, `/ajuda`, `/sair`.

## Testes
`python -m unittest discover -s tests -v`

## Estrutura
`nixlms_core/` contém os módulos `neural`, `eeg`, `mental_map`, `attention`, `memory`, `cognition`, `learning`, `language`, `learner`, `encoding`, `config`, `utils` e `agent`.

## Limitações
A rede LIF/STDP é uma aproximação didática, não neurobiologia validada. O mapa usa associações lexicais. As métricas avaliam recuperação de exemplos, não qualidade geral de linguagem. O LLM pequeno pode cometer erros. O EEG é sintético e não lê pensamentos, não acessa sensores nem realiza diagnósticos. A arquitetura não demonstra consciência ou senciência.
