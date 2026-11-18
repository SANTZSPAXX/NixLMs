"""Initial, idempotent engineering roadmap for the NixLMs GoalManager."""

INITIAL_ROADMAP = (
    {
        "title": "NixLMs — confiabilidade e qualidade do núcleo",
        "description": "Aumentar a previsibilidade, cobertura de testes, observabilidade e compatibilidade do runtime.",
        "steps": (
            ("Auditar arquitetura, contratos públicos e estado atual dos módulos", ()),
            ("Expandir testes de regressão para persistência, concorrência e falhas", ("Auditar arquitetura, contratos públicos e estado atual dos módulos",)),
            ("Adicionar diagnósticos estruturados e métricas de saúde dos componentes", ("Expandir testes de regressão para persistência, concorrência e falhas",)),
            ("Validar compatibilidade Windows/Linux e execução com recursos limitados", ("Adicionar diagnósticos estruturados e métricas de saúde dos componentes",)),
        ),
    },
    {
        "title": "NixLMs — memória e aprendizagem verificável",
        "description": "Melhorar memória episódica e semântica com proveniência, avaliação e aprendizagem controlada.",
        "steps": (
            ("Definir métricas e conjuntos de avaliação representativos em PT-BR", ()),
            ("Melhorar deduplicação, relevância e rastreabilidade das memórias", ("Definir métricas e conjuntos de avaliação representativos em PT-BR",)),
            ("Implementar consolidação de memória com prévia e política de retenção", ("Melhorar deduplicação, relevância e rastreabilidade das memórias",)),
            ("Validar aprendizagem incremental com baseline, rollback e métricas protegidas", ("Implementar consolidação de memória com prévia e política de retenção",)),
        ),
    },
    {
        "title": "NixLMs — raciocínio, contexto e modelo de mundo",
        "description": "Desenvolver raciocínio estruturado sem confundir hipóteses, lembranças e fatos verificados.",
        "steps": (
            ("Definir representação tipada para fatos, hipóteses e incerteza", ()),
            ("Adicionar inferência causal limitada com proveniência das premissas", ("Definir representação tipada para fatos, hipóteses e incerteza",)),
            ("Integrar recuperação de contexto com limites e proteção contra prompt injection", ("Adicionar inferência causal limitada com proveniência das premissas",)),
            ("Criar benchmark de raciocínio e abstenção com casos adversariais", ("Integrar recuperação de contexto com limites e proteção contra prompt injection",)),
        ),
    },
    {
        "title": "NixLMs — autonomia segura orientada a objetivos",
        "description": "Evoluir o planner para executar somente handlers tipados e autorizados, com verificação e recuperação.",
        "steps": (
            ("Especificar contratos de handlers tipados, payloads e permissões", ()),
            ("Implementar executor allowlisted com timeout, idempotência e cancelamento", ("Especificar contratos de handlers tipados, payloads e permissões",)),
            ("Adicionar observador de resultados e verificador de critérios de conclusão", ("Implementar executor allowlisted com timeout, idempotência e cancelamento",)),
            ("Implementar recuperação de tarefas interrompidas e reconciliação auditável", ("Adicionar observador de resultados e verificador de critérios de conclusão",)),
            ("Adicionar ciclo contínuo opcional com limites, kill switch e aprovação por política", ("Implementar recuperação de tarefas interrompidas e reconciliação auditável",)),
        ),
    },
    {
        "title": "NixLMs — interface e capacidades multimodais",
        "description": "Preparar interfaces extensíveis para interação multimodal, mantendo privacidade e consentimento explícito.",
        "steps": (
            ("Definir interfaces de entrada e saída independentes de plataforma", ()),
            ("Projetar adaptadores de voz com ativação explícita e indicadores de estado", ("Definir interfaces de entrada e saída independentes de plataforma",)),
            ("Projetar percepção visual com fontes e permissões por sessão", ("Definir interfaces de entrada e saída independentes de plataforma",)),
            ("Validar consumo de CPU, RAM, privacidade e comportamento degradado", ("Projetar adaptadores de voz com ativação explícita e indicadores de estado", "Projetar percepção visual com fontes e permissões por sessão")),
        ),
    },
)


def seed_initial_roadmap(goal_manager):
    """Create missing roadmap goals/steps without replacing operator data.

    Existing goals and steps are matched by exact title. Existing descriptions,
    statuses, IDs, dependencies and progress are preserved.
    """
    created_goals = 0
    created_steps = 0
    goal_ids = {}
    for spec in INITIAL_ROADMAP:
        existing = next(
            (goal for goal in goal_manager.list_goals()
             if goal.get("title") == spec["title"]),
            None,
        )
        if existing is None:
            existing = goal_manager.create_goal(spec["title"], spec["description"])
            created_goals += 1
        goal_id = existing["id"]
        goal_ids[spec["title"]] = goal_id
        known_steps = {
            step.get("title"): step.get("id")
            for step in goal_manager.get_goal(goal_id).get("steps", [])
        }
        for step_title, dependency_titles in spec["steps"]:
            if step_title in known_steps:
                continue
            missing = [title for title in dependency_titles if title not in known_steps]
            if missing:
                raise ValueError(
                    "Não foi possível resolver dependências existentes: "
                    + ", ".join(missing)
                )
            dependencies = [known_steps[title] for title in dependency_titles]
            step = goal_manager.add_step(goal_id, step_title, depends_on=dependencies)
            known_steps[step_title] = step["id"]
            created_steps += 1
    return {
        "created_goals": created_goals,
        "created_steps": created_steps,
        "total_goals": len(goal_manager.list_goals()),
        "roadmap_goals": len(INITIAL_ROADMAP),
    }
