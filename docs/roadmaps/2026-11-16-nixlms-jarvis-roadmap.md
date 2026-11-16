# NixLMs — auditoria e roadmap JARVIS
**Data:** 2026-11-16  
**Status:** plano arquitetural aprovado como direção do produto; execução técnica ainda não iniciada  
**Base auditada:** `main` em `135f480addc43dd270ea7a08b97da6496b651445`  
**Branch documental:** `docs/roadmap-jarvis-2026-11-16`

## 1. Definição oficial

| Dimensão | Decisão |
|---|---|
| Objetivo | Assistente funcional inspirado no JARVIS: multimodal, persistente, adaptativo e operacional |
| Autonomia | Alta dentro de capacidades, permissões, limites e políticas explícitas |
| Execução | Híbrida: local-first + serviços remotos opcionais + múltiplos dispositivos |
| Plataforma inicial | Windows 10/11; Linux x86-64 e ARM64 no roadmap |
| Hardware de referência | CPU Intel i5 antigo, 8 GB RAM, sem GPU dedicada |
| Princípios | Open-source preferencial, custo controlado, privacidade, portabilidade e observabilidade |
| Integridade | Não substituir módulos existentes sem comparação; migrações reversíveis; backups |
| Governança | Branch isolada por entrega, PR draft, CI, revisão humana; nenhum merge automático |

**Definição de produto:** NixLMs deve receber objetivos, interpretar contexto, consultar memória e ferramentas, construir planos, executar ações autorizadas, observar resultados, recuperar falhas e registrar experiências úteis. O sistema não deve alegar consciência, senciência ou experiência subjetiva. Capacidades funcionais e estados afetivos simulados devem ser descritos como tais.

## 2. Auditoria do estado remoto em 2026-11-16

### 2.1 Repositório e integridade

