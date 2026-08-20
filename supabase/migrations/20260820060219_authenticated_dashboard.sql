create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 100),
  role text not null default 'member' check (role in ('member', 'admin')),
  earnings_cycle_started_at timestamptz not null default now(),
  last_earnings_submission_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.campaign_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles (id) on delete set null,
  actor_name_snapshot text not null check (char_length(actor_name_snapshot) between 1 and 100),
  campaign_name text not null check (char_length(campaign_name) between 1 and 160),
  reward_rate numeric(12, 2) check (reward_rate is null or reward_rate >= 0),
  minimum_payout numeric(12, 2) check (minimum_payout is null or minimum_payout >= 0),
  maximum_payout numeric(12, 2) check (maximum_payout is null or maximum_payout >= 0),
  platforms text[] not null check (cardinality(platforms) > 0),
  episode_url text not null check (episode_url ~ '^https?://'),
  available_content text not null default '',
  requirements text not null check (char_length(requirements) > 0),
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'ready', 'failed')),
  current_stage text not null default 'queued'
    check (current_stage in ('queued', 'downloading', 'transcribing', 'selecting', 'rendering', 'ready', 'failed')),
  github_run_id bigint unique,
  github_run_url text,
  output_url text,
  manifest jsonb check (manifest is null or jsonb_typeof(manifest) = 'object'),
  error_stage text,
  error_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  check (minimum_payout is null or maximum_payout is null or minimum_payout <= maximum_payout),
  check (completed_at is null or completed_at >= created_at)
);

create table public.clip_outputs (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.campaign_runs (id) on delete cascade,
  rank smallint not null check (rank between 1 and 15),
  file_name text not null,
  output_url text,
  start_seconds numeric(12, 3) not null check (start_seconds >= 0),
  end_seconds numeric(12, 3) not null,
  duration_seconds numeric(6, 3) not null check (duration_seconds between 15 and 45),
  hook_text text not null,
  virality_score smallint not null check (virality_score between 0 and 100),
  hook_strength smallint not null check (hook_strength between 0 and 100),
  loop_potential smallint not null check (loop_potential between 0 and 100),
  selection_reason text not null,
  source_transcript text not null,
  suggested_caption text not null,
  suggested_hashtags text[] not null default '{}',
  compliance jsonb not null default '{}' check (jsonb_typeof(compliance) = 'object'),
  created_at timestamptz not null default now(),
  unique (run_id, rank),
  check (end_seconds > start_seconds)
);

create table public.run_events (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.campaign_runs (id) on delete cascade,
  stage text not null
    check (stage in ('queued', 'downloading', 'transcribing', 'selecting', 'rendering', 'ready', 'failed')),
  state text not null check (state in ('running', 'complete', 'failed')),
  message text not null check (char_length(message) between 1 and 1000),
  event_at timestamptz not null default now()
);

