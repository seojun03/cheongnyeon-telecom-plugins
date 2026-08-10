from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


selector = load_module("select_topic_idea", SKILL_DIR / "scripts" / "select_topic_idea.py")
recorder = load_module("record_article_state", SKILL_DIR / "scripts" / "record_article_state.py")


class TopicIdeaLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.library = json.loads((SKILL_DIR / "references" / "topic-idea-library.json").read_text(encoding="utf-8"))

    def test_catalog_has_all_188_compact_profiles(self) -> None:
        articles = self.library["articles"]
        self.assertEqual(len(articles), 188)
        self.assertEqual(self.library["source"]["observedPublicPostCount"], 188)
        self.assertEqual(len({article["id"] for article in articles}), 188)
        self.assertEqual(len({article["sourceUrl"] for article in articles}), 188)
        for article in articles:
            self.assertTrue(article["sourceFactsBlocked"])
            self.assertNotIn("analysisText", article)
            self.assertNotIn("body", article)
            self.assertTrue(article["answerAgenda"])
            self.assertTrue(article["titlePatternId"])

    def test_selector_avoids_recent_dimensions_and_returns_registered_master(self) -> None:
        state = {
            "maxEntries": 3,
            "entries": [
                {
                    "ideaType": "price-mechanism",
                    "titlePatternId": "keyword-specific-promise",
                    "ideaReferenceUrl": self.library["articles"][0]["sourceUrl"],
                    "writingMasterId": "price-reader-objections-01",
                }
            ],
        }
        chosen = selector.select_ideas(self.library, state, "광주 휴대폰 매장", count=3, seed="test-seed")
        self.assertEqual(len(chosen), 3)
        self.assertEqual(len({item["ideaReferenceUrl"] for item in chosen}), 3)
        self.assertNotIn(self.library["articles"][0]["sourceUrl"], {item["ideaReferenceUrl"] for item in chosen})
        self.assertTrue(all(item["writingMasterId"] in self.library["writingMasterRegistry"] for item in chosen))
        self.assertTrue(all("never transfer facts" in item["factPolicy"] for item in chosen))

        five = selector.select_ideas(self.library, state, "광주 휴대폰 매장", count=5, seed="test-seed")
        self.assertEqual(len({item["ideaReferenceId"] for item in five}), 5)

    def test_state_recorder_keeps_newest_three(self) -> None:
        state = {
            "maxEntries": 3,
            "entries": [{"title": f"old-{index}", "ideaReferenceUrl": f"u-{index}", "type": f"m-{index}"} for index in range(3)],
        }
        entry = {
            "title": "new",
            "mainKeyword": "광주 휴대폰 매장",
            "ideaReferenceId": "sungji-test",
            "ideaReferenceTitle": "source",
            "ideaReferenceUrl": "new-url",
            "ideaType": "fraud-prevention",
            "titlePatternId": "keyword-warning-loss",
            "writingMasterId": "warning-seller-lines-01",
            "writingReferenceUrl": "writing-url",
            "writtenAt": "2026-08-08",
        }
        updated = recorder.record(state, entry)
        self.assertEqual(len(updated["entries"]), 3)
        self.assertEqual(updated["entries"][0]["title"], "new")
        self.assertNotIn("old-2", {item["title"] for item in updated["entries"]})


if __name__ == "__main__":
    unittest.main()
