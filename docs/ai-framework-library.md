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

A detecção consulta metadados e disponibilidade dos módulos. Não prova que um
modelo específico pode ser carregado nem executa benchmark de desempenho.

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

### Perfil multimodal — somente instalação manual

O perfil de imagem/vídeo é opcional e não é preparado no startup. Em ambiente
virtual, use `python -m nixlms_core.media_install --plan` para visualizar o
inventário de pacotes ausentes e `python -m nixlms_core.media_install --install`
para solicitar a instalação com confirmação explícita. O instalador não baixa
modelos/datasets e não atualiza módulos já presentes. Linux ARM64 exige que o
operador selecione e instale PyTorch compatível antes de liberar os demais
pacotes.

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
