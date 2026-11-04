"""2.1 일자별 유입현황 업데이트 (dry-run 기본). 사용: python update_2_1.py <과정ID> <기수> <시작일> <종료일> [--apply]"""
import re, sys, time, datetime as dt
from collections import defaultdict
sys.path.insert(0, r"C:\Users\Admin\workspace\mkt_dashboard\scripts")
sys.path.insert(0, r"C:\Users\Admin\workspace\mkt_dashboard")
import sync_ga_channels as s
import gspread
from google.cloud import bigquery
from gspread.utils import rowcol_to_a1
from src.config import COURSES

PATHS = {"ai_agent": ["/ai-agent"], "ai_data_intel": ["/ai-data"], "private_ai": ["/private-ai", "/llm"],
         "data_analysis": ["/edata"], "planning_dev": ["/egigae", "/vibecoding"], "ai_researcher": ["/airesearcher", "/research"]}
# 대행사 raw 캠페인 이름으로 과정 구분
RAW_KEYS = {"ai_agent": ["에이전트", "agent"], "ai_data_intel": ["인텔리전스", "intelligence"], "private_ai": ["프라이빗", "private"],
            "data_analysis": ["재직자(데이터)", "edata"], "planning_dev": ["재직자(기획개발)", "egigae"], "ai_researcher": ["리서처", "researcher", "airesea"]}
# 대행사 raw 캠페인유형 -> 2.1 매체 블록 (배율 포함)
RAW_MEDIA = {"메타": "메타", "구글 실적최대화": "구글 DA", "구글디멘드젠": "구글 DA", "구글 검색": "구글 SA", "네이버 검색": "네이버 SA", "카카오": "카카오 DA", "카카오(무상캐시)": "카카오 DA", "타겟팅게이츠": "타게팅게이츠", "챗지피티": "ChatGPT DA"}
GA_METRICS = ["페이지뷰", "CTA 클릭", "지원서 랜딩", "지원서 제출"]
MEDIA_METRICS = ["비용", "노출", "클릭"]
AGENCY = {"ai_researcher": "1dxIAJNq_RpJQGWJDsqpzpFZK6VcnhdNSeyR1A8A_vu4", "ai_agent": "1Z_7mnZTkFcrj5eHVeGu7LtqSTOB7696E0XxaRzaZVuQ", "ai_data_intel": "1Z_7mnZTkFcrj5eHVeGu7LtqSTOB7696E0XxaRzaZVuQ", "private_ai": "1Z_7mnZTkFcrj5eHVeGu7LtqSTOB7696E0XxaRzaZVuQ", "data_analysis": "1vYMBImjzZVWTsnjn9wJLUdpZWvra_OpAoFRIwTrdTwM", "planning_dev": "1vYMBImjzZVWTsnjn9wJLUdpZWvra_OpAoFRIwTrdTwM"}
EVENT = {"페이지뷰": "page_view", "CTA 클릭": "Apply_click_cta", "지원서 랜딩": "Apply_step1", "지원서 제출": "Apply_step2"}
# ChatGPT 광고 블록 (GA 소스 ChatGPT / da, 대행사 raw 매체 '챗지피티')
CHATGPT_BLOCK = "ChatGPT DA"
# 블록 한 개의 열 구성 (비용부터 지원서 제출까지, 전환율은 바로 앞 지표 대비)
BLOCK_HEADERS = ["비용", "노출", "클릭", "클릭율", "페이지뷰", "CTA 클릭", "전환율", "지원서 랜딩", "전환율", "지원서 제출", "전환율"]
# 페이드(총합) 블록이 더하는 지표 (클릭율·전환율은 합계에서 다시 계산)
PAID_SUM_METRICS = ["비용", "노출", "클릭", "페이지뷰", "CTA 클릭", "지원서 랜딩", "지원서 제출"]


def block_of(source, medium, campaign):
    """GA (source, medium, campaign) -> 2.1 블록 이름. 구글 검색은 PMAX·디멘드젠이 아닌 구글 광고, B2B는 제외."""
    c = (campaign or "").lower()
    if (source, medium) == ("google", "cpc"):
        if "pmax" in c or "dgen" in c: return "구글 DA"
        if "b2b" in c: return None
        return "구글 SA"
    if (source or "").lower() == "chatgpt" and (medium or "").lower() == "da": return CHATGPT_BLOCK
    if (source, medium) == ("naver", "cpc"): return "네이버 SA"
    if (source, medium) == ("kakao", "cpc"): return "카카오 DA"
    if (source, medium) == ("meta", "da"): return "메타"
    if (source, medium) == ("targetinggates", "da"): return "타게팅게이츠"
    if (source, medium) == ("tiktok", "da"): return "틱톡"
    return "오가닉"


