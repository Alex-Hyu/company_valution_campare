"""
估值解读模块
将数字转化为可理解的分析文本、评级和操作建议
"""

from typing import Dict, Optional, List, Tuple
import pandas as pd


# ============================================
# 评级定义
# ============================================
RATING_LEVELS = {
    "VERY_CHEAP": {"emoji": "🟢", "label": "极度低估", "action": "重仓机会"},
    "CHEAP": {"emoji": "🟢", "label": "低估", "action": "分批建仓"},
    "FAIR_LOW": {"emoji": "🟡", "label": "合理偏低", "action": "可以买入"},
    "FAIR": {"emoji": "⚪", "label": "合理", "action": "持有观望"},
    "FAIR_HIGH": {"emoji": "🟡", "label": "合理偏高", "action": "谨慎持有"},
    "EXPENSIVE": {"emoji": "🟠", "label": "高估", "action": "考虑减仓"},
    "VERY_EXPENSIVE": {"emoji": "🔴", "label": "极度高估", "action": "建议清仓"},
    "NO_DATA": {"emoji": "⚫", "label": "数据不足", "action": "无法判断"},
}


def get_percentile_rating(percentile: float) -> str:
    """根据历史分位数返回评级"""
    if percentile is None:
        return "NO_DATA"
    if percentile < 10:
        return "VERY_CHEAP"
    elif percentile < 25:
        return "CHEAP"
    elif percentile < 40:
        return "FAIR_LOW"
    elif percentile < 60:
        return "FAIR"
    elif percentile < 75:
        return "FAIR_HIGH"
    elif percentile < 90:
        return "EXPENSIVE"
    else:
        return "VERY_EXPENSIVE"


def get_peer_rating(premium_pct: float) -> str:
    """根据同行溢价/折价返回评级"""
    if premium_pct is None:
        return "NO_DATA"
    if premium_pct < -30:
        return "VERY_CHEAP"
    elif premium_pct < -15:
        return "CHEAP"
    elif premium_pct < -5:
        return "FAIR_LOW"
    elif premium_pct < 10:
        return "FAIR"
    elif premium_pct < 25:
        return "FAIR_HIGH"
    elif premium_pct < 40:
        return "EXPENSIVE"
    else:
        return "VERY_EXPENSIVE"


def get_peg_rating(peg: float) -> str:
    """根据PEG返回评级"""
    if peg is None or peg <= 0:
        return "NO_DATA"
    if peg < 0.5:
        return "VERY_CHEAP"
    elif peg < 0.8:
        return "CHEAP"
    elif peg < 1.0:
        return "FAIR_LOW"
    elif peg < 1.5:
        return "FAIR"
    elif peg < 2.0:
        return "FAIR_HIGH"
    elif peg < 3.0:
        return "EXPENSIVE"
    else:
        return "VERY_EXPENSIVE"


def get_52week_rating(position: float) -> str:
    """根据52周位置返回评级"""
    if position is None:
        return "NO_DATA"
    if position < 10:
        return "VERY_CHEAP"
    elif position < 25:
        return "CHEAP"
    elif position < 40:
        return "FAIR_LOW"
    elif position < 60:
        return "FAIR"
    elif position < 75:
        return "FAIR_HIGH"
    elif position < 90:
        return "EXPENSIVE"
    else:
        return "VERY_EXPENSIVE"


