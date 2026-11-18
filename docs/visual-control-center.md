# Centro de Controle Visual NixLMs

## Windows / servidor privado no computador

Não exige bibliotecas Python extras. Requer Python 3.10+.

1. Extraia/clone o repositório.
2. Abra o CMD na pasta `NixLMs`.
3. Execute `py -3 -m nixlms_web.server` (ou `python -m nixlms_web.server`).
4. Abra `http://127.0.0.1:8765` no navegador.
5. Para encerrar, volte ao CMD e pressione `Ctrl+C`.

Alternativamente, execute `iniciar_interface.bat`, que inicia o servidor e abre o navegador.

O servidor escuta exclusivamente em `127.0.0.1`: não fica disponível para outros computadores da rede. Para acesso remoto, use uma VPN/túnel autenticado e uma configuração de proxy reverso revisada; não altere o bind para `0.0.0.0` sem autenticação.

## Google Colab

A interface pode ser aberta no runtime do Colab usando o proxy de portas autenticado do próprio Colab. O runtime do Colab é remoto e temporário; os dados gravados em `data/` pertencem à sessão e podem ser perdidos ao encerrar/reiniciar o runtime. Isso não transforma o Colab em servidor privado permanente.

Em uma célula:

```python
!git clone https://github.com/SANTZSPAXX/NixLMs.git
%cd NixLMs
```

Em outra célula, inicie o servidor e abra a janela proxy:

```python
import os
import threading
from http.server import ThreadingHTTPServer

os.environ["NIXLMS_COLAB_PROXY"] = "1"
from nixlms_web.server import Handler

server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

from google.colab import output
output.serve_kernel_port_as_window(8765)
```

O modo Colab aceita o Host/Origin encaminhado pelo proxy apenas quando a conexão chega ao socket pelo loopback do runtime. Não exponha diretamente a porta do servidor.

## Recursos

- Dashboard com indicadores reais do núcleo legado e da biblioteca SQLite.
- Conversa ligada a `nixlms.py`.
- Consulta/importação de documentos TXT, MD, RST, PY, JSON, YAML e TOML (até 5 MB).
- Inventário leve de frameworks por detecção de instalação, sem importar os pacotes.
- Diagnóstico básico do ambiente.

## Limitações

O chat usa recuperação lexical e regras simples; não é um LLM generativo. A biblioteca privada indexa documentos para pesquisa, mas não os transforma automaticamente em pesos de modelo. Esta interface não inicia treinamento autônomo, não instala frameworks e não baixa modelos.

## Segurança

- Bind local em `127.0.0.1`.
- Sem endpoint de execução de comandos.
- Uploads restritos a formatos textuais permitidos e limitados a 5 MB; conteúdo não é executado.
- O modo Colab depende do proxy autenticado do próprio Colab e exige conexão local do proxy ao runtime.
- Dados são armazenados em `data/`.
