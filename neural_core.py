#!/usr/bin/env python3
"""Interface de terminal da NixLMs Neural Core."""
from nixlms_core import NixLMsNeuralCore

def main():
    ai=NixLMsNeuralCore()
    print("NixLMs Neural Core 0.2.0 | hybrid / all")
    print("/ajuda /status /eeg /ensinar pergunta => resposta /positivo /negativo /sair")
    last_question=""
    while True:
        try: msg=input("Você: ").strip()
        except (EOFError,KeyboardInterrupt): print("\\nAté logo!"); break
        if not msg: continue
        low=msg.lower()
        if low in {"/sair","/exit","/quit"}: break
        if low=="/ajuda": print("Comandos: /ensinar pergunta => resposta | /status | /eeg | /positivo | /negativo | /sair"); continue
        if low=="/status": print(ai.status()); continue
        if low=="/eeg": print(ai.last_trace.get("eeg_bands","Envie uma mensagem primeiro.")); continue
        if low in {"/positivo","/negativo"}:
            ai.feedback(last_question,low=="/positivo"); print("Feedback aplicado."); continue
        if low.startswith("/ensinar "):
            payload=msg[len("/ensinar "):]
            if "=>" not in payload: print("Use /ensinar pergunta => resposta"); continue
            q,a=payload.split("=>",1)
            try: ai.learn(q,a); print("Conhecimento salvo e rede atualizada.")
            except ValueError as e: print(e)
            continue
        last_question=msg
        print("NixLMs:",ai.respond(msg))

if __name__=="__main__": main()
