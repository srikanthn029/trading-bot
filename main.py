import pandas as pd
import requests
import time

# ========= CONFIG =========
BOT_TOKEN = "8723933981:AAFJQV2G2kDGi4hzNJ5IB3VtNiMCyapGfvQ"
CHAT_ID = "995122719"

TOTAL_CAPITAL = 100000
MAX_TRADES = 4
SCAN_INTERVAL = 180  # 3 min (safe)

# ========= STATE =========
balance = TOTAL_CAPITAL
active_trades = []

# ========= COINS =========
SYMBOLS = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
    "AVAXUSDT","LINKUSDT","POLUSDT","DOGEUSDT","APTUSDT",
    "SUIUSDT","NEARUSDT","ARBUSDT","OPUSDT","INJUSDT",
    "RNDRUSDT","FETUSDT","SEIUSDT","KASUSDT","XLMUSDT"
]

# ========= TELEGRAM =========
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

# ========= DATA =========
def get_data(symbol):
    try:
        res = requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol": symbol, "interval": "5m", "limit": 50},
            timeout=5
        )

        if res.status_code != 200:
            return None

        data = res.json()

        if not isinstance(data, list) or len(data) < 20:
            return None

        df = pd.DataFrame(data, columns=[
            "time","o","h","l","c","v",
            "ct","q","n","taker_base","taker_quote","ignore"
        ])

        df["c"] = pd.to_numeric(df["c"])
        return df

    except:
        return None

# ========= SMART SCANNER =========
def scan_best_coin():
    best = None

    for symbol in SYMBOLS[:10]:  # limit API load
        df = get_data(symbol)
        if df is None:
            continue

        try:
            p_now = df["c"].iloc[-1]
            p_5 = df["c"].iloc[-5]
            p_15 = df["c"].iloc[-15]

            move_short = (p_now - p_5) / p_5 * 100
            move_mid = (p_now - p_15) / p_15 * 100

            score = abs(move_short) * 2 + abs(move_mid)

            if best is None or score > best[1]:
                best = (symbol, score, move_short)

        except:
            continue

    return best

# ========= ENTRY =========
def open_trade(symbol, direction, price, score):
    global balance

    size = round(balance / 4, 2)

    tp = price * 1.01 if direction == "LONG" else price * 0.99

    trade = {
        "symbol": symbol,
        "direction": direction,
        "entry": price,
        "tp": tp,
        "size": size
    }

    active_trades.append(trade)

    msg = f"""
📢 ENTRY {direction}

{symbol}
Entry: {round(price,4)}
TP: {round(tp,4)}

Size: {size}
Score: {round(score,2)}

Balance: {round(balance,2)}
"""
    print(msg)
    send(msg)

# ========= EXIT =========
def manage_trades():
    global balance, active_trades

    updated = []

    for t in active_trades:
        df = get_data(t["symbol"])
        if df is None:
            updated.append(t)
            continue

        price = df["c"].iloc[-1]

        entry = t["entry"]
        size = t["size"]

        exit_trade = False

        # TP
        if t["direction"] == "LONG" and price >= t["tp"]:
            pnl = 0.10
            exit_trade = True

        elif t["direction"] == "SHORT" and price <= t["tp"]:
            pnl = 0.10
            exit_trade = True

        # SL
        elif t["direction"] == "LONG" and price <= entry * 0.95:
            pnl = -0.50
            exit_trade = True

        elif t["direction"] == "SHORT" and price >= entry * 1.05:
            pnl = -0.50
            exit_trade = True

        if exit_trade:
            profit = size * pnl
            balance += profit

            msg = f"""
✅ EXIT {t['direction']}

{t['symbol']}
PnL: {round(pnl*100,2)}%
Profit: {round(profit,2)}

Balance: {round(balance,2)}
"""
            print(msg)
            send(msg)
        else:
            updated.append(t)

    active_trades = updated

# ========= MAIN =========
def run_cycle():
    manage_trades()

    if len(active_trades) >= MAX_TRADES:
        return

    best = scan_best_coin()

    if not best:
        print("No valid data this cycle")
        return

    symbol, score, move = best

    # minimum movement filter (very light)
    if abs(move) < 0.1:
        print(f"{symbol} weak move ({round(move,2)}%)")
        return

    # avoid duplicate
    if symbol in [t["symbol"] for t in active_trades]:
        return

    df = get_data(symbol)
    if df is None:
        return

    price = df["c"].iloc[-1]
    direction = "LONG" if move > 0 else "SHORT"

    open_trade(symbol, direction, price, score)

# ========= LOOP =========
print("🚀 HIGH QUALITY BOT STARTED\n")

while True:
    try:
        run_cycle()
        time.sleep(SCAN_INTERVAL)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
