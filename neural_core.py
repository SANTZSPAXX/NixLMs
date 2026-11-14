#!/usr/bin/env python3
"""Interface de terminal da NixLMs Neural Core 0.7."""
from pathlib import Path
from nixlms_core import NixLMsNeuralCore

HELP = """Comandos:
  /ensinar pergunta => resposta       salva ou atualiza conhecimento
  /ensinar-par texto A || texto B || 1|0
                                      adiciona par contrastivo (1=similar, 0=diferente)
  /importar arquivo.jsonl             importa exemplos QA e pares contrastivos
  /status                              estado dos módulos
  /eeg                                 bandas sintéticas e atividade LIF
  /mapa                                conceitos e associações
  /fato sujeito || relação || objeto [|| fonte]
                                      registra fato com proveniência
  /fato-buscar texto                   pesquisa fatos do modelo de mundo
  /objetivo criar título               cria um objetivo
  /objetivo listar                     lista objetivos
  /objetivo etapa ID || título [|| dependência1,dependência2]
                                      adiciona etapa a um objetivo
  /objetivo concluir ID || ETAPA_ID    conclui etapa liberada
  /objetivo proximos ID                mostra próximas etapas liberadas
  /agenda listar                       lista tarefas agendadas
  /agenda criar HANDLER SEGUNDOS       agenda tarefa recorrente
  /agenda uma-vez HANDLER SEGUNDOS     agenda tarefa única
  /agenda cancelar ID                 cancela tarefa pendente
  /agenda executar                    executa tarefas vencidas agora
  Handlers: memory_housekeeping, dataset_audit, goal_review
  /treinar [epocas]                    treino contrastivo incremental
  /calibrar-lif                        calibra limiar LIF com split validation
  /avaliar                             benchmark offline de recuperação, semântica e respostas
  /avaliar-llm                         benchmark integrado usando o Ollama local (opcional)
  /llm                                 diagnóstico do Ollama local
  /llm usar NOME                       seleciona modelo já instalado
  /positivo | /negativo                feedback da última pergunta
  /ajuda | /sair
"""


def _objective_command(ai, message):
    parts = message.split(None, 2)
    if len(parts) < 2:
        print("Use /objetivo criar|listar|etapa|concluir|proximos ...")
        return
    action = parts[1].lower()
    payload = parts[2] if len(parts) > 2 else ""
    try:
        if action == "criar":
            goal = ai.goals.create_goal(payload)
            print("Objetivo criado:", goal)
        elif action == "listar":
            print(ai.goals.list_goals())
        elif action == "etapa":
            fields = [value.strip() for value in payload.split("||")]
            if len(fields) not in (2, 3):
                print("Use /objetivo etapa ID || título [|| dependência1,dependência2]")
                return
            dependencies = [value.strip() for value in fields[2].split(",") if value.strip()] if len(fields) == 3 else []
            print("Etapa criada:", ai.goals.add_step(fields[0], fields[1], dependencies))
        elif action == "concluir":
            fields = [value.strip() for value in payload.split("||")]
            if len(fields) != 2:
                print("Use /objetivo concluir ID || ETAPA_ID")
                return
            print("Etapa atualizada:", ai.goals.set_step_status(fields[0], fields[1], "completed"))
        elif action == "proximos":
            print(ai.goals.next_actions(payload.strip()))
        else:
            print("Ação desconhecida. Use /ajuda.")
    except ValueError as exc:
        print("Falha no objetivo:", exc)


def _scheduler_command(ai, message):
    parts = message.split()
    if len(parts) < 2:
        print("Use /agenda listar|criar|uma-vez|cancelar|executar ...")
        return
    action = parts[1].lower()
    try:
        if action == "listar":
            print(ai.scheduler.list_jobs())
        elif action == "criar" and len(parts) == 4:
            job_id = ai.scheduler.schedule_interval(parts[2], float(parts[3]))
            print("Tarefa recorrente criada:", job_id)
        elif action == "uma-vez" and len(parts) == 4:
            job_id = ai.scheduler.schedule_once(parts[2], delay_seconds=float(parts[3]))
            print("Tarefa única criada:", job_id)
        elif action == "cancelar" and len(parts) == 3:
            print("Cancelada." if ai.scheduler.cancel(parts[2]) else
                  "Tarefa não encontrada, já iniciada ou não está pendente.")
        elif action == "executar" and len(parts) == 2:
            print("Tarefas processadas:", ai.scheduler.run_due())
        else:
            print("Uso: /agenda listar | criar HANDLER SEGUNDOS | uma-vez HANDLER SEGUNDOS | cancelar ID | executar")
    except (ValueError, TypeError) as exc:
        print("Falha no agendamento:", exc)


