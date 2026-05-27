"""
기술적 지표 계산 (pandas 기반)
"""
import pandas as pd
import numpy as np


def to_df(ohlcv: list[dict]) -> pd.DataFrame:
    """KIS API ohlcv 응답을 DataFrame으로 변환"""
    df = pd.DataFrame(ohlcv)
    df = df.rename(columns={
        "stck_bsop_date": "date",
        "stck_oprc":      "open",
        "stck_hgpr":      "high",
        "stck_lwpr":      "low",
        "stck_clpr":      "close",
        "acml_vol":       "volume",
    })
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    return df


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    return df["close"].rolling(period).mean()


def ema(df: pd.DataFrame, period: int) -> pd.Series:
    return df["close"].ewm(span=period, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta  = df["close"].diff()
    gain   = delta.clip(lower=0).rolling(period).mean()
    loss   = (-delta.clip(upper=0)).rolling(period).mean()
    rs     = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    e_fast   = ema(df, fast)
    e_slow   = ema(df, slow)
    macd_    = e_fast - e_slow
    signal_  = macd_.ewm(span=signal, adjust=False).mean()
    hist     = macd_ - signal_
    return pd.DataFrame({"macd": macd_, "signal": signal_, "hist": hist})


def bollinger(df: pd.DataFrame, period=20, std_mult=2) -> pd.DataFrame:
    mid   = sma(df, period)
    std   = df["close"].rolling(period).std()
    return pd.DataFrame({
        "upper": mid + std_mult * std,
        "mid":   mid,
        "lower": mid - std_mult * std,
    })


def atr(df: pd.DataFrame, period=14) -> pd.Series:
    high_low  = df["high"] - df["low"]
    high_prev = (df["high"] - df["close"].shift()).abs()
    low_prev  = (df["low"]  - df["close"].shift()).abs()
    tr        = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def golden_cross(df: pd.DataFrame, fast=5, slow=20) -> pd.Series:
    """골든크로스 시그널 (True = 크로스 발생)"""
    f = sma(df, fast)
    s = sma(df, slow)
    cross_up = (f > s) & (f.shift(1) <= s.shift(1))
    return cross_up


def dead_cross(df: pd.DataFrame, fast=5, slow=20) -> pd.Series:
    """데드크로스 시그널"""
    f = sma(df, fast)
    s = sma(df, slow)
    cross_dn = (f < s) & (f.shift(1) >= s.shift(1))
    return cross_dn


def is_52week_high(df: pd.DataFrame) -> bool:
    """현재가가 52주 신고가인지 확인"""
    if len(df) < 2:
        return False
    recent = df["close"].iloc[-1]
    high52 = df["high"].iloc[:-1].max()
    return recent >= high52


def volume_surge(df: pd.DataFrame, mult=2.0) -> bool:
    """거래량이 20일 평균 대비 mult배 이상인지 확인"""
    if len(df) < 21:
        return False
    avg_vol  = df["volume"].iloc[-21:-1].mean()
    curr_vol = df["volume"].iloc[-1]
    return curr_vol >= avg_vol * mult
