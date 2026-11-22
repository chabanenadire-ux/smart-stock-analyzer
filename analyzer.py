from __future__ import annotations

import logging
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
import numpy as np
import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "surge", "soar", "gain", "beat", "record", "growth", "bullish",
    "upgrade", "profit", "strong", "rally", "rise", "jump", "boost",
    "outperform", "success", "positive", "improve", "upside", "raises",
    "approved", "expands", "innovation", "breakthrough"
}
NEGATIVE_WORDS = {
    "drop", "fall", "slump", "miss", "loss", "bearish", "downgrade",
    "lawsuit", "weak", "plunge", "risk", "decline", "crash", "negative",
    "warning", "cut", "underperform", "downside", "investigation",
    "recall", "disappoints", "debt", "fraud"
}
NEGATIONS = {"not", "no", "never", "neither", "without", "fails", "failed"}

def yahoo_rss_url(ticker: str) -> str:
    return (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={quote(ticker.upper())}&region=US&lang=en-US"
    )

def score_headline(title: str) -> int:
    """Simple transparent dictionary score; not a trained AI model."""
    words = re.findall(r"[a-z]+", title.lower())
    score = 0
    negate_for = 0
    for word in words:
        if word in NEGATIONS:
            negate_for = 3
            continue
        value = 1 if word in POSITIVE_WORDS else -1 if word in NEGATIVE_WORDS else 0
        if value:
            score += -value if negate_for else value
        if negate_for:
            negate_for -= 1
    return score

def _parse_date(entry) -> pd.Timestamp | None:
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return pd.Timestamp(dt).tz_convert("UTC").tz_localize(None)
        except (TypeError, ValueError, OverflowError):
            pass

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return pd.Timestamp(
                year=parsed.tm_year, month=parsed.tm_mon, day=parsed.tm_mday,
                hour=parsed.tm_hour, minute=parsed.tm_min, second=parsed.tm_sec,
                tz="UTC"
            ).tz_localize(None)
        except (TypeError, ValueError):
            return None
    return None

def fetch_news(ticker: str, timeout: int = 20) -> pd.DataFrame:
    """Fetch Yahoo Finance RSS headlines. Raises on network/feed failure."""
    url = yahoo_rss_url(ticker)
    headers = {"User-Agent": "Mozilla/5.0 SmartStockAnalyzer/1.0"}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    if not feed.entries:
        # An empty feed is a valid outcome; distinguish it from a request failure.
        return pd.DataFrame(columns=["published_at", "date", "title", "sentiment"])

    rows = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        published_at = _parse_date(entry)
        if not title or published_at is None:
            continue
        rows.append({
            "published_at": published_at,
            "date": published_at.normalize(),
            "title": title,
            "sentiment": score_headline(title),
            "link": entry.get("link", "")
        })

    if not rows:
        return pd.DataFrame(columns=["published_at", "date", "title", "sentiment", "link"])

    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["title", "published_at"])
        .sort_values("published_at", ascending=False)
        .reset_index(drop=True)
    )

