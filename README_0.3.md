# NixLMs 0.3.0 — Cognitive Hybrid Architecture

## Subsistemas
- **Neural Core:** rede recorrente LIF, sinapses recorrentes, traços de elegibilidade e plasticidade STDP aproximada modulada por recompensa.
- **Mental Map:** grafo local persistente de conceitos e coocorrências.
- **Attention System:** seleção dinâmica de contexto e memória de trabalho limitada.
- **Learning Engine:** dataset JSON, treino incremental e avaliação top-5 hit rate/MRR.
- **Language Engine:** integração opcional com LLM local via Ollama em localhost.

## Windows
Python 3.10+. Execute `python neural_core.py` ou `iniciar_neural.bat`. Testes: `python -m unittest discover -s tests -v`.

## LLM local para computadores modestos
Instale Ollama e rode:
```powershell
ollama pull qwen2.5:0.5b
ollama serve
python neural_core.py
```
O adaptador acessa somente `http://127.0.0.1:11434`. Se o serviço não estiver disponível, o sistema usa a memória e recuperação local. Em 8 GB de RAM, prefira o modelo 0.5B, feche aplicativos pesados e espere latência maior em CPU. `qwen2.5:1.5b` exige mais memória.

Variáveis: `NIXLMS_LLM_MODEL=qwen2.5:0.5b`, `OLLAMA_HOST=http://127.0.0.1:11434`, `NIXLMS_LLM_ENABLED=0` para desativar.

## Dataset e avaliação
`/ensinar pergunta => resposta` adiciona exemplos ao dataset. `/treinar 2` executa duas épocas de aprendizagem incremental. `/avaliar` calcula taxa de recuperação top-5 e MRR. Dataset: `data/dataset.json`. Para separar teste, adicione registros com `split: test`.

## Colab
O notebook usa o mesmo núcleo, sem instalar pacotes. O LLM fica desativado por padrão na sessão Colab; a execução base usa memória e recuperação local. Para LLM, seria necessário iniciar Ollama/servidor de inferência dentro da sessão Colab. Os dados da sessão são efêmeros, salvo persistência configurada pelo usuário.

## Limitações
STDP/LIF são aproximações experimentais, não modelos neurobiológicos validados. O grafo usa coocorrência lexical. As métricas avaliam recuperação de exemplos, não qualidade geral de linguagem. O LLM é pequeno e limitado. EEG continua sintético; não há aquisição biomédica, diagnóstico ou leitura de estados mentais.
