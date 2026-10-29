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
import re
import sys
from collections import defaultdict
from pathlib import Path

import gspread
from google.api_core.exceptions import NotFound
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
    "age": "연령대",
}

# 헤더 행 자동 탐지 시 반드시 있어야 하는 컬럼
REQUIRED_HEADER_TITLES = ("일자", "신청자 이름")

# 시트에 없을 수 있어서 없으면 건너뛰는 컬럼
OPTIONAL_FIELDS = {"campaign", "age"}

# 이 날짜 이전 신청자는 기록하지 않음 (기존 시트 데이터 보호, 신규 신청분부터 반영)
APPLY_START_DATE = dt.date(2026, 10, 28)

# 오늘 미리 기록한 신청자 중, GA 데이터가 갱신되는 다음 날 다시 확인해서 덮어써야 하는 대상
# 키: 신청일(YYYY-MM-DD), 값: 신청자 이름 집합
REFRESH_APPLICANTS = {
    "2026-10-29": {"박재성", "임리원", "장재선", "이경수", "박은주", "이조원"},
}
# 다시 확인 대상의 덮어쓰기 가능 필드 (연령대는 생년월일 기준이라 제외)
REFRESHABLE_FIELDS = {"channel", "material", "campaign"}

# 기본 정보는 GA와 무관하게 기록, 유입 정보는 GA 데이터가 준비된 날짜만 기록
BASE_FIELDS = {"date", "name", "age"}
GA_FIELDS = {"channel", "material", "campaign"}

# 자동으로 기록한 유입 정보 내역 (다음 실행에서 자동 입력값인지 판단하는 데 사용)
LOG_TABLE_ID = f"{BQ_PROJECT}.Modulabs_internal_DB.sheet_auto_log"
GA_EVENTS_DATASET = f"{BQ_PROJECT}.analytics_373566527"

# 기록에서 제외할 신청자 이름 (대행사 테스트 데이터)
EXCLUDED_NAMES = {"김보현", "고유진"}

# 재직자 과정은 캠페인 구분을 기록하지 않음
EMPLOYED_SKIP_FIELDS = {"campaign", "age"}

# GA (source, medium) → 시트 유입 채널 (기존 시트 입력값과 대조해 학습한 결과)
# medium이 None이면 해당 source의 모든 medium에 적용
CHANNEL_BY_SOURCE_MEDIUM = {
    ("meta", "da"): "메타",
    ("kakao", "cpc"): "카카오 DA",
    ("naver", "bsa_pc"): "네이버 브검",
    ("naver", "bsa_mo"): "네이버 브검",
    ("naver", "cpc"): "네이버 SA",
    ("google", "organic"): "구글 검색",
    ("naver", "organic"): "네이버 검색",
    ("m.search.naver.com", "referral"): "네이버 검색",
    ("direct", "(none)"): "직접 지원",
    ("(direct)", "(none)"): "직접 지원",
    ("kauth.kakao.com", "referral"): "직접 지원",
    ("apply.aiffel.io", "referral"): "직접 지원",
    ("community", "board_all"): "커뮤니티/버티컬",
    ("chatgpt.com", None): "LLM(GPT, 퍼플렉시티 등)",
    ("kakao", "list_plus_friends"): "카카오 플러스친구",
    ("kakao", "mail_plus_friends"): "카카오 플러스친구",
    ("kakao", "message_plus_friends"): "카카오 플러스친구",
    ("stibee", None): "모두/광고레터",
    ("solapi", None): "마수동 문자",
    ("youtube", "shorts_all"): "기타(유가)",
    ("instagram", "shorts_all"): "기타(유가)",
    ("instagram", "board_all"): "기타(유가)",
    ("naver", "blog_all"): "기타(유가)",
    ("etc", "board_all"): "HRD Net",
    ("goyong24", "referral"): "HRD Net",
    ("work24.go.kr", "referral"): "HRD Net",
}

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

# GA가 유입 원본이 없을 때 캠페인에 붙이는 기본값 (캠페인 구분에 기록하지 않음)
GA_DEFAULT_CAMPAIGNS = {"(direct)", "(referral)", "(organic)"}


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


