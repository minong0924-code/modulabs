"""모두의연구소 마케팅 대시보드 - Streamlit 메인 앱"""

import streamlit as st
import pandas as pd
from src.config import COURSES, FUNNEL_LABELS, FUNNEL_COLS
from src.data_loader import load_applicants, get_funnel_counts, get_channel_counts, get_daily_trend, get_dropout_reasons, get_summary_stats, get_channel_detailed_stats, get_document_rejection_stats, get_weekly_funnel_stats, get_weekly_rejection_stats
from src.charts import create_funnel_chart, create_channel_donut_chart, create_channel_bar_chart, create_daily_trend_chart, create_dropout_reason_chart, create_channel_detailed_chart, create_top_channels_by_applicants_pie, create_top_channels_by_admission_pie, create_top_channels_by_paper_pie, create_top_channels_by_interview_pie, create_document_rejection_chart
from datetime import datetime

@st.cache_data(ttl=300, show_spinner=False)
def load_cached(sheet_id: str, sheet_name: str):
    """캐싱 적용된 데이터 로더 (5분 TTL)"""
    return load_applicants(sheet_id, sheet_name)

# 페이지 설정
st.set_page_config(
    page_title="모두의연구소 마케팅 대시보드",
    page_icon="📊",
    layout="wide"
)

# 제목
st.title("📊 과정별 모집현황 대시보드")

# 사이드바 필터
st.sidebar.header("필터 설정")

# 데이터 새로고침 버튼
if st.sidebar.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# 과정 타입 선택
course_type = st.sidebar.radio(
    "과정 유형 선택",
    ("실업자 과정", "재직자 과정")
)

# 과정 선택 (스프레드시트 연동된 과정만)
available_courses = {
    k: v for k, v in COURSES.items()
    if (course_type == "실업자 과정" and v["type"] == "unemployed" or
        course_type == "재직자 과정" and v["type"] == "employed")
    and v["cohorts"][max(v["cohorts"].keys())].get("sheet_id", "").strip()  # sheet_id가 있는 과정만
}

selected_course_id = st.sidebar.selectbox(
    "과정 선택",
    options=list(available_courses.keys()),
    format_func=lambda x: available_courses[x]["name"]
)

# 기수 선택
selected_course = available_courses[selected_course_id]
cohort_options = list(selected_course["cohorts"].keys())
selected_cohort = st.sidebar.selectbox(
    "기수 선택",
    options=cohort_options,
    format_func=lambda x: f"{x}기"
)

# 데이터 로드
st.sidebar.info("📥 데이터 로딩 중...")

sheet_info = selected_course["cohorts"][selected_cohort]
sheet_id = sheet_info.get("sheet_id", "").strip()

if not sheet_id:
    st.warning("⚠️ 이 과정은 아직 스프레드시트가 연동되지 않았습니다.")
    st.info("관리자에게 Sheet ID를 입력해달라고 요청해주세요.")
    st.stop()

df = load_cached(sheet_id, sheet_info["sheet_name"])

if df.empty:
    st.error("데이터를 불러올 수 없습니다. 권한을 확인해주세요.")
    st.stop()

# 요약 통계 계산
stats = get_summary_stats(df)
funnel_counts = get_funnel_counts(df)
channel_df = get_channel_counts(df)
channel_detailed_df = get_channel_detailed_stats(df)
daily_df = get_daily_trend(df)
dropout_df = get_dropout_reasons(df)
rejection_df = get_document_rejection_stats(df)
weekly_funnel_df = get_weekly_funnel_stats(df)
weekly_rejection_df = get_weekly_rejection_stats(df)

# 메인 콘텐츠
st.sidebar.success(f"✅ {selected_course['name']} {selected_cohort}기 데이터 로드 완료!")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📈 종합 현황", "📊 상세 분석", "📅 주차별 분석"])

with tab1:
    # KPI 카드 (1행)
    st.subheader("📊 모집 퍼널 현황")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("지원자", f"{stats['지원자']}명")

    with col2:
        서류합격_비율 = (stats['서류합격']/max(stats['지원자'], 1)*100)
        st.metric("서류 합격", f"{stats['서류합격']}명", f"{서류합격_비율:.0f}%")

    with col3:
        인터뷰합격_비율 = (stats['인터뷰합격']/max(stats['서류합격'], 1)*100)
        st.metric("인터뷰 합격", f"{stats['인터뷰합격']}명", f"{인터뷰합격_비율:.0f}%")

    with col4:
        최종입학_비율 = (stats['최종입학']/max(stats['인터뷰합격'], 1)*100)
        st.metric("최종 입학", f"{stats['최종입학']}명", f"{최종입학_비율:.0f}%")

    with col5:
        자기부담금결제_비율 = (stats['수강료결제']/max(stats['최종입학'], 1)*100)
        st.metric("자기부담금 결제", f"{stats['수강료결제']}명", f"{자기부담금결제_비율:.0f}%")

    with col6:
        st.metric("포기", f"{stats['수강포기']}명")

    # 퍼널 차트
    fig_funnel = create_funnel_chart(funnel_counts)
    st.plotly_chart(fig_funnel, use_container_width=True)

