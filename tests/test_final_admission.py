"""최종 합격 기준 매체 효율 인사이트 테스트"""

import unittest

import pandas as pd

from src.metrics import _alternative_actions, efficiency_actions, final_admission_lines


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
        """표본이 충분하고 최종 합격당 비용 차이가 크면 비싼 매체에서 싼 매체로 이관을 권한다"""
        apps = _apps([("메타", "2026-11-10", True)] * 8 + [("구글 DA", "2026-11-10", True)] * 4)
        wide = _wide({"메타": 400_000, "구글 DA": 600_000})
        lines = final_admission_lines(apps, wide, pd.Timestamp("2026-11-15"))
        shift = [line for line in lines if line.startswith("최종 합격 효율")]
        self.assertEqual(len(shift), 1)
        self.assertIn("구글 DA 예산 일부를 메타로", shift[0])

    def test_no_shift_when_final_sample_is_too_small(self):
        """최종 합격이 3명 미만이면 순위를 매기지 않고 이관 문구 대신 참고 문구만 남긴다"""
        apps = _apps([("메타", "2026-11-10", True)] * 1 + [("구글 DA", "2026-11-10", True)] * 1)
        wide = _wide({"메타": 400_000, "구글 DA": 600_000})
        lines = final_admission_lines(apps, wide, pd.Timestamp("2026-11-15"))
        self.assertFalse(any(line.startswith("최종 합격 효율") for line in lines))
        self.assertTrue(any(line.startswith("참고 ·") for line in lines))

    def test_submission_strong_but_final_weak_is_not_increased(self):
        """지원서 제출은 저렴해도 최종 합격이 저조하면 증액 대신 축소를 권한다"""
        verdict_weak = {"구글 DA"}
        wide = pd.DataFrame({
            "date": [pd.Timestamp("2026-11-10")] * 2,
            "block": ["메타", "구글 DA"],
            "비용": [300_000.0, 300_000.0],
            "CTA 클릭": [100.0, 100.0],
            "지원서 제출": [10.0, 60.0],
        })
        actions = efficiency_actions(wide, pd.Timestamp("2026-11-09"), pd.Timestamp("2026-11-15"),
                                     final_weak=verdict_weak)
        google = [a for a in actions if a.startswith("구글 DA")]
        self.assertTrue(google)
        self.assertNotIn("예산 증액을 검토하세요", google[0])
        self.assertIn("증액하지 않고", google[0])

    def test_returns_empty_without_ad_data(self):
        """광고 데이터가 없으면 빈 목록을 돌려준다"""
        apps = _apps([("메타", "2026-11-10", True)])
        self.assertEqual(final_admission_lines(apps, pd.DataFrame(), pd.Timestamp("2026-11-15")), [])


class ConflictRulesTest(unittest.TestCase):
    """제출 기준 액션과 최종 합격 판정이 서로 모순되지 않는지 확인합니다."""

    def _wide(self):
        """제출 0건 매체와 제출 저렴 매체가 섞인 광고 데이터를 만듭니다."""
        return pd.DataFrame({
            "date": [pd.Timestamp("2026-11-10")] * 3,
            "block": ["메타", "구글 DA", "네이버 SA"],
            "비용": [300_000.0, 300_000.0, 200_000.0],
            "CTA 클릭": [100.0, 100.0, 50.0],
            "지원서 제출": [10.0, 0.0, 0.0],
        })

    def test_zero_submission_with_good_final_is_not_stopped(self):
        """제출이 0건이어도 최종 합격이 우수하면 중단 대신 전환 추적 확인을 권한다"""
        actions = efficiency_actions(self._wide(), pd.Timestamp("2026-11-09"), pd.Timestamp("2026-11-15"),
                                     final_strong={"구글 DA"})
        google = [a for a in actions if a.startswith("구글 DA")]
        self.assertTrue(google)
        self.assertIn("전환 추적", google[0])
        self.assertNotIn("OFF", google[0])

    def test_no_transfer_target_without_proven_media(self):
        """최종 합격이 검증된 매체가 없으면 이관 대상을 정하지 않는다"""
        actions = efficiency_actions(self._wide(), pd.Timestamp("2026-11-09"), pd.Timestamp("2026-11-15"),
                                     final_unrated={"메타", "구글 DA", "네이버 SA"})
        self.assertFalse(any("예산 이관" in a for a in actions))

    def test_unrated_media_with_cheap_submission_is_held(self):
        """최종 합격 근거가 부족한 매체는 제출이 싸도 증액을 보류한다"""
        wide = pd.DataFrame({
            "date": [pd.Timestamp("2026-11-10")] * 2,
            "block": ["메타", "구글 DA"],
            "비용": [300_000.0, 300_000.0],
            "CTA 클릭": [100.0, 100.0],
            "지원서 제출": [10.0, 60.0],
        })
        actions = efficiency_actions(wide, pd.Timestamp("2026-11-09"), pd.Timestamp("2026-11-15"),
                                     final_unrated={"구글 DA", "메타"})
        google = [a for a in actions if a.startswith("구글 DA")]
        self.assertTrue(google)
        self.assertIn("증액은 보류", google[0])


