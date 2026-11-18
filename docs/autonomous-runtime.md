# Runtime autônomo governado

## O que o runtime faz automaticamente

Ao iniciar a NixLMs pelo runtime neural ou pela interface web, `start_runtime()`:

1. executa o autodiagnóstico e prepara o conjunto inicial somente em instalação limpa;
2. registra os handlers locais permitidos;
3. inicia o agendador SQLite persistente;
4. agenda o ciclo de aprendizagem ociosa já existente;
5. agenda `autonomy_cycle`, que consulta objetivos ativos e inicia no máximo o limite de etapas internas liberadas por ciclo;
6. mantém os ciclos recorrentes enquanto o processo da Nix estiver em execução.

O ciclo de autonomia é limitado e idempotente quanto à criação do agendamento. A agenda é persistida em `data/scheduler.sqlite3`, mas o processo da Nix precisa permanecer ativo para executar tarefas. Para iniciar com o Windows, use o atalho ou a opção de inicialização do próprio usuário; este módulo não instala serviço oculto nem altera a inicialização do sistema.

## Configuração

- `NIXLMS_AUTONOMY_ENABLED=1`: ativa o ciclo recorrente (padrão).
- `NIXLMS_AUTONOMY_ENABLED=0`: não cria um novo ciclo automático.
- `NIXLMS_AUTONOMY_INTERVAL_SECONDS=300`: intervalo entre ciclos; limitado a 60–3600 segundos.

## Inicialização automática com o sistema operacional (opcional)

A inicialização no login é uma configuração explícita de uma única vez. Ela usa somente o usuário atual, sem privilégios elevados e sem persistência oculta.

### Windows 10/11

No PowerShell, na pasta do repositório:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-autostart.ps1
```

Se as dependências estiverem em um ambiente virtual, informe o executável desse ambiente:

```powershell
.\scripts\install-autostart.ps1 -Python ".\venv\Scripts\python.exe"
```

A tarefa inicia a interface local no login do usuário. Para remover:

```powershell
.\scripts\remove-autostart.ps1
```

### Linux com systemd de usuário

```bash
PYTHON="$PWD/.venv/bin/python" sh ./scripts/install-autostart.sh
```

Para remover:

```bash
sh ./scripts/remove-autostart.sh
```

O processo roda enquanto a sessão do usuário estiver ativa. O computador precisa estar ligado; isso não depende de uma sessão do ChatGPT. Os scripts não instalam Python, dependências ou modelos e não concedem permissões adicionais. Em ambientes sem systemd de usuário, o script Linux não se aplica.

## Limites funcionais atuais

O planner existente não é um executor geral de tarefas. Ele apenas seleciona etapas já criadas pelo operador, verifica dependências e muda uma etapa liberada de `pending` para `in_progress`. Não inventa objetivos, não interpreta qualquer pedido em plano executável, não realiza pesquisa externa, não executa comandos, não modifica arquivos arbitrários e não conclui uma etapa por conta própria. O estado `in_progress` não significa que o trabalho foi realizado.

Ações locais e externas continuam exigindo adaptadores registrados explicitamente e aprovação humana conforme a política. O LLM não pode transformar texto livre em callbacks executáveis. O ciclo recorrente não altera pesos de modelos por si só; a aprendizagem em ociosidade continua sujeita às verificações, limites e promoção por validação documentados em `docs/startup-diagnostics-idle-learning.md`.

## Próximas capacidades necessárias para autonomia de agente

1. decomposição de objetivos em tarefas tipadas e verificáveis;
2. catálogo de ferramentas com contratos, escopos e limites por ferramenta;
3. executor de tarefas com timeout, cancelamento, idempotência e sandbox;
4. observação de resultados e critérios de conclusão verificáveis;
5. memória de execução e recuperação de falhas sem repetir efeitos colaterais;
6. adaptadores de pesquisa/rede/arquivos com consentimento e allowlists;
7. painel de supervisão com fila de aprovação, estado do ciclo e botão de parada;
8. inicialização opcional com o sistema operacional, explicitamente habilitada pelo usuário.

Essas etapas precisam de implementação e testes separados. Não se deve apresentar a Nix como agente geral autônomo enquanto elas não estiverem concluídas.
