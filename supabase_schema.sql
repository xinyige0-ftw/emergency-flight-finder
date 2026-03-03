-- Run in Supabase SQL Editor to enable persistent community data.
-- Set env: SUPABASE_URL, SUPABASE_KEY or SUPABASE_ANON_KEY

create table if not exists evac_reports (
  id text primary key,
  reporter text default 'anonymous',
  type text default 'flight_status',
  flight text default '',
  airport text default '',
  message text default '',
  status text default '',
  timestamp timestamptz default now(),
  upvotes int default 0
);

create table if not exists evac_rides (
  id text primary key,
  origin text default '',
  destination text default '',
  departure_time text default '',
  seats int default 1,
  contact text default '',
  notes text default '',
  posted timestamptz default now()
);

-- Flight alert subscriptions (WhatsApp / SMS) — persistent across deploys
create table if not exists flight_alert_subscriptions (
  id uuid primary key default gen_random_uuid(),
  phone text not null unique,
  channel text default 'whatsapp',
  active boolean default true,
  created_at timestamptz default now()
);
create index if not exists idx_flight_alert_subs_active on flight_alert_subscriptions(active) where active = true;

-- Optional: RLS policies (allow anon read/insert for public board)
alter table evac_reports enable row level security;
alter table evac_rides enable row level security;
alter table flight_alert_subscriptions enable row level security;
create policy "Allow anon read" on evac_reports for select using (true);
create policy "Allow anon insert" on evac_reports for insert with check (true);
create policy "Allow anon update" on evac_reports for update using (true);
create policy "Allow anon read" on evac_rides for select using (true);
create policy "Allow anon insert" on evac_rides for insert with check (true);
create policy "Allow service read" on flight_alert_subscriptions for select using (true);
create policy "Allow service insert" on flight_alert_subscriptions for insert with check (true);
create policy "Allow service update" on flight_alert_subscriptions for update using (true);