create table public.commission_accounts (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  agreed_rate numeric(7, 6) check (agreed_rate is null or agreed_rate between 0 and 1),
  total_owed numeric(14, 2) not null default 0 check (total_owed >= 0),
  total_paid numeric(14, 2) not null default 0 check (total_paid >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (total_paid <= total_owed)
);

create table public.earnings_submissions (
  id uuid primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  storage_path text not null unique check (char_length(storage_path) between 40 and 300),
  original_file_name text not null check (char_length(original_file_name) between 1 and 255),
  content_type text not null check (content_type in ('image/jpeg', 'image/png', 'image/webp')),
  byte_size integer not null check (byte_size between 1 and 10485760),
  reporting_period_started_at timestamptz not null,
  reporting_period_ended_at timestamptz not null,
  submitted_at timestamptz not null,
  review_status text not null default 'pending' check (review_status in ('pending', 'reviewed')),
  reviewed_by uuid references public.profiles (id) on delete set null,
  reviewer_name_snapshot text,
  reviewed_at timestamptz,
  confirmed_earnings numeric(14, 2) check (confirmed_earnings is null or confirmed_earnings >= 0),
  commission_rate_snapshot numeric(7, 6)
    check (commission_rate_snapshot is null or commission_rate_snapshot between 0 and 1),
  commission_owed numeric(14, 2) check (commission_owed is null or commission_owed >= 0),
  review_notes text check (review_notes is null or char_length(review_notes) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (reporting_period_ended_at >= reporting_period_started_at)
);

create table public.earnings_reminders (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  cycle_started_at timestamptz not null,
  cycle_day smallint not null check (cycle_day between 0 and 5),
  reminder_slot smallint not null check (reminder_slot between 1 and 2),
  shown_at timestamptz not null default now(),
  dismissed_at timestamptz,
  unique (user_id, cycle_started_at, cycle_day, reminder_slot)
);

create table public.commission_payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  amount numeric(14, 2) not null check (amount > 0),
  paid_at timestamptz not null default now(),
  recorded_by uuid references public.profiles (id) on delete set null,
  recorder_name_snapshot text not null,
  note text check (note is null or char_length(note) <= 1000),
  created_at timestamptz not null default now()
);

create index campaign_runs_user_created_idx on public.campaign_runs (user_id, created_at desc);
create index campaign_runs_active_created_idx on public.campaign_runs (status, created_at desc)
  where status in ('queued', 'processing');
create index clip_outputs_run_idx on public.clip_outputs (run_id);
create index run_events_run_event_idx on public.run_events (run_id, event_at desc);
create index earnings_submissions_user_submitted_idx
  on public.earnings_submissions (user_id, submitted_at desc);
create index earnings_submissions_pending_idx on public.earnings_submissions (submitted_at)
  where review_status = 'pending';
create index earnings_reminders_user_shown_idx on public.earnings_reminders (user_id, shown_at desc);
create index commission_payments_user_paid_idx on public.commission_payments (user_id, paid_at desc);

create or replace function private.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function private.set_updated_at();
create trigger campaign_runs_set_updated_at before update on public.campaign_runs
for each row execute function private.set_updated_at();
create trigger commission_accounts_set_updated_at before update on public.commission_accounts
for each row execute function private.set_updated_at();
create trigger earnings_submissions_set_updated_at before update on public.earnings_submissions
for each row execute function private.set_updated_at();

create or replace function private.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name, earnings_cycle_started_at, created_at)
  values (
    new.id,
    coalesce(nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''),
             nullif(split_part(new.email, '@', 1), ''), 'Team member'),
    coalesce(new.created_at, now()),
    coalesce(new.created_at, now())
  );
  insert into public.commission_accounts (user_id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
for each row execute function private.handle_new_user();

create or replace function private.is_admin()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid()) and role = 'admin'
  );
$$;

create or replace function private.has_dashboard_access()
returns boolean language sql stable security definer set search_path = '' as $$
  select coalesce((
    select now() < earnings_cycle_started_at + interval '7 days'
    from public.profiles where id = (select auth.uid())
  ), false);
$$;

create or replace function public.get_access_status()
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_user_id uuid := auth.uid();
  v_profile public.profiles;
  v_now timestamptz := clock_timestamp();
  v_deadline timestamptz;
  v_locked boolean;
  v_cycle_day smallint;
  v_last_shown timestamptz;
  v_recent_count integer := 0;
  v_day_count integer := 0;
  v_slot smallint;
  v_reminder_id bigint;
