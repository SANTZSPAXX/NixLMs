# Executar NixLMs no Render

## Serviço web

- Runtime: Python
- Build: `pip install -r requirements.txt`
- Start: `python -m nixlms_web.server`
- Health check: `/api/health`
- Porta: usa automaticamente `PORT` fornecida pelo Render
- Host: `0.0.0.0` somente quando `RENDER=true`; mantém loopback no uso local

## Variáveis obrigatórias

- `NIXLMS_ACCESS_TOKEN`: segredo aleatório com pelo menos 32 caracteres. Configure no painel do Render como Secret. O servidor recusa iniciar no Render se estiver ausente ou for curto.
- `NIXLMS_AUTO_INSTALL_MEDIA=0`: impede instalação automática de dependências opcionais de geração de mídia no boot cloud.

Para gerar um token localmente, use `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Não comite nem compartilhe o token. A interface solicita o token na primeira chamada à API e o mantém apenas em `sessionStorage` da aba.

## Persistência e limites

O armazenamento `data/` é local ao processo. Em um serviço Render sem persistent disk, o estado pode ser perdido em reinicializações, novos deploys ou substituição da instância. Esta configuração é adequada para teste funcional temporário, não para memória persistente de produção. Para preservar biblioteca, memória, modelos e bancos SQLite, será necessário projetar armazenamento persistente e escolher um serviço/plano que suporte o recurso; não habilite disco ou custos sem aprovação.

Modelos grandes, PyTorch, Transformers, Diffusers e geração de mídia não são instalados por padrão. A primeira validação cloud cobre o painel, API autenticada, núcleo padrão, diagnóstico, biblioteca vazia e chat legado. Inferência generativa depende de um provedor/modelo adicional compatível e de recursos suficientes.

## Voz

A interface usa Web Speech API do navegador. A síntese de voz ocorre no dispositivo do usuário. O reconhecimento pode depender de um serviço remoto do navegador; não é inferência de áudio executada no Render nem reconhecimento offline garantido. A palavra de ativação funciona apenas com a página aberta e o navegador mantendo o reconhecimento ativo.

## Segurança

- Todas as rotas `/api/*`, exceto `/api/health`, exigem `Authorization: Bearer <NIXLMS_ACCESS_TOKEN>` no modo Render.
- O token é comparado em tempo constante e nunca deve ser colocado no repositório.
- A página e os assets são públicos; dados e operações da API exigem token.
- Não há terminal remoto nem execução de código fornecido pelo usuário.
- Use HTTPS do Render; o servidor valida a origem HTTPS nas requisições POST quando o cabeçalho Origin está presente.

## Persistência e operação

- Confirme no Dashboard que o disco `nixlms-data` está anexado em `/var/data` antes de importar dados.
- O serviço usa `NIXLMS_DATA_DIR=/var/data`; não salve dados persistentes em caminhos fora desse diretório.
- Verifique `/api/diagnostics` para confirmar que o diretório de dados existe e é gravável.
- Faça um teste real: grave uma memória, importe um documento pequeno, reinicie/reimplante e confirme que ambos continuam disponíveis.
- Exporte periodicamente a biblioteca/memória para cópia externa. Snapshots diários do disco ajudam na recuperação, mas não protegem contra exclusão lógica e não substituem backup independente.

## Teste após deploy

1. Abra `/api/health` e confirme `ok: true`.
2. Abra o painel, faça a primeira chamada e informe o token.
3. Verifique `/api/status`, `/api/diagnostics`, `/api/library` e uma mensagem de chat.
4. Autorize o microfone no navegador e teste a palavra de ativação e a resposta falada.
5. Verifique logs do serviço e teste novamente após reiniciar para observar a limitação de persistência.