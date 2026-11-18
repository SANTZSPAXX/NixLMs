# Runtime autônomo governado

## Capacidades implementadas

Ao iniciar a NixLMs pelo runtime neural ou pela interface web, `start_runtime()` executa autodiagnóstico, registra handlers permitidos, inicia o agendador SQLite, agenda aprendizagem em ociosidade e ciclos recorrentes de autonomia. O planner seleciona etapas cujas dependências foram concluídas.

Etapas podem ser manuais ou associadas a tarefas tipadas. Uma tarefa só é executada quando seu nome corresponde a um handler registrado por código confiável. Uma tarefa automatizada só é marcada como concluída quando seu verificador retorna explicitamente `True`. Solicitações, resultados, erros e transições são auditados no SQLite.

## Registrando uma tarefa

Exemplo de integração dentro de um módulo confiável:

```python
planner.register_task(
    "count_local_records",
    callback=count_records,
    verifier=lambda result, payload: (
        isinstance(result, dict)
        and result.get("count") == payload.get("expected")
    ),
    description="Conta registros em uma fonte local autorizada",
)

goal = core.goals.create_goal("Auditoria local")
core.goals.add_step(
    goal["id"],
    "Contar registros",
    task={
        "name": "count_local_records",
        "payload": {"source": "events", "expected": 12},
    },
)
```

O callback deve ser determinístico, limitado em recursos, idempotente quando possível e operar somente sobre recursos autorizados. O verificador deve validar o resultado real, não apenas a ausência de exceção. Texto livre não é convertido em código ou callback.

Se o callback falhar ou o verificador rejeitar o resultado, a etapa fica em `failed`. O operador deve investigar e reabrir a etapa manualmente. Etapas `in_progress` após encerramento abrupto não são reproduzidas automaticamente.

## Modelo de linguagem

A Nix oferece integração opcional com Ollama local (modelo padrão configurado: `qwen2.5:0.5b`) e gerador Hugging Face local quando já instalado. Nenhum modelo é baixado automaticamente. Sem modelo generativo disponível, o núcleo legado continua funcionando, mas não oferece planejamento geral por linguagem natural.

Um LLM poderá propor planos em evolução futura, mas a saída deve ser tratada como dado não confiável. Só ações registradas e autorizadas podem ser executadas.

## Configuração

- `NIXLMS_AUTONOMY_ENABLED=1`: ativa ciclos recorrentes (padrão).
- `NIXLMS_AUTONOMY_ENABLED=0`: desativa novos ciclos e cancela ciclos pendentes.
- `NIXLMS_AUTONOMY_INTERVAL_SECONDS=300`: intervalo limitado a 60–3600 segundos.
- `NIXLMS_LLM_ENABLED=1`: permite consultar Ollama local se estiver instalado.
- `OLLAMA_HOST=http://127.0.0.1:11434`: endpoint local; endpoints remotos são recusados.

## Inicialização automática

### Windows 10/11

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-autostart.ps1
.\scripts\remove-autostart.ps1
```

Para usar ambiente virtual, passe `-Python ".\venv\Scripts\python.exe"` ao instalador.

### Linux com systemd de usuário

```bash
PYTHON="$PWD/.venv/bin/python" sh ./scripts/install-autostart.sh
sh ./scripts/remove-autostart.sh
```

Os scripts não instalam Python, dependências ou modelos. O computador precisa estar ligado e a sessão do usuário ativa. Isso não depende de conexão com ChatGPT.

## Limitações restantes

- O planner é determinístico e não decompõe sozinho qualquer objetivo em um plano completo. Objetivos e etapas ainda precisam ser criados pelo usuário ou por componente confiável.
- O catálogo executável é preenchido por código confiável; ainda não há catálogo universal de ferramentas pronto para uso.
- O executor de tarefas internas não é sandbox do sistema operacional. Handlers devem ser pequenos e controlados; ações locais/externas continuam no mecanismo de aprovação.
- Callbacks síncronos precisam impor seus próprios limites de tempo e recursos. O executor não interrompe à força código Python bloqueado.
- E-mail, calendário, mensageria, pesquisa externa, voz e câmeras exigem adaptadores, autenticação, escopos mínimos e testes próprios.
- A interface visual precisa consumir estados reais do executor e oferecer supervisão/aprovação; runtime não comprova que todos os painéis estejam conectados.
- Aprendizagem em ociosidade não equivale a autoalteração irrestrita de código nem atualização automática de pesos sem avaliação.

## Segurança

- Apenas handlers registrados em código confiável são executáveis.
- Payload de tarefa é JSON e limitado a 8 KiB.
- Cada ciclo respeita o limite de ações configurado.
- Resultado exige verificador explícito para concluir uma tarefa automatizada.
- Ações locais/externas continuam sujeitas à aprovação humana conforme `AutonomyPolicy`.
- Não há endpoint de shell arbitrário.
- Falhas não provocam replay automático de operações potencialmente não idempotentes.
- Solicitações e transições ficam persistidas para auditoria.