"""src/metrics.py 집계·분류 로직 테스트 (실행: python -m unittest discover -s tests)"""

import math
import unittest
from datetime import date

import pandas as pd

from src import metrics as m
from src.config import PAID_CHANNEL_GROUPS
from src.inflow_loader import comparison_periods, week_start_of


def _row(**kwargs):
    """2.2 시트 한 행을 만듭니다. 지정하지 않은 열은 빈 값입니다."""
    base = {
        "신청자 이름": "테스트", "일자": "2026-07-01", "유입 채널": "메타", "유입 소재 및 키워드": "",
        "서류 합격": "", "인터뷰 합격": "", "최종 입학": "", "수강료 결제": "",
        "수강포기": "", "사유": "", "타 과정으로 이관": "",
    }
    base.update(kwargs)
    return base


def _apps(rows):
    """행 목록을 prepare_applicants() 결과로 바꿉니다."""
    return m.prepare_applicants(pd.DataFrame(rows))


class ChannelReasonClassificationTest(unittest.TestCase):
    """유입 채널 분류 규칙"""

    def test_channel_mapping(self):
        self.assertEqual(m.classify_channel("메타"), "메타")
        self.assertEqual(m.classify_channel("구글 검색"), "구글 검색(오가닉)")
        self.assertEqual(m.classify_channel("네이버 검색"), "네이버 검색(오가닉)")
        self.assertNotIn("구글 검색(오가닉)", PAID_CHANNEL_GROUPS)
        self.assertNotIn("네이버 검색(오가닉)", PAID_CHANNEL_GROUPS)
        self.assertEqual(m.classify_channel("네이버 브검"), "네이버 브검")
        self.assertEqual(m.classify_channel("네이버 SA"), "네이버 SA")
        self.assertEqual(m.classify_channel("직접 지원"), "직접 지원")
        self.assertEqual(m.classify_channel("타 과정에서 이관"), "이관")
        self.assertEqual(m.classify_channel("기타(유입경로 확인X)"), "미분류")
        self.assertEqual(m.classify_channel("새로운 값"), "미분류")
        self.assertEqual(m.classify_channel(""), "미분류")
        self.assertEqual(m.classify_channel(None), "미분류")


