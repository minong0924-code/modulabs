"""과정별 스프레드시트 설정"""

# 기본 헤더 행 위치 (1-based)
DEFAULT_HEADER_ROW = 4

COURSES = {
    # 실업자 과정 (4개)
    "ai_data_intel": {
        "name": "AI데이터 인텔리전스",
        "type": "unemployed",
        "cohorts": {
            1: {
                "sheet_id": "12MZ1OnGKzKnH0dBwKYScAtVycJXcBXkVdA55kzqN7Ag",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            2: {
                "sheet_id": "1CtAxiS1avLv_1FEeqSwsWtpGJklo38d8HmOAhmyli9o",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            3: {
                "sheet_id": "1WNKASohoy1Fznprdt4lvyLuciCt-CaNSGZ65AVCbRi4",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
    "ai_agent": {
        "name": "AI에이전트",
        "type": "unemployed",
        "cohorts": {
            1: {
                "sheet_id": "1B9qZFr5lPdveCbOXKzZVur1RROQVaLosD8-2wd5wAwk",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            2: {
                "sheet_id": "1V3LwfYHEUM9L2LAnw_9NU8jGXkiRWmMJ2GdTgXq6n7A",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            3: {
                "sheet_id": "1Ag9T9TjTKQLH0WdS4tpFhE0Vsc1wFiejhrrzlfDlcUg",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            4: {
                "sheet_id": "1jDwsfkHQpgSZSc1XcDQg-bW6oWC_GEllL_AWNWddR6c",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
    "ai_researcher": {
        "name": "AI리서처",
        "type": "unemployed",
        "cohorts": {
            19: {
                "sheet_id": "1WwXtMRw85IJUY3lfm0DcbY1_gI2UbXkaME1-cJXkR_I",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            20: {
                "sheet_id": "1KD1MPgzLcymLY4k-WxYLxNjnOCZH7HUJjyV_3IgG3HI",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
    "private_ai": {
        "name": "프라이빗AI",
        "type": "unemployed",
        "cohorts": {
            1: {
                "sheet_id": "1Uz0du-rwMXVi-XPNXmo2EbCkE5XZgbX94dLbYCT-P5w",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            2: {
                "sheet_id": "1KmX3v8ePQTslYSShrkKE41OxXzbG-cTgt0fcXInysEQ",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
    # 재직자 과정 (2개)
    "planning_dev": {
        "name": "재직자 기획개발",
        "type": "employed",
        "cohorts": {
            7: {
                "sheet_id": "1EshDcl6lDKzFtMTb4g5Hn1gFffuGE2rQVZl66aHk-VE",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            8: {
                "sheet_id": "1DNIV5_3FSHrbPM3D-fEOjz6y7AX9LHrhBwQrXIsSzHQ",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            9: {
                "sheet_id": "1xhLf7BUkGr0RHfxe4OWubvlPKGIMeyTRuSK4WqjFOoA",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
    "data_analysis": {
        "name": "재직자 데이터",
        "type": "employed",
        "cohorts": {
            7: {
                "sheet_id": "1b_fMajcQe8mhaHWf1qDoP_mDpNYr-ZUshUKIwgt20zk",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            8: {
                "sheet_id": "1mMShR5uoS-1GZsWMcrhZOwyYS9TXjeenS1ILuoB_JAQ",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            9: {
                "sheet_id": "1J_9nuN-8t_eKtS0YM4twOMoBOQI-TBB_ItZVvM-JdVo",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            },
            10: {
                "sheet_id": "1VsqP0-ByDOf8OLBE-BS5sZYvdvILfUp84BPO4F5yJ_M",
                "sheet_name": "2.2 일자별 신청현황",
                "header_row": DEFAULT_HEADER_ROW
            }
        }
    },
}

# 컬럼명 매핑
COLUMN_MAPPING = {
    "date": "일자",
    "name": "신청자 이름",
    "channel": "유입 채널",
    "material": "유입 소재 및 키워드",
    "campaign": "캠페인 구분",
    "age": "연령대",
    "document_pass": "서류 합격",
    "interview_pass": "인터뷰 합격",
    "final_admission": "최종 입학",
    "dropout": "수강포기",
    "dropout_reason": "사유",
    "transfer": "타 과정으로 이관",
    "notes": "비고",
}

# 사용할 컬럼들 (비고까지만)
REQUIRED_COLUMNS = [
    "그룹 미팅일 기준",
    "일자",
    "신청자 이름",
    "유입 채널",
    "유입 소재 및 키워드",
    "캠페인 구분",
    "연령대",
    "지원서 검토 완료",
    "서류 합격",
    "인터뷰 합격",
    "최종 입학",
    "수강료 결제",
    "수강포기",
    "사유",
    "타 과정으로 이관",
    "비고"
]

# 퍼널 컬럼들
FUNNEL_COLS = [
    "지원서 검토 완료",
    "서류 합격",
    "인터뷰 합격",
    "최종 입학",
    "수강료 결제"
]

FUNNEL_LABELS = [
    "지원자",
    "지원서검토완료",
    "서류합격",
    "인터뷰합격",
    "최종입학",
    "수강료결제"
]

# BigQuery 과정 코드 → config.py 과정ID 매핑
COURSE_MAPPING = {
    "RESEARCH": "ai_researcher",
    "EDATA": "data_analysis",
    "EGIGAE": "planning_dev",
    "AI-DATA": "ai_data_intel",
    "AI-AGENT": "ai_agent",
    "PRIVATE-AI": "private_ai",
}

# 미매핑 과정 코드 (시트가 아직 없거나 준비 중)
UNMAPPED_COURSES = {
    "ELLM": "미래언어모델(미매핑)",
}

# ===================================================================
# 운영 설정 (아래 값은 가정값입니다. 운영팀 확인 후 수정하세요)
# ===================================================================

# 과정·기수별 목표·기간·예산. 키는 (과정ID, 기수). 값이 없는 항목은 None(미설정)으로 두고,
# 미설정 항목은 화면에 '미설정'으로 표시하며 해당 계산을 건너뜁니다.
# target_kind: "지원" | "최종합격" | "등록" (목표가 무엇을 뜻하는지)
DEFAULT_COHORT_SETTING = {
    "target_kind": "지원",
    "target_count": None,      # 목표 인원 (명)
    "recruit_start": None,     # 모집 시작일 (YYYY-MM-DD)
    "recruit_end": None,       # 모집 마감일 (YYYY-MM-DD). 비워 두면 2.1 시트 최하단 일자를 씀
    "budget": None,            # 마케팅 예산 (원, 부가세·수수료 포함 기준)
}
# 예시: {("ai_agent", 2): {"target_kind": "지원", "target_count": 300, "recruit_end": "2026-08-20", "budget": 50_000_000}}
# 목표 기준은 '최종합격' 인원입니다 (수강료 열이 없는 과정이 많아 등록 대신 최종 합격으로 집계). 모집 기간·예산은 확인 후 입력하세요.
COHORT_SETTINGS = {
    ("ai_agent", 4): {"target_kind": "최종합격", "target_count": 30, "budget": 40_000_000},
    ("ai_data_intel", 3): {"target_kind": "최종합격", "target_count": 20, "budget": 40_000_000},
    ("ai_researcher", 20): {"target_kind": "최종합격", "target_count": 15, "budget": 40_000_000},
    ("private_ai", 2): {"target_kind": "최종합격", "target_count": 20, "budget": 40_000_000},   # 'LLM 엔지니어 2기'로 가정한 프라이빗AI 2기
    ("data_analysis", 10): {"target_kind": "최종합격", "target_count": 45, "budget": 10_000_000},
}

# 현재 모집 중인 (과정ID, 기수). 대시보드의 과정·기수 선택과 과정 비교 표는 이 목록만 보여 줍니다.
RECRUITING_COHORTS = [
    ("ai_agent", 4),
    ("ai_data_intel", 3),
    ("ai_researcher", 20),
    ("private_ai", 2),
    ("data_analysis", 10),
]

# 광고비 부가세·수수료 포함 여부 (2.1 시트 비용 열 기준). 현재 대행사 raw의 'VAT포함, 마크업포함' 금액을 사용.
AD_COST_INCLUDES_VAT_AND_FEE = True

# 주 시작 요일 (datetime.weekday 기준, 0=월요일). 주차별 비교는 월~일 기준.
WEEK_START_WEEKDAY = 0

# 인사이트·알림 기준값 (초기값은 가정이며 운영 중 조정)
MIN_COST_FOR_CPA = 100_000        # 이 금액(원) 미만 집행은 CPA 판단에서 제외
MIN_SAMPLE_FOR_INSIGHT = 10       # 지원 표본이 이 값 미만이면 비율 기반 인사이트를 내지 않음
MIN_DAILY_APPLICANTS_STABLE = 5   # 일 지원 수가 이 값 미만이면 변동성이 크다고 표시
CPA_WORSE_RATIO = 1.3             # 직전 기간 대비 CPA 배율이 이 값 이상이면 '악화' 점검 대상
CPA_BETTER_RATIO = 0.7            # 직전 기간 대비 CPA 배율이 이 값 이하이면 '개선'
COST_UP_RATIO = 1.2               # 비용 증가율이 이 값 이상이고
APPLICANT_DOWN_RATIO = 0.8        # 지원 수 감소율이 이 값 이하이면 '비용↑ 지원↓'
REASON_SHARE_ALERT = 0.4          # 한 유입 구분에서 특정 사유 비중이 이 값 이상이면 주목
BUDGET_PACE_GAP_PT = 15.0         # 예산 소진율이 기간 경과율보다 이 값(%p) 이상 높으면 주목
MISSING_CHANNEL_ALERT = 0.1       # 유입 경로 누락 비율이 이 값 이상이면 데이터 품질 경고
IN_PROGRESS_ALERT = 0.5           # 진행 중 비율이 이 값 이상이면 품질 판단 한계 표시
LANDING_DROP_PT = 5.0             # 지원서 랜딩→제출 전환율 하락폭(%p) 기준

# 마케팅 액션 로그 (Google Sheet 탭). 시트를 만든 뒤 스프레드시트 ID를 입력하세요.
ACTION_LOG_SHEET_ID = ""
ACTION_LOG_SHEET_NAME = "마케팅 액션 로그"

# 2.2 시트 '유입 채널' 원문 -> 매체 그룹. 여기 없는 값은 '미분류'로 집계됩니다.
# '네이버 브검'(네이버 브랜드검색 광고)은 네이버 SA와 분리한 별도 그룹입니다.
CHANNEL_GROUP_MAP = {
    "메타": "메타",
    "구글 DA": "구글 DA",
    "구글 SA": "구글 SA",
    "구글 검색": "구글 검색(오가닉)",
    "네이버 SA": "네이버 SA",
    "네이버 검색": "네이버 검색(오가닉)",
    "네이버 브검": "네이버 브검",
    "카카오 DA": "카카오 DA",
    "ChatGPT DA": "ChatGPT DA",
    "기타(유가)": "기타 유료",
    "직접 지원": "직접 지원",
    "모두/광고레터": "자사·커뮤니티",
    "모두연 SNS": "자사·커뮤니티",
    "모두연 유튜브": "자사·커뮤니티",
    "모두연 배너": "자사·커뮤니티",
    "커뮤니티/버티컬": "자사·커뮤니티",
    "카카오 플러스친구": "자사·커뮤니티",
    "마수동 문자": "자사·커뮤니티",
    "오프라인(포스터, 전단 등)": "자사·커뮤니티",
    "HRD Net": "기타 자연",
    "LLM(GPT, 퍼플렉시티 등)": "기타 자연",
    "사전신청": "기타 자연",
    "타 과정에서 이관": "이관",
    "지난 기수에서 이관": "이관",
    "이전기수에서 이관": "이관",
    "기타(유입경로 확인X)": "미분류",
}

# '구글 검색(오가닉)'·'네이버 검색(오가닉)'은 검색엔진에서 들어온 자연 유입이라 유료 그룹이 아닙니다.
# 유료 매체 그룹. 이 중 2.1 광고 블록과 1:1로 맞는 그룹만 '유료 매체 CPA' 분모·분자에 씁니다.
# '네이버 브검'은 유료 유입이지만 2.1에 별도 광고비 블록이 없어 CPA 계산에서는 제외됩니다.
PAID_CHANNEL_GROUPS = ["메타", "구글 DA", "구글 SA", "네이버 SA", "네이버 브검", "카카오 DA", "ChatGPT DA", "기타 유료"]
MATCHED_AD_GROUPS = ["메타", "구글 DA", "구글 SA", "네이버 SA", "카카오 DA", "ChatGPT DA"]

