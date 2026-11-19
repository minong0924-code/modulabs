"""시트 명단 대조(이관 표시) 단위 테스트"""
import datetime as dt
import unittest

from scripts import sync_ga_channels as s

HEADERS = ["no", "일자", "신청자 이름", "유입 채널", "유입 소재 및 키워드", "캠페인 구분", "연령대", "비고", "사유"]
REASON_COL = HEADERS.index("사유")


def _sheet(*rows):
    """헤더 + 데이터 행을 시트 값 형태(2차원 리스트)로 만듭니다."""
    body = []
    for name, date, reason in rows:
        row = [""] * len(HEADERS)
        row[1] = date
        row[2] = name
        row[REASON_COL] = reason
        body.append(row)
    return [HEADERS] + body


class ReconcileTest(unittest.TestCase):
    """DB에서 사라진 신청자를 삭제하지 않고 사유를 이관으로 표시하는지 확인"""

    def _run(self, sheet, db_keys):
        """build_updates를 매칭 없이 명단 대조만 수행하고 이관 대상 범위를 돌려줍니다."""
        return s.build_updates(
            sheet, 1, [], db_keys=db_keys,
            check_start=dt.date(2026, 10, 28), check_end=dt.date(2026, 11, 3),
        )

    def test_missing_row_is_marked_transfer_not_deleted(self):
        """DB에 없는 기존 행은 사유를 '이관'으로 쓰고, 행 자체는 건드리지 않는다"""
        sheet = _sheet(("홍길동", "2026-10-29", ""), ("김이관", "2026-10-29", ""))
        updates, _, _, _, appended, transferred = self._run(sheet, {("홍길동", dt.date(2026, 10, 29))})

        self.assertEqual(len(transferred), 1)
        self.assertEqual(transferred[0]["name"], "김이관")
        self.assertEqual(appended, [])
        self.assertEqual(updates, [{"range": "I3", "values": [[s.TRANSFER_REASON]]}])

    def _transfer_sheet(self, rows):
        """'타 과정/타 기수 이관' 열이 있는 시트를 만듭니다. rows: (이름, 일자, 사유, 이관 과정)"""
        headers = HEADERS + [s.TRANSFER_COURSE_HEADERS[0]]
        body = []
        for name, date, reason, course in rows:
            row = [""] * len(headers)
            row[1], row[2], row[REASON_COL], row[-1] = date, name, reason, course
            body.append(row)
        return [headers] + body

    def test_transfer_without_course_is_collected_for_email(self):
        """사유가 '이관'이고 이관 과정이 빈칸이면 날짜와 무관하게 확인 목록에 올린다"""
        sheet = self._transfer_sheet([("빈칸이관", "2026-08-30", "이관", ""),
                                      ("기록됨", "2026-08-31", "이관", "에이전트 4기")])
        found = s.find_transfer_candidates(sheet, 1)

        self.assertEqual([m["name"] for m in found], ["빈칸이관"])
        self.assertEqual(found[0]["row"], 2)

    def test_transfer_with_course_is_excluded_from_email(self):
        """이관 과정이 기록된 행은 확인 목록에서 제외한다"""
        sheet = self._transfer_sheet([("기록됨", "2026-10-29", "이관", "리서처 20기")])

        self.assertEqual(s.find_transfer_candidates(sheet, 1), [])

    def test_transfer_candidates_ignore_reason_other_than_transfer(self):
        """사유가 이관이 아니면 이관 과정이 비어 있어도 확인 목록에 올리지 않는다"""
        sheet = self._transfer_sheet([("장기부재", "2026-10-29", "장기부재", "")])

        self.assertEqual(s.find_transfer_candidates(sheet, 1), [])

    def test_existing_reason_is_kept(self):
        """사유가 이미 적힌 행(탈락 등)은 '이관'으로 덮어쓰지 않는다"""
        sheet = _sheet(("박탈락", "2026-10-29", "일정불가"))
        updates, skipped, _, _, _, transferred = self._run(sheet, set())

        self.assertEqual(transferred, [])
        self.assertEqual(updates, [])
        self.assertTrue(any("일정불가" in msg for msg in skipped))

    def test_test_applicant_is_never_marked(self):
        """테스트 신청자는 DB에 없어도 이관 표시 대상이 아니다"""
        sheet = _sheet(("테스트계정", "2026-10-29", ""))
        updates, _, _, _, _, transferred = self._run(sheet, set())

        self.assertEqual(transferred, [])
        self.assertEqual(updates, [])

    def test_rows_outside_check_range_are_ignored(self):
        """대조 기간 밖(반영 시작일 이전, 종료일 이후) 행은 건드리지 않는다"""
        sheet = _sheet(("이전신청", "2026-10-27", ""), ("이후신청", "2026-11-04", ""))
        updates, _, _, _, _, transferred = self._run(sheet, set())

        self.assertEqual(transferred, [])
        self.assertEqual(updates, [])

    def test_no_reconcile_when_db_keys_missing(self):
        """db_keys가 없으면(기존 호출 방식) 명단 대조를 하지 않는다"""
        sheet = _sheet(("김이관", "2026-10-29", ""))
        result = s.build_updates(sheet, 1, [])
        self.assertEqual(result[5], [])
        self.assertEqual(result[0], [])


