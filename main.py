#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CCTX-Ana 基础代码
用于加密货币交易所数据分析
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import json
import pickle
from pathlib import Path
import yaml

# 导入数据库模块
from db import db, load_config

# 排名靠前的10大交易所列表
TOP_EXCHANGES = [
    'binance', 'coinbase', 'okx', 'bybit', 'kucoin', 
    'bitfinex', 'kraken', 'huobi', 'gate', 'mexc'
]

# 支持的时间周期列表
TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '8h', '12h', '1d']

# 数据存储目录
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'data'
CACHE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'cache'

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# 成功交易所缓存文件
SUCCESS_EXCHANGES_FILE = CACHE_DIR / 'success_exchanges.json'

# 加载配置
config = load_config()

def get_exchanges():
    """获取所有可用的交易所列表"""
    return ccxt.exchanges

def load_success_exchanges():
    """加载上次成功的交易所记录"""
    if SUCCESS_EXCHANGES_FILE.exists():
        try:
            with open(SUCCESS_EXCHANGES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载成功交易所记录时出错: {e}")
    return {}

def save_success_exchange(symbol, timeframe, exchange_id):
    """保存成功的交易所记录"""
    success_exchanges = load_success_exchanges()
    
    # 初始化字典结构
    if symbol not in success_exchanges:
        success_exchanges[symbol] = {}
    if timeframe not in success_exchanges[symbol]:
        success_exchanges[symbol][timeframe] = []
    
    # 将成功的交易所移到列表前面
    if exchange_id in success_exchanges[symbol][timeframe]:
        success_exchanges[symbol][timeframe].remove(exchange_id)
    success_exchanges[symbol][timeframe].insert(0, exchange_id)
    
    # 保存记录
    try:
        with open(SUCCESS_EXCHANGES_FILE, 'w') as f:
            json.dump(success_exchanges, f)
    except Exception as e:
        print(f"保存成功交易所记录时出错: {e}")

def get_prioritized_exchanges(symbol, timeframe):
    """获取优先排序后的交易所列表"""
    # 检查是否启用动态排序
    enable_dynamic_sorting = config.get('data', {}).get('enable_dynamic_sorting', True)
    if not enable_dynamic_sorting:
        return TOP_EXCHANGES
    
    success_exchanges = load_success_exchanges()
    
    # 获取该交易对和时间周期的成功交易所列表
    prioritized = []
    if symbol in success_exchanges and timeframe in success_exchanges[symbol]:
        prioritized = success_exchanges[symbol][timeframe]
    
    # 合并列表，确保所有交易所都在列表中，且优先使用上次成功的交易所
    result = []
    for exchange in prioritized:
        if exchange in TOP_EXCHANGES:
            result.append(exchange)
    
    for exchange in TOP_EXCHANGES:
        if exchange not in result:
            result.append(exchange)
    
    return result

def save_ohlcv_data(df, symbol, timeframe, exchange_id):
    """保存OHLCV数据"""
    return db.save_ohlcv_data(df, symbol, timeframe, exchange_id)

def load_ohlcv_data(symbol, timeframe, exchange_id=None):
    """加载OHLCV数据"""
    return db.load_ohlcv_data(symbol, timeframe, exchange_id)

def get_missing_timeframes(symbol, timeframe, start_time, end_time=None):
    """获取缺失的时间段"""
    # 检查是否启用数据补单
    enable_data_filling = config.get('data', {}).get('enable_data_filling', True)
    if not enable_data_filling:
        # 如果不启用数据补单，则返回整个时间段
        if end_time is None:
            end_time = datetime.now()
        return [(start_time, end_time)]
    
    # 如果未指定结束时间，使用当前时间
    if end_time is None:
        end_time = datetime.now()
    
    # 加载现有数据
    df = load_ohlcv_data(symbol, timeframe)
    
    if df is None or len(df) == 0:
        # 如果没有数据，返回整个时间段
        return [(start_time, end_time)]
    
    # 确保时间戳列是datetime类型
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 按时间排序
    df = df.sort_values('timestamp')
    
    # 找出缺失的时间段
    missing_periods = []
    
    # 检查开始时间之前是否有缺失
    if df['timestamp'].min() > start_time:
        missing_periods.append((start_time, df['timestamp'].min()))
    
    # 检查数据中间是否有缺失
    # 根据时间周期计算预期的时间间隔
    if timeframe.endswith('m'):
        interval = timedelta(minutes=int(timeframe[:-1]))
    elif timeframe.endswith('h'):
        interval = timedelta(hours=int(timeframe[:-1]))
    elif timeframe.endswith('d'):
        interval = timedelta(days=int(timeframe[:-1]))
    else:
        interval = timedelta(days=1)  # 默认为1天
    
    # 检查数据点之间的间隔
    for i in range(len(df) - 1):
        current_time = df['timestamp'].iloc[i]
        next_time = df['timestamp'].iloc[i + 1]
        expected_next_time = current_time + interval
        
        # 如果实际下一个时间点比预期的晚，说明中间有缺失
        if next_time > expected_next_time + interval:  # 允许一定的误差
            missing_periods.append((expected_next_time, next_time))
    
    # 检查结束时间之后是否有缺失
    if df['timestamp'].max() < end_time - interval:
        missing_periods.append((df['timestamp'].max() + interval, end_time))
    
    return missing_periods

def get_markets_from_multiple_exchanges(symbol='BTC/USDT'):
    """从多个交易所获取市场信息，直到成功或尝试完所有交易所"""
    # 获取优先排序后的交易所列表
    exchanges = get_prioritized_exchanges(symbol, '1d')  # 使用1d作为默认时间周期
    
    for exchange_id in exchanges:
        try:
            print(f"尝试从 {exchange_id} 获取市场信息...")
            # 初始化交易所
            exchange = getattr(ccxt, exchange_id)()
            # 加载市场
            markets = exchange.load_markets()
            
            # 检查指定交易对是否存在
            if symbol in markets:
                print(f"成功从 {exchange_id} 获取市场信息")
                # 保存成功记录
                save_success_exchange(symbol, '1d', exchange_id)
                return exchange_id, markets
            else:
                print(f"{exchange_id} 不支持交易对 {symbol}")
        except Exception as e:
            print(f"从 {exchange_id} 获取市场信息时出错: {e}")
            # 短暂暂停，避免请求过于频繁
            time.sleep(1)
    
    print("所有交易所都无法获取市场信息")
    return None, None

def fetch_ohlcv_from_multiple_exchanges(symbol='BTC/USDT', timeframe='1d', limit=30, since=None):
    """从多个交易所获取OHLCV数据，直到成功或尝试完所有交易所"""
    # 获取优先排序后的交易所列表
    exchanges = get_prioritized_exchanges(symbol, timeframe)
    
    for exchange_id in exchanges:
        try:
            print(f"尝试从 {exchange_id} 获取 {symbol} 的OHLCV数据...")
            # 初始化交易所
            exchange = getattr(ccxt, exchange_id)()
            
            # 确保交易所支持获取OHLCV数据
            if exchange.has['fetchOHLCV']:
                # 获取OHLCV数据
                params = {'limit': limit}
                if since is not None:
                    # 转换datetime为毫秒时间戳
                    if isinstance(since, datetime):
                        since = int(since.timestamp() * 1000)
                    params['since'] = since
                
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, **params)
                
                # 检查是否成功获取数据
                if ohlcv and len(ohlcv) > 0:
                    # 转换为DataFrame
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    # 转换时间戳为可读格式
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    print(f"成功从 {exchange_id} 获取OHLCV数据")
                    # 保存成功记录
                    save_success_exchange(symbol, timeframe, exchange_id)
                    return exchange_id, df
                else:
                    print(f"{exchange_id} 返回了空数据")
            else:
                print(f"{exchange_id} 不支持获取OHLCV数据")
        except Exception as e:
            print(f"从 {exchange_id} 获取OHLCV数据时出错: {e}")
            # 短暂暂停，避免请求过于频繁
            time.sleep(1)
    
    print("所有交易所都无法获取OHLCV数据")
    return None, None

