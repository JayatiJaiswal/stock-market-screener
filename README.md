# Market Pulse — Automated Stock Screener

A daily, sortable spreadsheet-style stock dashboard for a watchlist of up to approximately 600 symbols.

## View the dashboard
After enabling GitHub Pages (see below):
https://jayatijaiswal.github.io/stock-market-screener/

## Activate GitHub Pages (one-time)
1. Open **Settings → Pages** in this repository.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Choose branch **main**, folder **/docs**, and click **Save**.
4. Check the URL above after the first Pages deployment.

## Price updating
GitHub Actions workflow: **Daily stock screener update**.
- Scheduled weekdays at **23:30 UTC** (best effort, may be delayed).
- Also runs when you update `stocks.csv` or the calculation script.
- Manual trigger: **Actions → Daily stock screener update → Run workflow**.
- The first run fetches the initial seven sample stocks.
- After 600 rows are added, the script attempts to download their price history; unofficial Yahoo Finance access may rate-limit requests and may require batching.

If Actions is disabled, open **Actions** and enable workflows. If the workflow fails to commit updates, go to **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions** if your account settings allow it.

## Add stocks later — Symbol + ISIN + Exchange
The fastest way is **Actions → Daily stock screener update → Run workflow** and supply, for example:
- Symbol: `ARGX`
- ISIN: `NL0010832176`
- Exchange: `BRU`
- Company name: `argenx SE`

The workflow will append it to `stocks.csv` and fetch its history. If the same ticker/exchange already exists, it won't create a duplicate.

You can add many stocks at once by editing `stocks.csv` (columns: symbol, isin, exchange, name), then committing the file. **ISIN is stored for identification; the data fetch uses the exchange-qualified symbol.** Choose the actual trading exchange carefully, particularly for securities trading on several exchanges.

Exchange codes supported: NASDAQ, NYSE, AMEX, AMS, BRU, PAR, GER, XETRA, LSE, SWX, MIL, MAD, STO, OSL, CPH, HEL, ASX, TSX.

## Calculation
The dashboard shows:
- Last adjusted closing price, exchange currency, and price date
- 1-month, 3-month, 6-month and 1-year minimum daily closing prices
- Sort by lowest / highest price for any selected period
- Filter stocks trading within 10% of their period low, farther from the low, or missing/stale results
- Search by symbol, ISIN, name or exchange
- Export CSV

Each period displays the **minimum unadjusted daily closing price** observed over the trailing 1, 3, 6 or 12 calendar months, including the latest session. If full historical coverage is unavailable for a window, that field is blank. These are not intraday lows or percent returns. Last close and period lows are denominated in the listing currency (including GBp/pence where applicable). Prices are **not live**, and market holidays vary by exchange.

## Data safety and limitations
- Uses an **unofficial Yahoo Finance data source via yfinance**. Availability is not guaranteed; it can be rate-limited or interrupted.
- Missing updates are marked **stale** when previous data are available, rather than silently labeled current.
- This repository and Pages site are **public**. Keep personal holdings, API keys, passwords, or identifying financial information out of these files.
- This is a watchlist and research tool, not an investment recommendation or prediction.

## Run on your computer
```bash
pip install -r requirements.txt
python sync.py
python -m http.server 8000 --directory docs
```
Open http://localhost:8000.