class ChatGptChannelTest(unittest.TestCase):
    """ChatGPT 광고(ChatGPT / da)를 채널로 묶고 광고별 캠페인·소재를 기록하는지 확인"""

    def test_chatgpt_da_is_its_own_channel(self):
        """소스가 ChatGPT, 매체가 da이면 'ChatGPT DA'로 분류한다 (대소문자 무관)"""
        self.assertEqual(s.classify_channel("ChatGPT", "da", "aiintelligence3rd_agentdata_image_261102"), "ChatGPT DA")
        self.assertEqual(s.classify_channel("chatgpt", "DA", ""), "ChatGPT DA")

    def test_chatgpt_organic_keeps_llm_channel(self):
        """기존 자연 유입(chatgpt.com)은 기존 'LLM' 채널을 유지한다"""
        self.assertEqual(s.classify_channel("chatgpt.com", "referral", ""), "LLM(GPT, 퍼플렉시티 등)")

    def test_chatgpt_records_campaign_and_content(self):
        """ChatGPT DA 행은 캠페인 구분과 유입 소재에 GA 캠페인·콘텐츠를 그대로 기록한다"""
        match = {"session_campaign": "aiintelligence3rd_agentdata_image_261102",
                 "session_content": "conversion_aiintelligence3rd_X", "session_term": "(not set)"}
        self.assertEqual(s.material_for("ChatGPT DA", match), "conversion_aiintelligence3rd_X")
        self.assertEqual(s.campaign_for("ChatGPT DA", match), "aiintelligence3rd_agentdata_image_261102")


class BirthCheckTest(unittest.TestCase):
    """생년월일 없음 사람 확인 항목 판정 테스트"""

    def test_confirmed_applicant_is_excluded(self):
        """확인 완료된 임현우(private_ai 2기)는 생년월일이 없어도 사람 확인 대상이 아니다"""
        self.assertFalse(s.needs_birth_check("private_ai", 2, "임현우", None))

    def test_unconfirmed_applicant_without_birth_is_flagged(self):
        """확인 목록에 없는 신청자는 생년월일이 없으면 사람 확인 대상이다"""
        self.assertTrue(s.needs_birth_check("private_ai", 2, "홍길동", None))

    def test_applicant_with_birth_is_not_flagged(self):
        """생년월일이 있으면 확인 목록과 무관하게 대상이 아니다"""
        self.assertFalse(s.needs_birth_check("private_ai", 2, "홍길동", dt.date(1990, 1, 1)))

    def test_same_name_other_cohort_is_still_flagged(self):
        """이름이 같아도 다른 기수는 확인 완료로 보지 않는다"""
        self.assertTrue(s.needs_birth_check("private_ai", 1, "임현우", None))