with tab2:

    # 일자별 지원자 현황
    st.subheader("일자별 지원자 추이")
    if not daily_df.empty:
        fig_trend = create_daily_trend_chart(daily_df)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("날짜 데이터가 없습니다.")

    st.markdown("---")

    st.subheader("📊 유입 채널별 상세 현황")

    # 상위 채널 원형 차트 (1행 4열)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if not channel_detailed_df.empty:
            fig_top_applicants = create_top_channels_by_applicants_pie(channel_detailed_df)
            st.plotly_chart(fig_top_applicants, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")

    with col2:
        if not channel_detailed_df.empty:
            fig_top_paper = create_top_channels_by_paper_pie(channel_detailed_df)
            st.plotly_chart(fig_top_paper, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")

    with col3:
        if not channel_detailed_df.empty:
            fig_top_interview = create_top_channels_by_interview_pie(channel_detailed_df)
            st.plotly_chart(fig_top_interview, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")

    with col4:
        if not channel_detailed_df.empty:
            fig_top_admission = create_top_channels_by_admission_pie(channel_detailed_df)
            st.plotly_chart(fig_top_admission, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")

    if not channel_detailed_df.empty:
        # 채널을 인덱스로 설정하고 숫자 컬럼만 표시
        display_df = channel_detailed_df[["채널", "지원자", "서류합격", "인터뷰합격", "최종입학", "자기부담금 결제"]].set_index("채널")
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("채널별 상세 데이터가 없습니다.")

    st.markdown("---")

    col1, col2 = st.columns(2)

    # 서류 불합격자 인원 계산
    rejection_count = stats.get("서류불합격", 0)
    dropout_count = stats.get("수강포기", 0)

    with col1:
        st.subheader(f"서류 불합격자 ({rejection_count}명)")
        if not rejection_df.empty:
            fig_rejection = create_document_rejection_chart(rejection_df)
            st.plotly_chart(fig_rejection, use_container_width=True)

            st.subheader("불합격 사유별 인원")
            st.dataframe(rejection_df, use_container_width=True, hide_index=True)
        else:
            st.info("서류 불합격자 데이터가 없습니다.")

    with col2:
        st.subheader(f"수강포기자 ({dropout_count}명)")
        if not dropout_df.empty:
            fig_dropout = create_dropout_reason_chart(dropout_df)
            st.plotly_chart(fig_dropout, use_container_width=True)

            st.subheader("포기 사유별 인원")
            st.dataframe(dropout_df, use_container_width=True, hide_index=True)
        else:
            st.info("수강포기 데이터가 없습니다.")

with tab3:
    st.subheader("📅 주차별 퍼널 현황")

    if not weekly_funnel_df.empty:
        # 주차 순서 정렬 (사전신청, 사전신청자, 1주차, 2주차, ...)
        week_order = {"사전신청": 0, "사전신청자": 0}
        for i in range(1, 50):
            week_order[f"{i}주차"] = i

        weekly_funnel_sorted = weekly_funnel_df.copy()
        weekly_funnel_sorted["정렬순서"] = weekly_funnel_sorted["주차"].map(lambda x: week_order.get(x, 999))
        weekly_funnel_sorted = weekly_funnel_sorted.sort_values("정렬순서").drop("정렬순서", axis=1).reset_index(drop=True)

        # 주차 컬럼을 문자열로 변환하여 정렬 순서 유지
        weekly_funnel_sorted["주차"] = pd.Categorical(
            weekly_funnel_sorted["주차"],
            categories=sorted(weekly_funnel_sorted["주차"].unique(), key=lambda x: week_order.get(x, 999)),
            ordered=True
        )

        st.dataframe(weekly_funnel_sorted, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.subheader("📋 주차별 서류 불합격 사유")
        if not weekly_rejection_df.empty:
            # 주차 순서와 동일하게 정렬 (사전신청, 사전신청자, 1주차, 2주차, ...)
            week_order = {"사전신청": 0, "사전신청자": 0}
            for i in range(1, 50):
                week_order[f"{i}주차"] = i

            # 컬럼 순서 정렬
            sorted_cols = sorted(
                [col for col in weekly_rejection_df.columns if col != "총계"],
                key=lambda x: week_order.get(x, 999)
            )
            sorted_cols.append("총계")

            rejection_sorted = weekly_rejection_df[sorted_cols]

            # 주차별 총계 행 추가
            week_totals = rejection_sorted[sorted_cols[:-1]].sum()  # 총계 컬럼 제외
            week_totals['총계'] = week_totals.sum()
            week_totals.name = '총계'

            # 총계 행 추가
            rejection_with_total = pd.concat([rejection_sorted, pd.DataFrame(week_totals).T])

            st.dataframe(rejection_with_total, use_container_width=True)
        else:
            st.info("서류 불합격 데이터가 없습니다.")
    else:
        st.info("주차별 데이터가 없습니다.")
