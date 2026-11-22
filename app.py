from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analyzer import (
    fetch_news, fetch_price_history, add_technical_indicators,
    align_news_to_trading_days, calculate_metrics
)

logging.basicConfig(level=logging.INFO)
st.set_page_config(
    page_title="Smart Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

TEXT = {
    "العربية": {
        "title": "محلل الأسهم الذكي",
        "subtitle": "تحليل أسعار الأسهم والأخبار والمؤشرات الفنية",
        "ticker": "رمز السهم",
        "period": "الفترة الزمنية",
        "language": "اللغة",
        "analyze": "حلّل السهم",
        "loading": "جارٍ جلب البيانات وتحليلها...",
        "price": "آخر سعر إغلاق",
        "return": "العائد خلال الفترة",
        "news": "عدد الأخبار",
        "rsi": "مؤشر RSI (14)",
        "chart": "السعر والمؤشرات الفنية",
        "sentiment": "انطباع الأخبار اليومي",
        "articles": "الأخبار المسترجعة",
        "data": "بيانات التحليل",
        "download": "تنزيل بيانات CSV",
        "no_news": "لم يتم العثور على أخبار في الخلاصة. هذا لا يعني أن الأخبار محايدة.",
        "news_error": "تعذر جلب الأخبار، لكن يمكن عرض بيانات الأسعار.",
        "disclaimer": "هذه الأداة لأغراض تعليمية ومعلوماتية فقط وليست نصيحة استثمارية.",
        "portfolio": "حاسبة المحفظة الافتراضية",
        "shares": "عدد الأسهم",
        "buy": "سعر الشراء لكل سهم",
        "investment": "قيمة الاستثمار",
        "market_value": "القيمة الحالية",
        "pnl": "الربح / الخسارة غير المحققة",
        "technical": "المؤشرات الفنية",
        "news_note": "تصنيف الأخبار يعتمد على قاموس كلمات بسيط، وليس نموذج ذكاء اصطناعي مدرّب.",
        "bad_ticker": "أدخل رمز سهم صالحاً مثل AAPL أو MSFT.",
        "no_data": "لم تتوفر بيانات سعرية لهذا الرمز أو الفترة."
    },
    "English": {
        "title": "Smart Stock Analyzer",
        "subtitle": "Stock prices, financial headlines and technical indicators",
        "ticker": "Stock ticker",
        "period": "Time period",
        "language": "Language",
        "analyze": "Analyze stock",
        "loading": "Fetching and analyzing data...",
        "price": "Latest close",
        "return": "Period return",
        "news": "News articles",
        "rsi": "RSI (14)",
        "chart": "Price and technical indicators",
        "sentiment": "Daily news sentiment",
        "articles": "Retrieved headlines",
        "data": "Analysis data",
        "download": "Download CSV data",
        "no_news": "No headlines were found in the feed. This does not mean sentiment is neutral.",
        "news_error": "Could not retrieve news; price data can still be displayed.",
        "disclaimer": "For educational and informational purposes only. Not investment advice.",
        "portfolio": "Paper portfolio calculator",
        "shares": "Number of shares",
        "buy": "Purchase price per share",
        "investment": "Cost basis",
        "market_value": "Current value",
        "pnl": "Unrealized profit / loss",
        "technical": "Technical indicators",
        "news_note": "News sentiment uses a simple word dictionary, not a trained AI model.",
        "bad_ticker": "Enter a valid ticker such as AAPL or MSFT.",
        "no_data": "No price data was returned for this ticker or period."
    }
}

with st.sidebar:
    language = st.selectbox("Language / اللغة", ["العربية", "English"])
    t = TEXT[language]
    st.header("⚙️ " + ("الإعدادات" if language == "العربية" else "Settings"))
    ticker = st.text_input(t["ticker"], value="AAPL", max_chars=15).strip().upper()
    period_labels = {
        "1 شهر": "1mo", "3 أشهر": "3mo", "6 أشهر": "6mo",
        "سنة": "1y", "سنتان": "2y", "5 سنوات": "5y"
    }
    if language == "العربية":
        period_label = st.selectbox(t["period"], list(period_labels.keys()), index=1)
        period = period_labels[period_label]
    else:
        period = st.selectbox(t["period"], ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=1)
    run = st.button("🔍 " + t["analyze"], type="primary", use_container_width=True)

st.title("📈 " + t["title"])
st.caption(t["subtitle"])

if run:
    if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
        st.error(t["bad_ticker"])
        st.stop()

    with st.spinner(t["loading"]):
        try:
            prices = fetch_price_history(ticker, period)
            prices = add_technical_indicators(prices)
        except Exception as exc:
            st.error(f"{t['no_data']} ({exc})")
            st.stop()

        try:
            news = fetch_news(ticker)
            news_error = None
        except Exception as exc:
            news = pd.DataFrame(columns=["published_at", "date", "title", "sentiment", "link"])
            news_error = str(exc)

        result = align_news_to_trading_days(prices, news)
        metrics = calculate_metrics(result)
        st.session_state["analysis"] = {
            "ticker": ticker, "period": period, "result": result,
            "news": news, "metrics": metrics, "news_error": news_error
        }

if "analysis" in st.session_state:
    saved = st.session_state["analysis"]
    ticker = saved["ticker"]
    result = saved["result"]
    news = saved["news"]
    metrics = saved["metrics"]

    if saved["news_error"]:
        st.warning(t["news_error"] + " " + saved["news_error"])
    elif news.empty:
        st.info(t["no_news"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["price"], f"${metrics['last_price']:,.2f}")
    c2.metric(t["return"], f"{metrics['total_return']:+.2f}%")
    c3.metric(t["news"], f"{metrics['total_news']:,}")
    rsi_text = f"{metrics['latest_rsi']:.1f}" if metrics["latest_rsi"] is not None else "N/A"
    c4.metric(t["rsi"], rsi_text)

    st.subheader("📊 " + t["chart"])
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=[0.72, 0.28],
        subplot_titles=("Adjusted closing price", "RSI (14)")
    )
    fig.add_trace(go.Scatter(
        x=result["date"], y=result["close"], name="Close",
        line=dict(width=2)
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=result["date"], y=result["sma_20"], name="SMA 20",
        line=dict(width=1, dash="dot")
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=result["date"], y=result["sma_50"], name="SMA 50",
        line=dict(width=1, dash="dash")
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=result["date"], y=result["rsi_14"], name="RSI 14",
        line=dict(width=1.5)
    ), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_layout(height=650, hovermode="x unified", legend_orientation="h")
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📰 " + t["sentiment"])
    sentiment_fig = go.Figure()
    sentiment_colors = [
        "#16a34a" if x > 0 else "#dc2626" if x < 0 else "#9ca3af"
        for x in result["sentiment"]
    ]
    sentiment_fig.add_trace(go.Bar(
        x=result["date"], y=result["sentiment"],
        marker_color=sentiment_colors, name="Daily sentiment"
    ))
    sentiment_fig.update_layout(height=260, xaxis_title="Date", yaxis_title="Score")
    st.plotly_chart(sentiment_fig, use_container_width=True)

    st.caption(t["news_note"])
    st.subheader("📑 " + t["technical"])
    latest = result.iloc[-1]
    tech1, tech2, tech3 = st.columns(3)
    tech1.metric("SMA 20", f"${latest['sma_20']:.2f}")
    tech2.metric("SMA 50", f"${latest['sma_50']:.2f}")
    tech3.metric("MACD", f"{latest['macd']:.3f}")

    st.subheader("💼 " + t["portfolio"])
    p1, p2 = st.columns(2)
    shares = p1.number_input(t["shares"], min_value=0.0, value=10.0, step=1.0)
    buy_price = p2.number_input(t["buy"], min_value=0.0, value=float(metrics["last_price"]), step=1.0)
    cost = shares * buy_price
    current_value = shares * metrics["last_price"]
    pnl = current_value - cost
    p3, p4, p5 = st.columns(3)
    p3.metric(t["investment"], f"${cost:,.2f}")
    p4.metric(t["market_value"], f"${current_value:,.2f}")
    p5.metric(t["pnl"], f"${pnl:+,.2f}", delta=f"{(pnl / cost * 100):+.2f}%" if cost else None)

    st.subheader("🗞️ " + t["articles"])
    if not news.empty:
        display_news = news.copy()
        display_news["published_at"] = pd.to_datetime(display_news["published_at"]).dt.strftime("%Y-%m-%d %H:%M UTC")
        st.dataframe(
            display_news[["published_at", "sentiment", "title", "link"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "link": st.column_config.LinkColumn("Article link"),
                "sentiment": st.column_config.NumberColumn("Sentiment score")
            }
        )

    st.subheader("📋 " + t["data"])
    st.dataframe(result, use_container_width=True, hide_index=True)
    csv = result.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ " + t["download"],
        data=csv,
        file_name=f"{ticker}_analysis.csv",
        mime="text/csv"
    )
else:
    st.info("👈 " + ("أدخل رمز السهم واضغط «حلّل السهم» للبدء." if language == "العربية" else "Enter a ticker and click Analyze stock to begin."))

st.divider()
st.caption("⚠️ " + t["disclaimer"])
