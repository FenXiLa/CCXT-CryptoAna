#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CCTX-Ana 定时任务脚本
用于设置定时抓取加密货币交易所数据
"""

import argparse
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# 导入主模块功能
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import fetch_all_timeframes, fetch_and_save_ohlcv_data, TIMEFRAMES

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='CCTX-Ana 定时任务')
    parser.add_argument('--symbol', type=str, default='BTC/USDT',
                        help='要获取的交易对 (默认: BTC/USDT)')
    parser.add_argument('--timeframe', type=str, choices=TIMEFRAMES,
                        help='要获取的时间周期，不指定则获取所有时间周期')
    parser.add_argument('--days', type=int, default=1,
                        help='要获取的历史数据天数 (默认: 1)')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 计算开始时间
    start_time = datetime.now() - timedelta(days=args.days)
    
    print(f"开始获取 {args.symbol} 的数据，历史天数: {args.days}")
    
    if args.timeframe:
        # 获取指定时间周期的数据
        print(f"获取 {args.timeframe} 时间周期的数据...")
        success = fetch_and_save_ohlcv_data(args.symbol, args.timeframe, start_time)
        if success:
            print(f"{args.symbol} {args.timeframe} 数据获取成功")
        else:
            print(f"{args.symbol} {args.timeframe} 数据获取失败")
    else:
        # 获取所有时间周期的数据
        print("获取所有时间周期的数据...")
        results = fetch_all_timeframes(args.symbol, start_time)
        
        # 打印结果
        for timeframe, success in results.items():
            status = "成功" if success else "失败"
            print(f"{args.symbol} {timeframe} 数据获取{status}")

if __name__ == "__main__":
    main()