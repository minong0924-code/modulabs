"""자동 실행 결과를 이메일(SMTP)로 알립니다.

설정은 환경변수 또는 프로젝트 루트 .env에서 읽습니다.
  MAIL_SMTP_HOST      SMTP 서버 (예: smtp.gmail.com)
  MAIL_SMTP_PORT      포트 (기본 587, STARTTLS)
  MAIL_USER           보내는 계정 (로그인 ID)
  MAIL_PASSWORD       비밀번호 또는 앱 비밀번호
  MAIL_TO             받는 주소 (쉼표로 여러 개 가능)

설정이 없으면 아무것도 하지 않고 종료합니다.
알림 전송에 실패해도 호출한 작업의 결과에는 영향을 주지 않도록 항상 0으로 종료합니다.

사용 예:
  python scripts/notify_email.py --title "시트 기록 (PC)" --status success --detail "로그 파일 경로"
"""

import argparse
import logging
import os
import smtplib
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
TIMEOUT_SECONDS = 15
MAIL_KEYS = ("MAIL_SMTP_HOST", "MAIL_SMTP_PORT", "MAIL_USER", "MAIL_PASSWORD", "MAIL_TO")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("notify_email")


def load_mail_config():
    """메일 설정을 환경변수 또는 .env에서 읽습니다.

    Returns:
        {키: 값} dict (필수 값이 없으면 빈 dict)
    """
    config = {key: os.getenv(key, "").strip() for key in MAIL_KEYS}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                key = key.strip()
                if key in MAIL_KEYS and not config[key]:
                    config[key] = value.strip()
    required = ("MAIL_SMTP_HOST", "MAIL_USER", "MAIL_PASSWORD", "MAIL_TO")
    if not all(config[key] for key in required):
        return {}
    config["MAIL_SMTP_PORT"] = config["MAIL_SMTP_PORT"] or "587"
    return config


def build_message(title, status, detail, sender, recipients):
    """보낼 이메일 메시지를 만듭니다.

    Args:
        title: 작업 이름 (예: 시트 기록 (PC))
        status: "success" 또는 그 외(실패로 간주)
        detail: 추가 정보 (로그 파일 경로 등)
        sender: 보내는 주소
        recipients: 받는 주소 목록

    Returns:
        MIMEText 객체
    """
    ok = status == "success"
    result = "완료" if ok else "실패"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"{title} {result}\n실행 시각: {now}"
    if detail:
        body += f"\n{detail}"
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = str(Header(f"[자동 실행] {title} {result} ({now})", "utf-8"))
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    return message


def send(config, message):
    """SMTP 서버로 메일을 보냅니다.

    Args:
        config: load_mail_config()가 반환한 설정 dict
        message: 보낼 MIMEText 객체

    Returns:
        전송 성공 여부
    """
    try:
        with smtplib.SMTP(config["MAIL_SMTP_HOST"], int(config["MAIL_SMTP_PORT"]), timeout=TIMEOUT_SECONDS) as server:
            server.starttls()
            server.login(config["MAIL_USER"], config["MAIL_PASSWORD"])
            server.sendmail(config["MAIL_USER"], config["MAIL_TO"].split(","), message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as error:
        logger.warning("이메일 알림 전송 실패: %s", type(error).__name__)
        return False


def main():
    """CLI 진입점: 메일 설정이 있을 때만 알림을 보냅니다."""
    parser = argparse.ArgumentParser(description="실행 결과를 이메일로 알림")
    parser.add_argument("--title", required=True, help="작업 이름")
    parser.add_argument("--status", required=True, help="success 이면 완료, 그 외는 실패")
    parser.add_argument("--detail", default="", help="추가 정보")
    parser.add_argument("--detail-file", default="", help="본문 뒤에 붙일 텍스트 파일 (예: 사람 확인 항목)")
    args = parser.parse_args()

    config = load_mail_config()
    if not config:
        logger.info("메일 설정(MAIL_*)이 없어 이메일 알림을 건너뜁니다.")
        return

    detail = args.detail
    if args.detail_file and Path(args.detail_file).exists():
        # 파일이 없거나 읽을 수 없어도 알림 자체는 보냄
        extra = Path(args.detail_file).read_text(encoding="utf-8").strip()
        detail = f"{detail}\n\n[사람 확인 필요]\n{extra}" if extra else detail

    recipients = [addr.strip() for addr in config["MAIL_TO"].split(",") if addr.strip()]
    message = build_message(args.title, args.status, detail, config["MAIL_USER"], recipients)
    if send(config, message):
        logger.info("이메일 알림 전송 완료")


if __name__ == "__main__":
    main()
