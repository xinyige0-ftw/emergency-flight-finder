-- Flight alert subscriptions — run in Supabase SQL Editor
-- Set env: SUPABASE_URL, SUPABASE_KEY (or SUPABASE_ANON_KEY)

create table flight_alert_subscriptions (
  id uuid primary key default gen_random_uuid(),
  phone text not null unique,
  channel text default 'whatsapp',
  active boolean default true,
  created_at timestamptz default now()
);

create index idx_flight_alert_subs_active on flight_alert_subscriptions(active) where active = true;

alter table flight_alert_subscriptions enable row level security;
create policy "Allow service read" on flight_alert_subscriptions for select using (true);
create policy "Allow service insert" on flight_alert_subscriptions for insert with check (true);
create policy "Allow service update" on flight_alert_subscriptions for update using (true);
