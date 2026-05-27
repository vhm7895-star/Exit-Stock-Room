"""
전략 2: 이동평균선 골든크로스 / 데드크로스
5일선이 20일선을 상향 돌파 → 매수
5일선이 20일선을 하향 돌파 → 매도
"""
import logging
from .indicators import to_df, golden_cross, dead_cross, rsi

logger = logging.getLogger(__name__)


class GoldenCrossStrategy:
    def __init__(self, api, order_manager, risk_manager, notifier=None):
        self.api    = api
        self.om     = order_manager
        self.rm     = risk_manager
        self.notify = notifier

        self.fast        = 5
        self.slow        = 20
        self.buy_amount  = 1_000_000  # 1회 매수 금액 (원)
        self.watchlist   = []

    def add_watchlist(self, codes: list[str]):
        self.watchlist = codes

    def run(self):
        logger.info("[골든크로스] 전략 실행")
        for code in self.watchlist:
            try:
                self._check(code)
            except Exception as e:
                logger.error(f"[골든크로스] {code} 오류: {e}")

    def _check(self, code: str):
        ohlcv = self.api.get_ohlcv(code, period="D", count=60)
        if len(ohlcv) < 25:
            return

        df = to_df(ohlcv)
        gc = golden_cross(df, self.fast, self.slow)
        dc = dead_cross(df, self.fast, self.slow)

        if gc.iloc[-1]:
            ok, reason = self.rm.can_buy(code, self.buy_amount)
            if ok:
                logger.info(f"[골든크로스] {code} 골든크로스 매수 신호")
                self.om.buy_by_amount(code, self.buy_amount, reason="골든크로스")
            else:
                logger.info(f"[골든크로스] {code} 리스크 차단: {reason}")

        elif dc.iloc[-1]:
            # 보유 중이면 전량 매도
            balance  = self.api.get_balance()
            holdings = balance["holdings"]
            holding  = next((h for h in holdings if h["pdno"] == code), None)
            if holding:
                qty = int(holding["hldg_qty"])
                logger.info(f"[골든크로스] {code} 데드크로스 매도 신호 {qty}주")
                self.om.market_sell(code, qty, reason="데드크로스")
