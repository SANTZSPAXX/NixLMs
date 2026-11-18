# Nix Autonomy Engine 0.1

## Objetivo

Adicionar uma camada de execução governada por política, sem confundir autonomia funcional com consciência. O motor recebe propostas de um planejador confiável, valida ações registradas explicitamente, aplica política de escopo/risco e mantém auditoria SQLite.

## Contrato

- **Autonomia alta:** o runtime pode chamar `run_cycle()` repetidamente a partir de objetivos e eventos, sem exigir uma nova mensagem do usuário por etapa.
- **Execução híbrida:** ações internas, locais e externas podem ser registradas por adaptadores confiáveis. O escopo local/externo exige aprovação por padrão.
- **Aprovação por política:** ações internas de baixo risco podem executar; escopos local/externo e riscos alto/sensível aguardam aprovação.
- **Allowlist:** somente callbacks registrados pelo código confiável são executáveis. O banco nunca desserializa callbacks.
- **Sem shell arbitrário:** não existe executor genérico de comandos, descoberta implícita de ferramentas ou execução de código vindo de payload.
- **Limites:** payload/resultados limitados em bytes e quantidade de propostas por ciclo limitada.
- **Auditoria:** solicitações, aprovações, rejeições, conclusão e falhas ficam em SQLite.
- **Sem replay automático:** se o processo cair durante uma ação, a solicitação pode permanecer em `running` e exige reconciliação. Não há retry automático de efeitos colaterais.

## API inicial

```python
from nixlms_core.autonomy import AutonomyEngine, AutonomyPolicy

engine = AutonomyEngine("data/autonomy.sqlite3", AutonomyPolicy())
engine.register_action(
    "memory.review",
    callback=review_memory,
    scope="internal",
    risk="low",
)
result = engine.run_cycle([
    {"action": "memory.review", "payload": {"limit": 10}},
])
```

Para escopo local/externo, a solicitação fica em `pending_approval`. O runtime deve apresentar detalhes ao operador e chamar `approve(request_id, approved_by=...)` somente após consentimento explícito, ou `deny(...)`.

**Limite de autenticação:** `approved_by` é apenas um rótulo de auditoria; o motor não autentica o operador. A interface/runtime que expõe aprovação deve validar a identidade e obter consentimento explícito antes de chamar `approve()`. Não exponha esse método diretamente a entradas não confiáveis.

Os callbacks são funções Python fornecidas pelo runtime; não devem aceitar caminhos arbitrários, URLs arbitrárias, argumentos de shell ou outros alvos fora de suas próprias allowlists.

## Integração e limites desta versão

Esta primeira fatia fornece registro de ações, policy gate, ciclo limitado e trilha de auditoria. Não inicia worker de fundo, não gera planos por LLM, não escolhe automaticamente objetivos e não fornece adaptadores de sistema de arquivos/rede. O chamador confiável deve fornecer propostas. A integração com GoalManager/TaskScheduler, observação estruturada e reflexão será feita em etapas seguintes.

## Compatibilidade e recursos

Usa somente a biblioteca padrão do Python e SQLite. Não baixa modelos, não exige GPU e não inicia serviços. Cada operação abre sua própria conexão SQLite; WAL e busy timeout são configurados. O callback roda fora da transação de banco.

## Validação

```bash
python -m unittest discover -s tests -p "test_autonomy_engine.py" -v
python -m unittest discover -s tests -v
```

A CI do PR deve validar Windows e Linux. Nenhum teste local é declarado neste registro.

## Riscos e rollback

- Callbacks locais/externos podem ter efeitos colaterais; por isso exigem aprovação por padrão.
- A execução do callback não possui timeout/preempção nesta versão; callbacks devem ser curtos e cooperativos.
- Queda durante `running` requer reconciliação manual para evitar repetição não idempotente.
- A política padrão permite registrar os três escopos, mas somente ações internas de baixo risco executam sem aprovação.
- Rollback: remover o módulo, teste e documentação adicionados; nenhuma migração dos dados existentes é necessária. O banco de autonomia é isolado em `data/autonomy.sqlite3`.

## Referências

- Python sqlite3: https://docs.python.org/3/library/sqlite3.html
- Python threading: https://docs.python.org/3/library/threading.html
- SQLite transactions: https://www.sqlite.org/lang_transaction.html
