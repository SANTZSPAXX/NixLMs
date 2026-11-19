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

Use um ambiente virtual dedicado para instalar. O planejamento resolve o conjunto
transitivo e os artefatos, pode consultar os índices oficiais e não altera o ambiente:

- \`python -m venv .venv-ml\`
- Windows: \`.\\.venv-ml\\Scripts\\Activate.ps1\`
- Linux: \`source .venv-ml/bin/activate\`
- \`python -m nixlms_core.framework_install --plan\`

O PyTorch CPU é uma etapa separada para impedir que Sentence Transformers faça
uma resolução implícita de uma distribuição PyTorch não selecionada:

- \`python -m nixlms_core.framework_install --install-torch-cpu\`
- Depois, \`python -m nixlms_core.framework_install --install\`

Cada modo de instalação:
- exige Python 3.11+ e ambiente virtual ativo para instalar;
- limita a instalação automática a Windows/Linux x86-64;
- resolve dependências diretas e transitivas com pip dry-run/report;
- aplica somente wheels binárias na resolução e na instalação; se não houver wheel
  compatível, falha sem tentar compilar source;
- exige URL HTTPS de origem permitida, artefato .whl e SHA-256 por pacote;
- exibe origem, URL do artefato, hash e tamanho de download quando o host informa
  Content-Length; consultas HEAD têm limite agregado efetivo de 15 segundos; tamanho
  instalado e RAM/CPU permanecem não medidos;
- o comando --plan exibe o conjunto transitivo sem instalar; pode consultar índice
  e fazer HEAD para obter tamanho, mas não altera o ambiente;
- o comando --install apresenta o plano completo antes de exigir a digitação
  exata de INSTALAR;
- instala somente URLs e hashes aprovados, usando no-index, no-deps, no-upgrade e require-hashes,
  sem resolver novamente nomes/versões no índice;
- bloqueia estados ambíguos quando metadados e módulo não estão presentes juntos;
- registra a diferença de pip freeze antes/depois;
- não atualiza pip, não baixa modelos/datasets e não é chamado pelo runtime.


O relatório do pip é uma previsão de resolução, não um lockfile nem uma garantia
de compatibilidade em hardware não testado. O instalador conserva a URL e o
SHA-256 de cada wheel e passa o hash no URL direto durante a instalação. O tamanho
de download depende da resposta HEAD do host e pode ficar indisponível. Se a
instalação falhar no meio, pode haver pacotes parciais; revise o relatório e o
ambiente antes de tentar novamente.

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
modelos/datasets. A política de wheels, origem e hash desta mudança cobre a
Framework Library; a resolução transitiva e a verificação de artefatos do perfil
multimodal permanecem pendentes de uma PR própria.

### ARM64 e outras plataformas

Linux ARM64 e plataformas não verificadas ficam em modo de inventário/planejamento.
O instalador automático não escolhe wheels por tentativa nem compila pacotes; a
resolução falha fechada quando não encontra wheel, origem ou hash verificáveis.
O operador deve consultar a documentação oficial de cada projeto e selecionar
wheels compatíveis manualmente. Não declaramos a stack completa validada em ARM64.

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
- pip hash-checking mode: https://pip.pypa.io/en/stable/topics/secure-installs/
- Python virtual environments: https://docs.python.org/3/library/venv.html
- Transformers: https://huggingface.co/docs/transformers/installation
- Sentence Transformers: https://www.sbert.net/docs/installation.html
- ONNX Runtime: https://onnxruntime.ai/docs/get-started/with-python.html
- FAISS: https://github.com/facebookresearch/faiss
- llama-cpp-python: https://github.com/abetlen/llama-cpp-python
