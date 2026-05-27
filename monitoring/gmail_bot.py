"""
Gmail 알림
- 구글 앱 비밀번호로 SMTP 발송
- 나에게 보내기 방식 (발신 = 수신)
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GmailNotifier:
    def __init__(self):
        self.email    = os.getenv("GMAIL_ADDRESS", "")
        self.password = os.getenv("GMAIL_APP_PASSWORD", "")

    def _send(self, subject: str, body: str) -> bool:
        if not self.email or not self.password:
            logger.warning("Gmail 설정 없음 — 알림 스킵")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.email
            msg["To"]      = self.email
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.email, self.password)
                smtp.sendmail(self.email, self.email, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Gmail 전송 실패: {e}")
            return False

    def send(self, text: str) -> bool:
        subject = f"[자동매매] {datetime.now().strftime('%H:%M')}"
        return self._send(subject, text)

    def send_alert(self, title: str, body: str) -> bool:
        return self._send(f"[자동매매 알림] {title}", body)

    def send_daily_report(self, api):
        try:
            balance  = api.get_balance()
            summary  = balance["summary"]
            holdings = balance["holdings"]

            total     = int(summary.get("tot_evlu_amt", 0))
            profit    = int(summary.get("evlu_pfls_smtl_amt", 0))
            profit_rt = float(summary.get("asst_icdc_erng_rt", 0))

            lines = [
                f"일일 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"총 평가금액 : {total:,}원",
                f"평가손익   : {profit:+,}원 ({profit_rt:+.2f}%)",
                "",
                "[보유 종목]",
            ]
            for h in holdings:
                if int(h.get("hldg_qty", 0)) <= 0:
                    continue
                name = h.get("prdt_name", h["pdno"])
                qty  = int(h["hldg_qty"])
                pnl  = float(h.get("evlu_pfls_rt", 0))
                lines.append(f"  {name}({h['pdno']}): {qty}주  {pnl:+.2f}%")

            self._send(
                f"[자동매매] 일일 리포트 {datetime.now().strftime('%Y-%m-%d')}",
                "\n".join(lines),
            )
        except Exception as e:
            logger.error(f"일일 리포트 실패: {e}")
