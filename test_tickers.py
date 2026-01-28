import yfinance as yf

print("=== Testing problematic tickers ===")
tickers = ['VGIT', 'VGSH', 'MFC', 'BIP', 'CM', 'OGE', 'MDLZ', 'CEPI']

for t in tickers:
    try:
        ticker_obj = yf.Ticker(t)
        info = ticker_obj.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        print(f"{t}: price=${current_price}, type={info.get('quoteType')}, exchange={info.get('exchange')}")
    except Exception as e:
        print(f"{t}: ERROR - {e}")
