"""
전략 1: 모멘텀 전략
52주 신고가 돌파 + 거래량 급증 시 매수
"""
import logging
from .indicators import to_df, is_52week_high, volume_surge, rsi

logger = logging.getLogger(__name__)


class MomentumStrategy:
    def __init__(self, api, order_manager, risk_manager, notifier=None):
        self.api    = api
        self.om     = order_manager
        self.rm     = risk_manager
        self.notify = notifier

        self.buy_amount     = 500_000   # 1회 매수 금액 (원)
        self.rsi_max        = 75        # RSI 과매수 필터 (이 이상이면 패스)
        self.watchlist      = []        # 감시 종목 코드 리스트

    def add_watchlist(self, codes: list[str]):
        self.watchlist = codes

    def run(self):
        logger.info("[모멘텀] 전략 실행")
        for code in self.watchlist:
            try:
                self._check(code)
            except Exception as e:
                logger.error(f"[모멘텀] {code} 오류: {e}")

    def _check(self, code: str):
        ohlcv = self.api.get_ohlcv(code, period="D", count=260)
        if len(ohlcv) < 60:
            return

        df = to_df(ohlcv)

        if not is_52week_high(df):
            return
        if not volume_surge(df, mult=2.0):
            return

        r = rsi(df).iloc[-1]
        if r > self.rsi_max:
            logger.info(f"[모멘텀] {code} RSI 과매수 필터({r:.1f}) — 패스")
            return

        ok, reason = self.rm.can_buy(code, self.buy_amount)
        if not ok:
            logger.info(f"[모멘텀] {code} 리스크 차단: {reason}")
            return

        logger.info(f"[모멘텀] {code} 매수 신호 발생 (RSI={r:.1f})")
        self.om.buy_by_amount(code, self.buy_amount, reason=f"모멘텀 52주 신고가 돌파 RSI={r:.1f}")
