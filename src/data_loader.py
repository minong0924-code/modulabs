"""시트 데이터 파싱 및 퍼널 집계"""

import pandas as pd
from datetime import datetime
from .sheets_client import get_sheet_data
from .config import FUNNEL_COLS, FUNNEL_LABELS, REQUIRED_COLUMNS

def load_applicants(sheet_id: str, sheet_name: str, header_row: int = 4) -> pd.DataFrame:
    """시트에서 지원자 행 데이터를 DataFrame으로 반환"""
    if not sheet_id or not sheet_id.strip():
        return pd.DataFrame()

    data = get_sheet_data(sheet_id, sheet_name, header_row=header_row)

    if data is None or len(data) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # 모든 컬럼명의 앞뒤 공백 제거
    df.columns = df.columns.str.strip()

    # 필요한 컬럼만 선택 (존재하는 컬럼만)
    cols_to_keep = [col for col in REQUIRED_COLUMNS if col in df.columns]
    df = df[cols_to_keep]

    # "수강료 결제" 컬럼이 없으면 빈 컬럼으로 생성 (프라이빗AI 등에서 사용)
    if "수강료 결제" not in df.columns:
        df["수강료 결제"] = ""

    # 일자 컬럼 처리
    if "일자" in df.columns:
        df["일자"] = pd.to_datetime(df["일자"], errors="coerce")

    return df

def get_funnel_counts(df: pd.DataFrame) -> dict:
    """퍼널 단계별 인원 수 집계"""
    if df.empty:
        return {col: 0 for col in FUNNEL_LABELS}

    # 지원자는 신청자 이름이 있는 행만 카운트
    applicant_count = 0
    if "신청자 이름" in df.columns:
        applicant_count = df["신청자 이름"].astype(str).str.strip().ne("").sum()
    else:
        applicant_count = len(df)

    funnel_counts = {"지원자": int(applicant_count)}

    for col, label in zip(FUNNEL_COLS, FUNNEL_LABELS[1:]):
        if col in df.columns:
            # 'O' 값만 카운트 (대소문자 구분 없음, 공백 제거)
            count = (df[col].astype(str).str.strip().str.upper() == 'O').sum()
            funnel_counts[label] = int(count)
        else:
            # 컬럼이 없으면 로그 출력 (디버깅용)
            funnel_counts[label] = 0

    return funnel_counts

def get_channel_counts(df: pd.DataFrame) -> pd.DataFrame:
    """유입채널별 지원자 수 및 입학 전환율"""
    if df.empty:
        return pd.DataFrame()

    channel_col = "유입 채널"
    final_admission_col = "최종 입학"

    if channel_col not in df.columns:
        return pd.DataFrame()

    channel_data = []

    for channel in df[channel_col].unique():
        if pd.isna(channel) or channel == "":
            continue

        channel_df = df[df[channel_col] == channel]
        applicant_count = len(channel_df)

        admission_count = 0
        if final_admission_col in df.columns:
            admission_count = (channel_df[final_admission_col] == 'O').sum()

        conversion_rate = (admission_count / applicant_count * 100) if applicant_count > 0 else 0

        channel_data.append({
            "유입채널": channel,
            "지원자수": applicant_count,
            "최종합격수": int(admission_count),
            "전환율(%)": round(conversion_rate, 1)
        })

    return pd.DataFrame(channel_data).sort_values("지원자수", ascending=False)

