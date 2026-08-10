# 예상 결과

## 통과 조건

- `status: pass`
- `nonWhitespaceChars`: 1400~1800
- `titleKeywordCount`: 1
- `bodyKeywordCount`: 5
- `numberedSectionCount`: 제목의 약속과 일치
- 오류와 경고가 모두 없음

## 실패 결과 계약

사람용 출력은 상태·측정값·실패 코드·문단 번호가 보이게 출력한다. JSON 출력은 다음 구조를 유지한다.

```json
{
  "status": "fail",
  "metrics": {
    "nonWhitespaceChars": 0,
    "titleKeywordCount": 0,
    "bodyKeywordCount": 0,
    "paragraphCount": 0,
    "keywordEligibleParagraphCount": 0,
    "numberedSectionCount": 0,
    "brandProofCount": 0,
    "fixedPhoneFound": false,
    "fixedReservationFound": false,
    "errors": 1,
    "warnings": 0
  },
  "issues": [
    {
      "severity": "error",
      "code": "검수-코드",
      "detail": "수정 이유",
      "paragraph": 1
    }
  ]
}
```

`paragraph`는 특정 문단을 찾을 수 있을 때만 포함한다. 종료 코드는 `pass`일 때 0, `warning` 또는 `fail`일 때 1, 파일 읽기 실패일 때 2다.
