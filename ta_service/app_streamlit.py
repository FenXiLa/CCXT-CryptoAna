import os
import sys
import time
import pathlib
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 确保项目根目录在 sys.path 中，避免 ModuleNotFoundError: ta_service
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ta_service.core import fetch_data, generate_signals, analyze_signals, summarize_latest, SUPPORTED_EXCHANGES


def _get_proxies() -> dict:
    proxies = {}
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    return proxies


# 映射时间周期到秒数，用于自动刷新
TIMEFRAME_SECONDS = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '2h': 7200,
    '4h': 14400,
    '6h': 21600,
    '12h': 43200,
    '1d': 86400,
    '3d': 259200,
    '1w': 604800,
}

# 信号含义说明字典
SIGNAL_DESCRIPTIONS = {
    # MACD 信号
    'macd_buy': 'MACD 买入：MACD 线 > 信号线',
    'macd_sell': 'MACD 卖出：MACD 线 < 信号线',
    
    # RSI 信号
    'rsi_overbought': 'RSI 超买：RSI > 70',
    'rsi_oversold': 'RSI 超卖：RSI < 30',
    'rsi_bullish': 'RSI 看涨：50 < RSI < 70',
    'rsi_bearish': 'RSI 看跌：30 < RSI < 50',
    
    # 布林带信号
    'bb_buy': '布林带买入：价格 < 下轨',
    'bb_sell': '布林带卖出：价格 > 上轨',
    'bb_price_above_middle': '价格 > 布林带中轨',
    'bb_price_below_middle': '价格 < 布林带中轨',
    'bb_squeeze_low': '布林带收缩：低波动率',
    
    # 唐奇安通道信号
    'dc_buy': '唐奇安买入：价格 > 上轨',
    'dc_sell': '唐奇安卖出：价格 < 下轨',
    
    # Keltner 通道信号
    'kc_buy': 'Keltner 买入：价格 > 上轨',
    'kc_sell': 'Keltner 卖出：价格 < 下轨',
    
    # 趋势/动量信号
    'apo_positive': 'APO 为正：绝对价格振荡器看涨',
    'trix_positive': 'TRIX 为正：三重指数平滑看涨',
    'psar_long': 'PSAR 看涨：价格 > 抛物线SAR',
    'vortex_bull': 'Vortex 看涨：VI+ 金叉 VI-',
    'vortex_bear': 'Vortex 看跌：VI+ 死叉 VI-',
    'aroon_bull': 'Aroon 看涨：Aroon Up 金叉 Aroon Down',
    'aroon_bear': 'Aroon 看跌：Aroon Up 死叉 Aroon Down',
    'price_above_vwma': '价格 > 成交量加权移动平均',
    
    # 成交量信号
    'volume_above_avg': '成交量高于平均',
    'volume_spike': '成交量激增：> 1.5倍平均',
    'obv_trending_up': 'OBV 上升趋势',
    'volume_price_bullish': '价涨量增：看涨',
    'cmf_positive': 'CMF 为正：Chaikin资金流看涨',
    'emv_positive': 'EMV 为正：易变指标看涨',
    'fi_positive': 'FI 为正：力度指标看涨',
    'vwap_above_ma': 'VWAP > 移动平均：看涨',
    
    # 支撑阻力信号
    'price_near_support': '接近支撑位：距离 < 2%',
    'price_near_resistance': '接近阻力位：距离 < 2%',
    'price_break_resistance': '突破阻力位',
    'price_break_support': '跌破支撑位',
    
    # 动量信号
    'roc_positive': 'ROC 为正：变动率看涨',
    'mom_positive': 'MOM 为正：动量看涨',
    
    # 综合信号
    'bullish_signals': '多头信号总数',
    'bearish_signals': '空头信号总数',
    'signal_strength': '信号强度：多头 - 空头',
    'strong_buy': '强烈买入：信号强度 >= 5',
    'buy': '买入：信号强度 3-4',
    'neutral': '中性：信号强度 -2 到 2',
    'sell': '卖出：信号强度 -4 到 -3',
    'strong_sell': '强烈卖出：信号强度 <= -5',
}