begin
  if v_user_id is null then raise exception 'Authentication required'; end if;
  select * into v_profile from public.profiles where id = v_user_id for update;
  if not found then raise exception 'Profile not found'; end if;

  v_deadline := v_profile.earnings_cycle_started_at + interval '7 days';
  v_locked := v_now >= v_deadline;
  v_cycle_day := least(6, greatest(0, floor(extract(epoch from (v_now - v_profile.earnings_cycle_started_at)) / 86400)))::smallint;

  if not v_locked and v_cycle_day between 0 and 5 then
    select max(shown_at), count(*) filter (where shown_at > v_now - interval '24 hours')
      into v_last_shown, v_recent_count
    from public.earnings_reminders where user_id = v_user_id;

    select count(*) into v_day_count from public.earnings_reminders
    where user_id = v_user_id
      and cycle_started_at = v_profile.earnings_cycle_started_at
      and cycle_day = v_cycle_day;

    if v_day_count < 2 and v_recent_count < 2
       and (v_last_shown is null or v_last_shown <= v_now - interval '8 hours') then
      v_slot := (v_day_count + 1)::smallint;
      insert into public.earnings_reminders
        (user_id, cycle_started_at, cycle_day, reminder_slot, shown_at)
      values (v_user_id, v_profile.earnings_cycle_started_at, v_cycle_day, v_slot, v_now)
      on conflict do nothing returning id into v_reminder_id;
    end if;
  end if;

  return jsonb_build_object(
    'schema_version', 1,
    'user_id', v_profile.id,
    'display_name', v_profile.display_name,
    'role', v_profile.role,
    'cycle_started_at', v_profile.earnings_cycle_started_at,
    'deadline_at', v_deadline,
    'last_submission_at', v_profile.last_earnings_submission_at,
    'is_locked', v_locked,
    'cycle_day', v_cycle_day + 1,
    'reminder_due', v_reminder_id is not null,
    'server_time', v_now
  );
end;
$$;

create or replace function public.finalize_earnings_submission(
  p_submission_id uuid,
  p_storage_path text,
  p_original_file_name text,
  p_content_type text,
  p_byte_size integer
)
returns public.earnings_submissions
language plpgsql security definer set search_path = '' as $$
declare
  v_user_id uuid := auth.uid();
  v_now timestamptz := clock_timestamp();
  v_started_at timestamptz;
  v_submission public.earnings_submissions;
begin
  if v_user_id is null then raise exception 'Authentication required'; end if;
  if p_storage_path not like v_user_id::text || '/%' then raise exception 'Invalid screenshot path'; end if;
  if p_content_type not in ('image/jpeg', 'image/png', 'image/webp') then raise exception 'Unsupported screenshot type'; end if;
  if p_byte_size < 1 or p_byte_size > 10485760 then raise exception 'Screenshot must be 10 MiB or smaller'; end if;
  if not exists (
    select 1 from storage.objects
    where bucket_id = 'earnings-screenshots' and name = p_storage_path
  ) then raise exception 'Screenshot upload was not found'; end if;

  select * into v_submission from public.earnings_submissions where id = p_submission_id;
  if found then
    if v_submission.user_id <> v_user_id or v_submission.storage_path <> p_storage_path then
      raise exception 'Submission ID is already in use';
    end if;
    return v_submission;
  end if;

  select earnings_cycle_started_at into v_started_at from public.profiles
  where id = v_user_id for update;
  if not found then raise exception 'Profile not found'; end if;

  insert into public.earnings_submissions (
    id, user_id, storage_path, original_file_name, content_type, byte_size,
    reporting_period_started_at, reporting_period_ended_at, submitted_at
  ) values (
    p_submission_id, v_user_id, p_storage_path, p_original_file_name,
    p_content_type, p_byte_size, v_started_at, v_now, v_now
  ) returning * into v_submission;

  update public.profiles set earnings_cycle_started_at = v_now,
    last_earnings_submission_at = v_now where id = v_user_id;
  return v_submission;
end;
$$;

create or replace function public.admin_set_commission_rate(p_user_id uuid, p_rate numeric)
returns public.commission_accounts
language plpgsql security definer set search_path = '' as $$
declare v_account public.commission_accounts;
begin
  if auth.uid() is null or not private.is_admin() then raise exception 'Admin access required'; end if;
  if p_rate < 0 or p_rate > 1 then raise exception 'Rate must be between 0 and 1'; end if;
  update public.commission_accounts set agreed_rate = p_rate where user_id = p_user_id
  returning * into v_account;
  if not found then raise exception 'Commission account not found'; end if;
  return v_account;
end;
$$;