class StageClassificationTest(unittest.TestCase):
    """현재 단계와 누적 통과 판정"""

    def test_stage_priority_and_cumulative_flags(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "수강포기": "수강포기", "서류 합격": "O", "인터뷰 합격": "O", "최종 입학": "O"}),
            _row(**{"신청자 이름": "b", "수강료 결제": "O", "최종 입학": "O", "인터뷰 합격": "O", "서류 합격": "O"}),
            _row(**{"신청자 이름": "c", "최종 입학": "O", "인터뷰 합격": "O", "서류 합격": "O"}),
            _row(**{"신청자 이름": "d", "인터뷰 합격": "X", "서류 합격": "O"}),
            _row(**{"신청자 이름": "e", "인터뷰 합격": "미참석", "서류 합격": "O"}),
            _row(**{"신청자 이름": "f", "서류 합격": "X"}),
            _row(**{"신청자 이름": "g", "서류 합격": "O"}),
            _row(**{"신청자 이름": "h", "서류 합격": "지원서 검토 완료"}),
            _row(**{"신청자 이름": "i", "사유": "이관"}),
            _row(**{"신청자 이름": "j", "타 과정으로 이관": "지난 기수 이관", "서류 합격": "X"}),  # 사유에 이관이 없으면 이관 아님
        ])
        stages = dict(zip(apps["신청자 이름"], apps["현재단계"]))
        self.assertEqual(stages["a"], m.STAGE_DROPOUT)
        self.assertEqual(stages["b"], m.STAGE_REGISTERED)
        self.assertEqual(stages["c"], m.STAGE_FINAL_ADMITTED)
        self.assertEqual(stages["d"], m.STAGE_INTERVIEW_REJECTED)
        self.assertEqual(stages["e"], m.STAGE_INTERVIEW_ABSENT)
        self.assertEqual(stages["f"], m.STAGE_DOC_REJECTED)
        self.assertEqual(stages["g"], m.STAGE_DOC_PASSED)
        self.assertEqual(stages["h"], m.STAGE_REVIEWING)
        self.assertEqual(stages["i"], m.STAGE_TRANSFERRED)
        self.assertEqual(stages["j"], m.STAGE_DOC_REJECTED)

        # 누적 통과: 다음 단계 기록이 있으면 이전 단계 통과
        row_c = apps[apps["신청자 이름"] == "c"].iloc[0]
        self.assertTrue(row_c["누적_서류통과"])
        self.assertTrue(row_c["누적_인터뷰통과"])
        self.assertTrue(row_c["누적_최종합격"])
        self.assertFalse(row_c["누적_등록"])
        self.assertFalse(row_c["결과확정"])  # 최종 합격 후 결제 대기는 진행 중

        # 현재 단계가 '서류 검토 중'인 사람은 누적 통과가 없다
        row_h = apps[apps["신청자 이름"] == "h"].iloc[0]
        self.assertFalse(row_h["누적_서류통과"])
        self.assertFalse(row_h["결과확정"])

        # 수강포기는 확정 단계
        self.assertTrue(apps[apps["신청자 이름"] == "a"].iloc[0]["결과확정"])

    def test_dropout_mark_only_counts_after_interview_pass(self):
        # 인터뷰 합격 이전에 표기된 수강포기는 포기로 보지 않는다
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "O", "수강포기": "수강포기"}),
            _row(**{"신청자 이름": "b", "서류 합격": "지원서 검토 완료", "수강포기": "수강포기"}),
            _row(**{"신청자 이름": "c", "서류 합격": "O", "인터뷰 합격": "O", "수강포기": "수강포기"}),
        ])
        stages = dict(zip(apps["신청자 이름"], apps["현재단계"]))
        self.assertEqual(stages["a"], m.STAGE_DOC_PASSED)
        self.assertEqual(stages["b"], m.STAGE_REVIEWING)
        self.assertEqual(stages["c"], m.STAGE_DROPOUT)
        self.assertEqual(m.summarize_applicants(apps)["포기"], 1)

    def test_rejection_takes_precedence_over_dropout_mark(self):
        # 서류 탈락 후 수강포기 표기가 있어도 탈락 단계로 집계해야 서류 불합격이 사라지지 않는다
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "X", "수강포기": "수강포기"}),
            _row(**{"신청자 이름": "b", "수강료 결제": "O", "수강포기": "수강포기"}),  # 결제 후 포기
        ])
        stages = dict(zip(apps["신청자 이름"], apps["현재단계"]))
        self.assertEqual(stages["a"], m.STAGE_DOC_REJECTED)
        self.assertEqual(stages["b"], m.STAGE_DROPOUT)
        kinds = dict(zip(apps["신청자 이름"], apps["탈락구분"]))
        self.assertEqual(kinds["a"], m.REJECTION_KIND_DOC)
        self.assertEqual(kinds["b"], m.REJECTION_KIND_DROPOUT)

    def test_rejection_kind_and_blank_name_rows_excluded(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "X", "사유": "재직자"}),
            _row(**{"신청자 이름": "b", "인터뷰 합격": "미참석", "서류 합격": "O", "사유": "부재"}),
            _row(**{"신청자 이름": "", "서류 합격": "X"}),
        ])
        self.assertEqual(len(apps), 2)
        kinds = dict(zip(apps["신청자 이름"], apps["탈락구분"]))
        self.assertEqual(kinds["a"], m.REJECTION_KIND_DOC)
        self.assertEqual(kinds["b"], m.REJECTION_KIND_INTERVIEW)  # 인터뷰 불참은 인터뷰 구분으로 묶음
        reasons = dict(zip(apps["신청자 이름"], apps["사유원문"]))
        self.assertEqual(reasons["a"], "재직자")
        self.assertEqual(reasons["b"], "부재")

    def test_week_start_is_monday(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "일자": "2026-07-05"}),  # 일요일
            _row(**{"신청자 이름": "b", "일자": "2026-07-06"}),  # 월요일
        ])
        starts = dict(zip(apps["신청자 이름"], apps["주차시작"]))
        self.assertEqual(starts["a"], pd.Timestamp("2026-06-29"))
        self.assertEqual(starts["b"], pd.Timestamp("2026-07-06"))


