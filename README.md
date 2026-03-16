# 📊 估值预警系统 (Valuation Alert System)

一个基于多因子模型的美股估值监控与预警系统，帮助你识别潜在的底部和顶部机会。

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

## 🎯 核心功能

### 1. 单股票分析仪表盘
- 估值指标：P/E、P/S、P/B、PEG、EV/EBITDA
- 历史分位数：当前估值在5年历史中的位置
- 同行比较：相对于可比公司的溢价/折价
- 技术指标：RSI、布林带、均线偏离、52周位置
- 综合评分：底部/顶部信号强度

### 2. 全市场扫描
- 200只精选美股批量扫描
- 自动识别底部和顶部候选
- 综合评分排名

### 3. 同业比较矩阵
- 按行业分类查看估值排名
- 识别行业内最便宜/最贵的股票

### 4. Telegram预警推送
- 强信号自动推送
- 支持Cloudflare Workers webhook

---

## 📦 安装

```bash
# 克隆或复制项目
cd valuation_monitor

# 安装依赖
pip install -r requirements.txt
```

---

## 🚀 使用方法

### 方式1: Streamlit Cloud 部署 (推荐)

1. **Fork/上传到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/你的用户名/valuation-monitor.git
   git push -u origin main
   ```

2. **部署到 Streamlit Cloud**
   - 访问 [share.streamlit.io](https://share.streamlit.io)
   - 用 GitHub 登录
   - 选择仓库 → Main file: `app.py` → Deploy

3. **配置 Secrets (Telegram推送)**
   - 在 Streamlit Cloud 后台 → App settings → Secrets
   - 添加:
   ```toml
   TELEGRAM_WEBHOOK_URL = "https://your-worker.workers.dev/webhook"
   ```

### 方式2: 本地启动Streamlit Web界面

```bash
cd valuation_monitor
streamlit run app.py
```

然后在浏览器打开 http://localhost:8501

### 方式2: 命令行定时扫描

```bash
# 基础扫描（打印结果，不发送推送）
python scheduled_scan.py --no-alerts

# 扫描并推送到Telegram
python scheduled_scan.py --webhook "https://your-worker.workers.dev/webhook"

# 只显示前5个候选
python scheduled_scan.py --top-n 5
```

### 方式3: 设置Cron定时任务

```bash
# 每个交易日 9:00 和 16:00 (美东时间) 扫描
# 编辑 crontab: crontab -e

# 美东9点 = UTC 14点 (夏令时13点)
0 14 * * 1-5 cd /path/to/valuation_monitor && python scheduled_scan.py --webhook "YOUR_WEBHOOK_URL"

# 美东16点 = UTC 21点 (夏令时20点)
0 21 * * 1-5 cd /path/to/valuation_monitor && python scheduled_scan.py --webhook "YOUR_WEBHOOK_URL"
```

---

## ⚙️ 配置

### 编辑 `config.py`

#### 1. Telegram推送配置

```python
# 使用Cloudflare Workers webhook (推荐)
TELEGRAM_WEBHOOK_URL = "https://your-worker.workers.dev/webhook"

# 或直接使用Bot Token
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
```

#### 2. 预警阈值

```python
ALERT_THRESHOLDS = {
    "bottom_score": 75,     # 综合分 > 75 触发底部预警
    "top_score": 25,        # 综合分 < 25 触发顶部预警
    "valuation_bottom": 70, # 估值分 > 70 才能触发底部
    "valuation_top": 30,    # 估值分 < 30 才能触发顶部
}
```

#### 3. 自定义Peer Groups

```python
PEER_GROUPS = {
    "NVDA": ["AMD", "INTC", "AVGO", "MRVL", "QCOM"],
    "TSLA": ["RIVN", "LCID", "NIO", "GM", "F"],
    # 添加你自己的定义...
}
```

#### 4. 股票池

```python
STOCK_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", ...
    # 编辑这个列表添加/删除股票
]
```

---

## 📊 评分系统说明

### 综合评分 (0-100)

分数越高，信号越强：
- **底部分 ≥ 75**: 强底部信号 🟢
- **底部分 50-75**: 潜在底部 🟡
- **顶部分 ≥ 75**: 强顶部信号 🔴
- **顶部分 50-75**: 潜在顶部 🟠

### 因子权重

| 因子 | 权重 | 说明 |
|-----|------|------|
| 估值因子 | 30% | PE/PS历史分位 + 同行比较 |
| 技术因子 | 25% | RSI + 布林带 + MA偏离 + 52周位置 |
| 动量因子 | 20% | 1月/3月价格动量 |
| 相对强度 | 15% | vs SPY/QQQ表现 |
| 波动率调整 | 10% | 高波动增强信号 |

### 底部信号触发条件

1. PE/PS历史分位 < 25%
2. 相对同行折价 > 15%
3. RSI < 40 (接近超卖)
4. 52周位置 < 30%
5. 价格低于200MA

### 顶部信号触发条件

1. PE/PS历史分位 > 75%
2. 相对同行溢价 > 25%
3. RSI > 60 (接近超买)
4. 52周位置 > 80%
5. 价格远高于200MA

---

## 📁 项目结构

```
valuation_monitor/
├── app.py                 # Streamlit主应用
├── config.py              # 配置文件（股票池、peer groups、阈值）
├── data_fetcher.py        # 数据获取模块 (yfinance)
├── valuation_analysis.py  # 估值分析模块
├── technical_analysis.py  # 技术分析模块
├── scoring.py             # 评分与预警模块
├── scheduled_scan.py      # 定时扫描脚本
├── requirements.txt       # 依赖
└── README.md              # 文档
```

---

## ⚠️ 注意事项

1. **数据延迟**: yfinance数据有约15分钟延迟，适合每日分析，不适合日内实时交易
2. **历史估值估算**: 由于yfinance免费版无法获取历史PE，系统使用价格变化来估算历史估值分位数，这是粗略估算
3. **API限制**: yfinance有调用频率限制，批量获取200只股票可能需要1-2分钟
4. **信号验证**: 本系统提供的是参考信号，不构成投资建议，请结合其他分析工具和自己的判断

---

## 🔄 后续增强 (Phase 2/3)

- [ ] 添加Insider交易数据 (OpenInsider爬取)
- [ ] 添加Short Interest数据
- [ ] 添加盈利修正数据 (需付费API)
- [ ] 添加机构持仓变化 (13F解析)
- [ ] 集成到TradingView Pine Script

---

## 📝 License

MIT License
