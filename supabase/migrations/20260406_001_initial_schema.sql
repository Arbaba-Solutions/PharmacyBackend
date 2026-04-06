-- Module 1: Initial Supabase schema, RLS policies, and storage setup
-- Source of truth is planned to move to Django models in later modules.

begin;

create extension if not exists pgcrypto;

-- -----------------------------
-- Types
-- -----------------------------
create type public.user_role as enum ('admin', 'pharmacy', 'driver', 'customer');
create type public.order_status as enum (
  'pending_prescription',
  'approved_pending_driver',
  'driver_assigned',
  'drug_purchased',
  'in_delivery',
  'delivered',
  'cancelled',
  'disputed'
);
create type public.prescription_status as enum ('pending', 'approved', 'rejected');
create type public.approver_type as enum ('admin', 'pharmacy');
create type public.driver_transaction_type as enum ('top_up', 'delivery_fee_deduction', 'manual_adjustment');
create type public.notification_channel as enum ('push', 'in_app', 'email', 'sms');
create type public.notification_delivery_state as enum ('queued', 'sent', 'failed');
create type public.order_priority as enum ('normal', 'urgent');
create type public.order_source_mode as enum ('contracted_pharmacy', 'external_sourcing');
create type public.pricing_reference_mode as enum ('pharmacy_to_customer', 'city_center_to_customer');

-- -----------------------------
-- Common helpers
-- -----------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.current_user_role()
returns public.user_role
language sql
stable
security definer
set search_path = public
as $$
  select u.role from public.users u where u.id = auth.uid();
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(public.current_user_role() = 'admin', false);
$$;

-- -----------------------------
-- Core tables
-- -----------------------------
create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  role public.user_role not null,
  full_name text,
  phone text,
  is_active boolean not null default true,
  is_blacklisted boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  default_address text,
  latitude double precision,
  longitude double precision,
  flag_count integer not null default 0 check (flag_count >= 0),
  blacklisted_at timestamptz,
  blacklisted_by uuid references public.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.drivers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  is_approved boolean not null default false,
  is_active boolean not null default true,
  current_balance numeric(12,2) not null default 0 check (current_balance >= 0),
  vehicle_type text,
  last_latitude double precision,
  last_longitude double precision,
  last_location_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.pharmacies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  name text not null,
  contact_phone text,
  address text not null,
  latitude double precision,
  longitude double precision,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.pharmacy_inventory (
  id uuid primary key default gen_random_uuid(),
  pharmacy_id uuid not null references public.pharmacies(id) on delete cascade,
  drug_name text not null,
  description text,
  unit_price numeric(12,2) not null check (unit_price >= 0),
  is_available boolean not null default true,
  last_updated_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (pharmacy_id, drug_name)
);

