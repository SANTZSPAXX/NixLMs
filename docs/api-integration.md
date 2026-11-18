# NixLMs API — integração universal

A API fornece HTTP/JSON para conectar a NixLMs a aplicações, ferramentas próprias, ambientes virtuais, notebooks, containers e serviços que façam requisições HTTP. Usa somente a biblioteca padrão do Python. Não instala frameworks ou modelos automaticamente.

## Inicialização

Windows PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m nixlms_api.cli keygen --label "minha-ferramenta" --ttl-days 90
python -m nixlms_api.cli serve
```

Linux/macOS:
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m nixlms_api.cli keygen --label minha-ferramenta --ttl-days 90
python -m nixlms_api.cli serve
```

A chave completa aparece uma única vez. Guarde-a em variável de ambiente ou gerenciador de segredos; nunca no Git, frontend ou logs. O banco fica em data/api_keys.sqlite3 ou em NIXLMS_DATA_DIR.

## Endpoints

- GET /health — estado do processo, sem autenticação.
- GET /v1/models — inventário, exige models:read.
- POST /v1/chat/completions — formato básico Chat Completions, exige chat:write.
- POST /v1/chat — formato simples {"message":"..."}, exige chat:write.

Exemplo:
```bash
curl http://127.0.0.1:8766/v1/chat/completions \
  -H "Authorization: Bearer $NIXLMS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nixlms","messages":[{"role":"user","content":"Olá, Nix"}]}'
```

## Integração Python

```python
import os
from nixlms_api.client import NixLMsClient
nix = NixLMsClient(os.environ["NIXLMS_API_KEY"], base_url="http://127.0.0.1:8766")
print(nix.chat("Resuma o estado deste processo."))
```

Qualquer ferramenta com suporte HTTP pode usar Authorization: Bearer. O cliente e o servidor podem estar em ambientes virtuais separados. Execute o servidor no ambiente que contém o runtime e configure a URL no cliente.

## Ambientes

- venv/conda: execute python -m nixlms_api.cli serve no ambiente do runtime.
- Google Colab: execute o servidor no runtime e use o proxy de porta do Colab para acessar 8766. Guarde a chave em Secrets/getpass e não publique o túnel. A sessão é temporária. O caminho ainda precisa de validação em uma sessão Colab real.
- Docker/servidor: exponha a porta apenas em rede privada e coloque proxy TLS na frente.
- Outra máquina: padrão loopback. Para bind remoto, defina NIXLMS_API_ALLOW_REMOTE=1 e NIXLMS_API_HOST explicitamente, somente atrás de HTTPS e firewall. O servidor embutido não implementa TLS.

## Chaves e permissões

```bash
python -m nixlms_api.cli keygen --label automacao --scopes chat:write,models:read --ttl-days 30
python -m nixlms_api.cli keys
python -m nixlms_api.cli revoke nix_XXXXXXXX
```

Escopos: chat:read, chat:write, models:read. As chaves são armazenadas como SHA-256, exibidas somente na criação, expiram opcionalmente e podem ser revogadas. Não há endpoint HTTP para administrar chaves: a administração é local via CLI. Limite padrão: 60 requisições/minuto por chave (NIXLMS_API_RATE_LIMIT). Corpo máximo: 1 MB.

## Limitações atuais

- A API inicializa NixLMsNeuralCore; a geração de linguagem depende do backend configurado no runtime. A API não converte automaticamente o núcleo em um LLM generativo.
- Compatibilidade OpenAI é básica: mensagens e resposta; sem streaming, tool/function calling, embeddings ou suporte integral a parâmetros.
- /health verifica o processo, não a qualidade do modelo.
- Colab e cloud exigem validação no ambiente real; documentação não equivale a teste de implantação.
- SQLite é local; não é armazenamento distribuído para múltiplas réplicas.
