# Centro de Controle Visual NixLMs

Execute `iniciar_interface.bat` no Windows ou `python -m nixlms_web.server`.
A interface abre em http://127.0.0.1:8765 e escuta somente no loopback.

## Recursos
- Painel visual com indicadores reais do núcleo conversacional legado e da biblioteca SQLite.
- Conversa ligada a `nixlms.py`.
- Consulta/importação de documentos TXT, MD, RST, PY, JSON, YAML e TOML (até 5 MB).
- Inventário somente de leitura de frameworks e diagnóstico básico.

## Limitações
O mecanismo legado usa recuperação lexical, não é um LLM generativo. Esta versão não executa treinamento autônomo, não instala frameworks e não baixa modelos. O painel de aprendizagem informa os recursos disponíveis sem simular execução.

## Segurança
Sem endpoint de shell. Servidor limitado a 127.0.0.1, uploads em allowlist e tratados como texto não executável. Dados permanecem em data/.
