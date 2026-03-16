"""
数据获取模块
使用yfinance获取股票价格、估值指标、历史数据
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

from config import STOCK_UNIVERSE, HISTORY_YEARS, PEER_GROUPS, SECTOR_MAPPING


def get_sector_peers(ticker: str) -> List[str]:
    """
    获取股票的可比公司
    优先使用手动定义的peer group，否则fallback到行业分类
    """
    # 优先检查手动定义的peer groups
    if ticker in PEER_GROUPS:
        return PEER_GROUPS[ticker]
    
    # Fallback到行业分类
    for sector, stocks in SECTOR_MAPPING.items():
        if ticker in stocks:
            # 返回同行业其他股票（排除自己）
            peers = [s for s in stocks if s != ticker]
            return peers[:10]  # 最多返回10个
    
    return []


def fetch_single_stock(ticker: str) -> Optional[Dict]:
    """
    获取单只股票的完整数据
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 检查是否获取到有效数据
        if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None:
            # 尝试从历史数据获取价格
            try:
                hist = stock.history(period="5d")
                if hist.empty:
                    print(f"No data available for {ticker}")
                    return None
                current_price = hist['Close'].iloc[-1]
            except:
                print(f"Failed to get any data for {ticker}")
                return None
        else:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        
        # 基础信息
        data = {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap", 0),
            "price": current_price,
        }
        
        # 估值指标
        data["pe_ttm"] = info.get("trailingPE")
        data["pe_forward"] = info.get("forwardPE")
        data["ps_ttm"] = info.get("priceToSalesTrailing12Months")
        data["pb"] = info.get("priceToBook")
        data["peg"] = info.get("pegRatio")
        data["ev_ebitda"] = info.get("enterpriseToEbitda")
        
        # 收益指标
        data["profit_margin"] = info.get("profitMargins")
        data["revenue_growth"] = info.get("revenueGrowth")
        data["earnings_growth"] = info.get("earningsGrowth")
        
        # 52周数据
        data["week_52_high"] = info.get("fiftyTwoWeekHigh", 0)
        data["week_52_low"] = info.get("fiftyTwoWeekLow", 0)
        data["ma_50"] = info.get("fiftyDayAverage")
        data["ma_200"] = info.get("twoHundredDayAverage")
        
        # Beta
        data["beta"] = info.get("beta")
        
        # Short Interest
        data["short_ratio"] = info.get("shortRatio")
        data["short_percent_float"] = info.get("shortPercentOfFloat")
        
        return data
        
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


def fetch_price_history(ticker: str, years: int = 5) -> Optional[pd.DataFrame]:
    """
    获取股票价格历史数据用于计算技术指标
    """
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        hist = stock.history(start=start_date, end=end_date)
        if hist.empty:
            return None
            
        return hist
        
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return None


