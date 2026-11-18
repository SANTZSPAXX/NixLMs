# Percepção multimodal local da NixLMs

A percepção de imagem e fala é opcional e usa modelos já presentes no disco.

## Configuração

Defina, antes de iniciar a NixLMs:

- `NIXLMS_VISION_MODEL_PATH`: diretório local de um modelo Transformers compatível com a tarefa `image-to-text`.
- `NIXLMS_SPEECH_MODEL_PATH`: diretório local de um modelo Transformers compatível com `automatic-speech-recognition`.

Instale manualmente as dependências opcionais necessárias ao modelo. Nenhum modelo
ou pacote é baixado pelo módulo. A inferência é forçada para CPU (`device=-1`).

## Uso

```python
from nixlms_core.perception import PerceptionManager

perception = PerceptionManager()
print(perception.status())
caption = perception.describe_image("C:/dados/foto.png")
transcript = perception.transcribe_audio("C:/dados/audio.wav")
```

## Limites e segurança

- Imagens: PNG, JPEG e WebP; máximo de 10 MiB por padrão.
- Áudio: WAV; máximo de 20 MiB por padrão.
- Os caminhos são fornecidos explicitamente pelo chamador.
- Modelos devem estar em diretórios locais; `local_files_only=True` impede downloads.
- Não há câmera, microfone ou gravação contínua.
- O processamento não envia arquivos a serviços externos.
- O uso de modelos pode consumir RAM e CPU; prefira modelos compactos adequados ao hardware.
- O módulo não afirma reconhecer conteúdo corretamente; resultados devem ser tratados como inferências do modelo.
