from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.captions import caption_events_for_window, transcript_text_for_window
from pipeline.render import write_ass


class CaptionTests(unittest.TestCase):
    def test_words_are_grouped_and_clipped(self) -> None:
        transcript = [{
            "start": 10,
            "end": 13,
            "text": "This is a useful test.",
            "words": [
                {"start": 10.0, "end": 10.3, "word": "This"},
                {"start": 10.3, "end": 10.5, "word": "is"},
                {"start": 10.5, "end": 10.7, "word": "a"},
                {"start": 10.7, "end": 11.2, "word": "useful"},
                {"start": 11.2, "end": 11.6, "word": "test."},
            ],
        }]
        events = caption_events_for_window(transcript, 10.2, 12)
        self.assertEqual(events[0]["start"], 10.2)
        self.assertLessEqual(max(event["end"] for event in events), 12)
        self.assertTrue(all(len(event["text"].split()) <= 4 for event in events))

    def test_window_text_uses_only_overlapping_words(self) -> None:
        transcript = [{
            "start": 0,
            "end": 4,
            "text": "outside exact words only",
            "words": [
                {"start": 0, "end": 1, "word": "outside"},
                {"start": 1, "end": 2, "word": "exact"},
                {"start": 2, "end": 3, "word": "words"},
                {"start": 3, "end": 4, "word": "only"},
            ],
        }]
        self.assertEqual(transcript_text_for_window(transcript, 1.1, 2.9), "exact words")

    def test_ass_escapes_override_characters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.ass"
            write_ass([{"start": 1, "end": 2, "text": r"Use {this} \ path"}], 1, path)
            content = path.read_text(encoding="utf-8")
            self.assertIn(r"\{this\}", content)
            self.assertIn(r"\\ path", content)


if __name__ == "__main__":
    unittest.main()
