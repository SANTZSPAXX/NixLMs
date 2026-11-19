# QA noturno — 19/11/2026

## Snapshot e limites da auditoria

- Repositório canônico: https://github.com/SANTZSPAXX/NixLMs
- `main` observado: `e146e82b216eed56e950882af344e25901a32b87`.
- PR #48 está merged; a Framework Library está presente como catálogo e requisitos opcionais, não como prova de pacotes instalados.
- A consulta encontrou 16 PRs abertas após a criação da #80 e a issue #76 aberta. A listagem de branches retornou paginação adicional; não se afirma uma contagem total.

Comparação dos heads atuais com `main`: #69 está 6 commits à frente/3 atrás; #72 5/3; #74 8/1; #75 15/1; #77 33/3; #78 36/3; #79 23/1. Essas branches estão divergentes/empilhadas e não devem ser mescladas diretamente sem atualização de base e nova CI. A branch #80 está 4 commits à frente e 0 atrás, com base exata no HEAD de `main` observado.
- Nenhum pacote ML foi instalado; nenhum modelo, checkpoint ou dataset foi baixado.
- Nenhum serviço Supabase, Render ou Ollama foi iniciado; nenhum microfone foi acessado.
- Nenhum segredo, permissão, dado privado, release ou deploy foi alterado.
- Clone local tentado com `git clone --depth 1 https://github.com/SANTZSPAXX/NixLMs.git /tmp/nixlms-qa`: falhou porque este ambiente não resolveu `github.com`. Portanto, nenhum teste local do repositório é declarado.

## Alteração desta PR

A auditoria encontrou em `nixlms_core/private_library.py` uma importação de diretórios com `sorted(source.rglob("*"))`. O limite de 100 arquivos era aplicado somente depois de materializar e ordenar a árvore inteira. Um diretório muito grande podia consumir memória proporcional a todos os caminhos, apesar do limite anunciado.

Esta branch:
- troca a materialização integral por `os.walk` em fluxo;
- ordena diretórios/arquivos localmente para manter travessia determinística;
- não segue diretórios simbólicos e ignora arquivos simbólicos;
- conta somente arquivos de extensões aceitas e interrompe ao atingir 100;
- adiciona teste que verifica que a travessia não avança para um diretório posterior depois de encontrar o 101º arquivo compatível;
- atualiza CHANGELOG.

Arquivos alterados:
- `nixlms_core/private_library.py`
- `tests/test_private_library.py`
- `CHANGELOG.md`

A alteração está em branch própria derivada do SHA de `main` acima. Não foi feito merge. A CI desta PR ainda precisa executar.

## Estado de segurança prioritário em main

### P0 — instalação automática multimodal continua possível

Em `nixlms_web/server.py:432`, `main()` chama `media.bootstrap_async(enabled=os.getenv("NIXLMS_AUTO_INSTALL_MEDIA", "1") != "0")`. Em `nixlms_core/media_generation.py`, o worker executa `python -m pip install` para Torch e dependências multimodais. O padrão da variável é habilitado. A célula correspondente do Colab também chama o bootstrap em `main`.

A PR #69 remove o worker e a chamada do startup, mas continua aberta. A revisão desta noite confirmou que o instalador nela ainda usa `--no-upgrade`, opção não suportada pelo pip, e não mostra o conjunto transitivo completo antes do consentimento. A cadeia #70 → #77 → #78 corrige progressivamente o instalador; ainda não está integrada.

O script legado `scripts/install-ml-cpu.ps1` em `main` também executa `pip install --upgrade pip`, não exige venv e instala o arquivo de requisitos sem plano transitivo prévio. A invocação do script é manual, mas o fluxo ainda não satisfaz a política de instalação informada.

### PRs da cadeia de instalação

