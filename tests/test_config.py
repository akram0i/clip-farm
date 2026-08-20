from __future__ import annotations

import unittest
from uuid import uuid4

from pipeline.config import Campaign
from pipeline.errors import ClipFarmError


def valid_payload() -> dict:
    return {
        "schema_version": 1,
        "run_id": str(uuid4()),
        "campaign_name": "Demo",
        "episode_url": "https://example.com/video",
        "platforms": ["youtube", "tiktok"],
        "requirements": "20–35 seconds. Include #demo.",
        "reward_rate": "2.5",
    }


class CampaignTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        campaign = Campaign.from_dict(valid_payload())
        self.assertEqual(campaign.reward_rate, 2.5)
        self.assertEqual(campaign.platforms, ("youtube", "tiktok"))

    def test_invalid_url(self) -> None:
        payload = valid_payload()
        payload["episode_url"] = "javascript:alert(1)"
        with self.assertRaises(ClipFarmError):
            Campaign.from_dict(payload)

    def test_invalid_run_id(self) -> None:
        payload = valid_payload()
        payload["run_id"] = "owned-by-the-browser"
        with self.assertRaises(ClipFarmError):
            Campaign.from_dict(payload)

    def test_payout_order(self) -> None:
        payload = valid_payload()
        payload["minimum_payout"] = 100
        payload["maximum_payout"] = 20
        with self.assertRaises(ClipFarmError):
            Campaign.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
