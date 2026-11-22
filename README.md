# Smart Stock Analyzer

A Streamlit web app for exploring stock price history, Yahoo Finance RSS headlines,
basic dictionary-based headline sentiment, technical indicators, and a paper portfolio calculator.

## Features
- Stock history via `yfinance`
- Yahoo Finance RSS headline retrieval
- Simple, transparent dictionary-based sentiment score
- SMA 20 / SMA 50, MACD, RSI 14
- Interactive Plotly charts
- CSV export
- Arabic and English interface
- Paper portfolio calculator (no brokerage connection or real trades)

## Important limitations
- Headline sentiment is a simple word-list heuristic, not a trained AI model.
- Yahoo Finance RSS availability and `yfinance` data availability can change.
- News-to-session alignment is a daily approximation. It does not model intraday timing or prove causation.
- Market data may be delayed, incomplete, adjusted, or unavailable for some tickers.
- This app is for education and information, not investment advice.

## Run locally (Windows / macOS / Linux)

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended):

   Windows:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

   macOS / Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

5. Start the app:
   ```bash
   streamlit run app.py
   ```

Streamlit will print a local URL, usually http://localhost:8501.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository and upload `app.py`, `analyzer.py`, and `requirements.txt`.
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Create an app, select the repository/branch, and set the main file to `app.py`.
4. Deploy.

Do not upload passwords, API keys, or private account information to GitHub.
