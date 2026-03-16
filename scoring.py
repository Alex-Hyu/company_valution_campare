"""
综合评分与预警模块
整合估值、技术、动量等多因子，生成综合评分和预警
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import requests
import json

from config import SCORE_WEIGHTS, ALERT_THRESHOLDS, TELEGRAM_WEBHOOK_URL


def calculate_composite_score(
    valuation_result: Dict,
    technical_result: Dict
) -> Dict:
    """
    计算综合评分
    
    底部综合分 = 估值底部分 * 0.30 + 技术底部分 * 0.25 + 其他因子...
    顶部综合分 = 估值顶部分 * 0.30 + 技术顶部分 * 0.25 + 其他因子...
    """
    # 获取各维度分数
    val_bottom = valuation_result.get('valuation_bottom_score', 50)
    val_top = valuation_result.get('valuation_top_score', 50)
    tech_bottom = technical_result.get('bottom_score', 50)
    tech_top = technical_result.get('top_score', 50)
    
    # 动量因子 (使用技术指标中的动量)
    momentum_1m = technical_result.get('momentum_1m', 0)
    momentum_3m = technical_result.get('momentum_3m', 0)
    
    # 动量评分
    momentum_bottom = 0
    momentum_top = 0
    
    # 下跌幅度大 = 底部信号
    if momentum_1m < -20:
        momentum_bottom += 50
    elif momentum_1m < -10:
        momentum_bottom += 35
    elif momentum_1m < -5:
        momentum_bottom += 20
    
    # 上涨幅度大 = 顶部信号
    if momentum_1m > 30:
        momentum_top += 50
    elif momentum_1m > 20:
        momentum_top += 35
    elif momentum_1m > 10:
        momentum_top += 20
    
    # 3个月动量补充
    if momentum_3m < -30:
        momentum_bottom += 30
    elif momentum_3m < -15:
        momentum_bottom += 20
    
    if momentum_3m > 50:
        momentum_top += 30
    elif momentum_3m > 30:
        momentum_top += 20
    
    momentum_bottom = min(100, momentum_bottom)
    momentum_top = min(100, momentum_top)
    
    # 相对强度因子
    rs_vs_spy = valuation_result.get('rs_vs_spy', 0)
    
    rs_bottom = 0
    rs_top = 0
    
    if rs_vs_spy < -15:
        rs_bottom += 60
    elif rs_vs_spy < -10:
        rs_bottom += 40
    elif rs_vs_spy < -5:
        rs_bottom += 20
    
    if rs_vs_spy > 20:
        rs_top += 60
    elif rs_vs_spy > 10:
        rs_top += 40
    elif rs_vs_spy > 5:
        rs_top += 20
    
    # 波动率因子
    volatility = technical_result.get('volatility_20d', 30)
    
    vol_adjustment = 0
    if volatility > 60:  # 高波动
        vol_adjustment = 10  # 增加信号强度
    elif volatility < 20:  # 低波动
        vol_adjustment = -5  # 减少信号强度
    
    # 加权计算
    weights = SCORE_WEIGHTS
    
    composite_bottom = (
        val_bottom * weights['valuation'] +
        tech_bottom * weights['technical'] +
        momentum_bottom * weights['momentum'] +
        rs_bottom * weights['relative_strength']
    ) * (1 + vol_adjustment / 100)
    
    composite_top = (
        val_top * weights['valuation'] +
        tech_top * weights['technical'] +
        momentum_top * weights['momentum'] +
        rs_top * weights['relative_strength']
    ) * (1 + vol_adjustment / 100)
    
    # 确保在0-100范围
    composite_bottom = max(0, min(100, composite_bottom))
    composite_top = max(0, min(100, composite_top))
    
    # 生成信号
    signal = "NEUTRAL"
    alert_type = None
    
    thresholds = ALERT_THRESHOLDS
    
    # 底部预警判断
    if composite_bottom >= thresholds['bottom_score'] and val_bottom >= thresholds['valuation_bottom']:
        if composite_bottom >= 85:
            signal = "🟢 STRONG BUY SIGNAL"
            alert_type = "STRONG_BOTTOM"
        else:
            signal = "🟡 POTENTIAL BOTTOM"
            alert_type = "BOTTOM"
    
    # 顶部预警判断
    elif composite_top >= (100 - thresholds['top_score']) and val_top >= (100 - thresholds['valuation_top']):
        if composite_top >= 85:
            signal = "🔴 STRONG SELL SIGNAL"
            alert_type = "STRONG_TOP"
        else:
            signal = "🟠 POTENTIAL TOP"
            alert_type = "TOP"
    
    return {
        "composite_bottom_score": round(composite_bottom, 1),
        "composite_top_score": round(composite_top, 1),
        "valuation_bottom_score": val_bottom,
        "valuation_top_score": val_top,
        "technical_bottom_score": tech_bottom,
        "technical_top_score": tech_top,
        "momentum_bottom_score": momentum_bottom,
        "momentum_top_score": momentum_top,
        "signal": signal,
        "alert_type": alert_type
    }


def generate_alert_message(
    ticker: str,
    valuation_result: Dict,
    technical_result: Dict,
    composite_result: Dict
) -> str:
    """
    生成预警消息
    """
    alert_type = composite_result.get('alert_type')
    if not alert_type:
        return None
    
    # 确定是底部还是顶部信号
    is_bottom = 'BOTTOM' in alert_type
    
    # 构建消息
    emoji = "🟢" if is_bottom else "🔴"
    direction = "底部" if is_bottom else "顶部"
    
    msg = f"""
{emoji} **{ticker} {direction}预警** {emoji}

