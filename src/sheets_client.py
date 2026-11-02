"""Google Sheets API 연동"""

import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import os
import json

def get_sheets_client():
    """Google Sheets 클라이언트 생성 (Secrets 또는 환경변수 사용)"""
    try:
        # 먼저 Streamlit Secrets 시도
        if "gcp_service_account" in st.secrets:
            service_account_info = st.secrets["gcp_service_account"]
        # GCP_SERVICE_ACCOUNT_JSON 환경변수 시도 (JSON 문자열)
        elif os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
            service_account_info = json.loads(os.getenv("GCP_SERVICE_ACCOUNT_JSON"))
        else:
            st.error("Google Sheets 크레덴셜을 찾을 수 없습니다. Secrets 또는 환경변수를 확인해주세요.")
            return None
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Google Sheets 클라이언트 연결 실패: {e}")
        return None

def get_sheet_data(sheet_id: str, sheet_name: str, header_row: int = 4):
    """특정 스프레드시트의 시트 데이터 가져오기

    Args:
        sheet_id: 구글 스프레드시트 ID
        sheet_name: 시트 이름
        header_row: 헤더 행 번호 (1-based, 기본값 4행)
    """
    try:
        client = get_sheets_client()
        if client is None:
            return None

        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        # 모든 데이터 가져오기 (raw)
        all_values = worksheet.get_all_values()

        if not all_values or len(all_values) < header_row:
            return None

        # 헤더 행 (header_row는 1-based이므로 인덱스는 -1)
        header_idx = header_row - 1
        headers = all_values[header_idx]

        # "비고" 컬럼까지만 포함 (그 이후는 제외)
        cutoff_idx = len(headers)
        for i, h in enumerate(headers):
            if h.strip() == "비고":
                cutoff_idx = i + 1
                break

        headers = headers[:cutoff_idx]
        headers_with_idx = [(i, h) for i, h in enumerate(headers)]

        # 데이터 행 처리 (헤더 행 다음부터)
        data = []
        for row in all_values[header_idx + 1:]:
            # cutoff_idx까지만 처리
            row = row[:cutoff_idx]

            # 완전히 빈 행은 스킵
            if not any(cell.strip() for cell in row):
                continue

            row_dict = {}
            for idx, header in headers_with_idx:
                if header.strip():  # 헤더가 비어있지 않을 때만
                    value = row[idx] if idx < len(row) else ""
                    row_dict[header] = value

            # 최소 하나 이상의 데이터가 있는 행만 추가
            if any(value.strip() for value in row_dict.values()):
                data.append(row_dict)

        return data
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"시트 '{sheet_name}'를 찾을 수 없습니다. 시트명을 확인해주세요.")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"스프레드시트 ID '{sheet_id}'를 찾을 수 없습니다. 권한을 확인해주세요.")
        return None
    except Exception as e:
        st.error(f"데이터 조회 실패: {e}")
        return None


def get_ad_sheet_date_range(sheet_id: str, sheet_name: str = "2.1 일자별 유입현황"):
    """2.1 시트 B열(일자)의 첫 날짜와 최하단 날짜를 'YYYY-MM-DD' 문자열로 반환합니다.

    조회 기간의 최소·최대와 모집 마감일 기본값으로 쓰입니다.
    날짜 셀이 하나도 없거나 읽기에 실패하면 (None, None)을 반환합니다.

    Args:
        sheet_id: 과정·기수 스프레드시트 ID
        sheet_name: 광고 유입 시트 이름 (기본값: 2.1 일자별 유입현황)

    Returns:
        (첫 날짜, 마지막 날짜) 문자열 튜플
    """
    from datetime import date, timedelta

    try:
        client = get_sheets_client()
        if client is None:
            return None, None
        worksheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        rows = worksheet.get_all_values(value_render_option="UNFORMATTED_VALUE")
        days = []
        for row in rows[4:]:
            cell = str(row[1]).strip() if len(row) > 1 else ""
            if cell.replace(".", "", 1).isdigit():
                days.append(date(1899, 12, 30) + timedelta(days=int(float(cell))))
        if not days:
            return None, None
        return days[0].isoformat(), days[-1].isoformat()
    except Exception as error:  # 날짜 범위는 부가 정보이므로 실패해도 화면은 계속 동작
        st.warning(f"2.1 시트 날짜 범위를 읽지 못했습니다: {error}")
        return None, None
