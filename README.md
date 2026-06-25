# 모두의연구소 K-Digital Training 마케팅 대시보드

Google Sheets에 저장된 과정별 모집 현황 데이터를 시각화하는 Streamlit 대시보드입니다.

## 📊 기능

- **종합 현황**: 지원자, 최종입학, 수강포기 등 주요 지표 요약
- **모집 퍼널**: 가서류합격 → 최종입학까지의 인원 흐름 시각화
- **유입 채널 분석**: 매체별 지원자 수 및 입학 전환율
- **일자별 추이**: 누적 지원자 수 추이 그래프
- **수강포기 분석**: 포기 사유별 인원 분석

## 🚀 빠른 시작

### 1. 환경 설정 (Windows)

```bash
# PowerShell에서 실행

# 1) Python 3.9+ 설치 확인
python --version

# 2) 프로젝트 디렉토리로 이동
cd C:\Users\Admin\workspace\modulabs

# 3) 가상 환경 생성 (선택사항)
python -m venv venv
venv\Scripts\activate

# 4) 필수 패키지 설치
pip install -r requirements.txt
```

### 2. Streamlit 실행

```bash
streamlit run app.py
```

브라우저에서 자동으로 열립니다: `http://localhost:8501`

## ⚙️ 초기 설정

### GCP 서비스 계정 권한 확인

1. **클라이언트 이메일**: `marketing-ax-agent@modulabs-ga-workspace.iam.gserviceaccount.com`
2. **각 스프레드시트에 "뷰어" 권한으로 공유되어 있는지 확인**
3. **secrets.toml이 정상 위치에 있는지 확인**: `.streamlit/secrets.toml`

## 📋 데이터 구조

각 스프레드시트의 "2.2 일자별 신청현황" 시트는 다음 컬럼을 가져야 합니다:

| 컬럼명 | 설명 |
|--------|------|
| 일자 | 지원 날짜 |
| 신청자 이름 | 지원자 이름 |
| 유입 채널 | 매체 (메타, 직접지원, 기타 등) |
| 가서류 합격 | O/X/빈칸 |
| 서류 합격 | O/X/빈칸 |
| 인터뷰 합격 | O/X/빈칸 |
| 최종 입학 | O/X/빈칸 |
| 수강료 결제 | O/X/빈칸 |
| 수강포기 | O/X/빈칙 |
| 사유 | 포기 사유 |

## 🔧 과정 추가 방법

`src/config.py`의 `COURSES` 딕셔너리에 새로운 과정 추가:

```python
"과정_id": {
    "name": "과정명",
    "type": "unemployed",  # 또는 "employed"
    "cohorts": {
        1: {
            "sheet_id": "스프레드시트 ID",
            "sheet_name": "2.2 일자별 신청현황"
        }
    }
}
```

**스프레드시트 ID 추출 방법:**
```
https://docs.google.com/spreadsheets/d/{sheet_id}/edit
```

## 📁 프로젝트 구조

```
modulabs/
├── app.py                    # Streamlit 메인 앱
├── src/
│   ├── __init__.py
│   ├── config.py             # 과정 목록, 스프레드시트 ID 설정
│   ├── sheets_client.py      # Google Sheets API 연동
│   ├── data_loader.py        # 데이터 파싱 및 집계
│   └── charts.py             # Plotly 차트 함수
├── .streamlit/
│   └── secrets.toml          # GCP 서비스 계정 키 (gitignore)
├── requirements.txt
├── .gitignore
└── README.md
```

## 🌐 Streamlit Community Cloud 배포

### 1. GitHub 저장소 생성

```bash
git init
git add .
git commit -m "Initial commit: Marketing Dashboard"
git branch -M main
git remote add origin <your-github-url>
git push -u origin main
```

### 2. Streamlit Cloud 연결

1. https://streamlit.io/cloud 접속
2. "New app" → GitHub 저장소 선택
3. 리포지토리, 브랜치, 메인 파일 경로 입력
4. "Deploy" 클릭

### 3. Secrets 설정

Streamlit Cloud 앱 설정 → Secrets → 다음 내용 붙여넣기:

```toml
[gcp_service_account]
type = "service_account"
project_id = "modulabs-ga-workspace"
private_key_id = "..."
# ... JSON의 모든 내용 붙여넣기
```

## ❓ 문제 해결

### "권한 없음" 오류
```
gspread.exceptions.SpreadsheetNotFound 또는 
gspread.exceptions.WorksheetNotFound
```

**해결:**
1. 스프레드시트가 서비스 계정(`marketing-ax-agent@...`)에 공유되어 있는지 확인
2. 권한이 "뷰어"로 설정되어 있는지 확인
3. secrets.toml에 올바른 클라이언트 키가 있는지 확인

### 시트 이름 오류
- `src/config.py`의 `sheet_name` 정확성 확인
- Google Sheets에서 실제 시트명 확인 (대소문자, 공백 포함)

### 데이터가 안 로드됨
- 인터넷 연결 확인
- GCP API 활성화 확인
- 스프레드시트 URL 정확성 확인

## 📞 지원

문제가 발생하면:
1. 로그 메시지 확인 (브라우저 콘솔 또는 터미널)
2. `.streamlit/secrets.toml` 설정 다시 확인
3. 스프레드시트 권한 확인

---

**생성일**: 2026-06-23  
**대시보드**: 모두의연구소 K-Digital Training 마케팅 대시보드  
**기술**: Streamlit + Google Sheets API + Plotly
