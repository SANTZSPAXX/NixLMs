# Interface de voz hands-free

A interface web inclui uma camada de voz no painel Conversar.

## Como iniciar

1. Inicie a interface local normalmente.
2. Abra o painel **Conversar** no Chrome ou Edge atualizado.
3. Pressione **Ativar microfone** uma vez e autorize o acesso ao microfone.
4. Depois disso, fale **“Nix”** antes de cada pergunta ou comando.
5. A resposta é exibida no histórico e lida em voz alta pelo sintetizador do navegador.

O botão de microfone é necessário para conceder permissão. O microfone não é ativado silenciosamente na inicialização.

## Comandos de voz integrados

- “Nix, abrir visão geral/conversa/aprendizagem/biblioteca/frameworks/Hugging Face/diagnóstico/laboratório de mídia”.
- “Nix, atualizar painel”.
- “Nix, executar diagnóstico”.
- “Nix, pesquisar na biblioteca por [termo]”.
- “Nix, repetir”.
- “Nix, silenciar” / “Nix, voltar a falar”.
- “Nix, parar de ouvir”.
- “Nix, desativar modelo de linguagem/geração local/embeddings/visão/áudio”. A desativação exige confirmação falada: “Nix, confirmar” ou “Nix, cancelar”.

Perguntas e pedidos não reconhecidos como comandos da interface são encaminhados ao endpoint conversacional existente.

## Privacidade e compatibilidade

- A captura de voz usa Web Speech API (`SpeechRecognition`/`webkitSpeechRecognition`) em português brasileiro.
- O reconhecimento fornecido pelo navegador pode usar serviço remoto e exigir conexão com a internet. Esta implementação não promete transcrição offline.
- A resposta falada usa `SpeechSynthesis` do navegador/sistema operacional.
- O microfone só inicia após ação explícita do usuário e autorização do navegador.
- O reconhecimento contínuo depende do navegador, permissões, foco/estado da aba e disponibilidade do serviço. Não é um serviço de palavra de ativação do sistema operacional e não funciona com a interface fechada.
- Navegadores sem `SpeechRecognition` continuam podendo usar o chat digitado.
- A API de fala não transforma o núcleo conversacional em um LLM. A qualidade das respostas continua dependendo do motor local e de um modelo generativo opcional configurado.

## Segurança e limites

A camada de voz não executa texto reconhecido como código nem abre um terminal. As ações de interface estão em uma allowlist. Desativar componentes locais existentes exige confirmação verbal. Outras operações sensíveis ou externas não são executadas automaticamente por esta camada.