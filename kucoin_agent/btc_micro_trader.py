import ccxt
import time
import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

# === LOCKFILE PROTECTION ===
LOCK_FILE = "bot.lock"
if os.path.exists(LOCK_FILE):
    print("❌ Bot déjà en cours d'exécution.")
    sys.exit()
with open(LOCK_FILE, "w") as f:
    f.write("running")

# === CONFIGURATION ===
SYMBOL = "BTC/USDT"
TIMEFRAME = "1m"
RSI_PERIOD = 3
TRADE_INTERVAL = 60  # every minute
TRADE_AMOUNT_USD = 1.0
TAKE_PROFIT_RATIO = 0.007  # +0.7%
MIN_PROFIT_USD = 0.01
POSITIONS_FILE = "positions.json"
CSV_LOG_FILE = "trade_log.csv"
MAX_POSITIONS = 50

exchange = ccxt.kucoin({
    'apiKey': os.getenv("KUCOIN_API_KEY"),
    'secret': os.getenv("KUCOIN_API_SECRET"),
    'password': os.getenv("KUCOIN_API_PASSPHRASE"),
    'enableRateLimit': True,
})

# === UTILS ===
def log(msg):
    console.print(f"[bold cyan]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/] {msg}")

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_positions(positions):
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions[-MAX_POSITIONS:], f, indent=2)

def log_trade_to_csv(timestamp, action, amount, price, pnl):
    exists = os.path.exists(CSV_LOG_FILE)
    with open(CSV_LOG_FILE, 'a') as f:
        if not exists:
            f.write("timestamp,action,btc_amount,price,pnl\n")
        f.write(f"{timestamp},{action},{amount},{price},{pnl}\n")

def fetch_rsi(symbol, timeframe, period):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=period + 2)
    closes = [c[4] for c in ohlcv]
    if len(closes) < period + 1:
        return None, closes[-1]
    deltas = [closes[i+1] - closes[i] for i in range(period)]
    gains = sum(max(d, 0) for d in deltas) / period
    losses = sum(-min(d, 0) for d in deltas) / period
    rs = gains / losses if losses else 100
    rsi = 100 - (100 / (1 + rs))
    return rsi, closes[-1]

def get_usdt_balance(balance):
    return balance['free'].get('USDT', 0)

def print_summary(price, rsi, btc, usdt, wallet_total, pnl_total):
    table = Table(title="[bold yellow]MicroGrid RSI Bot Dashboard")
    table.add_column("[green]Prix BTC", justify="right")
    table.add_column("[blue]RSI", justify="right")
    table.add_column("[magenta]BTC", justify="right")
    table.add_column("[cyan]USDT", justify="right")
    table.add_column("[bold]Portefeuille", justify="right")
    table.add_column("[bold red]P&L Total", justify="right")
    table.add_row(f"{price:.2f}", f"{rsi:.2f}", f"{btc:.6f}", f"{usdt:.2f}", f"{wallet_total:.2f}", f"{pnl_total:.2f}")
    console.clear()
    console.print(table)

def run_bot():
    log("🤖 Lancement du bot MicroGrid RSI avec dashboard...")
    positions = load_positions()
    pnl_total = 0.0

    try:
        while True:
            try:
                rsi, price = fetch_rsi(SYMBOL, TIMEFRAME, RSI_PERIOD)
                if rsi is None:
                    log("⚠️ RSI indisponible.")
                    time.sleep(TRADE_INTERVAL)
                    continue

                balance = exchange.fetch_balance()
                btc = balance['free'].get('BTC', 0)
                usdt = get_usdt_balance(balance)
                btc_value = btc * price
                wallet_total = btc_value + usdt

                # DASHBOARD
                print_summary(price, rsi, btc, usdt, wallet_total, pnl_total)

                to_remove = []
                for pos in positions:
                    gain_ratio = (price - pos['buy_price']) / pos['buy_price']
                    profit = round((price - pos['buy_price']) * pos['btc_amount'], 4)
                    if (gain_ratio >= TAKE_PROFIT_RATIO or rsi > 75) and profit >= MIN_PROFIT_USD:
                        btc_amount = pos['btc_amount']
                        exchange.create_market_sell_order(SYMBOL, btc_amount)
                        pnl_total += profit
                        log(f"✅ Vente {btc_amount} BTC | 💰 P&L: {profit:.2f} $ | 🔁 Total: {pnl_total:.2f} $")
                        log_trade_to_csv(datetime.now().isoformat(), "sell", btc_amount, price, profit)
                        to_remove.append(pos)

                for pos in to_remove:
                    positions.remove(pos)

                if rsi < 25 and usdt >= TRADE_AMOUNT_USD:
                    btc_amount = round(TRADE_AMOUNT_USD / price, 6)
                    exchange.create_market_buy_order(SYMBOL, btc_amount)
                    positions.append({
                        "timestamp": datetime.now().isoformat(),
                        "btc_amount": btc_amount,
                        "buy_price": price
                    })
                    log(f"🟢 Achat {btc_amount} BTC @ {price:.2f} $")
                    log_trade_to_csv(datetime.now().isoformat(), "buy", btc_amount, price, 0)

                save_positions(positions)
                time.sleep(TRADE_INTERVAL)

            except Exception as e:
                log(f"💥 Erreur : {e}")
                time.sleep(TRADE_INTERVAL)

    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == "__main__":
    run_bot()