class SummaryAndRateTest(unittest.TestCase):
    """전형 현황 집계와 통과율 분모"""

    def test_pass_rate_denominators_only_count_decided_people(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "O", "인터뷰 합격": "O", "최종 입학": "O"}),  # 최종 합격
            _row(**{"신청자 이름": "b", "서류 합격": "X"}),                                     # 서류 탈락
            _row(**{"신청자 이름": "c", "서류 합격": "O"}),                                     # 인터뷰 대기(진행 중)
            _row(**{"신청자 이름": "d", "서류 합격": "지원서 검토 완료"}),                      # 검토 중(진행 중)
        ])
        s = m.summarize_applicants(apps)
        self.assertEqual(s["지원"], 4)
        # a 는 최종 합격이지만 결제 대기라 진행 중, 확정은 서류 탈락 b 한 명
        self.assertEqual(s["확정"], 1)
        self.assertEqual(s["진행중"], 3)
        # 서류 판정 인원: a(통과), b(X), c(통과) = 3, 통과 = a, c = 2
        self.assertEqual(s["서류결과확정"], 3)
        self.assertEqual(s["서류통과_누적"], 2)
        self.assertAlmostEqual(s["서류통과율(%)"], 2 / 3 * 100)

    def test_empty_group_returns_nan_rates_not_zero_division(self):
        s = m.summarize_applicants(_apps([]))
        self.assertEqual(s["지원"], 0)
        self.assertTrue(math.isnan(s["서류통과율(%)"]))

    def test_rejection_by_reason_uses_raw_text_and_same_kind_denominator(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "X", "사유": "재직자", "유입 채널": "메타"}),
            _row(**{"신청자 이름": "b", "서류 합격": "X", "사유": "부재", "유입 채널": "메타"}),
            _row(**{"신청자 이름": "c", "서류 합격": "X", "사유": "", "유입 채널": "구글 SA"}),
            _row(**{"신청자 이름": "d", "수강포기": "수강포기", "사유": "단순 변심", "유입 채널": "메타"}),
        ])
        table = m.rejection_by_reason(apps, by="매체그룹")
        meta_doc = table[(table["매체그룹"] == "메타") & (table["탈락구분"] == m.REJECTION_KIND_DOC)]
        self.assertEqual(set(meta_doc["분모(구분 인원)"]), {2})
        self.assertEqual(sorted(meta_doc["사유"].tolist()), ["부재", "재직자"])  # 원문 그대로
        self.assertIn("(미입력)", table[table["매체그룹"] == "구글 SA"]["사유"].tolist())

    def test_doc_x_is_not_passed_even_with_later_stage_record(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "X", "인터뷰 합격": "O"}),       # 시트 서류 X 우선
            _row(**{"신청자 이름": "b", "서류 합격": "", "인터뷰 합격": "O"}),        # 서류 빈칸이면 뒤 단계로 추정
            _row(**{"신청자 이름": "c", "서류 합격": "O"}),
        ])
        passed = dict(zip(apps["신청자 이름"], apps["누적_서류통과"]))
        self.assertEqual(passed, {"a": False, "b": True, "c": True})

    def test_rejection_table_has_three_kinds_and_absent_label(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "서류 합격": "X", "사유": "재직자"}),
            _row(**{"신청자 이름": "b", "인터뷰 합격": "미참석", "서류 합격": "O", "사유": ""}),
            _row(**{"신청자 이름": "c", "인터뷰 합격": "미참석", "서류 합격": "O", "사유": "개인 사정"}),
            _row(**{"신청자 이름": "d", "인터뷰 합격": "X", "서류 합격": "O", "사유": "점수 미달"}),
            _row(**{"신청자 이름": "e", "수강포기": "수강포기", "인터뷰 합격": "O", "사유": "단순 변심"}),
            _row(**{"신청자 이름": "f", "유입 채널": "타 과정에서 이관", "서류 합격": "O", "사유": "이관"}),
            _row(**{"신청자 이름": "g", "유입 채널": "타 과정에서 이관", "서류 합격": "O", "인터뷰 합격": "O", "사유": ""}),
        ])
        table = m.rejection_by_reason(apps)
        self.assertEqual(set(table["탈락구분"]), {m.REJECTION_KIND_DOC, m.REJECTION_KIND_INTERVIEW, m.REJECTION_KIND_DROPOUT})
        interview = table[table["탈락구분"] == m.REJECTION_KIND_INTERVIEW]
        self.assertEqual(sorted(interview["사유"].tolist()), sorted(["불참", "불참 (개인 사정)", "점수 미달"]))
        self.assertEqual(set(interview["분모(구분 인원)"]), {3})
        doc = table[table["탈락구분"] == m.REJECTION_KIND_DOC]
        self.assertEqual(sorted(doc["사유"].tolist()), ["이관", "재직자"])   # 사유에 이관이 명시된 건만, 서류 단계 이관은 서류 구분
        self.assertEqual(table[table["탈락구분"] == m.REJECTION_KIND_DROPOUT]["사유"].tolist(), ["단순 변심"])

    def test_channel_transfer_with_doc_rejection_counts_as_rejection(self):
        # 채널만 이관('지난 기수에서 이관')이고 서류 X가 표시된 건은 탈락으로 집계해야 한다 (사유에 이관이 없어도)
        apps = _apps([
            dict(_row(**{"신청자 이름": "a", "유입 채널": "지난 기수에서 이관", "서류 합격": "X", "사유": "일정불가"}), **{"그룹 미팅일 기준": "사전1주"}),
            _row(**{"신청자 이름": "b", "유입 채널": "지난 기수에서 이관", "서류 합격": "지원서 검토 완료"}),
        ])
        table = m.rejection_by_reason(apps)
        self.assertEqual(table["사유"].tolist(), ["일정불가"])
        self.assertEqual(table["분모(구분 인원)"].tolist(), [1])
        self.assertEqual(m.summarize_applicants(apps)["서류불합격"], 1)

    def test_rejection_table_order_is_doc_interview_dropout(self):
        # 표 정렬은 서류 → 인터뷰 → 수강 포기 순서 (수강포기는 인터뷰 합격 이후 포기)
        apps = _apps([
            _row(**{"신청자 이름": "a", "수강포기": "수강포기", "인터뷰 합격": "O", "사유": "단순 변심"}),
            _row(**{"신청자 이름": "b", "인터뷰 합격": "X", "서류 합격": "O", "사유": "점수 미달"}),
            _row(**{"신청자 이름": "c", "서류 합격": "X", "사유": "재직자"}),
        ])
        table = m.rejection_by_reason(apps)
        self.assertEqual(table["탈락구분"].tolist(), [m.REJECTION_KIND_DOC, m.REJECTION_KIND_INTERVIEW, m.REJECTION_KIND_DROPOUT])


