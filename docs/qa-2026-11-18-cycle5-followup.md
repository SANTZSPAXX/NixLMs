# QA noturno — 18/11/2026 (ciclo 5)

## Escopo e snapshot

Auditoria do repositório canônico em 18/11/2026, com foco em runtime, aprendizagem incremental, bibliotecas locais, segurança de instalação e PRs do dia.

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- `main` observado: `6b9417f63834d47cb86221827857b99548673119`.
- PR #48 está merged; a biblioteca de frameworks foi adicionada como inventário/catálogo e requisitos opcionais, não como instalação automática.
- Nenhum teste local foi executado nesta sessão; a integração disponível permitiu inspeção e alterações remotas, mas não forneceu um checkout local executável.
- Nenhum pacote ML foi instalado, nenhum modelo/dataset foi baixado e nenhum serviço Ollama, Render ou Supabase foi iniciado.
- Nenhuma credencial, segredo, permissão ou configuração externa foi alterada.

## Integração ponta a ponta observada em `main`

| Componente | Implementação observada | Limite atual |
|---|---|---|
| Runtime/diagnóstico | `NixLMsNeuralCore` instancia módulos e executa diagnóstico; CLI e servidor web chamam `start_runtime()`. | O diagnóstico confirma presença/estado de módulos, mas não faz integridade profunda de todos os SQLite nem comprova cada job agendado. |
| Scheduler ocioso | Scheduler SQLite persistente; `respond()` chama `idle_learning.mark_activity()`; `start_runtime()` agenda `idle_learning_cycle`. | Os handlers de housekeeping, auditoria do dataset e revisão de objetivos são registrados, mas não recebem agenda automática em `main`. |
| Aprendizagem incremental | Gate de splits, treino em `train`, métricas em `validation`, checkpoint, promoção condicionada e rollback. | O split `test` não é usado no gate de promoção. O treino não consome automaticamente candidatos da biblioteca privada. |
| Private Knowledge Library | SQLite/FTS5; importação de documentos e busca de trechos integrada à resposta do agente. | Candidatos exigem aprovação e exportação explícita; a entrada no Training Dataset Library ainda é um passo manual. |
| Model Library | Gerenciador Hugging Face com registro local, download e ativação explícitos. | Não há prova de modelo baixado/carregado apenas porque o pacote/framework está presente. |
| Training Dataset Library | Dataset local separado, com splits e auditoria; datasets Hugging Face ficam em diretório próprio. | Não há uma fachada única de inventário/versionamento que una todos os datasets locais e externos. |
| Framework Library | `framework_registry.py`, requisitos opcionais e inventário sem importar frameworks pesados. | O instalador com consentimento está em PRs draft; nenhum pacote foi instalado por esta auditoria. |
| Planner/executor | GoalManager, AutonomyEngine e AutonomyPlanner estão conectados; `run_autonomy_cycle()` pode iniciar etapas elegíveis. | Em `main`, o ciclo de autonomia não é agendado. A ação `goal.start_step` muda uma etapa para `in_progress`, mas não executa a tarefa. Não equivale a executor geral. |

### Limitação do diagnóstico

O diagnóstico atual valida componentes e handlers registrados. Isso não demonstra que todos os handlers estejam agendados, que o scheduler esteja processando cada classe de job, nem que todos os bancos SQLite estejam íntegros. Em `main`, apenas `idle_learning_cycle` é agendado automaticamente pelo runtime.

## Defeito reproduzível corrigido nesta branch

### Cópia excessiva e desnecessária no sandbox de treino

Antes da correção, `LearningEngine.train_incremental()` copiava todo o diretório de dados com `shutil.copytree()`. Esse diretório pode conter:

- `private_library.sqlite3`, com documentos privados;
- `scheduler.sqlite3` e `autonomy.sqlite3`;
- histórico episódico e outros arquivos de memória;
- pesos/modelos Hugging Face e artefatos multimodais;
- caches e outros arquivos que não participam do treino candidato.

Isso criava cópias temporárias desnecessárias, podia duplicar grandes pesos em disco e ampliava a exposição temporária de dados privados. O limite do checkpoint não limitava o tamanho dessa cópia.

### Correção proposta

A branch usa uma allowlist de estado necessário:

- snapshot de `dataset.json` contendo somente `train` e `validation` (o split `test` fica fora do sandbox);
- estado do encoder, rede LIF, decoder, conhecimento e mapa mental;
- calibrações LIF/decoder, quando presentes.

Não copia SQLite, histórico episódico, modelos baixados, mídia ou caches. O candidato continua isolado em diretório temporário; a promoção e o rollback existentes não foram alterados.

Foi adicionado teste de regressão que verifica o conjunto exato de arquivos staged e a ausência de bancos, modelos, mídia e histórico.

## Biblioteca de frameworks — avaliação de segurança

### Quatro acervos

1. **Framework Library:** catálogo de pacotes e ferramentas.
2. **Private Knowledge Library:** documentos/trechos privados em SQLite.
3. **Model Library:** pesos/checkpoints locais e registro de modelos.
4. **Training Dataset Library:** datasets, splits, qrels e benchmarks.

