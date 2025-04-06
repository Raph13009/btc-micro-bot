import ccxt
import os
from dotenv import load_dotenv
load_dotenv()

exchange = ccxt.kucoin({
    'apiKey': os.getenv("KUCOIN_API_KEY"),
    'secret': os.getenv("KUCOIN_API_SECRET"),
    'password': os.getenv("KUCOIN_API_PASSPHRASE"),
    'enableRateLimit': True,
})

SYMBOL = "BTC/USDT"

balance = exchange.fetch_balance()
btc = balance['free'].get('BTC', 0)

if btc > 0.00001:
    exchange.create_market_sell_order(SYMBOL, btc)
    print(f"🛑 Force exit: SELL {btc:.6f} BTC")
else:
    print("✅ Aucun BTC à liquider.")
