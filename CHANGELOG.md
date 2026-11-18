# Changelog

## Concorrência do gerenciador Ollama

- Serializa chamadas concorrentes a `start_service()` com lock por instância, evitando que inicializações simultâneas criem processos filhos duplicados e percam a referência de cleanup.
- Adiciona teste de regressão com oito chamadas concorrentes.


## Ollama — limpeza limitada após falha de inicialização

- Após falha de prontidão ou interrupção por Ctrl+C, tenta encerrar somente o processo `Popen` criado pela instância: `terminate()` + espera de até 2 segundos, seguida de `kill()` + nova espera de até 2 segundos; a interrupção do usuário continua sendo propagada.
- Expõe `last_cleanup` no diagnóstico e no resultado da inicialização, distinguindo encerramento confirmado de limpeza não confirmada.
- Preserva a referência do processo quando o encerramento não pode ser confirmado e recusa uma nova inicialização duplicada enquanto esse processo continuar ativo.
- Não encerra serviços preexistentes nem tenta finalizar a árvore de processos; descendentes podem exigir tratamento específico por sistema operacional.


## Ollama — isolamento do serviço gerenciado

- Inicia o processo Ollama com uma cópia explícita do ambiente e OLLAMA_HOST fixado ao endereço loopback correspondente ao endpoint local; o ambiente do processo pai não é alterado.
- Expõe bind_scope no diagnóstico: processos iniciados pelo gerenciador usam configured_loopback, enquanto serviços preexistentes são marcados como unverified_preexisting porque o bind do processo externo não é inspecionado.
- Adiciona regressões para ambiente herdado wildcard, preservação da porta e formatação IPv6.

## Consent-gated Ollama setup and runtime verification

- Adds an explicit `/llm preparar` CLI workflow with separate confirmation before installation, service startup, and Qwen model download.
- Adds a platform-aware Ollama manager: WinGet on Windows and the official installer on Linux; unsupported platforms receive a manual-install diagnostic.
- Starts only the local Ollama service and waits for a successful `/api/tags` response before continuing.
- Verifies the exact `qwen2.5:0.5b` model appears in the local model inventory after download.
- Requires Ollama `/api/chat` to return the expected model name, `done=true`, and non-empty content before marking generation as verified.
- Exposes the Ollama manager status and the verified model identity in runtime diagnostics.
- Reports installation, startup, download, API, and generation failures without claiming success.


## Surrogate-gradient training for recurrent LIF dynamics

- Adds fast-sigmoid surrogate-gradient BPTT for the LIF input and recurrent weights while keeping the supervised output readout frozen during recurrent updates.
- Adds a readout-independent contrastive objective directly on hidden LIF representations for positive and negative sentence pairs.
- Integrates recurrent and contrastive LIF updates into the train-only learning pipeline and reports update counts/losses.
- Persists a backward-compatible recurrent update counter in LIF checkpoints.
- Binds LIF and decoder confidence calibrations to recurrent update counts and recurrent weights so stale thresholds are rejected.
- Adds a validation-only hidden-representation benchmark for contrastive pairs; it does not update weights or inspect test examples.
- The safe incremental training gate also compares recurrent LIF validation metrics before promoting candidate weights.


## Safe incremental learning and rollback checkpoints

- Adds isolated candidate training: the active model is never modified while training and evaluating a candidate.
- Saves pre-training encoder, LIF, decoder, learned knowledge, mental map and calibration snapshots under `data/checkpoints/incremental/` with SHA-256 manifests.
- Compares decoder loss/token accuracy, generation token-F1, LIF readout loss and representation margins on the validation split only.
- Promotes candidate weights only when at least one metric improves and no protected metric regresses beyond tolerance; otherwise leaves the active model untouched.
- Detects concurrent changes to any dataset split or active model/knowledge state before promotion.
- Adds explicit checkpoint restore with path validation and integrity checks; no automatic checkpoint pruning.
- Routes CLI and Colab `/treinar` through the safe pipeline and adds `/rollback ID`.
- Keeps the existing low-level `LearningEngine.train()` for direct/internal experiments; interactive training uses `train_incremental()`.


## Validation-calibrated neural decoder confidence

- Adds a validation-only calibration flow for the autoregressive decoder's mean token probability threshold.
- Labels candidate generations with token-F1 overlap, requires a minimum sample count and both positive/negative outcomes, and selects the threshold maximizing acceptance F1.
- Persists calibration bound to decoder weights, LIF readout, encoder version counters, and validation fingerprint.
- Invalidates decoder calibration whenever training or LIF/encoder calibration invalidation occurs; explicit config thresholds remain authoritative.
- Exposes `/calibrar-decoder` in the CLI and Colab notebook; calibration does not update model weights or use the test split.


