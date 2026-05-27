"""
백테스트 실행 스크립트
실행: python backtest_run.py
"""
from dotenv import load_dotenv
load_dotenv()

from execution.kis_api   import KISApi
from backtest.backtester import Backtester


def main():
    api  = KISApi()
    bt   = Backtester(initial_cash=10_000_000)

    print("백테스트 대상 종목을 입력하세요 (예: 005930)")
    code = input("종목코드: ").strip() or "005930"

    print(f"\n{code} 일봉 데이터 수집 중...")
    ohlcv = api.get_ohlcv(code, period="D", count=260)
    print(f"  {len(ohlcv)}일 데이터 수집 완료")

    print("\n[골든크로스 5/20] 백테스트 실행...")
    result = bt.run_golden_cross(ohlcv, fast=5, slow=20, buy_amount=1_000_000)
    bt.print_report(result)


if __name__ == "__main__":
    main()
