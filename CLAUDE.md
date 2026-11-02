# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

모두의연구소 K-Digital Training 7개 과정의 모집/성과를 분석하는 Streamlit 대시보드입니다. Google Sheets에 저장된 과정별 데이터를 수집하여 퍼널, 채널, 주차별 분석 등을 시각화합니다.

## 개발 환경 및 명령어

### 실행
```bash
streamlit run app.py
```
브라우저에서 `http://localhost:8501`에 자동으로 열립니다.

### 설치 및 의존성
```bash
pip install -r requirements.txt
```

### 린트 및 타입 체크
현재 린팅 설정 없음. 추후 필요시 `black`, `isort`, `mypy` 추가.

## 아키텍처

### 데이터 흐름
```
Google Sheets API (sheets_client.py)
         ↓
데이터 파싱 및 집계 (data_loader.py)
         ↓
차트/테이블 생성 (charts.py)
         ↓
Streamlit UI (app.py)
```

### 주요 컴포넌트

1. **`src/config.py`** - 과정 및 기수 설정
   - `COURSES` 딕셔너리: 과정별 Google Sheet ID 및 기수 정보
   - 새 과정 추가 시 여기에 등록 (과정 타입: "unemployed"/"employed")
   - 각 기수마다 독립적인 Sheet ID 관리

2. **`src/sheets_client.py`** - Google Sheets API 연동
   - `get_sheets_client()`: Streamlit Secrets 또는 `GCP_SERVICE_ACCOUNT_JSON` 환경변수에서 GCP 자격증명 로드
   - `get_sheet_data()`: 특정 스프레드시트의 데이터 수집 (header_row 기본값 4행)
   - 읽기 전용 스코프 사용

3. **`src/data_loader.py`** - 데이터 파싱 및 퍼널 집계
   - `load_applicants()`: DataFrame으로 변환하고 필요 컬럼만 선택
   - 다양한 집계 함수들 (get_funnel_counts, get_channel_counts, get_weekly_funnel_stats 등)
   - 각 함수는 특정 분석 관점의 DataFrame 또는 dict 반환

4. **`src/charts.py`** - Plotly 차트 함수
   - 모든 함수는 `plotly.graph_objects.Figure` 반환
   - 차트명에 생성 함수명이 일치하도록 명확하게 구성

5. **`app.py`** - Streamlit UI (메인 진입점)
   - 3개 탭: 종합 현황, 상세 분석, 주차별 분석
   - 사이드바: 과정/기수 선택 및 데이터 새로고침
   - 데이터 로딩에 `@st.cache_data` (TTL 5분) 적용

### 데이터 스키마
모든 과정은 "2.2 일자별 신청현황" 시트에서 다음 컬럼을 사용합니다 (header_row=4):
- 일자, 신청자 이름, 유입 채널, 유입 소재 및 키워드, 캠페인 구분
- 지원서 검토 완료, 서류 합격, 인터뷰 합격, 최종 입학, 수강료 결제
- 수강포기, 사유, 타 과정으로 이관, 비고

## 새로운 기능 추가 시 가이드

### 새 과정/기수 추가
1. `src/config.py`의 `COURSES[과정_id]["cohorts"]`에 새 기수 항목 추가
2. Sheet ID는 URL의 `/d/` 와 `/edit` 사이의 문자열

### 새로운 분석 탭 추가
1. 필요한 데이터 집계 함수를 `src/data_loader.py`에 추가
2. 시각화 함수를 `src/charts.py`에 추가
3. `app.py`에 새 탭을 `st.tabs()`에 추가하고 데이터/차트 통합

### 데이터 파싱 로직 수정
- `src/data_loader.py`에서 컬럼명 처리 시 `.str.strip()` 사용 (Google Sheets 공백 제거)
- 빈 DataFrame 처리: 함수 시작에 `if df.empty:` 체크 추가

## Streamlit Cloud 배포

자동 배포 설정 완료됨. GitHub main 브랜치에 push하면 Streamlit Cloud에서 자동으로 재배포됩니다.
- Secrets: GCP 서비스 계정 키가 Streamlit Cloud 대시보드 → Secrets에 설정됨

## 주의사항

- **데이터 로딩**: Google Sheets API는 네트워크 지연 가능. 캐싱(TTL 5분)은 성능 개선용이며, 사이드바 "데이터 새로고침"으로 수동 갱신 가능
- **컬럼명**: Google Sheets에서 가져온 컬럼명은 앞뒤 공백이 있을 수 있으므로 반드시 `.str.strip()` 처리
- **빈 시트/데이터**: 모든 데이터 함수는 empty DataFrame 체크 후 안전한 기본값 반환
- **기수 선택**: 각 과정마다 기수가 다르므로, 기수 선택 후 해당 Sheet ID를 로드하는 로직 확인