def _wide(rows):
    """to_wide() 결과 형식의 DataFrame을 만듭니다."""
    frame = pd.DataFrame(rows, columns=["date", "block", "비용"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


class CpaTest(unittest.TestCase):
    """CPA 분모·분자와 중복 합산 방지"""

    def setUp(self):
        self.apps = _apps([
            _row(**{"신청자 이름": "a", "일자": "2026-07-01", "유입 채널": "메타", "수강료 결제": "O", "최종 입학": "O", "인터뷰 합격": "O", "서류 합격": "O"}),
            _row(**{"신청자 이름": "b", "일자": "2026-07-02", "유입 채널": "메타", "서류 합격": "X"}),
            _row(**{"신청자 이름": "c", "일자": "2026-07-02", "유입 채널": "기타(유가)", "서류 합격": "O"}),
            _row(**{"신청자 이름": "d", "일자": "2026-07-03", "유입 채널": "직접 지원", "서류 합격": "O"}),
            _row(**{"신청자 이름": "e", "일자": "2026-07-03", "유입 채널": "타 과정에서 이관", "서류 합격": "O"}),
            _row(**{"신청자 이름": "f", "일자": "2026-07-20", "유입 채널": "메타", "서류 합격": "O"}),  # 광고 기간 밖
        ])
        self.wide = _wide([
            ("2026-07-01", "메타", 100_000.0),
            ("2026-07-02", "메타", 200_000.0),
            ("2026-07-02", "기타 유료", 50_000.0),
            ("2026-07-03", "구글 DA", 300_000.0),
        ])

    def test_matched_paid_cpa_uses_only_matched_groups(self):
        cpa = m.period_cpa(self.apps, self.wide, "2026-07-01", "2026-07-03")
        self.assertEqual(cpa["광고비(전체)"], 650_000.0)
        self.assertEqual(cpa["광고비(매체 매칭)"], 600_000.0)       # 기타 유료 광고비 제외
        self.assertEqual(cpa["지원(유료 매칭 매체)"], 2)            # 메타 a, b (구글 DA 광고비만 있고 지원은 없음)
        self.assertEqual(cpa["지원 CPA(유료 매체)"], 300_000.0)     # 600,000 ÷ 2
        self.assertEqual(cpa["지원(전체)"], 5)                      # 이관 e 포함, 메타 a·b, 기타 유료 c, 직접 지원 d
        self.assertAlmostEqual(cpa["지원 CPA(전체 모집 비용)"], 650_000.0 / 5)

    def test_applicants_outside_ad_coverage_are_included_in_denominator(self):
        # 07-20 지원자 f 는 광고 데이터 기간(07-01~07-03) 밖이지만 모집 기간 안이면 분모에 포함된다
        cpa = m.period_cpa(self.apps, self.wide, "2026-07-01", "2026-07-31")
        self.assertEqual(cpa["광고비 집계 기간"], (pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-03")))
        self.assertEqual(cpa["광고비(전체)"], 650_000.0)
        self.assertEqual(cpa["지원(유료 매칭 매체)"], 3)            # 메타 a, b, f
        self.assertEqual(cpa["지원 CPA(유료 매체)"], 200_000.0)     # 600,000 ÷ 3
        self.assertEqual(cpa["지원(전체)"], 6)  # 이관 e 포함

    def test_zero_denominator_gives_nan(self):
        cpa = m.period_cpa(self.apps, self.wide, "2026-08-01", "2026-08-31")
        self.assertTrue(math.isnan(cpa["지원 CPA(유료 매체)"]))
        self.assertTrue(math.isnan(cpa["최종합격 CPA(유료 매체)"]))
        self.assertEqual(cpa["광고비(전체)"], 0.0)

    def test_final_cpa_counts_final_admitted_only(self):
        cpa = m.period_cpa(self.apps, self.wide, "2026-07-01", "2026-07-03")
        self.assertEqual(cpa["최종합격(유료 매칭 매체)"], 1)
        self.assertEqual(cpa["최종합격 CPA(유료 매체)"], 600_000.0)


class PeriodAndChangeTest(unittest.TestCase):
    """증감률·이동 비율·기간 계산"""

    def test_pct_change_handles_zero_previous(self):
        self.assertEqual(m.pct_change(10, 0), "신규 발생")
        self.assertEqual(m.pct_change(0, 0), "-")
        self.assertAlmostEqual(m.pct_change(50, 100), -50.0)
        self.assertEqual(m.pct_change(None, 10), "-")

    def test_rolling_ratio_is_sum_over_sum_not_mean_of_ratios(self):
        frame = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=2),
            "비용": [100.0, 900.0],
            "지원": [1, 3],
        })
        ratio = m.rolling_ratio(frame, "비용", "지원", window=2)
        self.assertAlmostEqual(ratio.iloc[-1], 1000 / 4)     # 합계 ÷ 합계 = 250
        self.assertNotAlmostEqual(ratio.iloc[-1], (100 / 1 + 900 / 3) / 2)  # 일별 CPA 평균(200)과 다름

    def test_rolling_ratio_zero_denominator_is_nan(self):
        frame = pd.DataFrame({"n": [0.0, 0.0], "d": [0.0, 0.0]})
        self.assertTrue(math.isnan(m.rolling_ratio(frame, "n", "d", window=2).iloc[-1]))

    def test_week_start_and_partial_week_comparison(self):
        self.assertEqual(week_start_of(date(2026, 7, 5)), date(2026, 6, 29))   # 일요일은 앞 주 월요일
        self.assertEqual(week_start_of(date(2026, 7, 6)), date(2026, 7, 6))
        partial = comparison_periods(date(2026, 7, 6), date(2026, 7, 8))       # 수요일까지만 데이터
        self.assertFalse(partial["complete"])
        self.assertEqual(partial["current"], (date(2026, 7, 6), date(2026, 7, 8)))
        self.assertEqual(partial["previous"], (date(2026, 6, 29), date(2026, 7, 1)))  # 같은 요일(3일간)까지만
        full = comparison_periods(date(2026, 6, 29), date(2026, 7, 8))
        self.assertTrue(full["complete"])
        self.assertEqual(full["previous"], (date(2026, 6, 22), date(2026, 6, 28)))


class InsightRuleTest(unittest.TestCase):
    """규칙 기반 인사이트 기준과 표본 처리"""

    SETTINGS = {
        "min_cost": 100_000, "min_sample": 10, "cpa_worse": 1.3, "cpa_better": 0.7,
        "cost_up": 1.2, "applicant_down": 0.8, "reason_share": 0.4,
        "missing_alert": 0.1, "in_progress_alert": 0.5,
    }

    def _period(self, label, cost, apps, **extra):
        base = {
            "label": label,
            "cost": pd.Series(cost, dtype=float),
            "applicants": pd.Series(apps, dtype=float),
            "reason_by_group": {},
            "complete": True,
        }
        base.update(extra)
        return base

    def test_cpa_worsening_flags_attention_with_evidence(self):
        cur = self._period("지난주", {"메타": 1_000_000}, {"메타": 20})   # CPA 50,000
        prev = self._period("직전 주", {"메타": 500_000}, {"메타": 20})   # CPA 25,000 -> 2배
        insights = m.build_rule_insights(cur, prev, self.SETTINGS)
        worse = [i for i in insights if i["level"] == "주의" and "CPA" in i["finding"]]
        self.assertEqual(len(worse), 1)
        self.assertIn("20", worse[0]["evidence"] + str(worse[0]["sample"]))
        self.assertIn("단정", worse[0]["limit"])

    def test_small_sample_suppresses_ratio_insight(self):
        cur = self._period("지난주", {"메타": 1_000_000}, {"메타": 3})
        prev = self._period("직전 주", {"메타": 500_000}, {"메타": 3})
        insights = m.build_rule_insights(cur, prev, self.SETTINGS)
        self.assertFalse([i for i in insights if i["level"] == "주의" and "CPA" in i["finding"]])
        self.assertTrue([i for i in insights if "표본" in i["finding"]])

    def test_reason_share_requires_sample(self):
        reason = {"메타": {"reason": "재직자", "count": 8, "sample": 10, "share": 0.8}}
        cur = self._period("지난주", {}, {}, reason_by_group=reason)
        insights = m.build_rule_insights(cur, self._period("직전 주", {}, {}), self.SETTINGS)
        self.assertTrue([i for i in insights if "재직자" in i["finding"]])
        reason_small = {"메타": {"reason": "재직자", "count": 3, "sample": 4, "share": 0.75}}
        cur_small = self._period("지난주", {}, {}, reason_by_group=reason_small)
        insights_small = m.build_rule_insights(cur_small, self._period("직전 주", {}, {}), self.SETTINGS)
        self.assertFalse([i for i in insights_small if "재직자" in i["finding"]])

    def test_incomplete_period_is_marked(self):
        cur = self._period("이번 주", {}, {}, complete=False, data_latest=pd.Timestamp("2026-07-08"))
        insights = m.build_rule_insights(cur, self._period("직전 주", {}, {}), self.SETTINGS)
        self.assertTrue([i for i in insights if "끝나지 않은" in i["finding"]])

    def test_no_change_message_when_nothing_flagged(self):
        insights = m.build_rule_insights(self._period("지난주", {}, {}), self._period("직전 주", {}, {}), self.SETTINGS)
        self.assertEqual(insights[0]["level"], "정보")


class ViewTableTest(unittest.TestCase):
    """화면 표·인사이트 입력 집계"""

    def setUp(self):
        self.apps = _apps([
            _row(**{"신청자 이름": "a", "일자": "2026-07-01", "유입 채널": "메타", "서류 합격": "X", "사유": "재직자"}),
            _row(**{"신청자 이름": "b", "일자": "2026-07-01", "유입 채널": "메타", "서류 합격": "X", "사유": "부재"}),
            _row(**{"신청자 이름": "c", "일자": "2026-07-02", "유입 채널": "메타", "서류 합격": "O"}),
            _row(**{"신청자 이름": "d", "일자": "2026-07-02", "유입 채널": "기타(유입경로 확인X)", "서류 합격": "O"}),
            _row(**{"신청자 이름": "e", "일자": "2026-07-03", "유입 채널": "타 과정에서 이관", "서류 합격": "O"}),
        ])
        self.wide = _wide([("2026-07-01", "메타", 100_000.0), ("2026-07-02", "메타", 100_000.0), ("2026-07-02", "구글 DA", 50_000.0)])

    def test_group_period_table_cpa_only_for_matched_groups(self):
        table = m.group_period_table(self.apps, self.wide, "2026-07-01", "2026-07-03").set_index("매체")
        self.assertEqual(table.loc["메타", "지원"], 3)
        self.assertAlmostEqual(table.loc["메타", "지원 CPA"], 200_000 / 3)
        self.assertTrue(math.isnan(table.loc["구글 DA", "지원 CPA"]))  # 지원 0건 -> 계산 불가
        self.assertAlmostEqual(table["광고비 비중(%)"].sum(), 100.0)

    def test_missing_channel_rate_includes_transfer(self):
        missing, rate = m.missing_channel_rate(self.apps)
        self.assertEqual(missing, 1)
        self.assertAlmostEqual(rate, 1 / 5)  # 이관 e 포함 5명 중 1명

    def test_compare_group_tables_marks_new_and_zero_previous(self):
        cur = m.group_period_table(self.apps, self.wide, "2026-07-02", "2026-07-03")
        prev = m.group_period_table(self.apps, self.wide, "2026-07-01", "2026-07-01")
        compared = m.compare_group_tables(cur, prev).set_index("매체")
        self.assertEqual(compared.loc["메타", "광고비 변화(%)"], 0.0)
        self.assertEqual(compared.loc["구글 DA", "광고비 변화(%)"], "신규 발생")

    def test_reason_concentration_uses_group_sample_as_denominator(self):
        top = m.reason_concentration(self.apps)["메타"]
        self.assertEqual(top["reason"], "재직자")  # 재직자·부재 동률이면 먼저 나온 원문 기준
        self.assertEqual(top["count"], 1)
        self.assertEqual(top["sample"], 2)
        self.assertAlmostEqual(top["share"], 0.5)

    def test_spend_without_applicants_flags_sharp_drop(self):
        daily = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=14),
            "매체": ["메타"] * 14,
            "비용": [100.0] * 14,
            "지원": [5] * 7 + [0] * 7,
        })
        flagged = m.spend_without_applicants(daily, window=7, min_sample=10)
        self.assertEqual(flagged[0]["매체"], "메타")
        self.assertEqual(flagged[0]["직전 지원"], 35)


