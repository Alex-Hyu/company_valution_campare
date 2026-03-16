"""
估值预警系统 - Streamlit主应用
Valuation Alert System

功能:
1. 单股票估值分析仪表盘
2. 全市场扫描预警
3. 同行业比较矩阵
4. Telegram预警推送
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# 导入自定义模块
from config import STOCK_UNIVERSE, PEER_GROUPS, SECTOR_MAPPING, ALERT_THRESHOLDS
from data_fetcher import (
    batch_fetch_stocks, 
    fetch_single_stock, 
    fetch_price_history,
    get_sector_peers,
    fetch_benchmark_data,
    calculate_relative_strength
)
from technical_analysis import (
    get_technical_indicators, 
    calculate_technical_score,
    calculate_rsi,
    calculate_bollinger_bands
)
from valuation_analysis import (
    get_full_valuation_analysis,
    calculate_pe_percentile,
    compare_with_peers
)
from scoring import (
    calculate_composite_score,
    generate_alert_message,
    send_telegram_alert,
    scan_all_stocks,
    get_bottom_candidates,
    get_top_candidates,
    format_scan_summary
)

# 页面配置
st.set_page_config(
    page_title="估值预警系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .bottom-signal {
        background: linear-gradient(135deg, #134e5e 0%, #71b280 100%);
        padding: 15px;
        border-radius: 8px;
        color: white;
    }
    .top-signal {
        background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%);
        padding: 15px;
        border-radius: 8px;
        color: white;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化session state"""
    if 'all_data' not in st.session_state:
        st.session_state.all_data = None
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    if 'valuation_results' not in st.session_state:
        st.session_state.valuation_results = {}
    if 'technical_results' not in st.session_state:
        st.session_state.technical_results = {}
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None


def load_data(tickers: list = None, force_refresh: bool = False):
    """加载数据"""
    if tickers is None:
        tickers = STOCK_UNIVERSE
    
    # 检查是否需要刷新
    if not force_refresh and st.session_state.all_data is not None:
        if st.session_state.last_refresh is not None:
            time_since_refresh = datetime.now() - st.session_state.last_refresh
            if time_since_refresh.seconds < 3600:  # 1小时内不刷新
                return st.session_state.all_data
    
    with st.spinner(f"正在加载 {len(tickers)} 只股票数据... (这可能需要1-2分钟)"):
        try:
            data = batch_fetch_stocks(tickers, max_workers=10)
            if data is not None and not data.empty:
                st.session_state.all_data = data
                st.session_state.last_refresh = datetime.now()
            else:
                st.warning("部分数据加载失败，请稍后重试")
        except Exception as e:
            st.error(f"数据加载错误: {e}")
            return pd.DataFrame()
    
    return st.session_state.all_data