def get_channel_detailed_stats(df: pd.DataFrame) -> pd.DataFrame:
    """유입채널별 상세 퍼널 통계 (지원자, 서류, 인터뷰, 입학, 결제 + 각 단계별 합격률)"""
    if df.empty:
        return pd.DataFrame()

    channel_col = "유입 채널"
    if channel_col not in df.columns:
        return pd.DataFrame()

    channel_data = []

    for channel in df[channel_col].unique():
        if pd.isna(channel) or channel == "":
            continue

        channel_df = df[df[channel_col] == channel]
        applicant_count = len(channel_df)

        # 각 단계별 'O' 개수 세기 (정확한 컬럼명 사용)
        paper_count = (channel_df["서류 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "서류 합격" in channel_df.columns else 0
        interview_count = (channel_df["인터뷰 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "인터뷰 합격" in channel_df.columns else 0
        admission_count = (channel_df["최종 입학"].astype(str).str.strip().str.upper() == 'O').sum() if "최종 입학" in channel_df.columns else 0
        payment_count = (channel_df["수강료 결제"].astype(str).str.strip().str.upper() == 'O').sum() if "수강료 결제" in channel_df.columns else 0

        # 각 단계별 합격률 계산
        paper_rate = (paper_count / max(applicant_count, 1)) * 100
        interview_rate = (interview_count / max(paper_count, 1)) * 100
        admission_rate = (admission_count / max(interview_count, 1)) * 100
        payment_rate = (payment_count / max(admission_count, 1)) * 100

        channel_data.append({
            "채널": channel,
            "지원자": applicant_count,
            "서류합격": int(paper_count),
            "서류합격율(%)": round(paper_rate, 1),
            "인터뷰합격": int(interview_count),
            "인터뷰합격율(%)": round(interview_rate, 1),
            "최종입학": int(admission_count),
            "최종입학율(%)": round(admission_rate, 1),
            "자기부담금 결제": int(payment_count),
            "결제율(%)": round(payment_rate, 1)
        })

    return pd.DataFrame(channel_data).sort_values("지원자", ascending=False)

def get_daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    """날짜별 지원자 현황 (1주차부터 최근까지)"""
    if df.empty or "일자" not in df.columns:
        return pd.DataFrame()

    df_copy = df.copy()

    # 그룹 미팅일 기준이 있으면 1주차의 일자를 시작점으로 사용
    start_date = None
    if "그룹 미팅일 기준" in df_copy.columns:
        week1_rows = df_copy[df_copy["그룹 미팅일 기준"].astype(str).str.strip() == "1주차"]
        if not week1_rows.empty and "일자" in week1_rows.columns:
            week1_dates = pd.to_datetime(week1_rows["일자"], errors="coerce").dropna()
            if len(week1_dates) > 0:
                start_date = week1_dates.min()

    # 일자 컬럼을 datetime으로 변환
    df_copy["일자"] = pd.to_datetime(df_copy["일자"], errors="coerce")

    # 날짜가 없는 행 제거
    df_copy = df_copy.dropna(subset=["일자"])

    if df_copy.empty:
        return pd.DataFrame()

    # 시간 정보 제거 - 날짜만 추출
    df_copy["일자_정규화"] = df_copy["일자"].dt.normalize()

    # 고유한 날짜들 추출
    unique_dates = sorted(df_copy["일자_정규화"].unique())

    if len(unique_dates) == 0:
        return pd.DataFrame()

    # start_date가 없으면 최소 날짜 사용
    if start_date is None:
        min_date = pd.Timestamp(unique_dates[0])
    else:
        min_date = pd.Timestamp(start_date)

    max_date = pd.Timestamp(unique_dates[-1])

    # 1주차 시작일부터 최근 일자까지의 모든 날짜 범위 생성
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')

    # 각 날짜별로 COUNTIF 방식으로 카운팅
    daily_counts = []
    for date in date_range:
        # 해당 날짜의 지원자 수 카운팅
        count = (df_copy["일자_정규화"] == date).sum()
        daily_counts.append({"일자": date, "일일지원자": int(count)})

    daily_df = pd.DataFrame(daily_counts)
    daily_df["누적지원자"] = daily_df["일일지원자"].cumsum()

    return daily_df

def get_dropout_reasons(df: pd.DataFrame) -> pd.DataFrame:
    """수강포기 사유별 집계 (수강포기 칼럼에 '수강포기'라고 명시된 경우)"""
    if df.empty:
        return pd.DataFrame()

    dropout_col = "수강포기"
    reason_col = "사유"

    if dropout_col not in df.columns:
        return pd.DataFrame()

    # 수강포기 칼럼에 '수강포기'라고 명시된 행만 필터링
    dropout_df = df[df[dropout_col].astype(str).str.strip() == "수강포기"].copy()

    if len(dropout_df) == 0:
        return pd.DataFrame()

    # 사유 컬럼에서 포기 사유 추출
    if reason_col in dropout_df.columns:
        # 빈 값 제거
        reason_df = dropout_df[dropout_df[reason_col].astype(str).str.strip() != ""].copy()
        if len(reason_df) > 0:
            reason_counts = reason_df[reason_col].value_counts().reset_index()
            reason_counts.columns = ["사유", "인원"]
            return reason_counts.sort_values("인원", ascending=False)
        else:
            return pd.DataFrame({"사유": ["기타"], "인원": [len(dropout_df)]})
    else:
        # 사유 컬럼이 없으면 전체 수강포기자 수만 표시
        return pd.DataFrame({"사유": ["기타"], "인원": [len(dropout_df)]})

def get_dropout_count(df: pd.DataFrame) -> int:
    """수강포기자 수"""
    if df.empty or "수강포기" not in df.columns:
        return 0
    return (df["수강포기"].astype(str).str.strip() == "수강포기").sum()

def get_document_rejection_stats(df: pd.DataFrame) -> pd.DataFrame:
    """서류 불합격자 사유별 집계 (서류 합격이 'X'인 경우)"""
    if df.empty or "서류 합격" not in df.columns:
        return pd.DataFrame()

    # 서류 합격이 'X'인 행만 필터링
    rejection_df = df[df["서류 합격"].astype(str).str.strip().str.upper() == 'X'].copy()

    if len(rejection_df) == 0:
        return pd.DataFrame()

    # 사유 컬럼에서 불합격 사유 추출
    if "사유" in rejection_df.columns:
        # 빈 값 제거
        reason_df = rejection_df[rejection_df["사유"].astype(str).str.strip() != ""].copy()
        if len(reason_df) > 0:
            reason_counts = reason_df["사유"].value_counts().reset_index()
            reason_counts.columns = ["사유", "인원"]
            return reason_counts.sort_values("인원", ascending=False)
        else:
            return pd.DataFrame({"사유": ["기타"], "인원": [len(rejection_df)]})
    else:
        # 사유 컬럼이 없으면 전체 불합격자 수만 표시
        return pd.DataFrame({"사유": ["기타"], "인원": [len(rejection_df)]})

def get_document_rejection_count(df: pd.DataFrame) -> int:
    """서류 불합격자 수"""
    if df.empty or "서류 합격" not in df.columns:
        return 0
    return (df["서류 합격"].astype(str).str.strip().str.upper() == 'X').sum()

def get_applicants_list(df: pd.DataFrame) -> pd.DataFrame:
    """지원자별 현황 목록 (이름, 채널, 퍼널 단계, 상태)"""
    if df.empty:
        return pd.DataFrame()

    applicants_df = df.copy()

    # 이름이 없는 행 제외
    if "신청자 이름" in applicants_df.columns:
        applicants_df = applicants_df[applicants_df["신청자 이름"].astype(str).str.strip() != ""].copy()

    if applicants_df.empty:
        return pd.DataFrame()

    # 상태 컬럼 추가 (퍼널 진행 상황)
    status_list = []
    for idx, row in applicants_df.iterrows():
        if "수강료 결제" in applicants_df.columns and str(row.get("수강료 결제", "")).strip().upper() == "O":
            status = "수강료 결제 완료"
        elif "최종 입학" in applicants_df.columns and str(row.get("최종 입학", "")).strip().upper() == "O":
            status = "최종 입학"
        elif "인터뷰 합격" in applicants_df.columns and str(row.get("인터뷰 합격", "")).strip().upper() == "O":
            status = "인터뷰 합격"
        elif "서류 합격" in applicants_df.columns and str(row.get("서류 합격", "")).strip().upper() == "X":
            status = "서류 불합격"
        elif "서류 합격" in applicants_df.columns and str(row.get("서류 합격", "")).strip().upper() == "O":
            status = "서류 합격"
        elif "수강포기" in applicants_df.columns and str(row.get("수강포기", "")).strip() == "수강포기":
            status = "수강포기"
        else:
            status = "지원 중"

        status_list.append(status)

    applicants_df["상태"] = status_list

    # 표시할 컬럼 정렬 (존재하는 컬럼만)
    display_cols = ["신청자 이름"]
    if "일자" in applicants_df.columns:
        display_cols.append("일자")
    if "유입 채널" in applicants_df.columns:
        display_cols.append("유입 채널")
    display_cols.append("상태")
    if "사유" in applicants_df.columns:
        display_cols.append("사유")

    result_df = applicants_df[display_cols].reset_index(drop=True)

    # 일자 컬럼 정규화 (datetime으로 변환)
    if "일자" in result_df.columns:
        result_df["일자"] = pd.to_datetime(result_df["일자"], errors="coerce")

    return result_df

def get_summary_stats(df: pd.DataFrame) -> dict:
    """종합 통계"""
    funnel = get_funnel_counts(df)
    dropout = get_dropout_count(df)
    rejection = get_document_rejection_count(df)

    return {
        "지원자": funnel.get("지원자", 0),
        "지원서검토완료": funnel.get("지원서검토완료", 0),
        "서류합격": funnel.get("서류합격", 0),
        "서류불합격": rejection,
        "인터뷰합격": funnel.get("인터뷰합격", 0),
        "최종입학": funnel.get("최종입학", 0),
        "수강료결제": funnel.get("수강료결제", 0),
        "수강포기": dropout,
    }

def get_weekly_funnel_stats(df: pd.DataFrame) -> pd.DataFrame:
    """주차별 퍼널 통계 (사전신청자, 1주차, 2주차 등) - 합격 비율 포함"""
    if df.empty or "그룹 미팅일 기준" not in df.columns:
        return pd.DataFrame()

    # 주차별로 그룹화
    weekly_data = []

    for week in df["그룹 미팅일 기준"].unique():
        if pd.isna(week) or week == "" or week.strip() == "":
            continue

        week_df = df[df["그룹 미팅일 기준"] == week]

        # 지원자 수 (신청자 이름이 있는 행)
        applicant_count = 0
        if "신청자 이름" in week_df.columns:
            applicant_count = week_df["신청자 이름"].astype(str).str.strip().ne("").sum()
        else:
            applicant_count = len(week_df)

        # 각 단계별 집계
        paper_count = (week_df["서류 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "서류 합격" in week_df.columns else 0
        interview_count = (week_df["인터뷰 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "인터뷰 합격" in week_df.columns else 0
        admission_count = (week_df["최종 입학"].astype(str).str.strip().str.upper() == 'O').sum() if "최종 입학" in week_df.columns else 0
        payment_count = (week_df["수강료 결제"].astype(str).str.strip().str.upper() == 'O').sum() if "수강료 결제" in week_df.columns else 0

        # 각 단계별 합격 비율 계산
        paper_rate = (paper_count / max(applicant_count, 1)) * 100
        interview_rate = (interview_count / max(paper_count, 1)) * 100
        admission_rate = (admission_count / max(interview_count, 1)) * 100
        payment_rate = (payment_count / max(admission_count, 1)) * 100

        weekly_data.append({
            "주차": week,
            "지원자": int(applicant_count),
            "서류합격": int(paper_count),
            "서류합격율(%)": round(paper_rate, 1),
            "인터뷰합격": int(interview_count),
            "인터뷰합격율(%)": round(interview_rate, 1),
            "최종입학": int(admission_count),
            "최종입학율(%)": round(admission_rate, 1),
            "자기부담금 결제": int(payment_count),
            "결제율(%)": round(payment_rate, 1)
        })

    # 주차 순서대로 정렬 (사전신청, 사전신청자, 1주차, 2주차, ...)
    week_order = {"사전신청": 0, "사전신청자": 0}
    for i in range(1, 50):
        week_order[f"{i}주차"] = i

    if weekly_data:
        weekly_df = pd.DataFrame(weekly_data)
        weekly_df["정렬순서"] = weekly_df["주차"].map(lambda x: week_order.get(x, 999))
        weekly_df = weekly_df.sort_values("정렬순서").drop("정렬순서", axis=1).reset_index(drop=True)
        return weekly_df

    return pd.DataFrame()

def get_weekly_channel_stats(df: pd.DataFrame) -> pd.DataFrame:
    """주차별 유입경로 통계 (지원자, 서류합격, 서류합격률, 서류불합격, 서류불합격률)"""
    if df.empty or "그룹 미팅일 기준" not in df.columns or "유입 채널" not in df.columns:
        return pd.DataFrame()

    # 주차 순서
    week_order = {"사전신청": 0, "사전신청자": 0}
    for i in range(1, 50):
        week_order[f"{i}주차"] = i

    channel_data = []

    # 각 주차별로 유입경로 통계 생성
    for week in sorted(df["그룹 미팅일 기준"].unique(), key=lambda x: week_order.get(x, 999)):
        if pd.isna(week) or week == "" or week.strip() == "":
            continue

        week_df = df[df["그룹 미팅일 기준"] == week]

        # 각 채널별 통계
        for channel in week_df["유입 채널"].unique():
            if pd.isna(channel) or channel == "" or channel.strip() == "":
                continue

            channel_df = week_df[week_df["유입 채널"] == channel]

            # 지원자 수
            applicant_count = len(channel_df)

            # 서류합격 수
            paper_count = (channel_df["서류 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "서류 합격" in channel_df.columns else 0

            # 서류합격률
            paper_rate = (paper_count / max(applicant_count, 1)) * 100

            # 서류불합격 수 (X인 경우)
            rejection_count = (channel_df["서류 합격"].astype(str).str.strip().str.upper() == 'X').sum() if "서류 합격" in channel_df.columns else 0

            # 서류불합격률
            rejection_rate = (rejection_count / max(applicant_count, 1)) * 100

            channel_data.append({
                "주차": week,
                "채널": channel,
                "지원자": int(applicant_count),
                "서류합격": int(paper_count),
                "서류합격율(%)": round(paper_rate, 1),
                "서류불합격": int(rejection_count),
                "서류불합격율(%)": round(rejection_rate, 1)
            })

    if not channel_data:
        return pd.DataFrame()

    channel_df = pd.DataFrame(channel_data)

    # 주차별로 그룹화하여 반환
    return channel_df

def get_weekly_rejection_stats(df: pd.DataFrame) -> dict:
    """주차별 서류 불합격 사유 (행: 사유, 열: 주차)"""
    if df.empty or "그룹 미팅일 기준" not in df.columns:
        return pd.DataFrame()

    # 주차별 정렬 순서
    week_order = {"사전신청": 0, "사전신청자": 0}
    for i in range(1, 50):
        week_order[f"{i}주차"] = i

    rejection_data = []

    for week in df["그룹 미팅일 기준"].unique():
        if pd.isna(week) or week == "" or week.strip() == "":
            continue

        week_df = df[df["그룹 미팅일 기준"] == week]

        # 서류 불합격 필터링
        rejection_df = week_df[week_df["서류 합격"].astype(str).str.strip().str.upper() == 'X'].copy()

        if len(rejection_df) == 0:
            continue

        # 사유 집계
        if "사유" in rejection_df.columns:
            reason_df = rejection_df[rejection_df["사유"].astype(str).str.strip() != ""].copy()
            if len(reason_df) > 0:
                reason_counts = reason_df["사유"].value_counts()
                for reason, count in reason_counts.items():
                    rejection_data.append({
                        "사유": reason,
                        "주차": week,
                        "인원": int(count)
                    })
            else:
                rejection_data.append({
                    "사유": "기타",
                    "주차": week,
                    "인원": len(rejection_df)
                })
        else:
            rejection_data.append({
                "사유": "기타",
                "주차": week,
                "인원": len(rejection_df)
            })

    if not rejection_data:
        return pd.DataFrame()

    # 데이터프레임으로 변환
    rejection_df = pd.DataFrame(rejection_data)

    # 피벗 테이블로 변환 (행: 사유, 열: 주차)
    pivot_df = rejection_df.pivot_table(
        index="사유",
        columns="주차",
        values="인원",
        aggfunc="sum",
        fill_value=0
    ).astype(int)

    # 열을 주차 순서대로 정렬
    sorted_weeks = sorted(pivot_df.columns, key=lambda x: week_order.get(x, 999))
    pivot_df = pivot_df[sorted_weeks]

    # 총계 컬럼 추가
    pivot_df["총계"] = pivot_df.sum(axis=1)

    # 총계 기준으로 내림차순 정렬
    pivot_df = pivot_df.sort_values("총계", ascending=False)

    return pivot_df

def get_weekly_meta_material_stats(df: pd.DataFrame) -> pd.DataFrame:
    """주차별 메타 유입자의 소재별 퍼널 통계 (주차, 소재, 지원자, 서류합격, 서류불합격)"""
    if df.empty or "그룹 미팅일 기준" not in df.columns or "유입 채널" not in df.columns:
        return pd.DataFrame()

    # 주차 순서
    week_order = {"사전신청": 0, "사전신청자": 0}
    for i in range(1, 50):
        week_order[f"{i}주차"] = i

    material_data = []

    # 각 주차별로 처리
    for week in df["그룹 미팅일 기준"].unique():
        if pd.isna(week) or week == "" or week.strip() == "":
            continue

        week_df = df[df["그룹 미팅일 기준"] == week]

        # 메타 유입자만 필터링
        meta_df = week_df[week_df["유입 채널"].astype(str).str.strip() == "메타"].copy()

        if meta_df.empty:
            continue

        # 소재 컬럼이 없으면 스킵
        if "유입 소재 및 키워드" not in meta_df.columns:
            continue

        # 각 소재별로 통계 생성
        for material in meta_df["유입 소재 및 키워드"].unique():
            if pd.isna(material) or str(material).strip() == "":
                continue

            material_df = meta_df[meta_df["유입 소재 및 키워드"] == material]

            # 지원자 수
            applicant_count = len(material_df)

            # 서류합격 수
            paper_pass_count = (material_df["서류 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "서류 합격" in material_df.columns else 0

            # 서류불합격 수
            paper_reject_count = (material_df["서류 합격"].astype(str).str.strip().str.upper() == 'X').sum() if "서류 합격" in material_df.columns else 0

            # 서류합격률
            paper_pass_rate = (paper_pass_count / max(applicant_count, 1)) * 100

            # 서류불합격률
            paper_reject_rate = (paper_reject_count / max(applicant_count, 1)) * 100

            material_data.append({
                "주차": week,
                "소재": material,
                "지원자": int(applicant_count),
                "서류합격": int(paper_pass_count),
                "서류합격율(%)": round(paper_pass_rate, 1),
                "서류불합격": int(paper_reject_count),
                "서류불합격율(%)": round(paper_reject_rate, 1)
            })

    if not material_data:
        return pd.DataFrame()

    material_df = pd.DataFrame(material_data)

    return material_df

def get_meta_material_detailed_stats(df: pd.DataFrame) -> pd.DataFrame:
    """메타 유입자의 소재별 상세 퍼널 통계 (지원자, 서류, 인터뷰, 입학, 결제 + 각 단계별 합격률)"""
    if df.empty or "유입 채널" not in df.columns:
        return pd.DataFrame()

    # 메타 유입자만 필터링
    meta_df = df[df["유입 채널"].astype(str).str.strip() == "메타"].copy()

    if meta_df.empty:
        return pd.DataFrame()

    # 소재 컬럼이 없으면 반환
    if "유입 소재 및 키워드" not in meta_df.columns:
        return pd.DataFrame()

    material_data = []

    # 각 소재별로 통계 생성
    for material in meta_df["유입 소재 및 키워드"].unique():
        if pd.isna(material) or str(material).strip() == "":
            continue

        material_df = meta_df[meta_df["유입 소재 및 키워드"] == material]
        applicant_count = len(material_df)

        # 각 단계별 'O' 개수 세기
        paper_count = (material_df["서류 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "서류 합격" in material_df.columns else 0
        interview_count = (material_df["인터뷰 합격"].astype(str).str.strip().str.upper() == 'O').sum() if "인터뷰 합격" in material_df.columns else 0
        admission_count = (material_df["최종 입학"].astype(str).str.strip().str.upper() == 'O').sum() if "최종 입학" in material_df.columns else 0
        payment_count = (material_df["수강료 결제"].astype(str).str.strip().str.upper() == 'O').sum() if "수강료 결제" in material_df.columns else 0

        # 각 단계별 합격률 계산
        paper_rate = (paper_count / max(applicant_count, 1)) * 100
        interview_rate = (interview_count / max(paper_count, 1)) * 100
        admission_rate = (admission_count / max(interview_count, 1)) * 100
        payment_rate = (payment_count / max(admission_count, 1)) * 100

        material_data.append({
            "소재": material,
            "지원자": applicant_count,
            "서류합격": int(paper_count),
            "서류합격율(%)": round(paper_rate, 1),
            "인터뷰합격": int(interview_count),
            "인터뷰합격율(%)": round(interview_rate, 1),
            "최종입학": int(admission_count),
            "최종입학율(%)": round(admission_rate, 1),
            "자기부담금 결제": int(payment_count),
            "결제율(%)": round(payment_rate, 1)
        })

    if not material_data:
        return pd.DataFrame()

    material_df = pd.DataFrame(material_data).sort_values("지원자", ascending=False)

    return material_df

