# Biblioteca de frameworks de IA da NixLMs

## Objetivo

Manter um catálogo e uma instalação modular de ferramentas de machine learning,
embeddings, recuperação e inferência. Esta biblioteca de software é independente
da biblioteca privada de documentos, da biblioteca de modelos e dos datasets.

O núcleo da NixLMs continua funcionando com a biblioteca padrão do Python.
Nenhum framework opcional é importado ou instalado automaticamente no startup.

## Quatro acervos separados

1. **Framework Library** — pacotes e ferramentas de desenvolvimento/execução.
2. **Private Knowledge Library** — documentos e trechos armazenados no SQLite local.
3. **Model Library** — checkpoints, tokenizadores e pesos disponibilizados localmente.
4. **Training Dataset Library** — dados de treino, validação, teste e benchmarks.

## Catálogo

| Grupo | Componentes | Uso |
|---|---|---|
| CPU recomendado | PyTorch, NumPy, SciPy, scikit-learn | Redes neurais, matemática e ML clássico |
| Linguagem e embeddings | Transformers, Sentence Transformers, Tokenizers | Modelos de linguagem e embeddings |
| Recuperação | FAISS CPU | Busca vetorial local |
| Inferência | ONNX Runtime CPU | Execução de modelos ONNX |
| Armazenamento | Safetensors | Pesos de tensores |
| Alternativo | TensorFlow CPU | Framework alternativo, opcional |
| GGUF | llama-cpp-python | Inferência local, instalação/compilação opcional |

TensorFlow e llama-cpp-python ficam fora do conjunto recomendado padrão para
evitar duplicação de runtimes, toolchains e pressão sobre o computador modesto.

## Inventário sem dependências

O inventário usa apenas a biblioteca padrão e não importa frameworks pesados:

```powershell
python -m nixlms_core.framework_registry
python -m nixlms_core.framework_registry --all
python -m nixlms_core.framework_registry --json
python -m nixlms_core.framework_registry --sizes
```

A detecção consulta metadados da distribuição e disponibilidade do módulo
separadamente, sem importar frameworks pesados. O estado "instalado" exige
ambos os sinais. Se apenas um estiver presente, o inventário informa
"metadata_only" ou "module_only" e não afirma que o pacote está utilizável.

O inventário não prova que um modelo específico está instalado, treinado,
carregado ou integrado, nem executa benchmark de desempenho. A opção
`--sizes` é opt-in para não adicionar varredura de arquivos ao caminho padrão.

### Proveniência, compatibilidade e footprint

O manifesto associa cada distribuição a páginas oficiais do projeto, repositório
de origem, índice de distribuição, documentação de compatibilidade e estado da
licença upstream. O SPDX só é preenchido quando o metadado do repositório
upstream o declara; `NOASSERTION` ou licença não confirmada ficam explícitos,
sem inferência. A licença do projeto principal não cobre automaticamente
dependências, modelos, checkpoints ou datasets.

O inventário informa o Python, implementação, SO e arquitetura do ambiente
atual. Ele não certifica uma matriz multiplataforma: a compatibilidade de uma
instalação deve ser resolvida no ambiente-alvo, por versão de Python, SO e
arquitetura, usando o fluxo explícito de instalação wheel-only. Sem wheel
compatível, o instalador deve falhar fechado; ARM64 continua sujeito a validação
específica e não é tratado como compatível por inferência.

O inventário padrão não percorre arquivos instalados. A opção `--sizes`
calcula, sem importar frameworks, a soma dos arquivos declarados pela
distribuição dentro de `purelib/platlib`. A medição inclui metadados da
distribuição, não inclui pesos/cache de modelos e não soma dependências
transitivas como se fossem parte do pacote. Use-a em um ambiente virtual limpo
para comparar o footprint por SO/Python/arquitetura.

RAM de pico e tempo de CPU permanecem explicitamente como `not_measured`;
não são estimados pelo tamanho do wheel ou pela presença do pacote. A
Model Library, a Training Dataset Library e a integração no runtime aparecem
como `not_inspected`/`not_verified`: pacote instalado não significa modelo
baixado, treinado, carregado ou integrado.

Fontes oficiais consultadas:
- PyTorch: https://pytorch.org/get-started/locally/
- NumPy: https://numpy.org/install/
- SciPy: https://scipy.org/install/
- scikit-learn: https://scikit-learn.org/stable/install.html
- Transformers: https://huggingface.co/docs/transformers/installation
- Sentence Transformers: https://www.sbert.net/docs/installation.html
- FAISS: https://github.com/facebookresearch/faiss/blob/main/INSTALL.md
- ONNX Runtime: https://onnxruntime.ai/docs/reference/compatibility
- Safetensors: https://huggingface.co/docs/safetensors/index
- Tokenizers: https://huggingface.co/docs/tokenizers/installation
- TensorFlow: https://www.tensorflow.org/install/pip
- llama-cpp-python: https://llama-cpp-python.readthedocs.io/en/latest/

## Instalação opcional no Windows

Use ambiente virtual para isolar dependências:

```powershell
python -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts/install-ml-cpu.ps1 -InstallTorch
```

O script instala PyTorch a partir do índice oficial CPU e depois os pacotes
de `requirements-ml-cpu.txt`. Para instalar os demais pacotes sem PyTorch,
omita `-InstallTorch`. O stack recomenda Python 3.11+; confira a matriz atual
de compatibilidade dos projetos antes de atualizar ambientes antigos.

TensorFlow e llama.cpp são opções independentes e devem ser instalados em
ambientes separados quando houver necessidade real:

```powershell
python -m pip install -r requirements-ml-tensorflow.txt
python -m pip install -r requirements-ml-llama-cpp.txt
```

A compilação de llama-cpp-python pode exigir compilador C/C++ e configuração
específica. Não é parte do caminho recomendado para o computador-alvo.

## Regras de operação e segurança

- Não instalar nem atualizar pacotes em tempo de execução.
- Não baixar modelos, datasets ou checkpoints automaticamente.
- Não executar comandos de instalação por meio do planejador/agendador.
- Registrar manualmente versões e origem de modelos adicionados ao acervo.
- Carregar modelos somente de caminhos locais explicitamente configurados.
- Preferir CPU e lotes pequenos; medir RAM/tempo antes de ativar treinamento.
- Não tornar TensorFlow, FAISS, PyTorch ou Transformers dependências obrigatórias.
- O inventário não carrega pesos nem executa código de modelos.

## Compatibilidade e validação

O núcleo permanece compatível com a matriz de Python já coberta pela CI.
A instalação opcional deve ser validada separadamente por SO, versão Python e
arquitetura. O stack de ML recomenda Python 3.11+ e não deve ser incluído na
matriz unitária básica como dependência obrigatória.

## Referências oficiais

- PyTorch: https://pytorch.org/get-started/locally/
- Transformers: https://huggingface.co/docs/transformers/installation
- Sentence Transformers: https://www.sbert.net/docs/installation.html
- ONNX Runtime: https://onnxruntime.ai/docs/get-started/with-python.html
- FAISS: https://github.com/facebookresearch/faiss
- llama.cpp: https://github.com/abetlen/llama-cpp-python
