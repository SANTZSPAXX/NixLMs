# NixLMs

**NixLMs 0.7 — Memória episódica e integração local** é uma IA experimental modular em Python, compatível com Windows e Google Colab. O núcleo permanece local-first e sem dependências externas obrigatórias.

## Evolução 0.5

- **Dataset Integrity:** importação JSONL transacional, auditoria de separação train/test e bloqueio de sobreposição textual entre QA e pares contrastivos.
- **World Model:** memória de fatos tipados com sujeito, relação, objeto, confiança, fonte e timestamps. Possíveis conflitos são apresentados sem resolução automática.
- **Goal Manager:** objetivos persistentes, etapas, dependências e lista de próximas ações. O módulo organiza planos, mas não executa ações.
- **Optional Multilingual Retrieval:** backend opcional `TransformersSentenceEncoder` para recuperação com embeddings pré-treinados, carregado sob demanda, somente CPU e arquivos locais/cache.
- **Native Neural Core:** o encoder treinável nativo continua alimentando a rede LIF e recebendo treinamento contrastivo.
- **Context Integration:** fatos e objetivos podem ser fornecidos ao LLM local Ollama como contexto identificado.
- **Benchmark Consistency:** recuperação híbrida usa a mesma fórmula e o contrato query/passage do sistema de memória.

## Memória episódica e aprendizagem experiencial (0.7 em desenvolvimento)

A memória episódica registra cada interação como uma experiência estruturada em `data/episodic_memory.json`, separada da memória de perguntas/respostas e do modelo de fatos.

Cada episódio inclui:
- Timestamp UTC e identificador único.
- Entrada do usuário e resposta produzida.
- Contexto de execução, origem da resposta e confiança estimada.
- Resultado registrado, importância, tags e feedback explícito.
- Recuperação por relevância lexical/semântica, recência e feedback.

O feedback `/positivo` e `/negativo` atualiza a avaliação do episódio correspondente e influencia a recuperação futura. Ele não altera pesos neurais: reforço da rede LIF exige treinamento explícito e avaliação separada. A recuperação episódica pode fornecer experiências anteriores ao LLM local como contexto, sem tratá-las como fatos verificados.

Limites: feedback não comprova que uma resposta está correta; episódios não são automaticamente convertidos em conhecimento factual; não há consolidação abstrativa nem alteração autônoma de pesos. A recuperação é uma heurística híbrida e deve ser avaliada em benchmark antes de qualquer alegação de melhoria geral.

## Agendador persistente (0.6)

O `TaskScheduler` usa SQLite e apenas a biblioteca padrão do Python. As tarefas sobrevivem ao reinício do processo e são executadas por handlers registrados explicitamente pelo runtime.

Handlers internos disponíveis:
- `memory_housekeeping` — poda conservadora de episódios acima do limite configurado e limpeza de cache excessivo.
- `dataset_audit` — verifica a integridade dos splits sem treinar nem modificar o dataset.
- `goal_review` — reúne objetivos ativos e etapas liberadas, sem alterar o plano.

Exemplos na CLI:
```text
/agenda listar
/agenda criar dataset_audit 3600
/agenda criar goal_review 1800
/agenda uma-vez memory_housekeeping 10
/agenda cancelar job-ID
/agenda executar
```

O worker automático é iniciado somente pela CLI. Aplicações que importam a biblioteca precisam chamar `ai.scheduler.start()` explicitamente e encerrá-lo com `ai.scheduler.stop()`. Tarefas recorrentes usam intervalo em segundos, não expressões cron nem calendário local.

Segurança e semântica:
- O banco armazena nome do handler e payload JSON; nunca serializa callables nem executa shell/comandos.
- Somente handlers registrados no código podem ser agendados.
- Há limite de tarefas ativas, tamanho de payload, tentativas e backoff exponencial.
- A reivindicação de tarefas usa transação `BEGIN IMMEDIATE`; o handler executa fora da transação.
- Leases são renovados durante a execução; tarefas abandonadas podem ser recuperadas após expiração.
- A entrega é *at-least-once*, não *exactly-once*. Handlers devem ser idempotentes.
- Cancelamento afeta tarefas pendentes; não interrompe um handler já em execução.
- Use o arquivo SQLite em disco local, não em filesystem de rede.

