# NixLMs 0.5 — Evolução cognitiva equilibrada

## Intenção
Evoluir a NixLMs de um protótipo de recuperação lexical/contrastiva para uma arquitetura cognitiva experimental mais integrada, preservando execução local, portabilidade e limites claros entre capacidades comprovadas e hipóteses.

## Objetivos
- Melhorar a integridade dos datasets e a validade dos benchmarks, impedindo vazamento entre treino e teste.
- Adicionar um modelo de mundo local com fatos tipados, proveniência, confiança e consulta.
- Adicionar gestão explícita de objetivos e planos com dependências, estados e persistência.
- Oferecer um encoder contextual multilíngue pré-treinado como backend opcional de recuperação semântica, mantendo o encoder nativo treinável.
- Integrar os novos módulos ao agente, CLI, status, documentação e CI.
- Manter operação offline por padrão e não exigir dependências pesadas no núcleo.

## Não objetivos
- Não declarar AGI, consciência, senciência ou compreensão humana.
- Não treinar um Transformer do zero.
- Não baixar modelos automaticamente, nem enviar texto para serviços externos durante inferência.
- Não executar planos ou alterar código/ambientes sem autorização explícita.
- Não remover nem migrar destrutivamente os dados existentes.
- Não alterar `main` nem mesclar branches automaticamente.

## Abordagens consideradas
1. **Somente aprimorar o encoder artesanal:** baixo custo, mas continua limitado a tokens/bigramas e não resolve planejamento nem representação explícita do mundo.
2. **Delegar a cognição a APIs remotas:** potencialmente maior qualidade imediata, mas cria dependência de rede, credenciais, custos, latência e riscos de privacidade.
3. **Arquitetura híbrida local-first (selecionada):** manter o núcleo nativo leve e treinável; adicionar módulos cognitivos locais determinísticos; oferecer encoder pré-treinado opcional carregado apenas de cache/local; usar ferramentas externas apenas no processo de desenvolvimento e nunca como dependência de runtime.

## Arquitetura e decisões
- Python 3.10+, sem dependências obrigatórias adicionais.
- O encoder nativo continua alimentando a rede LIF e recebendo treinamento contrastivo.
- `TransformersSentenceEncoder` será um backend opcional e independente para recuperação semântica, carregado sob demanda, CPU e `local_files_only=True`. A primeira referência recomendada é `intfloat/multilingual-e5-small` (384 dimensões, 118M parâmetros, até 512 tokens, MIT e suporte multilíngue incluindo português; o leaderboard MTEB reporta cerca de 449 MB de memória, não o consumo total do processo); o usuário deverá disponibilizar os arquivos localmente.
- E5 usa prefixos distintos para consulta (`query:`) e conteúdo indexado (`passage:`); a camada de memória deve respeitar esse contrato.
- `WorldModel` armazenará fatos estruturados e suas fontes. Conflitos serão reportados como possíveis inconsistências, nunca resolvidos automaticamente.
- `GoalManager` armazenará objetivos e etapas com dependências; apenas registra e apresenta próximas ações, sem executá-las.
- A importação de datasets será atômica: um erro não pode deixar metade dos registros gravados.
- A avaliação de recuperação deverá usar o mesmo cálculo híbrido da memória e validar a separação dos splits.

## Restrições globais
- Compatibilidade Windows 10/11 e Linux; Python 3.10, 3.11 e 3.12.
- Compatibilidade com computador CPU-only e 8 GB de RAM.
- Nenhuma dependência obrigatória nova.
- Nenhum download automático de modelos.
- Persistência JSON existente, com escrita atômica por arquivo.
- Testes automatizados e CI Windows/Linux.
- Mudanças somente na branch `feature/nixlms-0.5-balanced-evolution`.

## Critérios de aceitação
- Importação JSONL inválida não altera o dataset preexistente.
- Sentenças de pares contrastivos não podem atravessar os splits train/test sem erro explícito.
- O relatório de auditoria identifica vazamentos em datasets antigos.
- Modelo de mundo persiste fatos, permite consulta e expõe possíveis conflitos com proveniência.
- Gestor de objetivos persiste metas, impede conclusão de etapas bloqueadas e retorna somente etapas prontas.
- Backend E5 é lazy, CPU-only e offline por padrão; ausência de dependências/modelos não impede uso do encoder nativo.
- Memória híbrida e benchmark usam semântica de score consistente.
- Toda funcionalidade nova possui testes e documentação; CI deve passar nos ambientes configurados.

## Roadmap posterior
A versão 0.5 estabelece fundações. Próximos incrementos, após medir esta base:
1. Encoder contextual e benchmarks PT-BR/ASSIN com splits oficiais e licença verificada.
2. Memória episódica com eventos, tempo, contexto e consolidação.
3. Raciocínio causal e planejamento hierárquico mais rico.
4. Percepção de imagem e áudio por adaptadores locais opcionais; geração de voz/avatar fica fora do núcleo cognitivo.
5. Integração de ferramentas com sandbox, allowlist, aprovação humana, logs, limites e rollback.
6. Profiling de CPU/RAM e avaliação em Windows/Colab.

## Uso de integrações externas durante o desenvolvimento
GitHub será usado para branch, commits e CI. Exa, Parallel e Firecrawl serão usados para pesquisa técnica e checagem de documentação. Ferramentas de dados serão usadas para revisar métricas e qualidade dos benchmarks. Serviços de voz, imagem, avatar, design e hospedagem só serão acionados quando existir uma entrega concreta que os justifique; não serão criadas contas, recursos pagos, deploys ou assets desnecessários.