A separação funcional existe, mas não há ainda um catálogo central que prove proveniência, licença, tamanho, arquitetura compatível e estado de integração de cada artefato.

### Stack CPU opcional

- PyTorch CPU, NumPy, SciPy, scikit-learn, Transformers, Sentence Transformers, FAISS CPU, ONNX Runtime CPU, Safetensors e Tokenizers permanecem opcionais.
- TensorFlow CPU e llama-cpp-python são alternativas separadas.
- `requirements.txt` do núcleo não deve receber essas dependências pesadas.
- O inventário usa metadados e descoberta de módulos; não deve importar frameworks para apenas listar presença.
- Presença de pacote não significa pesos baixados, modelo carregado, treinamento executado ou integração funcional.
- Tamanho instalado e RAM/CPU reais não foram medidos. Como os requisitos não estão fixados por lockfile, o tamanho depende da resolução, Python, SO e arquitetura.

### Compatibilidade — estado conservador (documentação oficial consultada em 18/11/2026)

| Pacote/grupo | SO/Python/arquitetura | Licença/origem | Observação para 8 GB RAM |
|---|---|---|---|
| PyTorch CPU | O seletor oficial oferece CPU para Windows/Linux; a versão estável atual requer Python 3.11+. O instalador #70 restringe instalação automática a x86_64; ARM64 exige validação separada. | BSD-3-Clause no projeto principal; conferir licenças de componentes incluídos. Origem: https://pytorch.org/get-started/locally/ e https://github.com/pytorch/pytorch/blob/main/LICENSE | Dependência pesada; não instalar como requisito do núcleo. |
| NumPy/SciPy/scikit-learn | NumPy publica wheels Windows/Linux e Linux aarch64, mas as tags variam por release. scikit-learn recomenda wheels binárias; em Raspberry Pi/configurações sem wheel pode ocorrer build nativo. | BSD-3-Clause nos projetos principais; wheels podem incluir bibliotecas com licenças adicionais. Origem: https://numpy.org/install/, https://scipy.org/install/, https://scikit-learn.org/stable/install.html | Evitar compilação automática e medir RSS/tempo no hardware real. |
| Transformers | Documentação estável consultada indica Python 3.10+ e PyTorch 2.5+; a documentação main indica Python 3.11+ e PyTorch 2.6+. | Apache-2.0; https://github.com/huggingface/transformers/blob/main/LICENSE | O modelo baixado/carregado costuma dominar RAM e disco, não apenas o pacote. |
| Sentence Transformers | Instalação padrão e extras ONNX CPU estão documentados; confirmar dependências resolvidas no relatório pip para a versão selecionada. | Apache-2.0; https://github.com/UKPLab/sentence-transformers | Não assumir que instalar o pacote instala pesos ou um modelo funcional. |
| FAISS CPU | A via upstream oficialmente suportada é conda: CPU em Linux x86-64/aarch64, macOS arm64 e Windows x86-64. O projeto não garante equivalência de todos os wheels PyPI; a origem do pacote `faiss-cpu` usado pelo perfil pip precisa ser comprovada. | MIT no upstream; https://github.com/facebookresearch/faiss/blob/main/LICENSE e https://github.com/facebookresearch/faiss/blob/main/INSTALL.md | Não presumir wheel pip ARM64 nem compilar durante ciclo ocioso. |
| ONNX Runtime CPU | A matriz oficial lista Windows x64 e Linux x64/ARM64 para o pacote CPU. | MIT; https://onnxruntime.ai/docs/get-started/with-python e https://github.com/microsoft/onnxruntime/blob/main/LICENSE | Candidato a backend CPU/ARM64, mas requer benchmark com modelo real. |
| Safetensors/Tokenizers | Wheels dependem de Python/SO/arquitetura; verificar tag do release antes de instalar. | Apache-2.0; https://github.com/huggingface/safetensors/blob/main/LICENSE e https://github.com/huggingface/tokenizers/blob/main/LICENSE | Não incluem pesos de modelo. |
| TensorFlow CPU | TensorFlow 2.21 documenta Python 3.10–3.13. Linux ARM64 CPU é construído/mantido/testado por AWS como terceiro; Windows CPU é distribuído por Intel como terceiro. Os binários usam instruções AVX. | Apache-2.0; https://www.tensorflow.org/install/pip e https://github.com/tensorflow/tensorflow/blob/master/LICENSE | Alternativa separada; não combinar automaticamente com PyTorch no perfil básico. |
| llama-cpp-python | A instalação recomendada pelo projeto é a partir do código-fonte com toolchain; wheels comunitários não cobrem todas as plataformas. | MIT; https://github.com/abetlen/llama-cpp-python | Manter opcional e instalar somente após plano explícito de build. |