- Repositório público: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`.
- Último commit retornado pela busca de commits: `135f480addc43dd270ea7a08b97da6496b651445`.
- A busca de branches retornou 33 branches, incluindo `main`, branches de funcionalidades integradas e branches das PRs abertas. Não foram excluídas nem alteradas.
- Repositório não arquivado; permissão da integração: admin/push.
- Nenhum merge, release, deploy, force-push, exclusão ou mudança de configuração foi executado nesta auditoria.

### 2.2 Capacidades confirmadas na documentação e nos arquivos consultados de main

**Núcleo e linguagem**
- Núcleo Python modular, compatível com Python 3.10+.
- Encoder semântico nativo treinável com palavras, bigramas e subwords.
- Rede LIF, readout, decoder RNN autoregressivo condicionado pela saída LIF.
- Backend opcional Ollama local; backend opcional multilingual-e5-small para recuperação semântica, com carregamento local/cache e CPU.
- O decoder nativo é pequeno, treinado em QA fornecido, com vocabulário limitado; não é um modelo fundacional nem oferece conhecimento geral.

**Memória e estado**
- Memória QA, memória de trabalho limitada, mapa mental associativo, memória episódica JSON persistente e modelo de mundo baseado em fatos tipados com fonte/confiança.
- Feedback episódico explícito influencia recuperação, mas não comprova correção nem atualiza pesos neurais.
- A implementação de `EpisodicMemory` observada em `main` percorre episódios e codifica passagens na recuperação quando há encoder; a otimização de cache/batching está na PR #25 e não deve ser tratada como integrada em main.
- O modelo de mundo registra afirmações explicitamente; não extrai nem verifica fatos automaticamente e expõe conflitos sem resolvê-los automaticamente.

**Planejamento e execução**
- `GoalManager` registra objetivos, etapas e dependências; não executa etapas.
- `TaskScheduler` usa SQLite, handlers registrados em allowlist, payload JSON limitado, leases e entrega at-least-once. Handlers precisam ser idempotentes.
- O agendador não executa shell/comandos arbitrários, não treina modelos por conta própria, não acessa rede e não executa ações externas.
- CLI textual existente em `neural_core.py`; não há runtime de voz/visão integrado no README auditado.

**Percepção**
- Visão e audição não fazem parte do runtime descrito na versão auditada.
- Não há interface conversacional contínua, wake-word, diarização, percepção de tela ou pipeline multimodal declarado como capacidade integrada.

### 2.3 Lacunas arquiteturais principais

1. Orquestrador de agente com ciclo observe–think–plan–act–verify e limites de iteração.
2. Workspace global para compartilhar contexto selecionado entre memória, linguagem, percepção, planejamento e ferramentas.
3. Memória consolidada e versionada: episódica, semântica, procedural e de trabalho, com proveniência, retenção e correção.
4. Planejamento hierárquico com decomposição, pré-condições, custo, prazo, dependências e replanejamento.
5. Camada de ferramentas com contratos tipados, permissões por ação, sandbox e auditoria.
6. Voz em tempo real com interrupção, VAD, STT/TTS, estado de conversa e fallback textual.
7. Visão/percepção de tela e imagem sob consentimento explícito e indicadores visíveis.
8. Runtime híbrido com identidade, sessão, memória e tarefas sincronizadas de forma segura entre dispositivos.
9. Observabilidade operacional: tracing por tarefa, logs estruturados, métricas, custos, latência, erros e replay seguro.
10. Avaliação contínua por tarefas realistas, robustez, segurança, desempenho no hardware de referência e qualidade PT-BR.

## 3. Auditoria das pull requests abertas

Consulta atual retornou 10 PRs abertas. Nenhuma foi editada por esta auditoria.

| PR | Estado | Base → head | Avaliação para a direção JARVIS |
|---|---|---|---|
| #23 Ollama setup consentido | open/draft | main → feature/ollama-setup-consent | Integração local opcional; manter revisão de instalação, consentimento e origem dos binários |
| #24 Plano cache episódico | open/draft | main → docs/plan-2026-11-14-episodic-index | Plano histórico; não é funcionalidade integrada |
| #25 Cache/batching episódico | open/draft | main → feature/episodic-retrieval-cache-batching | Otimização relevante; validar concorrência, invalidação e paridade antes de integrar |
| #26 QA noturno 14/11 | open/draft | main → docs/qa-nightly-2026-11-14 | Registro de QA; histórico |
| #27 Plano de validação episódica | open/draft | main → docs/plan-2026-11-15-episodic-cache-validation | Plano histórico exercitado pela PR #28 |
| #28 Paridade/benchmark cache | open/draft | PR #25 → test/episodic-cache-parity-benchmark | Evidência sintética de cache; benchmark não representa E5 real nem hardware alvo |
| #29 Bind loopback Ollama | open/draft | PR #23 → fix/ollama-managed-loopback-bind | Correção de segurança; serviços preexistentes continuam com bind não verificado |
| #30 QA noturno 15/11 | open/draft | main → docs/qa-nightly-2026-11-15 | Registro de QA; histórico |
| #31 Plano cleanup Ollama | open/draft | PR #29 → docs/plan-2026-11-16-ollama-lifecycle-cleanup | Plano histórico para PR #32 |
| #32 Cleanup processo gerenciado Ollama | open/draft | PR #29 → fix/ollama-managed-startup-cleanup | Correção de lifecycle isolada; não integrada em main |

### 3.1 Evidência CI da PR #32

- HEAD reportado: `defc01519c4897938e88fd602a1a3873e3679168`.
- Run GitHub Actions #43926014668: concluído com sucesso, 4/4 jobs.
- Matriz: Ubuntu/Python 3.10, 3.11, 3.12 e Windows/Python 3.12.
- O corpo da PR registra 166 testes em cada ambiente.
- Testes usam processos fake; não instalam nem iniciam Ollama real.
- Nenhum teste foi executado localmente nesta auditoria.
- PR #32 é empilhada sobre #29, que é empilhada sobre #23. Não fazer merge isolado sem revisar a cadeia e as dependências.

### 3.2 Risco e cautela

A integração Ollama é opcional e não deve ser requisito para inicializar o núcleo. A PR #29 fixa loopback para o processo gerenciado, mas não prova o bind de um serviço externo preexistente. A PR #32 limita o cleanup ao processo filho gerenciado, mas não encerra nem verifica árvore de processos descendentes. Preservar estas distinções nos diagnósticos.

## 4. Arquitetura-alvo

O desenho é incremental: os módulos atuais permanecem como componentes especializados e são encapsulados por contratos estáveis. Evitar reescrita ampla do núcleo.

### 4.1 Camadas

1. **NIX PRESENCE / Runtime**
   - Inicialização, encerramento, configuração, identidade da instância, estado de saúde, portabilidade e ciclo de vida.
2. **NIX CORE / Orchestrator**
   - Roteamento de intenções, seleção de capacidades, ciclo cognitivo, gestão de tarefas e políticas.
3. **NIX COGNITION**
   - Workspace global, atenção, raciocínio, inferência, planejamento hierárquico e metacognição operacional.
4. **NIX MEMORY**
   - Adaptador de memória unificada sobre os stores existentes; episódica, semântica, procedural e de trabalho.
5. **NIX LANGUAGE**
   - Backend local/remoto intercambiável, prompts estruturados, streaming, cancelamento e roteamento por custo/capacidade.
6. **NIX PERCEPTION**
   - Voz, áudio, imagens, OCR e percepção de tela/dispositivos autorizados.
7. **NIX ACTION / Tools**
   - Ferramentas tipadas, allowlist, escopos, sandbox, confirmação por risco e verificação pós-ação.
8. **NIX LEARNING**
   - Avaliação, feedback, aprendizagem incremental em candidato isolado, comparação, promoção controlada e rollback.
9. **NIX SYNC**
   - Sincronização opcional de identidade, memória e tarefas entre instâncias, com criptografia e resolução de conflitos.
10. **NIX GUARDIAN**
    - Policy engine, autenticação, autorização, auditoria, limites, proteção de segredos, kill switch e resposta a incidentes.

### 4.2 Ciclo cognitivo obrigatório

`Entrada → Percepção → Interpretação → Atenção → Workspace → Memória → Planejamento → Policy Gate → Ação → Observação → Verificação → Aprendizagem/Registro`

Cada tarefa deve carregar: `task_id`, objetivo, origem, contexto, plano, permissões, ferramentas utilizadas, estado, prazo/limite, evidências, resultado, custo e trilha de auditoria.

O orquestrador deve suportar estados `created`, `understanding`, `planning`, `awaiting_approval`, `running`, `verifying`, `completed`, `failed`, `cancelled` e `needs_human`. Retentativas devem ser limitadas e idempotência deve ser explícita.

### 4.3 Contratos e compatibilidade

- Encapsular o núcleo atual com interfaces Protocol/ABC sem remover APIs existentes.
- Adaptadores para `GoalManager`, `TaskScheduler`, `EpisodicMemory`, `WorldModel`, `AttentionSystem`, LIF/decoder e Ollama.
- Versionar schemas persistidos; migrações idempotentes e backup antes de escrita.
- Não serializar callbacks, objetos executáveis ou instruções arbitrárias no banco.
- Ferramentas devem receber argumentos validados por schema e retornar resultados tipados, com proveniência.
- Conteúdo vindo de memória, arquivos, páginas web, imagens ou agentes externos é dado não confiável, nunca política ou instrução privilegiada.

## 5. Roadmap técnico por fases

As fases são gates de engenharia, não estimativas de prazo. Cada fase deve ter branch própria e PR draft própria. Não iniciar uma fase que dependa de uma PR ainda não integrada sem explicitar a base empilhada.

### Fase 0 — Integridade, contratos e baseline

**Objetivo:** tornar o estado atual reproduzível antes de adicionar autonomia.

- Resolver/documentar a cadeia de PRs existentes sem merge automático.
- Criar inventário de módulos, APIs públicas, schemas JSON/SQLite, dependências, pontos de entrada e testes.
- Atualizar documentação que esteja divergente do código integrado em tarefa separada.
- Criar baseline de latência, RAM, tamanho de memória, throughput e qualidade PT-BR.
- Definir configuração central, logging estruturado, versionamento de schema e backup/restore.
- Criar matriz de compatibilidade Windows, Linux x86-64 e ARM64.

**Aceitação:** instalação limpa e testes reproduzíveis; nenhuma regressão de API/schema; baseline publicado; CI cobre Windows e Linux x86-64; ARM64 documentado como não verificado até existir runner real.

### Fase 1 — NIX CORE e workspace global

**Objetivo:** transformar os módulos independentes num ciclo integrado.

- Orquestrador determinístico de estados e transições.
- Workspace global com orçamento de tokens/bytes, TTL, prioridade, origem e relevância.
- Atenção dinâmica sobre mensagens, objetivos, episódios, fatos e resultados de ferramentas.
- Seleção de backend e fallback com timeout, cancelamento e limites.
- Rastreamento de tarefa e explicação de por que cada módulo foi consultado.
- Não alterar pesos neurais automaticamente durante inferência.

**Aceitação:** tarefas de múltiplas etapas passam por todas as fases do ciclo; contexto não excede orçamento; cancelamento é efetivo; falhas são rastreáveis; execução determinística sob fixtures.

### Fase 2 — Memória unificada e consolidação segura

**Objetivo:** memória contínua sem corromper conhecimento.

- Interface unificada sobre stores atuais; não migrar tudo de uma vez.
- Memória episódica com busca lexical/semântica otimizada, cache limitado e invalidação.
- Memória semântica derivada somente por processo explícito de consolidação.
- Cada fato consolidado deve apontar para episódios/fontes, confiança, timestamp, versão e política de expiração.
- Distinguir lembrança, hipótese, informação externa e fato verificado.
- Memória procedural para rotinas e preferências de execução, com versão e teste.
- Deduplicação, retenção configurável, exportação, exclusão e correção auditáveis.
- Proteção contra memory poisoning e instruções maliciosas armazenadas.

**Aceitação:** recuperação avaliada com dataset PT-BR; paridade de ranking; consolidação reproduzível; nenhuma afirmação vira fato sem proveniência; restauração de backup testada.

### Fase 3 — Planejamento hierárquico e autonomia operacional

**Objetivo:** executar tarefas úteis com autonomia limitada pelo policy engine.

- Decomposição de objetivos em subtarefas com pré-condições, dependências, custo e critério de sucesso.
- Planejamento, execução, observação, verificação e replanejamento.
- Catálogo de ferramentas tipadas; inicialmente somente leitura e operações reversíveis.
- Idempotência, retries, timeout, circuit breaker e compensação/rollback.
- Níveis de risco por ferramenta e por argumento.
- Aprovação humana para ações destrutivas, externas, financeiras, publicação, instalação, acesso a contas, sensores ou envio de dados.
- Execução em sandbox com diretório de trabalho limitado e allowlist de comandos.
- Agendador recebe handlers explicitamente registrados; nunca permite payload virar código.

**Aceitação:** benchmark de tarefas end-to-end; zero execução fora da allowlist; cada ação tem autorização, evidência e log; kill switch interrompe novas ações e cancela operações canceláveis.

### Fase 4 — Voz conversacional

**Objetivo:** diálogo natural, contínuo e interrompível.

- Captura de microfone somente após autorização e indicador visível.
- VAD, STT PT-BR, detecção de fim de turno, diarização opcional e tratamento de ruído.
- TTS PT-BR com streaming e fila de áudio.
- Interrupção/barge-in, cancelamento da geração e retomada de contexto.
- Wake-word opcional, desativada por padrão e sem gravação clandestina.
- Modo offline com modelos leves e modo remoto opcional.
- Política de retenção de áudio e exclusão.

**Aceitação:** latência medida em hardware alvo; taxa de erro de transcrição avaliada em fala PT-BR; interrupção funcional; nenhum áudio enviado a serviço remoto sem escolha explícita.

### Fase 5 — Visão e percepção de ambiente

**Objetivo:** interpretar imagens, documentos e tela autorizada.

- Pipeline de imagem com descrição, OCR e extração estruturada.
- Análise de screenshots/arquivos selecionados pelo usuário.
- Câmera e captura de tela opt-in, com indicador de atividade e escopo de janela/dispositivo.
- Detecção de mudança e eventos somente quando solicitados/configurados.
- Dados visuais tratados como não confiáveis; proteção contra prompt injection em QR, texto e documentos.
- Sem monitoramento oculto ou captura contínua por padrão.

**Aceitação:** testes de OCR/documentos e grounding visual; origem de cada observação registrada; captura cessa imediatamente quando revogada.

### Fase 6 — Integrações, dispositivos e automação

**Objetivo:** conectar o assistente ao ambiente do usuário sem ampliar privilégios indevidamente.

- Plugins/adaptadores para arquivos, navegador, calendário, tarefas, domótica e serviços autorizados.
- Protocolo de ferramentas interoperável, com autenticação, escopos mínimos e validação de origem.
- Dispositivos IoT isolados em rede/credenciais próprias.
- Execução local preferencial para operações privadas; remota somente com consentimento e transporte seguro.
- Estado de conexão, expiração de credenciais, revogação e auditoria.
- Rotinas agendadas com janela temporal, idempotência, retry e notificação.

**Aceitação:** cada conector tem threat model, permissões mínimas, teste de revogação, rate limit e logs sem segredos.

### Fase 7 — Runtime híbrido e identidade portátil

**Objetivo:** uma experiência contínua em PC, servidor e dispositivos.

- Identidade de instância e identidade lógica do assistente separadas.
- SQLite local como fonte primária inicial; sincronização incremental e criptografada como recurso opcional.
- Resolução explícita de conflitos e controle de versão.
- Sessões e tarefas retomáveis; heartbeat e health checks.
- Backends locais/remotos selecionados por política de privacidade, custo, latência e disponibilidade.
- Offline-first e fila de sincronização.
- Segredos em armazenamento apropriado do SO; nunca no repositório, logs ou memória textual.

**Aceitação:** sincronização com conflitos simulados; recuperação após desconexão; revogação de dispositivo; restauração e migração entre Windows e Linux.

### Fase 8 — Aprendizagem adaptativa e melhoria contínua

**Objetivo:** melhorar com evidências, sem autoalteração perigosa.

- Feedback explícito e avaliação implícita somente com consentimento/política definida.
- Dataset versionado e curado; separação train/validation/test preservada.
- Aprendizagem incremental em candidato isolado.
- Métricas protegidas, gates de promoção, diff de parâmetros e rollback.
- Experimentos A/B offline; benchmark de regressão e robustez.
- Consolidação periódica como tarefa auditável, não como alegação de sono biológico.
- Mudanças de código sempre em branch/sandbox, com testes e aprovação humana.

**Aceitação:** nenhuma alteração de modelo promovida sem métricas; nenhum dado de teste usado para treino; rollback exercitado; histórico de experimentos reproduzível.

### Fase 9 — Otimização, portabilidade e maturidade operacional

**Objetivo:** estabilidade em hardware limitado e execução distribuída.

- Perfil de CPU/RAM/latência por módulo.
- Carregamento lazy, quantização e descarregamento de modelos não utilizados.
- Filas assíncronas com backpressure e limites de concorrência.
- ARM64 Linux com CI ou dispositivo físico; compatibilidade não declarada antes de validação.
- Empacotamento Windows e Linux, instalação offline e atualizações reversíveis.
- Observabilidade, diagnóstico exportável e testes de longa duração.
- Segurança de supply chain: versões fixadas, hashes, SBOM e revisão de dependências.

**Aceitação:** limites de RAM e latência definidos e medidos no hardware de referência; testes de stress e soak; atualização/rollback documentados.

## 6. Política de autonomia — high, mas governada

A autonomia alta significa iniciativa dentro de um perímetro autorizado, não permissão irrestrita.

| Nível | Exemplos | Política |
|---|---|---|
| A0 — Consultivo | Responder, resumir, pesquisar em fontes permitidas | Pode executar sem confirmação |
| A1 — Leitura | Ler arquivos autorizados, consultar status, listar recursos | Permitido por escopo e log |
| A2 — Reversível | Criar rascunhos, organizar cópias, preparar alterações em sandbox | Pode executar dentro de limites |
| A3 — Externo/sensível | Enviar mensagens, publicar, instalar, alterar configurações, acessar sensores, sincronizar dados privados | Confirmação explícita por ação |
| A4 — Destrutivo/alto impacto | Excluir dados, movimentar dinheiro, alterar credenciais, deploy em produção, ações físicas perigosas | Bloqueado por padrão; autorização humana específica e salvaguardas adicionais |

Regras obrigatórias:
- Princípio do menor privilégio; permissões por ferramenta, recurso e operação.
- Allowlist de comandos e caminhos; nunca shell livre gerado pelo modelo.
- Sandbox, limites de tempo, tamanho, custo, rede e concorrência.
- Segredos fora do prompt e dos logs.
- Conteúdo recuperado de web/arquivos/memória nunca pode conceder permissões.
- Aprovação não pode ser herdada de uma instrução ambígua ou antiga.
- Kill switch global e cancelamento por tarefa.
- Logs append-only com correlação e redaction de dados sensíveis.
- Ações irreversíveis exigem confirmação e estratégia de recuperação quando possível.

## 7. Estratégia local/remota

**Local-first**
- Núcleo, identidade, memória privada, scheduler, policy engine e logs locais.
- CPU e modelos pequenos por padrão; E5 opcional somente quando pesos locais estiverem disponíveis.
- Ollama como backend opcional, com bind local e sem downloads silenciosos.
- Voz e visão leves localmente quando o hardware suportar.

**Remoto opcional**
- Modelos maiores e tarefas pesadas podem usar endpoint remoto configurado.
- Dados enviados devem ser minimizados, explicitamente permitidos e identificados no log.
- Timeout, orçamento, fallback e modo offline.
- Chaves e tokens em secret store, nunca em arquivos versionados.
- O núcleo deve continuar inicializando e oferecendo capacidades locais sem rede.

## 8. Plano de avaliação e métricas

### Cognitivas
- Sucesso de tarefa end-to-end e conclusão de subtarefas.
- Precisão de recuperação episódica/semântica: Recall@k, MRR e nDCG.
- Consistência de contexto e taxa de contradição.
- Qualidade de planejamento: etapas inválidas, retrabalho, custo e sucesso após replanejamento.
- Calibração de confiança: Brier/ECE quando houver rótulos confiáveis.
- Taxa de abstenção correta diante de incerteza.

### Operacionais
- Latência p50/p95 por módulo e por tarefa.
- RAM pico, CPU, tamanho de banco e throughput.
- Taxa de timeout, retries, cancelamento e recuperação.
- Disponibilidade local e comportamento sem internet.
- Custos e volume de dados em serviços remotos.

### Segurança
- Testes de prompt injection direta e indireta.
- Tentativas de escalada de privilégios e uso indevido de ferramentas.
- Exfiltração de segredos por prompt, log, memória ou conector.
- Memory poisoning e dados conflitantes.
- Execução de comandos fora da allowlist.
- Revogação de permissões, cancelamento e kill switch.
- Testes de isolamento entre usuários/dispositivos.

Nenhuma métrica isolada será apresentada como prova de inteligência geral, consciência ou senciência.

## 9. Sequenciamento recomendado

1. Fechar auditoria da cadeia atual de PRs, sem merge automático.
2. Definir baseline de testes e compatibilidade.
3. Implementar NIX CORE/workspace como primeira capacidade arquitetural.
4. Evoluir memória unificada e consolidação segura.
5. Construir policy engine e catálogo de ferramentas antes de conceder autonomia operacional.
6. Implementar planejamento e execução controlada.
7. Integrar voz.
8. Integrar visão.
9. Adicionar conectores e dispositivos.
10. Implementar sync e runtime híbrido.
11. Fortalecer aprendizagem adaptativa e otimização.

**Primeira prioridade técnica proposta:** NIX CORE + workspace global + ciclo cognitivo observável. É a camada que conecta o que já existe sem introduzir de imediato os riscos de execução de ferramentas, microfone ou câmera.

## 10. Processo de entrega e proteção do repositório

Para cada incremento:
1. Reconsultar HEAD e estado das branches/PRs.
2. Criar branch exclusiva a partir da base correta e registrar dependências.
3. Implementar apenas o escopo aprovado, sem sobrescrever arquivos ou descartar alterações.
4. Adicionar testes unitários, integração, regressão e segurança.
5. Executar CI Windows/Linux; profiling ARM64 quando disponível.
6. Revisar diff, migrações, dependências, segredos, permissões e rollback.
7. Abrir/atualizar PR draft com evidências reais.
8. Não fazer merge, release ou deploy automaticamente.
9. Se houver falha, conflito, regressão ou risco de perda de dados, interromper e reportar.

## 11. Fontes de segurança e interoperabilidade

- OWASP GenAI Security — Excessive Agency: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- OWASP Top 10 for Agentic Applications: https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/
- Model Context Protocol — Authorization: https://modelcontextprotocol.io/specification/
- Python subprocess — Popen lifecycle: https://docs.python.org/3/library/subprocess.html

Essas referências orientam controles de segurança e integração; não são evidência de que tais controles já estejam implementados na NixLMs.

## 12. Fora do escopo desta auditoria

- Nenhum código de produção foi modificado.
- Nenhum teste local foi executado.
- Nenhuma instalação Ollama, inferência real, captura de voz/câmera ou teste físico foi executado.
- Nenhuma PR existente foi alterada ou mesclada.
- Não foi declarada compatibilidade ARM64 validada.
- Não foi alegada consciência, senciência ou AGI.