def generate_rating_table(valuation: Dict, technical: Dict) -> List[Dict]:
    """
    生成分档评级表
    返回各维度的评级列表
    """
    ratings = []
    
    # 1. P/E历史分位
    pe_pct = valuation.get('pe_percentile')
    pe_rating = get_percentile_rating(pe_pct)
    ratings.append({
        "dimension": "P/E历史分位",
        "value": f"{pe_pct:.0f}%" if pe_pct else "N/A",
        "rating": pe_rating,
        **RATING_LEVELS.get(pe_rating, RATING_LEVELS["NO_DATA"])
    })
    
    # 2. P/S历史分位
    ps_pct = valuation.get('ps_percentile')
    ps_rating = get_percentile_rating(ps_pct)
    ratings.append({
        "dimension": "P/S历史分位",
        "value": f"{ps_pct:.0f}%" if ps_pct else "N/A",
        "rating": ps_rating,
        **RATING_LEVELS.get(ps_rating, RATING_LEVELS["NO_DATA"])
    })
    
    # 3. 同行比较
    peer_premium = valuation.get('pe_vs_peers_pct', 0)
    peer_rating = get_peer_rating(peer_premium)
    premium_str = f"{peer_premium:+.1f}%" if peer_premium else "N/A"
    ratings.append({
        "dimension": "vs同行P/E",
        "value": premium_str,
        "rating": peer_rating,
        **RATING_LEVELS.get(peer_rating, RATING_LEVELS["NO_DATA"])
    })
    
    # 4. PEG
    peg = valuation.get('peg')
    peg_rating = get_peg_rating(peg)
    ratings.append({
        "dimension": "PEG增长匹配",
        "value": f"{peg:.2f}" if peg else "N/A",
        "rating": peg_rating,
        **RATING_LEVELS.get(peg_rating, RATING_LEVELS["NO_DATA"])
    })
    
    # 5. 52周位置
    w52_pos = technical.get('week_52_position')
    w52_rating = get_52week_rating(w52_pos)
    ratings.append({
        "dimension": "52周位置",
        "value": f"{w52_pos:.0f}%" if w52_pos else "N/A",
        "rating": w52_rating,
        **RATING_LEVELS.get(w52_rating, RATING_LEVELS["NO_DATA"])
    })
    
    return ratings


def calculate_price_targets(
    current_price: float,
    current_pe: float,
    pe_5y_median: float = None,
    pe_5y_25pct: float = None,
    pe_5y_75pct: float = None,
    peer_pe_median: float = None,
    pe_forward: float = None
) -> List[Dict]:
    """
    计算不同情景下的目标价位
    基于P/E均值回归
    """
    if not current_price or not current_pe or current_pe <= 0:
        return []
    
    # 每股盈利 (反推)
    eps = current_price / current_pe
    
    targets = []
    
    # 情景1: 回归5年中位数
    if pe_5y_median and pe_5y_median > 0:
        target_price = eps * pe_5y_median
        change_pct = (target_price / current_price - 1) * 100
        targets.append({
            "scenario": "回归历史中位数",
            "target_pe": pe_5y_median,
            "target_price": target_price,
            "change_pct": change_pct,
            "description": f"P/E回到5年中位数{pe_5y_median:.1f}x"
        })
    
    # 情景2: 跌到25%分位 (悲观)
    if pe_5y_25pct and pe_5y_25pct > 0:
        target_price = eps * pe_5y_25pct
        change_pct = (target_price / current_price - 1) * 100
        targets.append({
            "scenario": "悲观情景",
            "target_pe": pe_5y_25pct,
            "target_price": target_price,
            "change_pct": change_pct,
            "description": f"P/E跌到历史25%分位{pe_5y_25pct:.1f}x"
        })
    
    # 情景3: 涨到75%分位 (乐观)
    if pe_5y_75pct and pe_5y_75pct > 0:
        target_price = eps * pe_5y_75pct
        change_pct = (target_price / current_price - 1) * 100
        targets.append({
            "scenario": "乐观情景",
            "target_pe": pe_5y_75pct,
            "target_price": target_price,
            "change_pct": change_pct,
            "description": f"P/E涨到历史75%分位{pe_5y_75pct:.1f}x"
        })
    
    # 情景4: 回归同行中位数
    if peer_pe_median and peer_pe_median > 0:
        target_price = eps * peer_pe_median
        change_pct = (target_price / current_price - 1) * 100
        targets.append({
            "scenario": "回归同行水平",
            "target_pe": peer_pe_median,
            "target_price": target_price,
            "change_pct": change_pct,
            "description": f"P/E回到同行中位数{peer_pe_median:.1f}x"
        })
    
    # 情景5: 基于Forward P/E (如果盈利预期实现)
    if pe_forward and pe_forward > 0 and pe_forward != current_pe:
        # 假设未来EPS = current_price / pe_forward
        future_eps = current_price / pe_forward
        # 如果给予当前P/E倍数
        target_price = future_eps * current_pe
        change_pct = (target_price / current_price - 1) * 100
        targets.append({
            "scenario": "盈利预期实现",
            "target_pe": current_pe,
            "target_price": target_price,
            "change_pct": change_pct,
            "description": f"若盈利增长{((current_pe/pe_forward-1)*100):.0f}%实现，维持当前P/E"
        })
    
    return targets