class TransferSummaryTest(unittest.TestCase):
    """타 기수 이관 입과자: 지원 수·통과·합격 집계 모두 포함"""

    def test_transfer_counts_for_admission_but_not_applications(self):
        apps = _apps([
            _row(**{"신청자 이름": "a", "유입 채널": "메타", "서류 합격": "O", "인터뷰 합격": "O", "최종 입학": "O"}),
            _row(**{"신청자 이름": "b", "유입 채널": "이전기수에서 이관", "최종 입학": "O"}),
            _row(**{"신청자 이름": "c", "유입 채널": "이전기수에서 이관", "서류 합격": "X"}),
        ])
        s = m.summarize_applicants(apps)
        self.assertEqual(s["지원"], 3)          # 이관 b, c 도 지원 수에 포함
        self.assertEqual(s["최종합격_누적"], 2)  # 이관 b 의 최종 합격은 포함
        self.assertEqual(s["서류결과확정"], 3)   # a 합격, b 최종 이상(서류 통과로 봄), c 탈락 모두 판정 인원


class PreApplicationFlagTest(unittest.TestCase):
    """사전신청 표시: 그룹 미팅일 기준 또는 유입 채널에 사전신청이 있으면 표시"""

    def test_flag_from_group_or_channel(self):
        apps = _apps([
            dict(_row(**{"신청자 이름": "a", "일자": "2026-01-01", "유입 채널": "메타"}), **{"그룹 미팅일 기준": "사전 1차"}),
            _row(**{"신청자 이름": "b", "일자": "2026-07-01", "유입 채널": "사전신청"}),
            _row(**{"신청자 이름": "c", "일자": "2026-07-01", "유입 채널": "메타"}),
        ])
        flags = dict(zip(apps["신청자 이름"], apps["사전이관"]))
        self.assertTrue(flags["a"])
        self.assertTrue(flags["b"])
        self.assertFalse(flags["c"])


