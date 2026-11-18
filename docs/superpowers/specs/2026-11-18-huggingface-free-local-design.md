# Integração Hugging Face pública e local — Design

## Intenção
Integrar à NixLMs as capacidades do Hugging Face Hub que podem ser usadas sem conta, token ou cobrança: descoberta e leitura de metadados de modelos, datasets e Spaces públicos; inspeção de cards/licenças/arquivos; download explícito e limitado de artefatos públicos; registro local; e inferência local opcional em CPU.

## Objetivos
- Acesso anônimo ao catálogo público do Hub, sem ler, criar ou enviar tokens.
- Descobrir modelos, datasets e Spaces; mostrar licença, tarefa, tamanho, revisão e estado gated.
- Baixar somente após ação explícita do operador, com limite de tamanho, revisão imutável e arquivos seguros.
- Guardar modelos/datasets sob o diretório local da NixLMs e registrar metadados em JSON.
- Permitir ativar um modelo de geração baixado e executá-lo apenas localmente, em CPU, com `trust_remote_code=False`, `local_files_only=True` e pesos Safetensors.
- Tornar o catálogo e os controles acessíveis pela CLI e pelo painel local.
- Preservar o núcleo sem dependências obrigatórias e manter compatibilidade com Windows/Colab.

## Não objetivos / anti-objetivos
- Não usar Inference Providers, Inference Endpoints, Jobs, Sandboxes, GPU remota, APIs pagas ou qualquer serviço de inferência hospedada.
- Não autenticar, pedir token, acessar repositórios privados/gated, aceitar licenças automaticamente, enviar arquivos ou publicar modelos.
- Não executar código de Spaces, scripts de modelos, `trust_remote_code`, pickle ou pesos PyTorch `.bin`.
- Não baixar modelos/datasets automaticamente na inicialização.
- Não fazer fine-tuning automático, nem executar treinamento de terceiros em segundo plano.
- Não prometer execução rápida em CPU ou compatibilidade com qualquer modelo.
- Não instalar pacotes automaticamente.

## Abordagens consideradas
1. **Apenas links e pesquisa remota:** simples, mas não integra downloads, inventário local nem inferência.
2. **Integração Hub completa com download e execução automática:** oferece mais automação, mas introduz riscos de cadeia de suprimentos, downloads inesperados e execução de código.
3. **Catálogo público + downloads explícitos e limitados + execução local opt-in (escolhida):** dá acesso útil ao Hub, preserva controle de custo, dados e hardware e não executa conteúdo remoto.

## Arquitetura escolhida
- Novo módulo `nixlms_core/huggingface.py` com cliente REST anônimo baseado na biblioteca padrão, validação de IDs, metadados, limites, registro local e download via `huggingface_hub` opcional com `token=False`.
- Novo gerador `HuggingFaceLocalGenerator` carregado sob demanda, somente a partir de um diretório local previamente baixado e verificado.
- Integração do gerador como fallback local do `LanguageEngine`; Ollama local continua preferencial quando disponível.
- Rotas HTTP loopback para status, busca, detalhes, download, ativação e desativação.
- Aba Hugging Face no painel e comandos `/hf` na CLI.
- Requirements opcionais separados por capacidade; nenhum pacote novo no requirements base.

## Segurança e limites
- Acesso ao Hub via HTTPS público sem cabeçalho Authorization; `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`; downloads passam `token=False`.
- Só modelos/datasets públicos e não gated. Spaces são apenas catalogados; não executados.
- Download de modelo limitado por padrão a 1.5 GB e dataset a 512 MB, com teto absoluto, revisão SHA pinada e allowlist de extensões; pesos `.bin` e scripts `.py` são excluídos.
- Ativação de geração exige `config.json` e ao menos um `.safetensors`; CPU, threads limitadas, contexto/saída limitados.
- `trust_remote_code=False`, `local_files_only=True`, `use_safetensors=True`; nenhuma chamada remota durante geração.
- Downloads e imports são explícitos; falhas não apagam conteúdo já existente.
- Model cards/licenças são exibidos como dados não confiáveis; cabe ao operador conferir permissões de uso.

## Critérios de aceite
- Núcleo importa e testa sem `huggingface_hub`, `datasets`, `transformers` ou `torch`.
- Busca e detalhes públicos podem ser testados com HTTP mock; nenhum token é enviado.
- Rejeita IDs inválidos, modelos gated/privados, tipos não suportados, arquivos inseguros e downloads acima do limite.
- Download chama snapshot_download com token=False, SHA fixado e allowlist.
- Ativação só aceita modelos locais com Safetensors e config; gerador não acessa rede e não executa código remoto.
- Rotas exigem loopback e validação de entrada; CLI e painel exibem erros sem expor tokens.
- Testes da matriz CI e CodeQL passam antes de merge.
- Nenhum recurso pago ou remoto de computação é acionado.