create table public.delivery_zones (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  min_radius_km numeric(8,2) not null check (min_radius_km >= 0),
  max_radius_km numeric(8,2) not null check (max_radius_km > min_radius_km),
  base_delivery_price numeric(12,2) not null check (base_delivery_price >= 0),
  platform_fee numeric(12,2) not null check (platform_fee >= 0),
  surge_multiplier numeric(4,2) not null default 1.00 check (surge_multiplier >= 1 and surge_multiplier <= 2),
  surge_enabled boolean not null default false,
  pricing_reference_mode public.pricing_reference_mode not null default 'pharmacy_to_customer',
  city_center_latitude double precision,
  city_center_longitude double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(id),
  driver_id uuid references public.drivers(id),
  pharmacy_id uuid references public.pharmacies(id),
  delivery_zone_id uuid not null references public.delivery_zones(id),
  source_mode public.order_source_mode not null default 'contracted_pharmacy',
  priority public.order_priority not null default 'normal',
  status public.order_status not null default 'pending_prescription',
  delivery_address text not null,
  delivery_latitude double precision,
  delivery_longitude double precision,
  estimated_distance_km numeric(8,2),
  drug_cost_total numeric(12,2) not null default 0 check (drug_cost_total >= 0),
  delivery_price numeric(12,2) not null default 0 check (delivery_price >= 0),
  platform_fee numeric(12,2) not null default 0 check (platform_fee >= 0),
  applied_surge_multiplier numeric(4,2) not null default 1.00 check (applied_surge_multiplier >= 1 and applied_surge_multiplier <= 2),
  is_customer_urgent boolean not null default false,
  is_zone_surge_active boolean not null default false,
  accepted_at timestamptz,
  purchased_at timestamptz,
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  inventory_item_id uuid references public.pharmacy_inventory(id) on delete set null,
  drug_name text not null,
  quantity integer not null check (quantity > 0),
  unit_price numeric(12,2) not null check (unit_price >= 0),
  line_total numeric(12,2) generated always as (quantity * unit_price) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.prescriptions (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null unique references public.orders(id) on delete cascade,
  customer_id uuid not null references public.customers(id),
  storage_bucket text not null default 'prescriptions',
  storage_path text not null,
  status public.prescription_status not null default 'pending',
  approved_by_type public.approver_type,
  approved_by_user_id uuid references public.users(id),
  approved_at timestamptz,
  rejected_by_user_id uuid references public.users(id),
  rejected_at timestamptz,
  rejection_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (status <> 'approved') or
    (approved_by_type is not null and approved_by_user_id is not null and approved_at is not null)
  )
);