def classify_channel(source, medium, campaign):
    """GA 유입 정보로 시트의 '유입 채널' 이름을 정합니다. 판단할 수 없으면 None.

    Args:
        source: GA session_source 값
        medium: GA session_medium 값
        campaign: GA session_campaign 값 (구글 DA/SA 구분에 사용)

    Returns:
        유입 채널 이름 또는 None
    """
    if (source, medium) == ("google", "cpc"):
        # 구글 광고는 캠페인명으로 DA와 검색광고(SA)를 구분
        if re.search(r"pmax|dgen", campaign or "", re.IGNORECASE):
            return "구글 DA"
        if re.search(r"(^|_)sa($|_)", campaign or "", re.IGNORECASE):
            return "구글 SA"
        return None
    return CHANNEL_BY_SOURCE_MEDIUM.get((source, medium)) or CHANNEL_BY_SOURCE_MEDIUM.get((source, None))


def is_meta_ad(match):
    """GA 값에 메타 광고 흔적이 있는지 확인합니다.

    광고 ID(18자리 숫자), 'conversion_' 캠페인명, '_image/_video/_slide' 소재명 중 하나면 메타 광고로 봅니다.

    Args:
        match: BigQuery 매칭 결과 한 건

    Returns:
        메타 광고 흔적이 있으면 True
    """
    campaign = match["session_campaign"] or ""
    content = match["session_content"] or ""
    term = match["session_term"] or ""
    return (
        bool(re.fullmatch(r"\d{18}", term))
        or campaign.startswith("conversion_")
        or bool(re.search(r"_(image|video|slide)(_\d{6})?$", content, re.IGNORECASE))
    )


def shorten_name(value):
    """GA 소재명(content/term)에서 과정명, 날짜, 형식(image/video/slide)을 제거해 짧은 이름으로 만듭니다.

    예: 'aiagent_jeju1_image_260609' → 'jeju1'

    Args:
        value: GA 소재명 값

    Returns:
        줄인 소재명
    """
    parts = [p for p in (value or "").split("_") if p]
    if len(parts) >= 3:
        parts = parts[1:]
    if parts and re.fullmatch(r"\d{6}", parts[-1]):
        parts = parts[:-1]
    if len(parts) >= 2 and parts[-1].lower() in ("image", "video", "slide"):
        parts = parts[:-1]
    return "_".join(parts)


def material_for(channel, match):
    """유입 채널에 맞는 '유입 소재 및 키워드' 값을 정합니다.

    Args:
        channel: 분류된 유입 채널 이름
        match: BigQuery 매칭 결과 한 건

    Returns:
        기록할 소재/키워드 문자열 (기록하지 않는 채널이면 빈 문자열)
    """
    if channel == "메타":
        return shorten_name(match["session_content"])
    if channel == "카카오 DA":
        return shorten_name(match["session_term"])
    if channel in ("네이버 브검", "구글 SA"):
        return match["session_term"]
    if channel == "네이버 SA":
        # 네이버 SA의 키워드 뒤에 붙는 광고 ID(_nad-…)는 제외
        return match["session_term"].split("_nad-")[0]
    return ""


def campaign_for(channel, match):
    """유입 채널에 맞는 '캠페인 구분' 값을 정합니다.

    Args:
        channel: 분류된 유입 채널 이름
        match: BigQuery 매칭 결과 한 건

    Returns:
        기록할 캠페인 문자열 (기록하지 않는 채널이면 빈 문자열)
    """
    if channel in ("메타", "구글 DA", "카카오 DA"):
        campaign = match["session_campaign"] or ""
        if campaign in GA_DEFAULT_CAMPAIGNS:
            # GA가 붙인 기본값(유입 원본 없음)은 캠페인으로 기록하지 않음
            return ""
        # 카카오 시트 캠페인명은 'Aiffel_' 접두어 없이 기록됨
        return re.sub(r"^Aiffel_", "", campaign)
    return ""


def age_group_of(birth, apply_date):
    """생년월일과 신청일로 연령대 표기를 만듭니다 (만 나이 기준, 50대 이상은 한 묶음).

    기존 시트 값과 대조한 결과 98% 일치하는 규칙입니다.

    Args:
        birth: 생년월일 (datetime.date 또는 None)
        apply_date: 신청일 (datetime.date 또는 None)

    Returns:
        '10대', '20대', ..., '50대 이상' (정보가 없으면 빈 문자열)
    """
    if birth is None or apply_date is None:
        return ""
    age = apply_date.year - birth.year - ((apply_date.month, apply_date.day) < (birth.month, birth.day))
    if age >= 50:
        return "50대 이상"
    if age < 20:
        return "10대"
    return f"{age // 10 * 10}대"


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


