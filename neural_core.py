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
  /treinar [epocas]                    treino isolado com validação e checkpoint
  /rollback ID                         restaura checkpoint de aprendizagem
  /calibrar-lif                        calibra limiar LIF com split validation
  /calibrar-decoder                    calibra confiança do decoder com split validation
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


def _confirm_action(prompt):
    try:
        answer = input(prompt + " [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\\nOperação cancelada.")
        return False
    return answer in {"s", "sim", "y", "yes"}


def _prepare_ollama(ai):
    manager = ai.ollama
    target_model = "qwen2.5:0.5b"

    if manager.executable() is None:
        print("Ollama não está instalado.")
        if not _confirm_action("Autoriza instalar o Ollama neste computador?"):
            print("Instalação não autorizada; nenhuma alteração foi realizada.")
            return
        result = manager.install()
        if not result.get("ok"):
            print("ERRO na instalação:", result.get("error"))
            return
        print("Ollama instalado:", result.get("executable"))

    ai.language.refresh_models()
    if not ai.language.reachable:
        print("Serviço Ollama indisponível:", ai.language.last_error)
        if not _confirm_action("Autoriza iniciar o serviço local Ollama?"):
            print("Inicialização não autorizada.")
            return
        result = manager.start_service()
        if not result.get("ok"):
            print("ERRO ao iniciar Ollama:", result.get("error"))
            return
        print("Serviço Ollama acessível em", ai.language.host)

    ai.language.refresh_models()
    if target_model not in ai.language.installed_models:
        print("Modelo solicitado:", target_model)
        print("Modelos locais:", ai.language.installed_models or "nenhum")
        if not _confirm_action("Autoriza baixar o modelo Qwen 2.5 0.5B?"):
            print("Download não autorizado; nenhum modelo foi baixado.")
            return
        result = manager.pull_model(target_model)
        if not result.get("ok"):
            print("ERRO no download/verificação do modelo:", result.get("error"))
            return

    try:
        ai.language.select_model(target_model)
    except ValueError as exc:
        print("ERRO ao selecionar o modelo:", exc)
        return

    print("Executando teste real de geração no modelo solicitado...")
    answer = ai.language.generate("Responda somente com a palavra OK.")
    if answer and ai.language.last_used_model == target_model:
        print("SUCESSO: Ollama gerou uma resposta com", ai.language.last_used_model)
        print("Resposta de teste:", answer)
        print("Geração verificada em:", ai.language.last_generation)
    else:
        print("ERRO: não foi possível confirmar o uso do modelo.")
        print("Detalhe:", ai.language.last_error or "modelo retornado não corresponde ao solicitado.")
        print("Status:", ai.ollama.status())


def main():
    ai = NixLMsNeuralCore()
    print("NixLMs Neural Core 0.7 | Episodic Memory")
    initial_models = ai.language.refresh_models()
    print("Ollama:", "API acessível" if ai.language.reachable else "não detectado/indisponível")
    if not ai.language.reachable or "qwen2.5:0.5b" not in initial_models:
        print("Para configurar Ollama e Qwen com autorização, execute /llm preparar.")
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
            print("Gerenciador:", ai.ollama.status())
            if not available:
                print("Diagnóstico:", ai.language.last_error or "Nenhum modelo local disponível.")
                print("Use /llm preparar para instalar/iniciar e baixar o Qwen, sempre com confirmação.")
            continue
        if low == "/llm preparar":
            _prepare_ollama(ai)
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
                imported = ai.learning.dataset.import_jsonl(source)
                if imported:
                    ai.invalidate_lif_calibration()
                print("Registros importados:", imported)
            except (OSError, ValueError) as exc:
                print("Falha ao importar:", exc)
            continue
        if low.startswith("/treinar"):
            parts = low.split()
            try:
                print(ai.learning.train_incremental(int(parts[1]) if len(parts) > 1 else 1))
            except ValueError as exc:
                print("Falha no treinamento:", exc)
            continue
        if low.startswith("/rollback "):
            checkpoint_id = message.split(None, 1)[1].strip()
            try:
                print(ai.learning.restore_incremental_checkpoint(checkpoint_id))
            except (OSError, ValueError) as exc:
                print("Falha no rollback:", exc)
            continue
        if low == "/calibrar-lif":
            try:
                print(ai.learning.calibrate_lif_threshold())
            except ValueError as exc:
                print("Falha na calibração LIF:", exc)
            continue
        if low == "/calibrar-decoder":
            try:
                print(ai.learning.calibrate_decoder_confidence())
            except ValueError as exc:
                print("Falha na calibração do decoder:", exc)
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
                ai.invalidate_lif_calibration()
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
