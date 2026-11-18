# Plano matinal — 2026-11-15: validação da recuperação episódica

## Objetivo e decisão

Auditar o estado remoto da NixLMs em 2026-11-15 e selecionar uma única tarefa para o ciclo da tarde.

**Prioridade selecionada:** fechar a lacuna de equivalência e benchmark da otimização de recuperação episódica implementada na PR #25, por meio de testes de referência cache-off/cache-on e benchmark comparativo. Esta é uma tarefa de validação/hardening da implementação pendente, não uma nova arquitetura de memória.

Nenhum código de produção foi alterado neste ciclo.

## Estado remoto auditado

- Repositório: https://github.com/SANTZSPAXX/NixLMs
- Branch padrão: `main`
- HEAD de `main`: `135f480addc43dd270ea7a08b97da6496b651445`
- Comparação `135f480...main`: idêntica; `main` não avançou durante a auditoria.
- `main` contém a memória episódica 0.7, agendador 0.6, benchmark cognitivo, decoder autoregressivo e treinamento recorrente LIF.
- A otimização de cache/batching ainda **não está em main**: permanece somente na branch da PR #25, 3 commits à frente e 0 atrás de main.

### PRs abertas inspecionadas

| PR | Estado | Base/HEAD | Observação |
|---|---|---|---|
| [#23 — Ollama consentido](https://github.com/SANTZSPAXX/NixLMs/pull/23) | open, draft | main / `63b34cbd` | 20 commits, 9 arquivos; review de segurança pendente sobre `OLLAMA_HOST` herdado |
| [#24 — plano de cache](https://github.com/SANTZSPAXX/NixLMs/pull/24) | open, draft | main / `7d6d9ed0` | Documento de 2026-11-14; não foi alterado |
| [#25 — cache LRU e batching](https://github.com/SANTZSPAXX/NixLMs/pull/25) | open, draft | main / `1fb2126a` | 3 commits, 6 arquivos; review COMMENT com lacunas de equivalência, benchmark e concorrência |
| [#26 — QA noturno](https://github.com/SANTZSPAXX/NixLMs/pull/26) | open, draft | main / `9486ae0d` | Documento de auditoria noturna de 2026-11-14 |

PR #6 (agendador 0.6), #7 (memória episódica 0.7) e #22 (treinamento recorrente LIF) foram confirmadas como merged. A PR #6 não está pendente. Não foram encontradas issues abertas no repositório.

Branches de implementação/documentação relevantes inspecionadas: `main`, `feature/episodic-retrieval-cache-batching`, `feature/ollama-setup-consent`, `docs/plan-2026-11-14-episodic-index` e `docs/qa-nightly-2026-11-14`. Nenhuma branch ou PR existente foi modificada.

## CI e testes — evidência real

| Referência | Run | Resultado |
|---|---:|---|
| main | [43579135998](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579135998) | 4/4 jobs success; 148 testes por job |
| PR #23 | [43579532053](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579532053) | 4/4 success; 157 testes por job |
| PR #24 | [43596339567](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43596339567) | 4/4 success |
| PR #25 | [43625546189](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43625546189) | 4/4 success; 161 testes por job |
| PR #26 | [43659204826](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43659204826) | 4/4 success; 148 testes por job |

Matriz observada: Ubuntu/Python 3.10, 3.11 e 3.12; Windows/Python 3.12. Os logs consultados registram a conclusão da suíte em cada job.

**Execução local neste ciclo:** nenhum teste ou benchmark local foi executado. A evidência positiva deste documento é exclusivamente do GitHub Actions. Não houve profiling no PC i5/8 GB nem em Linux ARM64.

## Lacunas cognitivas e operacionais

1. **Memória episódica/consolidação:** episódios persistentes e recuperáveis existem, mas não há consolidação abstrativa. A poda mantém os itens mais recentes; não produz resumos com proveniência nem transforma experiências em fatos verificados.
2. **Representação semântica:** o encoder nativo é treinável e usa palavras, bigramas e subwords; a generalização continua limitada pela cobertura dos pares locais. E5 é opcional, CPU e local-only.
3. **Avaliação PT-BR:** `datasets/starter_ptbr.jsonl` tem 26 linhas: QA 9 train / 7 validation / 4 test e pares 4 train / 0 validation / 2 test. É insuficiente para estimativas robustas de qualidade.
4. **Planejamento:** Goal Manager persiste objetivos, etapas e dependências, mas não faz decomposição hierárquica, estima custo/risco nem executa replanning orientado por resultado.
5. **Metacognição:** há calibração por módulo e traces; ainda falta uma estimativa global de incerteza que integre recuperação, fatos, episódios, decoder e abstenção.
6. **Eficiência:** a PR #25 introduz cache e batching, mas continua pendente e ainda não demonstra equivalência direta com cache desabilitado nem ganho líquido de latência. O cache é limitado por quantidade, não por orçamento explícito em bytes; o overhead real depende da dimensão do encoder.

Dívida documental identificada em README.md: a memória 0.7 ainda aparece como “em desenvolvimento” embora a PR #7 esteja merged; há descrição antiga/contraditória sobre treinamento recorrente LIF em relação à PR #22. Não misturar essa atualização documental com a prioridade selecionada.

## Pesquisa e comparação de alternativas

### Cache/índice de recuperação

- **Recalcular todas as passagens em toda consulta:** simples, sem estado auxiliar; custo de inferência cresce com o número de episódios.
- **Codificar todas as passagens em lote a cada consulta:** aproveita o processamento em lote, mas ainda repete o trabalho em cada turno.
- **Persistir embeddings em SQLite:** pode sobreviver a reinícios, mas introduz esquema, migração, invalidação persistente e risco de cache obsoleto; não é necessário para validar a primeira otimização.
- **Cache LRU volátil + batching de misses:** preserva JSON como fonte de verdade, evita migração e reduz recodificações. É a alternativa já implementada na PR #25; agora precisa de evidência comparativa antes de ser promovida.

A documentação oficial do Sentence Transformers informa que `encode()` aceita coleções e `batch_size`; o tamanho ideal depende de hardware, modelo e comprimento do texto e deve ser medido. Fonte: https://www.sbert.net/docs/package_reference/sentence_transformer/model.html

O model card de `intfloat/multilingual-e5-small` registra 384 dimensões, suporte multilíngue (94 idiomas), licença MIT e os prefixos `query:`/`passage:`. A implementação deve manter o backend opcional e local-only: https://huggingface.co/intfloat/multilingual-e5-small

### Memória e avaliação

- LongMemEval organiza avaliação de memória em extração, raciocínio entre sessões, temporalidade, atualização e abstenção; são 500 perguntas em históricos longos, em inglês. Usar a taxonomia como referência, não assumir que seja benchmark PT-BR pronto: https://arxiv.org/abs/2410.10813
- ASSIN 2 oferece 6.500 pares de treino, 500 de validação e 2.448 de teste em português brasileiro, mas o cartão atual do dataset informa licença desconhecida. Não copiar nem redistribuir dados no repositório até esclarecer os termos: https://huggingface.co/datasets/nilc-nlp/assin2
- Generative Agents é referência para reflexões hierárquicas sobre experiências, mas a síntese generativa exige um leitor/LLM e pode produzir inferências não sustentadas. Uma futura consolidação deve preservar episódios-fonte, proveniência e distinção entre resumo, hipótese e fato: https://arxiv.org/abs/2304.03442

## Tarefa única para o ciclo da tarde

### Título

**Episodic cache — equivalência sem cache e benchmark comparativo**

### Problema

Os testes atuais da PR #25 comparam recuperação fria e aquecida dentro da nova implementação. Isso verifica reutilização e estabilidade cold/warm, mas não compara diretamente o ranking e os scores com o caminho sem cache. O benchmark atual mede cold/warm com cache habilitado e smoke test de 10 episódios na CI; não quantifica o ganho líquido contra recomputação nem executa o cenário completo 100/500/2.000.

### Hipótese

Com o mesmo conjunto de episódios e encoder determinístico, `embedding_cache_size=0` e cache habilitado devem produzir os mesmos IDs/ordem e scores dentro de tolerância compatível com a conversão para float32. Se a recuperação aquecida eliminar recodificação, o benchmark deve mostrar o efeito líquido depois do custo de fingerprint, hashing e preparação dos episódios.

### Base e isolamento

A PR #25 está aberta e em draft. Se o HEAD permanecer `1fb2126aca8cbbad8a874f09ad15b4ecfadd04da`, criar a branch exclusiva de validação a partir desse SHA (ou do HEAD atualizado da branch `feature/episodic-retrieval-cache-batching`) e abrir PR draft **com base nessa branch**, formando uma PR empilhada. Não editar, adicionar commits ou alterar metadados da PR #25. Se a PR #25 mudar de estado antes do ciclo da tarde, revalidar a base e redesenhar a relação das branches antes de criar qualquer branch.

### Arquivos prováveis

- `tests/test_episodic_retrieval_cache.py`: comparação cache-off/cache-on e persistência.
- `benchmarks/episodic_retrieval.py`: baseline sem cache e estatísticas comparativas.
- `README.md` e `CHANGELOG.md`: somente se o contrato do benchmark mudar; não corrigir toda a dívida documental neste escopo.

### Desenho

1. Construir dois conjuntos idênticos de episódios e dois encoders fake determinísticos equivalentes; usar uma memória com `embedding_cache_size=0` e outra com cache habilitado.
2. Comparar IDs retornados, ordenação e score por episódio; documentar tolerância absoluta de até `1e-5` para diferenças de float32.
3. Verificar que feedback, recência e importância continuam sendo calculados por consulta e não dependem do cache de embeddings.
4. Calcular SHA-256 do arquivo JSON antes e depois de chamadas a `recall()`; confirmar que a recuperação não persiste embeddings nem altera o formato dos episódios.
5. Estender o benchmark para apresentar, separadamente, baseline sem cache, primeira consulta com cache (cold) e consulta aquecida (warm), em 100, 500 e 2.000 episódios.
6. Usar mediana e percentil 95 de várias repetições; não impor limiar absoluto de milissegundos na CI.
7. Manter encoder sintético como padrão. O modo E5 só pode carregar pesos já presentes localmente e deve continuar sem download/rede.
8. Não adicionar dependência obrigatória, migração SQLite, persistência de embeddings, paralelismo ou lock amplo nesta tarefa. O risco de concorrência fica documentado para avaliação separada, salvo se um teste reproduzível demonstrar que é bloqueador.

### Critérios de aceitação

- Cache-off e cache-on retornam os mesmos IDs e a mesma ordenação para o conjunto determinístico.
- Diferença absoluta dos scores por ID não ultrapassa `1e-5`.
- Recuperação warm adicional codifica zero passagens; cache-off continua codificando as passagens a cada chamada.
- Feedback/alteração de importância/recência não provoca re-encoding desnecessário.
- O arquivo persistido permanece byte-a-byte idêntico após `recall()`.
- Benchmark emite JSON com configuração, número de episódios, latências baseline/cold/warm, mediana, p95 e contadores de codificação/cache.
- Smoke test do benchmark permanece rápido e sem pesos externos.
- Suíte completa passa em Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12.
- Registrar separadamente o resultado real do benchmark no hardware disponível; não alegar ganho em i5/8 GB se esse ambiente não for executado.

### Riscos e mitigação

- **Diferença float32:** comparar por ID com tolerância explícita; não relaxar ranking sem justificativa.
- **Encoder fake não representa E5:** separar teste determinístico de medição E5 opcional local.
- **Ruído de benchmark:** múltiplas repetições e mediana/p95; CI verifica formato e invariantes, não tempo absoluto.
- **RAM/hardware:** não extrapolar de x86 CI para i5/8 GB ou ARM64 sem profiling real.
- **Concorrência:** a classe usa estruturas mutáveis sem lock. Não declarar thread-safety; avaliar em tarefa isolada se o uso concorrente for requisito confirmado.

### Rollback

A tarefa é restrita a testes, benchmark e documentação. Reverter o commit da branch empilhada e fechar apenas a nova PR de validação se houver regressão. Não modificar os dados JSON, pesos, datasets, checkpoints, main ou PR #25.

## Observações de PRs pendentes

### PR #25 — cache episódico

Review COMMENT já registra três lacunas: comparação direta cache-off/cache-on, benchmark completo e risco de concorrência. A CI mais recente observada passou 4/4 com 161 testes por job. Não confundir CI verde com demonstração de ganho líquido no hardware-alvo. Nenhuma alteração foi feita nesta PR.

### PR #23 — instalação/gerenciamento Ollama

Review COMMENT de segurança já registra que `OllamaManager.start_service()` inicia o processo sem ambiente sanitizado e herda `OLLAMA_HOST`. Um endpoint cliente loopback não prova que o servidor gerenciado está escutando somente em loopback; um `OLLAMA_HOST=0.0.0.0:11434` herdado pode ampliar a exposição. A PR também deve distinguir serviço preexistente com bind não verificado e explicitar pré-requisito `zstd` no consentimento de instalação Linux. CI: 4/4, 157 testes por job. Não alterar a PR #23 neste ciclo.

## Próximos itens de roadmap (fora do escopo da tarde)

1. Consolidação episódica não destrutiva com proveniência e referências aos episódios-fonte.
2. Benchmark PT-BR de memória conversacional com temporalidade, atualização e abstenção; revisar licenças antes de incorporar datasets.
3. Planejamento hierárquico e replanning mensurado por resultado.
4. Metacognição integrada com calibração global e abstenção.
5. Profiling real de RAM/latência em Windows i5/8 GB e Linux ARM64.
6. Corrigir inconsistências documentais do README em tarefa própria.

## Limites deste ciclo

Auditoria remota, inspeção estática de arquivos/diffs e leitura de logs de CI. Nenhum checkout local, teste local, benchmark local, profiling físico ou teste ARM64 foi executado. Nenhuma implementação foi feita. Nenhuma PR existente foi aprovada, mergeada, editada ou fechada.

## Fontes primárias

- Sentence Transformers API: https://www.sbert.net/docs/package_reference/sentence_transformer/model.html
- multilingual-e5-small model card: https://huggingface.co/intfloat/multilingual-e5-small
- LongMemEval paper: https://arxiv.org/abs/2410.10813
- LongMemEval repository: https://github.com/xiaowu0162/LongMemEval
- ASSIN 2 dataset card: https://huggingface.co/datasets/nilc-nlp/assin2
- Generative Agents paper: https://arxiv.org/abs/2304.03442
- Ollama FAQ sobre bind/OLLAMA_HOST: https://github.com/ollama/ollama/blob/main/docs/faq.mdx