def generate_price_levels(
    current_price: float,
    current_pe: float,
    pe_5y_min: float = None,
    pe_5y_max: float = None,
    pe_5y_median: float = None
) -> List[Dict]:
    """
    生成买卖点参考表
    """
    if not current_price or not current_pe or current_pe <= 0:
        return []
    
    eps = current_price / current_pe
    
    levels = []
    
    # 定义P/E区间和对应操作
    pe_ranges = [
        {"label": "极度低估", "pe_range": (0, 15), "action": "🟢 重仓", "color": "green"},
        {"label": "低估", "pe_range": (15, 25), "action": "🟢 建仓", "color": "lightgreen"},
        {"label": "合理偏低", "pe_range": (25, 35), "action": "🟡 分批买", "color": "yellow"},
        {"label": "合理", "pe_range": (35, 50), "action": "⚪ 持有", "color": "white"},
        {"label": "偏高", "pe_range": (50, 70), "action": "🟠 减仓", "color": "orange"},
        {"label": "高估", "pe_range": (70, 100), "action": "🔴 清仓", "color": "red"},
    ]
    
    # 根据历史数据动态调整区间
    if pe_5y_min and pe_5y_max and pe_5y_median:
        pe_range_width = pe_5y_max - pe_5y_min
        pe_ranges = [
            {"label": "极度低估", "pe_range": (0, pe_5y_min), 
             "action": "🟢 重仓", "color": "green"},
            {"label": "低估", "pe_range": (pe_5y_min, pe_5y_min + pe_range_width * 0.25), 
             "action": "🟢 建仓", "color": "lightgreen"},
            {"label": "合理偏低", "pe_range": (pe_5y_min + pe_range_width * 0.25, pe_5y_median), 
             "action": "🟡 分批买", "color": "yellow"},
            {"label": "合理", "pe_range": (pe_5y_median, pe_5y_median + pe_range_width * 0.25), 
             "action": "⚪ 持有", "color": "white"},
            {"label": "偏高", "pe_range": (pe_5y_median + pe_range_width * 0.25, pe_5y_max), 
             "action": "🟠 减仓", "color": "orange"},
            {"label": "高估", "pe_range": (pe_5y_max, pe_5y_max * 1.5), 
             "action": "🔴 清仓", "color": "red"},
        ]
    
    for range_def in pe_ranges:
        pe_low, pe_high = range_def["pe_range"]
        price_low = eps * pe_low if pe_low > 0 else 0
        price_high = eps * pe_high
        
        # 判断当前价格是否在这个区间
        is_current = pe_low <= current_pe < pe_high
        
        levels.append({
            "label": range_def["label"],
            "pe_range": f"{pe_low:.0f}-{pe_high:.0f}x",
            "price_range": f"${price_low:.0f}-${price_high:.0f}",
            "action": range_def["action"],
            "is_current": is_current
        })
    
    return levels


