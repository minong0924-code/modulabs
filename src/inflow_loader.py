"""일자별 유입현황 로더 및 광고 지표 집계

데이터 원천: BigQuery `Modulabs_internal_DB.dash_daily_inflow` (scripts/export_inflow_to_bq.py가 매일 갱신)
지원자 분류와 인사이트 규칙은 src/metrics.py에 있습니다.
"""

import os
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2.service_account import Credentials

from src.config import WEEK_START_WEEKDAY

BQ_PROJECT = "modulabs-ga-workspace"
BQ_TABLE = f"{BQ_PROJECT}.Modulabs_internal_DB.dash_daily_inflow"
BQ_SCOPES = ["https://www.googleapis.com/auth/bigquery"]

# 화면에 쓰는 매체 순서 (틱톡은 raw 미확보로 제외, 시트의 '페이드(총합)'은 합계 행이라 제외)
BLOCK_ORDER = ["오가닉", "메타", "구글 DA", "구글 SA", "네이버 SA", "카카오 DA", "ChatGPT DA", "타게팅게이츠", "기타"]
# 집계 대상 지표 (시트 지표 이름)
METRICS = ["비용", "노출", "클릭", "페이지뷰", "CTA 클릭", "지원서 랜딩", "지원서 제출"]


def get_bigquery_client():
    """BigQuery 클라이언트를 Streamlit Secrets 또는 환경변수로 만듭니다.

    Returns:
        bigquery.Client 객체 (자격증명이 없으면 None)
    """
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
        elif os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
            info = json.loads(os.getenv("GCP_SERVICE_ACCOUNT_JSON"))
        else:
            return None
        credentials = Credentials.from_service_account_info(info, scopes=BQ_SCOPES)
        return bigquery.Client(project=BQ_PROJECT, credentials=credentials)
    except Exception as error:
        st.error(f"BigQuery 연결 실패: {error}")
        return None