def main():
    st.set_page_config(page_title="CCTX-Ana 技术分析仪表盘", layout="wide")

    # 全局样式：降低字体、调整内边距，确保标题不被遮挡
    st.markdown(
        """
        <style>
        /* 基础字体大小 */
        html, body, [class*="css"] { font-size: 13px !important; }
        
        /* 确保标题区域有足够空间，不被顶部导航栏遮挡 */
        .block-container { 
            padding-top: 2rem !important; 
            padding-bottom: 0.8rem !important; 
        }
        
        /* 标题样式 */
        h1 { 
            font-size: 1.5rem !important; 
            margin-top: 0.5rem !important;
            margin-bottom: 1rem !important;
            padding-top: 0 !important;
        }
        h2, h3 { 
            font-size: 1.15rem !important; 
            margin-top: 1rem !important;
        }
        
        /* 指标卡片样式 */
        [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
        [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
        
        /* 确保侧边栏不会遮挡主内容 */
        [data-testid="stSidebar"] {
            padding-top: 1rem;
        }
        
        /* 隐藏 Streamlit 默认的顶部装饰和底部 */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
        
        /* 确保主内容区域有足够的上边距 */
        .main .block-container {
            padding-top: 3rem !important;
        }
        
        /* 标题容器样式 */
        [data-testid="stAppViewContainer"] {
            padding-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("CCTX-Ana 技术分析仪表盘")

    with st.sidebar:
        st.header("参数设置")
        symbol = st.text_input("交易对 (symbol)", value="BTC/USDT")
        timeframe = st.selectbox(
            "时间周期 (timeframe)",
            options=list(TIMEFRAME_SECONDS.keys()),
            index=list(TIMEFRAME_SECONDS.keys()).index('1h') if '1h' in TIMEFRAME_SECONDS else 5,
        )
        limit = st.slider("K线数量 (limit)", min_value=200, max_value=1500, value=600, step=50)
        
        st.divider()
        st.subheader("交易所设置")
        exchange_mode = st.radio(
            "交易所选择",
            ["自动选择（推荐）", "手动指定"],
            index=0,
            help="自动选择会在失败时自动切换到其他交易所"
        )
        selected_exchange = None
        auto_fallback = True
        if exchange_mode == "手动指定":
            selected_exchange = st.selectbox(
                "选择交易所",
                options=SUPPORTED_EXCHANGES,
                index=0,
                help="如果选择的交易所不可用，将自动切换到其他交易所"
            )
        
        use_proxy = st.checkbox("使用环境代理 (HTTP_PROXY/HTTPS_PROXY)", value=True)
        st.divider()
        st.subheader("自动刷新")
        enable_auto = st.checkbox("开启自动刷新", value=False, help="按所选周期或自定义秒数自动刷新页面")
        refresh_mode = st.radio("刷新方式", ["按周期", "自定义(秒)"] , index=0, horizontal=True, disabled=not enable_auto)
        custom_seconds = st.number_input("自定义刷新秒数", min_value=5, max_value=86400, value=60, step=5, disabled=not enable_auto or refresh_mode!="自定义(秒)")
        run_btn = st.button("运行分析", use_container_width=True)

    if not run_btn and not enable_auto:
        st.info("请在左侧设置参数并点击 [运行分析]，或开启自动刷新。")
        st.stop()

    proxies = _get_proxies() if use_proxy else {}

    # 获取数据
    with st.spinner("获取数据中…"):
        try:
            df, used_exchange = fetch_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                proxies=proxies,
                exchange_id=selected_exchange,
                auto_fallback=auto_fallback
            )
            
            if df.empty:
                st.error("获取数据为空")
                st.stop()
            
            # 显示实际使用的交易所信息
            if selected_exchange and used_exchange != selected_exchange:
                st.warning(f"⚠️ 指定的交易所 {selected_exchange} 不可用，已自动切换到: **{used_exchange}**")
            else:
                st.success(f"✅ 数据来源: **{used_exchange}**")
                
        except Exception as e:
            st.error(f"❌ 获取数据失败: {str(e)}")
            st.info("💡 建议：\n1. 检查网络连接\n2. 尝试使用代理\n3. 尝试其他交易对\n4. 手动指定其他交易所")
            st.stop()

    # 价格与成交量（双Y轴图表）
    st.subheader("价格与成交量")
    
    # 创建双Y轴图表
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 添加价格线（主Y轴）
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['Close'],
            name=f'{symbol} 价格',
            line=dict(color='#1f77b4', width=1.5)
        ),
        secondary_y=False,
    )
    
    # 添加成交量柱状图（次Y轴）- 涨跌用不同颜色
    colors = []
    for i in range(len(df)):
        if i == 0:
            colors.append('#2ca02c')  # 第一个数据点默认为绿色
        elif df['Close'].iloc[i] >= df['Close'].iloc[i-1]:
            colors.append('#2ca02c')  # 上涨为绿色
        else:
            colors.append('#d62728')  # 下跌为红色
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['Volume'],
            name='成交量',
            marker_color=colors,
            opacity=0.3
        ),
        secondary_y=True,
    )
    
    # 设置Y轴标签
    fig.update_yaxes(title_text=f"{symbol} 价格", secondary_y=False)
    fig.update_yaxes(title_text="成交量", secondary_y=True)
    
    # 设置图表标题和布局
    fig.update_layout(
        title=f"{symbol} 价格与成交量",
        xaxis_title="时间",
        height=400,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 计算指标与信号（需要在显示K线图之前计算）
    with st.spinner("计算指标与信号…"):
        data = generate_signals(df)
        sigs = analyze_signals(data)
        summary = summarize_latest(data, sigs)
    
    # 蜡烛图 + 布林带 + MACD 图表
    st.subheader("K线图、布林带与 MACD")
    
    # 创建子图：上方是K线+布林带，下方是MACD
    fig_ta = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{symbol} K线图 + 布林带', 'MACD 指标'),
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # 第一行：K线图 + 布林带
    # 添加蜡烛图
    fig_ta.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='K线',
            increasing_line_color='#26a69a',  # 上涨绿色
            decreasing_line_color='#ef5350',  # 下跌红色
        ),
        row=1, col=1
    )
    
    # 添加布林带（先添加上轨，然后中轨，最后下轨并填充）
    fig_ta.add_trace(
        go.Scatter(
            x=data.index,
            y=data['bb_upper'],
            name='布林带上轨',
            line=dict(color='rgba(33, 150, 243, 0.4)', width=1, dash='dash'),
            showlegend=True
        ),
        row=1, col=1
    )
    
    fig_ta.add_trace(
        go.Scatter(
            x=data.index,
            y=data['bb_lower'],
            name='布林带下轨',
            line=dict(color='rgba(33, 150, 243, 0.4)', width=1, dash='dash'),
            fill='tonexty',  # 填充到上一条线（上轨）
            fillcolor='rgba(33, 150, 243, 0.08)',
            showlegend=False
        ),
        row=1, col=1
    )
    
    fig_ta.add_trace(
        go.Scatter(
            x=data.index,
            y=data['bb_middle'],
            name='布林带中轨',
            line=dict(color='rgba(156, 39, 176, 0.7)', width=1.5),
            showlegend=True
        ),
        row=1, col=1
    )
    
    # 第二行：MACD 图
    # MACD 线
    fig_ta.add_trace(
        go.Scatter(
            x=data.index,
            y=data['macd'],
            name='MACD',
            line=dict(color='#ff6f00', width=1.5),
            showlegend=True
        ),
        row=2, col=1
    )
    
    # MACD 信号线
    fig_ta.add_trace(
        go.Scatter(
            x=data.index,
            y=data['macd_signal'],
            name='MACD Signal',
            line=dict(color='#0277bd', width=1.5),
            showlegend=True
        ),
        row=2, col=1
    )
    
    # MACD 柱状图
    colors_hist = ['#26a69a' if h >= 0 else '#ef5350' for h in data['macd_hist']]
    fig_ta.add_trace(
        go.Bar(
            x=data.index,
            y=data['macd_hist'],
            name='MACD Hist',
            marker_color=colors_hist,
            opacity=0.6,
            showlegend=True
        ),
        row=2, col=1
    )
    
    # 添加零线（MACD 图）
    fig_ta.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)
    
    # 更新布局
    fig_ta.update_layout(
        title=f"{symbol} 技术分析图表",
        height=700,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,  # 隐藏底部滑块
    )
    
    # 更新Y轴标签
    fig_ta.update_yaxes(title_text="价格", row=1, col=1)
    fig_ta.update_yaxes(title_text="MACD", row=2, col=1)
    fig_ta.update_xaxes(title_text="时间", row=2, col=1)
    
    st.plotly_chart(fig_ta, use_container_width=True)

    # 摘要指标
    st.subheader("综合摘要")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("交易所", used_exchange.upper())
    s2.metric("最新时间", str(summary['timestamp']))
    s3.metric("当前价格", f"{summary['price']:.2f}")
    s4.metric("信号强度", summary['signal_strength'])
    s5.metric("建议", summary['recommendation'])

    # 最新信号表（带含义说明）
    st.subheader("信号一览（最新一行）")
    last_signals = sigs.iloc[[-1]].T
    last_signals.columns = ["状态"]
    
    # 创建带含义说明的DataFrame
    signal_df = pd.DataFrame({
        '信号名称': last_signals.index,
        '状态': last_signals['状态'].apply(lambda x: '✅ 是' if x else '❌ 否'),
        '含义说明': [SIGNAL_DESCRIPTIONS.get(name, '未知信号') for name in last_signals.index]
    })
    
    # 对于数值型信号（如bullish_signals, bearish_signals, signal_strength），显示数值
    numeric_signals = ['bullish_signals', 'bearish_signals', 'signal_strength']
    for idx, name in enumerate(signal_df['信号名称']):
        if name in numeric_signals:
            signal_df.at[idx, '状态'] = str(int(last_signals.loc[name, '状态']))
    
    st.dataframe(signal_df, use_container_width=True, hide_index=True)

    # 关键指标快照
    with st.expander("查看关键指标（最新数值）"):
        latest_metrics = data.iloc[[-1]][[
            'macd','macd_signal','macd_hist','rsi','bb_upper','bb_middle','bb_lower',
            'atr','dc_upper','dc_middle','dc_lower','kc_upper','ema_20','kc_lower',
            'apo','trix','psar','vi_plus','vi_minus','aroon_up','aroon_down','vwma_20',
        ]]
        st.dataframe(latest_metrics.T.rename(columns={latest_metrics.index[-1]: '最新'}), use_container_width=True)

    # 数据明细
    st.subheader("原始与衍生数据（可筛选）")
    with st.expander("展开/折叠数据表"):
        st.dataframe(data.tail(200), use_container_width=True)

    # 自动刷新逻辑（带倒计时）
    if enable_auto:
        if refresh_mode == "按周期":
            refresh_seconds = TIMEFRAME_SECONDS.get(timeframe, 60)
        else:
            refresh_seconds = int(custom_seconds)
        
        # 创建倒计时占位符（进度条和文本分开）
        progress_placeholder = st.empty()
        text_placeholder = st.empty()
        
        # 倒计时循环
        remaining = min(refresh_seconds, 3600)  # 最多显示3600秒
        while remaining > 0:
            # 计算分钟和秒
            mins = remaining // 60
            secs = remaining % 60
            
            # 格式化倒计时显示
            if mins > 0:
                countdown_text = f"⏱️ 自动刷新倒计时: **{mins}分{secs}秒** 后获取最新 {timeframe} 数据"
            else:
                countdown_text = f"⏱️ 自动刷新倒计时: **{secs}秒** 后获取最新 {timeframe} 数据"
            
            # 更新进度条和文本
            progress = 1.0 - (remaining / refresh_seconds)
            progress_placeholder.progress(progress)
            text_placeholder.caption(countdown_text)
            
            # 等待1秒
            time.sleep(1)
            remaining -= 1
        
        # 倒计时结束，清空占位符
        progress_placeholder.empty()
        text_placeholder.empty()
        
        # 倒计时结束，刷新页面
        st.info("🔄 正在刷新数据...")
        try:
            st.experimental_rerun()  # 兼容旧版 streamlit
        except Exception:
            st.rerun()  # 新版接口


if __name__ == "__main__":
    main()
