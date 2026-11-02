"""지원자 분류·집계와 마케팅 지표 계산 (Streamlit 비의존 순수 함수)

원칙
- 지원자 데이터(2.2 시트)와 광고 데이터(BigQuery 2.1)는 행 단위로 합치지 않습니다.
  각각 기간·매체 단위로 집계한 뒤 같은 기간·매체 키로 맞춰 비교합니다.
- 분모가 0이면 NaN을 반환하고, 화면에서는 '계산 불가'로 표시합니다.
- 누적 통과 여부는 '다음 단계 기록이 있으면 이전 단계를 통과한 것으로 본다'는 규칙을 씁니다.
"""

import pandas as pd

from src.config import (
    APPLICANT_DOWN_RATIO,
    CHANNEL_GROUP_MAP,
    COST_UP_RATIO,
    CPA_BETTER_RATIO,
    CPA_WORSE_RATIO,
    MATCHED_AD_GROUPS,
    MIN_SAMPLE_FOR_INSIGHT,
    PAID_CHANNEL_GROUPS,
    WEEK_START_WEEKDAY,
)

# 현재 단계 이름
STAGE_REVIEWING = "서류 검토 중"
STAGE_DOC_PASSED = "서류 합격 (인터뷰 대기)"
STAGE_INTERVIEW_PENDING = "인터뷰 진행 중"
STAGE_INTERVIEW_PASSED = "인터뷰 합격 (최종 결과 대기)"
STAGE_FINAL_ADMITTED = "최종 합격 (결제 대기)"
STAGE_REGISTERED = "등록 완료"
STAGE_DOC_REJECTED = "서류 불합격"
STAGE_INTERVIEW_REJECTED = "인터뷰 불합격"
STAGE_INTERVIEW_ABSENT = "인터뷰 불참"
STAGE_DROPOUT = "수강포기"
STAGE_TRANSFERRED = "타 과정 이관"

IN_PROGRESS_STAGES = {
    STAGE_REVIEWING, STAGE_DOC_PASSED, STAGE_INTERVIEW_PENDING,
    STAGE_INTERVIEW_PASSED, STAGE_FINAL_ADMITTED,
}
# 결과가 확정된 단계 (더 이상 전형이 진행되지 않음)
TERMINAL_STAGES = {
    STAGE_REGISTERED, STAGE_DOC_REJECTED, STAGE_INTERVIEW_REJECTED,
    STAGE_INTERVIEW_ABSENT, STAGE_DROPOUT, STAGE_TRANSFERRED,
}

# 탈락·포기 구분 (사유 집계의 분모 구분). 인터뷰 불합격과 인터뷰 불참은 '인터뷰'로 묶고, 사유 열에서 구분합니다.
REJECTION_KIND_DOC = "서류"
REJECTION_KIND_INTERVIEW = "인터뷰"
REJECTION_KIND_DROPOUT = "수강 포기"
REJECTION_KIND_TRANSFER = "타 과정 이관"
REJECTION_KINDS_SHOWN = [REJECTION_KIND_DOC, REJECTION_KIND_INTERVIEW, REJECTION_KIND_DROPOUT]
ABSENT_REASON_LABEL = "불참"
TRANSFER_REASON_LABEL = "이관"

# 서류 열에 들어가는 '검토 진행' 표기 (결과 아님)
REVIEW_PENDING_TEXTS = {"지원서 검토 완료", "지원서 제출 완료"}

UNCLASSIFIED = "미분류"


