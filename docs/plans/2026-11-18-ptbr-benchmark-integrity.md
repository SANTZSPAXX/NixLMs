# NixLMs — ciclo matinal de 2026-11-18
## Plano: integridade e validade do benchmark episódico PT-BR

**Status:** planejamento para o ciclo da tarde; nenhuma implementação foi feita neste ciclo.  
**Base auditada:** `main` em `135f480addc43dd270ea7a08b97da6496b651445`.  
**Branch documental:** `docs/plan-2026-11-18-ptbr-benchmark-integrity`.  
**Objetivo do produto:** assistente funcional inspirado no JARVIS, autonomia alta sob permissões, execução local e remota opcional.

## 1. Decisão executiva

**Única prioridade recomendada para a tarde: corrigir a integridade, a proveniência e a validade metodológica do benchmark de recuperação episódica PT-BR antes de usá-lo como gate de qualidade.**

A PR #36 já adicionou um benchmark offline, mas a revisão encontrou questões que impedem tratar o baseline como evidência confiável:
- a origem independente de parte do corpus não está demonstrada;
- a categoria `contextual` não fornece histórico conversacional ao avaliador;
- empates podem depender da ordem original dos episódios;
- a identidade do E5 local não é forte o suficiente para reproduzir comparações entre diretórios diferentes;
- a proteção de saída da PR #37 bloqueia caminhos específicos, mas não funciona como allowlist geral para todos os dados persistentes do projeto.

Não alterar #35, #36 ou #37. A implementação, se aprovada, deverá ser empilhada sobre o HEAD atual da #37 e aberta em PR draft própria.

## 2. Auditoria remota

### 2.1 Repositório

- Repositório público: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`.
- HEAD de `main`: `135f480addc43dd270ea7a08b97da6496b651445`.
- Branches retornadas: 38; a paginação terminou sem uma segunda página.
- PRs abertas: 15; todas estão em estado open/draft e sem merge.
- Issues abertas: nenhuma retornada.
- Nenhuma branch, PR, configuração, release ou deploy foi alterado nesta auditoria.

### 2.2 CI

- `main`, run [#43576200437](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43576200437): 4/4 jobs success — Ubuntu Python 3.10, 3.11, 3.12 e Windows Python 3.12.
- Todos os 15 HEADs de PR consultados possuem workflow associado concluído com `success`.
- PR #35, run [#44088737620](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44088737620): 4/4 jobs success.
- PR #36, run [#44153228925](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44153228925): 6/6 jobs success — quatro matrizes de testes e dois benchmarks. Isso valida o HEAD da #36, não as alterações posteriores da #37.
- PR #37, run [#44212492592](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44212492592): 6/6 jobs success. Os quatro logs da matriz foram consultados: 182 testes passaram em cada ambiente (Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12); os dois jobs de benchmark também passaram.
- Nenhum teste local foi executado neste ciclo. Nenhum teste foi executado em hardware i5/8 GB ou Linux ARM64.

### 2.3 PRs abertas inspecionadas

| PR | Base → head | Estado | CI atual consultada |
|---|---|---|---|
| [#23 Ollama consentido](https://github.com/SANTZSPAXX/NixLMs/pull/23) | main → feature/ollama-setup-consent | open/draft | success |
| [#24 Plano de cache](https://github.com/SANTZSPAXX/NixLMs/pull/24) | main → docs/plan-2026-11-14-episodic-index | open/draft | success |
| [#25 Cache episódico](https://github.com/SANTZSPAXX/NixLMs/pull/25) | main → feature/episodic-retrieval-cache-batching | open/draft | success |
| [#26 QA 14/11](https://github.com/SANTZSPAXX/NixLMs/pull/26) | main → docs/qa-nightly-2026-11-14 | open/draft | success |
| [#27 Plano de paridade](https://github.com/SANTZSPAXX/NixLMs/pull/27) | main → docs/plan-2026-11-15-episodic-cache-validation | open/draft | success |
| [#28 Paridade/cache benchmark](https://github.com/SANTZSPAXX/NixLMs/pull/28) | #25 → test/episodic-cache-parity-benchmark | open/draft | success |
| [#29 Bind loopback Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/29) | #23 → fix/ollama-managed-loopback-bind | open/draft | success |
| [#30 QA 15/11](https://github.com/SANTZSPAXX/NixLMs/pull/30) | main → docs/qa-nightly-2026-11-15 | open/draft | success |
| [#31 Plano cleanup Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/31) | #29 → docs/plan-2026-11-16-ollama-lifecycle-cleanup | open/draft | success |
| [#32 Cleanup Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/32) | #29 → fix/ollama-managed-startup-cleanup | open/draft | success |
| [#33 Roadmap JARVIS](https://github.com/SANTZSPAXX/NixLMs/pull/33) | main → docs/roadmap-jarvis-2026-11-16 | open/draft | success |
| [#34 QA 16/11](https://github.com/SANTZSPAXX/NixLMs/pull/34) | main → docs/qa-nightly-2026-11-16 | open/draft | success |
| [#35 Plano benchmark PT-BR](https://github.com/SANTZSPAXX/NixLMs/pull/35) | main → docs/plan-2026-11-17-ptbr-episodic-retrieval | open/draft | success |
| [#36 Benchmark PT-BR](https://github.com/SANTZSPAXX/NixLMs/pull/36) | #28 → test/episodic-retrieval-ptbr-quality | open/draft | success |
| [#37 Proteção de saída](https://github.com/SANTZSPAXX/NixLMs/pull/37) | #36 → fix/ptbr-benchmark-protect-output-paths | open/draft | success |

### 2.4 Cadeia de dependências relevante

`main → #25 (cache/batching) → #28 (paridade sintética) → #36 (qualidade PT-BR) → #37 (proteção de saída)`

