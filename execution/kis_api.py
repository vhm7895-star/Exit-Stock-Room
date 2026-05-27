"""
KIS (한국투자증권) REST API 클라이언트
"""
import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL_REAL   = "https://openapi.koreainvestment.com:9443"
BASE_URL_PAPER  = "https://openapivts.koreainvestment.com:29443"


class KISApi:
    def __init__(self):
        self.app_key    = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_no = os.getenv("KIS_ACCOUNT_NO", "").strip()
        self.is_paper   = os.getenv("KIS_IS_PAPER", "false").strip().lower() == "true"
        self.base_url   = BASE_URL_PAPER if self.is_paper else BASE_URL_REAL

        if not self.account_no or "-" not in self.account_no:
            print(f"[경고] KIS_ACCOUNT_NO가 설정되지 않았거나 형식이 올바르지 않습니다. 공유용 기본 가짜 계좌번호를 사용합니다.")
            self.account_no = "12345678-01"

        self._access_token = None
        self._token_expires = None

    # ── 인증 ──────────────────────────────────────────────

    def get_access_token(self) -> str:
        if not self.app_key or not self.app_secret:
            raise ValueError("KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 설정되지 않았습니다.")
            
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token

        if getattr(self, '_auth_failed_until', None) and datetime.now() < self._auth_failed_until:
            raise RuntimeError("이전 인증 실패로 인해 재시도를 보류중입니다.")

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        try:
            res = requests.post(url, json=body, timeout=5)
            res.raise_for_status()
        except Exception as e:
            self._auth_failed_until = datetime.now() + timedelta(minutes=1)
            raise RuntimeError(f"인증 실패: {e}")
            
        data = res.json()

        self._access_token  = data["access_token"]
        self._token_expires = datetime.now() + timedelta(hours=23)
        return self._access_token

    def _headers(self, tr_id: str, extra: dict = None) -> dict:
        h = {
            "content-type":  "application/json",
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
            "custtype":      "P",
        }
        if extra:
            h.update(extra)
        return h

    # ── 시세 조회 ──────────────────────────────────────────

    def get_price(self, stock_code: str) -> dict:
        """현재가 + 기본 시세 정보"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
        res = requests.get(url, headers=self._headers("FHKST01010100"), params=params, timeout=5)
        res.raise_for_status()
        return res.json()["output"]

    def get_ohlcv(self, stock_code: str, period: str = "D", count: int = 100) -> list[dict]:
        """일/주/월봉 데이터 (period: D/W/M)"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        end_date   = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=count * 2)).strftime("%Y%m%d")
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD":         stock_code,
            "FID_INPUT_DATE_1":       start_date,
            "FID_INPUT_DATE_2":       end_date,
            "FID_PERIOD_DIV_CODE":    period,
            "FID_ORG_ADJ_PRC":        "0",
        }
        res = requests.get(url, headers=self._headers("FHKST03010100"), params=params, timeout=5)
        res.raise_for_status()
        return res.json().get("output2", [])

    def get_intraday_minutes(self, stock_code: str, input_time: str = None) -> list[dict]:
        """1분 단위 당일 분봉 데이터"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_HOUR_1": input_time or datetime.now().strftime("%H%M%S"),
            "FID_PW_DATA_INCU_YN": "Y",
        }
        res = requests.get(url, headers=self._headers("FHKST03010200"), params=params, timeout=5)
        res.raise_for_status()
        return res.json().get("output2", [])

    def get_orderbook(self, stock_code: str) -> dict:
        """호가 10단계"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
        res = requests.get(url, headers=self._headers("FHKST01010200"), params=params)
        res.raise_for_status()
        return res.json()["output1"]

    # ── 계좌 조회 ──────────────────────────────────────────

    def get_balance(self) -> dict:
        """잔고 및 평가금액 조회"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        cano, acnt_prdt_cd = self.account_no.split("-")
        tr_id = "VTTC8434R" if self.is_paper else "TTTC8434R"
        params = {
            "CANO":            cano,
            "ACNT_PRDT_CD":    acnt_prdt_cd,
            "AFHR_FLPR_YN":    "N",
            "OFL_YN":          "",
            "INQR_DVSN":       "02",
            "UNPR_DVSN":       "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN":       "01",
            "CTX_AREA_FK100":  "",
            "CTX_AREA_NK100":  "",
        }
        res = requests.get(url, headers=self._headers(tr_id), params=params)
        res.raise_for_status()
        data = res.json()
        return {
            "holdings": data.get("output1", []),
            "summary":  data.get("output2", [{}])[0],
        }

    def get_cash(self) -> int:
        """주문 가능 현금"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
        cano, acnt_prdt_cd = self.account_no.split("-")
        tr_id = "VTTC8908R" if self.is_paper else "TTTC8908R"
        params = {
            "CANO":         cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO":         "005930",
            "ORD_UNPR":     "0",
            "ORD_DVSN":     "01",
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N",
        }
        res = requests.get(url, headers=self._headers(tr_id), params=params)
        res.raise_for_status()
        return int(res.json()["output"].get("ord_psbl_cash", 0))

    # ── 주문 ──────────────────────────────────────────────

    def buy_market(self, stock_code: str, qty: int) -> dict:
        """시장가 매수"""
        return self._order(stock_code, qty, "01", "BUY")

    def sell_market(self, stock_code: str, qty: int) -> dict:
        """시장가 매도"""
        return self._order(stock_code, qty, "01", "SELL")

    def buy_limit(self, stock_code: str, qty: int, price: int) -> dict:
        """지정가 매수"""
        return self._order(stock_code, qty, "00", "BUY", price)

    def sell_limit(self, stock_code: str, qty: int, price: int) -> dict:
        """지정가 매도"""
        return self._order(stock_code, qty, "00", "SELL", price)

    def _order(self, stock_code: str, qty: int, ord_dvsn: str, side: str, price: int = 0) -> dict:
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        cano, acnt_prdt_cd = self.account_no.split("-")

        if side == "BUY":
            tr_id = "VTTC0802U" if self.is_paper else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if self.is_paper else "TTTC0801U"

        body = {
            "CANO":         cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO":         stock_code,
            "ORD_DVSN":     ord_dvsn,
            "ORD_QTY":      str(qty),
            "ORD_UNPR":     str(price),
        }
        res = requests.post(url, headers=self._headers(tr_id), json=body)
        res.raise_for_status()
        result = res.json()

        if result["rt_cd"] != "0":
            raise RuntimeError(f"주문 실패: {result['msg1']}")
        return result["output"]

    def cancel_order(self, org_ord_no: str, stock_code: str, qty: int, price: int) -> dict:
        """주문 취소"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl"
        cano, acnt_prdt_cd = self.account_no.split("-")
        tr_id = "VTTC0803U" if self.is_paper else "TTTC0803U"
        body = {
            "CANO":         cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO":    org_ord_no,
            "ORD_DVSN":     "00",
            "RVSE_CNCL_DVSN_CD": "02",
            "ORD_QTY":      str(qty),
            "ORD_UNPR":     str(price),
            "QTY_ALL_ORD_YN": "Y",
        }
        res = requests.post(url, headers=self._headers(tr_id), json=body)
        res.raise_for_status()
        return res.json()["output"]
