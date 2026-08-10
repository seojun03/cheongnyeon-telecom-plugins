from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_rebuttal_analysis_mode_is_routed_from_skill(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("반박분석 3멘트", skill)
        self.assertIn("references/rebuttal-analysis-three-lines.md", skill)
        self.assertNotIn("초반 고정 가치입증 다섯 항목", skill)

    def test_rebuttal_reference_keeps_two_subtypes_and_sources(self) -> None:
        reference = (SKILL_DIR / "references" / "rebuttal-analysis-three-lines.md").read_text(encoding="utf-8")
        self.assertIn("판매자 멘트 3개형", reference)
        self.assertIn("독자 반론 3개형", reference)
        self.assertIn("223515173954", reference)
        self.assertIn("223916429310", reference)
        self.assertIn("역사적 사실 또는 문체 자료", reference)

    def test_brand_proof_matches_master_and_contact_is_fixed(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("마스터가 1개를 쓰면 1개, 3개를 쓰면 3개, 5개를 쓰면 5개", skill)
        self.assertIn("대표 전화 010-8489-4440", skill)
        self.assertIn("네이버 예약", skill)

    def test_second_hook_is_routed_and_reanalyzes_reader(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL_DIR / "references" / "reader-commitment-bridge.md").read_text(encoding="utf-8")
        pipeline = (SKILL_DIR / "references" / "natural-writing-pipeline.md").read_text(encoding="utf-8")
        self.assertIn("소비자 마음 2차 후킹", skill)
        self.assertIn("references/reader-commitment-bridge.md", skill)
        self.assertIn("remainingResistance", reference)
        self.assertIn("선택 압박 해제", reference)
        self.assertIn("독자가 최소 30만 원 절약", reference)
        self.assertIn("second-hook-duplicate", pipeline)
        self.assertIn("second-hook-unsupported-payoff", pipeline)

    def test_reference_selection_uses_one_exact_master_without_feature_mixing(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        exact = (SKILL_DIR / "references" / "reference-exact-reconstruction.md").read_text(encoding="utf-8")
        library = (SKILL_DIR / "references" / "type-reference-library.md").read_text(encoding="utf-8")
        pipeline = (SKILL_DIR / "references" / "natural-writing-pipeline.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, exact, library, pipeline))
        self.assertIn("마스터 한 편 선택", skill)
        self.assertIn("references/reference-exact-reconstruction.md", skill)
        self.assertIn("자동 조합 금지", exact)
        self.assertIn("마스터에 없으면 추가하지 않는다", exact)
        self.assertIn("최대 2편", combined)
        self.assertIn("주 마스터 1편", combined)
        self.assertIn("꾸미기·사진·줄바꿈 검토는 주 마스터 1편", combined)

    def test_openai_yaml_default_prompt_mentions_skill(self) -> None:
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('default_prompt: "$cheongnyeon-telecom-blog', metadata)

    def test_model_recommendation_warns_without_blocking(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        warning = (
            "참고: 글 퀄리티를 위해 GPT-5.6 Sol High 이상 모델을 사용해주시면 좋습니다. "
            "현재 모델에서도 작업은 계속 진행합니다."
        )
        self.assertIn("모델 품질 권장 안내", skill)
        self.assertIn("모든 모델과 추론 수준에서 실행", skill)
        self.assertIn("권장 조건일 뿐 실행 조건이나 중단 게이트가 아니다", skill)
        self.assertIn("낮은 것으로 **명확히 확인된 경우에만**", skill)
        self.assertIn(warning, skill)
        self.assertIn(warning, metadata)
        self.assertIn("같은 응답에서 정상 작업을 계속", skill)
        self.assertIn("런타임 정보를 확인할 수 없으면", skill)
        self.assertIn("경고 없이 정상 작업을 계속", skill)
        self.assertIn("제목·본문·HTML 생성을 차단하지 않는다", skill)
        self.assertIn("모든 모델과 추론 수준에서 실행", metadata)
        self.assertIn("중단 없이 계속", metadata)
        self.assertNotIn("제목·본문·HTML을 만들지 않는다", skill)
        self.assertNotIn("High 이상 전용입니다", skill)
        self.assertNotIn("원고를 만들지 말고 모델 변경", metadata)
        self.assertNotRegex(metadata, r"(?m)^\s*(?:model|reasoning_effort):")

    def test_naver_html_is_required_default_artifact(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("모든 완성 글", skill)
        self.assertIn("바탕화면 네이버용 HTML 파일", skill)
        self.assertIn("HTML 생성은 선택사항이 아니다", skill)
        self.assertIn("scripts/build_naver_copy_page.py", skill)
        self.assertIn("네이버용 HTML 복사", skill)
        self.assertIn('Path.home() / "Desktop"', skill)
        self.assertIn("Windows는 시스템에 등록된 바탕화면 경로", skill)
        self.assertIn("CHEONGNYEON_OUTPUT_DIR", skill)
        self.assertIn("Windows PowerShell", skill)
        self.assertIn("`py -3`", skill)
        self.assertIn("`Ctrl+V`", skill)
        self.assertIn("사용자 컴퓨터의 로컬 이미지 파일", skill)
        self.assertIn("정확한 레퍼런스 블로그 `sourceUrl`", skill)
        self.assertNotRegex(skill, r"/Users/[^/]+/Desktop")
        self.assertNotIn("HTML·미디어는 명시 요청 시에만 제공한다", skill)
        self.assertNotIn("사용자가 HTML이나 파일을 요청했을 때만 HTML을 만든다", skill)
        self.assertIn("HTML 요청 여부와 관계없이", metadata)

    def test_final_response_reports_html_path_and_reference_link(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("HTML 저장 완료:", skill)
        self.assertIn("주제·제목 참고 글:", skill)
        self.assertIn("말투·구조·꾸미기 참고 글:", skill)
        self.assertIn("선택한 외부 아이디어 글의 실제 URL", skill)
        self.assertIn("선택한 cjdsus4444 대표글의 실제 URL", skill)
        self.assertIn("두 참고 글 링크를 역할별로", metadata)

    def test_generic_ai_closing_is_explicitly_forbidden(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        closing = (SKILL_DIR / "references" / "closing-seven-posts.md").read_text(encoding="utf-8")
        for phrase in ("답변과 서류가 맞을 때", "결정하셔도 늦지 않습니다", "추상 명사 대조형 마무리"):
            self.assertIn(phrase, skill)
        self.assertIn("판매량을 증명할 사진이나 표창", closing)
        self.assertIn("할부원금", closing)
        self.assertIn("저압 문의 연결", closing)

    def test_topic_idea_and_writing_master_are_strictly_separated(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        guide = (SKILL_DIR / "references" / "topic-idea-types.md").read_text(encoding="utf-8")
        self.assertIn("ideaReferenceId", skill)
        self.assertIn("masterReferenceId", skill)
        self.assertIn("scripts/select_topic_idea.py", skill)
        self.assertIn("scripts/validate_title.py", skill)
        self.assertIn("scripts/record_article_state.py", skill)
        self.assertIn("주제·제목 아이디어 출처", guide)
        self.assertIn("말투·구조·꾸미기 출처", guide)
        self.assertIn("사실 출처", guide)

    def test_type_library_routes_without_loading_every_reference(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        library = (SKILL_DIR / "references" / "type-reference-library.md").read_text(encoding="utf-8")
        pipeline = (SKILL_DIR / "references" / "natural-writing-pipeline.md").read_text(encoding="utf-8")
        self.assertIn("references/type-reference-library.md", skill)
        self.assertIn("경고·피해예방형", library)
        self.assertIn("가격·권위형", library)
        self.assertIn("같은 유형의 두 번째 글은 필요할 때만 보조 1편으로 읽고, 다른 유형 글은 읽거나 섞지 않는다", pipeline)
        self.assertIn("선택한 주 마스터 외의 원문은 필요할 때만 보조 1편", library)
        self.assertIn("다른 유형의 전체 원문은 읽지 않는다", library)

    def test_reference_reading_budget_keeps_primary_decoration_exact(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        library = (SKILL_DIR / "references" / "type-reference-library.md").read_text(encoding="utf-8")
        decoration = (SKILL_DIR / "references" / "reference-decoration-profiles.md").read_text(encoding="utf-8")
        self.assertIn("주 마스터 1편을 기본으로 하고, 필요할 때만", skill)
        self.assertIn("총 2편을 넘기지 않는다", skill)
        self.assertIn("꾸미기·사진·줄바꿈은 항상 주 마스터 1편만 기준", skill)
        self.assertIn("보조 원문이 있어도 색·정렬·표·밑줄·사진·줄바꿈·CTA를", library)
        self.assertIn("보조 원문을 읽더라도 꾸미기 판단에는 사용하지 않는다", decoration)

    def test_mobile_body_uses_two_or_three_lines_then_one_gap(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        decoration = (SKILL_DIR / "references" / "reference-decoration-profiles.md").read_text(encoding="utf-8")
        profiles = json.loads(
            (SKILL_DIR / "assets" / "reference-decoration-profiles.json").read_text(encoding="utf-8")
        )
        authority = profiles["profiles"]["authority-broadcast-reason-01"]["renderContract"]
        self.assertIn("2~3줄 → 빈 줄 1칸", skill)
        self.assertIn("2~3줄 → 빈 줄 1칸", decoration)
        self.assertEqual(authority["maxConsecutiveDirectBodyParagraphs"], 3)
        self.assertEqual(authority["minEstimatedMobileLinesPerBodyGroup"], 2)
        self.assertEqual(authority["maxEstimatedMobileLinesPerBodyGroup"], 3)
        self.assertEqual(authority["estimatedMobileCharactersPerLine"], 24)

    def test_master_structure_controls_optional_features_and_order(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        exact = (SKILL_DIR / "references" / "reference-exact-reconstruction.md").read_text(encoding="utf-8")
        pipeline = (SKILL_DIR / "references" / "natural-writing-pipeline.md").read_text(encoding="utf-8")
        self.assertIn("블록 개수·순서·문장 역할·문장 수를 유지", skill)
        self.assertIn("다른 구조 후보를 만들지 않는다", skill)
        self.assertIn("마스터에 2차 후킹이 없으면 자동으로 추가하지 않는다", exact)
        self.assertIn("master-structure-drift", pipeline)
        self.assertIn("master-feature-added", pipeline)
        self.assertIn("master-tone-drift", pipeline)

    def test_reference_decoration_is_bound_to_same_master(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        exact = (SKILL_DIR / "references" / "reference-exact-reconstruction.md").read_text(encoding="utf-8")
        decoration = (SKILL_DIR / "references" / "reference-decoration-profiles.md").read_text(encoding="utf-8")
        profiles = json.loads(
            (SKILL_DIR / "assets" / "reference-decoration-profiles.json").read_text(encoding="utf-8")
        )
        warning = profiles["profiles"]["warning-seller-lines-01"]
        self.assertIn("decorationMasterReferenceId", skill)
        self.assertIn("decorationMasterReferenceId", exact)
        self.assertIn("항상 `masterReferenceId`와 같아야", decoration)
        self.assertIn("scripts/validate_reference_decoration.py", skill)
        self.assertEqual(warning["renderContract"]["tableRowCounts"], [5, 2])
        self.assertEqual(warning["renderContract"]["requiredRoleCounts"]["hook-line"], 3)
        self.assertEqual(len(warning["mediaSlots"]), 7)
        self.assertTrue(warning["renderContract"]["requireExactMediaSources"])
        self.assertEqual(warning["renderContract"]["requiredRoleCounts"]["reference-image"], 4)
        self.assertEqual(warning["renderContract"]["requiredRoleCounts"]["reference-group-image"], 3)
        for slot in warning["mediaSlots"]:
            self.assertTrue(slot["sourceUrl"].startswith("https://"))
            self.assertIn("postfiles.pstatic.net", slot["sourceUrl"])
        self.assertFalse(profiles["copySafetyOverrides"]["forbidUnderline"])
        self.assertEqual(warning["renderContract"]["requiredUnderlineCount"], 8)
        self.assertEqual(
            warning["renderContract"]["requiredUnderlineRoleCounts"],
            {
                "hook-line": 3,
                "danger-warning": 1,
                "seller-promise": 1,
                "contact-phone": 1,
                "contact-note": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
