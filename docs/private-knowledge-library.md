# Biblioteca privada de conhecimento

A NixLMs mantém o acervo em `data/private_library.sqlite3`. A biblioteca é local-first: não baixa documentos, não consulta serviços externos e não executa conteúdo importado.

## Importar materiais locais

Na CLI:

```text
/biblioteca importar C:\NixLMs\biblioteca
/biblioteca importar C:\NixLMs\anotacoes.md
/biblioteca buscar redes neurais
/biblioteca listar
/biblioteca status
```

A primeira versão aceita TXT, Markdown, RST, Python, JSON, YAML e TOML em UTF-8. O limite é 5 MiB por arquivo e 100 arquivos por importação. Arquivos duplicados são detectados por SHA-256. Os documentos são divididos em trechos e indexados com SQLite FTS5 quando disponível; sem FTS5, a pesquisa usa fallback local por texto.

Os trechos relevantes são recuperados como contexto para respostas, com indicação da fonte. A biblioteca não substitui a memória episódica, o modelo de mundo nem o dataset supervisionado.

## Aprendizagem com curadoria

Documentos importados não são convertidos automaticamente em fatos nem usados diretamente para alterar pesos. Para ensinar uma resposta específica:

```text
/biblioteca candidato O que é SQLite? => SQLite é um banco de dados relacional embutido. || documentação local
/biblioteca aprovar ID
/biblioteca exportar datasets/private_library_train.jsonl
/importar datasets/private_library_train.jsonl
```

Todo candidato começa como `pending`. Somente após aprovação explícita é exportado, sempre para o split `train`. Os exemplos de validação precisam ser criados separadamente, com exemplos representativos e sem duplicação ou paráfrases vazadas entre splits. O treinamento incremental existente continua responsável por comparar baseline e candidato; a biblioteca não promove pesos sozinha.

## Persistência e segurança

- Banco SQLite e documentos ficam no diretório local `data/`.
- Nenhum arquivo importado é executado.
- Importação limitada por extensão, tamanho e quantidade.
- Conteúdo duplicado é ignorado.
- A biblioteca não apaga nem altera os arquivos de origem.
- Faça backup de `data/private_library.sqlite3` junto com os demais arquivos de estado.
- A recuperação de conteúdo não comprova que ele é verdadeiro; avalie a fonte antes de aprovar um candidato.