def mark(value) -> str:
    """셀 값을 비교용 문자열로 정규화합니다 (앞뒤 공백 제거, 대문자).

    Args:
        value: 시트 셀 값 (None/NaN 가능)

    Returns:
        정규화된 문자열. 빈 값이면 빈 문자열.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip().upper()


def classify_channel(raw_channel) -> str:
    """유입 채널 원문을 매체 그룹으로 바꿉니다.

    Args:
        raw_channel: 2.2 시트 '유입 채널' 원문

    Returns:
        매체 그룹 이름 (예: 메타, 직접 지원, 이관, 미분류)
    """
    text = str(raw_channel).strip() if raw_channel is not None else ""
    if not text:
        return UNCLASSIFIED
    return CHANNEL_GROUP_MAP.get(text, UNCLASSIFIED)


def _stage_of(row) -> str:
    """한 지원자의 현재 전형 단계를 판정합니다.

    우선순위: 이관 > 서류 탈락 > 인터뷰 탈락 > 인터뷰 불참 > 수강포기(인터뷰 합격 이후만) > 등록 > 최종 합격 > 인터뷰 > 서류.
    탈락은 포기 표기보다 먼저 일어나므로, 탈락 기록이 있으면 포기 표기가 있어도 탈락으로 봅니다.

    Args:
        row: 정규화 전 2.2 시트 한 행 (Series)

    Returns:
        현재 단계 이름
    """
    # 이관은 사유 열에 '이관'이 명시된 경우만 인정합니다 (유입 채널·'타 과정으로 이관' 열만으로는 이관 아님)
    if TRANSFER_REASON_LABEL in mark(row.get("사유", "")):
        return STAGE_TRANSFERRED
    doc = mark(row.get("서류 합격", ""))
    interview = mark(row.get("인터뷰 합격", ""))
    if doc == "X":
        return STAGE_DOC_REJECTED
    if interview == "X":
        return STAGE_INTERVIEW_REJECTED
    if interview == "미참석":
        return STAGE_INTERVIEW_ABSENT
    # 수강포기는 인터뷰 합격 이후에 포기한 경우만 인정합니다. 그 이전 단계의 표기는 무시합니다.
    passed_interview = interview == "O" or mark(row.get("최종 입학", "")) == "O" or mark(row.get("수강료 결제", "")) == "O"
    if "수강포기" in mark(row.get("수강포기", "")) and passed_interview:
        return STAGE_DROPOUT
    if mark(row.get("수강료 결제", "")) == "O":
        return STAGE_REGISTERED
    if mark(row.get("최종 입학", "")) == "O":
        return STAGE_FINAL_ADMITTED
    if interview == "O":
        return STAGE_INTERVIEW_PASSED
    if interview:
        return STAGE_INTERVIEW_PENDING
    if doc == "O":
        return STAGE_DOC_PASSED
    return STAGE_REVIEWING


APPLICANT_COLUMNS = [
    "지원일", "주차시작", "채널원문", "사전이관", "매체그룹", "유료여부", "현재단계", "결과확정", "탈락구분",
    "사유원문", "사유표시", "탈락구분표시", "누적_서류통과", "누적_인터뷰통과", "누적_최종합격", "누적_등록",
    "서류결과확정", "인터뷰결과확정",
]


def prepare_applicants(df: pd.DataFrame) -> pd.DataFrame:
    """2.2 지원자 원본 DataFrame에 분류·누적 통과 열을 추가합니다.

    추가 열
    - 지원일, 주차시작(월요일), 채널원문, 매체그룹, 유료여부
    - 현재단계, 결과확정(bool), 탈락구분, 사유원문 (시트 원문 그대로)
    - 누적_서류통과, 누적_인터뷰통과, 누적_최종합격, 누적_등록 (bool)
    - 서류결과확정 (bool), 인터뷰결과확정 (bool)

    Args:
        df: data_loader.load_applicants() 결과 (신청자 이름이 있는 행만 지원자로 본다)

    Returns:
        분류 열이 추가된 새 DataFrame. 신청자 이름이 없는 행은 제외합니다.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=APPLICANT_COLUMNS)

    out = df.copy()
    if "신청자 이름" in out.columns:
        out = out[out["신청자 이름"].astype(str).str.strip() != ""].copy()
    if out.empty:
        return pd.DataFrame(columns=APPLICANT_COLUMNS)

    for col in ["서류 합격", "인터뷰 합격", "최종 입학", "수강료 결제", "수강포기", "타 과정으로 이관", "사유"]:
        if col not in out.columns:
            out[col] = ""

    out["지원일"] = pd.to_datetime(out["일자"], errors="coerce").dt.normalize() if "일자" in out.columns else pd.NaT
    out["주차시작"] = out["지원일"] - pd.to_timedelta(
        (out["지원일"].dt.day_of_week - WEEK_START_WEEKDAY) % 7, unit="D"
    )
    out["채널원문"] = out["유입 채널"].astype(str).str.strip() if "유입 채널" in out.columns else ""
    group_text = out["그룹 미팅일 기준"].astype(str).str.strip() if "그룹 미팅일 기준" in out.columns else pd.Series("", index=out.index)
    # 그룹 미팅일 기준이 1주차보다 앞선 '사전 신청'·'전기수 이관' 행은 모집 기간 밖이어도 지원자로 집계합니다
    out["사전이관"] = group_text.str.contains("사전|이관", na=False) | (out["채널원문"] == "사전신청")
    out["매체그룹"] = out["채널원문"].map(classify_channel)
    out["유료여부"] = out["매체그룹"].isin(PAID_CHANNEL_GROUPS)

    doc = out["서류 합격"].map(mark)
    interview = out["인터뷰 합격"].map(mark)
    final = out["최종 입학"].map(mark)
    paid = out["수강료 결제"].map(mark)

    out["현재단계"] = out.apply(_stage_of, axis=1)
    out["결과확정"] = out["현재단계"].isin(TERMINAL_STAGES)

    # 누적 통과: 다음 단계 기록이 있으면 이전 단계 통과로 본다
    # 서류 열이 X로 명시된 건은 뒤 단계 기록이 있어도 서류 통과로 보지 않습니다 (시트 기록 우선)
    later_evidence = interview.ne("") | (final == "O") | (paid == "O")
    out["누적_서류통과"] = (doc == "O") | ((doc != "X") & later_evidence)
    out["누적_인터뷰통과"] = (interview == "O") | (final == "O") | (paid == "O")
    out["누적_최종합격"] = (final == "O") | (paid == "O")
    out["누적_등록"] = paid == "O"

    # 서류·인터뷰 결과가 판정된 인원 (통과율 분모)
    out["서류결과확정"] = out["누적_서류통과"] | (doc == "X")
    out["인터뷰결과확정"] = (interview.isin(["O", "X"])) | out["누적_최종합격"]

    out["탈락구분"] = out["현재단계"].map(_rejection_kind)
    out["사유원문"] = out["사유"].astype(str).str.strip()
    # 사유표시: 인터뷰 불참은 '불참'을 앞에 붙이고, 시트 사유 문구가 있으면 괄호로 함께 보여 줍니다
    absent = out["현재단계"] == STAGE_INTERVIEW_ABSENT
    out["사유표시"] = out["사유원문"].where(~absent, "")
    out.loc[absent, "사유표시"] = [
        f"{ABSENT_REASON_LABEL} ({text})" if text else ABSENT_REASON_LABEL
        for text in out.loc[absent, "사유원문"]
    ]
    # 이관 판정: 사유 열에 '이관'이 명시된 건만 이관입니다. 유입 채널이나 '타 과정으로 이관' 열만으로는 이관으로 보지 않습니다.
    # 이관 건은 이관 전 단계로 구분을 나눕니다. 인터뷰 기록이 있으면 인터뷰, 없으면 서류로 봅니다.
    transfer = out["현재단계"] == STAGE_TRANSFERRED
    reached_interview = (interview != "") | out["누적_최종합격"]
    out["탈락구분표시"] = out["탈락구분"]
    out.loc[transfer, "탈락구분표시"] = [
        REJECTION_KIND_INTERVIEW if reached else REJECTION_KIND_DOC
        for reached in reached_interview[transfer]
    ]
    out.loc[transfer, "사유표시"] = TRANSFER_REASON_LABEL
    return out


