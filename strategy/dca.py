"""
전략 3: 변동성 조정 DCA (분할매수)
매일 정해진 시간에 일정 금액 매수
변동성(ATR) 높을수록 매수 금액 줄임
"""
import logging
from .indicators import to_df, atr

logger = logging.getLogger(__name__)


class DCAStrategy:
    def __init__(self, api, order_manager, risk_manager, notifier=None):
        self.api    = api
        self.om     = order_manager
        self.rm     = risk_manager
        self.notify = notifier

        self.base_amount  = 300_000   # 기본 1회 매수 금액 (원)
        self.atr_factor   = 1.5       # ATR 대비 가격 비율이 이 이상이면 금액 축소
        self.targets      = []        # {"code": "005930", "monthly_budget": 1_000_000}

    def add_target(self, code: str, monthly_budget: int):
        self.targets.append({"code": code, "monthly_budget": monthly_budget})

    def run(self):
        logger.info("[DCA] 전략 실행")
        for t in self.targets:
            try:
                self._execute(t["code"], t["monthly_budget"])
            except Exception as e:
                logger.error(f"[DCA] {t['code']} 오류: {e}")

    def _execute(self, code: str, monthly_budget: int):
        ohlcv = self.api.get_ohlcv(code, period="D", count=30)
        if len(ohlcv) < 15:
            return

        df            = to_df(ohlcv)
        current_price = df["close"].iloc[-1]
        atr_val       = atr(df).iloc[-1]

        # 변동성 비율 (ATR / 현재가)
        vol_ratio = atr_val / current_price if current_price > 0 else 0

        # 변동성 높으면 매수 금액 감소 (최소 50%)
        adj_factor = max(0.5, 1 - (vol_ratio / self.atr_factor))
        amount     = int(monthly_budget / 20 * adj_factor)  # 월 예산 / 20 영업일

        ok, reason = self.rm.can_buy(code, amount)
        if not ok:
            logger.info(f"[DCA] {code} 리스크 차단: {reason}")
            return

        logger.info(f"[DCA] {code} 매수 {amount:,}원 (변동성 조정 {adj_factor:.2f})")
        self.om.buy_by_amount(code, amount, reason=f"DCA 변동성조정={adj_factor:.2f}")
