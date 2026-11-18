"""Inventário leve de frameworks opcionais da NixLMs.

Este módulo usa somente a biblioteca padrão. Ele detecta instalações sem
importar frameworks pesados, iniciar downloads ou modificar o ambiente.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
from dataclasses import asdict, dataclass
from typing import Iterable


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


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def inspect_frameworks(frameworks: Iterable[Framework] = FRAMEWORKS) -> list[dict]:
    """Retorna inventário sem importar módulos de terceiros."""
    report = []
    for item in frameworks:
        version = _installed_version(item.package)
        try:
            module_available = importlib.util.find_spec(item.module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            module_available = False
        report.append({
            **asdict(item),
            "installed": version is not None or module_available,
            "version": version,
            "module_available": module_available,
        })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspeciona frameworks opcionais da NixLMs sem instalar nada."
    )
    parser.add_argument("--json", action="store_true", help="Imprime JSON.")
    parser.add_argument("--all", action="store_true",
                        help="Inclui frameworks opcionais não recomendados por padrão.")
    args = parser.parse_args(argv)

    report = inspect_frameworks()
    if not args.all:
        report = [item for item in report
                  if item["default_recommendation"] or item["installed"]]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Inventário de frameworks NixLMs (nenhuma instalação foi executada)")
        for item in report:
            state = f"instalado {item['version'] or ''}".strip() if item["installed"] else "ausente"
            print(f"- {item['name']}: {state} | grupo={item['install_group']} | {item['purpose']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
