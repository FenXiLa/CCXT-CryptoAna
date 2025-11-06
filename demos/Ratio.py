import os
import pandas as pd
import ccxt
import talib
import numpy as np

    
proxy_config = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

# 初始化交易所连接（使用币安）
# 如需使用其他交易所，可修改为 ccxt.huobi(), ccxt.okx() 等
exchange = ccxt.binance({
    'proxies': proxy_config,  # 代理配置
    'options': {
        'defaultType': 'swap'
    }
})

# print("24hr价格变动情况")
# print("BTCUSDT:")
# print(exchange.fetch_ticker("BTCUSDT"))

# print("ETHUSDT:")
# print(exchange.fetch_ticker("ETHUSDT"))

# print("SOLUSDT:")
# print(exchange.fetch_ticker("SOLUSDT"))

# print("DOGEUSDT:")
# print(exchange.fetch_ticker("DOGEUSDT"))

# print("BNBUSDT:")
# print(exchange.fetch_ticker("BNBUSDT"))
# print("--------------------------------")

# print("获取未平仓合约数")
# print(exchange.fetch_open_interest("BTCUSDT"))

# print("ETHUSDT:")
# print(exchange.fetch_open_interest("ETHUSDT"))

# print("SOLUSDT:")
# print(exchange.fetch_open_interest("SOLUSDT"))

# print("DOGEUSDT:")
# print(exchange.fetch_open_interest("DOGEUSDT"))

# print("BNBUSDT:")
# print(exchange.fetch_open_interest("BNBUSDT"))

# print("--------------------------------")

# print("合约持仓量历史")
# print(exchange.fetch_open_interest_history("BTCUSDT",timeframe="1h"))
# print("--------------------------------")


# print("大户持仓量多空比")
# print(exchange.fetch_long_short_ratio_history("BTCUSDT",timeframe="1h"))
# print("--------------------------------")



# exchange.fapidata_get_takerlongshortratio()

from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager

# 读取环境变量中的 API Key/Secret（如果没有可以保持 None 使用公共接口）
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(
    api_key=api_key,
    api_secret=api_secret,
    requests_params={
        "timeout": 15,
        "proxies": proxy_config,
    },
)
# get all symbol prices
# prices = client.get_all_tickers()
# print(prices)

print("合约主动买卖量")
ratios = client.futures_taker_longshort_ratio(symbol="BTCUSDT", period="1h", limit=100, startTime=None, endTime=None)
print(ratios)
print("--------------------------------")

print("多空持仓人数比(Global Long/Short Ratio)")
ratios = client.futures_global_longshort_ratio(symbol="BTCUSDT", period="1h", limit=100, startTime=None, endTime=None)
print(ratios)
print("--------------------------------")

print("大户账户数多空比(大户指保证金余额排名前20%的用户)")
ratios = client.futures_top_longshort_account_ratio(symbol="BTCUSDT", period="1h", limit=100, startTime=None, endTime=None)
print(ratios)
print("--------------------------------")

print("大户持仓量多空比(大户指保证金余额排名前20%的用户)")
ratios = client.futures_top_longshort_position_ratio(symbol="BTCUSDT", period="1h", limit=100, startTime=None, endTime=None)
print(ratios)
print("--------------------------------")

print("24hr价格变动情况(24小时滚动窗口价格变动统计数据)")
ticker = client.futures_ticker(symbol="BTCUSDT")
print(ticker)
print("--------------------------------")