class CarryOverInclusionTest(unittest.TestCase):
    """유입 채널이 이관인 행은 모두 지원자로 포함"""

    def test_group_marked_transfer_counts_as_applicant(self):
        apps = _apps([
            dict(_row(**{"신청자 이름": "a", "유입 채널": "지난 기수에서 이관", "서류 합격": "O"}), **{"그룹 미팅일 기준": "전기수 이관"}),
            _row(**{"신청자 이름": "b", "유입 채널": "타 과정에서 이관"}),
        ])
        s = m.summarize_applicants(apps)
        self.assertEqual(s["지원"], 2)  # 사전·전기수 이관 a 와 그룹 표시 없는 타 과정 이관 b 모두 포함


class ChangeNotesTest(unittest.TestCase):
    """직전 대비 참고 문구: 급감이 아니어도 비용·지원·CPA 변화를 알려 준다"""

    def _row(self, **kw):
        base = {"광고비": 0.0, "광고비 직전": 0.0, "지원": 0, "지원 직전": 0,
                "지원 CPA": float("nan"), "지원 CPA 직전": float("nan")}
        base.update(kw)
        return pd.Series(base)

    def test_cost_up_with_applicant_growth_is_noted(self):
        note = m.change_notes(self._row(**{"광고비": 300_000.0, "광고비 직전": 100_000.0, "지원": 20, "지원 직전": 10,
                                           "지원 CPA": 15_000.0, "지원 CPA 직전": 10_000.0}))
        self.assertIn("비용 증가", note)
        self.assertIn("지원 증가", note)
        self.assertIn("CPA 악화", note)

    def test_new_and_stopped_spend(self):
        self.assertIn("신규 집행", m.change_notes(self._row(**{"광고비": 50_000.0, "지원": 5, "지원 직전": 5})))
        self.assertIn("집행 중단", m.change_notes(self._row(**{"광고비 직전": 50_000.0, "지원": 5, "지원 직전": 5})))

    def test_small_sample_is_flagged_and_stable_is_plain(self):
        self.assertTrue(m.change_notes(self._row(**{"광고비": 1.0, "지원": 1, "지원 직전": 1})).startswith("표본 적음"))
        note = m.change_notes(self._row(**{"광고비": 100_000.0, "광고비 직전": 100_000.0, "지원": 40, "지원 직전": 40,
                                           "지원 CPA": 2_500.0, "지원 CPA 직전": 2_500.0}))
        self.assertEqual(note, "특이 변화 없음")


