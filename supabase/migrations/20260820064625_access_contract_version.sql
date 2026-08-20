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