create table public.driver_balance_transactions (
  id uuid primary key default gen_random_uuid(),
  driver_id uuid not null references public.drivers(id),
  order_id uuid references public.orders(id),
  transaction_type public.driver_transaction_type not null,
  amount numeric(12,2) not null,
  balance_before numeric(12,2) not null,
  balance_after numeric(12,2) not null check (balance_after >= 0),
  initiated_by_user_id uuid references public.users(id),
  note text,
  created_at timestamptz not null default now(),
  check (amount <> 0)
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  order_id uuid references public.orders(id) on delete set null,
  title text not null,
  body text not null,
  channel public.notification_channel not null default 'push',
  delivery_state public.notification_delivery_state not null default 'queued',
  retry_count integer not null default 0 check (retry_count >= 0),
  last_attempt_at timestamptz,
  sent_at timestamptz,
  failure_reason text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.blacklist_log (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(id) on delete cascade,
  order_id uuid references public.orders(id) on delete set null,
  reason text not null,
  incident_count_after integer not null check (incident_count_after >= 0),
  auto_blacklisted boolean not null default false,
  reviewed_by_user_id uuid references public.users(id),
  created_at timestamptz not null default now()
);

create table public.disputes (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  customer_id uuid not null references public.customers(id),
  driver_id uuid not null references public.drivers(id),
  dispute_type text not null,
  description text,
  status text not null default 'open',
  created_by_user_id uuid references public.users(id),
  resolved_by_user_id uuid references public.users(id),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- -----------------------------
-- Indexes
-- -----------------------------
create index idx_users_role on public.users(role);
create index idx_customers_user_id on public.customers(user_id);
create index idx_drivers_user_id on public.drivers(user_id);
create index idx_pharmacy_inventory_pharmacy_id on public.pharmacy_inventory(pharmacy_id);
create index idx_orders_customer_id on public.orders(customer_id);
create index idx_orders_driver_id on public.orders(driver_id);
create index idx_orders_pharmacy_id on public.orders(pharmacy_id);
create index idx_orders_delivery_zone_id on public.orders(delivery_zone_id);
create index idx_orders_status_priority_created_at on public.orders(status, priority, created_at desc);
create index idx_order_items_order_id on public.order_items(order_id);
create index idx_prescriptions_order_id on public.prescriptions(order_id);
create index idx_prescriptions_status_created_at on public.prescriptions(status, created_at asc);
create index idx_driver_balance_transactions_driver_id_created_at on public.driver_balance_transactions(driver_id, created_at desc);
create index idx_notifications_user_id_delivery_state on public.notifications(user_id, delivery_state);
create index idx_blacklist_log_customer_id_created_at on public.blacklist_log(customer_id, created_at desc);
create index idx_disputes_order_id on public.disputes(order_id);

-- -----------------------------
-- Update triggers
-- -----------------------------
create trigger set_users_updated_at
before update on public.users
for each row execute function public.set_updated_at();

create trigger set_customers_updated_at
before update on public.customers
for each row execute function public.set_updated_at();

create trigger set_drivers_updated_at
before update on public.drivers
for each row execute function public.set_updated_at();

create trigger set_pharmacies_updated_at
before update on public.pharmacies
for each row execute function public.set_updated_at();

create trigger set_pharmacy_inventory_updated_at
before update on public.pharmacy_inventory
for each row execute function public.set_updated_at();

create trigger set_delivery_zones_updated_at
before update on public.delivery_zones
for each row execute function public.set_updated_at();

create trigger set_orders_updated_at
before update on public.orders
for each row execute function public.set_updated_at();

create trigger set_order_items_updated_at
before update on public.order_items
for each row execute function public.set_updated_at();

create trigger set_prescriptions_updated_at
before update on public.prescriptions
for each row execute function public.set_updated_at();

create trigger set_notifications_updated_at
before update on public.notifications
for each row execute function public.set_updated_at();

create trigger set_disputes_updated_at
before update on public.disputes
for each row execute function public.set_updated_at();

-- -----------------------------
-- Domain guard functions
-- -----------------------------
create or replace function public.enforce_non_negative_driver_balance()
returns trigger
language plpgsql
as $$
begin
  if new.current_balance < 0 then
    raise exception 'Driver balance cannot be negative';
  end if;
  return new;
end;
$$;

create trigger trg_enforce_non_negative_driver_balance
before insert or update on public.drivers
for each row execute function public.enforce_non_negative_driver_balance();

create or replace function public.approve_prescription(
  p_prescription_id uuid,
  p_approver_type public.approver_type,
  p_approver_user_id uuid
)
returns public.prescriptions
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.prescriptions;
begin
  select *
  into v_row
  from public.prescriptions
  where id = p_prescription_id
  for update;

  if not found then
    raise exception 'Prescription not found';
  end if;

  if v_row.status <> 'pending' then
    raise exception 'Prescription already processed';
  end if;

  update public.prescriptions
  set
    status = 'approved',
    approved_by_type = p_approver_type,
    approved_by_user_id = p_approver_user_id,
    approved_at = now(),
    updated_at = now()
  where id = p_prescription_id
  returning * into v_row;

  update public.orders
  set status = 'approved_pending_driver', updated_at = now()
  where id = v_row.order_id
    and status = 'pending_prescription';

  return v_row;
end;
$$;

-- -----------------------------
-- Row Level Security
-- -----------------------------
alter table public.users enable row level security;
alter table public.customers enable row level security;
alter table public.drivers enable row level security;
alter table public.pharmacies enable row level security;
alter table public.pharmacy_inventory enable row level security;
alter table public.delivery_zones enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.prescriptions enable row level security;
alter table public.driver_balance_transactions enable row level security;
alter table public.notifications enable row level security;
alter table public.blacklist_log enable row level security;
alter table public.disputes enable row level security;

-- users
create policy users_select_self_or_admin on public.users
for select using (id = auth.uid() or public.is_admin());

create policy users_update_self_or_admin on public.users
for update using (id = auth.uid() or public.is_admin())
with check (id = auth.uid() or public.is_admin());

create policy users_insert_admin_only on public.users
for insert with check (public.is_admin());

-- customers
create policy customers_select_self_or_admin on public.customers
for select using (user_id = auth.uid() or public.is_admin());

create policy customers_update_self_or_admin on public.customers
for update using (user_id = auth.uid() or public.is_admin())
with check (user_id = auth.uid() or public.is_admin());

create policy customers_insert_self_or_admin on public.customers
for insert with check (user_id = auth.uid() or public.is_admin());

-- drivers
create policy drivers_select_self_or_admin on public.drivers
for select using (user_id = auth.uid() or public.is_admin());

create policy drivers_update_self_or_admin on public.drivers
for update using (user_id = auth.uid() or public.is_admin())
with check (user_id = auth.uid() or public.is_admin());

create policy drivers_insert_self_or_admin on public.drivers
for insert with check (user_id = auth.uid() or public.is_admin());

-- pharmacies
create policy pharmacies_select_all_authenticated on public.pharmacies
for select using (auth.uid() is not null);

create policy pharmacies_update_admin_or_owner on public.pharmacies
for update using (public.is_admin() or user_id = auth.uid())
with check (public.is_admin() or user_id = auth.uid());

create policy pharmacies_insert_admin_only on public.pharmacies
for insert with check (public.is_admin());

-- pharmacy_inventory
create policy inventory_select_all_authenticated on public.pharmacy_inventory
for select using (auth.uid() is not null);

create policy inventory_mutate_admin_or_pharmacy_owner on public.pharmacy_inventory
for all using (
  public.is_admin()
  or exists (
    select 1 from public.pharmacies p
    where p.id = pharmacy_inventory.pharmacy_id
      and p.user_id = auth.uid()
  )
)
with check (
  public.is_admin()
  or exists (
    select 1 from public.pharmacies p
    where p.id = pharmacy_inventory.pharmacy_id
      and p.user_id = auth.uid()
  )
);

-- delivery_zones
create policy delivery_zones_select_all_authenticated on public.delivery_zones
for select using (auth.uid() is not null);

create policy delivery_zones_admin_write on public.delivery_zones
for all using (public.is_admin())
with check (public.is_admin());

-- orders
create policy orders_select_by_role on public.orders
for select using (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = orders.customer_id and c.user_id = auth.uid())
  or exists (select 1 from public.drivers d where d.id = orders.driver_id and d.user_id = auth.uid())
  or exists (select 1 from public.pharmacies p where p.id = orders.pharmacy_id and p.user_id = auth.uid())
);

create policy orders_insert_customer_or_admin on public.orders
for insert with check (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = orders.customer_id and c.user_id = auth.uid())
);

