create policy earnings_reminders_deny_client_access
on public.earnings_reminders for all to authenticated
using (false) with check (false);

create index earnings_submissions_reviewed_by_idx
  on public.earnings_submissions (reviewed_by)
  where reviewed_by is not null;
create index commission_payments_recorded_by_idx
  on public.commission_payments (recorded_by)
  where recorded_by is not null;

create or replace view public.admin_user_stats with (security_invoker = true) as
select p.id, p.display_name, p.role, p.earnings_cycle_started_at, p.last_earnings_submission_at,
  count(r.id)::integer as total_runs,
  count(r.id) filter (where r.status in ('queued', 'processing'))::integer as pending_runs,
  count(r.id) filter (where r.status = 'ready')::integer as completed_runs,
  count(r.id) filter (where r.status = 'failed')::integer as failed_runs
from public.profiles p left join public.campaign_runs r on r.user_id = p.id
where (select private.is_admin())
group by p.id, p.display_name, p.role, p.earnings_cycle_started_at, p.last_earnings_submission_at;
