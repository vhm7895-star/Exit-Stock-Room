"""
KIS 자동매매 웹 대시보드
실행: python web_dashboard.py
접속: http://localhost:5000
"""
import sys, os, re, html, xml.etree.ElementTree as ET
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pykrx import stock as pykrx
import requests as req_lib
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import threading

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))
from execution.kis_api import KISApi

app = Flask(__name__)
api = KISApi()
_market_snapshot_cache = {"ts": None, "items": []}
_quote_cache = {}
_news_reason_cache = {}

# ── 국내 주요 종목 (정적 리스트) ──────────────────────────────
DOMESTIC_STOCKS = [
    # KOSPI 대형주
    {"code":"005930","name":"삼성전자","market":"KOSPI"},
    {"code":"000660","name":"SK하이닉스","market":"KOSPI"},
    {"code":"207940","name":"삼성바이오로직스","market":"KOSPI"},
    {"code":"005380","name":"현대차","market":"KOSPI"},
    {"code":"000270","name":"기아","market":"KOSPI"},
    {"code":"373220","name":"LG에너지솔루션","market":"KOSPI"},
    {"code":"068270","name":"셀트리온","market":"KOSPI"},
    {"code":"105560","name":"KB금융","market":"KOSPI"},
    {"code":"055550","name":"신한지주","market":"KOSPI"},
    {"code":"012330","name":"현대모비스","market":"KOSPI"},
    {"code":"028260","name":"삼성물산","market":"KOSPI"},
    {"code":"066570","name":"LG전자","market":"KOSPI"},
    {"code":"032830","name":"삼성생명","market":"KOSPI"},
    {"code":"086790","name":"하나금융지주","market":"KOSPI"},
    {"code":"015760","name":"한국전력","market":"KOSPI"},
    {"code":"034020","name":"두산에너빌리티","market":"KOSPI"},
    {"code":"003550","name":"LG","market":"KOSPI"},
    {"code":"009150","name":"삼성전기","market":"KOSPI"},
    {"code":"018260","name":"삼성에스디에스","market":"KOSPI"},
    {"code":"096770","name":"SK이노베이션","market":"KOSPI"},
    {"code":"017670","name":"SK텔레콤","market":"KOSPI"},
    {"code":"030200","name":"KT","market":"KOSPI"},
    {"code":"011200","name":"HMM","market":"KOSPI"},
    {"code":"032640","name":"LG유플러스","market":"KOSPI"},
    {"code":"035420","name":"NAVER","market":"KOSPI"},
    {"code":"035720","name":"카카오","market":"KOSPI"},
    {"code":"051910","name":"LG화학","market":"KOSPI"},
    {"code":"006400","name":"삼성SDI","market":"KOSPI"},
    {"code":"090430","name":"아모레퍼시픽","market":"KOSPI"},
    {"code":"011170","name":"롯데케미칼","market":"KOSPI"},
    {"code":"010130","name":"고려아연","market":"KOSPI"},
    {"code":"042660","name":"한화오션","market":"KOSPI"},
    {"code":"267250","name":"HD현대중공업","market":"KOSPI"},
    {"code":"329180","name":"현대중공업","market":"KOSPI"},
    {"code":"009540","name":"HD한국조선해양","market":"KOSPI"},
    {"code":"003490","name":"대한항공","market":"KOSPI"},
    {"code":"004020","name":"현대제철","market":"KOSPI"},
    {"code":"005490","name":"POSCO홀딩스","market":"KOSPI"},
    {"code":"010950","name":"S-Oil","market":"KOSPI"},
    {"code":"139480","name":"이마트","market":"KOSPI"},
    {"code":"097950","name":"CJ제일제당","market":"KOSPI"},
    {"code":"004990","name":"롯데지주","market":"KOSPI"},
    {"code":"016360","name":"삼성증권","market":"KOSPI"},
    {"code":"024110","name":"기업은행","market":"KOSPI"},
    {"code":"000100","name":"유한양행","market":"KOSPI"},
    {"code":"128940","name":"한미약품","market":"KOSPI"},
    {"code":"161390","name":"한국타이어앤테크놀로지","market":"KOSPI"},
    {"code":"000810","name":"삼성화재","market":"KOSPI"},
    {"code":"078930","name":"GS","market":"KOSPI"},
    {"code":"071050","name":"한국금융지주","market":"KOSPI"},
    {"code":"323410","name":"카카오뱅크","market":"KOSPI"},
    {"code":"377300","name":"카카오페이","market":"KOSPI"},
    {"code":"352820","name":"하이브","market":"KOSPI"},
    {"code":"030000","name":"제일기획","market":"KOSPI"},
    {"code":"088350","name":"한화생명","market":"KOSPI"},
    {"code":"000720","name":"현대건설","market":"KOSPI"},
    {"code":"028050","name":"삼성엔지니어링","market":"KOSPI"},
    {"code":"047050","name":"포스코인터내셔널","market":"KOSPI"},
    {"code":"009830","name":"한화솔루션","market":"KOSPI"},
    {"code":"000080","name":"하이트진로","market":"KOSPI"},
    {"code":"033780","name":"KT&G","market":"KOSPI"},
    {"code":"003670","name":"포스코퓨처엠","market":"KOSPI"},
    {"code":"010140","name":"삼성중공업","market":"KOSPI"},
    {"code":"002790","name":"아모레G","market":"KOSPI"},
    {"code":"071840","name":"롯데하이마트","market":"KOSPI"},
    {"code":"023530","name":"롯데쇼핑","market":"KOSPI"},
    {"code":"004170","name":"신세계","market":"KOSPI"},
    {"code":"069960","name":"현대백화점","market":"KOSPI"},
    {"code":"000240","name":"한국앤컴퍼니","market":"KOSPI"},
    {"code":"002380","name":"KCC","market":"KOSPI"},
    {"code":"010060","name":"OCI홀딩스","market":"KOSPI"},
    {"code":"001040","name":"CJ","market":"KOSPI"},
    # KOSPI ETF
    {"code":"069500","name":"KODEX 200","market":"ETF"},
    {"code":"102110","name":"TIGER 200","market":"ETF"},
    {"code":"360750","name":"TIGER 미국S&P500","market":"ETF"},
    {"code":"133690","name":"TIGER 미국나스닥100","market":"ETF"},
    {"code":"364970","name":"TIGER 미국나스닥100(H)","market":"ETF"},
    {"code":"122630","name":"KODEX 레버리지","market":"ETF"},
    {"code":"114800","name":"KODEX 인버스","market":"ETF"},
    {"code":"233740","name":"KODEX 코스닥150레버리지","market":"ETF"},
    {"code":"251340","name":"KODEX 코스닥150","market":"ETF"},
    {"code":"091160","name":"KODEX 반도체","market":"ETF"},
    {"code":"091180","name":"KODEX 자동차","market":"ETF"},
    {"code":"305080","name":"TIGER 차이나전기차","market":"ETF"},
    {"code":"411060","name":"ACE 미국S&P500","market":"ETF"},
    {"code":"287310","name":"KODEX 삼성그룹","market":"ETF"},
    {"code":"371460","name":"TIGER 미국채10년선물","market":"ETF"},
    {"code":"229200","name":"KODEX 코스닥150","market":"ETF"},
    {"code":"152100","name":"ARIRANG 200","market":"ETF"},
    {"code":"kodex_gold","name":"KODEX 골드선물(H)","market":"ETF"},
    # KOSDAQ 주요 종목
    {"code":"247540","name":"에코프로비엠","market":"KOSDAQ"},
    {"code":"086520","name":"에코프로","market":"KOSDAQ"},
    {"code":"196170","name":"알테오젠","market":"KOSDAQ"},
    {"code":"112040","name":"위메이드","market":"KOSDAQ"},
    {"code":"263750","name":"펄어비스","market":"KOSDAQ"},
    {"code":"293490","name":"카카오게임즈","market":"KOSDAQ"},
    {"code":"035900","name":"JYP Ent.","market":"KOSDAQ"},
    {"code":"041510","name":"에스엠","market":"KOSDAQ"},
    {"code":"091990","name":"셀트리온헬스케어","market":"KOSDAQ"},
    {"code":"141080","name":"레고켐바이오","market":"KOSDAQ"},
    {"code":"145020","name":"휴젤","market":"KOSDAQ"},
    {"code":"357780","name":"솔브레인","market":"KOSDAQ"},
    {"code":"166090","name":"하나머티리얼즈","market":"KOSDAQ"},
    {"code":"000660","name":"SK하이닉스","market":"KOSPI"},
    {"code":"278280","name":"천보","market":"KOSDAQ"},
    {"code":"214420","name":"토비스","market":"KOSDAQ"},
    {"code":"024090","name":"디씨엠","market":"KOSDAQ"},
    {"code":"240810","name":"원익IPS","market":"KOSDAQ"},
    {"code":"036570","name":"엔씨소프트","market":"KOSDAQ"},
    {"code":"251270","name":"넷마블","market":"KOSPI"},
    {"code":"376300","name":"디어유","market":"KOSDAQ"},
    {"code":"048260","name":"오스템임플란트","market":"KOSDAQ"},
    {"code":"237690","name":"에스티팜","market":"KOSDAQ"},
    {"code":"066970","name":"엘앤에프","market":"KOSDAQ"},
    {"code":"397030","name":"에코프로머티리얼즈","market":"KOSDAQ"},
    {"code":"039030","name":"이오테크닉스","market":"KOSDAQ"},
    {"code":"053800","name":"안랩","market":"KOSDAQ"},
    {"code":"095340","name":"ISC","market":"KOSDAQ"},
    {"code":"058470","name":"리노공업","market":"KOSDAQ"},
    {"code":"064760","name":"티씨케이","market":"KOSDAQ"},
    {"code":"052690","name":"한전기술","market":"KOSDAQ"},
    {"code":"950130","name":"엑스페릭스","market":"KOSDAQ"},
]
domestic_stocks   = DOMESTIC_STOCKS.copy()
domestic_loaded   = False

