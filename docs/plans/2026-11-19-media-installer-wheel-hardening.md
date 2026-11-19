# NixLMs — ciclo vespertino de 2026-11-19
## Hardening do instalador multimodal opcional

**Status:** implementação em branch própria; CI pendente no momento da criação deste documento.  
**Base funcional:** PR #77, commit `e037d4bf3835a5fccd509b1157b11aa72ccc9b90`.  
**Cadeia:** `main → PR #69 → PR #70 → PR #77 → esta PR`.

## 1. Plano matinal revalidado

A auditoria matinal registrada na issue [#76](https://github.com/SANTZSPAXX/NixLMs/issues/76) permanece válida contra `main` em `e146e82b216eed56e950882af344e25901a32b87`:

- A PR #69 remove o bootstrap automático de mídia do servidor e do notebook, mas o instalador multimodal ainda resolve dependências transitivas somente durante `pip install`.
- A PR #70 introduz consentimento para a Framework Library, mas a resolução de artefatos e os limites de wheels foram corrigidos na PR #77.
- A PR #77 usa `pip --dry-run --report`, `--only-binary=:all:`, origem HTTPS allowlisted, SHA-256 e instalação por URLs aprovadas com `--require-hashes`.
- A PR #77 não altera `media_install.py`; portanto, a superfície multimodal ainda não herda essas proteções.

PRs #69, #70, #71, #75 e #77 foram inspecionadas. Os workflows consultados de #69, #70, #71, #75 e #77 estavam concluídos com sucesso. A PR #77 tinha 6 jobs verdes, incluindo matriz Windows/Linux e benchmarks; não havia review submetida na PR #77 no momento da auditoria.

## 2. Lacuna e escopo único

A instalação multimodal ainda aceitava requisitos diretos e deixava pip resolver/baixar transitivas sem exibir previamente todos os artefatos. O comando também tentava instalar PyTorch CPU dentro do fluxo de mídia, duplicando responsabilidade da Framework Library.

Esta mudança:

1. Faz `media_install` delegar inventário, resolução transitiva e instalação ao resolvedor verificado da Framework Library.
2. Adiciona o mapeamento correto de distribuição `Pillow` para módulo `PIL`.
3. Exige PyTorch já presente; sua instalação CPU permanece uma etapa separada e explícita da Framework Library.
4. Mantém `--plan` como resolução read-only e `--install` com venv e confirmação exata.
5. Bloqueia source builds, origens não permitidas, wheels sem SHA-256 e alterações propostas a pacotes já instalados.
6. Não baixa modelos/datasets e não integra instalação ao runtime, scheduler ou ciclo ocioso.

## 3. Decisões e limites

- A instalação automatizada continua restrita a Windows/Linux x86-64 e Python 3.11+.
- Linux ARM64 permanece em inventário/seleção manual; não há afirmação de compatibilidade completa.
- O tamanho instalado e o consumo real de RAM/CPU continuam não medidos.
- O hash vem do relatório do índice configurado: confirma a correspondência com o artefato resolvido, mas não é assinatura independente do próprio índice.
- Uma falha de pip pode deixar o venv parcialmente alterado; não há rollback automático nem limpeza do ambiente global.
- Os quatro acervos continuam separados: Framework Library, Private Knowledge Library, Model Library e Training Dataset Library.

## 4. Validação

Comandos relevantes:

```bash
python -m unittest discover -s tests -p "test_framework_install.py"
python -m unittest discover -s tests -p "test_media_install.py"
python -m unittest discover -s tests
```

Nenhum teste local foi executado nesta execução: o clone do repositório falhou por erro de resolução DNS de `github.com`. Os resultados da GitHub Actions serão registrados após a execução real do workflow desta branch.

## 5. Referências oficiais

- pip installation reports: https://pip.pypa.io/en/stable/reference/installation-report/
- pip secure installs/hash checking: https://pip.pypa.io/en/stable/topics/secure-installs/
- pip install options: https://pip.pypa.io/en/stable/cli/pip_install/
- Python virtual environments: https://docs.python.org/3/library/venv.html
- PyTorch local installation selector: https://pytorch.org/get-started/locally/
