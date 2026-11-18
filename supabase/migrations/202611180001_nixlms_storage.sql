-- NixLMs durable runtime state + vector memory (Supabase Free compatible)
create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists public.nix_runtime_snapshots (
  path text primary key,
  content bytea not null,
  sha256 text not null check (length(sha256) = 64),
  updated_at timestamptz not null default now()
);

create table if not exists public.nix_memory_vectors (
  memory_id text primary key,
  memory_type text not null check (memory_type in ('knowledge', 'episode', 'library')),
  content text not null,
  embedding extensions.vector(64) not null,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists nix_memory_vectors_type_idx
  on public.nix_memory_vectors (memory_type);
create index if not exists nix_memory_vectors_embedding_hnsw_idx
  on public.nix_memory_vectors using hnsw (embedding extensions.vector_cosine_ops);

create or replace function public.match_nix_memory_vectors(
  query_embedding extensions.vector(64),
  match_count integer default 5,
  filter_type text default null
)
returns table (
  memory_id text,
  memory_type text,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
set search_path = public, extensions
as $$
  select v.memory_id, v.memory_type, v.content, v.metadata,
         1 - (v.embedding <=> query_embedding) as similarity
  from public.nix_memory_vectors v
  where filter_type is null or v.memory_type = filter_type
  order by v.embedding <=> query_embedding
  limit greatest(1, least(coalesce(match_count, 5), 20));
$$;

alter table public.nix_runtime_snapshots enable row level security;
alter table public.nix_memory_vectors enable row level security;

-- No anon/authenticated policies: the app uses a server-side PostgreSQL URL.
-- Do not expose the database password or connection URL to browser clients.
revoke all on public.nix_runtime_snapshots from anon, authenticated;
revoke all on public.nix_memory_vectors from anon, authenticated;
revoke all on function public.match_nix_memory_vectors(extensions.vector, integer, text) from public, anon, authenticated;