def last_data_row(sheet_values, header_row, col_index):
    """이름 또는 일자가 있는 마지막 행 번호를 반환합니다. 데이터가 없으면 헤더 행입니다.

    Args:
        sheet_values: worksheet.get_all_values() 결과 (2차원 리스트)
        header_row: 헤더 행 번호 (1-based)
        col_index: 컬럼 키별 0-based 인덱스

    Returns:
        마지막 데이터 행 번호 (1-based)
    """
    last = header_row
    for row_no, row in enumerate(sheet_values[header_row:], start=header_row + 1):
        if cell(row, col_index["name"]) or cell(row, col_index["date"]):
            last = row_no
    return last


def date_separator_of(sheet_values, header_row, col_index):
    """기존 일자 셀의 구분 기호('-', '.', '/')를 찾습니다. 찾지 못하면 '-'입니다.

    Args:
        sheet_values: worksheet.get_all_values() 결과 (2차원 리스트)
        header_row: 헤더 행 번호 (1-based)
        col_index: 컬럼 키별 0-based 인덱스

    Returns:
        날짜 구분 기호 문자열
    """
    for row in reversed(sheet_values[header_row:]):
        text = cell(row, col_index["date"])
        if parse_date(text):
            for sep in (".", "/", "-"):
                if sep in text:
                    return sep
    return "-"


def format_date(day, sep):
    """date를 시트 일자 표기(YYYY{sep}MM{sep}DD) 문자열로 바꿉니다.

    Args:
        day: 날짜 (datetime.date)
        sep: 구분 기호

    Returns:
        표기에 맞춘 날짜 문자열
    """
    return f"{day:%Y}{sep}{day:%m}{sep}{day:%d}"


def can_write_ga(current, value, field, refresh, last_auto):
    """유입 정보 칸을 새 GA 값으로 써도 되는지 판단합니다.

    - 칸이 비어 있으면 쓴다.
    - 다시 확인 대상(REFRESH_APPLICANTS)이면 값이 다를 때 덮어쓴다.
    - 현재 값이 자동 기록 내역과 같으면(사람이 고치지 않은 자동 입력값) 새 값이 다를 때 덮어쓴다.
    - 그 밖(사람이 직접 입력한 값)은 건드리지 않는다.

    Args:
        current: 시트의 현재 값
        value: 새로 계산한 GA 값
        field: 항목 이름 (channel, material, campaign)
        refresh: 다시 확인 대상 여부
        last_auto: 마지막으로 자동 기록한 값 (없으면 None)

    Returns:
        쓰면 True
    """
    if not current:
        return True
    if current == value:
        return False
    if refresh and field in REFRESHABLE_FIELDS:
        return True
    return last_auto is not None and current == last_auto