def render_sidebar():
    """渲染侧边栏"""
    st.sidebar.title("📊 估值预警系统")
    st.sidebar.markdown("---")
    
    # 功能选择
    page = st.sidebar.radio(
        "选择功能",
        ["🔍 单股分析", "📡 全市场扫描", "📊 同业比较", "⚙️ 设置"]
    )
    
    st.sidebar.markdown("---")
    
    # 数据状态
    if st.session_state.last_refresh:
        st.sidebar.info(f"上次刷新: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    
    if st.sidebar.button("🔄 刷新数据"):
        load_data(force_refresh=True)
        st.rerun()
    
    return page


def render_single_stock_analysis():
    """单股票分析页面"""
    st.title("🔍 单股票估值分析")
    
    # 股票选择
    col1, col2 = st.columns([2, 1])
    
    with col1:
        ticker = st.selectbox(
            "选择股票",
            options=STOCK_UNIVERSE,
            index=STOCK_UNIVERSE.index("NVDA") if "NVDA" in STOCK_UNIVERSE else 0
        )
    
    with col2:
        custom_ticker = st.text_input("或输入代码", "")
        if custom_ticker:
            ticker = custom_ticker.upper()
    
    if st.button("分析", type="primary"):
        analyze_single_stock(ticker)


def analyze_single_stock(ticker: str):
    """分析单只股票"""
    with st.spinner(f"正在分析 {ticker}..."):
        # 获取数据
        stock_data = fetch_single_stock(ticker)
        if not stock_data:
            st.error(f"❌ 无法获取 {ticker} 数据，请检查股票代码是否正确")
            return
        
        # 创建DataFrame用于同行比较
        peers = get_sector_peers(ticker)
        all_tickers = [ticker] + peers
        all_data = batch_fetch_stocks(all_tickers, max_workers=5)
        
        # 检查数据是否有效
        if all_data is None or all_data.empty:
            st.warning("⚠️ 无法获取同行数据，将只显示单股分析")
            all_data = pd.DataFrame([stock_data])
        
        # 估值分析
        try:
            valuation = get_full_valuation_analysis(ticker, all_data)
        except Exception as e:
            st.warning(f"估值分析部分失败: {e}")
            valuation = {"ticker": ticker, "name": stock_data.get("name", ticker)}
        
        # 技术分析
        try:
            technical = get_technical_indicators(ticker)
            if technical:
                tech_score = calculate_technical_score(technical)
                technical.update(tech_score)
            else:
                technical = {"rsi": 50, "week_52_position": 50, "ma_200_dev": 0}
        except Exception as e:
            st.warning(f"技术分析部分失败: {e}")
            technical = {"rsi": 50, "week_52_position": 50, "ma_200_dev": 0}
        
        # 综合评分
        composite = calculate_composite_score(valuation, technical)
    
    # 显示结果
    render_stock_dashboard(ticker, stock_data, valuation, technical, composite, all_data)


def render_stock_dashboard(ticker, stock_data, valuation, technical, composite, all_data):
    """渲染股票分析仪表盘"""
    
    # 导入解读模块
    from interpretation import (
        generate_valuation_interpretation,
        generate_rating_table,
        generate_warning_alerts,
        calculate_price_targets,
        generate_price_levels,
        get_overall_rating
    )
    
    # 标题和基本信息
    st.header(f"{stock_data.get('name', ticker)} ({ticker})")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("当前价格", f"${stock_data.get('price', 0):.2f}")
    with col2:
        st.metric("市值", f"${stock_data.get('market_cap', 0)/1e9:.1f}B")
    with col3:
        st.metric("行业", stock_data.get('sector', 'N/A'))
    with col4:
        st.metric("P/E TTM", f"{stock_data.get('pe_ttm', 'N/A'):.1f}" if stock_data.get('pe_ttm') else "N/A")
    
    st.markdown("---")
    
    # ===== 新增：智能估值解读 =====
    st.subheader("📝 估值诊断")
    
    # 综合评级
    overall = get_overall_rating(valuation, technical)
    col_rating, col_interpretation = st.columns([1, 3])
    
    with col_rating:
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white;">
            <div style="font-size: 48px;">{overall['emoji']}</div>
            <div style="font-size: 24px; font-weight: bold;">{overall['label']}</div>
            <div style="font-size: 16px; margin-top: 10px;">{overall['action']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_interpretation:
        interpretation = generate_valuation_interpretation(ticker, valuation, technical)
        st.markdown(interpretation)
    
    # 风险提示
    alerts = generate_warning_alerts(valuation, technical)
    if alerts:
        with st.expander("⚠️ 关键提示", expanded=True):
            for alert in alerts:
                st.markdown(f"• {alert}")
    
    st.markdown("---")
    
    # ===== 新增：分档评级表 =====
    st.subheader("📊 分档评级")
    
    ratings = generate_rating_table(valuation, technical)
    
    # 创建评级表格
    rating_cols = st.columns(len(ratings))
    for i, r in enumerate(ratings):
        with rating_cols[i]:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                <div style="font-size: 24px;">{r['emoji']}</div>
                <div style="font-size: 12px; color: #666;">{r['dimension']}</div>
                <div style="font-size: 18px; font-weight: bold;">{r['value']}</div>
                <div style="font-size: 11px; color: #888;">{r['label']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ===== 新增：买卖点参考 =====
    st.subheader("📍 买卖点参考")
    
    price_levels = generate_price_levels(
        current_price=valuation.get('price', 0),
        current_pe=valuation.get('pe_ttm'),
        pe_5y_min=valuation.get('pe_5y_min'),
        pe_5y_max=valuation.get('pe_5y_max'),
        pe_5y_median=valuation.get('pe_5y_median')
    )
    
    if price_levels:
        level_data = []
        for l in price_levels:
            level_data.append({
                "区间": l['label'],
                "P/E范围": l['pe_range'],
                "价格范围": l['price_range'],
                "操作建议": l['action'],
            })
        
        df_levels = pd.DataFrame(level_data)
        
        # 高亮当前所在区间
        def highlight_current(row):
            for l in price_levels:
                if l['label'] == row['区间'] and l['is_current']:
                    return ['background-color: #fff3cd'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            df_levels.style.apply(highlight_current, axis=1),
            use_container_width=True,
            hide_index=True
        )
    
    # ===== 新增：情景分析 =====
    st.subheader("🎯 目标价位情景分析")
    
    targets = calculate_price_targets(
        current_price=valuation.get('price', 0),
        current_pe=valuation.get('pe_ttm'),
        pe_5y_median=valuation.get('pe_5y_median'),
        pe_5y_25pct=valuation.get('pe_5y_25pct'),
        pe_5y_75pct=valuation.get('pe_5y_75pct'),
        peer_pe_median=valuation.get('peer_pe_median'),
        pe_forward=valuation.get('pe_forward')
    )
    
    if targets:
        target_cols = st.columns(len(targets))
        for i, t in enumerate(targets):
            with target_cols[i]:
                change_color = "green" if t['change_pct'] > 0 else "red"
                st.markdown(f"""
                <div style="text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                    <div style="font-size: 12px; color: #666;">{t['scenario']}</div>
                    <div style="font-size: 24px; font-weight: bold;">${t['target_price']:.0f}</div>
                    <div style="font-size: 16px; color: {change_color};">{t['change_pct']:+.0f}%</div>
                    <div style="font-size: 10px; color: #888; margin-top: 5px;">{t['description']}</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 综合信号（保留原有）
    signal_col1, signal_col2 = st.columns(2)
    
    with signal_col1:
        st.subheader("🎯 底部/顶部信号强度")
        
        # 底部/顶部分数条
        bottom_score = composite.get('composite_bottom_score', 0)
        top_score = composite.get('composite_top_score', 0)
        
        st.progress(bottom_score / 100)
        st.caption(f"底部信号强度: {bottom_score:.0f}/100")
        
        st.progress(top_score / 100)
        st.caption(f"顶部信号强度: {top_score:.0f}/100")
    
    with signal_col2:
        st.subheader("📊 分项评分")
        
        scores = {
            "估值底部分": composite.get('valuation_bottom_score', 0),
            "技术底部分": composite.get('technical_bottom_score', 0),
            "动量底部分": composite.get('momentum_bottom_score', 0),
        }
        
        fig = go.Figure(go.Bar(
            x=list(scores.values()),
            y=list(scores.keys()),
            orientation='h',
            marker_color=['#2ecc71', '#3498db', '#9b59b6']
        ))
        fig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_range=[0, 100]
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # 详细指标
    tab1, tab2, tab3, tab4 = st.tabs(["📈 估值详情", "📉 技术指标", "👥 同行比较", "📊 历史图表"])
    
    with tab1:
        render_valuation_tab(valuation)
    
    with tab2:
        render_technical_tab(technical)
    
    with tab3:
        render_peer_comparison_tab(ticker, valuation, all_data)
    
    with tab4:
        render_chart_tab(ticker)


def render_valuation_tab(valuation):
    """估值分析标签页"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("当前估值")
        metrics = {
            "P/E TTM": valuation.get('pe_ttm'),
            "P/E Forward": valuation.get('pe_forward'),
            "P/S TTM": valuation.get('ps_ttm'),
            "P/B": valuation.get('pb'),
            "PEG": valuation.get('peg'),
            "EV/EBITDA": valuation.get('ev_ebitda')
        }
        
        for name, value in metrics.items():
            if value is not None:
                st.metric(name, f"{value:.2f}")
    
    with col2:
        st.subheader("历史分位数")
        
        pe_pct = valuation.get('pe_percentile', 50)
        ps_pct = valuation.get('ps_percentile', 50)
        
        # PE分位数
        st.write("P/E 历史分位")
        fig_pe = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pe_pct,
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#3498db"},
                'steps': [
                    {'range': [0, 25], 'color': "#2ecc71"},
                    {'range': [25, 75], 'color': "#f1c40f"},
                    {'range': [75, 100], 'color': "#e74c3c"}
                ]
            },
            title={'text': f"{valuation.get('pe_signal', 'N/A')}"}
        ))
        fig_pe.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_pe, use_container_width=True)
        
        # 历史范围
        st.caption(f"5年范围: {valuation.get('pe_5y_min', 'N/A'):.1f} - {valuation.get('pe_5y_max', 'N/A'):.1f}" 
                  if valuation.get('pe_5y_min') else "历史数据不可用")


