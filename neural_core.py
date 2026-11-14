#!/usr/bin/env python3
"""Interface de terminal da NixLMs Neural Core 0.4."""
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
  /treinar [epocas]                    treino contrastivo incremental
  /avaliar                             métricas de recuperação e semântica
  /llm                                 disponibilidade do LLM local
  /positivo | /negativo                feedback da última pergunta
  /ajuda | /sair
"""

def main():
    ai = NixLMsNeuralCore()
    print("NixLMs Neural Core 0.4.0 | Semantic Learning")
    print("LLM local:", "disponível" if ai.language.available() else "não detectado; fallback para memória")
    print("Digite /ajuda para comandos.")
    while True:
        try:
            msg = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\\nAté logo!")
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
        if low == "/llm":
            print(ai.language.status(), "available=", ai.language.available())
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
        if low == "/avaliar":
            print(ai.learning.evaluate())
            continue
        if low in {"/positivo", "/negativo"}:
            ai.feedback(ai.last_question, low == "/positivo")
            print("Feedback aplicado.")
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

if __name__ == "__main__":
    main()