- [#69](https://github.com/SANTZSPAXX/NixLMs/pull/69): remove bootstrap automático; aberta, base main.
- [#70](https://github.com/SANTZSPAXX/NixLMs/pull/70): instalador de frameworks com consentimento; draft, empilhada sobre #69. A implementação anterior tinha `--no-upgrade`.
- [#77](https://github.com/SANTZSPAXX/NixLMs/pull/77): resolve dependências transitivas com pip dry-run/report, aceita somente wheels HTTPS em origens permitidas, preserva SHA-256 e instala URLs/hashes aprovados sem nova resolução.
- [#78](https://github.com/SANTZSPAXX/NixLMs/pull/78): reaproveita o resolvedor wheel-only no perfil multimodal e corrige o mapeamento Pillow/PIL.

A instalação real não foi executada. Os testes de instalação são mocks; CI verde não demonstra que um framework foi instalado ou executado.

## Framework Library — PR #48 e follow-ups

[PR #48](https://github.com/SANTZSPAXX/NixLMs/pull/48) está efetivamente merged (`eb55e8a7d001056ee8934aa5270f94b9b242d087`). A CI #44322381961 concluiu os jobs de testes e benchmarks. Não houve instalação de PyTorch, NumPy, FAISS, Transformers ou outros pacotes por essa execução.

A arquitetura mantém os quatro acervos como conceitos e módulos distintos:
1. Framework Library — catálogo/requirements de pacotes e ferramentas.
2. Private Knowledge Library — documentos e trechos locais em SQLite/FTS5.
3. Model Library — pesos/checkpoints locais geridos separadamente.
4. Training Dataset Library — datasets, splits e benchmarks.

Ainda não há um catálogo central que prove a integração funcional dos quatro acervos. Presença de pacote não significa modelo instalado, carregado, treinado ou conectado ao runtime.

### PR #79 — proveniência e footprint

[#79](https://github.com/SANTZSPAXX/NixLMs/pull/79) adiciona metadados upstream e medição opt-in dos arquivos declarados por distribuição. O caminho padrão não percorre arquivos e não importa frameworks. RAM/CPU e integração runtime permanecem explicitamente não medidos/não verificados.

Revisão publicada: links para `main`/`master` são mutáveis; recomenda-se registrar tag/versão ou commit upstream consultado por distribuição. O HEAD #79 não tem execução CodeQL associada porque a PR está empilhada sobre #75.

Limites comuns da stack:
- instalação automática prevista apenas para Windows/Linux x86-64 e Python 3.11+;
- Linux ARM64 permanece em inventário/seleção manual, sem validação completa;
- tamanho instalado não inclui dependências transitivas, modelos ou caches;
- nenhum footprint real de RAM/CPU foi medido;
- TensorFlow CPU e llama-cpp-python continuam alternativas separadas.

## Integração ponta a ponta observada em main

| Componente | Evidência no código | Limite real |
|---|---|---|
| Runtime/diagnóstico | `NixLMsNeuralCore.start_runtime()` executa diagnóstico e inicia scheduler; checks cobrem módulos, diretório gravável, auditoria de splits, persistência do decoder, encoder e handlers registrados. | Não executa `PRAGMA integrity_check` em todos os SQLite, nem prova a execução bem-sucedida de cada handler/job. |
| Scheduler | SQLite, handlers allowlisted, leases, eventos e retries. | Os handlers `memory_housekeeping`, `dataset_audit` e `goal_review` são registrados, mas `start_runtime()` agenda automaticamente apenas `idle_learning_cycle`. |
| Ciclo ocioso | Job recorrente a cada 60 s; padrão do manager: 300 s de inatividade, cooldown 1800 s, no máximo 100 linhas de treino, pelo menos 4 amostras de validação e 1 época. | `mark_activity()` só reinicia o relógio. Não cancela cooperativamente um treino já iniciado; `scheduler.stop()` aguarda até timeout, mas não interrompe o handler. |
| Private Knowledge Library | Importação local, chunks, deduplicação SHA-256, SQLite/FTS5 com fallback LIKE; `agent.respond()` injeta até três resultados da busca. | Candidatos exigem aprovação e exportação explícita. A exportação sem sobrescrita está na PR #72, ainda draft. |
| Model Library | Gerenciador Hugging Face registra/download/ativação local explícitos; o agente carrega modelo previamente ativado. | Nenhum modelo é baixado pelo inventário de frameworks. Não há evidência de modelo ativo apenas pela presença de pacote. |
| Training Dataset Library | JSONL com splits e auditoria; treino supervisionado usa train e gate de qualidade mede validation; test é separado da métrica de promoção. | Em main, `train_incremental()` copia o diretório `data/` inteiro para o candidato, incluindo bancos privados, modelos e o arquivo com split test. A PR #74 propõe staging por allowlist, ainda aberta. |
| Planner | GoalManager + AutonomyPlanner + AutonomyEngine; `run_autonomy_cycle()` pode selecionar etapa pronta e revalidar dependências. | O ciclo não é agendado pelo runtime. A ação interna `goal.start_step` só move `pending` para `in_progress`; não executa o trabalho nem marca conclusão. |
| Executor | Engine executa callbacks registrados e limitados pela policy, com escopo/risco, log e aprovação quando necessário. | Não existe executor geral de tarefas/objetivos integrado ponta a ponta. |

Conclusão: módulos de diagnóstico, scheduler, memória privada, planner e aprendizagem existem e alguns estão conectados; o sistema ainda não opera como agente autônomo completo. A execução de objetivos é uma transição interna explícita, e a aprendizagem ociosa não tem cancelamento cooperativo durante o treino.

## CI real consultada

Todos os resultados abaixo são execuções GitHub Actions, não testes locais.

| PR | Execução | Resultado observado |
|---|---|---|
| #48 | [#44322381961](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44322381961) | Jobs de matriz e benchmarks concluídos com sucesso; nenhum pacote ML instalado. |
| #69 | [Testes #44375657242](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44375657242), [CodeQL #44375657168](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44375657168) | 6/6 jobs de testes success, 323 testes no log Windows; CodeQL success. |
| #72 | [Testes #44417488132](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44417488132), [CodeQL #44417488269](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44417488269) | 6/6 jobs success, 314 testes no log Windows; CodeQL success. |
| #75 | [Testes #44425674104](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44425674104), [CodeQL #44425674115](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44425674115) | 6/6 jobs success, 317 testes por matriz; CodeQL success. |
| #74 | [Testes #44421737137](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44421737137), [CodeQL #44421737022](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44421737022) | 6/6 jobs success, 314 testes por matriz; CodeQL success. |
| #77 | [#44596099458](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44596099458) | 6/6 jobs success; 346 testes em cada matriz unitária consultada; dois benchmarks success. Sem CodeQL associado ao head. |
| #78 | [#44598518929](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44598518929) | 6/6 jobs success; 345 testes em cada matriz unitária consultada; dois benchmarks success. Sem CodeQL associado ao head. |
| #79 | [#44601843944](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44601843944) | 6/6 jobs success; 325 testes em Ubuntu 3.10/3.11/3.12 e Windows 3.12; dois benchmarks success. Sem CodeQL associado ao head. |
| #80 | [Testes #44632624937](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44632624937), [CodeQL #44632624975](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44632624975) | 6/6 jobs success; 314 testes em cada matriz, incluindo a regressão de travessia limitada; dois benchmarks success; CodeQL success com avisos de extração não bloqueantes. |

Os logs consultados mostram as etapas de checkout, validação JS quando aplicável, `python -m unittest discover -s tests -v`, benchmarks e CodeQL. Os testes de instaladores usam mocks e não baixam frameworks.

## Outros riscos e pendências

- [#72](https://github.com/SANTZSPAXX/NixLMs/pull/72): correção de exportação exclusiva evita sobrescrever datasets; main ainda usa modo `w`.
- [#74](https://github.com/SANTZSPAXX/NixLMs/pull/74): staging por allowlist reduz cópia de bancos privados/modelos e remove split test do sandbox candidato; não merged.
- `scripts/install-ml-cpu.ps1` continua atualizando pip e não exige venv em main.
- O ciclo de aprendizagem pode continuar após nova atividade do operador; falta token/evento de cancelamento cooperativo verificado entre épocas/lotes.
- Não foram medidos CPU, RSS/pico de RAM, latência ou tamanho total de dependências no i5/8 GB.
- Linux ARM64, instalação real de wheels, E5, Ollama e runtime físico não foram testados.

## Próximos passos priorizados

1. P0: integrar em ordem a cadeia #69 → #70 → #77 → #78 somente após revisar cada diff/base/check; garantir que o startup e Colab nunca instalem e que o script legado deixe de atualizar pip sem plano/venv.
2. Integrar #72 após revisão final e CI na base atual, protegendo exportações existentes.
3. Integrar #74 após revisão do staging, incluindo validação de que nenhum SQLite privado/modelo/test split entra no sandbox.
4. Implementar cancelamento cooperativo do treino ocioso, com checkpoints consistentes, log e rollback.
5. Fixar proveniência por versão/commit no manifesto #79 e executar CodeQL na cadeia antes de marcar pronta.
6. Medir RSS/CPU/latência em venv descartável no hardware real; depois validar Linux ARM64.
7. Só então ampliar executor de objetivos com handlers explícitos, timeout, limites, cancelamento, aprovação e idempotência.

## Estado desta auditoria

- Implementado nesta branch: travessia em fluxo e teste de regressão para limite de importação de documentos.
- Testes locais: não executados; clone bloqueado por DNS.
- CI da branch: #44632624937 e CodeQL #44632624975 aprovados no HEAD de código; a atualização deste relatório dispara nova execução de CI, que deve ser consultada antes de qualquer integração.
- Merge/release/deploy: nenhum.
- main, branches e PRs preexistentes: preservados.
