# QA noturno — 2026-11-17

## Escopo e integridade

Auditoria do plano matinal #35 e da implementação #36, com foco no benchmark piloto de recuperação episódica em PT-BR.

- Repositório: `SANTZSPAXX/NixLMs`.
- `main` observado em `135f480addc43dd270ea7a08b97da6496b651445`; confirmado pela referência remota `refs/heads/main`.
- PR #35: planejamento documental, aberta em draft, base `main`.
- PR #36: benchmark PT-BR, aberta em draft, base `test/episodic-cache-parity-benchmark`, HEAD `5fcf8de86a3004c825ed18223fcb0ae86c9ac9be`.
- A PR #36 é empilhada sobre a PR #28; não altera #25 nem #28.
- Nenhum merge, release, deploy, force-push, exclusão ou alteração de configuração sensível.

## Revisão da PR #36

Arquivos revisados: workflow de testes, README, CHANGELOG, avaliador, três arquivos de dados, README do dataset e testes.

### Aspectos aprovados por inspeção

- O avaliador usa memória temporária e desabilita o cache para isolar o ranking.
- O conjunto de 50 episódios, 30 consultas e 32 qrels é sintético e separado da memória de produção.
- Os qrels rejeitam referências inexistentes, pares duplicados, relevância fora de 1/2 e consultas sem resposta.
- O relatório contém IDs, hashes e métricas, sem texto das consultas/passagens ou caminhos absolutos.
- O modo lexical usa biblioteca padrão; E5 e checkpoint nativo são opt-in.
- E5 exige diretório local existente, CPU e `local_files_only=True`.
- Nenhuma fórmula de ranking ou código de produção é alterado.
- Não há etapa de treino neste benchmark; portanto, não foi identificado vazamento treino/teste introduzido pela PR. Os splits validation/test são relatados separadamente, mas o corpus de episódios é compartilhado como coleção de recuperação, não como dados de treino.

### Defeito reproduzível encontrado

A opção `--output` chamava `Path.write_text()` diretamente sem proteger os arquivos de entrada nem a memória episódica de produção. Um comando como:

```bash
python benchmarks/episodic_retrieval_quality_ptbr.py --output data/episodic_memory.json
```

poderia substituir o histórico real por um relatório de benchmark, contrariando a garantia declarada de não mutação.

### Correção isolada

Foi criada a branch `fix/ptbr-benchmark-protect-output-paths`, derivada do HEAD da PR #36, sem alterar a PR #36.

- Adiciona `validate_output_path()`.
- Resolve caminhos antes de comparar, cobrindo aliases relativos e symlinks já existentes.
- Bloqueia o caminho da memória episódica de produção.
- Bloqueia os três arquivos do dataset padrão e do diretório `--dataset-dir` selecionado.
- Mantém permitido um arquivo de relatório separado.
- Acrescenta testes para memória de produção, arquivos padrão, dataset customizado e destino permitido.
- Registra a correção no CHANGELOG.

Commits iniciais da branch:
- `6452eab64f592a5b1e82b6a07ae0292bc44de664` — guard de caminho.
- `cd1aad67eb232d8c874c6d9939055e271d576272` — testes de caminho.
- `3a82b1ac1f35cd2ee1782965f5ff2e99d2efbe96` — CHANGELOG.
- HEAD final após os ajustes: `f4f625d8ce417893ae02e8dba2a24698a3896a03` (8 commits no total).

## CI da PR #36 — execução anterior à correção