def render_technical_tab(technical):
    """技术指标标签页"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("动量指标")
        st.metric("RSI (14)", f"{technical.get('rsi', 50):.1f}", 
                 delta=technical.get('rsi_signal', ''))
        st.metric("1月涨跌", f"{technical.get('momentum_1m', 0):+.1f}%")
        st.metric("3月涨跌", f"{technical.get('momentum_3m', 0):+.1f}%")
    
    with col2:
        st.subheader("均线偏离")
        st.metric("vs 50MA", f"{technical.get('ma_50_dev', 0):+.1f}%")
        st.metric("vs 200MA", f"{technical.get('ma_200_dev', 0):+.1f}%",
                 delta=technical.get('ma_signal', ''))
    
    with col3:
        st.subheader("位置指标")
        st.metric("52周位置", f"{technical.get('week_52_position', 50):.0f}%",
                 delta=technical.get('week_52_signal', ''))
        st.metric("布林带位置", f"{technical.get('bb_position', 50):.0f}%",
                 delta=technical.get('bb_signal', ''))
        st.metric("20日波动率", f"{technical.get('volatility_20d', 0):.1f}%")


def render_peer_comparison_tab(ticker, valuation, all_data):
    """同行比较标签页"""
    st.subheader(f"{ticker} vs 同行")
    
    peers = valuation.get('peer_list', [])
    if not peers:
        st.info("未找到可比公司")
        return
    
    st.write(f"可比公司: {', '.join(peers)}")
    
    # 创建比较表格
    comparison_df = all_data[all_data['ticker'].isin([ticker] + peers)][
        ['ticker', 'name', 'price', 'pe_ttm', 'ps_ttm', 'pb', 'market_cap']
    ].copy()
    
    if not comparison_df.empty:
        comparison_df['market_cap_b'] = comparison_df['market_cap'] / 1e9
        comparison_df = comparison_df.sort_values('market_cap', ascending=False)
        
        # 高亮当前股票
        st.dataframe(
            comparison_df[['ticker', 'name', 'price', 'pe_ttm', 'ps_ttm', 'pb', 'market_cap_b']].round(2),
            use_container_width=True
        )
        
        # PE比较图
        fig = px.bar(
            comparison_df,
            x='ticker',
            y='pe_ttm',
            title='P/E TTM 比较',
            color='ticker',
            color_discrete_map={ticker: '#e74c3c'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 相对于同行的溢价/折价
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pe_vs = valuation.get('pe_vs_peers_pct', 0)
        st.metric(
            "P/E vs 同行中位数",
            f"{pe_vs:+.1f}%",
            delta="溢价" if pe_vs > 0 else "折价"
        )
    
    with col2:
        ps_vs = valuation.get('ps_vs_peers_pct', 0)
        st.metric(
            "P/S vs 同行中位数",
            f"{ps_vs:+.1f}%"
        )
    
    with col3:
        pb_vs = valuation.get('pb_vs_peers_pct', 0)
        st.metric(
            "P/B vs 同行中位数",
            f"{pb_vs:+.1f}%"
        )


def render_chart_tab(ticker):
    """历史图表标签页"""
    # 获取历史数据
    hist = fetch_price_history(ticker, years=2)
    
    if hist is None or hist.empty:
        st.warning("无法获取历史数据")
        return
    
    # 计算指标
    hist['MA50'] = hist['Close'].rolling(50).mean()
    hist['MA200'] = hist['Close'].rolling(200).mean()
    hist['RSI'] = calculate_rsi(hist['Close'])
    
    bb = calculate_bollinger_bands(hist['Close'])
    hist['BB_Upper'] = bb['upper']
    hist['BB_Lower'] = bb['lower']
    
    # 创建图表
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=[f'{ticker} 价格', 'RSI']
    )
    
    # 价格和均线
    fig.add_trace(
        go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='价格'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['MA50'], name='MA50', line=dict(color='blue', width=1)),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['MA200'], name='MA200', line=dict(color='red', width=1)),
        row=1, col=1
    )
    
    # 布林带
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['BB_Upper'], name='BB上轨', 
                  line=dict(color='gray', width=1, dash='dash')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['BB_Lower'], name='BB下轨',
                  line=dict(color='gray', width=1, dash='dash')),
        row=1, col=1
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='purple')),
        row=2, col=1
    )
    
    # RSI超买超卖线
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    fig.update_layout(
        height=600,
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_market_scan():
    """全市场扫描页面"""
    st.title("📡 全市场扫描")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.info(f"扫描股票池: {len(STOCK_UNIVERSE)} 只股票")
    
    with col2:
        send_telegram = st.checkbox("📱 推送到Telegram", value=True)
    
    with col3:
        scan_button = st.button("🔍 开始扫描", type="primary")
    
    if scan_button:
        run_market_scan(send_telegram=send_telegram)
    
    # 显示结果
    if st.session_state.scan_results is not None:
        render_scan_results()


def run_market_scan(send_telegram: bool = False):
    """执行全市场扫描"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 加载数据
    status_text.text("正在加载股票数据...")
    all_data = load_data(force_refresh=True)
    progress_bar.progress(30)
    
    # 检查数据是否有效
    if all_data is None or all_data.empty:
        st.error("❌ 无法获取股票数据，请稍后重试")
        progress_bar.empty()
        status_text.empty()
        return
    
    if 'ticker' not in all_data.columns:
        st.error("❌ 数据格式错误，缺少ticker列")
        progress_bar.empty()
        status_text.empty()
        return
    
    tickers = all_data['ticker'].unique()
    total_tickers = len(tickers)
    
    # 计算估值
    status_text.text(f"正在计算估值指标... (0/{total_tickers})")
    valuation_results = {}
    for i, ticker in enumerate(tickers):
        try:
            valuation_results[ticker] = get_full_valuation_analysis(ticker, all_data)
        except Exception as e:
            st.warning(f"估值计算失败: {ticker}")
        if i % 20 == 0:
            progress_bar.progress(30 + int(30 * i / total_tickers))
            status_text.text(f"正在计算估值指标... ({i}/{total_tickers})")
    
    st.session_state.valuation_results = valuation_results
    progress_bar.progress(60)
    
    # 计算技术指标
    status_text.text(f"正在计算技术指标... (0/{total_tickers})")
    technical_results = {}
    for i, ticker in enumerate(tickers):
        try:
            tech = get_technical_indicators(ticker)
            if tech:
                tech_score = calculate_technical_score(tech)
                tech.update(tech_score)
                technical_results[ticker] = tech
        except Exception as e:
            pass  # 静默处理技术指标错误
        if i % 20 == 0:
            progress_bar.progress(60 + int(30 * i / total_tickers))
            status_text.text(f"正在计算技术指标... ({i}/{total_tickers})")
    
    st.session_state.technical_results = technical_results
    progress_bar.progress(90)
    
    # 综合评分
    status_text.text("正在生成综合评分...")
    scan_results = scan_all_stocks(all_data, valuation_results, technical_results)
    st.session_state.scan_results = scan_results
    
    progress_bar.progress(95)
    
    # Telegram 推送
    if send_telegram:
        status_text.text("正在发送Telegram预警...")
        telegram_success = send_scan_alerts(scan_results, valuation_results, technical_results)
        if telegram_success:
            st.success("✅ 已推送到Telegram")
        else:
            st.warning("⚠️ Telegram推送失败，请检查webhook配置")
    
    progress_bar.progress(100)
    status_text.text(f"扫描完成! 成功获取 {len(scan_results)} 只股票数据")
    time.sleep(1)
    status_text.empty()
    progress_bar.empty()


