"""Daily stock screener: actual lowest daily closing prices over each lookback window."""
import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
STOCKS = ROOT / "stocks-short-term.csv"
OUTPUT = ROOT / "docs" / "short-term-data.json"
EXCHANGE_SUFFIX = {
    "NASDAQ":"", "NYSE":"", "AMEX":"", "AMS":".AS", "BRU":".BR",
    "PAR":".PA", "GER":".DE", "XETRA":".DE", "LSE":".L",
    "SWX":".SW", "MIL":".MI", "MAD":".MC", "STO":".ST",
    "OSL":".OL", "CPH":".CO", "HEL":".HE", "ASX":".AX", "TSX":".TO"
}

def clean(value):
    return (value or "").strip().upper()

def yahoo_symbol(row):
    ticker = clean(row["symbol"]).split("|")[0].strip()
    if not re.fullmatch(r"[A-Z0-9.\-^]{1,24}", ticker):
        raise ValueError("Invalid ticker")
    exchange = clean(row.get("exchange", ""))
    if exchange and exchange not in EXCHANGE_SUFFIX:
        raise ValueError("Unknown exchange: " + exchange)
    suffix = EXCHANGE_SUFFIX.get(exchange, "")
    return ticker if not suffix or ticker.endswith(suffix) else ticker + suffix

def read_stocks():
    with STOCKS.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    seen, output = set(), []
    for row in rows:
        row = {k:(v or "").strip() for k,v in row.items() if k}
        row["symbol"] = clean(row.get("symbol", "")).split("|")[0].strip()
        row["isin"] = clean(row.get("isin", ""))
        row["exchange"] = clean(row.get("exchange", ""))
        if not row["symbol"]:
            continue
        key = (row["symbol"], row["exchange"])
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output

def calculate(history):
    history = history.dropna().sort_index()
    if history.empty:
        raise ValueError("No price history")
    if getattr(history.index, "tz", None):
        history.index = history.index.tz_localize(None)
    date = history.index[-1].date()
    current = float(history.iloc[-1])
    lows = {}
    for label, months in [("1m", 1), ("3m", 3), ("6m", 6), ("1y", 12)]:
        start = pd.Timestamp(date) - pd.DateOffset(months=months)
        window = history.loc[history.index >= start]
        # Only show a minimum if the time series covers the whole requested period.
        has_full_window = history.index[0] <= start
        lows[label] = round(float(window.min()), 4) if has_full_window and not window.empty else None
    return round(current, 4), str(date), lows

def sync():
    """Fetch watchlist prices in batches, then write one complete snapshot.

    Public price feeds can fail or throttle; preserve prior valid quotes as stale
    instead of replacing them with missing values.
    """
    rows = read_stocks()
    previous = {}
    if OUTPUT.exists():
        try:
            previous = {
                (x["symbol"], x["exchange"]): x
                for x in json.loads(OUTPUT.read_text(encoding="utf-8")).get("stocks", [])
            }
        except (ValueError, KeyError):
            pass

    currency_by_exchange = {
        "NASDAQ": "USD", "NYSE": "USD", "AMEX": "USD",
        "AMS": "EUR", "BRU": "EUR", "PAR": "EUR", "GER": "EUR",
        "XETRA": "EUR", "MIL": "EUR", "MAD": "EUR", "LSE": "GBp",
        "SWX": "CHF", "STO": "SEK", "OSL": "NOK", "CPH": "DKK",
        "HEL": "EUR", "ASX": "AUD", "TSX": "CAD",
    }
    results = []
    ticker_rows = {}
    for row in rows:
        result = {
            **row, "provider_symbol": None, "price": None,
            "currency": currency_by_exchange.get(row["exchange"]),
            "price_date": None, "lows": {
                "1m": None, "3m": None, "6m": None, "1y": None,
            }, "status": "error", "error": None,
        }
        try:
            ticker = yahoo_symbol(row)
            result["provider_symbol"] = ticker
            ticker_rows.setdefault(ticker, []).append(result)
        except Exception as exc:
            result["error"] = str(exc)[:180]
        results.append(result)

    tickers = list(ticker_rows)
    batch_size = 25
    for start_idx in range(0, len(tickers), batch_size):
        batch = tickers[start_idx : start_idx + batch_size]
        print(f"Batch {start_idx // batch_size + 1}: {len(batch)} tickers", flush=True)
        try:
            data = yf.download(
                tickers=batch, period="18mo", interval="1d",
                auto_adjust=False, actions=False, group_by="ticker",
                threads=False, progress=False, timeout=20,
            )
            for ticker in batch:
                for result in ticker_rows[ticker]:
                    try:
                        if data.empty:
                            raise ValueError("No data returned for batch")
                        if isinstance(data.columns, pd.MultiIndex):
                            # group_by=ticker yields (ticker, field). For
                            # some yfinance versions single-ticker downloads
                            # use (field, ticker); support both.
                            if ticker in data.columns.get_level_values(0):
                                frame = data[ticker]
                            elif ticker in data.columns.get_level_values(1):
                                frame = data.xs(ticker, axis=1, level=1)
                            else:
                                raise ValueError("Ticker missing from batch")
                        else:
                            if len(batch) != 1:
                                raise ValueError("Unexpected response structure")
                            frame = data
                        if "Close" not in frame.columns:
                            raise ValueError("No Close column")
                        price, date, lows = calculate(frame["Close"])
                        result.update(price=price, price_date=date, lows=lows, status="ok")
                    except Exception as exc:
                        result["error"] = str(exc)[:180]
        except Exception as exc:
            for ticker in batch:
                for result in ticker_rows[ticker]:
                    result["error"] = ("Batch error: " + str(exc))[:180]

        # Write progress logs and pause to reduce burst rate.
        successful = sum(
            r["status"] == "ok"
            for ticker in batch for r in ticker_rows[ticker]
        )
        print(f"Batch complete: {successful} / {len(batch)} rows", flush=True)
        if start_idx + batch_size < len(tickers):
            time.sleep(3)

    for result in results:
        if result["status"] == "ok":
            continue
        old = previous.get((result["symbol"], result["exchange"]))
        if old and old.get("price") is not None and old.get("lows"):
            for field in ("price", "currency", "price_date", "lows"):
                result[field] = old.get(field)
            result["status"] = "stale"

    OUTPUT.parent.mkdir(exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "success": sum(x["status"] == "ok" for x in results),
        "stocks": results,
    }, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Finished: {len(results)} stocks; "
          f"{sum(x['status'] == 'ok' for x in results)} updated", flush=True)

def add_stock(args):
    symbol = clean(args.symbol).split("|")[0].strip()
    isin, exchange = clean(args.isin), clean(args.exchange)
    if not re.fullmatch(r"[A-Z0-9.\-^]{1,24}", symbol):
        raise ValueError("Invalid stock symbol")
    if isin and not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        raise ValueError("Invalid ISIN format")
    if exchange not in EXCHANGE_SUFFIX:
        raise ValueError("Unknown exchange: " + exchange)
    rows = read_stocks()
    if any(x["symbol"]==symbol and x["exchange"]==exchange for x in rows):
        print("Already in watchlist")
        return
    rows.append({"symbol":symbol,"isin":isin,"exchange":exchange,"name":args.name or symbol})
    with STOCKS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol","isin","exchange","name"])
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--add",action="store_true")
    for option in ("symbol","isin","exchange","name"):
        parser.add_argument("--"+option,default="")
    args=parser.parse_args()
    add_stock(args) if args.add else sync()