## LIF-conditioned autoregressive neural decoder

- Adds a compact CPU-oriented Elman RNN conditioned on the supervised LIF output vector.
- Trains the decoder with teacher forcing and backpropagation through time using QA rows from the train split only.
- Makes accepted neural generations the primary response path; low-confidence, empty, echo, or short outputs fall back to Ollama when enabled.
- Persists decoder vocabulary and weights separately in `neural_decoder.json`, preserving unreadable or incompatible checkpoints instead of overwriting them.
- Makes the EEG-inspired modulation deterministic per question so decoder training and inference receive the same LIF context across restarts.
- Adds decoder loss/perplexity/token-accuracy evaluation on the test split without updating weights.


## Trainable character subword encoder

- Extends the native semantic encoder with trainable 3–5 character n-gram features for morphological and OOV generalization.
- Keeps OOV inference deterministic and vocabulary-read-only; overlapping subwords reuse learned train features.
- Bounds encoder feature expansion to 128 tokens and 32 characters per token.
- Adds validation representation metrics: positive similarity, hard-negative similarity, margin, pairwise accuracy, and subword coverage.


## Validation-driven LIF calibration

- Adds a dedicated validation dataset split, separate from training and final test data.
- Keeps encoder vocabulary construction and training restricted to the train split.
- Adds a validation-only procedure to select the LIF acceptance threshold from top-candidate precision/recall/F1.
- Persists calibration only when validation has enough correct and incorrect top candidates.
- Binds saved calibration to readout/encoder update counts, vocabulary size, validation-set fingerprint, and candidate-memory fingerprint; stale calibration is ignored and new training invalidates it.
- Adds `/calibrar-lif` to CLI and Colab and expands the starter dataset with paraphrased validation QA.


## Integrated cognitive benchmark

- Adds end-to-end evaluation of held-out QA responses through the normal NixLMs response pipeline.
- Reports exact match, token F1, abstention and question-echo rates, response-source distribution, and LIF candidate/use metrics.
- Excludes exact held-out questions from QA and episodic memory during evaluation to prevent direct answer leakage.
- Adds a non-persistent response mode so benchmark runs do not append episodes or working-memory turns.
- Keeps evaluation offline by default and adds an explicit opt-in Ollama benchmark mode.


## LIF-conditioned language generation

- Added a supervised LIF output readout trained from QA question-to-answer examples.
- Uses the recurrent network output to retrieve answer representations and condition the local language model with a primary neural candidate.
- Uses the trained LIF associative readout as a confidence-gated fallback when no valid local LLM response is available.
- Persists backward-compatible output-readout update counts in neural weights and exposes readout diagnostics in the response trace.
- Keeps token-by-token generation in the local LLM; the LIF readout is an explicit semantic selection/conditioning mechanism, not an autoregressive language model.
- Added tests for supervised readout learning and LIF conditioning in the Ollama prompt.

## Conversational routing and Colab runtime fixes

- Added deterministic handling for greetings, unknown user-name questions, and local date/time queries.
- Prevented low-relevance semantic memories from becoming direct answers.
- Rejects generic greeting replies, question echoes, and person answers that omit the requested entity.
- Improves the Ollama system prompt and records answer-rejection diagnostics.
- Makes Colab bootstrap update an existing checkout, clear stale imported modules, and print the exact commit and import path.
- Adds `/diagnostico` to the Colab chat loop for runtime, LLM, and last-response inspection.


## Reliability improvements — runtime integration

- Added deterministic local date/time responses that work without an installed LLM.
- Reused the configured retrieval encoder for episodic as well as semantic memory.
- Added bounded context fields and explicit untrusted-context instructions to reduce prompt-injection risk from retrieved memories.
- Distinguished Ollama service reachability from model availability and validated malformed API payloads.
- Added response trace diagnostics for LLM and retrieval backend failures.


## 0.7.0 — Episodic Experience Memory (em desenvolvimento)

- Added structured persistent episodes with timestamps, context, response source, outcome, importance and tags.
- Added hybrid episodic retrieval with lexical/semantic relevance, recency and explicit feedback weighting.
- Integrated recalled experiences into local LLM context without promoting them to verified facts.
- Connected positive/negative user feedback to the latest matching episode.
- Preserved the legacy conversation log and kept episodic data in a separate file.
- Added persistence, retrieval, validation, retention and agent integration tests.


## 0.6.0 — Persistent Cognitive Scheduler