_REJECTION_KIND_BY_STAGE = {
    STAGE_TRANSFERRED: REJECTION_KIND_TRANSFER,
    STAGE_DROPOUT: REJECTION_KIND_DROPOUT,
    STAGE_DOC_REJECTED: REJECTION_KIND_DOC,
    STAGE_INTERVIEW_REJECTED: REJECTION_KIND_INTERVIEW,
    STAGE_INTERVIEW_ABSENT: REJECTION_KIND_INTERVIEW,
}


def _rejection_kind(stage: str) -> str:
    """현재 단계로 탈락·포기 구분을 정합니다. 탈락·포기·이관이 아니면 빈 문자열."""
    return _REJECTION_KIND_BY_STAGE.get(stage, "")


PROGRESS_FLAG_COLUMNS = ["누적_서류통과", "누적_인터뷰통과", "누적_최종합격", "누적_등록"]


def attach_phone(apps: pd.DataFrame, apply_raw: pd.DataFrame) -> pd.DataFrame:
    """2.2 지원자 행에 지원서 RAW의 전화번호(숫자)를 붙입니다. 이름과 지원일이 모두 맞을 때만 붙입니다.

    Args:
        apps: prepare_applicants() 결과
        apply_raw: data_loader.load_apply_raw() 결과 (이름, 지원일, 전화번호)

    Returns:
        '전화' 열을 추가한 DataFrame. 맞는 전화번호가 없으면 빈 문자열입니다.
    """
    apps = apps.copy()
    apps["전화"] = ""
    if apps.empty or apply_raw is None or apply_raw.empty:
        return apps
    # 같은 이름·지원일에 전화번호가 여럿이면 어느 사람인지 알 수 없으므로 제외합니다
    phone_sets = apply_raw.groupby(["이름", "지원일"])["전화번호"].agg(lambda s: set(s) - {""})
    phone_of = {key: next(iter(phones)) for key, phones in phone_sets.items() if len(phones) == 1}
    keys = list(zip(apps["신청자 이름"].astype(str).str.strip(), apps["지원일"].dt.strftime("%Y-%m-%d")))
    apps["전화"] = [phone_of.get(key, "") for key in keys]
    return apps


def drop_same_person_duplicates(apps: pd.DataFrame) -> tuple:
    """이름과 전화번호가 모두 같은 지원 행을 한 사람으로 묶고, 가장 진행이 많이 된 행 하나만 남깁니다.

    진행 정도는 누적 통과 플래그 수로 봅니다. 같으면 최근 지원 행을 남깁니다.
    전화번호를 알 수 없는 행은 중복 판정하지 않습니다. 이름만 같은 사람은 다른 사람으로 봅니다.

    Args:
        apps: attach_phone() 결과

    Returns:
        (중복을 뺀 DataFrame, 제외한 행 수)
    """
    if apps.empty or "전화" not in apps.columns:
        return apps, 0
    progress = apps[PROGRESS_FLAG_COLUMNS].astype(int).sum(axis=1)
    order = apps.assign(_progress=progress).sort_values(["_progress", "지원일"], ascending=False, kind="stable")
    duplicated = order.duplicated(subset=["신청자 이름", "전화"], keep="first") & order["전화"].ne("")
    kept = order[~duplicated].drop(columns="_progress").sort_index()
    return kept, int(duplicated.sum())


def application_mask(apps: pd.DataFrame) -> pd.Series:
    """지원 건수로 집계할 행을 True로 표시합니다.

    유입 채널이 이관인 건(타 과정에서 이관, 지난·이전 기수에서 이관 등)도 모두 지원으로 집계합니다.
    탈락·포기 판정만 사유 열 기준을 따릅니다.
    """
    return pd.Series(True, index=apps.index)


def safe_div(numerator, denominator):
    """분모가 0이거나 NaN이면 NaN을 반환하는 나눗셈 (비율 지표 전용).

    Args:
        numerator: 분자 (숫자)
        denominator: 분모 (숫자)

    Returns:
        나눗셈 결과 또는 NaN
    """
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return float("nan")
    if numerator is None or pd.isna(numerator):
        return float("nan")
    return numerator / denominator