# ── 해외 주요 종목 (내장 리스트) ───────────────────────────────
OVERSEAS_STOCKS = [
    # ── 미국 NASDAQ ──
    {"code":"AAPL",  "name":"Apple",            "excd":"NAS","market":"NASDAQ"},
    {"code":"MSFT",  "name":"Microsoft",         "excd":"NAS","market":"NASDAQ"},
    {"code":"NVDA",  "name":"NVIDIA",            "excd":"NAS","market":"NASDAQ"},
    {"code":"AMZN",  "name":"Amazon",            "excd":"NAS","market":"NASDAQ"},
    {"code":"META",  "name":"Meta Platforms",    "excd":"NAS","market":"NASDAQ"},
    {"code":"GOOGL", "name":"Alphabet (A)",      "excd":"NAS","market":"NASDAQ"},
    {"code":"GOOG",  "name":"Alphabet (C)",      "excd":"NAS","market":"NASDAQ"},
    {"code":"TSLA",  "name":"Tesla",             "excd":"NAS","market":"NASDAQ"},
    {"code":"AVGO",  "name":"Broadcom",          "excd":"NAS","market":"NASDAQ"},
    {"code":"AMD",   "name":"AMD",               "excd":"NAS","market":"NASDAQ"},
    {"code":"INTC",  "name":"Intel",             "excd":"NAS","market":"NASDAQ"},
    {"code":"QCOM",  "name":"Qualcomm",          "excd":"NAS","market":"NASDAQ"},
    {"code":"CSCO",  "name":"Cisco",             "excd":"NAS","market":"NASDAQ"},
    {"code":"ADBE",  "name":"Adobe",             "excd":"NAS","market":"NASDAQ"},
    {"code":"NFLX",  "name":"Netflix",           "excd":"NAS","market":"NASDAQ"},
    {"code":"PYPL",  "name":"PayPal",            "excd":"NAS","market":"NASDAQ"},
    {"code":"UBER",  "name":"Uber",              "excd":"NAS","market":"NASDAQ"},
    {"code":"ABNB",  "name":"Airbnb",            "excd":"NAS","market":"NASDAQ"},
    {"code":"SHOP",  "name":"Shopify",           "excd":"NAS","market":"NASDAQ"},
    {"code":"SNOW",  "name":"Snowflake",         "excd":"NAS","market":"NASDAQ"},
    {"code":"CRWD",  "name":"CrowdStrike",       "excd":"NAS","market":"NASDAQ"},
    {"code":"PLTR",  "name":"Palantir",          "excd":"NAS","market":"NASDAQ"},
    {"code":"NET",   "name":"Cloudflare",        "excd":"NAS","market":"NASDAQ"},
    {"code":"DDOG",  "name":"Datadog",           "excd":"NAS","market":"NASDAQ"},
    {"code":"ZS",    "name":"Zscaler",           "excd":"NAS","market":"NASDAQ"},
    {"code":"MDB",   "name":"MongoDB",           "excd":"NAS","market":"NASDAQ"},
    {"code":"MSTR",  "name":"MicroStrategy",     "excd":"NAS","market":"NASDAQ"},
    {"code":"COIN",  "name":"Coinbase",          "excd":"NAS","market":"NASDAQ"},
    {"code":"RBLX",  "name":"Roblox",            "excd":"NAS","market":"NASDAQ"},
    {"code":"SPOT",  "name":"Spotify",           "excd":"NAS","market":"NASDAQ"},
    {"code":"AMGN",  "name":"Amgen",             "excd":"NAS","market":"NASDAQ"},
    {"code":"GILD",  "name":"Gilead Sciences",   "excd":"NAS","market":"NASDAQ"},
    {"code":"BIIB",  "name":"Biogen",            "excd":"NAS","market":"NASDAQ"},
    {"code":"REGN",  "name":"Regeneron",         "excd":"NAS","market":"NASDAQ"},
    {"code":"VRTX",  "name":"Vertex Pharma",     "excd":"NAS","market":"NASDAQ"},
    {"code":"ISRG",  "name":"Intuitive Surgical","excd":"NAS","market":"NASDAQ"},
    {"code":"ASML",  "name":"ASML Holding",      "excd":"NAS","market":"NASDAQ"},
    {"code":"AMAT",  "name":"Applied Materials", "excd":"NAS","market":"NASDAQ"},
    {"code":"LRCX",  "name":"Lam Research",      "excd":"NAS","market":"NASDAQ"},
    {"code":"KLAC",  "name":"KLA Corporation",   "excd":"NAS","market":"NASDAQ"},
    # ── 미국 NYSE ──
    {"code":"BRK.B", "name":"Berkshire Hathaway","excd":"NYS","market":"NYSE"},
    {"code":"JPM",   "name":"JPMorgan Chase",    "excd":"NYS","market":"NYSE"},
    {"code":"V",     "name":"Visa",              "excd":"NYS","market":"NYSE"},
    {"code":"MA",    "name":"Mastercard",        "excd":"NYS","market":"NYSE"},
    {"code":"XOM",   "name":"ExxonMobil",        "excd":"NYS","market":"NYSE"},
    {"code":"CVX",   "name":"Chevron",           "excd":"NYS","market":"NYSE"},
    {"code":"JNJ",   "name":"Johnson & Johnson", "excd":"NYS","market":"NYSE"},
    {"code":"PG",    "name":"Procter & Gamble",  "excd":"NYS","market":"NYSE"},
    {"code":"UNH",   "name":"UnitedHealth",      "excd":"NYS","market":"NYSE"},
    {"code":"LLY",   "name":"Eli Lilly",         "excd":"NYS","market":"NYSE"},
    {"code":"GS",    "name":"Goldman Sachs",     "excd":"NYS","market":"NYSE"},
    {"code":"MS",    "name":"Morgan Stanley",    "excd":"NYS","market":"NYSE"},
    {"code":"BAC",   "name":"Bank of America",   "excd":"NYS","market":"NYSE"},
    {"code":"WFC",   "name":"Wells Fargo",       "excd":"NYS","market":"NYSE"},
    {"code":"AXP",   "name":"American Express",  "excd":"NYS","market":"NYSE"},
    {"code":"BLK",   "name":"BlackRock",         "excd":"NYS","market":"NYSE"},
    {"code":"KO",    "name":"Coca-Cola",         "excd":"NYS","market":"NYSE"},
    {"code":"PEP",   "name":"PepsiCo",           "excd":"NYS","market":"NYSE"},
    {"code":"PM",    "name":"Philip Morris",     "excd":"NYS","market":"NYSE"},
    {"code":"MCD",   "name":"McDonald's",        "excd":"NYS","market":"NYSE"},
    {"code":"DIS",   "name":"Walt Disney",       "excd":"NYS","market":"NYSE"},
    {"code":"BA",    "name":"Boeing",            "excd":"NYS","market":"NYSE"},
    {"code":"GE",    "name":"GE Aerospace",      "excd":"NYS","market":"NYSE"},
    {"code":"CAT",   "name":"Caterpillar",       "excd":"NYS","market":"NYSE"},
    {"code":"HON",   "name":"Honeywell",         "excd":"NYS","market":"NYSE"},
    {"code":"UPS",   "name":"UPS",               "excd":"NYS","market":"NYSE"},
    {"code":"FDX",   "name":"FedEx",             "excd":"NYS","market":"NYSE"},
    {"code":"LMT",   "name":"Lockheed Martin",   "excd":"NYS","market":"NYSE"},
    {"code":"RTX",   "name":"RTX Corporation",   "excd":"NYS","market":"NYSE"},
    {"code":"NEE",   "name":"NextEra Energy",    "excd":"NYS","market":"NYSE"},
    {"code":"NEM",   "name":"Newmont",           "excd":"NYS","market":"NYSE"},
    {"code":"FCX",   "name":"Freeport-McMoRan",  "excd":"NYS","market":"NYSE"},
    {"code":"WMT",   "name":"Walmart",           "excd":"NYS","market":"NYSE"},
    {"code":"TGT",   "name":"Target",            "excd":"NYS","market":"NYSE"},
    {"code":"COST",  "name":"Costco",            "excd":"NAS","market":"NASDAQ"},
    {"code":"HD",    "name":"Home Depot",        "excd":"NYS","market":"NYSE"},
    {"code":"NKE",   "name":"Nike",              "excd":"NYS","market":"NYSE"},
    {"code":"SBUX",  "name":"Starbucks",         "excd":"NAS","market":"NASDAQ"},
    {"code":"PFE",   "name":"Pfizer",            "excd":"NYS","market":"NYSE"},
    {"code":"MRK",   "name":"Merck",             "excd":"NYS","market":"NYSE"},
    {"code":"ABT",   "name":"Abbott Labs",       "excd":"NYS","market":"NYSE"},
    {"code":"TMO",   "name":"Thermo Fisher",     "excd":"NYS","market":"NYSE"},
    {"code":"DHR",   "name":"Danaher",           "excd":"NYS","market":"NYSE"},
    {"code":"SPY",   "name":"SPDR S&P500 ETF",   "excd":"NYS","market":"NYSE"},
    {"code":"QQQ",   "name":"Invesco QQQ ETF",   "excd":"NAS","market":"NASDAQ"},
    {"code":"IWM",   "name":"iShares Russell2000","excd":"NYS","market":"NYSE"},
    {"code":"GLD",   "name":"SPDR Gold ETF",     "excd":"NYS","market":"NYSE"},
    {"code":"TLT",   "name":"iShares 20Y Bond",  "excd":"NAS","market":"NASDAQ"},
    {"code":"SOXL",  "name":"반도체 3x ETF",      "excd":"NYS","market":"NYSE"},
    {"code":"TQQQ",  "name":"나스닥 3x ETF",       "excd":"NAS","market":"NASDAQ"},
    # ── 일본 TSE ──
    {"code":"7203",  "name":"Toyota (도요타)",    "excd":"TSE","market":"도쿄"},
    {"code":"6758",  "name":"Sony (소니)",        "excd":"TSE","market":"도쿄"},
    {"code":"9984",  "name":"SoftBank (소프트뱅크)","excd":"TSE","market":"도쿄"},
    {"code":"6861",  "name":"Keyence (키엔스)",   "excd":"TSE","market":"도쿄"},
    {"code":"7267",  "name":"Honda (혼다)",       "excd":"TSE","market":"도쿄"},
    {"code":"6501",  "name":"Hitachi (히타치)",   "excd":"TSE","market":"도쿄"},
    {"code":"6367",  "name":"Daikin (다이킨)",    "excd":"TSE","market":"도쿄"},
    {"code":"4063",  "name":"Shin-Etsu (신에츠화학)","excd":"TSE","market":"도쿄"},
    {"code":"8306",  "name":"MUFG (미쓰비시UFJ)", "excd":"TSE","market":"도쿄"},
    {"code":"9432",  "name":"NTT",               "excd":"TSE","market":"도쿄"},
    {"code":"6954",  "name":"Fanuc (화낙)",       "excd":"TSE","market":"도쿄"},
    {"code":"4568",  "name":"Daiichi Sankyo",     "excd":"TSE","market":"도쿄"},
    {"code":"2914",  "name":"Japan Tobacco (JT)", "excd":"TSE","market":"도쿄"},
    {"code":"8035",  "name":"Tokyo Electron",     "excd":"TSE","market":"도쿄"},
    # ── 홍콩 HKS ──
    {"code":"00700", "name":"Tencent (텐센트)",   "excd":"HKS","market":"홍콩"},
    {"code":"09988", "name":"Alibaba (알리바바)",  "excd":"HKS","market":"홍콩"},
    {"code":"03690", "name":"Meituan (메이퇀)",   "excd":"HKS","market":"홍콩"},
    {"code":"09999", "name":"NetEase (넷이즈)",   "excd":"HKS","market":"홍콩"},
    {"code":"01810", "name":"Xiaomi (샤오미)",    "excd":"HKS","market":"홍콩"},
    {"code":"00941", "name":"China Mobile",       "excd":"HKS","market":"홍콩"},
    {"code":"02318", "name":"Ping An Insurance",  "excd":"HKS","market":"홍콩"},
    {"code":"00005", "name":"HSBC Holdings",      "excd":"HKS","market":"홍콩"},
    {"code":"02382", "name":"Sunny Optical",      "excd":"HKS","market":"홍콩"},
    {"code":"06862", "name":"Haidilao (하이디라오)","excd":"HKS","market":"홍콩"},
]

