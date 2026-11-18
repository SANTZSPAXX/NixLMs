# Roadmap inicial de objetivos da NixLMs

O comando `/objetivo semear-roadmap` cria cinco objetivos de engenharia e suas etapas no `data/goals.json` local.

## Objetivos

1. **Confiabilidade e qualidade do núcleo** — contratos, regressões, diagnósticos e compatibilidade.
2. **Memória e aprendizagem verificável** — avaliação PT-BR, rastreabilidade, consolidação controlada e rollback.
3. **Raciocínio, contexto e modelo de mundo** — fatos versus hipóteses, causalidade limitada, contexto seguro e benchmark.
4. **Autonomia segura orientada a objetivos** — handlers tipados, executor allowlisted, verificação, recuperação e ciclo cancelável.
5. **Interface e capacidades multimodais** — interfaces portáveis, voz/visão consentidas e validação de recursos.

Cada objetivo possui etapas ordenadas por dependências. Todas começam como `pending`; o seed não marca trabalho como concluído nem executa ações.

## Uso

Na raiz do repositório:

```text
python neural_core.py
/objetivo semear-roadmap
/objetivo listar
/status
```

O seed é idempotente: identifica objetivos e etapas pelo título exato, adiciona somente os itens ausentes e preserva IDs, descrições, estados, dependências e objetivos que já existam. Faça backup de `data/goals.json` antes de alterações manuais extensas.

## Limite operacional atual

O Autonomy Planner 0.2 pode selecionar uma etapa liberada e movê-la de `pending` para `in_progress`. Isso não executa o trabalho descrito na etapa e não a conclui. A conclusão continua dependendo de verificação e registro explícito. O roadmap inclui essa lacuna como prioridade de engenharia; não habilita shell, rede, execução arbitrária ou ações externas.
