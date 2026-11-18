# QA noturno — NixLMs — 2026-11-16

**Data/hora da auditoria:** 2026-11-16, aproximadamente 21:22 (America/Sao_Paulo)  
**Repositório:** https://github.com/SANTZSPAXX/NixLMs  
**Branch documental:** `docs/qa-nightly-2026-11-16`  
**Base:** `main` em `135f480addc43dd270ea7a08b97da6496b651445`

## 1. Resumo executivo

- `main` permaneceu no SHA observado; nenhum merge, release, deploy, force-push, exclusão ou alteração de configuração foi executado.
- Foram inspecionadas as 11 PRs abertas (#23–#33) e 34 branches retornadas pela busca do repositório.
- A PR #32 implementa o cleanup limitado do processo Ollama gerenciado, empilhada sobre a PR #29. A revisão encontrou uma lacuna adicional: `KeyboardInterrupt` não era capturado por `except Exception`, então Ctrl+C durante a espera podia deixar o processo filho ativo.
- A lacuna foi corrigida na própria branch de trabalho da PR #32, com teste de regressão e atualização do README/CHANGELOG.
- A CI do novo HEAD da PR #32 concluiu com 4/4 jobs e 167 testes por ambiente.
- A PR #33 é somente documental e seu CI concluiu com 4/4 jobs.
- Não foram executados testes locais, instalação real do Ollama, inferência, profiling no computador i5/8 GB ou teste físico ARM64.

## 2. Integridade e inventário remoto

### main

- Branch padrão: `main`.
- Último commit retornado pela busca de commits: `135f480addc43dd270ea7a08b97da6496b651445`.
- A base da PR #33 também é esse SHA.
- Nenhuma alteração foi feita em `main`.

### PRs abertas verificadas

Todas as PRs abaixo foram consultadas individualmente por metadados; todas estavam `open`, `draft=true` e `merged=false` no momento da auditoria.

| PR | Branch head | Base | Escopo |
|---|---|---|---|
| [#23](https://github.com/SANTZSPAXX/NixLMs/pull/23) | `feature/ollama-setup-consent` | `main` | Setup Ollama com consentimento |
| [#24](https://github.com/SANTZSPAXX/NixLMs/pull/24) | `docs/plan-2026-11-14-episodic-index` | `main` | Plano histórico de cache |
| [#25](https://github.com/SANTZSPAXX/NixLMs/pull/25) | `feature/episodic-retrieval-cache-batching` | `main` | Cache/batching episódico |
| [#26](https://github.com/SANTZSPAXX/NixLMs/pull/26) | `docs/qa-nightly-2026-11-14` | `main` | QA histórico |
| [#27](https://github.com/SANTZSPAXX/NixLMs/pull/27) | `docs/plan-2026-11-15-episodic-cache-validation` | `main` | Plano de validação episódica |
| [#28](https://github.com/SANTZSPAXX/NixLMs/pull/28) | `test/episodic-cache-parity-benchmark` | PR #25 | Paridade/benchmark do cache |
| [#29](https://github.com/SANTZSPAXX/NixLMs/pull/29) | `fix/ollama-managed-loopback-bind` | PR #23 | Bind loopback do processo gerenciado |
| [#30](https://github.com/SANTZSPAXX/NixLMs/pull/30) | `docs/qa-nightly-2026-11-15` | `main` | QA histórico |
| [#31](https://github.com/SANTZSPAXX/NixLMs/pull/31) | `docs/plan-2026-11-16-ollama-lifecycle-cleanup` | PR #29 | Plano matinal de lifecycle |
| [#32](https://github.com/SANTZSPAXX/NixLMs/pull/32) | `fix/ollama-managed-startup-cleanup` | PR #29 | Cleanup limitado do processo filho |
| [#33](https://github.com/SANTZSPAXX/NixLMs/pull/33) | `docs/roadmap-jarvis-2026-11-16` | `main` | Auditoria e roadmap JARVIS |

A busca retornou 34 branches. A branch desta documentação é criada separadamente a partir do SHA atual de `main`; não modifica nenhuma branch de implementação ou PR anterior.

## 3. PR #32 — revisão do diff e correção

[PR #32 — Fix bounded cleanup for managed Ollama startup failures](https://github.com/SANTZSPAXX/NixLMs/pull/32)

- Base: `fix/ollama-managed-loopback-bind`, SHA `91ecf1151e35a54dd51247b10f9859dff5754884`.
- HEAD após a correção: `aae01637267a06f8851793d4c16830c90a99baef`.
- Estado: aberta, draft, não merged.
- Arquivos alterados: `nixlms_core/ollama_manager.py`, `tests/test_ollama_manager.py`, `README.md`, `CHANGELOG.md`.
- Nenhuma dependência obrigatória nova.

### Comportamento revisado

- Cleanup atua somente no objeto `Popen` criado pela instância.
- Consulta `poll()` antes de enviar sinais.
- Solicita `terminate()` e aguarda até 2 segundos.
- Após timeout, solicita `kill()` e aguarda mais 2 segundos.
- Se não confirmar o encerramento, preserva a referência e registra `unconfirmed`.
- Não encerra serviços preexistentes.
- Não afirma encerrar a árvore de processos descendentes.
- Em Windows, `kill()` é alias de `terminate()`; em POSIX, usa SIGKILL, conforme a documentação oficial de subprocess do Python: https://docs.python.org/3.10/library/subprocess.html#popen-objects.

### Defeito reproduzível encontrado e corrigido

O handler original capturava `Exception`, mas `KeyboardInterrupt` deriva de `BaseException`. Assim, Ctrl+C durante a espera por `/api/tags` podia escapar sem executar o cleanup do processo gerenciado.

Correção mínima na branch da PR #32:

1. Capturar `KeyboardInterrupt` separadamente.
2. Tentar cleanup limitado do processo gerenciado.
3. Registrar `last_action=start_cancelled` e o resultado de cleanup.
4. Propagar novamente a interrupção com `raise`, sem transformar cancelamento em sucesso nem ocultar Ctrl+C.
5. Adicionar `test_start_interruption_cleans_up_managed_process_and_reraises`, com processo fake, verificando `terminate`, ausência de `kill` desnecessário, referência limpa, diagnóstico e propagação da exceção.
6. Atualizar README e CHANGELOG para documentar o comportamento.

A correção foi aplicada por commits adicionais na própria branch da PR #32; não houve force-push nem sobrescrita de commits anteriores.

### CI do HEAD corrigido

Run [#43986968091](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43986968091): **4/4 jobs concluídos com sucesso**.

| Ambiente | Resultado | Testes | Duração |
|---|---|---:|---:|
| Ubuntu / Python 3.10 | success | 167 | 30,812 s |
| Ubuntu / Python 3.11 | success | 167 | 14,487 s |
| Ubuntu / Python 3.12 | success | 167 | 15,239 s |
| Windows / Python 3.12 | success | 167 | 27,061 s |

Os quatro logs foram consultados individualmente. Todos registram o novo teste de interrupção como `ok` e a suíte completa sem falhas.

O run anterior [#43926014668](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43926014668) validava o HEAD anterior, com 166 testes por job; ele foi substituído pelo run #43986968091 após a correção de Ctrl+C.

## 4. PR #31 — aderência ao plano matinal

[PR #31 — Plano de cleanup do lifecycle Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/31)

A implementação #32 cumpre os critérios centrais do plano:

- cleanup somente do processo próprio;
- terminate/wait limitado e fallback kill/wait;
- nenhum cleanup de serviço preexistente;
- preservação do erro original em falhas normais;
- retenção da referência quando o cleanup não é confirmado;
- diagnóstico de cleanup exposto em status/retorno;
- testes fake para timeout, fallback, corrida de saída, idempotência e falha de cleanup;
- compatibilidade automatizada Ubuntu/Python 3.10–3.12 e Windows/Python 3.12;
- sem dependências novas, downloads ou alterações persistentes.

A revisão desta noite ampliou o plano para cobrir cancelamento explícito por Ctrl+C. O novo teste passou em todos os quatro ambientes de CI.

**Limite:** os testes usam processos fake. Não comprovam o comportamento de um binário Ollama real, nem de processos descendentes.

## 5. PR #33 — auditoria do roadmap JARVIS

[PR #33 — Plan: NixLMs JARVIS architecture, audit and technical roadmap](https://github.com/SANTZSPAXX/NixLMs/pull/33)

- Uma alteração documental, sem código de produção.
- Base `main` em `135f480addc43dd270ea7a08b97da6496b651445`.
- Registra capacidades atuais versus recursos ainda em PRs.
- Define arquitetura-alvo modular, ciclo observe/plan/act/verify, política A0–A4, roadmap em fases, gates de segurança e avaliação.
- Mantém explícita a distinção entre capacidade funcional e consciência/senciência; não faz alegações de AGI.

Run [#43947443104](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43947443104): **4/4 jobs success**, com 148 testes por job:
- Ubuntu/Python 3.10 — 148, 17,627 s.
- Ubuntu/Python 3.11 — 148, 23,722 s.
- Ubuntu/Python 3.12 — 148, 23,279 s.
- Windows/Python 3.12 — 148, 40,895 s.

Os quatro logs foram consultados. Nenhuma falha foi registrada.

A contagem de 10 PRs no documento #33 corresponde às dez PRs #23–#32 existentes quando o inventário foi produzido; a própria PR #33 foi aberta depois e eleva a contagem atual para 11.

## 6. Revisão de segurança, concorrência e recursos

### Segurança

- O isolamento de bind da PR #29 continua na base empilhada da PR #32: processo gerenciado recebe ambiente filho com `OLLAMA_HOST` loopback; ambiente pai não é alterado.
- Serviço preexistente permanece `unverified_preexisting`; responder em loopback não prova em quais interfaces ele escuta.
- A PR #32 não usa shell, `taskkill`, `pkill` nem encerramento global por nome/PID.
- Não houve instalação, execução de instalador remoto, download de modelo ou chamada ao Ollama real nesta auditoria.
- Pendências de segurança da PR #23 continuam abertas:
  - consentimento Linux deve explicar `apt-get update` e instalação de `zstd`: https://github.com/SANTZSPAXX/NixLMs/pull/23#pullrequestreview-5913907219;
  - instalador `install.sh` remoto não tem versão/checksum fixos: https://github.com/SANTZSPAXX/NixLMs/pull/23#pullrequestreview-5913926061.
- A PR #29 ainda não inspeciona o bind de serviços preexistentes: https://github.com/SANTZSPAXX/NixLMs/pull/29#pullrequestreview-5913922320.

### Concorrência — risco não resolvido

A inspeção estática indica que `OllamaManager.start_service()` não serializa chamadas concorrentes. Duas threads poderiam observar `self.process is None`, iniciar processos separados e sobrescrever a referência de uma das instâncias, deixando um processo sem handle gerenciado.

Não foi demonstrado que o fluxo CLI atual chama esse método em paralelo, e não houve teste de estresse concorrente. Portanto, isto permanece como risco potencial, não como falha reproduzida. Antes de expor o gerenciador a um orquestrador multithread, avaliar lock estreito/idempotência e teste de concorrência.

### Recursos e compatibilidade

- Cleanup usa somente a biblioteca padrão; sem dependência adicional.
- Esperas solicitadas ao processo são limitadas a 2 + 2 segundos. Chamadas do SO e agendamento ainda podem acrescentar latência.
- A saída do processo é redirecionada a arquivo, não a pipes, evitando o caso documentado de deadlock por pipe cheio em `wait()`.
- Não houve medição de CPU/RAM.
- CI validou Ubuntu x86-64 e Windows x86-64. Linux ARM64 não foi executado.
- Os logs apresentam aviso de depreciação de Node.js 20 nas actions `checkout@v4`/`setup-python@v5` e aviso de depreciação do módulo `punycode`; não causaram falhas.

### Treino/teste e persistência

O diff da PR #32 altera somente lifecycle Ollama, testes e documentação. Não altera datasets, splits, treino, validação, teste, pesos, memória episódica ou schemas persistidos. Não foi introduzido vetor novo de vazamento treino/teste por esta mudança. Esta observação não substitui uma auditoria integral do pipeline de treinamento.

## 7. O que não foi executado

- Nenhum teste local nesta automação.
- Nenhuma instalação ou inicialização real do Ollama.
- Nenhum teste de bind por inspeção de sockets no Windows/Linux.
- Nenhuma execução real de Ctrl+C contra o binário Ollama.
- Nenhum teste de árvore de processos descendentes.
- Nenhum teste de concorrência.
- Nenhum benchmark E5 real ou medição de RAM/CPU.
- Nenhum teste no computador de referência i5 antigo / 8 GB / sem GPU.
- Nenhum teste em Linux ARM64.

Os resultados positivos descritos são exclusivamente da CI GitHub Actions, com processos fake na cobertura de lifecycle.

## 8. Próximos passos priorizados

1. **Validação consentida no Windows 11:** instalar somente com autorização explícita; testar endpoint loopback com ambiente pai `OLLAMA_HOST=0.0.0.0`; inspecionar o socket real e confirmar encerramento após timeout e Ctrl+C.
2. **Consentimento Linux:** esclarecer atualização do apt e instalação de zstd; revisar origem, versão e integridade do instalador remoto.
3. **Concorrência OllamaManager:** decidir/documentar contrato single-thread ou implementar lock estreito com testes concorrentes antes de uso paralelo.
4. **Lifecycle real:** validar que somente o processo gerenciado é encerrado e documentar comportamento de descendentes em Windows/POSIX.
5. **Profiling do hardware-alvo:** medir RSS, CPU e latência do núcleo; testar E5 somente se os pesos já estiverem disponíveis localmente.
6. **ARM64:** preparar runner/dispositivo real e não declarar compatibilidade antes da execução.
7. **Supply chain CI:** planejar atualização das GitHub Actions que ainda geram avisos de runtime Node.js 20.
8. **Roadmap JARVIS — Fase 0:** inventariar APIs/schemas/dependências e publicar baseline reproduzível antes de iniciar NIX CORE/workspace.

## 9. Decisão do ciclo

- PR #32 permanece draft, sem merge; novo HEAD validado em 4/4 jobs.
- PR #33 permanece draft, somente documental; CI em 4/4 jobs.
- PRs #23–#31 permanecem abertas/draft e sem alterações nesta auditoria.
- `main` permanece em `135f480addc43dd270ea7a08b97da6496b651445`.
- Nenhum release, deploy, force-push, exclusão ou alteração de configuração sensível foi realizado.
