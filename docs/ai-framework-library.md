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
```

A detecção consulta metadados da distribuição e disponibilidade do módulo
separadamente, sem importar frameworks pesados. O estado "instalado" exige
ambos os sinais. Se apenas um estiver presente, o inventário informa
"metadata_only" ou "module_only" e não afirma que o pacote está utilizável.

O inventário não prova que um modelo específico está instalado, treinado,
carregado ou integrado, nem executa benchmark de desempenho.

### Compatibilidade, origem e footprint

A compatibilidade depende da versão exata, do SO, da versão de Python e da
arquitetura. O catálogo atual ainda não mantém uma matriz completa de licenças,
origens, hashes, tamanhos instalados ou consumo de RAM/CPU. Esses campos não
devem ser inferidos do nome do pacote nem do estado de instalação.

Evidências oficiais consultadas nesta auditoria:

- PyTorch: o instalador padrão atual exige Python 3.11+; a página de plataformas
  adicionais separa builds de ARM64 de Linux/Windows comuns.
- ONNX Runtime CPU: a documentação do pacote Python lista Windows x64 e Linux
  x64/ARM64 para o artefato CPU.
- FAISS: o projeto upstream declara Conda como forma suportada e lista CPU para
  Linux x86-64/aarch64 e Windows x86-64. O uso de `pip install faiss-cpu` no
  requirements atual não tem, nesta auditoria, a mesma garantia upstream; não
  deve ser tratado como caminho universal ou ARM64.
- TensorFlow CPU: a documentação informa que os builds Linux ARM64 são
  mantidos/testados por AWS e os builds Windows CPU por Intel, ambos terceiros.
  Continua sendo alternativa, não requisito do núcleo.

Antes de oferecer instalação, o plano deve mostrar versões resolvidas, origem
do artefato, hash quando disponível e tamanho de download. O tamanho instalado
e RAM de pico precisam ser medidos em um ambiente virtual limpo por SO/arquitetura.
A instalação deve falhar de forma explícita quando não houver wheel compatível,
em vez de iniciar compilação pesada implicitamente.

Fontes oficiais:
- PyTorch: https://pytorch.org/get-started/locally/
- PyTorch additional platforms: https://docs.pytorch.org/get-started/additional-platforms/
- ONNX Runtime: https://onnxruntime.ai/docs/get-started/with-python
- FAISS: https://github.com/facebookresearch/faiss/blob/main/INSTALL.md
- TensorFlow: https://www.tensorflow.org/install/pip

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
