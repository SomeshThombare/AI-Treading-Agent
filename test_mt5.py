import MetaTrader5 as mt5

mt5.initialize()

print("--- Forex Pairs ---")
forex = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", 
         "USDCAD", "USDCHF", "NZDUSD", "EURGBP"]
for sym in forex:
    tick = mt5.symbol_info_tick(sym)
    print(f"{sym:12} = {tick.ask if tick else 'NOT AVAILABLE'}")

print("\n--- Commodities ---")
commodities = ["XAUUSD", "XAGUSD", "XTIUSD", "XBRUSD"]
for sym in commodities:
    tick = mt5.symbol_info_tick(sym)
    print(f"{sym:12} = {tick.ask if tick else 'NOT AVAILABLE'}")

print("\n--- Crypto ---")
crypto = ["BTCUSD", "ETHUSD", "BNBUSD", "SOLUSD"]
for sym in crypto:
    tick = mt5.symbol_info_tick(sym)
    print(f"{sym:12} = {tick.ask if tick else 'NOT AVAILABLE'}")

mt5.shutdown()
print("\nDone!")