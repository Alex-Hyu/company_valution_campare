"""
估值分析模块
计算估值指标的历史分位数、同行比较、综合估值评分
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from datetime import datetime, timedelta

from config import PEER_GROUPS, SECTOR_MAPPING, HISTORY_YEARS


def get_peers(ticker: str) -> List[str]:
    """
    获取股票的可比公司
    优先使用手动定义的peer group
    """
    if ticker in PEER_GROUPS:
        return PEER_GROUPS[ticker]
    
    # Fallback到行业分类
    for sector, stocks in SECTOR_MAPPING.items():
        if ticker in stocks:
            peers = [s for s in stocks if s != ticker]
            return peers[:8]
    
    return []


def calculate_pe_percentile(ticker: str, current_pe: float, years: int = 5) -> Dict:
    """
    计算当前PE在历史中的分位数
    
    由于yfinance免费版无法获取历史PE，这里使用价格/EPS变化来估算
    """
    try:
        stock = yf.Ticker(ticker)
        
        # 获取历史价格
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty or current_pe is None or current_pe <= 0:
            return {
                "pe_percentile": 50,
                "pe_5y_min": None,
                "pe_5y_max": None,
                "pe_5y_median": None,
                "pe_signal": "NO_DATA"
            }
        
        # 简化假设：使用价格相对变化来估算PE变化
        # 实际上EPS也会变化，所以这只是粗略估算
        current_price = hist['Close'].iloc[-1]
        price_ratio = hist['Close'] / current_price
        
        # 估算历史PE
        estimated_pe = current_pe * price_ratio
        
        # 去除异常值 (PE < 0 或 PE > 500)
        estimated_pe = estimated_pe[(estimated_pe > 0) & (estimated_pe < 500)]
        
        if len(estimated_pe) == 0:
            return {
                "pe_percentile": 50,
                "pe_5y_min": None,
                "pe_5y_max": None,
                "pe_5y_median": None,
                "pe_signal": "NO_DATA"
            }
        
        # 计算分位数
        percentile = (estimated_pe < current_pe).sum() / len(estimated_pe) * 100
        
        # 获取历史范围
        pe_min = estimated_pe.min()
        pe_max = estimated_pe.max()
        pe_median = estimated_pe.median()
        pe_25 = estimated_pe.quantile(0.25)
        pe_75 = estimated_pe.quantile(0.75)
        
        # 生成信号
        if percentile < 10:
            signal = "VERY_CHEAP"
        elif percentile < 25:
            signal = "CHEAP"
        elif percentile > 90:
            signal = "VERY_EXPENSIVE"
        elif percentile > 75:
            signal = "EXPENSIVE"
        else:
            signal = "FAIR"
        
        return {
            "pe_percentile": percentile,
            "pe_5y_min": pe_min,
            "pe_5y_max": pe_max,
            "pe_5y_median": pe_median,
            "pe_5y_25pct": pe_25,
            "pe_5y_75pct": pe_75,
            "pe_signal": signal
        }
        
    except Exception as e:
        print(f"Error calculating PE percentile for {ticker}: {e}")
        return {
            "pe_percentile": 50,
            "pe_signal": "ERROR"
        }


def calculate_ps_percentile(ticker: str, current_ps: float, years: int = 5) -> Dict:
    """
    计算当前P/S在历史中的分位数
    """
    try:
        stock = yf.Ticker(ticker)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty or current_ps is None or current_ps <= 0:
            return {
                "ps_percentile": 50,
                "ps_5y_min": None,
                "ps_5y_max": None,
                "ps_signal": "NO_DATA"
            }
        
        # 使用价格变化估算
        current_price = hist['Close'].iloc[-1]
        price_ratio = hist['Close'] / current_price
        estimated_ps = current_ps * price_ratio
        
        # 去除异常值
        estimated_ps = estimated_ps[(estimated_ps > 0) & (estimated_ps < 100)]
        
        if len(estimated_ps) == 0:
            return {
                "ps_percentile": 50,
                "ps_signal": "NO_DATA"
            }
        
        percentile = (estimated_ps < current_ps).sum() / len(estimated_ps) * 100
        
        if percentile < 10:
            signal = "VERY_CHEAP"
        elif percentile < 25:
            signal = "CHEAP"
        elif percentile > 90:
            signal = "VERY_EXPENSIVE"
        elif percentile > 75:
            signal = "EXPENSIVE"
        else:
            signal = "FAIR"
        
        return {
            "ps_percentile": percentile,
            "ps_5y_min": estimated_ps.min(),
            "ps_5y_max": estimated_ps.max(),
            "ps_5y_median": estimated_ps.median(),
            "ps_signal": signal
        }
        
    except Exception as e:
        print(f"Error calculating PS percentile for {ticker}: {e}")
        return {"ps_percentile": 50, "ps_signal": "ERROR"}


def compare_with_peers(ticker: str, all_data: pd.DataFrame) -> Dict:
    """
    与同行比较估值
    返回相对于同行中位数的溢价/折价百分比
    """
    peers = get_peers(ticker)
    
    if not peers:
        return {
            "pe_vs_peers_pct": 0,
            "ps_vs_peers_pct": 0,
            "pb_vs_peers_pct": 0,
            "peer_rank": None,
            "peer_count": 0,
            "peer_list": []
        }
    
    # 获取当前股票数据
    current_row = all_data[all_data['ticker'] == ticker]
    if current_row.empty:
        return {"peer_count": 0, "peer_list": peers}
    
    current = current_row.iloc[0]
    
    # 获取peer数据
    peer_data = all_data[all_data['ticker'].isin(peers)].copy()
    
    if peer_data.empty:
        return {"peer_count": 0, "peer_list": peers}
    
    result = {
        "peer_count": len(peer_data),
        "peer_list": peer_data['ticker'].tolist()
    }
    
    # PE比较
    if pd.notna(current.get('pe_ttm')) and current['pe_ttm'] > 0:
        peer_pe = peer_data['pe_ttm'].dropna()
        peer_pe = peer_pe[peer_pe > 0]
        
        if len(peer_pe) > 0:
            peer_pe_median = peer_pe.median()
            result['pe_vs_peers_pct'] = (current['pe_ttm'] - peer_pe_median) / peer_pe_median * 100
            result['peer_pe_median'] = peer_pe_median
            result['peer_pe_min'] = peer_pe.min()
            result['peer_pe_max'] = peer_pe.max()
            
            # 计算排名 (PE越低排名越好)
            all_pe = list(peer_pe) + [current['pe_ttm']]
            all_pe.sort()
            result['pe_rank'] = all_pe.index(current['pe_ttm']) + 1
            result['pe_rank_total'] = len(all_pe)
    
    # PS比较
    if pd.notna(current.get('ps_ttm')) and current['ps_ttm'] > 0:
        peer_ps = peer_data['ps_ttm'].dropna()
        peer_ps = peer_ps[peer_ps > 0]
        
        if len(peer_ps) > 0:
            peer_ps_median = peer_ps.median()
            result['ps_vs_peers_pct'] = (current['ps_ttm'] - peer_ps_median) / peer_ps_median * 100
            result['peer_ps_median'] = peer_ps_median
    
    # PB比较
    if pd.notna(current.get('pb')) and current['pb'] > 0:
        peer_pb = peer_data['pb'].dropna()
        peer_pb = peer_pb[peer_pb > 0]
        
        if len(peer_pb) > 0:
            peer_pb_median = peer_pb.median()
            result['pb_vs_peers_pct'] = (current['pb'] - peer_pb_median) / peer_pb_median * 100
            result['peer_pb_median'] = peer_pb_median
    
    return result


def calculate_valuation_score(
    pe_percentile: float,
    ps_percentile: float,
    pe_vs_peers: float,
    ps_vs_peers: float,
    peg: Optional[float] = None
) -> Dict:
    """
    计算综合估值评分
    
    底部信号（分数越高越像底部）:
    - PE/PS历史分位低
    - 相对同行折价大
    - PEG < 1
    
    顶部信号（分数越高越像顶部）:
    - PE/PS历史分位高
    - 相对同行溢价大
    - PEG > 2
    """
    bottom_score = 0
    top_score = 0
    
    # PE历史分位 (0-30分)
    if pe_percentile < 10:
        bottom_score += 30
    elif pe_percentile < 20:
        bottom_score += 25
    elif pe_percentile < 30:
        bottom_score += 20
    elif pe_percentile < 40:
        bottom_score += 10
    
    if pe_percentile > 90:
        top_score += 30
    elif pe_percentile > 80:
        top_score += 25
    elif pe_percentile > 70:
        top_score += 20
    elif pe_percentile > 60:
        top_score += 10
    
    # PS历史分位 (0-20分)
    if ps_percentile < 10:
        bottom_score += 20
    elif ps_percentile < 25:
        bottom_score += 15
    elif ps_percentile < 40:
        bottom_score += 10
    
    if ps_percentile > 90:
        top_score += 20
    elif ps_percentile > 75:
        top_score += 15
    elif ps_percentile > 60:
        top_score += 10
    
    # 同行比较 - PE (0-25分)
    if pe_vs_peers < -30:
        bottom_score += 25
    elif pe_vs_peers < -20:
        bottom_score += 20
    elif pe_vs_peers < -10:
        bottom_score += 15
    elif pe_vs_peers < 0:
        bottom_score += 10
    
    if pe_vs_peers > 50:
        top_score += 25
    elif pe_vs_peers > 30:
        top_score += 20
    elif pe_vs_peers > 15:
        top_score += 15
    elif pe_vs_peers > 0:
        top_score += 10
    
    # 同行比较 - PS (0-15分)
    if ps_vs_peers < -30:
        bottom_score += 15
    elif ps_vs_peers < -15:
        bottom_score += 10
    elif ps_vs_peers < 0:
        bottom_score += 5
    
    if ps_vs_peers > 40:
        top_score += 15
    elif ps_vs_peers > 20:
        top_score += 10
    elif ps_vs_peers > 0:
        top_score += 5
    
    # PEG (0-10分)
    if peg is not None and peg > 0:
        if peg < 0.8:
            bottom_score += 10
        elif peg < 1.0:
            bottom_score += 7
        elif peg < 1.2:
            bottom_score += 5
        
        if peg > 3:
            top_score += 10
        elif peg > 2.5:
            top_score += 7
        elif peg > 2:
            top_score += 5
    
    # 综合信号
    if bottom_score >= 70:
        signal = "STRONG_UNDERVALUED"
    elif bottom_score >= 50:
        signal = "UNDERVALUED"
    elif top_score >= 70:
        signal = "STRONG_OVERVALUED"
    elif top_score >= 50:
        signal = "OVERVALUED"
    else:
        signal = "FAIR_VALUED"
    
    return {
        "valuation_bottom_score": bottom_score,
        "valuation_top_score": top_score,
        "valuation_signal": signal
    }


def get_full_valuation_analysis(ticker: str, all_data: pd.DataFrame) -> Dict:
    """
    获取完整的估值分析
    """
    # 获取当前股票数据
    current_row = all_data[all_data['ticker'] == ticker]
    if current_row.empty:
        return {"error": "Ticker not found in data"}
    
    current = current_row.iloc[0]
    
    result = {
        "ticker": ticker,
        "name": current.get('name', ticker),
        "sector": current.get('sector', 'Unknown'),
        "price": current.get('price', 0),
        "market_cap": current.get('market_cap', 0),
    }
    
    # 当前估值
    result['pe_ttm'] = current.get('pe_ttm')
    result['pe_forward'] = current.get('pe_forward')
    result['ps_ttm'] = current.get('ps_ttm')
    result['pb'] = current.get('pb')
    result['peg'] = current.get('peg')
    result['ev_ebitda'] = current.get('ev_ebitda')
    
    # PE历史分位
    pe_analysis = calculate_pe_percentile(ticker, current.get('pe_ttm'))
    result.update(pe_analysis)
    
    # PS历史分位
    ps_analysis = calculate_ps_percentile(ticker, current.get('ps_ttm'))
    result.update(ps_analysis)
    
    # 同行比较
    peer_comparison = compare_with_peers(ticker, all_data)
    result.update(peer_comparison)
    
    # 综合估值评分
    valuation_score = calculate_valuation_score(
        pe_percentile=result.get('pe_percentile', 50),
        ps_percentile=result.get('ps_percentile', 50),
        pe_vs_peers=result.get('pe_vs_peers_pct', 0),
        ps_vs_peers=result.get('ps_vs_peers_pct', 0),
        peg=current.get('peg')
    )
    result.update(valuation_score)
    
    return result


if __name__ == "__main__":
    # 测试
    from data_fetcher import batch_fetch_stocks
    from config import STOCK_UNIVERSE
    
    print("Testing valuation analysis module...")
    
    # 获取数据
    test_tickers = ["NVDA", "AMD", "INTC", "AVGO", "MRVL", "QCOM"]
    all_data = batch_fetch_stocks(test_tickers)
    
    # 测试估值分析
    result = get_full_valuation_analysis("NVDA", all_data)
    
    print(f"\nNVDA Valuation Analysis:")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        elif isinstance(v, list):
            print(f"  {k}: {v[:5]}...")  # 只显示前5个
        else:
            print(f"  {k}: {v}")
