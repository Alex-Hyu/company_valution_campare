"""
技术分析模块
计算RSI、移动平均线偏离、布林带、52周位置等技术指标
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import yfinance as yf
from datetime import datetime, timedelta

from config import TECHNICAL_PARAMS


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    计算RSI指标
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict:
    """
    计算布林带
    """
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return {
        "upper": upper,
        "middle": sma,
        "lower": lower,
        "width": (upper - lower) / sma * 100  # 带宽百分比
    }


def calculate_ma_deviation(current_price: float, ma_value: float) -> float:
    """
    计算价格相对于均线的偏离百分比
    正数表示在均线上方，负数表示在均线下方
    """
    if ma_value is None or ma_value == 0:
        return 0
    return (current_price - ma_value) / ma_value * 100


def calculate_52week_position(current_price: float, week_52_high: float, week_52_low: float) -> float:
    """
    计算当前价格在52周范围内的位置 (0-100)
    0 = 52周最低点
    100 = 52周最高点
    """
    if week_52_high is None or week_52_low is None or week_52_high == week_52_low:
        return 50
    
    position = (current_price - week_52_low) / (week_52_high - week_52_low) * 100
    return max(0, min(100, position))


def get_technical_indicators(ticker: str) -> Dict:
    """
    获取单只股票的所有技术指标
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 获取价格历史
        hist = stock.history(period="1y")
        if hist.empty:
            return {}
        
        prices = hist['Close']
        current_price = prices.iloc[-1]
        
        # RSI
        rsi = calculate_rsi(prices, TECHNICAL_PARAMS['rsi_period'])
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
        
        # 布林带
        bb = calculate_bollinger_bands(prices, 
                                       TECHNICAL_PARAMS['bollinger_period'],
                                       TECHNICAL_PARAMS['bollinger_std'])
        bb_upper = bb['upper'].iloc[-1]
        bb_lower = bb['lower'].iloc[-1]
        bb_middle = bb['middle'].iloc[-1]
        bb_width = bb['width'].iloc[-1]
        
        # 计算价格在布林带中的位置 (0-100)
        if bb_upper != bb_lower:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) * 100
        else:
            bb_position = 50
        
        # 均线偏离
        ma_50 = info.get("fiftyDayAverage") or prices.rolling(50).mean().iloc[-1]
        ma_200 = info.get("twoHundredDayAverage") or prices.rolling(200).mean().iloc[-1]
        
        ma_50_dev = calculate_ma_deviation(current_price, ma_50)
        ma_200_dev = calculate_ma_deviation(current_price, ma_200)
        
        # 52周位置
        week_52_high = info.get("fiftyTwoWeekHigh", prices.max())
        week_52_low = info.get("fiftyTwoWeekLow", prices.min())
        week_52_position = calculate_52week_position(current_price, week_52_high, week_52_low)
        
        # 波动率 (20日)
        returns = prices.pct_change()
        volatility_20d = returns.rolling(20).std().iloc[-1] * np.sqrt(252) * 100  # 年化波动率
        
        # 动量指标
        momentum_1m = (current_price / prices.iloc[-21] - 1) * 100 if len(prices) > 21 else 0
        momentum_3m = (current_price / prices.iloc[-63] - 1) * 100 if len(prices) > 63 else 0
        
        # 成交量相对于20日均量
        if 'Volume' in hist.columns:
            volume = hist['Volume']
            vol_20_avg = volume.rolling(20).mean().iloc[-1]
            vol_ratio = volume.iloc[-1] / vol_20_avg if vol_20_avg > 0 else 1
        else:
            vol_ratio = 1
        
        return {
            "ticker": ticker,
            "current_price": current_price,
            "rsi": current_rsi,
            "rsi_signal": get_rsi_signal(current_rsi),
            "bb_position": bb_position,
            "bb_width": bb_width,
            "bb_signal": get_bb_signal(bb_position),
            "ma_50": ma_50,
            "ma_200": ma_200,
            "ma_50_dev": ma_50_dev,
            "ma_200_dev": ma_200_dev,
            "ma_signal": get_ma_signal(ma_50_dev, ma_200_dev),
            "week_52_high": week_52_high,
            "week_52_low": week_52_low,
            "week_52_position": week_52_position,
            "week_52_signal": get_52week_signal(week_52_position),
            "volatility_20d": volatility_20d,
            "momentum_1m": momentum_1m,
            "momentum_3m": momentum_3m,
            "volume_ratio": vol_ratio,
        }
        
    except Exception as e:
        print(f"Error calculating technicals for {ticker}: {e}")
        return {}


def get_rsi_signal(rsi: float) -> str:
    """
    根据RSI值返回信号
    """
    if rsi < 30:
        return "OVERSOLD"  # 超卖，可能底部
    elif rsi > 70:
        return "OVERBOUGHT"  # 超买，可能顶部
    elif rsi < 40:
        return "WEAK"
    elif rsi > 60:
        return "STRONG"
    else:
        return "NEUTRAL"


