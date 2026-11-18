# Autodiagnóstico e aprendizado em ociosidade

## Inicialização

Ao executar `python neural_core.py`, a NixLMs executa verificações locais não destrutivas e imprime um relatório. São verificados os módulos essenciais, a capacidade de escrita em `data/`, a integridade dos splits do dataset, a persistência do decoder, o encoder de recuperação e os handlers do scheduler. Ollama é opcional: sua ausência gera aviso, não impede o núcleo local de iniciar.

O diagnóstico classifica o runtime como `ok`, `degraded` ou `failed`. Ele identifica problemas; não apaga, sobrescreve ou tenta reparar automaticamente arquivos de estado potencialmente corrompidos.

## Aprendizado autônomo em ociosidade

O runtime agenda um handler persistente de verificação a cada 60 segundos. O ciclo só tenta aprender após pelo menos cinco minutos sem interação e respeita um intervalo mínimo de 30 minutos entre tentativas.

Antes de treinar, ele:
- audita a integridade e separação dos dados;
- exige pelo menos quatro exemplos QA em `validation`;
- exige dados no split `train`;
- limita o dataset de treino a 500 registros para manter o custo previsível;
- executa no máximo uma época por tentativa.

O treino usa `train_incremental`: o candidato é treinado isoladamente, comparado com o baseline em validation e só promovido quando supera os critérios de qualidade. Checkpoint e rollback continuam sob responsabilidade do mecanismo de aprendizagem. Sem validação suficiente, com vazamento de dados ou orçamento excedido, o ciclo apenas registra o motivo e não altera pesos.

Qualquer nova mensagem reseta o temporizador de ociosidade. O ciclo não usa LLM remoto, não coleta dados externos, não executa shell e não inventa exemplos.

## Comandos

- `/diagnostico`: repetir o autodiagnóstico.
- `/ocioso status`: consultar o estado e o último resultado do ciclo.
- `/status`: consultar o estado completo do runtime.

## Limites

O aprendizado em ociosidade é uma rotina de treinamento incremental sobre dados já presentes no dataset. Não equivale a aprendizagem geral a partir de qualquer conversa: exemplos de validação precisam ser preparados corretamente e o conhecimento novo deve ser fornecido por fontes autorizadas ou curadoria explícita. A execução é limitada e não garante melhoria em toda tentativa.
