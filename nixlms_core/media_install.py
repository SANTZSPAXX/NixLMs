"""Instalação explícita e auditável do perfil multimodal opcional.

Este módulo nunca é chamado pelo runtime. A instalação exige --install,
ambiente virtual e confirmação digitada pelo operador.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA_REQUIREMENTS = ROOT / "requirements-hf-media.txt"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
MODULE_MAP = {
    "huggingface-hub": "huggingface_hub",
    "imageio-ffmpeg": "imageio_ffmpeg",
    "pillow": "PIL",
}


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _distribution_name(requirement: str) -> str:
    value = requirement.strip()
    if (
        "://" in value or " @ " in value
        or value.startswith(("git+", "file:", "/", "./", "../"))
        or re.match(r"^[A-Za-z]:[\\/]", value)
    ):
        raise ValueError("URLs e caminhos diretos não são permitidos no perfil.")
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)", value)
    if not match:
        raise ValueError("Requisito inválido: " + requirement)
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _iter_requirements(requirements_file: Path, root: Path):
    root = Path(root).resolve()
    path = Path(requirements_file)
    if not path.is_absolute():
        path = root / path
    seen = set()

    def visit(current: Path):
        current = current.resolve()
        if root not in current.parents:
            raise ValueError("Arquivo de requisitos fora da raiz permitida.")
        if current in seen:
            return
        seen.add(current)
        for raw in current.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r "):
                nested = (current.parent / line[3:].strip()).resolve()
                yield from visit(nested)
            elif line.startswith("-"):
                raise ValueError("Opção de pip não permitida no perfil: " + line)
            else:
                yield line

    yield from visit(path)


def _module_for_distribution(distribution: str) -> str:
    return MODULE_MAP.get(distribution, distribution.replace("-", "_"))


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
    """Build a no-network package plan using metadata/spec discovery only."""
    module_probe = module_probe or _module_available
    version_probe = version_probe or _installed_version
    system_name = system_name or platform.system()
    machine = machine or platform.machine()
    python_version = tuple(python_version or sys.version_info[:2])
    python_supported = python_version >= (3, 11)
    packages = []
    seen = set()
    ambiguous_packages = []
    for requirement in _iter_requirements(Path(requirements_file), Path(root)):
        distribution = _distribution_name(requirement)
        if distribution in seen:
            continue
        seen.add(distribution)
        module = _module_for_distribution(distribution)
        version = version_probe(distribution)
        module_available = bool(module_probe(module))
        installed = version is not None or module_available
        ambiguous_install = (version is not None) != module_available
        if ambiguous_install:
            ambiguous_packages.append(distribution)
        packages.append({
            "requirement": requirement,
            "distribution": distribution,
            "module": module,
            "installed": installed,
            "version": version,
            "module_available": module_available,
            "ambiguous_install": ambiguous_install,
        })

    torch_version = version_probe("torch")
    torch_module_available = bool(module_probe("torch"))
    torch_installed = torch_version is not None or torch_module_available
    torch_ambiguous = (torch_version is not None) != torch_module_available
    cpu_index_supported = (
        system_name in {"Windows", "Linux"}
        and machine.lower() in {"x86_64", "amd64"}
    )
    missing_requirements = [
        item["requirement"] for item in packages if not item["installed"]
    ]
    blocked_reasons = []
    if not python_supported:
        blocked_reasons.append("Este perfil exige Python 3.11 ou superior.")
    if torch_ambiguous:
        blocked_reasons.append(
            "Metadados e módulo torch divergem; instalação bloqueada para preservar o ambiente."
        )
    if ambiguous_packages:
        blocked_reasons.append(
            "Pacotes com metadados/módulo divergentes: " + ", ".join(sorted(ambiguous_packages))
        )
    if not torch_installed and not cpu_index_supported:
        blocked_reasons.append(
            "PyTorch ausente: selecione e instale manualmente um wheel compatível "
            "com esta plataforma em https://pytorch.org/get-started/locally/."
        )
    blocked = bool(blocked_reasons)
    blocked_reason = "; ".join(blocked_reasons) if blocked_reasons else None
    return {
        "automatic_install": False,
        "requirements_file": Path(requirements_file).name,
        "platform": system_name,
        "architecture": machine,
        "python_version": ".".join(str(part) for part in python_version),
        "python_supported": python_supported,
        "torch": {
            "installed": torch_installed,
            "version": torch_version,
            "module_available": torch_module_available,
            "ambiguous_install": torch_ambiguous,
            "action": (
                "preserve" if torch_installed
                else "install_cpu" if cpu_index_supported
                else "manual_platform_selection"
            ),
            "cpu_index_supported": cpu_index_supported,
        },
        "packages": packages,
        "missing_requirements": missing_requirements,
        "ambiguous_packages": sorted(ambiguous_packages),
        "blocked": blocked,
        "blocked_reason": blocked_reason,
    }


def is_virtual_environment() -> bool:
    return (
        getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or hasattr(sys, "real_prefix")
    )


def _pip_freeze() -> dict:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            check=False, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    installed = {}
    for line in result.stdout.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            installed[re.sub(r"[-_.]+", "-", name).lower()] = version
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Planeja ou instala explicitamente dependências multimodais opcionais."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan", action="store_true", help="Somente mostra o plano (padrão).")
    group.add_argument("--install", action="store_true", help="Solicita confirmação e instala.")
    args = parser.parse_args(argv)

    if args.install and not is_virtual_environment():
        print("Instalação recusada: ative um ambiente virtual antes de continuar.")
        return 2

    try:
        plan = build_install_plan()
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.install:
        print("Somente consulta; nenhuma instalação foi executada.")
        return 0
    if plan["blocked"]:
        print("Instalação bloqueada: " + str(
            plan.get("blocked_reason") or "compatibilidade não confirmada."
        ))
        return 2

    torch_missing = not plan["torch"]["installed"]
    missing = plan["missing_requirements"]
    if not torch_missing and not missing:
        print("Todas as dependências diretas já estão presentes; nada a instalar.")
        return 0

    try:
        answer = input("Digite INSTALAR para autorizar os pacotes listados: ").strip()
    except EOFError:
        answer = ""
    if answer != "INSTALAR":
        print("Instalação cancelada; nenhum pacote foi alterado.")
        return 1

    before = _pip_freeze()
    try:
        if torch_missing:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "install", "--no-upgrade",
                    "torch", "--index-url", TORCH_CPU_INDEX,
                ],
                check=True, timeout=1800,
            )
        if missing:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-upgrade", *missing],
                check=True, timeout=1800,
            )
        after = _pip_freeze()
        changed = {
            name: {"before": before.get(name), "after": after.get(name)}
            for name in sorted(set(before) | set(after))
            if before.get(name) != after.get(name)
        }
        print(json.dumps({
            "status": "success",
            "planned_requirements": missing,
            "torch_cpu_installed": torch_missing,
            "installed_or_changed": changed,
            "models_or_datasets_downloaded": False,
        }, ensure_ascii=False, indent=2))
        return 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({
            "status": "failed",
            "error": type(exc).__name__,
            "returncode": getattr(exc, "returncode", None),
            "note": "Revise o ambiente antes de tentar novamente; nenhuma atualização automática será repetida.",
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
