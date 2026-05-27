"""
카카오톡 나에게 보내기 알림
- kakao_auth.py 를 먼저 실행해 토큰을 .env 에 저장해야 합니다.
"""
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv, set_key

load_dotenv()
logger = logging.getLogger(__name__)

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_SEND_URL  = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


class KakaoNotifier:
    def __init__(self):
        self.rest_api_key    = os.getenv("KAKAO_REST_API_KEY", "")
        self.access_token    = os.getenv("KAKAO_ACCESS_TOKEN", "")
        self.refresh_token   = os.getenv("KAKAO_REFRESH_TOKEN", "")

    def _refresh_access_token(self) -> bool:
        if not self.refresh_token:
            logger.error("카카오 REFRESH_TOKEN 없음 — kakao_auth.py 를 다시 실행하세요")
            return False
        try:
            res = requests.post(_TOKEN_URL, data={
                "grant_type":    "refresh_token",
                "client_id":     self.rest_api_key,
                "refresh_token": self.refresh_token,
            }, timeout=5)
            data = res.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                set_key(_ENV_PATH, "KAKAO_ACCESS_TOKEN", self.access_token)
                if "refresh_token" in data:
                    self.refresh_token = data["refresh_token"]
                    set_key(_ENV_PATH, "KAKAO_REFRESH_TOKEN", self.refresh_token)
                logger.info("카카오 액세스 토큰 갱신 완료")
                return True
            logger.error(f"토큰 갱신 실패: {data}")
            return False
        except Exception as e:
            logger.error(f"토큰 갱신 오류: {e}")
            return False

    def _send_request(self, template: dict) -> bool:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        res = requests.post(_SEND_URL,
                            headers=headers,
                            data={"template_object": __import__("json").dumps(template)},
                            timeout=5)
        if res.status_code == 401:
            if self._refresh_access_token():
                headers["Authorization"] = f"Bearer {self.access_token}"
                res = requests.post(_SEND_URL,
                                    headers=headers,
                                    data={"template_object": __import__("json").dumps(template)},
                                    timeout=5)
        if res.status_code == 200 and res.json().get("result_code") == 0:
            return True
        logger.error(f"카카오 전송 실패: {res.status_code} {res.text}")
        return False

    def send(self, text: str) -> bool:
        if not self.access_token:
            logger.warning("카카오 설정 없음 — 알림 스킵 (kakao_auth.py 실행 필요)")
            return False
        try:
            template = {
                "object_type": "text",
                "text": text[:10000],
                "link": {"web_url": "", "mobile_web_url": ""},
            }
            return self._send_request(template)
        except Exception as e:
            logger.error(f"카카오 전송 오류: {e}")
            return False

    def send_alert(self, title: str, body: str):
        self.send(f"[{title}]\n{body}")

    def send_daily_report(self, api):
        try:
            balance   = api.get_balance()
            summary   = balance["summary"]
            holdings  = balance["holdings"]

            total     = int(summary.get("tot_evlu_amt", 0))
            profit    = int(summary.get("evlu_pfls_smtl_amt", 0))
            profit_rt = float(summary.get("asst_icdc_erng_rt", 0))

            lines = [
                f"일일 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"총 평가금액: {total:,}원",
                f"평가손익: {profit:+,}원 ({profit_rt:+.2f}%)",
                "",
                "[보유 종목]",
            ]
            for h in holdings:
                if int(h.get("hldg_qty", 0)) <= 0:
                    continue
                code  = h["pdno"]
                name  = h.get("prdt_name", code)
                qty   = int(h["hldg_qty"])
                pnl   = float(h.get("evlu_pfls_rt", 0))
                lines.append(f"  {name}({code}): {qty}주 {pnl:+.2f}%")

            self.send("\n".join(lines))
        except Exception as e:
            logger.error(f"일일 리포트 실패: {e}")
