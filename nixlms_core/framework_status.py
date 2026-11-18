"""Classificação leve e consistente do estado de instalação de um pacote.

Não importa o pacote nem tenta carregá-lo. Metadados de distribuição e
disponibilidade do módulo são sinais independentes; divergências são ambíguas.
"""
from __future__ import annotations


def classify_installation(version: str | None, module_available: bool) -> dict[str, bool | str]:
    """Classifica metadados e módulo sem confundir presença parcial com instalação.

    installed só é verdadeiro quando os dois sinais concordam. Uma
    distribuição sem módulo importável, ou módulo sem metadados da distribuição
    esperada, é reportada como ambígua para investigação manual.
    """
    metadata_available = isinstance(version, str) and bool(version.strip())
    module_available = bool(module_available)

    if metadata_available and module_available:
        state = "installed"
    elif metadata_available:
        state = "metadata_only"
    elif module_available:
        state = "module_only"
    else:
        state = "absent"

    return {
        "installation_state": state,
        "installed": state == "installed",
        "ambiguous_install": state in {"metadata_only", "module_only"},
        "metadata_available": metadata_available,
        "module_available": module_available,
    }