def build_updates(sheet_values, header_row, matched_rows, skip_fields=frozenset(), auto_log=None):
    """매칭 결과로 시트에 쓸 셀 업데이트 목록을 만듭니다.

    Args:
        sheet_values: worksheet.get_all_values() 결과 (2차원 리스트)
        header_row: 헤더 행 번호 (1-based)
        matched_rows: 해당 과정/기수의 BigQuery 매칭 결과 목록 (_ga_ready 표시 포함)
        skip_fields: 기록하지 않을 필드 집합 (예: 재직자 과정의 campaign)
        auto_log: {(이름, 신청일, 항목): 마지막 자동 기록 값} dict

    Returns:
        (updates, skipped, written): gspread batch_update용 dict 목록, 건너뛴 사유 목록,
        자동 기록 로그에 남길 항목 목록
    """
    auto_log = auto_log or {}
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

    # 신규 신청자는 데이터 맨 아래 다음 행에 추가 (일자 표기는 기존 행 형식과 맞춤)
    next_row = last_data_row(sheet_values, header_row, col_index) + 1
    date_sep = date_separator_of(sheet_values, header_row, col_index)

    updates = []
    skipped = []
    written = []
    appended = set()
    for match in matched_rows:
        name = match["name"].strip()
        date = parse_date(match["db_submitted_at"])
        ga_on = match.get("_ga_ready", False)
        channel = classify_channel(match["session_source"], match["session_medium"], match["session_campaign"])
        if channel == "직접 지원" and is_meta_ad(match):
            # GA가 출처를 놓쳤지만 메타 광고 흔적이 있으면 메타로 분류
            channel = "메타"
        values = {
            "channel": channel or "",
            "material": material_for(channel, match),
            "campaign": campaign_for(channel, match),
            "age": age_group_of(match.get("applicant_birth"), date),
        }
        row_nos = sheet_index.get((name, date), [])

        if not row_nos:
            if (name, date) in appended:
                continue
            appended.add((name, date))
            new_values = {"date": format_date(date, date_sep), "name": name, **values}
            for field, value in new_values.items():
                if field not in col_index or not value or value in GA_PLACEHOLDERS:
                    continue
                if field in GA_FIELDS and not ga_on:
                    continue
                updates.append({
                    "range": rowcol_to_a1(next_row, col_index[field] + 1),
                    "values": [[value]],
                })
                if field in GA_FIELDS:
                    written.append({"name": name, "apply_date": date, "field": field, "value": value})
            logger.info("신규 행 추가: %d행 %s %s (채널: %s)", next_row, date, name, channel or "미분류")
            next_row += 1
            continue

        if len(row_nos) != 1:
            skipped.append(f"{name} {date}: 시트 매칭 {len(row_nos)}건")
            continue

        row_no = row_nos[0]
        row = sheet_values[row_no - 1]
        refresh = name in REFRESH_APPLICANTS.get(date.isoformat(), set())
        for field, value in values.items():
            if field not in col_index or not value or value in GA_PLACEHOLDERS:
                continue
            current = cell(row, col_index[field])
            if field in GA_FIELDS:
                if not ga_on:
                    continue
                last_auto = auto_log.get((name, date.isoformat(), field))
                if not can_write_ga(current, value, field, refresh, last_auto):
                    continue
                written.append({"name": name, "apply_date": date, "field": field, "value": value})
            elif current:
                # 기본 정보(연령대)는 비어 있을 때만 채움
                continue
            updates.append({
                "range": rowcol_to_a1(row_no, col_index[field] + 1),
                "values": [[value]],
            })

    return updates, skipped, written


def is_test_applicant(name):
    """테스트 신청자인지 확인합니다. 이름에 '테스트'가 들어가거나 제외 목록에 있으면 True입니다.

    Args:
        name: 신청자 이름

    Returns:
        테스트 신청자이면 True
    """
    name = (name or "").strip()
    return "테스트" in name or name in EXCLUDED_NAMES


def ga_ready(bq_client, day):
    """해당 날짜의 GA 일별 데이터가 준비되었는지 확인합니다.

    Args:
        bq_client: bigquery.Client 객체
        day: 확인할 날짜 (datetime.date)

    Returns:
        GA 일별 테이블이 있으면 True
    """
    try:
        bq_client.get_table(f"{GA_EVENTS_DATASET}.events_{day:%Y%m%d}")
        return True
    except NotFound:
        return False


def ensure_log_table(bq_client):
    """자동 기록 로그 테이블이 없으면 만듭니다.

    Args:
        bq_client: bigquery.Client 객체
    """
    try:
        bq_client.get_table(LOG_TABLE_ID)
    except NotFound:
        schema = [
            bigquery.SchemaField("written_at", "TIMESTAMP"),
            bigquery.SchemaField("course_id", "STRING"),
            bigquery.SchemaField("semester", "INTEGER"),
            bigquery.SchemaField("apply_date", "DATE"),
            bigquery.SchemaField("name", "STRING"),
            bigquery.SchemaField("field", "STRING"),
            bigquery.SchemaField("value", "STRING"),
        ]
        bq_client.create_table(bigquery.Table(LOG_TABLE_ID, schema=schema))
        logger.info("자동 기록 로그 테이블을 만들었습니다: %s", LOG_TABLE_ID)


