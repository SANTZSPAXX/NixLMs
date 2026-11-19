"""Inventário leve de frameworks opcionais da NixLMs.

Este módulo usa somente a biblioteca padrão. Ele detecta instalações sem
importar frameworks pesados, iniciar downloads ou modificar o ambiente.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import sysconfig
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Iterable

from .framework_status import classify_installation


@dataclass(frozen=True)
class Framework:
    name: str
    package: str
    module: str
    category: str
    purpose: str
    install_group: str
    default_recommendation: bool = False


FRAMEWORKS = (
    Framework("PyTorch", "torch", "torch", "training",
              "Treinamento e execução de redes neurais em CPU.",
              "pytorch-cpu", True),
    Framework("NumPy", "numpy", "numpy", "numerical",
              "Vetores, matrizes e operações numéricas.",
              "ml-cpu", True),
    Framework("SciPy", "scipy", "scipy", "numerical",
              "Algoritmos científicos e otimização.",
              "ml-cpu", True),
    Framework("scikit-learn", "scikit-learn", "sklearn", "classical-ml",
              "Modelos clássicos, métricas e pré-processamento.",
              "ml-cpu", True),
    Framework("Transformers", "transformers", "transformers", "language",
              "Tokenizadores e modelos de linguagem pré-treinados.",
              "ml-cpu", True),
    Framework("Sentence Transformers", "sentence-transformers",
              "sentence_transformers", "embeddings",
              "Embeddings semânticos e recuperação.",
              "ml-cpu", True),
    Framework("FAISS CPU", "faiss-cpu", "faiss", "retrieval",
              "Índices vetoriais locais para busca por similaridade.",
              "ml-cpu", True),
    Framework("ONNX Runtime CPU", "onnxruntime", "onnxruntime", "inference",
              "Inferência otimizada de modelos ONNX em CPU.",
              "ml-cpu", True),
    Framework("Safetensors", "safetensors", "safetensors", "model-storage",
              "Serialização de tensores de modelos.",
              "ml-cpu", True),
    Framework("Tokenizers", "tokenizers", "tokenizers", "language",
              "Tokenização eficiente.",
              "ml-cpu", True),
    Framework("Hugging Face Hub", "huggingface-hub", "huggingface_hub", "hub",
              "Pesquisa e download anônimo de modelos, datasets e Spaces públicos.",
              "hf-hub", False),
    Framework("Hugging Face Datasets", "datasets", "datasets", "data",
              "Leitura e processamento local de datasets do Hub.",
              "hf-data", False),
    Framework("Hugging Face Evaluate", "evaluate", "evaluate", "evaluation",
              "Métricas e avaliações locais de modelos.",
              "hf-eval", False),
    Framework("Accelerate", "accelerate", "accelerate", "training",
              "Preparação e execução de treinamento local.",
              "hf-local", False),
    Framework("PEFT", "peft", "peft", "fine-tuning",
              "Fine-tuning eficiente com adaptadores LoRA/PEFT.",
              "hf-finetune", False),
    Framework("TRL", "trl", "trl", "fine-tuning",
              "Treinamento alinhado opcional; requer dados e recursos locais.",
              "hf-finetune", False),
    Framework("Diffusers", "diffusers", "diffusers", "generation",
              "Pipelines locais de geração de imagem, vídeo e áudio.",
              "hf-image", False),
    Framework("Gradio", "gradio", "gradio", "apps",
              "Interfaces locais para demonstrações e ferramentas de ML.",
              "hf-local", False),
    Framework("TensorFlow CPU", "tensorflow-cpu", "tensorflow", "training",
              "Framework alternativo para treinamento e inferência.",
              "tensorflow", False),
    Framework("llama.cpp Python", "llama-cpp-python", "llama_cpp", "inference",
              "Bindings Python opcionais para inferência GGUF local.",
              "llama-cpp", False),
)

# Proveniência upstream verificada nesta revisão. A licença do projeto principal
# não substitui a auditoria das dependências, modelos ou datasets.
FRAMEWORK_METADATA = {
    "torch": {
        "project_url": "https://pytorch.org",
        "source_url": "https://github.com/pytorch/pytorch",
        "distribution_source_url": "https://download.pytorch.org/whl/cpu",
        "license_spdx": None,
        "license_status": "noassertion_upstream",
        "license_source_url": "https://github.com/pytorch/pytorch/blob/main/LICENSE",
        "license_note": "O metadado upstream retorna NOASSERTION; revisar LICENSE e componentes incluídos.",
        "compatibility_url": "https://pytorch.org/get-started/locally/",
    },
    "numpy": {
        "project_url": "https://numpy.org",
        "source_url": "https://github.com/numpy/numpy",
        "distribution_source_url": "https://pypi.org/project/numpy/",
        "license_spdx": None,
        "license_status": "noassertion_upstream",
        "license_source_url": "https://github.com/numpy/numpy/blob/main/LICENSE.txt",
        "license_note": "O metadado upstream retorna NOASSERTION; revisar licença principal e componentes incluídos.",
        "compatibility_url": "https://numpy.org/install/",
    },
    "scipy": {
        "project_url": "https://scipy.org",
        "source_url": "https://github.com/scipy/scipy",
        "distribution_source_url": "https://pypi.org/project/scipy/",
        "license_spdx": "BSD-3-Clause",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/scipy/scipy/blob/main/LICENSE.txt",
        "license_note": "SPDX informado pelo repositório upstream; dependências têm licenças próprias.",
        "compatibility_url": "https://scipy.org/install/",
    },
    "scikit-learn": {
        "project_url": "https://scikit-learn.org",
        "source_url": "https://github.com/scikit-learn/scikit-learn",
        "distribution_source_url": "https://pypi.org/project/scikit-learn/",
        "license_spdx": "BSD-3-Clause",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/scikit-learn/scikit-learn/blob/main/COPYING",
        "license_note": "SPDX informado pelo repositório upstream; dependências têm licenças próprias.",
        "compatibility_url": "https://scikit-learn.org/stable/install.html",
    },
    "transformers": {
        "project_url": "https://huggingface.co/docs/transformers",
        "source_url": "https://github.com/huggingface/transformers",
        "distribution_source_url": "https://pypi.org/project/transformers/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/transformers/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; modelos baixados têm licenças independentes.",
        "compatibility_url": "https://huggingface.co/docs/transformers/installation",
    },
    "sentence-transformers": {
        "project_url": "https://www.sbert.net",
        "source_url": "https://github.com/huggingface/sentence-transformers",
        "distribution_source_url": "https://pypi.org/project/sentence-transformers/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/sentence-transformers/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; modelos baixados têm licenças independentes.",
        "compatibility_url": "https://www.sbert.net/docs/installation.html",
    },
    "faiss-cpu": {
        "project_url": "https://faiss.ai",
        "source_url": "https://github.com/facebookresearch/faiss",
        "distribution_source_url": "https://pypi.org/project/faiss-cpu/",
        "license_spdx": "MIT",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/facebookresearch/faiss/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; validar wheels por plataforma.",
        "compatibility_url": "https://github.com/facebookresearch/faiss/blob/main/INSTALL.md",
    },
    "onnxruntime": {
        "project_url": "https://onnxruntime.ai",
        "source_url": "https://github.com/microsoft/onnxruntime",
        "distribution_source_url": "https://pypi.org/project/onnxruntime/",
        "license_spdx": None,
        "license_status": "not_verified",
        "license_source_url": None,
        "license_note": "Licença SPDX não confirmada nesta revisão; verificar upstream antes de redistribuir.",
        "compatibility_url": "https://onnxruntime.ai/docs/reference/compatibility",
    },
    "safetensors": {
        "project_url": "https://huggingface.co/docs/safetensors",
        "source_url": "https://github.com/huggingface/safetensors",
        "distribution_source_url": "https://pypi.org/project/safetensors/",
        "license_spdx": None,
        "license_status": "not_verified",
        "license_source_url": None,
        "license_note": "Licença SPDX não confirmada nesta revisão; verificar upstream antes de redistribuir.",
        "compatibility_url": "https://huggingface.co/docs/safetensors/index",
    },
    "tokenizers": {
        "project_url": "https://huggingface.co/docs/tokenizers",
        "source_url": "https://github.com/huggingface/tokenizers",
        "distribution_source_url": "https://pypi.org/project/tokenizers/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/tokenizers/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://huggingface.co/docs/tokenizers/installation",
    },
    "huggingface-hub": {
        "project_url": "https://huggingface.co/docs/huggingface_hub",
        "source_url": "https://github.com/huggingface/huggingface_hub",
        "distribution_source_url": "https://pypi.org/project/huggingface-hub/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/huggingface_hub/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; modelos e datasets têm licenças independentes.",
        "compatibility_url": "https://huggingface.co/docs/huggingface_hub/installation",
    },
    "datasets": {
        "project_url": "https://huggingface.co/docs/datasets",
        "source_url": "https://github.com/huggingface/datasets",
        "distribution_source_url": "https://pypi.org/project/datasets/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/datasets/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; datasets individuais têm licenças independentes.",
        "compatibility_url": "https://huggingface.co/docs/datasets/installation",
    },
    "evaluate": {
        "project_url": "https://huggingface.co/docs/evaluate",
        "source_url": "https://github.com/huggingface/evaluate",
        "distribution_source_url": "https://pypi.org/project/evaluate/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/evaluate/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://huggingface.co/docs/evaluate/installation",
    },
    "accelerate": {
        "project_url": "https://huggingface.co/docs/accelerate",
        "source_url": "https://github.com/huggingface/accelerate",
        "distribution_source_url": "https://pypi.org/project/accelerate/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/accelerate/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://huggingface.co/docs/accelerate/installation",
    },
    "peft": {
        "project_url": "https://huggingface.co/docs/peft",
        "source_url": "https://github.com/huggingface/peft",
        "distribution_source_url": "https://pypi.org/project/peft/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/peft/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://huggingface.co/docs/peft/installation",
    },
    "trl": {
        "project_url": "https://huggingface.co/docs/trl",
        "source_url": "https://github.com/huggingface/trl",
        "distribution_source_url": "https://pypi.org/project/trl/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/trl/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://huggingface.co/docs/trl/installation",
    },
    "diffusers": {
        "project_url": "https://huggingface.co/docs/diffusers",
        "source_url": "https://github.com/huggingface/diffusers",
        "distribution_source_url": "https://pypi.org/project/diffusers/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/huggingface/diffusers/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; modelos e artefatos têm licenças independentes.",
        "compatibility_url": "https://huggingface.co/docs/diffusers/installation",
    },
    "gradio": {
        "project_url": "https://www.gradio.app",
        "source_url": "https://github.com/gradio-app/gradio",
        "distribution_source_url": "https://pypi.org/project/gradio/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/gradio-app/gradio/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream.",
        "compatibility_url": "https://www.gradio.app/guides/quickstart",
    },
    "tensorflow-cpu": {
        "project_url": "https://www.tensorflow.org",
        "source_url": "https://github.com/tensorflow/tensorflow",
        "distribution_source_url": "https://pypi.org/project/tensorflow-cpu/",
        "license_spdx": "Apache-2.0",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/tensorflow/tensorflow/blob/master/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; builds Windows/ARM podem ter mantenedores distintos.",
        "compatibility_url": "https://www.tensorflow.org/install/pip",
    },
    "llama-cpp-python": {
        "project_url": "https://llama-cpp-python.readthedocs.io",
        "source_url": "https://github.com/abetlen/llama-cpp-python",
        "distribution_source_url": "https://pypi.org/project/llama-cpp-python/",
        "license_spdx": "MIT",
        "license_status": "verified_upstream",
        "license_source_url": "https://github.com/abetlen/llama-cpp-python/blob/main/LICENSE",
        "license_note": "SPDX informado pelo repositório upstream; wheels variam por plataforma e configuração.",
        "compatibility_url": "https://llama-cpp-python.readthedocs.io/en/latest/",
    },
}

LICENSE_AUDIT_NOTE = (
    "A licença indicada é do projeto principal. Dependências, modelos, checkpoints "
    "e datasets podem ter termos independentes."
)



def _installed_distribution(distribution: str):
    try:
        return importlib.metadata.distribution(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _installed_version(distribution: str) -> str | None:
    """Mantém um helper leve para consultar somente a versão da distribuição."""
    found = _installed_distribution(distribution)
    return found.version if found is not None else None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _measure_distribution_size(distribution):
    """Soma arquivos declarados pela distribuição dentro de purelib/platlib."""
    files = distribution.files
    if files is None:
        return None, 0
    paths = sysconfig.get_paths()
    roots = {
        Path(paths[key]).resolve()
        for key in ("purelib", "platlib")
        if paths.get(key)
    }
    if not roots:
        return None, 0
    seen = set()
    total = 0
    count = 0
    for entry in files:
        try:
            path = Path(distribution.locate_file(entry)).resolve()
            if path in seen or not path.is_file():
                continue
            if not any(_is_within(path, root) for root in roots):
                continue
            size = path.stat().st_size
        except (OSError, RuntimeError, ValueError):
            continue
        seen.add(path)
        total += size
        count += 1
    return (total, count) if count else (None, 0)


def inspect_frameworks(
    frameworks: Iterable[Framework] = FRAMEWORKS, *, include_sizes: bool = False
) -> list[dict]:
    """Retorna inventário sem importar frameworks nem percorrer arquivos por padrão."""
    environment = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.system(),
        "architecture": platform.machine(),
    }
    report = []
    for item in frameworks:
        distribution = _installed_distribution(item.package)
        version = distribution.version if distribution is not None else None
        try:
            module_available = importlib.util.find_spec(item.module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            module_available = False
        state = classify_installation(version, module_available)

        size_bytes = None
        size_files = None
        if state["installation_state"] == "installed":
            if include_sizes:
                size_bytes, size_files = _measure_distribution_size(distribution)
                size_status = "measured" if size_bytes is not None else "unavailable"
            else:
                size_status = "not_measured"
        elif state["ambiguous_install"]:
            size_status = "inconsistent_installation"
        else:
            size_status = "not_installed"

        metadata = FRAMEWORK_METADATA[item.package]
        report.append({
            **asdict(item),
            **metadata,
            **state,
            "version": version,
            "license_audit_note": LICENSE_AUDIT_NOTE,
            "current_environment": dict(environment),
            "compatibility_status": "not_resolved_by_inventory",
            "compatibility_method": (
                "A compatibilidade precisa ser resolvida no ambiente-alvo por "
                "um plano explícito wheel-only; o inventário não certifica "
                "uma matriz multiplataforma."
            ),
            "installed_size_bytes": size_bytes,
            "installed_size_file_count": size_files,
            "installed_size_status": size_status,
            "runtime_resources": {
                "cpu_time": "not_measured",
                "peak_ram_bytes": None,
            },
            "model_library_status": "not_inspected",
            "training_dataset_library_status": "not_inspected",
            "runtime_integration_status": "not_verified",
        })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspeciona frameworks opcionais da NixLMs sem instalar nada."
    )
    parser.add_argument("--json", action="store_true", help="Imprime JSON.")
    parser.add_argument("--all", action="store_true",
                        help="Inclui frameworks opcionais não recomendados por padrão.")
    parser.add_argument("--sizes", action="store_true",
                        help="Mede bytes dos arquivos instalados (mais lento; não mede RAM/CPU).")
    args = parser.parse_args(argv)

    report = inspect_frameworks(include_sizes=args.sizes)
    if not args.all:
        report = [item for item in report
                  if item["default_recommendation"] or item["installed"]
                  or item["ambiguous_install"]]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Inventário de frameworks NixLMs (nenhuma instalação foi executada)")
        for item in report:
            if item["installation_state"] == "installed":
                state = f"instalado {item['version'] or ''}".strip()
            elif item["installation_state"] == "metadata_only":
                state = "inconsistente: metadados sem módulo"
            elif item["installation_state"] == "module_only":
                state = "inconsistente: módulo sem metadados"
            else:
                state = "ausente"
            footprint = ""
            if args.sizes:
                size = item["installed_size_bytes"]
                footprint = (
                    f" | instalado={size} bytes"
                    if size is not None else f" | footprint={item['installed_size_status']}"
                )
            print(f"- {item['name']}: {state} | grupo={item['install_group']}{footprint} | {item['purpose']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