def generate_valuation_interpretation(
    ticker: str,
    valuation: Dict,
    technical: Dict
) -> str:
    """
    生成智能估值解读文本
    一段话说清楚当前估值状态
    """
    name = valuation.get('name', ticker)
    price = valuation.get('price', 0)
    
    # 获取关键数据
    pe_ttm = valuation.get('pe_ttm')
    pe_forward = valuation.get('pe_forward')
    pe_pct = valuation.get('pe_percentile', 50)
    ps_pct = valuation.get('ps_percentile', 50)
    pe_vs_peers = valuation.get('pe_vs_peers_pct', 0)
    peg = valuation.get('peg')
    w52_pos = technical.get('week_52_position', 50)
    
    # 构建解读
    paragraphs = []
    
    # ===== 第一段：当前估值位置 =====
    pe_str = f"{pe_ttm:.1f}x" if pe_ttm else "N/A"
    
    if pe_pct < 20:
        position_desc = "处于5年历史**极低位置**，属于罕见的低估区间"
        position_emoji = "🟢"
    elif pe_pct < 40:
        position_desc = "处于5年历史**偏低位置**，估值有一定吸引力"
        position_emoji = "🟢"
    elif pe_pct < 60:
        position_desc = "处于5年历史**中间位置**，估值较为合理"
        position_emoji = "⚪"
    elif pe_pct < 80:
        position_desc = "处于5年历史**偏高位置**，估值偏贵"
        position_emoji = "🟠"
    else:
        position_desc = "处于5年历史**极高位置**，估值昂贵需警惕"
        position_emoji = "🔴"
    
    para1 = f"{position_emoji} **{name}** 当前P/E {pe_str}，{position_desc}（{pe_pct:.0f}%分位）。"
    paragraphs.append(para1)
    
    # ===== 第二段：Forward P/E分析（如果有） =====
    if pe_forward and pe_ttm and pe_forward > 0 and pe_ttm > 0:
        growth_implied = (pe_ttm / pe_forward - 1) * 100
        if growth_implied > 20:
            para2 = f"📈 Forward P/E {pe_forward:.1f}x 显著低于TTM，市场预期盈利增长**{growth_implied:.0f}%**。"
            if peg and peg < 1:
                para2 += f" PEG={peg:.2f}<1，**增长速度可以支撑当前估值**。"
            elif peg and peg < 1.5:
                para2 += f" PEG={peg:.2f}，增长与估值基本匹配。"
            elif peg and peg >= 1.5:
                para2 += f" 但PEG={peg:.2f}>1.5，**估值已透支部分增长预期**。"
        elif growth_implied < -10:
            para2 = f"⚠️ Forward P/E {pe_forward:.1f}x 高于TTM，市场预期盈利**下滑{-growth_implied:.0f}%**，需警惕。"
        else:
            para2 = f"Forward P/E {pe_forward:.1f}x 与TTM接近，盈利预期平稳。"
        paragraphs.append(para2)
    
    # ===== 第三段：同行比较 =====
    if pe_vs_peers != 0:
        if pe_vs_peers > 30:
            peer_desc = f"⚠️ 相比同行**溢价{pe_vs_peers:.0f}%**，估值明显偏高。除非有显著竞争优势，否则溢价难以持续。"
        elif pe_vs_peers > 10:
            peer_desc = f"相比同行溢价{pe_vs_peers:.0f}%，如果是行业龙头，适度溢价合理。"
        elif pe_vs_peers > -10:
            peer_desc = f"与同行估值水平接近（{pe_vs_peers:+.0f}%），定价合理。"
        elif pe_vs_peers > -25:
            peer_desc = f"🟢 相比同行**折价{-pe_vs_peers:.0f}%**，可能被低估。"
        else:
            peer_desc = f"🟢 相比同行**大幅折价{-pe_vs_peers:.0f}%**，值得深入研究是否有隐藏问题或被错杀。"
        paragraphs.append(peer_desc)
    
    # ===== 第四段：技术位置 =====
    if w52_pos < 15:
        tech_desc = f"📍 股价接近52周低点（{w52_pos:.0f}%位置），技术面超卖。"
    elif w52_pos < 30:
        tech_desc = f"📍 股价处于52周偏低位置（{w52_pos:.0f}%），有反弹空间。"
    elif w52_pos > 90:
        tech_desc = f"📍 股价接近52周高点（{w52_pos:.0f}%位置），追高风险大。"
    elif w52_pos > 75:
        tech_desc = f"📍 股价处于52周偏高位置（{w52_pos:.0f}%），上行空间有限。"
    else:
        tech_desc = ""
    
    if tech_desc:
        paragraphs.append(tech_desc)
    
    # ===== 第五段：综合结论 =====
    # 综合评分
    score = 0
    if pe_pct < 30: score += 2
    elif pe_pct < 50: score += 1
    elif pe_pct > 70: score -= 1
    elif pe_pct > 85: score -= 2
    
    if pe_vs_peers < -15: score += 1
    elif pe_vs_peers > 25: score -= 1
    
    if peg and peg < 1: score += 1
    elif peg and peg > 2: score -= 1
    
    if w52_pos < 25: score += 1
    elif w52_pos > 80: score -= 1
    
    if score >= 3:
        conclusion = "🟢 **结论：估值具有吸引力，可考虑建仓或加仓。**"
    elif score >= 1:
        conclusion = "🟡 **结论：估值合理偏低，可逢低分批买入。**"
    elif score >= -1:
        conclusion = "⚪ **结论：估值中性，建议持有观望，等待更好机会。**"
    elif score >= -3:
        conclusion = "🟠 **结论：估值偏高，不建议追涨，可考虑减仓。**"
    else:
        conclusion = "🔴 **结论：估值过高风险大，建议规避或清仓。**"
    
    paragraphs.append(conclusion)
    
    return "\n\n".join(paragraphs)