def ga_counts(bq, course, start, end):
    paths = " OR ".join(f"REGEXP_EXTRACT(page_location, r'https?://[^/]+([^?#]*)') LIKE '{p}%'" for p in PATHS[course])
    sql = f"""
    SELECT DATE(TIMESTAMP_MICROS(event_timestamp), 'Asia/Seoul') AS d, event_name, user_pseudo_id,
      COALESCE(collected_traffic_source.manual_source, traffic_source.source) AS src,
      COALESCE(collected_traffic_source.manual_medium, traffic_source.medium) AS med,
      COALESCE(collected_traffic_source.manual_campaign_name, traffic_source.name, '(none)') AS camp,
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_location
    FROM `modulabs-ga-workspace.analytics_373566527.events_*`
    WHERE _TABLE_SUFFIX BETWEEN @s AND @e
    """
    sql = f"SELECT * FROM ({sql}) WHERE ({paths})"
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("s", "STRING", start.strftime("%Y%m%d")),
        bigquery.ScalarQueryParameter("e", "STRING", end.strftime("%Y%m%d"))]))
    out = defaultdict(set)
    for r in job.result():
        blk = block_of(r["src"], r["med"], r["camp"])
        if not blk: continue
        for metric, ev in EVENT.items():
            if r["event_name"] == ev:
                out[(r["d"], blk, metric)].add(r["user_pseudo_id"])
    return {k: len(v) for k, v in out.items()}


def parse_raw_date(text):
    """대행사 raw의 일자 문자열을 날짜로 바꿉니다. '2026-10-29'와 '2026. 10. 29' 두 형식을 모두 읽습니다.

    Args:
        text: raw 시트 A열 값

    Returns:
        datetime.date (형식이 맞지 않으면 None)
    """
    match = re.fullmatch(r"\s*(\d{4})\D+(\d{1,2})\D+(\d{1,2})\.?\s*", str(text))
    if not match:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def raw_media(course, start, end, gs):
    """대행사 raw에서 과정·날짜별 매체 비용·노출·클릭 집계.
    매체는 raw의 '매체' 열(23번), 비용은 '비용(VAT포함, 마크업포함)' 열(16번)을 그대로 씁니다."""
    num = lambda v: float(re.sub(r"[^\d.\-]", "", str(v)) or 0) if str(v).strip() not in ("", "-") else 0.0
    if course not in AGENCY: return {}
    time.sleep(3)
    raw = gs.open_by_key(AGENCY[course]).worksheet("raw").get_all_values()
    out = defaultdict(lambda: [0.0, 0.0, 0.0])
    keys = [k.lower() for k in RAW_KEYS[course]]
    for r in raw[1:]:
        if len(r) < 24 or not r[0][:4] == "2026": continue
        d = parse_raw_date(r[0])
        if d is None: continue
        if not (start <= d <= end): continue
        if not any(k in r[2].lower() for k in keys): continue
        blk = RAW_MEDIA.get(r[23].strip())
        if not blk: continue
        a = out[(d, blk)]
        a[0] += num(r[16]); a[1] += num(r[6]); a[2] += num(r[7])
    return out


def cohort_window(grid):
    """2.1 시트의 날짜 범위 (B열 날짜 시리얼 최소~최대)."""
    dates = []
    for row in grid[4:]:
        v = row[1] if len(row) > 1 else ""
        if re.fullmatch(r"\d+(\.\d+)?", str(v).strip()):
            dates.append(dt.date(1899, 12, 30) + dt.timedelta(days=int(float(v))))
    return (min(dates), max(dates)) if dates else None


def col_letter(index):
    """0-based 열 번호를 A1 표기 열 문자로 바꿉니다 (0 -> A, 26 -> AA).

    Args:
        index: 0-based 열 번호

    Returns:
        열 문자 문자열
    """
    text, n = "", index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        text = chr(65 + rem) + text
    return text