create or replace function public.admin_review_earnings(
  p_submission_id uuid,
  p_confirmed_earnings numeric,
  p_notes text default null
)
returns public.earnings_submissions
language plpgsql security definer set search_path = '' as $$
declare
  v_admin_id uuid := auth.uid();
  v_admin_name text;
  v_submission public.earnings_submissions;
  v_account public.commission_accounts;
  v_rate numeric(7, 6);
  v_old_owed numeric(14, 2) := 0;
  v_new_owed numeric(14, 2);
begin
  if v_admin_id is null or not private.is_admin() then raise exception 'Admin access required'; end if;
  if p_confirmed_earnings < 0 then raise exception 'Confirmed earnings cannot be negative'; end if;
  select display_name into v_admin_name from public.profiles where id = v_admin_id;
  select * into v_submission from public.earnings_submissions
    where id = p_submission_id for update;
  if not found then raise exception 'Submission not found'; end if;
  select * into v_account from public.commission_accounts
    where user_id = v_submission.user_id for update;
  if v_submission.review_status = 'reviewed' then
    v_rate := v_submission.commission_rate_snapshot;
    v_old_owed := v_submission.commission_owed;
  else
    v_rate := v_account.agreed_rate;
  end if;
  if v_rate is null then raise exception 'Configure the commission rate before review'; end if;
  v_new_owed := round(p_confirmed_earnings * v_rate, 2);
  if v_account.total_owed + v_new_owed - v_old_owed < v_account.total_paid then
    raise exception 'Correction would make paid commission exceed total owed';
  end if;

  update public.earnings_submissions set
    review_status = 'reviewed', reviewed_by = v_admin_id,
    reviewer_name_snapshot = v_admin_name,
    reviewed_at = coalesce(reviewed_at, clock_timestamp()),
    confirmed_earnings = p_confirmed_earnings,
    commission_rate_snapshot = v_rate,
    commission_owed = v_new_owed,
    review_notes = nullif(trim(p_notes), '')
  where id = p_submission_id returning * into v_submission;

  update public.commission_accounts set total_owed = total_owed + v_new_owed - v_old_owed
    where user_id = v_submission.user_id;
  return v_submission;
end;
$$;

create or replace function public.admin_record_payment(
  p_user_id uuid,
  p_amount numeric,
  p_note text default null
)
returns public.commission_payments
language plpgsql security definer set search_path = '' as $$
declare
  v_admin_id uuid := auth.uid();
  v_admin_name text;
  v_account public.commission_accounts;
  v_payment public.commission_payments;
begin
  if v_admin_id is null or not private.is_admin() then raise exception 'Admin access required'; end if;
  if p_amount <= 0 then raise exception 'Payment must be greater than zero'; end if;
  select display_name into v_admin_name from public.profiles where id = v_admin_id;
  select * into v_account from public.commission_accounts where user_id = p_user_id for update;
  if not found then raise exception 'Commission account not found'; end if;
  if p_amount > v_account.total_owed - v_account.total_paid then
    raise exception 'Payment exceeds outstanding commission';
  end if;
  insert into public.commission_payments
    (user_id, amount, recorded_by, recorder_name_snapshot, note)
  values (p_user_id, p_amount, v_admin_id, v_admin_name, nullif(trim(p_note), ''))
  returning * into v_payment;
  update public.commission_accounts set total_paid = total_paid + p_amount where user_id = p_user_id;
  return v_payment;
end;
$$;

alter table public.profiles enable row level security;
alter table public.campaign_runs enable row level security;
alter table public.clip_outputs enable row level security;
alter table public.run_events enable row level security;
alter table public.commission_accounts enable row level security;
alter table public.earnings_submissions enable row level security;
alter table public.earnings_reminders enable row level security;
alter table public.commission_payments enable row level security;