def generate_warning_alerts(valuation: Dict, technical: Dict) -> List[str]:
    """
    生成关键风险提示
    """
    alerts = []
    
    pe_ttm = valuation.get('pe_ttm')
    pe_forward = valuation.get('pe_forward')
    pe_pct = valuation.get('pe_percentile', 50)
    peg = valuation.get('peg')
    w52_pos = technical.get('week_52_position', 50)
    rsi = technical.get('rsi', 50)
    ma_200_dev = technical.get('ma_200_dev', 0)
    
    # P/E TTM vs Forward 差距大
    if pe_ttm and pe_forward and pe_forward > 0:
        growth_implied = (pe_ttm / pe_forward - 1) * 100
        if growth_implied > 40:
            alerts.append(f"⚠️ 市场预期盈利增长{growth_implied:.0f}%，**业绩miss风险大**，一旦不及预期可能大跌")
    
    # 历史高位
    if pe_pct > 85:
        alerts.append(f"⚠️ P/E处于历史{pe_pct:.0f}%分位，**不建议追高**")
    
    # PEG过高
    if peg and peg > 2.5:
        alerts.append(f"⚠️ PEG={peg:.1f}，估值已严重透支增长预期")
    
    # 接近52周高点
    if w52_pos > 95:
        alerts.append(f"⚠️ 股价接近52周高点，**技术面回调压力大**")
    
    # RSI超买
    if rsi > 70:
        alerts.append(f"⚠️ RSI={rsi:.0f}超买，短期可能回调")
    
    # 远高于200MA
    if ma_200_dev > 30:
        alerts.append(f"⚠️ 股价高于200日均线{ma_200_dev:.0f}%，偏离过大")
    
    # 正面提示
    if pe_pct < 15:
        alerts.append(f"🟢 P/E处于历史{pe_pct:.0f}%分位，罕见低估机会")
    
    if w52_pos < 10:
        alerts.append(f"🟢 接近52周低点，可能是错杀或底部")
    
    if rsi < 30:
        alerts.append(f"🟢 RSI={rsi:.0f}超卖，短期可能反弹")
    
    return alerts


