from __future__ import annotations

import os
from typing import Dict, Tuple, Any, Optional

import pandas as pd
import ccxt  # type: ignore
import talib  # type: ignore

BINANCE_IMPORT_ERROR: Optional[str] = None

try:
    from binance.client import Client  # type: ignore
    try:
        from binance.error import BinanceAPIException, BinanceRequestException  # type: ignore
    except ImportError:
        from binance.exceptions import BinanceAPIException, BinanceRequestException  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    BINANCE_IMPORT_ERROR = str(exc)
    Client = None  # type: ignore
    BinanceAPIException = BinanceRequestException = Exception  # type: ignore


# 支持的交易所列表（按优先级排序）
SUPPORTED_EXCHANGES = [
    'binance',
    'okx',
    'bybit',
    'huobi',
    'gate',
    'kucoin',
    'bitget',
    'coinbase',
    'kraken',
]


def _create_exchange(exchange_id: str, proxies: Optional[Dict[str, str]] = None) -> ccxt.Exchange:
    """
    创建交易所实例
    
    参数:
        exchange_id: 交易所ID（如 'binance', 'okx' 等）
        proxies: 代理配置字典
    
    返回:
        ccxt.Exchange 实例
    """
    exchange_class = getattr(ccxt, exchange_id)
    config = {
        'proxies': proxies or {},
        'options': {'defaultType': 'spot'},
        'enableRateLimit': True,  # 启用限流
        'timeout': 30000,  # 30秒超时
    }
    return exchange_class(config)


def fetch_data(
    symbol: str,
    timeframe: str = "1m",
    limit: int = 599,
    proxies: Optional[Dict[str, str]] = None,
    exchange_id: Optional[str] = None,
    auto_fallback: bool = True
) -> Tuple[pd.DataFrame, str]:
    """
    获取交易所K线数据，支持异常处理和自动切换交易所。
    
    参数:
        symbol: 交易对符号，如 'BTC/USDT'
        timeframe: 时间周期，如 '1m', '1h', '1d' 等
        limit: 获取的K线数量
        proxies: 代理配置字典
        exchange_id: 指定交易所ID，如果为None则自动选择
        auto_fallback: 是否在失败时自动切换到其他交易所
    
    返回:
        Tuple[pd.DataFrame, str]: (包含OHLCV数据的DataFrame, 实际使用的交易所ID)
        如果所有交易所都失败，抛出异常
    
    异常:
        Exception: 当所有交易所都无法获取数据时抛出
    """
    # 确定要尝试的交易所列表
    if exchange_id:
        # 如果指定了交易所，优先使用
        exchange_list = [exchange_id]
        if auto_fallback:
            # 添加其他交易所作为备选
            exchange_list.extend([e for e in SUPPORTED_EXCHANGES if e != exchange_id])
    else:
        # 未指定交易所，使用默认优先级列表
        exchange_list = SUPPORTED_EXCHANGES.copy()
    
    last_error = None
    last_exchange_id = None
    
    # 尝试每个交易所
    for ex_id in exchange_list:
        try:
            # 创建交易所实例
            exchange = _create_exchange(ex_id, proxies)
            
            # 尝试获取K线数据
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) == 0:
                raise Exception(f"交易所 {ex_id} 返回空数据")
            
            # 转换为DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 成功返回
            return df, ex_id
            
        except ccxt.ExchangeNotAvailable as e:
            # 交易所不可用（如地区限制）
            last_error = f"交易所 {ex_id} 不可用: {str(e)}"
            last_exchange_id = ex_id
            if not auto_fallback:
                raise Exception(last_error)
            continue
            
        except ccxt.NetworkError as e:
            # 网络错误
            last_error = f"交易所 {ex_id} 网络错误: {str(e)}"
            last_exchange_id = ex_id
            if not auto_fallback:
                raise Exception(last_error)
            continue
            
        except ccxt.ExchangeError as e:
            # 交易所API错误
            last_error = f"交易所 {ex_id} API错误: {str(e)}"
            last_exchange_id = ex_id
            if not auto_fallback:
                raise Exception(last_error)
            continue
            
        except Exception as e:
            # 其他未知错误
            last_error = f"交易所 {ex_id} 未知错误: {str(e)}"
            last_exchange_id = ex_id
            if not auto_fallback:
                raise Exception(last_error)
            continue
    
    # 所有交易所都失败了
    error_msg = (
        f"无法从任何交易所获取数据。\n"
        f"最后尝试的交易所: {last_exchange_id}\n"
        f"最后错误: {last_error}\n"
        f"已尝试的交易所: {', '.join(exchange_list)}\n"
        f"建议: 检查网络连接、代理设置或尝试其他交易对"
    )
    raise Exception(error_msg)


def _ratio_list_to_df(items: Any) -> pd.DataFrame:
    """将 Binance 返回的比率列表转换为 DataFrame。"""
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    if df.empty:
        return df

    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')

    for col in df.columns:
        if col in {'timestamp', 'symbol', 'period', 'interval'}:
            continue
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def fetch_binance_futures_ratios(
    symbol: str,
    period: str = "1h",
    limit: int = 50,
    proxies: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """获取 Binance 合约多空比数据。

    返回包含多个 DataFrame（或字典）的字典。
    """

    if Client is None:
        detail = f"python-binance 未安装或导入失败: {BINANCE_IMPORT_ERROR}" if BINANCE_IMPORT_ERROR else "python-binance 未安装"
        raise ImportError(detail)

    raw_symbol = symbol.replace('/', '').upper()

    requests_params: Dict[str, Any] = {
        'timeout': 15,
    }
    if proxies:
        # 将代理透传给 python-binance 库（支持 http/https/socks）
        requests_params['proxies'] = proxies

    client = Client(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        requests_params=requests_params,
    )

    try:
        taker_ratio = client.futures_taker_longshort_ratio(
            symbol=raw_symbol,
            period=period,
            limit=limit,
        )
        global_ratio = client.futures_global_longshort_ratio(
            symbol=raw_symbol,
            period=period,
            limit=limit,
        )
        top_account_ratio = client.futures_top_longshort_account_ratio(
            symbol=raw_symbol,
            period=period,
            limit=limit,
        )
        top_position_ratio = client.futures_top_longshort_position_ratio(
            symbol=raw_symbol,
            period=period,
            limit=limit,
        )
        ticker = client.futures_ticker(symbol=raw_symbol)

        return {
            'taker_ratio': _ratio_list_to_df(taker_ratio),
            'global_ratio': _ratio_list_to_df(global_ratio),
            'top_account_ratio': _ratio_list_to_df(top_account_ratio),
            'top_position_ratio': _ratio_list_to_df(top_position_ratio),
            'ticker': ticker,
        }

    except (BinanceAPIException, BinanceRequestException) as exc:
        raise Exception(f"Binance API 调用失败: {exc.message if hasattr(exc, 'message') else str(exc)}") from exc
    except Exception as exc:  # 捕获其他异常
        raise Exception(f"获取 Binance 多空数据失败: {str(exc)}") from exc


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
