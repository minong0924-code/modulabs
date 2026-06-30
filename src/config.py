"""과정별 스프레드시트 설정"""

# 기본 헤더 행 위치 (1-based)
DEFAULT_HEADER_ROW = 4

COURSES = {
    # 실업자 과정 (5개)
    "ai_data_intel": {
        "name": "AI데이터 인텔리전스",
        "type": "unemployed",
        "cohorts": {
            1: {
                "sheet_id": "12MZ1OnGKzKnH0dBwKYScAtVycJXcBXkVdA55kzqN7Ag",
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
            }
        }
    },
    "ai_engineer": {
        "name": "AI엔지니어",
        "type": "unemployed",
        "cohorts": {
            1: {
                "sheet_id": "",
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
