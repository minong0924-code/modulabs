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
# 절전 화면의 깨우기 버튼이 나타날 때까지 기다리는 시간 (ms)
WAKE_BUTTON_WAIT_MS = 45_000
# 세션을 유지하기 위해 페이지를 열어 두는 시간 (초)
HOLD_SECONDS = 30
# 실패 시 저장할 스크린샷 경로 (워크플로에서 아티팩트로 업로드)
FAILURE_SCREENSHOT_PATH = "keep_alive_failure.png"


def find_app_frame(page, timeout_ms: int):
    """앱이 들어 있는 화면(바깥 페이지 또는 iframe)을 찾습니다.

    Streamlit Cloud는 앱을 iframe 안에 넣어 보여 주므로, 바깥 페이지와 모든 iframe을 함께 확인합니다.
    깨우기 버튼이 보이면 눌러 주고, 앱 화면(stApp)이 나타나면 그 화면을 돌려줍니다.

    Args:
        page: Playwright 페이지 객체
        timeout_ms: 전체 대기 시간 (ms)

    Returns:
        앱 화면 객체, 시간 안에 찾지 못하면 None
    """
    deadline = time.time() + timeout_ms / 1000
    woke = False
    while time.time() < deadline:
        for frame in [page] + [f for f in page.frames if f != page.main_frame]:
            try:
                if frame.locator('[data-testid="stApp"]').count() > 0:
                    return frame
                wake = frame.get_by_role("button", name=WAKE_BUTTON_PATTERN)
                if not woke and wake.count() > 0 and wake.first.is_visible():
                    logger.info("절전 상태 감지, 앱 깨우기 버튼 클릭")
                    wake.first.click()
                    woke = True
            except Exception:
                continue
        page.wait_for_timeout(2_000)
    return None


def keep_alive(url: str) -> bool:
    """대시보드를 열어 앱을 깨우고 정상 렌더링을 확인합니다.

    Args:
        url: 대시보드 URL

    Returns:
        앱이 정상적으로 렌더링되면 True, 아니면 False
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            logger.info("대시보드 접속: %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            app_frame = find_app_frame(page, WAKE_BUTTON_WAIT_MS + RENDER_TIMEOUT_MS)
            if app_frame is None:
                raise TimeoutError("앱 화면(stApp)을 시간 안에 찾지 못했습니다")
            logger.info("앱 렌더링 확인, %d초간 세션 유지", HOLD_SECONDS)
            time.sleep(HOLD_SECONDS)
            return True
        except Exception:
            logger.exception("대시보드 접속 실패")
            save_failure_diagnostics(page)
            return False
        finally:
            browser.close()


def save_failure_diagnostics(page) -> None:
    """실패 시점의 URL, 제목, 화면을 로그와 스크린샷 파일로 남깁니다.

    Args:
        page: Playwright 페이지 객체
    """
    try:
        logger.error("실패 시점 URL: %s", page.url)
        logger.error("실패 시점 페이지 제목: %s", page.title())
        body_text = page.inner_text("body")[:500]
        logger.error("실패 시점 본문 일부:\n%s", body_text)
        page.screenshot(path=FAILURE_SCREENSHOT_PATH, full_page=True)
        logger.error("스크린샷 저장: %s", FAILURE_SCREENSHOT_PATH)
    except Exception:
        logger.exception("진단 정보 수집 실패")


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
