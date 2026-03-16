"""
定时扫描脚本
可以用cron或调度器定期运行，自动扫描并推送预警到Telegram

使用方法:
1. 配置 config.py 中的 TELEGRAM_WEBHOOK_URL
2. 运行: python scheduled_scan.py
3. 或设置cron: 0 9,16 * * 1-5 python /path/to/scheduled_scan.py

推荐扫描时间:
- 美东9:00 (开盘前) 
- 美东16:00 (收盘后)
"""

import sys
import os
from datetime import datetime
import argparse

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import STOCK_UNIVERSE, TELEGRAM_WEBHOOK_URL
from data_fetcher import batch_fetch_stocks
from technical_analysis import get_technical_indicators, calculate_technical_score
from valuation_analysis import get_full_valuation_analysis
from scoring import (
    calculate_composite_score,
    generate_alert_message,
    send_telegram_alert,
    scan_all_stocks,
    get_bottom_candidates,
    get_top_candidates,
    format_scan_summary
)


def run_scheduled_scan(webhook_url: str = None, send_alerts: bool = True, top_n: int = 10):
    """
    执行定时扫描
    
    Args:
        webhook_url: Telegram webhook URL
        send_alerts: 是否发送预警
        top_n: 显示前N个候选
    """
    print(f"\n{'='*60}")
    print(f"估值预警系统 - 定时扫描")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    if webhook_url is None:
        webhook_url = TELEGRAM_WEBHOOK_URL
    
    # 1. 获取所有股票数据
    print(f"📊 正在获取 {len(STOCK_UNIVERSE)} 只股票数据...")
    all_data = batch_fetch_stocks(STOCK_UNIVERSE, max_workers=15)
    
    if all_data.empty:
        print("❌ 数据获取失败")
        return
    
    print(f"✅ 成功获取 {len(all_data)} 只股票数据")
    
    # 2. 计算估值指标
    print("\n📈 正在计算估值指标...")
    valuation_results = {}
    for ticker in all_data['ticker'].unique():
        valuation_results[ticker] = get_full_valuation_analysis(ticker, all_data)
    
    # 3. 计算技术指标
    print("📉 正在计算技术指标...")
    technical_results = {}
    for ticker in all_data['ticker'].unique():
        tech = get_technical_indicators(ticker)
        if tech:
            tech_score = calculate_technical_score(tech)
            tech.update(tech_score)
            technical_results[ticker] = tech
    
    # 4. 综合评分
    print("🎯 正在生成综合评分...")
    scan_results = scan_all_stocks(all_data, valuation_results, technical_results)
    
    # 5. 获取候选
    bottom_candidates = get_bottom_candidates(scan_results, top_n)
    top_candidates = get_top_candidates(scan_results, top_n)
    
    # 6. 打印摘要
    summary = format_scan_summary(scan_results)
    print(f"\n{summary}")
    
    # 7. 打印底部候选
    print("\n" + "="*60)
    print("🟢 底部候选 (最可能触底)")
    print("="*60)
    
    if not bottom_candidates.empty:
        for _, row in bottom_candidates.iterrows():
            print(f"  {row['ticker']:6} | 底部分: {row['composite_bottom_score']:5.1f} | "
                  f"PE分位: {row['pe_percentile']:5.1f}% | RSI: {row['rsi']:5.1f} | "
                  f"52周位置: {row['week_52_position']:5.1f}%")
    else:
        print("  暂无明显底部信号")
    
    # 8. 打印顶部候选
    print("\n" + "="*60)
    print("🔴 顶部候选 (最可能见顶)")
    print("="*60)
    
    if not top_candidates.empty:
        for _, row in top_candidates.iterrows():
            print(f"  {row['ticker']:6} | 顶部分: {row['composite_top_score']:5.1f} | "
                  f"PE分位: {row['pe_percentile']:5.1f}% | RSI: {row['rsi']:5.1f} | "
                  f"52周位置: {row['week_52_position']:5.1f}%")
    else:
        print("  暂无明显顶部信号")
    
    # 9. 发送Telegram预警
    if send_alerts and webhook_url and webhook_url != "YOUR_CLOUDFLARE_WORKER_URL":
        print("\n📱 正在发送Telegram预警...")
        
        # 发送摘要
        send_telegram_alert(summary, webhook_url)
        
        # 发送强信号预警 (底部分 >= 75 或 顶部分 >= 75)
        alerts_sent = 0
        
        # 底部预警
        strong_bottom = scan_results[scan_results['composite_bottom_score'] >= 75]
        for _, row in strong_bottom.iterrows():
            ticker = row['ticker']
            val_result = valuation_results.get(ticker, {})
            tech_result = technical_results.get(ticker, {})
            composite = {
                'composite_bottom_score': row['composite_bottom_score'],
                'composite_top_score': row['composite_top_score'],
                'valuation_bottom_score': row['valuation_bottom_score'],
                'valuation_top_score': row['valuation_top_score'],
                'technical_bottom_score': row['technical_bottom_score'],
                'technical_top_score': row['technical_top_score'],
                'momentum_bottom_score': row['momentum_bottom_score'],
                'momentum_top_score': row['momentum_top_score'],
                'alert_type': 'STRONG_BOTTOM'
            }
            
            msg = generate_alert_message(ticker, val_result, tech_result, composite)
            if msg:
                send_telegram_alert(msg, webhook_url)
                alerts_sent += 1
        
        # 顶部预警
        strong_top = scan_results[scan_results['composite_top_score'] >= 75]
        for _, row in strong_top.iterrows():
            ticker = row['ticker']
            val_result = valuation_results.get(ticker, {})
            tech_result = technical_results.get(ticker, {})
            composite = {
                'composite_bottom_score': row['composite_bottom_score'],
                'composite_top_score': row['composite_top_score'],
                'valuation_bottom_score': row['valuation_bottom_score'],
                'valuation_top_score': row['valuation_top_score'],
                'technical_bottom_score': row['technical_bottom_score'],
                'technical_top_score': row['technical_top_score'],
                'momentum_bottom_score': row['momentum_bottom_score'],
                'momentum_top_score': row['momentum_top_score'],
                'alert_type': 'STRONG_TOP'
            }
            
            msg = generate_alert_message(ticker, val_result, tech_result, composite)
            if msg:
                send_telegram_alert(msg, webhook_url)
                alerts_sent += 1
        
        print(f"✅ 已发送 {alerts_sent} 个预警")
    else:
        print("\n⚠️ Telegram推送未配置或已禁用")
    
    print(f"\n{'='*60}")
    print(f"扫描完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    return scan_results


def main():
    parser = argparse.ArgumentParser(description='估值预警系统 - 定时扫描')
    parser.add_argument('--webhook', type=str, help='Telegram Webhook URL')
    parser.add_argument('--no-alerts', action='store_true', help='禁用Telegram推送')
    parser.add_argument('--top-n', type=int, default=10, help='显示前N个候选 (默认: 10)')
    
    args = parser.parse_args()
    
    run_scheduled_scan(
        webhook_url=args.webhook,
        send_alerts=not args.no_alerts,
        top_n=args.top_n
    )


if __name__ == "__main__":
    main()
