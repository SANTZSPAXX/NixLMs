# NixLMs

**NixLMs 0.1.0** é o primeiro protótipo de uma IA experimental local, feito em Python puro.

## O que existe nesta versão

- Conversa pelo terminal.
- Base de conhecimento local com busca textual TF-IDF/cosseno.
- Aprendizado manual de pares pergunta/resposta.
- Histórico persistente em JSON.
- Funciona sem API, chave, internet ou bibliotecas externas.
- Mesmo código no Windows e no Google Colab.

> **Limitação técnica:** esta versão é um assistente de recuperação de conhecimento com regras simples. Ainda não é um LLM, não possui rede neural generativa e não aprende automaticamente os parâmetros de um modelo. A arquitetura pode evoluir para isso em versões futuras.

## Requisitos

- Python 3.10 ou superior.
- Nenhuma dependência externa.

## Windows

1. Baixe ou clone este repositório.
2. Abra a pasta.
3. Execute `iniciar.bat` ou rode:

```bash
python nixlms.py
```

## Google Colab

Abra um notebook no [Google Colab](https://colab.research.google.com/) e execute:

```python
!git clone https://github.com/SANTZSPAXX/NixLMs.git
%cd NixLMs
!python nixlms.py
```

O Colab inicia uma sessão de terminal interativo. Para usar a IA diretamente em células, importe a classe:

```python
from nixlms import NixLMs
ia = NixLMs()
ia.respond("Olá, NixLMs!")
```

## Comandos

| Comando | Função |
|---|---|
| `/ajuda` | Lista os comandos |
| `/ensinar pergunta => resposta` | Ensina e salva uma resposta |
| `/memoria` | Exibe o tamanho da memória |
| `/sair` | Encerra |

Exemplo:

```text
Você: /ensinar qual é sua função => Sou uma IA experimental em desenvolvimento.
NixLMs: Aprendi e salvei esse conhecimento localmente.
Você: qual é sua função?
NixLMs: Sou uma IA experimental em desenvolvimento.
```

## Estrutura

```text
NixLMs/
├── nixlms.py
├── iniciar.bat
├── requirements.txt
├── README.md
└── data/
    ├── knowledge.json   (criado automaticamente)
    └── history.json     (criado automaticamente)
```

## Segurança e privacidade

As conversas e os conhecimentos são gravados localmente em `data/`. Não há envio de dados para serviços externos. Não coloque senhas, tokens ou informações sensíveis na base de conhecimento.

## Próximas etapas sugeridas

1. Testes automatizados e avaliação de qualidade das respostas.
2. Tokenizador e corpus de treinamento.
3. Pequena rede neural treinável em CPU/GPU.
4. Modelo Transformer causal de pequeno porte.
5. Interface gráfica e memória semântica.