create policy profiles_select_self_or_admin on public.profiles for select to authenticated
using ((id = (select auth.uid()) and (select private.has_dashboard_access())) or (select private.is_admin()));
create policy campaign_runs_select_owner_or_admin on public.campaign_runs for select to authenticated
using ((user_id = (select auth.uid()) and (select private.has_dashboard_access())) or (select private.is_admin()));
create policy clip_outputs_select_owner_or_admin on public.clip_outputs for select to authenticated
using (((select private.has_dashboard_access()) and exists (
  select 1 from public.campaign_runs r where r.id = clip_outputs.run_id and r.user_id = (select auth.uid())
)) or (select private.is_admin()));
create policy run_events_select_owner_or_admin on public.run_events for select to authenticated
using (((select private.has_dashboard_access()) and exists (
  select 1 from public.campaign_runs r where r.id = run_events.run_id and r.user_id = (select auth.uid())
)) or (select private.is_admin()));
create policy commission_accounts_select_owner_or_admin on public.commission_accounts for select to authenticated
using ((user_id = (select auth.uid()) and (select private.has_dashboard_access())) or (select private.is_admin()));
create policy earnings_submissions_select_owner_or_admin on public.earnings_submissions for select to authenticated
using ((user_id = (select auth.uid()) and (select private.has_dashboard_access())) or (select private.is_admin()));
create policy commission_payments_select_owner_or_admin on public.commission_payments for select to authenticated
using ((user_id = (select auth.uid()) and (select private.has_dashboard_access())) or (select private.is_admin()));

create or replace view public.admin_user_stats with (security_invoker = true) as
select p.id, p.display_name, p.role, p.earnings_cycle_started_at, p.last_earnings_submission_at,
  count(r.id)::integer as total_runs,
  count(r.id) filter (where r.status in ('queued', 'processing'))::integer as pending_runs,
  count(r.id) filter (where r.status = 'ready')::integer as completed_runs,
  count(r.id) filter (where r.status = 'failed')::integer as failed_runs
from public.profiles p left join public.campaign_runs r on r.user_id = p.id
group by p.id, p.display_name, p.role, p.earnings_cycle_started_at, p.last_earnings_submission_at;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('earnings-screenshots', 'earnings-screenshots', false, 10485760,
  array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy screenshots_insert_own on storage.objects for insert to authenticated
with check (bucket_id = 'earnings-screenshots'
  and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy screenshots_select_owner_or_admin on storage.objects for select to authenticated
using (bucket_id = 'earnings-screenshots' and (
  ((storage.foldername(name))[1] = (select auth.uid())::text and (select private.has_dashboard_access()))
  or (select private.is_admin())
));

revoke all on public.profiles, public.campaign_runs, public.clip_outputs, public.run_events,
  public.commission_accounts, public.earnings_submissions, public.earnings_reminders,
  public.commission_payments from anon, authenticated;
grant select on public.profiles, public.campaign_runs, public.clip_outputs, public.run_events,
  public.commission_accounts, public.earnings_submissions, public.commission_payments to authenticated;
grant select on public.admin_user_stats to authenticated;
grant usage on schema public to anon, authenticated;

revoke execute on function private.set_updated_at() from public, anon, authenticated;
revoke execute on function private.handle_new_user() from public, anon, authenticated;
revoke execute on function private.is_admin() from public, anon;
revoke execute on function private.has_dashboard_access() from public, anon;
revoke execute on function public.get_access_status() from public, anon;
revoke execute on function public.finalize_earnings_submission(uuid, text, text, text, integer) from public, anon;
revoke execute on function public.admin_set_commission_rate(uuid, numeric) from public, anon;
revoke execute on function public.admin_review_earnings(uuid, numeric, text) from public, anon;
revoke execute on function public.admin_record_payment(uuid, numeric, text) from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.is_admin(), private.has_dashboard_access() to authenticated;
grant execute on function public.get_access_status() to authenticated;
grant execute on function public.finalize_earnings_submission(uuid, text, text, text, integer) to authenticated;
grant execute on function public.admin_set_commission_rate(uuid, numeric) to authenticated;
grant execute on function public.admin_review_earnings(uuid, numeric, text) to authenticated;
grant execute on function public.admin_record_payment(uuid, numeric, text) to authenticated;