def get_overall_rating(valuation: Dict, technical: Dict) -> Dict:
    """
    计算综合评级
    """
    ratings = generate_rating_table(valuation, technical)
    
    # 计算评级得分
    rating_scores = {
        "VERY_CHEAP": 3,
        "CHEAP": 2,
        "FAIR_LOW": 1,
        "FAIR": 0,
        "FAIR_HIGH": -1,
        "EXPENSIVE": -2,
        "VERY_EXPENSIVE": -3,
        "NO_DATA": 0
    }
    
    total_score = 0
    valid_count = 0
    
    for r in ratings:
        rating = r.get('rating', 'NO_DATA')
        if rating != 'NO_DATA':
            total_score += rating_scores.get(rating, 0)
            valid_count += 1
    
    if valid_count == 0:
        avg_score = 0
    else:
        avg_score = total_score / valid_count
    
    # 转换为综合评级
    if avg_score >= 2:
        overall = "VERY_CHEAP"
    elif avg_score >= 1:
        overall = "CHEAP"
    elif avg_score >= 0.3:
        overall = "FAIR_LOW"
    elif avg_score >= -0.3:
        overall = "FAIR"
    elif avg_score >= -1:
        overall = "FAIR_HIGH"
    elif avg_score >= -2:
        overall = "EXPENSIVE"
    else:
        overall = "VERY_EXPENSIVE"
    
    return {
        "overall_rating": overall,
        "score": avg_score,
        **RATING_LEVELS.get(overall, RATING_LEVELS["NO_DATA"])
    }


if __name__ == "__main__":
    # 测试
    valuation = {
        "ticker": "NVDA",
        "name": "NVIDIA Corp",
        "price": 120,
        "pe_ttm": 45,
        "pe_forward": 28,
        "pe_percentile": 78,
        "ps_percentile": 65,
        "pe_vs_peers_pct": 15,
        "peg": 0.9,
        "pe_5y_min": 20,
        "pe_5y_max": 80,
        "pe_5y_median": 40,
        "pe_5y_25pct": 28,
        "pe_5y_75pct": 55,
        "peer_pe_median": 38
    }
    
    technical = {
        "week_52_position": 72,
        "rsi": 58,
        "ma_200_dev": 12
    }
    
    print("=" * 60)
    print("智能估值解读")
    print("=" * 60)
    interpretation = generate_valuation_interpretation("NVDA", valuation, technical)
    print(interpretation)
    
    print("\n" + "=" * 60)
    print("分档评级表")
    print("=" * 60)
    ratings = generate_rating_table(valuation, technical)
    for r in ratings:
        print(f"{r['emoji']} {r['dimension']}: {r['value']} → {r['label']}")
    
    print("\n" + "=" * 60)
    print("风险提示")
    print("=" * 60)
    alerts = generate_warning_alerts(valuation, technical)
    for a in alerts:
        print(a)
    
    print("\n" + "=" * 60)
    print("目标价位")
    print("=" * 60)
    targets = calculate_price_targets(
        current_price=120,
        current_pe=45,
        pe_5y_median=40,
        pe_5y_25pct=28,
        pe_5y_75pct=55,
        peer_pe_median=38,
        pe_forward=28
    )
    for t in targets:
        print(f"{t['scenario']}: ${t['target_price']:.0f} ({t['change_pct']:+.0f}%) - {t['description']}")
    
    print("\n" + "=" * 60)
    print("买卖点参考")
    print("=" * 60)
    levels = generate_price_levels(120, 45, 20, 80, 40)
    for l in levels:
        current_mark = " ← 当前" if l['is_current'] else ""
        print(f"{l['action']} {l['label']}: P/E {l['pe_range']} = {l['price_range']}{current_mark}")