O agendador não treina modelos automaticamente, não altera pesos neurais, não acessa a rede, não executa ações externas e não transforma fatos em conhecimento sem validação. Para programar uma nova capacidade, implemente um handler explícito, idempotente e coberto por testes.

## Arquitetura atual

- **Semantic Encoder:** embeddings treináveis de palavras, bigramas e subwords de caracteres (n-gramas 3–5), inicialização determinística e aprendizado contrastivo. A sobreposição de subwords permite generalização para flexões e tokens OOV sem expandir o vocabulário durante a inferência; a expansão é limitada a 128 tokens e 32 caracteres por token.
- **LIF/STDP + Readout + Neural Decoder:** o readout LIF aprende uma representação semântica da resposta e condiciona um pequeno RNN autoregressivo que gera tokens um a um. Quando treinado e confiante, esse decoder é o caminho primário; o Ollama permanece como fallback quando a geração neural é rejeitada.
- **Memory:** recuperação híbrida lexical/semântica, memória QA e episódios persistentes.
- **Attention:** memória de trabalho e priorização de contexto.
- **Mental Map:** grafo associativo lexical.
- **World Model:** grafo local de fatos com proveniência e confiança.
- **Goal Manager:** registro de objetivos e dependências.
- **Language Engine:** Ollama local opcional, limitado a loopback; descobre modelos já instalados, seleciona um modelo local disponível sem executar downloads e expõe diagnóstico de conexão/erros.

Na CLI, use `/llm` para verificar conectividade, modelos instalados e o último erro. Use `/llm usar NOME_EXATO` para selecionar um modelo já instalado. Se o Ollama estiver ativo, mas não houver modelo, instale um manualmente (por exemplo, `ollama pull qwen2.5:0.5b`). A NixLMs não baixa modelos automaticamente. Saudações e perguntas simples de data/hora são tratadas por regras determinísticas; perguntas sobre o nome do usuário não inventam um perfil ausente. A recuperação QA exige relevância mínima antes de usar uma lembrança como resposta. Respostas do LLM que apenas repetem a pergunta, desviam para uma saudação ou omitem a pessoa perguntada são recusadas. Para as demais perguntas, o contexto recuperado é limitado por tamanho e explicitamente tratado como dado não confiável no prompt do modelo.

## Limitações importantes

O readout LIF continua sendo um mapeador associativo supervisionado para representações semânticas, não um gerador de tokens. Os pesos recorrentes internos da LIF ainda não recebem BPTT end-to-end nesta versão; o treinamento supervisionado ajusta o readout, e um módulo RNN separado realiza a geração linguística condicionada. A geração token a token é feita por um RNN autoregressivo pequeno, supervisionado por respostas QA e condicionado pelo vetor de saída LIF. Ele é treinado apenas com o split `train`, usa vocabulário limitado e pode sobreajustar datasets pequenos; não é um Transformer, não é pré-treinado e não oferece conhecimento geral. A NixLMs só o prioriza quando a sequência gerada passa pelos critérios mínimos de confiança e consistência; caso contrário, tenta Ollama quando habilitado ou usa os caminhos de recuperação/abstenção. A confiança atual é a média das probabilidades dos tokens escolhidos e ainda é heurística, não uma probabilidade calibrada; sua calibração deve usar o split `validation`.

O encoder nativo não é um Transformer pré-treinado. Ele aprende a partir dos pares fornecidos e não possui semântica geral garantida. O backend E5 opcional melhora a qualidade inicial da recuperação semântica, mas não treina automaticamente o encoder nativo nem prova raciocínio geral.

O modelo de mundo não extrai fatos automaticamente de texto; fatos são registrados explicitamente e devem ter fonte confiável. Conflitos não são decididos automaticamente. O Goal Manager não executa etapas nem autoriza ações. Visão e audição ainda não fazem parte do runtime desta versão.

As métricas são proxies de tarefas específicas, não prova de compreensão geral, consciência ou senciência.

## Requisitos

- Python 3.10 ou superior.
- Núcleo sem dependências externas obrigatórias.
- Execução em CPU; GPU não é necessária.
- Para máquinas com 8 GB de RAM, mantenha o LLM opcional pequeno e carregue o encoder pré-treinado apenas se houver memória disponível.

## Windows

```powershell
python neural_core.py
```