def send_scan_alerts(scan_results, valuation_results, technical_results) -> bool:
    """发送扫描预警到Telegram"""
    from config import TELEGRAM_WEBHOOK_URL
    
    if not TELEGRAM_WEBHOOK_URL:
        return False
    
    alerts_sent = 0
    
    try:
        # 发送摘要
        summary = format_scan_summary(scan_results)
        send_telegram_alert(summary, TELEGRAM_WEBHOOK_URL)
        alerts_sent += 1
        
        # 发送强底部信号 (>= 70)
        strong_bottom = scan_results[scan_results['composite_bottom_score'] >= 70].head(5)
        for _, row in strong_bottom.iterrows():
            ticker = row['ticker']
            val_result = valuation_results.get(ticker, {})
            tech_result = technical_results.get(ticker, {})
            
            composite = {
                'composite_bottom_score': row['composite_bottom_score'],
                'composite_top_score': row['composite_top_score'],
                'valuation_bottom_score': row.get('valuation_bottom_score', 0),
                'valuation_top_score': row.get('valuation_top_score', 0),
                'technical_bottom_score': row.get('technical_bottom_score', 0),
                'technical_top_score': row.get('technical_top_score', 0),
                'momentum_bottom_score': row.get('momentum_bottom_score', 0),
                'momentum_top_score': row.get('momentum_top_score', 0),
                'alert_type': 'STRONG_BOTTOM'
            }
            
            msg = generate_alert_message(ticker, val_result, tech_result, composite)
            if msg:
                send_telegram_alert(msg, TELEGRAM_WEBHOOK_URL)
                alerts_sent += 1
        
        # 发送强顶部信号 (>= 70)
        strong_top = scan_results[scan_results['composite_top_score'] >= 70].head(5)
        for _, row in strong_top.iterrows():
            ticker = row['ticker']
            val_result = valuation_results.get(ticker, {})
            tech_result = technical_results.get(ticker, {})
            
            composite = {
                'composite_bottom_score': row['composite_bottom_score'],
                'composite_top_score': row['composite_top_score'],
                'valuation_bottom_score': row.get('valuation_bottom_score', 0),
                'valuation_top_score': row.get('valuation_top_score', 0),
                'technical_bottom_score': row.get('technical_bottom_score', 0),
                'technical_top_score': row.get('technical_top_score', 0),
                'momentum_bottom_score': row.get('momentum_bottom_score', 0),
                'momentum_top_score': row.get('momentum_top_score', 0),
                'alert_type': 'STRONG_TOP'
            }
            
            msg = generate_alert_message(ticker, val_result, tech_result, composite)
            if msg:
                send_telegram_alert(msg, TELEGRAM_WEBHOOK_URL)
                alerts_sent += 1
        
        return alerts_sent > 0
        
    except Exception as e:
        print(f"Telegram推送错误: {e}")
        return False


