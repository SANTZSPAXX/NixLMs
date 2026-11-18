"""Exemplo de integração de uma ferramenta Python com a NixLMs."""
import os
from nixlms_api.client import NixLMsClient
client=NixLMsClient(api_key=os.environ["NIXLMS_API_KEY"],
    base_url=os.getenv("NIXLMS_API_URL","http://127.0.0.1:8766"))
print(client.chat("Explique a tarefa que esta ferramenta está executando."))
