"""마케팅 액션 로그 읽기 (Google Sheet 탭)

저장소: config.ACTION_LOG_SHEET_ID 스프레드시트의 ACTION_LOG_SHEET_NAME 탭.
- 마케팅 팀이 시트에 직접 행을 추가·수정합니다 (시트 공유 권한으로 입력 권한을 관리).
- 대시보드는 기존 읽기 전용 서비스 계정 권한으로 읽기만 합니다 (쓰기 권한 불필요).
"""

import logging

import pandas as pd

from src.config import ACTION_LOG_SHEET_ID, ACTION_LOG_SHEET_NAME
from src.sheets_client import get_sheets_client

logger = logging.getLogger(__name__)

# 시트 헤더 (순서 무관, 이름으로 매칭)
ACTION_COLUMNS = [
    "변경일", "과정ID", "기수", "매체", "캠페인·소재", "변경유형", "변경내용",
    "변경이유", "담당자", "추후 확인 지표", "확인 예정일",
]
# 변경 유형 예시 (입력 가이드용, 목록 외 값도 허용)
CHANGE_TYPES = ["예산 조정", "소재 교체", "타깃 변경", "랜딩페이지 수정", "지원 절차·자격 안내 수정", "기타"]


def parse_action_log(rows: list) -> pd.DataFrame:
    """시트 값(2차원 리스트, 첫 행은 헤더)을 액션 로그 DataFrame으로 바꿉니다.

    Args:
        rows: gspread get_all_values() 결과 (첫 행 헤더)

    Returns:
        ACTION_COLUMNS 열을 가진 DataFrame. '변경일'이 날짜로 해석되지 않는 행은 제외합니다.
    """
    if not rows or len(rows) < 2:
        return pd.DataFrame(columns=ACTION_COLUMNS)

    header = [str(h).strip() for h in rows[0]]
    body = []
    for row in rows[1:]:
        padded = list(row) + [""] * (len(header) - len(row))
        record = {name: str(padded[idx]).strip() for idx, name in enumerate(header) if name}
        if any(record.values()):
            body.append(record)

    frame = pd.DataFrame(body)
    for col in ACTION_COLUMNS:
        if col not in frame.columns:
            frame[col] = ""

    frame["변경일"] = pd.to_datetime(frame["변경일"], errors="coerce").dt.normalize()
    frame["확인 예정일"] = pd.to_datetime(frame["확인 예정일"], errors="coerce").dt.normalize()
    invalid = frame["변경일"].isna() & frame["변경내용"].ne("")
    if invalid.any():
        logger.warning("액션 로그 날짜 형식 오류 %d건 제외", int(invalid.sum()))
    frame = frame[frame["변경일"].notna()].copy()
    return frame[ACTION_COLUMNS].sort_values("변경일").reset_index(drop=True)


def load_action_log() -> pd.DataFrame:
    """설정된 시트 탭에서 액션 로그를 읽습니다.

    Returns:
        parse_action_log() 결과. 시트 ID가 없거나 읽기에 실패하면 빈 DataFrame.
        실패 사유는 로그로 남기고 화면 쪽에서 안내합니다.
    """
    if not ACTION_LOG_SHEET_ID.strip():
        return pd.DataFrame(columns=ACTION_COLUMNS)

    try:
        client = get_sheets_client()
        if client is None:
            return pd.DataFrame(columns=ACTION_COLUMNS)
        worksheet = client.open_by_key(ACTION_LOG_SHEET_ID).worksheet(ACTION_LOG_SHEET_NAME)
        return parse_action_log(worksheet.get_all_values())
    except Exception as error:  # 시트 권한·이름 오류 등은 화면에서 안내
        logger.error("액션 로그 읽기 실패: %s", error)
        return pd.DataFrame(columns=ACTION_COLUMNS)


def filter_actions(actions: pd.DataFrame, course_id: str = None, cohort: int = None) -> pd.DataFrame:
    """과정·기수에 해당하는 액션만 고릅니다. 과정ID가 비어 있는 행은 '전체 적용'으로 보고 포함합니다.

    Args:
        actions: parse_action_log() 결과
        course_id: 과정ID (None이면 전체)
        cohort: 기수 (None이면 과정 전체)

    Returns:
        필터링된 DataFrame
    """
    if actions.empty:
        return actions
    mask = pd.Series(True, index=actions.index)
    if course_id:
        mask &= actions["과정ID"].isin([course_id, ""])
    if cohort is not None:
        cohort_text = actions["기수"].astype(str).str.replace("기", "", regex=False).str.strip()
        mask &= cohort_text.isin([str(cohort), ""])
    return actions[mask].reset_index(drop=True)


def before_after(daily: pd.DataFrame, change_date, window: int = 7) -> dict:
    """액션 전후 기간의 광고비·지원 수·CPA를 비교합니다. 단순 전후 비교이며 인과 효과가 아닙니다.

    Args:
        daily: date, 비용, 지원 열을 가진 일별 DataFrame (지원은 2.2 시트 지원자 수)
        change_date: 액션 날짜
        window: 전·후 비교 기간 (일)

    Returns:
        전·후 광고비, 지원 수, CPA(합계 기준). 한쪽 기간 데이터가 없으면 None 값.
    """
    change_date = pd.Timestamp(change_date).normalize()
    before = daily[(daily["date"] >= change_date - pd.Timedelta(days=window)) & (daily["date"] < change_date)]
    after = daily[(daily["date"] >= change_date) & (daily["date"] < change_date + pd.Timedelta(days=window))]

    def _summary(part):
        if part.empty:
            return {"days": 0, "비용": None, "지원": None, "CPA": None}
        cost, apps = float(part["비용"].sum()), float(part["지원"].sum())
        return {"days": len(part), "비용": cost, "지원": apps, "CPA": cost / apps if apps > 0 else None}

    return {"전": _summary(before), "후": _summary(after)}