def get_bb_signal(bb_position: float) -> str:
    """
    根据布林带位置返回信号
    """
    if bb_position < 5:
        return "BELOW_LOWER"  # 跌破下轨，可能底部
    elif bb_position > 95:
        return "ABOVE_UPPER"  # 突破上轨，可能顶部
    elif bb_position < 20:
        return "NEAR_LOWER"
    elif bb_position > 80:
        return "NEAR_UPPER"
    else:
        return "MIDDLE"


def get_ma_signal(ma_50_dev: float, ma_200_dev: float) -> str:
    """
    根据均线偏离返回信号
    """
    # 价格远低于200MA = 可能底部
    if ma_200_dev < -20:
        return "FAR_BELOW_200MA"
    elif ma_200_dev > 30:
        return "FAR_ABOVE_200MA"
    elif ma_50_dev > 0 and ma_200_dev > 0:
        return "ABOVE_ALL_MA"
    elif ma_50_dev < 0 and ma_200_dev < 0:
        return "BELOW_ALL_MA"
    else:
        return "MIXED"


def get_52week_signal(position: float) -> str:
    """
    根据52周位置返回信号
    """
    if position < 10:
        return "NEAR_52W_LOW"  # 接近52周低点，可能底部
    elif position > 90:
        return "NEAR_52W_HIGH"  # 接近52周高点，可能顶部
    elif position < 30:
        return "LOWER_RANGE"
    elif position > 70:
        return "UPPER_RANGE"
    else:
        return "MIDDLE_RANGE"


def calculate_technical_score(indicators: Dict) -> Dict:
    """
    计算综合技术评分
    返回底部得分和顶部得分 (各0-100)
    
    底部信号（分数越高越像底部）:
    - RSI超卖
    - 布林带下轨附近
    - 远低于200MA
    - 接近52周低点
    
    顶部信号（分数越高越像顶部）:
    - RSI超买
    - 布林带上轨附近
    - 远高于200MA
    - 接近52周高点
    """
    if not indicators:
        return {"bottom_score": 50, "top_score": 50, "signal": "NO_DATA"}
    
    # 底部得分计算
    bottom_score = 0
    
    # RSI (0-30分)
    rsi = indicators.get('rsi', 50)
    if rsi < 30:
        bottom_score += 30
    elif rsi < 40:
        bottom_score += 20
    elif rsi < 50:
        bottom_score += 10
    
    # 布林带位置 (0-25分)
    bb_pos = indicators.get('bb_position', 50)
    if bb_pos < 5:
        bottom_score += 25
    elif bb_pos < 15:
        bottom_score += 20
    elif bb_pos < 25:
        bottom_score += 15
    elif bb_pos < 35:
        bottom_score += 10
    
    # 200MA偏离 (0-25分)
    ma_200_dev = indicators.get('ma_200_dev', 0)
    if ma_200_dev < -25:
        bottom_score += 25
    elif ma_200_dev < -15:
        bottom_score += 20
    elif ma_200_dev < -10:
        bottom_score += 15
    elif ma_200_dev < -5:
        bottom_score += 10
    
    # 52周位置 (0-20分)
    w52_pos = indicators.get('week_52_position', 50)
    if w52_pos < 10:
        bottom_score += 20
    elif w52_pos < 20:
        bottom_score += 15
    elif w52_pos < 30:
        bottom_score += 10
    
    # 顶部得分计算
    top_score = 0
    
    # RSI (0-30分)
    if rsi > 70:
        top_score += 30
    elif rsi > 60:
        top_score += 20
    elif rsi > 50:
        top_score += 10
    
    # 布林带位置 (0-25分)
    if bb_pos > 95:
        top_score += 25
    elif bb_pos > 85:
        top_score += 20
    elif bb_pos > 75:
        top_score += 15
    elif bb_pos > 65:
        top_score += 10
    
    # 200MA偏离 (0-25分)
    if ma_200_dev > 40:
        top_score += 25
    elif ma_200_dev > 30:
        top_score += 20
    elif ma_200_dev > 20:
        top_score += 15
    elif ma_200_dev > 10:
        top_score += 10
    
    # 52周位置 (0-20分)
    if w52_pos > 95:
        top_score += 20
    elif w52_pos > 85:
        top_score += 15
    elif w52_pos > 75:
        top_score += 10
    
    # 综合信号
    if bottom_score >= 70:
        signal = "STRONG_BOTTOM"
    elif bottom_score >= 50:
        signal = "POTENTIAL_BOTTOM"
    elif top_score >= 70:
        signal = "STRONG_TOP"
    elif top_score >= 50:
        signal = "POTENTIAL_TOP"
    else:
        signal = "NEUTRAL"
    
    return {
        "bottom_score": bottom_score,
        "top_score": top_score,
        "technical_signal": signal
    }


if __name__ == "__main__":
    # 测试
    print("Testing technical analysis module...")
    
    # 测试单只股票
    indicators = get_technical_indicators("NVDA")
    if indicators:
        print(f"\nNVDA Technical Indicators:")
        for k, v in indicators.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")
        
        # 计算技术评分
        score = calculate_technical_score(indicators)
        print(f"\nTechnical Scores:")
        for k, v in score.items():
            print(f"  {k}: {v}")