- #25 e #28 continuam fora de `main`; o cache episódico candidato não deve ser descrito como integrado.
- #36 é empilhada sobre #28 e não altera a fórmula de ranking.
- #37 é empilhada sobre #36 e não altera #36.
- #32 é uma correção isolada sobre #29/#23; permanece draft. A CI passou, mas a revisão anterior registra que o cleanup trata o processo filho gerenciado, não a árvore de descendentes.
- A evolução 0.6 (#6), memória episódica 0.7 (#7) e aprendizagem recorrente LIF (#22) já estão merged. A evolução 0.6 não está pendente.

## 3. Auditoria funcional de main

### Memória e representação

- `EpisodicMemory` persiste episódios em JSON, incluindo pergunta, resposta, contexto, resultado, origem, importância, feedback e tags.
- A recuperação atual percorre os episódios, calcula sobreposição lexical Jaccard e, se houver encoder, combina score semântico e lexical; recência, importância e feedback também afetam o score.
- A busca episódica não recebe histórico conversacional separado; o método recebe a consulta textual.
- O backend E5 é opcional, CPU e local-only. Em main, a codificação de passagens é individual; o cache LRU e batching permanecem nas PRs #25/#28.
- Não existe consolidação automática de episódios em fatos semânticos. O `WorldModel` armazena fatos explicitamente, com fonte e confiança; não os extrai nem valida sozinho.
- O encoder nativo é treinável com os dados locais, mas não é um embedding fundacional pré-treinado e não possui semântica geral garantida.

### Planejamento e metacognição

- `GoalManager` registra objetivos, etapas, dependências e próximas etapas liberadas; não executa ações.
- `CognitiveEngine` usa heurísticas simples de saliência e confiança a partir do melhor candidato; não há ciclo de crítica/revisão ou calibração metacognitiva global.
- `AttentionSystem` mantém working memory de capacidade fixa e ranqueia candidatos por sobreposição, associação, foco e prioridade; ainda não é um workspace global integrado.
- `TaskScheduler` usa SQLite/WAL, handlers allowlisted, leases e entrega at-least-once. Handlers precisam ser idempotentes; o banco não desserializa código nem executa shell.
- A documentação de README ainda chama a memória episódica de “0.7 em desenvolvimento”, embora a PR #7 esteja merged; corrigir em tarefa documental separada, sem misturar com esta prioridade.

### Eficiência e plataforma

- CI padrão cobre Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12; não cobre ARM64.
- Não há teste de qualidade semântica de recuperação no CI de main.
- E5 pequeno é uma opção de comparação, não requisito para o i5/8 GB; carregamento deve permanecer explícito e local.
- SQLite FTS5 pode ser um baseline lexical persistente futuro, mas a disponibilidade da extensão deve ser verificada em runtime antes de torná-la requisito.

## 4. Revisão das PRs #36 e #37

### PR #36 — benchmark de recuperação PT-BR

O diff adiciona:
- 50 episódios, 30 consultas e 32 qrels graduados;
- cinco categorias declaradas: paráfrase, coloquialismo, variação ortográfica, contextual e sem resposta;
- métricas nDCG@5, MRR@5, Recall@5, Precision@5, cobertura, abstenção e falso positivo;
- relatório JSON com hash do conjunto;
- modo lexical offline; encoder nativo e E5 apenas quando caminhos locais são fornecidos;
- job de benchmark na CI.

Baseline declarado para o conjunto piloto: nDCG@5 0.829261, MRR@5 0.875000, Recall@5 0.750000, Precision@5 0.183333. São números do corpus sintético v1, não uma medida geral da qualidade da NixLMs nem comparáveis diretamente a leaderboards MTEB-BR/BEIR.

### Bloqueios de validade e privacidade identificados em revisão

1. **Proveniência:** a origem independente de parte dos exemplos não está demonstrada. O rótulo de fonte sintética não é evidência suficiente. Como o repositório é público, tratar os registros questionados como potencialmente derivados de contexto individual até verificar a origem. Não reproduzir nem copiar esses conteúdos para novas documentações ou datasets.
2. **Contexto:** as consultas classificadas como `contextual` não incluem histórico no schema; o avaliador passa somente o texto atual para `EpisodicMemory.recall()`. Portanto, a categoria não mede resolução de anáfora/ elipse com histórico conversacional.
3. **Empates:** os episódios usam timestamps iguais. Quando score e timestamp empatam, a ordenação estável pode preservar a posição original no arquivo. Não há fixture explícita que determine um desempate independente da ordem do corpus.
4. **Identidade do E5:** o relatório registra metadados básicos do diretório/modelo, mas não uma revisão imutável ou fingerprint dos pesos que permita distinguir dois diretórios com o mesmo nome/dimensão e conteúdo diferente.
5. **Qrels:** julgamentos são editoriais e ainda não possuem revisão independente documentada.

**Decisão de segurança:** não tratar #36 como benchmark de referência nem integrar a cadeia enquanto proveniência e validade contextual não forem resolvidas. Nenhuma PR foi editada ou aprovada nesta auditoria.

### PR #37 — proteção de saída

- Adiciona bloqueio para o arquivo de memória episódica de produção e para os três arquivos do dataset padrão/customizado.
- Resolve caminhos para cobrir aliases relativos e symlinks existentes.
- Rejeita `min-score` NaN e infinitos na API e no CLI.
- Os testes de regressão passaram no CI observado.

Limite residual: a proteção compara uma lista de caminhos específicos; não é uma allowlist geral de diretórios persistentes do projeto. Um destino diferente dentro de `data/` ainda não é recusado apenas por estar nesse diretório. A implementação da tarde deve restringir o destino a uma área de relatórios ou bloquear diretórios persistentes por política explícita.

## 5. Pesquisa técnica e comparação

### MTEB-BR — avaliação nativa em português

- Site: https://mteb-br.org/
- Código original: https://github.com/tardellirs/mteb-br
- Paper: https://arxiv.org/abs/2607.04581
- O benchmark apresenta 22 tarefas nativas de PT-BR em sete categorias e compara 93 modelos. A metodologia reforça que resultados multilíngues não substituem avaliação em dados nativos de português.
- Uso recomendado: referência metodológica e fonte de tarefas licenciadas quando apropriado; não importar o benchmark completo como dependência do núcleo.

### BEIR — protocolo de recuperação

- Paper: https://arxiv.org/abs/2104.08663
- Código: https://github.com/beir-cellar/beir
- O formato corpus/queries/qrels e as métricas de ranking são referências úteis. A NixLMs pode manter um avaliador pequeno em biblioteca padrão sem adicionar a dependência BEIR ao runtime.

### QReCC — recuperação conversacional

- Pesquisa Apple: https://machinelearning.apple.com/research/open-domain-question-answering-goes-conversational
- Repositório/dataset: https://github.com/apple-aiml-research/ml-qrecc
- QReCC separa histórico, pergunta atual, reescrita contextual e recuperação. O conjunto é em inglês e tem escala/licença próprias; usar apenas o schema/metodologia como referência, não copiar dados para o benchmark PT-BR sem avaliação de licença e adequação.

### SQLite FTS5 — baseline lexical CPU/local

- Documentação oficial: https://www.sqlite.org/fts5.html
- FTS5 fornece busca full-text e função BM25 dentro do SQLite. É uma alternativa leve para comparar com o Jaccard atual e evita manter índice lexical integral em memória.
- Antes de adotá-la, verificar se a biblioteca SQLite do Python alvo foi compilada com FTS5 em Windows e Linux ARM64. Não torná-la requisito sem teste de disponibilidade.

### multilingual-e5-small — opção semântica

- Model card: https://huggingface.co/intfloat/multilingual-e5-small
- Configuração consultada: 12 camadas, dimensão 384; o modelo tem aproximadamente 118M parâmetros e licença MIT no repositório do modelo.
- Mantê-lo opcional, local-only, CPU e com revisão/fingerprint de modelo no relatório. A escolha do encoder deve ser baseada no benchmark PT-BR, não apenas no ranking multilíngue.

## 6. Plano concreto para o ciclo da tarde

### Problema

O benchmark v1 não pode orientar mudanças de ranking com segurança enquanto a proveniência do corpus, a semântica da categoria contextual e a ordem dos empates não forem confiáveis.

### Hipótese

Um corpus independente, com rubrica e proveniência verificáveis, categorias que correspondam exatamente aos dados fornecidos ao avaliador e ordenação determinística permitirá medir recuperação episódica sem risco de publicar contexto individual nem confundir recuperação lexical com resolução conversacional.

### Escopo único

**Remediação do benchmark PT-BR v2; não implementar consolidação, planner, voz/visão ou novo algoritmo de embedding nesta tarefa.**

1. Recriar os exemplos cuja proveniência não possa ser demonstrada com conteúdo ficcional independente, sem copiar conversas, arquivos ou dados pessoais.
2. Adicionar manifesto de proveniência: versão, método de autoria, licença, data, rubrica de anotação e declaração de independência de contexto individual.
3. Renomear a categoria atual para algo equivalente a `consulta_eliptica_sem_historico`, porque o avaliador recebe apenas a consulta textual. Uma avaliação contextual real fica para uma fase posterior com `history` explícito, consulta atual e consulta reescrita.
4. Revisar qrels com rubrica explícita e segunda revisão humana dos casos ambíguos; não usar o próprio modelo avaliado como único juiz.
5. Definir desempate determinístico: score descendente, timestamp descendente e ID estável ascendente. Adicionar teste com permutações da ordem de entrada. Se isso exigir mudança em `EpisodicMemory`, manter a alteração mínima e preservar o score.
6. Restringir `--output` a uma área de relatório explícita ou recusar qualquer destino sob diretórios persistentes (`data/` e dataset de entrada); testar caminho relativo, absoluto, symlink existente e destino separado.
7. No modo E5 opcional, registrar revisão ou fingerprint verificável do manifesto de arquivos do modelo sem caminho absoluto e sem copiar pesos. Se não houver metadado suficiente, registrar `identity_unverified` e não comparar como se fosse o mesmo modelo.

### Arquivos prováveis

- `datasets/episodic_retrieval_ptbr/episodes.jsonl`
- `datasets/episodic_retrieval_ptbr/queries.jsonl`
- `datasets/episodic_retrieval_ptbr/qrels.tsv`
- `datasets/episodic_retrieval_ptbr/README.md`
- `datasets/episodic_retrieval_ptbr/provenance.json` (novo)
- `benchmarks/episodic_retrieval_quality_ptbr.py`
- `tests/test_episodic_retrieval_quality.py`
- `nixlms_core/episodic.py` (somente se necessário para desempate estável)
- `CHANGELOG.md`

Não modificar `main`, #35, #36 ou #37. Não copiar exemplos questionados para documentação, comentários ou novo dataset.

### Critérios de aceitação

1. Todos os registros novos têm proveniência independente documentada e nenhum conteúdo deriva de conversas ou dados pessoais do operador.
2. O schema e os nomes das categorias não afirmam testar histórico contextual quando o histórico não é fornecido.
3. Qrels válidos, sem referências ausentes/duplicadas; rubrica e revisão humana documentadas.
4. Ranking de empates permanece idêntico quando a ordem de entrada é permutada, salvo diferenças explicitamente documentadas.
5. O CLI não consegue sobrescrever memória, pesos, scheduler, modelo de mundo, objetivos ou arquivos do dataset.
6. O JSON de saída inclui hash do dataset, versão do benchmark, parâmetros, métricas por split/categoria e identidade verificável do encoder, sem texto de episódios/consultas, caminhos absolutos ou dados pessoais.
7. CI lexical permanece offline, sem dependências extras ou downloads: matriz Windows/Ubuntu existente e jobs de benchmark.
8. Nenhuma alteração de pesos, formato persistido da memória, treinamento ou fórmula de score, exceto o desempate determinístico documentado.
9. E5/checkpoint nativo continuam opcionais e somente locais; nenhum teste padrão carrega modelo pesado.

### Testes obrigatórios

- Validação do manifesto, schema, IDs, qrels e splits.
- Testes das métricas nDCG, MRR, Recall, Precision e abstenção com fixtures de valores esperados.
- Teste de empate com corpus em ordem original e permutada.
- Testes de proveniência estrutural e revisão manual documentada.
- Testes de saída para memória, pesos, scheduler, world model, dataset, symlink e diretório de relatório.
- Teste de não mutação da memória episódica e dos arquivos do dataset.
- Execução da suíte via `python -m unittest discover -s tests -v` em Windows e Ubuntu pela CI.
- Nenhum teste deve acessar rede, instalar modelo ou ler memória pessoal real.

### Riscos e rollback

- Os resultados v2 não serão comparáveis diretamente ao baseline v1; registrar nova versão e novo hash.
- Qrels continuam sujeitos a julgamento humano; preservar casos ambíguos e decisões de adjudicação.
- A categoria contextual verdadeira ficará fora do escopo até existir contrato de contexto no runtime.
- E5 pode consumir RAM/CPU adicional; permanecerá opcional.
- Rollback: reverter apenas os arquivos novos/alterados do benchmark e a mudança pontual de desempate; sem migração de banco, sem alteração do JSON de memória e sem tocar nas PRs existentes.

### Base da implementação da tarde

- Base de desenvolvimento: branch `fix/ptbr-benchmark-protect-output-paths`.
- HEAD observado: `7c45b8d0ae2c590bc19b4124f52423174fd844df`.
- Nova branch sugerida: `test/ptbr-benchmark-integrity-v2`.
- PR draft da implementação deverá usar `fix/ptbr-benchmark-protect-output-paths` como base, explicitando a dependência #36 → #37.
- Não editar nem retargetear #35, #36 ou #37.

## 7. Lacunas seguintes — não são prioridade desta tarde

1. Context-aware retrieval real, com histórico explícito e reescrita de consulta.
2. Consolidação episódica para candidatos semânticos com proveniência, revisão e rollback.
3. Avaliação PT-BR maior e mais diversa, com dados públicos licenciados e anotação humana.
4. Representação semântica leve, comparando Jaccard, SQLite FTS5 e E5-small local.
5. Planejamento hierárquico e ciclo de crítica/verificação.
6. Metacognição calibrada, com abstenção e estimativa de incerteza mensuradas.
7. Profiling real no i5/8 GB e em Linux ARM64.

## 8. Referências

- MTEB-BR: https://mteb-br.org/
- MTEB-BR code: https://github.com/tardellirs/mteb-br
- MTEB-BR paper: https://arxiv.org/abs/2607.04581
- BEIR paper: https://arxiv.org/abs/2104.08663
- QReCC research: https://machinelearning.apple.com/research/open-domain-question-answering-goes-conversational
- QReCC repository: https://github.com/apple-aiml-research/ml-qrecc
- SQLite FTS5: https://www.sqlite.org/fts5.html
- multilingual-e5-small: https://huggingface.co/intfloat/multilingual-e5-small

## 9. Integridade deste ciclo

- Somente este documento será adicionado na branch documental.
- Nenhum código de produção foi modificado.
- Nenhum teste local foi executado.
- Nenhum modelo foi baixado ou executado.
- Nenhuma PR existente foi modificada.
- Nenhum merge, release, deploy, force-push, exclusão ou alteração de configuração foi realizado.
