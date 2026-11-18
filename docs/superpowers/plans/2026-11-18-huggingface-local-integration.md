# Hugging Face local integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Integrar descoberta pública, downloads limitados e inferência local opcional do Hugging Face na NixLMs sem token, cobrança ou dependências obrigatórias.

**Architecture:** Cliente Hub anônimo com biblioteca padrão; download explícito por huggingface_hub com token=False; gerador Transformers CPU local-only; integração via CLI e painel loopback.

**Tech Stack:** Python 3.10+, urllib, pathlib, JSON, huggingface_hub opcional, Transformers/PyTorch CPU opcionais, unittest, HTTP server existente.

**Spec:** docs/superpowers/specs/2026-11-18-huggingface-free-local-design.md

## Global Constraints
- Sem token, login, segredo, cartão, endpoint pago, Inference Provider, Jobs ou Sandbox.
- Sem dependências ML no núcleo obrigatório.
- Somente recursos públicos e não gated.
- Downloads sempre explícitos, revision SHA, allowlist de arquivos e limites.
- Inferência somente CPU/local_files_only/trust_remote_code=False/use_safetensors=True.
- Preservar Ollama local como backend preferencial e todo o código existente.
- Windows 10/11, Colab e Python 3.10+.

## Review Focus
- HTTP API fora do ar, rate limit e JSON inválido: falha clara, sem travar o runtime.
- IDs maliciosos, path traversal e revisões não fixadas: rejeitar.
- Repositório gated, privado ou com tamanho desconhecido/excessivo: rejeitar.
- Arquivos .py/.bin e código remoto: nunca baixar/exec.
- Transformers ausente, modelo incompatível ou memória insuficiente: fallback seguro, sem interromper o núcleo.

---

### Task 1: Cliente público Hub e registro local

**Files:**
- Create: `nixlms_core/huggingface.py`
- Create: `tests/test_huggingface_hub.py`

**Interfaces:**
- `HuggingFaceHub(data_dir, opener=None, timeout=10)`
- `search(repo_type, query="", limit=20, sort="downloads")`
- `details(repo_type, repo_id)`
- `download(repo_type, repo_id, max_bytes=None)`
- `local_repositories()`, `status()`, `activate_model(repo_id)`, `deactivate_model()`, `active_model()`

- [ ] Add tests first for anonymous headers, public search/details, ID validation, gated/private rejection, size caps, file allowlist, SHA pinning, atomic registry, active model checks.
- [ ] Run tests to observe expected failures.
- [ ] Implement standard-library REST client and optional snapshot_download adapter.
- [ ] Run tests and ensure base imports do not require HF packages.

### Task 2: Local-only text generation

**Files:**
- Modify: `nixlms_core/huggingface.py`
- Modify: `nixlms_core/language.py`
- Modify: `nixlms_core/agent.py`
- Create: `tests/test_huggingface_local_generation.py`

- [ ] Add mocked generator tests for CPU-only settings, local_files_only, trust_remote_code=False, use_safetensors=True, bounded context/tokens, lazy imports and no network.
- [ ] Run tests to confirm failure.
- [ ] Implement lazy Transformers loader and Ollama-first/HF-local fallback.
- [ ] Keep provider metadata explicit in the agent trace.
- [ ] Run relevant language/agent tests.

### Task 3: Runtime API and CLI

**Files:**
- Modify: `nixlms_core/agent.py`
- Modify: `nixlms_web/server.py`
- Modify: `neural_core.py`
- Create: `tests/test_huggingface_api.py`

- [ ] Test status/search/details/download/activate/deactivate routes with patched Hub manager; verify loopback and input validation.
- [ ] Implement API routes and CLI commands `/hf status|buscar|detalhes|baixar|ativar|desativar`.
- [ ] Keep download opt-in and reject Spaces downloads/execution.
- [ ] Run API and CLI tests.

### Task 4: Control-center UI and optional packages

**Files:**
- Modify: `nixlms_web/static/index.html`
- Modify: `nixlms_web/static/app.js`
- Modify: `nixlms_web/static/style.css`
- Modify: `nixlms_core/framework_registry.py`
- Create: `requirements-hf-hub.txt`
- Create: `requirements-hf-local.txt`
- Create: `requirements-hf-data.txt`
- Create: `requirements-hf-eval.txt`
- Create: `requirements-hf-finetune.txt`
- Modify: `.gitignore`
- Create: `tests/test_huggingface_ui.py`

- [ ] Add static UI contract tests for tab, search, details, download and activation.
- [ ] Add opt-in install profiles; keep CPU PyTorch installation documented separately.
- [ ] Add framework inventory entries for Hub, Datasets, Evaluate, PEFT, Accelerate, Diffusers and Gradio.
- [ ] Wire UI to local API, render untrusted metadata with escaping and confirm before downloading/activating.
- [ ] Add Hugging Face storage paths to .gitignore.
- [ ] Run tests and JavaScript syntax checks if available.

### Task 5: Documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Create: `docs/huggingface-integration.md`
- Modify: `NixLMs_Colab.ipynb` only if a minimal optional setup cell can be added safely.

- [ ] Document anonymous/public access, exact free/local boundaries, install profiles, CLI/UI examples, hardware recommendations, licenses and unsupported gated resources.
- [ ] Run full test suite on GitHub Actions and CodeQL.
- [ ] Review PR diff, dependencies, security and compatibility.
- [ ] Merge only if all checks pass; otherwise report exact blocker and preserve branch.
