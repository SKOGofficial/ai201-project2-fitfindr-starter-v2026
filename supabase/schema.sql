-- feature/full-ui branch only. Run once in your Supabase project's SQL
-- editor (Project -> SQL Editor -> New query -> paste -> Run) before
-- starting webapp.py for the first time.
--
-- webapp.py's own DB calls (supabase_client.py) use the service-role key,
-- which bypasses RLS and filters by user_id in application code instead.
-- The policies below are still created, and are correct, in case this
-- project is ever used with a browser-side (anon-key) Supabase client later
-- — they cost nothing to have and mean that path is safe by default rather
-- than needing to be remembered.

create table if not exists wardrobe_items (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  name        text not null,
  category    text not null check (category in ('tops', 'bottoms', 'outerwear', 'shoes', 'accessories')),
  colors      text[] not null default '{}',
  style_tags  text[] not null default '{}',
  notes       text,
  created_at  timestamptz not null default now()
);

create table if not exists search_history (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  query       text not null,
  session     jsonb not null,
  created_at  timestamptz not null default now()
);

create table if not exists favorites (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users (id) on delete cascade,
  item               jsonb not null,
  outfit_suggestion  text,
  fit_card           text,
  created_at         timestamptz not null default now()
);

create index if not exists wardrobe_items_user_id_idx on wardrobe_items (user_id);
create index if not exists search_history_user_id_idx on search_history (user_id);
create index if not exists favorites_user_id_idx on favorites (user_id);

alter table wardrobe_items enable row level security;
alter table search_history enable row level security;
alter table favorites enable row level security;

create policy "own wardrobe items" on wardrobe_items
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "own search history" on search_history
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "own favorites" on favorites
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
