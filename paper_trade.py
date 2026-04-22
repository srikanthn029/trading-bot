from binance.client import Client
import pandas as pd
import requests
import time

# ========= CONFIG =========
BOT_TOKEN = "8723933981:AAFJQV2G2kDGi4hzNJ5IB3VtNiMCyapGfvQ"
CHAT_ID = "995122719"

TOTAL_CAPITAL = 100000
TRADE_SIZE = TOTAL_CAPITAL / 4
LEVERAGE = 10

MAX_TRADES = 4

client = Client()

# ========= STATE =========
active_trades = []
balance = TOTAL_CAPITAL


# ========= TELEGRAM =========
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass


# ========= DATA =========
def get_data(symbol):
    klines = client.futures_klines(symbol=symbol, interval="5m", limit=100)

    df = pd.DataFrame(klines, columns=[
        "time","o","h","l","c","v",
        "ct","q","n","taker_base","taker_quote","ignore"
    ])

    for col in ["o","h","l","c"]:
        df[col] = df[col].astype(float)

    return df


# ========= SCANNER =========
def scan_coins():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": 50,
            "price_change_percentage": "1h,24h"
        })

        data = r.json()
        coins = []

        for c in data:
            price = c.get("current_price", 0)
            vol = c.get("total_volume", 0)
            c1h = c.get("price_change_percentage_1h_in_currency", 0)

            if price < 0.05 or vol < 5_000_000:
                continue

            score = abs(c1h) * 2 + abs(c.get("price_change_percentage_24h", 0))

            coins.append((c["symbol"].upper()+"USDT", score, c1h))

        coins.sort(key=lambda x: x[1], reverse=True)

        return coins[:10]

    except:
        return []


# ========= ENTRY =========
def open_trade(symbol, direction, price, score):
    # TP = 1%
    if direction == "LONG":
        tp = price * 1.01
    else:
        tp = price * 0.99

    trade = {
        "symbol": symbol,
        "direction": direction,
        "entry": price,
        "tp": tp
    }

    active_trades.append(trade)

    msg = f"""
📢 ENTRY {direction}

Coin: {symbol}

Entry: {round(price,4)}
TP: {round(tp,4)}

Score: {round(score,2)}

Active Trades: {len(active_trades)}/4
Balance: {round(balance,2)}
"""
    print(msg)
    send_telegram(msg)


# ========= EXIT =========
def check_trades():
    global active_trades, balance

    new_trades = []

    for trade in active_trades:
        df = get_data(trade["symbol"])
        price = df["c"].iloc[-1]

        entry = trade["entry"]
        tp = trade["tp"]

        exit_hit = False

        # ===== PROFIT =====
        if trade["direction"] == "LONG" and price >= tp:
            pnl = 0.10   # 10% profit
            exit_hit = True

        elif trade["direction"] == "SHORT" and price <= tp:
            pnl = 0.10
            exit_hit = True

        # ===== STOP LOSS (50%) =====
        elif trade["direction"] == "LONG" and price <= entry * 0.95:
            pnl = -0.50
            exit_hit = True

        elif trade["direction"] == "SHORT" and price >= entry * 1.05:
            pnl = -0.50
            exit_hit = True

        if exit_hit:
            profit = TRADE_SIZE * pnl
            balance += profit

            msg = f"""
✅ EXIT {trade['direction']}
Coin: {trade['symbol']}

Trade PnL: {round(pnl*100,2)}%
Trade Profit: {round(profit,2)}

💰 Total Balance: {round(balance,2)}
"""
            print(msg)
            send_telegram(msg)

        else:
            new_trades.append(trade)

    active_trades = new_trades


# ========= MAIN =========
def run():
    global active_trades

    check_trades()

    while len(active_trades) < MAX_TRADES:
        coins = scan_coins()

        for symbol, score, c1h in coins:
            if symbol in [t["symbol"] for t in active_trades]:
                continue

            df = get_data(symbol)
            price = df["c"].iloc[-1]

            direction = "LONG" if c1h > 0 else "SHORT"

            open_trade(symbol, direction, price, score)
            break
        else:
            break


# ========= LOOP =========
while True:
    try:
        run()
        time.sleep(15)
    except Exception as e:
        print("Error:", e)
        time.sleep(5)