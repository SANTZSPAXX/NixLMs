# QA noturno — 2026-11-14

## Escopo e conclusão

Auditoria do estado remoto da NixLMs após a implementação vespertina de cache LRU e batching da recuperação episódica. A revisão cobriu estado de branches/PRs, diff, persistência, fingerprints, batching, recursos, segurança, testes e logs reais do GitHub Actions.

**Conclusão:** a implementação da PR #25 está estruturalmente alinhada ao plano, não altera datasets nem pesos e passou na matriz CI existente. Não foi encontrado defeito funcional reproduzível no diff. A PR ainda não deve ser considerada totalmente validada: falta uma comparação direta com o caminho sem cache, o benchmark completo não foi executado e não há profiling no hardware-alvo. A PR #23 mantém uma lacuna de garantia sobre o bind do servidor Ollama; revisão de segurança publicada.

## Estado remoto verificado

- Repositório: [SANTZSPAXX/NixLMs](https://github.com/SANTZSPAXX/NixLMs); branch padrão: `main`.
- `main` permaneceu em `135f480addc43dd270ea7a08b97da6496b651445` durante esta auditoria.
- [PR #25 — cache LRU e batching episódico](https://github.com/SANTZSPAXX/NixLMs/pull/25): aberta, draft, sem merge; branch `feature/episodic-retrieval-cache-batching`, HEAD `1fb2126aca8cbbad8a874f09ad15b4ecfadd04da`; 3 commits à frente e 0 atrás de `main`; 6 arquivos alterados (697 adições, 8 remoções).
- [PR #24 — plano de otimização episódica](https://github.com/SANTZSPAXX/NixLMs/pull/24): aberta, draft, documental.
- [PR #23 — preparação consentida do Ollama](https://github.com/SANTZSPAXX/NixLMs/pull/23): aberta, draft.
- As três PRs acima eram as PRs abertas encontradas. Nenhuma foi mergeada ou fechada. Nenhuma alteração foi feita em `main`, configurações, release ou deploy.

## Revisão da PR #25

### Verificações aprovadas

- Cache LRU volátil, limitado por padrão a `max_items` (2.000 entradas), com vetores `array('f')`/float32.
- Chaves incluem identidade do episódio, SHA-256 do texto da passagem e fingerprint do encoder; testes cobrem mudança de conteúdo, troca de instância, contador de atualização e retenção.
- Batching de misses limitado a 8 por padrão e 32 no máximo; prefixo E5 `passage: ` preservado.
- Fallback compatível para encoders com `encode_passage()` ou `encode()`.
- Recência, importância, feedback e fórmula de score continuam sendo calculados em tempo de consulta.
- Nenhuma dependência obrigatória nova, download de modelo, chamada de rede ou gravação de embeddings no JSON foi introduzida. O cache não participa do formato persistido dos episódios.
- O backend pré-treinado continua CPU-only e local-only. O modelo E5 permanece opcional.
- Nenhum dataset, split, rotina de treino ou peso foi alterado pela PR #25; não foi identificada nova superfície de vazamento treino/validação/teste nessa mudança.

### Matriz do plano da manhã

| Critério | Resultado | Evidência / lacuna |
|---|---|---|
| LRU limitado e float32 | Aprovado | Código e teste de limite LRU |
| Fingerprint de episódio/encoder | Aprovado com ressalva | Testes de conteúdo, identidade e contador; fingerprint usa atributos conhecidos e tamanho do vocabulário, não hash integral de todos os pesos |
| Invalidação por texto, encoder e retenção | Aprovado | Testes dedicados passaram |
| Batching de misses, E5 e fallback | Aprovado | Testes de lotes `[8, 8, 1]`, prefixo E5 e fallback legado |
| Equivalência com referência sem cache | **Parcial** | A fórmula não mudou e cold/warm coincide; falta comparar explicitamente cache habilitado com `embedding_cache_size=0` |
| JSON persistido inalterado | Aprovado por inspeção | Embeddings ficam somente em memória; não há teste específico de esquema JSON nesta PR |
| CPU/local/opcional/sem nova dependência obrigatória | Aprovado por inspeção | Construtor continua recusando dispositivo não CPU e carregamento remoto |
| Matriz Windows/Linux x86-64 | Aprovado | CI 4/4 |
| Benchmark completo 100/500/2.000 | **Não executado** | CI executa apenas smoke test com 10 episódios; benchmark E5 real também não executado |

### CI da PR #25 — logs consultados

Run [#43625546189](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43625546189), workflow `NixLMs tests`, HEAD `1fb2126aca8cbbad8a874f09ad15b4ecfadd04da`.

| Job | Resultado | Suíte |
|---|---|---:|
| Ubuntu / Python 3.10 | success | 161 testes |
| Ubuntu / Python 3.11 | success | 161 testes |
| Ubuntu / Python 3.12 | success | 161 testes |
| Windows / Python 3.12 | success | 161 testes |

Os quatro jobs concluíram o passo `Run unit tests` com `OK`. Os logs mostram aprovação dos testes novos de cache, invalidação, retenção, fallback, batching E5 e smoke do benchmark. Não houve falha de teste.

Os logs também exibem aviso de depreciação do runtime Node.js 20 em `actions/checkout@v4` e `actions/setup-python@v5`; não afetou o resultado desta execução, mas merece atualização futura do workflow/actions.

### Riscos e limitações da PR #25

1. **Evidência de equivalência:** o teste atual compara cold/warm dentro do novo caminho. Como ambos usam o cache float32, não demonstra equivalência numérica com a referência sem cache. Recomenda-se uma execução paralela com `embedding_cache_size=0`, comparando IDs, ordem e scores com tolerância explícita.
2. **Desempenho líquido:** hashing/fingerprinting e preparação percorrem todos os episódios em cada recuperação. O ganho de eliminar re-encoding está demonstrado por contadores, mas a redução líquida de latência ainda não foi medida para 100/500/2.000 itens nem com E5 real.
3. **Concorrência:** `OrderedDict` e `self.items` não têm lock. O fluxo CLI atual é essencialmente serial e o housekeeping normalmente encontra a lista já limitada; não foi reproduzida falha no uso padrão. Chamadas paralelas a `recall()`/`record()` ou poda concorrente podem intercalar operações de cache. Antes de expor a classe a API/thread pool, adicionar sincronização e teste de estresse ou documentar formalmente o uso single-thread.
4. **RAM:** o payload bruto de 2.000 embeddings E5 × 384 dimensões × 4 bytes é aproximadamente 2,93 MiB. Metadados e objetos Python adicionam overhead; profiling real ainda é necessário.
5. **Plataformas:** CI cobre Ubuntu e Windows x86-64; Linux ARM64 não está coberto.

Uma revisão COMMENT foi publicada na [PR #25](https://github.com/SANTZSPAXX/NixLMs/pull/25), review ID `5908188084`, registrando a lacuna de comparação sem cache, o benchmark pendente e a ressalva de concorrência. Nenhum commit foi adicionado à branch da PR.

## Auditoria de segurança da PR #23

A CI da PR #23, run [#43579532053](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579532053), também foi inspecionada pelos logs: 4/4 jobs aprovados, com 157 testes em cada ambiente (Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12). Os testes existentes cobrem endpoint não-loopback, ciclo de vida e seleção de modelo, mas não o caso de ambiente herdado divergente.

**Achado:** `LanguageEngine.local_host` valida o endpoint do cliente; `OllamaManager.start_service()` chama `Popen([binary, "serve"])` sem ambiente sanitizado. O processo filho herda `OLLAMA_HOST`, variável que a [FAQ oficial do Ollama](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) documenta como configuração do endereço de bind. Com um host cliente explicitamente loopback e `OLLAMA_HOST=0.0.0.0:11434` no ambiente do processo, o cliente passa na validação, mas o servidor gerenciado pode escutar em todas as interfaces. Serviço preexistente também é aceito quando responde em loopback, sem comprovação das interfaces de escuta.

Foi publicada revisão COMMENT na [PR #23](https://github.com/SANTZSPAXX/NixLMs/pull/23), review ID `5908188208`, sugerindo fixar `OLLAMA_HOST=127.0.0.1:11434` no ambiente do processo filho e reportar bind não verificado para serviços preexistentes, além de teste de regressão. A PR não foi modificada.

Observação secundária: o caminho de instalação Linux executa `apt-get update` e instala `zstd` quando necessário. O resumo de consentimento deve deixar explícita essa alteração de pacote de sistema.

## CI de referência de `main`

O run [#43579135998](https://github.com/SANTZSPAXX/NixLMs/actions/runs/43579135998), associado ao HEAD auditado de `main`, teve 4/4 jobs aprovados. Os logs de cada job registram 148 testes e `OK` (Ubuntu Python 3.10/3.11/3.12 e Windows Python 3.12).

## Execução local neste ambiente

Foi tentado obter um checkout isolado da branch para executar testes locais, mas a conexão de rede do ambiente não resolveu `github.com` (`Could not resolve host: github.com`). Portanto:

- Nenhum teste local foi executado neste ciclo.
- Nenhum benchmark local foi executado.
- Os resultados positivos acima são exclusivamente de CI real do GitHub Actions; não são apresentados como execução no computador do usuário.

Ainda precisam de validação no computador físico: Windows 11 com CPU i5 antigo/8 GB, consumo real de RAM, latência cold/warm com encoder nativo e E5 somente se já estiver instalado localmente. Não baixar modelo automaticamente. Linux ARM64 permanece pendente.

## Próximos passos priorizados

1. Adicionar teste de equivalência entre cache habilitado e `embedding_cache_size=0`, comparando ranking e scores com tolerância documentada.
2. Adicionar teste explícito de que o JSON episódico não recebe campos de embedding/cache.
3. Executar e registrar `python benchmarks/episodic_retrieval.py` para 100, 500 e 2.000 episódios; medir E5 apenas com pesos locais já disponíveis.
4. Resolver a garantia de bind loopback e o teste de ambiente divergente na PR #23 antes de remover o draft.
5. Fazer profiling no Windows 11/i5/8 GB e, quando houver ambiente disponível, Linux ARM64.
6. Avaliar sincronização do cache antes de qualquer uso concorrente; não introduzir lock amplo sem medir impacto de bloquear inferência do encoder.

## Limites desta auditoria

Esta revisão é estática mais evidência de CI; não comprova ganho de latência no hardware-alvo, qualidade semântica geral, segurança do bind de um serviço Ollama externo em execução nem compatibilidade Linux ARM64. Nenhuma PR foi aprovada, mergeada ou promovida; as PRs de implementação permanecem draft.