def fetch_and_save_ohlcv_data(symbol, timeframe, start_time=None, end_time=None):
    """获取并保存OHLCV数据，支持补充缺失数据"""
    # 如果未指定开始时间，默认为30天前
    if start_time is None:
        default_days = config.get('data', {}).get('default_days', 30)
        if timeframe == '1d':
            start_time = datetime.now() - timedelta(days=default_days)
        elif timeframe == '1h':
            start_time = datetime.now() - timedelta(days=7)
        else:
            start_time = datetime.now() - timedelta(days=1)
    
    # 如果未指定结束时间，使用当前时间
    if end_time is None:
        end_time = datetime.now()
    
    # 获取缺失的时间段
    missing_periods = get_missing_timeframes(symbol, timeframe, start_time, end_time)
    
    if not missing_periods:
        print(f"{symbol} {timeframe} 数据已是最新，无需更新")
        return True
    
    # 加载现有数据
    existing_df = load_ohlcv_data(symbol, timeframe)
    if existing_df is None:
        existing_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    success = False
    
    # 对每个缺失的时间段进行数据获取
    for period_start, period_end in missing_periods:
        print(f"获取 {symbol} {timeframe} 从 {period_start} 到 {period_end} 的数据")
        
        # 计算需要获取的数据点数量
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            limit = int((period_end - period_start).total_seconds() / 60 / minutes) + 1
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            limit = int((period_end - period_start).total_seconds() / 3600 / hours) + 1
        elif timeframe.endswith('d'):
            limit = (period_end - period_start).days + 1
        else:
            limit = 1000  # 默认限制
        
        # 限制单次请求的数据量
        limit = min(limit, 1000)
        
        # 获取数据
        exchange_id, df = fetch_ohlcv_from_multiple_exchanges(
            symbol, timeframe, limit=limit, since=period_start
        )
        
        if df is not None and len(df) > 0:
            # 合并数据
            combined_df = pd.concat([existing_df, df])
            # 去重
            combined_df = combined_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            # 保存数据
            if save_ohlcv_data(combined_df, symbol, timeframe, exchange_id):
                existing_df = combined_df
                success = True
            
            # 避免API请求过于频繁
            time.sleep(1)
    
    return success