def render_scan_results():
    """渲染扫描结果"""
    scan_results = st.session_state.scan_results
    
    if scan_results is None or scan_results.empty:
        st.warning("暂无扫描结果")
        return
    
    # 摘要统计
    st.markdown(format_scan_summary(scan_results))
    
    st.markdown("---")
    
    # 底部候选和顶部候选
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🟢 底部候选 (最可能触底)")
        bottom = get_bottom_candidates(scan_results, 15)
        
        if not bottom.empty:
            display_df = bottom[['ticker', 'name', 'price', 'composite_bottom_score', 
                               'pe_percentile', 'rsi', 'week_52_position']].copy()
            display_df.columns = ['代码', '名称', '价格', '底部分', 'PE分位', 'RSI', '52周位置']
            st.dataframe(display_df.round(1), use_container_width=True, hide_index=True)
        else:
            st.info("暂无明显底部信号")
    
    with col2:
        st.subheader("🔴 顶部候选 (最可能见顶)")
        top = get_top_candidates(scan_results, 15)
        
        if not top.empty:
            display_df = top[['ticker', 'name', 'price', 'composite_top_score',
                            'pe_percentile', 'rsi', 'week_52_position']].copy()
            display_df.columns = ['代码', '名称', '价格', '顶部分', 'PE分位', 'RSI', '52周位置']
            st.dataframe(display_df.round(1), use_container_width=True, hide_index=True)
        else:
            st.info("暂无明显顶部信号")
    
    st.markdown("---")
    
    # 完整结果表
    with st.expander("📋 查看完整扫描结果"):
        st.dataframe(scan_results.round(2), use_container_width=True)


