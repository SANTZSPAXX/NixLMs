# NixLMs 0.5 Balanced Evolution — Implementation Plan

> **For agentic workers:** Execute task-by-task using the repository's existing GitHub workflow. Steps are ordered test-first. Keep all work on `feature/nixlms-0.5-balanced-evolution`.

**Goal:** Add reliable dataset validation, explicit world and goal models, and an optional offline multilingual retrieval encoder without breaking the lightweight native core.

**Architecture:** Preserve the existing native `SemanticEncoder` for LIF input and contrastive learning. Add independent local modules for typed facts and goal state, and an optional lazy Hugging Face Sentence Transformers backend used only by memory retrieval. Harden dataset ingestion and ensure evaluation mirrors production retrieval.

**Tech Stack:** Python 3.10+, standard library by default, optional `sentence-transformers`/PyTorch, JSON persistence, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-13-balanced-evolution-design.md`

## Global Constraints
- Keep `main` and `feature/semantic-learning-0.4` unchanged.
- Work only on `feature/nixlms-0.5-balanced-evolution`.
- Python 3.10+; no new mandatory dependencies.
- No automatic model downloads; optional backend must use CPU and local-only loading.
- Preserve existing JSON files and public APIs where possible.
- Never execute goals or external actions automatically.

## Review Focus
- Cross-task train/test leakage where a sentence appears in different pair records or in QA and contrastive data.
- Partial dataset writes after malformed JSONL or a late validation error.
- Model files missing, optional libraries absent, or model output dimensions differing from the LIF input size.
- Conflicting world facts with different sources or confidence values.
- Goal steps with missing dependencies, invalid statuses, or attempts to complete blocked steps.

---

### Task 1: Dataset integrity and retrieval benchmark

**Files:**
- Modify: `nixlms_core/learning.py`
- Modify: `tests/test_core.py`
- Test: `tests/test_evolution.py`

**Interfaces:**
- `DatasetStore.audit_splits() -> dict` returns `valid`, `counts`, and `violations`.
- `DatasetStore.import_jsonl(source) -> int` parses, validates, then writes once.
- `LearningEngine.train()` and `evaluate()` reject invalid split separation.
- Retrieval evaluation uses the same nonnegative cosine clamp and E5 query/passage contract as `MemorySystem.recall`.

- [ ] Add failing tests for pair-text overlap across splits, QA/pair cross-task overlap, and atomic import rollback.
- [ ] Run the tests and confirm expected failures.
- [ ] Implement centralized row validation and atomic import.
- [ ] Add split audit and enforce it before training/evaluation.
- [ ] Add regression test that hybrid evaluation score matches production memory scoring.
- [ ] Run full unittest suite.

### Task 2: Typed local world model

**Files:**
- Create: `nixlms_core/world_model.py`
- Modify: `nixlms_core/agent.py`
- Test: `tests/test_evolution.py`

**Interfaces:**
- `WorldModel(path, max_facts=5000)`
- `assert_fact(subject, predicate, object, confidence=1.0, source="user") -> dict`
- `query(subject=None, predicate=None, object=None, limit=100) -> list[dict]`
- `search(text, limit=10) -> list[dict]`
- `possible_conflicts(subject, predicate) -> list[list[dict]]`
- `stats() -> dict`

- [ ] Add failing tests for persistence, normalization, validation, search, and non-destructive conflict reporting.
- [ ] Implement bounded JSON-backed fact storage with provenance and timestamps.
- [ ] Integrate world model into agent initialization and status.
- [ ] Include retrieved facts in local LLM context, clearly marked as sourced memory.
- [ ] Run full unittest suite.

### Task 3: Goal and step manager

**Files:**
- Create: `nixlms_core/planning.py`
- Modify: `nixlms_core/agent.py`
- Test: `tests/test_evolution.py`

**Interfaces:**
- `GoalManager(path, max_goals=500)`
- `create_goal(title, description="") -> dict`
- `add_step(goal_id, title, depends_on=None) -> dict`
- `set_step_status(goal_id, step_id, status) -> dict`
- `get_goal(goal_id) -> dict | None`
- `list_goals(status=None) -> list[dict]`
- `next_actions(goal_id) -> list[dict]`
- `stats() -> dict`

- [ ] Add failing tests for persistence, dependency ordering, invalid transitions, and blocked completion.
- [ ] Implement goal storage with stable IDs, dependency checks and derived readiness.
- [ ] Integrate goal manager into agent status and local LLM context.
- [ ] Keep execution out of scope: planner only stores and reports steps.
- [ ] Run full unittest suite.

### Task 4: Optional local multilingual retrieval backend

**Files:**
- Create: `nixlms_core/pretrained_encoder.py`
- Modify: `nixlms_core/memory.py`
- Modify: `nixlms_core/agent.py`
- Modify: `nixlms_core/learning.py`
- Create: `requirements-embeddings.txt`
- Test: `tests/test_evolution.py`

**Interfaces:**
- `TransformersSentenceEncoder(model_path, device="cpu", local_files_only=True, max_seq_length=256, model_loader=None)`
- `encode(text)`, `encode_query(text)`, `encode_passage(text)`, `status()`
- The injected `model_loader` is used by tests; production loading imports Sentence Transformers lazily.
- Native encoder remains the default and the LIF input encoder.

- [ ] Add failing tests for lazy loading, E5 prefixes, CPU/local-only loader arguments, normalized output and missing optional dependency handling.
- [ ] Implement the adapter with no import-time dependency and no network downloads.
- [ ] Add retrieval-encoder selection through `NIXLMS_EMBEDDING_MODEL_PATH`; fall back safely to native encoder if unavailable.
- [ ] Update memory and benchmark to use query/passage methods when present.
- [ ] Document manual model provisioning and optional installation.
- [ ] Run full unittest suite and verify default mode works without optional dependencies.

### Task 5: CLI, documentation and release validation

**Files:**
- Modify: `neural_core.py`
- Modify: `README.md`
- Create or update: `CHANGELOG.md`
- Modify: `tests/test_evolution.py`

- [ ] Add commands to inspect/add facts and create/list goals, add steps, complete steps and show next actions.
- [ ] Document architecture, privacy, optional backend setup, limitations and hardware profile.
- [ ] Add migration notes; never overwrite user data.
- [ ] Run `python -m unittest discover -s tests -v` in GitHub Actions on Ubuntu 3.10/3.11/3.12 and Windows 3.12.
- [ ] Inspect all job logs and fix failures with a new regression test.
- [ ] Review branch diff; do not merge into main.

## Commit strategy
Use small, reviewable commits per task. The final handoff must report exact commits, CI job results, files changed, and remaining limitations. A green CI run is not a substitute for local Windows/Colab validation.


## Execution record — 2026-11-14

- Branch: `feature/nixlms-0.5-balanced-evolution`.
- Pull request: [#2](https://github.com/SANTZSPAXX/NixLMs/pull/2), draft, base `feature/semantic-learning-0.4`; not merged.
- GitHub Actions run: [#66](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43544452554).
- Matrix result: Ubuntu Python 3.10, 3.11, 3.12 and Windows Python 3.12 — all four jobs completed successfully.
- The unit-test step reported **34 tests, OK** in the inspected Ubuntu 3.11 and Windows 3.12 logs; the other two matrix jobs also completed successfully.
- The optional E5 backend was validated with an injected test model. Actual loading of downloaded E5 weights was not exercised because no model files were provisioned in CI.
- The test suite was authored before the implementation, but a failing CI run was not captured before the implementation commits. The final green run is verified; a strict red-green trace is not claimed.
- Remaining validation: run on the user's Windows machine, provision the optional model locally, profile CPU/RAM, and evaluate on a licensed held-out Portuguese benchmark such as ASSIN/ASSIN2 or MTEB-BR with leakage controls.


## Final verification after the last code changes

- Pull-request CI run: [43544638232](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43544638232).
- All four matrix jobs completed successfully: Ubuntu Python 3.10, 3.11, 3.12 and Windows Python 3.12.
- Each matrix job executed **35 tests**.
- The latest branch commit at the time of this record is `2af6b37ddcf4bc21caa7a2cb58c8d131accc08ff`.
- No merge was performed. The draft PR remains based on `feature/semantic-learning-0.4`.
