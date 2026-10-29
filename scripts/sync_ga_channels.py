"""BigQuery 매칭 결과를 과정별 구글 시트 '2.2 일자별 신청현황'에 반영하는 스크립트.

흐름:
  1. sql/ga_applicant_match.sql을 날짜별로 실행해 내부 지원자 DB와 GA 유입 정보를 매칭
  2. 과정/기수별 시트를 읽어 같은 날짜·같은 이름의 행을 찾음
  3. 비어 있는 유입 채널/소재/캠페인 칸만 채움 (사람이 입력한 값은 덮어쓰지 않음)

기본값은 드라이런(시트 변경 없음)입니다. --apply 를 붙여야 실제로 기록합니다.
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

import gspread
from google.cloud import bigquery
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

# src 패키지 import를 위해 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import COURSE_MAPPING, COURSES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_ga_channels")

SQL_PATH = PROJECT_ROOT / "sql" / "ga_applicant_match.sql"
BQ_PROJECT = "modulabs-ga-workspace"
KST = dt.timezone(dt.timedelta(hours=9))

BQ_SCOPES = ["https://www.googleapis.com/auth/bigquery"]
# 시트 쓰기를 위해 읽기/쓰기 스코프 사용 (src/sheets_client.py의 읽기 전용 스코프와 별개)
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 시트에서 사용하는 컬럼명 (config.COLUMN_MAPPING 값과 동일)
TARGET_HEADERS = {
    "date": "일자",
    "name": "신청자 이름",
    "channel": "유입 채널",
    "material": "유입 소재 및 키워드",
    "campaign": "캠페인 구분",
}

# 헤더 행 자동 탐지 시 반드시 있어야 하는 컬럼
REQUIRED_HEADER_TITLES = ("일자", "신청자 이름")

# 시트에 없을 수 있어서 없으면 건너뛰는 컬럼
OPTIONAL_FIELDS = {"campaign"}

# 기록에서 제외할 신청자 이름 (대행사 테스트 데이터)
EXCLUDED_NAMES = {"김보현"}

# 재직자 과정은 캠페인 구분을 기록하지 않음
EMPLOYED_SKIP_FIELDS = {"campaign"}

# 시트의 '일자' 셀 형식 후보 (실제 형식과 다르면 여기에 추가)
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%Y. %m. %d.",
    "%Y-%m-%d %H:%M:%S",
]

# GA에서 값이 없을 때 쓰는 placeholder (시트에 기록하지 않음)
GA_PLACEHOLDERS = {"(not set)", "(not provided)"}


def get_credentials(scopes):
    """GCP_SERVICE_ACCOUNT_JSON 환경변수에서 서비스 계정 자격증명을 로드합니다.

    Args:
        scopes: 요청할 OAuth 스코프 목록

    Returns:
        google.oauth2 Credentials 객체
    """
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON 환경변수가 없습니다.")
    return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)


def parse_date(value):
    """문자열을 date로 변환합니다. 형식이 맞지 않으면 None을 반환합니다.

    Args:
        value: 시트 셀 또는 BigQuery 타임스탬프 문자열

    Returns:
        datetime.date 또는 None
    """
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def cell(row, idx):
    """행에서 idx 위치의 값을 공백 제거 후 반환합니다. 범위를 벗어나면 빈 문자열입니다.

    Args:
        row: 시트 한 행 (문자열 리스트)
        idx: 0-based 컬럼 인덱스

    Returns:
        공백이 제거된 셀 값
    """
    return row[idx].strip() if idx < len(row) else ""


def join_material(content, term):
    """GA의 content/term 값을 '유입 소재 및 키워드' 한 칸 값으로 합칩니다.

    Args:
        content: GA 캠페인 소재(content) 값
        term: GA 검색 키워드(term) 값

    Returns:
        '소재 / 키워드' 형식 문자열 (둘 다 없으면 빈 문자열)
    """
    parts = [p for p in (content, term) if p and p not in GA_PLACEHOLDERS]
    return " / ".join(parts)


def fetch_matched_rows(bq_client, target_date):
    """특정 날짜의 지원자-GA 매칭 결과를 BigQuery에서 가져옵니다.

    Args:
        bq_client: bigquery.Client 객체
        target_date: 처리할 지원 일자 (datetime.date)

    Returns:
        매칭 결과 dict 목록
    """
    sql = SQL_PATH.read_text(encoding="utf-8")
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("target_date", "DATE", target_date)]
    )
    rows = bq_client.query(sql, job_config=job_config).result()
    return [dict(row.items()) for row in rows]


def find_header_row(sheet_values, default_row):
    """헤더 행을 찾습니다. 설정된 행에 필수 컬럼이 없으면 상단 15행에서 다시 찾습니다.

    Args:
        sheet_values: worksheet.get_all_values() 결과 (2차원 리스트)
        default_row: config에 설정된 헤더 행 번호 (1-based)

    Returns:
        실제 헤더 행 번호 (1-based)
    """
    def has_required_headers(row_no):
        """해당 행에 필수 헤더가 모두 있는지 확인합니다."""
        if row_no > len(sheet_values):
            return False
        titles = [h.strip() for h in sheet_values[row_no - 1]]
        return all(title in titles for title in REQUIRED_HEADER_TITLES)

    if has_required_headers(default_row):
        return default_row
    for row_no in range(1, min(15, len(sheet_values)) + 1):
        if has_required_headers(row_no):
            logger.info("헤더 행 자동 탐지: %d행 (설정값 %d행)", row_no, default_row)
            return row_no
    raise ValueError(f"상단 15행에서 {REQUIRED_HEADER_TITLES} 헤더를 찾지 못했습니다.")


def build_updates(sheet_values, header_row, matched_rows, skip_fields=frozenset()):
    """매칭 결과로 시트에 쓸 셀 업데이트 목록을 만듭니다.

    Args:
        sheet_values: worksheet.get_all_values() 결과 (2차원 리스트)
        header_row: 헤더 행 번호 (1-based)
        matched_rows: 해당 과정/기수의 BigQuery 매칭 결과 목록
        skip_fields: 기록하지 않을 필드 집합 (예: 재직자 과정의 campaign)

    Returns:
        (updates, skipped): gspread batch_update용 dict 목록, 건너뛴 사유 목록
    """
    header_row = find_header_row(sheet_values, header_row)
    headers = [h.strip() for h in sheet_values[header_row - 1]]
    col_index = {}
    for key, title in TARGET_HEADERS.items():
        if key in skip_fields:
            continue
        if title in headers:
            col_index[key] = headers.index(title)
        elif key in OPTIONAL_FIELDS:
            # 선택 컬럼이 없는 시트는 해당 칸만 기록하지 않음
            logger.warning("'%s' 컬럼이 없어 이 칸은 기록하지 않습니다.", title)
        else:
            raise ValueError(f"시트에 '{title}' 컬럼이 없습니다. {header_row}행 헤더: {headers}")

    # (이름, 날짜) → 시트 행 번호 목록 인덱스
    sheet_index = defaultdict(list)
    for row_no, row in enumerate(sheet_values[header_row:], start=header_row + 1):
        name = cell(row, col_index["name"])
        date = parse_date(cell(row, col_index["date"]))
        if name and date:
            sheet_index[(name, date)].append(row_no)

    updates = []
    skipped = []
    for match in matched_rows:
        name = match["name"].strip()
        date = parse_date(match["db_submitted_at"])
        row_nos = sheet_index.get((name, date), [])
        if len(row_nos) != 1:
            skipped.append(f"{name} {date}: 시트 매칭 {len(row_nos)}건")
            continue

        row_no = row_nos[0]
        row = sheet_values[row_no - 1]
        values = {
            "channel": match["session_source"],
            "material": join_material(match["session_content"], match["session_term"]),
            "campaign": match["session_campaign"],
        }
        for field, value in values.items():
            # 컬럼이 없거나 이미 값이 있으면 건드리지 않음 (사람이 입력한 내용 보호)
            if field not in col_index or not value or value in GA_PLACEHOLDERS or cell(row, col_index[field]):
                continue
            updates.append({
                "range": rowcol_to_a1(row_no, col_index[field] + 1),
                "values": [[value]],
            })

    return updates, skipped


def group_by_cohort(bq_client, start, end):
    """기간 내 매칭 결과를 (과정ID, 기수) 단위로 묶습니다.

    Args:
        bq_client: bigquery.Client 객체
        start: 시작일 (datetime.date, 포함)
        end: 종료일 (datetime.date, 포함)

    Returns:
        {(과정ID, 기수): 매칭 결과 목록} dict
    """
    grouped = defaultdict(list)
    day = start
    while day <= end:
        for row in fetch_matched_rows(bq_client, day):
            if row["name"].strip() in EXCLUDED_NAMES:
                logger.info("테스트 데이터 제외: %s", row["name"])
                continue
            course_id = COURSE_MAPPING.get(row["course"])
            if course_id is None:
                logger.info("미매핑 과정 건너뜀: %s (%s)", row["course"], row["name"])
                continue
            grouped[(course_id, int(row["semester"]))].append(row)
        logger.info("%s 매칭 조회 완료", day)
        day += dt.timedelta(days=1)
    return grouped


def parse_cli_date(text):
    """CLI 인자 YYYY-MM-DD를 date로 변환합니다.

    Args:
        text: 날짜 문자열

    Returns:
        datetime.date
    """
    return dt.datetime.strptime(text, "%Y-%m-%d").date()


def main():
    """CLI 진입점: 기간을 조회해 과정별 시트에 유입 정보를 기록합니다."""
    parser = argparse.ArgumentParser(description="BigQuery 매칭 결과를 과정별 시트에 기록")
    parser.add_argument("--start", type=parse_cli_date, help="시작일 YYYY-MM-DD (기본: 어제 KST)")
    parser.add_argument("--end", type=parse_cli_date, help="종료일 YYYY-MM-DD (기본: 시작일)")
    parser.add_argument("--apply", action="store_true", help="실제로 시트에 기록 (없으면 드라이런)")
    args = parser.parse_args()

    yesterday = dt.datetime.now(KST).date() - dt.timedelta(days=1)
    start = args.start or yesterday
    end = args.end or start
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("실행 모드: %s, 기간: %s ~ %s", mode, start, end)

    bq_client = bigquery.Client(project=BQ_PROJECT, credentials=get_credentials(BQ_SCOPES))
    gs_client = gspread.authorize(get_credentials(SHEETS_SCOPES))

    grouped = group_by_cohort(bq_client, start, end)
    for (course_id, semester), rows in sorted(grouped.items()):
        cohort = COURSES.get(course_id, {}).get("cohorts", {}).get(semester)
        if cohort is None:
            logger.warning("config에 없는 기수: %s %s기 (%d건)", course_id, semester, len(rows))
            continue

        label = f"{course_id} {semester}기"
        try:
            worksheet = gs_client.open_by_key(cohort["sheet_id"]).worksheet(cohort["sheet_name"])
            is_employed = COURSES[course_id]["type"] == "employed"
            skip_fields = EMPLOYED_SKIP_FIELDS if is_employed else frozenset()
            updates, skipped = build_updates(
                worksheet.get_all_values(), cohort["header_row"], rows, skip_fields
            )
        except Exception:
            # 한 시트의 문제가 다른 과정/기수 처리를 막지 않도록 건너뜀
            logger.exception("[%s] 시트 처리 실패, 다음 기수로 넘어감", label)
            continue

        for reason in skipped:
            logger.warning("[%s] 건너뜀 - %s", label, reason)

        logger.info("[%s] 매칭 %d건, 기록 대상 셀 %d개", label, len(rows), len(updates))
        for update in updates:
            logger.info("  %s → %s", update["range"], update["values"][0][0])

        if args.apply and updates:
            worksheet.batch_update(updates, value_input_option="RAW")
            logger.info("[%s] 시트 기록 완료", label)


if __name__ == "__main__":
    main()
