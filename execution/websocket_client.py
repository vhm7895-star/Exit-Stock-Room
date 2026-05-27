"""
KIS WebSocket 실시간 데이터 수신
"""
import os
import json
import time
import threading
import websocket
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL_REAL  = "https://openapi.koreainvestment.com:9443"
BASE_URL_PAPER = "https://openapivts.koreainvestment.com:29443"
WS_URL_REAL    = "ws://ops.koreainvestment.com:21000"
WS_URL_PAPER   = "ws://ops.koreainvestment.com:31000"


class KISWebSocket:
    def __init__(self, on_price=None, on_conclusion=None):
        self.is_paper   = os.getenv("KIS_IS_PAPER", "false").lower() == "true"
        self.app_key    = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.base_url   = BASE_URL_PAPER if self.is_paper else BASE_URL_REAL
        self.ws_url     = WS_URL_PAPER if self.is_paper else WS_URL_REAL

        self.on_price      = on_price       # 현재가 콜백
        self.on_conclusion = on_conclusion  # 체결 콜백

        self._ws        = None
        self._thread    = None
        self._approval  = None
        self._subscribed = []

    def _get_approval(self) -> str:
        url  = f"{self.base_url}/oauth2/Approval"
        body = {"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.app_secret}
        res  = requests.post(url, json=body)
        res.raise_for_status()
        return res.json()["approval_key"]

    def _subscribe_msg(self, tr_id: str, stock_code: str) -> str:
        return json.dumps({
            "header": {
                "approval_key": self._approval,
                "custtype":     "P",
                "tr_type":      "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {"tr_id": tr_id, "tr_key": stock_code}
            },
        })

    def _on_message(self, ws, message):
        try:
            if message.startswith("{"):
                data = json.loads(message)
                # PINGPONG 처리
                if data.get("header", {}).get("tr_id") == "PINGPONG":
                    ws.send(message)
                return

            parts = message.split("|")
            if len(parts) < 4:
                return

            tr_id   = parts[1]
            payload = parts[3].split("^")

            if tr_id == "H0STCNT0" and self.on_price:
                self.on_price({
                    "code":        payload[0],
                    "price":       int(payload[2]),
                    "change_rate": float(payload[5]),
                    "volume":      int(payload[8]),
                    "time":        payload[1],
                })
            elif tr_id == "H0STCNI0" and self.on_conclusion:
                self.on_conclusion({
                    "code":  payload[0],
                    "price": int(payload[2]),
                    "qty":   int(payload[3]),
                    "side":  "BUY" if payload[4] == "1" else "SELL",
                })
        except Exception as e:
            print(f"[WS] 메시지 파싱 오류: {e}")

    def _on_open(self, ws):
        print("[WS] 연결됨")
        for tr_id, code in self._subscribed:
            ws.send(self._subscribe_msg(tr_id, code))

    def _on_error(self, ws, error):
        print(f"[WS] 오류: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print("[WS] 연결 종료 — 5초 후 재연결")
        time.sleep(5)
        self.connect()

    def subscribe_price(self, stock_code: str):
        self._subscribed.append(("H0STCNT0", stock_code))
        if self._ws:
            self._ws.send(self._subscribe_msg("H0STCNT0", stock_code))

    def subscribe_conclusion(self, stock_code: str):
        self._subscribed.append(("H0STCNI0", stock_code))
        if self._ws:
            self._ws.send(self._subscribe_msg("H0STCNI0", stock_code))

    def connect(self):
        self._approval = self._get_approval()
        self._ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._thread.start()

    def disconnect(self):
        if self._ws:
            self._ws.close()