- Added a standard-library SQLite scheduler with durable one-shot and interval jobs.
- Added allowlisted runtime handlers, JSON payload validation, task limits and priority ordering.
- Added atomic task claiming, renewable leases, retry backoff, event history and graceful worker shutdown.
- Integrated conservative memory housekeeping, dataset integrity audits and goal review handlers.
- Added CLI agenda commands; background execution starts only in the CLI or after explicit API opt-in.
- Documented at-least-once delivery semantics, idempotency requirements and local-filesystem constraints.
- Added scheduler persistence, recurrence, retry, priority, cancellation and lifecycle tests.


## 0.5.0 — Balanced Cognitive Evolution

- Added a persistent typed World Model with source, confidence and possible-conflict reporting.
- Added a Goal Manager with persistent goals, dependent steps and next-action inspection; it does not execute actions.
- Added optional lazy CPU-only multilingual sentence embeddings through Sentence Transformers, with local/cache-only loading and E5 query/passage prefixes.
- Kept the native trainable encoder as the LIF input encoder and contrastive-learning target.
- Added dataset split auditing across QA and contrastive input text.
- Made JSONL imports atomic: invalid input no longer leaves partial records.
- Training and evaluation now reject detected train/test text overlap.
- Aligned semantic/hybrid benchmark scoring with production memory retrieval.
- Excluded exact test questions from retrieval candidates.
- Extended local LLM context with sourced world facts and active goals.
- Added CLI commands for facts and goal management.
- Corrected the starter dataset's train/test overlap and added a train-side QA candidate for the capital-city retrieval example.
- Documented optional model setup, privacy boundaries and module limitations.

## 0.4.0

- Added trainable word/bigram semantic embeddings and contrastive learning.
- Added hybrid semantic/lexical memory retrieval.
- Added LIF spike telemetry and explicit-feedback plasticity.
- Added split-aware QA and contrastive datasets and evaluation metrics.
- Added optional local Ollama language generation.

## Validação comparativa da recuperação episódica

- Compara cache desabilitado, cache frio e cache aquecido com o mesmo conjunto determinístico de episódios e encoder.
- Verifica equivalência de IDs/ordenação e scores por ID com tolerância absoluta de `1e-5`.
- Confirma que `recall()` não altera o JSON persistido e que feedback, importância e recência continuam sendo recalculados sem re-encoding.
- Mede mediana e p95 em repetições para 100, 500 e 2.000 episódios; a CI publica o relatório JSON sintético como artefato.
- Mantém E5 opcional e local-only; nenhum modelo é baixado automaticamente.


## Recuperação episódica otimizada — cache LRU e codificação em lote

- Adiciona cache LRU volátil e limitado para embeddings de passagens episódicas, armazenados em float32 e sem alterar o JSON persistido.
- Vincula entradas ao fingerprint do conteúdo e à identidade/configuração/versão do encoder; invalida entradas obsoletas e libera itens removidos.
- Codifica somente misses em lotes limitados; mantém fallback compatível para encoders que oferecem apenas encode_passage ou encode.
- Adiciona métricas de hits, misses, evictions, passagens codificadas e chamadas ao encoder.
- Adiciona testes com encoders determinísticos/fakes e benchmark reproduzível para 100, 500 e 2.000 episódios; o modo E5 usa exclusivamente um modelo local informado pelo usuário.



## Benchmark piloto de qualidade da recuperação episódica em PT-BR

- Adiciona corpus sintético offline com 50 episódios, 30 consultas e qrels graduados, incluindo paráfrases, coloquialismos, variações ortográficas, referências contextuais e consultas sem resposta.
- Adiciona avaliador determinístico com nDCG@k, MRR@k, Recall@k, Precision@k, cobertura e métricas de abstenção/falsos positivos, além de resultados por categoria e split.
- Mantém o modo lexical sem dependências; encoder nativo e multilingual E5 são opcionais e exigem checkpoint/diretório local explicitamente informado.
- Gera relatório JSON com hash do conjunto e IDs, sem gravar na memória pessoal nem incluir conteúdo textual das consultas/passagens.
- Adiciona testes de métricas, integridade dos qrels, determinismo, não mutação do conjunto, checkpoint local e execução offline.



## Segurança do benchmark de recuperação episódica PT-BR

- Rejeita caminhos de saída que coincidam com a memória episódica de produção ou com os arquivos de entrada do benchmark (conjunto padrão e diretório selecionado).
- Resolve caminhos antes da comparação para também bloquear aliases com segmentos relativos e symlinks já existentes.
- Rejeita `min-score` NaN e infinitos tanto na API de avaliação quanto no CLI, evitando métricas enganosas e JSON não padrão.
- Adiciona testes para caminhos protegidos, destino separado permitido e limiares não finitos.