EXCD_TO_EXCG = {
    "NAS": "NASD", "NYS": "NYSE", "AMS": "AMEX",
    "TSE": "TKSE", "HKS": "SEHK", "SHS": "SHAA", "SZS": "SZAA",
}


def _clean_html_cell(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _load_krx_listed_stocks():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
    res = req_lib.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()
    text = res.content.decode("euc-kr", errors="ignore")
    rows = []
    seen = set()
    market_map = {"유가증권": "KOSPI", "유가": "KOSPI", "코스닥": "KOSDAQ", "코넥스": "KONEX"}
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S | re.I)
        if len(cells) < 3:
            continue
        name = _clean_html_cell(cells[0])
        market_ko = _clean_html_cell(cells[1])
        code = _clean_html_cell(cells[2]).zfill(6)
        if not code.isdigit() or code in seen:
            continue
        seen.add(code)
        rows.append({"code": code, "name": name, "market": market_map.get(market_ko, market_ko or "KRX")})
    return rows


def load_domestic_stocks():
    global domestic_stocks, domestic_loaded
    try:
        rows = _load_krx_listed_stocks()
        if not rows:
            raise RuntimeError("KRX listed stock list is empty")

        # Keep hand-curated ETFs/themes even when pykrx omits some ETF aliases.
        by_code = {row["code"]: row for row in rows}
        for stock in DOMESTIC_STOCKS:
            by_code.setdefault(stock["code"], stock)

        domestic_stocks = sorted(by_code.values(), key=lambda x: (x.get("market", ""), x.get("name", "")))
        domestic_loaded = True
        print(f"[stocks] domestic search universe loaded: {len(domestic_stocks)}")
    except Exception as e:
        domestic_stocks = DOMESTIC_STOCKS.copy()
        domestic_loaded = True
        print(f"[stocks] fallback domestic list: {e}")


threading.Thread(target=load_domestic_stocks, daemon=True).start()

CANDIDATES = {
    "069500": "KODEX 200",      "360750": "TIGER 미국S&P500",
    "102110": "TIGER 200",      "114800": "KODEX 인버스",
    "233740": "KODEX 코스닥150레버리지",
    "005930": "삼성전자",        "000660": "SK하이닉스",
    "035720": "카카오",          "035420": "NAVER",
    "068270": "셀트리온",        "015760": "한국전력",
    "011200": "HMM",            "017670": "SK텔레콤",
    "030200": "KT",             "096770": "SK이노베이션",
}

