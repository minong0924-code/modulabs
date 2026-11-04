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


if __name__ == "__main__":
    unittest.main()
