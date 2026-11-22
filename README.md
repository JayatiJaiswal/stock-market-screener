# Market Pulse — Automated Stock Screener

A daily, sortable spreadsheet-style stock dashboard for a watchlist of 1,000 or more symbols.

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
- The updater fetches up to 25 symbols per batch, with short pauses between batches. Lists of 1,000+ symbols are supported by the program, but Yahoo Finance can rate-limit, fail or deliver partial data, so completion for every ticker is not guaranteed.

If Actions is disabled, open **Actions** and enable workflows. If the workflow fails to commit updates, go to **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions** if your account settings allow it.

## Add stocks later — Symbol + ISIN + Exchange
The fastest way is **Actions → Daily stock screener update → Run workflow** and supply, for example:
- Symbol: `ARGX`
- ISIN: `NL0010832176`
- Exchange: `BRU`
- Company name: `argenx SE`

The workflow will append it to `stocks.csv` and fetch its history. If the same ticker/exchange already exists, it won't create a duplicate.

To add 1,000 stocks, click **+ Add / bulk-edit stocks** in the dashboard to open the GitHub editor for `stocks.csv`, add or paste new CSV rows under the header (`symbol,isin,exchange,name`), then click **Commit changes**. The daily update workflow will be triggered on the changed watchlist. Do not paste a second header. The dashboard displays 100 rows per page, with search, sorting and Previous/Next controls working across the full data set. You can also upload or replace `stocks.csv` in GitHub with a correctly structured CSV when adding a large list. **ISIN is stored for identification; the data fetch uses the exchange-qualified symbol.** Choose the actual trading exchange carefully, particularly for securities trading on several exchanges.

Exchange codes supported: NASDAQ, NYSE, AMEX, AMS, BRU, PAR, GER, XETRA, LSE, SWX, MIL, MAD, STO, OSL, CPH, HEL, ASX, TSX.

## Calculation
The dashboard shows:
- Last closing price and currency (date is stored but hidden in the table)
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

## Scaling notes
- At least 1,000 symbols may be listed; no hard cap is imposed in the code.
- Fetching uses batched Yahoo Finance downloads. Unofficial API limits, delisted tickers, exchange coverage and GitHub Actions runtime can affect completion.
- Failed stocks preserve their last available values as stale when possible; the dashboard intentionally hides the status column, but the JSON includes per-stock status and error details.
- Avoid using the raw numeric prices as a cross-currency ranking: USD, EUR, GBp etc. are not comparable.
