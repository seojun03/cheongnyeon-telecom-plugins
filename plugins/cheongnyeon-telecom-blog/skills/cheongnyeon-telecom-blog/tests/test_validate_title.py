from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "validate_title.py"
spec = importlib.util.spec_from_file_location("validate_title", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ValidateTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = module.read_allowed_evidence(
            [
                str(SKILL_DIR / "references" / "brand_facts.md"),
                str(SKILL_DIR / "references" / "temporary_information.md"),
            ],
            date.today(),
        )
        cls.library = json.loads((SKILL_DIR / "references" / "topic-idea-library.json").read_text(encoding="utf-8"))

    def validate(self, title: str):
        return module.validate_title(title, "광주 휴대폰 매장", evidence=self.evidence, library=self.library)

    def test_concrete_verified_title_passes(self) -> None:
        result = self.validate("광주 휴대폰 매장, 연 8,000대가 팔리는 진짜 이유")
        self.assertNotEqual(result["status"], "fail", result["issues"])

    def test_vague_titles_fail(self) -> None:
        for title in (
            "광주 휴대폰 매장, 가격보다 상담 과정을 먼저 볼 이유",
            "광주 휴대폰 매장, 싼 곳이 의심될 때 확인할 근거",
        ):
            with self.subTest(title=title):
                self.assertEqual(self.validate(title)["status"], "fail")

    def test_brand_inquiry_title_fails_even_with_verified_number(self) -> None:
        result = self.validate("광주 휴대폰 매장? 하루 81건 문의가 남는 진짜 이유")
        self.assertEqual(result["status"], "fail")
        self.assertIn("brand-centric-inquiry", {issue["code"] for issue in result["issues"]})

    def test_external_source_fact_leak_fails(self) -> None:
        result = self.validate("광주 휴대폰 매장, 동탄 상위 1% 방식의 비밀")
        self.assertEqual(result["status"], "fail")
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("source-location", codes)
        self.assertIn("source-number", codes)

    def test_unverified_number_fails(self) -> None:
        result = self.validate("광주 휴대폰 매장, 10명 중 8명이 놓치는 계약 조건")
        self.assertEqual(result["status"], "fail")
        self.assertIn("unsupported-title-number", {issue["code"] for issue in result["issues"]})


if __name__ == "__main__":
    unittest.main()