create policy orders_update_participants_or_admin on public.orders
for update using (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = orders.customer_id and c.user_id = auth.uid())
  or exists (select 1 from public.drivers d where d.id = orders.driver_id and d.user_id = auth.uid())
  or exists (select 1 from public.pharmacies p where p.id = orders.pharmacy_id and p.user_id = auth.uid())
)
with check (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = orders.customer_id and c.user_id = auth.uid())
  or exists (select 1 from public.drivers d where d.id = orders.driver_id and d.user_id = auth.uid())
  or exists (select 1 from public.pharmacies p where p.id = orders.pharmacy_id and p.user_id = auth.uid())
);

-- order_items
create policy order_items_select_by_order_access on public.order_items
for select using (
  exists (
    select 1
    from public.orders o
    where o.id = order_items.order_id
      and (
        public.is_admin()
        or exists (select 1 from public.customers c where c.id = o.customer_id and c.user_id = auth.uid())
        or exists (select 1 from public.drivers d where d.id = o.driver_id and d.user_id = auth.uid())
        or exists (select 1 from public.pharmacies p where p.id = o.pharmacy_id and p.user_id = auth.uid())
      )
  )
);

create policy order_items_write_by_customer_or_admin on public.order_items
for all using (
  public.is_admin()
  or exists (
    select 1 from public.orders o
    join public.customers c on c.id = o.customer_id
    where o.id = order_items.order_id
      and c.user_id = auth.uid()
  )
)
with check (
  public.is_admin()
  or exists (
    select 1 from public.orders o
    join public.customers c on c.id = o.customer_id
    where o.id = order_items.order_id
      and c.user_id = auth.uid()
  )
);

