"""
텔레그램 알림 봇
"""
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("텔레그램 설정 없음 — 알림 스킵")
            return False
        try:
            res = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=5,
            )
            return res.json().get("ok", False)
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
            return False

    def send_daily_report(self, api):
        """일일 수익률 리포트"""
        try:
            balance  = api.get_balance()
            summary  = balance["summary"]
            holdings = balance["holdings"]

            total      = int(summary.get("tot_evlu_amt", 0))
            profit     = int(summary.get("evlu_pfls_smtl_amt", 0))
            profit_rt  = float(summary.get("asst_icdc_erng_rt", 0))

            lines = [
                f"<b>일일 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M')}</b>",
                f"총 평가금액: {total:,}원",
                f"평가손익: {profit:+,}원 ({profit_rt:+.2f}%)",
                "",
                "<b>보유 종목</b>",
            ]

            for h in holdings:
                if int(h.get("hldg_qty", 0)) <= 0:
                    continue
                code   = h["pdno"]
                name   = h.get("prdt_name", code)
                qty    = int(h["hldg_qty"])
                pnl    = float(h.get("evlu_pfls_rt", 0))
                lines.append(f"  {name}({code}): {qty}주 {pnl:+.2f}%")

            self.send("\n".join(lines))
        except Exception as e:
            logger.error(f"일일 리포트 실패: {e}")

    def send_alert(self, title: str, body: str):
        self.send(f"<b>{title}</b>\n{body}")