def load_inflow(course_id: str, semester: int) -> pd.DataFrame:
    """과정·기수의 일자별 유입 데이터를 긴 형식으로 읽습니다.

    Args:
        course_id: 과정 ID (예: ai_agent)
        semester: 기수 번호

    Returns:
        일자·매체·지표 행 DataFrame (컬럼: date, block, metric, value, snapshot_at).
        어제까지의 데이터만 포함합니다. 연결 실패 시 빈 DataFrame.
    """
    client = get_bigquery_client()
    if client is None:
        return pd.DataFrame()
    sql = f"""
        SELECT date, block, metric, value, snapshot_at
        FROM `{BQ_TABLE}`
        WHERE course_id = @course_id AND semester = @semester
          AND date <= DATE_SUB(CURRENT_DATE('Asia/Seoul'), INTERVAL 1 DAY)
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("course_id", "STRING", course_id),
        bigquery.ScalarQueryParameter("semester", "INTEGER", semester),
    ])
    df = client.query(sql, job_config=job_config).to_dataframe()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df


def to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """긴 형식을 (일자, 매체) 행 · 지표 열 형식으로 바꿉니다.

    Args:
        long_df: load_inflow() 결과

    Returns:
        일자·매체별 지표 DataFrame. 지표 열이 없으면 0으로 채웁니다.
    """
    if long_df.empty:
        return pd.DataFrame(columns=["date", "block", *METRICS])
    long_df = long_df[long_df["block"].isin(BLOCK_ORDER)]
    wide = long_df.pivot_table(index=["date", "block"], columns="metric", values="value", aggfunc="sum", fill_value=0).reset_index()
    for metric in METRICS:
        if metric not in wide.columns:
            wide[metric] = 0.0
    return wide[["date", "block", *METRICS]]


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """비용 기반 지표와 전환율을 계산해 열로 추가합니다. 분모가 0이면 NaN입니다.

    Args:
        df: 지표 열이 있는 DataFrame (일자·매체 또는 기간·매체 단위)

    Returns:
        CTR, CPA(제출), 랜딩율, 제출율 열이 추가된 DataFrame
    """
    out = df.copy()
    out["CTR(%)"] = _safe_ratio(out["클릭"], out["노출"]) * 100
    out["CPA(제출)"] = _safe_ratio(out["비용"], out["지원서 제출"])
    out["CTA율(%)"] = _safe_ratio(out["CTA 클릭"], out["페이지뷰"]) * 100
    out["랜딩율(%)"] = _safe_ratio(out["지원서 랜딩"], out["CTA 클릭"]) * 100
    out["제출율(%)"] = _safe_ratio(out["지원서 제출"], out["지원서 랜딩"]) * 100
    return out


def _safe_ratio(numerator, denominator):
    """0으로 나누는 경우 NaN을 반환하는 비율 계산"""
    return numerator / denominator.where(denominator > 0)


def aggregate_period(wide: pd.DataFrame, start: date, end: date, by: str = "block") -> pd.DataFrame:
    """기간 안의 지표를 매체(또는 일자) 단위로 합칩니다.

    Args:
        wide: to_wide() 결과
        start: 시작일 (포함)
        end: 종료일 (포함)
        by: "block"이면 매체별, "date"이면 일자별로 합산

    Returns:
        지표 합계 DataFrame (비율 열 포함)
    """
    mask = (wide["date"] >= pd.Timestamp(start)) & (wide["date"] <= pd.Timestamp(end))
    part = wide[mask]
    if part.empty:
        return add_rates(pd.DataFrame(columns=[by, *METRICS]))
    grouped = part.groupby(by, as_index=False)[METRICS].sum()
    return add_rates(grouped)


def daily_totals(wide: pd.DataFrame) -> pd.DataFrame:
    """일자별 전체 합계 (매체 합산)를 계산합니다.

    Args:
        wide: to_wide() 결과

    Returns:
        일자별 지표 합계 DataFrame (비율 열 포함)
    """
    if wide.empty:
        return pd.DataFrame(columns=["date", *METRICS])
    totals = wide.groupby("date", as_index=False)[METRICS].sum()
    return add_rates(totals)


def weekly_totals(wide: pd.DataFrame) -> pd.DataFrame:
    """config.WEEK_START_WEEKDAY 기준 주 단위 매체별 합계를 계산합니다.

    Args:
        wide: to_wide() 결과

    Returns:
        주 시작일(week_start)·매체별 지표 DataFrame (비율 열 포함)
    """
    if wide.empty:
        return pd.DataFrame(columns=["week_start", "block", *METRICS])
    frame = wide.copy()
    frame["week_start"] = frame["date"] - pd.to_timedelta((frame["date"].dt.day_of_week - WEEK_START_WEEKDAY) % 7, unit="D")
    grouped = frame.groupby(["week_start", "block"], as_index=False)[METRICS].sum()
    return add_rates(grouped)


def week_start_of(day: date) -> date:
    """날짜가 속한 주의 시작일을 반환합니다 (config.WEEK_START_WEEKDAY 기준)."""
    return day - timedelta(days=(day.weekday() - WEEK_START_WEEKDAY) % 7)


def comparison_periods(selected_week_start: date, data_latest: date) -> dict:
    """선택한 주와 직전 주의 비교 기간을 만듭니다.

    선택한 주가 아직 끝나지 않았으면(데이터가 주 마지막 날 전에 끝남) 직전 주도 같은 요일까지만 자릅니다.

    Args:
        selected_week_start: 선택한 주의 시작일
        data_latest: 광고 데이터가 있는 마지막 날짜

    Returns:
        {"current": (시작, 종료), "previous": (시작, 종료), "complete": bool}
    """
    cur_end_full = selected_week_start + timedelta(days=6)
    complete = cur_end_full <= data_latest
    cur_end = cur_end_full if complete else data_latest
    elapsed_days = (cur_end - selected_week_start).days
    prev_start = selected_week_start - timedelta(days=7)
    prev_end = prev_start + timedelta(days=6 if complete else elapsed_days)
    return {"current": (selected_week_start, cur_end), "previous": (prev_start, prev_end), "complete": complete}


def recent_days(today: date, count: int = 7) -> list:
    """어제부터 거슬러 올라간 count일의 날짜 목록을 오래된 순으로 반환합니다 (오늘 데이터는 아직 없음)."""
    yesterday = today - timedelta(days=1)
    return [yesterday - timedelta(days=offset) for offset in range(count - 1, -1, -1)]