def summarize_applicants(apps: pd.DataFrame) -> dict:
    """지원자 묶음의 전형 현황 집계 (현재 단계별 인원 + 누적 통과 인원 + 확인 가능한 통과율).

    - 지원·진행 중·확정·포기 등 '지원 건수' 계열은 유입 채널이 이관인 건도 모두 포함합니다.
    - 누적 통과(서류·인터뷰·최종·등록)와 통과율 분모도 이관으로 들어온 사람을 포함합니다.

    Args:
        apps: prepare_applicants() 결과 (필터 적용 후)

    Returns:
        지원, 진행 중, 확정, 누적 통과 인원, 통과율 및 분모 값을 담은 dict
    """
    counted_rows = apps[application_mask(apps)] if not apps.empty else apps
    total = len(counted_rows)
    confirmed = int(counted_rows["결과확정"].sum()) if total else 0
    doc_decided = int(apps["서류결과확정"].sum()) if not apps.empty else 0
    interview_decided = int(apps["인터뷰결과확정"].sum()) if not apps.empty else 0
    doc_passed = int(apps["누적_서류통과"].sum()) if not apps.empty else 0
    interview_passed = int(apps["누적_인터뷰통과"].sum()) if not apps.empty else 0
    return {
        "지원": total,
        "진행중": total - confirmed,
        "확정": confirmed,
        "서류통과_누적": doc_passed,
        "인터뷰통과_누적": interview_passed,
        "최종합격_누적": int(apps["누적_최종합격"].sum()) if not apps.empty else 0,
        "등록": int(apps["누적_등록"].sum()) if not apps.empty else 0,
        "서류결과확정": doc_decided,
        "인터뷰결과확정": interview_decided,
        "서류통과율(%)": safe_div(doc_passed, doc_decided) * 100,
        "인터뷰통과율(%)": safe_div(interview_passed, interview_decided) * 100,
        "서류불합격": int((counted_rows["탈락구분표시"] == REJECTION_KIND_DOC).sum()) if total else 0,
        "인터뷰불참": int((counted_rows["현재단계"] == STAGE_INTERVIEW_ABSENT).sum()) if total else 0,
        "포기": int((counted_rows["탈락구분표시"] == REJECTION_KIND_DROPOUT).sum()) if total else 0,
        "이관": int((apps["탈락구분"] == REJECTION_KIND_TRANSFER).sum()) if not apps.empty else 0,
    }


def rejection_by_reason(apps: pd.DataFrame, by: str = None) -> pd.DataFrame:
    """탈락·포기 사유를 구분별로 집계합니다. 구분은 서류·인터뷰·수강 포기 세 가지이며, 타 과정 이관은 제외합니다.

    사유는 시트 문구 그대로 씁니다. 인터뷰 불참은 '불참'으로 표기합니다. 비율의 분모는 같은 탈락 구분 인원입니다.

    Args:
        apps: prepare_applicants() 결과
        by: 추가로 묶을 열 이름 (예: "매체그룹"). None이면 전체.

    Returns:
        [묶음, 탈락구분, 사유, 인원, 구분 내 비율(%), 분모(구분 인원)] 열 DataFrame. 사유가 비어 있으면 '(미입력)'.
    """
    prefix = [by] if by else []
    cols = prefix + ["탈락구분", "사유", "인원", "구분 내 비율(%)", "분모(구분 인원)"]
    rows = apps[apps["탈락구분표시"].isin(REJECTION_KINDS_SHOWN)].copy() if not apps.empty else apps
    if rows.empty:
        return pd.DataFrame(columns=cols)
    rows["탈락구분"] = rows["탈락구분표시"]
    rows["사유"] = rows["사유표시"].replace("", "(미입력)")
    group_keys = prefix + ["탈락구분"]
    counts = rows.groupby(group_keys + ["사유"]).size().rename("인원").reset_index()
    denom = rows.groupby(group_keys).size().rename("분모(구분 인원)").reset_index()
    result = counts.merge(denom, on=group_keys)
    result["구분 내 비율(%)"] = result["인원"] / result["분모(구분 인원)"] * 100
    # 구분 순서는 서류 → 인터뷰 → 수강 포기 (수강포기는 인터뷰 합격 이후 포기이므로 마지막)
    kind_order = pd.CategoricalDtype(REJECTION_KINDS_SHOWN, ordered=True)
    result["탈락구분"] = result["탈락구분"].astype(kind_order)
    result = result.sort_values(prefix + ["탈락구분", "인원"], ascending=[True] * len(prefix) + [True, False])
    result["탈락구분"] = result["탈락구분"].astype(str)
    return result[cols].reset_index(drop=True)


def ad_coverage(wide: pd.DataFrame):
    """광고 데이터가 존재하는 기간(최소·최대 일자)을 반환합니다.

    Args:
        wide: inflow_loader.to_wide() 결과 (date 열 포함)

    Returns:
        (시작일, 종료일) Timestamp 튜플. 데이터가 없으면 (None, None).
    """
    if wide is None or wide.empty:
        return None, None
    return wide["date"].min(), wide["date"].max()


