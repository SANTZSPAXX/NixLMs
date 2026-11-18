# Plano matinal — 2026-11-16: cleanup do processo Ollama gerenciado

## Objetivo e decisão

Auditar o estado remoto da NixLMs em 2026-11-16 e preparar uma única tarefa para o ciclo da tarde.

**Prioridade selecionada:** encerrar de forma limitada e verificável o processo `ollama serve` criado por `OllamaManager` quando a inicialização falha ou expira aguardando prontidão.

A tarefa é uma correção de lifecycle empilhada sobre a correção de bind loopback da PR #29. Não implementa novas capacidades cognitivas e não modifica dados persistentes.

## Integridade e estado remoto

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`
- HEAD de `main`: `135f480addc43dd270ea7a08b97da6496b651445`
- `main` permanece no mesmo SHA observado nos planos de 14 e 15/11.
- A branch `main` aparece como não protegida no inventário de branches. Nenhuma configuração foi alterada.
- Nenhuma issue aberta foi retornada pela consulta de issues; os itens abertos observados são PRs.
- Nenhum merge, release, deploy, force-push, exclusão ou alteração de configuração sensível foi executado.

### Evoluções integradas

- [PR #6 — Scheduler 0.6](https://github.com/SANTZSPAXX/NixLMs/pull/6): merged em 2026-11-14 02:49:34 UTC.
- [PR #7 — memória episódica 0.7](https://github.com/SANTZSPAXX/NixLMs/pull/7): merged em 2026-11-14 02:49:48 UTC.
- [PR #22 — treinamento recorrente LIF](https://github.com/SANTZSPAXX/NixLMs/pull/22): merged em 2026-11-14 08:31:06 UTC.

A evolução 0.6 não está pendente. O scheduler usa SQLite e handlers allowlisted, sem execução de shell ou execução automática de objetivos.

### PRs abertas inspecionadas

| PR | Estado | Base → branch/HEAD | Observação |
|---|---|---|---|
| [#23 — Ollama consentido](https://github.com/SANTZSPAXX/NixLMs/pull/23) | open/draft | `main` → `feature/ollama-setup-consent` / `63b34cbd` | Instalação/configuração opcional; reviews de consentimento e origem do instalador ainda relevantes |
| [#24 — plano de cache](https://github.com/SANTZSPAXX/NixLMs/pull/24) | open/draft | `main` → `docs/plan-2026-11-14-episodic-index` | Plano anterior, não alterado |
| [#25 — cache episódico](https://github.com/SANTZSPAXX/NixLMs/pull/25) | open/draft | `main` → `feature/episodic-retrieval-cache-batching` / `1fb2126a` | Implementação LRU/batching, não alterada |
| [#26 — QA noturno 14/11](https://github.com/SANTZSPAXX/NixLMs/pull/26) | open/draft | `main` → `docs/qa-nightly-2026-11-14` | Registro anterior, não alterado |
| [#27 — plano de validação episódica](https://github.com/SANTZSPAXX/NixLMs/pull/27) | open/draft | `main` → `docs/plan-2026-11-15-episodic-cache-validation` | Plano anterior, critérios agora exercitados pela #28 |
| [#28 — paridade/benchmark episódico](https://github.com/SANTZSPAXX/NixLMs/pull/28) | open/draft | `feature/episodic-retrieval-cache-batching` → `test/episodic-cache-parity-benchmark` / `d536a693` | Validação empilhada sobre #25 |
| [#29 — bind loopback Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/29) | open/draft | `feature/ollama-setup-consent` → `fix/ollama-managed-loopback-bind` / `91ecf115` | Correção de bind empilhada sobre #23 |
| [#30 — QA noturno 15/11](https://github.com/SANTZSPAXX/NixLMs/pull/30) | open/draft | `main` → `docs/qa-nightly-2026-11-15` / `4a607906` | Relatório de auditoria anterior, não alterado |

Nenhuma PR existente foi editada. As PRs #28 e #29 continuam empilhadas sobre suas respectivas PRs-base; não devem ser confundidas com alterações já integradas em `main`.

## CI e testes — evidência consultada

| Referência | Run | Resultado observado |
|---|---:|---|
| `main` | [43576200437](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43576200437) | 4/4 jobs success; log Ubuntu/Python 3.12 registra 148 testes |
| PR #23 | [43579532053](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579532053) | 4/4 jobs success no HEAD da PR-base |
| PR #25 | [43625546189](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43625546189) | 4/4 jobs success no HEAD da implementação |
| PR #28 | [43749733054](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43749733054) | 5/5 jobs success; 163 testes em cada uma das quatro matrizes e benchmark sintético concluído |
| PR #29 | [43783387426](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43783387426) | 4/4 jobs success; logs Ubuntu/Python 3.12 e Windows/Python 3.12 registram 159 testes |
| PR #30 | [43783796015](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43783796015) | 4/4 jobs success; log consultado registra 148 testes |

Matriz de testes do workflow: Ubuntu/Python 3.10, 3.11 e 3.12; Windows/Python 3.12. PR #28 adiciona um job Ubuntu/Python 3.12 para benchmark sintético.

**Execução local neste ciclo:** nenhum teste, benchmark ou serviço Ollama foi executado localmente. Os resultados acima são evidências remotas do GitHub Actions. Não houve profiling no i5/8 GB nem teste físico em Linux ARM64.

### Resultado relevante da PR #28

O review COMMENT da PR #28 registra inspeção do artefato [episodic-retrieval-benchmark](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43749733054/artifacts/14175378995): IDs/ordenação iguais nos cenários cache-off/cold/warm, diferença máxima de score até `1e-8` e zero re-encoding warm. A redução sintética de mediana warm vs. cache-off reportada foi 14,69%, 13,73% e 15,42% para 100, 500 e 2.000 episódios.

Limitações: o cache-off usa a mesma revisão com `embedding_cache_size=0`, não um checkout pré-cache; o encoder é sintético; não houve E5 local, profiling de RAM, i5/8 GB ou ARM64. Não extrapolar esses números para o hardware-alvo.

## Diagnóstico de lacunas cognitivas e técnicas

1. **Memória episódica:** registro e recuperação persistentes existem. Não há consolidação abstrativa não destrutiva com proveniência e referências aos episódios-fonte.
2. **Representação semântica:** encoder nativo treinável com palavras, bigramas e subwords; qualidade depende da cobertura e qualidade dos pares. E5 é opcional, CPU e local-only.
3. **Avaliação PT-BR:** `datasets/starter_ptbr.jsonl` contém 26 linhas: QA 9 train / 7 validation / 4 test; pares 4 train / 0 validation / 2 test. O conjunto é pequeno para estimativas robustas. O cartão do ASSIN 2 continua com licença desconhecida; não redistribuir dados sem esclarecer os termos.
4. **Planejamento:** Goal Manager persiste objetivos e dependências, mas não faz decomposição hierárquica nem replanning mensurado por resultado; não executa ações.
5. **Metacognição:** há calibração e traces por módulo, mas não uma estimativa global integrada de incerteza e abstenção.
6. **Eficiência:** a PR #28 fornece evidência sintética de paridade e cache warm. Ainda faltam E5 local e medições no hardware-alvo.

Essas lacunas permanecem no backlog; não serão combinadas com a tarefa única da tarde.

## PR #29 — análise do risco residual

A PR #29 fixa `OLLAMA_HOST` no ambiente do processo filho, sem alterar o ambiente do processo pai, preserva porta customizada/IPv6 e marca serviços preexistentes como `unverified_preexisting`. O review de segurança sobre bind herdado está endereçado no diff atual, mas a PR segue draft e não foi integrada.

**Risco residual confirmado por inspeção estática:** em `nixlms_core/ollama_manager.py::OllamaManager.start_service()`, após `subprocess.Popen`, o código aguarda `/api/tags` até `readiness_timeout`. Se o prazo expira enquanto o filho continua vivo, a exceção é capturada e a função retorna `start_failed`, mas não chama `terminate()`, `wait()` ou `kill()`. O processo iniciado pela própria instância pode permanecer ativo mesmo que a operação seja reportada como falha.

A suíte `tests/test_ollama_manager.py` na branch da PR #29 cobre bind wildcard herdado, porta customizada, IPv6, serviço preexistente, endpoint não-loopback e download. Não encontrei teste de timeout/limpeza do processo filho.

A revisão COMMENT já registrada na PR #29 descreve esse risco e recomenda uma tarefa de lifecycle separada. Nenhum serviço real foi iniciado nem o cenário foi reproduzido neste ciclo; o achado é estático e requer teste fake de processo.

### Outros pontos pendentes da PR #23

Reviews existentes também observam:
- o consentimento Linux deve mencionar claramente atualização dos índices apt e instalação de `zstd`, ou pedir confirmação separada;
- o instalador remoto oficial é baixado e executado sem versão/checksum fixos; se mantido, o consentimento deve explicar essa execução remota.

A PR #29 não resolve esses dois pontos. Eles ficam registrados, mas não fazem parte da prioridade escolhida para evitar ampliar o escopo.

## Tarefa única para o ciclo da tarde

### Título

**Ollama manager — cleanup bounded do processo filho após falha de prontidão**

### Problema

Um processo `ollama serve` iniciado por esta instância pode sobreviver ao timeout de prontidão. A função informa falha, mas não encerra nem aguarda o processo que ela própria criou.

### Hipótese

Uma rotina de limpeza limitada no caminho de falha pode encerrar somente o processo filho gerenciado por esta instância, sem afetar serviços preexistentes e sem introduzir dependências externas.

### Base e isolamento

- PR #29 permanece open/draft.
- HEAD observado da branch `fix/ollama-managed-loopback-bind`: `91ecf1151e35a54dd51247b10f9859dff5754884`.
- A tarefa deve ser implementada em branch nova derivada desse HEAD, empilhada sobre a PR #29.
- A PR nova deve ter como base `fix/ollama-managed-loopback-bind`.
- Não adicionar commits, mudar metadados, aprovar, fechar ou fazer merge das PRs #23/#29.
- Se o HEAD da PR #29 mudar antes da implementação, revalidar a base e recriar a branch de trabalho a partir do novo HEAD sem force-push.

### Arquivos prováveis

- Modificar: `nixlms_core/ollama_manager.py`
- Modificar: `tests/test_ollama_manager.py`
- Atualizar: `CHANGELOG.md` somente para documentar o comportamento efetivamente implementado.

Não alterar `LanguageEngine`, formato de dados, memória, pesos, datasets, scheduler, instalação ou seleção de modelos, salvo se um bloqueio concreto for demonstrado e documentado.

### Desenho proposto

1. Criar um helper privado de cleanup que opere exclusivamente sobre `self.process`, isto é, o objeto `Popen` criado pela própria instância.
2. Se não houver processo ou `poll()` indicar que ele já terminou, não enviar sinais.
3. Se o processo estiver vivo, chamar `terminate()` e aguardar com `wait(timeout=...)` curto e limitado.
4. Se o prazo de encerramento expirar, chamar `kill()` e fazer um segundo `wait(timeout=...)` limitado.
5. Se o cleanup terminar, limpar a referência gerenciada de modo consistente. Se falhar, preservar a referência para diagnóstico e registrar explicitamente que a limpeza não foi confirmada.
6. Preservar o erro original de startup e acrescentar o resultado/erro de cleanup sem mascarar a causa primária.
7. Não executar cleanup no caminho `already_running`; um serviço preexistente nunca pertence a esta instância.
8. Não alterar `os.environ`; manter o ambiente filho explícito e o bind loopback já implementado.
9. Não afirmar que descendentes/processos auxiliares do Ollama foram encerrados. Esta tarefa cobre apenas o processo `Popen` diretamente gerenciado; limpeza de árvore de processos seria trabalho separado e específico por SO.

### Testes de regressão necessários

- Processo fake permanece vivo após falha de prontidão: `terminate()` e `wait()` são chamados.
- Processo fake não encerra após `terminate()`: ocorre `kill()` seguido de `wait()`.
- Processo já terminou antes do cleanup: não chama `terminate()` nem `kill()`.
- Serviço preexistente acessível: não cria nem encerra processo.
- Inicialização bem-sucedida: mantém o processo gerenciado e não executa cleanup.
- Falha no cleanup: o retorno não afirma que o processo foi encerrado; erro primário e falha de cleanup permanecem observáveis.
- Corrida entre `poll()` e encerramento: erros esperados de processo já finalizado são tratados sem afetar processo externo.
- Testar chamadas repetidas para garantir cleanup idempotente.

Usar mocks/fakes; não iniciar Ollama real nem executar instalação/download de modelo nos testes.

### Critérios de aceitação

- Todo caminho de falha após criação de `Popen` tenta cleanup limitado quando o processo ainda está vivo.
- `terminate` tem espera limitada; `kill` é usado somente após timeout do encerramento inicial.
- O método nunca atua sobre serviço preexistente ou processo não criado por esta instância.
- O erro original de startup não é perdido.
- Estado de cleanup é verificável por retorno/status/log sem alegação falsa de sucesso.
- O bind loopback e o isolamento de ambiente da PR #29 permanecem intactos.
- Nenhuma dependência obrigatória nova, migração, download ou ação externa é introduzida.
- Testes focados e suíte completa passam em Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12.
- O diff é revisado para garantir que nenhum processo externo seja encerrado.

### Riscos e mitigação

- **Diferença POSIX/Windows:** `terminate()` envia SIGTERM em POSIX e usa TerminateProcess no Windows; `kill()` é SIGKILL em POSIX e alias de terminate no Windows. Usar API portátil e timeouts pequenos, sem assumir encerramento gracioso idêntico.
- **Corrida de processo:** o filho pode encerrar entre `poll()` e `terminate()`; tratar somente as exceções esperadas e confirmar o estado por `poll()/wait()`.
- **Árvore de processos:** encerrar o processo pai não prova encerramento de todos os processos descendentes. Documentar a limitação; não usar comandos globais como `taskkill` ou `pkill`.
- **Falha de cleanup:** não ocultar a falha nem descartar a referência do processo ainda possivelmente vivo.
- **Ambiente real:** CI com fakes não comprova comportamento do binário Ollama em todas as distribuições; teste real opcional deve ser manual e consentido.

### Rollback

A mudança é restrita ao gerenciador e seus testes. Reverter apenas os commits da nova branch/PR empilhada. Não alterar `main`, PR #23/#29, dados, modelos, arquivos de usuário, serviços preexistentes ou configurações do SO.

## Pesquisa — fontes primárias

- Python 3.10 subprocess: https://docs.python.org/3.10/library/subprocess.html — documenta `Popen.poll()`, `wait(timeout)`, `terminate()`, `kill()` e a necessidade de cleanup explícito após timeout.
- Python 3.10 subprocess em português: https://docs.python.org/pt-br/3.10/library/subprocess.html
- Ollama FAQ: https://github.com/ollama/ollama/blob/main/docs/faq.mdx — documenta que `OLLAMA_HOST` controla o endereço de bind e que o servidor usa loopback por padrão.

Alternativas:
- **Não limpar:** mantém o risco atual de processo órfão após falha reportada; rejeitada.
- **Somente `terminate()`:** não confirma encerramento dentro de prazo; insuficiente.
- **`terminate()` + `wait(timeout)` + fallback `kill()` + `wait(timeout)`:** escolhida por usar a API padrão Python, ser portátil e ter limites temporais verificáveis.
- **Encerrar árvore inteira de processos:** não escolhido; exige estratégias específicas de Windows/POSIX e amplia o risco de atingir processos não pertencentes à instância.

## Limites deste ciclo

Auditoria remota do GitHub, inspeção de branches/PRs/diffs/arquivos e leitura de logs reais de GitHub Actions. Nenhum checkout local, teste local, benchmark local, profiling físico ou serviço Ollama real foi executado. Nenhuma implementação de produção foi feita. Nenhuma PR preexistente foi alterada.

## Próximo passo

O ciclo da tarde deve revalidar o HEAD da PR #29, implementar apenas o cleanup do processo filho gerenciado em branch empilhada própria, adicionar testes com fakes, revisar o diff e aguardar a CI real. Não fazer merge automático.
