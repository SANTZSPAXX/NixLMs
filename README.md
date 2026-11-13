# NixLMs

**NixLMs 0.4.0 — Semantic Learning Architecture** é uma IA experimental modular em Python, compatível com Windows e Google Colab. Esta versão introduz um encoder de palavras e bigramas treinável por pares contrastivos, memória vetorial híbrida e avaliação separada de recuperação e similaridade.

## O que mudou na 0.4

- **Semantic Encoder:** embeddings densos treináveis de tokens e bigramas, com vocabulário persistente e inicialização determinística.
- **Contrastive Learning:** pares positivos aproximam representações; pares negativos com similaridade acima da margem são afastados.
- **Semantic Memory:** recuperação combina similaridade vetorial (85%) e sobreposição lexical (15%); não executa a rede LIF para cada memória.
- **Memory Upsert:** ensinar ou treinar repetidamente uma mesma pergunta atualiza o registro em vez de duplicá-lo.
- **LIF:** telemetria de disparos real, traços de elegibilidade corrigidos e plasticidade acumulada apenas durante aprendizagem/feedback explícitos.
- **Evaluation Engine:** métricas separadas de recuperação QA e classificação de pares contrastivos.
- **Ollama:** integração opcional com endpoint localhost; endereços remotos são recusados.

## Limitações importantes

O Semantic Encoder 0.4 é um modelo compacto treinável de embeddings de palavras e bigramas, não um Transformer contextual pré-treinado. Ele começa com vetores determinísticos inicializados aleatoriamente e aprende similaridades a partir dos pares contrastivos fornecidos. Portanto, **não possui semântica geral garantida sem dados de treinamento suficientes e representativos**. A ordem local é parcialmente representada por bigramas; relações linguísticas complexas e contexto longo ainda não são modelados adequadamente.

O HashEncoder permanece no código apenas para compatibilidade. A rede LIF/STDP é experimental e não substitui o encoder semântico. As métricas são proxies de tarefas específicas, não prova de compreensão geral, consciência ou senciência.

## Requisitos

- Python 3.10 ou superior.
- Núcleo sem dependências externas obrigatórias.
- Execução em CPU; GPU não é necessária.
- Para máquinas com 8 GB de RAM, mantenha o LLM opcional desativado ou use um modelo Ollama pequeno.

## Windows

```powershell
python neural_core.py
```

Ou execute `iniciar_neural.bat`.

## Google Colab

Abra [NixLMs_Colab.ipynb](https://colab.research.google.com/github/SANTZSPAXX/NixLMs/blob/main/NixLMs_Colab.ipynb). A sessão do Colab é temporária; copie o diretório `data/` para armazenamento persistente se quiser preservar pesos, vocabulário e memória.

## Treinamento

O dataset inicial está em `datasets/starter_ptbr.jsonl`. Ele contém exemplos QA e pares contrastivos:

- QA: `question`, `answer`, `split`.
- Par: `type: "pair"`, `text_a`, `text_b`, `label` (1 = similar; 0 = diferente), `split`.

No terminal:

```text
/importar datasets/starter_ptbr.jsonl
/treinar 5
/avaliar
```

Para criar pares manualmente:

```text
/ensinar-par estou feliz || estou contente || 1
/ensinar-par o cachorro persegue o gato || o gato persegue o cachorro || 0
/treinar 5
```

O conjunto de teste não é utilizado pelo treinamento. Separe pares de teste que não sejam simples duplicatas ou reformulações triviais dos pares de treino.

## Memória e persistência

Os arquivos em `data/` incluem:

- `semantic_encoder.json`: vocabulário, embeddings e contagem de atualizações.
- `knowledge.json`: conhecimento QA.
- `episodes.json`: histórico episódico.
- `mental_map.json`: grafo associativo.
- `neural_weights.json`: pesos LIF e elegibilidade.
- `dataset.json`: exemplos locais de treinamento.

Faça backup do diretório `data/` antes de trocar versões ou realizar treinamento extenso.

## Testes

```powershell
python -m unittest discover -s tests -v
```

A CI executa a suíte em versões suportadas do Python e em Windows/Linux.

## Segurança e privacidade

O adaptador Ollama aceita somente `localhost`, `127.0.0.1` ou `::1`. Não inclua dados pessoais ou confidenciais nos datasets sem autorização e base legal. O núcleo não acessa sensores nem dispositivos.

## Arquitetura

`nixlms_core/` contém encoder, rede LIF, memória, atenção, mapa mental, aprendizagem, cognição, EEG sintético e adaptador linguístico opcional.
