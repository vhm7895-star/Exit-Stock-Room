"""
고도화된 매도 로직
- 트레일링 스탑 (고점 대비 -X% 시 매도)
- 시간 기반 청산 (보유 N일 초과)
- 변동성 급등 청산
- 장 마감 전 익절 확정
"""
import logging
from datetime import datetime, date
from collections import defaultdict

logger = logging.getLogger(__name__)


class ExitManager:
    def __init__(self, api, order_manager, notifier=None):
        self.api      = api
        self.om       = order_manager
        self.notifier = notifier

        # 트레일링 스탑 설정
        self.trailing_stop_pct  = 0.05   # 고점 대비 -5% 시 매도
        self.trailing_stop_min  = 0.03   # 매수가 대비 최소 +3% 이상일 때만 트레일링 활성화

        # 시간 기반 청산
        self.max_hold_days = 20          # 최대 보유일

        # 변동성 청산
        self.vol_spike_mult = 3.0        # 평균 ATR 대비 3배 이상 급등 시 청산

        # 장 마감 전 익절
        self.eod_profit_threshold = 0.03  # +3% 이상이면 장 마감 전 익절

        # 내부 상태 추적
        self._peak_prices   = {}   # {code: 고점가격}
        self._entry_dates   = {}   # {code: 최초 매수일}
        self._entry_prices  = {}   # {code: 평균매수가}

    # ── 보유 종목 상태 동기화 ─────────────────────────────

    def sync_holdings(self):
        """보유 종목 정보를 API에서 가져와 내부 상태 갱신"""
        balance  = self.api.get_balance()
        holdings = balance["holdings"]

        current_codes = {h["pdno"] for h in holdings if int(h.get("hldg_qty", 0)) > 0}

        # 청산된 종목 제거
        for code in list(self._peak_prices.keys()):
            if code not in current_codes:
                self._peak_prices.pop(code, None)
                self._entry_dates.pop(code, None)
                self._entry_prices.pop(code, None)

        for h in holdings:
            code  = h["pdno"]
            qty   = int(h.get("hldg_qty", 0))
            if qty <= 0:
                continue

            avg   = float(h.get("pchs_avg_pric", 0))
            curr  = float(h.get("prpr", 0))

            # 최초 등록
            if code not in self._entry_prices:
                self._entry_prices[code] = avg
                self._entry_dates[code]  = date.today()
                self._peak_prices[code]  = curr
            else:
                # 고점 갱신
                if curr > self._peak_prices.get(code, 0):
                    self._peak_prices[code] = curr

    # ── 메인 체크 (매 분 호출) ────────────────────────────

    def check_all(self) -> list[dict]:
        """
        모든 매도 조건 체크
        returns: [{"code": ..., "qty": ..., "reason": ...}, ...]
        """
        self.sync_holdings()

        balance  = self.api.get_balance()
        holdings = balance["holdings"]
        signals  = []

        for h in holdings:
            code = h["pdno"]
            qty  = int(h.get("hldg_qty", 0))
            if qty <= 0:
                continue

            curr  = float(h.get("prpr", 0))
            avg   = float(h.get("pchs_avg_pric", 1))
            pnl   = (curr - avg) / avg

            sig = self._check_one(code, qty, curr, avg, pnl)
            if sig:
                signals.append(sig)

        return signals

    def _check_one(self, code, qty, curr, avg, pnl) -> dict | None:

        # 1. 트레일링 스탑
        if pnl >= self.trailing_stop_min:
            peak = self._peak_prices.get(code, curr)
            drop_from_peak = (curr - peak) / peak
            if drop_from_peak <= -self.trailing_stop_pct:
                return {
                    "code":   code,
                    "qty":    qty,
                    "reason": f"트레일링스탑 고점({peak:,.0f}) 대비 {drop_from_peak:.1%}",
                }

        # 2. 시간 기반 청산
        entry_date  = self._entry_dates.get(code)
        if entry_date:
            hold_days = (date.today() - entry_date).days
            if hold_days >= self.max_hold_days and pnl < 0:
                return {
                    "code":   code,
                    "qty":    qty,
                    "reason": f"보유기간초과 {hold_days}일 (손실보유 청산)",
                }

        # 3. 장 마감 전 익절 (15:00~15:20)
        now = datetime.now().strftime("%H:%M")
        if "15:00" <= now <= "15:20" and pnl >= self.eod_profit_threshold:
            return {
                "code":   code,
                "qty":    qty,
                "reason": f"장마감 전 익절 {pnl:.1%}",
            }

        return None

    # ── 변동성 급등 청산 ──────────────────────────────────

    def check_volatility_spike(self, code: str, current_atr: float, avg_atr: float) -> bool:
        """
        ATR이 평균의 vol_spike_mult 배 이상이면 True
        외부에서 ATR 값을 계산하여 전달
        """
        if avg_atr <= 0:
            return False
        return current_atr >= avg_atr * self.vol_spike_mult

    # ── 매도 실행 ─────────────────────────────────────────

    def execute_exits(self):
        """check_all() 결과를 바탕으로 실제 매도 실행"""
        signals = self.check_all()
        for sig in signals:
            logger.info(f"[ExitManager] {sig['code']} 매도: {sig['reason']}")
            self.om.market_sell(sig["code"], sig["qty"], reason=sig["reason"])

    # ── 설정 변경 ─────────────────────────────────────────

    def set_trailing_stop(self, pct: float, min_profit: float = 0.03):
        self.trailing_stop_pct = pct
        self.trailing_stop_min = min_profit

    def set_max_hold_days(self, days: int):
        self.max_hold_days = days

    def set_eod_profit(self, threshold: float):
        self.eod_profit_threshold = threshold
