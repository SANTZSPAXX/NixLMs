#!/usr/bin/env python3
"""NixLMs 0.1 — assistente local experimental, sem APIs ou dependências externas.

Este protótipo usa recuperação de conhecimento por similaridade lexical (TF-IDF/cosseno),
regras simples e memória persistente. Não é ainda um LLM nem uma rede neural generativa.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.json"
HISTORY_FILE = DATA_DIR / "history.json"
BOT_NAME = "NixLMs"
VERSION = "0.1.0"

DEFAULT_KNOWLEDGE = [
    {"question": "oi olá bom dia boa tarde boa noite", "answer": "Olá! Eu sou a NixLMs. Como posso ajudar?"},
    {"question": "quem é você qual seu nome", "answer": "Sou a NixLMs, uma IA experimental local em desenvolvimento."},
    {"question": "o que você consegue fazer", "answer": "Nesta versão consigo conversar, recuperar respostas ensinadas, guardar histórico e aprender pares de pergunta e resposta."},
    {"question": "como você funciona", "answer": "Uso regras simples e busca por similaridade textual para encontrar respostas na minha base local. Ainda não sou um grande modelo de linguagem."},
    {"question": "obrigado valeu agradeço", "answer": "Por nada! Estou aqui para ajudar."},
    {"question": "tchau até logo adeus", "answer": "Até logo! Nossa conversa ficará salva localmente."},
]

STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "que", "e", "ou",
    "é", "ser", "sou", "eu", "você", "voce", "me", "minha", "meu", "seu", "sua",
    "como", "qual", "quais", "quando", "onde", "porque", "porquê", "isso", "essa",
    "esse", "isto", "ao", "à", "às", "aos", "já", "mais", "muito", "pode", "poderia"
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w not in STOPWORDS and len(w) > 1]


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class NixLMs:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.knowledge = load_json(KNOWLEDGE_FILE, DEFAULT_KNOWLEDGE.copy())
        self.history = load_json(HISTORY_FILE, [])
        if not isinstance(self.knowledge, list):
            self.knowledge = DEFAULT_KNOWLEDGE.copy()
        if not self.knowledge:
            self.knowledge = DEFAULT_KNOWLEDGE.copy()

    def learn(self, question: str, answer: str) -> None:
        question, answer = question.strip(), answer.strip()
        if not question or not answer:
            raise ValueError("Pergunta e resposta não podem ficar vazias.")
        self.knowledge.append({"question": question, "answer": answer})
        save_json(KNOWLEDGE_FILE, self.knowledge)

    def similarity(self, query: str, document: str) -> float:
        q, d = tokenize(query), tokenize(document)
        if not q or not d:
            return 0.0
        docs = [tokenize(item["question"]) for item in self.knowledge]
        n = max(1, len(docs))
        df = Counter(token for doc in docs for token in set(doc))
        q_count, d_count = Counter(q), Counter(d)
        vocabulary = set(q_count) | set(d_count)

        def weight(term: str, count: int) -> float:
            idf = math.log(1 + (n / (1 + df.get(term, 0))))
            return (1 + math.log(count)) * idf

        qv = {t: weight(t, q_count[t]) for t in vocabulary if q_count[t]}
        dv = {t: weight(t, d_count[t]) for t in vocabulary if d_count[t]}
        dot = sum(qv.get(t, 0.0) * dv.get(t, 0.0) for t in vocabulary)
        qnorm = math.sqrt(sum(v * v for v in qv.values()))
        dnorm = math.sqrt(sum(v * v for v in dv.values()))
        return dot / (qnorm * dnorm) if qnorm and dnorm else 0.0

    def respond(self, message: str) -> str:
        clean = message.strip()
        if not clean:
            return "Digite uma mensagem para começarmos."
        normalized = normalize(clean)

        if normalized in {"oi", "ola", "bom dia", "boa tarde", "boa noite"}:
            answer = "Olá! Como posso ajudar?"
        else:
            ranked = [
                (self.similarity(clean, item.get("question", "")), item)
                for item in self.knowledge
            ]
            score, best = max(ranked, key=lambda pair: pair[0], default=(0.0, None))
            if best and score >= 0.22:
                answer = best["answer"]
            elif any(word in normalized.split() for word in ("hora", "data", "hoje")):
                answer = f"Data e horário deste computador: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}."
            else:
                answer = (
                    "Ainda não tenho uma resposta confiável para isso. "
                    "Você pode me ensinar usando /ensinar pergunta => resposta."
                )

        self.history.append({
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "user": clean,
            "assistant": answer,
        })
        save_json(HISTORY_FILE, self.history)
        return answer

    def show_memory(self) -> str:
        return (
            f"Conhecimentos: {len(self.knowledge)}\n"
            f"Mensagens registradas: {len(self.history)}\n"
            f"Arquivos: {KNOWLEDGE_FILE} e {HISTORY_FILE}"
        )


def main() -> None:
    ai = NixLMs()
    print(f"\n{BOT_NAME} {VERSION} — IA experimental local")
    print("Digite /ajuda para ver os comandos. Digite /sair para encerrar.\n")
    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNixLMs: Até logo!")
            break

        if not message:
            continue
        command = message.lower()

        if command in {"/sair", "/exit", "/quit"}:
            print("NixLMs: Até logo!")
            break
        if command == "/ajuda":
            print("NixLMs: Comandos disponíveis:")
            print("  /ensinar pergunta => resposta  salva um conhecimento")
            print("  /memoria                       mostra os dados salvos")
            print("  /ajuda                         mostra esta ajuda")
            print("  /sair                          encerra o programa")
            continue
        if command == "/memoria":
            print("NixLMs:", ai.show_memory())
            continue
        if command.startswith("/ensinar "):
            payload = message[len("/ensinar "):]
            if "=>" not in payload:
                print("NixLMs: Use /ensinar pergunta => resposta")
                continue
            question, answer = payload.split("=>", 1)
            try:
                ai.learn(question, answer)
                print("NixLMs: Aprendi e salvei esse conhecimento localmente.")
            except ValueError as exc:
                print("NixLMs:", exc)
            continue

        print("NixLMs:", ai.respond(message))


if __name__ == "__main__":
    main()
