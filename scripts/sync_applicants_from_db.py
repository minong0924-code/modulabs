"""내부 PostgreSQL 지원서 데이터를 BigQuery KDT_Daily_Apply에 추가하는 스크립트.

흐름:
  1. .env의 PG_* 설정으로 PostgreSQL에 읽기 전용 접속
  2. DBeaver에서 쓰던 추출 쿼리와 같은 조건으로 지원 데이터 조회
  3. BigQuery에 이미 있는 apply_id는 제외하고 새 신청만 추가 (기존 행은 수정하지 않음)

기본값은 미리보기(추가하지 않음)입니다. --apply 를 붙여야 실제로 추가합니다.
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
import tomllib
from pathlib import Path

import psycopg
from google.cloud import bigquery
from google.oauth2.service_account import Credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_applicants_from_db")

BQ_PROJECT = "modulabs-ga-workspace"
BQ_SCOPES = ["https://www.googleapis.com/auth/bigquery"]
ENV_PATH = PROJECT_ROOT / ".env"
SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"
TABLE_ID = f"{BQ_PROJECT}.Modulabs_internal_DB.KDT_Daily_Apply"

# DBeaver에서 쓰던 추출 쿼리와 동일한 조건 (한국 시간 기준 오늘 신청분 제외)
EXTRACT_SQL = """
SELECT
    p.submitted_at::TIMESTAMP(0) AS submitted_at,
    p.id AS apply_id,
    m.id AS member_id,
    m.uuid AS uuid,
    p.name,
    p.birth AS applicant_birth,
    p.email,
    p.course,
    p.online_semester AS semester
FROM public.apply_applicationform AS p
LEFT JOIN membership.auth_member AS m
    ON p.email = m.email
WHERE p.name IS NOT NULL
  AND p.name NOT LIKE '%테스트%'
  AND p.name NOT LIKE 'TEST'
  AND p.name NOT LIKE 'test'
  AND p.email NOT LIKE '%modulabs.co.kr%'
  AND p.birth IS NOT NULL
  AND p.submitted_at >= '2026-01-01'
  AND (p.submitted_at AT TIME ZONE 'Asia/Seoul')::date < (now() AT TIME ZONE 'Asia/Seoul')::date
  AND p.course IN ('ENGR','RESEARCH','EDATA','ELLM','EGIGAE','AI-DATA','AI-AGENT','PRIVATE-AI')
ORDER BY p.submitted_at ASC
"""


def load_env(path):
    """.env 파일을 읽어 dict로 반환합니다.

    Args:
        path: .env 파일 경로

    Returns:
        {키: 값} dict
    """
    env = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def load_gcp_info():
    """서비스 계정 정보를 환경변수 또는 .streamlit/secrets.toml에서 읽습니다.

    Returns:
        서비스 계정 정보 dict
    """
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if raw:
        return json.loads(raw)
    secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    return dict(secrets["gcp_service_account"])


def fetch_from_db(env):
    """PostgreSQL에서 추출 쿼리를 실행해 행 목록을 반환합니다.

    Args:
        env: PG_* 접속 정보 dict

    Returns:
        행마다 BigQuery 적재용 dict 목록 (apply_id 중복 제거)
    """
    rows = {}
    with psycopg.connect(
        host=env["PG_HOST"], port=int(env["PG_PORT"]), dbname=env["PG_DATABASE"],
        user=env["PG_USER"], password=env["PG_PASSWORD"], connect_timeout=15,
    ) as conn:
        with conn.cursor() as cur:
            # 기존 BigQuery 데이터는 한국 시각으로 저장되어 있으므로 접속 시간대를 한국 시간으로 맞춤
            cur.execute("SET TIME ZONE 'Asia/Seoul'")
            cur.execute(EXTRACT_SQL)
            columns = [c.name for c in cur.description]
            for values in cur.fetchall():
                row = dict(zip(columns, values))
                if row["apply_id"] in rows:
                    # 같은 이메일이 여러 회원과 연결되면 첫 번째 것만 사용
                    continue
                rows[row["apply_id"]] = {
                    # 접속 시간대를 한국 시간으로 설정했으므로 한국 시각(시간대 표기 없음)으로 저장 (기존 데이터와 동일 방식)
                    "submitted_at": row["submitted_at"].replace(tzinfo=None).isoformat(sep=" "),
                    "apply_id": row["apply_id"],
                    "member_id": row["member_id"],
                    "uuid": row["uuid"],
                    "name": row["name"],
                    "applicant_birth": row["applicant_birth"].isoformat() if row["applicant_birth"] else None,
                    "email": row["email"],
                    "course": row["course"],
                    "semester": row["semester"],
                }
    logger.info("DB 추출 완료: %d건", len(rows))
    return list(rows.values())


def fetch_existing_apply_ids(bq_client):
    """BigQuery에 이미 있는 apply_id 집합을 반환합니다.

    Args:
        bq_client: bigquery.Client 객체

    Returns:
        apply_id 집합
    """
    query = f"SELECT apply_id FROM `{TABLE_ID}`"
    return {row["apply_id"] for row in bq_client.query(query).result()}


def main():
    """CLI 진입점: DB의 새 신청을 BigQuery에 추가합니다 (--apply 없으면 미리보기)."""
    parser = argparse.ArgumentParser(description="DB 지원서 데이터를 BigQuery에 추가")
    parser.add_argument("--apply", action="store_true", help="실제로 BigQuery에 추가 (없으면 미리보기)")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    credentials = Credentials.from_service_account_info(load_gcp_info(), scopes=BQ_SCOPES)
    bq_client = bigquery.Client(project=BQ_PROJECT, credentials=credentials)

    db_rows = fetch_from_db(env)
    existing = fetch_existing_apply_ids(bq_client)
    new_rows = [r for r in db_rows if r["apply_id"] not in existing]
    logger.info("BigQuery 기존 %d건, 새로 추가할 신청 %d건", len(existing), len(new_rows))

    if not args.apply:
        logger.info("미리보기 모드입니다. 실제로 추가하려면 --apply 를 붙여 주세요.")
        return
    if not new_rows:
        logger.info("추가할 신규 신청이 없습니다.")
        return

    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    job = bq_client.load_table_from_json(new_rows, TABLE_ID, job_config=job_config)
    job.result()
    logger.info("BigQuery 추가 완료: %d건", len(new_rows))


if __name__ == "__main__":
    main()
