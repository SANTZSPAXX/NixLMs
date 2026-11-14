# NixLMs — Plano técnico do ciclo 2026-11-14

**Status:** planejamento para o ciclo da tarde; nenhuma alteração de código de produção foi feita neste ciclo.  
**Base auditada:** `main` em `135f480addc43dd270ea7a08b97da6496b651445` (merge da PR #22).  
**Branch deste documento:** `docs/plan-2026-11-14-episodic-index`.

## 1. Resumo executivo

A evolução recente já adicionou memória episódica persistente, benchmark cognitivo integrado, decoder autoregressivo condicionado pela saída LIF, calibração por validação, treinamento incremental com checkpoints/rollback e aprendizagem recorrente LIF com surrogate gradients.

A prioridade recomendada para a tarde é **otimizar a recuperação episódica para CPU por meio de cache de embeddings limitado e codificação em lote das entradas ausentes**.

O motivo é concreto: `EpisodicMemory.recall()` percorre os episódios e, quando há encoder semântico, chama `encode_passage()` para cada episódio em toda consulta. O backend E5 implementa essa chamada com `model.encode([um_texto], batch_size=1)`. Com o limite atual de até 2.000 episódios, isso pode repetir milhares de inferências do encoder por mensagem. A memória QA já mantém cache de embeddings; a memória episódica ainda não.

A mudança proposta é local, reversível e não altera o formato persistido dos episódios. O cache será apenas em memória, com limite explícito, chaveado por conteúdo e identidade/versão do encoder. O backend opcional poderá codificar faltas em pequenos lotes, mantendo prefixo `passage:`, CPU e carregamento exclusivamente local.

## 2. Auditoria do repositório

### Estado GitHub

- Repositório público: [SANTZSPAXX/NixLMs](https://github.com/SANTZSPAXX/NixLMs).
- Branch padrão: `main`; HEAD auditado: `135f480addc43dd270ea7a08b97da6496b651445`.
- A branch `main` aparece como não protegida na listagem de branches. Nenhuma configuração foi alterada.
- Há branches históricas de implementações já integradas e branches de PRs fechadas. Não foram excluídas nem atualizadas.
- Não há issue aberta retornada pela consulta ao repositório.
- Não existe plano versionado para 2026-11-14 no diretório `docs/superpowers/plans`; o plano anterior visível é o de 2026-11-13 para a evolução 0.5.

### Pull requests relevantes

| PR | Estado observado | Observação |
|---|---|---|
| [#6 — NixLMs 0.6 Persistent Cognitive Scheduler](https://github.com/SANTZSPAXX/NixLMs/pull/6) | merged | A evolução 0.6 está integrada em `main`; não está pendente. |
| [#7 — NixLMs 0.7 memória episódica](https://github.com/SANTZSPAXX/NixLMs/pull/7) | merged | Memória episódica estruturada e recuperação híbrida integradas. |
| [#16 — Integrated cognitive response benchmark](https://github.com/SANTZSPAXX/NixLMs/pull/16) | merged | Benchmark end-to-end e modo sem persistência durante avaliação. |
| [#19 — Autoregressive neural decoder](https://github.com/SANTZSPAXX/NixLMs/pull/19) | merged | Decoder RNN condicionado pela saída LIF. |
| [#20 — Calibrate decoder confidence](https://github.com/SANTZSPAXX/NixLMs/pull/20) | merged | Calibração do limiar no split validation. |
| [#21 — Safe incremental training](https://github.com/SANTZSPAXX/NixLMs/pull/21) | merged | Treino isolado, comparação por validation e rollback. |
| [#22 — Recurrent LIF surrogate-gradient learning](https://github.com/SANTZSPAXX/NixLMs/pull/22) | merged | BPTT com surrogate gradients e objetivo contrastivo sobre representações ocultas. |
| [#23 — Consent-gated Ollama setup](https://github.com/SANTZSPAXX/NixLMs/pull/23) | open, draft | Única PR aberta encontrada; análise de segurança na seção 7. |

No instante da auditoria, a PR #23 era a única PR aberta. A PR #24 é esta PR documental, criada depois da inspeção; contém somente este plano e não altera código de produção.

As PRs #3, #4 e #5 do agendador 0.6 estão fechadas sem merge; a implementação final foi integrada pela PR #6. Não reabrir nem editar essas PRs sem autorização.

### CI e testes

- Workflow: `.github/workflows/tests.yml`.
- Matriz configurada: Ubuntu com Python 3.10, 3.11 e 3.12; Windows com Python 3.12.
- No HEAD de `main`, o endpoint de check-runs retornou 8 verificações concluídas com sucesso, correspondentes a dois conjuntos de 4 jobs. Run mais recente observado para esse HEAD: [43579135998](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579135998).
- Na PR #23, o último run observado para o HEAD `63b34cbd6433270cbb1cc2d0ea4a935ec49a7625` concluiu 4/4 jobs com sucesso: [43579532053](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579532053).
- A PR #23 teve execuções anteriores com falha em commits intermediários; o HEAD atual observado está verde.
- Não foram executados testes locais neste ciclo. A leitura dos arquivos de teste não equivale à execução da suíte.
- A CI não cobre Linux ARM64; a compatibilidade ARM64 permanece sem evidência automatizada neste workflow.

### Documentação

A documentação principal contém divergências em relação ao código integrado:
- O README ainda descreve a memória 0.7 como “em desenvolvimento”, embora a PR #7 esteja merged.
- A seção de limitações do README ainda diz que os pesos recorrentes LIF não recebem BPTT end-to-end, o que está desatualizado após a PR #22 e o changelog.
- O changelog já registra treinamento recorrente LIF, checkpoints incrementais e calibração do decoder.
- Não há plano de implementação 0.8 ou plano datado de 2026-11-14 antes deste documento.

Essas divergências devem ser corrigidas em uma tarefa documental própria, sem misturar a atualização do README com a mudança de desempenho proposta para a tarde.

## 3. Lacunas técnicas identificadas

### Memória episódica e consolidação

- A memória episódica é persistente, estruturada, recuperável e recebe feedback explícito.
- A recuperação combina relevância lexical/semântica, recência, importância e feedback.
- Ainda não existe consolidação/reflexão de experiências em representações derivadas de nível superior.
- `prune()` apenas mantém os últimos `max_items`; não prioriza episódios antigos com importância ou feedback positivo. O housekeeping atual também não consolida experiências.
- A recuperação semântica de episódios recalcula embeddings de passagens a cada consulta, diferentemente da memória QA, que já possui cache.

### Representação semântica

- O encoder nativo usa palavras, bigramas e subwords de caracteres, com aprendizado contrastivo.
- A rede LIF agora tem treinamento recorrente com surrogate gradients e objetivo contrastivo independente do readout.
- O backend E5 é opcional, CPU e local-only; não é requisito do núcleo.
- A qualidade do encoder nativo continua limitada pela cobertura e diversidade dos pares de treino. Não há evidência suficiente para afirmar generalização semântica ampla.

### Avaliação em português brasileiro

O arquivo `datasets/starter_ptbr.jsonl` é pequeno: 9 exemplos QA de treino, 7 de validação e 4 de teste, além de 4 pares contrastivos de treino e 2 de teste. O split de teste atual não sustenta conclusões estatísticas fortes.

ASSIN 2 é uma referência útil para similaridade textual e inferência textual em português, mas não substitui um benchmark de memória conversacional. O dataset `nilc-nlp/assin2` exibe licença “unknown” no Hugging Face; não copiar nem redistribuir seus dados no repositório antes de confirmar os termos aplicáveis. LongMemEval oferece uma taxonomia mais completa de memória de longo prazo, mas é um benchmark de conversas em inglês e com históricos extensos; deve servir como referência de desenho, não como substituto direto do teste PT-BR.

### Planejamento e metacognição

- `GoalManager` persiste objetivos, etapas, dependências e próximas ações.
- Não há decomposição hierárquica mais rica, estimativa de custo/risco ou replanning baseado em resultados observados.
- O runtime já expõe traces, métricas, calibração do readout LIF e do decoder.
- Ainda não há estimativa global e calibrada de incerteza que combine recuperação, fatos, episódios, decoder e abstenção. Os limiares existentes são específicos de módulos/tarefas.

### Eficiência de inferência

- O núcleo LIF e o decoder são compactos e orientados a CPU.
- O E5 opcional tem 12 camadas, dimensão 384 e licença MIT, mas requer dependências externas e pesos locais.
- O maior gargalo claramente observável nesta auditoria é a re-encoding repetida de cada episódio durante a recuperação com encoder semântico.
- Não há benchmark de latência/RAM executado no computador-alvo de 8 GB; os resultados de CI não substituem profiling no hardware real.

## 4. Pesquisa e alternativas

### Memória e consolidação

- [Generative Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442) descreve memória de observações, reflexões de nível superior e recuperação dinâmica. O trabalho também relata que reflexões podem sintetizar experiências, mas usa um LLM e reconhece risco de embelezamento/alucinação. É uma referência arquitetural, não uma justificativa para tornar reflexão generativa obrigatória no runtime modesto.
- [LongMemEval (Wu et al., 2024/ICLR 2025)](https://arxiv.org/abs/2410.10813) avalia extração de informação, raciocínio entre sessões, temporalidade, atualização de conhecimento e abstenção com 500 perguntas. A taxonomia é útil para o roadmap; o corpus não é PT-BR.
- Para a NixLMs, consolidação futura deve preservar episódios originais, guardar referências de proveniência e separar resumo/hipótese de fato verificado. Uma síntese gerada não deve apagar a evidência que a originou.

### Recuperação semântica

Alternativas consideradas:

1. **Recalcular tudo a cada pergunta:** simples e sem estado auxiliar, mas desperdiça inferência do encoder.
2. **Codificar todos os episódios em lote a cada pergunta:** reduz overhead de chamadas e aproveita `batch_size`, mas continua repetindo o trabalho em cada turno.
3. **Persistir embeddings em SQLite:** reduz trabalho após reinício, mas adiciona esquema, migração, invalidação persistente e risco de cache obsoleto; é desnecessário para a primeira melhoria.
4. **Cache em memória, limitado e com fingerprint, mais lote somente para misses:** mantém a fonte de verdade atual, não cria migração e evita reprocessar passagens já vistas. **Alternativa escolhida.**

A documentação oficial do [Sentence Transformers](https://sbert.net/docs/package_reference/sentence_transformer/model.html) aceita listas de textos em `encode()` e afirma que ajustar `batch_size` pode melhorar significativamente a velocidade, devendo ser medido para o hardware/modelo. O [model card do multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) especifica os prefixos `query:` e `passage:`, 12 camadas, dimensão 384, 94 idiomas e licença MIT.

### Benchmark PT-BR

- [ASSIN 2 Shared Task](https://ceur-ws.org/Vol-2583/) documenta a tarefa de similaridade semântica e inferência textual em português.
- [Cartão do dataset ASSIN 2 no Hugging Face](https://huggingface.co/datasets/nilc-nlp/assin2) mostra aproximadamente 6,5 mil exemplos de treino e licença desconhecida. O proceedings CC BY 4.0 não deve ser interpretado como licença automática dos dados.
- Recomendação futura: adaptar um loader local para ASSIN 2 somente após revisão de licença e adicionar um conjunto PT-BR específico para memória conversacional, com temporalidade, atualização de fatos e abstenção.

## 5. Prioridade única para o ciclo da tarde

**Título:** Cache limitado e codificação em lote de embeddings episódicos.

### Problema

Com o backend E5 habilitado, cada chamada a `EpisodicMemory.recall()` codifica novamente cada passagem de cada episódio. O limite atual é de 2.000 itens. O caminho de recuperação episódica é executado em respostas normais, então a latência cresce com o tamanho da memória e o número de inferências do encoder por turno.

### Hipótese

Se cada embedding de passagem for calculado uma vez por conteúdo/versão do encoder e mantido em cache limitado, a recuperação aquecida poderá manter o mesmo score e ranking sem repetir inferência das passagens. Codificar misses em lotes pequenos deverá reduzir o custo de inicialização do índice no backend E5.

### Desenho proposto

1. Adicionar à `EpisodicMemory` um cache LRU em memória, limitado por `max_items` ou por um limite configurável. Não persistir embeddings no JSON.
2. Chavear cada entrada por ID estável do episódio (ou hash de conteúdo para registros legados), fingerprint do texto efetivamente codificado e fingerprint do encoder.
3. O fingerprint do encoder deve distinguir pelo menos tipo/dimensões, versão de atualização nativa e configuração do backend pré-treinado (caminho local, comprimento máximo e identidade da instância/modelo carregado). Não depender apenas de `updates=0` para distinguir encoders diferentes.
4. Guardar vetores compactos (preferencialmente `array('f')` quando compatível com `cosine()`) para limitar RAM. Com 2.000 vetores de 384 dimensões float32, o payload bruto fica em aproximadamente 2,93 MiB, sem contar metadados.
5. Adicionar `encode_passages(texts, batch_size=...)` ao backend E5 opcional. Usar o prefixo `passage: `, normalização e CPU já existentes. Processar misses em chunks pequenos; começar com batch conservador 8 e medir 8/16/32 no benchmark manual.
6. Encoders sem API de lote devem continuar funcionando com fallback para `encode_passage()`, mas seus resultados também devem ser cacheados.
7. A consulta continua sendo codificada a cada chamada com `encode_query()`. Feedback, recência e importância continuam fazendo parte do score em tempo de consulta e não devem forçar re-encoding do texto.
8. Conteúdo alterado, encoder alterado ou versão de pesos alterada deve invalidar somente as entradas afetadas. Evicção e remoção de episódios devem liberar entradas correspondentes.
9. Expor contadores simples de hits, misses, evictions e passagens codificadas em `stats()`/diagnóstico, sem gravar telemetria sensível no disco.

### Arquivos prováveis

- Modificar: `nixlms_core/episodic.py`
- Modificar: `nixlms_core/pretrained_encoder.py`
- Modificar: `tests/test_episodic_memory.py`
- Modificar ou criar testes em: `tests/test_evolution.py`
- Atualizar: `README.md` e `CHANGELOG.md` somente para documentar o comportamento entregue.

Não modificar `main`; implementar em branch nova derivada do HEAD mais recente no início do ciclo da tarde. Não reaproveitar a branch deste documento para código de produção se ela já tiver sido usada para outro trabalho.

### Critérios de aceitação

1. Para um conjunto fixo de episódios e encoder determinístico, score e ordenação com cache devem coincidir com a referência sem cache, com tolerância numérica documentada.
2. Primeira recuperação deve codificar cada passagem ausente uma única vez (ou em lotes); segunda recuperação sem mudanças deve codificar zero passagens novamente.
3. Acrescentar um episódio novo deve codificar somente a nova passagem; atualizar feedback deve alterar o fator de score sem re-encoding.
4. Alterar texto de episódio ou fingerprint do encoder deve invalidar a entrada correspondente e preservar as demais.
5. Cache deve respeitar o limite configurado; evicção não pode alterar o resultado da recuperação, apenas exigir recodificação futura.
6. Registros legados sem ID devem continuar recuperáveis usando uma chave de conteúdo estável.
7. Testes do backend E5 devem usar modelo fake/injetado; CI não pode baixar pesos nem exigir PyTorch/Sentence Transformers.
8. O backend continua CPU-only, local-only e opcional. A ausência de dependências/modelos deve manter o encoder nativo funcionando.
9. A suíte completa deve passar na matriz existente: Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12.
10. Um benchmark reproduzível com 100, 500 e 2.000 episódios deve registrar cold/warm latency e número de chamadas de encoder. Não impor limiar absoluto de milissegundos em CI; o critério primário é eliminar chamadas repetidas de passagem no caminho aquecido sem alterar a qualidade de recuperação.

### Riscos e mitigação

- **Cache obsoleto:** chave inclui conteúdo e fingerprint do encoder; testes cobrem mutação e atualização.
- **Crescimento de RAM:** LRU limitado e armazenamento float32 compacto; sem persistência.
- **Pico de memória no lote:** chunks pequenos e batch configurável; sem multiprocessamento.
- **Diferença numérica:** testar score/ranking com tolerância e manter normalização atual.
- **Backend opcional ausente:** fallback atual sem dependências obrigatórias.
- **Regressão de desempenho no encoder nativo:** benchmark separa backend nativo e E5; cache não deve tornar o caminho nativo mais complexo de forma relevante.

### Rollback

O cache é volátil e não altera `episodic_memory.json`, pesos, datasets ou checkpoints. Se houver regressão, reverter o commit da branch/PR draft e retornar ao caminho atual sem migração de dados. Não promover alterações automaticamente.

## 6. Backlog técnico após esta prioridade

1. Consolidação episódica não destrutiva com proveniência e referências aos episódios-fonte; não promover automaticamente resumos a fatos verificados.
2. Benchmark PT-BR maior e balanceado, incluindo memória conversacional, temporalidade, atualização e abstenção; revisar licença de cada dataset antes de incluir dados.
3. Atualizar documentação desatualizada sobre versão 0.7 e treinamento recorrente LIF.
4. Planejamento hierárquico e replanning medido por resultados, mantendo execução de ações externas fora do escopo automático.
5. Metacognição com calibração/abstenção integrada entre módulos e avaliação de confiabilidade, sem alegar consciência ou senciência.
6. Profiling de RAM/latência em Windows CPU-only e Linux ARM64 quando houver ambiente real disponível.

## 7. Observações da PR #23 (sem alteração da PR existente)

A PR [#23](https://github.com/SANTZSPAXX/NixLMs/pull/23) está aberta em draft, base `main`, com 9 arquivos alterados, 20 commits e 518 adições/43 remoções. O HEAD observado é `63b34cbd6433270cbb1cc2d0ea4a935ec49a7625`; o CI mais recente observado passou em 4/4 jobs. Não havia reviews nem comentários retornados.

**Ponto de segurança que merece correção/revisão antes de remover o draft:** `OllamaManager.start_service()` verifica que o endpoint usado pelo cliente é loopback, mas inicia `ollama serve` herdando o ambiente do processo. A documentação oficial do Ollama informa que `OLLAMA_HOST` controla o endereço de bind do servidor e pode ser configurado como `0.0.0.0`. Assim, um ambiente com `OLLAMA_HOST=0.0.0.0:11434` pode fazer o serviço escutar em todas as interfaces enquanto o cliente NixLMs continua consultando `127.0.0.1`. O mesmo risco existe quando a PR encontra um serviço já ativo: a conectividade local não prova que o bind é local.

Antes de afirmar “loopback-only”, o fluxo gerenciado deve forçar/validar o bind `127.0.0.1:11434` e testar o caso de ambiente herdado com `OLLAMA_HOST` não local. Para um serviço preexistente cujo bind não possa ser verificado de forma portátil, o diagnóstico deve dizer “endpoint local acessível; bind do servidor não verificado”, não afirmar isolamento de rede. Referência: [FAQ oficial do Ollama](https://github.com/ollama/ollama/blob/main/docs/faq.mdx).

Observação secundária: no Linux, a instalação do Ollama pode executar `apt-get update` e instalar `zstd` como pré-requisito. Essa alteração de pacote de sistema deve ficar explícita no resumo de consentimento ou receber confirmação própria. Nenhuma dessas observações foi publicada como comentário nem aplicada à PR #23.

Outra lacuna documental: a PR seleciona `qwen2.5:0.5b`, mas a documentação alterada não aponta claramente a origem upstream nem a licença do modelo. O cartão oficial [Qwen/Qwen2.5-0.5B](https://huggingface.co/Qwen/Qwen2.5-0.5B) declara Apache-2.0; a documentação deve registrar o modelo upstream, o tag exato usado pelo Ollama e a licença/avisos correspondentes, sem presumir que o tag quantizado seja idêntico aos pesos originais.

## 8. Próxima ação

O ciclo da tarde deve começar confirmando novamente o HEAD de `main`, branches e PRs; criar uma branch exclusiva de implementação a partir do SHA atual; executar testes primeiro; implementar somente o cache/batching episódico; revisar diff e compatibilidade; aguardar CI real; abrir PR draft. Não fazer merge, release, deploy, alteração de configurações ou modificação de PR existente.

## Referências externas

- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior*: https://arxiv.org/abs/2304.03442
- Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*: https://arxiv.org/abs/2410.10813
- Sentence Transformers — API `encode()` e parâmetro `batch_size`: https://sbert.net/docs/package_reference/sentence_transformer/model.html
- intfloat/multilingual-e5-small — model card, idioma, dimensão, licença e prefixos: https://huggingface.co/intfloat/multilingual-e5-small
- ASSIN 2 — proceedings da shared task: https://ceur-ws.org/Vol-2583/
- ASSIN 2 — dataset card; licença reportada como desconhecida: https://huggingface.co/datasets/nilc-nlp/assin2
- Ollama — FAQ oficial sobre bind e `OLLAMA_HOST`: https://github.com/ollama/ollama/blob/main/docs/faq.mdx
