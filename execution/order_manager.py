"""
주문 관리 — TWAP/VWAP 분할매수, 주문 이력 추적
"""
import time
import math
import logging
from datetime import datetime
from .kis_api import KISApi

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, api: KISApi, notifier=None):
        self.api      = api
        self.notifier = notifier
        self.history  = []  # 주문 이력

    # ── 단순 주문 ──────────────────────────────────────────

    def market_buy(self, code: str, qty: int, reason: str = "") -> dict | None:
        try:
            result = self.api.buy_market(code, qty)
            self._record("BUY", code, qty, 0, "market", reason, result)
            msg = f"[매수] {code} {qty}주 시장가\n사유: {reason}"
            logger.info(msg)
            if self.notifier:
                self.notifier.send(msg)
            return result
        except Exception as e:
            logger.error(f"시장가 매수 실패 {code}: {e}")
            return None

    def market_sell(self, code: str, qty: int, reason: str = "") -> dict | None:
        try:
            result = self.api.sell_market(code, qty)
            self._record("SELL", code, qty, 0, "market", reason, result)
            msg = f"[매도] {code} {qty}주 시장가\n사유: {reason}"
            logger.info(msg)
            if self.notifier:
                self.notifier.send(msg)
            return result
        except Exception as e:
            logger.error(f"시장가 매도 실패 {code}: {e}")
            return None

    # ── TWAP 분할매수 ──────────────────────────────────────

    def twap_buy(self, code: str, total_qty: int, slices: int = 5, interval_sec: int = 60):
        """
        TWAP 매수: total_qty를 slices 등분으로 interval_sec 간격 분할 매수
        슬리피지 최소화용
        """
        base_qty  = total_qty // slices
        remainder = total_qty % slices

        logger.info(f"[TWAP] {code} 총 {total_qty}주, {slices}회 분할, {interval_sec}초 간격")

        for i in range(slices):
            qty = base_qty + (1 if i < remainder else 0)
            if qty <= 0:
                continue
            self.market_buy(code, qty, reason=f"TWAP {i+1}/{slices}")
            if i < slices - 1:
                time.sleep(interval_sec)

    # ── 금액 기반 매수 ────────────────────────────────────

    def buy_by_amount(self, code: str, amount: int, reason: str = "") -> dict | None:
        """금액 기준 매수 (현재가로 수량 자동 계산)"""
        try:
            price_data = self.api.get_price(code)
            current_price = int(price_data["stck_prpr"])
            qty = math.floor(amount / current_price)
            if qty < 1:
                logger.warning(f"{code} 매수 수량 부족 (금액:{amount}, 현재가:{current_price})")
                return None
            return self.market_buy(code, qty, reason)
        except Exception as e:
            logger.error(f"금액 매수 실패 {code}: {e}")
            return None

    # ── 이력 ──────────────────────────────────────────────

    def _record(self, side, code, qty, price, order_type, reason, raw):
        self.history.append({
            "time":       datetime.now().isoformat(),
            "side":       side,
            "code":       code,
            "qty":        qty,
            "price":      price,
            "order_type": order_type,
            "reason":     reason,
            "raw":        raw,
        })

    def get_history(self, code: str = None) -> list:
        if code:
            return [h for h in self.history if h["code"] == code]
        return self.history
