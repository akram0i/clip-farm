from __future__ import annotations

import unittest

from pipeline.constraints import (
    derive_constraints,
    merge_required_hashtags,
    validate_candidate_window,
)
from pipeline.errors import ClipFarmError


class ConstraintTests(unittest.TestCase):
    def test_defaults_are_target_window(self) -> None:
        value = derive_constraints("Keep it energetic.")
        self.assertEqual((value.minimum_seconds, value.maximum_seconds), (20.0, 35.0))

    def test_explicit_range_and_requirements_are_extracted(self) -> None:
        value = derive_constraints(
            "Clips must be 18–40 seconds. Must include #OurBrand and mention 'free trial'."
        )
        self.assertEqual((value.minimum_seconds, value.maximum_seconds), (18.0, 40.0))
        self.assertEqual(value.required_hashtags, ("#OurBrand",))
        self.assertEqual(value.required_phrases, ("free trial",))

    def test_absolute_bounds_are_enforced(self) -> None:
        value = derive_constraints("Clips between 5 and 60 seconds")
        self.assertEqual((value.minimum_seconds, value.maximum_seconds), (15.0, 45.0))

    def test_impossible_range_fails(self) -> None:
        with self.assertRaises(ClipFarmError):
            derive_constraints("Maximum 10 seconds")

    def test_candidate_duration_is_rejected(self) -> None:
        constraints = derive_constraints("20 to 35 seconds")
        candidate = {
            "start_seconds": 5,
            "end_seconds": 18,
            "virality_score": 80,
            "hook_strength": 80,
            "loop_potential": 70,
            "campaign_compliant": True,
        }
        self.assertIn("below", validate_candidate_window(candidate, constraints, 300) or "")

    def test_required_hashtags_are_added_without_duplicates(self) -> None:
        value = merge_required_hashtags(["#Fun", "brand"], ("#fun", "#required"))
        self.assertEqual(value, ["#Fun", "#brand", "#required"])


if __name__ == "__main__":
    unittest.main()
