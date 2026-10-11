-- Run this in your Supabase SQL editor

create table if not exists tasks (
  id uuid primary key,
  task text not null,
  url text default '',
  status text default 'queued',
  created_at float8 default extract(epoch from now()),
  steps text default '[]',
  result text,
  screenshot text
);

-- Index for fast listing
create index if not exists tasks_created_at_idx on tasks(created_at desc);

-- Enable RLS (Row Level Security) - optional for production
-- alter table tasks enable row level security;
