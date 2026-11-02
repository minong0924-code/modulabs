"""2.1 일자별 유입현황 시트를 BigQuery 한 테이블로 내보냅니다 (대시보드 저장 층).

사용: python scripts/export_inflow_to_bq.py [--dry-run]
  - 모든 과정·기수의 2.1 시트를 읽어 긴 형식(일자 × 매체 × 지표)으로 펼칩니다.
  - 테이블은 매번 전체를 덮어씁니다(WRITE_TRUNCATE). 데이터가 작아 전체 갱신이 가장 단순합니다.
  - 카카오 DA 계열(모먼트·비즈보드)은 같은 블록으로 합산합니다.
"""

import datetime as dt
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import gspread  # noqa: E402
from google.cloud import bigquery  # noqa: E402

import sync_ga_channels as s  # noqa: E402  (자격증명·BQ 프로젝트 설정 재사용)
from src.config import COURSES  # noqa: E402

TABLE_ID = f"{s.BQ_PROJECT}.Modulabs_internal_DB.dash_daily_inflow"
SHEET_NAME = "2.1 일자별 유입현황"
# 시트 지표 이름 -> 저장 지표 이름 (클릭율·전환율 등 계산 열은 제외)
METRICS = ["비용", "노출", "클릭", "페이지뷰", "CTA 클릭", "지원서 랜딩", "지원서 제출"]
SCHEMA = [
    bigquery.SchemaField("snapshot_at", "TIMESTAMP"),
    bigquery.SchemaField("course_id", "STRING"),
    bigquery.SchemaField("course_name", "STRING"),
    bigquery.SchemaField("semester", "INTEGER"),
    bigquery.SchemaField("date", "DATE"),
    bigquery.SchemaField("block", "STRING"),
    bigquery.SchemaField("metric", "STRING"),
    bigquery.SchemaField("value", "FLOAT"),
]


# 매체 합계 행 등 집계에서 빼야 하는 블록 (합계를 또 더하면 중복 집계됨)
SKIP_BLOCKS = {"페이드(총합)"}


def canon_block(name):
    """2.1 블록 이름을 표준 매체 이름으로 바꿉니다.

    Args:
        name: 시트 행 2에 적힌 블록 이름 (예: "카카오 DA(9/23~)", "구글SA")

    Returns:
        표준 매체 이름 (예: "카카오 DA")
    """
    name = name.strip()
    compact = name.replace(" ", "")
    if compact.startswith("카카오"):
        return "카카오 DA"
    if compact.startswith(("타게팅", "타겟팅")):
        return "타게팅게이츠"
    if compact == "구글SA":
        return "구글 SA"
    if compact.startswith("네이버GFA"):
        return "기타"  # 네이버 디스플레이(GFA)는 SA가 아니므로 기타로 묶음
    return name


def parse_sheet(grid):
    """2.1 시트 값을 (일자, 매체, 지표) -> 값 dict로 펼칩니다.

    Args:
        grid: get_all_values(UNFORMATTED_VALUE) 결과 (행 2 블록, 행 4 지표, 5행부터 데이터, B열 날짜 시리얼)

    Returns:
        {(date, block, metric): value} dict. 빈 칸은 제외합니다.
    """
    header_block, header_metric = grid[1], grid[3]
    starts = [(i, str(v).strip()) for i, v in enumerate(header_block) if str(v).strip() and str(v).strip() != "일자"]
    blocks = []
    for idx, (c0, name) in enumerate(starts):
        if name in SKIP_BLOCKS:
            continue
        c1 = starts[idx + 1][0] if idx + 1 < len(starts) else len(header_metric)
        blocks.append((canon_block(name), {str(header_metric[j]).strip(): j for j in range(c0, c1) if str(header_metric[j]).strip()}))

    values = defaultdict(float)
    for row in grid[4:]:
        if len(row) < 2 or not re.fullmatch(r"\d+(\.\d+)?", str(row[1]).strip()):
            continue
        day = dt.date(1899, 12, 30) + dt.timedelta(days=int(float(row[1])))
        for block, cols in blocks:
            for metric in METRICS:
                j = cols.get(metric)
                if j is None or j >= len(row):
                    continue
                cell = str(row[j]).strip().replace(",", "")
                if cell in ("", "-"):
                    continue
                try:
                    values[(day, block, metric)] += float(cell)
                except ValueError:
                    continue
    return dict(values)


def collect_rows(gs, snapshot_at):
    """모든 과정·기수의 2.1 시트를 읽어 BigQuery 행 목록을 만듭니다.

    Args:
        gs: gspread 클라이언트
        snapshot_at: 적재 시각 ISO 문자열

    Returns:
        BigQuery 적재용 dict 목록
    """
    rows = []
    for course_id, course in COURSES.items():
        for semester, cohort in course["cohorts"].items():
            try:
                sheet = gs.open_by_key(cohort["sheet_id"]).worksheet(SHEET_NAME)
                grid = [[str(c) for c in r] for r in sheet.get_all_values(value_render_option="UNFORMATTED_VALUE")]
                time.sleep(2)
            except Exception as error:  # 한 기수 실패가 전체를 막지 않도록 건너뜁니다
                print(f"{course_id} {semester}기 건너뜀: {type(error).__name__} {str(error)[:120]}", flush=True)
                continue
            values = parse_sheet(grid)
            for (day, block, metric), value in values.items():
                rows.append({
                    "snapshot_at": snapshot_at,
                    "course_id": course_id,
                    "course_name": course["name"],
                    "semester": semester,
                    "date": day.isoformat(),
                    "block": block,
                    "metric": metric,
                    "value": value,
                })
            print(f"{course_id} {semester}기: {len(values)}개 값", flush=True)
    return rows


def main():
    """CLI 진입점: 2.1 시트를 읽어 BigQuery 테이블을 갱신합니다."""
    dry_run = "--dry-run" in sys.argv
    snapshot_at = dt.datetime.now(dt.timezone.utc).isoformat()
    gs = gspread.authorize(s.get_credentials(s.SHEETS_SCOPES))
    rows = collect_rows(gs, snapshot_at)
    print(f"총 {len(rows)}행 수집", flush=True)
    if dry_run or not rows:
        print("드라이런 또는 데이터 없음: BigQuery에 쓰지 않습니다.", flush=True)
        return
    bq = bigquery.Client(project=s.BQ_PROJECT, credentials=s.get_credentials(s.BQ_SCOPES))
    job_config = bigquery.LoadJobConfig(schema=SCHEMA, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bq.load_table_from_json(rows, TABLE_ID, job_config=job_config).result()
    print(f"적재 완료: {TABLE_ID} ({len(rows)}행)", flush=True)


if __name__ == "__main__":
    main()
