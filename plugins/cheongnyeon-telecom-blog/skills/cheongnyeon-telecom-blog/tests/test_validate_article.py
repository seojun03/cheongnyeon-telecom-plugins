from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "validate_article.py"
SPEC = importlib.util.spec_from_file_location("validate_article", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

KEYWORD = "광주 휴대폰 계약"
TITLE = f"{KEYWORD}, 먼저 물어볼 질문 3가지"


def compact_length(value: str) -> int:
    return len("".join(value.split()))


def valid_article() -> str:
    paragraphs = [
        f"{KEYWORD}을 앞두고 같은 기종인데 월 금액이 다르게 보이면 무엇부터 봐야 할지 고민되실 겁니다. 저는 그 의문을 가격표 한 줄이 아니라 실제로 내는 금액의 구성에서 풀어야 한다고 생각합니다.",
        "월 납부액만 낮아 보인다고 기기값까지 낮은 것은 아닙니다. 기기 할부금과 요금제 이용료가 한 화면에 함께 보이면 서로 다른 금액을 하나처럼 받아들이기 쉽기 때문입니다.",
        "그래서 질문은 막연한 할인 여부보다 할부원금, 할부 개월 수, 요금제, 부가서비스처럼 계약에 적히는 명사를 향해야 합니다. 말로 들은 설명과 서류의 내용이 이어져야 선택 뒤에도 계산이 흔들리지 않습니다.",
        "1. 할부원금은 얼마인지 먼저 묻습니다",
        f"제가 드리는 첫 답은 {KEYWORD}에서 월 납부액보다 할부원금을 먼저 분리해 듣는 것입니다. 할부원금은 기기 대금의 원금이고 매달 청구되는 전체 금액과는 같은 말이 아닙니다.",
        "할부원금이 보이면 두 견적이 같은 기종과 용량을 놓고 비교된 것인지부터 알 수 있습니다. 여기에 통신사까지 같아야 서로 다른 설명이 어디에서 시작됐는지 차분히 따라갈 수 있습니다.",
        f"같은 할부원금도 {KEYWORD}에서 정한 할부 개월 수에 따라 월 기기 할부금이 달라집니다. 월 금액이 낮아진 이유가 원금 감소인지 기간 증가인지 구분해야 결과를 오해하지 않습니다.",
        "이 원리를 한 번 설명한 뒤에는 같은 말을 되풀이할 필요가 없습니다. 다음에는 견적서에 적힌 할부 개월 수와 월 기기 할부금이 앞서 들은 내용과 이어지는지 보면 됩니다.",
        "2. 월 납부액에는 무엇이 들어가는지 묻습니다?",
        "두 번째 질문은 매달 빠져나가는 금액의 구성을 향합니다. 기기 할부금 외에 요금제와 부가서비스 이용료가 함께 보일 수 있으므로 각각의 이름과 금액을 나눠 들어야 합니다.",
        f"견적서와 계약서에서 {KEYWORD}의 설명을 찾을 때는 할부원금, 할부 개월 수, 요금제, 부가서비스가 어디에 적혔는지 연결해 봅니다. 실제 서식에서 확인하지 않은 칸 이름을 제가 임의로 만들지는 않겠습니다.",
        "반납이나 결합은 별도의 세 번째 비용이 아닙니다. 해당 요건을 충족할 때 빠질 수 있는 금액이므로 적용되지 않을 때 월 납부액이 어떻게 보이는지도 같은 설명 안에서 다뤄야 합니다.",
        "이렇게 나누면 낮은 월 금액만 보고 기기값이 싸다고 단정하는 일을 피할 수 있습니다. 고객에게 중요한 결과는 어떤 혜택이 빠져도 감당할 금액을 계약 전에 이해하는 것입니다.",
        "3. 말로 들은 내용이 서류에도 적히는지 확인합니다",
        f"저는 {KEYWORD}을 서두르기 전에 구두 안내와 서류가 이어지는지를 중요하게 봅니다. 설명과 계약서가 다르면 어느 항목에 어떻게 반영되는지 다시 듣고 난 뒤 결정하는 편이 낫습니다.",
        "이때 확인할 대상은 추상적인 좋은 조건이 아니라 앞에서 들은 할부원금, 월 납부액, 유지 기간, 반납 조건입니다. 적용되지 않는 경우의 금액까지 들었다면 그 내용이 서류와 맞는지 차례로 이어 볼 수 있습니다.",
        "세 질문은 같은 말을 세 번 나눈 것이 아닙니다. 첫 질문은 기기 원금, 두 번째는 매달 내는 금액의 구성, 마지막 질문은 말과 문서의 일치를 다루며 서로 다른 결정을 돕습니다.",
        "모든 내용을 한꺼번에 외우실 필요는 없습니다. 받은 견적서에서 설명과 다른 부분이 보이면 서명 전에 그 항목이 어디에 반영되는지만 다시 물어보셔도 충분합니다.",
    ]
    fillers = [
        "판매자가 편한 표현보다 고객이 나중에도 다시 찾을 수 있는 명사가 남아야 설명의 의미가 선명해집니다.",
        "같은 금액을 여러 표현으로 되풀이하기보다 다음 서류와 다음 결과로 설명을 앞으로 보내는 편이 이해하기 쉽습니다.",
        "한 문장에서 원인과 행동을 모두 밀어 넣지 않으면 독자도 자신이 받은 견적에 차례대로 대입해 볼 수 있습니다.",
        "설명이 길어져도 새로운 정보가 없다면 도움이 되지 않으므로 이미 말한 조언은 결론에서 다시 포장하지 않습니다.",
    ]
    article = f"# {TITLE}\n\n" + "\n\n".join(paragraphs)
    index = 0
    while compact_length(article) < 1500:
        paragraphs[-2] += " " + fillers[index % len(fillers)]
        index += 1
        article = f"# {TITLE}\n\n" + "\n\n".join(paragraphs)
    return article


def article_with_fixed_components() -> str:
    title, body = VALIDATOR.extract_article(valid_article())
    parts = VALIDATOR.paragraphs(body)
    proof_block = "\n".join(
        [
            "광주 휴대폰매장 청년통신",
            "※ SBS 생활의 달인 1029화 '휴대폰 달인' 출연",
            "※ 연간 8,000대 이상 판매",
            "※ 구매 후 3년간 휴대폰 서비스센터 무상 대행",
            "※ 고객 사용량 조회 후 맞춤형 요금제 상담",
            "※ 최신 기종 대기 없이 즉시 개통 가능",
        ]
    )
    closing = "\n".join(
        [
            "광주 휴대폰매장 청년통신",
            "대표 전화 010-8489-4440",
            "문의가 많아 연락을 남겨도 부재중일 수 있습니다.",
            "네이버 예약 후 방문해 주시면 바로 상담 가능합니다.",
        ]
    )
    parts.insert(1, proof_block)
    parts.append(closing)
    return f"# {title}\n\n" + "\n\n".join(parts)


def article_with_single_proof_and_contact() -> str:
    title, body = VALIDATOR.extract_article(valid_article())
    parts = VALIDATOR.paragraphs(body)
    parts.append("SBS 생활의 달인 1029화 '휴대폰 달인'에 출연한 청년통신 대표 김웅빈입니다.")
    parts.append(
        "광주 휴대폰매장 청년통신\n대표 전화 010-8489-4440\n"
        "문의가 많아 연락을 남겨도 부재중일 수 있습니다.\n"
        "네이버 예약 후 방문해 주시면 바로 상담 가능합니다."
    )
    return f"# {title}\n\n" + "\n\n".join(parts)


def issue_codes(result: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in result["issues"]}


class ValidateArticleTests(unittest.TestCase):
    def test_normal_three_question_article_passes(self) -> None:
        result = VALIDATOR.validate_article(valid_article(), KEYWORD)
        self.assertEqual(result["status"], "pass", result)

    def test_title_three_but_only_two_numbered_sections_fails(self) -> None:
        article = valid_article().replace("3. 말로 들은 내용이 서류에도 적히는지 확인합니다", "말로 들은 내용이 서류에도 적히는지 확인합니다")
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("title-section-count", issue_codes(result))

    def test_numbered_html_headings_are_counted(self) -> None:
        body = "".join(
            [
                "<p>도입 설명입니다.</p>",
                "<h2><strong>1. 첫 번째 확인</strong></h2><p>첫 답입니다.</p>",
                "<h2>2. 두 번째 확인</h2><p>둘째 답입니다.</p>",
                "<h2>3. 세 번째 확인</h2><p>셋째 답입니다.</p>",
            ]
        )
        markers = VALIDATOR.numbered_section_markers(body)
        self.assertEqual([number for _, number, _ in markers], [1, 2, 3])

    def test_zero_body_keyword_fails(self) -> None:
        title, body = VALIDATOR.extract_article(valid_article())
        body = body.replace(KEYWORD, "광주에서 하는 계약")
        result = VALIDATOR.validate_article(f"# {title}\n\n{body}", KEYWORD)
        self.assertIn("body-keyword-count", issue_codes(result))

    def test_six_body_keywords_fail(self) -> None:
        article = valid_article().replace("월 납부액만 낮아", f"{KEYWORD}에서 월 납부액만 낮아", 1)
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("body-keyword-count", issue_codes(result))

    def test_cta_and_caption_keywords_are_excluded_from_body_count(self) -> None:
        article = valid_article()
        article += f"\n\n{KEYWORD} 예약 문의는 확인된 연락처로 남겨 주세요."
        article += f"\n\n<figcaption>{KEYWORD} 서류 확인 장면</figcaption>"
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertEqual(result["metrics"]["bodyKeywordCount"], 5, result)

    def test_adjacent_keyword_paragraphs_fail(self) -> None:
        title, body = VALIDATOR.extract_article(valid_article())
        parts = VALIDATOR.paragraphs(body)
        parts[1] = f"{KEYWORD}에서 보이는 월 납부액은 기기값 하나만 뜻하지 않습니다."
        parts[14] = parts[14].replace(KEYWORD, "계약")
        result = VALIDATOR.validate_article(f"# {title}\n\n" + "\n\n".join(parts), KEYWORD)
        self.assertIn("adjacent-keyword-paragraphs", issue_codes(result))

    def test_under_1400_chars_fails(self) -> None:
        article = valid_article()[:900]
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("article-too-short", issue_codes(result))

    def test_over_1800_chars_fails(self) -> None:
        article = valid_article() + "\n\n" + ("새로운 사실이 없는 문장을 넣지 않습니다. " * 80)
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("article-too-long", issue_codes(result))

    def test_style_only_number_without_evidence_fails(self) -> None:
        article = valid_article().replace("낮은 월 금액만", "90만원이라는 가격을 들었더라도 낮은 월 금액만", 1)
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("unsupported-numeric-claim", issue_codes(result))

    def test_numeric_claim_with_current_usable_evidence_passes(self) -> None:
        article = valid_article().replace("낮은 월 금액만", "90만원이라는 가격을 들었더라도 낮은 월 금액만", 1)
        evidence = "## FACT-9000\n- 상태: 사용 가능\n- 정확한 사실: 확인된 가격은 90만원\n- 만료일: 2099-12-31"
        result = VALIDATOR.validate_article(article, KEYWORD, evidence=evidence)
        self.assertNotIn("unsupported-numeric-claim", issue_codes(result))

    def test_expired_evidence_is_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_path = Path(temp_dir) / "facts.md"
            evidence_path.write_text(
                "## FACT-9001\n- 상태: 사용 가능\n- 정확한 사실: 확인된 가격은 90만원\n- 만료일: 2020-01-01",
                encoding="utf-8",
            )
            loaded = VALIDATOR.read_allowed_evidence([str(evidence_path)], date(2026, 8, 4))
        self.assertNotIn("90만원", loaded)

    def test_forbidden_and_superseded_fields_are_not_loaded_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_path = Path(temp_dir) / "facts.md"
            evidence_path.write_text(
                "\n".join(
                    [
                        "## TEMP-9002",
                        "- 상태: 사용 가능",
                        "- 정확한 사실: 현재 하루 평균 81건의 문의",
                        "- 대체한 이전 사실: 하루 87건의 문의",
                        "- 사용할 수 있는 표현: 하루 평균 81건",
                        "- 사용하면 안 되는 확대 표현: 현재 하루 87건",
                    ]
                ),
                encoding="utf-8",
            )
            loaded = VALIDATOR.read_allowed_evidence([str(evidence_path)], date(2026, 8, 4))
        self.assertIn("81건", loaded)
        self.assertNotIn("87건", loaded)

    def test_parallel_numbered_structure_is_not_rejected_without_master_comparison(self) -> None:
        body = "\n\n".join(
            [
                f"{KEYWORD}을 앞두고 무엇을 물어볼지 고민하실 수 있습니다.",
                "저는 구체적인 금액 이름부터 보시길 권합니다.",
                "1. 첫 질문인가요?",
                f"답은 {KEYWORD}에서 할부원금을 묻는 것입니다.",
                "서류에서 해당 내용을 확인해 보세요.",
                "2. 두 번째 질문인가요?",
                f"금액이 달라지는 원인은 {KEYWORD}에서 할부 개월 수가 달라지기 때문입니다.",
                "서류에서 해당 내용을 확인해 보세요.",
                "3. 세 번째 질문인가요?",
                f"계약서에는 {KEYWORD}의 요금제가 적혀 있는지 봅니다.",
                "서류에서 해당 내용을 확인해 보세요.",
            ]
        )
        result = VALIDATOR.validate_article(f"# {TITLE}\n\n{body}", KEYWORD, min_chars=1, max_chars=10000)
        self.assertNotIn("parallel-section-structure", issue_codes(result))

    def test_photo_label_and_summary_table_fail(self) -> None:
        article = valid_article() + "\n\n상담 현장\n\n| 구분 | 내용 |\n|---|---|\n| 요약 | 본문 반복 |"
        result = VALIDATOR.validate_article(article, KEYWORD, max_chars=10000)
        codes = issue_codes(result)
        self.assertIn("production-label", codes)
        self.assertIn("table-present", codes)

    def test_title_this_must_be_revealed_early(self) -> None:
        _, body = VALIDATOR.extract_article(valid_article())
        parts = VALIDATOR.paragraphs(body)
        parts[0] = f"{KEYWORD}을 앞두고 무엇이 중요한지 막막하실 수 있습니다. 저는 그 의문을 차분히 풀어드리겠습니다."
        parts[1] = "이것은 누구나 한 번쯤 궁금해할 만한 내용입니다. 아직 이름을 밝히지 않고 설명부터 이어가겠습니다."
        title = f"{KEYWORD}, 이것부터 보세요"
        result = VALIDATOR.validate_article(f"# {title}\n\n" + "\n\n".join(parts), KEYWORD)
        self.assertIn("this-not-revealed", issue_codes(result))

    def test_first_person_speaker_must_remain(self) -> None:
        article = valid_article().replace("저는", "대표는").replace("제가", "대표가").replace("저희는", "매장은")
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("speaker-missing", issue_codes(result))

    def test_external_idea_source_fact_cannot_leak_into_body(self) -> None:
        article = valid_article().replace("판매자가 편한 표현", "동탄도매폰센터가 편한 표현", 1)
        result = VALIDATOR.validate_article(article, KEYWORD)
        self.assertIn("external-idea-brand", issue_codes(result))

    def test_brand_operations_cannot_replace_buyer_hook_lines(self) -> None:
        article = valid_article().replace(
            "월 납부액만 낮아 보인다고 기기값까지 낮은 것은 아닙니다.",
            '<p data-reference-role="hook-line">가격만 싸면 문의가 계속 남는 걸까요?</p>'
            '<p data-reference-role="hook-line">하루 81건 문의의 핵심은 운영입니다.</p>'
            '<p data-reference-role="hook-line">판매량이 많으면 믿어도 되는 걸까요?</p>'
            "월 납부액만 낮아 보인다고 기기값까지 낮은 것은 아닙니다.",
            1,
        )
        result = VALIDATOR.validate_article(article, KEYWORD, max_chars=10000)
        self.assertIn("brand-centric-hook", issue_codes(result))

    def test_buyer_problem_hook_lines_pass_relevance_gate(self) -> None:
        article = valid_article().replace(
            "월 납부액만 낮아 보인다고 기기값까지 낮은 것은 아닙니다.",
            '<p data-reference-role="hook-line">안내받은 기기값과 계약서의 할부원금이 달라요.</p>'
            '<p data-reference-role="hook-line">계약 때 들은 요금제와 실제 청구 금액이 달라요.</p>'
            '<p data-reference-role="hook-line">추천받은 요금제가 정말 저한테 맞는 걸까요?</p>'
            "월 납부액만 낮아 보인다고 기기값까지 낮은 것은 아닙니다.",
            1,
        )
        result = VALIDATOR.validate_article(article, KEYWORD, max_chars=10000)
        self.assertNotIn("brand-centric-hook", issue_codes(result))

    def test_abstract_match_closing_is_rejected(self) -> None:
        title, body = VALIDATOR.extract_article(valid_article())
        body += "\n\n답변과 서류가 맞을 때 결정하셔도 늦지 않습니다."
        result = VALIDATOR.validate_article(f"# {title}\n\n{body}", KEYWORD, max_chars=10000)
        codes = issue_codes(result)
        self.assertIn("abstract-match-closing", codes)
        self.assertIn("generic-late-decision-closing", codes)

        variant = body.replace("답변과 서류가 맞을 때 결정하셔도", "설명과 계약서를 맞춘 뒤 판단해도")
        variant_result = VALIDATOR.validate_article(f"# {title}\n\n{variant}", KEYWORD, max_chars=10000)
        variant_codes = issue_codes(variant_result)
        self.assertIn("abstract-match-closing", variant_codes)
        self.assertIn("generic-late-decision-closing", variant_codes)

    def test_concrete_reference_style_closing_is_allowed(self) -> None:
        title, body = VALIDATOR.extract_article(valid_article())
        body += (
            "\n\n판매량을 증명할 사진이나 표창이 있는지 먼저 보시면 "
            "말뿐인 광고와 구분하기가 훨씬 쉽습니다."
        )
        result = VALIDATOR.validate_article(f"# {title}\n\n{body}", KEYWORD, max_chars=10000)
        codes = issue_codes(result)
        self.assertNotIn("abstract-match-closing", codes)
        self.assertNotIn("generic-late-decision-closing", codes)

    def test_unicode_normalization_counts_zero_width_keyword(self) -> None:
        title, body = VALIDATOR.extract_article(valid_article())
        split_keyword = "\u200b".join(KEYWORD)
        body = body.replace(KEYWORD, split_keyword)
        title = title.replace(" ", "\u00a0")
        result = VALIDATOR.validate_article(f"# {title}\r\n\r\n{body}", KEYWORD)
        self.assertEqual(result["status"], "pass", result)

    def test_publication_mode_requires_fixed_components(self) -> None:
        result = VALIDATOR.validate_article(valid_article(), KEYWORD, require_fixed_components=True)
        codes = issue_codes(result)
        self.assertIn("brand-proof-missing", codes)
        self.assertIn("fixed-phone-missing", codes)
        self.assertIn("fixed-reservation-missing", codes)

    def test_publication_mode_accepts_one_late_brand_proof(self) -> None:
        result = VALIDATOR.validate_article(
            article_with_single_proof_and_contact(),
            KEYWORD,
            require_fixed_components=True,
        )
        component_codes = {
            code for code in issue_codes(result) if code.startswith("fixed-") or code.startswith("brand-proof-")
        }
        self.assertEqual(component_codes, set(), result)
        self.assertEqual(result["metrics"]["brandProofCount"], 1, result)

    def test_publication_mode_accepts_complete_fixed_components(self) -> None:
        evidence = VALIDATOR.read_allowed_evidence(
            [str(SKILL_DIR / "references" / "brand_facts.md"), str(SKILL_DIR / "references" / "temporary_information.md")],
            date(2026, 8, 4),
        )
        result = VALIDATOR.validate_article(
            article_with_fixed_components(),
            KEYWORD,
            evidence=evidence,
            require_fixed_components=True,
        )
        fixed_codes = {code for code in issue_codes(result) if code.startswith("fixed-")}
        self.assertEqual(fixed_codes, set(), result)
        self.assertEqual(result["metrics"]["brandProofCount"], 5, result)

    def test_fixed_proof_and_contact_do_not_inflate_keyword_count(self) -> None:
        alternate_keyword = "광주 휴대폰매장"
        article = article_with_fixed_components().replace(KEYWORD, alternate_keyword)
        result = VALIDATOR.validate_article(article, alternate_keyword)
        self.assertEqual(result["metrics"]["titleKeywordCount"], 1, result)
        self.assertEqual(result["metrics"]["bodyKeywordCount"], 5, result)


if __name__ == "__main__":
    unittest.main()
