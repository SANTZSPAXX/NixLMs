"""Instalador explícito da Framework Library; nunca chamado pelo runtime."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements-ml-cpu.txt"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
MIN_PYTHON = (3, 11)
SUPPORTED_SYSTEMS = {"Windows", "Linux"}
SUPPORTED_MACHINES = {"x86_64", "amd64"}
MODULE_MAP = {
    "scikit-learn": "sklearn",
    "sentence-transformers": "sentence_transformers",
    "faiss-cpu": "faiss",
    "huggingface-hub": "huggingface_hub",
}


def _norm(name):
    return re.sub(r"[-_.]+", "-", str(name)).lower()


def _module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _dist_name(requirement):
    value = requirement.strip()
    if "://" in value or " @ " in value or value.startswith(("git+", "file:")):
        raise ValueError("URLs e caminhos diretos não são permitidos no perfil.")
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)", value)
    if not match:
        raise ValueError("Requisito inválido no catálogo.")
    return _norm(match.group(1))


def _iter_requirements(requirements_file=REQUIREMENTS, root=ROOT):
    root = Path(root).resolve()
    path = Path(requirements_file)
    if not path.is_absolute():
        path = root / path
    seen = set()

    def visit(current):
        current = Path(current).resolve()
        if current == root or root not in current.parents:
            raise ValueError("Arquivo de requisitos fora da raiz permitida.")
        if current in seen:
            return
        seen.add(current)
        for raw in current.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r "):
                yield from visit(current.parent / line[3:].strip())
            elif line.startswith("--requirement "):
                yield from visit(current.parent / line[len("--requirement "):].strip())
            elif line.startswith("-"):
                raise ValueError("Opção de pip não permitida no perfil.")
            else:
                yield line
    yield from visit(path)


def is_virtual_environment():
    return sys.prefix != sys.base_prefix


def _environment(system=None, machine=None, python=None, venv=None):
    system = system or platform.system()
    machine = machine or platform.machine()
    python = tuple(python or sys.version_info[:2])
    if venv is None:
        venv = is_virtual_environment()
    supported = system in SUPPORTED_SYSTEMS and str(machine).lower() in SUPPORTED_MACHINES
    return {
        "platform": system,
        "architecture": machine,
        "python_version": ".".join(map(str, python)),
        "python_supported": python >= MIN_PYTHON,
        "platform_supported": supported,
        "virtual_environment": bool(venv),
    }


def build_install_plan(requirements_file=REQUIREMENTS, *, root=ROOT,
                       module_probe=None, version_probe=None, system=None,
                       machine=None, python=None, venv=None):
    """Plano offline; só consulta metadados e find_spec, sem imports ML ou pip."""
    module_probe = module_probe or _module_available
    version_probe = version_probe or _version
    env = _environment(system, machine, python, venv)
    packages, seen = [], set()
    for requirement in _iter_requirements(requirements_file, root):
        dist = _dist_name(requirement)
        if dist in seen:
            continue
        seen.add(dist)
        module = MODULE_MAP.get(dist, dist.replace("-", "_"))
        installed_version = version_probe(dist)
        module_present = bool(module_probe(module))
        packages.append({
            "requirement": requirement,
            "distribution": dist,
            "module": module,
            "installed": installed_version is not None,
            "version": installed_version,
            "module_available": module_present,
            "ambiguous_install": module_present and installed_version is None,
        })

    torch_version = version_probe("torch")
    torch_module = bool(module_probe("torch"))
    torch_installed = torch_version is not None
    missing = [p["requirement"] for p in packages if not p["installed"]]
    ambiguous = sorted(p["distribution"] for p in packages if p["ambiguous_install"])
    reasons = []
    if missing and not env["python_supported"]:
        reasons.append("O stack atual exige Python 3.11 ou superior.")
    if missing and not env["platform_supported"]:
        reasons.append("Instalação automática limitada a Windows/Linux x86-64; ARM64 exige seleção manual.")
    if missing and not torch_installed:
        reasons.append(
            "PyTorch ausente; instale-o primeiro com --install-torch-cpu para evitar resolução implícita."
            if not torch_module else
            "Módulo torch presente sem metadados de distribuição; instalação bloqueada."
        )
    if ambiguous:
        reasons.append("Módulos sem metadados de distribuição: " + ", ".join(ambiguous))
    blocked = bool(reasons)
    return {
        "automatic_install": False,
        "requirements_file": Path(requirements_file).name,
        **env,
        "torch": {
            "installed": torch_installed,
            "version": torch_version,
            "module_available": torch_module,
            "variant": "unknown_not_imported" if torch_installed else "missing",
        },
        "packages": packages,
        "missing_direct_requirements": missing,
        "ambiguous_packages": ambiguous,
        "blocked": blocked,
        "blocked_reasons": reasons,
        "install_allowed": bool(missing) and not blocked and env["virtual_environment"],
        "transitive_dependencies": "not_resolved_offline; --install uses pip dry-run report",
    }


def build_torch_plan(*, module_probe=None, version_probe=None, system=None,
                     machine=None, python=None, venv=None):
    module_probe = module_probe or _module_available
    version_probe = version_probe or _version
    env = _environment(system, machine, python, venv)
    version = version_probe("torch")
    module_present = bool(module_probe("torch"))
    installed = version is not None
    reasons = []
    if not installed and module_present:
        reasons.append("Módulo torch presente sem metadados; não será sobrescrito.")
    if not installed and not env["python_supported"]:
        reasons.append("PyTorch stable atual exige Python 3.11 ou superior.")
    if not installed and not env["platform_supported"]:
        reasons.append("Wheel CPU automático não habilitado; selecione uma distribuição oficial compatível.")
    return {
        "automatic_install": False,
        "action": "preserve" if installed else "install_cpu_if_confirmed",
        **env,
        "torch": {
            "installed": installed,
            "version": version,
            "module_available": module_present,
            "variant": "unknown_not_imported" if installed else "missing",
        },
        "blocked": bool(reasons),
        "blocked_reasons": reasons,
        "install_allowed": not installed and not reasons and env["virtual_environment"],
        "index": TORCH_CPU_INDEX,
    }


def _pip_supports_report(run):
    try:
        result = run([sys.executable, "-m", "pip", "install", "--help"],
                     capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    help_text = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0 and "--dry-run" in help_text and "--report" in help_text


def _summarize_report(report):
    packages = []
    for item in report.get("install", []):
        meta = item.get("metadata") or {}
        name, version = str(meta.get("name") or "").strip(), str(meta.get("version") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("Nome de pacote inválido no relatório pip.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version):
            raise ValueError("Versão inválida no relatório pip.")
        packages.append({"name": name, "version": version, "direct": bool(item.get("requested"))})
    return sorted(packages, key=lambda p: _norm(p["name"]))


def _resolve(arguments, run):
    with tempfile.TemporaryDirectory(prefix="nixlms-framework-plan-") as temp:
        report_path = Path(temp) / "pip-report.json"
        command = [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-upgrade", "--dry-run", "--report", str(report_path), *arguments,
        ]
        try:
            result = run(command, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Falha ao resolver o plano pip.") from exc
        if result.returncode != 0 or not report_path.is_file():
            raise RuntimeError("pip não produziu relatório de resolução.")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Relatório pip inválido.") from exc
        if not isinstance(report, dict) or not isinstance(report.get("install", []), list):
            raise RuntimeError("Estrutura de relatório pip não reconhecida.")
        return _summarize_report(report)


def _freeze(run):
    try:
        result = run([sys.executable, "-m", "pip", "freeze"],
                     capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    values = {}
    for line in (result.stdout or "").splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            values[_norm(name)] = version
    return values


def _freeze_diff(before, after):
    if before is None or after is None:
        return {}
    return {
        name: {"before": before.get(name), "after": after.get(name)}
        for name in sorted(set(before) | set(after))
        if before.get(name) != after.get(name)
    }


def run_install(mode, plan, *, requirements_file=REQUIREMENTS, run=subprocess.run,
                input_fn=None, version_probe=None, module_probe=None, venv=None):
    if mode not in {"frameworks", "torch_cpu"}:
        return {"status": "blocked", "reason": "Modo inválido."}
    version_probe = version_probe or _version
    module_probe = module_probe or _module_available
    if venv is None:
        venv = bool(plan.get("virtual_environment"))

    if mode == "frameworks":
        if not plan.get("missing_direct_requirements"):
            return {"status": "nothing_to_do", "planned_packages": []}
        if not plan.get("torch", {}).get("installed"):
            return {"status": "blocked", "reason": "PyTorch precisa estar presente antes do stack."}
        arguments = ["-r", str(Path(requirements_file).resolve())]
    else:
        if plan.get("torch", {}).get("installed"):
            return {"status": "nothing_to_do", "planned_packages": []}
        arguments = ["torch", "--index-url", TORCH_CPU_INDEX]

    if not venv:
        return {"status": "blocked", "reason": "Ative um ambiente virtual antes de instalar."}
    if plan.get("blocked"):
        return {"status": "blocked", "reason": "; ".join(plan.get("blocked_reasons", []))}
    if not plan.get("install_allowed"):
        return {"status": "blocked", "reason": "Plano não autoriza instalação nesta plataforma."}
    if not _pip_supports_report(run):
        return {"status": "blocked", "reason": "pip 22.2+ com --dry-run e --report é necessário; atualize manualmente no venv."}

    try:
        planned = _resolve(arguments, run)
    except RuntimeError as exc:
        return {"status": "failed", "reason": str(exc)}
    if not planned:
        return {"status": "nothing_to_do", "planned_packages": []}

    conflicts = []
    for item in planned:
        current = version_probe(item["name"])
        module = MODULE_MAP.get(_norm(item["name"]), _norm(item["name"]).replace("-", "_"))
        module_present = bool(module_probe(module))
        if current is not None or module_present:
            conflicts.append({
                "name": item["name"], "installed_version": current,
                "module_available_without_metadata": module_present and current is None,
                "planned_version": item["version"],
            })
    if conflicts:
        return {
            "status": "blocked",
            "reason": "O resolvedor propôs alterar distribuições já instaladas.",
            "conflicts": conflicts,
        }

    input_fn = input_fn or input
    try:
        answer = input_fn("Digite INSTALAR para autorizar exatamente os pacotes listados: ").strip()
    except EOFError:
        answer = ""
    if answer != "INSTALAR":
        return {"status": "cancelled", "planned_packages": planned,
                "models_or_datasets_downloaded": False}

    before = _freeze(run)
    specs = [p["name"] + "==" + p["version"] for p in planned]
    command = [
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-upgrade", "--no-deps",
    ]
    if mode == "torch_cpu":
        command.extend(["--index-url", TORCH_CPU_INDEX])
    command.extend(specs)
    try:
        result = run(command, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "failed", "reason": "Instalação falhou ou excedeu 30 minutos.",
                "planned_packages": planned, "before_after_report_available": before is not None}
    after = _freeze(run)
    if result.returncode != 0:
        return {
            "status": "failed", "reason": "pip retornou erro; revise o ambiente antes de tentar novamente.",
            "returncode": result.returncode, "planned_packages": planned,
            "changed_packages": _freeze_diff(before, after),
            "models_or_datasets_downloaded": False,
        }
    return {
        "status": "success", "planned_packages": planned,
        "changed_packages": _freeze_diff(before, after),
        "freeze_report_complete": before is not None and after is not None,
        "models_or_datasets_downloaded": False, "automatic_install": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Instalação opcional e explícita da Framework Library.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan", action="store_true", help="Plano offline, sem instalação.")
    group.add_argument("--install", action="store_true", help="Resolve, exibe relatório e pede confirmação.")
    group.add_argument("--install-torch-cpu", action="store_true", help="Instala somente PyTorch CPU.")
    args = parser.parse_args(argv)
    try:
        mode = "torch_cpu" if args.install_torch_cpu else "frameworks"
        plan = build_torch_plan() if mode == "torch_cpu" else build_install_plan()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if not args.install and not args.install_torch_cpu:
            print("Somente consulta; nenhuma instalação ou resolução de rede foi executada.")
            return 0
        result = run_install(mode, plan)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] in {"success", "nothing_to_do"}:
            return 0
        return 2 if result["status"] == "blocked" else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__, "detail": str(exc)},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