def render_peer_comparison():
    """同业比较页面"""
    st.title("📊 同业比较矩阵")
    
    # 选择行业
    sectors = list(SECTOR_MAPPING.keys())
    selected_sector = st.selectbox("选择行业", sectors)
    
    if selected_sector:
        tickers = SECTOR_MAPPING[selected_sector]
        st.info(f"该行业共 {len(tickers)} 只股票")
        
        if st.button("生成比较矩阵", type="primary"):
            render_sector_matrix(tickers, selected_sector)


def render_sector_matrix(tickers: list, sector_name: str):
    """渲染行业比较矩阵"""
    with st.spinner("正在加载数据..."):
        all_data = batch_fetch_stocks(tickers, max_workers=10)
    
    if all_data.empty:
        st.error("无法获取数据")
        return
    
    # 创建比较表格
    comparison_df = all_data[['ticker', 'name', 'price', 'market_cap', 
                              'pe_ttm', 'pe_forward', 'ps_ttm', 'pb', 
                              'profit_margin', 'revenue_growth']].copy()
    
    comparison_df['market_cap_b'] = comparison_df['market_cap'] / 1e9
    
    # 计算行业中位数
    pe_median = comparison_df['pe_ttm'].median()
    ps_median = comparison_df['ps_ttm'].median()
    
    # 计算相对估值
    comparison_df['pe_vs_median'] = ((comparison_df['pe_ttm'] - pe_median) / pe_median * 100).round(1)
    comparison_df['ps_vs_median'] = ((comparison_df['ps_ttm'] - ps_median) / ps_median * 100).round(1)
    
    # 排序
    comparison_df = comparison_df.sort_values('pe_vs_median')
    
    st.subheader(f"{sector_name} 估值比较")
    
    # 摘要
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("行业P/E中位数", f"{pe_median:.1f}" if pe_median else "N/A")
    with col2:
        st.metric("行业P/S中位数", f"{ps_median:.1f}" if ps_median else "N/A")
    with col3:
        st.metric("股票数量", len(comparison_df))
    
    # 表格
    display_df = comparison_df[['ticker', 'name', 'price', 'market_cap_b', 
                                'pe_ttm', 'pe_vs_median', 'ps_ttm', 'ps_vs_median']].copy()
    display_df.columns = ['代码', '名称', '价格', '市值(B)', 'P/E', 'PE vs 中位数%', 'P/S', 'PS vs 中位数%']
    
    st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)
    
    # 可视化
    fig = px.scatter(
        comparison_df,
        x='pe_ttm',
        y='ps_ttm',
        size='market_cap_b',
        color='pe_vs_median',
        hover_name='ticker',
        title=f'{sector_name} P/E vs P/S 散点图',
        color_continuous_scale='RdYlGn_r'
    )
    
    # 添加中位数参考线
    fig.add_hline(y=ps_median, line_dash="dash", line_color="gray", 
                 annotation_text=f"P/S中位数: {ps_median:.1f}")
    fig.add_vline(x=pe_median, line_dash="dash", line_color="gray",
                 annotation_text=f"P/E中位数: {pe_median:.1f}")
    
    st.plotly_chart(fig, use_container_width=True)