class ReviewTransferTest(unittest.TestCase):
    """2.3 사업팀 시트의 이관을 2.2 사유 칸에 반영하는 로직 테스트"""

    REVIEW_HEADERS = ["", "일자", "이름", "나이", "지원자 현황", "지원서 제출 주간", "지원서 처리 주간", "서류 합격",
                      "사유", "이관여부", "부재횟수", "인터뷰 합격", "사유", "이관여부"]

    def _review(self, *rows):
        """2.3 탭 형태(헤더 2행 + 데이터)의 값을 만듭니다. rows: (이름, 일자, 인터뷰 사유, 이관여부)"""
        body = []
        for name, date, reason, flag in rows:
            row = [""] * len(self.REVIEW_HEADERS)
            row[1] = date
            row[2] = name
            row[12] = reason
            row[13] = flag
            body.append(row)
        return [["", "어드민"], self.REVIEW_HEADERS] + body

    def test_finds_transfer_by_interview_reason(self):
        """인터뷰 사유 칸에 '이관'이 있으면 이관으로 찾고 날짜 시·분은 버린다"""
        review = self._review(("최낙영", "2026.10.18 07:08", "이관", "O"))
        self.assertEqual(s.find_review_transfers(review),
                         [{"name": "최낙영", "apply_date": dt.date(2026, 10, 18)}])

    def test_ignores_non_transfer_rows(self):
        """이관 표시가 없는 행은 찾지 않는다"""
        review = self._review(("홍길동", "2026.10.18 07:08", "미참석", ""))
        self.assertEqual(s.find_review_transfers(review), [])

    def test_missing_header_returns_empty(self):
        """헤더를 찾지 못하면 빈 목록을 돌려준다"""
        self.assertEqual(s.find_review_transfers([["아무거나"]]), [])

    def test_marks_empty_reason_before_check_range(self):
        """2.2 사유가 비어 있으면 신청일이 명단 기간 이전이어도 '이관'으로 표시한다"""
        sheet = _sheet(("최낙영", "2026-10-18", ""))
        transfers = [{"name": "최낙영", "apply_date": dt.date(2026, 10, 18)}]
        updates, notes, marked, _fmt, _added = s.build_review_transfer_updates(sheet, 1, transfers)
        self.assertEqual(updates, [{"range": "I2", "values": [[s.TRANSFER_REASON]]}])
        self.assertEqual(marked[0]["row"], 2)
        self.assertEqual(notes, [])

    def test_does_not_overwrite_existing_reason(self):
        """2.2 사유에 탈락 등 다른 사유가 있으면 덮어쓰지 않고 확인 목록에 남긴다"""
        sheet = _sheet(("최낙영", "2026-10-18", "단순변심"))
        transfers = [{"name": "최낙영", "apply_date": dt.date(2026, 10, 18)}]
        updates, notes, marked, _fmt, _added = s.build_review_transfer_updates(sheet, 1, transfers)
        self.assertEqual(updates, [])
        self.assertEqual(marked, [])
        self.assertTrue(any("사유 충돌" in n for n in notes))

    def test_appends_row_when_missing_in_2_2(self):
        """2.2에 행이 없으면 시트 맨 아래(마지막 데이터 다음 행)에 일자·이름·사유 '이관' 행을 추가한다"""
        sheet = _sheet(("다른사람", "2026-10-18", ""))
        transfers = [{"name": "최낙영", "apply_date": dt.date(2026, 10, 18)}]
        updates, notes, marked, format_src, appended_rows = s.build_review_transfer_updates(sheet, 1, transfers)
        self.assertEqual(appended_rows, [3])
        self.assertEqual(format_src, 2)
        self.assertTrue(marked[0]["appended"])
        values = {u["range"]: u["values"][0][0] for u in updates}
        self.assertEqual(values, {"B3": "2026-10-18", "C3": "최낙영", "I3": s.TRANSFER_REASON})

    def test_appends_once_per_person(self):
        """같은 이름·일자가 2.3에 중복되어도 2.2 행은 한 번만 추가한다"""
        sheet = _sheet()
        transfers = [{"name": "최낙영", "apply_date": dt.date(2026, 10, 18)},
                     {"name": "최낙영", "apply_date": dt.date(2026, 10, 18)}]
        _u, _n, marked, _f, appended_rows = s.build_review_transfer_updates(sheet, 1, transfers)
        self.assertEqual(appended_rows, [2])
        self.assertEqual(len(marked), 1)


if __name__ == "__main__":
    unittest.main()
