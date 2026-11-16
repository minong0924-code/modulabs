"""최종 합격 기준 매체 효율 인사이트 테스트"""

import unittest

import pandas as pd

from src.metrics import final_admission_lines


def _apps(rows):
    """테스트용 지원자 DataFrame을 만듭니다 (매체그룹, 지원일, 누적_최종합격)."""
    frame = pd.DataFrame(rows, columns=["매체그룹", "지원일", "누적_최종합격"])
    frame["지원일"] = pd.to_datetime(frame["지원일"])
    frame["이관"] = False
    frame["유입채널"] = "x"
    return frame


def _wide(costs):
    """테스트용 광고 일별 데이터를 만듭니다 (7일, 매체별 일정 광고비)."""
    rows = []
    for block, cost in costs.items():
        for day in pd.date_range("2026-11-09", periods=7):
            rows.append({"date": day, "block": block, "비용": cost / 7})
    return pd.DataFrame(rows)


class FinalAdmissionLinesTest(unittest.TestCase):
    """매체별 최종 합격 집계와 비적합·이관 문구를 확인합니다."""

    def test_flags_media_with_applicants_but_no_admission(self):
        """지원은 많은데 최종 합격이 0명인 매체는 비적합 의심으로 표시한다"""
        apps = _apps([("메타", "2026-11-10", True)] * 3 + [("카카오 DA", "2026-11-10", False)] * 12)
        wide = _wide({"메타": 300_000, "카카오 DA": 700_000})
        lines = final_admission_lines(apps, wide, pd.Timestamp("2026-11-15"))
        self.assertTrue(any(line.startswith("비적합 의심 · 카카오 DA") for line in lines))
        self.assertFalse(any(line.startswith("비적합 의심 · 메타") for line in lines))

    def test_suggests_shift_to_cheaper_final_admission_media(self):
        """최종 합격당 비용 차이가 크면 비싼 매체에서 싼 매체로 이관을 권한다"""
        apps = _apps([("메타", "2026-11-10", True)] * 4 + [("구글 DA", "2026-11-10", True)] * 2)
        wide = _wide({"메타": 400_000, "구글 DA": 600_000})
        lines = final_admission_lines(apps, wide, pd.Timestamp("2026-11-15"))
        shift = [line for line in lines if line.startswith("최종 합격 효율")]
        self.assertEqual(len(shift), 1)
        self.assertIn("구글 DA 예산 일부를 메타로", shift[0])

    def test_returns_empty_without_ad_data(self):
        """광고 데이터가 없으면 빈 목록을 돌려준다"""
        apps = _apps([("메타", "2026-11-10", True)])
        self.assertEqual(final_admission_lines(apps, pd.DataFrame(), pd.Timestamp("2026-11-15")), [])


if __name__ == "__main__":
    unittest.main()