# ── 테마별 종목 맵 ───────────────────────────────────────────────
THEME_MAP = {
    "반도체": [
        {"code":"005930","name":"삼성전자","market":"KOSPI"},
        {"code":"000660","name":"SK하이닉스","market":"KOSPI"},
        {"code":"009150","name":"삼성전기","market":"KOSPI"},
        {"code":"240810","name":"원익IPS","market":"KOSDAQ"},
        {"code":"357780","name":"솔브레인","market":"KOSDAQ"},
        {"code":"058470","name":"리노공업","market":"KOSDAQ"},
        {"code":"039030","name":"이오테크닉스","market":"KOSDAQ"},
        {"code":"166090","name":"하나머티리얼즈","market":"KOSDAQ"},
        {"code":"091160","name":"KODEX 반도체","market":"ETF"},
        {"code":"064760","name":"티씨케이","market":"KOSDAQ"},
        {"code":"095340","name":"ISC","market":"KOSDAQ"},
        {"code":"000990","name":"DB하이텍","market":"KOSPI"},
    ],
    "2차전지": [
        {"code":"373220","name":"LG에너지솔루션","market":"KOSPI"},
        {"code":"006400","name":"삼성SDI","market":"KOSPI"},
        {"code":"096770","name":"SK이노베이션","market":"KOSPI"},
        {"code":"086520","name":"에코프로","market":"KOSDAQ"},
        {"code":"247540","name":"에코프로비엠","market":"KOSDAQ"},
        {"code":"003670","name":"포스코퓨처엠","market":"KOSPI"},
        {"code":"066970","name":"엘앤에프","market":"KOSDAQ"},
        {"code":"278280","name":"천보","market":"KOSDAQ"},
        {"code":"397030","name":"에코프로머티리얼즈","market":"KOSDAQ"},
    ],
    "배터리": [
        {"code":"373220","name":"LG에너지솔루션","market":"KOSPI"},
        {"code":"006400","name":"삼성SDI","market":"KOSPI"},
        {"code":"086520","name":"에코프로","market":"KOSDAQ"},
        {"code":"247540","name":"에코프로비엠","market":"KOSDAQ"},
        {"code":"003670","name":"포스코퓨처엠","market":"KOSPI"},
        {"code":"066970","name":"엘앤에프","market":"KOSDAQ"},
    ],
    "바이오": [
        {"code":"068270","name":"셀트리온","market":"KOSPI"},
        {"code":"207940","name":"삼성바이오로직스","market":"KOSPI"},
        {"code":"128940","name":"한미약품","market":"KOSPI"},
        {"code":"000100","name":"유한양행","market":"KOSPI"},
        {"code":"196170","name":"알테오젠","market":"KOSDAQ"},
        {"code":"141080","name":"레고켐바이오","market":"KOSDAQ"},
        {"code":"237690","name":"에스티팜","market":"KOSDAQ"},
        {"code":"145020","name":"휴젤","market":"KOSDAQ"},
        {"code":"091990","name":"셀트리온헬스케어","market":"KOSDAQ"},
    ],
    "제약": [
        {"code":"068270","name":"셀트리온","market":"KOSPI"},
        {"code":"207940","name":"삼성바이오로직스","market":"KOSPI"},
        {"code":"128940","name":"한미약품","market":"KOSPI"},
        {"code":"000100","name":"유한양행","market":"KOSPI"},
        {"code":"069620","name":"대웅제약","market":"KOSPI"},
        {"code":"185750","name":"종근당","market":"KOSPI"},
    ],
    "AI": [
        {"code":"035420","name":"NAVER","market":"KOSPI"},
        {"code":"035720","name":"카카오","market":"KOSPI"},
        {"code":"018260","name":"삼성에스디에스","market":"KOSPI"},
        {"code":"017670","name":"SK텔레콤","market":"KOSPI"},
        {"code":"030200","name":"KT","market":"KOSPI"},
        {"code":"053800","name":"안랩","market":"KOSDAQ"},
        {"code":"032640","name":"LG유플러스","market":"KOSPI"},
    ],
    "인공지능": [
        {"code":"035420","name":"NAVER","market":"KOSPI"},
        {"code":"035720","name":"카카오","market":"KOSPI"},
        {"code":"018260","name":"삼성에스디에스","market":"KOSPI"},
        {"code":"017670","name":"SK텔레콤","market":"KOSPI"},
        {"code":"030200","name":"KT","market":"KOSPI"},
    ],
    "자동차": [
        {"code":"005380","name":"현대차","market":"KOSPI"},
        {"code":"000270","name":"기아","market":"KOSPI"},
        {"code":"012330","name":"현대모비스","market":"KOSPI"},
        {"code":"161390","name":"한국타이어앤테크놀로지","market":"KOSPI"},
        {"code":"091180","name":"KODEX 자동차","market":"ETF"},
    ],
    "게임": [
        {"code":"259960","name":"크래프톤","market":"KOSPI"},
        {"code":"036570","name":"엔씨소프트","market":"KOSDAQ"},
        {"code":"293490","name":"카카오게임즈","market":"KOSDAQ"},
        {"code":"263750","name":"펄어비스","market":"KOSDAQ"},
        {"code":"112040","name":"위메이드","market":"KOSDAQ"},
        {"code":"251270","name":"넷마블","market":"KOSPI"},
    ],
    "조선": [
        {"code":"042660","name":"한화오션","market":"KOSPI"},
        {"code":"267250","name":"HD현대중공업","market":"KOSPI"},
        {"code":"009540","name":"HD한국조선해양","market":"KOSPI"},
        {"code":"010140","name":"삼성중공업","market":"KOSPI"},
        {"code":"329180","name":"현대중공업","market":"KOSPI"},
    ],
    "방산": [
        {"code":"012450","name":"한화에어로스페이스","market":"KOSPI"},
        {"code":"047810","name":"한국항공우주","market":"KOSPI"},
        {"code":"272210","name":"한화시스템","market":"KOSPI"},
        {"code":"064350","name":"현대로템","market":"KOSPI"},
    ],
    "방위산업": [
        {"code":"012450","name":"한화에어로스페이스","market":"KOSPI"},
        {"code":"047810","name":"한국항공우주","market":"KOSPI"},
        {"code":"272210","name":"한화시스템","market":"KOSPI"},
        {"code":"064350","name":"현대로템","market":"KOSPI"},
    ],
    "우주": [
        {"code":"012450","name":"한화에어로스페이스","market":"KOSPI"},
        {"code":"047810","name":"한국항공우주","market":"KOSPI"},
        {"code":"272210","name":"한화시스템","market":"KOSPI"},
        {"code":"003490","name":"대한항공","market":"KOSPI"},
        {"code":"093240","name":"AP위성","market":"KOSDAQ"},
        {"code":"049200","name":"컨텍","market":"KOSDAQ"},
    ],
    "항공": [
        {"code":"003490","name":"대한항공","market":"KOSPI"},
        {"code":"012450","name":"한화에어로스페이스","market":"KOSPI"},
        {"code":"047810","name":"한국항공우주","market":"KOSPI"},
        {"code":"272210","name":"한화시스템","market":"KOSPI"},
    ],
    "금융": [
        {"code":"105560","name":"KB금융","market":"KOSPI"},
        {"code":"055550","name":"신한지주","market":"KOSPI"},
        {"code":"086790","name":"하나금융지주","market":"KOSPI"},
        {"code":"024110","name":"기업은행","market":"KOSPI"},
        {"code":"032830","name":"삼성생명","market":"KOSPI"},
        {"code":"000810","name":"삼성화재","market":"KOSPI"},
        {"code":"071050","name":"한국금융지주","market":"KOSPI"},
    ],
    "은행": [
        {"code":"105560","name":"KB금융","market":"KOSPI"},
        {"code":"055550","name":"신한지주","market":"KOSPI"},
        {"code":"086790","name":"하나금융지주","market":"KOSPI"},
        {"code":"024110","name":"기업은행","market":"KOSPI"},
        {"code":"316140","name":"우리금융지주","market":"KOSPI"},
        {"code":"323410","name":"카카오뱅크","market":"KOSPI"},
    ],
    "건설": [
        {"code":"028260","name":"삼성물산","market":"KOSPI"},
        {"code":"000720","name":"현대건설","market":"KOSPI"},
        {"code":"028050","name":"삼성엔지니어링","market":"KOSPI"},
        {"code":"006360","name":"GS건설","market":"KOSPI"},
        {"code":"047040","name":"대우건설","market":"KOSPI"},
    ],
    "에너지": [
        {"code":"015760","name":"한국전력","market":"KOSPI"},
        {"code":"096770","name":"SK이노베이션","market":"KOSPI"},
        {"code":"010950","name":"S-Oil","market":"KOSPI"},
        {"code":"010060","name":"OCI홀딩스","market":"KOSPI"},
        {"code":"009830","name":"한화솔루션","market":"KOSPI"},
        {"code":"034020","name":"두산에너빌리티","market":"KOSPI"},
    ],
    "태양광": [
        {"code":"009830","name":"한화솔루션","market":"KOSPI"},
        {"code":"010060","name":"OCI홀딩스","market":"KOSPI"},
        {"code":"112610","name":"씨에스윈드","market":"KOSPI"},
    ],
    "철강": [
        {"code":"005490","name":"POSCO홀딩스","market":"KOSPI"},
        {"code":"004020","name":"현대제철","market":"KOSPI"},
        {"code":"010130","name":"고려아연","market":"KOSPI"},
    ],
    "화학": [
        {"code":"051910","name":"LG화학","market":"KOSPI"},
        {"code":"011170","name":"롯데케미칼","market":"KOSPI"},
        {"code":"009830","name":"한화솔루션","market":"KOSPI"},
    ],
    "엔터": [
        {"code":"352820","name":"하이브","market":"KOSPI"},
        {"code":"041510","name":"에스엠","market":"KOSDAQ"},
        {"code":"035900","name":"JYP Ent.","market":"KOSDAQ"},
        {"code":"122870","name":"YG엔터테인먼트","market":"KOSDAQ"},
        {"code":"376300","name":"디어유","market":"KOSDAQ"},
    ],
    "엔터테인먼트": [
        {"code":"352820","name":"하이브","market":"KOSPI"},
        {"code":"041510","name":"에스엠","market":"KOSDAQ"},
        {"code":"035900","name":"JYP Ent.","market":"KOSDAQ"},
        {"code":"122870","name":"YG엔터테인먼트","market":"KOSDAQ"},
        {"code":"376300","name":"디어유","market":"KOSDAQ"},
    ],
    "로봇": [
        {"code":"277810","name":"레인보우로보틱스","market":"KOSDAQ"},
        {"code":"056080","name":"유진로봇","market":"KOSDAQ"},
        {"code":"108490","name":"로보티즈","market":"KOSDAQ"},
    ],
    "식품": [
        {"code":"097950","name":"CJ제일제당","market":"KOSPI"},
        {"code":"003230","name":"삼양식품","market":"KOSPI"},
        {"code":"271560","name":"오리온","market":"KOSPI"},
        {"code":"004370","name":"농심","market":"KOSPI"},
        {"code":"000080","name":"하이트진로","market":"KOSPI"},
        {"code":"280360","name":"롯데웰푸드","market":"KOSPI"},
        {"code":"033780","name":"KT&G","market":"KOSPI"},
    ],
    "음식": [
        {"code":"097950","name":"CJ제일제당","market":"KOSPI"},
        {"code":"003230","name":"삼양식품","market":"KOSPI"},
        {"code":"271560","name":"오리온","market":"KOSPI"},
        {"code":"004370","name":"농심","market":"KOSPI"},
        {"code":"000080","name":"하이트진로","market":"KOSPI"},
    ],
    "화장품": [
        {"code":"090430","name":"아모레퍼시픽","market":"KOSPI"},
        {"code":"002790","name":"아모레G","market":"KOSPI"},
        {"code":"051900","name":"LG생활건강","market":"KOSPI"},
        {"code":"192820","name":"코스맥스","market":"KOSPI"},
        {"code":"161890","name":"한국콜마","market":"KOSPI"},
    ],
    "코스메틱": [
        {"code":"090430","name":"아모레퍼시픽","market":"KOSPI"},
        {"code":"002790","name":"아모레G","market":"KOSPI"},
        {"code":"051900","name":"LG생활건강","market":"KOSPI"},
    ],
    "통신": [
        {"code":"017670","name":"SK텔레콤","market":"KOSPI"},
        {"code":"030200","name":"KT","market":"KOSPI"},
        {"code":"032640","name":"LG유플러스","market":"KOSPI"},
    ],
    "유통": [
        {"code":"139480","name":"이마트","market":"KOSPI"},
        {"code":"023530","name":"롯데쇼핑","market":"KOSPI"},
        {"code":"004170","name":"신세계","market":"KOSPI"},
        {"code":"069960","name":"현대백화점","market":"KOSPI"},
    ],
    "해운": [
        {"code":"011200","name":"HMM","market":"KOSPI"},
        {"code":"000120","name":"CJ대한통운","market":"KOSPI"},
        {"code":"086280","name":"현대글로비스","market":"KOSPI"},
    ],
    "인터넷": [
        {"code":"035420","name":"NAVER","market":"KOSPI"},
        {"code":"035720","name":"카카오","market":"KOSPI"},
        {"code":"323410","name":"카카오뱅크","market":"KOSPI"},
        {"code":"377300","name":"카카오페이","market":"KOSPI"},
    ],
    "콘텐츠": [
        {"code":"352820","name":"하이브","market":"KOSPI"},
        {"code":"041510","name":"에스엠","market":"KOSDAQ"},
        {"code":"035900","name":"JYP Ent.","market":"KOSDAQ"},
        {"code":"259960","name":"크래프톤","market":"KOSPI"},
        {"code":"263750","name":"펄어비스","market":"KOSDAQ"},
    ],
    "ETF": [
        {"code":"069500","name":"KODEX 200","market":"ETF"},
        {"code":"102110","name":"TIGER 200","market":"ETF"},
        {"code":"360750","name":"TIGER 미국S&P500","market":"ETF"},
        {"code":"133690","name":"TIGER 미국나스닥100","market":"ETF"},
        {"code":"122630","name":"KODEX 레버리지","market":"ETF"},
        {"code":"114800","name":"KODEX 인버스","market":"ETF"},
        {"code":"233740","name":"KODEX 코스닥150레버리지","market":"ETF"},
        {"code":"091160","name":"KODEX 반도체","market":"ETF"},
    ],
}