def main():
    ai = NixLMsNeuralCore()
    print("NixLMs Neural Core 0.7 | Episodic Memory")
    print("LLM local:", "disponível" if ai.language.available() else "não detectado; fallback para memória")
    print("Digite /ajuda para comandos.")
    ai.scheduler.start()
    while True:
        try:
            msg = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo!")
            break
        if not msg:
            continue
        low = msg.lower()
        if low in {"/sair", "/exit", "/quit"}:
            break
        if low == "/ajuda":
            print(HELP)
            continue
        if low == "/status":
            print(ai.status())
            continue
        if low == "/eeg":
            print(ai.last_trace.get("eeg_bands", "Envie uma mensagem primeiro."))
            if ai.last_trace:
                print("Atividade LIF:", ai.last_trace.get("active_neurons"), "neurônios ativos;", ai.last_trace.get("spike_activity"), "disparos")
            continue
        if low == "/mapa":
            print({"concepts": len(ai.mental_map.nodes), "associations": ai.mental_map.associate(ai.last_question, 12)})
            continue
        if low.startswith("/fato-buscar "):
            print(ai.world_model.search(msg[len("/fato-buscar "):], limit=10))
            continue
        if low.startswith("/fato "):
            fields = [value.strip() for value in msg[len("/fato "):].split("||")]
            if len(fields) not in (3, 4):
                print("Use /fato sujeito || relação || objeto [|| fonte]")
                continue
            try:
                print("Fato registrado:", ai.world_model.assert_fact(
                    fields[0], fields[1], fields[2], source=fields[3] if len(fields) == 4 else "user"
                ))
            except ValueError as exc:
                print("Falha ao registrar fato:", exc)
            continue
        if low.startswith("/agenda"):
            _scheduler_command(ai, msg)
            continue
        if low.startswith("/objetivo"):
            _objective_command(ai, msg)
            continue
        if low == "/llm":
            available = ai.language.available()
            print("Ollama:", "disponível" if available else "indisponível")
            print(ai.language.status())
            if not available:
                print("Diagnóstico:", ai.language.last_error or "Nenhum modelo local disponível.")
            print("Encoder de recuperação:", ai.status()["retrieval_encoder"])
            continue
        if low.startswith("/llm usar "):
            model = msg[len("/llm usar "):].strip()
            try:
                print("Modelo selecionado:", ai.language.select_model(model))
            except ValueError as exc:
                print("Falha ao selecionar modelo:", exc)
            continue
        if low.startswith("/importar "):
            source = Path(msg[len("/importar "):].strip()).expanduser()
            try:
                print("Registros importados:", ai.learning.dataset.import_jsonl(source))
            except (OSError, ValueError) as exc:
                print("Falha ao importar:", exc)
            continue
        if low.startswith("/treinar"):
            parts = low.split()
            try:
                print(ai.learning.train(int(parts[1]) if len(parts) > 1 else 1))
            except ValueError as exc:
                print("Falha no treinamento:", exc)
            continue
        if low == "/calibrar-lif":
            try:
                print(ai.learning.calibrate_lif_threshold())
            except ValueError as exc:
                print("Falha na calibração LIF:", exc)
            continue
        if low in {"/avaliar", "/avaliar-llm"}:
            try:
                print(ai.learning.evaluate(include_llm=low == "/avaliar-llm"))
            except ValueError as exc:
                print("Falha na avaliação:", exc)
            continue
        if low in {"/positivo", "/negativo"}:
            applied = ai.feedback(ai.last_question, low == "/positivo")
            print("Feedback registrado na memória episódica." if applied else
                  "Nenhum episódio correspondente. Envie uma mensagem antes de avaliar.")
            continue
        if low.startswith("/ensinar-par "):
            parts = [part.strip() for part in msg[len("/ensinar-par "):].split("||")]
            if len(parts) != 3:
                print("Use /ensinar-par texto A || texto B || 1 (ou 0)")
                continue
            try:
                ai.learning.dataset.add_pair(parts[0], parts[1], int(parts[2]), "train")
                ai.encoder.fit_vocabulary(parts[:2])
                ai._save_encoder()
                print("Par contrastivo salvo. Execute /treinar para ajustar as representações.")
            except ValueError as exc:
                print("Falha ao adicionar par:", exc)
            continue
        if low.startswith("/ensinar "):
            payload = msg[len("/ensinar "):]
            if "=>" not in payload:
                print("Use /ensinar pergunta => resposta")
                continue
            question, answer = payload.split("=>", 1)
            try:
                ai.learn(question, answer, add_to_dataset=True)
                print("Conhecimento salvo e incluído no dataset.")
            except ValueError as exc:
                print(exc)
            continue
        print("NixLMs:", ai.respond(msg))
    ai.scheduler.stop()


if __name__ == "__main__":
    main()
