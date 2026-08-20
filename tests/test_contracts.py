from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pipeline.callback import notify_status

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_contracts_are_json_schema_objects(self) -> None:
        for path in sorted((ROOT / "contracts").glob("*.schema.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(value["type"], "object")
            self.assertFalse(value.get("additionalProperties", True))

    def test_pipeline_contracts_share_stable_run_id(self) -> None:
        for name in (
            "campaign-dispatch.schema.json",
            "run-status.schema.json",
            "manifest.schema.json",
        ):
            value = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
            self.assertIn("run_id", value["properties"])

    def test_earnings_contracts_expose_access_and_review_boundaries(self) -> None:
        access = json.loads(
            (ROOT / "contracts" / "earnings-access.schema.json").read_text(encoding="utf-8")
        )
        submission = json.loads(
            (ROOT / "contracts" / "earnings-submission.schema.json").read_text(encoding="utf-8")
        )
        review = json.loads(
            (ROOT / "contracts" / "earnings-review.schema.json").read_text(encoding="utf-8")
        )
        self.assertTrue({"is_locked", "deadline_at", "reminder_due"} <= set(access["required"]))
        self.assertEqual(submission["properties"]["unlocked"], {"const": True})
        self.assertNotIn("commission_rate", review["properties"])

    def test_signed_callback_uses_exact_compact_json_body(self) -> None:
        status = {
            "schema_version": 1,
            "run_id": str(uuid4()),
            "stage": "rendering",
            "state": "running",
            "message": "Rendering clips.",
            "updated_at": "2026-08-20T00:00:00+00:00",
        }
        response = MagicMock()
        response.status = 204
        response.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            path.write_text(json.dumps(status), encoding="utf-8")
            with patch.dict(os.environ, {
                "CLIPFARM_CALLBACK_URL": "https://example.com/status",
                "CLIPFARM_CALLBACK_SECRET": "test-secret",
            }, clear=False), patch("urllib.request.urlopen", return_value=response) as urlopen:
                notify_status(path)

        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data), status)
        self.assertTrue(request.headers["X-clipfarm-signature"].startswith("sha256="))


if __name__ == "__main__":
    unittest.main()
