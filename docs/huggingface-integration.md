# Hugging Face na NixLMs — modo gratuito, anônimo e local

## Garantias de custo e autenticação

A integração usa o catálogo público do Hub por HTTPS sem cabeçalho de autorização. O runtime força `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`; downloads passam explicitamente `token=False`. Não é solicitado nem criado token, conta, cartão ou assinatura.

A NixLMs não chama Inference Providers, Inference Endpoints, HF Jobs, Sandboxes, GPUs remotas ou Spaces como serviços de inferência. A documentação do Hugging Face descreve Inference Providers como chamadas de API autenticadas e pay-as-you-go; esse caminho não é usado pela NixLMs.

Público e gratuito não significa custo zero de infraestrutura pessoal: downloads usam internet, disco e energia do computador. O software não cria cobrança no Hugging Face nem instala pacotes por conta própria.

## Capacidades integradas

| Capacidade | Estado | Comportamento |
|---|---|---|
| Busca de modelos | Integrada | Pesquisa pública por nome/tarefa e ordenação |
| Busca de datasets | Integrada | Catálogo público e metadados |
| Busca de Spaces | Integrada | Catálogo e link para o Hub; não executa o Space |
| Papers, documentação e Collections | Links no painel | Abrem recursos públicos oficiais no navegador; não executam código nem exigem conta |
| Detalhes e Model/Dataset Cards | Integrada | Licença declarada, tags, tarefa, SHA, arquivos e tamanho |
| Download de modelos | Integrado | Ação explícita, revisão SHA fixa, allowlist e limite de tamanho |
| Download de datasets | Integrado | Ação explícita, apenas arquivos tabulares/textuais permitidos |
| Registro local | Integrado | Manifesto JSON sob `data/huggingface/` |
| Geração com Transformers | Integrada, opcional | Safetensors local, CPU, sem rede |
| Geração GGUF | Integrada, opcional | llama.cpp CPU, arquivo GGUF local |
| Embeddings | Integrada, opcional | Sentence Transformers local, CPU e cache de recuperação invalidado ao trocar encoder |
| Visão e fala | Integradas, opcionais | Modelos image-to-text e automatic-speech-recognition baixados localmente e conectados ao PerceptionManager |
| Datasets/Evaluate/PEFT/TRL/Diffusers/Gradio | Inventário e perfis opcionais | Instalação manual, apenas quando necessário |
| Upload/publicação | Não integrado | Sem token e sem escrita no Hub |
| Repositórios privados/gated | Bloqueados | A NixLMs não solicita nem contorna acesso |
| Execução de código remoto | Bloqueada | Sem `trust_remote_code`, scripts de Spaces ou arquivos executáveis |
| Inferência hospedada/compute remoto | Bloqueada | Sem chamadas pagas ou jobs remotos |

## Interface e CLI

No painel local, abra a aba **Hugging Face** para consultar status, pesquisar modelos/datasets/Spaces, inspecionar detalhes, baixar arquivos permitidos e ativar modelos locais.

Na CLI:

```text
/hf status
/hf buscar model Qwen
/hf buscar model multilingual-e5
/hf buscar dataset Portuguese
/hf buscar space text-to-speech
/hf detalhes model Qwen/Qwen2.5-0.5B-Instruct
/hf baixar model Qwen/Qwen2.5-0.5B-Instruct
/hf ativar Qwen/Qwen2.5-0.5B-Instruct
/hf desativar
/hf ativar-embedding intfloat/multilingual-e5-small
/hf desativar-embedding
/hf ativar-visao autor/modelo-image-to-text
/hf ativar-audio autor/modelo-asr
/hf desativar-visao
/hf desativar-audio
```

O comando `baixar` pede confirmação. No painel, o botão de download também pede confirmação. Nenhum download é disparado pela inicialização.

## Limites e segurança de downloads

