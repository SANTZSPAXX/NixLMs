# QA noturno — 2026-11-18

## Estado observado

- Repositório: `SANTZSPAXX/NixLMs`
- `main` antes da consolidação: `6b9417f63834d47cb86221827857b99548673119`
- PR #55 foi mesclada após revisão de diff e CI: merge commit `e146e82b216eed56e950882af344e25901a32b87`.
- Nenhuma outra PR foi mesclada neste ciclo.
- Não houve release, deploy, force-push, exclusão de branch, alteração de secrets ou acesso a serviços externos.

## Correção nesta branch

O inventário de frameworks confundia metadados de distribuição e disponibilidade do módulo:
- `version != None OR find_spec(module) != None` podia marcar como instalado um pacote parcialmente quebrado.
- O servidor web mantinha uma segunda implementação com a mesma falha.
- O painel só apresentava instalado/não instalado e ocultava a inconsistência.

Esta branch adiciona `nixlms_core/framework_status.py`, classifica quatro estados (`installed`, `metadata_only`, `module_only`, `absent`), alinha o inventário do servidor e exibe `INCONSISTENTE` no painel. `installed` só é verdadeiro quando metadados e módulo estão presentes.

Testes de regressão adicionados para os dois estados parciais e para o contrato da API web. A execução local não foi possível: o clone isolado falhou por DNS (`Could not resolve host: github.com`). A CI da PR #75 foi concluída: run #44424702564 (quatro matrizes, 317 testes por ambiente e dois benchmarks) e CodeQL #44424702610; todos os jobs success. Os logs individuais confirmam `Ran 317 tests` e `OK` nos quatro ambientes; CodeQL analisou 69/69 arquivos Python e 2/2 workflows.

## PR #48 — Framework Library

