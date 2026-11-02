"""src/action_log.py 파싱·필터·전후 비교 테스트"""

import unittest

import pandas as pd

from src import action_log as al


class ParseActionLogTest(unittest.TestCase):
    """시트 값 파싱"""

    def test_parses_by_header_name_and_skips_invalid_dates(self):
        rows = [
            ["변경일", "과정ID", "기수", "매체", "캠페인·소재", "변경유형", "변경내용", "변경이유", "담당자", "추후 확인 지표", "확인 예정일"],
            ["2026-07-10", "ai_agent", "2", "메타", "", "예산 조정", "일예산 증액", "CPA 안정", "김담당", "CPA", "2026-07-17"],
            ["날짜아님", "ai_agent", "2", "메타", "", "소재 교체", "새 소재", "", "", "", ""],
            ["2026-07-12", "", "", "구글 DA", "", "랜딩페이지 수정", "문구 수정", "", "", "", ""],
        ]
        actions = al.parse_action_log(rows)
        self.assertEqual(len(actions), 2)
        self.assertEqual(list(actions.columns), al.ACTION_COLUMNS)
        self.assertEqual(actions.iloc[0]["변경일"], pd.Timestamp("2026-07-10"))
        self.assertEqual(actions.iloc[0]["확인 예정일"], pd.Timestamp("2026-07-17"))

    def test_short_rows_are_padded_and_empty_sheet_returns_empty_frame(self):
        rows = [
            ["변경일", "과정ID", "기수", "매체", "캠페인·소재", "변경유형", "변경내용"],
            ["2026-07-10", "ai_agent", "2"],
        ]
        actions = al.parse_action_log(rows)
        self.assertEqual(actions.iloc[0]["변경내용"], "")
        self.assertTrue(al.parse_action_log([]).empty)
        self.assertTrue(al.parse_action_log([rows[0]]).empty)


class FilterAndBeforeAfterTest(unittest.TestCase):
    """과정·기수 필터와 전후 비교"""

    def setUp(self):
        self.actions = al.parse_action_log([
            ["변경일", "과정ID", "기수", "매체", "캠페인·소재", "변경유형", "변경내용", "변경이유", "담당자", "추후 확인 지표", "확인 예정일"],
            ["2026-07-10", "ai_agent", "2기", "메타", "", "예산 조정", "A", "", "", "", ""],
            ["2026-07-11", "ai_agent", "3", "메타", "", "예산 조정", "B", "", "", "", ""],
            ["2026-07-12", "", "", "전체", "", "랜딩페이지 수정", "C", "", "", "", ""],
        ])

    def test_filter_includes_blank_course_rows_as_all_courses(self):
        picked = al.filter_actions(self.actions, "ai_agent", 2)
        self.assertEqual(picked["변경내용"].tolist(), ["A", "C"])

    def test_filter_without_course_returns_everything(self):
        self.assertEqual(len(al.filter_actions(self.actions)), 3)

    def test_before_after_uses_sums_not_daily_average(self):
        daily = pd.DataFrame({
            "date": pd.to_datetime(["2026-07-07", "2026-07-08", "2026-07-10", "2026-07-11"]),
            "비용": [100.0, 300.0, 500.0, 500.0],
            "지원": [1, 1, 5, 5],
        })
        result = al.before_after(daily, "2026-07-10", window=3)
        self.assertEqual(result["전"]["days"], 2)
        self.assertAlmostEqual(result["전"]["CPA"], 400 / 2)
        self.assertAlmostEqual(result["후"]["CPA"], 1000 / 10)

    def test_before_after_without_data_returns_none(self):
        daily = pd.DataFrame({"date": pd.to_datetime(["2026-07-01"]), "비용": [1.0], "지원": [1]})
        result = al.before_after(daily, "2026-07-10", window=3)
        self.assertIsNone(result["후"]["CPA"])


if __name__ == "__main__":
    unittest.main()