def fetch_valuation_history(ticker: str, years: int = 5) -> Dict:
    """
    获取历史估值数据用于计算分位数
    注意：yfinance免费版无法获取历史PE等，这里用价格变化来估算
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 当前估值
        current_pe = info.get("trailingPE")
        current_ps = info.get("priceToSalesTrailing12Months")
        current_pb = info.get("priceToBook")
        
        # 获取历史价格
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty or current_pe is None:
            return {}
        
        # 使用价格相对于当前的比例来估算历史PE
        # 这是一个简化假设：假设EPS相对稳定
        current_price = hist['Close'].iloc[-1]
        price_ratio = hist['Close'] / current_price
        
        # 估算历史PE范围
        estimated_pe_history = current_pe * price_ratio
        
        return {
            "pe_history": estimated_pe_history,
            "price_history": hist['Close'],
            "current_pe": current_pe,
            "current_ps": current_ps,
            "current_pb": current_pb,
            "pe_min": estimated_pe_history.min() if len(estimated_pe_history) > 0 else None,
            "pe_max": estimated_pe_history.max() if len(estimated_pe_history) > 0 else None,
            "pe_median": estimated_pe_history.median() if len(estimated_pe_history) > 0 else None,
        }
        
    except Exception as e:
        print(f"Error fetching valuation history for {ticker}: {e}")
        return {}


def calculate_percentile(current_value: float, historical_series: pd.Series) -> float:
    """
    计算当前值在历史数据中的分位数 (0-100)
    """
    if current_value is None or historical_series is None or len(historical_series) == 0:
        return 50.0  # 默认中位数
    
    # 去除NaN
    historical_series = historical_series.dropna()
    if len(historical_series) == 0:
        return 50.0
    
    # 计算分位数
    percentile = (historical_series < current_value).sum() / len(historical_series) * 100
    return percentile


def batch_fetch_stocks(tickers: List[str], max_workers: int = 10) -> pd.DataFrame:
    """
    批量获取股票数据
    使用多线程加速
    """
    results = []
    failed = []
    
    print(f"Fetching data for {len(tickers)} stocks...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(fetch_single_stock, ticker): ticker 
                          for ticker in tickers}
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
                else:
                    failed.append(ticker)
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                failed.append(ticker)
    
    print(f"Successfully fetched: {len(results)}, Failed: {len(failed)}")
    if failed:
        print(f"Failed tickers: {failed[:10]}...")  # 只显示前10个
    
    df = pd.DataFrame(results)
    return df


def calculate_peer_comparison(ticker: str, all_data: pd.DataFrame) -> Dict:
    """
    计算与同行的估值比较
    返回相对于同行中位数的溢价/折价百分比
    """
    peers = get_sector_peers(ticker)
    if not peers:
        return {"pe_vs_peers": 0, "ps_vs_peers": 0, "pb_vs_peers": 0, "peer_count": 0}
    
    # 获取当前股票数据
    current = all_data[all_data['ticker'] == ticker]
    if current.empty:
        return {"pe_vs_peers": 0, "ps_vs_peers": 0, "pb_vs_peers": 0, "peer_count": 0}
    
    current = current.iloc[0]
    
    # 获取peer数据
    peer_data = all_data[all_data['ticker'].isin(peers)]
    if peer_data.empty:
        return {"pe_vs_peers": 0, "ps_vs_peers": 0, "pb_vs_peers": 0, "peer_count": 0}
    
    result = {"peer_count": len(peer_data)}
    
    # 计算各指标相对于peer中位数的偏离
    for metric in ['pe_ttm', 'ps_ttm', 'pb']:
        current_val = current.get(metric)
        peer_median = peer_data[metric].median()
        
        if current_val and peer_median and peer_median > 0:
            # 正数表示溢价，负数表示折价
            premium = (current_val - peer_median) / peer_median * 100
            result[f"{metric.replace('_ttm', '')}_vs_peers"] = premium
        else:
            result[f"{metric.replace('_ttm', '')}_vs_peers"] = 0
    
    return result


def fetch_benchmark_data() -> Dict:
    """
    获取基准指数数据 (SPY, QQQ)
    用于计算相对强度
    """
    benchmarks = {}
    
    for symbol in ['SPY', 'QQQ']:
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1y")
            
            if not hist.empty:
                benchmarks[symbol] = {
                    "price": hist['Close'].iloc[-1],
                    "return_1m": (hist['Close'].iloc[-1] / hist['Close'].iloc[-21] - 1) * 100 if len(hist) > 21 else 0,
                    "return_3m": (hist['Close'].iloc[-1] / hist['Close'].iloc[-63] - 1) * 100 if len(hist) > 63 else 0,
                    "return_ytd": (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100,
                    "history": hist['Close']
                }
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    
    return benchmarks


def calculate_relative_strength(ticker: str, benchmarks: Dict, period_days: int = 21) -> Dict:
    """
    计算相对于大盘的强度
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        
        if hist.empty or 'SPY' not in benchmarks:
            return {"rs_vs_spy": 0, "rs_vs_qqq": 0}
        
        spy_hist = benchmarks['SPY']['history']
        qqq_hist = benchmarks.get('QQQ', {}).get('history')
        
        # 计算最近period_days的回报
        if len(hist) >= period_days:
            stock_return = (hist['Close'].iloc[-1] / hist['Close'].iloc[-period_days] - 1) * 100
        else:
            stock_return = 0
        
        # 获取SPY同期回报
        if len(spy_hist) >= period_days:
            spy_return = (spy_hist.iloc[-1] / spy_hist.iloc[-period_days] - 1) * 100
        else:
            spy_return = 0
        
        # 计算相对强度
        rs_vs_spy = stock_return - spy_return
        
        # 对QQQ做同样的计算
        rs_vs_qqq = 0
        if qqq_hist is not None and len(qqq_hist) >= period_days:
            qqq_return = (qqq_hist.iloc[-1] / qqq_hist.iloc[-period_days] - 1) * 100
            rs_vs_qqq = stock_return - qqq_return
        
        return {
            "rs_vs_spy": rs_vs_spy,
            "rs_vs_qqq": rs_vs_qqq,
            "return_1m": stock_return
        }
        
    except Exception as e:
        print(f"Error calculating RS for {ticker}: {e}")
        return {"rs_vs_spy": 0, "rs_vs_qqq": 0}


if __name__ == "__main__":
    # 测试
    print("Testing data fetcher...")
    
    # 测试单只股票
    data = fetch_single_stock("NVDA")
    if data:
        print(f"\nNVDA data:")
        for k, v in data.items():
            print(f"  {k}: {v}")
    
    # 测试peer获取
    peers = get_sector_peers("NVDA")
    print(f"\nNVDA peers: {peers}")
    
    # 测试批量获取（只取10只测试）
    test_tickers = STOCK_UNIVERSE[:10]
    df = batch_fetch_stocks(test_tickers, max_workers=5)
    print(f"\nBatch fetch result: {len(df)} stocks")
    print(df[['ticker', 'name', 'price', 'pe_ttm', 'ps_ttm']].head())