# 칩으로 표시할 주요 테마 (순서 고정)
THEME_PRIMARY = [
    "반도체", "2차전지", "바이오", "AI", "자동차", "게임",
    "조선", "방산", "우주", "금융", "에너지", "건설",
    "엔터", "로봇", "식품", "화장품", "통신", "ETF",
]

# ── 라우트 ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/balance")
def api_balance():
    try:
        data      = api.get_balance()
        summary   = data["summary"]
        holdings  = data["holdings"]
        total     = int(summary.get("tot_evlu_amt", 0))
        cash      = int(summary.get("dnca_tot_amt", 0))
        profit    = int(summary.get("evlu_pfls_smtl_amt", 0))
        profit_rt = float(summary.get("asst_icdc_erng_rt", 0))
        stocks = []
        for h in holdings:
            qty = int(h.get("hldg_qty", 0))
            if qty <= 0:
                continue
            stocks.append({
                "code":      h.get("pdno", ""),
                "name":      h.get("prdt_name", ""),
                "qty":       qty,
                "avg_price": int(h.get("pchs_avg_pric", 0)),
                "cur_price": int(h.get("prpr", 0)),
                "eval_amt":  int(h.get("evlu_amt", 0)),
                "profit":    int(h.get("evlu_pfls_amt", 0)),
                "profit_rt": float(h.get("evlu_pfls_rt", 0)),
                "trend_rt":  _trend_for_code(h.get("pdno", "")),
            })
        return jsonify({"total": total, "cash": cash,
                        "profit": profit, "profit_rt": profit_rt,
                        "stocks": stocks,
                        "updated": datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/themes")
def api_themes():
    return jsonify({"themes": [t for t in THEME_PRIMARY if t in THEME_MAP]})


@app.route("/api/search")
def api_search():
    q      = request.args.get("q", "").strip()
    market = request.args.get("market", "domestic")
    if not q:
        return jsonify({"results": [], "loaded": domestic_loaded})

    qu = q.upper()

    if market == "domestic" and len(q) >= 2:
        # 1순위: 정확히 일치하는 테마
        for theme_name, theme_stocks in THEME_MAP.items():
            if theme_name.upper() == qu:
                return jsonify({"results": _enrich_prices(theme_stocks), "theme": theme_name,
                                "loaded": domestic_loaded})
        # 2순위: 테마명이 입력값으로 시작
        for theme_name, theme_stocks in THEME_MAP.items():
            if theme_name.upper().startswith(qu):
                return jsonify({"results": _enrich_prices(theme_stocks), "theme": theme_name,
                                "loaded": domestic_loaded})

    if market == "domestic":
        matched = [s for s in domestic_stocks
                   if qu in s["code"] or qu in s["name"].upper()][:20]
    else:
        matched = [s for s in OVERSEAS_STOCKS
                   if qu in s["code"].upper() or qu in s["name"].upper()][:20]

    return jsonify({"results": matched, "loaded": domestic_loaded})


def _num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(str(value).replace(",", "").strip() or default)
    except Exception:
        return default


def _row_value(row, names, fallback_idx=None, default=0):
    for name in names:
        if name in row.index:
            return row.get(name, default)
    if fallback_idx is not None and len(row) > fallback_idx:
        return row.iloc[fallback_idx]
    return default


def _today_yyyymmdd():
    return datetime.now().strftime("%Y%m%d")


def _quote_cached(code, ttl=30):
    now = datetime.now()
    cached = _quote_cache.get(code)
    if cached and (now - cached["ts"]).total_seconds() < ttl:
        return cached["data"]
    data = api.get_price(code)
    _quote_cache[code] = {"ts": now, "data": data}
    return data


def _market_snapshot(limit_name_lookup=15):
    now = datetime.now()
    cached_ts = _market_snapshot_cache.get("ts")
    if cached_ts and (now - cached_ts).total_seconds() < 60:
        return _market_snapshot_cache.get("items", [])

    items = _kis_watchlist_snapshot()
    _market_snapshot_cache["ts"] = now
    _market_snapshot_cache["items"] = items
    return items

    frames = []
    snapshot_date = None
    for day_offset in range(0, 10):
        date = (datetime.now() - timedelta(days=day_offset)).strftime("%Y%m%d")
        day_frames = []
        for market in ("KOSPI", "KOSDAQ"):
            try:
                df = pykrx.get_market_ohlcv_by_ticker(date, market=market)
                if df is not None and not df.empty:
                    df = df.copy()
                    df["market"] = market
                    day_frames.append(df)
            except Exception:
                continue
        if day_frames:
            frames = day_frames
            snapshot_date = date
            break

    if not frames:
        items = _kis_watchlist_snapshot()
        _market_snapshot_cache["ts"] = now
        _market_snapshot_cache["items"] = items
        return items

    df_all = pd.concat(frames)
    items = []
    for code, row in df_all.iterrows():
        open_price = _num(_row_value(row, ["시가", "open"], 0))
        close = _num(_row_value(row, ["종가", "close"], 3))
        volume = int(_num(_row_value(row, ["거래량", "volume"], 4)))
        trade_value = int(_num(_row_value(row, ["거래대금", "value"], 5)))
        change_rt = _num(_row_value(row, ["등락률", "change_rt"], None, 0))
        if change_rt == 0 and open_price > 0 and close > 0:
            change_rt = (close - open_price) / open_price * 100
        if close <= 0:
            continue
        items.append({
            "code": str(code),
            "name": "",
            "market": str(row.get("market", "")),
            "price": int(close),
            "open": int(open_price),
            "volume": volume,
            "trade_amount": trade_value,
            "trend_rt": round(change_rt, 2),
            "date": snapshot_date,
        })

    # Name lookup is only needed for visible ranking rows; keep this bounded.
    visible_codes = set()
    for key in ("volume", "trend_rt"):
        visible_codes.update(i["code"] for i in sorted(items, key=lambda x: x[key], reverse=True)[:limit_name_lookup])
        visible_codes.update(i["code"] for i in sorted(items, key=lambda x: x[key])[:limit_name_lookup])
    for item in items:
        if item["code"] in visible_codes:
            try:
                item["name"] = pykrx.get_market_ticker_name(item["code"])
            except Exception:
                item["name"] = item["code"]

    _market_snapshot_cache["ts"] = now
    _market_snapshot_cache["items"] = items
    return items


def _kis_watchlist_snapshot():
    items = []
    watchlist = list(CANDIDATES.items())[:25]
    existing = {code for code, _ in watchlist}
    for stock in DOMESTIC_STOCKS:
        if stock["code"] not in existing:
            watchlist.append((stock["code"], stock["name"]))
            existing.add(stock["code"])
        if len(watchlist) >= 40:
            break

    market_by_code = {s["code"]: s.get("market", "KOSPI") for s in DOMESTIC_STOCKS}
    for code, name in watchlist:
        try:
            d = _quote_cached(code)
            price = int(_num(d.get("stck_prpr", 0)))
            volume = int(_num(d.get("acml_vol", 0)))
            change_rt = _num(d.get("prdy_ctrt", 0))
            if price <= 0:
                continue
            items.append({
                "code": code,
                "name": name,
                "market": market_by_code.get(code, "KOSPI"),
                "price": price,
                "open": int(_num(d.get("stck_oprc", 0))),
                "volume": volume,
                "trade_amount": int(_num(d.get("acml_tr_pbmn", 0))),
                "trend_rt": round(change_rt, 2),
                "date": _today_yyyymmdd(),
            })
        except Exception:
            continue
    return items


def _trend_for_code(code):
    for item in _market_snapshot():
        if item["code"] == str(code):
            return item.get("trend_rt", 0)
    return None


def _enrich_prices(stocks, limit=15):
    cached_items = _market_snapshot_cache.get("items", [])
    snapshot = {i["code"]: i for i in cached_items}
    enriched = []
    for s in stocks[:limit]:
        item = snapshot.get(s["code"])
        if item:
            enriched.append({**s, "price": item.get("price"), "trend_rt": item.get("trend_rt")})
            continue
        try:
            d = _quote_cached(s["code"])
            enriched.append({
                **s,
                "price": int(_num(d.get("stck_prpr", 0))),
                "trend_rt": round(_num(d.get("prdy_ctrt", 0)), 2),
            })
        except Exception:
            try:
                today = datetime.now().strftime("%Y%m%d")
                start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
                df = pykrx.get_market_ohlcv(start, today, s["code"])
                if not df.empty:
                    last = df.iloc[-1]
                    price = int(last["종가"])
                    open_ = int(last["시가"])
                    enriched.append({
                        **s,
                        "price": price,
                        "trend_rt": round((price - open_) / open_ * 100, 2) if open_ else None,
                    })
                    continue
            except Exception:
                pass
            enriched.append(s)
    return enriched


def _latest_news_title(name, ttl=600):
    now = datetime.now()
    cached = _news_reason_cache.get(name)
    if cached and (now - cached["ts"]).total_seconds() < ttl:
        return cached["title"]
    try:
        q = f"{name} 주가"
        url = (f"https://news.google.com/rss/search"
               f"?q={req_lib.utils.quote(q)}&hl=ko&gl=KR&ceid=KR:ko")
        res = req_lib.get(url, timeout=2, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(res.content)
        item = root.find(".//item")
        title = item.findtext("title", "") if item is not None else ""
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]
        title = title.strip()
    except Exception:
        title = ""
    _news_reason_cache[name] = {"ts": now, "title": title}
    return title


def _ranking_reason(item, kind):
    trend = float(item.get("trend_rt") or 0)
    volume = int(item.get("volume") or 0)
    amount = int(item.get("trade_amount") or 0)
    name = item.get("name") or item.get("code") or ""

    if kind == "gainer":
        base = f"전일 대비 {trend:+.2f}% 상승, 거래량 {volume:,}주 유입"
    elif kind == "loser":
        base = f"전일 대비 {trend:+.2f}% 하락, 매도 우위 가능성"
    else:
        base = f"거래량 {volume:,}주, 거래대금 {amount:,}원 기준 상위"

    title = _latest_news_title(name)
    if title:
        return f"{base}. 최근 뉴스: {title}"
    return f"{base}. 관련 뉴스는 추가 확인 필요"


def _annotate_ranking(items, kind):
    ranked = [dict(item) for item in items]
    if not ranked:
        return ranked
    with ThreadPoolExecutor(max_workers=6) as pool:
        reasons = list(pool.map(lambda x: _ranking_reason(x, kind), ranked))
    for item, reason in zip(ranked, reasons):
        item["reason"] = reason
    return ranked


def _momentum_score(item):
    trend = float(item.get("trend_rt") or 0)
    volume = int(item.get("volume") or 0)
    amount = int(item.get("trade_amount") or 0)
    price = int(item.get("price") or 0)
    open_price = int(item.get("open") or 0)
    name = item.get("name") or item.get("code") or ""

    score = 0
    reasons = []
    cautions = []

    if 1.0 <= trend <= 12.0:
        add = min(35, trend * 3)
        score += add
        reasons.append(f"전일 대비 {trend:+.2f}% 상승")
    elif trend > 12.0:
        score += 18
        reasons.append(f"강한 상승세({trend:+.2f}%)")
        cautions.append("이미 급등 구간")
    elif -1.5 <= trend < 1.0:
        score += 8
        reasons.append("보합권 대기")
    else:
        score -= 10
        cautions.append(f"하락 추세({trend:+.2f}%)")

    if open_price > 0 and price > open_price:
        intraday = (price - open_price) / open_price * 100
        score += min(18, intraday * 4)
        reasons.append(f"시가 대비 {intraday:+.2f}%")

    if volume >= 10_000_000:
        score += 22
        reasons.append("거래량 천만주 이상")
    elif volume >= 3_000_000:
        score += 16
        reasons.append("거래량 300만주 이상")
    elif volume >= 1_000_000:
        score += 10
        reasons.append("거래량 100만주 이상")

    if amount >= 1_000_000_000_000:
        score += 20
        reasons.append("거래대금 1조원 이상")
    elif amount >= 300_000_000_000:
        score += 14
        reasons.append("거래대금 3000억원 이상")
    elif amount >= 100_000_000_000:
        score += 8
        reasons.append("거래대금 1000억원 이상")

    if price < 1000:
        cautions.append("초저가 변동성 주의")
        score -= 8

    score = max(0, min(100, int(round(score))))
    news = ""
    if False and news:
        reasons.append(f"뉴스: {news}")

    return {
        **item,
        "score": score,
        "reason": " · ".join(reasons[:4]) or "추가 모멘텀 확인 필요",
        "caution": " · ".join(cautions[:2]),
        "news": news,
    }


@app.route("/api/momentum_candidates")
def api_momentum_candidates():
    try:
        items = _market_snapshot()
        active = [i for i in items if i.get("volume", 0) > 0 and i.get("price", 0) > 0]
        candidates = [_momentum_score(i) for i in active]
        candidates = [c for c in candidates if c["score"] >= 25]
        candidates.sort(key=lambda x: (x["score"], x.get("trade_amount", 0)), reverse=True)
        candidates = candidates[:12]
        with ThreadPoolExecutor(max_workers=6) as pool:
            news_titles = list(pool.map(lambda x: _latest_news_title(x.get("name") or x.get("code") or ""), candidates[:6]))
        for item, news in zip(candidates[:6], news_titles):
            item["news"] = news
        return jsonify({
            "candidates": candidates,
            "updated": datetime.now().strftime("%H:%M:%S"),
            "note": "급등 가능성 후보이며 매수 추천이 아닙니다.",
        })
    except Exception as e:
        return jsonify({"error": str(e), "candidates": []}), 500


@app.route("/api/rankings")
def api_rankings():
    try:
        items = _market_snapshot()
        active = [i for i in items if i.get("volume", 0) > 0]
        volume = _annotate_ranking(sorted(active, key=lambda x: x.get("volume", 0), reverse=True)[:10], "volume")
        gainers = _annotate_ranking(sorted(active, key=lambda x: x.get("trend_rt", 0), reverse=True)[:10], "gainer")
        losers = _annotate_ranking(sorted(active, key=lambda x: x.get("trend_rt", 0))[:10], "loser")
        return jsonify({
            "volume": volume,
            "gainers": gainers,
            "losers": losers,
            "updated": datetime.now().strftime("%H:%M:%S"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/price")
def api_price():
    code   = request.args.get("code", "").strip()
    market = request.args.get("market", "domestic")
    excd   = request.args.get("excd", "NAS")
    if not code:
        return jsonify({"error": "코드 없음"}), 400
    try:
        def to_int(value, default=0):
            try:
                return int(float(str(value).replace(",", "").strip() or default))
            except (TypeError, ValueError):
                return default

        def to_float(value, default=0.0):
            try:
                return float(str(value).replace(",", "").strip() or default)
            except (TypeError, ValueError):
                return default

        if market == "domestic":
            d = api.get_price(code)
            return jsonify({
                "price":     to_int(d.get("stck_prpr", 0)),
                "change":    to_float(d.get("prdy_vrss", 0)),
                "change_rt": to_float(d.get("prdy_ctrt", 0)),
                "volume":    to_int(d.get("acml_vol", 0)),
                "trade_amount": to_int(d.get("acml_tr_pbmn", 0)),
                "volume_time": datetime.now().strftime("%H:%M:%S"),
                "name":      d.get("hts_kor_isnm", code),
                "currency":  "KRW",
            })
        else:
            url    = f"{api.base_url}/uapi/overseas-price/v1/quotations/price"
            params = {"AUTH": "", "EXCD": excd, "SYMB": code}
            res    = req_lib.get(url, headers=api._headers("HHDFS00000300"), params=params, timeout=5)
            d      = res.json().get("output", {})
            return jsonify({
                "price":     to_float(d.get("last", 0)),
                "change":    to_float(d.get("diff", 0)),
                "change_rt": to_float(d.get("rate", 0)),
                "volume":    to_int(d.get("tvol") or d.get("evol") or d.get("pvol") or 0),
                "trade_amount": to_float(d.get("tamt") or d.get("eamt") or 0),
                "volume_time": datetime.now().strftime("%H:%M:%S"),
                "name":      d.get("rsym", code),
                "currency":  "USD" if excd in ("NAS","NYS","AMS") else
                             "JPY" if excd == "TSE" else
                             "HKD" if excd == "HKS" else "USD",
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/screening")
def api_screening():
    try:
        today  = datetime.now().strftime("%Y%m%d")
        start  = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        budget = int(api.get_balance()["summary"].get("dnca_tot_amt", 50000))
        budget = max(budget, 10000)
        results = []
        for code, name in CANDIDATES.items():
            try:
                df = pykrx.get_market_ohlcv(start, today, code)
                if df.empty or len(df) < 2:
                    continue
                price = int(df["종가"].iloc[-1])
                if price > budget:
                    continue
                vol_avg   = df["거래량"].iloc[-6:-1].mean()
                vol_today = int(df["거래량"].iloc[-1])
                ret_1m    = (df["종가"].iloc[-1] / df["종가"].iloc[0] - 1) * 100
                shares    = budget // price
                fund = pykrx.get_market_fundamental(today, today, code)
                per  = float(fund["PER"].iloc[0]) if not fund.empty and float(fund["PER"].iloc[0]) > 0 else None
                pbr  = float(fund["PBR"].iloc[0]) if not fund.empty and float(fund["PBR"].iloc[0]) > 0 else None
                results.append({
                    "code": code, "name": name, "price": price, "shares": shares,
                    "ret_1m": round(ret_1m, 1),
                    "trend_rt": round((price / int(df["시가"].iloc[-1]) - 1) * 100, 2) if int(df["시가"].iloc[-1]) > 0 else 0,
                    "volume": vol_today,
                    "vol_ratio": round(vol_today / vol_avg, 1) if vol_avg > 0 else 0,
                    "per": round(per, 1) if per else "-",
                    "pbr": round(pbr, 1) if pbr else "-",
                })
            except Exception:
                continue
        results.sort(key=lambda x: x["ret_1m"], reverse=True)
        return jsonify({"budget": budget, "stocks": results,
                        "updated": datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs")
def api_logs():
    try:
        log_path = os.path.join(os.path.dirname(__file__), "logs", "trader.log")
        if not os.path.exists(log_path):
            return jsonify({"lines": ["로그 파일 없음 (main.py 실행 후 생성됩니다)"]})
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        last = [l.rstrip() for l in lines[-100:]]
        last.reverse()
        return jsonify({"lines": last})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chart")
def api_chart():
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        df    = pykrx.get_market_ohlcv(start, today, "069500")
        if df.empty:
            return jsonify({"labels": [], "values": []})
        return jsonify({
            "labels": [str(d)[:10] for d in df.index.tolist()],
            "values": df["종가"].tolist(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sell", methods=["POST"])
def api_sell():
    try:
        body = request.get_json()
        code = str(body.get("code", "")).strip()
        qty  = int(body.get("qty", 0))
        if not code or qty <= 0:
            return jsonify({"error": "종목코드 또는 수량이 올바르지 않습니다."}), 400
        result   = api.sell_market(code, qty)
        order_no = result.get("ODNO", "")
        return jsonify({"ok": True, "order_no": order_no, "msg": "매도 주문 완료"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/buy", methods=["POST"])
def api_buy():
    try:
        body   = request.get_json()
        code   = str(body.get("code", "")).strip()
        qty    = int(body.get("qty", 0))
        market = body.get("market", "domestic")
        excd   = body.get("excd", "NAS")
        price  = float(body.get("price", 0))
        if not code or qty <= 0:
            return jsonify({"error": "종목코드 또는 수량이 올바르지 않습니다."}), 400

        if market == "domestic":
            result = api.buy_market(code, qty)
            order_no = result.get("ODNO", "")
        else:
            excg = EXCD_TO_EXCG.get(excd, "NASD")
            tr_id = "VTTT1002U" if api.is_paper else "TTTT1002U"
            url   = f"{api.base_url}/uapi/overseas-stock/v1/trading/order"
            cano, acnt = api.account_no.split("-")
            body_data = {
                "CANO": cano, "ACNT_PRDT_CD": acnt,
                "OVRS_EXCG_CD": excg, "PDNO": code,
                "ORD_QTY": str(qty),
                "OVRS_ORD_UNPR": str(round(price, 2)),
                "ORD_SVR_DVSN_CD": "0",
                "ORD_DVSN": "00",
            }
            res = req_lib.post(url, headers=api._headers(tr_id), json=body_data, timeout=5)
            data = res.json()
            if data.get("rt_cd") != "0":
                raise RuntimeError(data.get("msg1", "해외 주문 실패"))
            order_no = data.get("output", {}).get("ODNO", "")

        return jsonify({"ok": True, "order_no": order_no, "msg": "매수 주문 완료"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/news")
def api_news():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"news": []})
    try:
        url = (f"https://news.google.com/rss/search"
               f"?q={req_lib.utils.quote(q)}&hl=ko&gl=KR&ceid=KR:ko")
        res  = req_lib.get(url, timeout=6,
                           headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:6]
        news  = []
        for item in items:
            title   = item.findtext("title", "")
            link    = item.findtext("link", "")
            pub     = item.findtext("pubDate", "")
            source  = item.findtext("source", "")
            news.append({"title": title, "link": link,
                         "pubDate": pub, "source": source})
        return jsonify({"news": news})
    except Exception as e:
        return jsonify({"error": str(e), "news": []}), 500


@app.route("/api/stock_chart/<code>")
def api_stock_chart(code):
    try:
        period = request.args.get("period", "day")

        if period == "day":
            rows = api.get_intraday_minutes(code)
            rows = list(reversed(rows))[-240:]
            if not rows:
                return jsonify({"error": "분봉 데이터 없음"}), 404
            labels, open_, close, high, low, volume = [], [], [], [], [], []
            for r in rows:
                t = str(r.get("stck_cntg_hour", ""))
                labels.append(f"{t[0:2]}:{t[2:4]}" if len(t) >= 4 else t)
                open_.append(int(float(r.get("stck_oprc", r.get("stck_prpr", 0)) or 0)))
                close.append(int(float(r.get("stck_prpr", 0) or 0)))
                high.append(int(float(r.get("stck_hgpr", r.get("stck_prpr", 0)) or 0)))
                low.append(int(float(r.get("stck_lwpr", r.get("stck_prpr", 0)) or 0)))
                volume.append(int(float(r.get("cntg_vol", r.get("acml_vol", 0)) or 0)))
            return jsonify({"labels": labels, "open": open_, "close": close, "high": high, "low": low, "volume": volume, "period": period})

        today = datetime.now().strftime("%Y%m%d")
        if period == "week":
            start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        elif period == "month":
            start = (datetime.now() - timedelta(days=31)).strftime("%Y%m%d")
        elif period == "year":
            start = (datetime.now() - timedelta(days=3650)).strftime("%Y%m%d")
        else:
            start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

        df = pykrx.get_market_ohlcv(start, today, code)
        if df.empty:
            return jsonify({"error": "데이터 없음"}), 404
        if period == "year":
            df = df.resample("M").last().dropna()
        return jsonify({
            "labels": [str(d)[:10] for d in df.index.tolist()],
            "open":   df["시가"].tolist(),
            "close":  df["종가"].tolist(),
            "high":   df["고가"].tolist(),
            "low":    df["저가"].tolist(),
            "volume": df["거래량"].tolist(),
            "period": period,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orderbook/<code>")
def api_orderbook(code):
    try:
        data = api.get_orderbook(code)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/indices")
def api_indices():
    start  = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    today  = datetime.now().strftime("%Y%m%d")
    result = {}
    for key, idx in [("kospi", "1001"), ("kosdaq", "2001")]:
        try:
            df = pykrx.get_index_ohlcv_by_date(start, today, idx)
            if not df.empty:
                close  = float(df["종가"].iloc[-1])
                open_  = float(df["시가"].iloc[-1])
                chg_rt = (close - open_) / open_ * 100 if open_ > 0 else 0
                result[key] = {"value": round(close, 2), "change_rt": round(chg_rt, 2)}
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/pending_orders")
def api_pending_orders():
    try:
        cano, acnt = api.account_no.split("-")
        tr_id  = "VTTC8036R" if api.is_paper else "TTTC8036R"
        url    = f"{api.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"
        params = {
            "CANO": cano, "ACNT_PRDT_CD": acnt,
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
            "INQR_DVSN_1": "0", "INQR_DVSN_2": "0",
        }
        res    = req_lib.get(url, headers=api._headers(tr_id), params=params, timeout=5)
        orders = res.json().get("output", [])
        result = []
        for o in orders:
            qty    = int(o.get("ord_qty", 0))
            exec_q = int(o.get("tot_ccld_qty", 0))
            remain = qty - exec_q
            if remain <= 0:
                continue
            result.append({
                "order_no":  o.get("odno", ""),
                "org_no":    o.get("orgn_odno", ""),
                "code":      o.get("pdno", ""),
                "name":      o.get("prdt_name", ""),
                "side":      "매수" if o.get("sll_buy_dvsn_cd") == "02" else "매도",
                "qty":       qty,
                "remain":    remain,
                "price":     int(o.get("ord_unpr", 0)),
            })
        return jsonify({"orders": result})
    except Exception as e:
        return jsonify({"error": str(e), "orders": []}), 500


@app.route("/api/cancel_order", methods=["POST"])
def api_cancel_order():
    return jsonify({"error": "공유용 데모 버전에서는 주문 취소 기능이 제한되어 있습니다."}), 403


@app.route("/api/strategy", methods=["GET"])
def api_strategy_get():
    return jsonify({
        "stop_loss":   float(os.getenv("STOP_LOSS_RATIO",       0.07)),
        "take_profit": float(os.getenv("TAKE_PROFIT_RATIO",     0.15)),
        "max_single":  float(os.getenv("MAX_SINGLE_STOCK_RATIO",0.10)),
        "daily_loss":  float(os.getenv("DAILY_LOSS_LIMIT",      0.02)),
        "max_sector":  float(os.getenv("MAX_SECTOR_RATIO",      0.25)),
    })


@app.route("/api/strategy", methods=["POST"])
def api_strategy_post():
    try:
        from dotenv import set_key
        body     = request.get_json()
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        mapping  = {
            "stop_loss":   "STOP_LOSS_RATIO",
            "take_profit": "TAKE_PROFIT_RATIO",
            "max_single":  "MAX_SINGLE_STOCK_RATIO",
            "daily_loss":  "DAILY_LOSS_LIMIT",
            "max_sector":  "MAX_SECTOR_RATIO",
        }
        for key, env_key in mapping.items():
            if key in body:
                set_key(env_path, env_key, str(body[key]))
                os.environ[env_key] = str(body[key])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    try:
        from backtest.backtester import Backtester
        body  = request.get_json()
        code  = str(body.get("code", "005930"))
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
        df    = pykrx.get_market_ohlcv(start, today, code)
        if df.empty:
            return jsonify({"error": "데이터 없음"}), 404
        df  = df.reset_index()
        df.columns = ["date","open","high","low","close","volume","value"]
        ohlcv = df.rename(columns={
            "date":"stck_bsop_date","open":"stck_oprc","high":"stck_hgpr",
            "low":"stck_lwpr","close":"stck_clpr","volume":"acml_vol",
        }).to_dict("records")
        bt     = Backtester(initial_cash=10_000_000)
        result = bt.run_golden_cross(ohlcv, fast=5, slow=20, buy_amount=1_000_000)
        return jsonify({"ok": True, "code": code, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일에 추가해주세요."}), 400
            
        client = genai.Client(api_key=api_key)
        body = request.get_json()
        user_message = body.get("message", "")
        
        sys_prompt = "너는 주식 투자를 도와주는 전문 AI 어시스턴트야. 사용자의 질문에 항상 친절하고 전문적으로 답변해줘. 한국어로 대답해야 해."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=sys_prompt
            )
        )
        return jsonify({"ok": True, "reply": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 45)
    print(" KIS 자동매매 대시보드 시작")
    print(" http://localhost:5000 에서 확인하세요")
    print("=" * 45)
    app.run(host="0.0.0.0", port=5000, debug=False)
