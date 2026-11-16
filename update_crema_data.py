#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
매일 한국시간(KST) 07:00에 GitHub Actions에서 자동 실행되어
QQQ, QTY(QLD), TQQQ의 최근 6개월 일봉(OHLC + 200일선) 및 크레마 지수(6대 지표)를 계산하고
index.html 및 crema_data.json을 최신 상태로 갱신하는 스크립트입니다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf


def linear_score(val: float, zero_pt: float, hundred_pt: float) -> float:
    if pd.isna(val):
        return 0.0
    if hundred_pt == zero_pt:
        return 50.0
    ratio = (val - zero_pt) / (hundred_pt - zero_pt)
    return float(np.clip(ratio * 100.0, 0.0, 100.0))


def compute_wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def fetch_cnn_fear_greed() -> Optional[float]:
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.cnn.com/markets/fear-and-greed",
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            score = r.json().get("fear_and_greed", {}).get("score")
            if score is not None:
                return float(score)
    except Exception:
        pass
    return None


def build_ticker_records(ui_key: str, yf_symbol: str, vix_close: pd.Series, latest_fg: Optional[float]) -> list[dict]:
    df = yf.download(yf_symbol, period="2y", interval="1d", auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"Failed to download {yf_symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close"]].dropna().copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.sort_index()

    vix_s = vix_close.copy()
    vix_s.index = pd.to_datetime(vix_s.index).tz_localize(None)
    df["VIX"] = vix_s.reindex(df.index).ffill()

    # 1. 연중 낙폭 (YTD High 기준, 연초 보정을 위해 252일 롤링 고점과 병행)
    ytd_high = df["Close"].groupby(df.index.year).cummax()
    roll_high = df["Close"].rolling(252, min_periods=20).max()
    ref_high = np.maximum(ytd_high, roll_high)
    df["rawDd"] = ((df["Close"] / ref_high) - 1.0) * 100.0

    # 2. 주간 RSI (14주)
    w_close = df["Close"].resample("W-FRI").last().dropna()
    w_rsi = compute_wilder_rsi(w_close, 14)
    df["rawRw"] = w_rsi.reindex(df.index).ffill().fillna(50.0)

    # 3. 일간 RSI (14일)
    df["rawRd"] = compute_wilder_rsi(df["Close"], 14)

    # 4. VIX 이격도 (200일 이동평균 대비 %)
    vix_ma200 = df["VIX"].rolling(200, min_periods=20).mean()
    df["rawVx"] = ((df["VIX"] / vix_ma200) - 1.0) * 100.0

    # 5. 200일선 이격도 (%)
    df["ma200"] = df["Close"].rolling(200, min_periods=50).mean()
    df["rawMa"] = ((df["Close"] / df["ma200"]) - 1.0) * 100.0

    # 전일 대비 등락률 (%)
    df["changePct"] = df["Close"].pct_change().fillna(0.0) * 100.0

    # 환산 점수 계산
    df["scoreDd"] = df["rawDd"].apply(lambda x: linear_score(x, 0.0, -12.0))
    df["scoreRw"] = df["rawRw"].apply(lambda x: linear_score(x, 70.0, 30.0))
    df["scoreRd"] = df["rawRd"].apply(lambda x: linear_score(x, 70.0, 30.0))
    df["scoreVx"] = df["rawVx"].apply(lambda x: linear_score(x, -10.0, 40.0))
    df["scoreMa"] = df["rawMa"].apply(lambda x: linear_score(x, 12.0, -12.0))

    # 6. 공포탐욕지수 (과거 일자는 5대 지표 가중평균 기반 역산, 최신 일자는 CNN 실측치 반영)
    df["scoreFg"] = (
        df["scoreDd"] * 0.30
        + df["scoreRw"] * 0.20
        + df["scoreRd"] * 0.10
        + df["scoreVx"] * 0.15
        + df["scoreMa"] * 0.15
    ) / 0.90
    df["rawFg"] = 100.0 - df["scoreFg"]

    if latest_fg is not None and len(df) > 0:
        fg_clamped = float(np.clip(latest_fg, 0.0, 100.0))
        df.iloc[-1, df.columns.get_loc("rawFg")] = fg_clamped
        df.iloc[-1, df.columns.get_loc("scoreFg")] = 100.0 - fg_clamped

    df["cremaIndex"] = (
        df["scoreDd"] * 0.30
        + df["scoreRw"] * 0.20
        + df["scoreRd"] * 0.10
        + df["scoreVx"] * 0.15
        + df["scoreMa"] * 0.15
        + df["scoreFg"] * 0.10
    )

    # 최근 6개월(약 131영업일) 추출
    recent = df.dropna(subset=["ma200", "cremaIndex"]).tail(131)
    records = []
    for dt, row in recent.iterrows():
        records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "ticker": ui_key,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "ma200": round(float(row["ma200"]), 2),
            "changePct": round(float(row["changePct"]), 2),
            "cremaIndex": round(float(row["cremaIndex"]), 2),
            "scoreDd": round(float(row["scoreDd"]), 2),
            "scoreRw": round(float(row["scoreRw"]), 2),
            "scoreRd": round(float(row["scoreRd"]), 2),
            "scoreVx": round(float(row["scoreVx"]), 2),
            "scoreMa": round(float(row["scoreMa"]), 2),
            "scoreFg": round(float(row["scoreFg"]), 2),
            "rawDd": round(float(row["rawDd"]), 2),
            "rawRw": round(float(row["rawRw"]), 1),
            "rawRd": round(float(row["rawRd"]), 1),
            "rawVx": round(float(row["rawVx"]), 2),
            "rawMa": round(float(row["rawMa"]), 2),
            "rawFg": round(float(row["rawFg"]), 1),
        })
    return records


def main() -> None:
    vix_df = yf.download("^VIX", period="2y", interval="1d", auto_adjust=True, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.get_level_values(0)
    vix_close = vix_df["Close"].dropna()

    latest_fg = fetch_cnn_fear_greed()
    mapping = {"QQQ": "QQQ", "QTY": "QLD", "TQQQ": "TQQQ"}

    payload = {}
    for ui_key, yf_sym in mapping.items():
        payload[ui_key] = build_ticker_records(ui_key, yf_sym, vix_close, latest_fg)

    # 1. crema_data.json 저장
    json_path = Path("crema_data.json")
    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    json_path.write_text(json_str, encoding="utf-8")

    # 2. index.html 내부 마커 영역에 최신 데이터 직접 주입 (모바일 오프라인·무지연 로딩 보장)
    html_path = Path("index.html")
    if html_path.exists():
        html_text = html_path.read_text(encoding="utf-8")
        pattern = r"(/\*__CREMA_DATA_START__\*/).*?(/\*__CREMA_DATA_END__\*/)"
        replacement = rf"\1 {json_str} \2"
        updated_html = re.sub(pattern, replacement, html_text, flags=re.DOTALL)
        html_path.write_text(updated_html, encoding="utf-8")

    kst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[{kst_now}] Updated QQQ, QTY(QLD), TQQQ 6M daily records successfully.")


if __name__ == "__main__":
    main()