[PR #48](https://github.com/SANTZSPAXX/NixLMs/pull/48) está mesclada. A CI [#44322381961](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44322381961) executou a matriz Windows/Ubuntu e os dois benchmarks. Os logs de teste registraram 250 testes por ambiente; os jobs de benchmark concluíram com sucesso.

Os logs não mostram instalação de PyTorch, Transformers, FAISS, TensorFlow ou outros pacotes ML. Portanto, a PR criou catálogo/requirements/instalador, mas não prova que frameworks ou modelos estejam instalados no computador do operador.

O instalador ainda presente em `main`:
- atualiza pip automaticamente;
- apenas recomenda venv, sem exigir ambiente virtual;
- não apresenta um plano completo de versões transitivas antes de instalar.

A correção proposta está em [PR #70](https://github.com/SANTZSPAXX/NixLMs/pull/70), ainda não integrada.

## Compatibilidade e origem dos frameworks

- PyTorch: a página oficial atual informa Python 3.11+ para a versão estável mais recente; a instalação CPU padrão é selecionada por SO e compute platform. Builds ARM64 aparecem em fluxo separado de plataformas adicionais.
- ONNX Runtime CPU: o pacote Python oficial lista Windows x64 e Linux x64/ARM64.
- FAISS: o upstream declara Conda como caminho suportado; o pacote CPU Conda é listado para Linux x86-64/aarch64 e Windows x86-64. O uso de `pip install faiss-cpu` no requirements da NixLMs não foi validado como caminho oficial equivalente.
- TensorFlow CPU: os builds Linux ARM64 são mantidos/testados por AWS e os builds Windows CPU por Intel, conforme a documentação oficial; ambos são terceiros.
- Para NumPy, SciPy, scikit-learn, Transformers, Sentence Transformers, Safetensors e Tokenizers, a compatibilidade precisa ser verificada por release/wheel antes de prometer a matriz completa.
- O registry atual não registra licença, origem/hash, tamanho instalado ou RAM de pico. Nenhum desses valores foi inventado ou medido.
- Não foram instalados pacotes nem baixados modelos/datasets neste ciclo.

Fontes:
- https://pytorch.org/get-started/locally/
- https://docs.pytorch.org/get-started/additional-platforms/
- https://onnxruntime.ai/docs/get-started/with-python
- https://github.com/facebookresearch/faiss/blob/main/INSTALL.md
- https://www.tensorflow.org/install/pip

## Integração ponta a ponta em main

| Capacidade | Evidência no código atual | Estado real |
|---|---|---|
| Diagnóstico de startup | `NixLMsNeuralCore.run_startup_diagnostics()`, chamado na inicialização e em `start_runtime()` | Integrado |
| Agendador ocioso | `start_runtime()` agenda `idle_learning_cycle` | Integrado |
| Aprendizagem incremental | `IdleLearningManager` chama `train_incremental()`; candidato em sandbox, validação, checkpoint e rollback | Integrado com gates |
| Cancelamento da aprendizagem | `mark_activity()` apenas reinicia relógio; não cancela treino em andamento. `TaskScheduler.stop()` interrompe o loop, não o handler atual | Ausente |
| Biblioteca privada | SQLite/FTS, importação e busca integradas ao chat e API web | Parcialmente integrado |
| Candidatos de aprendizagem da biblioteca privada | Métodos de aprovação/exportação existem no módulo, mas não foi encontrada rota web/CLI de ponta a ponta para esse fluxo | Parcial |
| Model Library | Gerenciador Hugging Face permite operações explícitas de modelos locais | Integrado em escopo limitado |
| Training Dataset Library | `DatasetStore` usa arquivo JSON; valida splits e serve ao treino incremental | Integrado, não SQLite |
| Planejador de objetivos | Seleciona etapas elegíveis e `goal.start_step` transiciona para `in_progress` | Planejador, não executor |
| Executor de tarefas | O engine de ações existe, mas não há ciclo de execução de tarefas do planner agendado em `main` | Não integrado ponta a ponta |
| Framework adapters | O catálogo detecta pacotes; não há integração geral dos frameworks listados | Não integrado |

## PRs recentes e riscos

### Runtime e instalação

- [PR #69](https://github.com/SANTZSPAXX/NixLMs/pull/69) remove a instalação automática de mídia em runtime e oferece instalador explícito. Ainda não foi integrada. Em `main`, `server.main()` chama `media.bootstrap_async()` e `NIXLMS_AUTO_INSTALL_MEDIA` usa default `1`; o worker pode executar pip install em background no startup. Risco crítico até a correção ser integrada.
- [PR #70](https://github.com/SANTZSPAXX/NixLMs/pull/70) adiciona instalador de frameworks com consentimento e venv. A inspeção encontrou assimetria: metadados presentes com módulo ausente ainda podem ser tratados como instalado. Também falta restringir a wheels e apresentar origem/hash/tamanho do artefato.
- [PR #71](https://github.com/SANTZSPAXX/NixLMs/pull/71) melhora detecção de instalações inconsistentes no instalador de mídia; não resolve a apresentação completa de dependências transitivas antes da confirmação.
- [PR #72](https://github.com/SANTZSPAXX/NixLMs/pull/72) protege exportação de candidatos contra sobrescrita com criação exclusiva. Está em draft e baseada em branch anterior; CI passou, mas não foi mesclada.
- [PR #74](https://github.com/SANTZSPAXX/NixLMs/pull/74) limita o sandbox de treino a estado necessário e linhas train/validation; exclui split test. CI e CodeQL passaram. Ainda falta validar E5 real, RAM e hardware físico.

### Autonomia, voz, API e cloud

- [PR #59](https://github.com/SANTZSPAXX/NixLMs/pull/59): gateway autenticado por padrão em loopback. O modo remoto não aplica TLS no próprio servidor; não habilitar sem proxy HTTPS confiável e teste de origem.
- [PR #60](https://github.com/SANTZSPAXX/NixLMs/pull/60): branch agenda autonomia com default ON. Sem handlers, etapas manuais podem ir para `in_progress` sem execução. Callbacks são síncronos, sem timeout/cancelamento cooperativo; PR #68 foi fechada sem merge. Scripts de autostart usam `Register-ScheduledTask -Force`, podendo substituir tarefa homônima.
- [PR #61](https://github.com/SANTZSPAXX/NixLMs/pull/61): Web Speech API pode enviar áudio ao serviço do navegador. A documentação informa isso, mas a UI precisa avisar e obter consentimento informado antes da escuta contínua.
- [PR #62](https://github.com/SANTZSPAXX/NixLMs/pull/62): validação de Origin ainda permite somente loopback/Colab; origem pública Render seria rejeitada em POST. Não houve deploy.
- [PR #63](https://github.com/SANTZSPAXX/NixLMs/pull/63): não integrar. O backfill referencia `library` antes da atribuição; snapshots por extensão incluem `private_library.sqlite3` e `api_keys.sqlite3`; restauração remota pode sobrescrever estado local sem backup/conflito; `psycopg[binary]` foi adicionado a requirements core; não houve CodeQL para o head/base não-main. Nenhum acesso ou alteração no Supabase foi feito.

## CI real consultada

- PR #48: run #44322381961; matriz 4 ambientes, 250 testes por ambiente; 2 jobs de benchmark aprovados.
- PR #55: runs #44418141130 (4 ambientes, 313 testes por ambiente e 2 benchmarks) e #44418141144 (CodeQL); todos os jobs passaram. PR #55 foi mesclada em `e146e82b216eed56e950882af344e25901a32b87`.
- PR #59: runs #44345273110/#44345272790; 4 ambientes, 322 testes por ambiente; CodeQL aprovado.
- PR #60: runs #44349569259/#44349569252; 4 ambientes, 327 testes por ambiente; CodeQL aprovado.
- PR #61: runs #44350486894/#44350487072; 4 ambientes, 314 testes por ambiente; CodeQL aprovado. Uma execução anterior foi cancelada; a execução final consultada passou.
- PR #62: runs #44351251086/#44351250703; 4 ambientes, 315 testes por ambiente; CodeQL aprovado.
- PR #63: run #44355049320; 4 ambientes, 318 testes por ambiente. Não foi observado job CodeQL neste head.
- PR #69: runs #44375657168/#44375657242; 4 ambientes, 323 testes por ambiente; CodeQL aprovado.
- PR #70: run #44379056345; 4 ambientes, 337 testes por ambiente; CodeQL aprovado.
- PR #71: run #44416546444; 4 ambientes, 327 testes por ambiente; CodeQL aprovado.
- PR #72: runs #44417488132/#44417488269; 4 ambientes, 314 testes por ambiente; CodeQL aprovado.
- PR #74: run #44421737137; 4 ambientes, 314 testes por ambiente e 2 benchmarks aprovados; CodeQL #44421737022 aprovou e registrou 69/69 arquivos Python e 2/2 workflows analisados.

Os logs individuais foram consultados para os jobs de matriz, benchmarks e CodeQL citados. Há avisos não bloqueantes de depreciação Node.js 20 em workflows ainda usando setup-python@v5/v6; PR #55 atualiza setup-python para v7. CodeQL também registrou aviso de dynload path, mas concluiu com sucesso.

## Execução local e hardware

- Clone isolado tentou: `git clone --depth 1 https://github.com/SANTZSPAXX/NixLMs.git /tmp/nixlms-qa`.
- Resultado: falhou antes de baixar código, por DNS (`Could not resolve host: github.com`). Nenhum teste local foi executado.
- Não houve teste no Windows físico, Linux ARM64, CPU i5/8 GB, E5 real, Ollama real ou navegador com microfone.
- Não houve instalação de pacotes, compilação, download de modelo/dataset, deploy, acesso a Render/Supabase ou leitura de secrets.

## Próximas prioridades

1. Integrar a correção de auto-instalação em runtime apenas após revisar instalador, base atualizada, CI e consentimento; manter default OFF.
2. Corrigir o instalador de frameworks para tratar ambos os sentidos de divergência metadata/módulo, preferir wheels, e apresentar versões, URLs, hashes e tamanhos resolvidos.
3. Retirar FAISS do caminho pip padrão até validar a origem e compatibilidade; considerar Conda/Pixi como alternativa opcional.
4. Corrigir persistência Supabase com opt-in por acervo, exclusão padrão de biblioteca privada e banco de chaves, backup local e resolução de conflito antes de restore.
5. Manter autonomia automática OFF por padrão; não iniciar etapas manuais sem executor; adicionar timeout, cancelamento cooperativo, limites e autostart sem sobrescrever tarefas existentes.
6. Exibir aviso/consentimento de privacidade antes do Web Speech contínuo e corrigir o contrato de Origin no modo Render.
7. Expor fluxo de candidatos da biblioteca privada com aprovação explícita, sem autoexportação.
8. Medir tamanho instalado, RAM/CPU e compatibilidade por SO/Python/arquitetura em venv descartável; não tornar frameworks obrigatórios.
9. Validar no computador físico Windows 11 e em Linux ARM64 antes de promover integrações.
