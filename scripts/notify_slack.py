"""자동 실행 결과를 Slack 웹훅으로 알립니다.

웹훅 URL은 환경변수 SLACK_WEBHOOK_URL 또는 프로젝트 루트 .env에서 읽습니다.
URL이 없으면 아무것도 하지 않고 종료합니다.
알림 전송에 실패해도 호출한 작업의 결과에는 영향을 주지 않도록 항상 0으로 종료합니다.

사용 예:
  python scripts/notify_slack.py --title "시트 기록 (GitHub)" --status success --detail "실행 로그 링크"
"""

import argparse
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
TIMEOUT_SECONDS = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("notify_slack")


def load_webhook_url():
    """웹훅 URL을 환경변수 또는 .env에서 읽습니다.

    Returns:
        웹훅 URL 문자열 (없으면 빈 문자열)
    """
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if url or not ENV_PATH.exists():
        return url
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("SLACK_WEBHOOK_URL="):
            return line.split("=", 1)[1].strip()
    return ""


def build_message(title, status, detail):
    """Slack에 보낼 메시지 본문을 만듭니다.

    Args:
        title: 작업 이름 (예: 시트 기록 (GitHub))
        status: "success" 또는 그 외(실패로 간주)
        detail: 추가 정보 (실행 로그 링크, 로그 파일 경로 등)

    Returns:
        Slack 웹훅 payload dict
    """
    ok = status == "success"
    icon = ":white_check_mark:" if ok else ":x:"
    result = "완료" if ok else "실패"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"{icon} *{title}* {result}", f"실행 시각: {now}"]
    if detail:
        lines.append(detail)
    return {"text": "\n".join(lines)}


def send(url, payload):
    """웹훅으로 payload를 전송합니다.

    Args:
        url: 웹훅 URL
        payload: 전송할 dict

    Returns:
        전송 성공 여부
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError) as error:
        logger.warning("Slack 알림 전송 실패: %s", type(error).__name__)
        return False


def main():
    """CLI 진입점: 웹훅 URL이 있을 때만 알림을 보냅니다."""
    parser = argparse.ArgumentParser(description="실행 결과를 Slack으로 알림")
    parser.add_argument("--title", required=True, help="작업 이름")
    parser.add_argument("--status", required=True, help="success 이면 완료, 그 외는 실패")
    parser.add_argument("--detail", default="", help="추가 정보")
    args = parser.parse_args()

    url = load_webhook_url()
    if not url:
        logger.info("SLACK_WEBHOOK_URL 이 없어 알림을 건너뜁니다.")
        return

    payload = build_message(args.title, args.status, args.detail)
    if send(url, payload):
        logger.info("Slack 알림 전송 완료")


if __name__ == "__main__":
    main()
