"""
리스크 관리 모듈
- 종목/섹터 비중 한도
- 일일 손실 한도
- 개별 손절/익절
- VaR 계산
"""
import os
import logging
import numpy as np
from datetime import date
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, api):
        self.api = api

        self.MAX_SINGLE   = float(os.getenv("MAX_SINGLE_STOCK_RATIO", 0.10))
        self.MAX_SECTOR   = float(os.getenv("MAX_SECTOR_RATIO", 0.25))
        self.DAILY_LIMIT  = float(os.getenv("DAILY_LOSS_LIMIT", 0.02))
        self.STOP_LOSS    = float(os.getenv("STOP_LOSS_RATIO", 0.07))
        self.TAKE_PROFIT  = float(os.getenv("TAKE_PROFIT_RATIO", 0.15))

        self._daily_start_value = None
        self._today             = None
        self._trading_halted    = False

    # ── 일일 기준값 초기화 ─────────────────────────────────

    def initialize_day(self):
        today = date.today()
        if self._today != today:
            balance         = self.api.get_balance()
            summary         = balance["summary"]
            total           = int(summary.get("tot_evlu_amt", 0))
            self._daily_start_value = total
            self._today             = today
            self._trading_halted    = False
            logger.info(f"[리스크] 일일 기준값 설정: {total:,}원")

    # ── 매수 가능 여부 확인 ────────────────────────────────

    def can_buy(self, stock_code: str, amount: int, sector: str = "기타") -> tuple[bool, str]:
        """매수 전 리스크 체크. (가능여부, 사유) 반환"""
        if self._trading_halted:
            return False, "일일 손실 한도 초과로 거래 중단"

        balance  = self.api.get_balance()
        summary  = balance["summary"]
        holdings = balance["holdings"]
        total    = int(summary.get("tot_evlu_amt", 1))

        # 일일 손실 체크
        if self._daily_start_value:
            loss_rate = (total - self._daily_start_value) / self._daily_start_value
            if loss_rate <= -self.DAILY_LIMIT:
                self._trading_halted = True
                return False, f"일일 손실 한도 초과: {loss_rate:.1%}"

        # 종목 비중 체크
        stock_value = next(
            (int(h["evlu_amt"]) for h in holdings if h["pdno"] == stock_code), 0
        )
        new_ratio = (stock_value + amount) / total
        if new_ratio > self.MAX_SINGLE:
            return False, f"종목 비중 한도 초과: {new_ratio:.1%} > {self.MAX_SINGLE:.0%}"

        # 섹터 비중 체크 (같은 섹터 전체 합산)
        sector_value = sum(
            int(h["evlu_amt"]) for h in holdings
            if h.get("prdt_type_cd", "") == sector
        )
        sector_ratio = (sector_value + amount) / total
        if sector_ratio > self.MAX_SECTOR:
            return False, f"섹터 비중 한도 초과: {sector_ratio:.1%} > {self.MAX_SECTOR:.0%}"

        return True, "OK"

    # ── 손절/익절 체크 ────────────────────────────────────

    def check_exit_signals(self) -> list[dict]:
        """
        보유 종목 중 손절/익절 조건 달성 종목 반환
        returns: [{"code": ..., "qty": ..., "reason": ...}, ...]
        """
        balance  = self.api.get_balance()
        holdings = balance["holdings"]
        signals  = []

        for h in holdings:
            code      = h["pdno"]
            qty       = int(h["hldg_qty"])
            buy_avg   = float(h["pchs_avg_pric"])
            current   = int(h["prpr"])

            if buy_avg <= 0 or qty <= 0:
                continue

            change = (current - buy_avg) / buy_avg

            if change <= -self.STOP_LOSS:
                signals.append({"code": code, "qty": qty, "reason": f"손절 {change:.1%}"})
            elif change >= self.TAKE_PROFIT:
                signals.append({"code": code, "qty": qty, "reason": f"익절 {change:.1%}"})

        return signals

    # ── VaR 계산 ──────────────────────────────────────────

    def calc_var(self, returns: list[float], confidence: float = 0.95) -> float:
        """
        Historical VaR 계산
        returns: 일별 수익률 리스트
        """
        if len(returns) < 20:
            return 0.0
        arr = np.array(returns)
        return float(np.percentile(arr, (1 - confidence) * 100))

    # ── 포지션 크기 계산 ──────────────────────────────────

    def kelly_position_size(self, win_rate: float, avg_win: float, avg_loss: float, total_asset: int) -> int:
        """
        켈리 공식으로 최적 투자 금액 계산
        실제 사용 시 half-kelly (0.5 곱) 권장
        """
        if avg_loss == 0:
            return 0
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b
        kelly = max(0, min(kelly * 0.5, self.MAX_SINGLE))  # half-kelly, 상한 적용
        return int(total_asset * kelly)
