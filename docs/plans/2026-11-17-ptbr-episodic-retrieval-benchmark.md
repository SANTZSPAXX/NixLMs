# Ciclo matinal — NixLMs — 2026-11-17
## Plano de avaliação da recuperação episódica em português brasileiro

**Objetivo do ciclo:** auditar o estado remoto e preparar uma única tarefa verificável para o ciclo da tarde.  
**Produto:** NixLMs, assistente funcional inspirado no JARVIS; autonomia alta sob permissões; execução local e remota opcional.  
**Base documental:** `main` em `135f480addc43dd270ea7a08b97da6496b651445`.  
**Branch deste plano:** `docs/plan-2026-11-17-ptbr-episodic-retrieval`.

## 1. Resumo executivo

**Prioridade única para a tarde:** criar um benchmark pequeno, reproduzível e nativo de português brasileiro para medir a qualidade da recuperação da memória episódica.

A prioridade não é adicionar outro algoritmo de memória nem otimizar novamente o cache. A NixLMs já tem recuperação episódica e há uma implementação de cache/batching em PRs abertas. A lacuna mais importante é a falta de um conjunto de consultas e julgamentos de relevância que prove se a lembrança correta é recuperada para paráfrases, linguagem coloquial, variações ortográficas e consultas sem resposta.

O benchmark será uma mudança de avaliação/dados, sem alterar o comportamento de produção de `EpisodicMemory.recall()`. Deve rodar offline com a biblioteca padrão; E5 e checkpoints nativos serão opcionais e somente locais.

## 2. Estado remoto observado

