-- AI Move Estimator: database schema
-- Run in Supabase > SQL Editor (run 01_schema.sql first, then 02_seed_items.sql)

create extension if not exists "pgcrypto";

-- Removal companies (each one gets its own branded link: /q/<slug>)
create table companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  logo_url text,
  primary_color text default '#1e40af',
  contact_email text,
  contact_phone text,
  created_at timestamptz default now()
);

-- Links logged-in users (company staff) to their company
create table company_users (
  user_id uuid references auth.users(id) on delete cascade,
  company_id uuid references companies(id) on delete cascade,
  role text default 'staff' check (role in ('owner', 'staff')),
  primary key (user_id, company_id)
);

-- Standard item volumes. Grows over time with items found online or entered by customers.
create table item_catalog (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  category text not null,
  aliases text[] default '{}',
  volume_m3 numeric(6,3) not null,
  dismantlable boolean default false,
  dismantled_volume_m3 numeric(6,3),
  heavy boolean default false,
  width_cm numeric,
  depth_cm numeric,
  height_cm numeric,
  source text not null default 'standard' check (source in ('standard', 'web', 'customer')),
  source_url text,
  verified boolean default true,
  created_at timestamptz default now()
);

-- One quote request per customer move
create table quotes (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  customer_name text,
  customer_email text,
  customer_phone text,
  pickup_address text,
  dropoff_address text,
  move_date date,
  -- access details for pickup and dropoff
  pickup_access jsonb default '{}',
  dropoff_access jsonb default '{}',
  status text not null default 'draft'
    check (status in ('draft', 'submitted', 'reviewed', 'quoted', 'completed', 'cancelled')),
  estimated_volume_m3 numeric(6,2),
  estimated_min_m3 numeric(6,2),
  estimated_max_m3 numeric(6,2),
  packing_allowance numeric(4,2) default 0.15,
  suggested_truck text,
  actual_volume_m3 numeric(6,2),   -- filled by the company after the job
  company_notes text,
  created_at timestamptz default now(),
  submitted_at timestamptz,
  completed_at timestamptz
);

-- Photos uploaded by the customer, grouped by room
create table quote_photos (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references quotes(id) on delete cascade,
  room text not null,
  storage_path text not null,
  analysed boolean default false,
  created_at timestamptz default now()
);

-- Each item identified in the move
create table quote_items (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references quotes(id) on delete cascade,
  photo_id uuid references quote_photos(id) on delete set null,
  catalog_item_id uuid references item_catalog(id) on delete set null,
  room text not null,
  name text not null,
  brand_model text,
  quantity int not null default 1,
  volume_m3 numeric(6,3),
  width_cm numeric,
  depth_cm numeric,
  height_cm numeric,
  will_dismantle boolean default false,
  heavy boolean default false,
  -- where the measurement came from
  measure_source text check (measure_source in ('table', 'web', 'customer', 'adjusted')),
  source_url text,
  confidence numeric(3,2),
  needs_customer_input boolean default false,
  created_at timestamptz default now()
);

create index on quotes (company_id, status);
create index on quote_items (quote_id);
create index on quote_photos (quote_id);
create index on item_catalog using gin (aliases);

-- Row Level Security
-- Customers never touch the database directly: the FastAPI backend uses the service key.
-- Company staff log in and only see their own company's data.
alter table companies enable row level security;
alter table company_users enable row level security;
alter table item_catalog enable row level security;
alter table quotes enable row level security;
alter table quote_photos enable row level security;
alter table quote_items enable row level security;

create or replace function is_company_member(cid uuid)
returns boolean language sql security definer stable as $$
  select exists (
    select 1 from company_users
    where company_id = cid and user_id = auth.uid()
  );
$$;

create policy "public can read companies" on companies
  for select using (true);

create policy "members manage own company" on companies
  for update using (is_company_member(id));

create policy "users see own memberships" on company_users
  for select using (user_id = auth.uid());

create policy "anyone reads catalog" on item_catalog
  for select using (true);

create policy "members manage own quotes" on quotes
  for all using (is_company_member(company_id));

create policy "members manage own photos" on quote_photos
  for all using (
    is_company_member((select company_id from quotes where quotes.id = quote_id))
  );

create policy "members manage own items" on quote_items
  for all using (
    is_company_member((select company_id from quotes where quotes.id = quote_id))
  );

-- Storage bucket for customer photos (private)
insert into storage.buckets (id, name, public)
values ('quote-photos', 'quote-photos', false)
on conflict (id) do nothing;
