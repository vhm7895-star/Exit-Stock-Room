"""
5만원 이하 매수 가능 종목 스크리닝
"""
from dotenv import load_dotenv
load_dotenv()

from pykrx import stock as pykrx
from datetime import datetime, timedelta
import pandas as pd

today  = datetime.now().strftime("%Y%m%d")
start  = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
budget = 50_000

print("=" * 55)
print(f"5만원 이하 매수 가능 종목 스크리닝 중... (잠시 대기)")
print("=" * 55)

# 관심 종목 후보 (ETF + 우량주 중 소액 가능한 것들)
candidates = {
    "069500": "KODEX 200",
    "360750": "TIGER 미국S&P500",
    "102110": "TIGER 200",
    "114800": "KODEX 인버스",
    "233740": "KODEX 코스닥150레버리지",
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035720": "카카오",
    "035420": "NAVER",
    "068270": "셀트리온",
    "028260": "삼성물산",
    "032830": "삼성생명",
    "003550": "LG",
    "009150": "삼성전기",
    "018260": "삼성에스디에스",
    "096770": "SK이노베이션",
    "017670": "SK텔레콤",
    "030200": "KT",
    "015760": "한국전력",
    "011200": "HMM",
}

results = []

for code, name in candidates.items():
    try:
        df = pykrx.get_market_ohlcv(start, today, code)
        if df.empty:
            continue

        price     = int(df["종가"].iloc[-1])
        vol_avg   = int(df["거래량"].iloc[-6:-1].mean())
        vol_today = int(df["거래량"].iloc[-1])
        ret_1m    = (df["종가"].iloc[-1] / df["종가"].iloc[0] - 1) * 100

        if price > budget:
            continue

        shares = budget // price

        # 재무 데이터
        fund = pykrx.get_market_fundamental(today, today, code)
        per  = float(fund["PER"].iloc[0]) if not fund.empty else 0
        pbr  = float(fund["PBR"].iloc[0]) if not fund.empty else 0

        results.append({
            "코드":      code,
            "종목명":    name,
            "현재가":    price,
            "매수가능":  f"{shares}주",
            "1개월수익": f"{ret_1m:+.1f}%",
            "거래량비율": f"{vol_today/vol_avg:.1f}x" if vol_avg > 0 else "-",
            "PER":       f"{per:.1f}" if per > 0 else "-",
            "PBR":       f"{pbr:.1f}" if pbr > 0 else "-",
        })
    except Exception:
        continue

if not results:
    print("조건에 맞는 종목이 없습니다.")
else:
    df_result = pd.DataFrame(results)
    print(df_result.to_string(index=False))
    print()
    print("※ 투자 판단은 본인 책임입니다. 참고 용도로만 활용하세요.")
