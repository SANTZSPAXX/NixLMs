# Biblioteca de frameworks de IA da NixLMs

## Objetivo

Manter um catálogo e uma instalação modular de ferramentas de machine learning,
embeddings, recuperação e inferência. Esta biblioteca de software é independente
da biblioteca privada de documentos, da biblioteca de modelos e dos datasets.

O núcleo da NixLMs continua funcionando com a biblioteca padrão do Python.
Nenhum framework opcional é importado ou instalado automaticamente no startup,
agendador, ciclo ocioso ou execução de tarefas.

## Quatro acervos separados

1. **Framework Library** — pacotes e ferramentas de desenvolvimento/execução.
2. **Private Knowledge Library** — documentos e trechos armazenados no SQLite local.
3. **Model Library** — checkpoints, tokenizadores e pesos disponibilizados localmente.
4. **Training Dataset Library** — dados de treino, validação, teste e benchmarks.

A presença de um pacote na Framework Library não significa que um modelo esteja
baixado, carregado, treinado ou integrado à NixLMs.

## Catálogo atual

| Grupo | Componentes | Uso |
|---|---|---|
| CPU recomendado | PyTorch, NumPy, SciPy, scikit-learn | Redes neurais, matemática e ML clássico |
| Linguagem e embeddings | Transformers, Sentence Transformers, Tokenizers | Modelos de linguagem e embeddings |
| Recuperação | FAISS CPU | Busca vetorial local |
| Inferência | ONNX Runtime CPU | Inferência de modelos ONNX em CPU |
| Armazenamento | Safetensors | Serialização de tensores |
| Alternativo | TensorFlow CPU | Framework alternativo, opcional |
| GGUF | llama-cpp-python | Inferência local, instalação/compilação opcional |

TensorFlow e llama-cpp-python ficam fora do conjunto recomendado padrão para
evitar duplicação de runtimes, toolchains e pressão sobre o computador modesto.
A matriz detalhada de licenças, versões, wheels por arquitetura e footprint
instalado ainda precisa ser catalogada; o inventário atual não estima RAM/CPU.

## Inventário sem dependências pesadas

O inventário usa a biblioteca padrão e não importa frameworks, inicializa modelos
ou consulta a rede:

- \`python -m nixlms_core.framework_registry\`
- \`python -m nixlms_core.framework_registry --all\`
- \`python -m nixlms_core.framework_registry --json\`

A detecção de pacotes não prova que um modelo específico possa ser carregado.
O estado do pacote não é evidência de checkpoint instalado, treinamento ou
integração funcional.

## Instalação opcional e explícita

Use um ambiente virtual dedicado. O modo de planejamento é offline e não altera
o ambiente:

- \`python -m venv .venv-ml\`
- Windows: \`.\\.venv-ml\\Scripts\\Activate.ps1\`
- Linux: \`source .venv-ml/bin/activate\`
- \`python -m nixlms_core.framework_install --plan\`

O PyTorch CPU é uma etapa separada para impedir que Sentence Transformers faça
uma resolução implícita de uma distribuição PyTorch não selecionada:

- \`python -m nixlms_core.framework_install --install-torch-cpu\`
- Depois, \`python -m nixlms_core.framework_install --install\`

Cada modo de instalação:
- exige Python 3.11+ e ambiente virtual ativo;
- limita a instalação automática a Windows/Linux x86-64;
- resolve dependências com \`pip install --dry-run --report\` e mostra nomes/versões;
- exige digitação exata de \`INSTALAR\` depois do relatório;
- instala somente as versões listadas no relatório, usando \`--no-deps --no-upgrade\`;
- bloqueia quando o resolvedor propõe alterar uma distribuição já instalada;
- registra a diferença de \`pip freeze\` antes/depois;
- não atualiza pip, não baixa modelos/datasets e não é chamado pelo runtime.

O relatório do pip é uma previsão de resolução, não um lockfile. A instalação
usa as versões exatas exibidas no relatório. Se a instalação falhar no meio,
pode haver pacotes parciais; revise o relatório e o ambiente antes de tentar
novamente.

### Windows PowerShell

- Somente plano: \`scripts/install-ml-cpu.ps1 -Plan\`
- Instalar stack, com PyTorch já presente: \`scripts/install-ml-cpu.ps1 -Install\`
- Instalar somente PyTorch CPU: \`scripts/install-ml-cpu.ps1 -InstallTorchCpu\`
- Compatibilidade legada: \`scripts/install-ml-cpu.ps1 -InstallTorch\` executa
  as duas etapas, com confirmação independente para cada uma.

O arquivo Batch continua encaminhando os argumentos ao PowerShell.

### Perfil multimodal — somente instalação manual

O perfil de imagem/vídeo é opcional e não é preparado no startup. A inicialização
do servidor, runtime, agendador, ciclo ocioso e notebook Colab não instala,
atualiza nem compila pacotes. Em ambiente virtual, use:

- \`python -m nixlms_core.media_install --plan\`
- \`python -m nixlms_core.media_install --install\`

O instalador multimodal também exige confirmação explícita e não baixa
modelos/datasets.

### ARM64 e outras plataformas

Linux ARM64 e plataformas não verificadas ficam em modo de inventário/planejamento.
O instalador não escolhe wheels por tentativa nem compila pacotes. O operador
deve consultar a documentação oficial de cada projeto e selecionar wheels
compatíveis manualmente. Não declaramos a stack completa validada em ARM64.

## Regras de operação e segurança

- Nunca instalar, atualizar ou compilar pacotes no startup, agendador, ciclo
  ocioso ou executor de tarefas.
- Não baixar modelos, datasets ou checkpoints automaticamente.
- Não executar comandos de instalação por meio do planejador/agendador.
- Carregar modelos somente de caminhos locais explicitamente configurados.
- Preferir CPU e lotes pequenos; medir RAM/tempo antes de ativar treinamento.
- Não tornar TensorFlow, FAISS, PyTorch ou Transformers dependências obrigatórias.
- Preservar pacotes existentes; a instalação bloqueia quando o resolvedor propõe
  alterar uma distribuição já presente.
- O inventário não carrega pesos nem executa código de modelos.

## Referências oficiais

- PyTorch e seleção de plataforma/CPU: https://pytorch.org/get-started/locally/
- pip install report e dry-run: https://pip.pypa.io/en/stable/reference/installation-report/
- pip install options: https://pip.pypa.io/en/stable/cli/pip_install/
- Python virtual environments: https://docs.python.org/3/library/venv.html
- Transformers: https://huggingface.co/docs/transformers/installation
- Sentence Transformers: https://www.sbert.net/docs/installation.html
- ONNX Runtime: https://onnxruntime.ai/docs/get-started/with-python.html
- FAISS: https://github.com/facebookresearch/faiss
- llama-cpp-python: https://github.com/abetlen/llama-cpp-python