def fetch_all_timeframes(symbol, start_time=None, end_time=None):
    """获取所有时间周期的数据"""
    # 获取配置中的时间周期列表
    config_timeframes = config.get('data', {}).get('timeframes', TIMEFRAMES)
    timeframes_to_fetch = config_timeframes if config_timeframes else TIMEFRAMES
    
    results = {}
    
    for timeframe in timeframes_to_fetch:
        print(f"获取 {symbol} {timeframe} 数据...")
        success = fetch_and_save_ohlcv_data(symbol, timeframe, start_time, end_time)
        results[timeframe] = success
        # 避免API请求过于频繁
        time.sleep(2)
    
    return results

def get_markets(exchange_id='binance'):
    """获取指定交易所的市场信息（保留原函数以兼容旧代码）"""
    try:
        # 初始化交易所
        exchange = getattr(ccxt, exchange_id)()
        # 加载市场
        markets = exchange.load_markets()
        return markets
    except Exception as e:
        print(f"获取市场信息时出错: {e}")
        return None

def fetch_ohlcv(exchange_id='binance', symbol='BTC/USDT', timeframe='1d', limit=30):
    """获取OHLCV数据（保留原函数以兼容旧代码）"""
    try:
        # 初始化交易所
        exchange = getattr(ccxt, exchange_id)()
        
        # 确保交易所支持获取OHLCV数据
        if exchange.has['fetchOHLCV']:
            # 获取OHLCV数据
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # 转换为DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 转换时间戳为可读格式
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        else:
            print(f"{exchange_id} 不支持获取OHLCV数据")
            return None
    except Exception as e:
        print(f"获取OHLCV数据时出错: {e}")
        return None

