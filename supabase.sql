create table if not exists public.leads (
id text primary key, place_id text unique, name text, category text, address text, city text, state text,
phone text, website text, instagram text, facebook text, tiktok text, maps_url text, photo_url text,
rating numeric, reviews integer, score integer default 0, status text default 'Novo', notes text,
created_at timestamptz default now(), updated_at timestamptz default now());
create index if not exists leads_state_idx on public.leads(state);
create index if not exists leads_score_idx on public.leads(score);
create index if not exists leads_status_idx on public.leads(status);