-- prescriptions
create policy prescriptions_select_by_role on public.prescriptions
for select using (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = prescriptions.customer_id and c.user_id = auth.uid())
  or exists (
    select 1
    from public.orders o
    join public.pharmacies p on p.id = o.pharmacy_id
    where o.id = prescriptions.order_id
      and p.user_id = auth.uid()
  )
);

create policy prescriptions_insert_customer_or_admin on public.prescriptions
for insert with check (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = prescriptions.customer_id and c.user_id = auth.uid())
);

create policy prescriptions_update_admin_or_pharmacy on public.prescriptions
for update using (
  public.is_admin()
  or exists (
    select 1
    from public.orders o
    join public.pharmacies p on p.id = o.pharmacy_id
    where o.id = prescriptions.order_id
      and p.user_id = auth.uid()
  )
)
with check (
  public.is_admin()
  or exists (
    select 1
    from public.orders o
    join public.pharmacies p on p.id = o.pharmacy_id
    where o.id = prescriptions.order_id
      and p.user_id = auth.uid()
  )
);

-- driver balance transactions
create policy driver_balance_select_self_or_admin on public.driver_balance_transactions
for select using (
  public.is_admin()
  or exists (
    select 1 from public.drivers d
    where d.id = driver_balance_transactions.driver_id
      and d.user_id = auth.uid()
  )
);

create policy driver_balance_insert_admin_only on public.driver_balance_transactions
for insert with check (public.is_admin());

-- notifications
create policy notifications_select_self_or_admin on public.notifications
for select using (user_id = auth.uid() or public.is_admin());

create policy notifications_insert_admin_only on public.notifications
for insert with check (public.is_admin());

create policy notifications_update_admin_only on public.notifications
for update using (public.is_admin())
with check (public.is_admin());

-- blacklist_log
create policy blacklist_log_select_admin_only on public.blacklist_log
for select using (public.is_admin());

create policy blacklist_log_insert_admin_only on public.blacklist_log
for insert with check (public.is_admin());

-- disputes
create policy disputes_select_participants_or_admin on public.disputes
for select using (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = disputes.customer_id and c.user_id = auth.uid())
  or exists (select 1 from public.drivers d where d.id = disputes.driver_id and d.user_id = auth.uid())
);

create policy disputes_insert_participants_or_admin on public.disputes
for insert with check (
  public.is_admin()
  or exists (select 1 from public.customers c where c.id = disputes.customer_id and c.user_id = auth.uid())
  or exists (select 1 from public.drivers d where d.id = disputes.driver_id and d.user_id = auth.uid())
);

create policy disputes_update_admin_only on public.disputes
for update using (public.is_admin())
with check (public.is_admin());

-- -----------------------------
-- Storage bucket and object policies
-- -----------------------------
insert into storage.buckets (id, name, public)
values ('prescriptions', 'prescriptions', false)
on conflict (id) do nothing;

create policy storage_prescriptions_insert_customer
on storage.objects
for insert
with check (
  bucket_id = 'prescriptions'
  and auth.uid()::text = (storage.foldername(name))[1]
);

create policy storage_prescriptions_select_owner_admin_pharmacy
on storage.objects
for select
using (
  bucket_id = 'prescriptions'
  and (
    auth.uid()::text = (storage.foldername(name))[1]
    or public.is_admin()
    or public.current_user_role() = 'pharmacy'
  )
);

create policy storage_prescriptions_update_owner_or_admin
on storage.objects
for update
using (
  bucket_id = 'prescriptions'
  and (
    auth.uid()::text = (storage.foldername(name))[1]
    or public.is_admin()
  )
)
with check (
  bucket_id = 'prescriptions'
  and (
    auth.uid()::text = (storage.foldername(name))[1]
    or public.is_admin()
  )
);

create policy storage_prescriptions_delete_admin_only
on storage.objects
for delete
using (
  bucket_id = 'prescriptions'
  and public.is_admin()
);

commit;