if __name__ == "__main__":
    unittest.main()


class SamePersonTest(unittest.TestCase):
    """이름과 전화번호가 같은 중복 지원은 한 명으로, 이름만 같은 동명이인은 별도로 집계"""

    def setUp(self):
        self.apps = pd.DataFrame({
            "신청자 이름": ["정솔", "정솔", "김성민", "김성민"],
            "지원일": pd.to_datetime(["2026-10-07", "2026-10-16", "2026-10-26", "2026-10-03"]),
            "누적_서류통과": [False, True, False, True],
            "누적_인터뷰통과": [False, False, False, True],
            "누적_최종합격": [False, False, False, True],
            "누적_등록": [False, False, False, False],
        })

    def test_same_name_and_phone_counted_once_keeping_most_progressed(self):
        raw = pd.DataFrame({
            "이름": ["정솔", "정솔", "김성민", "김성민"],
            "지원일": ["2026-10-07", "2026-10-16", "2026-10-26", "2026-10-03"],
            "전화번호": ["01011112222", "01011112222", "01033334444", "01055556666"],
        })
        kept, dropped = m.drop_same_person_duplicates(m.attach_phone(self.apps, raw))
        self.assertEqual(dropped, 1)
        self.assertEqual(sorted(kept["지원일"].dt.strftime("%m-%d").tolist()), ["10-03", "10-16", "10-26"])

    def test_ambiguous_phone_is_not_merged(self):
        # 같은 이름·지원일에 전화번호가 둘이면 어느 사람인지 알 수 없으므로 중복 판정하지 않는다
        raw = pd.DataFrame({
            "이름": ["정솔", "정솔", "정솔"],
            "지원일": ["2026-10-07", "2026-10-07", "2026-10-16"],
            "전화번호": ["01011112222", "01099990000", "01011112222"],
        })
        apps = self.apps.iloc[[0, 1]].copy()
        apps["신청자 이름"] = "정솔"
        apps["지원일"] = pd.to_datetime(["2026-10-07", "2026-10-07"])
        kept, dropped = m.drop_same_person_duplicates(m.attach_phone(apps, raw))
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), 2)
