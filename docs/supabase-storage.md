# Persistência Supabase + memória vetorial da NixLMs

A implantação gratuita usa o Render Free apenas para executar a aplicação e o Supabase Free como armazenamento durável. O disco do Render é efêmero; não deve ser usado como fonte de verdade.

## Componentes
- PostgreSQL do Supabase: snapshots dos arquivos de estado JSON/JSONL e bancos SQLite do runtime.
- pgvector: embeddings de 64 dimensões gerados pelo encoder nativo da NixLMs.
- HNSW/cosine: recuperação vetorial de conhecimento e episódios.
- `NIXLMS_DATABASE_URL`: URL PostgreSQL privada, usada somente no processo Python do servidor.
- `NIXLMS_REQUIRE_SUPABASE=1`: faz o serviço exigir a conexão e retornar health check 503 se a persistência estiver ausente.

## Configuração do Supabase Free
1. Abra o projeto Supabase `teck` e aguarde o status `ACTIVE_HEALTHY`.
2. Em SQL Editor, execute `supabase/migrations/202611180001_nixlms_storage.sql` (ou aplique a migration via Supabase CLI).
3. Confirme que a extensão `vector` está habilitada e que existem as tabelas `nix_runtime_snapshots` e `nix_memory_vectors`.
4. Em Project Settings / Database / Connect, copie a connection string do **Session pooler** para aplicações hospedadas em redes IPv4. Não publique a senha.

## Configuração do Render Free
No serviço `nixlms-free`, abra Environment e adicione:
- `NIXLMS_DATABASE_URL`: connection string completa do Session pooler (segredo).
- `NIXLMS_REQUIRE_SUPABASE`: `1`.
- `NIXLMS_SUPABASE_SYNC_SECONDS`: `10`.

Não use `service_role` ou chave publishable no browser. A aplicação conecta ao PostgreSQL diretamente no backend; a senha não deve ir para o GitHub, frontend ou logs.

## O que é persistido
O worker restaura snapshots antes de inicializar os módulos e sincroniza alterações em intervalos curtos e ao final de respostas HTTP. Arquivos JSON/JSONL e bancos SQLite são copiados; bancos SQLite usam a API de backup do próprio SQLite. Diretórios de cache, modelos baixados e saídas de mídia são excluídos para proteger a cota gratuita.

A busca vetorial grava conhecimento aprendido e episódios de conversa com embedding de 64 dimensões. A dimensão deve corresponder ao encoder nativo `CoreConfig.input_size=64`; não misture embeddings de modelos diferentes.

## Limites do plano gratuito
- Render Free não oferece disco persistente e pode suspender o processo quando ocioso.
- Supabase Free tem limites de armazenamento/compute e pode pausar projetos com inatividade prolongada.
- Snapshots consomem a cota de banco; grandes modelos e arquivos de mídia não são sincronizados.
- Este desenho não substitui backup externo. Exporte snapshots periodicamente se os dados forem críticos.

## Diagnóstico
- `GET /api/health`: mostra se a persistência está conectada; com `NIXLMS_REQUIRE_SUPABASE=1`, responde 503 se o banco estiver ausente.
- `GET /api/status`: expõe estado da persistência.
- `GET /api/diagnostics`: diagnóstico geral do runtime.