### Repositório e branches

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`.
- HEAD mais recente consultado: `135f480addc43dd270ea7a08b97da6496b651445` (commit de 2026-11-14).
- 35 branches retornadas; nenhuma foi removida ou alterada.
- 12 PRs abertas, todas em draft e não merged no momento da consulta.
- Nenhuma issue aberta foi retornada pela busca.
- O endpoint de proteção de `main` respondeu HTTP 403 para a integração; portanto, não foi possível confirmar a configuração de branch protection. Nenhuma configuração foi alterada.

### PRs abertas

| PR | Base → head | Estado/CI observado | Observação |
|---|---|---|---|
| [#23 — setup Ollama com consentimento](https://github.com/SANTZSPAXX/NixLMs/pull/23) | main → `feature/ollama-setup-consent` | open/draft; run #43579532053 success | Comentários de revisão sobre escopo do consentimento Linux e instalador remoto sem versão/checksum fixos permanecem relevantes |
| [#24 — plano de índice episódico](https://github.com/SANTZSPAXX/NixLMs/pull/24) | main → `docs/plan-2026-11-14-episodic-index` | open/draft; run #43596339567 success | Plano histórico |
| [#25 — cache LRU e batching episódico](https://github.com/SANTZSPAXX/NixLMs/pull/25) | main → `feature/episodic-retrieval-cache-batching` | open/draft; run #43625546189 success | Cache limitado, float32, fingerprint e batching; não altera a fórmula de ranking |
| [#26 — QA de 14/11](https://github.com/SANTZSPAXX/NixLMs/pull/26) | main → `docs/qa-nightly-2026-11-14` | open/draft; run #43659204826 success | Registro histórico |
| [#27 — plano de paridade do cache](https://github.com/SANTZSPAXX/NixLMs/pull/27) | main → `docs/plan-2026-11-15-episodic-cache-validation` | open/draft; run #43713229771 success | Plano histórico exercitado pela #28 |
| [#28 — paridade e benchmark cache](https://github.com/SANTZSPAXX/NixLMs/pull/28) | PR #25 → `test/episodic-cache-parity-benchmark` | open/draft; run #43749733054 success, 5/5 jobs | Inclui testes de equivalência e benchmark sintético |
| [#29 — bind loopback Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/29) | PR #23 → `fix/ollama-managed-loopback-bind` | open/draft; run #43783387426 success | Serviços preexistentes continuam com bind não verificado |
| [#30 — QA de 15/11](https://github.com/SANTZSPAXX/NixLMs/pull/30) | main → `docs/qa-nightly-2026-11-15` | open/draft; run #43783796015 success | Registro histórico |
| [#31 — plano de cleanup Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/31) | PR #29 → `docs/plan-2026-11-16-ollama-lifecycle-cleanup` | open/draft; run #43870773835 success | Plano concluído pela #32 |
| [#32 — cleanup de processo Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/32) | PR #29 → `fix/ollama-managed-startup-cleanup` | open/draft; run #43986968091 success, 4/4 jobs | Inclui cleanup em timeout e Ctrl+C; revisão registra risco potencial de concorrência em `start_service()` |
| [#33 — roadmap JARVIS](https://github.com/SANTZSPAXX/NixLMs/pull/33) | main → `docs/roadmap-jarvis-2026-11-16` | open/draft; run #43947443104 success, 4/4 jobs | Plano arquitetural geral |
| [#34 — QA noturno de 16/11](https://github.com/SANTZSPAXX/NixLMs/pull/34) | main → `docs/qa-nightly-2026-11-16` | open/draft; run #43987309031 success, 4/4 jobs | Registra a revisão da #32 e riscos residuais |

Todos os HEADs das 12 PRs tiveram uma execução de workflow associada retornando `completed/success`. Isso não equivale a validação em hardware real. A execução de `main` no SHA atual, run [#43576200437](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43576200437), também concluiu 4/4 jobs com sucesso (Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12).

### Evoluções integradas

- [PR #6 — Scheduler 0.6](https://github.com/SANTZSPAXX/NixLMs/pull/6): merged em 2026-11-14.
- [PR #7 — memória episódica 0.7](https://github.com/SANTZSPAXX/NixLMs/pull/7): merged em 2026-11-14.
- [PR #22 — aprendizagem recorrente LIF](https://github.com/SANTZSPAXX/NixLMs/pull/22): merged em 2026-11-14.
- Portanto, a evolução 0.6 não está pendente.

## 3. Auditoria funcional de main

Arquivos consultados em `main`: `nixlms_core/agent.py`, `episodic.py`, `encoding.py`, `pretrained_encoder.py`, `memory.py`, `attention.py`, `cognition.py`, `planning.py`, `scheduler.py`, `world_model.py`, `language.py`, `learning.py`, README, CHANGELOG, workflow e testes.

### O que já existe

- `NixLMsNeuralCore.respond()` integra LIF, recuperação semântica, atenção, episódios, mapa mental, fatos, objetivos, decoder neural e Ollama local opcional.
- Memória episódica persistente em JSON com contexto, resultado, origem, importância, tags, timestamp e feedback positivo/negativo.
- Encoder nativo treinável com palavras, bigramas e subwords de caracteres, atualizado por pares contrastivos.
- Backend opcional `TransformersSentenceEncoder`, CPU-only e local-only; E5 recebe prefixos `query:` e `passage:`.
- Modelo de mundo com fatos tipados, confiança e proveniência; conflitos são expostos, não resolvidos automaticamente.
- `GoalManager` registra objetivos, etapas e dependências; o agendador SQLite executa somente handlers registrados.
- Avaliação atual cobre QA, pares contrastivos, representações LIF e fluxo de resposta, com separação train/validation/test e exclusão de consultas de teste durante a avaliação cognitiva.

### Lacunas de maior impacto

1. **Recuperação episódica — qualidade ainda sem benchmark dedicado.** `EpisodicMemory.recall()` percorre todos os episódios, calcula Jaccard lexical e, quando há encoder, codifica cada passagem durante a consulta. Aplica recência, importância e feedback, mas não há qrels PT-BR que meçam a posição dos episódios relevantes.
2. **Consolidação — ausente.** O código registra episódios e feedback, mas não converte experiências em memória semântica com proveniência, revisão e política de esquecimento. O README declara essa limitação.
3. **Representação semântica — dependente de dados.** O encoder nativo não é pré-treinado e não tem semântica geral garantida. O E5 é opcional e não pode ser presumido como melhor em português brasileiro sem avaliação nativa.
4. **Avaliação PT-BR — pequena e voltada a QA.** `datasets/starter_ptbr.jsonl` é um conjunto inicial de smoke tests, não um corpus de recuperação episódica com consultas, episódios candidatos e julgamentos de relevância. Os testes episódicos atuais verificam persistência, recuperação lexical básica e feedback, não qualidade de ranking em paráfrases.
5. **Planejamento — registro, não agente executor.** `GoalManager` mantém dependências e próximas etapas, mas não decompõe objetivos nem executa ações.
6. **Metacognição — heurística limitada.** `CognitiveEngine` calcula saliência e confiança a partir do melhor candidato; não há ciclo de crítica, revisão de hipótese, calibração global ou avaliação autônoma de plano.
7. **Eficiência — parcialmente tratada em PR.** O cache LRU e batching da #25 reduzem re-encoding, mas permanecem em PR aberta. A #28 valida paridade e custo com encoder sintético, não a qualidade semântica do E5 nem desempenho no i5/8 GB.
8. **Multimodalidade e execução híbrida — ainda não integradas em main.** README declara que visão e audição não fazem parte do runtime. `LanguageEngine` aceita somente Ollama em loopback; não há backend remoto genérico no núcleo auditado.

### Testes e documentação

- CI de main usa `python -m unittest discover -s tests -v`, matriz Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12.
- Diretório `tests/` contém testes para núcleo, linguagem, encoder, decoder, memória episódica, aprendizagem e scheduler.
- Não há teste específico de nDCG/MRR/Recall para recuperação episódica PT-BR.
- Pequena divergência documental: o README chama a memória episódica de “0.7 em desenvolvimento”, embora a PR #7 esteja merged.
- Nenhum teste local foi executado neste ciclo; os estados positivos citados são exclusivamente GitHub Actions.

## 4. Revisão específica das PRs de memória

### PR #25 — cache e batching

A implementação usa cache LRU volátil, fingerprints de encoder/conteúdo, vetores float32, batches limitados e métricas. Mantém a fórmula de ranking e o JSON de episódios. A CI #43625546189 passou 4/4 jobs.

A revisão COMMENT da #25 apontou três pontos: necessidade de comparação direta cache-off/cache-on; benchmark completo e E5 real ainda não executados; risco potencial de concorrência em `recall()/record()/prune()` sem lock. A #28 resolveu a primeira lacuna e adicionou benchmark sintético, mas não fecha thread-safety.

### PR #28 — paridade e benchmark sintético

A CI #43749733054 passou 5/5 jobs: quatro matrizes de testes e um job de benchmark. O comentário de revisão registrou 163 testes por ambiente, paridade de IDs/ordem e diferença máxima de score de `1e-8` no artefato, abaixo da tolerância `1e-5`. Warm teve zero re-encoding adicional; as medianas sintéticas warm foram menores que cache-off nos três tamanhos medidos.

**Interpretação correta:** isso demonstra paridade do cache e comportamento do encoder sintético. Não demonstra que a memória recupera o episódio semanticamente correto em PT-BR, não mede E5 real, não mede o hardware i5/8 GB e não valida Linux ARM64.

As PRs #25 e #28 não foram alteradas. A tarefa proposta será empilhada sobre a #28 para reutilizar a implementação candidata sem modificar a cadeia existente.

## 5. Pesquisa técnica — fontes primárias

### Benchmark nativo em português brasileiro

- **MTEB-BR**, paper: https://arxiv.org/abs/2607.04581
- Repositório original: https://github.com/tardellirs/mteb-br
- O benchmark reúne tarefas nativas de português brasileiro, sem corpora traduzidos, e inclui seis tarefas de retrieval. O paper reporta que a posição em leaderboard multilíngue prediz apenas moderadamente a posição em português (Spearman ρ=0,75 em modelos compartilhados). Isso justifica não assumir que um embedding multilíngue tem qualidade suficiente em PT-BR sem medição local.

### Protocolo e métricas de recuperação

- **BEIR**, paper: https://arxiv.org/abs/2104.08663
- Repositório: https://github.com/beir-cellar/beir
- O formato separa corpus, queries e relevance judgments (qrels). O paper discute nDCG@k para relevância graduada e métricas como MRR, Recall e Precision. Também mostra que BM25 é um baseline lexical robusto e que métodos densos/reranking podem ter custo computacional maior.
- Para esta entrega, usar métricas de ranking e qrels inspirados no formato BEIR, mas sem adicionar a dependência BEIR ao núcleo.

### Embeddings multilíngues opcionais

- **multilingual-e5-small**, model card oficial: https://huggingface.co/intfloat/multilingual-e5-small
- O card documenta 12 camadas, dimensão 384, suporte declarado a 100 idiomas e uso obrigatório de prefixos `query:` e `passage:` para retrieval. O modelo é opção de comparação, não requisito. O backend existente já limita o carregamento a CPU e arquivos locais.
- **MTEB**, paper original: https://arxiv.org/abs/2210.07316
- MTEB mostra que modelos de embedding variam por tarefa; não há um modelo universalmente melhor em todos os cenários.

## 6. Plano concreto para o ciclo da tarde — uma prioridade

### Problema

Não há evidência mensurável de que a memória episódica encontre o episódio certo quando a consulta não repete as palavras originais. As otimizações de cache em #25/#28 medem reuso e paridade, não relevância semântica.

### Hipótese

Um conjunto fixo de consultas e episódios PT-BR com julgamentos manuais graduados permitirá comparar o ranking lexical atual com embeddings nativos já treinados e E5 local opcional, detectando regressões sem depender de modelos remotos. A ativação/desativação do cache não deve alterar a relevância nem a ordem dos resultados.

### Escopo proposto

**Somente benchmark, dados e testes; sem alteração em código de produção ou na fórmula de ranking.**

Arquivos prováveis:
- `datasets/episodic_retrieval_ptbr/episodes.jsonl` — corpus de episódios fictícios/anonimizados, IDs estáveis e metadados mínimos.
- `datasets/episodic_retrieval_ptbr/queries.jsonl` — consultas PT-BR, categoria e split.
- `datasets/episodic_retrieval_ptbr/qrels.tsv` — `query_id`, `episode_id`, relevância graduada 1–2; ausência de linha significa não relevante.
- `benchmarks/episodic_retrieval_quality_ptbr.py` — avaliador determinístico com biblioteca padrão.
- `tests/test_episodic_retrieval_quality.py` — validação de dados, métricas e integração.
- Atualizar README/CHANGELOG apenas para documentar o benchmark e os limites.

Tamanho inicial sugerido: pelo menos 50 episódios e 30 consultas, com exemplos de paráfrase, coloquialismo, abreviações, acentos/typos, referência contextual e consultas sem episódio correspondente. Julgamentos devem ser revisados manualmente; não gerar qrels com o próprio modelo avaliado.

### Modos de avaliação

1. **Lexical:** `EpisodicMemory.recall(query, encoder=None)`, referência do comportamento atual.
2. **Encoder nativo:** somente quando houver checkpoint explícito e compatível, sem treinar no split de teste.
3. **E5 opcional:** somente caminho local informado pelo operador; `local_files_only=True`; sem download, rede ou requisito no CI.

O benchmark deve usar cópia temporária do corpus e nunca ler/escrever a memória pessoal do operador. O CI executará somente o modo lexical e fixtures determinísticas; E5 fica fora da CI padrão.

### Métricas

- nDCG@5 para relevância graduada.
- MRR@5 para a posição do primeiro episódio relevante.
- Recall@5 e Precision@5.
- Taxa de falso positivo/abstenção em consultas sem episódio correspondente.
- Relatório por tipo de consulta e macro média; não ocultar categorias com baixa amostra.

### Critérios de aceitação

1. IDs únicos, qrels válidos e todas as referências existentes; splits sem duplicação exata de consultas.
2. Métricas conferidas por fixtures pequenas com valores esperados conhecidos.
3. Resultados determinísticos para o mesmo dataset/encoder.
4. CI Windows e Ubuntu sem dependências adicionais.
5. Modo lexical funciona offline; E5 só é carregado se o caminho local existir e for explicitamente informado.
6. JSON de saída registra hash do dataset, modo/identidade do encoder, parâmetros e métricas; não grava conteúdo privado nem caminho absoluto de diretório pessoal.
7. Nenhuma alteração de produção, formato persistido, pesos ou memória do usuário.
8. Não estabelecer limiar de qualidade arbitrário antes do primeiro baseline; publicar os valores medidos e definir gates de regressão em ciclo posterior.

### Testes

- Unitários para nDCG, MRR, Recall, Precision, qrels, consulta sem resultado e empates.
- Integração com `EpisodicMemory` em diretório temporário.
- Teste de não mutação do arquivo de episódios durante avaliação.
- Teste de exclusão/abstenção para consultas sem relevância.
- Execução via `python -m unittest discover -s tests -v` na matriz Windows/Ubuntu existente.
- Nenhum teste deve baixar modelo, acessar rede ou usar dados pessoais.

### Branch, base e PR

A implementação da tarde deverá:
- criar branch própria `test/episodic-retrieval-ptbr-quality` a partir do HEAD da branch `test/episodic-cache-parity-benchmark` (`d536a69319e3775d127e86e997d0576eb02175e4`);
- abrir PR draft tendo `test/episodic-cache-parity-benchmark` como base, explicitando dependência da cadeia #25 → #28;
- não alterar PR #25 ou #28;
- revisar o diff completo, executar CI real e aguardar os resultados;
- não fazer merge automático.

### Riscos e rollback

- O conjunto inicial é um benchmark piloto, não uma avaliação completa de todos os domínios do português.
- Julgamentos humanos podem ser subjetivos; registrar a rubrica e revisar os casos ambíguos.
- Vazamento entre consultas e episódios pode inflar resultados; validar duplicatas e paráfrases entre splits.
- E5 pode consumir RAM adicional por causa do runtime PyTorch; por isso é opcional e fora da CI padrão.
- Checkpoint nativo ausente/incompatível deve resultar em modo ignorado com diagnóstico claro, nunca em download.
- Rollback: reverter somente o commit do benchmark ou fechar a PR nova; nenhuma migração ou arquivo de memória de usuário será tocado.

## 7. Backlog observado, não selecionado neste ciclo

- Consolidação episódica para semântica com proveniência, confiança, revisão e retenção.
- Workspace global e ciclo observe–plan–act–verify completo.
- Planejamento hierárquico e metacognição verificável.
- Thread-safety de cache episódico e de `OllamaManager.start_service()`.
- Revisão do consentimento Linux e integridade do instalador Ollama.
- Voz, visão, backend remoto opcional, sincronização e portabilidade ARM64.
- Profiling real de CPU/RAM/latência no hardware i5/8 GB.

Esses itens permanecem fora do escopo do incremento da tarde para evitar misturar várias mudanças e impedir uma avaliação clara.

## 8. Limites deste ciclo

- Nenhum código de produção foi modificado.
- Nenhuma PR existente foi editada, aprovada ou mesclada.
- Nenhum teste local foi executado.
- Nenhum modelo foi baixado ou carregado.
- Nenhum Ollama real, câmera, microfone, serviço remoto ou dispositivo foi utilizado.
- Não foi declarado suporte ARM64 validado, consciência, senciência ou AGI.

## 9. Decisão

**A única tarefa recomendada para a tarde é o benchmark de qualidade da recuperação episódica em PT-BR**, empilhado sobre a PR #28. Ele fecha uma lacuna de evidência anterior à consolidação de memória e permite que futuras alterações de encoder, ranking e cache sejam avaliadas por qualidade, não apenas por latência sintética.