def fetch_price_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Download adjusted daily OHLCV data using yfinance."""
    data = yf.download(
        ticker.upper(), period=period, interval="1d",
        auto_adjust=True, progress=False, threads=False
    )
    if data is None or data.empty:
        raise ValueError(f"No price data returned for ticker '{ticker}'.")

    if isinstance(data.columns, pd.MultiIndex):
        # yfinance versions may return either (Price, Ticker) or (Ticker, Price).
        close = None
        for level in range(data.columns.nlevels):
            if "Close" in data.columns.get_level_values(level):
                close = data.xs("Close", axis=1, level=level)
                break
        if close is None:
            raise ValueError("The downloaded data has no Close column.")
        if isinstance(close, pd.DataFrame):
            if ticker.upper() in close.columns:
                close = close[ticker.upper()]
            elif close.shape[1] == 1:
                close = close.iloc[:, 0]
            else:
                raise ValueError("Could not identify the requested ticker in price data.")
        close = close.rename("close")
        # Retrieve OHLCV as a single ticker when possible for technical indicators.
        frames = {"Close": close}
        for field in ["Open", "High", "Low", "Volume"]:
            try:
                part = data.xs(field, axis=1, level=0)
                if isinstance(part, pd.DataFrame):
                    part = part[ticker.upper()] if ticker.upper() in part.columns else part.iloc[:, 0]
                frames[field] = part
            except (KeyError, ValueError):
                pass
        normalized = pd.DataFrame(frames)
    else:
        normalized = data.copy()
        if "Close" not in normalized.columns:
            raise ValueError("The downloaded data has no Close column.")

    normalized = normalized.rename(columns={
        "Close": "close", "Open": "open", "High": "high",
        "Low": "low", "Volume": "volume"
    })
    normalized = normalized.reset_index()
    date_col = "Date" if "Date" in normalized.columns else normalized.columns[0]
    normalized = normalized.rename(columns={date_col: "date"})
    normalized["date"] = pd.to_datetime(normalized["date"], utc=True).dt.tz_localize(None).dt.normalize()

    for col in ["close", "open", "high", "low", "volume"]:
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    normalized = (
        normalized.dropna(subset=["close"])
        .drop_duplicates(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )
    if normalized.empty:
        raise ValueError("No valid closing prices found.")
    return normalized

def add_technical_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    close = df["close"]
    df["sma_20"] = close.rolling(20, min_periods=1).mean()
    df["sma_50"] = close.rolling(50, min_periods=1).mean()
    df["ema_12"] = close.ewm(span=12, adjust=False).mean()
    df["ema_26"] = close.ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    df.loc[(loss == 0) & (gain > 0), "rsi_14"] = 100
    df.loc[(gain == 0) & (loss == 0), "rsi_14"] = 50
    df["daily_return_pct"] = close.pct_change() * 100
    return df

def align_news_to_trading_days(prices: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each article to the first available trading date on/after its publication date.
    Weekend/holiday articles therefore move to the next available session.
    This is a daily approximation; it does not model intraday event windows.
    """
    result = prices.copy()
    result["news_count"] = 0
    result["sentiment"] = 0
    result["avg_sentiment"] = np.nan
    result["has_news"] = False
    result["sample_title"] = ""

    if news is None or news.empty:
        return result

    trading_dates = pd.DatetimeIndex(result["date"])
    positions = trading_dates.searchsorted(pd.DatetimeIndex(news["date"]), side="left")
    valid = positions < len(trading_dates)
    if not valid.any():
        return result

    aligned = news.loc[valid].copy()
    aligned["trading_date"] = trading_dates[positions[valid]].to_numpy()
    daily = aligned.groupby("trading_date", as_index=False).agg(
        news_count=("title", "count"),
        sentiment=("sentiment", "sum"),
        avg_sentiment=("sentiment", "mean"),
        sample_title=("title", "first")
    )
    result = result.merge(daily, left_on="date", right_on="trading_date", how="left", suffixes=("", "_news"))
    result["has_news"] = result["news_count_news"].notna()
    for col in ["news_count", "sentiment"]:
        result[col] = result[f"{col}_news"].fillna(0).astype(int)
        result.drop(columns=[f"{col}_news"], inplace=True)
    result["avg_sentiment"] = result["avg_sentiment_news"]
    result["sample_title"] = result["sample_title_news"].fillna("")
    result.drop(columns=["avg_sentiment_news", "sample_title_news", "trading_date"], inplace=True)
    return result

def calculate_metrics(df: pd.DataFrame) -> dict:
    first_price = float(df["close"].iloc[0])
    last_price = float(df["close"].iloc[-1])
    total_return = (last_price / first_price - 1) * 100 if first_price else 0.0
    news_rows = df[df["has_news"]]
    return {
        "first_price": first_price,
        "last_price": last_price,
        "total_return": total_return,
        "total_news": int(df["news_count"].sum()),
        "positive_days": int((news_rows["sentiment"] > 0).sum()),
        "negative_days": int((news_rows["sentiment"] < 0).sum()),
        "neutral_days": int((news_rows["sentiment"] == 0).sum()),
        "latest_rsi": float(df["rsi_14"].dropna().iloc[-1]) if df["rsi_14"].notna().any() else None,
    }