📊 **基本信息**
• 股票: {valuation_result.get('name', ticker)}
• 价格: ${valuation_result.get('price', 0):.2f}
• 行业: {valuation_result.get('sector', 'N/A')}

📈 **估值指标**
• P/E TTM: {valuation_result.get('pe_ttm', 'N/A'):.1f if valuation_result.get('pe_ttm') else 'N/A'}
• P/E 历史分位: {valuation_result.get('pe_percentile', 50):.0f}%
• P/E vs 同行: {valuation_result.get('pe_vs_peers_pct', 0):+.1f}%
• P/S TTM: {valuation_result.get('ps_ttm', 'N/A'):.1f if valuation_result.get('ps_ttm') else 'N/A'}

📉 **技术指标**
• RSI: {technical_result.get('rsi', 50):.1f}
• 52周位置: {technical_result.get('week_52_position', 50):.0f}%
• vs 200MA: {technical_result.get('ma_200_dev', 0):+.1f}%
• 1月动量: {technical_result.get('momentum_1m', 0):+.1f}%

🎯 **综合评分**
• {direction}信号强度: {composite_result.get(f'composite_{"bottom" if is_bottom else "top"}_score', 0):.0f}/100
• 估值分: {composite_result.get(f'valuation_{"bottom" if is_bottom else "top"}_score', 0):.0f}/100
• 技术分: {composite_result.get(f'technical_{"bottom" if is_bottom else "top"}_score', 0):.0f}/100

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    return msg.strip()


def send_telegram_alert(message: str, webhook_url: str = None) -> bool:
    """
    通过Telegram发送预警
    """
    if not webhook_url:
        webhook_url = TELEGRAM_WEBHOOK_URL
    
    if not webhook_url or webhook_url == "YOUR_CLOUDFLARE_WORKER_URL":
        print("Telegram webhook not configured")
        return False
    
    try:
        payload = {
            "message": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"Alert sent successfully")
            return True
        else:
            print(f"Failed to send alert: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")
        return False