def ensure_chatgpt_block(ws, grid):
    """2.1 시트 맨 오른쪽에 ChatGPT DA 블록을 만들고 페이드(총합) 합계에 포함합니다. 이미 있으면 아무것도 하지 않습니다.

    블록 구성은 메타·구글 DA 블록과 같습니다(비용·노출·클릭·클릭율·페이지뷰·CTA·랜딩·제출, 전환율은 앞 지표 대비).
    데이터 행(5행부터)은 수식으로, 합계 행은 SUM으로 채웁니다. 비용·노출·클릭·GA 지표 값은 이후 run_cohort가 채웁니다.

    Args:
        ws: 2.1 일자별 유입현황 워크시트
        grid: FORMULA 모드로 읽은 시트 값 (행 리스트)

    Returns:
        새로 만들었으면 True
    """
    if CHATGPT_BLOCK in [str(v).strip() for v in grid[1]]:
        return False
    start = max(len(grid[1]), len(grid[3]))  # 현재 마지막 열 다음 (0-based)
    width = len(BLOCK_HEADERS)
    if ws.col_count < start + width:
        ws.add_cols(start + width - ws.col_count)
    col = lambda k: col_letter(start + k)
    last_row = len(grid)  # 합계 행 번호 (1-based)
    data_rows = [r for r in range(5, last_row) if re.fullmatch(r"\d+(\.\d+)?", str(grid[r - 1][1]).strip())]
    # 전환율 열은 (분자, 분모) 열 번호로 정의: 바로 앞 지표 대비
    conv = {6: (5, 4), 8: (7, 5), 10: (9, 7)}
    sum_cols = (0, 1, 2, 4, 5, 7, 9)

    updates = [
        {"range": f"{col(0)}2:{col(width - 1)}2", "values": [[CHATGPT_BLOCK] + [""] * (width - 1)]},
        {"range": f"{col(0)}3:{col(width - 1)}3", "values": [["매체", "", "", "", "GA 기준"] + [""] * (width - 5)]},
        {"range": f"{col(0)}4:{col(width - 1)}4", "values": [BLOCK_HEADERS]},
    ]
    for r in data_rows + [last_row]:
        values = [""] * width
        for k in sum_cols:
            values[k] = f"=SUM({col(k)}5:{col(k)}{last_row - 1})" if r == last_row else ""
        values[3] = f"=IFERROR({col(2)}{r}/{col(1)}{r},0)"
        for k, (num, den) in conv.items():
            values[k] = f"=IFERROR({col(num)}{r}/{col(den)}{r},0)"
        updates.append({"range": f"{col(0)}{r}:{col(width - 1)}{r}", "values": [values]})

    # 페이드(총합) 열의 합계 수식에 새 블록을 더합니다
    paid_start = grid[1].index("페이드(총합)") if "페이드(총합)" in [str(v).strip() for v in grid[1]] else None
    if paid_start is not None:
        for metric in PAID_SUM_METRICS:
            j = next((i for i in range(paid_start, len(grid[3])) if str(grid[3][i]).strip() == metric), None)
            if j is None:
                continue
            refs = re.findall(r"([A-Z]+)\d+", grid[4][j])  # 현재 수식의 열 목록 (예: =SUM(U5,AF5,AQ5,BB5))
            refs = [ref for ref in refs if ref != col(BLOCK_HEADERS.index(metric))]
            refs.append(col(BLOCK_HEADERS.index(metric)))
            for r in data_rows:
                updates.append({"range": f"{col_letter(j)}{r}",
                                "values": [[f"=SUM({','.join(f'{ref}{r}' for ref in refs)})"]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    return True


def run_cohort(cid, sem, start, end, gs, bq, apply):
    sh = gs.open_by_key(COURSES[cid]["cohorts"][sem]["sheet_id"])
    ws = sh.worksheet("2.1 일자별 유입현황")
    grid = [[str(c) for c in r] for r in ws.get_all_values(value_render_option="FORMULA")]
    time.sleep(3)
    if apply and ensure_chatgpt_block(ws, grid):
        print(f"{cid} {sem}기: {CHATGPT_BLOCK} 블록 추가", flush=True)
        time.sleep(3)
        grid = [[str(c) for c in r] for r in ws.get_all_values(value_render_option="FORMULA")]
    ga = ga_counts(bq, cid, start, end)
    media = raw_media(cid, start, end, gs)
    # 블록 시작 열 (행 2의 블록 이름) -> 행 4의 지표 이름으로 열 위치 찾기
    h2, h4 = grid[1], grid[3]
    starts = [(i, h2[i]) for i in range(len(h2)) if h2[i].strip() and h2[i].strip() != "일자"]
    cols = {}
    for idx, (c0, name) in enumerate(starts):
        c1 = starts[idx + 1][0] if idx + 1 < len(starts) else len(h4)
        cols[name.strip()] = {h4[j].strip(): j for j in range(c0, c1) if h4[j].strip()}
    KNOWN = {"오가닉", "메타", "구글 DA", "구글 SA", "네이버 SA", "카카오 DA", "타게팅게이츠", "틱톡", CHATGPT_BLOCK}
    def canon(name):
        if name.startswith("카카오"): return "카카오 DA"  # 카카오 모먼트·비즈보드 모두 카카오 DA
        if name.startswith("타게팅") or name.startswith("타겟팅"): return "타게팅게이츠"
        return name
    cols = {canon(k): v for k, v in cols.items()}
    updates, diffs = [], []
    media_blocks = {b for (_, b) in media}
    for r_no in range(5, len(grid) + 1):
        row = grid[r_no - 1]
        if len(row) < 2 or not row[1].strip(): continue
        serial = int(float(row[1])) if re.fullmatch(r"\d+(\.\d+)?", row[1].strip()) else None
        if serial is None: continue
        d = dt.date(1899, 12, 30) + dt.timedelta(days=serial)
        if not (start <= d <= end): continue
        for blk, names in cols.items():
            if blk not in KNOWN: continue
            for metric, ev in EVENT.items():
                if metric in names:
                    val = ga.get((d, blk, metric), 0)
                    updates.append((r_no, names[metric], blk, metric, d, val))
            for metric in MEDIA_METRICS:
                if metric in names and blk in media_blocks:
                    m = media.get((d, blk))
                    val = {"비용": m[0], "노출": m[1], "클릭": m[2]}[metric] if m else 0
                    updates.append((r_no, names[metric], blk, metric, d, round(val)))
    n_diff = 0
    bigs = []
    for r_no, c, blk, metric, d, val in updates:
        cur = grid[r_no - 1][c] if c < len(grid[r_no - 1]) else ""
        if str(cur).startswith("="): continue
        if str(cur).strip() != "" and val == 0: continue
        if str(cur).strip() != str(val):
            try:
                cv = float(str(cur).replace(",", ""))
                big = False
            except ValueError:
                big = False
            n_diff += 1
            if len(diffs) < 400: diffs.append((d, blk, metric, cur, val))
    print(f"{cid} {sem}기 {start}~{end}: 셀 {len(updates)}, 기존과 다른 셀 {n_diff}", flush=True)
    grp = defaultdict(list)
    for d, blk, metric, cur, val in diffs: grp[(blk, metric)].append((str(d), cur, val))
    for (blk, metric), items in sorted(grp.items()):
        print(f"   [{blk} {metric}] {len(items)}건, 예: {items[:2]}")
    if apply:
        ups = []
        for r_no, c, blk, metric, d, val in updates:
            cur = grid[r_no - 1][c] if c < len(grid[r_no - 1]) else ""
            if str(cur).startswith("=") or (str(cur).strip() != "" and val == 0): continue
            ups.append({"range": rowcol_to_a1(r_no, c + 1), "values": [[val]]})
        for i in range(0, len(ups), 300):
            ws.batch_update(ups[i:i + 300], value_input_option="USER_ENTERED")
            time.sleep(4)
        print("적용 완료", len(ups))


def main():
    apply = "--apply" in sys.argv
    backfill = "--backfill" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gs = gspread.authorize(s.get_credentials(s.SHEETS_SCOPES))
    bq = bigquery.Client(project=s.BQ_PROJECT, credentials=s.get_credentials(s.BQ_SCOPES))
    targets = [(args[0], int(args[1]))] if len(args) >= 2 else [(c, n) for c in COURSES for n in COURSES[c]["cohorts"]]
    yesterday = dt.date.today() - dt.timedelta(days=1)
    for cid, sem in targets:
        try:
            if backfill:
                sh = gs.open_by_key(COURSES[cid]["cohorts"][sem]["sheet_id"])
                win = cohort_window(sh.worksheet("2.1 일자별 유입현황").get_all_values(value_render_option="UNFORMATTED_VALUE"))
                time.sleep(2)
                if not win: continue
            else:
                win = (yesterday - dt.timedelta(days=6), yesterday)
            run_cohort(cid, sem, win[0], win[1], gs, bq, apply)
        except Exception as e:
            print(f"{cid} {sem}기 건너뜀: {type(e).__name__} {str(e)[:120]}", flush=True)


main()
