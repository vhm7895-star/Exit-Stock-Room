from dotenv import load_dotenv
load_dotenv()

from execution.kis_api import KISApi

api     = KISApi()
balance = api.get_balance()
summary = balance["summary"]
holdings = balance["holdings"]

total    = int(summary.get("tot_evlu_amt", 0))
cash     = int(summary.get("dnca_tot_amt", 0))
profit   = int(summary.get("evlu_pfls_smtl_amt", 0))
profit_rt = float(summary.get("asst_icdc_erng_rt", 0))

print("=" * 40)
print("계좌 잔고 현황")
print("=" * 40)
print(f"총 평가금액 : {total:>15,} 원")
print(f"주문가능현금 : {cash:>15,} 원")
print(f"평가손익    : {profit:>+15,} 원 ({profit_rt:+.2f}%)")
print()

if holdings:
    print("[보유 종목]")
    for h in holdings:
        if int(h.get("hldg_qty", 0)) <= 0:
            continue
        name  = h.get("prdt_name", h["pdno"])
        code  = h["pdno"]
        qty   = int(h["hldg_qty"])
        avg   = float(h.get("pchs_avg_pric", 0))
        curr  = int(h.get("prpr", 0))
        pnl   = float(h.get("evlu_pfls_rt", 0))
        evlu  = int(h.get("evlu_amt", 0))
        print(f"  {name}({code}) {qty}주 | 평균:{avg:,.0f} 현재:{curr:,} | {pnl:+.2f}% | 평가:{evlu:,}원")
else:
    print("보유 종목 없음")

print("=" * 40)
