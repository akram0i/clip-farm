from __future__ import annotations

import unittest

from pipeline.download import _google_drive_file_id, _normalize_dropbox_url


class GoogleDriveDetectionTests(unittest.TestCase):
    def test_file_view_url_is_detected(self) -> None:
        url = "https://drive.google.com/file/d/1a2B3c4D5e6F7g8H/view?usp=sharing"
        self.assertEqual(_google_drive_file_id(url), "1a2B3c4D5e6F7g8H")

    def test_open_id_url_is_detected(self) -> None:
        url = "https://drive.google.com/open?id=1a2B3c4D5e6F7g8H"
        self.assertEqual(_google_drive_file_id(url), "1a2B3c4D5e6F7g8H")

    def test_uc_export_url_is_detected(self) -> None:
        url = "https://drive.google.com/uc?export=download&id=1a2B3c4D5e6F7g8H"
        self.assertEqual(_google_drive_file_id(url), "1a2B3c4D5e6F7g8H")

    def test_non_drive_url_is_not_detected(self) -> None:
        self.assertIsNone(_google_drive_file_id("https://www.youtube.com/watch?v=abc123"))


class DropboxNormalizationTests(unittest.TestCase):
    def test_dl_zero_is_rewritten_to_one(self) -> None:
        url = "https://www.dropbox.com/s/abc123/video.mp4?dl=0"
        self.assertEqual(
            _normalize_dropbox_url(url),
            "https://www.dropbox.com/s/abc123/video.mp4?dl=1",
        )

    def test_missing_dl_param_gets_added(self) -> None:
        url = "https://www.dropbox.com/s/abc123/video.mp4"
        self.assertEqual(
            _normalize_dropbox_url(url),
            "https://www.dropbox.com/s/abc123/video.mp4?dl=1",
        )

    def test_existing_dl_one_is_left_alone(self) -> None:
        url = "https://www.dropbox.com/s/abc123/video.mp4?dl=1"
        self.assertEqual(_normalize_dropbox_url(url), url)

    def test_other_query_params_are_preserved(self) -> None:
        url = "https://www.dropbox.com/scl/fi/xyz/video.mp4?rlkey=abc&dl=0"
        result = _normalize_dropbox_url(url)
        self.assertIn("rlkey=abc", result)
        self.assertTrue(result.endswith("dl=1"))

    def test_non_dropbox_url_is_unchanged(self) -> None:
        url = "https://example.com/video.mp4"
        self.assertEqual(_normalize_dropbox_url(url), url)


if __name__ == "__main__":
    unittest.main()