def period_cpa(apps: pd.DataFrame, wide: pd.DataFrame, start, end) -> dict:
    """같은 기간의 광고비와 지원자로 CPA를 계산합니다.

    - 유료 매체 CPA: 2.1 광고 블록과 맞는 매체(MATCHED_AD_GROUPS)의 광고비 ÷ 그 매체 지원 수
    - 전체 모집 비용 지표: 전체 광고비 ÷ 전체 지원 수 (자연 유입 포함, 유료 매체 CPA와 다른 지표)
    - 지원자는 요청 기간 전체를 셉니다. 정규 모집 기간 밖에 들어온 지원자(사전 신청, 광고 데이터 밖 지원 포함)도 포함합니다.
    - 광고비만 광고 데이터가 있는 기간으로 잘라냅니다. 광고비 집계에 쓰인 기간은 '광고비 집계 기간' 값으로 반환합니다.

    Args:
        apps: prepare_applicants() 결과
        wide: to_wide() 결과 (매체·일자별 광고 지표)
        start: 기간 시작 (포함)
        end: 기간 종료 (포함)

    Returns:
        광고비·지원 수·CPA·최종합격 CPA 등을 담은 dict. 광고비가 없으면 값은 0 또는 NaN.
    """
    req_start, req_end = pd.Timestamp(start), pd.Timestamp(end)
    cov_start, cov_end = ad_coverage(wide)
    if cov_start is None:
        ad_start, ad_end = None, None
    else:
        ad_start, ad_end = max(req_start, cov_start), min(req_end, cov_end)
    ad_valid = ad_start is not None and ad_start <= ad_end

    empty_ad = pd.DataFrame(columns=["date", "block", "비용"])
    ad = wide[(wide["date"] >= ad_start) & (wide["date"] <= ad_end)] if ad_valid else empty_ad
    scope = apps[(apps["지원일"] >= req_start) & (apps["지원일"] <= req_end)] if not apps.empty else apps
    if not scope.empty:
        scope = scope[application_mask(scope)]

    cost_total = float(ad["비용"].sum()) if not ad.empty else 0.0
    cost_matched = float(ad.loc[ad["block"].isin(MATCHED_AD_GROUPS), "비용"].sum()) if not ad.empty else 0.0
    apps_total = len(scope)
    matched_mask = scope["매체그룹"].isin(MATCHED_AD_GROUPS) if not scope.empty else pd.Series(dtype=bool)
    apps_matched = int(matched_mask.sum())
    final_total = int(scope["누적_최종합격"].sum()) if not scope.empty else 0
    final_matched = int(scope.loc[matched_mask, "누적_최종합격"].sum()) if not scope.empty else 0

    return {
        "광고비 집계 기간": (ad_start, ad_end) if ad_valid else None,
        "광고비(전체)": cost_total,
        "광고비(매체 매칭)": cost_matched,
        "지원(전체)": apps_total,
        "지원(유료 매칭 매체)": apps_matched,
        "최종합격(전체)": final_total,
        "최종합격(유료 매칭 매체)": final_matched,
        "지원 CPA(유료 매체)": safe_div(cost_matched, apps_matched),
        "지원 CPA(전체 모집 비용)": safe_div(cost_total, apps_total),
        "최종합격 CPA(유료 매체)": safe_div(cost_matched, final_matched),
        "최종합격 CPA(전체 모집 비용)": safe_div(cost_total, final_total),
    }


def pct_change(current, previous):
    """전주·전일 대비 증감률(%)을 계산합니다. 직전 값이 0이면 표시용 문자열을 반환합니다.

    Args:
        current: 현재 기간 값
        previous: 직전 기간 값

    Returns:
        증감률(float %), '신규 발생'(직전 0, 현재 >0), '-'(둘 다 0 또는 값 없음)
    """
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return "-"
    if previous == 0:
        return "신규 발생" if current > 0 else "-"
    return (current - previous) / previous * 100


def rolling_ratio(frame: pd.DataFrame, numerator: str, denominator: str, window: int = 7) -> pd.Series:
    """일별 데이터의 이동 비율을 '분자 합계 ÷ 분모 합계'로 계산합니다 (일별 비율의 단순 평균 금지).

    Args:
        frame: date 열과 분자·분모 열을 가진 일별 DataFrame (date 오름차순)
        numerator: 분자 열 이름
        denominator: 분모 열 이름
        window: 이동 기간 (일)

    Returns:
        이동 비율 Series. 분모 합계가 0이면 NaN.
    """
    num_sum = frame[numerator].rolling(window, min_periods=window).sum()
    den_sum = frame[denominator].rolling(window, min_periods=window).sum()
    return num_sum / den_sum.where(den_sum > 0)


