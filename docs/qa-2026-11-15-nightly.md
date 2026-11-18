# QA noturno — NixLMs — 2026-11-15

## Escopo e integridade

Auditoria remota do repositório em 15/11/2026 (horário America/Sao_Paulo), com evidências de CI até 16/11/2026 00:58 UTC.

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`
- HEAD de `main`: `135f480addc43dd270ea7a08b97da6496b651445`
- Comparação `135f480...main`: `identical`, 0 commits à frente/atrás.
- Nenhuma alteração foi feita em `main`.
- Nenhum merge, release, deploy, force-push, exclusão ou alteração de configuração sensível foi executado.
- Nenhuma PR anterior foi editada; a nova correção de segurança foi isolada em branch/PR empilhada.

## PRs e branches observadas

| PR | Estado | Base → HEAD | Observação |
|---|---|---|---|
| [#23 — Ollama consentido](https://github.com/SANTZSPAXX/NixLMs/pull/23) | open/draft | `main` → `63b34cbd` | Integração opcional; revisão de segurança pendente |
| [#24 — plano de otimização](https://github.com/SANTZSPAXX/NixLMs/pull/24) | open/draft | `main` → `7d6d9ed0` | Plano anterior, não alterado |
| [#25 — cache episódico](https://github.com/SANTZSPAXX/NixLMs/pull/25) | open/draft | `main` → `1fb2126a` | Implementação LRU/batching, não alterada |
| [#26 — QA de 14/11](https://github.com/SANTZSPAXX/NixLMs/pull/26) | open/draft | `main` → `9486ae0d` | Registro anterior, não alterado |
| [#27 — plano de validação](https://github.com/SANTZSPAXX/NixLMs/pull/27) | open/draft | `main` → `148ad498` | Critérios da tarefa de validação da tarde |
| [#28 — paridade e benchmark](https://github.com/SANTZSPAXX/NixLMs/pull/28) | open/draft | `feature/episodic-retrieval-cache-batching` → `d536a693` | Validação empilhada sobre #25 |
| [#29 — bind loopback Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/29) | open/draft | `feature/ollama-setup-consent` → `91ecf115` | Correção de segurança empilhada sobre #23 |

A PR #28 usa como base o HEAD `1fb2126aca8cbbad8a874f09ad15b4ecfadd04da` da PR #25. A PR #29 usa como base o HEAD `63b34cbd6433270cbb1cc2d0ea4a935ec49a7625` da PR #23. Ambas as PRs-base permanecem inalteradas.

## PR #28 — validação do cache episódico

### Revisão do diff

A PR altera cinco arquivos: workflow de CI, CHANGELOG, README, benchmark e testes. Não altera código de produção, formato de episódios, dependências Python, pesos, datasets ou configuração de runtime.

A implementação cobre os critérios automatizáveis do plano #27:

- comparação de `embedding_cache_size=0` com cache habilitado;
- igualdade de IDs e ordenação e tolerância absoluta de score `1e-5`;
- SHA-256 do JSON antes/depois de `recall()`;
- recálculo de feedback, importância e recência sem re-encoding;
- cenários cache-off, cold e warm;
- mediana, p95 e contadores;
- encoder sintético determinístico como padrão e E5 somente por caminho local, sem download.

A comparação cache-off usa a implementação atual com cache de tamanho zero; não é um checkout pré-cache. Essa limitação está descrita na PR e no benchmark.

### CI real

Run: https://github.com/SANTZSPAXX/NixLMs/actions/runs/43749733054

| Job | Resultado | Testes | Duração da suíte |
|---|---|---:|---:|
| Ubuntu / Python 3.10 | success | 163 | 30,333 s |
| Ubuntu / Python 3.11 | success | 163 | 23,536 s |
| Ubuntu / Python 3.12 | success | 163 | 28,078 s |
| Windows / Python 3.12 | success | 163 | 40,662 s |
| Benchmark Ubuntu / Python 3.12 | success | — | job concluído |

Resultado: 5/5 jobs concluídos com sucesso. Os logs de cada job de testes registram 163 testes e conclusão OK. O job de benchmark publicou o artefato `episodic-retrieval-benchmark`.

Artefato: https://github.com/SANTZSPAXX/NixLMs/actions/runs/43749733054/artifacts/14175378995  
ID: `14175378995`  
SHA-256 do ZIP: `6d73a42484becc456e2a20873e43f10c5bb562c4c59d5c4f92e050362a98585d`  
Expiração informada: 29/11/2026.

O ZIP foi baixado e o JSON interno foi inspecionado. Resultados em milissegundos (mediana / p95; cinco amostras):

| Episódios | Cache-off | Cold | Warm | Redução warm vs. off |
|---:|---:|---:|---:|---:|
| 100 | 2,948 / 3,685 | 3,236 / 3,287 | 2,515 / 2,573 | 14,69% |
| 500 | 14,501 / 14,901 | 16,305 / 21,188 | 12,510 / 12,959 | 13,73% |
| 2.000 | 59,495 / 59,691 | 64,525 / 65,006 | 50,323 / 51,978 | 15,42% |

- IDs e ordenação: iguais nos três cenários.
- Diferença absoluta máxima de score por tamanho: `1e-8`, `0` e `1e-8`; tolerância `1e-5`.
- Warm: zero passagens adicionais codificadas, zero chamadas adicionais ao encoder e 100/500/2.000 hits por repetição.
- Cold ficou aproximadamente 8,45%–12,44% mais lento que cache-off; o custo inicial de fingerprint/cache não é gratuito.
- Com cinco amostras, p95 nearest-rank equivale ao maior valor observado.

**Conclusão:** a PR #28 fecha os critérios automatizáveis do plano #27. Não encontrei defeito reproduzível no diff de testes/benchmark. A evidência demonstra paridade e ganho sintético no runner CI, não desempenho do E5 nem do computador-alvo.

### Limitações restantes

- Encoder sintético não mede qualidade semântica nem latência real do E5.
- Cache-off usa a mesma revisão com tamanho zero, não código anterior ao cache.
- Nenhum profiling de RAM foi executado.
- Nenhum benchmark foi executado no i5/8 GB nem em Linux ARM64.
- A classe `EpisodicMemory` continua sem garantia de thread-safety; concorrência ficou fora do escopo conforme plano #27.
- Não foi identificado vazamento treino/teste introduzido: o benchmark usa episódios sintéticos e não treina nem consulta os splits de QA.

Review COMMENT registrada: https://github.com/SANTZSPAXX/NixLMs/pull/28#pullrequestreview-5913909333

## PR #23 — achado de segurança Ollama

A revisão estática confirmou que `LanguageEngine.local_host` valida o endpoint usado pelo cliente, mas o processo iniciado por `OllamaManager.start_service()` herdava o ambiente do processo pai. A variável `OLLAMA_HOST` controla o bind do servidor. Assim, um cliente configurado explicitamente para loopback poderia iniciar um filho herdando `OLLAMA_HOST=0.0.0.0:11434`.

Fonte primária Ollama: https://github.com/ollama/ollama/blob/main/docs/faq.mdx  
A documentação do Python confirma que `Popen(env=...)` permite fornecer um ambiente próprio ao processo filho: https://docs.python.org/3.10/library/subprocess.html

A PR #23 não foi modificada. Foi aberta a PR empilhada [#29](https://github.com/SANTZSPAXX/NixLMs/pull/29), branch `fix/ollama-managed-loopback-bind`, baseada exatamente no HEAD da PR #23.

### Correção proposta na PR #29

- Passa uma cópia de `os.environ` ao processo filho e fixa `OLLAMA_HOST` ao loopback e à porta do endpoint local.
- Não altera o ambiente do processo pai.
- Preserva porta customizada e formata IPv6 loopback.
- Marca serviço preexistente como `unverified_preexisting`; responder em localhost não prova em quais interfaces o processo externo está escutando.
- Usa `configured_loopback` somente para descrever a configuração fornecida ao processo gerenciado; não afirma inspeção do socket do SO.
- Acrescenta testes para ambiente herdado wildcard, ambiente pai inalterado, porta, IPv6, porta inválida e serviço preexistente.

### CI real da PR #29

Run: https://github.com/SANTZSPAXX/NixLMs/actions/runs/43783387426

| Job | Resultado | Testes | Duração |
|---|---|---:|---:|
| Ubuntu / Python 3.10 | success | 159 | 16,553 s |
| Ubuntu / Python 3.11 | success | 159 | 15,490 s |
| Ubuntu / Python 3.12 | success | 159 | 28,317 s |
| Windows / Python 3.12 | success | 159 | 34,220 s |

Resultado: 4/4 jobs concluídos com sucesso. Os logs confirmam os novos testes de bind loopback e formatação IPv6 aprovados. Nenhuma falha registrada.

- Testes locais: não executados neste ambiente.
- Instalação real, inicialização de servidor real e inspeção de sockets no Windows/Linux: não executadas.
- O serviço preexistente permanece com bind não verificado; a PR não altera um servidor já iniciado por outro processo.
- Em timeout após `Popen`, o processo gerenciado não é encerrado explicitamente; uma revisão COMMENT em #29 recomenda tratar o lifecycle em tarefa separada, sem encerrar serviços preexistentes.

### Consentimento Linux — observação adicional

Na PR #23, a instalação Linux pode executar `apt-get update` e `apt-get install zstd` quando o pacote não existe. O prompt atual menciona instalar Ollama, mas não explicita a atualização dos índices e a instalação de pacote de sistema. Foi registrada uma revisão COMMENT pedindo que esse escopo seja informado ou confirmado separadamente, sem alegar que uma instalação real ocorreu:

https://github.com/SANTZSPAXX/NixLMs/pull/23#pullrequestreview-5913907219

## CI histórica das PRs anteriores

As execuções abaixo são evidência previamente registrada e não foram reexecutadas neste ciclo:

- main: [#43579135998](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579135998), 4/4 jobs, 148 testes por job.
- PR #23: [#43579532053](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579532053), 4/4 jobs, 157 testes por job.
- PR #24: [#43596339567](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43596339567), 4/4 jobs.
- PR #25: [#43625546189](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43625546189), 4/4 jobs, 161 testes por job.
- PR #26: [#43659204826](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43659204826), 4/4 jobs, 148 testes por job.

## Ambiente local e compatibilidade

- Nenhum teste local ou benchmark local foi executado neste ciclo.
- CI x86-64: Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12 aprovados nas PRs #28 e #29.
- Linux ARM64: não executado.
- Hardware i5 antigo / 8 GB RAM / sem GPU: não executado.
- Nenhuma dependência Python obrigatória foi adicionada pelas PRs #28 e #29.
- Os logs de CI apresentam aviso de depreciação do runtime Node.js 20 para `actions/checkout@v4`, `actions/setup-python@v5` e, no job de artefato, `actions/upload-artifact@v4`. Não houve falha por esse aviso; revisar versões das actions em tarefa separada.

## Próximos passos priorizados

1. Manter #28 em draft até obter benchmark E5 local (se os pesos já existirem) e profiling no hardware-alvo; não extrapolar o resultado sintético.
2. Revisar #29 e executar validação manual com consentimento em Windows 11 e Linux: ambiente pai com `OLLAMA_HOST=0.0.0.0:11434`, cliente local explícito, processo gerenciado e inspeção de interfaces de escuta.
3. Resolver o escopo de consentimento para `apt-get update` e instalação de `zstd` na PR #23.
4. Tratar serviço preexistente como não verificado até que exista inspeção confiável do bind no SO.
5. Avaliar thread-safety de `EpisodicMemory` em tarefa isolada se o runtime passar a chamar a memória em paralelo.
6. Medir RSS/pico de RAM e latência cold/warm no i5/8 GB; validar Linux ARM64 quando houver runner/hardware.
7. Atualizar actions para versões compatíveis com o runtime Node.js vigente, após revisão separada.

## Decisão do ciclo

- PR #28: critérios automatizados do plano #27 satisfeitos; limitações de hardware/E5/concurrency permanecem.
- PR #29: correção isolada passou na CI 4/4; validação do serviço real permanece pendente.
- PR #23 e #25: não alteradas.
- main: preservada no SHA `135f480addc43dd270ea7a08b97da6496b651445`.
- Nenhuma implementação foi promovida; nenhuma tarefa foi marcada como concluída sem a evidência correspondente.