Ou execute `iniciar_neural.bat`.

## Google Colab

Abra [NixLMs_Colab.ipynb](https://colab.research.google.com/github/SANTZSPAXX/NixLMs/blob/main/NixLMs_Colab.ipynb). A sessão do Colab é temporária; copie o diretório `data/` para armazenamento persistente se quiser preservar pesos, vocabulário e memória.

## Backend opcional de embeddings multilíngues

A referência inicial é [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small): 118M parâmetros, 384 dimensões, contexto de até 512 tokens, licença MIT e suporte a português entre aproximadamente 100 idiomas. O leaderboard MTEB reporta cerca de 449 MB de memória para o modelo; o consumo total do processo depende também do PyTorch, precisão e runtime. O backend usa CPU e `local_files_only=True`: não baixa modelos automaticamente nem envia texto para serviços externos.

1. Instale PyTorch para CPU conforme as instruções oficiais para sua versão do Windows/Python. Exemplo para Windows x64:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

2. Instale a dependência opcional:

```powershell
python -m pip install -r requirements-embeddings.txt
```

3. Baixe o modelo manualmente com a ferramenta Hugging Face e mantenha-o em uma pasta local. Exemplo:

```powershell
hf download intfloat/multilingual-e5-small --local-dir models/multilingual-e5-small
```

4. Configure a pasta local antes de iniciar:

```powershell
$env:NIXLMS_EMBEDDING_MODEL_PATH = ".\\models\\multilingual-e5-small"
python neural_core.py
```

O carregamento é lazy. Se o pacote ou os pesos locais não estiverem disponíveis, a NixLMs retorna ao encoder nativo. O encoder pré-treinado é usado somente para recuperação; o encoder nativo continua responsável pelo vetor LIF e pelo treinamento contrastivo. E5 recebe prefixo `query:` para consultas e `passage:` para itens da memória.

Sem essa configuração, o núcleo continua funcionando sem PyTorch, Transformers ou acesso à internet.

## Treinamento e avaliação

O dataset inicial está em `datasets/starter_ptbr.jsonl`. Ele contém exemplos QA e pares contrastivos:

- QA: `question`, `answer`, `split` (`train`, `validation` ou `test`).
- Par: `type: "pair"`, `text_a`, `text_b`, `label` (1 = similar; 0 = diferente), `split`.

No terminal:

```text
/importar datasets/starter_ptbr.jsonl
/treinar 5
/rollback ID
/calibrar-lif
/calibrar-decoder
/avaliar
```

O comando `/treinar` cria um checkpoint do estado atual, treina uma cópia isolada e compara antes/depois usando exclusivamente QA do split `validation`. A promoção só ocorre se houver melhoria mensurável e nenhuma métrica de proteção regredir além da tolerância; caso contrário, o modelo ativo permanece intacto. Os artefatos de checkpoint ficam em `data/checkpoints/incremental/` e não são apagados automaticamente. Use `/rollback ID` com o identificador retornado pelo treinamento para restaurar pesos e calibrações anteriores. O comando `/treinar` ajusta encoder contrastivo, readout LIF e decoder autoregressivo usando somente o split `train`; o contexto LIF é determinístico por pergunta. A comparação mede loss/token accuracy do decoder, F1 textual de geração, loss do readout e margem de representação. Essas métricas são proxies e não comprovam factualidade. O split `test` não participa da seleção ou promoção do candidato. O split `validation` não participa do treinamento: use `/calibrar-lif` depois de treinar para selecionar o limiar de aceitação do readout com base no acerto do melhor candidato LIF. A calibração LIF exige pelo menos quatro exemplos pontuados, com ao menos dois candidatos top-1 corretos e dois incorretos; se a evidência for insuficiente, o limiar atual é preservado. Use `/calibrar-decoder` para calibrar separadamente a confiança média do decoder: ele gera respostas para o split `validation`, classifica a qualidade por token-F1 (limiar padrão 0,60) e escolhe o limiar que maximiza F1 de aceitação, exigindo no mínimo quatro exemplos, dois positivos e dois negativos. Essa qualidade é apenas sobreposição textual, não verificação factual; a calibração não atualiza pesos e é invalidada quando o decoder, o readout LIF, o encoder ou o split validation muda. Para datasets persistentes já existentes, importe novamente o starter atualizado com `/importar datasets/starter_ptbr.jsonl` para acrescentar o split validation. A calibração é persistida e vinculada às contagens do readout/encoder, ao vocabulário, ao fingerprint do conjunto validation e à memória candidata. Ela é ignorada quando esses dados divergem e invalidada antes de novos treinos ou mudanças de vocabulário.

A auditoria pode ser consultada pela API:

```python
report = ai.learning.dataset.audit_splits()
print(report)
```

O treinamento e a avaliação recusam datasets com sobreposição exata de textos de entrada entre treino e teste. Para avaliações confiáveis, use datasets maiores, representativos e com deduplicação de paráfrases; os exemplos iniciais são apenas smoke tests.

O comando `/avaliar` também mede a representação semântica no split `validation`: compara cada pergunta a exemplos `train` com a mesma resposta e a hard negatives, informa margem/pairwise accuracy e cobertura de subwords. Essa etapa não treina pesos nem expande o vocabulário. O benchmark cognitivo integrado no split `test` também passa cada pergunta pelo fluxo completo de resposta sem persistir os episódios de avaliação. Ele informa exact match, token F1, taxa de abstenção, eco da pergunta, distribuição da origem das respostas e uso/candidatos da LIF. O relatório também apresenta loss, perplexity, token accuracy e taxa de tokens-alvo OOV do decoder no split `test`, sem atualizar pesos. Esses indicadores são proxies textuais e operacionais, não verificadores de factualidade. As consultas exatas do split de teste são temporariamente excluídas da memória QA e episódica durante essa avaliação.

Use `/avaliar-llm` para uma execução opcional com o Ollama instalado. A avaliação padrão não chama o LLM, permitindo comparações offline reproduzíveis; a variante com LLM depende do modelo local, sua versão e configuração.

## Modelo de mundo e objetivos

Registrar um fato:

```text
/fato Terra || orbita || Sol || fonte científica
/fato-buscar Terra Sol
```

Criar objetivo e etapas:

```text
/objetivo criar Evoluir a memória semântica
/objetivo etapa goal-ID || Criar benchmark
/objetivo etapa goal-ID || Integrar avaliação || step-ID
/objetivo proximos goal-ID
/objetivo concluir goal-ID || step-ID
```

As dependências precisam estar concluídas antes de iniciar ou concluir uma etapa dependente. O sistema apenas registra e apresenta o plano.

## Memória e persistência

Os arquivos em `data/` incluem:

- `semantic_encoder.json`: vocabulário, embeddings e contagem de atualizações.
- `knowledge.json`: conhecimento QA.
- `episodic_memory.json`: histórico episódico.
- `mental_map.json`: grafo associativo.
- `world_model.json`: fatos tipados e proveniência.
- `goals.json`: objetivos e etapas.
- `neural_weights.json`: pesos LIF, elegibilidade e contador de atualizações do readout supervisionado.
- `neural_decoder.json`: vocabulário e pesos do decoder autoregressivo condicionado pela saída LIF.
- `decoder_calibration.json`: limiar de confiança do decoder, vinculado aos pesos LIF/decoder e ao fingerprint de validation.
- `dataset.json`: exemplos locais de treinamento.

Faça backup do diretório `data/` antes de trocar versões ou realizar treinamento extenso. Os novos módulos criam seus próprios arquivos sem sobrescrever os arquivos anteriores.

## Testes

```powershell
python -m unittest discover -s tests -v
```

A CI executa a suíte em versões suportadas do Python e em Windows/Linux.

## Segurança e privacidade

- O adaptador Ollama aceita somente `localhost`, `127.0.0.1` ou `::1`.
- O backend de embeddings aceita somente carregamento local/cache.
- O modelo de mundo registra fonte e confiança; não transforma afirmações em verdades verificadas.
- O Goal Manager não executa ferramentas, comandos ou alterações no sistema.
- Não inclua dados pessoais ou confidenciais nos datasets sem autorização e base legal.
- O núcleo não acessa sensores nem dispositivos.

## Arquitetura

`nixlms_core/` contém encoder, rede LIF, memória, atenção, mapa mental, modelo de mundo, gestão de objetivos, agendador SQLite, aprendizagem, EEG sintético e adaptadores linguísticos/embeddings opcionais.
