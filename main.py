"""
KIS 자동매매 메인 엔진 (풀버전)
- 시장 전체 스크리닝으로 종목 자동 발굴
- 퀀트 스코어링으로 상위 종목 선정
- 모멘텀 / 골든크로스 / DCA 전략
- 트레일링스탑 / 시간청산 / 장마감 익절 매도
- 텔레그램 알림

실행: python main.py
"""
import sys
import time
import logging
import schedule
from datetime import datetime
from dotenv import load_dotenv

# Windows CP949 환경에서 한글/특수문자 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

from execution.kis_api       import KISApi
from execution.order_manager  import OrderManager
from risk.risk_manager        import RiskManager
from risk.exit_manager        import ExitManager
from strategy.momentum        import MomentumStrategy
from strategy.golden_cross    import GoldenCrossStrategy
from strategy.dca             import DCAStrategy
from data.market_screener     import MarketScreener
from data.quant_scorer        import QuantScorer
from monitoring.gmail_bot     import GmailNotifier as TelegramNotifier

# ── 로깅 설정 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/trader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ── 설정 ───────────────────────────────────────────────────

SCREEN_CONDITIONS = ["52week_high", "volume_surge", "golden_cross"]
SCREEN_TOP_N      = 50   # 스크리닝 후보 수
QUANT_TOP_N       = 5    # 퀀트 스코어 최종 선정 수

DCA_FIXED = [
    {"code": "005930", "monthly_budget": 500_000},   # 삼성전자
    {"code": "360750", "monthly_budget": 300_000},   # TIGER 미국S&P500
]

MOMENTUM_BUY_AMOUNT     = 500_000
GOLDEN_CROSS_BUY_AMOUNT = 1_000_000

MARKET_OPEN  = "09:00"
MARKET_CLOSE = "15:20"


def is_market_hours() -> bool:
    now = datetime.now().strftime("%H:%M")
    return MARKET_OPEN <= now <= MARKET_CLOSE


def is_weekday() -> bool:
    return datetime.now().weekday() < 5


def main():
    logger.info("=" * 55)
    logger.info("KIS 자동매매 시스템 시작 (풀버전)")
    logger.info("=" * 55)

    # ── 컴포넌트 초기화 ────────────────────────────────────
    api      = KISApi()
    notifier = TelegramNotifier()
    rm       = RiskManager(api)
    om       = OrderManager(api, notifier)
    em       = ExitManager(api, om, notifier)

    screener = MarketScreener(api)
    scorer   = QuantScorer()

    momentum = MomentumStrategy(api, om, rm, notifier)
    momentum.buy_amount = MOMENTUM_BUY_AMOUNT

    gc_strategy = GoldenCrossStrategy(api, om, rm, notifier)
    gc_strategy.buy_amount = GOLDEN_CROSS_BUY_AMOUNT

    dca = DCAStrategy(api, om, rm, notifier)
    for t in DCA_FIXED:
        dca.add_target(t["code"], t["monthly_budget"])

    # 트레일링 스탑 / 매도 설정
    em.set_trailing_stop(pct=0.05, min_profit=0.03)  # 고점 -5%, +3% 이후 활성
    em.set_max_hold_days(20)                          # 20일 초과 손실보유 → 청산
    em.set_eod_profit(0.03)                           # 장 마감 전 +3% 익절

    notifier.send("자동매매 시스템 시작 (풀버전)")

    # ── 스케줄 함수 정의 ───────────────────────────────────

    def morning_scan():
        """08:30 — 종목 자동 발굴 + 퀀트 스코어링"""
        if not is_weekday():
            return
        logger.info("[모닝스캔] 시작")
        try:
            screened  = screener.top_n(n=SCREEN_TOP_N, conditions=SCREEN_CONDITIONS)
            codes     = [s["code"] for s in screened]
            logger.info(f"[스크리너] {len(codes)}개 후보 발굴")

            picks     = scorer.top_picks(codes, n=QUANT_TOP_N)
            top_codes = [p["code"] for p in picks]
            logger.info(f"[퀀트] 최종 선정: {top_codes}")

            lines = ["<b>오늘의 자동 추천 종목</b>"]
            for p in picks:
                lines.append(
                    f"  {p['name']}({p['code']}) 총점:{p['total_score']} "
                    f"[모멘텀:{p['momentum']} 재무:{p['finance']} 기관:{p['institution']}]"
                )
            notifier.send("\n".join(lines))

            momentum.add_watchlist(top_codes)
            gc_strategy.add_watchlist(top_codes)

        except Exception as e:
            logger.error(f"[모닝스캔] 오류: {e}")
            notifier.send_alert("모닝스캔 오류", str(e))

    def morning_init():
        """09:00 — 리스크 일일 초기화"""
        if not is_weekday():
            return
        rm.initialize_day()
        notifier.send_daily_report(api)

    def run_strategies():
        """5분마다 — 모멘텀 + 골든크로스 전략 실행"""
        if not (is_weekday() and is_market_hours()):
            return
        momentum.run()
        gc_strategy.run()

    def run_dca():
        """09:10 — DCA 분할매수"""
        if not is_weekday():
            return
        dca.run()

    def check_exits():
        """1분마다 — 트레일링스탑 / 손절익절 체크"""
        if not (is_weekday() and is_market_hours()):
            return
        em.execute_exits()
        signals = rm.check_exit_signals()
        for sig in signals:
            logger.info(f"[리스크] {sig['code']} 청산: {sig['reason']}")
            om.market_sell(sig["code"], sig["qty"], reason=sig["reason"])

    def evening_report():
        """15:30 — 일일 결과 리포트"""
        if not is_weekday():
            return
        notifier.send_daily_report(api)

    # ── 스케줄 등록 ────────────────────────────────────────
    schedule.every().day.at("08:30").do(morning_scan)
    schedule.every().day.at("09:00").do(morning_init)
    schedule.every().day.at("09:10").do(run_dca)
    schedule.every(5).minutes.do(run_strategies)
    schedule.every(1).minutes.do(check_exits)
    schedule.every().day.at("15:30").do(evening_report)

    logger.info("스케줄러 시작. Ctrl+C 로 종료.")

    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except KeyboardInterrupt:
            logger.info("시스템 종료")
            notifier.send("자동매매 시스템 종료됨")
            break
        except Exception as e:
            logger.error(f"메인 루프 오류: {e}")
            notifier.send_alert("시스템 오류", str(e))
            time.sleep(30)


if __name__ == "__main__":
    main()
