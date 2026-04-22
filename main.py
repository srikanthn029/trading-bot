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


# ========= TELEGRAM =========
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except:
        pass


# ========= DATA =========
def get_data(symbol):
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": "5m", "limit": 100}

        res = requests.get(url, params=params, timeout=5)

        if res.status_code != 200:
            return None

        data = res.json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        df = pd.DataFrame(data)

        df.columns = [
            "time","o","h","l","c","v",
            "ct","q","n","taker_base","taker_quote","ignore"
        ]

        for col in ["o","h","l","c"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna()

        # 🔥 IMPORTANT SAFETY
        if df.shape[0] < 10:
            return None

        return df

    except Exception as e:
        print("DATA ERROR:", e)
        return None


# ========= SCANNER =========
def scan_coins():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 50,
                "price_change_percentage": "1h,24h"
            },
            timeout=5
        )

        if r.status_code != 200:
            print("⚠️ API ERROR:", r.status_code)
            return []

        data = r.json()

        # 🔥 CRITICAL FIX
        if not isinstance(data, list):
            print("⚠️ Rate limit / bad response:", data)
            return []

        coins = []

        for c in data:
            if not isinstance(c, dict):
                continue

            price = c.get("current_price", 0)
            vol = c.get("total_volume", 0)
            c1h = c.get("price_change_percentage_1h_in_currency", 0)

            if price < 0.05 or vol < 5_000_000:
                continue

            score = abs(c1h) * 2 + abs(c.get("price_change_percentage_24h", 0))

            coins.append((c["symbol"].upper() + "USDT", score, c1h))

        coins.sort(key=lambda x: x[1], reverse=True)

        return coins[:10]

    except Exception as e:
        print("SCANNER ERROR:", e)
        return []


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

Trade Size: {trade_size}
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

        if df is None or len(df) == 0 or "c" not in df.columns:
            print(f"⚠️ Skipping {trade['symbol']} (no data)")
            new_trades.append(trade)
            continue

        try:
            price = df["c"].iloc[-1]
        except:
            print(f"⚠️ Price error {trade['symbol']}")
            new_trades.append(trade)
            continue

        entry = trade["entry"]
        tp = trade["tp"]
        size = trade["size"]

        exit_hit = False

        # ===== PROFIT =====
        if trade["direction"] == "LONG" and price >= tp:
            pnl = 0.10
            exit_hit = True

        elif trade["direction"] == "SHORT" and price <= tp:
            pnl = 0.10
            exit_hit = True

        # ===== STOP LOSS =====
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
        print("⚠️ No coins found")
        return

    while len(active_trades) < MAX_TRADES:
        for symbol, score, c1h in coins:

            if symbol in [t["symbol"] for t in active_trades]:
                continue

            df = get_data(symbol)

            if df is None or len(df) == 0 or "c" not in df.columns:
                print(f"⚠️ Skipping {symbol}")
                continue

            try:
                price = df["c"].iloc[-1]
            except:
                continue

            direction = "LONG" if c1h > 0 else "SHORT"

            open_trade(symbol, direction, price, score)
            break
        else:
            break


# ========= LOOP =========
print("🚀 BOT STARTED (FINAL STABLE VERSION)\n")

while True:
    try:
        run()
        time.sleep(20)
    except Exception as e:
        print("CRASH:", e)
        time.sleep(10)