Run [#44153228925](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44153228925), HEAD `5fcf8de86a3004c825ed18223fcb0ae86c9ac9be`:

- Ubuntu/Python 3.10: 176 testes, success.
- Ubuntu/Python 3.11: 176 testes, success.
- Ubuntu/Python 3.12: 176 testes, success.
- Windows/Python 3.12: 176 testes, success.
- Job `episodic-benchmark`: success.
- Job `episodic-quality-benchmark`: success; artefato enviado (ID 14386102603).

Os logs dos seis jobs foram consultados. Avisos não bloqueantes incluem depreciação do runtime Node.js 20 das actions e avisos Node `punycode`/`url.parse`. A CI anterior não valida os commits desta branch de correção.

## Métricas do baseline declarado na PR #36

Os números publicados na descrição da PR são: nDCG@5 0.829261; MRR@5 0.875000; Recall@5 0.750000; Precision@5 0.183333; cobertura 0.875000; abstenção em consultas sem resposta 1.0; falso positivo 0.0.

Limitações: conjunto sintético pequeno; qrels editoriais sem anotação independente; a categoria contextual não representa ainda uma avaliação completa de resolução de referência conversacional, pois o avaliador passa somente o texto da consulta para `recall()`. Não comparar diretamente com MTEB-BR/BEIR nem generalizar para todo PT-BR.

## Testes desta correção

- Nenhum teste local foi executado neste ambiente.
- CI real da PR #37: [run #44211940434](https://github.com/SANTZSPAXX/NixLMs/actions/runs/44211940434), HEAD `b7350afde8830a875dc0911e737ed412b569c929`, concluída com sucesso (6/6 jobs).
- Ubuntu/Python 3.10: 182 testes, success.
- Ubuntu/Python 3.11: 182 testes, success.
- Ubuntu/Python 3.12: 182 testes, success.
- Windows/Python 3.12: 182 testes, success.
- Job `episodic-benchmark`: success; artefato enviado (ID 14385449940).
- Job `episodic-quality-benchmark`: success; artefato enviado.
- Os seis logs foram consultados. Cada matriz executou 182 testes e terminou em `OK`; os testes de caminho protegido, destino separado e NaN/±infinito aparecem como `ok` no log Python 3.12.
- Os dois artefatos do run #44211940434 foram publicados. O JSON de qualidade foi baixado e inspecionado; preservou o hash do dataset e as métricas por split.
- A aprovação da CI da PR #36 não foi atribuída a esta correção.
- Não foi executado E5 real nem checkpoint nativo real.
- Nenhum arquivo da memória pessoal foi lido ou alterado por este ciclo.

## Riscos e limitações restantes

1. Os julgamentos são editoriais e precisam de revisão independente.
2. Consultas da categoria contextual não testam um histórico conversacional explícito; a API avaliada recebe apenas a consulta textual.
3. O artefato JSON publicado na CI deve ser inspecionado separadamente se for usado como evidência quantitativa externa.
4. E5 local pode elevar RAM/CPU e não faz parte da CI padrão.
5. Windows CI não equivale ao hardware i5/8 GB do operador.
6. Linux ARM64 não foi executado.
7. Não foi identificado vazamento de treino/teste novo na PR #36; o benchmark não treina encoder nem pesos.

## Próximos passos priorizados

1. Aguardar e inspecionar logs completos da CI da correção de caminho.
2. Confirmar que a saída protegida falha sem alterar memória/dataset e que um destino separado funciona.
3. Revisar manualmente qrels ambíguos, sobretudo contextual, antes de usar o baseline como gate.
4. Planejar um conjunto de avaliação contextual com histórico explícito, sem misturar dados pessoais.
5. Executar benchmark no computador físico somente com encoder local já disponível e medir RAM/CPU.
6. Preparar runner Linux ARM64 quando houver ambiente real.
7. Manter todas as PRs em draft; sem merge automático.

## Referências

- PR #35: https://github.com/SANTZSPAXX/NixLMs/pull/35
- PR #36: https://github.com/SANTZSPAXX/NixLMs/pull/36
- CI #36: https://github.com/SANTZSPAXX/NixLMs/actions/runs/44153228925
- MTEB-BR: https://mteb-br.org/
- MTEB-BR repository: https://github.com/tardellirs/mteb-br
- BEIR: https://arxiv.org/abs/2104.08663
- E5 model card: https://huggingface.co/intfloat/multilingual-e5-small


## Adendo — revisão final de parâmetros e artefato

A inspeção do artefato JSON `episodic-retrieval-quality-ptbr` (ID 14359367899, gerado pelo run #44153228925) confirmou o SHA-256 do conjunto `15bb508c03426adf37b34889ee63238a355676d007451a1cabf92f49a7b95508` e os valores publicados na descrição da PR #36.

Métricas por split observadas no artefato:
- Validation (12 respondíveis + 3 sem resposta): nDCG@5 0.937482, MRR@5 1.000000, Recall@5 0.833333, cobertura 1.000000.
- Test (12 respondíveis + 3 sem resposta): nDCG@5 0.721039, MRR@5 0.750000, Recall@5 0.666667, cobertura 0.750000.
- Abstenção nas consultas sem resposta: 3/3 em cada split; nenhum falso positivo.

A diferença entre validation e test é relevante e reforça que o conjunto ainda é pequeno; não se deve interpretar o agregado como qualidade geral. O artefato contém IDs e resultados, sem textos de consultas/passagens.

A revisão também identificou que `--min-score nan` ou `inf` era aceito: NaN fazia todas as comparações de score falharem e podia gerar JSON com valores não padrão em outras saídas. A branch desta PR agora rejeita limiares não finitos tanto em `evaluate_dataset()` quanto no CLI, com testes de regressão para NaN e ±infinito.

CI da branch de correção permanece pendente até a execução do workflow no HEAD final. Nenhuma aprovação da PR #36 foi atribuída aos commits desta correção.
