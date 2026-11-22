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
STOCKS = ROOT / "stocks.csv"
OUTPUT = ROOT / "docs" / "data.json"
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
    rows = read_stocks()
    previous = {}
    if OUTPUT.exists():
        try:
            previous = {(x["symbol"], x["exchange"]): x for x in json.loads(OUTPUT.read_text(encoding="utf-8")).get("stocks", [])}
        except (ValueError, KeyError):
            pass
    results = []
    for i, row in enumerate(rows, 1):
        result = {**row, "provider_symbol":None, "price":None, "currency":None, "price_date":None,
                  "lows":{"1m":None,"3m":None,"6m":None,"1y":None}, "status":"error", "error":None}
        try:
            ticker = yahoo_symbol(row)
            result["provider_symbol"] = ticker
            security = yf.Ticker(ticker)
            history = security.history(period="18mo", interval="1d", auto_adjust=False, actions=False)
            if history.empty or "Close" not in history:
                raise ValueError("No history; verify symbol and exchange")
            price, date, lows = calculate(history["Close"])
            result.update(price=price, price_date=date, lows=lows, status="ok")
            try:
                result["currency"] = security.fast_info.currency
            except Exception:
                pass
        except Exception as exc:
            result["error"] = str(exc)[:180]
            old = previous.get((row["symbol"], row["exchange"]))
            if old and old.get("price") is not None:
                for field in ("price", "currency", "price_date", "lows"):
                    result[field] = old.get(field)
                result["status"] = "stale"
        results.append(result)
        print(f'{i}/{len(rows)} {row["symbol"]}: {result["status"]}', flush=True)
        if i % 50 == 0:
            time.sleep(3)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),
                 "total":len(results), "success":sum(x["status"]=="ok" for x in results),
                 "stocks":results}, indent=2), encoding="utf-8")

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
