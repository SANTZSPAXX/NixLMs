# Benchmark piloto de recuperação episódica em PT-BR

Este diretório contém um conjunto pequeno, sintético e offline para avaliar a recuperação da NixLMs em português brasileiro.

## Conteúdo

- episodes.jsonl: 50 episódios fictícios, com IDs estáveis e estrutura compatível com EpisodicMemory.
- queries.jsonl: 30 consultas em cinco categorias, divididas entre validation e test.
- qrels.tsv: 32 julgamentos graduados; 2 significa diretamente relevante e 1 significa apoio contextual secundário.
- Consultas sem resposta têm expects_no_answer=true e não possuem linha em qrels.tsv.

As consultas cobrem paráfrases, linguagem coloquial, variações de acentuação/digitação, referências contextuais e abstenção. O corpus e as consultas foram escritos para este piloto; não contêm conversas, dados pessoais ou memórias reais de usuários.

## Rubrica e limites

Os julgamentos são uma curadoria editorial inicial do projeto, não uma anotação independente com múltiplos avaliadores. Casos ambíguos devem ser revisados antes de usar estes números como evidência comparativa externa. Ausência de qrel significa não relevante para esta versão do conjunto.

Este piloto não é uma implementação de MTEB-BR nem uma amostra representativa de todos os domínios do português brasileiro. Ele mede apenas o comportamento da recuperação episódica nos exemplos incluídos. Nenhum limiar mínimo de qualidade é imposto nesta primeira linha de base.

## Fontes metodológicas

- MTEB-BR: benchmark de embeddings com tarefas nativas em português brasileiro — https://mteb-br.org/ e https://github.com/tardellirs/mteb-br
- Paper MTEB-BR — https://arxiv.org/abs/2607.04581
- BEIR, protocolo de avaliação de recuperação e julgamentos de relevância — https://arxiv.org/abs/2104.08663
- Model card multilingual-e5-small, incluindo prefixos query: e passage: — https://huggingface.co/intfloat/multilingual-e5-small

O projeto mantém avaliador próprio com biblioteca padrão do Python; não instala BEIR, MTEB, PyTorch ou Sentence Transformers como dependências obrigatórias.