def render_settings():
    """设置页面"""
    st.title("⚙️ 设置")
    
    st.subheader("Telegram 预警设置")
    
    webhook_url = st.text_input(
        "Cloudflare Worker Webhook URL",
        value="",
        type="password"
    )
    
    if st.button("测试连接"):
        if webhook_url:
            success = send_telegram_alert("🔔 测试消息 - 估值预警系统已连接", webhook_url)
            if success:
                st.success("✅ 测试消息发送成功!")
            else:
                st.error("❌ 发送失败，请检查webhook配置")
        else:
            st.warning("请输入webhook URL")
    
    st.markdown("---")
    
    st.subheader("预警阈值设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.number_input("底部预警阈值 (综合分)", value=ALERT_THRESHOLDS['bottom_score'], min_value=50, max_value=100)
        st.number_input("底部估值阈值", value=ALERT_THRESHOLDS['valuation_bottom'], min_value=50, max_value=100)
    
    with col2:
        st.number_input("顶部预警阈值 (综合分)", value=ALERT_THRESHOLDS['top_score'], min_value=0, max_value=50)
        st.number_input("顶部估值阈值", value=ALERT_THRESHOLDS['valuation_top'], min_value=0, max_value=50)
    
    st.markdown("---")
    
    st.subheader("股票池管理")
    st.write(f"当前股票池: {len(STOCK_UNIVERSE)} 只")
    
    with st.expander("查看完整股票列表"):
        st.write(STOCK_UNIVERSE)


def main():
    """主函数"""
    init_session_state()
    
    page = render_sidebar()
    
    if page == "🔍 单股分析":
        render_single_stock_analysis()
    elif page == "📡 全市场扫描":
        render_market_scan()
    elif page == "📊 同业比较":
        render_peer_comparison()
    elif page == "⚙️ 设置":
        render_settings()


if __name__ == "__main__":
    main()
