# QA noturno — 18/11/2026

## Escopo e decisão

Auditoria do estado remoto de NixLMs em 18/11/2026, incluindo PRs recentes, CI, biblioteca de frameworks, integração ponta a ponta, privacidade e persistência.

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- `main` observado após consolidação de ações: `6b9417f63834d47cb86221827857b99548673119`
- Nenhum teste local foi executado: `git clone` falhou por resolução DNS de `github.com` no ambiente disponível.
- Nenhum pacote ML, modelo ou dataset foi instalado/baixado.
- Nenhuma credencial foi lida, nenhum segredo/configuração foi alterado e nenhum serviço Render/Supabase foi acessado.
- Nenhum deploy/release foi executado.

## Alterações concretas deste ciclo

### Merges seguros de manutenção

- [PR #53 — actions/checkout v7](https://github.com/SANTZSPAXX/NixLMs/pull/53) — merge squash confirmado em `b335be5fc5a93c4bd062148364fe25ea90b90021`.
- [PR #54 — actions/upload-artifact v7](https://github.com/SANTZSPAXX/NixLMs/pull/54) — merge squash confirmado em `6b9417f63834d47cb86221827857b99548673119`.
- Os logs dos jobs de teste e CodeQL nas PRs foram consultados. Não havia workflow run anexado aos commits de merge no momento da auditoria.
- [PR #55 — actions/setup-python v7](https://github.com/SANTZSPAXX/NixLMs/pull/55) permanece aberta; após os merges, o GitHub reportou `mergeable=false`. Nenhum update de branch ou force-push foi feito.

### Correções em branches novas

- [PR #71 — detecção conservadora do instalador multimodal](https://github.com/SANTZSPAXX/NixLMs/pull/71), branch própria empilhada sobre #69. Usa metadados de distribuição e disponibilidade do módulo, bloqueia estados divergentes e rejeita URLs/caminhos diretos no arquivo de requisitos. Quatro testes de regressão adicionados. CI #44416546444: 327 testes em cada matriz Windows/Ubuntu, mais dois jobs de benchmark, todos concluídos com sucesso. Sem CodeQL associado a esta PR. Continua draft; depende de #69.
- [PR #72 — exportação da biblioteca sem sobrescrita](https://github.com/SANTZSPAXX/NixLMs/pull/72), branch própria baseada no main observado antes dos merges #53/#54. A exportação agora usa criação exclusiva (`open("x")`) e preserva um JSONL existente. Adiciona teste e CHANGELOG. A branch ficou atrás de main após os merges; CI ainda não foi confirmada. Continua draft e não está pronta para merge.

## Estado de main e PR #48 — Framework Library

[PR #48](https://github.com/SANTZSPAXX/NixLMs/pull/48) foi confirmada como merged; commit de merge `eb55e8a7d001056ee8934aa5270f94b9b242d087`.

A CI #44322381961 foi consultada:
- 4 matrizes de testes, 250 testes por ambiente, todas aprovadas.
- 2 jobs de benchmark aprovados.
- Os logs dos seis jobs foram consultados.

O merge entregou inventário leve e documentação, não instalação de frameworks. O inventário usa `importlib.metadata`/`find_spec` e não importa PyTorch, Transformers, FAISS ou ONNX Runtime. Nenhum pacote foi instalado nesta auditoria.

### Quatro acervos — estado real

| Acervo | Implementação observada | Integração e limite |
|---|---|---|
| Framework Library | `framework_registry.py`, requisitos opcionais e scripts | Inventário leve presente. O instalador seguro da PR #70 ainda não está em main. |
| Private Knowledge Library | SQLite/FTS5, importação de documentos, busca de trechos e fila de candidatos | Integrada à resposta do agente; candidatos só entram no dataset após aprovação explícita. |
| Model Library | Gerenciador Hugging Face e diretório local de modelos | Download e ativação são operações explícitas; limite de download documentado. Não prova que um modelo esteja instalado ou carregado. |
| Training Dataset Library | Dataset JSONL local, auditoria de splits e diretório separado de datasets Hugging Face | Funcionalmente separada, mas ainda não há uma fachada única de biblioteca com inventário/versionamento para todos os datasets. |

### Stack CPU opcional

A lista `requirements-ml-cpu.txt` contém NumPy, SciPy, scikit-learn, Transformers, Sentence Transformers, FAISS CPU, ONNX Runtime, Safetensors e Tokenizers. PyTorch CPU é tratado separadamente; TensorFlow CPU e llama-cpp-python permanecem alternativas separadas.

A documentação/registro ainda não fornece uma matriz versionada completa por pacote com origem, licença, SO/Python/arquitetura e footprint medido. Fontes upstream consultadas:

| Pacote | Licença upstream (resumo) | Compatibilidade relevante |
|---|---|---|
| PyTorch | Licença principal BSD-3-Clause, com licenças de terceiros/componentes | O instalador #70 restringe a Python >=3.11 e Windows/Linux x86_64; ARM64 permanece manual/não validado. |
| NumPy | BSD-3-Clause; wheels incluem componentes de terceiros com licenças próprias | Wheels e tags variam por versão, Python e arquitetura. |
| SciPy | BSD-3-Clause | Dependência binária de NumPy; não assumir wheel para toda combinação ARM. |
| scikit-learn | BSD-3-Clause | Usar wheels; em plataformas ARM específicas pode ser necessário compilar, o que não deve ocorrer automaticamente. |
| Transformers | Apache-2.0 | Documentação atual exige Python moderno e backend como PyTorch; pesos são separados do pacote. |
| Sentence Transformers | Apache-2.0 | Depende de PyTorch/Transformers; consumo de RAM depende principalmente do encoder carregado. |
| FAISS CPU | MIT | Disponibilidade de wheels varia por release, Python e plataforma; instalador atual não habilita ARM64. |
| ONNX Runtime CPU | MIT | Documentação oficial lista wheels CPU para Windows x64 e Linux x64/ARM64, conforme release. |
| Safetensors | Apache-2.0 | Serializador; não inclui pesos. |
| Tokenizers | Apache-2.0 | Extensão Rust; wheel compatível depende da versão e tag Python/plataforma. |

Fontes oficiais:
- PyTorch: https://pytorch.org/get-started/locally/ e https://github.com/pytorch/pytorch/blob/main/pyproject.toml
- NumPy: https://github.com/numpy/numpy/blob/main/LICENSE.txt
- SciPy: https://github.com/scipy/scipy/blob/main/LICENSE.txt
- scikit-learn: https://scikit-learn.org/stable/install.html e https://github.com/scikit-learn/scikit-learn/blob/main/COPYING
- Transformers: https://huggingface.co/docs/transformers/installation e https://github.com/huggingface/transformers/blob/main/LICENSE
- Sentence Transformers: https://github.com/UKPLab/sentence-transformers/blob/master/LICENSE
- FAISS: https://github.com/facebookresearch/faiss/blob/main/LICENSE
- ONNX Runtime: https://onnxruntime.ai/docs/install/
- Safetensors: https://github.com/huggingface/safetensors/blob/main/LICENSE
- Tokenizers: https://github.com/huggingface/tokenizers/blob/main/LICENSE

**Não medido:** tamanho instalado, RSS, latência e CPU no i5/8 GB. A CI não instala o stack ML pesado nem resolve wheels para cada combinação. O instalador #70 só permite Windows/Linux x86_64 e Python >=3.11; Linux ARM64 continua sem validação real. Não habilitar a instalação conjunta do stack como requisito do core.

## Integração ponta a ponta

| Etapa | Estado em main | Evidência/limite |
|---|---|---|
| Diagnóstico de inicialização | Integrado | O core executa checks e expõe status; CI testa os checks. Não substitui diagnóstico no PC físico. |
| Agendador ocioso | Integrado parcialmente | SQLite persistente, handler de ciclo ocioso e intervalo periódico; o manager verifica inatividade/cooldown e limita o treino. |
| Biblioteca privada | Integrada | Busca local é usada no contexto da resposta; importação não executa arquivos. Aprovação de candidatos é explícita. |
| Aprendizagem incremental | Integrada com gates | Candidato isolado, validação e rollback; test split não é usado para escolher a promoção. Não houve treino real neste ciclo. |
| Planejador de objetivos | Integrado parcialmente | Seleciona etapas elegíveis e registra transições; não é executor geral. |
| Executor de tarefas | Não integrado em main | A PR #60 adiciona registry de callbacks, mas o agente da branch não registra handlers concretos. |
| Voz | Não integrada em main | PR #61 é draft e usa Web Speech API do navegador; reconhecimento pode ser remoto, não é ASR local garantido. |
| Persistência Supabase | Não integrada em main | PR #63 é draft; nenhuma conexão/alteração externa foi feita. |
| Runtime Render | Não integrado em main | PR #62 é draft; nenhum deploy foi feito. |

### Risco de cancelamento

O scheduler de main para o loop de polling, mas não interrompe um handler já em execução. O ciclo de aprendizagem é síncrono e não recebe token de cancelamento. Portanto, ainda não há garantia de kill switch durante uma época já iniciada. Não marcar cancelamento de treino como concluído.

## Revisão das PRs recentes e CI

Todos os links abaixo apontam para os runs reais; foram consultados os estados dos jobs e logs de teste representativos. Não inferir ausência de alertas apenas porque CodeQL terminou com sucesso.

| PR | CI real | Resultado observado | Decisão |
|---|---|---|---|
| #48 | [#44322381961](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44322381961) | 4 matrizes x 250 testes + 2 benchmarks | Merged antes deste ciclo; nenhum pacote instalado. |
| #53 | [#44331994555](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44331994555), CodeQL [#44331994550](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44331994550) | Testes e CodeQL aprovados; 276 testes no log Windows | Squash merged. |
| #54 | [#44332009913](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44332009913), CodeQL [#44332009968](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44332009968) | Testes e CodeQL aprovados; 276 testes no log Windows | Squash merged. |
| #55 | [#44340652106](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44340652106), CodeQL [#44340652330](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44340652330) | Testes e CodeQL aprovados; 298 testes no log Ubuntu 3.12 | Não merged: mergeability false após mudanças na main. |
| #56 | [#44332064482](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44332064482), CodeQL [#44332064012](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44332064012) | Testes e CodeQL aprovados; 276 testes no log Ubuntu 3.10 | Não merged: mergeability false. |
| #59 | [#44345273110](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44345273110), CodeQL [#44345272790](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44345272790) | 322 testes no log Windows; CodeQL analisou 69/69 arquivos Python e 2/2 workflows e enviou resultado | Draft; cliente não exige HTTPS para URL remota e servidor permite bind remoto sem TLS nativo. |
| #60 | [#44349569259](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44349569259), CodeQL [#44349569252](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44349569252) | 327 testes no log Ubuntu 3.12; jobs restantes concluíram success | Draft; autonomia default-on, etapas manuais iniciadas sem handler e autostart pode sobrescrever serviço/tarefa existente. |
| #61 | [#44350486894](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44350486894), CodeQL [#44350487072](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44350487072) | 314 testes no log Ubuntu 3.10; CodeQL success | Draft; microfone exige ação do usuário, mas reconhecimento pode ser remoto e a escuta contínua não pausa ao ocultar a aba. |
| #62 | [#44351251086](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44351251086), CodeQL [#44351250703](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44351250703) | 315 testes no log Ubuntu 3.12; CodeQL success | Draft; Origin same-origin Render é rejeitado e Blueprint usa plano Starter pago. |
| #63 | [#44355049320](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44355049320) | 318 testes no log Ubuntu 3.10; jobs de benchmark success; sem CodeQL associado | Draft; NameError no backfill, restore pode sobrescrever dados locais e snapshot envia DB privado automaticamente quando URL está presente. |
| #64–#67 | #64 [#44371504994](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44371504994), #65 [#44371526840](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44371526840), #66 [#44371544619](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44371544619), #67 [#44371555478](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44371555478) | Todos os jobs unitários/benchmarks/CodeQL concluíram success; 313 testes no log representativo de #64–#67 | Não merged: #65–#67 mergeability false; #64 é mergeable, mas altera requisitos usados pelo bootstrap multimodal ainda ativo em main. |
| #69 | [#44375657242](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44375657242), CodeQL [#44375657168](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44375657168) | 323 testes por matriz; 2 benchmarks; CodeQL analisou 69/69 Python e 2/2 workflows | Aberta; remove bootstrap automático, mas o consentimento ainda não mostra a árvore transitiva. |
| #70 | [#44379056345](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44379056345) | 337 testes por matriz; 1 skip nos ambientes Linux para wrapper PowerShell; sem CodeQL associado | Draft; instalador exige venv e confirmação, mas falta binary-only e matriz de origem/licença/footprint. |
| #71 | [#44416546444](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44416546444) | 327 testes por matriz + 2 benchmarks, todos success | Draft; empilhada sobre #69. |
| #72 | [#44417488132](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44417488132), CodeQL [#44417488269](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44417488269) | 314 testes por matriz + 2 benchmarks; CodeQL success | Draft; base ficou atrás de main após #53/#54. |

CodeQL em estado success significa que a análise terminou e enviou SARIF; os logs não forneceram contagem explícita de alertas para todos os runs.

## Achados de segurança e correções recomendadas

### #69 — instalação multimodal automática

Em main, `nixlms_web/server.py` ainda chama `media.bootstrap_async` com padrão habilitado; o gerenciador pode instalar dependências no startup. A PR #69 remove esse bootstrap automático, mas ainda não foi integrada. Até ela ser resolvida, não iniciar o servidor principal em ambiente que não autorize a instalação automática.

A PR #71 corrige detecção de metadados/módulos e rejeita URLs/caminhos diretos, mas não resolve a prévia da árvore transitiva. O instalador ainda deve usar `pip --dry-run --report`, exibir todas as dependências, origem/versão e instalar exatamente a resolução aprovada.

### #70 — Framework installer

O novo instalador é mais seguro que o script de main, mas:
- a detecção de PyTorch usa metadados sem bloquear divergência entre dist-info e módulo;
- não restringe a resolução a wheels binárias, permitindo preparação/build de sdist;
- não apresenta origem/hash de cada artefato;
- não estima tamanho de download/instalado;
- não separa perfil mínimo de perfil pesado.
O script antigo em main ainda atualiza pip e instala requisitos sem exigir venv/consentimento tipado. Não usar até a substituição segura ser integrada.

### #60 — autonomia e autostart

- `NIXLMS_AUTONOMY_ENABLED` usa default `1`; o ciclo é habilitado sem opt-in.
- O preview propõe iniciar etapas sem handler; o job pode deixá-las em `in_progress` sem execução.
- Não foram encontradas chamadas concretas a `register_task()` no agente desta branch.
- `Register-ScheduledTask -Force` pode sobrescrever tarefa existente.
- `cat > ~/.config/systemd/user/nixlms.service` pode sobrescrever serviço existente.
Não integrar antes de default-off, execução apenas de handlers allowlisted e instalação não destrutiva.

### #62 — Render

A validação de Origin permite apenas loopback. O POST same-origin do domínio Render pode retornar 403. O YAML usa `plan: starter` com disco de 1 GB, não plano Free. Nenhum deploy foi feito.

### #63 — Supabase

- O bloco de backfill usa `library` antes de atribuir essa variável; o NameError é capturado e o backfill não ocorre.
- `NIXLMS_DATABASE_URL` inicia restore e sync sem opt-in separado.
- O snapshot inclui banco da biblioteca privada, episódios, objetivos e datasets.
- `restore()` substitui arquivos locais sem comparar geração/hash local ou criar backup recuperável.
- `stop()` também chama sync remoto.
Nenhuma conexão Supabase foi feita e nenhuma migration foi aplicada por esta auditoria. Não integrar antes de opt-in explícito, allowlist de dados, backup/conflito e correção do backfill.

### #59 — API gateway

Loopback por padrão e chaves em hash são bons controles. Porém, o servidor permite bind remoto por variável de ambiente sem TLS embutido e o cliente envia Bearer token para qualquer `base_url`, inclusive HTTP remoto. Manter atrás de proxy HTTPS em loopback ou validar HTTPS para hosts remotos.

### #61 — voz

O botão e a permissão do navegador são explícitos. A Web Speech API pode usar reconhecimento remoto; não é processamento local garantido. A escuta contínua deve parar em `visibilitychange`/`pagehide` e exigir nova ativação ao retornar.

### Runtime/treino

O scheduler interrompe o polling, mas não cancela um handler em execução. `train_incremental` não recebe token de cancelamento; um ciclo já iniciado pode continuar depois de `stop()`. Adicionar cancelamento cooperativo por batch/epoch, checkpoint e rollback antes de anunciar kill switch.

### Biblioteca privada

A exportação de candidatos aprovados em main abria destino com modo `w` e podia sobrescrever um JSONL existente. A correção está na PR #72; aguardar CI e atualizar base antes de integrar.

## Revisões registradas

- [PR #59](https://github.com/SANTZSPAXX/NixLMs/pull/59) — TLS e proteção do Bearer token.
- [PR #60](https://github.com/SANTZSPAXX/NixLMs/pull/60) — default de autonomia, etapas sem handler e autostart não destrutivo.
- [PR #61](https://github.com/SANTZSPAXX/NixLMs/pull/61) — pausa de microfone quando a aba fica oculta.
- [PR #62](https://github.com/SANTZSPAXX/NixLMs/pull/62) — Origin Render e plano pago.
- [PR #63](https://github.com/SANTZSPAXX/NixLMs/pull/63) — backfill, opt-in/allowlist e restore sem perda.
- [PR #69](https://github.com/SANTZSPAXX/NixLMs/pull/69) — consentimento e dependências transitivas.
- [PR #70](https://github.com/SANTZSPAXX/NixLMs/pull/70) — detecção, wheels e matriz de frameworks.

Busca de issues abertas retornou zero issues.

## Próximas prioridades

1. Desabilitar bootstrap multimodal automático em main via #69 após resolver relatório completo de dependências; depois integrar #71 na ordem correta.
2. Atualizar o branch da #72 para o main atual e confirmar CI antes de qualquer merge.
3. Corrigir #60: autonomia default-off, handlers concretos, etapas manuais não executáveis e autostart com backup/recusa de sobrescrita.
4. Corrigir #63: opt-in separado, allowlist de dados, restore com conflito/backup e backfill sem NameError.
5. Corrigir #62 e #59: origem pública estrita, custo real e TLS obrigatório para tráfego remoto.
6. Fechar #70 com wheels binárias, origem/hash, licença, matriz por pacote e perfis mínimos/pesados.
7. Adicionar cancelamento cooperativo ao treino ocioso e teste de concorrência da promoção.
8. Validar no Windows 11 físico com i5/8 GB: startup, SQLite, ciclo ocioso, cancelamento, Ollama local e RSS/CPU.
9. Validar Linux ARM64 em hardware/runner real; não habilitar instalação automática de frameworks até comprovar wheels para cada versão.

## Decisão

Somente PRs de manutenção de GitHub Actions #53 e #54 foram integradas após revisão de diff, logs e checks verdes. Nenhuma PR funcional de runtime, autonomia, voz, cloud, Supabase ou framework foi mesclada. Nenhum deploy, instalação, download de modelo ou alteração de serviço externo foi executado.
