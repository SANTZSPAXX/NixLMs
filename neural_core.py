#!/usr/bin/env python3
"""Interface de terminal da NixLMs Neural Core 0.3."""
from pathlib import Path
from nixlms_core import NixLMsNeuralCore

HELP="""Comandos:
  /ensinar pergunta => resposta   salva conhecimento e dataset
  /importar arquivo.jsonl         importa dataset JSONL com split train/test
  /status                          estado dos módulos
  /eeg                             bandas sintéticas
  /mapa                            conceitos e associações
  /treinar [epocas]                treino incremental
  /avaliar                         métricas do dataset
  /llm                             disponibilidade do LLM local
  /positivo | /negativo            feedback da última pergunta
  /ajuda | /sair
"""

def main():
    ai=NixLMsNeuralCore()
    print("NixLMs Neural Core 0.3.0 | Cognitive Hybrid Architecture")
    print("LLM local:", "disponível" if ai.language.available() else "não detectado; fallback para memória")
    print("Digite /ajuda para comandos.")
    while True:
        try: msg=input("Você: ").strip()
        except (EOFError,KeyboardInterrupt): print("\nAté logo!"); break
        if not msg: continue
        low=msg.lower()
        if low in {"/sair","/exit","/quit"}: break
        if low=="/ajuda": print(HELP); continue
        if low=="/status": print(ai.status()); continue
        if low=="/eeg": print(ai.last_trace.get("eeg_bands","Envie uma mensagem primeiro.")); continue
        if low=="/mapa":
            print({"concepts":len(ai.mental_map.nodes),"associations":ai.mental_map.associate(ai.last_question,12)}); continue
        if low=="/llm": print(ai.language.status(),"available=",ai.language.available()); continue
        if low.startswith("/importar "):
            source=Path(msg[len("/importar "):].strip()).expanduser()
            try: print("Registros importados:",ai.learning.dataset.import_jsonl(source))
            except (OSError,ValueError) as exc: print("Falha ao importar:",exc)
            continue
        if low.startswith("/treinar"):
            parts=low.split()
            try: print(ai.learning.train(int(parts[1]) if len(parts)>1 else 1))
            except ValueError: print("Informe um número inteiro de épocas.")
            continue
        if low=="/avaliar": print(ai.learning.evaluate()); continue
        if low in {"/positivo","/negativo"}:
            ai.feedback(ai.last_question,low=="/positivo"); print("Feedback aplicado."); continue
        if low.startswith("/ensinar "):
            payload=msg[len("/ensinar "):]
            if "=>" not in payload: print("Use /ensinar pergunta => resposta"); continue
            q,a=payload.split("=>",1)
            try: ai.learn(q,a,add_to_dataset=True); print("Conhecimento salvo, associado ao mapa mental e incluído no dataset.")
            except ValueError as e: print(e)
            continue
        print("NixLMs:",ai.respond(msg))

if __name__=="__main__": main()