- Modelos: limite padrão/teto de 1,5 GiB por repositório.
- Datasets: limite padrão/teto de 512 MiB por repositório.
- O tamanho é estimado pelos metadados do Hub antes da transferência e verificado novamente depois.
- O download é fixado ao SHA informado pelo Hub, não a uma branch móvel.
- Modelos: permite Safetensors, GGUF, ONNX e arquivos de configuração/tokenização necessários. Datasets: Parquet, JSONL, JSON, CSV, TSV e texto.
- Arquivos `.py`, `.bin`, `.pt`, `.pth`, pickle e arquivos compactados não são baixados.
- Repositórios com tamanho de arquivo desconhecido, IDs inválidos, caminho inseguro, acesso privado/gated ou revisão sem SHA são recusados.
- Diretórios existentes nunca são sobrescritos. Os downloads são preparados em pasta temporária e renomeados após validação.
- Model Cards, licenças, descrições e datasets são conteúdo de terceiros, não instruções confiáveis. Confira a licença e a origem antes de uso.

O limite pode ser reduzido na chamada da API, mas não aumentado acima do teto. Para modelos grandes, escolha um quantizado GGUF e instale llama.cpp CPU separadamente. O gerador Transformers aceita somente Safetensors; GGUF usa llama.cpp.

## Inferência local

A geração usa Ollama local primeiro quando disponível; o backend Hugging Face é fallback local. A ativação de geração exige um modelo `text-generation`; embeddings exigem `sentence-similarity`/`feature-extraction`; percepção exige `image-to-text` ou `automatic-speech-recognition`, todos baixados no registro local. O carregamento é lazy, CPU-only, com número de threads e contexto/saída limitados. O gerador Transformers usa `local_files_only=True`, `trust_remote_code=False`, `use_safetensors=True` e `torch.float32`. GGUF usa `llama-cpp-python` em CPU.

Nenhum pedido de geração/percepção é enviado ao Hub. Depois da ativação, a inferência lê somente o diretório local.

Para embeddings, ative um modelo com tarefa `sentence-similarity` ou `feature-extraction` que seja compatível com Sentence Transformers. A referência multilíngue leve é [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), com suporte declarado a português e licença MIT. O encoder nativo é restaurado ao desativar.

Uma opção compacta para experimentar geração é [Qwen/Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct), listado com 494 milhões de parâmetros e licença Apache-2.0. A velocidade e a qualidade em português dependem da CPU e do prompt; avalie antes de substituir qualquer backend. Os dois modelos são sugestões, não downloads automáticos.

## Instalação opcional

O núcleo continua sem dependências ML obrigatórias. Crie um ambiente virtual antes de instalar.

Somente catálogo/download:

```powershell
python -m pip install -r requirements-hf-hub.txt
```

Transformers local (instale PyTorch CPU separadamente, conforme a plataforma):

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-hf-local.txt
```

Outros perfis:
- `requirements-hf-data.txt`: datasets.
- `requirements-hf-eval.txt`: avaliação local.
- `requirements-hf-finetune.txt`: PEFT/TRL para treinamento local; não recomendado no computador de 8 GB sem reduzir modelos e batch size.
- `requirements-hf-image.txt`: Diffusers; modelos de imagem são grandes e CPU pode ser muito lenta.
- `requirements-hf-audio.txt`: ferramentas de áudio.
- `requirements-hf-apps.txt`: Gradio para interfaces locais.
- GGUF: `requirements-ml-llama-cpp.txt`, cuja instalação pode exigir compilação no Windows.

Nenhum desses perfis é instalado automaticamente. Para o computador com 8 GB RAM e sem GPU, priorize Hub + multilingual E5 small; teste um modelo gerador de até 0,5B/quantizado e não instale simultaneamente todos os perfis.

## Datasets e aprendizagem

O download guarda os arquivos em `data/huggingface/datasets/autor/nome`. Não injeta dados automaticamente na memória ou no treinamento. Revise a licença e o conteúdo e importe manualmente arquivos JSONL compatíveis com `/importar CAMINHO`. Outros formatos podem exigir `datasets` e conversão explícita. A validação e o teste devem ser separados; não use os mesmos registros em treino e avaliação.

## Colab e Windows

A integração usa caminhos `pathlib`, HTTP padrão e dependências opcionais, portanto não exige GPU nem token no Colab ou Windows. No Colab, os arquivos ficam na sessão temporária, a menos que sejam copiados para armazenamento persistente. Não foram prometidos testes de runtime real em Colab ou no hardware do operador até a validação específica desses ambientes.
