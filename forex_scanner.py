import os
import time
import pandas as pd
import requests
import yfinance as yf

TIMEFRAMES = ["4h", "30m"]

# MINOR + CROSS FOREX PAIRS
SYMBOLS = [
    "AUD/NZD",
    "AUD/CAD",
    "AUD/CHF",
    "AUD/JPY",
    "CAD/CHF",
    "CAD/JPY",
    "CHF/JPY",
    "EUR/AUD",
    "EUR/CAD",
    "EUR/CHF",
    "EUR/GBP",
    "EUR/NZD",
    "EUR/JPY",
    "GBP/AUD",
    "GBP/CAD",
    "GBP/CHF",
    "GBP/JPY",
    "GBP/NZD",
    "NZD/CAD",
    "NZD/CHF",
    "NZD/JPY",
]

EMA_PERIODS = [20, 50, 100, 200]

# Maximum distance between the 4 EMAs
GATE_MAX_SPREAD_PCT = 0.50

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=20
        )

        print("Telegram:", response.status_code)

    except Exception as e:
        print("Telegram error:", e)


def get_data(symbol, timeframe):

    yahoo_symbol = symbol.replace("/", "") + "=X"

    try:
        df = yf.download(
            yahoo_symbol,
            period="2y",
            interval=timeframe,
            progress=False,
            auto_adjust=False
        )

        if df is None or len(df) < 220:
            print("Not enough data:", symbol, timeframe)
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        return df

    except Exception as e:
        print("Data error:", symbol, timeframe, e)
        return None


def check_gate(symbol, timeframe):

    df = get_data(symbol, timeframe)

    if df is None or len(df) < 220:
        return None

    close = df["Close"]

    # Calculate EMAs
    for period in EMA_PERIODS:
        df[f"EMA{period}"] = close.ewm(
            span=period,
            adjust=False
        ).mean()

    latest = df.iloc[-1]
    previous = df.iloc[-2]
    previous2 = df.iloc[-3]
    previous3 = df.iloc[-4]

    # Current EMA values
    ema_values = [
        latest["EMA20"],
        latest["EMA50"],
        latest["EMA100"],
        latest["EMA200"]
    ]

    previous_values = [
        previous["EMA20"],
        previous["EMA50"],
        previous["EMA100"],
        previous["EMA200"]
    ]

    # Current spread
    spread = max(ema_values) - min(ema_values)

    price = float(latest["Close"])

    if price == 0:
        return None

    spread_pct = (spread / price) * 100

    # Previous spread
    previous_spread = (
        max(previous_values) -
        min(previous_values)
    ) / float(previous["Close"]) * 100

    # 2 candles ago
    previous2_values = [
        previous2["EMA20"],
        previous2["EMA50"],
        previous2["EMA100"],
        previous2["EMA200"]
    ]

    previous2_spread = (
        max(previous2_values) -
        min(previous2_values)
    ) / float(previous2["Close"]) * 100

    # 3 candles ago
    previous3_values = [
        previous3["EMA20"],
        previous3["EMA50"],
        previous3["EMA100"],
        previous3["EMA200"]
    ]

    previous3_spread = (
        max(previous3_values) -
        min(previous3_values)
    ) / float(previous3["Close"]) * 100

    # Gate must be tight
    tight_gate = spread_pct <= GATE_MAX_SPREAD_PCT

    # Gate must be tightening for 3 consecutive candles
    tightening = (
        spread_pct < previous_spread
        and previous_spread < previous2_spread
        and previous2_spread < previous3_spread
    )

    if not tight_gate:
        return None

    if not tightening:
        return None

    # EMA200 direction
    ema200_rising = (
        latest["EMA200"] > previous["EMA200"]
    )

    ema200_falling = (
        latest["EMA200"] < previous["EMA200"]
    )

    bullish = (
        price > latest["EMA200"]
        and ema200_rising
    )

    bearish = (
        price < latest["EMA200"]
        and ema200_falling
    )

    if bullish:
        direction = "🟢 BULLISH GATE"

    elif bearish:
        direction = "🔴 BEARISH GATE"

    else:
        return None

    message = (
        "🚨 MINOR + CROSS EMA GATE ALERT 🚨\n\n"

        f"Pair: {symbol}\n"
        f"Timeframe: {timeframe.upper()}\n"
        f"Direction: {direction}\n\n"

        f"Price: {price:.5f}\n"
        f"EMA20: {latest['EMA20']:.5f}\n"
        f"EMA50: {latest['EMA50']:.5f}\n"
        f"EMA100: {latest['EMA100']:.5f}\n"
        f"EMA200: {latest['EMA200']:.5f}\n\n"

        f"EMA Spread: {spread_pct:.3f}%\n\n"

        "⚠️ Gate is forming before breakout."
    )

    return message


def main():

    print("================================")
    print("MINOR + CROSS EMA GATE SCANNER")
    print("Data: Yahoo Finance")
    print("Timeframes: 4H + 30M")
    print("Pairs:", len(SYMBOLS))
    print("================================")

    for symbol in SYMBOLS:

        for timeframe in TIMEFRAMES:

            print(
                f"Checking: {symbol} | "
                f"{timeframe.upper()}"
            )

            alert = check_gate(
                symbol,
                timeframe
            )

            if alert:

                print(alert)

                send_telegram(alert)

            else:

                print(
                    f"No gate: {symbol} | "
                    f"{timeframe.upper()}"
                )

            time.sleep(1)

    print("================================")
    print("FOREX MINOR + CROSS SCAN COMPLETE")
    print("================================")


if __name__ == "__main__":
    main()
