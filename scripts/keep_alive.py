"""Streamlit Community Cloud 절전 방지 스크립트.

헤드리스 브라우저로 대시보드를 열어 앱이 정상 렌더링되는지 확인합니다.
절전 상태라면 "get this app back up" 버튼을 눌러 앱을 깨웁니다.
"""

import logging
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("keep_alive")

# 절전 상태에서 나타나는 깨우기 버튼 문구 (대소문자 무시)
WAKE_BUTTON_PATTERN = re.compile(r"get this app back up", re.IGNORECASE)
# 앱이 렌더링될 때까지 기다리는 시간 (ms)
RENDER_TIMEOUT_MS = 120_000
# 세션을 유지하기 위해 페이지를 열어 두는 시간 (초)
HOLD_SECONDS = 30


def keep_alive(url: str) -> bool:
    """대시보드를 열어 앱을 깨우고 정상 렌더링을 확인합니다.

    Args:
        url: 대시보드 URL

    Returns:
        앱이 정상적으로 렌더링되면 True, 아니면 False
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            logger.info("대시보드 접속: %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            wake_button = page.get_by_role("button", name=WAKE_BUTTON_PATTERN)
            if wake_button.count() > 0:
                logger.info("절전 상태 감지, 앱 깨우기 버튼 클릭")
                wake_button.first.click()

            page.wait_for_selector('[data-testid="stApp"]', timeout=RENDER_TIMEOUT_MS)
            logger.info("앱 렌더링 확인, %d초간 세션 유지", HOLD_SECONDS)
            time.sleep(HOLD_SECONDS)
            return True
        except Exception:
            logger.exception("대시보드 접속 실패")
            return False
        finally:
            browser.close()


def main() -> None:
    """환경변수 APP_URL을 읽어 절전 방지를 실행합니다."""
    url = os.environ.get("APP_URL")
    if not url:
        logger.error("APP_URL 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    if not keep_alive(url):
        sys.exit(1)


if __name__ == "__main__":
    main()