Fontes upstream para verificação por release:
- PyTorch: https://pytorch.org/get-started/locally/ e https://github.com/pytorch/pytorch
- NumPy: https://numpy.org/install/ e https://github.com/numpy/numpy/blob/main/LICENSE.txt
- SciPy: https://scipy.org/install/ e https://github.com/scipy/scipy/blob/main/LICENSE.txt
- scikit-learn: https://scikit-learn.org/stable/install.html
- Transformers: https://huggingface.co/docs/transformers/installation
- Sentence Transformers: https://sbert.net/docs/installation.html
- FAISS: https://github.com/facebookresearch/faiss/wiki/Installing-Faiss
- ONNX Runtime: https://onnxruntime.ai/docs/install/
- Safetensors: https://github.com/huggingface/safetensors
- Tokenizers: https://github.com/huggingface/tokenizers
- TensorFlow: https://www.tensorflow.org/install/pip
- llama-cpp-python: https://github.com/abetlen/llama-cpp-python

## PRs recentes e riscos

| PR | Estado observado | Resultado da revisão |
|---|---|---|
| #48 | Merged | Inventário e documentação; CI não instalou frameworks nem modelos. |
| #55 | Aberta, não draft | Atualização de `actions/setup-python`; mergeability não substitui verificação de checks exigidos. |
| #59 | Draft | API autenticada, loopback por padrão e remote opt-in; testes usam assistant fake. Não houve teste de runtime real. |
| #60 | Draft | Orquestração limitada; não é executor geral. Callbacks são síncronos e não têm cancelamento/timeout cooperativo nesta branch. |
| #61 | Draft | Microfone exige clique/permissão, mas Web Speech pode enviar áudio ao serviço remoto do navegador; sem teste real de browser. |
| #62 | Draft | O gate de Origin para POST aceita apenas hosts loopback (ou Colab). Em Render, o Origin same-origin público também não é loopback e pode receber 403. |
| #63 | Draft | Supabase sincroniza snapshots JSON/SQLite; isso inclui biblioteca privada e outros bancos locais quando configurado. A restauração remota pode substituir arquivos locais. Não houve conexão externa. O backfill vetorial referencia `library` antes de sua atribuição, e a exceção é absorvida, impedindo o backfill inicial. |
| #68 | Closed, não merged | O controle cooperativo de timeout/cancelamento não está em `main` nem na PR #60 atual. |
| #69 | Aberta, pronta para review | Remove instalação automática no runtime, mas o instalador multimodal mostra apenas requisitos diretos; transitivas ainda não são exibidas antes do consentimento. |
| #70 | Draft | Plano de instalação CPU com resolução dry-run e confirmação. Ainda precisa restringir source builds, fixar origem e expor hashes/URLs/licenças; detecção de instalação é assimétrica quando metadados existem mas o módulo não. |
| #71 | Draft, baseada em #69 | Bloqueia sinais divergentes de módulo/metadados e caminhos/URLs diretos, mas não resolve a apresentação do conjunto transitivo instalado pelo pip. |
| #72 | Draft | Criação exclusiva do JSONL evita sobrescrever arquivo existente. CI atual foi consultada; branch ainda deriva de base anterior ao avanço de main. |
| #73 | Draft | Relatório QA anterior; parte do estado de CI foi atualizada nesta auditoria. |

### Integrações externas

- Render: não houve deploy nem alteração de variáveis. O PR #62 precisa corrigir o gate de Origin e ser testado em serviço real antes de qualquer publicação.
- Supabase: não houve conexão, migration ou upload. O PR #63 exige aviso explícito de que SQLite/documentos privados serão enviados ao PostgreSQL, backup local e política de conflito/restore antes de ser considerado seguro.
- Voz: não houve captura real. A UI deve informar claramente quando o reconhecimento usa serviço remoto do navegador.

## Testes e CI

- Testes locais: não executados por indisponibilidade de resolução DNS do GitHub no ambiente.
- Nenhum modelo, framework ou dataset foi instalado/baixado.
- Nenhum teste em i5/8 GB, Windows físico ou Linux ARM64 foi executado.
- Nenhum teste real de Ollama, microfone, Render ou Supabase foi executado.
- A CI do commit desta branch deve ser consultada antes de qualquer conclusão de aprovação; resultados anteriores de outras branches não validam este diff.

## Decisão

- Não fazer merge de PRs draft.
- Não mesclar PR #69 enquanto a apresentação de dependências transitivas e o review de consentimento estiverem pendentes.
- Não mesclar PR #63 sem corrigir o backfill, tornar explícita a transferência de dados privados e definir proteção contra sobrescrita na restauração.
- Não declarar o executor geral pronto: o ciclo de autonomia em `main` não está agendado e o executor limitado permanece em draft.
- Não instalar pacotes ML nem baixar modelos por cron, runtime ou ciclo ocioso.

## Próximos passos prioritários

1. Validar a CI da correção de staging e revisar o diff final.
2. Corrigir o backfill e o gate de Origin nas PRs correspondentes, sem alterar branches de terceiros.
3. Fechar consentimento/transitivas e segurança do instalador de frameworks; preferir wheels binárias e origem explícita.
4. Revisar PR #72 e atualizar sua base somente em branch própria, preservando o histórico.
5. Definir o contrato de execução/autonomia com timeout cooperativo, cancelamento e kill switch antes de agendar ciclos automáticos.
6. Testar persistência, SQLite, E5 e consumo de recursos no Windows físico; depois executar matriz Linux ARM64.