def build_rule_insights(current: dict, previous: dict, settings: dict) -> list:
    """두 기간의 집계를 비교해 규칙 기반 인사이트를 만듭니다.

    Args:
        current: 현재 기간 입력 dict
            - "label": 비교 기간 이름 (예: "직전 주")
            - "cost": 매체별 광고비 Series (index=매체)
            - "applicants": 매체별 지원 수 Series (index=매체)
            - "reason_by_group": reason_concentration() 결과 (선택)
            - "in_progress_rate", "in_progress", "applicants_total": 진행 중 비율·인원·지원 수 (선택)
            - "missing_rate", "missing_count": 유입 경로 누락 비율·인원 (선택)
            - "complete": 기간이 끝났는지, "data_latest": 광고 데이터 최신일 (선택)
        previous: 직전 기간 입력 dict (cost, applicants, label)
        settings: 기준값 dict
            {"min_cost", "min_sample", "cpa_worse", "cpa_better", "cost_up", "applicant_down",
             "reason_share", "missing_alert", "in_progress_alert"}

    Returns:
        [{"level": "주의"|"개선"|"정보", "finding", "evidence", "sample", "next_check", "limit"}] 목록
    """
    insights = []
    cur_cost = current.get("cost", pd.Series(dtype=float))
    prev_cost = previous.get("cost", pd.Series(dtype=float))
    cur_app = current.get("applicants", pd.Series(dtype=float))
    prev_app = previous.get("applicants", pd.Series(dtype=float))
    compare = f"{previous.get('label', '직전')} 대비"

    for group in MATCHED_AD_GROUPS:
        c_cost, p_cost = float(cur_cost.get(group, 0)), float(prev_cost.get(group, 0))
        c_app, p_app = int(cur_app.get(group, 0)), int(prev_app.get(group, 0))
        if p_cost == 0 and c_cost == 0:
            continue
        if p_cost > 0 and c_cost == 0:
            insights.append(_insight("정보", f"{group}: {compare} 집행이 없었습니다.",
                                     f"직전 광고비 {p_cost:,.0f}원 → 0원", c_app, "집행 중단 의도였는지 확인", "광고 집행 여부는 2.1 시트 기준"))
            continue
        if c_app < settings["min_sample"] or p_app < settings["min_sample"]:
            insights.append(_insight("정보", f"{group}: 지원 표본이 적어 비율 비교를 생략했습니다.",
                                     f"지원 {p_app}건 → {c_app}건 (최소 표본 {settings['min_sample']}건)", c_app,
                                     "표본이 쌓인 뒤 다시 확인", "표본 부족"))
            continue
        if c_cost < settings["min_cost"]:
            continue
        p_cpa, c_cpa = p_cost / p_app, c_cost / c_app
        ratio = c_cpa / p_cpa
        evidence = f"CPA {p_cpa:,.0f}원 → {c_cpa:,.0f}원 (광고비 {p_cost:,.0f}원→{c_cost:,.0f}원, 지원 {p_app}건→{c_app}건)"
        if ratio >= settings["cpa_worse"]:
            insights.append(_insight("주의", f"{group}: CPA가 {ratio:.1f}배로 올랐습니다.", evidence, c_app,
                                     "소재·타깃·랜딩페이지 변경 시점과 지원 채널 변화를 확인 (예산 삭감 전 원인 점검)",
                                     "CPA 상승의 원인은 단정할 수 없음 (소재·시즌·전형 진행 영향 가능)"))
        elif ratio <= settings["cpa_better"]:
            insights.append(_insight("개선", f"{group}: CPA가 {p_cpa:,.0f}원 → {c_cpa:,.0f}원으로 낮아졌습니다.", evidence, c_app,
                                     "효율 개선이 지속되는지 다음 기간에 확인", "단순 전후 비교이며 인과 효과가 아님"))
        cost_ratio = c_cost / p_cost
        app_ratio = c_app / p_app
        if cost_ratio >= settings["cost_up"] and app_ratio <= settings["applicant_down"]:
            insights.append(_insight("주의", f"{group}: 광고비는 늘었지만 지원 수는 줄었습니다.", evidence, c_app,
                                     "노출·클릭 등 광고 지표와 랜딩 전환을 함께 확인", "광고 노출·클릭은 집계 범위가 다를 수 있음"))

    for group, reasons in current.get("reason_by_group", {}).items():
        share = reasons.get("share")
        if share is None or reasons.get("sample", 0) < settings["min_sample"]:
            continue
        if share >= settings["reason_share"]:
            insights.append(_insight("주의", f"{group}: '{reasons['reason']}' 사유가 탈락·포기의 {share * 100:.0f}%입니다.",
                                     f"{reasons['reason']} {reasons['count']}건 / {reasons['sample']}건 (같은 구분 인원)", reasons["sample"],
                                     "해당 유입 경로의 모집 문구와 자격 안내 문구를 점검", "사유는 담당자 기록 기준이며 일부 미입력일 수 있음"))

    if current.get("in_progress_rate") is not None and current["in_progress_rate"] >= settings["in_progress_alert"]:
        insights.append(_insight("정보", f"전형 진행 중 인원이 {current['in_progress_rate'] * 100:.0f}%입니다.",
                                 f"진행 중 {current.get('in_progress', 0)}명 / 지원 {current.get('applicants_total', 0)}명", current.get("applicants_total", 0),
                                 "결과 확정 후 통과율을 다시 확인", "진행 중 인원은 통과율 분모에서 빠지므로 품질 판단에 한계가 있음"))

    if current.get("missing_rate") is not None and current["missing_rate"] >= settings["missing_alert"]:
        insights.append(_insight("주의", f"유입 경로 누락·미분류가 {current['missing_rate'] * 100:.0f}%입니다.",
                                 f"미분류 {current.get('missing_count', 0)}건 / 지원 {current.get('applicants_total', 0)}건", current.get("applicants_total", 0),
                                 "2.2 시트 '유입 채널' 입력 누락 건을 정리", "미분류 건은 어떤 매체에도 포함되지 않음"))

    if current.get("data_latest") is not None and not current.get("complete", True):
        insights.append(_insight("정보", "현재 기간은 아직 끝나지 않은 기간입니다.",
                                 f"광고 데이터는 {current['data_latest']:%Y-%m-%d}까지 반영", current.get("applicants_total", 0),
                                 "기간이 끝난 뒤 최종 비교", "진행 중 기간 수치는 잠정값"))

    if not insights:
        insights.append(_insight("정보", f"{compare} 눈에 띄는 변화가 없습니다.", "기준값을 넘는 변화 없음", 0, "-", "기준값은 config.py 참고"))
    return insights


def _insight(level, finding, evidence, sample, next_check, limit):
    """인사이트 한 항목을 표준 dict 형식으로 만듭니다."""
    return {"level": level, "finding": finding, "evidence": evidence, "sample": sample,
            "next_check": next_check, "limit": limit}


def channel_quality_table(apps: pd.DataFrame) -> pd.DataFrame:
    """매체 그룹별 전형 현황을 한 표로 만듭니다. 이관 건은 지원에 넣지 않습니다.

    Args:
        apps: prepare_applicants() 결과

    Returns:
        매체그룹별 summarize_applicants() 값 DataFrame (지원 수 내림차순). 지원자가 없으면 빈 DataFrame.
    """
    if apps.empty:
        return pd.DataFrame()
    counted = apps[application_mask(apps)]
    rows = []
    for group, part in counted.groupby("매체그룹"):
        summary = summarize_applicants(part)
        summary["매체그룹"] = group
        summary["유료여부"] = group in PAID_CHANNEL_GROUPS
        rows.append(summary)
    if not rows:
        return pd.DataFrame()
    table = pd.DataFrame(rows)
    return table.sort_values("지원", ascending=False).reset_index(drop=True)