def fetch_auto_log(bq_client):
    """자동 기록 로그에서 (이름, 신청일, 항목)별 마지막 자동 기록 값을 가져옵니다.

    Args:
        bq_client: bigquery.Client 객체

    Returns:
        {(이름, 신청일 ISO 문자열, 항목): 값} dict
    """
    query = f"""
        SELECT name, CAST(apply_date AS STRING) AS apply_date, field, value
        FROM `{LOG_TABLE_ID}`
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY name, apply_date, field ORDER BY written_at DESC
        ) = 1
    """
    return {(r["name"], r["apply_date"], r["field"]): r["value"] for r in bq_client.query(query).result()}


def append_auto_log(bq_client, course_id, semester, entries):
    """자동 기록한 유입 정보를 로그 테이블에 추가합니다.

    Args:
        bq_client: bigquery.Client 객체
        course_id: 과정 ID
        semester: 기수
        entries: build_updates가 반환한 written 목록
    """
    if not entries:
        return
    written_at = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = [
        {
            "written_at": written_at,
            "course_id": course_id,
            "semester": semester,
            "apply_date": e["apply_date"].isoformat(),
            "name": e["name"],
            "field": e["field"],
            "value": e["value"],
        }
        for e in entries
    ]
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    bq_client.load_table_from_json(rows, LOG_TABLE_ID, job_config=job_config).result()


def group_by_cohort(bq_client, start, end, ready):
    """기간 내 매칭 결과를 (과정ID, 기수) 단위로 묶습니다.

    Args:
        bq_client: bigquery.Client 객체
        start: 시작일 (datetime.date, 포함)
        end: 종료일 (datetime.date, 포함)
        ready: {날짜: GA 준비 여부} dict

    Returns:
        {(과정ID, 기수): 매칭 결과 목록} dict
    """
    grouped = defaultdict(list)
    day = start
    while day <= end:
        if day < APPLY_START_DATE:
            logger.info("%s는 반영 시작일(%s) 이전이라 건너뜀", day, APPLY_START_DATE)
            day += dt.timedelta(days=1)
            continue
        for row in fetch_matched_rows(bq_client, day):
            if is_test_applicant(row["name"]):
                logger.info("테스트 데이터 제외: %s", row["name"])
                continue
            course_id = COURSE_MAPPING.get(row["course"])
            if course_id is None:
                logger.info("미매핑 과정 건너뜀: %s (%s)", row["course"], row["name"])
                continue
            row["_ga_ready"] = ready.get(day, False)
            grouped[(course_id, int(row["semester"]))].append(row)
        logger.info("%s 매칭 조회 완료 (GA 준비: %s)", day, ready.get(day, False))
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
    """CLI 진입점: 기본 정보는 바로, 유입 정보는 GA가 준비된 날짜만 과정별 시트에 기록합니다."""
    parser = argparse.ArgumentParser(description="BigQuery 매칭 결과를 과정별 시트에 기록")
    parser.add_argument("--start", type=parse_cli_date, help="시작일 YYYY-MM-DD (기본: 최근 7일 KST)")
    parser.add_argument("--end", type=parse_cli_date, help="종료일 YYYY-MM-DD (기본: 어제 KST)")
    parser.add_argument("--apply", action="store_true", help="실제로 시트에 기록 (없으면 드라이런)")
    args = parser.parse_args()

    yesterday = dt.datetime.now(KST).date() - dt.timedelta(days=1)
    if args.start:
        start, end = args.start, args.end or args.start
    else:
        # 주말 등 PC가 꺼져 DB 추출이 밀린 경우와 GA가 늦게 올라오는 경우를 위해 최근 7일을 함께 확인
        start, end = yesterday - dt.timedelta(days=6), args.end or yesterday
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("실행 모드: %s, 기간: %s ~ %s", mode, start, end)

    bq_client = bigquery.Client(project=BQ_PROJECT, credentials=get_credentials(BQ_SCOPES))
    gs_client = gspread.authorize(get_credentials(SHEETS_SCOPES))
    ensure_log_table(bq_client)

    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    ready = {day: ga_ready(bq_client, day) for day in days}
    auto_log = fetch_auto_log(bq_client)
    grouped = group_by_cohort(bq_client, start, end, ready)

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
            updates, skipped, written = build_updates(
                worksheet.get_all_values(), cohort["header_row"], rows, skip_fields, auto_log
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
            append_auto_log(bq_client, course_id, semester, written)


if __name__ == "__main__":
    main()
