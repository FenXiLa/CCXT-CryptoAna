from __future__ import annotations

import os
from typing import Dict, Tuple, Any, Optional

import pandas as pd
import ccxt  # type: ignore
import talib  # type: ignore


def fetch_data(symbol: str, timeframe: str = "1m", limit: int = 599, proxies: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    获取交易所K线数据（默认 Binance 现货）。
    返回包含 ['Open','High','Low','Close','Volume'] 且以时间戳为索引的 DataFrame。
    """
    exchange = ccxt.binance({
        'proxies': proxies or {},
        'options': {'defaultType': 'spot'}
    })
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _typical_price(df: pd.DataFrame) -> pd.Series:
    return (df['High'] + df['Low'] + df['Close']) / 3.0


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算核心技术指标并将结果列追加到 df 中。
    与 notebook 保持一致：MACD/RSI/BBANDS/ATR/Donchian/Keltner/OBV/volume_sma/支撑阻力/ROC/MOM 等。
    """
    data = df.copy()
    # MACD
    data['macd'], data['macd_signal'], data['macd_hist'] = talib.MACD(
        data['Close'], fastperiod=12, slowperiod=26, signalperiod=9)

    # RSI
    data['rsi'] = talib.RSI(data['Close'], timeperiod=14)

    # BBANDS + width
    data['bb_upper'], data['bb_middle'], data['bb_lower'] = talib.BBANDS(
        data['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['bb_middle'].replace(0, pd.NA) * 100

    # ATR
    data['atr'] = talib.ATR(data['High'], data['Low'], data['Close'], timeperiod=14)

    # Donchian Channel
    data['dc_upper'] = talib.MAX(data['High'], timeperiod=20)
    data['dc_lower'] = talib.MIN(data['Low'], timeperiod=20)
    data['dc_middle'] = (data['dc_upper'] + data['dc_lower']) / 2

    # Keltner Channel
    data['ema_20'] = talib.EMA(data['Close'], timeperiod=20)
    data['kc_upper'] = data['ema_20'] + (2 * data['atr'])
    data['kc_lower'] = data['ema_20'] - (2 * data['atr'])

    # 其他扩展
    data['apo'] = talib.APO(data['Close'], fastperiod=12, slowperiod=26)
    data['trix'] = talib.TRIX(data['Close'], timeperiod=15)
    data['psar'] = talib.SAR(data['High'], data['Low'], acceleration=0.02, maximum=0.2)
    # Vortex
    tr = talib.TRANGE(data['High'], data['Low'], data['Close'])
    vm_plus = (data['High'] - data['Low'].shift(1)).abs()
    vm_minus = (data['Low'] - data['High'].shift(1)).abs()
    data['vi_plus'] = vm_plus.rolling(14).sum() / tr.rolling(14).sum()
    data['vi_minus'] = vm_minus.rolling(14).sum() / tr.rolling(14).sum()
    # Aroon
    aroon_down, aroon_up = talib.AROON(data['High'], data['Low'], timeperiod=25)
    data['aroon_up'] = aroon_up
    data['aroon_down'] = aroon_down
    # VWMA
    tp = _typical_price(data)
    data['vwma_20'] = (tp * data['Volume']).rolling(20, min_periods=20).sum() / data['Volume'].rolling(20, min_periods=20).sum()

    # Volume set
    data['obv'] = talib.OBV(data['Close'], data['Volume'])
    # CMF/EMV/FI/VPT/VWAP
    mfm = ((data['Close'] - data['Low']) - (data['High'] - data['Close'])) / (data['High'] - data['Low']).replace(0, pd.NA)
    mfv = mfm * data['Volume']
    data['cmf_20'] = mfv.rolling(20).sum() / data['Volume'].rolling(20).sum()
    mid_move = ((data['High'] + data['Low']) / 2.0).diff()
    br = data['High'] - data['Low']
    data['emv_14'] = (mid_move * (data['High'] - data['Low']) / br.replace(0, pd.NA)).rolling(14).mean()
    data['fi_13'] = (data['Close'].diff() * data['Volume']).ewm(span=13, adjust=False).mean()
    data['vpt'] = (data['Close'].pct_change().fillna(0) * data['Volume']).cumsum()
    cum_v = data['Volume'].cumsum().replace(0, pd.NA)
    data['vwap'] = ((tp * data['Volume']).cumsum() / cum_v)

    data['volume_sma_20'] = talib.SMA(data['Volume'], timeperiod=20)

    # 支撑阻力 & 位置
    data['support'] = data['Low'].rolling(window=20).min()
    data['resistance'] = data['High'].rolling(window=20).max()
    data['price_position'] = (data['Close'] - data['support']) / (data['resistance'] - data['support'])

    # 动量
    data['roc'] = talib.ROC(data['Close'], timeperiod=10)
    data['mom'] = talib.MOM(data['Close'], timeperiod=10)

    return data


def analyze_signals(data: pd.DataFrame) -> pd.DataFrame:
    """
    基于 generate_signals 的结果生成布尔信号矩阵。
    返回与数据同索引的 DataFrame，每列为一个布尔信号。
    """
    signals = pd.DataFrame(index=data.index)

    # MACD
    signals['macd_buy'] = (data['macd'] > data['macd_signal'])
    signals['macd_sell'] = (data['macd'] < data['macd_signal'])

    # RSI
    signals['rsi_overbought'] = data['rsi'] > 70
    signals['rsi_oversold'] = data['rsi'] < 30
    signals['rsi_bullish'] = (data['rsi'] > 50) & (data['rsi'] < 70)
    signals['rsi_bearish'] = (data['rsi'] < 50) & (data['rsi'] > 30)

    # BBANDS
    signals['bb_buy'] = data['Close'] < data['bb_lower']
    signals['bb_sell'] = data['Close'] > data['bb_upper']
    signals['bb_price_above_middle'] = data['Close'] > data['bb_middle']
    signals['bb_price_below_middle'] = data['Close'] < data['bb_middle']
    signals['bb_squeeze_low'] = data['bb_width'] < data['bb_width'].rolling(100).quantile(0.2)

    # Donchian / Keltner
    signals['dc_buy'] = data['Close'] > data['dc_upper']
    signals['dc_sell'] = data['Close'] < data['dc_lower']
    signals['kc_buy'] = data['Close'] > data['kc_upper']
    signals['kc_sell'] = data['Close'] < data['kc_lower']

    # 其他趋势/动量
    signals['apo_positive'] = data['apo'] > 0
    signals['trix_positive'] = data['trix'] > 0
    signals['psar_long'] = data['Close'] > data['psar']
    signals['vortex_bull'] = (data['vi_plus'] > data['vi_minus']) & (data['vi_plus'].shift(1) <= data['vi_minus'].shift(1))
    signals['vortex_bear'] = (data['vi_plus'] < data['vi_minus']) & (data['vi_plus'].shift(1) >= data['vi_minus'].shift(1))
    signals['aroon_bull'] = (data['aroon_up'] > data['aroon_down']) & (data['aroon_up'].shift(1) <= data['aroon_down'].shift(1))
    signals['aroon_bear'] = (data['aroon_up'] < data['aroon_down']) & (data['aroon_up'].shift(1) >= data['aroon_down'].shift(1))
    signals['price_above_vwma'] = data['Close'] > data['vwma_20']

    # Volume
    signals['volume_above_avg'] = data['Volume'] > data['volume_sma_20']
    signals['volume_spike'] = data['Volume'] > data['volume_sma_20'] * 1.5
    signals['obv_trending_up'] = data['obv'] > data['obv'].shift(5)
    signals['volume_price_bullish'] = (data['Volume'] > data['volume_sma_20']) & (data['Close'] > data['Close'].shift(1))
    signals['cmf_positive'] = data['cmf_20'] > 0
    signals['emv_positive'] = data['emv_14'] > 0
    signals['fi_positive'] = data['fi_13'] > 0
    signals['vwap_above_ma'] = data['vwap'] > data['vwap'].rolling(50, min_periods=10).mean()

    # 支撑阻力
    signals['price_near_support'] = (data['Close'] - data['support']) / data['support'] < 0.02
    signals['price_near_resistance'] = (data['resistance'] - data['Close']) / data['Close'] < 0.02
    signals['price_break_resistance'] = (data['Close'] > data['resistance']) & (data['Close'].shift(1) <= data['resistance'].shift(1))
    signals['price_break_support'] = (data['Close'] < data['support']) & (data['Close'].shift(1) >= data['support'].shift(1))

    # 动量
    signals['roc_positive'] = data['roc'] > 0
    signals['mom_positive'] = data['mom'] > 0

    # 综合评分
    bullish_keys = [
        'macd_buy','rsi_bullish','bb_price_above_middle','dc_buy','kc_buy',
        'apo_positive','trix_positive','psar_long','vortex_bull','aroon_bull',
        'price_above_vwma','volume_price_bullish','cmf_positive','emv_positive','fi_positive','vwap_above_ma','roc_positive','mom_positive'
    ]
    bearish_keys = [
        'macd_sell','rsi_bearish','bb_price_below_middle','dc_sell','kc_sell',
        'vortex_bear','aroon_bear','price_break_support'
    ]
    signals['bullish_signals'] = signals[bullish_keys].sum(axis=1)
    signals['bearish_signals'] = signals[bearish_keys].sum(axis=1)
    signals['signal_strength'] = signals['bullish_signals'] - signals['bearish_signals']

    signals['strong_buy'] = signals['signal_strength'] >= 5
    signals['buy'] = (signals['signal_strength'] >= 3) & (signals['signal_strength'] < 5)
    signals['neutral'] = (signals['signal_strength'] > -3) & (signals['signal_strength'] < 3)
    signals['sell'] = (signals['signal_strength'] <= -3) & (signals['signal_strength'] > -5)
    signals['strong_sell'] = signals['signal_strength'] <= -5
    return signals


def summarize_latest(data: pd.DataFrame, signals: pd.DataFrame) -> Dict[str, Any]:
    """
    返回最新一条综合摘要，用于 UI 显示。
    """
    last = data.iloc[-1]
    sig = signals.iloc[-1]
    rec = (
        '🟢🟢🟢 强烈买入' if sig['strong_buy'] else
        '🟢🟢 买入' if sig['buy'] else
        '🔴🔴🔴 强烈卖出' if sig['strong_sell'] else
        '🔴🔴 卖出' if sig['sell'] else
        '⚪ 中性/观望'
    )
    return {
        'timestamp': data.index[-1],
        'price': float(last['Close']),
        'recommendation': rec,
        'signal_strength': int(sig['signal_strength']),
        'bullish_count': int(sig['bullish_signals']),
        'bearish_count': int(sig['bearish_signals'])
    }
