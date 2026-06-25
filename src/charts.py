"""Plotly 차트 함수"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

def create_funnel_chart(funnel_counts: dict) -> go.Figure:
    """모집 퍼널 차트 (지원자 > 서류합격 > 인터뷰합격 > 최종입학 > 자기부담금결제)"""

    # 단순화된 퍼널: 지원서검토완료 제거
    display_labels = [
        "지원자",
        "서류합격",
        "인터뷰합격",
        "최종입학",
        "자기부담금 결제"
    ]

    funnel_stages = [
        "지원자",
        "서류합격",
        "인터뷰합격",
        "최종입학",
        "수강료결제"
    ]

    values = [funnel_counts.get(stage, 0) for stage in funnel_stages]

    # 비율 계산 및 라벨 생성
    text = []
    for i, label in enumerate(display_labels):
        value = values[i]
        if i == 0:  # 지원자
            text.append(f"{label}<br>{value}명")
        elif i == 1:  # 서류합격 (지원자 대비)
            if values[0] > 0:
                percent = (value / values[0]) * 100
                text.append(f"{label}<br>{value}명<br>({percent:.1f}%)")
            else:
                text.append(f"{label}<br>{value}명")
        elif i == 2:  # 인터뷰합격 (서류합격 대비)
            if values[1] > 0:
                percent = (value / values[1]) * 100
                text.append(f"{label}<br>{value}명<br>({percent:.1f}%)")
            else:
                text.append(f"{label}<br>{value}명")
        elif i == 3:  # 최종입학 (인터뷰합격 대비)
            if values[2] > 0:
                percent = (value / values[2]) * 100
                text.append(f"{label}<br>{value}명<br>({percent:.1f}%)")
            else:
                text.append(f"{label}<br>{value}명")
        elif i == 4:  # 자기부담금결제 (최종입학 대비)
            if values[3] > 0:
                percent = (value / values[3]) * 100
                text.append(f"{label}<br>{value}명<br>({percent:.1f}%)")
            else:
                text.append(f"{label}<br>{value}명")

    fig = go.Figure(go.Funnel(
        y=display_labels,
        x=values,
        text=text,
        textposition="inside",
        textfont=dict(size=11, color="white"),
        marker=dict(color=["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]),
        hovertemplate="<b>%{y}</b><br>인원: %{x}<extra></extra>",
        textinfo="text"
    ))

    fig.update_layout(
        height=450,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False
    )

    return fig

def create_channel_donut_chart(channel_df: pd.DataFrame) -> go.Figure:
    """유입채널별 도넛 차트"""
    if channel_df.empty:
        return go.Figure()

    fig = go.Figure(data=[go.Pie(
        labels=channel_df["유입채널"],
        values=channel_df["지원자수"],
        hole=0.3,
        textposition="inside",
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>지원자: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    return fig

def create_channel_bar_chart(channel_df: pd.DataFrame) -> go.Figure:
    """유입채널별 전환율 비교"""
    if channel_df.empty:
        return go.Figure()

    fig = go.Figure(data=[
        go.Bar(
            x=channel_df["유입채널"],
            y=channel_df["전환율(%)"],
            marker_color="indianred",
            text=channel_df["전환율(%)"],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>전환율: %{y}%<extra></extra>"
        )
    ])

    fig.update_layout(
        title="유입채널별 최종입학 전환율",
        xaxis_title="유입채널",
        yaxis_title="전환율 (%)",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return fig

def create_top_channels_by_applicants_pie(channel_detailed_df: pd.DataFrame) -> go.Figure:
    """지원자 수가 많은 순서대로 상위 5개 채널 원형 차트"""
    if channel_detailed_df.empty:
        return go.Figure()

    top_5 = channel_detailed_df.nlargest(5, "지원자")

    fig = go.Figure(data=[go.Pie(
        labels=top_5["채널"],
        values=top_5["지원자"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>지원자: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        title="<b>지원자 수 상위 5개 채널</b>",
        height=500,
        margin=dict(l=50, r=50, t=50, b=150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)),
        title_font_size=14
    )

    return fig

def create_top_channels_by_admission_pie(channel_detailed_df: pd.DataFrame) -> go.Figure:
    """최종 입학자가 많은 순서대로 상위 5개 채널 원형 차트"""
    if channel_detailed_df.empty:
        return go.Figure()

    top_5 = channel_detailed_df.nlargest(5, "최종입학")

    fig = go.Figure(data=[go.Pie(
        labels=top_5["채널"],
        values=top_5["최종입학"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>최종입학: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        title="<b>최종입학 수 상위 5개 채널</b>",
        height=500,
        margin=dict(l=50, r=50, t=50, b=150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)),
        title_font_size=14
    )

    return fig

def create_top_channels_by_paper_pie(channel_detailed_df: pd.DataFrame) -> go.Figure:
    """서류 합격자가 많은 순서대로 상위 5개 채널 원형 차트"""
    if channel_detailed_df.empty:
        return go.Figure()

    top_5 = channel_detailed_df.nlargest(5, "서류합격")

    fig = go.Figure(data=[go.Pie(
        labels=top_5["채널"],
        values=top_5["서류합격"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>서류합격: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        title="<b>서류합격 수 상위 5개 채널</b>",
        height=500,
        margin=dict(l=50, r=50, t=50, b=150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)),
        title_font_size=14
    )

    return fig

def create_top_channels_by_interview_pie(channel_detailed_df: pd.DataFrame) -> go.Figure:
    """인터뷰 합격자가 많은 순서대로 상위 5개 채널 원형 차트"""
    if channel_detailed_df.empty:
        return go.Figure()

    top_5 = channel_detailed_df.nlargest(5, "인터뷰합격")

    fig = go.Figure(data=[go.Pie(
        labels=top_5["채널"],
        values=top_5["인터뷰합격"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>인터뷰합격: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        title="<b>인터뷰합격 수 상위 5개 채널</b>",
        height=500,
        margin=dict(l=50, r=50, t=50, b=150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)),
        title_font_size=14
    )

    return fig

def create_channel_detailed_chart(channel_detailed_df: pd.DataFrame) -> go.Figure:
    """채널별 상세 정보 (지원자, 서류, 인터뷰, 입학, 결제) 그룹 바 차트"""
    if channel_detailed_df.empty:
        return go.Figure()

    fig = go.Figure()

    # 각 단계별로 trace 추가
    stages = ["지원자", "서류합격", "인터뷰합격", "최종입학", "자기부담금 결제"]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]

    for stage, color in zip(stages, colors):
        fig.add_trace(go.Bar(
            x=channel_detailed_df["채널"],
            y=channel_detailed_df[stage],
            name=stage,
            marker_color=color,
            text=channel_detailed_df[stage],
            textposition="auto",
            hovertemplate="<b>%{x}</b><br>" + stage + ": %{y}<extra></extra>"
        ))

    fig.update_layout(
        title="채널별 퍼널 단계별 인원",
        xaxis_title="유입 채널",
        yaxis_title="인원 (명)",
        barmode="group",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )

    return fig

def create_daily_trend_chart(daily_df: pd.DataFrame) -> go.Figure:
    """날짜별 일일 지원자 수 차트 (추세선 포함)"""
    if daily_df.empty:
        return go.Figure()

    # 데이터 복사본 생성 및 날짜를 문자열로 변환
    chart_df = daily_df.copy()
    chart_df["일자_str"] = pd.to_datetime(chart_df["일자"]).dt.strftime("%Y-%m-%d")

    fig = go.Figure()

    # 일일 지원자 차트
    fig.add_trace(go.Scatter(
        x=chart_df["일자_str"],
        y=chart_df["일일지원자"],
        mode="lines+markers",
        name="일일 지원자",
        line=dict(color="royalblue", width=2),
        marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>지원자: %{y}명<extra></extra>"
    ))

    # 추세선 계산 (1차 선형 회귀)
    import numpy as np
    x_numeric = np.arange(len(chart_df))
    y_values = chart_df["일일지원자"].values

    # NaN 값 제거
    mask = ~np.isnan(y_values)
    x_clean = x_numeric[mask]
    y_clean = y_values[mask]

    if len(x_clean) > 1:
        # 선형 회귀
        coeffs = np.polyfit(x_clean, y_clean, 1)
        trend_line = np.polyval(coeffs, x_numeric)

        # 추세선 추가
        fig.add_trace(go.Scatter(
            x=chart_df["일자_str"],
            y=trend_line,
            mode="lines",
            name="추세선",
            line=dict(color="red", width=2, dash="dash"),
            hovertemplate="<b>%{x}</b><br>추세: %{y:.1f}<extra></extra>"
        ))

    # Y축 범위를 최대값 기준으로 설정
    max_applicants = chart_df["일일지원자"].max()
    y_max = max_applicants * 1.1 if max_applicants > 0 else 10

    fig.update_layout(
        title="일자별 지원자 현황",
        xaxis_title="날짜",
        yaxis_title="지원자 (명)",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        yaxis=dict(range=[0, y_max]),
        showlegend=True,
        xaxis=dict(tickangle=-45),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig

def create_dropout_reason_chart(dropout_df: pd.DataFrame) -> go.Figure:
    """수강포기 사유별 도넛 차트"""
    if dropout_df.empty:
        return go.Figure()

    fig = go.Figure(data=[go.Pie(
        labels=dropout_df["사유"],
        values=dropout_df["인원"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>인원: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    return fig

def create_document_rejection_chart(rejection_df: pd.DataFrame) -> go.Figure:
    """서류 불합격자 사유별 도넛 차트"""
    if rejection_df.empty:
        return go.Figure()

    fig = go.Figure(data=[go.Pie(
        labels=rejection_df["사유"],
        values=rejection_df["인원"],
        hole=0.3,
        textposition="inside",
        textinfo="value",
        hovertemplate="<b>%{label}</b><br>인원: %{value}<br>비율: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    return fig