def scan_all_stocks(all_data: pd.DataFrame, 
                   valuation_results: Dict[str, Dict],
                   technical_results: Dict[str, Dict]) -> pd.DataFrame:
    """
    扫描所有股票，计算综合评分，找出预警信号
    """
    results = []
    
    for ticker in all_data['ticker'].unique():
        val_result = valuation_results.get(ticker, {})
        tech_result = technical_results.get(ticker, {})
        
        if not val_result or not tech_result:
            continue
        
        # 计算综合评分
        composite = calculate_composite_score(val_result, tech_result)
        
        # 合并所有结果
        row = {
            "ticker": ticker,
            "name": val_result.get('name', ticker),
            "sector": val_result.get('sector', ''),
            "price": val_result.get('price', 0),
            "pe_ttm": val_result.get('pe_ttm'),
            "pe_percentile": val_result.get('pe_percentile', 50),
            "pe_vs_peers_pct": val_result.get('pe_vs_peers_pct', 0),
            "rsi": tech_result.get('rsi', 50),
            "week_52_position": tech_result.get('week_52_position', 50),
            "ma_200_dev": tech_result.get('ma_200_dev', 0),
            "momentum_1m": tech_result.get('momentum_1m', 0),
            **composite
        }
        
        results.append(row)
    
    df = pd.DataFrame(results)
    
    # 按底部信号排序（找最可能触底的）
    df = df.sort_values('composite_bottom_score', ascending=False)
    
    return df


def get_bottom_candidates(scan_results: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    获取最可能触底的股票
    """
    # 过滤出有底部信号的
    candidates = scan_results[scan_results['composite_bottom_score'] >= 50].copy()
    return candidates.head(top_n)


def get_top_candidates(scan_results: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    获取最可能见顶的股票
    """
    # 按顶部信号排序
    sorted_df = scan_results.sort_values('composite_top_score', ascending=False)
    candidates = sorted_df[sorted_df['composite_top_score'] >= 50].copy()
    return candidates.head(top_n)


def format_scan_summary(scan_results: pd.DataFrame) -> str:
    """
    格式化扫描摘要
    """
    total = len(scan_results)
    
    # 统计各类信号
    strong_bottom = len(scan_results[scan_results['composite_bottom_score'] >= 75])
    potential_bottom = len(scan_results[(scan_results['composite_bottom_score'] >= 50) & 
                                        (scan_results['composite_bottom_score'] < 75)])
    strong_top = len(scan_results[scan_results['composite_top_score'] >= 75])
    potential_top = len(scan_results[(scan_results['composite_top_score'] >= 50) & 
                                     (scan_results['composite_top_score'] < 75)])
    
    summary = f"""
📊 **扫描摘要** ({datetime.now().strftime('%Y-%m-%d %H:%M')})

总扫描股票: {total}

🟢 **底部信号**
• 强底部信号 (>75): {strong_bottom}
• 潜在底部 (50-75): {potential_bottom}

🔴 **顶部信号**
• 强顶部信号 (>75): {strong_top}
• 潜在顶部 (50-75): {potential_top}
"""
    return summary.strip()


if __name__ == "__main__":
    # 测试
    print("Testing scoring module...")
    
    # 模拟数据
    val_result = {
        "ticker": "TEST",
        "name": "Test Stock",
        "price": 100,
        "sector": "Technology",
        "pe_ttm": 15,
        "pe_percentile": 20,
        "ps_percentile": 25,
        "pe_vs_peers_pct": -15,
        "ps_vs_peers_pct": -10,
        "valuation_bottom_score": 65,
        "valuation_top_score": 15,
    }
    
    tech_result = {
        "rsi": 28,
        "week_52_position": 15,
        "ma_200_dev": -18,
        "momentum_1m": -12,
        "momentum_3m": -25,
        "volatility_20d": 45,
        "bottom_score": 70,
        "top_score": 10
    }
    
    composite = calculate_composite_score(val_result, tech_result)
    print(f"\nComposite Score Results:")
    for k, v in composite.items():
        print(f"  {k}: {v}")
    
    # 测试消息生成
    msg = generate_alert_message("TEST", val_result, tech_result, composite)
    if msg:
        print(f"\nAlert Message:\n{msg}")