def group_period_table(apps: pd.DataFrame, wide: pd.DataFrame, start, end) -> pd.DataFrame:
    """기간 안의 매체별 광고비·지원 수·지원 CPA·비중을 계산합니다.

    광고비는 2.1 블록 이름, 지원은 매체그룹 이름으로 맞춥니다. 두 이름이 같은 매체만 CPA를 계산합니다.
    호출하는 쪽에서 start·end를 광고 데이터 기간 안으로 잘라 전달하세요.

    Args:
        apps: prepare_applicants() 결과
        wide: to_wide() 결과
        start: 기간 시작 (포함)
        end: 기간 종료 (포함)

    Returns:
        매체, 광고비, 지원, 지원 CPA, 광고비 비중(%), 지원 비중(%) 열 DataFrame
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    columns = ["매체", "광고비", "지원", "지원 CPA", "광고비 비중(%)", "지원 비중(%)"]
    counted = apps[(apps["지원일"] >= start) & (apps["지원일"] <= end)] if not apps.empty else apps
    if not counted.empty:
        counted = counted[application_mask(counted)]
    ad = wide[(wide["date"] >= start) & (wide["date"] <= end)] if wide is not None and not wide.empty else pd.DataFrame(columns=["block", "비용"])

    cost = ad.groupby("block")["비용"].sum() if not ad.empty else pd.Series(dtype=float)
    apps_count = counted.groupby("매체그룹").size() if not counted.empty else pd.Series(dtype=int)
    groups = sorted(set(cost.index) | set(apps_count.index))
    if not groups:
        return pd.DataFrame(columns=columns)

    total_cost = float(cost.sum())
    total_apps = int(apps_count.sum())
    rows = []
    for group in groups:
        group_cost = float(cost.get(group, 0.0))
        group_apps = int(apps_count.get(group, 0))
        rows.append({
            "매체": group,
            "광고비": group_cost,
            "지원": group_apps,
            "지원 CPA": safe_div(group_cost, group_apps) if group in MATCHED_AD_GROUPS else float("nan"),
            "광고비 비중(%)": safe_div(group_cost, total_cost) * 100,
            "지원 비중(%)": safe_div(group_apps, total_apps) * 100,
        })
    return pd.DataFrame(rows, columns=columns).sort_values("지원", ascending=False).reset_index(drop=True)


def compare_group_tables(current: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    """두 기간의 매체별 표를 합쳐 변화량을 붙입니다. 직전 값이 0이면 '신규 발생'으로 표시합니다.

    Args:
        current: group_period_table() 결과 (현재 기간)
        previous: group_period_table() 결과 (직전 기간)

    Returns:
        매체별 현재·직전 값과 광고비·지원·CPA의 직전 대비 변화 열 DataFrame
    """
    cur = current.set_index("매체")[["광고비", "지원"]] if not current.empty else pd.DataFrame(columns=["광고비", "지원"])
    prev = previous.set_index("매체")[["광고비", "지원"]] if not previous.empty else pd.DataFrame(columns=["광고비", "지원"])
    merged = cur.merge(prev, left_index=True, right_index=True, how="outer", suffixes=(" 현재", " 직전")).fillna(0)
    out = pd.DataFrame(index=merged.index)
    out["광고비"] = merged["광고비 현재"]
    out["광고비 직전"] = merged["광고비 직전"]
    out["광고비 변화(%)"] = [pct_change(c, p) for c, p in zip(merged["광고비 현재"], merged["광고비 직전"])]
    out["지원"] = merged["지원 현재"].astype(int)
    out["지원 직전"] = merged["지원 직전"].astype(int)
    out["지원 변화(%)"] = [pct_change(c, p) for c, p in zip(merged["지원 현재"], merged["지원 직전"])]
    cur_cpa = [safe_div(c, a) for c, a in zip(merged["광고비 현재"], merged["지원 현재"])]
    prev_cpa = [safe_div(c, a) for c, a in zip(merged["광고비 직전"], merged["지원 직전"])]
    out["지원 CPA"] = cur_cpa
    out["지원 CPA 직전"] = prev_cpa
    out["CPA 변화(%)"] = [pct_change(c, p) for c, p in zip(cur_cpa, prev_cpa)]
    return out.reset_index().rename(columns={"index": "매체"})


def change_notes(row) -> str:
    """직전 기간 대비 매체 한 줄의 변화를 읽을 수 있는 참고 문구로 바꿉니다.

    기준값은 config.py의 비용 증가·지원 감소·CPA 악화/개선 비율을 씁니다.
    문구가 없으면 '특이 변화 없음'을 돌려줍니다. 표본(현재+직전 지원)이 적으면 앞에 '표본 적음'을 붙입니다.

    Args:
        row: compare_group_tables() 결과의 한 행 (광고비, 광고비 직전, 지원, 지원 직전, 지원 CPA, 지원 CPA 직전)

    Returns:
        참고 문구 문자열 (여러 개면 ' · '로 이어 붙임)
    """
    notes = []
    cost, cost_prev = float(row["광고비"]), float(row["광고비 직전"])
    apps_now, apps_prev = int(row["지원"]), int(row["지원 직전"])
    if cost_prev == 0 and cost > 0:
        notes.append("신규 집행")
    elif cost_prev > 0 and cost == 0:
        notes.append("집행 중단")
    elif cost_prev > 0 and cost / cost_prev >= COST_UP_RATIO:
        notes.append("비용 증가")

    if apps_prev == 0 and apps_now > 0:
        notes.append("지원 신규 발생")
    elif apps_prev > 0 and apps_now / apps_prev <= APPLICANT_DOWN_RATIO:
        notes.append("지원 감소")
    elif apps_prev > 0 and apps_now / apps_prev >= 1 / APPLICANT_DOWN_RATIO:
        notes.append("지원 증가")

    cpa_now, cpa_prev = row["지원 CPA"], row["지원 CPA 직전"]
    if pd.notna(cpa_now) and pd.notna(cpa_prev) and cpa_prev > 0:
        ratio = cpa_now / cpa_prev
        if ratio >= CPA_WORSE_RATIO:
            notes.append("CPA 악화")
        elif ratio <= CPA_BETTER_RATIO:
            notes.append("CPA 개선")

    if apps_now + apps_prev < MIN_SAMPLE_FOR_INSIGHT:
        notes.insert(0, "표본 적음")
    return " · ".join(notes) if notes else "특이 변화 없음"


# 참고 문구별 권장 액션 (퍼포먼스 마케터가 확인·실행할 일)
ACTION_GUIDE = {
    "비용 증가": "증액된 예산의 소재·키워드별 노출·클릭·CTR을 먼저 확인하고, 비효율 항목의 입찰·예산을 줄이세요",
    "지원 감소": "랜딩·지원서 제출 퍼널에서 이탈 구간을 점검하고, 광고 승인·노출 제한·예산 소진 여부를 확인하세요",
    "지원 증가": "증가를 만든 소재·키워드를 찾아 유지하고, 늘어난 지원의 서류 통과율도 함께 확인하세요",
    "CPA 악화": "CPA가 나빠진 상위 소재·키워드를 점검해 비효율 항목은 중지·교체하고, 입찰 상한을 조정하세요",
    "CPA 개선": "성과가 좋아진 소재·키워드에 예산을 소폭 늘리고, 변경 내용을 액션 로그에 남겨 효과를 추적하세요",
    "신규 집행": "집행 목적·타겟·소재를 확인하고, 초기 3~7일 성과를 매일 모니터링하세요",
    "집행 중단": "중단 의도(예산 소진·승인 반려·의도적 중단)를 확인하고, 필요하면 재개 계획을 세우세요",
    "지원 신규 발생": "광고 집행 없이 생긴 지원인지(오가닉·직접 유입) 유입 경로 귀속을 확인하세요",
    "표본 적음": "지원 수가 적어 판단이 어려우니 3일 이상 누적 후 다시 보세요",
}


def recommended_actions(note: str) -> str:
    """참고 문구(change_notes 결과)를 권장 액션 문장으로 바꿉니다. 해당 없으면 '유지 모니터링'.

    Args:
        note: change_notes() 결과 문자열 (' · '로 이어진 여러 문구)

    Returns:
        권장 액션 문장들을 ' / '로 이은 문자열
    """
    actions = [ACTION_GUIDE[part.strip()] for part in str(note).split("·") if part.strip() in ACTION_GUIDE]
    return " / ".join(dict.fromkeys(actions)) if actions else "유지 모니터링"


def reason_concentration(apps: pd.DataFrame) -> dict:
    """매체 그룹별로 탈락·포기 사유 원문이 한쪽으로 몰린 정도를 계산합니다 (미입력은 제외).

    Args:
        apps: prepare_applicants() 결과

    Returns:
        {매체그룹: {"reason", "count", "sample", "share"}}. share 분모는 그 매체의 탈락·포기 전체 인원.
    """
    result = {}
    if apps.empty:
        return result
    rejected = apps[apps["탈락구분"] != ""]
    for group, part in rejected.groupby("매체그룹"):
        known = part[part["사유원문"] != ""]
        if known.empty:
            continue
        top = known["사유원문"].value_counts()
        result[group] = {
            "reason": top.index[0],
            "count": int(top.iloc[0]),
            "sample": len(part),
            "share": float(top.iloc[0]) / len(part),
        }
    return result


def missing_channel_rate(apps: pd.DataFrame):
    """유입 경로가 누락되었거나 분류되지 않은 지원자 비율을 계산합니다 (이관 포함).

    Args:
        apps: prepare_applicants() 결과

    Returns:
        (미분류 인원, 비율 0~1). 지원자가 없으면 (0, NaN).
    """
    counted = apps[application_mask(apps)] if not apps.empty else apps
    total = len(counted)
    missing = int((counted["매체그룹"] == UNCLASSIFIED).sum()) if total else 0
    return missing, safe_div(missing, total)


def spend_without_applicants(daily_group: pd.DataFrame, window: int = 7, min_sample: int = 10, drop_ratio: float = 0.5) -> list:
    """광고비는 나가는데 지원이 급감한 매체를 찾습니다 (최근 window일 vs 그 직전 window일).

    Args:
        daily_group: date, 매체, 비용, 지원 열을 가진 일별·매체별 DataFrame
        window: 비교 기간 길이 (일)
        min_sample: 직전 기간 지원 수가 이 값 이상일 때만 판단
        drop_ratio: 최근 지원이 직전의 이 비율 이하이면 급감으로 봅니다

    Returns:
        [{"매체", "최근 비용", "최근 지원", "직전 지원"}] 목록
    """
    if daily_group is None or daily_group.empty:
        return []
    last_date = daily_group["date"].max()
    recent_start = last_date - pd.Timedelta(days=window - 1)
    prev_start = recent_start - pd.Timedelta(days=window)
    recent = daily_group[daily_group["date"] >= recent_start].groupby("매체")[["비용", "지원"]].sum()
    prev = daily_group[(daily_group["date"] >= prev_start) & (daily_group["date"] < recent_start)].groupby("매체")[["지원"]].sum()
    flagged = []
    for group in recent.index:
        if group not in MATCHED_AD_GROUPS:
            continue
        r_cost, r_apps = recent.loc[group, "비용"], recent.loc[group, "지원"]
        p_apps = prev.loc[group, "지원"] if group in prev.index else 0
        if r_cost > 0 and p_apps >= min_sample and r_apps <= p_apps * drop_ratio:
            flagged.append({"매체": group, "최근 비용": float(r_cost), "최근 지원": int(r_apps), "직전 지원": int(p_apps)})
    return flagged
