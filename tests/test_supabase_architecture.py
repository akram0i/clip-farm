from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
).lower()


class SupabaseArchitectureTests(unittest.TestCase):
    def test_required_tables_are_real_migrations(self) -> None:
        for table in (
            "profiles", "campaign_runs", "clip_outputs", "run_events",
            "earnings_submissions", "earnings_reminders",
            "commission_accounts", "commission_payments",
        ):
            self.assertIn(f"create table public.{table}", MIGRATIONS)
            self.assertIn(f"alter table public.{table} enable row level security", MIGRATIONS)

    def test_roles_and_lockout_are_server_enforced(self) -> None:
        self.assertIn("create or replace function private.is_admin()", MIGRATIONS)
        self.assertIn("create or replace function private.has_dashboard_access()", MIGRATIONS)
        self.assertIn("earnings_cycle_started_at + interval '7 days'", MIGRATIONS)
        self.assertIn("where (select private.is_admin())", MIGRATIONS)
        self.assertIn("with (security_invoker = true)", MIGRATIONS)

    def test_submission_unlock_is_not_coupled_to_review(self) -> None:
        function_start = MIGRATIONS.index("create or replace function public.finalize_earnings_submission")
        function_end = MIGRATIONS.index("$$;", function_start)
        function = MIGRATIONS[function_start:function_end]
        self.assertIn("earnings_cycle_started_at = v_now", function)
        self.assertIn("last_earnings_submission_at = v_now", function)
        self.assertNotIn("review_status = 'reviewed'", function)

    def test_screenshots_are_private_and_scoped(self) -> None:
        self.assertIn("'earnings-screenshots', 'earnings-screenshots', false", MIGRATIONS)
        self.assertIn("screenshots_insert_own", MIGRATIONS)
        self.assertIn("(storage.foldername(name))[1] = (select auth.uid())::text", MIGRATIONS)

    def test_member_frontend_has_no_github_configuration(self) -> None:
        frontend = "\n".join(
            (ROOT / "dashboard" / name).read_text(encoding="utf-8")
            for name in ("index.html", "app.js")
        )
        self.assertNotIn("Connect GitHub", frontend)
        self.assertNotIn("api.github.com", frontend)
        edge = (ROOT / "supabase/functions/start-campaign/index.ts").read_text(encoding="utf-8")
        self.assertIn('Deno.env.get("GITHUB_TOKEN")', edge)
        download = (ROOT / "supabase/functions/download-results/index.ts").read_text(encoding="utf-8")
        self.assertIn('.from("campaign_runs")', download)
        self.assertIn("archive_download_url", download)


if __name__ == "__main__":
    unittest.main()