def main():
    """主函数"""
    print("CCTX-Ana - 加密货币交易所数据分析工具")
    print("-" * 50)
    
    # 显示可用交易所
    exchanges = get_exchanges()
    print(f"可用交易所数量: {len(exchanges)}")
    print(f"我们将尝试的交易所: {', '.join(TOP_EXCHANGES)}")
    
    # 获取默认交易对
    default_symbol = config.get('data', {}).get('default_symbol', 'BTC/USDT')
    
    # 获取市场信息（从多个交易所尝试）
    print(f"\n尝试获取 {default_symbol} 的市场信息...")
    exchange_id, markets = get_markets_from_multiple_exchanges(default_symbol)
    
    if markets:
        print(f"成功从 {exchange_id} 获取市场信息")
        print(f"可用交易对数量: {len(markets)}")
        print(f"部分交易对: {', '.join(list(markets.keys())[:5])}...")
    else:
        print("无法从任何交易所获取市场信息")
    
    # 获取OHLCV数据（从多个交易所尝试）
    print(f"\n尝试获取 {default_symbol} 的最近7天OHLCV数据...")
    exchange_id, ohlcv_data = fetch_ohlcv_from_multiple_exchanges(default_symbol, '1d', 7)
    
    if ohlcv_data is not None:
        print(f"成功从 {exchange_id} 获取OHLCV数据:")
        print(ohlcv_data)
        
        # 保存数据
        save_ohlcv_data(ohlcv_data, default_symbol, '1d', exchange_id)
    else:
        print(f"无法从任何交易所获取 {default_symbol} 的OHLCV数据")
    
    # 演示获取多个时间周期的数据
    print("\n演示获取多个时间周期的数据...")
    # 这里只获取几个时间周期作为演示
    demo_timeframes = ['1h', '4h', '1d']
    for tf in demo_timeframes:
        print(f"\n获取 {default_symbol} {tf} 数据...")
        success = fetch_and_save_ohlcv_data(default_symbol, tf)
        if success:
            print(f"{default_symbol} {tf} 数据获取成功")
        else:
            print(f"{default_symbol} {tf} 数据获取失败")

if __name__ == "__main__":
    main()

def get_markets(exchange_id='binance'):
    """获取指定交易所的市场信息（保留原函数以兼容旧代码）"""
    try:
        # 初始化交易所
        exchange = getattr(ccxt, exchange_id)()
        # 加载市场
        markets = exchange.load_markets()
        return markets
    except Exception as e:
        print(f"获取市场信息时出错: {e}")
        return None

def fetch_ohlcv(exchange_id='binance', symbol='BTC/USDT', timeframe='1d', limit=30):
    """获取OHLCV数据（保留原函数以兼容旧代码）"""
    try:
        # 初始化交易所
        exchange = getattr(ccxt, exchange_id)()
        
        # 确保交易所支持获取OHLCV数据
        if exchange.has['fetchOHLCV']:
            # 获取OHLCV数据
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # 转换为DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 转换时间戳为可读格式
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        else:
            print(f"{exchange_id} 不支持获取OHLCV数据")
            return None
    except Exception as e:
        print(f"获取OHLCV数据时出错: {e}")
        return None

def main():
    """主函数"""
    print("CCTX-Ana - 加密货币交易所数据分析工具")
    print("-" * 50)
    
    # 显示可用交易所
    exchanges = get_exchanges()
    print(f"可用交易所数量: {len(exchanges)}")
    print(f"我们将尝试的交易所: {', '.join(TOP_EXCHANGES)}")
    
    # 获取市场信息（从多个交易所尝试）
    symbol = 'BTC/USDT'
    print(f"\n尝试获取 {symbol} 的市场信息...")
    exchange_id, markets = get_markets_from_multiple_exchanges(symbol)
    
    if markets:
        print(f"成功从 {exchange_id} 获取市场信息")
        print(f"可用交易对数量: {len(markets)}")
        print(f"部分交易对: {', '.join(list(markets.keys())[:5])}...")
    else:
        print("无法从任何交易所获取市场信息")
    
    # 获取OHLCV数据（从多个交易所尝试）
    print(f"\n尝试获取 {symbol} 的最近7天OHLCV数据...")
    exchange_id, ohlcv_data = fetch_ohlcv_from_multiple_exchanges(symbol, '1d', 7)
    
    if ohlcv_data is not None:
        print(f"成功从 {exchange_id} 获取OHLCV数据:")
        print(ohlcv_data)
    else:
        print(f"无法从任何交易所获取 {symbol} 的OHLCV数据")

if __name__ == "__main__":
    main()