"""Instalador explícito do perfil multimodal usando o resolvedor seguro comum.

PyTorch CPU é pré-requisito separado, instalado pelo fluxo explícito da
Framework Library. Este módulo nunca é chamado pelo runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import framework_install

ROOT = Path(__file__).resolve().parents[1]
MEDIA_REQUIREMENTS = ROOT / "requirements-hf-media.txt"


def build_install_plan(
    requirements_file: Path = MEDIA_REQUIREMENTS,
    *,
    root: Path = ROOT,
    module_probe=None,
    version_probe=None,
    system_name: str | None = None,
    machine: str | None = None,
    python_version: tuple[int, int] | None = None,
) -> dict:
    """Inspeciona o ambiente sem importar frameworks nem instalar pacotes.

    A resolução transitiva e a validação dos wheels acontecem no resolvedor
    compartilhado, chamado pelo modo --plan/--install.
    """
    return framework_install.build_install_plan(
        requirements_file=requirements_file,
        root=root,
        module_probe=module_probe,
        version_probe=version_probe,
        system=system_name,
        machine=machine,
        python=python_version,
    )


def is_virtual_environment() -> bool:
    """Mantém a consulta pública compatível com o instalador anterior."""
    return framework_install.is_virtual_environment()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Planeja ou instala o perfil multimodal opcional usando somente "
            "wheels verificáveis e consentimento explícito."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--plan",
        action="store_true",
        help="Resolve transitivas e artefatos sem instalar (padrão).",
    )
    group.add_argument(
        "--install",
        action="store_true",
        help="Exibe o plano completo e exige confirmação em ambiente virtual.",
    )
    args = parser.parse_args(argv)

    try:
        plan = build_install_plan()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        result = framework_install.run_install(
            "frameworks",
            plan,
            requirements_file=MEDIA_REQUIREMENTS,
            confirm=args.install,
            require_venv=args.install,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({
            "status": "error",
            "error": type(exc).__name__,
            "detail": str(exc),
        }, ensure_ascii=False))
        return 2

    status = result.get("status")
    if status in {"success", "nothing_to_do", "planned"}:
        return 0
    if status == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
