"""모두의연구소 마케팅 대시보드 - Streamlit 메인 앱

화면 구성
- 📈 종합 현황: 과정·기수별 모집 목표, 전형 현황, 예산·CPA, 매체·사유
- 📅 주차별 현황: 주 단위 매체 효율, 전주 대비, 지원자 전형 결과, 인사이트
- 📆 일자별 현황: 일별 추이, 7일 지표, 데이터 상태, 마케팅 액션 로그
- ⚙️ 설정·지표 정의: 지표 정의, 설정값, 분류 규칙, 데이터 연결 상태

집계 로직은 src/metrics.py에 있고, 이 파일은 화면 배치만 담당합니다.
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.action_log import CHANGE_TYPES, before_after, filter_actions, load_action_log
from src.charts import (
    create_applicant_funnel_chart,
    create_daily_timeline_chart,
    create_weekly_cost_applicant_chart,
)
from src.config import (
    ACTION_LOG_SHEET_ID,
    ACTION_LOG_SHEET_NAME,
    APPLICANT_DOWN_RATIO,
    AD_COST_INCLUDES_VAT_AND_FEE,
    BUDGET_PACE_GAP_PT,
    CHANNEL_GROUP_MAP,
    COHORT_SETTINGS,
    COST_UP_RATIO,
    COURSES,
    CPA_BETTER_RATIO,
    CPA_WORSE_RATIO,
    DEFAULT_COHORT_SETTING,
    IN_PROGRESS_ALERT,
    MIN_COST_FOR_CPA,
    MIN_DAILY_APPLICANTS_STABLE,
    MIN_SAMPLE_FOR_INSIGHT,
    MISSING_CHANNEL_ALERT,
    REASON_SHARE_ALERT,
    RECRUITING_COHORTS,
)
from src.data_loader import load_applicants, load_apply_raw
from src.sheets_client import get_ad_sheet_date_range
from src.inflow_loader import (
    comparison_periods,
    daily_totals,
    load_inflow,
    to_wide,
    week_start_of,
)
from src.metrics import (
    REJECTION_KIND_DOC,
    weekly_comparison_table,
    UNCLASSIFIED,
    ad_coverage,
    application_mask,
    build_rule_insights,
    change_notes,
    channel_quality_table,
    recommended_actions,
    small_sample_checklist,
    efficiency_actions,
    weekly_narrative,
    compare_group_tables,
    group_period_table,
    missing_channel_rate,
    pct_change,
    period_cpa,
    attach_phone,
    drop_same_person_duplicates,
    prepare_applicants,
    reason_concentration,
    rejection_by_reason,
    safe_div,
    summarize_applicants,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
INSIGHT_SETTINGS = {
    "min_cost": MIN_COST_FOR_CPA,
    "min_sample": MIN_SAMPLE_FOR_INSIGHT,
    "cpa_worse": CPA_WORSE_RATIO,
    "cpa_better": CPA_BETTER_RATIO,
    "cost_up": COST_UP_RATIO,
    "applicant_down": APPLICANT_DOWN_RATIO,
    "reason_share": REASON_SHARE_ALERT,
    "missing_alert": MISSING_CHANNEL_ALERT,
    "in_progress_alert": IN_PROGRESS_ALERT,
}
LEVEL_ICON = {"주의": "🟠", "개선": "🟢", "정보": "🔵"}
# 기수 전체 기간을 뜻하는 넓은 범위 (실제 계산은 광고 데이터 기간으로 자동 제한됨)
ALL_TIME_START = pd.Timestamp("1900-01-01")
ALL_TIME_END = pd.Timestamp("2100-01-01")


# ---------------------------------------------------------------------------
# 데이터 로딩 (캐시)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def load_cohort_bundle(course_id: str, semester: int) -> dict:
    """과정·기수 하나의 지원자(2.2)·광고(2.1, BigQuery) 데이터를 읽어 분류까지 마친 묶음을 반환합니다.

    Args:
        course_id: 과정 ID
        semester: 기수 번호

    Returns:
        {"apps": 분류된 지원자 DataFrame, "wide": 매체·일자별 광고 DataFrame, "snapshot": 적재 시각 또는 None}
    """
    cohort = COURSES[course_id]["cohorts"][semester]
    sheet_id = cohort.get("sheet_id", "").strip()
    raw = load_applicants(sheet_id, cohort["sheet_name"], cohort.get("header_row", 4)) if sheet_id else pd.DataFrame()
    if sheet_id and raw.empty:
        # 예외를 던지면 Streamlit이 이 결과를 캐시하지 않으므로, 일시적 API 오류가 5분간 고정되지 않습니다
        raise RuntimeError(f"{COURSES[course_id]['name']} {semester}기 지원자 시트를 읽지 못했습니다")
    inflow_long = load_inflow(course_id, semester)
    snapshot = inflow_long["snapshot_at"].max() if not inflow_long.empty and "snapshot_at" in inflow_long.columns else None
    # 지원서 RAW(읽기 전용)에서 전화번호를 받아 이름+전화번호가 같은 중복 지원을 한 사람으로 묶습니다
    apps = attach_phone(prepare_applicants(raw), load_apply_raw(sheet_id))
    apps, same_person_dropped = drop_same_person_duplicates(apps)
    return {"apps": apps, "wide": to_wide(inflow_long), "snapshot": snapshot,
            "same_person_dropped": same_person_dropped}


@st.cache_data(ttl=300, show_spinner=False)
def load_actions_cached() -> pd.DataFrame:
    """마케팅 액션 로그를 읽습니다 (5분 캐시)."""
    return load_action_log()


@st.cache_data(ttl=3600, show_spinner=False)
def load_ad_sheet_range_cached(sheet_id: str):
    """2.1 시트의 첫 날짜와 마지막 날짜를 읽습니다 (1시간 캐시). 모집 기간 범위와 모집 마감일 기본값으로 씁니다."""
    return get_ad_sheet_date_range(sheet_id)


def try_bundle(course_id: str, semester: int):
    """과정·기수 묶음을 읽고, 실패하면 None을 돌려줍니다 (전체 기수 표가 한 기수 실패로 멈추지 않도록)."""
    try:
        return load_cohort_bundle(course_id, semester)
    except Exception as error:
        logger.error("기수 데이터 로드 실패 (%s %s기): %s", course_id, semester, error)
        return None


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

def cohort_setting(course_id: str, semester: int) -> dict:
    """과정·기수 설정을 기본값과 합쳐 반환합니다. 날짜 문자열은 Timestamp로 바꿉니다."""
    merged = {**DEFAULT_COHORT_SETTING, **COHORT_SETTINGS.get((course_id, semester), {})}
    for key in ("recruit_start", "recruit_end"):
        merged[key] = pd.Timestamp(merged[key]) if merged[key] else None
    return merged


def show_table(frame: pd.DataFrame, **kwargs):
    """표를 표시하면서 숫자 열에는 천 단위 구분 기호를 넣습니다."""
    config = dict(kwargs.pop("column_config", None) or {})
    for column in frame.columns:
        if column in config:
            continue
        if pd.api.types.is_integer_dtype(frame[column]) or pd.api.types.is_float_dtype(frame[column]):
            config[column] = st.column_config.NumberColumn(format="localized")
    st.dataframe(frame, column_config=config, **kwargs)


def fmt_int(value) -> str:
    """정수 표시. 값이 없으면 '-'."""
    return "-" if value is None or pd.isna(value) else f"{value:,.0f}"


def fmt_pct(value) -> str:
    """퍼센트 표시. 분모가 0이라 계산할 수 없으면 '계산 불가'."""
    return "계산 불가" if pd.isna(value) else f"{value:.1f}%"


def fmt_won(value) -> str:
    """원화 표시. 계산할 수 없으면 '계산 불가'."""
    return "계산 불가" if pd.isna(value) else f"{value:,.0f}원"


def fmt_count(value) -> str:
    """인원 표시 (소수는 반올림). 계산할 수 없으면 '계산 불가'."""
    return "계산 불가" if pd.isna(value) else f"{value:,.0f}명"


def fmt_speed(value, signed: bool = False) -> str:
    """일 평균 지원 속도 표시. 계산할 수 없으면 '계산 불가'."""
    if pd.isna(value):
        return "계산 불가"
    return f"{value:+.1f}명/일" if signed else f"{value:.1f}명/일"


def fmt_change(value) -> str:
    """전기 대비 변화 표시. 문자열(신규 발생 등)은 그대로 둡니다."""
    if isinstance(value, str):
        return value
    return "-" if pd.isna(value) else f"{value:+.1f}%"


def to_date(value) -> date:
    """Timestamp·datetime을 date로 바꿉니다."""
    return pd.Timestamp(value).date()


def clip_period(start, end, cov_start, cov_end):
    """모집 기간을 광고 데이터 기간 안으로 자릅니다. 겹치지 않으면 (None, None)."""
    if cov_start is None:
        return None, None
    start = max(pd.Timestamp(start), cov_start)
    end = min(pd.Timestamp(end), cov_end)
    return (start, end) if start <= end else (None, None)


def counted(apps: pd.DataFrame, start=None, end=None, include_pre: bool = False) -> pd.DataFrame:
    """지원 건수 기준(이관 포함) 지원자를 기간으로 자릅니다.

    Args:
        apps: prepare_applicants() 결과
        start: 기간 시작 (포함). None이면 기간 제한 없음
        end: 기간 종료 (포함)
        include_pre: True면 기간 밖이어도 사전·전기수 이관 지원자를 포함
    """
    if apps.empty:
        return apps
    part = apps[application_mask(apps)]
    if start is not None:
        in_period = (part["지원일"] >= pd.Timestamp(start)) & (part["지원일"] <= pd.Timestamp(end))
        keep = in_period | (part["사전이관"] if include_pre else False)
        part = part[keep]
    return part


def week_label(week_start: date) -> str:
    """주 시작일을 'YYYY-MM-DD ~ MM-DD' 형식으로 바꿉니다."""
    return f"{week_start:%Y-%m-%d} ~ {(week_start + timedelta(days=6)):%m-%d}"


def last_full_week_start(latest) -> date:
    """데이터 기준일 기준으로 마지막으로 끝난 주(월~일)의 시작일을 반환합니다.

    기준일이 일요일이면 그 주가 끝난 것으로 보고, 아니면 한 주 앞을 씁니다.
    """
    latest_day = to_date(latest)
    start = week_start_of(latest_day)
    return start if latest_day >= start + timedelta(days=6) else start - timedelta(days=7)


def render_wow_table(wide: pd.DataFrame, latest):
    """직전 주와 그 전주의 광고 지표를 WoW 증감률과 함께 표로 보여 줍니다."""
    last_week = last_full_week_start(latest)
    st.markdown(f"#### 📊 직전 주 vs 그 전주 (WoW): {last_week:%m.%d}~{last_week + timedelta(days=6):%m.%d}")
    table = weekly_comparison_table(wide, last_week)
    money_like = ["비용 지출", "CTA 클릭 합계", "지원서 랜딩 합계", "지원서 제출 합계"]
    display = table.copy()
    for col in money_like:
        display[col] = [
            fmt_change(v) if key == "WoW" else f"{v:,.0f}"
            for key, v in zip(table["기간"], table[col])
        ]
    show_table(display, use_container_width=True, hide_index=True)


def render_insights(insights: list):
    """인사이트 목록을 '발견 사항·근거·표본·다음 확인·한계' 순서로 표시합니다."""
    for item in insights:
        with st.container(border=True):
            st.markdown(f"{LEVEL_ICON.get(item['level'], '🔵')} **{item['level']}** · {item['finding']}")
            st.caption(f"근거: {item['evidence']} · 표본: {item['sample']:,}명")
            st.caption(f"다음에 확인할 행동: {item['next_check']} · 한계: {item['limit']}")


def render_data_status(bundle: dict, cov_start, cov_end, now_kst: datetime):
    """탭 상단에 조회 기준 시각만 표시합니다. (지원일·광고 기간·적재 시각 등 상세 상태는 숨김 처리)"""
    st.caption(f"조회 기준 시각 {now_kst:%Y-%m-%d %H:%M} (KST)")


# ---------------------------------------------------------------------------
# 페이지 설정·사이드바
# ---------------------------------------------------------------------------

st.set_page_config(page_title="모두의연구소 마케팅 대시보드", page_icon="📊", layout="wide")
st.title("📊 과정별 모집현황 대시보드")

st.sidebar.header("필터 설정")
if st.sidebar.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("---")

course_type = st.sidebar.radio("과정 유형 선택", ("실업자 과정", "재직자 과정"))
# 과정 유형별 기본(맨 앞) 과정: 실업자는 AI에이전트, 재직자는 데이터
FIRST_COURSE_BY_TYPE = {"unemployed": "ai_agent", "employed": "data_analysis"}


def courses_of_type(type_label: str) -> dict:
    """선택한 유형(실업자·재직자)의 전체 과정과 기수 목록을 반환합니다. 종료된 기수도 포함합니다."""
    type_key = "unemployed" if type_label == "실업자 과정" else "employed"
    courses = {cid: course for cid, course in COURSES.items() if course["type"] == type_key and course["cohorts"]}
    # 유형별로 먼저 보여 줄 과정을 맨 앞에 둡니다 (나머지는 설정 순서 유지)
    first = FIRST_COURSE_BY_TYPE.get(type_key)
    return dict(sorted(courses.items(), key=lambda item: item[0] != first))


def default_cohort(course_id: str) -> int:
    """과정의 기본 기수: 모집 중인 기수(config.RECRUITING_COHORTS)가 있으면 그 기수, 없으면 가장 최근 기수."""
    recruiting = [sem for cid, sem in RECRUITING_COHORTS if cid == course_id]
    return recruiting[0] if recruiting else max(COURSES[course_id]["cohorts"])


available_courses = courses_of_type(course_type)
if not available_courses:
    st.warning("이 유형에 연동된 과정이 없습니다. src/config.py를 확인해주세요.")
    st.stop()

selected_course_id = st.sidebar.selectbox(
    "과정 선택", options=list(available_courses.keys()),
    format_func=lambda x: available_courses[x]["name"],
)
selected_course = available_courses[selected_course_id]
cohort_options = sorted(selected_course["cohorts"])
# 과정을 바꾸면 그 과정의 기본 기수(모집 중인 기수)가 선택되도록 과정별 키를 씁니다
selected_cohort = st.sidebar.selectbox(
    "기수 선택", options=cohort_options, index=cohort_options.index(default_cohort(selected_course_id)),
    format_func=lambda x: f"{x}기", key=f"cohort_{selected_course_id}",
)
setting = cohort_setting(selected_course_id, selected_cohort)
# 2.1 시트의 첫 날짜·마지막 날짜: 모집 기간 범위이자 모집 마감일 기본값
sheet_first, sheet_last = load_ad_sheet_range_cached(selected_course["cohorts"][selected_cohort]["sheet_id"].strip())
if setting["recruit_end"] is None and sheet_last:
    setting["recruit_end"] = pd.Timestamp(sheet_last)
    setting["recruit_end_source"] = "2.1 시트 최하단 일자"
# 모집 시작일: 설정값이 없으면 2.1 시트의 첫 날짜를 씁니다 (주차별 현황의 1주차 기준)
if setting["recruit_start"] is None and sheet_first:
    setting["recruit_start"] = pd.Timestamp(sheet_first)
    setting["recruit_start_source"] = "2.1 시트 첫 날짜"

with st.spinner("데이터를 불러오는 중입니다..."):
    bundle = try_bundle(selected_course_id, selected_cohort)
if bundle is None:
    st.error("선택한 기수의 데이터를 불러오지 못했습니다. 시트 공유 권한과 네트워크 상태를 확인한 뒤 "
             "사이드바의 '데이터 새로고침'을 눌러주세요. 실패한 결과는 캐시되지 않습니다.")
    st.stop()
apps, wide = bundle["apps"], bundle["wide"]
cov_start, cov_end = ad_coverage(wide)
now_kst = datetime.now(KST)
today_kst = now_kst.date()
yesterday = today_kst - timedelta(days=1)
data_latest = cov_end if cov_end is not None else pd.Timestamp(yesterday)

# 모집 기간: 2.1 시트의 첫 날짜~마지막 날짜로만 제한 (시트 날짜가 없으면 광고 데이터 범위)
if sheet_first and sheet_last:
    range_min, range_max = pd.Timestamp(sheet_first), pd.Timestamp(sheet_last)
else:
    range_min = cov_start if cov_start is not None else pd.Timestamp(yesterday - timedelta(days=13))
    range_max = cov_end if cov_end is not None else pd.Timestamp(yesterday)
period_value = st.sidebar.date_input(
    "모집 기간", value=(to_date(range_min), to_date(range_max)),
    min_value=to_date(range_min), max_value=to_date(range_max),
)
if isinstance(period_value, tuple) and len(period_value) == 2:
    period_start, period_end = pd.Timestamp(period_value[0]), pd.Timestamp(period_value[1])
else:
    period_start, period_end = range_min, range_max

media_options = sorted(apps["매체그룹"].unique()) if not apps.empty else []
selected_media = st.sidebar.multiselect("매체 (표 필터)", options=media_options, default=media_options)
st.sidebar.markdown("---")
st.sidebar.caption(f"기준 시각 {now_kst:%Y-%m-%d %H:%M}")
if apps.empty:
    st.sidebar.warning("지원자 데이터를 불러오지 못했습니다.")
else:
    st.sidebar.success(f"✅ {selected_course['name']} {selected_cohort}기 데이터 로드 완료")

# '설정·지표 정의' 탭은 숨김 처리했습니다 (render_settings 함수는 필요 시 다시 연결할 수 있도록 남겨 둠)
tab_overview, tab_media, tab_weekly, tab_daily = st.tabs(
    ["📈 종합 현황", "🧩 매체별 현황", "📅 주차별 현황", "📆 일자별 현황"]
)


# ---------------------------------------------------------------------------
# 📈 종합 현황
# ---------------------------------------------------------------------------

def render_overview():
    """과정·기수 누적 현황, 목표, 예산·CPA, 매체·사유 표를 그립니다."""
    st.subheader(f"{selected_course['name']} {selected_cohort}기 종합 현황")
    render_data_status(bundle, cov_start, cov_end, now_kst)
    if apps.empty:
        st.error("지원자 데이터를 불러올 수 없습니다. 시트 공유 권한과 시트 이름을 확인해주세요.")
        return

    if bundle.get("same_person_dropped"):
        st.caption(f"ℹ️ 이름·전화번호가 같은 중복 지원 {bundle['same_person_dropped']:,}건은 한 명으로 묶어 집계했습니다. "
                   "(이름만 같은 동명이인은 별도 사람으로 집계합니다)")
    counted_all = counted(apps)
    summary = summarize_applicants(apps)  # 이관 입과자도 지원·통과·합격 집계에 포함
    transferred = int((apps["매체그룹"] == "이관").sum())
    cost_total = float(wide["비용"].sum()) if not wide.empty else 0.0

    kind = setting["target_kind"]
    current_by_kind = {"지원": summary["지원"], "최종합격": summary["최종합격_누적"], "등록": summary["등록"]}
    current_value = current_by_kind.get(kind, summary["지원"])
    # 목표가 설정된 모집 중 기수만 목표 블록을 보여 줍니다 (종료된 기수는 목표가 없어 생략)
    if setting["target_count"] is not None:
        st.markdown("#### 🎯 모집 목표")
        if setting["recruit_end"] is not None:
            st.caption(f"모집 마감일: {setting['recruit_end']:%Y-%m-%d}")
        target = int(setting["target_count"])
        remaining = max(target - current_value, 0)
        cols = st.columns(4)
        cols[0].metric(f"목표 {kind}", f"{target:,}명")
        cols[1].metric(f"현재 {kind}", f"{current_value:,}명")
        cols[2].metric("달성률", fmt_pct(safe_div(current_value, target) * 100))
        cols[3].metric("남은 인원", f"{remaining:,}명")

    st.markdown("#### 📊 지원·전형 현황")
    cols = st.columns(5)
    cols[0].metric("지원", f"{summary['지원']:,}명")
    cols[1].metric("서류 통과", f"{summary['서류통과_누적']:,}명",
                   f"판정 {summary['서류결과확정']:,}명 중 {fmt_pct(summary['서류통과율(%)'])}", delta_color="off")
    cols[2].metric("인터뷰 통과", f"{summary['인터뷰통과_누적']:,}명",
                   f"판정 {summary['인터뷰결과확정']:,}명 중 {fmt_pct(summary['인터뷰통과율(%)'])}", delta_color="off")
    cols[3].metric("최종 합격", f"{summary['최종합격_누적']:,}명")
    cols[4].metric("등록", f"{summary['등록']:,}명")
    if summary["등록"] == 0 and summary["최종합격_누적"] > 0:
        st.caption("🟠 등록 인원이 0명입니다. 수강료 열이 없는 과정이거나 값이 기록되지 않았을 수 있으니 시트를 확인하세요.")

    # 위 '지원·전형 현황'과 같은 집계(전체 지원자, 매체 필터 없음)로 지원자 퍼널을 그립니다
    st.markdown("#### 🔻 지원자 퍼널")
    funnel_stages = [("지원", summary["지원"]), ("서류 통과", summary["서류통과_누적"]),
                     ("인터뷰 통과", summary["인터뷰통과_누적"]), ("최종 합격", summary["최종합격_누적"]),
                     ("등록", summary["등록"])]
    st.plotly_chart(create_applicant_funnel_chart(funnel_stages), use_container_width=True)
    funnel_rows = []
    previous = None
    for label, value in funnel_stages:
        funnel_rows.append({"단계": label, "인원": value,
                            "직전 단계 대비(%)": safe_div(value, previous) * 100 if previous is not None else float("nan")})
        previous = value
    show_table(pd.DataFrame(funnel_rows).round(1), use_container_width=True, hide_index=True)

    if setting["target_count"] is not None and setting["recruit_end"] is not None:
        target = int(setting["target_count"])
        days_left = (setting["recruit_end"] - pd.Timestamp(today_kst)).days + 1
        recent_start = pd.Timestamp(today_kst - timedelta(days=7))
        recent_apps = len(counted_all[(counted_all["지원일"] >= recent_start) & (counted_all["지원일"] < pd.Timestamp(today_kst))])
        recent_speed = recent_apps / 7
        pipeline = summary["진행중"]
        if kind == "지원":
            conv, expected_pipeline = 1.0, 0.0
        else:
            # 현재까지의 지원→목표 단계 전환율을 진행 중 인원에 적용해 기대 달성 수를 빼고, 나머지를 새로 지원받아야 할 인원으로 환산
            conv = safe_div(current_value, summary["지원"])
            expected_pipeline = pipeline * conv if not pd.isna(conv) else float("nan")
        needed_new = max(target - current_value - expected_pipeline, 0) / conv if conv and not pd.isna(conv) else float("nan")
        st.markdown("**앞으로 필요한 모집 인원**")
        if days_left <= 0:
            st.warning("모집 마감일이 지났습니다. 마감 기간 설정을 확인해주세요.")
        else:
            required = needed_new / days_left
            cols = st.columns(4)
            cols[0].metric("추가 필요 지원", fmt_count(needed_new))
            cols[1].metric("남은 기간", f"{days_left:,}일")
            cols[2].metric("필요 지원 속도", fmt_speed(required))
            cols[3].metric("최근 7일 지원 속도", fmt_speed(recent_speed))
            if kind != "지원":
                cols = st.columns(3)
                cols[0].metric("전형 진행 중", f"{pipeline:,}명")
                cols[1].metric(f"지원→{kind} 전환율", fmt_pct(conv * 100))
                cols[2].metric("진행 중 기대 달성", fmt_count(expected_pipeline))
                if pd.isna(conv) or conv == 0:
                    st.info(f"{kind} 인원이 0명이라 전환율을 계산할 수 없어 추가 필요 지원 수를 산출하지 않습니다.")
                else:
                    st.caption(f"가정: 현재 전환율이 남은 기간에도 유지되고, 진행 중 인원이 같은 비율로 {kind}에 도달한다고 봅니다.")
            if not pd.isna(required) and recent_speed < required:
                st.warning("최근 지원 속도가 필요 속도보다 낮습니다. 매체 집행·랜딩 전환을 우선 점검하세요.")

    st.markdown("#### 💰 예산·비용")
    cov_range_text = (f"{to_date(cov_start)} ~ {to_date(cov_end)}" if cov_start is not None else "광고 데이터 없음")
    total_cpa = period_cpa(apps, wide, ALL_TIME_START, ALL_TIME_END)  # 광고 데이터 기간으로 자동 제한됨
    budget = setting["budget"]
    cols = st.columns(4)
    cols[0].metric("누적 광고비", fmt_won(cost_total), f"광고 기간 {cov_range_text}", delta_color="off")
    if budget:
        spent_rate = cost_total / budget * 100
        cols[1].metric("예산 소진율", fmt_pct(spent_rate), f"예산 {budget:,.0f}원", delta_color="off")
    else:
        cols[1].metric("예산 소진율", "미설정")
    cols[2].metric("지원 CPA (전체 모집)", fmt_won(total_cpa["지원 CPA(전체 모집 비용)"]),
                   f"전체 지원 {total_cpa['지원(전체)']:,}명", delta_color="off")
    cols[3].metric("최종 합격 CPA (전체 모집, 잠정)", fmt_won(total_cpa["최종합격 CPA(전체 모집 비용)"]),
                   f"최종 합격 {total_cpa['최종합격(전체)']:,}명", delta_color="off")
    if budget and setting["recruit_start"] is not None and setting["recruit_end"] is not None:
        span = (setting["recruit_end"] - setting["recruit_start"]).days or 1
        elapsed = min(max((pd.Timestamp(today_kst) - setting["recruit_start"]).days, 0), span) / span * 100
        pace_gap = spent_rate - elapsed
        if pace_gap >= BUDGET_PACE_GAP_PT:
            st.warning(f"🟠 예산 소진율 {spent_rate:.0f}%가 모집 기간 경과율 {elapsed:.0f}%보다 {pace_gap:.0f}%p 높습니다. "
                       "집행 속도와 지원 전환을 함께 점검하세요.")
        else:
            st.caption(f"예산 소진율 {spent_rate:.0f}% · 모집 기간 경과율 {elapsed:.0f}%")

    scope_apps = counted(apps)  # 모집 기간 밖 지원자 포함 (이관 건 제외)
    scope_apps = scope_apps[scope_apps["매체그룹"].isin(selected_media)] if selected_media else scope_apps.iloc[0:0]
    st.markdown("#### 🚫 탈락·포기 사유 (매체 필터 적용)")
    reasons = rejection_by_reason(scope_apps)
    if reasons.empty:
        st.info("탈락·포기 기록이 없습니다.")
    else:
        show_table(reasons.round(1), use_container_width=True, hide_index=True)

def render_media():
    """매체별 전형 현황, 매체별 서류 불합격 사유, 메타 소재별 현황을 그립니다.

    전형 현황과 소재별 현황, 광고비·CPA는 모집 기간 밖 지원자를 포함합니다.
    """
    st.subheader(f"{selected_course['name']} {selected_cohort}기 매체별 현황")
    render_data_status(bundle, cov_start, cov_end, now_kst)
    if apps.empty:
        st.error("지원자 데이터를 불러올 수 없습니다. 시트 공유 권한과 시트 이름을 확인해주세요.")
        return

    st.markdown("#### 🧭 매체별 전형 현황")
    scope_apps = counted(apps)  # 모집 기간 밖 지원자 포함 (이관 건 제외)
    scope_apps = scope_apps[scope_apps["매체그룹"].isin(selected_media)] if selected_media else scope_apps.iloc[0:0]
    quality = channel_quality_table(scope_apps)
    if quality.empty:
        st.info("지원자가 없습니다.")
    else:
        cost_table = group_period_table(apps, wide, ALL_TIME_START, ALL_TIME_END)  # 광고비·CPA도 전체 기간 기준
        cost_map = cost_table.set_index("매체")["광고비"].to_dict() if not cost_table.empty else {}
        cpa_map = cost_table.set_index("매체")["지원 CPA"].to_dict() if not cost_table.empty else {}
        quality["광고비"] = quality["매체그룹"].map(cost_map)
        quality["지원 CPA(유료 매체)"] = quality["매체그룹"].map(cpa_map)
        view = quality[["매체그룹", "지원", "서류결과확정", "서류통과율(%)", "인터뷰결과확정", "인터뷰통과율(%)",
                        "최종합격_누적", "진행중", "확정", "광고비", "지원 CPA(유료 매체)"]].rename(columns={
            "서류결과확정": "서류 판정 분모", "인터뷰결과확정": "인터뷰 판정 분모",
            "최종합격_누적": "최종 합격(누적)", "진행중": "진행 중", "확정": "결과 확정",
        })
        show_table(view.round(1), use_container_width=True, hide_index=True)

    st.markdown("#### 🧾 매체별 서류 불합격 사유")
    doc_reasons = rejection_by_reason(scope_apps, by="매체그룹")
    if not doc_reasons.empty:
        doc_reasons = doc_reasons[doc_reasons["탈락구분"] == REJECTION_KIND_DOC]
    if doc_reasons.empty:
        st.info("서류 불합격 기록이 없습니다.")
    else:
        # 행은 매체, 열은 사유로 피벗합니다. 사유 열은 전체 인원이 많은 순, 서류 불합격 합계 열을 맨 앞에 둡니다
        pivot = doc_reasons.pivot_table(index="매체그룹", columns="사유", values="인원", aggfunc="sum", fill_value=0)
        reason_order = doc_reasons.groupby("사유")["인원"].sum().sort_values(ascending=False).index.tolist()
        pivot = pivot[reason_order]
        pivot.insert(0, "서류 불합격", pivot.sum(axis=1))
        pivot = pivot.sort_values("서류 불합격", ascending=False).reset_index()
        pivot.columns.name = None
        show_table(pivot, use_container_width=True, hide_index=True)

    st.markdown("#### 🎨 메타 소재별 현황 (2.2 시트 기준, 광고비 연결 없음)")
    meta = scope_apps[scope_apps["매체그룹"] == "메타"]
    if meta.empty or "유입 소재 및 키워드" not in meta.columns:
        st.info("메타 유입 지원자가 없습니다.")
    else:
        rows = []
        for material, part in meta.groupby(meta["유입 소재 및 키워드"].astype(str).str.strip()):
            if not material:
                continue
            s = summarize_applicants(part)
            rows.append({"소재": material, "지원": s["지원"], "서류 판정 분모": s["서류결과확정"],
                         "서류통과율(%)": s["서류통과율(%)"], "진행 중": s["진행중"], "최종 합격(누적)": s["최종합격_누적"]})
        show_table(pd.DataFrame(rows).sort_values("지원", ascending=False).round(1), use_container_width=True, hide_index=True)



with tab_overview:
    render_overview()


with tab_media:
    render_media()


# ---------------------------------------------------------------------------
# 📅 주차별 현황
# ---------------------------------------------------------------------------

def recruit_week_table(apps: pd.DataFrame, wide: pd.DataFrame, recruit_start, last_date, n_weeks: int = 8) -> pd.DataFrame:
    """모집 시작일을 1주차 첫날로 삼아 최근 n주의 광고비·지원·전형 결과 표를 만듭니다.

    Args:
        apps: prepare_applicants() 결과
        wide: 광고 일별 데이터 (date, 비용 열)
        recruit_start: 모집 시작일 (1주차 첫날)
        last_date: 데이터 기준 마지막 날짜. 이 날짜가 속한 주까지 표시합니다.
        n_weeks: 표시할 최근 주 수

    Returns:
        주차, 광고비, 지원, 진행 중, 결과 확정, 서류 통과, 최종 합격, 등록, 탈락·포기 열 DataFrame.
        모집 시작 전 지원은 '모집 시작 전' 행으로 먼저 보여 줍니다.
    """
    start = pd.Timestamp(recruit_start)
    last = pd.Timestamp(last_date)
    total_weeks = max((last - start).days // 7 + 1, 1)
    has_ad = not wide.empty

    def build_row(label: str, begin, end, part: pd.DataFrame, cost: float) -> dict:
        """한 주(또는 시작 전 구간)의 전형 결과 한 행을 만듭니다."""
        s = summarize_applicants(part)
        return {
            "주차": label, "광고비(원)": cost if has_ad else float("nan"), "지원": s["지원"],
            "진행 중": s["진행중"], "결과 확정": s["확정"], "서류 통과(누적)": s["서류통과_누적"],
            "최종 합격(누적)": s["최종합격_누적"], "등록": s["등록"], "탈락·포기(확정)": s["확정"] - s["등록"],
        }

    rows = []
    pre_apps = apps[apps["지원일"] < start]
    if not pre_apps.empty:
        pre_cost = float(wide.loc[wide["date"] < start, "비용"].sum()) if has_ad else float("nan")
        rows.append(build_row("모집 시작 전", None, start - pd.Timedelta(days=1), pre_apps, pre_cost))
    for k in range(max(1, total_weeks - n_weeks + 1), total_weeks + 1):
        w_start = start + pd.Timedelta(days=7 * (k - 1))
        w_end = w_start + pd.Timedelta(days=6)
        part = apps[(apps["지원일"] >= w_start) & (apps["지원일"] <= w_end)]
        cost = float(wide.loc[(wide["date"] >= w_start) & (wide["date"] <= w_end), "비용"].sum()) if has_ad else float("nan")
        suffix = " (진행 중)" if w_end > last else ""
        label = f"{k}주차 ({w_start:%m-%d} ~ {w_end:%m-%d}){suffix}"
        rows.append(build_row(label, w_start, w_end, part, cost))
    return pd.DataFrame(rows)


def render_weekly():
    """주차별 추이를 맨 위에 두고, 주 단위 매체 효율·전주 대비·해당 주 지원자 전형 결과·인사이트를 그립니다."""
    st.subheader("주차별 현황 (월~일 기준)")
    render_data_status(bundle, cov_start, cov_end, now_kst)
    if apps.empty or wide.empty:
        st.info("주차별 현황을 표시할 데이터가 없습니다. 지원자 시트와 광고 데이터(2.1, BigQuery) 연결을 확인해주세요.")
        return

    render_wow_table(wide, data_latest)

    week_starts = sorted({week_start_of(to_date(d)) for d in apps["지원일"].dropna()} |
                         {week_start_of(to_date(d)) for d in wide["date"].dropna()})

    st.markdown("#### 📈 주차별 추이")
    trend_weeks = week_starts[-8:]
    trend = pd.DataFrame({"week_start": trend_weeks})
    trend["week_start"] = pd.to_datetime(trend["week_start"])
    trend["비용"] = [float(wide.loc[(wide["date"] >= w) & (wide["date"] <= w + pd.Timedelta(days=6)), "비용"].sum()) for w in trend["week_start"]]
    trend["지원"] = [len(counted(apps, w, w + pd.Timedelta(days=6))) for w in trend["week_start"]]
    st.plotly_chart(create_weekly_cost_applicant_chart(trend), use_container_width=True)

    latest_ad_week = week_start_of(to_date(data_latest))
    default_index = week_starts.index(latest_ad_week) if latest_ad_week in week_starts else len(week_starts) - 1
    selected_week = st.selectbox(
        "주차 선택", options=week_starts, index=default_index,
        format_func=week_label,
    )
    periods = comparison_periods(selected_week, to_date(data_latest))
    cur_start, cur_end = periods["current"]
    prev_start, prev_end = periods["previous"]
    if selected_week > to_date(data_latest):
        st.info(f"{week_label(selected_week)} 주는 광고 데이터({to_date(data_latest)})가 아직 없습니다.")
    elif not periods["complete"]:
        st.warning(f"🟠 {week_label(selected_week)} 주는 아직 끝나지 않았습니다. 광고 데이터는 {to_date(data_latest)}까지이며, "
                   f"직전 주도 같은 요일({(cur_end - cur_start).days + 1:,}일)까지만 비교합니다.")

    cov_s, cov_e = ad_coverage(wide)
    cur_clip = clip_period(cur_start, cur_end, cov_s, cov_e)
    prev_clip = clip_period(prev_start, prev_end, cov_s, cov_e)
    cur_tbl = group_period_table(apps, wide, *cur_clip) if cur_clip[0] is not None else pd.DataFrame()
    prev_tbl = group_period_table(apps, wide, *prev_clip) if prev_clip[0] is not None else pd.DataFrame()
    comp = compare_group_tables(cur_tbl, prev_tbl) if not cur_tbl.empty or not prev_tbl.empty else pd.DataFrame()

    st.markdown(f"#### 💰 매체별 효율: {week_label(cur_start)} vs 직전 {'주' if periods['complete'] else '같은 기간'}")
    if comp.empty:
        st.info("선택한 주에 광고비나 지원 데이터가 없습니다.")
    else:
        # 광고비는 매체 필터와 무관하게 모두 집계합니다 (필터를 걸면 광고비 합계가 빠지는 문제 방지).
        # 매체 필터는 지원자 표(아래 '선택 주차에 지원한 사람들')에만 적용합니다.
        total_row = {
            "매체": "전체", "광고비": comp["광고비"].sum(), "광고비 직전": comp["광고비 직전"].sum(),
            "지원": comp["지원"].sum(), "지원 직전": comp["지원 직전"].sum(),
        }
        total_row["광고비 변화(%)"] = pct_change(total_row["광고비"], total_row["광고비 직전"])
        total_row["지원 변화(%)"] = pct_change(total_row["지원"], total_row["지원 직전"])
        total_row["지원 CPA"] = safe_div(total_row["광고비"], total_row["지원"])
        total_row["지원 CPA 직전"] = safe_div(total_row["광고비 직전"], total_row["지원 직전"])
        total_row["CPA 변화(%)"] = pct_change(total_row["지원 CPA"], total_row["지원 CPA 직전"])
        view = pd.concat([comp, pd.DataFrame([total_row])], ignore_index=True)
        view["지원 비중(%)"] = [safe_div(v, total_row["지원"]) * 100 for v in view["지원"]]
        view["광고비 비중(%)"] = [safe_div(v, total_row["광고비"]) * 100 for v in view["광고비"]]
        view = view[["매체", "광고비", "광고비 변화(%)", "광고비 비중(%)", "지원", "지원 변화(%)", "지원 비중(%)",
                     "지원 CPA", "CPA 변화(%)"]]
        for column in ["광고비 변화(%)", "지원 변화(%)", "CPA 변화(%)"]:
            view[column] = view[column].map(fmt_change)
        show_table(view.round(1), use_container_width=True, hide_index=True)

    st.markdown("#### 🧭 이번 주 요약과 제안 액션 (지출 대비 전환 효율)")
    narrative = weekly_narrative(wide, cur_start, cur_end, prev_start, prev_end)
    with st.container(border=True):
        st.markdown(f"**총평** {narrative['headline']}")
        if narrative["spend_lines"]:
            st.markdown("**매체별 광고비·유입·전환**")
            for line in narrative["spend_lines"]:
                st.markdown(f"- {line}")
        for line in narrative["difference_lines"]:
            st.markdown(f"- {line}")
        st.markdown("**이번 주 제안 액션**")
        for action in narrative["actions"]:
            st.markdown(f"- {action}")

    week_apps = counted(apps, cur_start, cur_end)
    week_apps = week_apps[week_apps["매체그룹"].isin(selected_media)] if selected_media else week_apps.iloc[0:0]
    st.markdown("#### 🧑‍💼 선택 주에 지원한 사람들의 현재 전형 결과 (지원일 기준)")
    if week_apps.empty:
        st.info("선택한 주에 지원자가 없습니다.")
    else:
        s = summarize_applicants(week_apps)
        cols = st.columns(5)
        cols[0].metric("지원", f"{s['지원']:,}명")
        cols[1].metric("전형 진행 중", f"{s['진행중']:,}명")
        cols[2].metric("결과 확정", f"{s['확정']:,}명")
        cols[3].metric("서류 통과율", fmt_pct(s["서류통과율(%)"]), f"판정 {s['서류결과확정']:,}명", delta_color="off")
        cols[4].metric("최종 합격(누적)", f"{s['최종합격_누적']:,}명")
        quality = channel_quality_table(week_apps)
        view = quality[["매체그룹", "지원", "서류결과확정", "서류통과율(%)", "인터뷰결과확정", "인터뷰통과율(%)",
                        "최종합격_누적", "진행중", "확정", "서류불합격", "포기"]].rename(columns={
            "서류결과확정": "서류 판정 분모", "인터뷰결과확정": "인터뷰 판정 분모", "최종합격_누적": "최종 합격(누적)",
            "진행중": "진행 중", "확정": "결과 확정", "서류불합격": "서류 불합격", "포기": "수강 포기"})
        show_table(view.round(1), use_container_width=True, hide_index=True)

        st.markdown("**탈락·포기 사유 (선택 주 지원자, 구분별 분모 표시)**")
        reasons = rejection_by_reason(week_apps)
        if reasons.empty:
            st.info("선택한 주의 탈락·포기 기록이 없습니다.")
        else:
            show_table(reasons.round(1), use_container_width=True, hide_index=True)

    checklist = small_sample_checklist(len(week_apps), MIN_SAMPLE_FOR_INSIGHT)
    if checklist:
        with st.container(border=True):
            st.markdown("**🧭 표본이 적은 주에 마케터가 챙길 일** (판단 확정 대신 점검 순서)")
            for item in checklist:
                st.markdown(f"- {item}")

    st.markdown("#### 🗂️ 최근 8주 전형 결과 (모집 시작일 기준 주차, 지원일 기준 현재 상태)")
    if setting["recruit_start"] is None:
        st.info("모집 시작일을 알 수 없어 주차를 구분하지 못했습니다. 2.1 시트 또는 설정에 모집 시작일을 확인해주세요.")
    else:
        last_date = max([pd.Timestamp(data_latest)] + apps["지원일"].dropna().tolist())
        show_table(recruit_week_table(apps, wide, setting["recruit_start"], last_date).round(1),
                   use_container_width=True, hide_index=True)


with tab_weekly:
    render_weekly()


# ---------------------------------------------------------------------------
# 📆 일자별 현황
# ---------------------------------------------------------------------------

def build_daily_frame() -> pd.DataFrame:
    """광고 데이터가 있는 전 기간의 일별 표(광고비·지원·CPA·7일 지표·누락)를 만듭니다."""
    cov_s, cov_e = ad_coverage(wide)
    if cov_s is None:
        return pd.DataFrame()
    days = pd.date_range(cov_s, cov_e, freq="D")
    base = pd.DataFrame({"date": days})
    ad_daily = daily_totals(wide)[["date", "비용", "지원서 제출"]].rename(columns={"지원서 제출": "GA 지원서 제출"})
    apps_daily = counted(apps).groupby("지원일").size().rename("지원").reset_index().rename(columns={"지원일": "date"})
    missing_daily = (apps[(apps["매체그룹"] == UNCLASSIFIED) & application_mask(apps)]
                     .groupby("지원일").size().rename("누락").reset_index().rename(columns={"지원일": "date"}))
    frame = base.merge(ad_daily, on="date", how="left").merge(apps_daily, on="date", how="left").merge(missing_daily, on="date", how="left")
    frame[["지원", "누락"]] = frame[["지원", "누락"]].fillna(0).astype(int)
    frame["GA 지원서 제출"] = frame["GA 지원서 제출"].fillna(0)
    frame["비용"] = frame["비용"].fillna(0.0)
    frame["지원 CPA"] = [safe_div(c, a) for c, a in zip(frame["비용"], frame["지원"])]
    frame["7일 CPA"] = (frame["비용"].rolling(7, min_periods=7).sum() / frame["지원"].rolling(7, min_periods=7).sum()).where(
        frame["지원"].rolling(7, min_periods=7).sum() > 0)
    frame["누락 비율(%)"] = [safe_div(m, a) * 100 for m, a in zip(frame["누락"], frame["지원"])]
    frame["전일 대비 비용(%)"] = [pct_change(c, p) for c, p in zip(frame["비용"], frame["비용"].shift(1))]
    frame["전일 대비 지원(%)"] = [pct_change(c, p) for c, p in zip(frame["지원"], frame["지원"].shift(1))]
    return frame


def render_daily():
    """일별 추이, 7일 지표, 전일 대비 참고 사항(권장 액션 포함)을 그립니다."""
    st.subheader("일자별 현황")
    render_data_status(bundle, cov_start, cov_end, now_kst)
    frame = build_daily_frame()
    if frame.empty:
        st.info("광고 데이터가 없습니다. 2.1 시트 갱신(BigQuery 적재)을 확인해주세요.")
        return

    display = frame[(frame["date"] >= period_start) & (frame["date"] <= period_end)].copy()
    if display.empty:
        st.info("선택한 모집 기간에 광고 데이터가 없습니다.")
        return
    latest = frame.iloc[-1]
    cols = st.columns(4)
    cols[0].metric(f"광고비 ({to_date(latest['date'])})", fmt_won(latest["비용"]),
                   fmt_change(latest["전일 대비 비용(%)"]), delta_color="off")
    cols[1].metric("지원 (2.2 시트)", f"{int(latest['지원']):,}명", fmt_change(latest["전일 대비 지원(%)"]), delta_color="off")
    cols[2].metric("지원 CPA (전체 모집 비용)", fmt_won(latest["지원 CPA"]))
    cols[3].metric("7일 CPA (광고비 합 ÷ 지원 합)", fmt_won(latest["7일 CPA"]))
    if latest["지원"] < MIN_DAILY_APPLICANTS_STABLE:
        st.caption(f"⚠️ 최근 일 지원 {int(latest['지원']):,}명으로 일별 CPA 변동이 큽니다.")
    unclassified_latest = int(latest["누락"])
    if unclassified_latest:
        st.caption(f"🟠 유입 경로 누락·미분류 {unclassified_latest:,}명 ({fmt_pct(latest['누락 비율(%)'])})")

    actions_all = load_actions_cached() if ACTION_LOG_SHEET_ID.strip() else pd.DataFrame()
    actions = filter_actions(actions_all, selected_course_id, selected_cohort) if not actions_all.empty else actions_all
    if not actions.empty:
        actions = actions[(actions["변경일"] >= period_start) & (actions["변경일"] <= period_end)]

    st.plotly_chart(create_daily_timeline_chart(display[["date", "비용", "지원"]], actions if not actions.empty else None),
                    use_container_width=True)

    st.markdown("#### 📋 일자별 표")
    table = display[["date", "비용", "전일 대비 비용(%)", "지원", "전일 대비 지원(%)", "지원 CPA", "7일 CPA",
                     "누락", "누락 비율(%)", "GA 지원서 제출"]].copy()
    table["변동 주의"] = table["지원"].map(lambda v: "지원 적음(변동 큼)" if v < MIN_DAILY_APPLICANTS_STABLE else "")
    table["date"] = table["date"].dt.strftime("%Y-%m-%d")
    for column in ["전일 대비 비용(%)", "전일 대비 지원(%)"]:
        table[column] = table[column].map(fmt_change)
    # 과거 날짜부터 오름차순으로 표시합니다 (YYYY-MM-DD 문자열이라 사전순 = 날짜순)
    show_table(table.sort_values("date", ascending=True).round(1), use_container_width=True, hide_index=True)

    cov_s, cov_e = ad_coverage(wide)

    def change_view(cur_start, cur_end, prev_start, prev_end):
        """두 기간의 매체별 광고비·지원·CPA 변화와 참고 문구·권장 액션 표를 만듭니다. 비교할 데이터가 없으면 None."""
        cur_clip = clip_period(cur_start, cur_end, cov_s, cov_e)
        prev_clip = clip_period(prev_start, prev_end, cov_s, cov_e)
        cur_tbl = group_period_table(apps, wide, *cur_clip) if cur_clip[0] is not None else pd.DataFrame()
        prev_tbl = group_period_table(apps, wide, *prev_clip) if prev_clip[0] is not None else pd.DataFrame()
        comp = compare_group_tables(cur_tbl, prev_tbl) if not cur_tbl.empty or not prev_tbl.empty else pd.DataFrame()
        if comp.empty:
            return None
        comp = comp.assign(참고=comp.apply(change_notes, axis=1)).sort_values("광고비", ascending=False)
        comp["권장 액션"] = [recommended_actions(note) for note in comp["참고"]]
        view = comp[["매체", "광고비", "광고비 직전", "광고비 변화(%)", "지원", "지원 직전", "지원 변화(%)",
                     "지원 CPA", "CPA 변화(%)", "참고", "권장 액션"]].copy()
        for column in ["광고비 변화(%)", "지원 변화(%)", "CPA 변화(%)"]:
            view[column] = view[column].map(fmt_change)
        return view

    st.markdown("#### 🔎 전일 대비 참고 사항 (어제 vs 그제)")
    if cov_e is None:
        st.info("광고 데이터가 없어 전일 대비를 계산할 수 없습니다.")
    else:
        day_view = change_view(cov_e, cov_e, cov_e - pd.Timedelta(days=1), cov_e - pd.Timedelta(days=1))
        if day_view is None:
            st.caption("비교할 광고비·지원 데이터가 없습니다.")
        else:
            show_table(day_view.drop(columns=["참고", "권장 액션"]).round(1), use_container_width=True, hide_index=True)

    # 제안 액션은 하루 표본이 적어 최근 3일 vs 직전 3일 기준으로 만듭니다
    st.markdown("#### 🧭 제안 액션 (최근 3일 기준, 지출 대비 전환 효율)")
    if cov_e is None:
        st.info("광고 데이터가 없어 제안 액션을 만들 수 없습니다.")
    else:
        actions = efficiency_actions(wide, cov_e - pd.Timedelta(days=2), cov_e)
        if actions:
            for action in actions:
                st.markdown(f"- {action}")
        else:
            st.caption("특이 변화가 없어 현재 집행을 유지하며 다음 추이를 확인하세요.")

    st.caption("제안 기준: 매체별 제출당 비용을 타 매체 평균과 비교합니다. 평균의 1.5배 이상이면 저조, 0.67배 이하면 우수로 봅니다.")

    # '데이터 업데이트 상태'와 '마케팅 액션 로그와 전후 비교' 섹션은 숨김 처리했습니다.


with tab_daily:
    render_daily()


# ---------------------------------------------------------------------------
# ⚙️ 설정·지표 정의
# ---------------------------------------------------------------------------

def render_settings():
    """지표 정의, 현재 설정값, 분류 규칙, 데이터 연결 상태를 보여줍니다."""
    st.subheader("지표 정의")
    definitions = pd.DataFrame([
        ("지원", "2.2 시트 신청자 행 수 (지원서 1건 = 1행)", "중복 제거 안 함 (동일인 식별 키 없음), 유입 채널이 이관인 건(타 과정·전기수 이관 등)도 포함", "2.2 시트"),
        ("서류 통과(누적)", "서류 합격 O, 또는 인터뷰·최종·등록 기록이 있는 인원", "서류 통과율 분모 = 서류 판정 인원(통과 또는 불합격)", "2.2 시트"),
        ("인터뷰 통과(누적)", "인터뷰 합격 O, 또는 최종·등록 기록이 있는 인원", "인터뷰 판정 분모 = 인터뷰 O/X 또는 최종 이상", "2.2 시트"),
        ("현재 단계", "지금 머물러 있는 단계 (우선순위: 이관>서류 탈락>인터뷰 탈락·불참>수강포기(인터뷰 합격 이후만)>등록>최종>인터뷰>서류)",
         "확정 단계: 등록·탈락·불참·포기·이관. 탈락 기록이 있으면 수강포기 표기보다 탈락을 우선", "2.2 시트"),
        ("지원 CPA (유료 매체)", "메타·구글 DA·구글 SA·네이버 SA·카카오 DA·ChatGPT DA 광고비 ÷ 해당 매체 지원 수", "지원은 모집 기간 밖 포함, 광고비는 광고 데이터 기간 안", "2.1 (BigQuery) + 2.2"),
        ("지원 CPA (전체 모집 비용)", "전체 광고비 ÷ 전체 지원 수 (자연 유입 포함)", "유료 매체 CPA와 다른 지표", "2.1 + 2.2"),
        ("최종 합격 CPA", "광고비 ÷ 최종 합격(누적). 전형 진행 중이면 잠정값", "분모 0이면 '계산 불가'", "2.1 + 2.2"),
        ("7일 CPA", "최근 7일 광고비 합 ÷ 최근 7일 지원 합", "일별 CPA의 평균이 아님", "2.1 + 2.2"),
        ("CTR / CPC / CPM", "클릭÷노출 / 광고비÷클릭 / 광고비÷노출×1,000", "매체 집계 단위(회)", "2.1 (BigQuery)"),
        ("주차", "월요일~일요일 (config.WEEK_START_WEEKDAY = 0)", "진행 중 주는 직전 주를 같은 요일까지 비교", "—"),
    ], columns=["지표", "정의", "분모·기준", "데이터 출처"])
    show_table(definitions, use_container_width=True, hide_index=True)

    st.markdown("#### 🔧 분류 규칙 (src/config.py)")
    st.markdown("**유입 채널 → 매체 그룹**")
    show_table(pd.DataFrame(list(CHANNEL_GROUP_MAP.items()), columns=["유입 채널(원문)", "매체 그룹"]),
                 use_container_width=True, hide_index=True)

    st.markdown("#### ⚙️ 기준값 (초기값은 가정)")
    show_table(pd.DataFrame([
        ("최소 집행액 (CPA 판단)", f"{MIN_COST_FOR_CPA:,}원 미만 제외"),
        ("최소 표본 (비율 인사이트)", f"지원 {MIN_SAMPLE_FOR_INSIGHT:,}명 미만이면 생략"),
        ("일 지원 변동 주의", f"일 지원 {MIN_DAILY_APPLICANTS_STABLE:,}명 미만"),
        ("CPA 악화 / 개선 배율", f"{CPA_WORSE_RATIO} 이상 / {CPA_BETTER_RATIO} 이하"),
        ("비용↑ 지원↓", f"비용 {COST_UP_RATIO}배 이상 & 지원 {APPLICANT_DOWN_RATIO}배 이하"),
        ("사유 집중 기준", f"한 매체 탈락·포기의 {REASON_SHARE_ALERT * 100:.0f}% 이상"),
        ("유입 경로 누락 경고", f"{MISSING_CHANNEL_ALERT * 100:.0f}% 이상"),
        ("진행 중 비율 경고", f"{IN_PROGRESS_ALERT * 100:.0f}% 이상"),
    ], columns=["항목", "기준"]), use_container_width=True, hide_index=True)

    st.markdown("#### 🛰️ 데이터 연결 상태")
    status_rows = []
    for cid, course in COURSES.items():
        for sem, cohort in course["cohorts"].items():
            if (cid, sem) not in RECRUITING_COHORTS:
                continue
            b = try_bundle(cid, sem)
            if b is None:
                status_rows.append({"과정": course["name"], "기수": f"{sem}기", "상태": "조회 실패",
                                    "지원자 행 수": None, "광고 매체 수": None, "광고 최신 일자": ""})
                continue
            latest_ad = b["wide"]["date"].max() if not b["wide"].empty else None
            status_rows.append({"과정": course["name"], "기수": f"{sem}기", "상태": "정상",
                                "지원자 행 수": len(b["apps"]),
                                "광고 매체 수": int(b["wide"]["block"].nunique()) if not b["wide"].empty else 0,
                                "광고 최신 일자": f"{to_date(latest_ad):%Y-%m-%d}" if latest_ad is not None else "없음"})
    show_table(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 📝 마케팅 액션 로그 입력 가이드")
    st.markdown(
        f"- 스프레드시트 ID: `ACTION_LOG_SHEET_ID` (현재 {'설정됨' if ACTION_LOG_SHEET_ID.strip() else '미설정'}) · 탭 이름: `{ACTION_LOG_SHEET_NAME}`\n"
        "- 첫 행 헤더: 변경일, 과정ID, 기수, 매체, 캠페인·소재, 변경유형, 변경내용, 변경이유, 담당자, 추후 확인 지표, 확인 예정일\n"
        "- 과정ID를 비우면 모든 과정에 적용, 기수를 비우면 과정 전체에 적용됩니다\n"
        "- 변경일은 YYYY-MM-DD 형식으로 입력하세요 (형식이 틀린 행은 무시됩니다)\n"
        f"- 변경유형 예시: {', '.join(CHANGE_TYPES)}\n"
        "- 대시보드는 읽기 전용입니다. 입력·수정 권한은 시트 공유 설정으로 관리하세요"
    )


