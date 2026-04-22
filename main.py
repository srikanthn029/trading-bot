import pandas as pd
import requests
import time

# ========= CONFIG =========
BOT_TOKEN = "8723933981:AAFJQV2G2kDGi4hzNJ5IB3VtNiMCyapGfvQ"
CHAT_ID = "995122719"

TOTAL_CAPITAL = 100000
MAX_TRADES = 4

active_trades = []
balance = TOTAL_CAPITAL

# ========= SELECTED COINS ONLY =========
SYMBOLS = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
    "AVAXUSDT","LINKUSDT","POLUSDT","DOGEUSDT","APTUSDT",
    "SUIUSDT","NEARUSDT","ARBUSDT","OPUSDT","INJUSDT",
    "RNDRUSDT","FETUSDT","SEIUSDT","KASUSDT","XLMUSDT"
]

# ========= TELEGRAM =========
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass


# ========= DATA =========
def get_data(symbol):
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": "5m", "limit": 50}

        data = requests.get(url, params=params).json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        df = pd.DataFrame(data, columns=[
            "time","o","h","l","c","v",
            "ct","q","n","taker_base","taker_quote","ignore"
        ])

        df["c"] = pd.to_numeric(df["c"])
        return df

    except:
        return None


# ========= IMPROVED MOMENTUM =========
def scan_coins():
    results = []

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if df is None or len(df) < 20:
            continue

        try:
            price_now = df["c"].iloc[-1]
            price_5 = df["c"].iloc[-5]
            price_15 = df["c"].iloc[-15]

            # short + medium momentum
            change_5 = ((price_now - price_5) / price_5) * 100
            change_15 = ((price_now - price_15) / price_15) * 100

            # combined score
            score = abs(change_5) * 2 + abs(change_15)

            # filter weak moves
            if abs(change_5) < 0.3:
                continue

            results.append((symbol, score, change_5))

        except:
            continue

    results.sort(key=lambda x: x[1], reverse=True)

    return results[:5]


# ========= ENTRY =========
def open_trade(symbol, direction, price, score):
    global balance

    trade_size = round(balance / 4, 2)

    tp = price * 1.01 if direction == "LONG" else price * 0.99

    trade = {
        "symbol": symbol,
        "direction": direction,
        "entry": price,
        "tp": tp,
        "size": trade_size
    }

    active_trades.append(trade)

    msg = f"""
📢 ENTRY {direction}

Coin: {symbol}
Entry: {round(price,4)}
TP: {round(tp,4)}

Size: {trade_size}
Score: {round(score,2)}

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

        if df is None or len(df) == 0:
            new_trades.append(trade)
            continue

        price = df["c"].iloc[-1]

        entry = trade["entry"]
        tp = trade["tp"]
        size = trade["size"]

        exit_hit = False

        # PROFIT
        if trade["direction"] == "LONG" and price >= tp:
            pnl = 0.10
            exit_hit = True

        elif trade["direction"] == "SHORT" and price <= tp:
            pnl = 0.10
            exit_hit = True

        # STOP LOSS
        elif trade["direction"] == "LONG" and price <= entry * 0.95:
            pnl = -0.50
            exit_hit = True

        elif trade["direction"] == "SHORT" and price >= entry * 1.05:
            pnl = -0.50
            exit_hit = True

        if exit_hit:
            profit = size * pnl
            balance += profit

            msg = f"""
✅ EXIT {trade['direction']}
Coin: {trade['symbol']}

PnL: {round(pnl*100,2)}%
Profit: {round(profit,2)}

💰 Balance: {round(balance,2)}
"""
            print(msg)
            send_telegram(msg)
        else:
            new_trades.append(trade)

    active_trades = new_trades


# ========= MAIN =========
def run():
    check_trades()

    coins = scan_coins()

    if not coins:
        print("⚠️ No strong momentum")
        return

    while len(active_trades) < MAX_TRADES:
        for symbol, score, change in coins:

            if symbol in [t["symbol"] for t in active_trades]:
                continue

            df = get_data(symbol)
            if df is None:
                continue

            price = df["c"].iloc[-1]
            direction = "LONG" if change > 0 else "SHORT"

            open_trade(symbol, direction, price, score)
            break
        else:
            break


# ========= LOOP =========
print("🚀 BOT STARTED (PRO MODE)\n")

while True:
    try:
        run()
        time.sleep(60)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