class AlternativeActionsTest(unittest.TestCase):
    """주력 매체가 모두 축소 대상일 때 옮길 곳과 운영 테스트 후보를 제안하는지 확인합니다."""

    def test_all_running_media_cut_suggests_test_candidates(self):
        """운영 중인 매체가 모두 축소 대상이면 대안 문장과 미운영 매체의 테스트 후보를 함께 준다"""
        wide = pd.DataFrame({
            "date": [pd.Timestamp("2026-11-10")] * 2,
            "block": ["메타", "구글 DA"],
            "비용": [300_000.0, 300_000.0],
            "CTA 클릭": [100.0, 100.0],
            "지원서 제출": [60.0, 10.0],
        })
        actions = efficiency_actions(wide, pd.Timestamp("2026-11-09"), pd.Timestamp("2026-11-15"),
                                     final_weak={"메타"}, final_unrated={"구글 DA"})
        self.assertTrue(any(a.startswith("대안 · 현재 운영 매체가 모두 축소 대상") for a in actions))
        tests = [a for a in actions if a.startswith("운영 테스트 후보")]
        self.assertEqual(len(tests), 1)
        self.assertIn("구글 SA", tests[0])
        self.assertNotIn("메타", tests[0])
        self.assertNotIn("구글 DA", tests[0])

    def test_verified_running_media_is_named_as_destination(self):
        """최종 합격이 검증되고 제출 효율도 평균 이내인 운영 매체를 옮길 곳으로 지목한다"""
        agg = pd.DataFrame({"비용": [300_000.0, 300_000.0], "CTA 클릭": [100.0, 100.0],
                            "지원서 제출": [40.0, 20.0]}, index=["메타", "구글 SA"])
        valid_cps = {"메타": 7_500.0, "구글 SA": 15_000.0}
        notes = _alternative_actions(agg, {"구글 SA"}, set(), {"메타"}, set(), valid_cps,
                                     overall_cps=10_000.0, weak_ratio=1.5)
        self.assertTrue(any(n.startswith("대안 · 현재 운영 매체 중 최종 합격 효율이 우수한 메타") for n in notes))

    def test_no_destination_when_no_media_is_verified(self):
        """최종 합격으로 검증된 운영 매체가 없으면 옮길 곳을 정하지 않고 증액을 막는다"""
        agg = pd.DataFrame({"비용": [300_000.0], "CTA 클릭": [100.0], "지원서 제출": [10.0]}, index=["구글 DA"])
        notes = _alternative_actions(agg, {"메타"}, set(), set(), {"구글 DA"}, {"구글 DA": 30_000.0},
                                     overall_cps=10_000.0, weak_ratio=1.5)
        self.assertTrue(any("검증된 곳이 없어" in n and "구글 DA" in n for n in notes))
        self.assertFalse(any("옮길 곳" in n and "우수한" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
