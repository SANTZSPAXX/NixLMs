# Changelog

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
